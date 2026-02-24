"""
Access control policies — role and identity restrictions.

These policies answer the question: "Is this actor *allowed* to do this action?"
They are complementary to CRM and time policies, which answer "Is this action
*safe* to do right now?" Access policies run before the workflow so a contractor
or viewer role can never accidentally trigger a restricted operation.

All role information is read from context.payload rather than from a database.
The caller (or a preceding auth middleware) is responsible for setting
context.payload["actor_role"] to the authenticated role before calling run().
Enact does not verify identities — it enforces decisions based on what it's told.

Payload keys used by this module
----------------------------------
  "actor_role"  — string role of the actor (e.g. "admin", "engineer", "contractor")
  "pii_fields"  — list of field names considered PII (contractor_cannot_write_pii)
  "data"        — dict of fields being written (contractor_cannot_write_pii)
"""
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
