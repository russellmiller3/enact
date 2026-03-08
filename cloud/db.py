"""
Database layer for Enact Cloud.

Dual-mode:
  - Production: set DATABASE_URL to your Supabase/Postgres connection string
  - Dev/test: leave DATABASE_URL unset → uses SQLite via ENACT_DB_PATH

All route SQL uses %s placeholders (Postgres-native). The SQLite wrapper
translates %s → ? automatically so routes are backend-agnostic.

Schema init runs on startup via init_db(). Tables are CREATE IF NOT EXISTS
so it's safe to call repeatedly.
"""
import os
import sqlite3
from contextlib import contextmanager


def _is_postgres():
    return bool(os.environ.get("DATABASE_URL"))


class PgConnection:
    """Wraps psycopg2 connection to match sqlite3's conn.execute().fetchone() chain."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        from psycopg2.extras import RealDictCursor
        cur = self._conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


class SqliteCompat:
    """Wraps sqlite3 connection to accept %s placeholders (Postgres style)."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        sql = sql.replace("%s", "?")
        if params:
            return self._conn.execute(sql, params)
        return self._conn.execute(sql)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_connection():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        import psycopg2
        conn = psycopg2.connect(database_url)
        return PgConnection(conn)
    else:
        db_path = os.environ.get("ENACT_DB_PATH", "cloud.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return SqliteCompat(conn)


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
    """Create all tables + indexes. Safe to call on every startup."""
    if _is_postgres():
        _init_postgres()
    else:
        _init_sqlite()


def _init_postgres():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id    TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                plan       TEXT NOT NULL DEFAULT 'free',
                created_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash   TEXT PRIMARY KEY,
                team_id    TEXT NOT NULL REFERENCES teams(team_id),
                label      TEXT,
                created_at TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                run_id        TEXT PRIMARY KEY,
                team_id       TEXT NOT NULL REFERENCES teams(team_id),
                workflow      TEXT NOT NULL,
                decision      TEXT NOT NULL,
                timestamp     TEXT,
                policy_names  TEXT,
                receipt_json  TEXT,
                metadata_json TEXT,
                payload_blob  TEXT,
                encrypted     BOOLEAN DEFAULT FALSE,
                created_at    TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hitl_requests (
                hitl_id      TEXT PRIMARY KEY,
                team_id      TEXT NOT NULL REFERENCES teams(team_id),
                workflow     TEXT NOT NULL,
                payload      TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'PENDING',
                notify_email TEXT NOT NULL,
                callback_url TEXT,
                created_at   TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                expires_at   TEXT NOT NULL,
                decided_at   TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hitl_receipts (
                hitl_id      TEXT PRIMARY KEY,
                team_id      TEXT NOT NULL REFERENCES teams(team_id),
                workflow     TEXT NOT NULL,
                decision     TEXT NOT NULL,
                decided_by   TEXT NOT NULL,
                decided_at   TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                signature    TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                team_id                TEXT PRIMARY KEY REFERENCES teams(team_id),
                stripe_customer_id     TEXT NOT NULL,
                stripe_subscription_id TEXT NOT NULL,
                status                 TEXT NOT NULL DEFAULT 'trialing',
                plan_name              TEXT NOT NULL DEFAULT 'cloud',
                current_period_end     TEXT,
                created_at             TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
                updated_at             TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkout_sessions (
                session_id     TEXT PRIMARY KEY,
                team_id        TEXT,
                raw_api_key    TEXT,
                customer_email TEXT,
                status         TEXT NOT NULL DEFAULT 'pending',
                retrieved_at   TEXT,
                created_at     TEXT DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
            )
        """)
        _create_indexes(conn)


def _init_sqlite():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id    TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                plan       TEXT NOT NULL DEFAULT 'free',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash   TEXT PRIMARY KEY,
                team_id    TEXT NOT NULL REFERENCES teams(team_id),
                label      TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                run_id        TEXT PRIMARY KEY,
                team_id       TEXT NOT NULL REFERENCES teams(team_id),
                workflow      TEXT NOT NULL,
                decision      TEXT NOT NULL,
                timestamp     TEXT,
                policy_names  TEXT,
                receipt_json  TEXT,
                metadata_json TEXT,
                payload_blob  TEXT,
                encrypted     INTEGER DEFAULT 0,
                created_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
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
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hitl_receipts (
                hitl_id      TEXT PRIMARY KEY,
                team_id      TEXT NOT NULL REFERENCES teams(team_id),
                workflow     TEXT NOT NULL,
                decision     TEXT NOT NULL,
                decided_by   TEXT NOT NULL,
                decided_at   TEXT NOT NULL,
                receipt_json TEXT NOT NULL,
                signature    TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                team_id                TEXT PRIMARY KEY REFERENCES teams(team_id),
                stripe_customer_id     TEXT NOT NULL,
                stripe_subscription_id TEXT NOT NULL,
                status                 TEXT NOT NULL DEFAULT 'trialing',
                plan_name              TEXT NOT NULL DEFAULT 'cloud',
                current_period_end     TEXT,
                created_at             TEXT DEFAULT (datetime('now')),
                updated_at             TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkout_sessions (
                session_id     TEXT PRIMARY KEY,
                team_id        TEXT,
                raw_api_key    TEXT,
                customer_email TEXT,
                status         TEXT NOT NULL DEFAULT 'pending',
                retrieved_at   TEXT,
                created_at     TEXT DEFAULT (datetime('now'))
            )
        """)
        _create_indexes(conn)


def _create_indexes(conn):
    """Indexes for query performance. Safe to call repeatedly (IF NOT EXISTS)."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_team_created ON receipts(team_id, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_team_workflow ON receipts(team_id, workflow)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_team_decision ON receipts(team_id, decision)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hitl_team ON hitl_requests(team_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_team ON api_keys(team_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_customer ON subscriptions(stripe_customer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_checkout_sessions_status ON checkout_sessions(status)")
