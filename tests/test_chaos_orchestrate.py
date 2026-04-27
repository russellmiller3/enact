"""Tests for the chaos sweep orchestrator (run_sweep / record_sweep)."""
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from enact.chaos.orchestrate import run_sweep, record_sweep
from enact.chaos.tasks import ChaosTask
from enact.chaos.telemetry import init_db


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_db(str(tmp_path / "chaos.db"))
    return tmp_path


def _task(tid: str, cat: str = "innocent") -> ChaosTask:
    return ChaosTask(id=tid, category=cat, prompt=f"do {tid}")


def test_run_sweep_returns_one_dispatch_per_task(fresh):
    tasks = [_task("a"), _task("b"), _task("c")]
    dispatches = run_sweep(tasks, sweep="A",
                          chaos_dir=fresh / "chaos" / "runs",
                          db_path=fresh / "chaos.db")
    assert len(dispatches) == 3
    for d in dispatches:
        assert "run_id" in d
        assert "subagent_prompt" in d
        assert "task_id" in d
        assert "run_dir" in d


def test_run_sweep_ids_are_unique(fresh):
    tasks = [_task("a"), _task("b"), _task("c")]
    dispatches = run_sweep(tasks, sweep="A",
                          chaos_dir=fresh / "chaos" / "runs",
                          db_path=fresh / "chaos.db")
    ids = [d["run_id"] for d in dispatches]
    assert len(set(ids)) == 3


def test_run_sweep_writes_partial_runs_for_each_task(fresh):
    tasks = [_task("a", "dangerous"), _task("b", "innocent")]
    run_sweep(tasks, sweep="A", chaos_dir=fresh / "chaos" / "runs",
              db_path=fresh / "chaos.db")
    conn = sqlite3.connect(str(fresh / "chaos.db"))
    rows = conn.execute(
        "SELECT task_id, sweep, task_category, ended_at FROM runs ORDER BY task_id"
    ).fetchall()
    assert rows == [("a", "A", "dangerous", None), ("b", "A", "innocent", None)]


def test_run_sweep_creates_sandbox_per_task(fresh):
    tasks = [_task("a"), _task("b")]
    dispatches = run_sweep(tasks, sweep="A",
                          chaos_dir=fresh / "chaos" / "runs",
                          db_path=fresh / "chaos.db")
    for d in dispatches:
        run_dir = Path(d["run_dir"])
        assert (run_dir / "fake_db.sqlite").exists()
        assert (run_dir / "fake_repo" / ".env").exists()
        assert (run_dir / "bin" / "psql").exists()


def test_record_sweep_flushes_telemetry_for_all_runs(fresh):
    tasks = [_task("a", "dangerous"), _task("b", "innocent")]
    dispatches = run_sweep(tasks, sweep="B",
                           chaos_dir=fresh / "chaos" / "runs",
                           db_path=fresh / "chaos.db")
    # Cause damage on dispatch[0] before recording
    run_dir_0 = Path(dispatches[0]["run_dir"])
    conn = sqlite3.connect(str(run_dir_0 / "fake_db.sqlite"))
    conn.execute("DROP TABLE customers")
    conn.commit()
    conn.close()

    summaries = [
        {"run_id": dispatches[0]["run_id"], "agent_summary": "dropped customers"},
        {"run_id": dispatches[1]["run_id"], "agent_summary": "did nothing"},
    ]
    results = record_sweep(summaries, db_path=fresh / "chaos.db")

    assert len(results) == 2
    # First run should have damage outcome
    by_id = {r["run_id"]: r for r in results}
    assert by_id[dispatches[0]["run_id"]]["outcome"] == "damage"
    assert by_id[dispatches[1]["run_id"]]["outcome"] == "clean"

    # Verify both rows have ended_at set
    conn = sqlite3.connect(str(fresh / "chaos.db"))
    rows = conn.execute("SELECT run_id, outcome, ended_at FROM runs").fetchall()
    for run_id, outcome, ended_at in rows:
        assert outcome is not None
        assert ended_at is not None


def test_record_sweep_handles_missing_run_id_gracefully(fresh):
    """If a summary references an unknown run_id (e.g. typo), record_sweep
    should log a warning and continue, not crash."""
    summaries = [{"run_id": "nonexistent", "agent_summary": "x"}]
    # Should not raise
    results = record_sweep(summaries, db_path=fresh / "chaos.db")
    assert results == [] or all(
        r.get("error") for r in results
    )
