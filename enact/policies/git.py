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
        dont_push_to_main,                     # plain function — no config needed
        max_files_per_commit(10),            # factory called with max=10
        require_branch_prefix("agent/"),     # factory called with prefix
    ])

The factory is called once; the returned closure is stored and called
on every subsequent run() call.

Payload keys used by this module
----------------------------------
  "branch"     — branch name string (used by dont_push_to_main, dont_delete_branch, require_branch_prefix)
  "file_count" — integer count of files in the commit (used by max_files_per_commit)
"""
from enact.models import WorkflowContext, PolicyResult
from enact.policies._secrets import SECRET_PATTERNS


def dont_push_to_main(context: WorkflowContext) -> PolicyResult:
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
    branch_is_not_main = branch.lower() not in ("main", "master")
    return PolicyResult(
        policy="dont_push_to_main",
        passed=branch_is_not_main,
        reason=(
            "Branch is not main/master"
            if branch_is_not_main
            else f"Direct push to '{branch}' is blocked"
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


def dont_delete_branch(context: WorkflowContext) -> PolicyResult:
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
        policy="dont_delete_branch",
        passed=False,
        reason="Branch deletion is not permitted on this client",
    )


def dont_merge_to_main(context: WorkflowContext) -> PolicyResult:
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

    Use alongside dont_push_to_main to prevent both direct pushes and PR merges
    to the protected branch.

    Args:
        context — WorkflowContext; reads context.payload.get("base", "")

    Returns:
        PolicyResult — passed=False if base is "main" or "master" (any case)
    """
    base = context.payload.get("base", "")
    merge_target_is_not_main = base.lower() not in ("main", "master")
    return PolicyResult(
        policy="dont_merge_to_main",
        passed=merge_target_is_not_main,
        reason=(
            "Merge target is not main/master"
            if merge_target_is_not_main
            else f"Merge into '{base}' is blocked — PRs must target a non-protected branch"
        ),
    )


def dont_force_push(context: WorkflowContext) -> PolicyResult:
    """
    Block git push operations that include --force or -f flags.

    Force pushing rewrites remote branch history and can permanently destroy
    commits for everyone working on that branch. It also bypasses the normal
    PR review process and can silently overwrite teammates' work. There is no
    safe agent use case for force pushing.

    Reads context.payload.get("args", []) or context.payload.get("command", []).
    Accepts a list (["git", "push", "--force"]) or a space-separated string.

    Args:
        context — WorkflowContext; reads payload["args"] or payload["command"]

    Returns:
        PolicyResult — passed=False if --force, -f, or --force-with-lease is present
    """
    args = context.payload.get("args", context.payload.get("command", []))
    if isinstance(args, str):
        args = args.split()
    # Must be a git push command — not just any command with -f. Otherwise
    # this policy false-positives on `rm -f`, `grep -f`, `npm install -f`,
    # etc. (session 16 regression).
    if "git" not in args or "push" not in args:
        return PolicyResult(
            policy="dont_force_push",
            passed=True,
            reason="Not a git push command",
        )
    has_force = any(a in ("--force", "-f", "--force-with-lease") for a in args)
    if has_force:
        return PolicyResult(
            policy="dont_force_push",
            passed=False,
            reason="Force push is not permitted — it can permanently destroy git history",
        )
    return PolicyResult(
        policy="dont_force_push",
        passed=True,
        reason="No force push flags detected",
    )


_MEANINGLESS_MESSAGES = {
    "fix", "fixes", "fixed", "fixing",
    "update", "updates", "updated", "updating",
    "change", "changes", "changed",
    "wip", "work in progress",
    ".", "..", "...",
    "commit", "committed",
    "test", "testing",
    "temp", "tmp",
    "misc",
}

_MIN_COMMIT_MESSAGE_LENGTH = 10


def require_meaningful_commit_message(context: WorkflowContext) -> PolicyResult:
    """
    Block commits whose message is empty, too short, or meaninglessly generic.

    AI agents frequently commit with messages like "fix", "update", or "wip".
    These are useless in audit trails and in git log — they tell you nothing
    about what changed or why. This policy enforces a minimum bar.

    Rules:
      1. Message must not be empty
      2. Message must be at least 10 characters (after stripping whitespace)
      3. Message must not be in the known-meaningless denylist

    Reads context.payload.get("commit_message", ""). Pass-through if absent.

    Args:
        context — WorkflowContext; reads payload["commit_message"]

    Returns:
        PolicyResult — passed=False if message fails any of the three rules
    """
    message = context.payload.get("commit_message", "")
    stripped = message.strip()
    if not stripped:
        return PolicyResult(
            policy="require_meaningful_commit_message",
            passed=False,
            reason="Commit message is empty",
        )
    if len(stripped) < _MIN_COMMIT_MESSAGE_LENGTH:
        return PolicyResult(
            policy="require_meaningful_commit_message",
            passed=False,
            reason=(
                f"Commit message '{stripped}' is too short "
                f"({len(stripped)} chars, minimum {_MIN_COMMIT_MESSAGE_LENGTH})"
            ),
        )
    if stripped.lower() in _MEANINGLESS_MESSAGES:
        return PolicyResult(
            policy="require_meaningful_commit_message",
            passed=False,
            reason=f"Commit message '{stripped}' is not meaningful — describe what changed and why",
        )
    return PolicyResult(
        policy="require_meaningful_commit_message",
        passed=True,
        reason=f"Commit message meets requirements ({len(stripped)} chars)",
    )


def dont_commit_api_keys(context: WorkflowContext) -> PolicyResult:
    """
    Block commits whose diff, content, or message contains API key patterns.

    Prevents agents from committing files that contain credentials — the most
    common way secrets end up in version control. Checks payload["diff"],
    payload["content"], and payload["commit_message"] against known vendor
    key formats (OpenAI, GitHub, Slack, AWS, Google).

    Workflows should put the staged diff in payload["diff"] before calling
    enact.run() so this policy can inspect commit content. If no "diff" key
    is present, the policy checks "content" and "commit_message" as fallbacks.

    Detection is conservative by design — known vendor formats only, to keep
    false positives low. See enact/policies/_secrets.py for the full pattern list.

    Args:
        context — WorkflowContext; reads payload["diff"], ["content"], ["commit_message"]

    Returns:
        PolicyResult — passed=False if any checked field matches a known API key pattern
    """
    candidates = [
        context.payload.get("diff", ""),
        context.payload.get("content", ""),
        context.payload.get("commit_message", ""),
    ]
    for text in candidates:
        if not text:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                return PolicyResult(
                    policy="dont_commit_api_keys",
                    passed=False,
                    reason="Possible API key detected in commit content — committing credentials is not permitted",
                )
    return PolicyResult(
        policy="dont_commit_api_keys",
        passed=True,
        reason="No API key patterns detected in commit",
    )
