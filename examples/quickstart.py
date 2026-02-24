"""
Enact quickstart — matches the README example.

Usage:
    pip install -e ".[dev]"
    python examples/quickstart.py
"""
from enact import EnactClient
from enact.models import WorkflowContext, PolicyResult, ActionResult


# --- Define a simple policy ---

def require_email_in_payload(context: WorkflowContext) -> PolicyResult:
    has_email = "email" in context.payload
    return PolicyResult(
        policy="require_email",
        passed=has_email,
        reason="Email present" if has_email else "Missing email in payload",
    )


# --- Define a simple workflow ---

def hello_workflow(context: WorkflowContext) -> list[ActionResult]:
    """A demo workflow that just returns a greeting."""
    email = context.payload["email"]
    return [
        ActionResult(
            action="greet",
            system="demo",
            success=True,
            output={"message": f"Hello, {email}!"},
        )
    ]


# --- Wire it up ---

enact = EnactClient(
    policies=[require_email_in_payload],
    workflows=[hello_workflow],
    receipt_dir="receipts",
)

# Run with valid payload → PASS
print("=== Run 1: Valid payload ===")
result, receipt = enact.run(
    workflow="hello_workflow",
    actor_email="agent@company.com",
    payload={"email": "jane@acme.com"},
)
print(f"Success:   {result.success}")
print(f"Output:    {result.output}")
print(f"Decision:  {receipt.decision}")
print(f"Signature: {receipt.signature[:16]}...")
print()

# Run without email → BLOCK
print("=== Run 2: Missing email ===")
result, receipt = enact.run(
    workflow="hello_workflow",
    actor_email="agent@company.com",
    payload={"name": "Jane"},
)
print(f"Success:  {result.success}")
print(f"Decision: {receipt.decision}")
print("Policy results:")
for pr in receipt.policy_results:
    status = "PASS" if pr.passed else "FAIL"
    print(f"  [{status}] {pr.policy}: {pr.reason}")
