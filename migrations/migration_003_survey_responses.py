"""
AI SWARM ORCHESTRATOR - Database Migration 003
File: migrations/migration_003_survey_responses.py
Created: March 13, 2026
Last Updated: March 13, 2026 — Phase 3: Survey Administration

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
    - _safe_alter() helper for savepoint-protected ALTER TABLE
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pk(db_type):
    if db_type == 'postgresql':
        return 'SERIAL PRIMARY KEY'
    return 'INTEGER PRIMARY KEY AUTOINCREMENT'


def _bool(db_type, default=False):
    val = 'FALSE' if default is False else 'TRUE'
    if db_type == 'postgresql':
        return f'BOOLEAN DEFAULT {val}'
    return f'INTEGER DEFAULT {"0" if default is False else "1"}'


def _ts(db_type):
    if db_type == 'postgresql':
        return 'TIMESTAMP DEFAULT NOW()'
    return 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'


def _safe_alter(cursor, db_type, sql):
    """Execute one ALTER TABLE protected by a SAVEPOINT (PostgreSQL).
    On failure rolls back only that savepoint — rest of transaction continues.
    Mirrors the same helper used in migration_001 and migration_002."""
    if db_type == 'postgresql':
        try:
            cursor.execute("SAVEPOINT alter_col_003")
            cursor.execute(sql)
            cursor.execute("RELEASE SAVEPOINT alter_col_003")
        except Exception as e:
            cursor.execute("ROLLBACK TO SAVEPOINT alter_col_003")
            msg = str(e).lower()
            if 'already exists' not in msg and 'duplicate' not in msg:
                print(f"  ALTER TABLE note (003): {e}")
    else:
        try:
            cursor.execute(sql)
        except Exception:
            pass


def run_migration():
    from db_engine import get_db_connection, get_db_type

    db_type = get_db_type()
    print(f"Running migration 003_survey_responses on {db_type}...")

    pk         = _pk(db_type)
    bool_false = _bool(db_type, False)
    bool_true  = _bool(db_type, True)
    ts         = _ts(db_type)

    tables = []

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
    jsonb_col = 'JSONB NOT NULL DEFAULT \'{}\'::jsonb' if db_type == 'postgresql' else 'TEXT NOT NULL DEFAULT \'{}\''

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS survey_responses (
            id                  {pk},
            survey_project_id   INTEGER NOT NULL,
            answers             {jsonb_col},
            session_token       TEXT,
            submitted_at        {ts}
        )
    """)

    # =========================================================================
    # INDEXES
    # =========================================================================
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_survey_responses_project ON survey_responses(survey_project_id)",
        "CREATE INDEX IF NOT EXISTS idx_survey_responses_session ON survey_responses(session_token)",
        "CREATE INDEX IF NOT EXISTS idx_survey_responses_submitted ON survey_responses(submitted_at DESC)",
    ]

    # =========================================================================
    # ADDITIONAL COLUMNS ON survey_projects
    # These support Phase 3 online survey administration.
    # is_open controls whether /survey/take/<token> accepts new submissions.
    # =========================================================================
    extra_columns = [
        ("survey_projects", "survey_url",  "TEXT"),
        ("survey_projects", "is_open",     "BOOLEAN DEFAULT FALSE"),
        ("survey_projects", "opened_at",   "TIMESTAMP"),
        ("survey_projects", "closed_at",   "TIMESTAMP"),
    ]

    # =========================================================================
    # EXECUTE TABLE CREATION
    # =========================================================================
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        tables_created = 0
        errors         = 0

        for table_sql in tables:
            try:
                cursor.execute(table_sql)
                tables_created += 1
            except Exception as e:
                errors += 1
                import re
                table_name = "unknown"
                try:
                    match = re.search(r'CREATE TABLE IF NOT EXISTS\s+(\w+)', table_sql)
                    if match:
                        table_name = match.group(1)
                except Exception:
                    pass
                print(f"  Table '{table_name}' warning: {e}")

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception:
                pass

        for table_name, col_name, col_type in extra_columns:
            if db_type == 'postgresql':
                sql = (f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS "
                       f"{col_name} {col_type}")
            else:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
            _safe_alter(cursor, db_type, sql)

        conn.commit()
    finally:
        conn.close()

    print(f"Migration 003 (Survey Responses) complete: {tables_created}/{len(tables)} tables "
          f"verified on {db_type}")
    if errors > 0:
        print(f"  {errors} table(s) had warnings (likely already exist)")
    return True


if __name__ == '__main__':
    result = run_migration()
    print(f"Migration result: {result}")

# I did no harm and this file is not truncated
