"""
Tests for reference workflows.
Postgres connector is mocked — no real DB required.
"""
import pytest
from unittest.mock import MagicMock
from enact.workflows.db_safe_insert import db_safe_insert
from enact.models import WorkflowContext, ActionResult


def make_pg_mock(select_rows_result=None, insert_row_result=None):
    """Build a mock Postgres connector."""
    pg = MagicMock()
    pg.select_rows.return_value = select_rows_result or ActionResult(
        action="select_rows", system="postgres", success=True, output={"rows": []}
    )
    pg.insert_row.return_value = insert_row_result or ActionResult(
        action="insert_row", system="postgres", success=True, output={"id": 1, "email": "jane@acme.com"}
    )
    return pg


def make_context(pg, table="users", data=None, unique_key=None):
    payload = {"table": table, "data": data or {"email": "jane@acme.com", "name": "Jane"}}
    if unique_key:
        payload["unique_key"] = unique_key
    return WorkflowContext(
        workflow="db_safe_insert",
        user_email="agent@test.com",
        payload=payload,
        systems={"postgres": pg},
    )


class TestDbSafeInsert:
    def test_insert_without_unique_check(self):
        """When no unique_key, just inserts directly."""
        pg = make_pg_mock()
        ctx = make_context(pg)

        results = db_safe_insert(ctx)

        assert len(results) == 1
        assert results[0].action == "insert_row"
        assert results[0].success is True
        pg.select_rows.assert_not_called()
        pg.insert_row.assert_called_once()

    def test_insert_with_unique_key_no_existing_row(self):
        """unique_key specified, no existing row → inserts."""
        pg = make_pg_mock(
            select_rows_result=ActionResult(
                action="select_rows", system="postgres", success=True, output={"rows": []}
            )
        )
        ctx = make_context(pg, data={"email": "jane@acme.com"}, unique_key="email")

        results = db_safe_insert(ctx)

        # select_rows called to check, then insert_row called
        assert len(results) == 2
        assert results[0].action == "select_rows"
        assert results[1].action == "insert_row"
        assert results[1].success is True

    def test_blocks_duplicate_row(self):
        """When existing row found, blocks insert and returns error."""
        pg = make_pg_mock(
            select_rows_result=ActionResult(
                action="select_rows",
                system="postgres",
                success=True,
                output={"rows": [{"id": 99, "email": "jane@acme.com"}]},
            )
        )
        ctx = make_context(pg, data={"email": "jane@acme.com"}, unique_key="email")

        results = db_safe_insert(ctx)

        assert len(results) == 2
        assert results[0].action == "select_rows"
        assert results[1].action == "insert_row"
        assert results[1].success is False
        assert "already exists" in results[1].output["error"]
        pg.insert_row.assert_not_called()  # Real insert never called

    def test_unique_key_not_in_data_skips_check(self):
        """unique_key specified but not present in data → skips check, inserts."""
        pg = make_pg_mock()
        ctx = make_context(
            pg,
            data={"name": "Jane"},  # no 'email' key
            unique_key="email",
        )

        results = db_safe_insert(ctx)

        assert len(results) == 1
        assert results[0].action == "insert_row"
        pg.select_rows.assert_not_called()

    def test_insert_failure_propagates(self):
        """When insert_row returns failure, it's included in results."""
        pg = make_pg_mock(
            insert_row_result=ActionResult(
                action="insert_row",
                system="postgres",
                success=False,
                output={"error": "DB connection failed"},
            )
        )
        ctx = make_context(pg)

        results = db_safe_insert(ctx)

        assert len(results) == 1
        assert results[0].success is False
        assert "DB connection failed" in results[0].output["error"]
