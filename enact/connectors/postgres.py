"""
Postgres connector — wraps psycopg2 for safe, allowlist-gated database operations.

Design: allowlist-first
------------------------
Every public method calls _check_allowed() before touching the database.
This mirrors the GitHubConnector pattern: even if a bug in Enact invokes the
wrong action, the connector itself refuses unless that action was explicitly
permitted at init time.

Error handling pattern
-----------------------
Mutating methods (insert_row, update_row, delete_row) catch broad Exception,
rollback, and return ActionResult(success=False, output={"error": ...}).
select_rows catches and returns failure without a rollback (read-only).

The one exception: _check_allowed() raises PermissionError for unlisted actions.
This is a programming error, not a runtime DB failure — it should blow up loudly.

SQL safety
-----------
Table and column names are composed via psycopg2.sql.Identifier(), which
double-quotes identifiers and escapes them. Values are passed as parameterized
arguments (%s / Placeholder()), never interpolated into the query string.
This prevents SQL injection on both the schema and data sides.

Idempotency (already_done convention)
--------------------------------------
delete_row: if rowcount == 0, the desired state (row gone) is already achieved.
  Returns already_done="deleted" — safe to retry without double-deleting.

insert_row / update_row: always already_done=False. Idempotency for inserts
  lives at the workflow level (db_safe_insert does select_rows → insert_row).
  Updates are naturally idempotent (setting the same value twice is harmless).

All future connectors MUST follow this convention (documented in CLAUDE.md).

Usage:
    pg = PostgresConnector(
        dsn="postgresql://user:pass@host:5432/dbname",
        allowed_actions=["select_rows", "insert_row"],  # restrict to what this agent needs
    )
    result = pg.insert_row("users", {"email": "jane@acme.com", "name": "Jane"})
"""
try:
    import psycopg2
    from psycopg2 import sql as pgsql
except ImportError:
    psycopg2 = None
    pgsql = None

from enact.models import ActionResult


