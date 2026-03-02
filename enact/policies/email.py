"""
Email policies — prevent email abuse before the workflow sends.

Policies in this module check the payload of email-sending workflows
to enforce rules like "no mass emails" and "no repeat emails".

Payload keys used by this module
----------------------------------
  "to"      — recipient email address (str) or list of addresses (list[str])
  "subject" — email subject line (used for repeat detection)
"""
from enact.models import WorkflowContext, PolicyResult


def no_mass_emails(context: WorkflowContext) -> PolicyResult:
    """
    Block emails with more than one recipient.

    Prevents agents from sending mass emails by enforcing a 1:1 ratio.
    If "to" is a list with more than 1 element, the run is blocked.

    Passes through (does not block) if:
    - No "to" key in the payload (nothing to check)
    - "to" is a single string (one recipient)
    - "to" is a list with exactly 1 element

    Args:
        context — WorkflowContext; reads context.payload["to"]

    Returns:
        PolicyResult — passed=False if more than 1 recipient
    """
    to = context.payload.get("to")
    if not to:
        # No recipient — nothing to check; pass through
        return PolicyResult(
            policy="no_mass_emails",
            passed=True,
            reason="No recipient in payload to check",
        )

    # Count recipients
    if isinstance(to, str):
        recipient_count = 1
    elif isinstance(to, list):
        recipient_count = len(to)
    else:
        # Unexpected type — pass through (fail open)
        return PolicyResult(
            policy="no_mass_emails",
            passed=True,
            reason=f"Unexpected 'to' type: {type(to).__name__}",
        )

    if recipient_count > 1:
        return PolicyResult(
            policy="no_mass_emails",
            passed=False,
            reason=f"Mass email blocked: {recipient_count} recipients (max 1)",
        )

    return PolicyResult(
        policy="no_mass_emails",
        passed=True,
        reason=f"Single recipient: {to if isinstance(to, str) else to[0]}",
    )


def no_repeat_emails(context: WorkflowContext) -> PolicyResult:
    """
    Block repeat emails to the same recipient within a time window.

    Prevents agents from spamming the same person with multiple emails.
    Uses a hint-based approach: the caller sets `recently_emailed` in the
    payload before calling enact.run().

    HINT-BASED APPROACH (default):
        The caller is responsible for checking their own receipts/storage
        to determine if this recipient was recently emailed. Set the hint:

            payload = {
                "to": "alice@example.com",
                "recently_emailed": True,  # Caller computed this
            }

        This matches the pattern used by limit_tasks_per_contact.

    DB-BACKED APPROACH (Enact Cloud only):
        If you're using Enact Cloud, you can query the receipts table directly
        instead of computing the hint. See the commented implementation below.

    Passes through (does not block) if:
    - No "to" key in the payload (nothing to check)
    - No "recently_emailed" key in the payload (hint not provided)

    Args:
        context — WorkflowContext; reads context.payload["to"] and
                  context.payload["recently_emailed"]

    Returns:
        PolicyResult — passed=False if recently_emailed is True
    """
    to = context.payload.get("to")
    if not to:
        return PolicyResult(
            policy="no_repeat_emails",
            passed=True,
            reason="No recipient in payload to check",
        )

    # Normalize recipient to string for the reason message
    recipient = to if isinstance(to, str) else (to[0] if to else "unknown")

    # Hint-based check: caller sets recently_emailed before run()
    recently_emailed = context.payload.get("recently_emailed", False)
    if recently_emailed:
        return PolicyResult(
            policy="no_repeat_emails",
            passed=False,
            reason=f"Repeat email blocked: {recipient} was emailed recently",
        )

    return PolicyResult(
        policy="no_repeat_emails",
        passed=True,
        reason=f"No recent email to {recipient}",
    )


# -----------------------------------------------------------------------------
# DB-BACKED IMPLEMENTATION (Enact Cloud only)
# -----------------------------------------------------------------------------
# If you're using Enact Cloud, you can query the receipts table directly
# instead of computing the hint. Uncomment and use this version:
#
# def no_repeat_emails_db(
#     window_hours: int = 24,
#     workflow_name: str = "send_email",  # Adjust to your email workflow name
# ):
#     """
#     Factory: return a policy that queries the receipts table for recent emails.
#
#     Requires: Enact Cloud with DB access. The receipts table stores full
#     receipt_json which includes the payload.to field.
#
#     Args:
#         window_hours  — how far back to check for repeat emails; default 24
#         workflow_name — name of the email-sending workflow to filter on
#
#     Returns:
#         callable — (WorkflowContext) -> PolicyResult
#     """
#     from cloud.db import db
#     import json
#
#     def _policy(context: WorkflowContext) -> PolicyResult:
#         to = context.payload.get("to")
#         if not to:
#             return PolicyResult(
#                 policy="no_repeat_emails",
#                 passed=True,
#                 reason="No recipient in payload to check",
#             )
#
#         recipient = to if isinstance(to, str) else (to[0] if to else "unknown")
#
#         with db() as conn:
#             cursor = conn.execute(
#                 """
#                 SELECT run_id FROM receipts
#                 WHERE workflow = ?
#                 AND decision = 'ALLOW'
#                 AND created_at > datetime('now', ?)
#                 AND receipt_json LIKE ?
#                 LIMIT 1
#                 """,
#                 (workflow_name, f"-{window_hours} hours", f'%{recipient}%'),
#             )
#             found = cursor.fetchone()
#
#         if found:
#             return PolicyResult(
#                 policy="no_repeat_emails",
#                 passed=False,
#                 reason=f"Repeat email blocked: {recipient} emailed in last {window_hours}h",
#             )
#
#         return PolicyResult(
#             policy="no_repeat_emails",
#             passed=True,
#             reason=f"No recent email to {recipient}",
#         )
#
#     return _policy