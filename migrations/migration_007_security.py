"""
AI SWARM ORCHESTRATOR — Migration 007: Security Enhancements 
Created: April 7, 2026
Last Updated: April 7, 2026
Author: Claude Opus 4.6 for Jim @ Shiftwork Solutions LLC

PURPOSE:
    Adds security infrastructure to the Swarm database:

    1. ip_blocklist table — stores blocked IPs with reason and timestamps.
       Used by newsletter subscribe, contact form, and any future endpoints
       that accept public input. Jim can block/unblock IPs via admin API.

    2. contact_submissions table — logs every contact form submission with
       IP, user agent, email domain, and spam score. Gives Jim the same
       visibility on contact form senders that he already has on newsletter
       signups. Submissions are logged here THEN forwarded to Formspree.

    3. user_agent column on newsletter_subscribers — tracks the browser/bot
       user agent string on every newsletter signup for forensic analysis.

    4. email_domain column on newsletter_subscribers — extracted domain
       from email for quick filtering/reporting by domain.

    All changes are fully idempotent — safe to run on every startup.

TABLES CREATED:
    ip_blocklist
        id              SERIAL PRIMARY KEY
        ip_address      VARCHAR(45) NOT NULL UNIQUE
        reason          TEXT
        blocked_at      TIMESTAMP DEFAULT NOW()
        blocked_by      VARCHAR(100) DEFAULT 'admin'
        is_active       BOOLEAN DEFAULT TRUE

    contact_submissions
        id              SERIAL PRIMARY KEY
        name            VARCHAR(255)
        email           VARCHAR(255) NOT NULL
        email_domain    VARCHAR(255)
        company         VARCHAR(255)
        phone           VARCHAR(50)
        employees       VARCHAR(50)
        message         TEXT
        source          VARCHAR(100) DEFAULT 'website-contact'
        ip_address      VARCHAR(45)
        user_agent      TEXT
        submitted_at    TIMESTAMP DEFAULT NOW()
        is_spam         BOOLEAN DEFAULT FALSE
        spam_reason     VARCHAR(255)
        forwarded       BOOLEAN DEFAULT FALSE

COLUMNS ADDED:
    newsletter_subscribers.user_agent   TEXT
    newsletter_subscribers.email_domain VARCHAR(255)

GOLDEN RULES FOLLOWED:
    - All SQL uses %s placeholders via db_engine.py
    - Never imports sqlite3 directly
    - Uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS
    - Fully idempotent — safe to run on every startup

I did no harm and this file is not truncated
"""

from db_engine import get_db_connection, get_db_type


def run_migration():
    """Run all security enhancement migrations."""
    print("Migration 007: Security Enhancements...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        if get_db_type() == 'postgresql':
            _migrate_postgresql(cursor)
        else:
            _migrate_sqlite(cursor)

        conn.commit()
        print("Migration 007: Security enhancements complete")

    except Exception as e:
        print(f"Migration 007 error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_postgresql(cursor):
    """PostgreSQL-specific migration statements."""

    # ── TABLE 1: ip_blocklist ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ip_blocklist (
            id              SERIAL PRIMARY KEY,
            ip_address      VARCHAR(45) NOT NULL UNIQUE,
            reason          TEXT,
            blocked_at      TIMESTAMP DEFAULT NOW(),
            blocked_by      VARCHAR(100) DEFAULT 'admin',
            is_active       BOOLEAN DEFAULT TRUE
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_blocklist_ip
        ON ip_blocklist (ip_address)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_blocklist_active
        ON ip_blocklist (is_active) WHERE is_active = TRUE
    """)
    print("  - ip_blocklist table ready")

    # ── TABLE 2: contact_submissions ───────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_submissions (
            id              SERIAL PRIMARY KEY,
            name            VARCHAR(255),
            email           VARCHAR(255) NOT NULL,
            email_domain    VARCHAR(255),
            company         VARCHAR(255),
            phone           VARCHAR(50),
            employees       VARCHAR(50),
            message         TEXT,
            source          VARCHAR(100) DEFAULT 'website-contact',
            ip_address      VARCHAR(45),
            user_agent      TEXT,
            submitted_at    TIMESTAMP DEFAULT NOW(),
            is_spam         BOOLEAN DEFAULT FALSE,
            spam_reason     VARCHAR(255),
            forwarded       BOOLEAN DEFAULT FALSE
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_contact_email
        ON contact_submissions (email)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_contact_ip
        ON contact_submissions (ip_address)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_contact_submitted
        ON contact_submissions (submitted_at DESC)
    """)
    print("  - contact_submissions table ready")

    # ── COLUMN ADDS on newsletter_subscribers ──────────────────────────
    cursor.execute("""
        ALTER TABLE newsletter_subscribers
        ADD COLUMN IF NOT EXISTS user_agent TEXT
    """)
    cursor.execute("""
        ALTER TABLE newsletter_subscribers
        ADD COLUMN IF NOT EXISTS email_domain VARCHAR(255)
    """)
    # Index on ip_address for blocklist lookups (may already exist from usage)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_newsletter_ip
        ON newsletter_subscribers (ip_address)
    """)
    # Index on email_domain for domain-level reporting
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_newsletter_domain
        ON newsletter_subscribers (email_domain)
    """)
    print("  - newsletter_subscribers columns added (user_agent, email_domain)")


def _migrate_sqlite(cursor):
    """SQLite fallback for local development."""

    # ── TABLE 1: ip_blocklist ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ip_blocklist (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address      TEXT NOT NULL UNIQUE,
            reason          TEXT,
            blocked_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            blocked_by      TEXT DEFAULT 'admin',
            is_active       INTEGER DEFAULT 1
        )
    """)
    print("  - ip_blocklist table ready (SQLite)")

    # ── TABLE 2: contact_submissions ───────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_submissions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT,
            email           TEXT NOT NULL,
            email_domain    TEXT,
            company         TEXT,
            phone           TEXT,
            employees       TEXT,
            message         TEXT,
            source          TEXT DEFAULT 'website-contact',
            ip_address      TEXT,
            user_agent      TEXT,
            submitted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_spam         INTEGER DEFAULT 0,
            spam_reason     TEXT,
            forwarded       INTEGER DEFAULT 0
        )
    """)
    print("  - contact_submissions table ready (SQLite)")

    # ── COLUMN ADDS on newsletter_subscribers (SQLite) ─────────────────
    # SQLite does not support ADD COLUMN IF NOT EXISTS, so we check first
    try:
        cursor.execute("SELECT user_agent FROM newsletter_subscribers LIMIT 1")
    except Exception:
        cursor.execute("ALTER TABLE newsletter_subscribers ADD COLUMN user_agent TEXT")

    try:
        cursor.execute("SELECT email_domain FROM newsletter_subscribers LIMIT 1")
    except Exception:
        cursor.execute("ALTER TABLE newsletter_subscribers ADD COLUMN email_domain TEXT")

    print("  - newsletter_subscribers columns added (SQLite)")


if __name__ == '__main__':
    run_migration()


# I did no harm and this file is not truncated
