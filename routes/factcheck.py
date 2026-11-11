"""
Speech Fact-Checker — Flask Routes
File: routes/factcheck.py
Created: November 11, 2026
Last Updated: November 11, 2026 — Initial implementation inside the Swarm

PURPOSE:
    Flask blueprint for the Live Political Speech Fact-Checker. Serves the
    listening page and a small job API. Every route here returns in
    milliseconds: it either hands a job to the queue or reads a job's result.
    The AI work itself runs in the separate helper process (factcheck_runner.py),
    so these routes can never tie up a Swarm web worker. See the architecture
    note at the top of factcheck_engine.py.

    The engine is imported lazily inside handlers (matching the Swarm's
    pattern) so a missing module degrades to a clean 503, not a failed start.

ENDPOINTS:
    GET   /factcheck                    — the listening page
    GET   /api/factcheck/health         — is the checker ready? (key, passcode, helper)
    POST  /api/factcheck/claims         — queue: find the claims in a passage
    POST  /api/factcheck/check          — queue: fast live check of one claim
    POST  /api/factcheck/deep           — queue: five-layer recheck of one claim
    POST  /api/factcheck/jobs/status    — where do these jobs stand? {ids: [...]}

    The three queue routes answer 202 with {"job_id": "..."}; the page then asks
    /jobs/status every two seconds until each job is 'done' or 'failed'.

PASSCODE:
    If the FACTCHECK_PASSCODE environment variable is set in Render, every
    /api/factcheck/* route except /health requires it in the X-App-Passcode
    header (the page asks for it once per browser session). Without it, anyone
    who finds the address can spend the Swarm's AI budget.

CHANGELOG:
- November 11, 2026: INITIAL IMPLEMENTATION
  * New blueprint factcheck_bp. Registered in app.py (see app.py changelog).
    No existing route touched. Rule 1 (do no harm) preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import hmac
import logging
import os
import re

from flask import Blueprint, jsonify, request, send_from_directory

logger = logging.getLogger(__name__)

factcheck_bp = Blueprint('factcheck', __name__)

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
_MAX_BODY_BYTES = 256 * 1024          # nothing the page sends is bigger than this
_MAX_IDS_PER_STATUS_CALL = 50
_JOB_ID = re.compile(r'^[0-9a-f]{32}$')


def _engine():
    """Import the engine lazily; raises ImportError if the module is absent."""
    import factcheck_engine
    return factcheck_engine


# ============================================================================
# PASSCODE
# ============================================================================

def _passcode_required():
    return bool(os.environ.get('FACTCHECK_PASSCODE', '').strip())


def _passcode_ok():
    expected = os.environ.get('FACTCHECK_PASSCODE', '').strip()
    if not expected:
        return True
    given = request.headers.get('X-App-Passcode', '')
    return hmac.compare_digest(given.encode('utf-8'), expected.encode('utf-8'))


# ============================================================================
# HEADERS (this blueprint's responses only)
# ============================================================================

@factcheck_bp.after_request
def _factcheck_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if request.path.startswith('/api/factcheck/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


# ============================================================================
# PAGE
# ============================================================================

@factcheck_bp.route('/factcheck', methods=['GET'])
def factcheck_page():
    """
    The listening page. Sent as a plain file, NOT through render_template: the
    page's own script is full of braces, and it needs nothing filled in by the
    server, so keeping the template engine away from it removes a whole class
    of future breakage.
    """
    response = send_from_directory(_TEMPLATES_DIR, 'factcheck.html', mimetype='text/html')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Permissions-Policy'] = 'microphone=(self)'
    return response


# ============================================================================
# HEALTH
# ============================================================================

@factcheck_bp.route('/api/factcheck/health', methods=['GET'])
def factcheck_health():
    """What the page needs to know before it starts. Never queues anything."""
    info = {
        'ok': True,
        'passcode_required': _passcode_required(),
        'passcode_ok': _passcode_ok(),
        'engine': 'missing',
        'ai_ready': False,
        'database': 'unknown',
        'helper': 'unknown',
    }
    try:
        eng = _engine()
    except ImportError:
        info['ok'] = False
        return jsonify(info)
    info['engine'] = 'ok'
    info['ai_ready'] = eng.ai_ready()
    info['models'] = {'claims': eng.CLAIM_MODEL, 'check': eng.CHECK_MODEL, 'deep': eng.DEEP_MODEL}
    try:
        info['helper'] = 'running' if eng.runner_alive() else 'idle'
        info['database'] = 'ok'
    except Exception as e:
        logger.error(f"GET /api/factcheck/health database check failed: {e}")
        info['database'] = 'error'
        info['ok'] = False
    return jsonify(info)


# ============================================================================
# QUEUE A JOB
# ============================================================================

def _queue(kind):
    """Shared handler for the three queue routes."""
    if not _passcode_ok():
        return jsonify({'error': 'Passcode needed.'}), 401
    if (request.content_length or 0) > _MAX_BODY_BYTES:
        return jsonify({'error': 'That is more text than the checker accepts in one go.'}), 413
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'The request was not understood.'}), 400
    try:
        eng = _engine()
    except ImportError:
        return _not_ready()
    if not eng.ai_ready():
        return jsonify({'error': 'The server has no AI key. Check ANTHROPIC_API_KEY in Render '
                                 'under Environment, then redeploy.'}), 503
    try:
        payload = eng.clean_payload(kind, data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    try:
        job_id = eng.submit_job(kind, payload)
    except eng.NotReady as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        logger.error(f"POST /api/factcheck/{kind} could not queue the job: {e}")
        return jsonify({'error': 'The server could not save this request (database problem). '
                                 'The details are in the Render log.'}), 500
    return jsonify({'job_id': job_id, 'status': 'queued'}), 202


@factcheck_bp.route('/api/factcheck/claims', methods=['POST'])
def factcheck_claims():
    """Queue: find the checkable claims in a passage. Body: {new_text, context?, known_claims?, speaker?, event?, final?}"""
    return _queue('claims')


@factcheck_bp.route('/api/factcheck/check', methods=['POST'])
def factcheck_check():
    """Queue: fast live check of one claim. Body: {claim, quote?, kind?, context?, speaker?, event?}"""
    return _queue('check')


@factcheck_bp.route('/api/factcheck/deep', methods=['POST'])
def factcheck_deep():
    """Queue: five-layer recheck of one claim. Body: as /check plus {live_verdict?, live_reason?}"""
    return _queue('deep')


# ============================================================================
# JOB STATUS
# ============================================================================

@factcheck_bp.route('/api/factcheck/jobs/status', methods=['POST'])
def factcheck_jobs_status():
    """
    Body: {"ids": ["<job id>", ...]} (at most 50).
    Returns {"jobs": [{"id", "status", "result"? , "error"?}, ...]} in the order asked.
    status is one of: queued, running, done, failed, missing.
    """
    if not _passcode_ok():
        return jsonify({'error': 'Passcode needed.'}), 401
    data = request.get_json(silent=True)
    ids = data.get('ids') if isinstance(data, dict) else None
    if not isinstance(ids, list):
        return jsonify({'error': 'The request was not understood.'}), 400
    ids = [i for i in ids if isinstance(i, str) and _JOB_ID.match(i)][:_MAX_IDS_PER_STATUS_CALL]
    try:
        eng = _engine()
    except ImportError:
        return _not_ready()
    try:
        return jsonify({'jobs': eng.get_jobs(ids)})
    except Exception as e:
        logger.error(f"POST /api/factcheck/jobs/status failed: {e}")
        return jsonify({'error': 'The server could not read the results (database problem). '
                                 'The details are in the Render log.'}), 500


# ============================================================================
# HELPERS
# ============================================================================

def _not_ready():
    return jsonify({
        'error': 'The fact-checker engine is not available on the server '
                 '(factcheck_engine.py is not deployed).',
    }), 503


# I did no harm and this file is not truncated
