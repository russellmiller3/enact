"""
Tests for PostgresConnector.

All database calls are mocked — no real Postgres connection required.
psycopg2.connect is patched at the module level; the stored mock connection
is what each method calls through, so the patch only needs to be active
during construction.
"""
import pytest
from unittest.mock import MagicMock, patch
from enact.connectors.postgres import PostgresConnector
from enact.models import ActionResult


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_cursor(rows=None, one=None, description=None, rowcount=0):
    """Build a mock psycopg2 cursor."""
    cursor = MagicMock()
    cursor.fetchall.return_value = rows or []
    cursor.fetchone.return_value = one
    cursor.description = description or []
    cursor.rowcount = rowcount
    return cursor


def make_conn(cursor=None):
    """
    Build a mock psycopg2 connection.

    conn.cursor() is used as a context manager in the connector:
        with conn.cursor() as cursor: ...
    So we need the return value to support __enter__ / __exit__.
    """
    conn = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cursor or make_cursor())
    cm.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cm
    return conn


def make_pg(conn=None, allowed_actions=None):
    """
    Build a PostgresConnector with a mocked psycopg2 connection.

    The patch is only active for the duration of __init__ — long enough for
    psycopg2.connect(dsn) to return the mock connection and store it as
    self._conn. After that, methods call self._get_connection() which returns
    the already-stored mock.
    """
    with patch("enact.connectors.postgres.psycopg2") as mock_psycopg2:
        mock_psycopg2.connect.return_value = conn or make_conn()
        # Keep pgsql (psycopg2.sql) as the real module so SQL composition works
        import psycopg2.sql as real_sql
        mock_psycopg2.sql = real_sql
        pg = PostgresConnector(dsn="postgresql://test", allowed_actions=allowed_actions)
    return pg


# ---------------------------------------------------------------------------
# Allowlist + init
# ---------------------------------------------------------------------------

class TestPostgresConnectorInit:
    def test_default_allowlist_includes_all_four_actions(self):
        with patch("enact.connectors.postgres.psycopg2") as mock_psycopg2:
            import psycopg2.sql as real_sql
            mock_psycopg2.sql = real_sql
            mock_psycopg2.connect.return_value = MagicMock()
            pg = PostgresConnector(dsn="postgresql://test")
        assert "select_rows" in pg._allowed_actions
        assert "insert_row" in pg._allowed_actions
        assert "update_row" in pg._allowed_actions
        assert "delete_row" in pg._allowed_actions

    def test_custom_allowlist_restricts_to_specified_actions(self):
        with patch("enact.connectors.postgres.psycopg2") as mock_psycopg2:
            import psycopg2.sql as real_sql
            mock_psycopg2.sql = real_sql
            mock_psycopg2.connect.return_value = MagicMock()
            pg = PostgresConnector(dsn="postgresql://test", allowed_actions=["select_rows"])
        assert "select_rows" in pg._allowed_actions
        assert "insert_row" not in pg._allowed_actions
        assert "update_row" not in pg._allowed_actions
        assert "delete_row" not in pg._allowed_actions

    def test_action_blocked_by_allowlist_raises_permission_error(self):
        pg = make_pg(allowed_actions=["select_rows"])
        with pytest.raises(PermissionError):
            pg.insert_row("users", {"email": "x@y.com"})


# ---------------------------------------------------------------------------
# select_rows
# ---------------------------------------------------------------------------

