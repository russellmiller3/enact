"""
CRM policies — prevent bad CRM operations before they reach the connector.

Policies in this module may call connector methods (live lookups) because
they run *before* the workflow executes. For example, no_duplicate_contacts
checks HubSpot for an existing contact before the workflow creates one.
This is the correct place for pre-flight checks — not inside the workflow.

If the required system (e.g. "hubspot") is not registered in the client,
policies in this module pass through gracefully rather than raising.
This makes them safe to register even when a connector is not yet wired up.

Payload keys used by this module
----------------------------------
  "email"             — contact email address (no_duplicate_contacts)
  "recent_task_count" — integer hint set by the caller (limit_tasks_per_contact v1)

v1 limitation of limit_tasks_per_contact
------------------------------------------
The v1 implementation reads a "recent_task_count" hint from the payload rather
than querying HubSpot directly. The caller (or a preceding workflow step) is
responsible for computing this value. A future version will query the HubSpot
engagements API directly.
"""
from enact.models import WorkflowContext, PolicyResult


def no_duplicate_contacts(context: WorkflowContext) -> PolicyResult:
    """
    Block creating a contact that already exists in HubSpot.

    Performs a live lookup via context.systems["hubspot"].get_contact(email)
    before the workflow runs. If the contact is found, the run is blocked.

    Passes through (does not block) if:
    - No "email" key in the payload (nothing to check)
    - No "hubspot" system registered (connector not wired up)
    - get_contact returns found=False or success=False

    This fail-open behaviour for missing systems means you can register the
    policy on a client that doesn't yet have HubSpot configured without
    causing every run to fail.

    Args:
        context — WorkflowContext; reads context.payload["email"] and
                  context.systems.get("hubspot")

    Returns:
        PolicyResult — passed=False if contact already exists in HubSpot
    """
    email = context.payload.get("email")
    if not email:
        # No email in payload — nothing to deduplicate; pass through
        return PolicyResult(
            policy="no_duplicate_contacts",
            passed=True,
            reason="No email in payload to check",
        )

    hubspot = context.systems.get("hubspot")
    if not hubspot:
        # Connector not registered — can't check; pass through rather than fail
        return PolicyResult(
            policy="no_duplicate_contacts",
            passed=True,
            reason="No HubSpot system registered",
        )

    result = hubspot.get_contact(email)
    if result.success and result.output.get("found"):
        # Contact exists — block the run
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
    """
    Factory: return a policy that limits how many tasks an agent creates per contact.

    Prevents an agent from spamming a contact with follow-up tasks by enforcing
    a rate limit over a rolling time window.

    v1 implementation note: reads context.payload["recent_task_count"] as a hint
    rather than querying HubSpot directly. The caller should pre-compute this
    value (e.g. from a prior select step) before calling enact.run(). If the
    key is absent, defaults to 0 and always passes.

    Args:
        max_tasks    — maximum tasks allowed in the window (exclusive); default 3
        window_days  — length of the time window in days (informational in v1); default 7

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """

    def _policy(context: WorkflowContext) -> PolicyResult:
        # v1: hint-based check. The workflow or caller sets this before run().
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
