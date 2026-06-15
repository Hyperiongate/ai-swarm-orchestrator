"""
AI SWARM ORCHESTRATOR - Proactive Agent API Routes
File: routes/proactive.py
Created: March 12, 2026
Last Updated: June 14, 2026 — WO-13 Phase 3: /api/canaries/run runs full routine

PURPOSE:
    Flask blueprint exposing all Proactive Agent endpoints.
    Covers briefings, tasks, leads (stub), monitor (stub), and self-test
    canaries. Leads and monitor stubs return 503 with a clear message until
    those modules are deployed in Deliverables 3 and 4.

ENDPOINTS:
    GET  /api/briefing                — latest briefing (generates on-demand if none today)
    GET  /api/briefing/generate       — force-regenerate today's briefing
    GET  /api/briefing/history        — past N days (?days=7)

    GET  /api/tasks                   — all pending tasks (sorted by priority)
    POST /api/tasks                   — create a task manually
    PUT  /api/tasks/<id>              — update a task
    PUT  /api/tasks/<id>/complete     — mark a task completed
    PUT  /api/tasks/<id>/defer        — defer a task

    GET  /api/leads                   — new/unreviewed leads (stub until Deliverable 3)
    PUT  /api/leads/<id>/review       — review/dismiss a lead (stub)

    GET  /api/monitor/services        — monitored services health (stub until Deliverable 4)
    POST /api/monitor/services        — register a service to monitor (stub)

    POST /api/canaries/run            — run all self-test canaries now (WO-13)
    GET  /api/canaries/status         — latest canary results (WO-13)

    GET  /api/proactive/status        — overall proactive system status

CHANGELOG:
- June 14, 2026: WO-13 PHASE 3 — /api/canaries/run RUNS FULL DAILY ROUTINE
  * POST /api/canaries/run now calls run_daily_self_tests() (canaries +
    anomaly checks) instead of run_all_canaries(), so the on-demand endpoint
    exercises exactly what the scheduler's daily JOB 6 runs. Response gains an
    'anomalies' block alongside the existing 'summary'; status is 200 only when
    every canary passed AND no anomaly fired, else 207. Backward compatible —
    the 'summary' key is unchanged. No other endpoint touched.
- June 14, 2026: WO-13 PHASE 1 — SELF-TEST CANARY ENDPOINTS
  * Added two endpoints on this (already-registered) blueprint, so no change
    to app.py was required:
      - POST /api/canaries/run     -> proactive.canaries.run_all_canaries()
      - GET  /api/canaries/status  -> proactive.canaries.get_latest_canary_results()
    Both import proactive.canaries lazily inside the handler (matching the
    import-in-body pattern used for every other module here); if the module
    is somehow unavailable the endpoints return a clean 503 rather than 500.
  * /api/proactive/status now includes a 'canaries' block (latest pass/fail
    per canary) via get_canary_health(), so the status readout you already
    poll shows self-test health at a glance. This block is purely additive
    and wrapped in its own try/except — every existing block in the status
    response is byte-for-byte unchanged. Rule 1 (do no harm) preserved.
- June 13, 2026: WO-10 FOLLOW-ON — REAL SCHEDULER STATUS
  * /api/proactive/status previously returned a HARDCODED placeholder for the
    'scheduler' block:
        {'status': 'not_yet_deployed',
         'detail': 'Scheduler will be active after Phase 6 Deliverable 5'}
    That text predates the scheduler, which was actually built and deployed in
    WO-4 (Phase 6 Deliverable 5). Because the endpoint never called the real
    status function, the Briefing panel's indicator read a frozen value and
    always showed a red "Scheduler not running" dot regardless of the true
    state.
  * Fix: the 'scheduler' block now calls get_scheduler_status() from
    proactive/scheduler.py, using the same try/except-on-import pattern used
    for every other module in this file. A 'job_count' field is derived from
    the returned 'jobs' list to match exactly what the frontend indicator
    reads (data.scheduler.running + data.scheduler.job_count), so the dot now
    reflects reality: green with the live job count when the scheduler is
    running, red with accurate enabled/running flags when it is not.
  * No other endpoint changed. All briefing / task / lead / monitor routes are
    byte-for-byte the same as the March 12 version.
- March 12, 2026: Phase 6 Deliverable 2 — Initial implementation
  * All briefing endpoints fully functional
  * All task endpoints fully functional
  * Leads and monitor endpoints are documented stubs — return 503 until
    their backing modules are deployed
  * /api/proactive/status shows which modules are live vs. pending
  * Blueprint registered in app.py (see app.py changelog for that change)

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

proactive_bp = Blueprint('proactive', __name__)


# ============================================================================
# HELPER — safe module import with clear error message
# ============================================================================

def _module_not_ready(module_name: str, deliverable: str):
    """Return a standard 503 response for modules not yet deployed."""
    return jsonify({
        'success': False,
        'error': f'{module_name} not yet deployed',
        'detail': f'This endpoint will be active after Phase 6 {deliverable} is deployed.',
    }), 503


# ============================================================================
# BRIEFING ENDPOINTS
# ============================================================================

@proactive_bp.route('/api/briefing', methods=['GET'])
def get_briefing():
    """
    GET /api/briefing

    Returns the latest daily briefing.
    If no briefing exists for today, generates one on-demand before returning.
    This is the primary endpoint called by the frontend on page load.
    """
    try:
        from proactive.daily_briefing import (
            get_briefing_for_date,
            generate_daily_briefing,
        )
        from datetime import date

        today_iso = date.today().isoformat()

        # Check if today's briefing already exists
        briefing = get_briefing_for_date(today_iso)

        if not briefing:
            # Generate on-demand — first load of the day
            logger.info("No briefing for today — generating on-demand")
            result = generate_daily_briefing()
            if result.get('success') or result.get('content'):
                briefing = {
                    'briefing_id':   result.get('briefing_id'),
                    'briefing_date': result.get('briefing_date'),
                    'content':       result.get('content'),
                    'data_summary':  result.get('data_summary', {}),
                    'generated_at':  result.get('generated_at'),
                }
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to generate briefing',
                    'detail': result.get('error', 'Unknown error'),
                }), 500

        return jsonify({
            'success': True,
            'briefing': briefing,
        })

    except Exception as e:
        logger.error(f"GET /api/briefing failed: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


@proactive_bp.route('/api/briefing/generate', methods=['GET'])
def force_generate_briefing():
    """
    GET /api/briefing/generate

    Force-regenerate today's briefing, overwriting any existing one.
    Use this when Jim wants a fresh briefing after adding tasks or leads.
    """
    try:
        from proactive.daily_briefing import generate_daily_briefing

        result = generate_daily_briefing()

        status_code = 200 if result.get('success') else 207
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"GET /api/briefing/generate failed: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


@proactive_bp.route('/api/briefing/history', methods=['GET'])
def briefing_history():
    """
    GET /api/briefing/history?days=7

    Returns briefings from the past N days (default 7, max 90).
    """
    try:
        days = int(request.args.get('days', 7))
    except (ValueError, TypeError):
        days = 7

    try:
        from proactive.daily_briefing import get_briefing_history

        briefings = get_briefing_history(days=days)
        return jsonify({
            'success':  True,
            'days':     days,
            'count':    len(briefings),
            'briefings': briefings,
        })

    except Exception as e:
        logger.error(f"GET /api/briefing/history failed: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


# ============================================================================
# TASK ENDPOINTS
# ============================================================================

@proactive_bp.route('/api/tasks', methods=['GET'])
def get_tasks():
    """
    GET /api/tasks

    Returns pending and in-progress tasks, sorted by priority.
    Optional query params: ?category=client_work  ?priority=high  ?limit=50
    """
    try:
        from proactive.task_manager import get_pending_tasks

        limit    = int(request.args.get('limit', 50))
        category = request.args.get('category')
        priority = request.args.get('priority')

        tasks = get_pending_tasks(limit=limit, category=category, priority=priority)

        return jsonify({
            'success': True,
            'count':   len(tasks),
            'tasks':   tasks,
        })

    except Exception as e:
        logger.error(f"GET /api/tasks failed: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


@proactive_bp.route('/api/tasks', methods=['POST'])
def create_task():
    """
    POST /api/tasks

    Create a task manually.
    Body (JSON):
        title        (str, required)
        description  (str, optional)
        priority     (str, optional) — critical|high|medium|low
        category     (str, optional) — client_work|lead_generation|app_maintenance|
                                        marketing|learning|admin
        project_name (str, optional)
        due_date     (str, optional) — ISO date 'YYYY-MM-DD'
    """
    try:
        from proactive.task_manager import add_task

        data = request.get_json(force=True, silent=True) or {}

        title = data.get('title', '').strip()
        if not title:
            return jsonify({
                'success': False,
                'error': 'title is required',
            }), 400

        task_id = add_task(
            title        = title,
            description  = data.get('description'),
            priority     = data.get('priority', 'medium'),
            category     = data.get('category', 'admin'),
            source       = 'user',
            due_date     = data.get('due_date'),
            project_name = data.get('project_name'),
        )

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f"Task #{task_id} created: {title}",
        }), 201

    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"POST /api/tasks failed: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


@proactive_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id: int):
    """
    PUT /api/tasks/<id>

    Update one or more fields on a task.
    Body (JSON): any combination of title, description, priority, status,
                 category, due_date, project_name, notes
    """
    try:
        from proactive.task_manager import update_task as _update_task

        data = request.get_json(force=True, silent=True) or {}

        if not data:
            return jsonify({'success': False, 'error': 'Request body is empty'}), 400

        updated = _update_task(task_id, **data)

        if updated:
            return jsonify({'success': True, 'task_id': task_id, 'updated': True})
        else:
            return jsonify({
                'success': False,
                'error': f'Task {task_id} not found or nothing changed',
            }), 404

    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"PUT /api/tasks/{task_id} failed: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


@proactive_bp.route('/api/tasks/<int:task_id>/complete', methods=['PUT'])
def complete_task(task_id: int):
    """
    PUT /api/tasks/<id>/complete

    Mark a task as completed.
    Body (JSON, optional): { "notes": "Done — sent to client" }
    """
    try:
        from proactive.task_manager import complete_task as _complete_task

        data  = request.get_json(force=True, silent=True) or {}
        notes = data.get('notes')

        updated = _complete_task(task_id, notes=notes)

        if updated:
            return jsonify({
                'success': True,
                'task_id': task_id,
                'status':  'completed',
            })
        else:
            return jsonify({
                'success': False,
                'error':   f'Task {task_id} not found or already completed',
            }), 404

    except Exception as e:
        logger.error(f"PUT /api/tasks/{task_id}/complete failed: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


@proactive_bp.route('/api/tasks/<int:task_id>/defer', methods=['PUT'])
def defer_task(task_id: int):
    """
    PUT /api/tasks/<id>/defer

    Defer a task with an optional new due date and reason.
    Body (JSON, optional):
        { "new_due_date": "2026-03-20", "reason": "Waiting on client data" }
    """
    try:
        from proactive.task_manager import defer_task as _defer_task

        data         = request.get_json(force=True, silent=True) or {}
        new_due_date = data.get('new_due_date')
        reason       = data.get('reason')

        updated = _defer_task(task_id, new_due_date=new_due_date, reason=reason)

        if updated:
            return jsonify({
                'success':      True,
                'task_id':      task_id,
                'status':       'deferred',
                'new_due_date': new_due_date,
            })
        else:
            return jsonify({
                'success': False,
                'error':   f'Task {task_id} not found or already completed',
            }), 404

    except Exception as e:
        logger.error(f"PUT /api/tasks/{task_id}/defer failed: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


# ============================================================================
# LEAD ENDPOINTS (stubs until Deliverable 3: proactive/lead_scanner.py)
# ============================================================================

@proactive_bp.route('/api/leads', methods=['GET'])
def get_leads():
    """
    GET /api/leads
    Returns new/unreviewed leads.
    """
    try:
        from proactive.lead_scanner import get_new_leads
        limit = int(request.args.get('limit', 10))
        leads = get_new_leads(limit=limit)
        return jsonify({'success': True, 'count': len(leads), 'leads': leads})
    except ImportError:
        return _module_not_ready('Lead Scanner', 'Deliverable 3')
    except Exception as e:
        logger.error(f"GET /api/leads failed: {e}")
        import traceback
        return jsonify({
            'success': False, 'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


@proactive_bp.route('/api/leads/<int:lead_id>/review', methods=['PUT'])
def review_lead(lead_id: int):
    """
    PUT /api/leads/<id>/review
    Mark a lead as reviewed, contacted, or dismissed.
    Body: { "status": "reviewed" | "contacted" | "dismissed" }
    """
    try:
        from proactive.lead_scanner import update_lead_status
        data   = request.get_json(force=True, silent=True) or {}
        status = data.get('status', 'reviewed')
        updated = update_lead_status(lead_id, status)
        if updated:
            return jsonify({'success': True, 'lead_id': lead_id, 'status': status})
        return jsonify({'success': False, 'error': f'Lead {lead_id} not found'}), 404
    except ImportError:
        return _module_not_ready('Lead Scanner', 'Deliverable 3')
    except Exception as e:
        logger.error(f"PUT /api/leads/{lead_id}/review failed: {e}")
        import traceback
        return jsonify({
            'success': False, 'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


# ============================================================================
# MONITOR ENDPOINTS (stubs until Deliverable 4: proactive/app_monitor.py)
# ============================================================================

@proactive_bp.route('/api/monitor/services', methods=['GET'])
def get_monitored_services():
    """
    GET /api/monitor/services
    Returns all monitored services with latest health status.
    """
    try:
        from proactive.app_monitor import get_health_summary
        summary = get_health_summary()
        return jsonify({'success': True, 'health_summary': summary})
    except ImportError:
        return _module_not_ready('App Monitor', 'Deliverable 4')
    except Exception as e:
        logger.error(f"GET /api/monitor/services failed: {e}")
        import traceback
        return jsonify({
            'success': False, 'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


@proactive_bp.route('/api/monitor/services', methods=['POST'])
def register_monitored_service():
    """
    POST /api/monitor/services
    Register a new service to monitor.
    Body: { "service_name": "...", "endpoint_url": "...", "check_interval_minutes": 60 }
    """
    try:
        from proactive.app_monitor import register_service
        data = request.get_json(force=True, silent=True) or {}
        service_name = data.get('service_name', '').strip()
        endpoint_url = data.get('endpoint_url', '').strip()
        interval     = int(data.get('check_interval_minutes', 60))

        if not service_name or not endpoint_url:
            return jsonify({
                'success': False,
                'error': 'service_name and endpoint_url are required',
            }), 400

        service_id = register_service(service_name, endpoint_url, interval)
        return jsonify({
            'success': True,
            'service_id': service_id,
            'service_name': service_name,
        }), 201
    except ImportError:
        return _module_not_ready('App Monitor', 'Deliverable 4')
    except Exception as e:
        logger.error(f"POST /api/monitor/services failed: {e}")
        import traceback
        return jsonify({
            'success': False, 'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


# ============================================================================
# CANARY ENDPOINTS (WO-13 Phase 1: proactive/canaries.py)
# ============================================================================

@proactive_bp.route('/api/canaries/run', methods=['POST'])
def run_canaries():
    """
    POST /api/canaries/run

    Run the full daily self-monitoring routine now and return the summary:
    every canary (each a SEMANTIC check — did the thing actually happen) plus
    every anomaly check (metric-trend analysis). This is exactly what the
    scheduler's daily JOB 6 runs, so an on-demand call exercises the same work.

    NOTE: the alert-delivery canary creates a real test alert and (if delivery
    is healthy) sends one '[CANARY]' email each time this runs. That IS the
    test. Detected anomalies also email a consolidated alert.
    """
    try:
        from proactive.canaries import run_daily_self_tests
        result = run_daily_self_tests()
        summary   = result.get('canaries', {})
        anomalies = result.get('anomalies', {})
        # 200 only if every canary passed AND no anomaly was detected
        clean = summary.get('failed', 0) == 0 and anomalies.get('count', 0) == 0
        status_code = 200 if clean else 207
        return jsonify({
            'success': True,
            'summary': summary,
            'anomalies': anomalies,
        }), status_code
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Canary module not available',
            'detail': 'proactive/canaries.py is not deployed.',
        }), 503
    except Exception as e:
        logger.error(f"POST /api/canaries/run failed: {e}")
        import traceback
        return jsonify({
            'success': False, 'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


@proactive_bp.route('/api/canaries/status', methods=['GET'])
def canaries_status():
    """
    GET /api/canaries/status?limit=20

    Returns the most recent canary results (newest first). This is the
    non-email surface for canary outcomes — in particular it is how the
    alert-delivery canary's own failures are seen, since that canary cannot
    report itself by email.
    """
    try:
        limit = int(request.args.get('limit', 20))
    except (ValueError, TypeError):
        limit = 20

    try:
        from proactive.canaries import get_latest_canary_results, get_canary_health
        results = get_latest_canary_results(limit=limit)
        health  = get_canary_health()
        return jsonify({
            'success': True,
            'healthy': health.get('healthy'),
            'canaries': health.get('canaries', {}),
            'recent':  results,
        })
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'Canary module not available',
            'detail': 'proactive/canaries.py is not deployed.',
        }), 503
    except Exception as e:
        logger.error(f"GET /api/canaries/status failed: {e}")
        import traceback
        return jsonify({
            'success': False, 'error': str(e),
            'traceback': traceback.format_exc(),
        }), 500


# ============================================================================
# PROACTIVE STATUS ENDPOINT
# ============================================================================

@proactive_bp.route('/api/proactive/status', methods=['GET'])
def proactive_status():
    """
    GET /api/proactive/status

    Returns the status of all proactive system components, including the live
    scheduler state (WO-10 follow-on) and self-test canary health (WO-13).
    """
    status = {
        'success': True,
        'modules': {},
    }

    # Task Manager
    try:
        from proactive.task_manager import get_task_summary
        summary = get_task_summary()
        status['modules']['task_manager'] = {
            'status': 'active',
            'total_pending_tasks': summary.get('total_pending', 0),
        }
    except Exception as e:
        status['modules']['task_manager'] = {'status': 'error', 'error': str(e)}

    # Daily Briefing
    try:
        from proactive.daily_briefing import get_latest_briefing
        latest = get_latest_briefing()
        status['modules']['daily_briefing'] = {
            'status': 'active',
            'latest_briefing_date': latest['briefing_date'] if latest else None,
        }
    except Exception as e:
        status['modules']['daily_briefing'] = {'status': 'error', 'error': str(e)}

    # Lead Scanner (Deliverable 3)
    try:
        from proactive.lead_scanner import get_lead_summary
        status['modules']['lead_scanner'] = {'status': 'active'}
    except ImportError:
        status['modules']['lead_scanner'] = {
            'status': 'pending',
            'detail': 'Deploys with Phase 6 Deliverable 3',
        }
    except Exception as e:
        status['modules']['lead_scanner'] = {'status': 'error', 'error': str(e)}

    # App Monitor (Deliverable 4)
    try:
        from proactive.app_monitor import get_health_summary
        status['modules']['app_monitor'] = {'status': 'active'}
    except ImportError:
        status['modules']['app_monitor'] = {
            'status': 'pending',
            'detail': 'Deploys with Phase 6 Deliverable 4',
        }
    except Exception as e:
        status['modules']['app_monitor'] = {'status': 'error', 'error': str(e)}

    # Scheduler (WO-10 follow-on) — live status from proactive/scheduler.py.
    # The frontend indicator reads scheduler.running and scheduler.job_count;
    # get_scheduler_status() returns a 'jobs' list, so job_count is derived
    # from it here to satisfy that contract. The whole status dict (enabled,
    # running, jobs, and any message) is passed through so the readout is
    # honest whether the scheduler is running, disabled, or uninitialized.
    try:
        from proactive.scheduler import get_scheduler_status
        sched_status = get_scheduler_status()
        if isinstance(sched_status, dict):
            sched_status['job_count'] = len(sched_status.get('jobs', []))
        status['scheduler'] = sched_status
    except ImportError:
        status['scheduler'] = {
            'enabled': False,
            'running': False,
            'job_count': 0,
            'detail': 'proactive/scheduler.py not found',
        }
    except Exception as e:
        status['scheduler'] = {
            'enabled': False,
            'running': False,
            'job_count': 0,
            'error': str(e),
        }

    # Canaries (WO-13 Phase 1) — latest pass/fail per self-test canary.
    # Purely additive: wrapped in its own try/except so a canary-module issue
    # can never affect the rest of this status response. 'healthy' is True if
    # every canary's most recent result passed, False if any failed, and None
    # if no canary has ever run yet.
    try:
        from proactive.canaries import get_canary_health
        status['canaries'] = get_canary_health()
    except ImportError:
        status['canaries'] = {
            'healthy': None,
            'canaries': {},
            'detail': 'proactive/canaries.py not found',
        }
    except Exception as e:
        status['canaries'] = {
            'healthy': None,
            'canaries': {},
            'error': str(e),
        }

    return jsonify(status)


# I did no harm and this file is not truncated