class TestSelectRows:
    def test_returns_all_rows_when_no_where_clause(self):
        description = [("id",), ("email",)]
        cursor = make_cursor(
            rows=[(1, "a@b.com"), (2, "c@d.com")],
            description=description,
        )
        pg = make_pg(conn=make_conn(cursor))

        result = pg.select_rows("users")

        assert result.success is True
        assert result.action == "select_rows"
        assert result.system == "postgres"
        assert result.output["rows"] == [
            {"id": 1, "email": "a@b.com"},
            {"id": 2, "email": "c@d.com"},
        ]

    def test_filters_rows_with_where_clause(self):
        description = [("id",), ("email",)]
        cursor = make_cursor(rows=[(1, "a@b.com")], description=description)
        pg = make_pg(conn=make_conn(cursor))

        result = pg.select_rows("users", where={"email": "a@b.com"})

        assert result.success is True
        assert result.output["rows"] == [{"id": 1, "email": "a@b.com"}]
        # Confirm execute was called with the where value as a parameter
        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args
        assert list(where.values()) == ["a@b.com"] if (
            where := {"email": "a@b.com"}
        ) else True
        assert "a@b.com" in cursor.execute.call_args[0][1]

    def test_returns_empty_rows_list_when_no_match(self):
        cursor = make_cursor(rows=[], description=[("id",)])
        pg = make_pg(conn=make_conn(cursor))

        result = pg.select_rows("users", where={"email": "ghost@nowhere.com"})

        assert result.success is True
        assert result.output["rows"] == []

    def test_returns_failure_on_database_error(self):
        conn = make_conn()
        conn.cursor.side_effect = Exception("connection timed out")
        pg = make_pg(conn=conn)

        result = pg.select_rows("users")

        assert result.success is False
        assert result.action == "select_rows"
        assert "connection timed out" in result.output["error"]

    def test_select_blocked_by_allowlist_raises_permission_error(self):
        pg = make_pg(allowed_actions=["insert_row"])
        with pytest.raises(PermissionError):
            pg.select_rows("users")


# ---------------------------------------------------------------------------
# insert_row
# ---------------------------------------------------------------------------

class TestInsertRow:
    def test_returns_inserted_row_data_with_already_done_false(self):
        description = [("id",), ("email",), ("name",)]
        cursor = make_cursor(
            one=(42, "jane@acme.com", "Jane"),
            description=description,
        )
        conn = make_conn(cursor)
        pg = make_pg(conn=conn)

        result = pg.insert_row("users", {"email": "jane@acme.com", "name": "Jane"})

        assert result.success is True
        assert result.action == "insert_row"
        assert result.system == "postgres"
        assert result.output["id"] == 42
        assert result.output["email"] == "jane@acme.com"
        assert result.output["already_done"] is False
        conn.commit.assert_called_once()
        assert result.rollback_data["table"] == "users"
        assert result.rollback_data["inserted_row"] == {"id": 42, "email": "jane@acme.com", "name": "Jane"}

    def test_commits_transaction_on_success(self):
        description = [("id",)]
        cursor = make_cursor(one=(1,), description=description)
        conn = make_conn(cursor)
        pg = make_pg(conn=conn)

        pg.insert_row("logs", {"msg": "hello"})

        conn.commit.assert_called_once()

    def test_rolls_back_and_returns_failure_on_error(self):
        conn = make_conn()
        conn.cursor.side_effect = Exception("unique constraint violated")
        pg = make_pg(conn=conn)

        result = pg.insert_row("users", {"email": "dup@acme.com"})

        assert result.success is False
        assert "unique constraint violated" in result.output["error"]
        conn.rollback.assert_called_once()

    def test_insert_blocked_by_allowlist_raises_permission_error(self):
        pg = make_pg(allowed_actions=["select_rows"])
        with pytest.raises(PermissionError):
            pg.insert_row("users", {"email": "x@y.com"})


# ---------------------------------------------------------------------------
# update_row
# ---------------------------------------------------------------------------

