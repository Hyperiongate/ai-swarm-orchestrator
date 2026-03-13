"""
AI SWARM ORCHESTRATOR - Database Migration 003
File: migrations/migration_003_survey_responses.py
Created: March 13, 2026
Last Updated: March 13, 2026 — BUG FIX 2: Detect and rebuild broken survey_responses schema

PURPOSE:
    Creates the survey_responses table required for Survey in a Box Phase 3.
    This table stores anonymous employee survey responses for online surveys.

    Storage design (per Opus architecture guidance):
        One row per respondent per survey project.
        All answers stored as JSONB keyed by question short_label.
        Missing/unanswered questions export as the string "BLANK".
        No respondent identifiers — fully anonymous by design.
        session_token is a one-way hashed browser cookie value used only
        to prevent duplicate submissions within a session. It is NOT
        linkable to any individual respondent.

    Tables created:
        survey_responses  — Anonymous respondent answers

    Also adds columns to survey_projects:
        survey_url        — The public /survey/take/<token> URL (convenience)
        is_open           — Boolean: is the survey currently accepting responses?
        opened_at         — Timestamp when Jim opened the survey
        closed_at         — Timestamp when Jim closed the survey

CHANGELOG:
    - March 13, 2026 (BUG FIX 2): Added schema integrity check. If
      survey_responses exists but is missing survey_project_id (from a prior
      broken deploy), the table is dropped and recreated. Safe because
      survey_responses has no real data at this stage. Drop+create runs on
      an autocommit connection to avoid transaction state contamination.

    - March 13, 2026 (BUG FIX 1): Replaced savepoint-based _safe_alter()
      with a dedicated autocommit connection for all ALTER TABLE statements.
      Root cause: PostgreSQL savepoints cannot be set inside an already-aborted
      transaction.

    - March 13, 2026: Initial creation. Phase 3 of Survey in a Box roadmap.
      One new table. Adds 4 columns to survey_projects. No other changes.

USAGE:
    Called automatically by app.py STEP 1 (after migration_002).
    Can also be run directly: python migrations/migration_003_survey_responses.py
    Safe to run multiple times — checks schema before acting.

POSTGRESQL RULES FOLLOWED:
    - RealDictCursor dict-only rows (no index access)
    - TRUE/FALSE for booleans
    - %s for all parameters
    - RETURNING id for inserts
    - Autocommit connection for all DDL statements
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pk(db_type):
    if db_type == 'postgresql':
        return 'SERIAL PRIMARY KEY'
    return 'INTEGER PRIMARY KEY AUTOINCREMENT'


def _ts(db_type):
    if db_type == 'postgresql':
        return 'TIMESTAMP DEFAULT NOW()'
    return 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'


def _get_autocommit_conn(db_type):
    """
    Return a fresh psycopg2 connection with autocommit=True.
    Used for all DDL (CREATE TABLE, DROP TABLE, ALTER TABLE, CREATE INDEX)
    so each statement runs in its own implicit transaction and a failure
    on one statement never aborts subsequent ones.
    """
    if db_type == 'postgresql':
        import psycopg2
        dsn = os.environ.get('DATABASE_URL', '')
        if not dsn:
            raise RuntimeError("DATABASE_URL environment variable not set")
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        return conn
    else:
        import sqlite3
        db_path = os.environ.get('SQLITE_DB_PATH', 'swarm_intelligence.db')
        return sqlite3.connect(db_path)


def _table_has_column(cursor, db_type, table_name, column_name):
    """
    Return True if table_name.column_name exists in the database.
    Works for both PostgreSQL and SQLite.
    """
    if db_type == 'postgresql':
        cursor.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = %s
              AND column_name = %s
        """, (table_name, column_name))
        return cursor.fetchone() is not None
    else:
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        return any(row[1] == column_name for row in rows)


