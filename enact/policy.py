"""
Policy engine — runs all registered policies against a WorkflowContext.
Never bails early. Always runs every check.
"""
from enact.models import WorkflowContext, PolicyResult


def evaluate_all(
    context: WorkflowContext,
    policies: list,
) -> list[PolicyResult]:
    """
    Run every policy function against the context.
    Each policy is a callable: (WorkflowContext) -> PolicyResult
    Returns list of ALL results — never short-circuits.
    """
    results = []
    for policy_fn in policies:
        result = policy_fn(context)
        results.append(result)
    return results


def all_passed(results: list[PolicyResult]) -> bool:
    """Check if every policy passed."""
    return all(r.passed for r in results)
