"""
Tests for the GitHub connector.
PyGithub calls are fully mocked — no real API calls made.
"""
import pytest
from unittest.mock import patch, MagicMock
from github import UnknownObjectException
from enact.connectors.github import GitHubConnector


@pytest.fixture
def connector():
    with patch("enact.connectors.github.Github"):
        return GitHubConnector(token="fake-token")


class TestAllowlist:
    def test_default_allowlist_includes_all_actions(self):
        with patch("enact.connectors.github.Github"):
            conn = GitHubConnector(token="fake")
        for action in ["create_branch", "create_pr", "push_commit", "delete_branch", "create_issue", "merge_pr"]:
            assert action in conn._allowed_actions

    def test_custom_allowlist_restricts_actions(self):
        with patch("enact.connectors.github.Github"):
            conn = GitHubConnector(token="fake", allowed_actions=["create_branch"])
        assert "create_branch" in conn._allowed_actions
        assert "merge_pr" not in conn._allowed_actions

    def test_blocked_action_raises_permission_error(self):
        with patch("enact.connectors.github.Github"):
            conn = GitHubConnector(token="fake", allowed_actions=["create_branch"])
        with pytest.raises(PermissionError, match="not in allowlist"):
            conn.merge_pr(repo="owner/repo", pr_number=1)


class TestCreateBranch:
    def test_create_branch_success(self, connector):
        mock_repo = MagicMock()
        # Target branch doesn't exist (idempotency check fails), source branch has SHA
        mock_source = MagicMock()
        mock_source.commit.sha = "abc123"

        def get_branch_side_effect(name):
            if name == "agent/feature-x":
                raise Exception("Branch not found")
            return mock_source

        mock_repo.get_branch.side_effect = get_branch_side_effect
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_branch(repo="owner/repo", branch="agent/feature-x")

        assert result.success is True
        assert result.action == "create_branch"
        assert result.output["branch"] == "agent/feature-x"
        assert result.output["already_done"] is False
        mock_repo.create_git_ref.assert_called_once_with(
            "refs/heads/agent/feature-x", "abc123"
        )

    def test_create_branch_failure(self, connector):
        connector._get_repo = MagicMock(side_effect=Exception("API rate limit"))

        result = connector.create_branch(repo="owner/repo", branch="agent/feature-x")

        assert result.success is False
        assert "API rate limit" in result.output["error"]


class TestCreateBranchIdempotency:
    def test_create_branch_returns_success_when_already_exists(self, connector):
        """Retry safety: if branch already exists, return success with already_done."""
        mock_repo = MagicMock()
        # get_branch(target) succeeds = branch already exists
        mock_repo.get_branch.return_value.commit.sha = "abc123"
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_branch(repo="owner/repo", branch="agent/feature-x")

        assert result.success is True
        assert result.output["branch"] == "agent/feature-x"
        assert result.output["already_done"] == "created"
        # Should NOT have called create_git_ref
        mock_repo.create_git_ref.assert_not_called()


class TestCreatePR:
    def test_create_pr_success(self, connector):
        mock_repo = MagicMock()
        mock_repo.get_pulls.return_value = []  # No existing PRs
        mock_pr = MagicMock()
        mock_pr.number = 42
        mock_pr.html_url = "https://github.com/owner/repo/pull/42"
        mock_repo.create_pull.return_value = mock_pr
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_pr(
            repo="owner/repo",
            title="Agent PR",
            body="Automated",
            head="agent/feature-x",
        )

        assert result.success is True
        assert result.output["pr_number"] == 42
        assert "pull/42" in result.output["url"]
        assert result.output["already_done"] is False

    def test_create_pr_failure(self, connector):
        connector._get_repo = MagicMock(side_effect=Exception("Branch not found"))

        result = connector.create_pr(
            repo="owner/repo", title="t", body="b", head="agent/missing"
        )

        assert result.success is False
        assert "Branch not found" in result.output["error"]


class TestCreatePRIdempotency:
    def test_create_pr_returns_existing_when_open(self, connector):
        """Retry safety: if open PR exists for same head->base, return it."""
        mock_repo = MagicMock()
        mock_existing_pr = MagicMock()
        mock_existing_pr.number = 42
        mock_existing_pr.html_url = "https://github.com/owner/repo/pull/42"
        mock_repo.get_pulls.return_value = [mock_existing_pr]
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_pr(
            repo="owner/repo", title="Agent PR", body="Automated", head="agent/feature-x",
        )

        assert result.success is True
        assert result.output["pr_number"] == 42
        assert result.output["already_done"] == "created"
        mock_repo.create_pull.assert_not_called()


