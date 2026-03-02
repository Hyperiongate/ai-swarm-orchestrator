"""
AI SWARM ORCHESTRATOR - Database Engine (Abstraction Layer)
Created: March 02, 2026
Last Updated: March 02, 2026 - CONNECTION POOL FIX

PURPOSE:
    Single database abstraction layer for the entire Swarm system.
    Uses PostgreSQL (via psycopg2) when DATABASE_URL environment variable is set.
    Falls back to SQLite for local development only.

    Every module that touches the database imports get_db_connection() from here.
    No module should ever import sqlite3 or psycopg2 directly.

CHANGELOG:
- March 02, 2026: CONNECTION POOL FIX
  * Increased pool from minconn=1/maxconn=10 to minconn=2/maxconn=20
  * Fixed putconn() error handling — failed putconn no longer destroys pool slot
  * Added pool status logging to help diagnose future exhaustion issues
  * No other changes

- March 02, 2026: CREATED as part of PostgreSQL migration (Phase 1)
  * PostgreSQL via psycopg2 when DATABASE_URL is set (production on Render)
  * SQLite fallback for local development only
  * Connection pooling for PostgreSQL via psycopg2.pool.ThreadedConnectionPool
  * Parameter style: always use %s in SQL. SQLite wrapper translates %s -> ?
  * Row factory: both backends return dict-like rows (access by column name)
  * SQLiteConnectionWrapper.execute() shortcut preserves legacy code compatibility

PARAMETER STYLE RULE:
    Always write SQL with %s placeholders throughout the entire codebase.
    db_engine translates %s -> ? automatically when running SQLite locally.
    Never write ? in SQL. Always write %s.

USAGE:
    from db_engine import get_db_connection, get_db_type

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        row = cursor.fetchone()
        print(row['id'], row['status'])
    finally:
        conn.close()

    # Or as context manager (auto-commit/rollback + close):
    with get_db_connection() as conn:
        conn.execute("INSERT INTO tasks (user_request) VALUES (%s)", ("hello",))

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# DETECT WHICH DATABASE BACKEND TO USE
# ============================================================================

_DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Render provides postgres:// but psycopg2 requires postgresql://
if _DATABASE_URL.startswith('postgres://'):
    _DATABASE_URL = _DATABASE_URL.replace('postgres://', 'postgresql://', 1)

DB_TYPE = 'postgresql' if _DATABASE_URL else 'sqlite'

# SQLite fallback path (local development only)
_SQLITE_PATH = '/mnt/project/swarm_intelligence.db'

print(f"🗄️  DB Engine: {'PostgreSQL (production)' if DB_TYPE == 'postgresql' else 'SQLite (local dev only)'}")

# ============================================================================
# POSTGRESQL CONNECTION POOL (lazy init)
# Pool sizing: minconn=2, maxconn=20
# With gunicorn workers=1 and typical request concurrency, 20 is ample headroom.
# ============================================================================

_pg_pool = None


def _get_pg_pool():
    """Initialize and return the PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is None:
        try:
            from psycopg2 import pool as pg_pool
            _pg_pool = pg_pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                dsn=_DATABASE_URL
            )
            logger.info("PostgreSQL connection pool created (min=2, max=20)")
            print("✅ PostgreSQL connection pool created (min=2, max=20)")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL connection pool: {e}")
            raise
    return _pg_pool


# ============================================================================
# SQLITE ROW WRAPPER — makes sqlite3.Row behave like psycopg2 RealDictRow
# ============================================================================

class DictRow:
    """
    Wraps a sqlite3.Row so it behaves identically to psycopg2 RealDictRow.
    Supports row['column_name'] and row[index] access.
    """
    def __init__(self, row):
        if isinstance(row, sqlite3.Row):
            self._dict = dict(row)
        elif isinstance(row, dict):
            self._dict = row
        else:
            self._dict = {}

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._dict.values())[key]
        return self._dict[key]

    def __contains__(self, key):
        return key in self._dict

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def keys(self):
        return self._dict.keys()

    def values(self):
        return self._dict.values()

    def items(self):
        return self._dict.items()

    def __iter__(self):
        return iter(self._dict)

    def __repr__(self):
        return repr(self._dict)


# ============================================================================
# SQLITE CURSOR WRAPPER — translates %s -> ? and returns DictRow objects
# ============================================================================

class SQLiteCursorWrapper:
    """
    Wraps sqlite3 cursor to:
    1. Translate %s parameter placeholders to ? (sqlite style)
    2. Return DictRow objects so callers use row['column'] everywhere
    3. Expose .lastrowid and .rowcount
    """

    def __init__(self, cursor):
        self._cursor = cursor

    @staticmethod
    def _translate(sql):
        """Replace %s with ? for SQLite compatibility."""
        return sql.replace('%s', '?')

    def execute(self, sql, params=None):
        translated = self._translate(sql)
        if params is None:
            self._cursor.execute(translated)
        else:
            self._cursor.execute(translated, params)
        return self

    def executemany(self, sql, params_list):
        translated = self._translate(sql)
        self._cursor.executemany(translated, params_list)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return DictRow(row)

    def fetchall(self):
        return [DictRow(row) for row in self._cursor.fetchall()]

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        return [DictRow(row) for row in rows]

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def __iter__(self):
        for row in self._cursor:
            yield DictRow(row)


