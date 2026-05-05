"""
AI SWARM ORCHESTRATOR - Database Engine (Abstraction Layer)
Created: March 02, 2026
Last Updated: 2026-05-05

PURPOSE:
    Single database abstraction layer for the entire Swarm system.
    Uses PostgreSQL (via psycopg2) when DATABASE_URL environment variable is set.
    Falls back to SQLite for local development only.

    Every module that touches the database imports get_db_connection() from here.
    No module should ever import sqlite3 or psycopg2 directly.

CHANGELOG:
- 2026-05-05: STALE CONNECTION FIX
  * ROOT CAUSE: When Gunicorn restarts a worker, connections in the pool may
    have been closed by the PostgreSQL server (SSL SYSCALL error: EOF detected).
    The previous code only retried on PoolError (pool exhaustion) but not on
    OperationalError (dead/stale connection). The first query after a worker
    restart would hit a dead connection and raise a 500.
  * FIX: get_db_connection() now tests each connection with SELECT 1 before
    returning it. On OperationalError (stale connection), it discards the dead
    connection via putconn(close=True) and retries up to 3 times with a 0.5s
    wait. This ensures callers always receive a live connection.
  * putconn(close=True) tells the pool to discard the connection entirely rather
    than returning a known-bad connection to the available pool.
  * All existing retry logic for PoolError (exhaustion) preserved unchanged.

- March 03, 2026: Phase 9 - CONNECTION POOL EXHAUSTION FIX
  * Increased pool from minconn=2/maxconn=20 to minconn=2/maxconn=40
  * Added connect_timeout=10 to DSN
  * get_db_connection() retries once on PoolError with 1-second wait
  * PostgreSQLConnectionWrapper.__del__() safety net for leaked connections

- March 02, 2026: CONNECTION POOL FIX
  * Increased pool from minconn=1/maxconn=10 to minconn=2/maxconn=20
  * Fixed putconn() error handling

- March 02, 2026: CREATED as part of PostgreSQL migration (Phase 1)

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

I did no harm and this file is not truncated.
"""

import os
import time
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
# Pool sizing: minconn=2, maxconn=40
# ============================================================================

_pg_pool = None


def _get_pg_pool():
    """Initialize and return the PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is None:
        try:
            from psycopg2 import pool as pg_pool

            # Add connect_timeout to DSN so hung connections don't block forever
            dsn = _DATABASE_URL
            if 'connect_timeout' not in dsn:
                separator = '&' if '?' in dsn else '?'
                dsn = f"{dsn}{separator}connect_timeout=10"

            _pg_pool = pg_pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=40,
                dsn=dsn
            )
            logger.info("PostgreSQL connection pool created (min=2, max=40)")
            print("✅ PostgreSQL connection pool created (min=2, max=40)")
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

    SAFETY NET: __del__ returns connection to pool if close() was never called.
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
        """
        if self._closed:
            return
        self._closed = True

        try:
            try:
                self._conn.rollback()
            except Exception:
                pass

            if self._pool and not self._pool.closed:
                self._pool.putconn(self._conn)
            else:
                self._conn.close()
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")
            try:
                self._conn.reset()
                if self._pool and not self._pool.closed:
                    self._pool.putconn(self._conn)
            except Exception as e2:
                logger.error(f"Could not recover connection after pool return error: {e2}")
                try:
                    self._conn.close()
                except Exception:
                    pass

    def __del__(self):
        """Safety net: return connection to pool if close() was never called."""
        if not self._closed:
            logger.warning("PostgreSQL connection was garbage collected without close()! "
                           "Connection leak detected.")
            try:
                self.close()
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

    STALE CONNECTION HANDLING (2026-05-05):
    When a Gunicorn worker restarts, connections in the pool may have been
    closed by PostgreSQL (SSL SYSCALL error: EOF detected). This function
    tests each connection with SELECT 1 before returning it. If the connection
    is dead, it discards it via putconn(close=True) and retries up to 3 times
    with a 0.5-second wait between attempts.

    POOL EXHAUSTION HANDLING:
    On PoolError (pool exhausted), retries once after a 1-second wait.

    Returns:
        PostgreSQLConnectionWrapper or SQLiteConnectionWrapper
    """
    if DB_TYPE == 'postgresql':
        from psycopg2.pool import PoolError
        import psycopg2

        for attempt in range(3):
            raw_conn = None
            try:
                pool = _get_pg_pool()
                raw_conn = pool.getconn()
                raw_conn.autocommit = False

                # Test the connection is alive before returning it.
                # This catches stale connections from worker restarts.
                test_cur = raw_conn.cursor()
                test_cur.execute("SELECT 1")
                test_cur.close()

                return PostgreSQLConnectionWrapper(raw_conn, pool)

            except psycopg2.OperationalError as e:
                # Dead/stale connection — discard it and get a fresh one.
                msg = str(e)
                print(f"⚠️  Stale DB connection (attempt {attempt + 1}/3): {msg[:80]}")
                logger.warning(f"Stale DB connection on attempt {attempt + 1}: {msg}")

                if raw_conn is not None:
                    try:
                        # putconn(close=True) discards the connection entirely
                        # rather than returning a known-bad connection to the pool.
                        pool = _get_pg_pool()
                        pool.putconn(raw_conn, close=True)
                    except Exception:
                        try:
                            raw_conn.close()
                        except Exception:
                            pass

                if attempt < 2:
                    time.sleep(0.5)
                else:
                    logger.error(f"All 3 connection attempts failed with OperationalError: {msg}")
                    raise

            except PoolError as e:
                # Pool exhaustion — wait and retry once
                if raw_conn is not None:
                    try:
                        pool = _get_pg_pool()
                        pool.putconn(raw_conn)
                    except Exception:
                        pass
                if attempt == 0:
                    logger.warning(
                        f"Connection pool exhausted (attempt 1/3). "
                        f"Waiting 1 second before retry. "
                        f"Pool status: {get_pool_status()}"
                    )
                    print(f"⚠️  Connection pool exhausted — retrying in 1 second...")
                    time.sleep(1)
                else:
                    logger.error(
                        f"Connection pool exhausted after retry. "
                        f"Pool status: {get_pool_status()}"
                    )
                    print(f"❌ Connection pool exhausted after retry. Pool: {get_pool_status()}")
                    raise

            except Exception as e:
                if raw_conn is not None:
                    try:
                        pool = _get_pg_pool()
                        pool.putconn(raw_conn, close=True)
                    except Exception:
                        try:
                            raw_conn.close()
                        except Exception:
                            pass
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

# I did no harm and this file is not truncated.
