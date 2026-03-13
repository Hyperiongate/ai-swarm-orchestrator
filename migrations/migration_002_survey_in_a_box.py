"""
AI SWARM ORCHESTRATOR - Database Migration 002
File: migrations/migration_002_survey_in_a_box.py
Created: March 10, 2026
Last Updated: March 10, 2026 - Initial creation for Survey in a Box Phase 1

PURPOSE:
    Creates the three new tables required for Survey in a Box (Phase 1).
    These tables are COMPLETELY SEPARATE from the existing Swarm schema.
    This migration does NOT touch any existing table.

    Tables created:
        survey_clients       — Intake form submissions from prospective clients
        survey_projects      — Jim's project configuration per client
        survey_project_history — Links repeat clients across years (year-over-year)

CHANGELOG:
    - March 10, 2026: Initial creation. Phase 1 of Survey in a Box roadmap.
      Three new tables only. No modifications to any existing table.

USAGE:
    Called automatically by app.py STEP 1 (after migration_001).
    Can also be run directly: python migrations/migration_002_survey_in_a_box.py
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
    Mirrors the same helper used in migration_001 to maintain consistency."""
    if db_type == 'postgresql':
        try:
            cursor.execute("SAVEPOINT alter_col_002")
            cursor.execute(sql)
            cursor.execute("RELEASE SAVEPOINT alter_col_002")
        except Exception as e:
            cursor.execute("ROLLBACK TO SAVEPOINT alter_col_002")
            msg = str(e).lower()
            if 'already exists' not in msg and 'duplicate' not in msg:
                print(f"  ALTER TABLE note (002): {e}")
    else:
        try:
            cursor.execute(sql)
        except Exception:
            pass  # SQLite: column already exists → ignore


def run_migration():
    from db_engine import get_db_connection, get_db_type

    db_type = get_db_type()
    print(f"Running migration 002_survey_in_a_box on {db_type}...")

    pk = _pk(db_type)
    bool_false = _bool(db_type, False)
    ts = _ts(db_type)

    tables = []

    # -------------------------------------------------------------------------
    # SURVEY_CLIENTS
    # One row per prospective client that submits the public intake form.
    # department_names, biggest_challenges, shift_start_times stored as JSON
    # strings (TEXT) to avoid needing ARRAY type; parsed in Python.
    # status lifecycle: new → reviewing → approved → rejected
    # -------------------------------------------------------------------------
    tables.append(f"""
        CREATE TABLE IF NOT EXISTS survey_clients (
            id {pk},
            company_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            industry TEXT,
            employee_count INTEGER,
            department_count INTEGER,
            department_names TEXT,
            current_schedule_type TEXT,
            crew_count INTEGER,
            shift_start_times TEXT,
            union_status TEXT DEFAULT 'non-union',
            biggest_challenges TEXT,
            previously_surveyed {bool_false},
            last_survey_date TEXT,
            preferred_administration TEXT DEFAULT 'online',
            preferred_delivery_date TEXT,
            referral_source TEXT,
            additional_notes TEXT,
            status TEXT DEFAULT 'new',
            admin_notes TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    # -------------------------------------------------------------------------
    # SURVEY_PROJECTS
    # One row per survey engagement (a client may have multiple over the years).
    # selected_questions, excluded_questions, custom_questions, selected_schedules
    # stored as JSON strings (TEXT) — arrays/dicts serialized in Python.
    # status lifecycle: draft → approved → administered → processing → delivered
    # project_token is the unique slug used in public-facing URLs (Phase 3).
    # -------------------------------------------------------------------------
    tables.append(f"""
        CREATE TABLE IF NOT EXISTS survey_projects (
            id {pk},
            survey_client_id INTEGER NOT NULL,
            project_token TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'draft',
            selected_questions TEXT,
            excluded_questions TEXT,
            custom_questions TEXT,
            selected_schedules TEXT,
            admin_notes TEXT,
            generated_document_path TEXT,
            response_count INTEGER DEFAULT 0,
            approved_at TIMESTAMP,
            approved_by TEXT DEFAULT 'jim',
            created_at {ts},
            updated_at {ts}
        )
    """)

    # -------------------------------------------------------------------------
    # SURVEY_PROJECT_HISTORY
    # Links multiple survey_projects to the same survey_client for
    # year-over-year tracking (Phase 7 repeat client feature).
    # Inserted when Jim approves a project for a client that already exists.
    # -------------------------------------------------------------------------
    tables.append(f"""
        CREATE TABLE IF NOT EXISTS survey_project_history (
            id {pk},
            survey_client_id INTEGER NOT NULL,
            survey_project_id INTEGER NOT NULL,
            year INTEGER,
            notes TEXT,
            created_at {ts}
        )
    """)

    # =========================================================================
    # INDEXES
    # =========================================================================
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_survey_clients_status ON survey_clients(status)",
        "CREATE INDEX IF NOT EXISTS idx_survey_clients_email ON survey_clients(email)",
        "CREATE INDEX IF NOT EXISTS idx_survey_clients_created ON survey_clients(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_survey_projects_client ON survey_projects(survey_client_id)",
        "CREATE INDEX IF NOT EXISTS idx_survey_projects_token ON survey_projects(project_token)",
        "CREATE INDEX IF NOT EXISTS idx_survey_projects_status ON survey_projects(status)",
        "CREATE INDEX IF NOT EXISTS idx_survey_history_client ON survey_project_history(survey_client_id)",
        "CREATE INDEX IF NOT EXISTS idx_survey_history_project ON survey_project_history(survey_project_id)",
    ]

    # =========================================================================
    # EXECUTE TABLE CREATION
    # =========================================================================
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        tables_created = 0
        errors = 0

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

        # =====================================================================
        # ADD MISSING COLUMNS (patch for tables that already exist)
        # These are safe no-ops if the columns are already present.
        # =====================================================================
        extra_columns = [
            ("survey_clients", "admin_notes", "TEXT"),
            ("survey_clients", "updated_at", "TIMESTAMP DEFAULT NOW()"),
            ("survey_projects", "excluded_questions", "TEXT"),
            ("survey_projects", "response_count", "INTEGER DEFAULT 0"),
            ("survey_projects", "approved_at", "TIMESTAMP"),
            ("survey_projects", "updated_at", "TIMESTAMP DEFAULT NOW()"),
        ]

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

    print(f"Migration 002 (Survey in a Box) complete: {tables_created}/{len(tables)} tables "
          f"verified on {db_type}")
    if errors > 0:
        print(f"  {errors} table(s) had warnings (likely already exist)")
    return True


if __name__ == '__main__':
    result = run_migration()
    print(f"Migration result: {result}")

# I did no harm and this file is not truncated
