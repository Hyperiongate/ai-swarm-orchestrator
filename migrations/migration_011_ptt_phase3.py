"""
migrations/migration_011_ptt_phase3.py
AI Swarm Orchestrator — Migration 011: Part Time Tracker Phase 3
Shiftwork Solutions LLC

Created:      2026-05-06
Last Updated: 2026-05-06

CHANGELOG:
  2026-05-06 — INITIAL BUILD (Phase 3).
    Adds two columns to ptt_shift that are required for Phase 3:
      urgency          TEXT DEFAULT 'moderate'
                       Values: 'urgent' | 'moderate' | 'long_term'
      skill_required_id INTEGER REFERENCES ptt_skill(id) ON DELETE SET NULL
                       NULL means any skill (or no skill filter).
    Both columns are idempotent (ADD COLUMN IF NOT EXISTS).
    No other tables modified. No existing data changed.

I did no harm and this file is not truncated.
"""

from db_engine import get_db_connection, get_db_type


def run_migration():
    """Add urgency and skill_required_id to ptt_shift."""
    print("Migration 011: Part Time Tracker Phase 3 schema additions...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        db_type = get_db_type()

        if db_type == 'postgresql':
            # Add urgency column
            try:
                cursor.execute("SAVEPOINT m011_a")
                cursor.execute("""
                    ALTER TABLE ptt_shift
                    ADD COLUMN IF NOT EXISTS urgency TEXT DEFAULT 'moderate'
                """)
                cursor.execute("RELEASE SAVEPOINT m011_a")
                print("  - ptt_shift.urgency: ready")
            except Exception as e:
                cursor.execute("ROLLBACK TO SAVEPOINT m011_a")
                if 'already exists' not in str(e).lower():
                    print(f"  - ptt_shift.urgency note: {e}")

            # Add skill_required_id column
            try:
                cursor.execute("SAVEPOINT m011_b")
                cursor.execute("""
                    ALTER TABLE ptt_shift
                    ADD COLUMN IF NOT EXISTS skill_required_id INTEGER
                    REFERENCES ptt_skill(id) ON DELETE SET NULL
                """)
                cursor.execute("RELEASE SAVEPOINT m011_b")
                print("  - ptt_shift.skill_required_id: ready")
            except Exception as e:
                cursor.execute("ROLLBACK TO SAVEPOINT m011_b")
                if 'already exists' not in str(e).lower():
                    print(f"  - ptt_shift.skill_required_id note: {e}")

            # Add check constraint for urgency values (ignore if already exists)
            try:
                cursor.execute("SAVEPOINT m011_c")
                cursor.execute("""
                    ALTER TABLE ptt_shift
                    ADD CONSTRAINT ptt_shift_urgency_check
                    CHECK (urgency IN ('urgent', 'moderate', 'long_term'))
                """)
                cursor.execute("RELEASE SAVEPOINT m011_c")
                print("  - ptt_shift urgency check constraint: ready")
            except Exception as e:
                cursor.execute("ROLLBACK TO SAVEPOINT m011_c")
                # Constraint already exists — not an error
                if 'already exists' not in str(e).lower():
                    print(f"  - ptt_shift urgency constraint note: {e}")

        else:
            # SQLite — recreate not needed, ADD COLUMN works
            for col_sql in [
                "ALTER TABLE ptt_shift ADD COLUMN urgency TEXT DEFAULT 'moderate'",
                "ALTER TABLE ptt_shift ADD COLUMN skill_required_id INTEGER",
            ]:
                try:
                    cursor.execute(col_sql)
                except Exception as e:
                    if 'duplicate column' not in str(e).lower():
                        print(f"  SQLite note: {e}")

        conn.commit()
        print("Migration 011: Part Time Tracker Phase 3 schema additions complete")

    except Exception as e:
        print(f"Migration 011 error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()

# I did no harm and this file is not truncated.