# ============================================================================
# SQLITE CONNECTION WRAPPER
# ============================================================================

class SQLiteConnectionWrapper:
    """
    Wraps sqlite3.Connection.
    Adds execute() shortcut compatible with legacy code.
    Returns SQLiteCursorWrapper from cursor().
    """

    def __init__(self, connection):
        self._conn = connection

    def cursor(self):
        return SQLiteCursorWrapper(self._conn.cursor())

    def execute(self, sql, params=None):
        """Shortcut: creates cursor, executes, returns cursor wrapper."""
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, params_list):
        cur = self.cursor()
        cur.executemany(sql, params_list)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


# ============================================================================
# POSTGRESQL CONNECTION WRAPPER — returns connection to pool on close()
# ============================================================================

class PostgreSQLConnectionWrapper:
    """
    Wraps a psycopg2 connection from the pool.
    Returns connection to pool on close() instead of destroying it.
    Adds execute() shortcut compatible with legacy code.
    Uses RealDictCursor so rows are dict-like.
    """

    def __init__(self, connection, pool):
        self._conn = connection
        self._pool = pool
        self._closed = False
        from psycopg2.extras import RealDictCursor
        self._cursor_factory = RealDictCursor

    def cursor(self):
        return self._conn.cursor(cursor_factory=self._cursor_factory)

    def execute(self, sql, params=None):
        """Shortcut: creates cursor, executes, returns cursor."""
        cur = self.cursor()
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
        return cur

    def executemany(self, sql, params_list):
        cur = self.cursor()
        cur.executemany(sql, params_list)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception as e:
            logger.warning(f"Error during rollback: {e}")

    def close(self):
        """
        Return connection to pool rather than closing it.
        If already closed, do nothing (safe to call multiple times).
        If pool return fails, reset connection state rather than destroying the slot.
        """
        if self._closed:
            return
        self._closed = True

        try:
            # Always rollback any uncommitted transaction before returning to pool
            # This ensures the connection is clean for the next caller
            try:
                self._conn.rollback()
            except Exception:
                pass

            if self._pool and not self._pool.closed:
                self._pool.putconn(self._conn)
            else:
                # Pool is gone (shutdown) — close the raw connection
                self._conn.close()
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")
            # Do NOT call self._conn.close() here — that would destroy the
            # connection and permanently reduce the pool size. Instead, attempt
            # to reset the connection state so the pool can reuse it.
            try:
                self._conn.reset()
                if self._pool and not self._pool.closed:
                    self._pool.putconn(self._conn)
            except Exception as e2:
                logger.error(f"Could not recover connection after pool return error: {e2}")
                # Last resort: close to avoid leaving it in unknown state
                try:
                    self._conn.close()
                except Exception:
                    pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            try:
                self.commit()
            except Exception as e:
                logger.error(f"Error committing transaction: {e}")
                self.rollback()
        self.close()


# ============================================================================
# PUBLIC API
# ============================================================================

def get_db_connection():
    """
    Get a database connection appropriate for the current environment.

    Production (Render, DATABASE_URL set): returns PostgreSQL connection from pool.
    Local development (no DATABASE_URL): returns SQLite connection.

    Both connections expose identical interface:
        conn.execute(sql, params)  — use %s placeholders always
        conn.cursor()              — returns dict-like rows
        conn.commit()
        conn.rollback()
        conn.close()               — pg: returns to pool; sqlite: closes file

    ALWAYS call conn.close() when done, or use as context manager:
        with get_db_connection() as conn:
            conn.execute(...)

    Returns:
        PostgreSQLConnectionWrapper or SQLiteConnectionWrapper
    """
    if DB_TYPE == 'postgresql':
        try:
            pool = _get_pg_pool()
            raw_conn = pool.getconn()
            raw_conn.autocommit = False
            return PostgreSQLConnectionWrapper(raw_conn, pool)
        except Exception as e:
            logger.error(f"Failed to get PostgreSQL connection: {e}")
            raise
    else:
        sqlite_dir = os.path.dirname(_SQLITE_PATH)
        if sqlite_dir and not os.path.exists(sqlite_dir):
            os.makedirs(sqlite_dir, exist_ok=True)
        raw_conn = sqlite3.connect(_SQLITE_PATH)
        raw_conn.row_factory = sqlite3.Row
        return SQLiteConnectionWrapper(raw_conn)


def get_db_type():
    """Return 'postgresql' or 'sqlite'. Used by health check and migrations."""
    return DB_TYPE


def get_pool_status():
    """
    Return current pool status for diagnostics.
    Returns dict with pool info, or None if not PostgreSQL or pool not initialized.
    """
    if DB_TYPE != 'postgresql' or _pg_pool is None:
        return None
    try:
        return {
            'min_connections': _pg_pool.minconn,
            'max_connections': _pg_pool.maxconn,
            'pool_closed': _pg_pool.closed,
        }
    except Exception as e:
        return {'error': str(e)}


def close_pool():
    """Close the PostgreSQL connection pool. Call on application shutdown."""
    global _pg_pool
    if _pg_pool and not _pg_pool.closed:
        _pg_pool.closeall()
        _pg_pool = None
        logger.info("PostgreSQL connection pool closed")

# I did no harm and this file is not truncated
