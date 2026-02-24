"""
Tests for enact/rollback.py — execute_rollback_action() dispatch logic.
All connector calls are mocked. No real GitHub/Postgres API calls made.
"""
import pytest
from unittest.mock import MagicMock
from enact.models import ActionResult
from enact.rollback import execute_rollback_action


# ── GitHub rollback dispatch ──────────────────────────────────────────────────

class TestRollbackGitHub:
    def _make_gh_connector(self):
        connector = MagicMock()
        connector.delete_branch.return_value = ActionResult(
            action="delete_branch", system="github", success=True,
            output={"branch": "agent/x", "already_done": False},
        )
        connector.close_pr.return_value = ActionResult(
            action="close_pr", system="github", success=True,
            output={"pr_number": 42, "already_done": False},
        )
        connector.close_issue.return_value = ActionResult(
            action="close_issue", system="github", success=True,
            output={"issue_number": 7, "already_done": False},
        )
        connector.create_branch_from_sha.return_value = ActionResult(
            action="create_branch_from_sha", system="github", success=True,
            output={"branch": "agent/x", "already_done": False},
        )
        return connector

    def test_rollback_create_branch_calls_delete_branch(self):
        connector = self._make_gh_connector()
        systems = {"github": connector}
        action = ActionResult(
            action="create_branch", system="github", success=True,
            output={"branch": "agent/x", "already_done": False},
            rollback_data={"repo": "owner/repo", "branch": "agent/x"},
        )
        result = execute_rollback_action(action, systems)
        connector.delete_branch.assert_called_once_with(repo="owner/repo", branch="agent/x")
        assert result.success is True

    def test_rollback_create_pr_calls_close_pr(self):
        connector = self._make_gh_connector()
        systems = {"github": connector}
        action = ActionResult(
            action="create_pr", system="github", success=True,
            output={"pr_number": 42, "already_done": False},
            rollback_data={"repo": "owner/repo", "pr_number": 42},
        )
        result = execute_rollback_action(action, systems)
        connector.close_pr.assert_called_once_with(repo="owner/repo", pr_number=42)
        assert result.success is True

    def test_rollback_create_issue_calls_close_issue(self):
        connector = self._make_gh_connector()
        systems = {"github": connector}
        action = ActionResult(
            action="create_issue", system="github", success=True,
            output={"issue_number": 7, "already_done": False},
            rollback_data={"repo": "owner/repo", "issue_number": 7},
        )
        result = execute_rollback_action(action, systems)
        connector.close_issue.assert_called_once_with(repo="owner/repo", issue_number=7)
        assert result.success is True

    def test_rollback_delete_branch_calls_create_branch_from_sha(self):
        connector = self._make_gh_connector()
        systems = {"github": connector}
        action = ActionResult(
            action="delete_branch", system="github", success=True,
            output={"branch": "agent/x", "already_done": False},
            rollback_data={"repo": "owner/repo", "branch": "agent/x", "sha": "deadbeef"},
        )
        result = execute_rollback_action(action, systems)
        connector.create_branch_from_sha.assert_called_once_with(
            repo="owner/repo", branch="agent/x", sha="deadbeef"
        )
        assert result.success is True

    def test_rollback_merge_pr_is_irreversible(self):
        systems = {"github": MagicMock()}
        action = ActionResult(
            action="merge_pr", system="github", success=True,
            output={"merged": True, "already_done": False},
            rollback_data={},
        )
        result = execute_rollback_action(action, systems)
        assert result.success is False
        assert "cannot be reversed" in result.output["error"]

    def test_rollback_push_commit_is_irreversible(self):
        """push_commit cannot be undone — un-pushing requires destructive force-push."""
        systems = {"github": MagicMock()}
        action = ActionResult(
            action="push_commit", system="github", success=True,
            output={"sha": "deadbeef", "already_done": False},
            rollback_data={},
        )
        result = execute_rollback_action(action, systems)
        assert result.success is False
        assert "cannot be reversed" in result.output["error"]


# ── Postgres rollback dispatch ────────────────────────────────────────────────

