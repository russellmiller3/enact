"""
Access control policies — role and identity restrictions.

These policies answer the question: "Is this actor *allowed* to do this action?"
They are complementary to CRM and time policies, which answer "Is this action
*safe* to do right now?" Access policies run before the workflow so a contractor
or viewer role can never accidentally trigger a restricted operation.

Role and clearance information is read from either context.payload (legacy
require_actor_role, contractor_cannot_write_pii) or context.user_attributes
(new require_user_role, require_clearance_for_path). Prefer user_attributes
for new policies.
Enact does not verify identities — it enforces decisions based on what it's told.

Payload keys used by this module
----------------------------------
  "actor_role"  — string role of the actor (e.g. "admin", "engineer", "contractor")
  "pii_fields"  — list of field names considered PII (contractor_cannot_write_pii)
  "data"        — dict of fields being written (contractor_cannot_write_pii)
  "path"        — file path being accessed (dont_read_sensitive_paths, require_clearance_for_path)
  "table"       — DB table being accessed (dont_read_sensitive_tables)

user_attributes keys used by this module
------------------------------------------
  "role"            — actor role string (require_user_role)
  "clearance_level" — int clearance level, defaults to 0 if absent (require_clearance_for_path)
"""
from pathlib import PurePosixPath
from enact.models import WorkflowContext, PolicyResult


def contractor_cannot_write_pii(context: WorkflowContext) -> PolicyResult:
    """
    Block contractors from writing to any field marked as PII.

    Reads three payload keys:
      - "actor_role"  — must be "contractor" to trigger the block
      - "pii_fields"  — list of field names the caller considers PII (e.g. ["ssn", "dob"])
      - "data"        — the dict being written; checked for any key in pii_fields

    If the actor is a contractor AND the data dict contains any key from
    pii_fields, the run is blocked. Any other combination passes through.

    This design puts the definition of "PII" in the hands of the caller —
    different workflows can have different PII field lists without changing
    this policy function.

    Args:
        context — WorkflowContext; reads payload keys listed above

    Returns:
        PolicyResult — passed=False only if role is "contractor" AND data
                       contains at least one PII field
    """
    actor_role = context.payload.get("actor_role", "")
    pii_fields = context.payload.get("pii_fields", [])
    # any() short-circuits — stops at first PII field found in data
    writing_pii = any(f in context.payload.get("data", {}) for f in pii_fields)

    if actor_role == "contractor" and writing_pii:
        return PolicyResult(
            policy="contractor_cannot_write_pii",
            passed=False,
            reason="Contractors cannot write to PII fields",
        )
    return PolicyResult(
        policy="contractor_cannot_write_pii",
        passed=True,
        reason="No PII violation",
    )


def require_actor_role(allowed_roles: list[str]):
    """
    Factory: return a policy that requires the actor to have one of the allowed roles.

    Use this to restrict a workflow to specific roles:

        EnactClient(policies=[require_actor_role(["admin", "engineer"])])

    Reads context.payload.get("actor_role", "unknown"). If the role is absent
    from the payload it defaults to "unknown", which will fail this check for
    any non-empty allowed_roles list. This is intentional — an unidentified
    actor should not be able to run restricted workflows.

    Args:
        allowed_roles — list of role strings that are permitted (e.g. ["admin", "engineer"])

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """

    def _policy(context: WorkflowContext) -> PolicyResult:
        # Default to "unknown" so missing actor_role fails the check
        actor_role = context.payload.get("actor_role", "unknown")
        passed = actor_role in allowed_roles
        return PolicyResult(
            policy="require_actor_role",
            passed=passed,
            reason=(
                f"Role '{actor_role}' not in allowed roles: {allowed_roles}"
                if not passed
                else f"Role '{actor_role}' is authorized"
            ),
        )

    return _policy


def _is_under(target: PurePosixPath, prefix: PurePosixPath) -> bool:
    """Return True if target is under prefix (or equals it)."""
    try:
        target.relative_to(prefix)
        return True
    except ValueError:
        return False


