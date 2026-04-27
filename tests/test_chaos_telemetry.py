"""Tests for the chaos harness telemetry SQLite layer."""
import sqlite3
from pathlib import Path

import pytest

from enact.chaos.telemetry import (
    init_db,
    write_run,
    update_run_end,
    write_action,
    write_policy_fired,
    write_damage_event,
    read_command_history,
)


def test_init_db_creates_schema_with_wal(tmp_path):
    db = tmp_path / "chaos.db"
    conn = init_db(str(db))
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert {"runs", "actions", "policies_fired", "damage_events"} <= tables
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_init_db_idempotent(tmp_path):
    db = tmp_path / "chaos.db"
    init_db(str(db))
    init_db(str(db))  # second call must not error
    # Schema should still be intact
    conn = sqlite3.connect(str(db))
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert {"runs", "actions", "policies_fired", "damage_events"} <= tables


def test_write_run_roundtrip(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    write_run(conn, "rid", "A", "20_dangerous_drop_customers",
              "dangerous", "2026-04-26T00:00:00Z", "/runs/rid")
    rows = conn.execute(
        "SELECT run_id, sweep, task_id, task_category, started_at, run_dir FROM runs"
    ).fetchall()
    assert rows == [("rid", "A", "20_dangerous_drop_customers",
                     "dangerous", "2026-04-26T00:00:00Z", "/runs/rid")]


def test_update_run_end_sets_end_time_and_summary(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    write_run(conn, "rid", "B", "t", "innocent", "t1", "/x")
    update_run_end(conn, "rid", "t2", "agent did stuff")
    row = conn.execute(
        "SELECT ended_at, agent_summary FROM runs WHERE run_id = ?",
        ("rid",),
    ).fetchone()
    assert row == ("t2", "agent did stuff")


def test_update_run_end_with_outcome(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    write_run(conn, "rid", "B", "t", "innocent", "t1", "/x")
    update_run_end(conn, "rid", "t2", "agent did stuff", outcome="clean")
    row = conn.execute(
        "SELECT ended_at, agent_summary, outcome FROM runs WHERE run_id = ?",
        ("rid",),
    ).fetchone()
    assert row == ("t2", "agent did stuff", "clean")


def test_runs_table_has_outcome_column(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    cols = {row[1] for row in conn.execute(
        "PRAGMA table_info(runs)"
    ).fetchall()}
    assert "outcome" in cols


def test_write_action_with_block_reason(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    write_run(conn, "rid", "A", "20_d", "dangerous", "t", "/x")
    write_action(conn, "rid", "Bash", 'psql -c "DROP TABLE customers"',
                 blocked=True,
                 block_reason="protect_tables: customers protected")
    rows = conn.execute(
        "SELECT command, blocked, block_reason FROM actions"
    ).fetchall()
    assert rows == [('psql -c "DROP TABLE customers"', 1,
                     "protect_tables: customers protected")]


def test_write_action_unblocked_has_null_block_reason(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    write_run(conn, "rid", "B", "t", "innocent", "t", "/x")
    write_action(conn, "rid", "Bash", "ls", blocked=False, block_reason=None)
    rows = conn.execute(
        "SELECT blocked, block_reason FROM actions"
    ).fetchall()
    assert rows == [(0, None)]


def test_write_policy_fired_passed_and_failed(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    write_run(conn, "rid", "A", "t", "dangerous", "t", "/x")
    write_policy_fired(conn, "rid", "protect_tables", passed=False,
                       reason="customers protected")
    write_policy_fired(conn, "rid", "code_freeze_active", passed=True,
                       reason="no freeze")
    rows = conn.execute(
        "SELECT policy, passed, reason FROM policies_fired ORDER BY id"
    ).fetchall()
    assert rows == [
        ("protect_tables", 0, "customers protected"),
        ("code_freeze_active", 1, "no freeze"),
    ]


def test_write_damage_event(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    write_run(conn, "rid", "B", "t", "dangerous", "t", "/x")
    write_damage_event(conn, "rid", "customers_emptied", "critical",
                       "row count went from 50 to 0")
    rows = conn.execute(
        "SELECT event_type, severity, detail FROM damage_events"
    ).fetchall()
    assert rows == [("customers_emptied", "critical",
                     "row count went from 50 to 0")]


def test_read_command_history_returns_ordered_commands(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    write_run(conn, "rid", "B", "t", "innocent", "t", "/x")
    write_action(conn, "rid", "Bash", "ls", blocked=False, block_reason=None)
    write_action(conn, "rid", "Bash", "git push --force",
                 blocked=False, block_reason=None)
    write_action(conn, "rid", "Bash", "pwd", blocked=False, block_reason=None)
    history = read_command_history(conn, "rid")
    assert history == ["ls", "git push --force", "pwd"]


def test_read_command_history_empty_for_unknown_run(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    assert read_command_history(conn, "nonexistent") == []


def test_foreign_key_enforced_on_actions(tmp_path):
    conn = init_db(str(tmp_path / "chaos.db"))
    # No matching run row exists; FK should refuse the insert
    with pytest.raises(sqlite3.IntegrityError):
        write_action(conn, "no-such-run", "Bash", "ls",
                     blocked=False, block_reason=None)
