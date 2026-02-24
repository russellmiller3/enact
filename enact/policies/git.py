"""
Git policies — prevent dangerous git operations.
"""
from enact.models import WorkflowContext, PolicyResult


def no_push_to_main(context: WorkflowContext) -> PolicyResult:
    """Block any direct push to main or master."""
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
    """Factory: returns a policy that blocks commits touching too many files."""

    def _policy(context: WorkflowContext) -> PolicyResult:
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
    """Factory: returns a policy that requires branches to start with a prefix."""

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
