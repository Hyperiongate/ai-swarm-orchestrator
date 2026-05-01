"""
migrations/migration_009_ptt.py
AI Swarm Orchestrator — Migration 009: Part Time Tracker (Lite) Schema
Shiftwork Solutions LLC

Created:      2026-05-01
Last Updated: 2026-05-01

CHANGELOG:
  2026-05-01 — INITIAL BUILD (Phase 1).
    Creates all ptt_* tables for the Part Time Tracker Lite product.
    All tables are prefixed ptt_ to avoid any collision with existing
    Swarm tables. No existing tables are modified.

PURPOSE:
    Part Time Tracker Lite is a hosted, multi-tenant web application that
    lives at /ptt/ on the AI Swarm Orchestrator. It allows industrial
    operations HR admins to manage a pre-vetted pool of part-time and
    on-call workers.

TABLES CREATED:
    ptt_company         — one row per tenant (HR signup creates this)
    ptt_admin_user      — HR admins for a company (multi-admin capable)
    ptt_skill           — editable skill taxonomy per company
    ptt_worker          — part-time worker pool per company
    ptt_worker_skill    — many-to-many worker <-> skill
    ptt_availability    — recurring weekly availability per worker
    ptt_blackout        — date-range unavailability per worker
    ptt_shift           — open shifts created by HR
    ptt_shift_skill     — skills required for a shift
    ptt_shift_outreach  — HR contact log per shift/worker
    ptt_shift_claim     — worker claims on a shift
    ptt_magic_token     — single-use, time-limited login tokens (hashed)
    ptt_session         — server-side session store (cookie-backed)

GOLDEN RULES:
    - All SQL uses %s placeholders via db_engine.py
    - Never imports sqlite3 directly
    - Uses IF NOT EXISTS throughout
    - Fully idempotent — safe to run on every startup
    - No existing Swarm tables modified

I did no harm and this file is not truncated.
"""

from db_engine import get_db_connection, get_db_type


