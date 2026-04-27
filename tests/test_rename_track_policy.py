"""Tests for block_rename_then_drop — catches the rename-then-drop bypass.

Naive `protect_tables(["customers"])` only blocks DROP TABLE customers — it
doesn't catch ALTER TABLE customers RENAME TO archived; DROP TABLE archived.
This policy tracks RENAME aliases per session and applies protected-table
rules to all aliases.
"""
import pytest

from enact.models import WorkflowContext
from enact.policies.coding_agent import block_rename_then_drop, _RENAME_TRACKER


@pytest.fixture(autouse=True)
def clear_tracker():
    """Reset the per-session rename tracker between tests."""
    _RENAME_TRACKER.clear()


def _ctx(cmd: str, session_id: str = "default") -> WorkflowContext:
    return WorkflowContext(
        workflow="tool.bash",
        user_email="test@local",
        payload={"command": cmd, "session_id": session_id},
    )


def test_select_passes():
    result = block_rename_then_drop(_ctx("SELECT * FROM customers"))
    assert result.passed is True


def test_drop_unrenamed_table_passes():
    result = block_rename_then_drop(_ctx("DROP TABLE archived"))
    assert result.passed is True


def test_rename_then_drop_blocks():
    block_rename_then_drop(_ctx("ALTER TABLE customers RENAME TO archived"))
    result = block_rename_then_drop(_ctx("DROP TABLE archived"))
    assert result.passed is False
    assert "customers" in result.reason.lower()
    assert "archived" in result.reason.lower()


def test_different_session_isolated():
    block_rename_then_drop(_ctx("ALTER TABLE customers RENAME TO archived", "sess_a"))
    result = block_rename_then_drop(_ctx("DROP TABLE archived", "sess_b"))
    assert result.passed is True


def test_truncate_after_rename_blocks():
    block_rename_then_drop(_ctx("ALTER TABLE users RENAME TO old_users"))
    result = block_rename_then_drop(_ctx("TRUNCATE TABLE old_users"))
    assert result.passed is False


def test_delete_after_rename_blocks():
    block_rename_then_drop(_ctx("ALTER TABLE orders RENAME TO archived_orders"))
    result = block_rename_then_drop(_ctx("DELETE FROM archived_orders"))
    assert result.passed is False


def test_case_insensitive():
    block_rename_then_drop(_ctx("alter table CUSTOMERS rename to ARCHIVED"))
    result = block_rename_then_drop(_ctx("drop table archived"))
    assert result.passed is False


def test_rename_of_unprotected_table_is_not_tracked():
    """RENAME of a non-protected table doesn't put the alias on the watch list."""
    block_rename_then_drop(_ctx("ALTER TABLE temp_data RENAME TO temp_data_old"))
    result = block_rename_then_drop(_ctx("DROP TABLE temp_data_old"))
    assert result.passed is True


def test_psql_wrapped_command_caught():
    """Real-world shape: `psql -c "ALTER TABLE customers RENAME TO ..."`"""
    block_rename_then_drop(_ctx(
        'psql $DATABASE_URL -c "ALTER TABLE customers RENAME TO archived"'
    ))
    result = block_rename_then_drop(_ctx(
        'psql $DATABASE_URL -c "DROP TABLE archived"'
    ))
    assert result.passed is False


def test_no_command_passes():
    """Empty/missing payload command → pass-through (don't false-positive)."""
    ctx = WorkflowContext(
        workflow="tool.bash",
        user_email="test@local",
        payload={},
    )
    result = block_rename_then_drop(ctx)
    assert result.passed is True