class TestUpdateRow:
    def test_returns_rows_updated_count_with_already_done_false(self):
        # Pre-SELECT sees the old row; UPDATE affects 1 row.
        # Same cursor handles both: fetchall() returns old data, rowcount is used post-UPDATE.
        cursor = make_cursor(
            rows=[(1, "old@acme.com")],
            description=[("id",), ("email",)],
            rowcount=1,
        )
        conn = make_conn(cursor)
        pg = make_pg(conn=conn)

        result = pg.update_row("users", data={"email": "new@acme.com"}, where={"id": 1})

        assert result.success is True
        assert result.action == "update_row"
        assert result.system == "postgres"
        assert result.output["rows_updated"] == 1
        assert result.output["already_done"] is False
        assert result.rollback_data["table"] == "users"
        assert result.rollback_data["old_rows"] == [{"id": 1, "email": "old@acme.com"}]
        assert result.rollback_data["where"] == {"id": 1}
        conn.commit.assert_called_once()

    def test_zero_rows_updated_still_succeeds_with_already_done_false(self):
        """Zero rows updated means the WHERE matched nothing — not an error."""
        cursor = make_cursor(rowcount=0)
        conn = make_conn(cursor)
        pg = make_pg(conn=conn)

        result = pg.update_row("users", data={"email": "x@y.com"}, where={"id": 999})

        assert result.success is True
        assert result.output["rows_updated"] == 0
        assert result.output["already_done"] is False

    def test_rolls_back_and_returns_failure_on_error(self):
        conn = make_conn()
        conn.cursor.side_effect = Exception("deadlock detected")
        pg = make_pg(conn=conn)

        result = pg.update_row("users", data={"name": "X"}, where={"id": 1})

        assert result.success is False
        assert "deadlock detected" in result.output["error"]
        conn.rollback.assert_called_once()

    def test_update_blocked_by_allowlist_raises_permission_error(self):
        pg = make_pg(allowed_actions=["select_rows"])
        with pytest.raises(PermissionError):
            pg.update_row("users", data={"name": "X"}, where={"id": 1})


# ---------------------------------------------------------------------------
# delete_row
# ---------------------------------------------------------------------------

class TestDeleteRow:
    def test_deletes_existing_row_returns_already_done_false(self):
        # Pre-SELECT captures the row before deletion for rollback.
        cursor = make_cursor(
            rows=[(1, "jane@acme.com")],
            description=[("id",), ("email",)],
            rowcount=1,
        )
        conn = make_conn(cursor)
        pg = make_pg(conn=conn)

        result = pg.delete_row("users", where={"id": 1})

        assert result.success is True
        assert result.action == "delete_row"
        assert result.system == "postgres"
        assert result.output["rows_deleted"] == 1
        assert result.output["already_done"] is False
        assert result.rollback_data["table"] == "users"
        assert result.rollback_data["deleted_rows"] == [{"id": 1, "email": "jane@acme.com"}]
        conn.commit.assert_called_once()

    def test_deletes_multiple_rows_returns_already_done_false(self):
        cursor = make_cursor(
            rows=[(1, "a@b.com"), (2, "c@d.com"), (3, "e@f.com")],
            description=[("id",), ("email",)],
            rowcount=3,
        )
        conn = make_conn(cursor)
        pg = make_pg(conn=conn)

        result = pg.delete_row("logs", where={"user_id": 5})

        assert result.success is True
        assert result.output["rows_deleted"] == 3
        assert result.output["already_done"] is False
        assert len(result.rollback_data["deleted_rows"]) == 3

    def test_zero_rows_deleted_returns_already_done_deleted(self):
        """
        Idempotency: if nothing was deleted, the desired state (row gone)
        is already achieved. Return already_done='deleted' like GitHub's
        delete_branch does when the branch is already gone.
        """
        cursor = make_cursor(rows=[], description=[("id",)], rowcount=0)
        conn = make_conn(cursor)
        pg = make_pg(conn=conn)

        result = pg.delete_row("users", where={"id": 999})

        assert result.success is True
        assert result.output["rows_deleted"] == 0
        assert result.output["already_done"] == "deleted"
        assert result.rollback_data["deleted_rows"] == []  # Nothing to restore — expected

    def test_rolls_back_and_returns_failure_on_error(self):
        conn = make_conn()
        conn.cursor.side_effect = Exception("foreign key constraint")
        pg = make_pg(conn=conn)

        result = pg.delete_row("users", where={"id": 1})

        assert result.success is False
        assert "foreign key constraint" in result.output["error"]
        conn.rollback.assert_called_once()

    def test_delete_blocked_by_allowlist_raises_permission_error(self):
        pg = make_pg(allowed_actions=["select_rows"])
        with pytest.raises(PermissionError):
            pg.delete_row("users", where={"id": 1})
