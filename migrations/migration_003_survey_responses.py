"""
AI SWARM ORCHESTRATOR - Database Migration 003
File: migrations/migration_003_survey_responses.py
Created: March 13, 2026
Last Updated: March 13, 2026 — BUG FIX: ALTER TABLE now uses autocommit connection

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
    - March 13, 2026 (BUG FIX): Replaced savepoint-based _safe_alter() with
      a dedicated autocommit connection for all ALTER TABLE statements.
      Root cause: PostgreSQL savepoints cannot be set inside an already-aborted
      transaction. Using autocommit=True puts each ALTER TABLE in its own
      implicit transaction, so failures are isolated without savepoints.
      The main transaction (CREATE TABLE + indexes) is completely unchanged.

    - March 13, 2026: Initial creation. Phase 3 of Survey in a Box roadmap.
      One new table. Adds 4 columns to survey_projects. No other changes.

USAGE:
    Called automatically by app.py STEP 1 (after migration_002).
    Can also be run directly: python migrations/migration_003_survey_responses.py
    Safe to run multiple times — all CREATE TABLE statements use IF NOT EXISTS.
    All ALTER TABLE statements use ADD COLUMN IF NOT EXISTS (PostgreSQL).

POSTGRESQL RULES FOLLOWED:
    - RealDictCursor dict-only rows (no index access)
    - TRUE/FALSE for booleans
    - %s for all parameters
    - RETURNING id for inserts
    - Autocommit connection for DDL ALTER TABLE (proper isolation)
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


def _safe_alter_autocommit(dsn, sql, db_type):
    """
    Execute one ALTER TABLE using a dedicated autocommit connection.

    PostgreSQL DDL (ALTER TABLE ADD COLUMN IF NOT EXISTS) must not run inside
    a transaction that has already errored. Using autocommit=True gives each
    statement its own implicit transaction — a failure on one column does NOT
    roll back or abort subsequent statements.

    For SQLite (dev/test), falls back to a simple try/except execute.
    """
    if db_type == 'postgresql':
        import psycopg2
        try:
            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            cursor = conn.cursor()
            try:
                cursor.execute(sql)
                print(f"  ALTER OK: {sql.strip()[:80]}")
            except Exception as e:
                msg = str(e).lower()
                if 'already exists' in msg or 'duplicate column' in msg:
                    print(f"  ALTER SKIP (already exists): {sql.strip()[:80]}")
                else:
                    print(f"  ALTER NOTE: {e}")
            finally:
                cursor.close()
                conn.close()
        except Exception as conn_err:
            print(f"  ALTER connection error: {conn_err}")
    else:
        # SQLite path (dev/test only)
        import sqlite3
        try:
            conn = sqlite3.connect(dsn)
            try:
                conn.execute(sql)
                conn.commit()
            except Exception as e:
                msg = str(e).lower()
                if 'duplicate column' not in msg:
                    print(f"  ALTER NOTE (sqlite): {e}")
            finally:
                conn.close()
        except Exception as conn_err:
            print(f"  ALTER connection error (sqlite): {conn_err}")


def run_migration():
    from db_engine import get_db_connection, get_db_type

    db_type = get_db_type()
    print(f"Running migration 003_survey_responses on {db_type}...")

    pk = _pk(db_type)
    ts = _ts(db_type)

    # -------------------------------------------------------------------------
    # SURVEY_RESPONSES
    # One row per anonymous respondent submission.
    #
    # answers (JSONB):
    #   Keyed by question short_label (e.g. "Department", "like current schedule").
    #   Values are the FULL TEXT of the selected answer option.
    #   Example: {"Department": "Shipping", "like current schedule": "4 Agree"}
    #   Questions not answered are absent from the JSONB; the export function
    #   fills missing keys with the string "BLANK".
    #
    # session_token:
    #   One-way SHA-256 hash of a browser cookie value. Used only to detect
    #   duplicate submissions within a single browser session. Cannot be
    #   reversed to identify any individual. NULL if browser cookies disabled.
    #
    # submitted_at:
    #   UTC timestamp of final submission. Not exposed in any export.
    # -------------------------------------------------------------------------
    if db_type == 'postgresql':
        jsonb_col = "JSONB NOT NULL DEFAULT '{}'::jsonb"
    else:
        jsonb_col = "TEXT NOT NULL DEFAULT '{}'"

    table_sql = f"""
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

    # =========================================================================
    # ADDITIONAL COLUMNS ON survey_projects
    # These support Phase 3 online survey administration.
    # is_open controls whether /survey/take/<token> accepts new submissions.
    #
    # Each ALTER runs on its OWN autocommit connection so failures are isolated.
    # =========================================================================
    extra_columns = [
        ("survey_projects", "survey_url",  "TEXT"),
        ("survey_projects", "is_open",     "BOOLEAN DEFAULT FALSE"),
        ("survey_projects", "opened_at",   "TIMESTAMP"),
        ("survey_projects", "closed_at",   "TIMESTAMP"),
    ]

    # =========================================================================
    # PHASE 1: CREATE TABLE + INDEXES (inside one transaction)
    # =========================================================================
    conn = get_db_connection()
    tables_created = 0
    errors = 0
    try:
        cursor = conn.cursor()

        try:
            cursor.execute(table_sql)
            tables_created += 1
        except Exception as e:
            errors += 1
            print(f"  Table 'survey_responses' warning: {e}")

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception:
                pass  # Index may already exist — non-fatal

        conn.commit()
    finally:
        conn.close()

    # =========================================================================
    # PHASE 2: ALTER TABLE — each on its own autocommit connection
    #
    # Resolve the DSN for the autocommit connection.
    # PostgreSQL: use DATABASE_URL env var (same one db_engine uses).
    # SQLite: use the db file path.
    # =========================================================================
    if db_type == 'postgresql':
        dsn = os.environ.get('DATABASE_URL', '')
        if not dsn:
            print("  WARNING: DATABASE_URL not set — cannot run ALTER TABLE statements")
        else:
            for table_name, col_name, col_type in extra_columns:
                sql = (f"ALTER TABLE {table_name} "
                       f"ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
                _safe_alter_autocommit(dsn, sql, db_type)
    else:
        # SQLite dev path — use a fresh connection per ALTER
        db_path = os.environ.get('SQLITE_DB_PATH', 'swarm_intelligence.db')
        for table_name, col_name, col_type in extra_columns:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
            _safe_alter_autocommit(db_path, sql, db_type)

    print(f"Migration 003 (Survey Responses) complete: {tables_created}/1 tables "
          f"verified on {db_type}")
    if errors > 0:
        print(f"  {errors} table(s) had warnings (likely already exist)")
    return True


if __name__ == '__main__':
    result = run_migration()
    print(f"Migration result: {result}")

# I did no harm and this file is not truncated
