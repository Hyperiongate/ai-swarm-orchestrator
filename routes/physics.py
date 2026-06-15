"""
FeynmanLab — Flask Routes
File: routes/physics.py
Created: June 14, 2026
Last Updated: June 14, 2026 — WO-14 Phase 5: voice endpoint

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
    GET    /api/physics/image/<id>        — serve a stored figure (Phase 4)
    POST   /api/physics/voice             — hands-free turn (Phase 5) audio+session_id

CHANGELOG:
- June 14, 2026: WO-14 PHASE 5 — VOICE ENDPOINT
  * Added POST /api/physics/voice: takes a recorded audio clip + session_id,
    transcribes (Whisper), runs the partner in voice mode, and returns the
    transcript, the full written reply, figures, and base64 TTS audio (ElevenLabs)
    when available. Additive only; the text endpoints are untouched.
- June 14, 2026: WO-14 PHASE 4 — FIGURE-SERVING ROUTE
  * Added GET /api/physics/image/<id>, which streams a stored figure's bytes with
    its mime type (engine get_image()). The message and session payloads already
    carry image URLs (engine change), so no other route needed touching.
    Additive only; Rule 1 preserved.
- June 14, 2026: WO-14 PHASE 1 — INITIAL IMPLEMENTATION
  * New blueprint physics_bp. Page route + session CRUD + the message endpoint.
  * Registered in app.py (see app.py changelog). No existing route touched.
    Rule 1 (do no harm) preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import logging
from flask import Blueprint, jsonify, request, render_template, Response

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
# FIGURE SERVING (Phase 4)
# ============================================================================

@physics_bp.route('/api/physics/image/<int:image_id>', methods=['GET'])
def get_physics_image(image_id: int):
    """Stream a stored figure's bytes with its mime type."""
    try:
        img = _lab().get_image(image_id)
        if img is None:
            return jsonify({'success': False, 'error': f'Image {image_id} not found'}), 404
        resp = Response(img['data'], mimetype=img['mime'])
        resp.headers['Cache-Control'] = 'private, max-age=86400'
        return resp
    except ImportError:
        return _not_ready()
    except Exception as e:
        logger.error(f"GET /api/physics/image/{image_id} failed: {e}")
        return _error(e)


# ============================================================================
# VOICE (Phase 5)
# ============================================================================

@physics_bp.route('/api/physics/voice', methods=['POST'])
def physics_voice():
    """
    Hands-free turn. Multipart form: audio=<file>, session_id=<int>.
    Transcribes the audio (Whisper), runs it through the partner in voice mode,
    synthesizes the spoken reply (ElevenLabs), and returns:
      { success, transcript, reply, spoken, images, computed, searched,
        audio_b64?, audio_mime? }
    If TTS is unavailable, audio_b64 is omitted and the client speaks the reply
    with the browser's built-in voice instead.
    """
    try:
        lab = _lab()

        if 'audio' not in request.files:
            return jsonify({'success': False, 'error': 'no audio uploaded'}), 400
        audio_file = request.files['audio']
        audio_bytes = audio_file.read()
        if not audio_bytes:
            return jsonify({'success': False, 'error': 'empty audio'}), 400

        session_id = request.form.get('session_id')
        if session_id is None:
            return jsonify({'success': False, 'error': 'session_id is required'}), 400
        try:
            session_id = int(session_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'session_id must be an integer'}), 400

        filename = audio_file.filename or 'voice.webm'
        tr = lab.transcribe_audio(audio_bytes, filename)
        if not tr.get('success'):
            return jsonify({'success': False,
                            'error': 'transcription failed: ' + tr.get('error', '')}), 502
        transcript = tr.get('text', '')
        if not transcript:
            return jsonify({'success': False, 'error': 'no speech detected',
                            'transcript': ''}), 200

        result = lab.ask(session_id, transcript, voice=True)
        result['transcript'] = transcript
        if not result.get('success'):
            err = result.get('error', 'Unknown error')
            status = 404 if 'not found' in err.lower() else 500
            return jsonify(result), status

        spoken = result.get('spoken') or result.get('reply', '')
        audio = lab.synthesize_speech(spoken)
        if audio:
            import base64
            result['audio_b64'] = base64.b64encode(audio).decode('ascii')
            result['audio_mime'] = 'audio/mpeg'
        return jsonify(result)
    except ImportError:
        return _not_ready()
    except Exception as e:
        logger.error(f"POST /api/physics/voice failed: {e}")
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
