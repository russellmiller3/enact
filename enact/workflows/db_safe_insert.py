"""
Reference workflow: Safe database insert with constraint checking.
"""
from enact.models import WorkflowContext, ActionResult


def db_safe_insert(context: WorkflowContext) -> list[ActionResult]:
    """Insert a row into a Postgres table after checking constraints."""
    pg = context.systems["postgres"]
    table = context.payload["table"]
    data = context.payload["data"]

    # Step 1: Check if row already exists (if unique_key provided)
    results = []
    unique_key = context.payload.get("unique_key")
    if unique_key and unique_key in data:
        check = pg.select_rows(table, where={unique_key: data[unique_key]})
        results.append(check)
        if check.success and check.output.get("rows"):
            # Row exists — return early with info
            return results + [
                ActionResult(
                    action="insert_row",
                    system="postgres",
                    success=False,
                    output={"error": f"Row with {unique_key}={data[unique_key]} already exists"},
                )
            ]

    # Step 2: Insert the row
    insert_result = pg.insert_row(table, data)
    results.append(insert_result)
    return results