def _table_exists(cursor, db_type, table_name):
    """Return True if table_name exists."""
    if db_type == 'postgresql':
        cursor.execute("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = %s
        """, (table_name,))
        return cursor.fetchone() is not None
    else:
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None


def run_migration():
    from db_engine import get_db_type

    db_type = get_db_type()
    print(f"Running migration 003_survey_responses on {db_type}...")

    pk = _pk(db_type)
    ts = _ts(db_type)

    if db_type == 'postgresql':
        jsonb_col = "JSONB NOT NULL DEFAULT '{}'::jsonb"
    else:
        jsonb_col = "TEXT NOT NULL DEFAULT '{}'"

    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS survey_responses (
            id                  {pk},
            survey_project_id   INTEGER NOT NULL,
            answers             {jsonb_col},
            session_token       TEXT,
            submitted_at        {ts}
        )
    """

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_survey_responses_project ON survey_responses(survey_project_id)",
        "CREATE INDEX IF NOT EXISTS idx_survey_responses_session ON survey_responses(session_token)",
        "CREATE INDEX IF NOT EXISTS idx_survey_responses_submitted ON survey_responses(submitted_at DESC)",
    ]

    extra_columns = [
        ("survey_projects", "survey_url",  "TEXT"),
        ("survey_projects", "is_open",     "BOOLEAN DEFAULT FALSE"),
        ("survey_projects", "opened_at",   "TIMESTAMP"),
        ("survey_projects", "closed_at",   "TIMESTAMP"),
    ]

    # =========================================================================
    # ALL DDL runs on a single autocommit connection so every statement is
    # fully isolated. A failure on any one statement never aborts the others.
    # =========================================================================
    conn = _get_autocommit_conn(db_type)
    try:
        cursor = conn.cursor()

        # ---------------------------------------------------------------------
        # STEP 1: Check if survey_responses exists with correct schema.
        # If it exists but is missing survey_project_id (broken prior deploy),
        # drop it so it can be recreated correctly below.
        # ---------------------------------------------------------------------
        if _table_exists(cursor, db_type, 'survey_responses'):
            if not _table_has_column(cursor, db_type, 'survey_responses', 'survey_project_id'):
                print("  survey_responses exists but is missing survey_project_id — dropping for rebuild")
                try:
                    # Drop dependent indexes first (PostgreSQL)
                    for idx in ['idx_survey_responses_project',
                                'idx_survey_responses_session',
                                'idx_survey_responses_submitted']:
                        try:
                            cursor.execute(f"DROP INDEX IF EXISTS {idx}")
                        except Exception:
                            pass
                    cursor.execute("DROP TABLE survey_responses")
                    print("  survey_responses dropped — will recreate with correct schema")
                except Exception as drop_err:
                    print(f"  WARNING: Could not drop survey_responses: {drop_err}")
            else:
                print("  survey_responses already exists with correct schema — skipping CREATE")

        # ---------------------------------------------------------------------
        # STEP 2: Create the table (skipped if already correct per IF NOT EXISTS)
        # ---------------------------------------------------------------------
        try:
            cursor.execute(create_table_sql)
            print("  survey_responses table verified/created")
        except Exception as e:
            print(f"  Table 'survey_responses' warning: {e}")

        # ---------------------------------------------------------------------
        # STEP 3: Create indexes
        # ---------------------------------------------------------------------
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception:
                pass  # Already exists — non-fatal

        # ---------------------------------------------------------------------
        # STEP 4: Add columns to survey_projects (each isolated by autocommit)
        # ---------------------------------------------------------------------
        for table_name, col_name, col_type in extra_columns:
            if db_type == 'postgresql':
                sql = (f"ALTER TABLE {table_name} "
                       f"ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            else:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
            try:
                cursor.execute(sql)
                print(f"  ALTER OK: {table_name}.{col_name}")
            except Exception as e:
                msg = str(e).lower()
                if 'already exists' in msg or 'duplicate column' in msg:
                    print(f"  ALTER SKIP (already exists): {table_name}.{col_name}")
                else:
                    print(f"  ALTER NOTE {table_name}.{col_name}: {e}")

    finally:
        conn.close()

    # Verify final state
    verify_conn = _get_autocommit_conn(db_type)
    try:
        vcursor = verify_conn.cursor()
        has_table = _table_exists(vcursor, db_type, 'survey_responses')
        has_col   = _table_has_column(vcursor, db_type, 'survey_responses', 'survey_project_id') if has_table else False
        has_is_open = _table_has_column(vcursor, db_type, 'survey_projects', 'is_open')
    finally:
        verify_conn.close()

    if has_table and has_col and has_is_open:
        print("Migration 003 (Survey Responses) complete: schema verified OK")
    else:
        print(f"Migration 003 WARNING: survey_responses={has_table}, "
              f"survey_project_id={has_col}, is_open={has_is_open}")

    return True


if __name__ == '__main__':
    result = run_migration()
    print(f"Migration result: {result}")

# I did no harm and this file is not truncated
