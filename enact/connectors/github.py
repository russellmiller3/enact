"""
GitHub connector — wraps PyGithub for safe repository operations.
"""
from github import Github
from enact.models import ActionResult


class GitHubConnector:
    def __init__(self, token: str, allowed_actions: list[str] | None = None):
        self._github = Github(token)
        self._allowed_actions = set(
            allowed_actions
            or [
                "create_branch",
                "create_pr",
                "push_commit",
                "delete_branch",
                "create_issue",
                "merge_pr",
            ]
        )

    def _check_allowed(self, action: str):
        if action not in self._allowed_actions:
            raise PermissionError(
                f"Action '{action}' not in allowlist: {self._allowed_actions}"
            )

    def _get_repo(self, repo_name: str):
        return self._github.get_repo(repo_name)

    def create_branch(
        self, repo: str, branch: str, from_branch: str = "main"
    ) -> ActionResult:
        self._check_allowed("create_branch")
        try:
            repo_obj = self._get_repo(repo)
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
        self._check_allowed("delete_branch")
        try:
            repo_obj = self._get_repo(repo)
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
        self._check_allowed("merge_pr")
        try:
            repo_obj = self._get_repo(repo)
            pr = repo_obj.get_pull(pr_number)
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
