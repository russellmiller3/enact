"""
Tests for the GitHub connector.
PyGithub calls are fully mocked — no real API calls made.
"""
import pytest
from unittest.mock import patch, MagicMock
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
        mock_repo.get_branch.return_value.commit.sha = "abc123"
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_branch(repo="owner/repo", branch="agent/feature-x")

        assert result.success is True
        assert result.action == "create_branch"
        assert result.output["branch"] == "agent/feature-x"
        mock_repo.create_git_ref.assert_called_once_with(
            "refs/heads/agent/feature-x", "abc123"
        )

    def test_create_branch_failure(self, connector):
        connector._get_repo = MagicMock(side_effect=Exception("API rate limit"))

        result = connector.create_branch(repo="owner/repo", branch="agent/feature-x")

        assert result.success is False
        assert "API rate limit" in result.output["error"]


class TestCreatePR:
    def test_create_pr_success(self, connector):
        mock_repo = MagicMock()
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

    def test_create_pr_failure(self, connector):
        connector._get_repo = MagicMock(side_effect=Exception("Branch not found"))

        result = connector.create_pr(
            repo="owner/repo", title="t", body="b", head="agent/missing"
        )

        assert result.success is False
        assert "Branch not found" in result.output["error"]


class TestCreateIssue:
    def test_create_issue_success(self, connector):
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_issue.number = 7
        mock_issue.html_url = "https://github.com/owner/repo/issues/7"
        mock_repo.create_issue.return_value = mock_issue
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_issue(repo="owner/repo", title="Bug found")

        assert result.success is True
        assert result.output["issue_number"] == 7

    def test_create_issue_failure(self, connector):
        connector._get_repo = MagicMock(side_effect=Exception("Not authorized"))

        result = connector.create_issue(repo="owner/repo", title="Bug")

        assert result.success is False
        assert "Not authorized" in result.output["error"]


class TestDeleteBranch:
    def test_delete_branch_success(self, connector):
        mock_repo = MagicMock()
        mock_ref = MagicMock()
        mock_repo.get_git_ref.return_value = mock_ref
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.delete_branch(repo="owner/repo", branch="agent/old-feature")

        assert result.success is True
        assert result.output["branch"] == "agent/old-feature"
        mock_ref.delete.assert_called_once()

    def test_delete_branch_failure(self, connector):
        connector._get_repo = MagicMock(side_effect=Exception("Ref not found"))

        result = connector.delete_branch(repo="owner/repo", branch="gone")

        assert result.success is False
        assert "Ref not found" in result.output["error"]


class TestMergePR:
    def test_merge_pr_success(self, connector):
        mock_repo = MagicMock()
        mock_pr = MagicMock()
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

    def test_merge_pr_failure(self, connector):
        connector._get_repo = MagicMock(side_effect=Exception("PR not mergeable"))

        result = connector.merge_pr(repo="owner/repo", pr_number=99)

        assert result.success is False
        assert "not mergeable" in result.output["error"]
