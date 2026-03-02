"""
Cloud storage policies — prevent dangerous operations on GDrive and S3.

These policies answer the question: "Is this cloud storage operation safe?"
They read from context.payload. Workflows are responsible for putting the relevant
fields in the payload before calling enact.run():

  payload["path"]   — the file or object path (GDrive/S3)
  payload["action"] — the action being performed (e.g. "delete", "write")

Human-in-the-loop (HITL)
-------------------------
The dont_delete_without_human_ok policy is a factory that returns a policy
requiring a human approval hint for any deletion.
"""
from enact.models import WorkflowContext, PolicyResult


def dont_delete_without_human_ok(system_name: str):
    """
    Factory: return a policy that blocks deletions on a specific system
    unless a human approval hint is present in the payload.

    This is a "soft" HITL gate. It doesn't trigger the HITL workflow itself,
    but it ensures that the workflow *must* have gone through a HITL gate
    (setting the hint) before this policy will pass.

    Args:
        system_name — the name of the system to protect (e.g. "gdrive", "s3")

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """

    def _policy(context: WorkflowContext) -> PolicyResult:
        action = context.payload.get("action", "").lower()
        # Only trigger for delete actions
        if action != "delete":
            return PolicyResult(
                policy=f"dont_delete_{system_name}_without_human_ok",
                passed=True,
                reason=f"Action '{action}' is not a deletion",
            )

        # Check for human approval hint
        human_ok = context.payload.get("human_ok", False)
        if not human_ok:
            return PolicyResult(
                policy=f"dont_delete_{system_name}_without_human_ok",
                passed=False,
                reason=f"Deletion on {system_name} requires human approval. Set payload['human_ok']=True.",
            )

        return PolicyResult(
            policy=f"dont_delete_{system_name}_without_human_ok",
            passed=True,
            reason=f"Human approval verified for {system_name} deletion",
        )

    return _policy
