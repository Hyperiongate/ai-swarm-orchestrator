"""
AI SWARM ORCHESTRATOR — Migration 006: Newsletter Subscribers Table
Created: April 2, 2026
Last Updated: April 2, 2026
Author: Claude Opus 4.6 for Jim @ Shiftwork Solutions LLC

PURPOSE:
    Creates the newsletter_subscribers table for storing email signups
    from the shift-work.com newsletter page. Fully idempotent — safe
    to run on every startup.

TABLE: newsletter_subscribers
    id              SERIAL PRIMARY KEY
    email           VARCHAR(255) NOT NULL UNIQUE
    name            VARCHAR(255)
    source          VARCHAR(100)       — where they signed up (e.g., 'website-newsletter-page', 'sidebar')
    subscribed_at   TIMESTAMP          — when they subscribed
    is_active       BOOLEAN            — for future unsubscribe support
    ip_address      VARCHAR(45)        — for rate limiting (IPv4 or IPv6)

GOLDEN RULES FOLLOWED:
    - All SQL uses %s placeholders via db_engine.py
    - Never imports sqlite3 directly
    - Uses RETURNING id (not lastrowid)
    - Fully idempotent with IF NOT EXISTS
    - Minimal-change rule for working files

I did no harm and this file is not truncated
"""

from db_engine import get_db_connection, get_db_type


def run_migration():
    """Create the newsletter_subscribers table if it does not exist."""
    print("Migration 006: Newsletter Subscribers table...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        if get_db_type() == 'postgresql':
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS newsletter_subscribers (
                    id              SERIAL PRIMARY KEY,
                    email           VARCHAR(255) NOT NULL UNIQUE,
                    name            VARCHAR(255),
                    source          VARCHAR(100) DEFAULT 'website',
                    subscribed_at   TIMESTAMP DEFAULT NOW(),
                    is_active       BOOLEAN DEFAULT TRUE,
                    ip_address      VARCHAR(45)
                )
            """)

            # Index on email for fast duplicate checks
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_newsletter_email
                ON newsletter_subscribers (email)
            """)

            # Index on subscribed_at for chronological queries / exports
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_newsletter_subscribed_at
                ON newsletter_subscribers (subscribed_at DESC)
            """)

        else:
            # SQLite fallback for local development
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS newsletter_subscribers (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    email           TEXT NOT NULL UNIQUE,
                    name            TEXT,
                    source          TEXT DEFAULT 'website',
                    subscribed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active       INTEGER DEFAULT 1,
                    ip_address      TEXT
                )
            """)

        conn.commit()
        print("Migration 006: newsletter_subscribers table ready")

    except Exception as e:
        print(f"Migration 006 error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()

# I did no harm and this file is not truncated
