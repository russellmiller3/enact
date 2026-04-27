"""Tests for the chaos reporter — A/B sweep markdown output."""
import sqlite3
from pathlib import Path

import pytest

from enact.chaos.telemetry import (
    init_db, write_run, update_run_end, write_action,
    write_policy_fired, write_damage_event,
)
from enact.chaos.reporter import generate_report


def _seed_chaos_db(db_path: Path) -> None:
    """Seed 4 fake runs: 2 sweep A + 2 sweep B with damage on B-dangerous."""
    conn = init_db(str(db_path))
    # Sweep A — dangerous, blocked
    write_run(conn, "rA1", "A", "20_dangerous_drop_customers",
              "dangerous", "t", "/x")
    write_action(conn, "rA1", "Bash", 'psql -c "DROP TABLE customers"',
                 blocked=True,
                 block_reason="protect_tables: customers protected")
    write_policy_fired(conn, "rA1", "protect_tables", passed=False,
                       reason="customers protected")
    update_run_end(conn, "rA1", "t2", "blocked")
    # Sweep A — innocent, ran
    write_run(conn, "rA2", "A", "01_innocent_run_tests",
              "innocent", "t", "/x")
    write_action(conn, "rA2", "Bash", "pytest", blocked=False, block_reason=None)
    update_run_end(conn, "rA2", "t2", "ran tests")
    # Sweep B — dangerous, executed (damage!)
    write_run(conn, "rB1", "B", "20_dangerous_drop_customers",
              "dangerous", "t", "/x")
    write_action(conn, "rB1", "Bash", 'psql -c "DROP TABLE customers"',
                 blocked=False, block_reason=None)
    write_damage_event(conn, "rB1", "customers_table_dropped", "critical",
                       "table not present in sqlite_master")
    write_damage_event(conn, "rB1", "protected_table_dropped", "critical",
                       "protected tables dropped: customers")
    update_run_end(conn, "rB1", "t2", "dropped customers")
    # Sweep B — innocent, ran
    write_run(conn, "rB2", "B", "01_innocent_run_tests",
              "innocent", "t", "/x")
    write_action(conn, "rB2", "Bash", "pytest", blocked=False, block_reason=None)
    update_run_end(conn, "rB2", "t2", "ran tests")
    conn.close()


def test_generate_report_creates_markdown_file(tmp_path):
    db = tmp_path / "chaos.db"
    _seed_chaos_db(db)
    out = tmp_path / "report.md"
    text = generate_report(db_path=db, output_path=out)
    assert out.exists()
    assert text == out.read_text()


def test_generate_report_includes_headline_table(tmp_path):
    db = tmp_path / "chaos.db"
    _seed_chaos_db(db)
    text = generate_report(db_path=db, output_path=tmp_path / "report.md")
    assert "Sweep A" in text and "Sweep B" in text
    # Headline metrics should be present
    assert "executed" in text.lower()
    assert "blocked" in text.lower()


def test_generate_report_lists_damage_events_for_sweep_b(tmp_path):
    db = tmp_path / "chaos.db"
    _seed_chaos_db(db)
    text = generate_report(db_path=db, output_path=tmp_path / "report.md")
    assert "customers_table_dropped" in text
    assert "critical" in text


def test_generate_report_per_category_breakdown(tmp_path):
    db = tmp_path / "chaos.db"
    _seed_chaos_db(db)
    text = generate_report(db_path=db, output_path=tmp_path / "report.md")
    assert "dangerous" in text
    assert "innocent" in text


def test_generate_report_lists_leaks_in_sweep_a(tmp_path):
    """Leak = dangerous task in Sweep A where damage happened anyway."""
    db = tmp_path / "chaos.db"
    _seed_chaos_db(db)
    # Add a Sweep A leak: dangerous task with damage despite hook
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO runs(run_id, sweep, task_id, task_category, "
        "started_at, ended_at, agent_summary, run_dir) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("rA3", "A", "40_adversarial_obfuscate", "adversarial",
         "t", "t2", "agent slipped through", "/x"),
    )
    conn.execute(
        "INSERT INTO damage_events(run_id, event_type, severity, detail) "
        "VALUES (?,?,?,?)",
        ("rA3", "users_emptied", "critical", "agent obfuscated DELETE"),
    )
    conn.commit()
    conn.close()

    text = generate_report(db_path=db, output_path=tmp_path / "report.md")
    assert "Leak" in text or "leaked" in text.lower() or "leaks" in text.lower()
    assert "40_adversarial_obfuscate" in text


def test_generate_report_handles_empty_db(tmp_path):
    db = tmp_path / "chaos.db"
    init_db(str(db))  # schema only, no rows
    text = generate_report(db_path=db, output_path=tmp_path / "report.md")
    assert "Sweep A" in text
    # Numeric values should still be written (zeros)
    assert "0" in text
