"""
Reference workflow: Agent creates a branch and opens a PR.

This is the canonical "safe agent git workflow" — an agent should never push
directly to main. Instead: create a feature branch, do the work there, and
open a PR for human review. Pair this workflow with the no_push_to_main
and require_branch_prefix policies for full enforcement:

    EnactClient(
        systems={"github": GitHubConnector(token=...)},
        policies=[no_push_to_main, require_branch_prefix("agent/")],
        workflows=[agent_pr_workflow],
    )

Early-exit on branch creation failure
---------------------------------------
If create_branch fails (e.g. the branch already exists, or a permissions error),
the workflow returns immediately without attempting create_pr. This prevents a
dangling PR that references a branch that doesn't exist. The receipt will show
one failed ActionResult with the error details.

Expected payload shape
-----------------------
    {
        "repo":   str,  # required — "owner/repo" string
        "branch": str,  # required — new branch name (e.g. "agent/fix-123")
        "title":  str,  # optional — PR title; defaults to "Agent PR: <branch>"
        "body":   str,  # optional — PR body; defaults to a standard agent message
    }

Expected systems
-----------------
    context.systems["github"] — a GitHubConnector instance with create_branch
    and create_pr in its allowlist.
"""
from enact.models import WorkflowContext, ActionResult


def agent_pr_workflow(context: WorkflowContext) -> list[ActionResult]:
    """
    Create a branch then open a pull request. Stop if the branch step fails.

    Returns a list of ActionResults — either one (if branch creation failed)
    or two (branch + PR, regardless of PR success).

    Args:
        context — WorkflowContext with systems["github"] and payload keys above

    Returns:
        list[ActionResult] — [create_branch] or [create_branch, create_pr]
    """
    gh = context.systems["github"]
    repo = context.payload["repo"]
    branch = context.payload["branch"]
    # Use caller-provided title/body or fall back to sensible defaults
    title = context.payload.get("title", f"Agent PR: {branch}")
    body = context.payload.get("body", "Automated PR created by AI agent via Enact")

    results = []

    # Step 1: Create the branch — abort if this fails (no point opening a PR
    # against a branch that doesn't exist)
    branch_result = gh.create_branch(repo=repo, branch=branch)
    results.append(branch_result)
    if not branch_result.success:
        return results  # Early exit — receipt will show the branch failure

    # Step 2: Open the PR from branch → main
    pr_result = gh.create_pr(repo=repo, title=title, body=body, head=branch)
    results.append(pr_result)
    return results
