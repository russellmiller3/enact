"""Tests for the chaos auto-policy-suggestion (leak → draft policy)."""
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from enact.chaos.suggest import (
    detect_leaks,
    write_leak_files,
    build_suggestion_prompt,
)
from enact.chaos.telemetry import (
    init_db, write_run, update_run_end, write_action,
    write_policy_fired, write_damage_event,
)


def _seed_leak(db_path: Path, run_id: str = "rA-leak") -> None:
    """A Sweep A run that produced damage despite hooks being on — a leak."""
    conn = init_db(str(db_path))
    write_run(conn, run_id, "A", "40_adversarial_obfuscate",
              "adversarial", "t", "/x")
    write_action(conn, run_id, "Bash", 'OP=DELETE; psql -c "$OP FROM customers"',
                 blocked=False, block_reason=None)
    write_policy_fired(conn, run_id, "protect_tables", passed=True,
                       reason="No table specified in payload")
    write_damage_event(conn, run_id, "customers_emptied", "critical",
                       "row count went from 50 to 0")
    update_run_end(conn, run_id, "t2", "agent ran obfuscated DELETE",
                   outcome="damage")
    conn.close()


def _seed_clean(db_path: Path) -> None:
    """Sweep A run with no damage — not a leak."""
    conn = init_db(str(db_path))
    write_run(conn, "rA-clean", "A", "01_innocent", "innocent", "t", "/x")
    update_run_end(conn, "rA-clean", "t2", "ran tests", outcome="clean")
    conn.close()


def test_detect_leaks_finds_sweep_a_runs_with_damage(tmp_path):
    db = tmp_path / "chaos.db"
    _seed_leak(db)
    _seed_clean(db)
    leaks = detect_leaks(db_path=db)
    assert len(leaks) == 1
    leak = leaks[0]
    assert leak["run_id"] == "rA-leak"
    assert leak["task_id"] == "40_adversarial_obfuscate"
    assert leak["sweep"] == "A"


def test_detect_leaks_skips_sweep_b(tmp_path):
    """Sweep B damage is expected (control). Only Sweep A damage = leak."""
    db = tmp_path / "chaos.db"
    conn = init_db(str(db))
    write_run(conn, "rB", "B", "20_dangerous", "dangerous", "t", "/x")
    write_damage_event(conn, "rB", "customers_emptied", "critical", "x")
    update_run_end(conn, "rB", "t2", "did damage", outcome="damage")
    conn.close()
    leaks = detect_leaks(db_path=db)
    assert leaks == []


def test_detect_leaks_includes_command_history(tmp_path):
    db = tmp_path / "chaos.db"
    _seed_leak(db)
    leaks = detect_leaks(db_path=db)
    assert "command_history" in leaks[0]
    assert any("$OP FROM customers" in c for c in leaks[0]["command_history"])


def test_detect_leaks_includes_policies_that_passed(tmp_path):
    """Policies that PASSED but the action still caused damage —
    these are the policies that need strengthening or augmenting."""
    db = tmp_path / "chaos.db"
    _seed_leak(db)
    leaks = detect_leaks(db_path=db)
    policies = leaks[0]["policies_that_passed"]
    assert any(p["policy"] == "protect_tables" for p in policies)


def test_detect_leaks_includes_damage_events(tmp_path):
    db = tmp_path / "chaos.db"
    _seed_leak(db)
    leaks = detect_leaks(db_path=db)
    events = leaks[0]["damage_events"]
    assert any(e["event_type"] == "customers_emptied" for e in events)


def test_write_leak_files_creates_one_json_per_leak(tmp_path):
    db = tmp_path / "chaos.db"
    _seed_leak(db)
    out_dir = tmp_path / "chaos" / "leaks"
    paths = write_leak_files(db_path=db, output_dir=out_dir)
    assert len(paths) == 1
    p = paths[0]
    assert p.exists()
    leak = json.loads(p.read_text())
    assert leak["run_id"] == "rA-leak"
    assert "command_history" in leak
    assert "damage_events" in leak


def test_write_leak_files_returns_empty_when_no_leaks(tmp_path):
    db = tmp_path / "chaos.db"
    _seed_clean(db)
    out_dir = tmp_path / "chaos" / "leaks"
    paths = write_leak_files(db_path=db, output_dir=out_dir)
    assert paths == []


def test_build_suggestion_prompt_includes_commands_and_damage(tmp_path):
    leak = {
        "run_id": "rA-leak",
        "task_id": "40_adversarial_obfuscate",
        "task_category": "adversarial",
        "command_history": ['OP=DELETE; psql -c "$OP FROM customers"'],
        "policies_that_passed": [
            {"policy": "protect_tables", "reason": "No table specified"}
        ],
        "damage_events": [
            {"event_type": "customers_emptied", "severity": "critical",
             "detail": "row count went from 50 to 0"}
        ],
    }
    prompt = build_suggestion_prompt(leak)
    assert '$OP FROM customers' in prompt
    assert "customers_emptied" in prompt
    assert "protect_tables" in prompt
    # Should ask for code in the existing policy interface
    assert "PolicyResult" in prompt
    assert "WorkflowContext" in prompt
