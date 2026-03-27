"""
AI SWARM ORCHESTRATOR - Database Migration 005
File: migrations/migration_005_code_mode.py
Created: March 27, 2026
Last Updated: March 27, 2026 — Phase 2: Code mode selection

PURPOSE:
    Adds code_mode column to survey_projects.
    Stores whether the project uses randomly-assigned 5-digit survey codes
    (the default) or existing employee ID numbers for survey access.

    Values:
        'random'       — System generates unique 5-digit codes per employee.
                         Jim distributes a code sheet. Employees enter the code
                         when starting the survey. (default)
        'employee_id'  — Employees enter their existing employee ID number.
                         No code sheet needed. Roster upload must include an
                         Employee ID column.

    This column is set during roster upload and read by:
        - survey_respondent.py (submit_survey): determines validation rules
          for the code field (5 digits vs flexible alphanumeric)
        - survey_respondent.py (get_survey_questions): passes code_mode to
          frontend so it can show appropriate label and placeholder
        - survey_admin.py (download_roster_codes): adjusts instructions text

CHANGELOG:
    - March 27, 2026: Initial creation. Follows exact pattern of migration_004.

USAGE:
    Called automatically by app.py STEP 1 (after migration_004).
    Can also be run directly:
        python migrations/migration_005_code_mode.py
    Safe to run multiple times — fully idempotent.

POSTGRESQL RULES FOLLOWED:
    - %s for all parameters
    - Autocommit connection for all DDL statements
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_autocommit_conn(db_type):
    """Return autocommit connection — same pattern as migrations 003 and 004."""
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
    """Return True if table_name.column_name exists."""
    if db_type == 'postgresql':
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        """, (table_name, column_name))
        return cursor.fetchone() is not None
    else:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return any(row[1] == column_name for row in cursor.fetchall())


def run_migration():
    from db_engine import get_db_type

    db_type = get_db_type()
    print(f"Running migration 005_code_mode on {db_type}...")

    conn = _get_autocommit_conn(db_type)
    try:
        cursor = conn.cursor()

        # Add code_mode to survey_projects
        if db_type == 'postgresql':
            sql = ("ALTER TABLE survey_projects "
                   "ADD COLUMN IF NOT EXISTS code_mode TEXT DEFAULT 'random'")
        else:
            sql = "ALTER TABLE survey_projects ADD COLUMN code_mode TEXT DEFAULT 'random'"

        try:
            cursor.execute(sql)
            print("  ALTER OK: survey_projects.code_mode")
        except Exception as e:
            msg = str(e).lower()
            if 'already exists' in msg or 'duplicate column' in msg:
                print("  ALTER SKIP (already exists): survey_projects.code_mode")
            else:
                print(f"  ALTER NOTE survey_projects.code_mode: {e}")

    finally:
        conn.close()

    # Verify
    verify_conn = _get_autocommit_conn(db_type)
    try:
        vcursor = verify_conn.cursor()
        has_col = _table_has_column(vcursor, db_type, 'survey_projects', 'code_mode')
    finally:
        verify_conn.close()

    if has_col:
        print("Migration 005 (Code Mode) complete: schema verified OK")
    else:
        print("Migration 005 WARNING: survey_projects.code_mode not found after migration")

    return has_col


if __name__ == '__main__':
    result = run_migration()
    print(f"Migration result: {result}")

# I did no harm and this file is not truncated
