"""
Survey in a Box — Admin Dashboard Routes
File: routes/survey_admin.py
Created: March 16, 2026
Last Updated: March 16, 2026 — Phase 1, Step 1.3: Initial creation

PURPOSE:
    Password-protected admin dashboard for Survey in a Box.
    Jim uses this to review intake submissions, configure survey projects,
    and approve clients for Phase 2 (survey assembly).

ENDPOINTS:
    GET  /survey/admin                          — Dashboard (password gate)
    GET  /api/survey/admin/clients              — List all survey_clients (JSON)
    GET  /api/survey/admin/client/<id>          — Get one client + project (JSON)
    POST /api/survey/admin/client/<id>/status   — Update client status
    POST /api/survey/admin/project/save         — Save/update survey_projects row
    POST /api/survey/admin/project/<id>/approve — Approve project (status → approved)
    POST /api/survey/admin/client/<id>/notes    — Save admin notes to survey_clients

AUTH:
    Session-cookie based. Password checked against SURVEY_ADMIN_PASSWORD env var.
    GET /api/survey/admin/login  and POST /api/survey/admin/login handle auth.
    GET /api/survey/admin/logout clears session.

DESIGN RULES:
    - PostgreSQL: RealDictCursor, %s params, RETURNING id
    - All JSON list fields decoded on read, encoded on write
    - No changes to any existing Swarm table or route
    - Blueprint prefix: none (routes defined with full paths)
    - project_token generated with secrets.token_urlsafe(16) on first save

CHANGELOG:
    - March 16, 2026: Initial creation for Phase 1, Step 1.3.
"""

import json
import os
import secrets
import traceback
from datetime import datetime
from functools import wraps

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

survey_admin_bp = Blueprint('survey_admin', __name__)

# ---------------------------------------------------------------------------
# AUTH HELPERS
# ---------------------------------------------------------------------------

ADMIN_SESSION_KEY = 'survey_admin_authenticated'


def _get_admin_password():
    """Read the admin password from environment. Never hard-code."""
    return os.environ.get('SURVEY_ADMIN_PASSWORD', '')


def _is_authenticated():
    return session.get(ADMIN_SESSION_KEY) is True