class TestCreateIssue:
    def test_create_issue_success(self, connector):
        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = []  # No matching issues
        mock_issue = MagicMock()
        mock_issue.number = 7
        mock_issue.html_url = "https://github.com/owner/repo/issues/7"
        mock_repo.create_issue.return_value = mock_issue
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_issue(repo="owner/repo", title="Bug found")

        assert result.success is True
        assert result.output["issue_number"] == 7
        assert result.output["already_done"] is False

    def test_create_issue_failure(self, connector):
        connector._get_repo = MagicMock(side_effect=Exception("Not authorized"))

        result = connector.create_issue(repo="owner/repo", title="Bug")

        assert result.success is False
        assert "Not authorized" in result.output["error"]


class TestCreateIssueIdempotency:
    def test_create_issue_returns_existing_when_title_matches(self, connector):
        """Retry safety: if open issue with same title exists, return it."""
        mock_repo = MagicMock()
        mock_existing = MagicMock()
        mock_existing.number = 7
        mock_existing.html_url = "https://github.com/owner/repo/issues/7"
        mock_existing.title = "Bug found"
        mock_repo.get_issues.return_value = [mock_existing]
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_issue(repo="owner/repo", title="Bug found")

        assert result.success is True
        assert result.output["issue_number"] == 7
        assert result.output["already_done"] == "created"
        mock_repo.create_issue.assert_not_called()

    def test_create_issue_creates_when_no_match(self, connector):
        """No matching open issue — creates new one."""
        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = []
        mock_new_issue = MagicMock()
        mock_new_issue.number = 8
        mock_new_issue.html_url = "https://github.com/owner/repo/issues/8"
        mock_repo.create_issue.return_value = mock_new_issue
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_issue(repo="owner/repo", title="New bug")

        assert result.success is True
        assert result.output["issue_number"] == 8
        assert result.output["already_done"] is False


class TestDeleteBranch:
    def test_delete_branch_success(self, connector):
        mock_repo = MagicMock()
        mock_ref = MagicMock()
        mock_repo.get_git_ref.return_value = mock_ref
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.delete_branch(repo="owner/repo", branch="agent/old-feature")

        assert result.success is True
        assert result.output["branch"] == "agent/old-feature"
        assert result.output["already_done"] is False
        mock_ref.delete.assert_called_once()

    def test_delete_branch_failure(self, connector):
        connector._get_repo = MagicMock(side_effect=Exception("Ref not found"))

        result = connector.delete_branch(repo="owner/repo", branch="gone")

        assert result.success is False
        assert "Ref not found" in result.output["error"]


class TestDeleteBranchIdempotency:
    def test_delete_branch_success_when_already_gone(self, connector):
        """Retry safety: if branch already deleted, return success."""
        mock_repo = MagicMock()
        mock_repo.get_git_ref.side_effect = UnknownObjectException(404, {}, {})
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.delete_branch(repo="owner/repo", branch="agent/old")

        assert result.success is True
        assert result.output["branch"] == "agent/old"
        assert result.output["already_done"] == "deleted"


class TestMergePR:
    def test_merge_pr_success(self, connector):
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.merged = False  # Not yet merged — proceed to merge
        mock_merge_result = MagicMock()
        mock_merge_result.merged = True
        mock_merge_result.sha = "deadbeef"
        mock_pr.merge.return_value = mock_merge_result
        mock_repo.get_pull.return_value = mock_pr
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.merge_pr(repo="owner/repo", pr_number=42)

        assert result.success is True
        assert result.output["merged"] is True
        assert result.output["sha"] == "deadbeef"
        assert result.output["already_done"] is False

    def test_merge_pr_failure(self, connector):
        connector._get_repo = MagicMock(side_effect=Exception("PR not mergeable"))

        result = connector.merge_pr(repo="owner/repo", pr_number=99)

        assert result.success is False
        assert "not mergeable" in result.output["error"]


class TestMergePRIdempotency:
    def test_merge_pr_success_when_already_merged(self, connector):
        """Retry safety: if PR already merged, return success."""
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.merged = True
        mock_pr.merge_commit_sha = "deadbeef"
        mock_repo.get_pull.return_value = mock_pr
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.merge_pr(repo="owner/repo", pr_number=42)

        assert result.success is True
        assert result.output["merged"] is True
        assert result.output["sha"] == "deadbeef"
        assert result.output["already_done"] == "merged"
        mock_pr.merge.assert_not_called()


