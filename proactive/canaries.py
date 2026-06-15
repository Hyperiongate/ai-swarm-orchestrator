"""
AI SWARM ORCHESTRATOR - Self-Test Canaries
File: proactive/canaries.py
Created: June 14, 2026
Last Updated: June 14, 2026 — WO-13 Phase 3: anomaly detection + daily routine

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

    Phase 3 adds anomaly detection (passive metric-trend analysis) and the
    combined daily routine the scheduler runs.

DESIGN — why a canary can't always email its own failure:
    The alert-delivery canary tests the EMAIL channel itself. If that channel
    is broken, emailing the failure would fail too. So each canary declares
    can_alert_by_email. Failures are ALWAYS recorded to the canary_results
    table and exposed via /api/canaries/status; only canaries whose
    can_alert_by_email is True additionally raise an email alert (by which
    point delivery has been independently verified).

CHANGELOG:
- June 14, 2026: WO-13 PHASE 3 — ANOMALY DETECTION + DAILY ROUTINE
  * Added passive anomaly checks (trend analysis on already-stored data):
      - _anomaly_eval_score_slide(): latest active eval health score >= 15
        points below its trailing average (needs >= 3 active evals).
      - _anomaly_eval_stale(): no evaluation stored in > 8 days (the weekly
        eval job may have stopped). The eval canary does NOT save eval rows,
        so this signal is not masked by canary activity.
      - _anomaly_briefing_collapse(): latest briefing content far below its
        trailing average (needs >= 3 briefings) — data sources failing.
    Each check is isolated and no-ops quietly until enough history exists, so
    none false-fire on a fresh system.
  * run_anomaly_checks(): runs all checks and emails ONE consolidated alert if
    any fire (anomalies don't involve the email channel, so emailing directly
    is safe). Once-daily cadence => at most one reminder per day per anomaly.
  * run_daily_self_tests(): canaries + anomalies in one call — what the
    scheduler's JOB 6 and POST /api/canaries/run both invoke, so on-demand and
    scheduled runs do exactly the same work.
  * Purely additive; no existing canary or function changed. Rule 1 preserved.
- June 14, 2026: WO-13 PHASE 2 — BRIEFING + EVALUATION CANARIES
  * _canary_briefing_generation(): calls generate_daily_briefing() and passes
    only if it stored a row (success=True) AND produced non-empty content.
    A Sonnet outage that falls back to plain text still passes (graceful
    degradation is by design); an exception, storage failure, or empty content
    fails. can_alert_by_email=True. Cost: one Sonnet call + an idempotent
    overwrite of today's briefing per run.
  * _canary_eval_metrics(): runs PerformanceCollector.collect_weekly_metrics()
    (the migrated PostgreSQL reads that WO-8 repaired) and scores them with
    SwarmReportGenerator, passing if the health score lands in 0–100. It
    deliberately skips MarketScanner.scan_ai_landscape() so the canary makes
    NO Sonnet/Tavily calls. An idle (zero-task) period is a valid pass.
    can_alert_by_email=True.
  * Both registered in _CANARIES after the alert-delivery canary. No existing
    canary or behaviour changed; daily_briefing.py and swarm_self_evaluation.py
    are only called, never modified. Rule 1 (do no harm) preserved.
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


def _canary_briefing_generation():
    """
    Daily briefing generation.

    Actively calls generate_daily_briefing() and verifies it both stored a row
    (result['success']) and produced real content. generate_daily_briefing()
    degrades gracefully — if Sonnet is unavailable it returns a plain-text
    fallback, which is by design and still counts as healthy — so this canary
    treats only an exception, success=False (storage failed), or empty content
    as a failure. Storage failure is exactly the WO-8-class silent break this
    is meant to catch.

    can_alert_by_email=True — a briefing failure does not involve the email
    channel, so it is safe to report by email.

    Cost note: each run makes one Sonnet call and overwrites today's briefing
    (idempotent UPSERT on briefing_date). Phase 3 schedules this once daily,
    shortly after the morning briefing job, so it doubles as verification that
    the morning generation worked.
    """
    name = 'briefing_generation'
    try:
        from proactive.daily_briefing import generate_daily_briefing
        result = generate_daily_briefing() or {}
        content = (result.get('content') or '').strip()
        stored = bool(result.get('success'))
        passed = stored and len(content) >= 50

        if passed:
            detail = (f"briefing {result.get('briefing_date', 'today')} generated "
                      f"and stored ({len(content)} chars)")
        elif not stored:
            detail = (f"briefing generated but storage failed: "
                      f"{result.get('error', 'unknown error')}")
        else:
            detail = f"briefing stored but content too short ({len(content)} chars)"

        _record_result(name, passed, detail)
        return {'name': name, 'passed': passed, 'detail': detail,
                'can_alert_by_email': True}

    except Exception as e:
        detail = f'canary raised an exception: {e}'
        _record_result(name, False, detail)
        return {'name': name, 'passed': False, 'detail': detail,
                'can_alert_by_email': True}


def _canary_eval_metrics():
    """
    Swarm evaluation — metrics collection + scoring.

    Exercises the part of the evaluation engine that actually broke before
    (WO-8): PerformanceCollector.collect_weekly_metrics() runs the migrated
    PostgreSQL reads, and SwarmReportGenerator turns those metrics into a
    health score. This deliberately SKIPS MarketScanner.scan_ai_landscape(),
    which makes Sonnet/Tavily calls and would make the canary slow and costly
    to run often. An empty market dict is passed to the report generator, which
    handles it cleanly.

    Passes when metrics collect without an internal error and scoring yields a
    health score in 0–100. An idle period (zero tasks) is a valid, healthy
    outcome — the WO-8 fix scores it as neutral, not failing — so it still
    passes.

    can_alert_by_email=True — does not involve the email channel.
    """
    name = 'eval_metrics'
    try:
        from swarm_self_evaluation import PerformanceCollector, SwarmReportGenerator
        collector = PerformanceCollector()
        metrics = collector.collect_weekly_metrics(days=7)

        # collect_weekly_metrics isolates each block; a failed block leaves an
        # {'error': ...} marker rather than raising. Treat a tasks-block error
        # (the core metric) as a canary failure.
        tasks = metrics.get('tasks', {}) if isinstance(metrics, dict) else {}
        if isinstance(tasks, dict) and 'error' in tasks:
            detail = f"metrics collection error: {tasks['error']}"
            _record_result(name, False, detail)
            return {'name': name, 'passed': False, 'detail': detail,
                    'can_alert_by_email': True}

        # Score the real metrics with an empty market scan (no API calls).
        report = SwarmReportGenerator(metrics, {}, [], []).generate_report()
        score = report.get('health_score', {}).get('overall')
        passed = isinstance(score, (int, float)) and 0 <= score <= 100

        if passed:
            detail = (f"metrics collected and scored — health {score}/100"
                      + (" (idle period)" if report.get('idle_period') else ""))
        else:
            detail = f"scoring produced an invalid health score: {score!r}"

        _record_result(name, passed, detail)
        return {'name': name, 'passed': passed, 'detail': detail,
                'can_alert_by_email': True}

    except Exception as e:
        detail = f'canary raised an exception: {e}'
        _record_result(name, False, detail)
        return {'name': name, 'passed': False, 'detail': detail,
                'can_alert_by_email': True}


# ============================================================================
# RUNNER + READBACK
# ============================================================================

# Registry of canaries to run.
_CANARIES = [
    _canary_alert_delivery,
    _canary_briefing_generation,
    _canary_eval_metrics,
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


# ============================================================================
# ANOMALY DETECTION (WO-13 Phase 3)
# Passive trend analysis on data already stored. Unlike canaries (which
# actively test that something works right now), anomaly checks look for
# worrying CHANGES over time and alert on them. Each check is isolated; one
# failing check never blocks the others. Checks no-op quietly until there is
# enough history, so they never false-fire on a fresh system.
# ============================================================================

def _as_date(value):
    """Best-effort parse of a date/timestamp value to a datetime.date, else None."""
    if value is None:
        return None
    try:
        from datetime import date as _date
        if hasattr(value, 'year') and hasattr(value, 'month'):  # date/datetime
            return value if not hasattr(value, 'date') else value.date()
        s = str(value).strip()[:10]  # 'YYYY-MM-DD' prefix of a date or timestamp
        return _date.fromisoformat(s)
    except Exception:
        return None


def _anomaly_eval_score_slide():
    """Eval health score sliding: latest active eval well below its trailing average."""
    try:
        from swarm_self_evaluation import get_swarm_evaluator
        hist = get_swarm_evaluator().get_evaluation_history(limit=6)  # newest-first
        active = [h for h in (hist or [])
                  if not h.get('idle_period') and isinstance(h.get('health_score'), (int, float))]
        if len(active) < 3:
            return None
        latest = active[0]['health_score']
        prior = [h['health_score'] for h in active[1:]]
        baseline = sum(prior) / len(prior)
        drop = baseline - latest
        if baseline > 0 and drop >= 15:
            return {
                'check': 'eval_score_slide',
                'detail': (f"swarm health score fell to {latest:.0f}/100 vs a trailing "
                           f"average of {baseline:.0f}/100 ({drop:.0f}-point drop)"),
            }
    except Exception as e:
        logger.warning(f"[Anomaly] eval_score_slide check failed (non-fatal): {e}")
    return None


def _anomaly_eval_stale():
    """No evaluation stored in over 8 days — the weekly eval job may have stopped."""
    try:
        from datetime import date
        from swarm_self_evaluation import get_swarm_evaluator
        latest = get_swarm_evaluator().get_latest_evaluation()
        if not latest:
            return None  # no evals yet — not an anomaly (system may be new)
        d = _as_date(latest.get('evaluation_date'))
        if d is None:
            return None
        gap = (date.today() - d).days
        if gap > 8:  # weekly cadence is ~7 days; >8 means a Wednesday was missed
            return {
                'check': 'eval_stale',
                'detail': (f"no swarm evaluation in {gap} days (last: {d.isoformat()}) — "
                           f"the weekly evaluation job may have stopped firing"),
            }
    except Exception as e:
        logger.warning(f"[Anomaly] eval_stale check failed (non-fatal): {e}")
    return None


def _anomaly_briefing_collapse():
    """Briefing content collapsing: latest briefing far smaller than its trailing average."""
    try:
        from proactive.daily_briefing import get_briefing_history
        briefs = get_briefing_history(days=14)  # newest-first
        sizes = [len((b.get('content') or '')) for b in (briefs or [])]
        if len(sizes) < 3:
            return None
        latest = sizes[0]
        prior = sizes[1:]
        baseline = sum(prior) / len(prior)
        floor = max(50, 0.4 * baseline)
        if baseline > 0 and latest < floor:
            return {
                'check': 'briefing_collapse',
                'detail': (f"latest briefing is {latest} chars vs a trailing average of "
                           f"{baseline:.0f} — content has collapsed (data sources may be failing)"),
            }
    except Exception as e:
        logger.warning(f"[Anomaly] briefing_collapse check failed (non-fatal): {e}")
    return None


_ANOMALY_CHECKS = [
    _anomaly_eval_score_slide,
    _anomaly_eval_stale,
    _anomaly_briefing_collapse,
]


def run_anomaly_checks():
    """
    Run every anomaly check and, if any fired, email a single consolidated
    alert (anomalies don't involve the email channel, so they're safe to
    email directly). Returns {checked_at, count, anomalies}.

    Cadence note: this runs once daily via the scheduler, so a persistent
    anomaly produces at most one alert per day — a daily reminder, not a flood.
    If persistent-anomaly fatigue ever becomes an issue, add signature-based
    dedup here. Never raises into the caller.
    """
    anomalies = []
    for check in _ANOMALY_CHECKS:
        try:
            hit = check()
            if hit:
                anomalies.append(hit)
        except Exception as e:
            logger.warning(f"[Anomaly] a check raised (non-fatal): {e}")

    if anomalies:
        try:
            from alert_system import get_alert_manager, AlertCategory, AlertPriority
            body = "\n".join(f"- {a['check']}: {a['detail']}" for a in anomalies)
            get_alert_manager().create_alert(
                category=AlertCategory.SYSTEM,
                title=f"Swarm anomaly detected ({len(anomalies)})",
                summary="Self-monitoring detected a worrying trend in stored metrics.",
                priority=AlertPriority.HIGH,
                details=body,
                send_email=True,
            )
        except Exception as e:
            logger.error(f"[Anomaly] failed to send anomaly alert: {e}")

    if anomalies:
        print(f"[Anomaly] {len(anomalies)} detected: {[a['check'] for a in anomalies]}")
    else:
        print("[Anomaly] no anomalies detected")

    return {
        'checked_at': datetime.now().isoformat(),
        'count': len(anomalies),
        'anomalies': anomalies,
    }


def run_daily_self_tests():
    """
    The full daily self-monitoring routine: run every canary, then every
    anomaly check. This is what the scheduler's JOB 6 calls, and what the
    POST /api/canaries/run endpoint runs, so an on-demand test exercises
    exactly what the scheduled run does. Returns both summaries.
    """
    canary_summary = run_all_canaries()
    anomaly_summary = run_anomaly_checks()
    return {'canaries': canary_summary, 'anomalies': anomaly_summary}


# I did no harm and this file is not truncated
