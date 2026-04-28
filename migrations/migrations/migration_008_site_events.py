"""
AI SWARM ORCHESTRATOR — Migration 008: Site Events Tracking
Created: April 28, 2026
Last Updated: April 28, 2026
Author: Claude Sonnet 4.6 for Jim @ Shiftwork Solutions LLC

PURPOSE:
    Creates the site_events table for shift-work.com visitor event tracking.
    Stores all 10 tracked event types captured by /js/event-tracker.js on
    the static site. Data feeds the monthly analytics review alongside
    Plausible and Microsoft Clarity exports.

    Events tracked:
        1.  landing_page         — first page of session + referral source
        2.  contact_form         — contact form submission
        3.  newsletter_signup    — newsletter form submission
        4.  booking_click        — "Book a consultation" button click
        5.  thomas_opened        — Thomas AI widget opened
        6.  thomas_question      — Thomas AI question submitted
        7.  resource_download    — resource/guide download link click
        8.  phone_click          — phone number tap/click
        9.  scroll_depth         — scroll depth milestone (50% or 75%)
        10. time_on_page         — time threshold reached (60s)

TABLE CREATED:
    site_events
        id              SERIAL PRIMARY KEY
        event_type      VARCHAR(50) NOT NULL
        page_url        TEXT
        referrer        TEXT
        session_id      VARCHAR(64)
        device_type     VARCHAR(20)     — 'mobile' | 'tablet' | 'desktop'
        event_data      JSONB           — event-specific payload
        ip_address      VARCHAR(45)
        user_agent      TEXT
        created_at      TIMESTAMP DEFAULT NOW()

GOLDEN RULES FOLLOWED:
    - All SQL uses %s placeholders via db_engine.py
    - Never imports sqlite3 directly
    - Uses IF NOT EXISTS
    - Fully idempotent — safe to run on every startup

I did no harm and this file is not truncated
"""

from db_engine import get_db_connection, get_db_type


def run_migration():
    """Create site_events table for shift-work.com event tracking."""
    print("Migration 008: Site Events Tracking...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        if get_db_type() == 'postgresql':
            _migrate_postgresql(cursor)
        else:
            _migrate_sqlite(cursor)

        conn.commit()
        print("Migration 008: Site Events Tracking complete")

    except Exception as e:
        print(f"Migration 008 error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_postgresql(cursor):
    """PostgreSQL-specific migration statements."""

    # ── TABLE: site_events ────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_events (
            id              SERIAL PRIMARY KEY,
            event_type      VARCHAR(50) NOT NULL,
            page_url        TEXT,
            referrer        TEXT,
            session_id      VARCHAR(64),
            device_type     VARCHAR(20),
            event_data      JSONB DEFAULT '{}',
            ip_address      VARCHAR(45),
            user_agent      TEXT,
            created_at      TIMESTAMP DEFAULT NOW()
        )
    """)

    # Indexes for common query patterns in monthly review
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_events_type
        ON site_events (event_type)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_events_created
        ON site_events (created_at DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_events_session
        ON site_events (session_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_events_page
        ON site_events (page_url)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_events_type_created
        ON site_events (event_type, created_at DESC)
    """)

    print("  - site_events table ready (PostgreSQL)")


def _migrate_sqlite(cursor):
    """SQLite fallback for local development."""

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS site_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type      TEXT NOT NULL,
            page_url        TEXT,
            referrer        TEXT,
            session_id      TEXT,
            device_type     TEXT,
            event_data      TEXT DEFAULT '{}',
            ip_address      TEXT,
            user_agent      TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    print("  - site_events table ready (SQLite)")


if __name__ == '__main__':
    run_migration()


# I did no harm and this file is not truncated
