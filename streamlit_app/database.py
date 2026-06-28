"""
JN Engine — Database abstraction layer.
SQLite for dev/local; PostgreSQL (Neon/Supabase) for prod.
Set DATABASE_URL in Streamlit secrets to activate PostgreSQL mode.
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


class _PgCursor:
    """Wraps a psycopg2 cursor to return _Row objects, matching the sqlite3.Row API."""
    def __init__(self, cur):
        self._c = cur

    def fetchone(self):
        row = self._c.fetchone()
        return _Row(row) if row is not None else None

    def fetchall(self):
        return [_Row(r) for r in self._c.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def rowcount(self):
        return self._c.rowcount


class JNDatabase:
    """
    Unified DB wrapper — API-compatible with sqlite3.Connection.
    Set DATABASE_URL in Streamlit secrets for PostgreSQL; otherwise SQLite.
    """

    def __init__(self):
        url = _db_url()
        if url:
            self._url     = url
            self._backend = "postgres"
            self._conn    = None
            self._pg_connect()
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

    def _pg_connect(self):
        import psycopg2
        import psycopg2.extras
        self._conn = psycopg2.connect(
            self._url,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        self._conn.autocommit = True

    def _pg_reconnect(self):
        """Close stale connection and open a fresh one."""
        try:
            self._conn.close()
        except Exception:
            pass
        self._pg_connect()

    @property
    def backend(self) -> str:
        return self._backend

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

    def _pg_execute(self, sql: str, params=()):
        """
        Execute one SQL statement on PostgreSQL.
        On InterfaceError / OperationalError (Neon idle-timeout drop),
        reconnect once and retry before giving up.
        """
        import psycopg2
        fixed = self._fix_insert(sql)
        try:
            cur = self._conn.cursor()
            cur.execute(fixed, params or ())
            return _PgCursor(cur)
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            self._pg_reconnect()
            cur = self._conn.cursor()
            cur.execute(fixed, params or ())
            return _PgCursor(cur)

    def _pg_executemany(self, sql: str, params_list):
        import psycopg2
        fixed = self._fix_insert(sql)
        try:
            cur = self._conn.cursor()
            cur.executemany(fixed, params_list)
            return _PgCursor(cur)
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            self._pg_reconnect()
            cur = self._conn.cursor()
            cur.executemany(fixed, params_list)
            return _PgCursor(cur)

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
            for stmt in script.split(";"):
                stmt = self._fix(stmt).strip()
                if stmt:
                    try:
                        self._pg_execute(stmt)
                    except Exception:
                        pass
        else:
            self._conn.executescript(script)

    def commit(self):
        if self._backend == "sqlite":
            self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
