"""
JN Engine — Database abstraction layer.
SQLite for dev/local; PostgreSQL (Neon/Supabase) for prod.
Set DATABASE_URL in Streamlit secrets to activate PostgreSQL mode.

PostgreSQL strategy: open a fresh connection per query, fetch all rows
eagerly, then close immediately.  This is the correct pattern for
serverless Postgres (Neon) — no persistent connections, no idle-timeout
drops, no psycopg2 thread-safety issues with @st.cache_resource.
"""
import os
import sqlite3


def _db_url() -> str:
    try:
        import streamlit as st
        return st.secrets.get("DATABASE_URL") or ""
    except Exception:
        return os.environ.get("DATABASE_URL", "")


class _Row(dict):
    """Dict that also supports integer-index access (needed for COUNT(*) fetchone()[0])."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _EagerResult:
    """
    Holds rows fetched before the connection was closed.
    Behaves like a sqlite3 cursor for the patterns we use.
    """
    def __init__(self, rows: list, rowcount: int):
        self._rows     = rows   # already list[_Row]
        self._rowcount = rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows

    def __iter__(self):
        return iter(self._rows)

    @property
    def rowcount(self):
        return self._rowcount


class JNDatabase:
    """
    Unified DB wrapper.
    - SQLite : single persistent connection (dev / local).
    - PostgreSQL : new connection per query (serverless-safe).
    """

    def __init__(self):
        url = _db_url()
        if url:
            self._url     = url
            self._backend = "postgres"
            self._conn    = None          # no persistent pg connection
        else:
            self._url     = ""
            self._backend = "sqlite"
            db_dir  = os.path.join(os.path.expanduser("~"), ".jn_engine")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "jn_engine.db")
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")

    @property
    def backend(self) -> str:
        return self._backend

    # ------------------------------------------------------------------
    # SQL translation helpers
    # ------------------------------------------------------------------

    def _fix(self, sql: str) -> str:
        if self._backend == "sqlite":
            return sql
        sql = sql.replace("?", "%s")
        sql = sql.replace("datetime('now')", "NOW()")
        return sql

    def _fix_insert(self, sql: str) -> str:
        has_ignore = "INSERT OR IGNORE INTO" in sql
        sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        sql = self._fix(sql)
        if has_ignore and self._backend == "postgres" and "ON CONFLICT" not in sql:
            sql = sql.rstrip(" ;") + " ON CONFLICT DO NOTHING"
        return sql

    # ------------------------------------------------------------------
    # PostgreSQL: fresh-connection helpers
    # ------------------------------------------------------------------

    def _pg_conn(self):
        """Open and return a fresh psycopg2 connection."""
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(
            self._url,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        conn.autocommit = True
        return conn

    def _pg_execute(self, sql: str, params=()):
        """Run a single statement on a fresh connection; fetch all rows eagerly."""
        conn = self._pg_conn()
        try:
            cur = conn.cursor()
            cur.execute(self._fix_insert(sql), params or ())
            # cur.description is None for INSERT/UPDATE/DELETE — only fetch for SELECT
            rows     = [_Row(r) for r in cur.fetchall()] if cur.description else []
            rowcount = cur.rowcount
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return _EagerResult(rows, rowcount)

    def _pg_executemany(self, sql: str, params_list):
        """Run executemany on a fresh connection."""
        conn = self._pg_conn()
        try:
            cur = conn.cursor()
            cur.executemany(self._fix_insert(sql), params_list)
            rowcount = cur.rowcount
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return _EagerResult([], rowcount)

    def _pg_executescript(self, script: str):
        """Run a DDL script on a fresh connection; ignore per-statement errors."""
        conn = self._pg_conn()
        try:
            cur = conn.cursor()
            for stmt in script.split(";"):
                stmt = self._fix(stmt).strip()
                if stmt:
                    try:
                        cur.execute(stmt)
                    except Exception:
                        pass   # table / index already exists
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, sql: str, params=()):
        if self._backend == "postgres":
            return self._pg_execute(sql, params)
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params_list):
        if self._backend == "postgres":
            return self._pg_executemany(sql, params_list)
        return self._conn.executemany(sql, params_list)

    def executescript(self, script: str):
        if self._backend == "postgres":
            self._pg_executescript(script)
        else:
            self._conn.executescript(script)

    def commit(self):
        if self._backend == "sqlite":
            self._conn.commit()
        # postgres: autocommit=True on every connection — no-op

    def close(self):
        if self._backend == "sqlite":
            try:
                self._conn.close()
            except Exception:
                pass
        # postgres: no persistent connection to close
