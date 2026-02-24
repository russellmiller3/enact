"""
Policy engine — runs all registered policies against a WorkflowContext.

Design decision: NEVER bail early.
------------------------------------
Even when the first policy fails, every remaining policy still runs. This
is intentional and important for two reasons:

1. Audit completeness — the Receipt should show ALL the reasons an action was
   blocked, not just the first one. If three policies fail, the operator needs
   to see all three to fix the problem in one pass.

2. No hidden failures — a policy that only runs "if nothing has failed yet"
   gives a false sense of security. Unconditional evaluation means the test
   suite can verify each policy in isolation without worrying about
   evaluation order or early-exit interactions.

Policy callable interface
--------------------------
Every policy is a plain Python callable with this signature:

    def my_policy(context: WorkflowContext) -> PolicyResult:
        ...

Factory policies (those that take configuration parameters) return a closure
with the same signature:

    def max_files_per_commit(max_files: int = 50):
        def _policy(context: WorkflowContext) -> PolicyResult:
            ...
        return _policy

The factory is called once at EnactClient init time (e.g. max_files_per_commit(10)),
and the returned closure is stored and called on every subsequent run.
This pattern lets policies carry configuration without needing classes.
"""
from enact.models import WorkflowContext, PolicyResult


def evaluate_all(
    context: WorkflowContext,
    policies: list,
) -> list[PolicyResult]:
    """
    Run every policy function against the context. Return ALL results.

    The returned list has one PolicyResult per policy, in the same order
    the policies were registered. Never short-circuits — even if the first
    policy fails, all remaining policies still execute.

    Args:
        context   — the WorkflowContext built from the caller's run() args;
                    passed unchanged to every policy function
        policies  — list of policy callables, each (WorkflowContext) -> PolicyResult;
                    may be a mix of plain functions and factory-produced closures

    Returns:
        list[PolicyResult] — one result per policy, in registration order;
                             empty list if no policies are registered
    """
    results = []
    for policy_fn in policies:
        result = policy_fn(context)
        results.append(result)
    return results


def all_passed(results: list[PolicyResult]) -> bool:
    """
    Return True only if every PolicyResult has passed=True.

    Used by EnactClient.run() to determine the PASS/BLOCK decision after
    evaluate_all() has run. A single False is enough to block the run.

    Empty list behaviour: returns True. A client with no policies registered
    allows all workflows through — the registered-workflow allowlist (checked
    before policies run) still applies as a first line of defence.

    Args:
        results — list returned by evaluate_all()

    Returns:
        bool — True if all passed (or list is empty), False if any failed
    """
    return all(r.passed for r in results)
