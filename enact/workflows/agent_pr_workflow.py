"""
Reference workflow: Agent creates a branch and opens a PR (never pushes to main directly).
"""
from enact.models import WorkflowContext, ActionResult


def agent_pr_workflow(context: WorkflowContext) -> list[ActionResult]:
    """Create branch → open PR. Never push to main directly."""
    gh = context.systems["github"]
    repo = context.payload["repo"]
    branch = context.payload["branch"]
    title = context.payload.get("title", f"Agent PR: {branch}")
    body = context.payload.get("body", "Automated PR created by AI agent via Enact")

    results = []

    # Step 1: Create branch
    branch_result = gh.create_branch(repo=repo, branch=branch)
    results.append(branch_result)
    if not branch_result.success:
        return results

    # Step 2: Open PR
    pr_result = gh.create_pr(repo=repo, title=title, body=body, head=branch)
    results.append(pr_result)
    return results
