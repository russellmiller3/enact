"""
Reference workflow: Safe database insert with duplicate constraint checking.

This workflow demonstrates the two-step "check then act" pattern:
  1. If a unique_key is provided, check whether the row already exists
  2. If it exists, abort with an explanatory ActionResult rather than
     letting the database raise a constraint violation
  3. If it doesn't exist (or no unique_key was given), insert the row

Why check in the workflow rather than in a policy?
---------------------------------------------------
Policies run before the workflow and answer "is this action allowed?"
Duplicate checks are workflow-level logic because they require inspecting
the specific data being inserted — something policies don't have deep
context about. The dont_duplicate_contacts CRM policy is an exception
(it's a pre-flight check on email) but the general "does this exact row
exist?" question belongs here.

Expected payload shape
-----------------------
    {
        "table":      str,    # required — e.g. "users"
        "data":       dict,   # required — column/value pairs to insert
        "unique_key": str,    # optional — if set, deduplication is performed on this column
    }

Expected systems
-----------------
    context.systems["postgres"] — a PostgresConnector instance (or any object
    with .select_rows(table, where) and .insert_row(table, data) methods
    returning ActionResult objects). In tests this is a MagicMock.
"""
from enact.models import WorkflowContext, ActionResult


def db_safe_insert(context: WorkflowContext) -> list[ActionResult]:
    """
    Insert a row into a Postgres table after an optional duplicate check.

    Returns a list of ActionResults representing each step taken. The caller
    (and the receipt) can inspect this list to understand exactly what happened:
    - [select_rows, insert_row(success=False)] → duplicate found, insert skipped
    - [select_rows, insert_row(success=True)]  → no duplicate, row inserted
    - [insert_row(success=True)]               → no unique_key, inserted directly
    - [insert_row(success=False)]              → DB error, insert failed

    Args:
        context — WorkflowContext with systems["postgres"] and payload keys above

    Returns:
        list[ActionResult] — one or two results depending on deduplication path
    """
    pg = context.systems["postgres"]
    table = context.payload["table"]
    data = context.payload["data"]

    results = []

    # Step 1: Duplicate check — only if unique_key is provided AND present in data
    unique_key = context.payload.get("unique_key")
    if unique_key and unique_key in data:
        # Query for an existing row matching the unique key value
        check = pg.select_rows(table, where={unique_key: data[unique_key]})
        results.append(check)

        if check.success and check.output.get("rows"):
            # Duplicate found — return an explanatory failure rather than attempting
            # the insert (which would hit a DB constraint and produce a less useful error)
            return results + [
                ActionResult(
                    action="insert_row",
                    system="postgres",
                    success=False,
                    output={"error": f"Row with {unique_key}={data[unique_key]} already exists"},
                )
            ]

    # Step 2: No duplicate (or no unique_key) — proceed with the insert
    insert_result = pg.insert_row(table, data)
    results.append(insert_result)
    return results
