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

Idempotency (already_done convention)
--------------------------------------
Every mutating method checks whether the desired state already exists before
acting. If it does, the method returns ActionResult(success=True) with
output["already_done"] set to a descriptive string ("created", "deleted",
"merged"). If it's a fresh action, already_done is False.

This makes every action safe to retry. Callers check:
    if result.output.get("already_done"):  # truthy string = noop
        log(f"Skipped — {result.output['already_done']}")

All future connectors MUST follow this convention.

Usage:
    gh = GitHubConnector(
        token=os.environ["GITHUB_TOKEN"],
        allowed_actions=["create_branch", "create_pr"],  # restrict to what this agent needs
    )
    result = gh.create_branch(repo="owner/repo", branch="agent/fix-123")
"""
from github import Github, UnknownObjectException
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
                # close_pr, close_issue, create_branch_from_sha are rollback operations
                # — not included by default; must be explicitly added to allowed_actions
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
            # Idempotency: check if target branch already exists
            try:
                repo_obj.get_branch(branch)
                return ActionResult(
                    action="create_branch",
                    system="github",
                    success=True,
                    output={"branch": branch, "already_done": "created"},
                    rollback_data={},
                )
            except Exception:
                pass  # Branch doesn't exist — proceed to create

            source = repo_obj.get_branch(from_branch)
            repo_obj.create_git_ref(f"refs/heads/{branch}", source.commit.sha)
            return ActionResult(
                action="create_branch",
                system="github",
                success=True,
                output={"branch": branch, "already_done": False},
                rollback_data={"repo": repo, "branch": branch},
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
            # Idempotency: check for existing open PR with same head->base
            try:
                existing = list(repo_obj.get_pulls(state="open", head=head, base=base))
                if existing:
                    pr = existing[0]
                    return ActionResult(
                        action="create_pr",
                        system="github",
                        success=True,
                        output={"pr_number": pr.number, "url": pr.html_url, "already_done": "created"},
                        rollback_data={},
                    )
            except Exception:
                pass  # Lookup failed — proceed to create

            pr = repo_obj.create_pull(title=title, body=body, head=head, base=base)
            return ActionResult(
                action="create_pr",
                system="github",
                success=True,
                output={"pr_number": pr.number, "url": pr.html_url, "already_done": False},
                rollback_data={"repo": repo, "pr_number": pr.number},
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
            # Idempotency: check for open issue with same title
            try:
                for issue in repo_obj.get_issues(state="open"):
                    if issue.title == title:
                        return ActionResult(
                            action="create_issue",
                            system="github",
                            success=True,
                            output={"issue_number": issue.number, "url": issue.html_url, "already_done": "created"},
                            rollback_data={},
                        )
            except Exception:
                pass  # Lookup failed — proceed to create

            issue = repo_obj.create_issue(title=title, body=body)
            return ActionResult(
                action="create_issue",
                system="github",
                success=True,
                output={"issue_number": issue.number, "url": issue.html_url, "already_done": False},
                rollback_data={"repo": repo, "issue_number": issue.number},
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
            try:
                ref = repo_obj.get_git_ref(f"heads/{branch}")
            except UnknownObjectException:
                # Branch already gone — idempotent success
                return ActionResult(
                    action="delete_branch",
                    system="github",
                    success=True,
                    output={"branch": branch, "already_done": "deleted"},
                    rollback_data={},
                )
            sha = ref.object.sha  # capture before deletion for potential rollback
            ref.delete()
            return ActionResult(
                action="delete_branch",
                system="github",
                success=True,
                output={"branch": branch, "already_done": False},
                rollback_data={"repo": repo, "branch": branch, "sha": sha},
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
            # Idempotency: check if already merged
            if pr.merged:
                return ActionResult(
                    action="merge_pr",
                    system="github",
                    success=True,
                    output={"merged": True, "sha": pr.merge_commit_sha, "already_done": "merged"},
                )
            result = pr.merge()
            return ActionResult(
                action="merge_pr",
                system="github",
                success=True,
                output={"merged": result.merged, "sha": result.sha, "already_done": False},
                rollback_data={
                    "repo": repo,
                    "merge_sha": result.sha,       # SHA of the merge commit — needed by revert_commit
                    "base_branch": pr.base.ref,    # e.g. "main" — the branch the PR was merged into
                },
            )
        except Exception as e:
            return ActionResult(
                action="merge_pr",
                system="github",
                success=False,
                output={"error": str(e)},
            )

    def revert_commit(self, repo: str, merge_sha: str, base_branch: str = "main") -> ActionResult:
        """
        Revert a merge commit by creating a new commit whose tree matches the
        first parent of the merge (i.e. what base_branch looked like before the merge).

        This is the programmatic equivalent of `git revert -m 1 <merge_sha>`.
        It does NOT rewrite history — it adds a new commit on top of base_branch,
        which is safe on protected branches.

        CAVEAT: If you later try to re-merge the same branch, Git will skip the
        commits it already saw. You would need to `git revert <revert_sha>` first
        to "undo the undo" before re-merging.

        Args:
            repo         — "owner/repo" string
            merge_sha    — SHA of the merge commit to revert (from merge_pr output)
            base_branch  — branch that was merged into (default: "main")

        Returns:
            ActionResult — success=True with {"revert_sha": str, "reverted_merge": str}, or
                           success=False with {"error": str(e)}
        """
        self._check_allowed("revert_commit")
        try:
            repo_obj = self._get_repo(repo)

            # Low-level GitCommit (has .tree and .parents as GitCommit objects)
            merge_git_commit = repo_obj.get_git_commit(merge_sha)

            # Validate: a merge commit has 2+ parents
            if len(merge_git_commit.parents) < 2:
                return ActionResult(
                    action="revert_commit",
                    system="github",
                    success=False,
                    output={"error": f"SHA {merge_sha} is not a merge commit ({len(merge_git_commit.parents)} parent(s))"},
                )

            # parent[0] = tip of base_branch just before the merge happened
            # Its tree = the state we want to restore
            parent_sha = merge_git_commit.parents[0].sha
            parent_git_commit = repo_obj.get_git_commit(parent_sha)
            parent_tree = parent_git_commit.tree  # GitTree object

            # Current HEAD of base_branch becomes the new commit's parent
            current_head_sha = repo_obj.get_branch(base_branch).commit.sha
            current_head_git_commit = repo_obj.get_git_commit(current_head_sha)

            revert_message = (
                f"Revert merge {merge_sha[:7]}\n\n"
                f"This reverts merge commit {merge_sha}.\n"
                f"Created automatically by Enact rollback."
            )

            # Create the revert commit: same tree as parent[0], current HEAD as its parent
            new_commit = repo_obj.create_git_commit(
                message=revert_message,
                tree=parent_tree,
                parents=[current_head_git_commit],
            )

            # Fast-forward base_branch to the new revert commit
            ref = repo_obj.get_git_ref(f"heads/{base_branch}")
            ref.edit(new_commit.sha)

            return ActionResult(
                action="revert_commit",
                system="github",
                success=True,
                output={
                    "revert_sha": new_commit.sha,
                    "reverted_merge": merge_sha,
                    "base_branch": base_branch,
                    "already_done": False,
                },
            )
        except Exception as e:
            return ActionResult(
                action="revert_commit",
                system="github",
                success=False,
                output={"error": str(e)},
            )

    def close_pr(self, repo: str, pr_number: int) -> ActionResult:
        """
        Close an open pull request without merging.
        Used as the rollback inverse of create_pr.

        Args:
            repo      — "owner/repo" string
            pr_number — integer PR number

        Returns:
            ActionResult — success=True with {"pr_number": int}, or
                           success=False with {"error": str(e)}
        """
        self._check_allowed("close_pr")
        try:
            repo_obj = self._get_repo(repo)
            pr = repo_obj.get_pull(pr_number)
            if pr.state == "closed":
                return ActionResult(
                    action="close_pr",
                    system="github",
                    success=True,
                    output={"pr_number": pr_number, "already_done": "closed"},
                )
            pr.edit(state="closed")
            return ActionResult(
                action="close_pr",
                system="github",
                success=True,
                output={"pr_number": pr_number, "already_done": False},
            )
        except Exception as e:
            return ActionResult(
                action="close_pr",
                system="github",
                success=False,
                output={"error": str(e)},
            )

    def close_issue(self, repo: str, issue_number: int) -> ActionResult:
        """
        Close an open issue.
        Used as the rollback inverse of create_issue.

        Args:
            repo         — "owner/repo" string
            issue_number — integer issue number

        Returns:
            ActionResult — success=True with {"issue_number": int}, or
                           success=False with {"error": str(e)}
        """
        self._check_allowed("close_issue")
        try:
            repo_obj = self._get_repo(repo)
            issue = repo_obj.get_issue(issue_number)
            if issue.state == "closed":
                return ActionResult(
                    action="close_issue",
                    system="github",
                    success=True,
                    output={"issue_number": issue_number, "already_done": "closed"},
                )
            issue.edit(state="closed")
            return ActionResult(
                action="close_issue",
                system="github",
                success=True,
                output={"issue_number": issue_number, "already_done": False},
            )
        except Exception as e:
            return ActionResult(
                action="close_issue",
                system="github",
                success=False,
                output={"error": str(e)},
            )

    def create_branch_from_sha(self, repo: str, branch: str, sha: str) -> ActionResult:
        """
        Create a branch pointing at a specific commit SHA.
        Used as the rollback inverse of delete_branch — restores a deleted branch
        to the SHA captured before deletion.

        Args:
            repo   — "owner/repo" string
            branch — branch name to restore
            sha    — commit SHA to point the new branch at

        Returns:
            ActionResult — success=True with {"branch": branch}, or
                           success=False with {"error": str(e)}
        """
        self._check_allowed("create_branch_from_sha")
        try:
            repo_obj = self._get_repo(repo)
            try:
                repo_obj.get_branch(branch)
                return ActionResult(
                    action="create_branch_from_sha",
                    system="github",
                    success=True,
                    output={"branch": branch, "already_done": "created"},
                )
            except Exception:
                pass  # Branch doesn't exist — proceed to create
            repo_obj.create_git_ref(f"refs/heads/{branch}", sha)
            return ActionResult(
                action="create_branch_from_sha",
                system="github",
                success=True,
                output={"branch": branch, "already_done": False},
            )
        except Exception as e:
            return ActionResult(
                action="create_branch_from_sha",
                system="github",
                success=False,
                output={"error": str(e)},
            )
