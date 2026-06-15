"""
AI SWARM ORCHESTRATOR - Proactive Scheduler
File: proactive/scheduler.py
Created: June 01, 2026
Last Updated: June 14, 2026 — WO-13 Phase 3: Daily Canary Suite Job (now 6 jobs)

CHANGELOG:
- June 14, 2026: WO-13 PHASE 3 — ADD DAILY CANARY SUITE JOB (now 6 jobs)
  * Added JOB 6: canary_suite_daily — runs EVERY day at 6:45 AM Pacific,
    calling run_daily_self_tests() from proactive/canaries.py (all canaries +
    all anomaly checks).
  * Why 6:45 AM Pacific: 15 minutes after the morning briefing job (JOB 5 at
    6:30), so the briefing canary doubles as verification that the morning
    generation actually worked. Uses America/Los_Angeles for the same
    stable-local-time / automatic-DST reason as JOB 5.
  * Pattern preserved: JOB 6 follows the established pattern exactly — a
    standalone no-argument function (_job_canary_suite), import performed
    inside the function body, and a full try/except so a canary failure never
    affects the other jobs or the running app. Same job_defaults apply.
  * Still gated on ENABLE_SCHEDULED_JOBS=true. NO existing job was changed —
    the five prior jobs are byte-for-byte the same. Rule 1 (do no harm)
    preserved.

- June 13, 2026: WO-10 — ADD DAILY BRIEFING JOB (now 5 jobs)
  * Added JOB 5: daily_briefing_morning — runs EVERY day at 6:30 AM Pacific,
    calling generate_daily_briefing() from proactive/daily_briefing.py.
  * Why: that generator was always designed to be driven by this scheduler —
    its own docstring names "proactive/scheduler.py at 6:30 AM Pacific
    (automatic)" as a caller — but the job was never registered when this
    file was first created in WO-4. As a result the briefing only ever
    generated on-demand when the Briefing panel was opened. This wires the
    intended automatic morning run so the briefing is pre-built each day.
  * Timezone: this single job uses America/Los_Angeles (NOT UTC like the
    other four), by deliberate choice — a morning briefing should land at a
    stable 6:30 AM LOCAL time year-round, so APScheduler/pytz handles the
    PDT<->PST daylight-saving shift automatically. pytz resolves the string
    'America/Los_Angeles' exactly as it already resolves 'UTC' for the other
    jobs (string timezones are supported and already in use here).
  * Idempotent: generate_daily_briefing() UPSERTs on briefing_date, so a
    daily run cleanly overwrites that day's briefing — running it every
    morning is safe.
  * Pattern preserved: JOB 5 follows the exact established pattern — a
    standalone no-argument function, import performed inside the function
    body, and a full try/except so a briefing failure never affects the
    other jobs or the running app. Same job_defaults apply (coalesce,
    max_instances=1, misfire_grace_time=3600).
  * Still gated on ENABLE_SCHEDULED_JOBS=true. NO existing job was changed —
    the four WO-4 jobs are byte-for-byte the same. Rule 1 (do no harm)
    preserved.

- June 01, 2026: WO-4 — INITIAL IMPLEMENTATION
  * Created proactive/scheduler.py — this file previously did not exist,
    causing app.py's `from proactive.scheduler import init_scheduler` to
    fail silently with "Scheduler not found (non-fatal)" on every startup.
  * init_scheduler(app): registers APScheduler BackgroundScheduler with the
    Flask app. Reads ENABLE_SCHEDULED_JOBS env var (must be 'true' to
    activate). Defaults to disabled so no jobs run until explicitly enabled
    in Render environment variables.
  * Four jobs registered (all fire only when ENABLE_SCHEDULED_JOBS=true):
      1. swarm_evaluation_weekly   — runs every Wednesday at 08:05 AM UTC
         Calls SwarmSelfEvaluator.run_evaluation(days=7, save_to_db=True)
      2. introspection_weekly      — runs every Wednesday at 08:15 AM UTC
         Calls IntrospectionEngine.run_introspection(days=7, is_monthly=False)
      3. introspection_monthly     — runs first Wednesday of each month at 08:30 AM UTC
         Calls IntrospectionEngine.run_introspection(days=30, is_monthly=True)
      4. service_health_check      — runs every 30 minutes
         Calls check_all_services() from proactive.app_monitor
  * Evaluation and introspection jobs are staggered by 10 minutes to avoid
    simultaneous AI API calls.
  * Monthly introspection uses a day_of_week + day filter (day <= 7) to
    target the first Wednesday of each month.
  * All jobs are wrapped in try/except so a single job failure never
    crashes the scheduler or the app.
  * APScheduler is already in requirements.txt (apscheduler>=3.10).
  * ENABLE_SCHEDULED_JOBS defaults to 'false' — matches the existing
    config.py pattern. Set to 'true' in Render env vars to activate.
  * Job misfire_grace_time set to 1 hour so jobs missed during a deploy
    restart fire once when the app comes back up.

USAGE (Render environment variables to activate):
    ENABLE_SCHEDULED_JOBS=true
    ENABLE_EMAIL_ALERTS=true          (optional, for alert emails)
    ALERT_TO_EMAIL=jim@shift-work.com (required if email alerts enabled)

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

ENABLE_SCHEDULED_JOBS = os.environ.get('ENABLE_SCHEDULED_JOBS', 'false').lower() == 'true'

# Staggered UTC times on Wednesday — avoids simultaneous AI API calls
EVALUATION_DAY        = 'wed'
EVALUATION_HOUR       = 8
EVALUATION_MINUTE     = 5   # 08:05 UTC Wednesday

INTROSPECTION_HOUR    = 8
INTROSPECTION_MINUTE  = 15  # 08:15 UTC Wednesday

MONTHLY_INTRO_HOUR    = 8
MONTHLY_INTRO_MINUTE  = 30  # 08:30 UTC first Wednesday of month

HEALTH_CHECK_INTERVAL_MINUTES = 30  # every 30 minutes, matches app_monitor.py default

# WO-10: Daily morning briefing — fires in LOCAL Pacific time (not UTC) so it
# always lands at 6:30 AM regardless of daylight saving. APScheduler/pytz
# resolve this string timezone and apply the PDT/PST offset automatically.
BRIEFING_TIMEZONE = 'America/Los_Angeles'
BRIEFING_HOUR     = 6
BRIEFING_MINUTE   = 30  # 6:30 AM Pacific, every day

# WO-13 Phase 3: daily self-test canaries + anomaly detection. Fires 15 minutes
# after the morning briefing (also Pacific) so the briefing canary doubles as
# verification that the 6:30 AM generation worked. Pacific time for the same
# stable-local-time / automatic-DST reason as the briefing job.
CANARY_TIMEZONE = 'America/Los_Angeles'
CANARY_HOUR     = 6
CANARY_MINUTE   = 45  # 6:45 AM Pacific, every day


# ============================================================================
# JOB FUNCTIONS
# ============================================================================
# Each function is a standalone callable — no arguments, no shared state.
# Wrapped in try/except so a failure in one job never affects other jobs
# or the running app.

def _job_swarm_evaluation():
    """Weekly Swarm Self-Evaluation — runs every Wednesday at 08:05 UTC."""
    logger.info("[Scheduler] Starting weekly swarm self-evaluation")
    print(f"[Scheduler] {datetime.utcnow().isoformat()} — weekly swarm evaluation starting")
    try:
        from swarm_self_evaluation import get_swarm_evaluator
        evaluator = get_swarm_evaluator()
        report = evaluator.run_evaluation(days=7, save_to_db=True)
        health = report.get('health_score', {}).get('overall', 'N/A')
        print(f"[Scheduler] Swarm evaluation complete — health score: {health}/100")
        logger.info(f"[Scheduler] Swarm evaluation complete — health score: {health}/100")
    except Exception as e:
        logger.error(f"[Scheduler] Swarm evaluation failed: {e}")
        print(f"[Scheduler] Swarm evaluation failed: {e}")


def _job_introspection_weekly():
    """Weekly Introspection — runs every Wednesday at 08:15 UTC."""
    logger.info("[Scheduler] Starting weekly introspection")
    print(f"[Scheduler] {datetime.utcnow().isoformat()} — weekly introspection starting")
    try:
        from introspection import get_introspection_engine
        engine = get_introspection_engine()
        report = engine.run_introspection(days=7, is_monthly=False)
        health = report.get('summary', {}).get('health_score', 'N/A')
        print(f"[Scheduler] Weekly introspection complete — health score: {health}/100")
        logger.info(f"[Scheduler] Weekly introspection complete — health score: {health}/100")
    except Exception as e:
        logger.error(f"[Scheduler] Weekly introspection failed: {e}")
        print(f"[Scheduler] Weekly introspection failed: {e}")


def _job_introspection_monthly():
    """
    Monthly deep-dive introspection — runs on the first Wednesday of each
    month at 08:30 UTC.

    APScheduler's cron trigger fires every Wednesday with day <= 7.
    That combination always targets the first Wednesday of the month.
    """
    logger.info("[Scheduler] Starting monthly introspection deep-dive")
    print(f"[Scheduler] {datetime.utcnow().isoformat()} — monthly introspection starting")
    try:
        from introspection import get_introspection_engine
        engine = get_introspection_engine()
        report = engine.run_introspection(days=30, is_monthly=True)
        health = report.get('summary', {}).get('health_score', 'N/A')
        print(f"[Scheduler] Monthly introspection complete — health score: {health}/100")
        logger.info(f"[Scheduler] Monthly introspection complete — health score: {health}/100")
    except Exception as e:
        logger.error(f"[Scheduler] Monthly introspection failed: {e}")
        print(f"[Scheduler] Monthly introspection failed: {e}")


def _job_service_health_check():
    """Service health check — runs every 30 minutes."""
    logger.debug("[Scheduler] Running service health checks")
    try:
        from proactive.app_monitor import check_all_services
        result = check_all_services()
        total   = result.get('total_checked', 0)
        healthy = result.get('healthy_count', 0)
        issues  = result.get('issues', [])
        if issues:
            print(f"[Scheduler] Health check: {healthy}/{total} healthy, "
                  f"{len(issues)} issue(s): "
                  f"{[i['service_name'] for i in issues]}")
        else:
            logger.debug(f"[Scheduler] Health check: {healthy}/{total} healthy")
    except Exception as e:
        logger.error(f"[Scheduler] Service health check failed: {e}")
        print(f"[Scheduler] Service health check failed: {e}")


def _job_daily_briefing():
    """
    WO-10: Daily morning briefing — runs every day at 6:30 AM Pacific.

    Calls generate_daily_briefing() (proactive/daily_briefing.py), which is
    the same underlying function the on-demand GET /api/briefing path uses.
    The generator UPSERTs on briefing_date, so this daily run simply ensures
    today's briefing exists (pre-built) and overwrites it cleanly if it does.

    The import is performed inside this function (matching the other jobs) so
    that, if proactive/daily_briefing.py is ever unavailable at runtime, this
    job logs and returns without disturbing the scheduler or other jobs.
    """
    logger.info("[Scheduler] Starting daily briefing generation")
    print(f"[Scheduler] {datetime.utcnow().isoformat()} — daily briefing generation starting (6:30 AM Pacific)")
    try:
        from proactive.daily_briefing import generate_daily_briefing
        result = generate_daily_briefing()
        if isinstance(result, dict) and result.get('success'):
            print(f"[Scheduler] Daily briefing generated for {result.get('briefing_date', 'today')}")
            logger.info(f"[Scheduler] Daily briefing generated for {result.get('briefing_date', 'today')}")
        else:
            err = result.get('error') if isinstance(result, dict) else 'unknown result'
            print(f"[Scheduler] Daily briefing returned no success flag: {err}")
            logger.warning(f"[Scheduler] Daily briefing returned no success flag: {err}")
    except Exception as e:
        logger.error(f"[Scheduler] Daily briefing failed: {e}")
        print(f"[Scheduler] Daily briefing failed: {e}")


def _job_canary_suite():
    """
    WO-13 Phase 3: Daily self-test canaries + anomaly detection — runs every
    day at 6:45 AM Pacific, 15 minutes after the morning briefing job.

    Calls run_daily_self_tests() from proactive/canaries.py, which runs every
    canary (alert delivery, briefing generation, eval metrics) and then every
    anomaly check (eval score slide, eval staleness, briefing collapse). Canary
    failures and detected anomalies email Jim via the alert system; the
    alert-delivery canary's own result is recorded for /api/canaries/status,
    since that canary cannot report itself by email.

    The import is performed inside this function (matching the other jobs) so
    that, if proactive/canaries.py is ever unavailable at runtime, this job
    logs and returns without disturbing the scheduler or other jobs.
    """
    logger.info("[Scheduler] Starting daily self-test canary suite")
    print(f"[Scheduler] {datetime.utcnow().isoformat()} — daily canary suite starting (6:45 AM Pacific)")
    try:
        from proactive.canaries import run_daily_self_tests
        result = run_daily_self_tests()
        c = result.get('canaries', {}) if isinstance(result, dict) else {}
        a = result.get('anomalies', {}) if isinstance(result, dict) else {}
        print(f"[Scheduler] Canary suite complete — "
              f"{c.get('passed', 0)}/{c.get('total', 0)} passed, "
              f"{a.get('count', 0)} anomaly(ies)")
        logger.info(f"[Scheduler] Canary suite: {c.get('passed', 0)}/{c.get('total', 0)} passed, "
                    f"{a.get('count', 0)} anomalies")
    except Exception as e:
        logger.error(f"[Scheduler] Canary suite failed: {e}")
        print(f"[Scheduler] Canary suite failed: {e}")


# ============================================================================
# SCHEDULER INIT
# ============================================================================

_scheduler = None  # module-level singleton — prevents duplicate schedulers


def init_scheduler(app):
    """
    Initialize and start the APScheduler BackgroundScheduler.

    Called from app.py:
        from proactive.scheduler import init_scheduler
        init_scheduler(app)

    Guards:
    - Reads ENABLE_SCHEDULED_JOBS env var. If false (default), logs the
      disabled state and returns without starting any jobs. This means
      no automated runs happen until Jim sets ENABLE_SCHEDULED_JOBS=true
      in Render environment variables.
    - Module-level _scheduler singleton prevents duplicate schedulers if
      init_scheduler is called more than once (e.g. during testing).
    - All job exceptions are caught internally — a failed job never
      crashes the scheduler thread or the Flask app.

    Job schedule:
        swarm_evaluation_weekly  — Wednesday 08:05 UTC
        introspection_weekly     — Wednesday 08:15 UTC
        introspection_monthly    — First Wednesday of month 08:30 UTC
        service_health_check     — Every 30 minutes
        daily_briefing_morning   — Every day 06:30 America/Los_Angeles (WO-10)
        canary_suite_daily       — Every day 06:45 America/Los_Angeles (WO-13)

    Args:
        app: The Flask application instance (passed for context if needed
             in future; not used directly in this version)
    """
    global _scheduler

    if _scheduler is not None:
        logger.info("[Scheduler] Already initialized — skipping duplicate init")
        return

    if not ENABLE_SCHEDULED_JOBS:
        print(
            "[Scheduler] ENABLE_SCHEDULED_JOBS is false — scheduler disabled. "
            "Set ENABLE_SCHEDULED_JOBS=true in Render environment variables to activate."
        )
        logger.info("[Scheduler] Disabled via ENABLE_SCHEDULED_JOBS=false")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler(
            job_defaults={
                'coalesce':           True,   # merge missed runs into one
                'max_instances':      1,       # never run the same job twice at once
                'misfire_grace_time': 3600,    # fire up to 1 hour late after a restart
            },
            timezone='UTC'
        )

        # ------------------------------------------------------------------
        # JOB 1: Weekly Swarm Self-Evaluation
        # Every Wednesday at 08:05 UTC
        # ------------------------------------------------------------------
        scheduler.add_job(
            func=_job_swarm_evaluation,
            trigger=CronTrigger(day_of_week=EVALUATION_DAY,
                                hour=EVALUATION_HOUR,
                                minute=EVALUATION_MINUTE,
                                timezone='UTC'),
            id='swarm_evaluation_weekly',
            name='Weekly Swarm Self-Evaluation',
            replace_existing=True,
        )

        # ------------------------------------------------------------------
        # JOB 2: Weekly Introspection
        # Every Wednesday at 08:15 UTC
        # ------------------------------------------------------------------
        scheduler.add_job(
            func=_job_introspection_weekly,
            trigger=CronTrigger(day_of_week=EVALUATION_DAY,
                                hour=INTROSPECTION_HOUR,
                                minute=INTROSPECTION_MINUTE,
                                timezone='UTC'),
            id='introspection_weekly',
            name='Weekly Introspection',
            replace_existing=True,
        )

        # ------------------------------------------------------------------
        # JOB 3: Monthly Introspection Deep-Dive
        # First Wednesday of each month at 08:30 UTC
        # day <= 7 combined with day_of_week='wed' = first Wednesday
        # ------------------------------------------------------------------
        scheduler.add_job(
            func=_job_introspection_monthly,
            trigger=CronTrigger(day_of_week=EVALUATION_DAY,
                                day='1-7',
                                hour=MONTHLY_INTRO_HOUR,
                                minute=MONTHLY_INTRO_MINUTE,
                                timezone='UTC'),
            id='introspection_monthly',
            name='Monthly Introspection Deep-Dive',
            replace_existing=True,
        )

        # ------------------------------------------------------------------
        # JOB 4: Service Health Check
        # Every 30 minutes
        # ------------------------------------------------------------------
        scheduler.add_job(
            func=_job_service_health_check,
            trigger=IntervalTrigger(minutes=HEALTH_CHECK_INTERVAL_MINUTES,
                                    timezone='UTC'),
            id='service_health_check',
            name='Service Health Check',
            replace_existing=True,
        )

        # ------------------------------------------------------------------
        # JOB 5: Daily Morning Briefing  (WO-10)
        # Every day at 06:30 America/Los_Angeles (stable 6:30 AM Pacific,
        # DST handled automatically). Pre-builds the briefing each morning;
        # generate_daily_briefing() UPSERTs on briefing_date so this is
        # idempotent. NOTE: this job intentionally uses Pacific time rather
        # than UTC — see the WO-10 changelog note at the top of this file.
        # ------------------------------------------------------------------
        scheduler.add_job(
            func=_job_daily_briefing,
            trigger=CronTrigger(hour=BRIEFING_HOUR,
                                minute=BRIEFING_MINUTE,
                                timezone=BRIEFING_TIMEZONE),
            id='daily_briefing_morning',
            name='Daily Morning Briefing',
            replace_existing=True,
        )

        # ------------------------------------------------------------------
        # JOB 6: Daily Self-Test Canaries + Anomaly Detection  (WO-13 Phase 3)
        # Every day at 06:45 America/Los_Angeles — 15 minutes after the morning
        # briefing (JOB 5) so the briefing canary doubles as proof the 6:30
        # generation worked. Uses Pacific time like JOB 5 (see config note).
        # ------------------------------------------------------------------
        scheduler.add_job(
            func=_job_canary_suite,
            trigger=CronTrigger(hour=CANARY_HOUR,
                                minute=CANARY_MINUTE,
                                timezone=CANARY_TIMEZONE),
            id='canary_suite_daily',
            name='Daily Self-Test Canaries',
            replace_existing=True,
        )

        scheduler.start()
        _scheduler = scheduler

        print(
            f"[Scheduler] Started — 6 jobs active:\n"
            f"  swarm_evaluation_weekly  : Wednesday 08:05 UTC\n"
            f"  introspection_weekly     : Wednesday 08:15 UTC\n"
            f"  introspection_monthly    : First Wednesday 08:30 UTC\n"
            f"  service_health_check     : every {HEALTH_CHECK_INTERVAL_MINUTES} minutes\n"
            f"  daily_briefing_morning   : every day 06:30 {BRIEFING_TIMEZONE}\n"
            f"  canary_suite_daily       : every day 06:45 {CANARY_TIMEZONE}"
        )
        logger.info("[Scheduler] BackgroundScheduler started with 6 jobs")

    except ImportError:
        print(
            "[Scheduler] APScheduler not installed — install apscheduler>=3.10. "
            "Scheduled jobs will not run."
        )
        logger.error("[Scheduler] APScheduler import failed")
    except Exception as e:
        logger.error(f"[Scheduler] Failed to start: {e}")
        print(f"[Scheduler] Failed to start (non-fatal): {e}")


def get_scheduler_status() -> dict:
    """
    Return the current scheduler status and registered jobs.
    Used by health checks and admin endpoints.

    Returns:
        dict with keys: enabled, running, jobs (list)
    """
    if not ENABLE_SCHEDULED_JOBS:
        return {
            'enabled': False,
            'running': False,
            'message': 'Set ENABLE_SCHEDULED_JOBS=true in Render to activate',
            'jobs': []
        }

    if _scheduler is None:
        return {
            'enabled': True,
            'running': False,
            'message': 'Scheduler not yet initialized',
            'jobs': []
        }

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            'id':       job.id,
            'name':     job.name,
            'next_run': next_run.isoformat() if next_run else None,
        })

    return {
        'enabled': True,
        'running': _scheduler.running,
        'jobs':    jobs
    }

# I did no harm and this file is not truncated
