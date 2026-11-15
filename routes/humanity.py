"""
The Humanity Index — Flask Routes
File: routes/humanity.py
Created: November 15, 2026
Last Updated: November 15, 2026 — Initial implementation

PURPOSE:
    Flask blueprint for the Humanity Index page and its small API. Every
    route returns in milliseconds: it hands a job to the queue, reads a job's
    result, or reads/writes the library or the ledger. The AI work runs in the
    separate helper process (humanity_runner.py). See humanity_engine.py.

    The engine is imported lazily inside handlers (the Swarm's pattern), so a
    missing module degrades to a clean 503, not a failed start.

ENDPOINTS:
    GET   /humanity                         the page
    GET   /api/humanity/health              is it ready? (key, passcode, panel, helper)
    POST  /api/humanity/ask                 queue: research a sentence {question, place?}
    POST  /api/humanity/review              queue: other AIs rate a stored answer {answer_id}
    POST  /api/humanity/jobs/status         where do these jobs stand? {ids: [...]}
    GET   /api/humanity/library             the answers asked so far (newest first)
    GET   /api/humanity/library/<id>        one stored answer with its review
    POST  /api/humanity/library/delete      {id}
    GET   /api/humanity/ledger              every "I did this"
    POST  /api/humanity/ledger/add          {answer_id, done_on?, times?, note?}
    POST  /api/humanity/ledger/delete       {id}

PASSCODE (Jim's choice, November 15, 2026: "just you, with passcode"):
    Every /api/humanity/* route except /health needs the passcode in the
    X-App-Passcode header (the page asks for it once per browser session).
    The passcode is HUMANITY_PASSCODE, or FACTCHECK_PASSCODE if that is not
    set. If NEITHER is set the API is locked for everyone, on purpose: no one
    can spend the Swarm's AI budget through this page by accident. The Admin
    Gate (swarm_security.py) lists this blueprint as having its own login.

CHANGELOG:
- November 15, 2026: INITIAL IMPLEMENTATION
  * New blueprint humanity_bp. Registered in app.py (see app.py changelog).
    No existing route touched. Rule 1 (do no harm) preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import hmac
import logging
import os
import re
from functools import wraps

from flask import Blueprint, jsonify, request, send_from_directory

logger = logging.getLogger(__name__)

humanity_bp = Blueprint('humanity', __name__)

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
_MAX_BODY_BYTES = 32 * 1024
_MAX_IDS_PER_STATUS_CALL = 20
_ID = re.compile(r'^[0-9a-f]{32}$')


def _engine():
    import humanity_engine
    return humanity_engine


def _not_ready():
    return jsonify({'error': 'The Humanity Index is not installed correctly on the server. '
                             'The details are in the Render log.'}), 503


def _db_error(what, e):
    logger.error(f"Humanity: {what} failed: {e}")
    return jsonify({'error': 'The server could not reach its database. The details are in the Render log.'}), 500


# ============================================================================
# PASSCODE
# ============================================================================

def _expected_passcode():
    return (os.environ.get('HUMANITY_PASSCODE', '').strip()
            or os.environ.get('FACTCHECK_PASSCODE', '').strip())


def _passcode_ok():
    expected = _expected_passcode()
    if not expected:
        return False           # locked until a passcode is set (see the note at the top)
    given = request.headers.get('X-App-Passcode', '')
    return hmac.compare_digest(given.encode('utf-8'), expected.encode('utf-8'))


def _locked_message():
    if not _expected_passcode():
        return ('No passcode has been set for the Humanity Index, so it is locked. In Render > '
                'Environment, add HUMANITY_PASSCODE, then redeploy.')
    return 'Passcode needed.'


def needs_passcode(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not _passcode_ok():
            return jsonify({'error': _locked_message()}), 401
        if (request.content_length or 0) > _MAX_BODY_BYTES:
            return jsonify({'error': 'That request is too large.'}), 413
        return view(*args, **kwargs)
    return wrapper


def _body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


# ============================================================================
# HEADERS (this blueprint's responses only)
# ============================================================================

@humanity_bp.after_request
def _humanity_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if request.path.startswith('/api/humanity/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


# ============================================================================
# PAGE AND HEALTH
# ============================================================================

@humanity_bp.route('/humanity', methods=['GET'])
def humanity_page():
    """Sent as a plain file, not through render_template (the script is full of braces)."""
    response = send_from_directory(_TEMPLATES_DIR, 'humanity.html', mimetype='text/html')
    response.headers['Cache-Control'] = 'no-cache'
    return response


@humanity_bp.route('/api/humanity/health', methods=['GET'])
def humanity_health():
    """What the page needs to know before it starts. Never queues anything."""
    info = {'ok': True, 'passcode_set': bool(_expected_passcode()), 'passcode_ok': _passcode_ok(),
            'engine': 'missing', 'ai_ready': False, 'database': 'unknown', 'helper': 'unknown', 'panel': []}
    try:
        eng = _engine()
    except ImportError as e:
        logger.error(f"Humanity: engine import failed: {e}")
        info['ok'] = False
        return jsonify(info)
    info['engine'] = 'ok'
    info['ai_ready'] = eng.ai_ready()
    info['model'] = eng.ANSWER_MODEL
    info['areas'] = list(eng.AREAS)
    info['panel'] = eng.panel_names()
    try:
        info['helper'] = 'running' if eng.runner_alive() else 'idle'
        info['database'] = 'ok'
    except Exception as e:
        logger.error(f"Humanity: health database check failed: {e}")
        info['database'] = 'error'
        info['ok'] = False
    return jsonify(info)


# ============================================================================
# QUEUE WORK
# ============================================================================

@humanity_bp.route('/api/humanity/ask', methods=['POST'])
@needs_passcode
def humanity_ask():
    data = _body()
    if data is None:
        return jsonify({'error': 'The request was not understood.'}), 400
    try:
        eng = _engine()
    except ImportError:
        return _not_ready()
    try:
        payload = eng.clean_question(data)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    try:
        job_id = eng.submit_job('answer', payload)
    except eng.NotReady as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return _db_error('queueing a question', e)
    return jsonify({'job_id': job_id, 'status': 'queued'}), 202


@humanity_bp.route('/api/humanity/review', methods=['POST'])
@needs_passcode
def humanity_review():
    data = _body()
    answer_id = str((data or {}).get('answer_id') or '')
    if not _ID.match(answer_id):
        return jsonify({'error': 'The request was not understood.'}), 400
    try:
        eng = _engine()
    except ImportError:
        return _not_ready()
    if not eng.panel_names():
        return jsonify({'error': 'No other AI is available to review the figures. The Swarm needs '
                                 'OPENAI_API_KEY, GOOGLE_API_KEY or DEEPSEEK_API_KEY in Render.'}), 503
    try:
        job_id = eng.submit_review(answer_id)
    except LookupError as e:
        return jsonify({'error': str(e)}), 404
    except eng.NotReady as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return _db_error('queueing a review', e)
    return jsonify({'job_id': job_id, 'status': 'queued'}), 202


@humanity_bp.route('/api/humanity/jobs/status', methods=['POST'])
@needs_passcode
def humanity_jobs_status():
    data = _body()
    ids = data.get('ids') if data else None
    if not isinstance(ids, list):
        return jsonify({'error': 'The request was not understood.'}), 400
    ids = [i for i in ids if isinstance(i, str) and _ID.match(i)][:_MAX_IDS_PER_STATUS_CALL]
    try:
        eng = _engine()
    except ImportError:
        return _not_ready()
    try:
        return jsonify({'jobs': eng.get_jobs(ids)})
    except Exception as e:
        return _db_error('reading job status', e)


# ============================================================================
# LIBRARY
# ============================================================================

@humanity_bp.route('/api/humanity/library', methods=['GET'])
@needs_passcode
def humanity_library():
    try:
        return jsonify({'answers': _engine().library_list()})
    except ImportError:
        return _not_ready()
    except Exception as e:
        return _db_error('reading the library', e)


@humanity_bp.route('/api/humanity/library/<answer_id>', methods=['GET'])
@needs_passcode
def humanity_library_item(answer_id):
    if not _ID.match(answer_id):
        return jsonify({'error': 'Not found.'}), 404
    try:
        entry = _engine().library_get(answer_id)
    except ImportError:
        return _not_ready()
    except Exception as e:
        return _db_error('reading an answer', e)
    if entry is None:
        return jsonify({'error': 'That answer is no longer in the library.'}), 404
    return jsonify(entry)


@humanity_bp.route('/api/humanity/library/delete', methods=['POST'])
@needs_passcode
def humanity_library_delete():
    answer_id = str((_body() or {}).get('id') or '')
    if not _ID.match(answer_id):
        return jsonify({'error': 'The request was not understood.'}), 400
    try:
        deleted = _engine().library_delete(answer_id)
    except ImportError:
        return _not_ready()
    except Exception as e:
        return _db_error('deleting an answer', e)
    return jsonify({'deleted': deleted})


# ============================================================================
# LEDGER
# ============================================================================

@humanity_bp.route('/api/humanity/ledger', methods=['GET'])
@needs_passcode
def humanity_ledger():
    try:
        return jsonify({'entries': _engine().ledger_list()})
    except ImportError:
        return _not_ready()
    except Exception as e:
        return _db_error('reading the ledger', e)


@humanity_bp.route('/api/humanity/ledger/add', methods=['POST'])
@needs_passcode
def humanity_ledger_add():
    data = _body()
    if data is None:
        return jsonify({'error': 'The request was not understood.'}), 400
    try:
        eng = _engine()
    except ImportError:
        return _not_ready()
    try:
        entry = eng.ledger_add(eng.clean_ledger_entry(data))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return _db_error('adding to the ledger', e)
    return jsonify({'entry': entry}), 201


@humanity_bp.route('/api/humanity/ledger/delete', methods=['POST'])
@needs_passcode
def humanity_ledger_delete():
    entry_id = str((_body() or {}).get('id') or '')
    if not _ID.match(entry_id):
        return jsonify({'error': 'The request was not understood.'}), 400
    try:
        deleted = _engine().ledger_delete(entry_id)
    except ImportError:
        return _not_ready()
    except Exception as e:
        return _db_error('deleting from the ledger', e)
    return jsonify({'deleted': deleted})

# I did no harm and this file is not truncated
