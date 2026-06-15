"""
FeynmanLab — Flask Routes
File: routes/physics.py
Created: June 14, 2026
Last Updated: June 14, 2026 — WO-14 Phase 1: page + session/message API

PURPOSE:
    Flask blueprint for FeynmanLab, the physics thinking partner.
    Serves the lab page and the session/message API. All physics_lab calls are
    imported lazily inside handlers (matching the swarm's pattern) so a missing
    module degrades to a clean 503 rather than a 500 at import time.

ENDPOINTS:
    GET    /physics                       — the FeynmanLab page
    POST   /api/physics/session           — create a session            {title?}
    GET    /api/physics/sessions          — list sessions
    GET    /api/physics/session/<id>      — get a session + its messages
    PUT    /api/physics/session/<id>      — rename a session             {title}
    DELETE /api/physics/session/<id>      — delete a session
    POST   /api/physics/message           — ask the partner   {session_id, content}

CHANGELOG:
- June 14, 2026: WO-14 PHASE 1 — INITIAL IMPLEMENTATION
  * New blueprint physics_bp. Page route + session CRUD + the message endpoint.
  * Registered in app.py (see app.py changelog). No existing route touched.
    Rule 1 (do no harm) preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import logging
from flask import Blueprint, jsonify, request, render_template

logger = logging.getLogger(__name__)

physics_bp = Blueprint('physics', __name__)


def _lab():
    """Import the engine lazily; raises ImportError if the module is absent."""
    import physics_lab
    return physics_lab


# ============================================================================
# PAGE
# ============================================================================

@physics_bp.route('/physics', methods=['GET'])
def physics_page():
    """The FeynmanLab interface."""
    return render_template('physics.html')


# ============================================================================
# SESSION ENDPOINTS
# ============================================================================

@physics_bp.route('/api/physics/session', methods=['POST'])
def create_physics_session():
    """Create a new session. Body (JSON, optional): { "title": "..." }"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        session = _lab().create_session(title=data.get('title'))
        return jsonify({'success': True, 'session': session}), 201
    except ImportError:
        return _not_ready()
    except Exception as e:
        logger.error(f"POST /api/physics/session failed: {e}")
        return _error(e)


@physics_bp.route('/api/physics/sessions', methods=['GET'])
def list_physics_sessions():
    """List sessions, newest-activity first."""
    try:
        limit = int(request.args.get('limit', 100))
    except (ValueError, TypeError):
        limit = 100
    try:
        sessions = _lab().list_sessions(limit=limit)
        return jsonify({'success': True, 'count': len(sessions), 'sessions': sessions})
    except ImportError:
        return _not_ready()
    except Exception as e:
        logger.error(f"GET /api/physics/sessions failed: {e}")
        return _error(e)


@physics_bp.route('/api/physics/session/<int:session_id>', methods=['GET'])
def get_physics_session(session_id: int):
    """Return a session with its full message thread."""
    try:
        session = _lab().get_session(session_id)
        if session is None:
            return jsonify({'success': False, 'error': f'Session {session_id} not found'}), 404
        return jsonify({'success': True, 'session': session})
    except ImportError:
        return _not_ready()
    except Exception as e:
        logger.error(f"GET /api/physics/session/{session_id} failed: {e}")
        return _error(e)


@physics_bp.route('/api/physics/session/<int:session_id>', methods=['PUT'])
def rename_physics_session(session_id: int):
    """Rename a session. Body (JSON): { "title": "..." }"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        title = (data.get('title') or '').strip()
        if not title:
            return jsonify({'success': False, 'error': 'title is required'}), 400
        ok = _lab().rename_session(session_id, title)
        if not ok:
            return jsonify({'success': False, 'error': f'Session {session_id} not found'}), 404
        return jsonify({'success': True, 'session_id': session_id, 'title': title})
    except ImportError:
        return _not_ready()
    except Exception as e:
        logger.error(f"PUT /api/physics/session/{session_id} failed: {e}")
        return _error(e)


@physics_bp.route('/api/physics/session/<int:session_id>', methods=['DELETE'])
def delete_physics_session(session_id: int):
    """Delete a session and its messages."""
    try:
        existed = _lab().delete_session(session_id)
        if not existed:
            return jsonify({'success': False, 'error': f'Session {session_id} not found'}), 404
        return jsonify({'success': True, 'session_id': session_id, 'deleted': True})
    except ImportError:
        return _not_ready()
    except Exception as e:
        logger.error(f"DELETE /api/physics/session/{session_id} failed: {e}")
        return _error(e)


# ============================================================================
# MESSAGE ENDPOINT
# ============================================================================

@physics_bp.route('/api/physics/message', methods=['POST'])
def physics_message():
    """
    Ask the partner within a session.
    Body (JSON): { "session_id": <int>, "content": "<your message>" }
    Returns the partner's reply.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        session_id = data.get('session_id')
        content = (data.get('content') or '').strip()

        if session_id is None:
            return jsonify({'success': False, 'error': 'session_id is required'}), 400
        try:
            session_id = int(session_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'session_id must be an integer'}), 400
        if not content:
            return jsonify({'success': False, 'error': 'content is required'}), 400

        result = _lab().ask(session_id, content)
        if result.get('success'):
            return jsonify(result)
        # Distinguish "not found" from other failures for a cleaner client.
        err = result.get('error', 'Unknown error')
        status = 404 if 'not found' in err.lower() else 500
        return jsonify(result), status
    except ImportError:
        return _not_ready()
    except Exception as e:
        logger.error(f"POST /api/physics/message failed: {e}")
        return _error(e)


# ============================================================================
# HELPERS
# ============================================================================

def _not_ready():
    return jsonify({
        'success': False,
        'error': 'FeynmanLab engine not available',
        'detail': 'physics_lab.py is not deployed.',
    }), 503


def _error(e):
    import traceback
    return jsonify({
        'success': False,
        'error': str(e),
        'traceback': traceback.format_exc(),
    }), 500


# I did no harm and this file is not truncated
