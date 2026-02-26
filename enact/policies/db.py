"""
Database safety policies — prevent dangerous Postgres operations by AI agents.

These policies answer the question: "Is this database operation safe to perform?"
They complement access.py (who can act) and time.py (when can they act).

All policies in this module are pure functions over WorkflowContext — no DB
connections are made. Workflows are responsible for putting the relevant fields
in the payload so policies can inspect intent before execution:

  payload["table"]  — table name (protect_tables)
  payload["where"]  — filter dict (dont_delete_without_where, dont_update_without_where)
  payload["data"]   — row data being written (informational)

Sentinel policies
------------------
dont_delete_row is a sentinel — it always blocks regardless of payload. Register it
on a client where row deletion should never happen, not on a client that has
legitimate delete workflows. This mirrors how firewall rules work: the rule
applies to all traffic through this client, not just specific operations.

Factory pattern
----------------
protect_tables is a factory (same pattern as max_files_per_commit in git.py).
Call it with the list of protected tables at init time; it returns a closure:

    EnactClient(policies=[
        protect_tables(["users", "payments", "orders"]),
        dont_delete_without_where,
    ])

Payload convention
------------------
"where" mirrors the `where` parameter on connector methods:
  delete_row(table, where)   — the where dict the workflow will use
  update_row(table, data, where) — same

Workflows should populate these keys in the payload before calling enact.run()
so policies can inspect them. This is the same convention as file_count in
max_files_per_commit — the workflow sets the context, the policy reads it.
"""
import re
from enact.models import WorkflowContext, PolicyResult


def dont_delete_row(context: WorkflowContext) -> PolicyResult:
    """
    Block all row deletion on this client — regardless of table or WHERE clause.

    Sentinel policy: register this on any client where delete_row should never
    run. Useful for read-mostly agents that should only query and insert, never
    delete. No payload keys are read — the block is unconditional.

    Args:
        context — WorkflowContext (payload not inspected)

    Returns:
        PolicyResult — always passed=False
    """
    return PolicyResult(
        policy="dont_delete_row",
        passed=False,
        reason="Row deletion is not permitted on this client",
    )


def dont_delete_without_where(context: WorkflowContext) -> PolicyResult:
    """
    Block delete_row operations that lack a WHERE clause.

    Reads context.payload.get("where", {}). An empty or missing where dict
    means the workflow intends to delete ALL rows in the table — the database
    equivalent of rm -rf. This policy requires at least one filter condition.

    Allows deletes through when where contains at least one key-value pair.
    Passes through (does not block) if the workflow legitimately needs no
    where filter — register dont_delete_row instead if deletion must be banned.

    Payload keys:
        "where" — dict of {column: value} filter conditions. Empty or missing → block.

    Args:
        context — WorkflowContext; reads context.payload.get("where", {})

    Returns:
        PolicyResult — passed=False if where is empty or absent
    """
    where = context.payload.get("where")
    if not where:
        return PolicyResult(
            policy="dont_delete_without_where",
            passed=False,
            reason=(
                "delete_row blocked: where clause is required to prevent deleting all rows. "
                "Set payload['where'] to a non-empty filter dict."
            ),
        )
    return PolicyResult(
        policy="dont_delete_without_where",
        passed=True,
        reason=f"WHERE clause present with {len(where)} condition(s)",
    )


def dont_update_without_where(context: WorkflowContext) -> PolicyResult:
    """
    Block update_row operations that lack a WHERE clause.

    Reads context.payload.get("where", {}). An empty or missing where dict
    means the workflow intends to update ALL rows in the table — silently
    overwriting every record with the new values.

    Payload keys:
        "where" — dict of {column: value} filter conditions. Empty or missing → block.

    Args:
        context — WorkflowContext; reads context.payload.get("where", {})

    Returns:
        PolicyResult — passed=False if where is empty or absent
    """
    where = context.payload.get("where")
    if not where:
        return PolicyResult(
            policy="dont_update_without_where",
            passed=False,
            reason=(
                "update_row blocked: where clause is required to prevent updating all rows. "
                "Set payload['where'] to a non-empty filter dict."
            ),
        )
    return PolicyResult(
        policy="dont_update_without_where",
        passed=True,
        reason=f"WHERE clause present with {len(where)} condition(s)",
    )


def protect_tables(protected: list[str]):
    """
    Factory: return a policy that blocks any operation targeting a protected table.

    Use to prevent agents from reading or modifying high-stakes tables. The check
    is exact-match and case-sensitive — "users" and "Users" are different tables.
    If no table is specified in the payload, the policy passes through (can't block
    what it can't see).

    Example:
        EnactClient(policies=[protect_tables(["users", "payments", "audit_log"])])

    Payload keys:
        "table" — the table name the workflow intends to operate on.

    Args:
        protected — list of table name strings to block (exact, case-sensitive match)

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """
    protected_set = set(protected)

    def _policy(context: WorkflowContext) -> PolicyResult:
        table = context.payload.get("table", "")
        if not table:
            # No table in payload — pass through (can't determine target)
            return PolicyResult(
                policy="protect_tables",
                passed=True,
                reason="No table specified in payload",
            )
        if table in protected_set:
            return PolicyResult(
                policy="protect_tables",
                passed=False,
                reason=f"Table '{table}' is protected — operations not permitted",
            )
        return PolicyResult(
            policy="protect_tables",
            passed=True,
            reason=f"Table '{table}' is not protected",
        )

    return _policy


# DDL keywords that should never appear in agent-executed SQL.
# Use bare verbs (DROP, ALTER, CREATE) rather than qualified forms (ALTER TABLE,
# CREATE TABLE) so that all variants are caught: DROP VIEW, ALTER SEQUENCE,
# CREATE FUNCTION, CREATE TRIGGER, etc.
# \b word boundaries prevent matching column names like "created_at" or "creator".
_DDL_KEYWORDS = ("DROP", "TRUNCATE", "ALTER", "CREATE")
_DDL_PATTERN = re.compile(
    r'\b(?:' + '|'.join(re.escape(k) for k in _DDL_KEYWORDS) + r')\b'
)


def block_ddl(context: WorkflowContext) -> PolicyResult:
    """
    Block any operation that contains DDL keywords in payload["sql"] or payload["action"].

    Sentinel policy — register on any client where schema changes must never happen.
    The Replit database deletion incident (July 2025) was triggered by a schema push
    (`npm run db:push`). This policy is the Enact equivalent: if an agent tries to
    run DROP, TRUNCATE, ALTER TABLE, or CREATE TABLE, it gets blocked before firing.

    Detection uses word-boundary regex (\\b) so "SELECT 1;DROP TABLE" is caught even
    without a leading space before DROP. Case-insensitive (input is uppercased first).
    The policy passes through if neither "sql" nor "action" is present in the payload.

    Payload keys:
        "sql"    — raw SQL string (checked for DDL keywords)
        "action" — action string (checked for DDL keywords as fallback)

    Args:
        context — WorkflowContext; reads payload["sql"] and payload["action"]

    Returns:
        PolicyResult — passed=False if any DDL keyword is found
    """
    candidates = [
        context.payload.get("sql", ""),
        context.payload.get("action", ""),
    ]
    for text in candidates:
        if not text:
            continue
        upper = text.strip().upper()
        match = _DDL_PATTERN.search(upper)
        if match:
            return PolicyResult(
                policy="block_ddl",
                passed=False,
                reason=f"DDL statement blocked: '{match.group(0)}' is not permitted",
            )
    return PolicyResult(
        policy="block_ddl",
        passed=True,
        reason="No DDL keywords detected",
    )
