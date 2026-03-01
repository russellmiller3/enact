"""
Database layer for Enact Cloud.

Uses sqlite3 for local dev/test. Swap DB_URL to postgres:// in prod
(with psycopg2 and identical SQL — no ORM to swap out).

Schema init runs on startup via init_db(). Tables are CREATE IF NOT EXISTS
so it's safe to call repeatedly.
"""
import sqlite3
import os
from contextlib import contextmanager


def get_connection():
    # Read env var fresh each call so test fixtures can override it with monkeypatch.setenv
    # without requiring a module reload.
    db_path = os.environ.get("ENACT_DB_PATH", "cloud.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables. Safe to call on every startup."""
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id    TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                plan       TEXT NOT NULL DEFAULT 'free',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash   TEXT PRIMARY KEY,
                team_id    TEXT NOT NULL REFERENCES teams(team_id),
                label      TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS receipts (
                run_id       TEXT PRIMARY KEY,
                team_id      TEXT NOT NULL REFERENCES teams(team_id),
                workflow     TEXT NOT NULL,
                decision     TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS hitl_requests (
                hitl_id      TEXT PRIMARY KEY,
                team_id      TEXT NOT NULL REFERENCES teams(team_id),
                workflow     TEXT NOT NULL,
                payload      TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'PENDING',
                notify_email TEXT NOT NULL,
                callback_url TEXT,
                created_at   TEXT DEFAULT (datetime('now')),
                expires_at   TEXT NOT NULL,
                decided_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS hitl_receipts (
                hitl_id      TEXT PRIMARY KEY,
                team_id      TEXT NOT NULL REFERENCES teams(team_id),
                workflow     TEXT NOT NULL,
                decision     TEXT NOT NULL,
                decided_by   TEXT NOT NULL,
                decided_at   TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                signature    TEXT NOT NULL
            );
        """)
