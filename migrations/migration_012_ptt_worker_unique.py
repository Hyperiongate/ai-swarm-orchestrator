"""
migrations/migration_012_ptt_worker_unique.py
AI Swarm Orchestrator — Migration 012: Fix ptt_worker unique constraint
Shiftwork Solutions LLC

Created:      2026-05-08
Last Updated: 2026-05-08

CHANGELOG:
  2026-05-08 — INITIAL BUILD.
    The original migration_009 created ptt_worker with a
    UNIQUE(company_id, email) constraint. This prevents two people
    with different names from applying using the same email address
    (e.g. a shared family email). The business rule is:
      - Same name + same email + same company = duplicate (blocked)
      - Different name + same email + same company = allowed

    This migration:
      1. Drops the old UNIQUE(company_id, email) constraint
      2. Adds a new UNIQUE(company_id, name, email) constraint

    Fully idempotent — safe to run on every startup.
    No other tables modified.

I did no harm and this file is not truncated.
"""

from db_engine import get_db_connection, get_db_type


def run_migration():
    """Replace unique(company_id, email) with unique(company_id, name, email) on ptt_worker."""
    print("Migration 012: Fix ptt_worker unique constraint...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        db_type = get_db_type()

        if db_type == 'postgresql':

            # Step 1: Drop the old unique constraint on (company_id, email)
            # The constraint name from migration_009 is 'ptt_worker_company_id_email_key'
            try:
                cursor.execute("SAVEPOINT m012_drop")
                cursor.execute("""
                    ALTER TABLE ptt_worker
                    DROP CONSTRAINT IF EXISTS ptt_worker_company_id_email_key
                """)
                cursor.execute("RELEASE SAVEPOINT m012_drop")
                print("  - Dropped ptt_worker_company_id_email_key")
            except Exception as e:
                cursor.execute("ROLLBACK TO SAVEPOINT m012_drop")
                print(f"  - Drop constraint note: {e}")

            # Step 2: Add new unique constraint on (company_id, name, email)
            try:
                cursor.execute("SAVEPOINT m012_add")
                cursor.execute("""
                    ALTER TABLE ptt_worker
                    ADD CONSTRAINT ptt_worker_company_name_email_key
                    UNIQUE (company_id, name, email)
                """)
                cursor.execute("RELEASE SAVEPOINT m012_add")
                print("  - Added ptt_worker_company_name_email_key (company_id, name, email)")
            except Exception as e:
                cursor.execute("ROLLBACK TO SAVEPOINT m012_add")
                if 'already exists' not in str(e).lower():
                    print(f"  - Add constraint note: {e}")
                else:
                    print("  - ptt_worker_company_name_email_key already exists")

        else:
            # SQLite — constraints cannot be easily modified; recreate not needed for dev
            print("  - SQLite: constraint modification skipped (dev only)")

        conn.commit()
        print("Migration 012: ptt_worker unique constraint fix complete")

    except Exception as e:
        print(f"Migration 012 error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()

# I did no harm and this file is not truncated.
