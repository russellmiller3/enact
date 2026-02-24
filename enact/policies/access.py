"""
Access policies — role and identity restrictions.
"""
from enact.models import WorkflowContext, PolicyResult


def contractor_cannot_write_pii(context: WorkflowContext) -> PolicyResult:
    """Block contractors from writing to PII fields."""
    actor_role = context.payload.get("actor_role", "")
    pii_fields = context.payload.get("pii_fields", [])
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
    """Factory: returns a policy requiring the actor to have one of the allowed roles."""

    def _policy(context: WorkflowContext) -> PolicyResult:
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
