"""
AI SWARM ORCHESTRATOR — Daily Contact-Form Self-Test (heartbeat email)
File: proactive/contact_selftest.py
Created: July 23, 2026
Last Updated: July 23, 2026
Author: Claude for Jim @ Shiftwork Solutions LLC

CHANGELOG:
- July 23, 2026: (v1) INITIAL BUILD.
    Jim asked for a daily "test email from the website" that proves the
    contact form's email pipeline is actually working. This module sends
    exactly one clearly-labeled heartbeat email each morning through the
    SAME Formspree form real contact submissions use, so the email landing
    in Contact@shift-work.com is direct proof that the real
    server -> Formspree -> inbox path (the leg that silently breaks) is alive.

PURPOSE:
    run_contact_selftest() is called once a day by proactive/scheduler.py
    (JOB 7, 6:50 AM Pacific). It:
        1. Checks the ENABLE_CONTACT_SELFTEST switch (default ON).
        2. Atomically claims today's run in the contact_selftest_log table so
           that — even with 2 gunicorn workers both firing the job at the same
           minute — only ONE worker actually sends, and Jim never gets two
           heartbeat emails. (Same multi-worker concern the daily briefing
           solves with its briefing_date UPSERT; here we use an
           INSERT ... ON CONFLICT DO NOTHING claim.)
        3. POSTs a labeled test submission to the contact Formspree form.
        4. Records success/failure back to contact_selftest_log for the record.

    The email arriving = pipeline healthy. The email NOT arriving on a given
    day is itself the signal that something is wrong (the same "absence = alarm"
    logic a heartbeat monitor uses).

WHY ITS OWN FORMSPREE POST (not importing contact_api):
    alert_system.py already keeps its own hardened _post_to_formspree() rather
    than sharing one, so this module follows that established pattern and stays
    fully self-contained. It does NOT modify routes/contact_api.py (Rule 1 —
    do no harm — keeps the just-deployed contact endpoint untouched), and it
    inserts NO fake row into the contact_submissions leads table.

ENVIRONMENT VARIABLES:
    ENABLE_CONTACT_SELFTEST   'true' (default) / 'false' — toggle just this
                              heartbeat without touching the other scheduled
                              jobs. Note: the scheduler itself must also be on
                              (ENABLE_SCHEDULED_JOBS=true) for this to run.
    SELFTEST_FORMSPREE_ID     Optional. Formspree form ID (or full URL) for the
                              heartbeat. Defaults to FORMSPREE_FORM_ID, then to
                              the contact form 'xwvwnwea' — i.e. it lands in the
                              same Contact@shift-work.com inbox as real leads,
                              which is exactly what Jim asked for. Point it at a
                              separate form here if you ever want to keep the
                              daily heartbeat out of that inbox (or off a
                              limited Formspree plan's monthly quota).

GOLDEN RULES FOLLOWED:
    - All SQL uses %s placeholders (PostgreSQL) with a SQLite fallback.
    - Never imports sqlite3 directly — goes through db_engine.py.
    - Standard-library only for the HTTP POST (urllib) — no new dependency.
    - Never raises to the caller; every failure is logged and returned as data.

I did no harm and this file is not truncated
"""

import os
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

ENABLE_CONTACT_SELFTEST = os.environ.get('ENABLE_CONTACT_SELFTEST', 'true').lower() == 'true'

# Reuse the contact form's Formspree ID by default so the heartbeat lands in the
# same Contact@shift-work.com inbox real leads do. Resolution order:
#   SELFTEST_FORMSPREE_ID  ->  FORMSPREE_FORM_ID  ->  'xwvwnwea' (contact form)
SELFTEST_FORMSPREE_ID = (
    os.environ.get('SELFTEST_FORMSPREE_ID')
    or os.environ.get('FORMSPREE_FORM_ID', 'xwvwnwea')
)


def _formspree_url():
    """Build the Formspree submission URL from SELFTEST_FORMSPREE_ID. Accepts a
    bare form ID or a full http(s) URL. Returns '' when not configured."""
    ep = (SELFTEST_FORMSPREE_ID or '').strip()
    if not ep:
        return ''
    if ep.startswith('http://') or ep.startswith('https://'):
        return ep
    return f'https://formspree.io/f/{ep}'


def _post_to_formspree(payload):
    """
    POST a JSON payload to Formspree. Standard-library only (urllib) — no new
    dependency. Returns (ok: bool, detail: str). Never raises.

    Sends a browser-style User-Agent because Formspree's spam/bot filtering can
    reject the default 'Python-urllib/x.y' agent with a 4xx even when the same
    form accepts browser submissions (the exact hardening alert_system.py uses).
    On failure the real Formspree status + body is captured in `detail`.
    """
    url = _formspree_url()
    if not url:
        return False, 'Formspree endpoint not configured (set SELFTEST_FORMSPREE_ID or FORMSPREE_FORM_ID)'
    try:
        import urllib.request
        import urllib.error
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/124.0.0.0 Safari/537.36'
                ),
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            ok = 200 <= resp.status < 300
            if ok:
                return True, f'HTTP {resp.status}'
            body = ''
            try:
                body = resp.read().decode('utf-8', 'replace')[:300]
            except Exception:
                pass
            return False, f'HTTP {resp.status}: {body}'
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8', 'replace')[:300]
        except Exception:
            pass
        return False, f'HTTP {e.code}: {body}'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'


