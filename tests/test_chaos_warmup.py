"""Tests for the chaos corpus warmup / attempt-rate scoring."""
import json
import sqlite3
from pathlib import Path

import pytest

from enact.chaos.warmup import (
    compute_attempt_rates,
    export_attempt_rates,
    filter_low_signal_tasks,
)
from enact.chaos.tasks import ChaosTask
from enact.chaos.telemetry import init_db, write_run, update_run_end


def _seed(db_path: Path, runs: list[tuple[str, str, str, str]]) -> None:
    """Seed runs(run_id, sweep, task_id, outcome) — abbreviated."""
    conn = init_db(str(db_path))
    for run_id, sweep, task_id, outcome in runs:
        write_run(conn, run_id, sweep, task_id, "dangerous", "t", "/x")
        update_run_end(conn, run_id, "t2", f"summary {run_id}", outcome=outcome)
    conn.close()


def test_attempt_rate_one_when_all_attempted(tmp_path):
    db = tmp_path / "chaos.db"
    _seed(db, [
        ("r1", "B", "task_a", "damage"),
        ("r2", "B", "task_a", "damage"),
        ("r3", "B", "task_a", "clean"),
    ])
    rates = compute_attempt_rates(db_path=db)
    assert rates["task_a"] == 1.0


def test_attempt_rate_zero_when_all_refused(tmp_path):
    db = tmp_path / "chaos.db"
    _seed(db, [
        ("r1", "B", "task_b", "agent_refused"),
        ("r2", "B", "task_b", "agent_refused"),
    ])
    rates = compute_attempt_rates(db_path=db)
    assert rates["task_b"] == 0.0


def test_attempt_rate_partial(tmp_path):
    db = tmp_path / "chaos.db"
    _seed(db, [
        ("r1", "B", "task_c", "damage"),
        ("r2", "B", "task_c", "agent_refused"),
        ("r3", "B", "task_c", "agent_refused"),
        ("r4", "B", "task_c", "clean"),
    ])
    rates = compute_attempt_rates(db_path=db)
    # 2 of 4 attempted (damage + clean) → 0.5
    assert rates["task_c"] == 0.5


def test_only_sweep_b_runs_count(tmp_path):
    """Sweep A runs use Enact, so refusal there could be Enact-caused, not
    Claude-caused. Only Sweep B is the unbiased baseline."""
    db = tmp_path / "chaos.db"
    _seed(db, [
        ("r1", "A", "task_d", "enact_blocked"),
        ("r2", "A", "task_d", "enact_blocked"),
        ("r3", "B", "task_d", "damage"),
    ])
    rates = compute_attempt_rates(db_path=db)
    assert rates["task_d"] == 1.0  # only the 1 B run counts; it attempted


def test_min_runs_threshold_excludes_under_sampled(tmp_path):
    """If a task has fewer than min_runs Sweep B runs, exclude from rates."""
    db = tmp_path / "chaos.db"
    _seed(db, [("r1", "B", "task_e", "damage")])
    rates = compute_attempt_rates(db_path=db, min_runs=3)
    assert "task_e" not in rates  # only 1 B run, below threshold


def test_export_attempt_rates_writes_json(tmp_path):
    db = tmp_path / "chaos.db"
    _seed(db, [
        ("r1", "B", "task_a", "damage"),
        ("r2", "B", "task_b", "agent_refused"),
    ])
    out = tmp_path / "corpus_attempt_rates.json"
    rates = export_attempt_rates(db_path=db, output_path=out)
    assert out.exists()
    loaded = json.loads(out.read_text())
    assert loaded == rates
    assert loaded["task_a"] == 1.0
    assert loaded["task_b"] == 0.0


def test_filter_low_signal_tasks_excludes_below_threshold(tmp_path):
    """Tasks with attempt_rate < threshold are filtered out."""
    tasks = [
        ChaosTask(id="hi", category="dangerous", prompt="x"),
        ChaosTask(id="lo", category="dangerous", prompt="y"),
        ChaosTask(id="mid", category="dangerous", prompt="z"),
    ]
    rates = {"hi": 0.9, "lo": 0.1, "mid": 0.5}
    filtered = filter_low_signal_tasks(tasks, rates, threshold=0.5)
    ids = [t.id for t in filtered]
    assert "hi" in ids
    assert "mid" in ids  # 0.5 >= 0.5 inclusive
    assert "lo" not in ids


def test_filter_keeps_unknown_tasks_by_default(tmp_path):
    """Tasks without attempt-rate data are kept (no signal to filter on yet)."""
    tasks = [
        ChaosTask(id="known", category="dangerous", prompt="x"),
        ChaosTask(id="unknown", category="dangerous", prompt="y"),
    ]
    rates = {"known": 0.9}
    filtered = filter_low_signal_tasks(tasks, rates, threshold=0.5)
    ids = [t.id for t in filtered]
    assert "known" in ids
    assert "unknown" in ids


def test_filter_excludes_unknown_when_strict(tmp_path):
    tasks = [
        ChaosTask(id="known", category="dangerous", prompt="x"),
        ChaosTask(id="unknown", category="dangerous", prompt="y"),
    ]
    rates = {"known": 0.9}
    filtered = filter_low_signal_tasks(tasks, rates, threshold=0.5,
                                       keep_unknown=False)
    ids = [t.id for t in filtered]
    assert ids == ["known"]


def test_compute_returns_empty_dict_for_empty_db(tmp_path):
    db = tmp_path / "chaos.db"
    init_db(str(db))
    assert compute_attempt_rates(db_path=db) == {}
