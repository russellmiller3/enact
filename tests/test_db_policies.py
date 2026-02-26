"""
Tests for database safety policies (enact/policies/db.py).

All policies are pure functions over WorkflowContext — no DB connections needed.
"""
import pytest
from enact.policies.db import (
    dont_delete_row,
    dont_delete_without_where,
    dont_update_without_where,
    protect_tables,
)
from enact.models import WorkflowContext


def make_context(payload=None):
    return WorkflowContext(
        workflow="test",
        actor_email="agent@test.com",
        payload=payload or {},
        systems={},
    )


# ── dont_delete_row ─────────────────────────────────────────────────────────────

class TestNoDeleteRow:
    def test_always_blocks(self):
        """Sentinel policy — blocks regardless of payload."""
        ctx = make_context()
        result = dont_delete_row(ctx)
        assert result.passed is False

    def test_blocks_even_with_where_clause(self):
        """WHERE clause doesn't matter — deletion is categorically blocked."""
        ctx = make_context({"table": "users", "where": {"id": 42}})
        result = dont_delete_row(ctx)
        assert result.passed is False

    def test_blocks_any_workflow_name(self):
        ctx = WorkflowContext(
            workflow="routine_cleanup", actor_email="agent@test.com",
            payload={}, systems={},
        )
        result = dont_delete_row(ctx)
        assert result.passed is False

    def test_reason_mentions_deletion(self):
        ctx = make_context()
        result = dont_delete_row(ctx)
        assert "deletion" in result.reason.lower()

    def test_policy_name(self):
        ctx = make_context()
        result = dont_delete_row(ctx)
        assert result.policy == "dont_delete_row"


# ── dont_delete_without_where ───────────────────────────────────────────────────

class TestNoDeleteWithoutWhere:
    def test_blocks_missing_where(self):
        """No where key in payload at all → block."""
        ctx = make_context({"table": "users"})
        result = dont_delete_without_where(ctx)
        assert result.passed is False

    def test_blocks_empty_where(self):
        """Empty dict where = delete ALL rows → block."""
        ctx = make_context({"table": "users", "where": {}})
        result = dont_delete_without_where(ctx)
        assert result.passed is False

    def test_passes_with_where_clause(self):
        """Non-empty where → safe to proceed."""
        ctx = make_context({"table": "users", "where": {"id": 42}})
        result = dont_delete_without_where(ctx)
        assert result.passed is True

    def test_passes_with_multi_condition_where(self):
        ctx = make_context({
            "table": "orders",
            "where": {"status": "cancelled", "user_id": 7},
        })
        result = dont_delete_without_where(ctx)
        assert result.passed is True

    def test_reason_mentions_where_on_block(self):
        ctx = make_context({"table": "users", "where": {}})
        result = dont_delete_without_where(ctx)
        assert "where" in result.reason.lower()

    def test_policy_name(self):
        ctx = make_context({"where": {"id": 1}})
        result = dont_delete_without_where(ctx)
        assert result.policy == "dont_delete_without_where"


# ── dont_update_without_where ───────────────────────────────────────────────────

class TestNoUpdateWithoutWhere:
    def test_blocks_missing_where(self):
        """UPDATE without WHERE updates every row in the table."""
        ctx = make_context({"table": "users", "data": {"status": "inactive"}})
        result = dont_update_without_where(ctx)
        assert result.passed is False

    def test_blocks_empty_where(self):
        ctx = make_context({"table": "users", "where": {}, "data": {"status": "inactive"}})
        result = dont_update_without_where(ctx)
        assert result.passed is False

    def test_passes_with_where_clause(self):
        ctx = make_context({
            "table": "users",
            "where": {"id": 99},
            "data": {"status": "inactive"},
        })
        result = dont_update_without_where(ctx)
        assert result.passed is True

    def test_reason_mentions_where_on_block(self):
        ctx = make_context({"where": {}})
        result = dont_update_without_where(ctx)
        assert "where" in result.reason.lower()

    def test_policy_name(self):
        ctx = make_context({"where": {"id": 1}})
        result = dont_update_without_where(ctx)
        assert result.policy == "dont_update_without_where"


# ── protect_tables ────────────────────────────────────────────────────────────

class TestProtectTables:
    def test_blocks_protected_table(self):
        policy = protect_tables(["users", "payments"])
        ctx = make_context({"table": "users"})
        result = policy(ctx)
        assert result.passed is False

    def test_blocks_second_protected_table(self):
        policy = protect_tables(["users", "payments"])
        ctx = make_context({"table": "payments"})
        result = policy(ctx)
        assert result.passed is False

    def test_allows_unprotected_table(self):
        policy = protect_tables(["users", "payments"])
        ctx = make_context({"table": "temp_logs"})
        result = policy(ctx)
        assert result.passed is True

    def test_missing_table_passes(self):
        """No table in payload → can't determine target → pass through."""
        policy = protect_tables(["users"])
        ctx = make_context({})
        result = policy(ctx)
        assert result.passed is True

    def test_table_name_in_reason_on_block(self):
        policy = protect_tables(["users"])
        ctx = make_context({"table": "users"})
        result = policy(ctx)
        assert "users" in result.reason

    def test_case_sensitive(self):
        """Table names are compared exactly — 'Users' != 'users'."""
        policy = protect_tables(["Users"])
        ctx = make_context({"table": "users"})
        result = policy(ctx)
        assert result.passed is True  # "users" not in ["Users"]

    def test_empty_protected_list_allows_everything(self):
        policy = protect_tables([])
        ctx = make_context({"table": "users"})
        result = policy(ctx)
        assert result.passed is True

    def test_policy_name(self):
        policy = protect_tables(["users"])
        ctx = make_context({"table": "logs"})
        result = policy(ctx)
        assert result.policy == "protect_tables"
