"""
Tests for enact/rollback.py — execute_rollback_action() dispatch logic.
All connector calls are mocked. No real GitHub/Postgres API calls made.
"""
import pytest
from unittest.mock import MagicMock, patch
from enact.models import ActionResult, PolicyResult
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


# ── EnactClient.rollback() ────────────────────────────────────────────────────

from enact.client import EnactClient
from enact.models import Receipt
from enact.receipt import build_receipt, sign_receipt, write_receipt


def _write_test_receipt(tmp_path, actions_taken, decision="PASS"):
    """Helper: write a receipt to tmp_path and return its run_id."""
    receipt = build_receipt(
        workflow="test_workflow",
        actor_email="agent@test.com",
        payload={"x": 1},
        policy_results=[PolicyResult(policy="p", passed=True, reason="ok")],
        decision=decision,
        actions_taken=actions_taken,
    )
    receipt = sign_receipt(receipt, "enact-default-secret")
    write_receipt(receipt, str(tmp_path))
    return receipt.run_id


class TestEnactClientRollbackGate:
    def test_rollback_disabled_by_default(self):
        client = EnactClient()
        with pytest.raises(PermissionError, match="premium feature"):
            client.rollback("any-run-id")

    def test_rollback_enabled_flag(self):
        client = EnactClient(rollback_enabled=True)
        assert client._rollback_enabled is True

    def test_rollback_missing_receipt_raises(self, tmp_path):
        client = EnactClient(rollback_enabled=True, receipt_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError, match="No receipt found"):
            client.rollback("nonexistent-uuid")

    def test_rollback_blocked_run_raises(self, tmp_path):
        run_id = _write_test_receipt(tmp_path, actions_taken=[], decision="BLOCK")
        client = EnactClient(rollback_enabled=True, receipt_dir=str(tmp_path))
        with pytest.raises(ValueError, match="Cannot rollback a blocked run"):
            client.rollback(run_id)


class TestEnactClientRollbackExecution:
    def test_rollback_reverses_actions_in_reverse_order(self, tmp_path):
        """Actions are undone last-to-first."""
        actions = [
            ActionResult(
                action="create_branch", system="github", success=True,
                output={"branch": "agent/x", "already_done": False},
                rollback_data={"repo": "owner/repo", "branch": "agent/x"},
            ),
            ActionResult(
                action="create_pr", system="github", success=True,
                output={"pr_number": 1, "already_done": False},
                rollback_data={"repo": "owner/repo", "pr_number": 1},
            ),
        ]
        run_id = _write_test_receipt(tmp_path, actions)

        mock_gh = MagicMock()
        mock_gh.close_pr.return_value = ActionResult(
            action="close_pr", system="github", success=True, output={}
        )
        mock_gh.delete_branch.return_value = ActionResult(
            action="delete_branch", system="github", success=True, output={}
        )

        client = EnactClient(
            systems={"github": mock_gh},
            rollback_enabled=True,
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.rollback(run_id)

        # Verify order: PR closed first (it was last), then branch deleted
        call_order = [call[0] for call in mock_gh.method_calls]
        assert call_order.index("close_pr") < call_order.index("delete_branch")

    def test_rollback_skips_already_done_noops(self, tmp_path):
        """Actions with already_done set were not actually performed — skip them."""
        actions = [
            ActionResult(
                action="create_branch", system="github", success=True,
                output={"branch": "agent/x", "already_done": "created"},
                rollback_data={},
            ),
        ]
        run_id = _write_test_receipt(tmp_path, actions)

        mock_gh = MagicMock()
        client = EnactClient(
            systems={"github": mock_gh},
            rollback_enabled=True,
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.rollback(run_id)

        mock_gh.delete_branch.assert_not_called()

    def test_rollback_skips_failed_actions(self, tmp_path):
        """Failed actions produced no state change — nothing to undo."""
        actions = [
            ActionResult(
                action="create_branch", system="github", success=False,
                output={"error": "API error"},
                rollback_data={},
            ),
        ]
        run_id = _write_test_receipt(tmp_path, actions)

        mock_gh = MagicMock()
        client = EnactClient(
            systems={"github": mock_gh},
            rollback_enabled=True,
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.rollback(run_id)

        mock_gh.delete_branch.assert_not_called()

    def test_rollback_partial_failure_continues(self, tmp_path):
        """If one rollback step fails, the rest still execute."""
        actions = [
            ActionResult(
                action="create_branch", system="github", success=True,
                output={"branch": "agent/x", "already_done": False},
                rollback_data={"repo": "owner/repo", "branch": "agent/x"},
            ),
            ActionResult(
                action="create_pr", system="github", success=True,
                output={"pr_number": 1, "already_done": False},
                rollback_data={"repo": "owner/repo", "pr_number": 1},
            ),
        ]
        run_id = _write_test_receipt(tmp_path, actions)

        mock_gh = MagicMock()
        # close_pr fails, delete_branch should still be called
        mock_gh.close_pr.return_value = ActionResult(
            action="close_pr", system="github", success=False, output={"error": "API down"}
        )
        mock_gh.delete_branch.return_value = ActionResult(
            action="delete_branch", system="github", success=True, output={}
        )

        client = EnactClient(
            systems={"github": mock_gh},
            rollback_enabled=True,
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.rollback(run_id)

        mock_gh.close_pr.assert_called_once()
        mock_gh.delete_branch.assert_called_once()
        assert result.success is False  # partial failure → RunResult.success=False
        assert receipt.decision == "PARTIAL"  # not "PASS" — caller must know undo was incomplete

    def test_rollback_produces_signed_receipt(self, tmp_path):
        actions = [
            ActionResult(
                action="create_branch", system="github", success=True,
                output={"branch": "agent/x", "already_done": False},
                rollback_data={"repo": "owner/repo", "branch": "agent/x"},
            ),
        ]
        run_id = _write_test_receipt(tmp_path, actions)

        mock_gh = MagicMock()
        mock_gh.delete_branch.return_value = ActionResult(
            action="delete_branch", system="github", success=True, output={}
        )
        client = EnactClient(
            systems={"github": mock_gh},
            rollback_enabled=True,
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.rollback(run_id)

        assert receipt.signature != ""
        assert receipt.decision == "PASS"

    def test_rollback_receipt_references_original_run_id(self, tmp_path):
        actions = [
            ActionResult(
                action="create_branch", system="github", success=True,
                output={"branch": "agent/x", "already_done": False},
                rollback_data={"repo": "owner/repo", "branch": "agent/x"},
            ),
        ]
        run_id = _write_test_receipt(tmp_path, actions)

        mock_gh = MagicMock()
        mock_gh.delete_branch.return_value = ActionResult(
            action="delete_branch", system="github", success=True, output={}
        )
        client = EnactClient(
            systems={"github": mock_gh},
            rollback_enabled=True,
            receipt_dir=str(tmp_path),
        )
        _, receipt = client.rollback(run_id)

        assert receipt.payload["original_run_id"] == run_id
        assert receipt.payload["rollback"] is True