class TestRollbackPostgres:
    def _make_pg_connector(self):
        connector = MagicMock()
        connector.delete_row.return_value = ActionResult(
            action="delete_row", system="postgres", success=True,
            output={"rows_deleted": 1, "already_done": False},
        )
        connector.update_row.return_value = ActionResult(
            action="update_row", system="postgres", success=True,
            output={"rows_updated": 1, "already_done": False},
        )
        connector.insert_row.return_value = ActionResult(
            action="insert_row", system="postgres", success=True,
            output={"id": 1, "already_done": False},
        )
        return connector

    def test_rollback_insert_row_calls_delete_row(self):
        connector = self._make_pg_connector()
        systems = {"postgres": connector}
        action = ActionResult(
            action="insert_row", system="postgres", success=True,
            output={"id": 1, "name": "jane", "already_done": False},
            rollback_data={"table": "users", "inserted_row": {"id": 1, "name": "jane"}},
        )
        result = execute_rollback_action(action, systems)
        # Should delete using "id" as the PK column
        connector.delete_row.assert_called_once_with(table="users", where={"id": 1})
        assert result.success is True

    def test_rollback_insert_row_uses_first_col_if_no_id(self):
        connector = self._make_pg_connector()
        systems = {"postgres": connector}
        action = ActionResult(
            action="insert_row", system="postgres", success=True,
            output={"email": "jane@co.com", "already_done": False},
            rollback_data={"table": "contacts", "inserted_row": {"email": "jane@co.com", "name": "jane"}},
        )
        execute_rollback_action(action, systems)
        connector.delete_row.assert_called_once_with(table="contacts", where={"email": "jane@co.com"})

    def test_rollback_update_row_reapplies_old_values(self):
        connector = self._make_pg_connector()
        systems = {"postgres": connector}
        action = ActionResult(
            action="update_row", system="postgres", success=True,
            output={"rows_updated": 1, "already_done": False},
            rollback_data={
                "table": "users",
                "old_rows": [{"id": 1, "name": "old_name"}],
                "where": {"id": 1},
            },
        )
        execute_rollback_action(action, systems)
        connector.update_row.assert_called_once_with(
            table="users",
            data={"id": 1, "name": "old_name"},
            where={"id": 1},
        )

    def test_rollback_update_row_skips_if_no_old_rows(self):
        connector = self._make_pg_connector()
        systems = {"postgres": connector}
        action = ActionResult(
            action="update_row", system="postgres", success=True,
            output={"rows_updated": 0, "already_done": False},
            rollback_data={"table": "users", "old_rows": [], "where": {"id": 999}},
        )
        result = execute_rollback_action(action, systems)
        connector.update_row.assert_not_called()
        assert result.success is True
        assert result.output.get("already_done") == "skipped"

    def test_rollback_delete_row_reinserts_deleted_rows(self):
        connector = self._make_pg_connector()
        systems = {"postgres": connector}
        action = ActionResult(
            action="delete_row", system="postgres", success=True,
            output={"rows_deleted": 1, "already_done": False},
            rollback_data={
                "table": "users",
                "deleted_rows": [{"id": 1, "name": "jane"}],
            },
        )
        execute_rollback_action(action, systems)
        connector.insert_row.assert_called_once_with(
            table="users", data={"id": 1, "name": "jane"}
        )

    def test_rollback_select_rows_is_skipped(self):
        connector = self._make_pg_connector()
        systems = {"postgres": connector}
        action = ActionResult(
            action="select_rows", system="postgres", success=True,
            output={"rows": []},
            rollback_data={},
        )
        result = execute_rollback_action(action, systems)
        connector.select_rows.assert_not_called()
        assert result.success is True
        assert result.output.get("already_done") == "skipped"


# ── System not found ──────────────────────────────────────────────────────────

class TestRollbackSystemNotFound:
    def test_missing_system_returns_failure(self):
        action = ActionResult(
            action="create_branch", system="github", success=True,
            output={}, rollback_data={"repo": "r", "branch": "b"},
        )
        result = execute_rollback_action(action, systems={})  # github not in systems
        assert result.success is False
        assert "not available for rollback" in result.output["error"]