class TestClosePr:
    def test_close_pr_success(self, connector):
        connector._allowed_actions.add("close_pr")
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.state = "open"
        mock_repo.get_pull.return_value = mock_pr
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.close_pr(repo="owner/repo", pr_number=42)

        assert result.success is True
        assert result.action == "close_pr"
        assert result.output["pr_number"] == 42
        assert result.output["already_done"] is False
        mock_pr.edit.assert_called_once_with(state="closed")

    def test_close_pr_already_closed(self, connector):
        connector._allowed_actions.add("close_pr")
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.state = "closed"
        mock_repo.get_pull.return_value = mock_pr
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.close_pr(repo="owner/repo", pr_number=42)

        assert result.success is True
        assert result.output["already_done"] == "closed"
        mock_pr.edit.assert_not_called()

    def test_close_pr_failure(self, connector):
        connector._allowed_actions.add("close_pr")
        connector._get_repo = MagicMock(side_effect=Exception("API error"))
        result = connector.close_pr(repo="owner/repo", pr_number=42)
        assert result.success is False
        assert "API error" in result.output["error"]

    def test_close_pr_not_in_default_allowlist(self):
        """close_pr is a rollback operation — must be explicitly allowed."""
        with patch("enact.connectors.github.Github"):
            conn = GitHubConnector(token="fake")
        assert "close_pr" not in conn._allowed_actions

    def test_close_pr_blocked_without_allowlist(self, connector):
        with patch("enact.connectors.github.Github"):
            conn = GitHubConnector(token="fake", allowed_actions=["create_pr"])
        with pytest.raises(PermissionError, match="not in allowlist"):
            conn.close_pr(repo="owner/repo", pr_number=1)


class TestCloseIssue:
    def test_close_issue_success(self, connector):
        connector._allowed_actions.add("close_issue")
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_issue.state = "open"
        mock_repo.get_issue.return_value = mock_issue
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.close_issue(repo="owner/repo", issue_number=7)

        assert result.success is True
        assert result.action == "close_issue"
        assert result.output["issue_number"] == 7
        assert result.output["already_done"] is False
        mock_issue.edit.assert_called_once_with(state="closed")

    def test_close_issue_already_closed(self, connector):
        connector._allowed_actions.add("close_issue")
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_issue.state = "closed"
        mock_repo.get_issue.return_value = mock_issue
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.close_issue(repo="owner/repo", issue_number=7)

        assert result.success is True
        assert result.output["already_done"] == "closed"

    def test_close_issue_failure(self, connector):
        connector._allowed_actions.add("close_issue")
        connector._get_repo = MagicMock(side_effect=Exception("not found"))
        result = connector.close_issue(repo="owner/repo", issue_number=7)
        assert result.success is False
        assert "not found" in result.output["error"]


class TestCreateBranchFromSha:
    def test_create_branch_from_sha_success(self, connector):
        connector._allowed_actions.add("create_branch_from_sha")
        mock_repo = MagicMock()
        mock_repo.get_branch.side_effect = Exception("not found")  # doesn't exist yet
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_branch_from_sha(
            repo="owner/repo", branch="agent/restored", sha="deadbeef"
        )

        assert result.success is True
        assert result.action == "create_branch_from_sha"
        assert result.output["branch"] == "agent/restored"
        assert result.output["already_done"] is False
        mock_repo.create_git_ref.assert_called_once_with(
            "refs/heads/agent/restored", "deadbeef"
        )

    def test_create_branch_from_sha_already_exists(self, connector):
        connector._allowed_actions.add("create_branch_from_sha")
        mock_repo = MagicMock()
        mock_repo.get_branch.return_value = MagicMock()  # branch exists
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_branch_from_sha(
            repo="owner/repo", branch="agent/restored", sha="deadbeef"
        )

        assert result.success is True
        assert result.output["already_done"] == "created"

    def test_create_branch_from_sha_failure(self, connector):
        connector._allowed_actions.add("create_branch_from_sha")
        connector._get_repo = MagicMock(side_effect=Exception("API error"))
        result = connector.create_branch_from_sha(
            repo="owner/repo", branch="agent/x", sha="abc"
        )
        assert result.success is False
        assert "API error" in result.output["error"]
