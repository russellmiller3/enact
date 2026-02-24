"""
CRM policies — prevent bad CRM operations.
"""
from enact.models import WorkflowContext, PolicyResult


def no_duplicate_contacts(context: WorkflowContext) -> PolicyResult:
    """Block creating a contact that already exists."""
    email = context.payload.get("email")
    if not email:
        return PolicyResult(
            policy="no_duplicate_contacts",
            passed=True,
            reason="No email in payload to check",
        )

    hubspot = context.systems.get("hubspot")
    if not hubspot:
        return PolicyResult(
            policy="no_duplicate_contacts",
            passed=True,
            reason="No HubSpot system registered",
        )

    result = hubspot.get_contact(email)
    if result.success and result.output.get("found"):
        return PolicyResult(
            policy="no_duplicate_contacts",
            passed=False,
            reason=f"Contact {email} already exists (id={result.output.get('id')})",
        )
    return PolicyResult(
        policy="no_duplicate_contacts",
        passed=True,
        reason=f"No existing contact for {email}",
    )


def limit_tasks_per_contact(max_tasks: int = 3, window_days: int = 7):
    """Factory: returns a policy limiting task creation per contact."""

    def _policy(context: WorkflowContext) -> PolicyResult:
        # In v1, this checks the payload for a task_count hint
        task_count = context.payload.get("recent_task_count", 0)
        passed = task_count < max_tasks
        return PolicyResult(
            policy="limit_tasks_per_contact",
            passed=passed,
            reason=(
                f"Contact has {task_count} tasks in last {window_days} days (max {max_tasks})"
                if not passed
                else f"Task count {task_count} within limit"
            ),
        )

    return _policy
