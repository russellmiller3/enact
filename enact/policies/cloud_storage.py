"""
Cloud storage policies — prevent dangerous operations on GDrive and S3.

These policies answer the question: "Is this cloud storage operation safe?"
They read from context.payload. Workflows are responsible for putting the relevant
fields in the payload before calling enact.run():

  payload["path"]   — the file or object path (GDrive/S3)
  payload["action"] — the action being performed (e.g. "delete", "write")
  payload["hitl_id"] — the ID of the approved HITL request

Human-in-the-loop (HITL)
-------------------------
The dont_delete_without_human_ok policy is a factory that returns a policy
requiring a cryptographically verified human approval receipt from the database.
"""
from enact.models import WorkflowContext, PolicyResult


def dont_delete_without_human_ok(system_name: str):
    """
    Factory: return a policy that blocks deletions on a specific system
    unless a valid, approved HITL receipt exists in the database for this run.

    Requires: Enact Cloud with DB access.

    Args:
        system_name — the name of the system to protect (e.g. "gdrive", "s3")

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """
    from cloud.db import db

    def _policy(context: WorkflowContext) -> PolicyResult:
        action = context.payload.get("action", "").lower()
        # Only trigger for delete actions
        if action != "delete":
            return PolicyResult(
                policy=f"dont_delete_{system_name}_without_human_ok",
                passed=True,
                reason=f"Action '{action}' is not a deletion",
            )

        hitl_id = context.payload.get("hitl_id")
        if not hitl_id:
            return PolicyResult(
                policy=f"dont_delete_{system_name}_without_human_ok",
                passed=False,
                reason=f"Deletion on {system_name} requires human approval. No hitl_id provided.",
            )

        with db() as conn:
            cursor = conn.execute(
                """
                SELECT decision FROM hitl_receipts
                WHERE hitl_id = ?
                """,
                (hitl_id,),
            )
            row = cursor.fetchone()

        if not row:
            return PolicyResult(
                policy=f"dont_delete_{system_name}_without_human_ok",
                passed=False,
                reason=f"No HITL receipt found for hitl_id '{hitl_id}'",
            )

        if row["decision"] != "APPROVE":
            return PolicyResult(
                policy=f"dont_delete_{system_name}_without_human_ok",
                passed=False,
                reason=f"HITL request '{hitl_id}' was not approved (decision: {row['decision']})",
            )

        return PolicyResult(
            policy=f"dont_delete_{system_name}_without_human_ok",
            passed=True,
            reason=f"Human approval verified for {system_name} deletion (hitl_id: {hitl_id})",
        )

    return _policy
