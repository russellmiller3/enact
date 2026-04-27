"""
Chaos harness telemetry — SQLite writers for runs, actions, policies, damage.

WAL journal mode is enabled at init so concurrent writes from a single
parent dispatcher don't deadlock. Foreign keys are ON so an action without
its run row gets rejected at write time (catches sequencing bugs in the
runner).

Schema lives in this file as `_SCHEMA_SQL`. Each `write_*` helper opens
a transaction implicitly via the connection's autocommit / explicit commit.
"""
import sqlite3
from typing import Optional


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    sweep           TEXT NOT NULL,
    task_id         TEXT NOT NULL,
    task_category   TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    agent_summary   TEXT,
    outcome         TEXT,            -- damage|enact_blocked|agent_refused|clean
    run_dir         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    tool_name       TEXT NOT NULL,
    command         TEXT,
    blocked         INTEGER NOT NULL,
    block_reason    TEXT,
    timestamp       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS policies_fired (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    policy          TEXT NOT NULL,
    passed          INTEGER NOT NULL,
    reason          TEXT
);

CREATE TABLE IF NOT EXISTS damage_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    event_type      TEXT NOT NULL,
    severity        TEXT NOT NULL,
    detail          TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_sweep_task ON runs(sweep, task_id);
CREATE INDEX IF NOT EXISTS idx_actions_run ON actions(run_id);
CREATE INDEX IF NOT EXISTS idx_damage_run ON damage_events(run_id);
"""


def init_db(path: str = "chaos.db") -> sqlite3.Connection:
    """Open a SQLite connection at `path`, install schema, enable WAL + FKs.

    Idempotent — safe to call repeatedly. Returns an open connection.
    """
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn


def write_run(
    conn: sqlite3.Connection,
    run_id: str,
    sweep: str,
    task_id: str,
    task_category: str,
    started_at: str,
    run_dir: str,
) -> None:
    conn.execute(
        "INSERT INTO runs (run_id, sweep, task_id, task_category, started_at, run_dir) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, sweep, task_id, task_category, started_at, run_dir),
    )
    conn.commit()


def update_run_end(
    conn: sqlite3.Connection,
    run_id: str,
    ended_at: str,
    agent_summary: str,
    outcome: str | None = None,
) -> None:
    conn.execute(
        "UPDATE runs SET ended_at = ?, agent_summary = ?, outcome = ? "
        "WHERE run_id = ?",
        (ended_at, agent_summary, outcome, run_id),
    )
    conn.commit()


def write_action(
    conn: sqlite3.Connection,
    run_id: str,
    tool_name: str,
    command: Optional[str],
    blocked: bool,
    block_reason: Optional[str],
) -> int:
    """Insert one action row; returns the generated action id."""
    cur = conn.execute(
        "INSERT INTO actions (run_id, tool_name, command, blocked, block_reason) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, tool_name, command, 1 if blocked else 0, block_reason),
    )
    conn.commit()
    return cur.lastrowid


def write_policy_fired(
    conn: sqlite3.Connection,
    run_id: str,
    policy: str,
    passed: bool,
    reason: Optional[str],
) -> None:
    conn.execute(
        "INSERT INTO policies_fired (run_id, policy, passed, reason) "
        "VALUES (?, ?, ?, ?)",
        (run_id, policy, 1 if passed else 0, reason),
    )
    conn.commit()


def write_damage_event(
    conn: sqlite3.Connection,
    run_id: str,
    event_type: str,
    severity: str,
    detail: Optional[str],
) -> None:
    conn.execute(
        "INSERT INTO damage_events (run_id, event_type, severity, detail) "
        "VALUES (?, ?, ?, ?)",
        (run_id, event_type, severity, detail),
    )
    conn.commit()


def read_command_history(
    conn: sqlite3.Connection, run_id: str, include_blocked: bool = False
) -> list[str]:
    """Return the ordered list of command strings recorded for this run.

    By default returns only UNBLOCKED commands — i.e. commands that actually
    executed. Damage rules use this list to distinguish "agent caused damage"
    from "agent attempted but firewall stopped them". Pass include_blocked=True
    if you need to see every command including denials (useful for audits).
    """
    if include_blocked:
        rows = conn.execute(
            "SELECT command FROM actions WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT command FROM actions WHERE run_id = ? AND blocked = 0 ORDER BY id",
            (run_id,),
        ).fetchall()
    return [r[0] for r in rows if r[0] is not None]