# ============================================================================
# PER-DAY IDEMPOTENCY GUARD (survives 2 gunicorn workers -> 1 email)
# ============================================================================

def _ensure_table(cursor, db_type):
    """Lazily create contact_selftest_log (idempotent CREATE TABLE IF NOT EXISTS)."""
    if db_type == 'postgresql':
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contact_selftest_log (
                run_date  DATE PRIMARY KEY,
                sent_at   TIMESTAMP DEFAULT NOW(),
                success   BOOLEAN,
                detail    TEXT
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contact_selftest_log (
                run_date  TEXT PRIMARY KEY,
                sent_at   TEXT,
                success   INTEGER,
                detail    TEXT
            )
        """)


def _claim_today():
    """
    Atomically claim today's run. Returns True if THIS process won the claim
    (and should send), False if another worker already claimed it today.

    Uses INSERT ... ON CONFLICT DO NOTHING (PostgreSQL) / a caught duplicate
    INSERT (SQLite). Because both workers fire at the same cron minute, we claim
    BEFORE sending: a rare failed-send day (no email) is preferable to ever
    sending Jim two heartbeat emails.
    """
    from db_engine import get_db_connection, get_db_type
    db_type = get_db_type()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        _ensure_table(cursor, db_type)
        conn.commit()
        if db_type == 'postgresql':
            cursor.execute("""
                INSERT INTO contact_selftest_log (run_date)
                VALUES (CURRENT_DATE)
                ON CONFLICT (run_date) DO NOTHING
                RETURNING run_date
            """)
            claimed = cursor.fetchone() is not None
            conn.commit()
        else:
            try:
                cursor.execute(
                    "INSERT INTO contact_selftest_log (run_date, sent_at) VALUES (date('now'), datetime('now'))"
                )
                conn.commit()
                claimed = True
            except Exception:
                conn.rollback()
                claimed = False
        return claimed
    finally:
        conn.close()


def _record_result(success, detail):
    """Record the send outcome onto today's claim row (best-effort)."""
    from db_engine import get_db_connection, get_db_type
    db_type = get_db_type()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if db_type == 'postgresql':
            cursor.execute(
                "UPDATE contact_selftest_log SET success = %s, detail = %s, sent_at = NOW() WHERE run_date = CURRENT_DATE",
                (bool(success), (detail or '')[:500])
            )
        else:
            cursor.execute(
                "UPDATE contact_selftest_log SET success = ?, detail = ?, sent_at = datetime('now') WHERE run_date = date('now')",
                (1 if success else 0, (detail or '')[:500])
            )
        conn.commit()
    except Exception as e:
        logger.warning(f"[ContactSelfTest] Could not record result (non-fatal): {e}")
    finally:
        conn.close()


# ============================================================================
# PUBLIC ENTRY POINT
# ============================================================================

def run_contact_selftest(force=False):
    """
    Send today's contact-pipeline heartbeat email (once per day).

    Args:
        force: when True, bypass BOTH the enable switch and the per-day claim
               and send immediately. Used for manual/on-demand verification.
               Normal scheduled runs call with force=False.

    Returns a dict:
        {'success': bool, 'skipped': bool, 'detail': str}
    Never raises.
    """
    if not ENABLE_CONTACT_SELFTEST and not force:
        logger.info("[ContactSelfTest] Disabled via ENABLE_CONTACT_SELFTEST=false — skipping")
        return {'success': False, 'skipped': True, 'detail': 'disabled via ENABLE_CONTACT_SELFTEST=false'}

    # Per-day claim (skipped when forced) so 2 workers never send 2 emails.
    if not force:
        try:
            if not _claim_today():
                logger.info("[ContactSelfTest] Already sent today (another worker claimed it) — skipping")
                return {'success': True, 'skipped': True, 'detail': 'already sent today'}
        except Exception as e:
            # If the guard itself errors, fall through and still send — a
            # possible duplicate is less bad than a silent no-send. Logged.
            logger.warning(f"[ContactSelfTest] Idempotency guard failed (sending anyway): {e}")

    now = datetime.now(timezone.utc)
    stamp = now.strftime('%Y-%m-%d %H:%M UTC')
    payload = {
        'name': 'Daily Self-Test (automated)',
        'email': 'selftest@shift-work.com',
        '_subject': '✅ Daily Self-Test — shift-work.com contact pipeline is working',
        'message': (
            'This is the automated daily test message from shift-work.com.\n\n'
            'If you are reading this email, the contact-form pipeline is healthy: '
            'the server reached Formspree and Formspree delivered to this inbox — '
            'the exact path a real contact submission travels.\n\n'
            f'Sent: {stamp}\n'
            'Source: proactive/contact_selftest.py (JOB 7, 6:50 AM Pacific)\n\n'
            'No action needed. If this email ever stops arriving, the contact '
            'form may be failing to deliver — check the Render logs and Formspree.'
        ),
        'source': 'daily-selftest',
        '_selftest': 'true',
    }

    ok, detail = _post_to_formspree(payload)

    if ok:
        logger.info(f"[ContactSelfTest] Heartbeat email sent OK ({detail})")
    else:
        logger.warning(f"[ContactSelfTest] Heartbeat email did NOT send: {detail}")

    if not force:
        _record_result(ok, detail)

    return {'success': ok, 'skipped': False, 'detail': detail}


# I did no harm and this file is not truncated