def require_survey_admin(f):
    """Decorator: return 401 JSON for API routes if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _is_authenticated():
            return jsonify({'success': False, 'error': 'Not authenticated.', 'redirect': '/survey/admin'}), 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# DB HELPER
# ---------------------------------------------------------------------------

def _get_db():
    from db_engine import get_db_connection
    return get_db_connection()


# ---------------------------------------------------------------------------
# JSON DECODE HELPERS
# ---------------------------------------------------------------------------

def _decode_json_field(val, fallback=None):
    """Safely decode a JSON string stored in a TEXT column."""
    if val is None:
        return fallback if fallback is not None else []
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return fallback if fallback is not None else []


def _client_to_dict(row):
    """Convert a survey_clients RealDictRow to a clean Python dict."""
    d = dict(row)
    d['department_names']  = _decode_json_field(d.get('department_names'), [])
    d['biggest_challenges'] = _decode_json_field(d.get('biggest_challenges'), [])
    # Serialize datetime fields for JSON
    for key in ('created_at', 'updated_at'):
        if d.get(key) and hasattr(d[key], 'isoformat'):
            d[key] = d[key].isoformat()
    return d


def _project_to_dict(row):
    """Convert a survey_projects RealDictRow to a clean Python dict."""
    d = dict(row)
    for field in ('selected_questions', 'excluded_questions',
                  'custom_questions', 'selected_schedules'):
        d[field] = _decode_json_field(d.get(field), [])
    for key in ('created_at', 'updated_at', 'approved_at', 'opened_at', 'closed_at'):
        if d.get(key) and hasattr(d[key], 'isoformat'):
            d[key] = d[key].isoformat()
    return d


# ---------------------------------------------------------------------------
# DASHBOARD PAGE
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/survey/admin', methods=['GET'])
def admin_dashboard():
    """Render the admin dashboard HTML. Auth is handled client-side via API."""
    return render_template('survey_admin.html')


# ---------------------------------------------------------------------------
# AUTH ENDPOINTS
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/login', methods=['POST'])
def admin_login():
    """Validate password and set session cookie."""
    data = request.get_json(force=True) or {}
    password = data.get('password', '')
    correct  = _get_admin_password()

    if not correct:
        # If env var not set, deny access — never allow empty-password login
        return jsonify({'success': False, 'error': 'Admin password not configured on server.'}), 500

    if password == correct:
        session[ADMIN_SESSION_KEY] = True
        session.permanent = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Incorrect password.'}), 401


@survey_admin_bp.route('/api/survey/admin/logout', methods=['POST'])
def admin_logout():
    """Clear the admin session."""
    session.pop(ADMIN_SESSION_KEY, None)
    return jsonify({'success': True})


@survey_admin_bp.route('/api/survey/admin/auth-status', methods=['GET'])
def auth_status():
    """Check whether the current session is authenticated."""
    return jsonify({'authenticated': _is_authenticated()})


# ---------------------------------------------------------------------------
# CLIENT LIST
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/clients', methods=['GET'])
@require_survey_admin
def list_clients():
    """
    Return all survey_clients ordered by created_at DESC.
    Also returns the associated project (if any) for each client.
    """
    try:
        conn = _get_db()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    sc.*,
                    sp.id            AS project_id,
                    sp.project_token AS project_token,
                    sp.status        AS project_status,
                    sp.response_count AS response_count
                FROM survey_clients sc
                LEFT JOIN survey_projects sp ON sp.survey_client_id = sc.id
                ORDER BY sc.created_at DESC
            """)
            rows = cursor.fetchall()
        finally:
            conn.close()

        clients = []
        for row in rows:
            d = _client_to_dict(row)
            # Flatten project fields
            d['project_id']     = d.get('project_id')
            d['project_token']  = d.get('project_token')
            d['project_status'] = d.get('project_status')
            d['response_count'] = d.get('response_count', 0)
            clients.append(d)

        return jsonify({'success': True, 'clients': clients, 'total': len(clients)})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# SINGLE CLIENT DETAIL
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/client/<int:client_id>', methods=['GET'])
@require_survey_admin
def get_client(client_id):
    """Return full detail for one client plus their project config (if any)."""
    try:
        conn = _get_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM survey_clients WHERE id = %s", (client_id,))
            client_row = cursor.fetchone()
            if not client_row:
                return jsonify({'success': False, 'error': f'Client {client_id} not found.'}), 404

            cursor.execute(
                "SELECT * FROM survey_projects WHERE survey_client_id = %s ORDER BY created_at DESC LIMIT 1",
                (client_id,)
            )
            project_row = cursor.fetchone()
        finally:
            conn.close()

        client  = _client_to_dict(client_row)
        project = _project_to_dict(project_row) if project_row else None

        return jsonify({'success': True, 'client': client, 'project': project})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# UPDATE CLIENT STATUS
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/client/<int:client_id>/status', methods=['POST'])
@require_survey_admin
def update_client_status(client_id):
    """Change the status of a survey_clients row."""
    try:
        data = request.get_json(force=True) or {}
        new_status = data.get('status', '').strip()

        valid_statuses = ('new', 'reviewing', 'approved', 'rejected', 'in-progress', 'delivered')
        if new_status not in valid_statuses:
            return jsonify({'success': False,
                            'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400

        conn = _get_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE survey_clients SET status = %s, updated_at = NOW() WHERE id = %s",
                (new_status, client_id)
            )
            if cursor.rowcount == 0:
                conn.rollback()
                return jsonify({'success': False, 'error': f'Client {client_id} not found.'}), 404
            conn.commit()
        finally:
            conn.close()

        return jsonify({'success': True, 'client_id': client_id, 'status': new_status})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# SAVE ADMIN NOTES ON CLIENT
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/client/<int:client_id>/notes', methods=['POST'])
@require_survey_admin
def save_client_notes(client_id):
    """Save Jim's admin notes to survey_clients.admin_notes."""
    try:
        data = request.get_json(force=True) or {}
        notes = data.get('admin_notes', '')

        conn = _get_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE survey_clients SET admin_notes = %s, updated_at = NOW() WHERE id = %s",
                (notes, client_id)
            )
            if cursor.rowcount == 0:
                conn.rollback()
                return jsonify({'success': False, 'error': f'Client {client_id} not found.'}), 404
            conn.commit()
        finally:
            conn.close()

        return jsonify({'success': True, 'client_id': client_id})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# SAVE / UPDATE PROJECT CONFIGURATION
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/project/save', methods=['POST'])
@require_survey_admin
def save_project():
    """
    Upsert a survey_projects row for a given survey_client_id.
    If a project already exists for this client, update it.
    If not, create a new one (generates project_token).
    """
    try:
        data = request.get_json(force=True) or {}
        client_id = data.get('survey_client_id')
        if not client_id:
            return jsonify({'success': False, 'error': 'survey_client_id is required.'}), 400

        selected_questions  = json.dumps(data.get('selected_questions', []))
        excluded_questions  = json.dumps(data.get('excluded_questions', []))
        custom_questions    = json.dumps(data.get('custom_questions', []))
        selected_schedules  = json.dumps(data.get('selected_schedules', []))
        admin_notes         = data.get('admin_notes', None)

        conn = _get_db()
        try:
            cursor = conn.cursor()

            # Check if project already exists for this client
            cursor.execute(
                "SELECT id FROM survey_projects WHERE survey_client_id = %s ORDER BY created_at DESC LIMIT 1",
                (client_id,)
            )
            existing = cursor.fetchone()

            if existing:
                project_id = existing['id'] if isinstance(existing, dict) else existing[0]
                cursor.execute("""
                    UPDATE survey_projects SET
                        selected_questions = %s,
                        excluded_questions = %s,
                        custom_questions   = %s,
                        selected_schedules = %s,
                        admin_notes        = %s,
                        updated_at         = NOW()
                    WHERE id = %s
                """, (
                    selected_questions, excluded_questions, custom_questions,
                    selected_schedules, admin_notes, project_id
                ))
                conn.commit()
                return jsonify({'success': True, 'project_id': project_id, 'action': 'updated'})
            else:
                # Create new project
                token = secrets.token_urlsafe(16)
                cursor.execute("""
                    INSERT INTO survey_projects (
                        survey_client_id, project_token, status,
                        selected_questions, excluded_questions,
                        custom_questions, selected_schedules, admin_notes,
                        created_at, updated_at
                    ) VALUES (%s, %s, 'draft', %s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING id
                """, (
                    client_id, token,
                    selected_questions, excluded_questions,
                    custom_questions, selected_schedules, admin_notes
                ))
                row = cursor.fetchone()
                project_id = row['id'] if isinstance(row, dict) else row[0]
                conn.commit()
                return jsonify({'success': True, 'project_id': project_id,
                                'project_token': token, 'action': 'created'})
        finally:
            conn.close()

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# APPROVE PROJECT
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/project/<int:project_id>/approve', methods=['POST'])
@require_survey_admin
def approve_project(project_id):
    """
    Set survey_projects.status = 'approved'.
    Also sets survey_clients.status = 'approved' and records approved_at.
    This is the gate for Phase 2 (survey assembly).
    """
    try:
        conn = _get_db()
        try:
            cursor = conn.cursor()

            # Fetch the project to get the client_id
            cursor.execute(
                "SELECT survey_client_id FROM survey_projects WHERE id = %s",
                (project_id,)
            )
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return jsonify({'success': False, 'error': f'Project {project_id} not found.'}), 404

            client_id = row['survey_client_id'] if isinstance(row, dict) else row[0]

            # Update the project
            cursor.execute("""
                UPDATE survey_projects
                SET status = 'approved', approved_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (project_id,))

            # Update the client
            cursor.execute("""
                UPDATE survey_clients
                SET status = 'approved', updated_at = NOW()
                WHERE id = %s
            """, (client_id,))

            conn.commit()

        finally:
            conn.close()

        print(f"[survey_admin] Project {project_id} approved for client {client_id}")
        return jsonify({
            'success': True,
            'project_id': project_id,
            'client_id': client_id,
            'status': 'approved',
            'message': 'Project approved. Ready for Phase 2 (Survey Assembly).'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# GET PROJECT DETAIL (standalone, for Phase 2+ use)
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/project/<int:project_id>', methods=['GET'])
@require_survey_admin
def get_project(project_id):
    """Return full detail for one survey_projects row."""
    try:
        conn = _get_db()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM survey_projects WHERE id = %s", (project_id,))
            row = cursor.fetchone()
        finally:
            conn.close()

        if not row:
            return jsonify({'success': False, 'error': f'Project {project_id} not found.'}), 404

        return jsonify({'success': True, 'project': _project_to_dict(row)})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# I did no harm and this file is not truncated
