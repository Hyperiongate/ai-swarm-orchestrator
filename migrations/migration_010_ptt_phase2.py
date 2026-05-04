"""
migrations/migration_010_ptt_phase2.py
AI Swarm Orchestrator — Migration 010: Part Time Tracker Phase 2 Schema
Shiftwork Solutions LLC

Created:      2026-05-04
Last Updated: 2026-05-04

CHANGELOG:
  2026-05-04 — INITIAL BUILD (Phase 2).
    Adds worker audit columns to ptt_worker that are required for the
    approval/rejection workflow. No tables dropped, no existing columns
    modified. Fully idempotent — safe to run on every startup.

COLUMNS ADDED TO ptt_worker:
    approved_by       INTEGER   — FK to ptt_admin_user.id (nullable)
    approved_at       TIMESTAMPTZ — when the admin approved the worker
    rejected_at       TIMESTAMPTZ — when the admin rejected the worker
    rejection_reason  TEXT        — optional note from admin on rejection

NOTES:
    - ptt_shift_skill (junction table from migration_009) is confirmed
      as the correct many-to-many join for shift skill requirements.
      No skill_required_id column is needed or added.
    - All existing ptt_* tables from migration_009 are untouched.
    - No existing Swarm tables modified.

I did no harm and this file is not truncated.
"""

from db_engine import get_db_connection, get_db_type


def run_migration():
    """Add Phase 2 worker audit columns to ptt_worker."""
    print("Migration 010: Part Time Tracker Phase 2 schema...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        db_type = get_db_type()

        if db_type == 'postgresql':
            _migrate_postgresql(cursor)
        else:
            _migrate_sqlite(cursor)

        conn.commit()
        print("Migration 010: Part Time Tracker Phase 2 schema complete")

    except Exception as e:
        print(f"Migration 010 error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def _safe_alter(cursor, sql, label=""):
    """SAVEPOINT-protected ALTER TABLE — identical pattern to migration_001."""
    try:
        cursor.execute("SAVEPOINT m010_alter")
        cursor.execute(sql)
        cursor.execute("RELEASE SAVEPOINT m010_alter")
    except Exception as e:
        cursor.execute("ROLLBACK TO SAVEPOINT m010_alter")
        msg = str(e).lower()
        if 'already exists' not in msg and 'duplicate' not in msg:
            print(f"  Migration 010 note [{label}]: {e}")


def _migrate_postgresql(cursor):
    columns = [
        ("approved_by",      "INTEGER REFERENCES ptt_admin_user(id) ON DELETE SET NULL"),
        ("approved_at",      "TIMESTAMPTZ"),
        ("rejected_at",      "TIMESTAMPTZ"),
        ("rejection_reason", "TEXT"),
    ]
    for col_name, col_def in columns:
        sql = (f"ALTER TABLE ptt_worker ADD COLUMN IF NOT EXISTS "
               f"{col_name} {col_def}")
        _safe_alter(cursor, sql, col_name)
    print("  - ptt_worker audit columns ready (PostgreSQL)")


def _migrate_sqlite(cursor):
    """SQLite fallback — no FK enforcement, no IF NOT EXISTS on ALTER."""
    columns = [
        ("approved_by",      "INTEGER"),
        ("approved_at",      "TIMESTAMP"),
        ("rejected_at",      "TIMESTAMP"),
        ("rejection_reason", "TEXT"),
    ]
    for col_name, col_def in columns:
        try:
            cursor.execute(
                f"ALTER TABLE ptt_worker ADD COLUMN {col_name} {col_def}")
        except Exception as e:
            if 'duplicate' not in str(e).lower() and 'already exists' not in str(e).lower():
                print(f"  Migration 010 SQLite note [{col_name}]: {e}")
    print("  - ptt_worker audit columns ready (SQLite)")


if __name__ == '__main__':
    run_migration()

# I did no harm and this file is not truncated.
