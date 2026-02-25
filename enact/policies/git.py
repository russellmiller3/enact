"""
Git policies — prevent dangerous git operations by AI agents.

All policies in this module read from context.payload. The workflow calling
enact.run() is responsible for putting the relevant fields in the payload
before the run (e.g. "branch", "file_count"). Policies never call external
APIs — they are pure functions over the context.

Factory pattern
----------------
max_files_per_commit and require_branch_prefix are factory functions rather
than plain policy functions. They accept configuration parameters and return
a closure that satisfies the policy callable interface:

    (WorkflowContext) -> PolicyResult

This lets callers configure policies inline at EnactClient init time:

    EnactClient(policies=[
        no_push_to_main,                     # plain function — no config needed
        max_files_per_commit(10),            # factory called with max=10
        require_branch_prefix("agent/"),     # factory called with prefix
    ])

The factory is called once; the returned closure is stored and called
on every subsequent run() call.

Payload keys used by this module
----------------------------------
  "branch"     — branch name string (used by no_push_to_main, no_delete_branch, require_branch_prefix)
  "file_count" — integer count of files in the commit (used by max_files_per_commit)
"""
from enact.models import WorkflowContext, PolicyResult


def no_push_to_main(context: WorkflowContext) -> PolicyResult:
    """
    Block any direct push or workflow targeting main or master.

    Reads context.payload["branch"]. The check is case-insensitive so
    "MAIN", "Main", "master", etc. are all caught. An empty or missing
    branch field is allowed through — the policy can only block what it
    can see.

    Use this with agent_pr_workflow to ensure agents always go through
    a PR rather than pushing directly.

    Args:
        context — WorkflowContext; reads context.payload.get("branch", "")

    Returns:
        PolicyResult — passed=False if branch is "main" or "master" (any case)
    """
    branch = context.payload.get("branch", "")
    blocked = branch.lower() in ("main", "master")
    return PolicyResult(
        policy="no_push_to_main",
        passed=not blocked,
        reason=(
            f"Direct push to '{branch}' is blocked"
            if blocked
            else "Branch is not main/master"
        ),
    )


def max_files_per_commit(max_files: int = 50):
    """
    Factory: return a policy that blocks commits touching more than max_files files.

    Blast radius control — prevents an agent from making sweeping changes across
    the entire codebase in a single commit. The caller sets the limit at init time:

        EnactClient(policies=[max_files_per_commit(10)])  # no more than 10 files

    The policy reads context.payload.get("file_count", 0). The workflow is
    responsible for computing this value before calling enact.run().

    Args:
        max_files — maximum number of files allowed in the commit (inclusive); default 50

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """

    def _policy(context: WorkflowContext) -> PolicyResult:
        # Default to 0 if not provided — a workflow that forgets to set file_count
        # will always pass this check, which is the safe default.
        file_count = context.payload.get("file_count", 0)
        passed = file_count <= max_files
        return PolicyResult(
            policy="max_files_per_commit",
            passed=passed,
            reason=(
                f"Commit touches {file_count} files (max {max_files})"
                if not passed
                else f"File count {file_count} within limit of {max_files}"
            ),
        )

    return _policy


def require_branch_prefix(prefix: str = "agent/"):
    """
    Factory: return a policy that requires branch names to start with a prefix.

    Enforces naming conventions for agent-created branches. For example,
    requiring all agent branches to start with "agent/" makes them easy to
    identify in GitHub and enables separate branch protection rules.

        EnactClient(policies=[require_branch_prefix("agent/")])

    The policy reads context.payload.get("branch", ""). An empty branch name
    fails this check (empty string does not start with any non-empty prefix).

    Args:
        prefix — required branch name prefix (default: "agent/")

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """

    def _policy(context: WorkflowContext) -> PolicyResult:
        branch = context.payload.get("branch", "")
        passed = branch.startswith(prefix)
        return PolicyResult(
            policy="require_branch_prefix",
            passed=passed,
            reason=(
                f"Branch '{branch}' must start with '{prefix}'"
                if not passed
                else f"Branch '{branch}' has required prefix '{prefix}'"
            ),
        )

    return _policy


def no_delete_branch(context: WorkflowContext) -> PolicyResult:
    """
    Block all branch deletion on this client — regardless of branch name.

    Sentinel policy: register this on any client where delete_branch should
    never run. Useful for agents whose only job is to create branches and open
    PRs — they have no business deleting anything. No payload keys are read;
    the block is unconditional.

    If you have a legitimate branch-cleanup workflow, create a separate
    EnactClient for it without this policy rather than trying to conditionally
    allow deletion on a shared client.

    Args:
        context — WorkflowContext (payload not inspected)

    Returns:
        PolicyResult — always passed=False
    """
    return PolicyResult(
        policy="no_delete_branch",
        passed=False,
        reason="Branch deletion is not permitted on this client",
    )


def no_merge_to_main(context: WorkflowContext) -> PolicyResult:
    """
    Block any merge_pr operation whose target branch is main or master.

    Reads context.payload["base"] — the branch the PR merges INTO. The
    workflow is responsible for populating this field before calling enact.run():

        enact.run(context=WorkflowContext(
            workflow="merge_approved_pr",
            payload={"base": pr.base.ref, "pr_number": 42},
            ...
        ))

    The check is case-insensitive. An empty or missing base is allowed through
    — the policy can only block what it can see.

    Use alongside no_push_to_main to prevent both direct pushes and PR merges
    to the protected branch.

    Args:
        context — WorkflowContext; reads context.payload.get("base", "")

    Returns:
        PolicyResult — passed=False if base is "main" or "master" (any case)
    """
    base = context.payload.get("base", "")
    blocked = base.lower() in ("main", "master")
    return PolicyResult(
        policy="no_merge_to_main",
        passed=not blocked,
        reason=(
            f"Merge into '{base}' is blocked — PRs must target a non-protected branch"
            if blocked
            else "Merge target is not main/master"
        ),
    )