class PostgresConnector:
    """
    Thin wrapper around psycopg2 with per-instance action allowlisting.

    Instantiate once and pass into EnactClient(systems={"postgres": pg}).
    The connector is then available to policies and workflows via
    context.systems["postgres"].

    Works with any Postgres-compatible host: Supabase, Neon, Railway, AWS RDS.
    Pass a standard libpq DSN: "postgresql://user:pass@host:5432/dbname"
    """

    def __init__(self, dsn: str, allowed_actions: list[str] | None = None):
        """
        Initialise the connector.

        Args:
            dsn             — libpq connection string, e.g.
                              "postgresql://user:pass@host:5432/dbname"
                              Supports SSL params: "?sslmode=require"
            allowed_actions — explicit list of action names this connector instance
                              is permitted to execute. Defaults to all four actions.
                              Restricting this at init time is recommended for
                              production — a read-only agent should not be able
                              to delete rows.
        """
        if psycopg2 is None:
            raise ImportError(
                "psycopg2 is required for PostgresConnector. "
                "Install it with: pip install 'enact-sdk[postgres]'"
            )
        self._conn = psycopg2.connect(dsn)
        self._allowed_actions = set(
            allowed_actions
            or ["select_rows", "insert_row", "update_row", "delete_row"]
        )

    def _check_allowed(self, action: str):
        """
        Raise PermissionError if the action is not in this connector's allowlist.

        Called at the top of every public method — loud and traceable.
        """
        if action not in self._allowed_actions:
            raise PermissionError(
                f"Action '{action}' not in allowlist: {self._allowed_actions}"
            )

    def _get_connection(self):
        """
        Return the psycopg2 connection.

        Isolated into a method so tests can verify it is called and the
        stored mock connection is used without needing to patch the module.
        """
        return self._conn

    def select_rows(self, table: str, where: dict | None = None) -> ActionResult:
        """
        Fetch rows from a table with an optional WHERE clause.

        Args:
            table — table name (safe: composed via Identifier)
            where — dict of {column: value} equality filters (AND-joined).
                    Pass None or {} to fetch all rows.

        Returns:
            ActionResult — success=True with {"rows": [{"col": val, ...}, ...]},
                           or success=False with {"error": str(e)}
        """
        self._check_allowed("select_rows")
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                if where:
                    conditions = pgsql.SQL(" AND ").join(
                        pgsql.SQL("{} = {}").format(
                            pgsql.Identifier(k), pgsql.Placeholder()
                        )
                        for k in where
                    )
                    query = pgsql.SQL("SELECT * FROM {} WHERE {}").format(
                        pgsql.Identifier(table), conditions
                    )
                    cursor.execute(query, list(where.values()))
                else:
                    query = pgsql.SQL("SELECT * FROM {}").format(
                        pgsql.Identifier(table)
                    )
                    cursor.execute(query)

                rows = cursor.fetchall()
                cols = [desc[0] for desc in (cursor.description or [])]
                return ActionResult(
                    action="select_rows",
                    system="postgres",
                    success=True,
                    output={"rows": [dict(zip(cols, row)) for row in rows]},
                )
        except Exception as e:
            return ActionResult(
                action="select_rows",
                system="postgres",
                success=False,
                output={"error": str(e)},
            )

    def insert_row(self, table: str, data: dict) -> ActionResult:
        """
        Insert a row and return the inserted record (including DB-assigned fields
        like auto-increment IDs and server defaults).

        Uses RETURNING * so the caller gets back the full row as stored,
        not just what was passed in.

        Args:
            table — table name
            data  — dict of {column: value} pairs to insert

        Returns:
            ActionResult — success=True with {**inserted_row, "already_done": False},
                           or success=False with {"error": str(e)}
        """
        self._check_allowed("insert_row")
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                query = pgsql.SQL(
                    "INSERT INTO {} ({}) VALUES ({}) RETURNING *"
                ).format(
                    pgsql.Identifier(table),
                    pgsql.SQL(", ").join(map(pgsql.Identifier, data.keys())),
                    pgsql.SQL(", ").join([pgsql.Placeholder()] * len(data)),
                )
                cursor.execute(query, list(data.values()))
                row = cursor.fetchone()
                conn.commit()
                cols = [desc[0] for desc in (cursor.description or [])]
                row_dict = dict(zip(cols, row)) if row else {}
                return ActionResult(
                    action="insert_row",
                    system="postgres",
                    success=True,
                    output={**row_dict, "already_done": False},
                    rollback_data={"table": table, "inserted_row": row_dict},
                )
        except Exception as e:
            if conn:
                conn.rollback()
            return ActionResult(
                action="insert_row",
                system="postgres",
                success=False,
                output={"error": str(e)},
            )

    def update_row(self, table: str, data: dict, where: dict) -> ActionResult:
        """
        Update rows matching the WHERE clause to the values in data.

        Args:
            table — table name
            data  — dict of {column: new_value} pairs to SET
            where — dict of {column: value} equality filters (AND-joined)

        Returns:
            ActionResult — success=True with {"rows_updated": int, "already_done": False},
                           or success=False with {"error": str(e)}

        Note: rows_updated=0 means the WHERE clause matched nothing — not an error.
        Updates are naturally idempotent (setting the same value twice is harmless),
        so already_done is always False rather than trying to detect no-ops.
        """
        self._check_allowed("update_row")
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                where_clause = pgsql.SQL(" AND ").join(
                    pgsql.SQL("{} = {}").format(
                        pgsql.Identifier(k), pgsql.Placeholder()
                    )
                    for k in where
                )
                # --- Pre-SELECT: capture current state for rollback ---
                pre_query = pgsql.SQL("SELECT * FROM {} WHERE {}").format(
                    pgsql.Identifier(table), where_clause
                )
                cursor.execute(pre_query, list(where.values()))
                old_rows_raw = cursor.fetchall()
                old_cols = [desc[0] for desc in (cursor.description or [])]
                old_rows = [dict(zip(old_cols, row)) for row in old_rows_raw]
                # --- UPDATE ---
                set_clause = pgsql.SQL(", ").join(
                    pgsql.SQL("{} = {}").format(
                        pgsql.Identifier(k), pgsql.Placeholder()
                    )
                    for k in data
                )
                query = pgsql.SQL("UPDATE {} SET {} WHERE {}").format(
                    pgsql.Identifier(table), set_clause, where_clause
                )
                cursor.execute(query, list(data.values()) + list(where.values()))
                conn.commit()
                return ActionResult(
                    action="update_row",
                    system="postgres",
                    success=True,
                    output={"rows_updated": cursor.rowcount, "already_done": False},
                    rollback_data={"table": table, "old_rows": old_rows, "where": where},
                )
        except Exception as e:
            if conn:
                conn.rollback()
            return ActionResult(
                action="update_row",
                system="postgres",
                success=False,
                output={"error": str(e)},
            )

    def delete_row(self, table: str, where: dict) -> ActionResult:
        """
        Delete rows matching the WHERE clause.

        Idempotency: if rowcount == 0 (nothing deleted), the desired state
        (row gone) is already achieved — returns already_done="deleted".
        Safe to retry without creating phantom deletes.

        Args:
            table — table name
            where — dict of {column: value} equality filters (AND-joined)

        Returns:
            ActionResult — success=True with {"rows_deleted": int, "already_done": False | "deleted"},
                           or success=False with {"error": str(e)}
        """
        self._check_allowed("delete_row")
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                where_clause = pgsql.SQL(" AND ").join(
                    pgsql.SQL("{} = {}").format(
                        pgsql.Identifier(k), pgsql.Placeholder()
                    )
                    for k in where
                )
                # --- Pre-SELECT: capture rows before deleting for rollback ---
                pre_query = pgsql.SQL("SELECT * FROM {} WHERE {}").format(
                    pgsql.Identifier(table), where_clause
                )
                cursor.execute(pre_query, list(where.values()))
                rows_raw = cursor.fetchall()
                cols = [desc[0] for desc in (cursor.description or [])]
                deleted_rows = [dict(zip(cols, row)) for row in rows_raw]
                # --- DELETE ---
                query = pgsql.SQL("DELETE FROM {} WHERE {}").format(
                    pgsql.Identifier(table), where_clause
                )
                cursor.execute(query, list(where.values()))
                conn.commit()
                rows_deleted = cursor.rowcount
                return ActionResult(
                    action="delete_row",
                    system="postgres",
                    success=True,
                    output={
                        "rows_deleted": rows_deleted,
                        "already_done": "deleted" if rows_deleted == 0 else False,
                    },
                    rollback_data={"table": table, "deleted_rows": deleted_rows},
                )
        except Exception as e:
            if conn:
                conn.rollback()
            return ActionResult(
                action="delete_row",
                system="postgres",
                success=False,
                output={"error": str(e)},
            )