def dont_read_sensitive_tables(tables: list[str]):
    """
    Factory: block select_rows when the target table is in the sensitive list.

    Reads context.payload.get("table", ""). Pass-through if no table in payload.
    Exact, case-sensitive match — same convention as protect_tables in db.py.

    Args:
        tables — list of table name strings to protect from reads

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """
    sensitive_tables = set(tables)

    def _policy(context: WorkflowContext) -> PolicyResult:
        table = context.payload.get("table", "")
        if not table:
            return PolicyResult(
                policy="dont_read_sensitive_tables",
                passed=True,
                reason="No table specified in payload",
            )
        if table in sensitive_tables:
            return PolicyResult(
                policy="dont_read_sensitive_tables",
                passed=False,
                reason=f"Table '{table}' is sensitive — read access not permitted",
            )
        return PolicyResult(
            policy="dont_read_sensitive_tables",
            passed=True,
            reason=f"Table '{table}' is not sensitive",
        )

    return _policy


def dont_read_sensitive_paths(paths: list[str]):
    """
    Factory: block read_file when the target path is under a sensitive directory.

    Uses PurePosixPath.relative_to() for prefix matching — '/etchosts' does NOT
    match the '/etc' prefix, only paths genuinely under '/etc/' do.

    Reads context.payload.get("path", ""). Pass-through if no path in payload.

    Args:
        paths — list of directory prefixes to protect (e.g. ["/etc", "/root"])

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """

    def _policy(context: WorkflowContext) -> PolicyResult:
        path = context.payload.get("path", "")
        if not path:
            return PolicyResult(
                policy="dont_read_sensitive_paths",
                passed=True,
                reason="No path specified in payload",
            )
        target = PurePosixPath(path)
        for sensitive in paths:
            if _is_under(target, PurePosixPath(sensitive)):
                return PolicyResult(
                    policy="dont_read_sensitive_paths",
                    passed=False,
                    reason=f"Path '{path}' is under sensitive prefix '{sensitive}' — read access not permitted",
                )
        return PolicyResult(
            policy="dont_read_sensitive_paths",
            passed=True,
            reason=f"Path '{path}' is not under any sensitive prefix",
        )

    return _policy


def require_clearance_for_path(paths: list[str], min_clearance: int):
    """
    ABAC factory: block access to paths under sensitive prefixes unless the actor
    has the required clearance level.

    Reads context.user_attributes.get("clearance_level", 0). Missing clearance
    defaults to 0 — an unidentified actor has no clearance. Paths not under any
    sensitive prefix pass through regardless of clearance level.

    Args:
        paths         — list of directory prefixes requiring elevated clearance
        min_clearance — minimum clearance_level required (integer)

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """

    def _policy(context: WorkflowContext) -> PolicyResult:
        path = context.payload.get("path", "")
        if not path:
            return PolicyResult(
                policy="require_clearance_for_path",
                passed=True,
                reason="No path specified in payload",
            )
        target = PurePosixPath(path)
        under_sensitive = any(
            _is_under(target, PurePosixPath(p)) for p in paths
        )
        if not under_sensitive:
            return PolicyResult(
                policy="require_clearance_for_path",
                passed=True,
                reason=f"Path '{path}' does not require elevated clearance",
            )
        clearance = context.user_attributes.get("clearance_level", 0)
        if clearance < min_clearance:
            return PolicyResult(
                policy="require_clearance_for_path",
                passed=False,
                reason=(
                    f"Clearance level {clearance} insufficient for path '{path}' "
                    f"(requires {min_clearance})"
                ),
            )
        return PolicyResult(
            policy="require_clearance_for_path",
            passed=True,
            reason=f"Clearance level {clearance} meets requirement of {min_clearance}",
        )

    return _policy


def require_user_role(*allowed_roles: str):
    """
    ABAC factory: block if the actor's role is not in the allowed set.

    Reads context.user_attributes.get("role", "unknown"). Missing role defaults
    to "unknown" — an unidentified actor fails any non-empty role check.

    Prefer this over require_actor_role for new code — it reads from
    user_attributes (structured identity context) rather than payload.

    Args:
        *allowed_roles — role strings that are permitted (e.g. "admin", "engineer")

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """
    allowed = set(allowed_roles)

    def _policy(context: WorkflowContext) -> PolicyResult:
        role = context.user_attributes.get("role", "unknown")
        passed = role in allowed
        return PolicyResult(
            policy="require_user_role",
            passed=passed,
            reason=(
                f"Role '{role}' not in allowed roles: {sorted(allowed)}"
                if not passed
                else f"Role '{role}' is authorized"
            ),
        )

    return _policy
