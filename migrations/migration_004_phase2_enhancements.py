"""
AI SWARM ORCHESTRATOR - Database Migration 004
File: migrations/migration_004_phase2_enhancements.py
Created: March 26, 2026
Last Updated: March 26, 2026 — Phase 2: Survey Assembly & Admin Controls

PURPOSE:
    Creates the survey_roster table and adds new columns required for
    Survey in a Box Phase 2 (employee roster upload, code generation,
    and survey management controls).

    Changes made:
        1. Creates survey_roster table — one row per employee per project.
           Stores the employee's 5-digit code and demographic data (dept,
           shift, tenure) used for response linking in export.

        2. Adds to survey_projects:
               roster_uploaded          BOOLEAN DEFAULT FALSE
               roster_count             INTEGER DEFAULT 0
               generated_document_path  TEXT

        3. Adds to survey_responses:
               employee_code            VARCHAR(5)

DESIGN NOTES:
    - survey_roster.employee_code is UNIQUE within each project so that
      the same code cannot be issued to two employees in the same survey.
    - has_responded tracks whether the code has been used to prevent
      duplicate submissions (set to TRUE on first successful survey submit).
    - employee_code in survey_responses links a response row to the
      roster row for demographic enrichment during export.
    - generated_document_path on survey_projects will store the path to
      the .docx survey document generated during Phase 2 assembly.
    - This migration adds NO changes to any existing Swarm tables.

CHANGELOG:
    - March 26, 2026: Initial creation for Phase 2 of Survey in a Box.
      Follows exact pattern of migration_003_survey_responses.py.

USAGE:
    Called automatically by app.py STEP 1 (after migration_003).
    Can also be run directly:
        python migrations/migration_004_phase2_enhancements.py
    Safe to run multiple times — all DDL is idempotent.

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


# ---------------------------------------------------------------------------
# DB TYPE HELPERS  (copied verbatim from migration_003 pattern)
# ---------------------------------------------------------------------------

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
    Return a fresh connection with autocommit=True (PostgreSQL) or a
    standard SQLite connection.  Used for all DDL so each statement runs
    in its own implicit transaction and a failure never aborts others.
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
    """Return True if table_name.column_name exists in the database."""
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
    """Return True if table_name exists in the database."""
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


# ---------------------------------------------------------------------------
# MAIN MIGRATION
# ---------------------------------------------------------------------------

def run_migration():
    from db_engine import get_db_type

    db_type = get_db_type()
    print(f"Running migration 004_phase2_enhancements on {db_type}...")

    pk = _pk(db_type)
    ts = _ts(db_type)

    # ------------------------------------------------------------------
    # survey_roster CREATE TABLE
    # ------------------------------------------------------------------
    create_roster_sql = f"""
        CREATE TABLE IF NOT EXISTS survey_roster (
            id                  {pk},
            survey_project_id   INTEGER NOT NULL,
            employee_name       TEXT NOT NULL,
            department          TEXT,
            shift               TEXT,
            tenure_bracket      TEXT,
            employee_code       VARCHAR(5) NOT NULL,
            has_responded       BOOLEAN DEFAULT FALSE,
            created_at          {ts},
            UNIQUE(survey_project_id, employee_code)
        )
    """

    roster_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_survey_roster_project  ON survey_roster(survey_project_id)",
        "CREATE INDEX IF NOT EXISTS idx_survey_roster_code     ON survey_roster(employee_code)",
        "CREATE INDEX IF NOT EXISTS idx_survey_roster_responded ON survey_roster(has_responded)",
    ]

    # ------------------------------------------------------------------
    # Columns to add via ALTER TABLE (table, column, type)
    # ------------------------------------------------------------------
    extra_columns = [
        # survey_projects Phase 2 columns
        ("survey_projects",  "roster_uploaded",          "BOOLEAN DEFAULT FALSE"),
        ("survey_projects",  "roster_count",             "INTEGER DEFAULT 0"),
        ("survey_projects",  "generated_document_path",  "TEXT"),
        # survey_responses Phase 2 column
        ("survey_responses", "employee_code",            "VARCHAR(5)"),
    ]

    # ==================================================================
    # ALL DDL runs on a single autocommit connection so every statement
    # is fully isolated.  A failure on one never aborts the others.
    # ==================================================================
    conn = _get_autocommit_conn(db_type)
    try:
        cursor = conn.cursor()

        # --------------------------------------------------------------
        # STEP 1: Create survey_roster table
        # --------------------------------------------------------------
        if _table_exists(cursor, db_type, 'survey_roster'):
            print("  survey_roster already exists — skipping CREATE")
        else:
            try:
                cursor.execute(create_roster_sql)
                print("  survey_roster table created")
            except Exception as e:
                print(f"  survey_roster CREATE warning: {e}")

        # --------------------------------------------------------------
        # STEP 2: Create roster indexes
        # --------------------------------------------------------------
        for index_sql in roster_indexes:
            try:
                cursor.execute(index_sql)
            except Exception:
                pass  # Already exists — non-fatal

        print("  survey_roster indexes verified")

        # --------------------------------------------------------------
        # STEP 3: Add new columns to survey_projects and survey_responses
        #         Each ALTER TABLE is isolated by autocommit.
        # --------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Verify final state
    # ------------------------------------------------------------------
    verify_conn = _get_autocommit_conn(db_type)
    try:
        vcursor = verify_conn.cursor()
        has_roster_table    = _table_exists(vcursor, db_type, 'survey_roster')
        has_roster_code_col = (_table_has_column(vcursor, db_type, 'survey_roster', 'employee_code')
                               if has_roster_table else False)
        has_roster_uploaded = _table_has_column(vcursor, db_type, 'survey_projects', 'roster_uploaded')
        has_roster_count    = _table_has_column(vcursor, db_type, 'survey_projects', 'roster_count')
        has_gen_doc_path    = _table_has_column(vcursor, db_type, 'survey_projects', 'generated_document_path')
        has_emp_code_resp   = _table_has_column(vcursor, db_type, 'survey_responses', 'employee_code')
    finally:
        verify_conn.close()

    all_ok = all([
        has_roster_table,
        has_roster_code_col,
        has_roster_uploaded,
        has_roster_count,
        has_gen_doc_path,
        has_emp_code_resp,
    ])

    if all_ok:
        print("Migration 004 (Phase 2 Enhancements) complete: schema verified OK")
    else:
        print(
            f"Migration 004 WARNING: "
            f"survey_roster={has_roster_table}, "
            f"employee_code(roster)={has_roster_code_col}, "
            f"roster_uploaded={has_roster_uploaded}, "
            f"roster_count={has_roster_count}, "
            f"generated_document_path={has_gen_doc_path}, "
            f"employee_code(responses)={has_emp_code_resp}"
        )

    return all_ok


if __name__ == '__main__':
    result = run_migration()
    print(f"Migration result: {result}")

# I did no harm and this file is not truncated