def run_migration():
    """Create all ptt_* tables for Part Time Tracker Lite."""
    print("Migration 009: Part Time Tracker schema...")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        db_type = get_db_type()

        if db_type == 'postgresql':
            _migrate_postgresql(cursor)
        else:
            _migrate_sqlite(cursor)

        conn.commit()
        print("Migration 009: Part Time Tracker schema complete")

    except Exception as e:
        print(f"Migration 009 error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SAVEPOINT HELPER — identical pattern used in migration_001
# ---------------------------------------------------------------------------
def _safe_exec(cursor, db_type, sql, label="statement"):
    """Execute SQL protected by a SAVEPOINT on PostgreSQL."""
    if db_type == 'postgresql':
        try:
            cursor.execute("SAVEPOINT ptt_stmt")
            cursor.execute(sql)
            cursor.execute("RELEASE SAVEPOINT ptt_stmt")
        except Exception as e:
            cursor.execute("ROLLBACK TO SAVEPOINT ptt_stmt")
            msg = str(e).lower()
            if 'already exists' not in msg and 'duplicate' not in msg:
                print(f"  Migration 009 note [{label}]: {e}")
    else:
        try:
            cursor.execute(sql)
        except Exception as e:
            msg = str(e).lower()
            if 'already exists' not in msg and 'duplicate' not in msg:
                print(f"  Migration 009 note [{label}]: {e}")


def _migrate_postgresql(cursor):
    """PostgreSQL DDL for all ptt_* tables."""

    statements = []

    # ── ptt_company ──────────────────────────────────────────────────────────
    statements.append(("ptt_company", """
        CREATE TABLE IF NOT EXISTS ptt_company (
            id              SERIAL PRIMARY KEY,
            name            TEXT NOT NULL,
            slug            TEXT NOT NULL UNIQUE,
            email_domain    TEXT NOT NULL,
            signup_email    TEXT NOT NULL,
            industry        TEXT,
            facility_size   TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    statements.append(("idx_ptt_company_email_domain", """
        CREATE INDEX IF NOT EXISTS idx_ptt_company_email_domain
        ON ptt_company(email_domain)
    """))
    statements.append(("idx_ptt_company_slug", """
        CREATE INDEX IF NOT EXISTS idx_ptt_company_slug
        ON ptt_company(slug)
    """))

    # ── ptt_admin_user ────────────────────────────────────────────────────────
    statements.append(("ptt_admin_user", """
        CREATE TABLE IF NOT EXISTS ptt_admin_user (
            id              SERIAL PRIMARY KEY,
            company_id      INTEGER NOT NULL REFERENCES ptt_company(id)
                            ON DELETE CASCADE,
            email           TEXT NOT NULL,
            name            TEXT NOT NULL,
            role            TEXT DEFAULT 'admin',
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            last_login_at   TIMESTAMPTZ,
            UNIQUE (company_id, email)
        )
    """))
    statements.append(("idx_ptt_admin_user_company", """
        CREATE INDEX IF NOT EXISTS idx_ptt_admin_user_company
        ON ptt_admin_user(company_id)
    """))

    # ── ptt_skill ─────────────────────────────────────────────────────────────
    statements.append(("ptt_skill", """
        CREATE TABLE IF NOT EXISTS ptt_skill (
            id              SERIAL PRIMARY KEY,
            company_id      INTEGER NOT NULL REFERENCES ptt_company(id)
                            ON DELETE CASCADE,
            name            TEXT NOT NULL,
            description     TEXT,
            sort_order      INTEGER DEFAULT 0,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (company_id, name)
        )
    """))
    statements.append(("idx_ptt_skill_company", """
        CREATE INDEX IF NOT EXISTS idx_ptt_skill_company
        ON ptt_skill(company_id, sort_order)
    """))

    # ── ptt_worker ────────────────────────────────────────────────────────────
    statements.append(("ptt_worker", """
        CREATE TABLE IF NOT EXISTS ptt_worker (
            id              SERIAL PRIMARY KEY,
            company_id      INTEGER NOT NULL REFERENCES ptt_company(id)
                            ON DELETE CASCADE,
            name            TEXT NOT NULL,
            email           TEXT NOT NULL,
            phone           TEXT,
            status          TEXT NOT NULL DEFAULT 'pending',
            notes           TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            approved_at     TIMESTAMPTZ,
            UNIQUE (company_id, email)
        )
    """))
    statements.append(("idx_ptt_worker_company_status", """
        CREATE INDEX IF NOT EXISTS idx_ptt_worker_company_status
        ON ptt_worker(company_id, status)
    """))

    # ── ptt_worker_skill ──────────────────────────────────────────────────────
    statements.append(("ptt_worker_skill", """
        CREATE TABLE IF NOT EXISTS ptt_worker_skill (
            worker_id       INTEGER NOT NULL REFERENCES ptt_worker(id)
                            ON DELETE CASCADE,
            skill_id        INTEGER NOT NULL REFERENCES ptt_skill(id)
                            ON DELETE CASCADE,
            PRIMARY KEY (worker_id, skill_id)
        )
    """))

    # ── ptt_availability ──────────────────────────────────────────────────────
    statements.append(("ptt_availability", """
        CREATE TABLE IF NOT EXISTS ptt_availability (
            id              SERIAL PRIMARY KEY,
            worker_id       INTEGER NOT NULL REFERENCES ptt_worker(id)
                            ON DELETE CASCADE,
            day_of_week     SMALLINT NOT NULL,
            start_time      TIME NOT NULL,
            end_time        TIME NOT NULL,
            CHECK (day_of_week BETWEEN 0 AND 6),
            CHECK (end_time > start_time)
        )
    """))
    statements.append(("idx_ptt_availability_worker", """
        CREATE INDEX IF NOT EXISTS idx_ptt_availability_worker
        ON ptt_availability(worker_id)
    """))

    # ── ptt_blackout ──────────────────────────────────────────────────────────
    statements.append(("ptt_blackout", """
        CREATE TABLE IF NOT EXISTS ptt_blackout (
            id              SERIAL PRIMARY KEY,
            worker_id       INTEGER NOT NULL REFERENCES ptt_worker(id)
                            ON DELETE CASCADE,
            start_date      DATE NOT NULL,
            end_date        DATE NOT NULL,
            reason          TEXT,
            CHECK (end_date >= start_date)
        )
    """))
    statements.append(("idx_ptt_blackout_worker", """
        CREATE INDEX IF NOT EXISTS idx_ptt_blackout_worker
        ON ptt_blackout(worker_id)
    """))

    # ── ptt_shift ─────────────────────────────────────────────────────────────
    statements.append(("ptt_shift", """
        CREATE TABLE IF NOT EXISTS ptt_shift (
            id              SERIAL PRIMARY KEY,
            company_id      INTEGER NOT NULL REFERENCES ptt_company(id)
                            ON DELETE CASCADE,
            title           TEXT NOT NULL,
            shift_date      DATE NOT NULL,
            start_time      TIME NOT NULL,
            end_time        TIME NOT NULL,
            workers_needed  INTEGER NOT NULL DEFAULT 1,
            status          TEXT NOT NULL DEFAULT 'open',
            notes           TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            updated_at      TIMESTAMPTZ DEFAULT NOW(),
            CHECK (workers_needed >= 1),
            CHECK (status IN ('open', 'filled', 'cancelled'))
        )
    """))
    statements.append(("idx_ptt_shift_company_date", """
        CREATE INDEX IF NOT EXISTS idx_ptt_shift_company_date
        ON ptt_shift(company_id, shift_date)
    """))
    statements.append(("idx_ptt_shift_status", """
        CREATE INDEX IF NOT EXISTS idx_ptt_shift_status
        ON ptt_shift(company_id, status)
    """))

    # ── ptt_shift_skill ───────────────────────────────────────────────────────
    statements.append(("ptt_shift_skill", """
        CREATE TABLE IF NOT EXISTS ptt_shift_skill (
            shift_id        INTEGER NOT NULL REFERENCES ptt_shift(id)
                            ON DELETE CASCADE,
            skill_id        INTEGER NOT NULL REFERENCES ptt_skill(id)
                            ON DELETE CASCADE,
            PRIMARY KEY (shift_id, skill_id)
        )
    """))

    # ── ptt_shift_outreach ────────────────────────────────────────────────────
    statements.append(("ptt_shift_outreach", """
        CREATE TABLE IF NOT EXISTS ptt_shift_outreach (
            id              SERIAL PRIMARY KEY,
            shift_id        INTEGER NOT NULL REFERENCES ptt_shift(id)
                            ON DELETE CASCADE,
            worker_id       INTEGER NOT NULL REFERENCES ptt_worker(id)
                            ON DELETE CASCADE,
            contacted_at    TIMESTAMPTZ DEFAULT NOW(),
            notes           TEXT,
            UNIQUE (shift_id, worker_id)
        )
    """))
    statements.append(("idx_ptt_outreach_shift", """
        CREATE INDEX IF NOT EXISTS idx_ptt_outreach_shift
        ON ptt_shift_outreach(shift_id)
    """))

    # ── ptt_shift_claim ───────────────────────────────────────────────────────
    statements.append(("ptt_shift_claim", """
        CREATE TABLE IF NOT EXISTS ptt_shift_claim (
            id              SERIAL PRIMARY KEY,
            shift_id        INTEGER NOT NULL REFERENCES ptt_shift(id)
                            ON DELETE CASCADE,
            worker_id       INTEGER NOT NULL REFERENCES ptt_worker(id)
                            ON DELETE CASCADE,
            status          TEXT NOT NULL DEFAULT 'claimed',
            claimed_at      TIMESTAMPTZ DEFAULT NOW(),
            resolved_at     TIMESTAMPTZ,
            notes           TEXT,
            UNIQUE (shift_id, worker_id),
            CHECK (status IN ('claimed', 'confirmed', 'declined'))
        )
    """))
    statements.append(("idx_ptt_claim_shift", """
        CREATE INDEX IF NOT EXISTS idx_ptt_claim_shift
        ON ptt_shift_claim(shift_id)
    """))
    statements.append(("idx_ptt_claim_worker", """
        CREATE INDEX IF NOT EXISTS idx_ptt_claim_worker
        ON ptt_shift_claim(worker_id)
    """))

    # ── ptt_magic_token ───────────────────────────────────────────────────────
    # Tokens are stored as SHA-256 hash — NEVER plaintext.
    # single_use: once redeemed, the token is deleted.
    # user_type: 'admin' or 'worker'
    statements.append(("ptt_magic_token", """
        CREATE TABLE IF NOT EXISTS ptt_magic_token (
            id              SERIAL PRIMARY KEY,
            token_hash      TEXT NOT NULL UNIQUE,
            user_type       TEXT NOT NULL,
            user_id         INTEGER NOT NULL,
            company_id      INTEGER NOT NULL REFERENCES ptt_company(id)
                            ON DELETE CASCADE,
            expires_at      TIMESTAMPTZ NOT NULL,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            CHECK (user_type IN ('admin', 'worker'))
        )
    """))
    statements.append(("idx_ptt_token_hash", """
        CREATE INDEX IF NOT EXISTS idx_ptt_token_hash
        ON ptt_magic_token(token_hash)
    """))
    statements.append(("idx_ptt_token_expires", """
        CREATE INDEX IF NOT EXISTS idx_ptt_token_expires
        ON ptt_magic_token(expires_at)
    """))

    # ── ptt_session ───────────────────────────────────────────────────────────
    # Server-side session store. Cookie holds the session_id (random UUID).
    # Payload is JSON: {user_id, user_type, company_id, expires_at}
    statements.append(("ptt_session", """
        CREATE TABLE IF NOT EXISTS ptt_session (
            id              SERIAL PRIMARY KEY,
            session_id      TEXT NOT NULL UNIQUE,
            user_type       TEXT NOT NULL,
            user_id         INTEGER NOT NULL,
            company_id      INTEGER NOT NULL,
            payload         JSONB NOT NULL DEFAULT '{}',
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            expires_at      TIMESTAMPTZ NOT NULL,
            last_seen_at    TIMESTAMPTZ DEFAULT NOW(),
            CHECK (user_type IN ('admin', 'worker'))
        )
    """))
    statements.append(("idx_ptt_session_id", """
        CREATE INDEX IF NOT EXISTS idx_ptt_session_id
        ON ptt_session(session_id)
    """))
    statements.append(("idx_ptt_session_expires", """
        CREATE INDEX IF NOT EXISTS idx_ptt_session_expires
        ON ptt_session(expires_at)
    """))

    # Execute all statements
    for label, sql in statements:
        _safe_exec(cursor, 'postgresql', sql, label)

    print("  - All ptt_* tables and indexes ready (PostgreSQL)")


def _migrate_sqlite(cursor):
    """SQLite fallback — development use only."""

    # ptt_company
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_company (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            slug            TEXT NOT NULL UNIQUE,
            email_domain    TEXT NOT NULL,
            signup_email    TEXT NOT NULL,
            industry        TEXT,
            facility_size   TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ptt_admin_user
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_admin_user (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id      INTEGER NOT NULL,
            email           TEXT NOT NULL,
            name            TEXT NOT NULL,
            role            TEXT DEFAULT 'admin',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at   TIMESTAMP,
            UNIQUE (company_id, email)
        )
    """)

    # ptt_skill
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_skill (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id      INTEGER NOT NULL,
            name            TEXT NOT NULL,
            description     TEXT,
            sort_order      INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (company_id, name)
        )
    """)

    # ptt_worker
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_worker (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id      INTEGER NOT NULL,
            name            TEXT NOT NULL,
            email           TEXT NOT NULL,
            phone           TEXT,
            status          TEXT NOT NULL DEFAULT 'pending',
            notes           TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at     TIMESTAMP,
            UNIQUE (company_id, email)
        )
    """)

    # ptt_worker_skill
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_worker_skill (
            worker_id       INTEGER NOT NULL,
            skill_id        INTEGER NOT NULL,
            PRIMARY KEY (worker_id, skill_id)
        )
    """)

    # ptt_availability
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_availability (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id       INTEGER NOT NULL,
            day_of_week     INTEGER NOT NULL,
            start_time      TEXT NOT NULL,
            end_time        TEXT NOT NULL
        )
    """)

    # ptt_blackout
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_blackout (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id       INTEGER NOT NULL,
            start_date      TEXT NOT NULL,
            end_date        TEXT NOT NULL,
            reason          TEXT
        )
    """)

    # ptt_shift
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_shift (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id      INTEGER NOT NULL,
            title           TEXT NOT NULL,
            shift_date      TEXT NOT NULL,
            start_time      TEXT NOT NULL,
            end_time        TEXT NOT NULL,
            workers_needed  INTEGER NOT NULL DEFAULT 1,
            status          TEXT NOT NULL DEFAULT 'open',
            notes           TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ptt_shift_skill
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_shift_skill (
            shift_id        INTEGER NOT NULL,
            skill_id        INTEGER NOT NULL,
            PRIMARY KEY (shift_id, skill_id)
        )
    """)

    # ptt_shift_outreach
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_shift_outreach (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id        INTEGER NOT NULL,
            worker_id       INTEGER NOT NULL,
            contacted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes           TEXT,
            UNIQUE (shift_id, worker_id)
        )
    """)

    # ptt_shift_claim
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_shift_claim (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id        INTEGER NOT NULL,
            worker_id       INTEGER NOT NULL,
            status          TEXT NOT NULL DEFAULT 'claimed',
            claimed_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at     TIMESTAMP,
            notes           TEXT,
            UNIQUE (shift_id, worker_id)
        )
    """)

    # ptt_magic_token
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_magic_token (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash      TEXT NOT NULL UNIQUE,
            user_type       TEXT NOT NULL,
            user_id         INTEGER NOT NULL,
            company_id      INTEGER NOT NULL,
            expires_at      TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ptt_session
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ptt_session (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT NOT NULL UNIQUE,
            user_type       TEXT NOT NULL,
            user_id         INTEGER NOT NULL,
            company_id      INTEGER NOT NULL,
            payload         TEXT NOT NULL DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at      TEXT NOT NULL,
            last_seen_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    print("  - All ptt_* tables ready (SQLite)")


if __name__ == '__main__':
    run_migration()

# I did no harm and this file is not truncated.
