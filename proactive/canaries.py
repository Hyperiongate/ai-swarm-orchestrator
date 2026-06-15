"""
AI SWARM ORCHESTRATOR - Self-Test Canaries
File: proactive/canaries.py
Created: June 14, 2026
Last Updated: June 14, 2026 — WO-13 Phase 1: framework + alert-delivery canary

PURPOSE:
    Automated SEMANTIC self-tests for the swarm. A canary does not just check
    that an endpoint returns HTTP 200 — it verifies the thing actually
    happened (an alert's email was really delivered, a briefing really has
    content, an evaluation really produced a score). The goal is to hand the
    manual "is anything quietly broken?" probing off to the swarm itself.

    Phase 1 (this file) ships the framework plus the single most relevant
    canary: end-to-end alert-email delivery — the exact silent failure that
    motivated WO-13 (the alert endpoint returned 200 the whole time while
    Formspree delivery was broken; the only proof of delivery is the alert
    row's emailed_at timestamp).

    Phase 2 adds briefing + evaluation canaries (needs daily_briefing.py and
    swarm_self_evaluation.py). Phase 3 schedules these via the scheduler and
    adds metric-trend anomaly detection.

DESIGN — why a canary can't always email its own failure:
    The alert-delivery canary tests the EMAIL channel itself. If that channel
    is broken, emailing the failure would fail too. So each canary declares
    can_alert_by_email. Failures are ALWAYS recorded to the canary_results
    table and exposed via /api/canaries/status; only canaries whose
    can_alert_by_email is True additionally raise an email alert (by which
    point delivery has been independently verified).

CHANGELOG:
- June 14, 2026: WO-13 PHASE 1 — INITIAL IMPLEMENTATION
  * New file. Defines the canary framework: a canary_results table (lazy
    init, SERIAL PK, %s placeholders — PostgreSQL), _record_result(),
    run_all_canaries(), and get_latest_canary_results().
  * First canary _canary_alert_delivery(): creates a HIGH-priority test
    alert with send_email=True (alert_system only emails HIGH/CRITICAL),
    then reads the row back via AlertManager.get_alert() and passes only if
    emailed_at is populated — i.e. the Formspree POST genuinely succeeded.
    Declares can_alert_by_email=False (it tests the email channel).
  * No existing file is modified by this module. alert_system is imported
    lazily inside functions (matches the scheduler's import-in-body pattern
    and avoids any import-time coupling). Rule 1 (do no harm) preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import logging
from datetime import datetime

from database import get_db

logger = logging.getLogger(__name__)


# ============================================================================
# RESULTS TABLE (lazy init)
# ============================================================================

_tables_initialized = False


def _ensure_canary_tables():
    """Create the canary_results table on first use. Idempotent."""
    global _tables_initialized
    if _tables_initialized:
        return
    db = get_db()
    try:
        db.execute('''
            CREATE TABLE IF NOT EXISTS canary_results (
                id          SERIAL PRIMARY KEY,
                canary_name TEXT NOT NULL,
                passed      BOOLEAN NOT NULL,
                detail      TEXT,
                checked_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()
    finally:
        db.close()
    _tables_initialized = True


def _record_result(name, passed, detail):
    """Persist a single canary outcome. Never raises into the caller."""
    try:
        _ensure_canary_tables()
        db = get_db()
        try:
            db.execute(
                'INSERT INTO canary_results (canary_name, passed, detail, checked_at) '
                'VALUES (%s, %s, %s, %s)',
                (name, bool(passed), detail, datetime.now())
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        # Recording is best-effort; a logging failure must not mask the canary.
        logger.error(f"[Canaries] could not record result for {name}: {e}")


# ============================================================================
# INDIVIDUAL CANARIES
# Each returns: {'name', 'passed', 'detail', 'can_alert_by_email'}
# and records its own result before returning.
# ============================================================================

def _canary_alert_delivery():
    """
    End-to-end alert email delivery.

    Creates a HIGH-priority test alert with send_email=True (alert_system
    only emails HIGH/CRITICAL), then reads the row back and verifies
    emailed_at was set — which is only true if the Formspree POST actually
    returned success. A 200 from the endpoint is NOT sufficient; emailed_at
    is the deterministic proof of delivery.

    can_alert_by_email is False: this canary tests the email channel, so its
    own failure cannot be reported through that same channel.
    """
    name = 'alert_delivery'
    try:
        from alert_system import get_alert_manager, AlertCategory, AlertPriority
        mgr = get_alert_manager()

        # If delivery is disabled by configuration, that's a known state, not a
        # send failure — report it plainly (and still not by email).
        if not getattr(mgr, 'email_enabled', False):
            detail = ('email delivery disabled — set ENABLE_EMAIL_ALERTS=true and '
                      'ALERT_FORMSPREE_ENDPOINT in Render')
            _record_result(name, False, detail)
            return {'name': name, 'passed': False, 'detail': detail,
                    'can_alert_by_email': False}

        alert_id = mgr.create_alert(
            category=AlertCategory.SYSTEM,
            title='[CANARY] alert delivery self-test',
            summary='Automated canary verifying end-to-end Formspree email delivery.',
            priority=AlertPriority.HIGH,
            details='If you received this email, alert delivery is healthy.',
            send_email=True,
        )

        alert = mgr.get_alert(alert_id) if alert_id else None
        emailed_at = alert.get('emailed_at') if alert else None
        passed = emailed_at is not None

        if passed:
            detail = f'alert {alert_id} delivered (emailed_at={emailed_at})'
        elif not alert_id:
            detail = 'create_alert returned no id — alert row was not created'
        else:
            detail = (f'alert {alert_id} created but emailed_at is null — '
                      f'Formspree send failed (check Render log for the exact error)')

        _record_result(name, passed, detail)
        return {'name': name, 'passed': passed, 'detail': detail,
                'can_alert_by_email': False}

    except Exception as e:
        detail = f'canary raised an exception: {e}'
        _record_result(name, False, detail)
        return {'name': name, 'passed': False, 'detail': detail,
                'can_alert_by_email': False}


# ============================================================================
# RUNNER + READBACK
# ============================================================================

# Registry of canaries to run. Phase 2 appends the briefing and eval canaries.
_CANARIES = [
    _canary_alert_delivery,
]


def run_all_canaries():
    """
    Run every registered canary, persist each result, and email any failures
    that are safe to email.

    Notification rule: a failing canary triggers an email alert ONLY if its
    result has can_alert_by_email=True. The alert-delivery canary sets that
    False — you can't use the broken channel to report its own breakage — so
    such failures are recorded and surfaced via /api/canaries/status instead.

    Returns a summary dict: {checked_at, total, passed, failed, results}.
    Never raises into the caller (safe to call from a scheduler job).
    """
    results = []
    for fn in _CANARIES:
        try:
            results.append(fn())
        except Exception as e:
            nm = getattr(fn, '__name__', 'unknown_canary')
            detail = f'runner caught exception: {e}'
            _record_result(nm, False, detail)
            results.append({'name': nm, 'passed': False, 'detail': detail,
                            'can_alert_by_email': False})

    failures = [r for r in results if not r.get('passed')]
    emailable = [r for r in failures if r.get('can_alert_by_email')]

    if emailable:
        try:
            from alert_system import get_alert_manager, AlertCategory, AlertPriority
            mgr = get_alert_manager()
            body = "\n".join(f"- {r['name']}: {r['detail']}" for r in emailable)
            mgr.create_alert(
                category=AlertCategory.SYSTEM,
                title=f"Swarm canary failure ({len(emailable)})",
                summary="One or more swarm self-test canaries failed.",
                priority=AlertPriority.HIGH,
                details=body,
                send_email=True,
            )
        except Exception as e:
            logger.error(f"[Canaries] failed to send failure alert: {e}")

    summary = {
        'checked_at': datetime.now().isoformat(),
        'total':  len(results),
        'passed': len([r for r in results if r.get('passed')]),
        'failed': len(failures),
        'results': results,
    }

    if failures:
        print(f"[Canaries] {summary['failed']}/{summary['total']} FAILED: "
              f"{[r['name'] for r in failures]}")
    else:
        print(f"[Canaries] all {summary['total']} canary check(s) passed")

    return summary


def get_latest_canary_results(limit=20):
    """
    Return the most recent canary_results rows, newest first, as a list of
    plain dicts with ISO-formatted checked_at. Safe if the table is empty.
    """
    _ensure_canary_tables()
    db = get_db()
    try:
        rows = db.execute(
            'SELECT id, canary_name, passed, detail, checked_at '
            'FROM canary_results '
            'ORDER BY checked_at DESC, id DESC '
            'LIMIT %s',
            (limit,)
        ).fetchall()
    finally:
        db.close()

    out = []
    for row in (rows or []):
        r = dict(row)
        ca = r.get('checked_at')
        if ca is not None and hasattr(ca, 'isoformat'):
            r['checked_at'] = ca.isoformat()
        elif ca is not None:
            r['checked_at'] = str(ca)
        out.append(r)
    return out


def get_canary_health():
    """
    Compact at-a-glance health derived from the latest result per canary.
    Returns {'healthy': bool, 'canaries': {name: {passed, detail, checked_at}}}.
    Used by the proactive status endpoint.
    """
    latest = get_latest_canary_results(limit=50)
    by_name = {}
    for r in latest:
        # latest is newest-first, so the first occurrence of a name is current
        if r['canary_name'] not in by_name:
            by_name[r['canary_name']] = {
                'passed':     r['passed'],
                'detail':     r['detail'],
                'checked_at': r['checked_at'],
            }
    healthy = all(v['passed'] for v in by_name.values()) if by_name else None
    return {'healthy': healthy, 'canaries': by_name}


# I did no harm and this file is not truncated
