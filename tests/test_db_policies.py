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
    block_ddl,
)
from enact.models import WorkflowContext


def make_context(payload=None):
    return WorkflowContext(
        workflow="test",
        user_email="agent@test.com",
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
            workflow="routine_cleanup", user_email="agent@test.com",
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


# ── block_ddl ─────────────────────────────────────────────────────────────────

class TestBlockDDL:
    def test_passes_when_no_sql_in_payload(self):
        ctx = make_context(payload={})
        result = block_ddl(ctx)
        assert result.passed is True
        assert result.policy == "block_ddl"

    def test_blocks_drop_table(self):
        ctx = make_context(payload={"sql": "DROP TABLE users"})
        result = block_ddl(ctx)
        assert result.passed is False
        assert "DROP" in result.reason

    def test_blocks_truncate(self):
        ctx = make_context(payload={"sql": "TRUNCATE TABLE users"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_alter_table(self):
        ctx = make_context(payload={"sql": "ALTER TABLE users ADD COLUMN foo TEXT"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_alter_sequence(self):
        # ALTER bare verb catches ALTER SEQUENCE, ALTER VIEW, etc.
        ctx = make_context(payload={"sql": "ALTER SEQUENCE payments_id_seq RESTART WITH 1"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_create_table(self):
        ctx = make_context(payload={"sql": "CREATE TABLE new_table (id INT)"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_create_function(self):
        # CREATE bare verb catches CREATE FUNCTION, CREATE VIEW, CREATE TRIGGER, etc.
        ctx = make_context(payload={"sql": "CREATE FUNCTION inject() RETURNS void AS $$ $$ LANGUAGE sql"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_drop_view(self):
        # DROP bare verb catches DROP VIEW, DROP FUNCTION, DROP SEQUENCE, etc.
        ctx = make_context(payload={"sql": "DROP VIEW active_users"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_case_insensitive(self):
        ctx = make_context(payload={"sql": "drop table users"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_passes_for_select(self):
        ctx = make_context(payload={"sql": "SELECT * FROM users WHERE id = 1"})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_passes_for_insert(self):
        ctx = make_context(payload={"sql": "INSERT INTO users (email) VALUES ('a@b.com')"})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_passes_for_update(self):
        ctx = make_context(payload={"sql": "UPDATE users SET name = 'foo' WHERE id = 1"})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_passes_column_named_created_at(self):
        # "created_at" must NOT trigger — \b after CREATE fails because next char is '_'
        ctx = make_context(payload={"sql": "SELECT created_at FROM users WHERE id = 1"})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_blocks_via_action_key(self):
        ctx = make_context(payload={"action": "DROP TABLE payments"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_passes_when_action_is_non_ddl(self):
        ctx = make_context(payload={"action": "insert_row"})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_passes_when_sql_is_empty_string(self):
        # Empty string sql key — nothing to inspect, should pass
        ctx = make_context(payload={"sql": ""})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_blocks_semicolon_joined_ddl(self):
        # No space before DROP — word boundary regex still catches it
        ctx = make_context(payload={"sql": "SELECT 1;DROP TABLE users"})
        result = block_ddl(ctx)
        assert result.passed is False
