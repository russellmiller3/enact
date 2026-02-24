"""
GitHub connector — wraps PyGithub for safe, allowlist-gated repository operations.

Design: allowlist-first
------------------------
Every public method calls _check_allowed() before touching the GitHub API.
This means even if a bug in Enact somehow invokes the wrong action, the
connector itself refuses to execute it unless that action was explicitly
permitted at init time. The allowlist is the last line of defence.

Error handling pattern
-----------------------
All methods catch broad Exception and return ActionResult(success=False, output={"error": ...})
rather than letting exceptions propagate. This is intentional:
  - Workflows can inspect results and decide how to proceed (partial success)
  - The receipt always reflects what actually happened
  - The calling agent doesn't need try/except around enact.run()

The one exception to this rule: _check_allowed() raises PermissionError if
the action is not in the allowlist. This is a programming error (wrong action
name), not a runtime API failure, so it should blow up loudly.

Usage:
    gh = GitHubConnector(
        token=os.environ["GITHUB_TOKEN"],
        allowed_actions=["create_branch", "create_pr"],  # restrict to what this agent needs
    )
    result = gh.create_branch(repo="owner/repo", branch="agent/fix-123")
"""
from github import Github
from enact.models import ActionResult


class GitHubConnector:
    """
    Thin wrapper around PyGithub with per-instance action allowlisting.

    Instantiate once and pass into EnactClient(systems={"github": gh}).
    The connector is then available to policies and workflows via
    context.systems["github"].
    """

    def __init__(self, token: str, allowed_actions: list[str] | None = None):
        """
        Initialise the connector.

        Args:
            token           — GitHub personal access token or GitHub App token.
                              Needs repo scope for branch/PR/issue operations.
            allowed_actions — explicit list of action names this connector instance
                              is permitted to execute. Defaults to all six actions.
                              Restricting this list at init time is recommended for
                              production — an agent that only needs to open PRs should
                              not be able to merge or delete branches.
        """
        # PyGithub client — lazy HTTP connection, not established until first API call.
        self._github = Github(token)
        self._allowed_actions = set(
            allowed_actions
            or [
                "create_branch",
                "create_pr",
                "push_commit",   # reserved for future push_commit implementation
                "delete_branch",
                "create_issue",
                "merge_pr",
            ]
        )

    def _check_allowed(self, action: str):
        """
        Raise PermissionError if the action is not in this connector's allowlist.

        Called at the top of every public method. Raises immediately so the
        error is loud and traceable — not silently returning a failure result.
        """
        if action not in self._allowed_actions:
            raise PermissionError(
                f"Action '{action}' not in allowlist: {self._allowed_actions}"
            )

    def _get_repo(self, repo_name: str):
        """
        Return a PyGithub Repository object for the given 'owner/repo' string.
        Isolated into a method so tests can patch it cleanly with a mock.
        """
        return self._github.get_repo(repo_name)

    def create_branch(
        self, repo: str, branch: str, from_branch: str = "main"
    ) -> ActionResult:
        """
        Create a new branch pointing at the tip of from_branch.

        Under the hood this calls create_git_ref with a "refs/heads/<branch>" ref,
        which is how the GitHub API creates branches (they're just named refs).

        Args:
            repo        — "owner/repo" string
            branch      — name for the new branch (e.g. "agent/fix-123")
            from_branch — source branch to branch from (default: "main")

        Returns:
            ActionResult — success=True with {"branch": branch}, or
                           success=False with {"error": str(e)}
        """
        self._check_allowed("create_branch")
        try:
            repo_obj = self._get_repo(repo)
            # get_branch returns a Branch object; we only need the tip commit's SHA.
            source = repo_obj.get_branch(from_branch)
            repo_obj.create_git_ref(f"refs/heads/{branch}", source.commit.sha)
            return ActionResult(
                action="create_branch",
                system="github",
                success=True,
                output={"branch": branch},
            )
        except Exception as e:
            return ActionResult(
                action="create_branch",
                system="github",
                success=False,
                output={"error": str(e)},
            )

    def create_pr(
        self, repo: str, title: str, body: str, head: str, base: str = "main"
    ) -> ActionResult:
        """
        Open a pull request from head into base.

        Args:
            repo   — "owner/repo" string
            title  — PR title
            body   — PR description (markdown supported)
            head   — source branch name (the branch with changes)
            base   — target branch (default: "main")

        Returns:
            ActionResult — success=True with {"pr_number": int, "url": str}, or
                           success=False with {"error": str(e)}
        """
        self._check_allowed("create_pr")
        try:
            repo_obj = self._get_repo(repo)
            pr = repo_obj.create_pull(title=title, body=body, head=head, base=base)
            return ActionResult(
                action="create_pr",
                system="github",
                success=True,
                output={"pr_number": pr.number, "url": pr.html_url},
            )
        except Exception as e:
            return ActionResult(
                action="create_pr",
                system="github",
                success=False,
                output={"error": str(e)},
            )

    def create_issue(self, repo: str, title: str, body: str = "") -> ActionResult:
        """
        Open a new GitHub issue.

        Args:
            repo   — "owner/repo" string
            title  — issue title
            body   — issue description (markdown supported); defaults to empty

        Returns:
            ActionResult — success=True with {"issue_number": int, "url": str}, or
                           success=False with {"error": str(e)}
        """
        self._check_allowed("create_issue")
        try:
            repo_obj = self._get_repo(repo)
            issue = repo_obj.create_issue(title=title, body=body)
            return ActionResult(
                action="create_issue",
                system="github",
                success=True,
                output={"issue_number": issue.number, "url": issue.html_url},
            )
        except Exception as e:
            return ActionResult(
                action="create_issue",
                system="github",
                success=False,
                output={"error": str(e)},
            )

    def delete_branch(self, repo: str, branch: str) -> ActionResult:
        """
        Delete a branch by deleting its underlying git ref.

        Note: GitHub's API deletes branches via their git ref ("heads/<branch>"),
        not via a branch-specific endpoint. This method uses get_git_ref to fetch
        the ref object and calls ref.delete() on it.

        Args:
            repo   — "owner/repo" string
            branch — branch name to delete (NOT the full ref path)

        Returns:
            ActionResult — success=True with {"branch": branch}, or
                           success=False with {"error": str(e)}
        """
        self._check_allowed("delete_branch")
        try:
            repo_obj = self._get_repo(repo)
            # Note: get_git_ref expects "heads/<branch>", not "refs/heads/<branch>"
            ref = repo_obj.get_git_ref(f"heads/{branch}")
            ref.delete()
            return ActionResult(
                action="delete_branch",
                system="github",
                success=True,
                output={"branch": branch},
            )
        except Exception as e:
            return ActionResult(
                action="delete_branch",
                system="github",
                success=False,
                output={"error": str(e)},
            )

    def merge_pr(self, repo: str, pr_number: int) -> ActionResult:
        """
        Merge an open pull request using the repository's default merge strategy.

        Args:
            repo      — "owner/repo" string
            pr_number — integer PR number (from create_pr output or GitHub UI)

        Returns:
            ActionResult — success=True with {"merged": bool, "sha": str}, or
                           success=False with {"error": str(e)}
        """
        self._check_allowed("merge_pr")
        try:
            repo_obj = self._get_repo(repo)
            pr = repo_obj.get_pull(pr_number)
            # pr.merge() returns a MergedPullRequest namedtuple with .merged and .sha
            result = pr.merge()
            return ActionResult(
                action="merge_pr",
                system="github",
                success=True,
                output={"merged": result.merged, "sha": result.sha},
            )
        except Exception as e:
            return ActionResult(
                action="merge_pr",
                system="github",
                success=False,
                output={"error": str(e)},
            )
