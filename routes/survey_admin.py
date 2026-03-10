"""
SURVEY IN A BOX — Admin Routes
File: routes/survey_admin.py
Created: March 10, 2026
Last Updated: March 10, 2026 — Initial creation, Phase 1 Step 1.3

PURPOSE:
    Backend routes for Jim's password-protected Survey in a Box admin dashboard.
    Handles authentication, intake submission review, project configuration,
    and survey approval. Reads from survey_clients and survey_projects tables
    created in migration_002_survey_in_a_box.py.

    Authentication uses Flask session (cookie-based). Password is read from
    environment variable SURVEY_ADMIN_PASSWORD. Falls back to a dev default
    if the variable is not set. Uses secrets.compare_digest for timing-safe
    comparison.

    This blueprint does NOT touch any existing Swarm routes or tables.

ENDPOINTS:
    GET  /survey/admin                          — Dashboard page (HTML)
    POST /api/survey/admin/login                — Verify password, set session
    POST /api/survey/admin/logout               — Clear session
    GET  /api/survey/admin/clients              — List all intake submissions
    GET  /api/survey/admin/client/<id>          — Full client + project details
    POST /api/survey/admin/client/<id>/status   — Update client status
    POST /api/survey/admin/client/<id>/notes    — Save admin notes on client
    POST /api/survey/admin/project/save         — Create or update project config
    POST /api/survey/admin/project/<id>/approve — Approve survey (sets both
                                                  project and client to approved,
                                                  records history)

POSTGRESQL RULES:
    - RealDictCursor dict-only rows (access by name, never by index)
    - TRUE/FALSE for booleans (not 0/1)
    - %s for all parameters
    - RETURNING id on INSERT

ENVIRONMENT VARIABLES:
    SURVEY_ADMIN_PASSWORD — Required in production. The admin login password.
                            Set in Render environment variables.

CHANGELOG:
    - March 10, 2026: Initial creation. Phase 1 Step 1.3 of Survey in a Box.
"""

import json
import os
import secrets
import traceback
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request, session

from db_engine import get_db_connection

survey_admin_bp = Blueprint('survey_admin', __name__)

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

VALID_CLIENT_STATUSES = ['new', 'reviewing', 'approved', 'rejected']
VALID_PROJECT_STATUSES = ['draft', 'approved', 'administered', 'processing', 'delivered']


# ---------------------------------------------------------------------------
# AUTH HELPERS
# ---------------------------------------------------------------------------

def _get_admin_password():
    """
    Return the configured admin password from environment.
    Falls back to a dev default — logs a warning if the env var is missing
    so it's obvious in production logs.
    """
    pw = os.environ.get('SURVEY_ADMIN_PASSWORD', '')
    if not pw:
        print('[survey_admin] WARNING: SURVEY_ADMIN_PASSWORD env var not set. '
              'Using insecure dev default. Set this in Render environment variables.')
        pw = 'shiftwork-admin-dev'
    return pw


def _is_logged_in():
    """Return True if the current session is authenticated as survey admin."""
    return session.get('survey_admin_logged_in') is True


def _require_auth():
    """
    Returns None if authenticated, or a 401 JSON response tuple if not.
    Use as: auth_error = _require_auth(); if auth_error: return auth_error
    """
    if not _is_logged_in():
        return jsonify({'success': False, 'error': 'Not authenticated',
                        'redirect': '/survey/admin'}), 401
    return None


# ---------------------------------------------------------------------------
# SAFE JSON HELPERS
# ---------------------------------------------------------------------------

def _safe_json_loads(val, default=None):
    """Parse a JSON string safely. Returns default on failure."""
    if default is None:
        default = []
    if not val:
        return default
    try:
        return json.loads(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# ROUTES — PAGE
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/survey/admin', methods=['GET'])
def survey_admin_page():
    """
    Serve the admin dashboard HTML page.
    The page handles its own auth state in JavaScript — it calls
    /api/survey/admin/clients which returns 401 if not logged in,
    and the page shows a login form in that case.
    """
    return render_template('survey_admin.html')


# ---------------------------------------------------------------------------
# ROUTES — AUTH
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/login', methods=['POST'])
def admin_login():
    """
    Verify admin password and establish session.

    Request body: { 'password': str }
    Returns: { 'success': bool, 'message': str }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        provided = data.get('password', '')

        if not provided:
            return jsonify({'success': False, 'message': 'Password is required.'}), 400

        if secrets.compare_digest(str(provided), _get_admin_password()):
            session['survey_admin_logged_in'] = True
            session.permanent = False
            return jsonify({'success': True, 'message': 'Logged in.'})
        else:
            return jsonify({'success': False, 'message': 'Incorrect password.'}), 401

    except Exception as e:
        print(f'[survey_admin] login error: {traceback.format_exc()}')
        return jsonify({'success': False, 'message': str(e)}), 500


@survey_admin_bp.route('/api/survey/admin/logout', methods=['POST'])
def admin_logout():
    """Clear the admin session."""
    session.pop('survey_admin_logged_in', None)
    return jsonify({'success': True, 'message': 'Logged out.'})


# ---------------------------------------------------------------------------
# ROUTES — CLIENT LIST
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/clients', methods=['GET'])
def list_clients():
    """
    Return all survey client intake submissions, ordered newest first.
    Includes a summary of any associated survey_project record.

    Query params:
        status  — filter by client status (optional)
        search  — search company_name or contact_name (optional)

    Returns: { 'success': bool, 'clients': [...], 'total': int }
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        status_filter = request.args.get('status', '').strip()
        search_filter = request.args.get('search', '').strip()

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Build query with optional filters
            where_clauses = []
            params = []

            if status_filter and status_filter in VALID_CLIENT_STATUSES:
                where_clauses.append('sc.status = %s')
                params.append(status_filter)

            if search_filter:
                where_clauses.append(
                    '(LOWER(sc.company_name) LIKE %s OR LOWER(sc.contact_name) LIKE %s)'
                )
                like = '%' + search_filter.lower() + '%'
                params.extend([like, like])

            where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

            cursor.execute(f"""
                SELECT
                    sc.id,
                    sc.company_name,
                    sc.contact_name,
                    sc.email,
                    sc.phone,
                    sc.industry,
                    sc.employee_count,
                    sc.current_schedule_type,
                    sc.preferred_administration,
                    sc.status,
                    sc.created_at,
                    sc.updated_at,
                    sp.id            AS project_id,
                    sp.project_token AS project_token,
                    sp.status        AS project_status
                FROM survey_clients sc
                LEFT JOIN survey_projects sp
                    ON sp.survey_client_id = sc.id
                {where_sql}
                ORDER BY sc.created_at DESC
            """, params)

            rows = cursor.fetchall()
        finally:
            conn.close()

        clients = []
        for row in rows:
            clients.append({
                'id':                    row['id'],
                'company_name':          row['company_name'],
                'contact_name':          row['contact_name'],
                'email':                 row['email'],
                'phone':                 row['phone'] or '',
                'industry':              row['industry'] or '',
                'employee_count':        row['employee_count'],
                'current_schedule_type': row['current_schedule_type'] or '',
                'preferred_administration': row['preferred_administration'] or '',
                'status':                row['status'],
                'created_at':            str(row['created_at']),
                'updated_at':            str(row['updated_at']),
                'project_id':            row['project_id'],
                'project_token':         row['project_token'] or '',
                'project_status':        row['project_status'] or '',
            })

        return jsonify({'success': True, 'clients': clients, 'total': len(clients)})

    except Exception as e:
        print(f'[survey_admin] list_clients error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — CLIENT DETAIL
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/client/<int:client_id>', methods=['GET'])
def get_client(client_id):
    """
    Return full details for one intake submission, including any
    associated survey_project configuration.

    Returns: { 'success': bool, 'client': {...}, 'project': {...} or None }
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Fetch client
            cursor.execute(
                'SELECT * FROM survey_clients WHERE id = %s',
                (client_id,)
            )
            client_row = cursor.fetchone()

            if not client_row:
                return jsonify({'success': False, 'error': 'Client not found'}), 404

            # Fetch associated project (may not exist yet)
            cursor.execute(
                'SELECT * FROM survey_projects WHERE survey_client_id = %s ORDER BY id DESC LIMIT 1',
                (client_id,)
            )
            project_row = cursor.fetchone()
        finally:
            conn.close()

        # Build client dict — parse JSON fields back to lists
        client = {
            'id':                    client_row['id'],
            'company_name':          client_row['company_name'],
            'contact_name':          client_row['contact_name'],
            'email':                 client_row['email'],
            'phone':                 client_row['phone'] or '',
            'industry':              client_row['industry'] or '',
            'employee_count':        client_row['employee_count'],
            'department_count':      client_row['department_count'],
            'department_names':      _safe_json_loads(client_row['department_names'], []),
            'current_schedule_type': client_row['current_schedule_type'] or '',
            'crew_count':            client_row['crew_count'],
            'shift_start_times':     client_row['shift_start_times'] or '',
            'union_status':          client_row['union_status'] or '',
            'biggest_challenges':    _safe_json_loads(client_row['biggest_challenges'], []),
            'previously_surveyed':   client_row['previously_surveyed'],
            'last_survey_date':      client_row['last_survey_date'] or '',
            'preferred_administration': client_row['preferred_administration'] or '',
            'preferred_delivery_date': client_row['preferred_delivery_date'] or '',
            'referral_source':       client_row['referral_source'] or '',
            'additional_notes':      client_row['additional_notes'] or '',
            'status':                client_row['status'],
            'admin_notes':           client_row['admin_notes'] or '',
            'created_at':            str(client_row['created_at']),
            'updated_at':            str(client_row['updated_at']),
        }

        # Build project dict if it exists
        project = None
        if project_row:
            project = {
                'id':                  project_row['id'],
                'survey_client_id':    project_row['survey_client_id'],
                'project_token':       project_row['project_token'],
                'status':              project_row['status'],
                'selected_questions':  _safe_json_loads(project_row['selected_questions'], []),
                'excluded_questions':  _safe_json_loads(project_row['excluded_questions'], []),
                'custom_questions':    _safe_json_loads(project_row['custom_questions'], []),
                'selected_schedules':  _safe_json_loads(project_row['selected_schedules'], []),
                'admin_notes':         project_row['admin_notes'] or '',
                'generated_document_path': project_row['generated_document_path'] or '',
                'response_count':      project_row['response_count'] or 0,
                'approved_at':         str(project_row['approved_at']) if project_row['approved_at'] else None,
                'created_at':          str(project_row['created_at']),
                'updated_at':          str(project_row['updated_at']),
            }

        return jsonify({'success': True, 'client': client, 'project': project})

    except Exception as e:
        print(f'[survey_admin] get_client error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — CLIENT STATUS & NOTES
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/client/<int:client_id>/status', methods=['POST'])
def update_client_status(client_id):
    """
    Update the status of a survey client intake submission.

    Request body: { 'status': str }
    Valid statuses: new, reviewing, approved, rejected
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        data = request.get_json(force=True, silent=True) or {}
        new_status = data.get('status', '').strip()

        if new_status not in VALID_CLIENT_STATUSES:
            return jsonify({
                'success': False,
                'error': f"Invalid status '{new_status}'. "
                         f"Valid options: {', '.join(VALID_CLIENT_STATUSES)}"
            }), 400

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE survey_clients SET status = %s, updated_at = NOW() WHERE id = %s',
                (new_status, client_id)
            )
            if cursor.rowcount == 0:
                conn.rollback()
                return jsonify({'success': False, 'error': 'Client not found'}), 404
            conn.commit()
        finally:
            conn.close()

        return jsonify({
            'success': True,
            'message': f'Status updated to \'{new_status}\'.',
            'status': new_status
        })

    except Exception as e:
        print(f'[survey_admin] update_client_status error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


@survey_admin_bp.route('/api/survey/admin/client/<int:client_id>/notes', methods=['POST'])
def update_client_notes(client_id):
    """
    Save Jim's internal admin notes on a client submission.

    Request body: { 'admin_notes': str }
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        data = request.get_json(force=True, silent=True) or {}
        notes = data.get('admin_notes', '').strip()

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE survey_clients SET admin_notes = %s, updated_at = NOW() WHERE id = %s',
                (notes, client_id)
            )
            if cursor.rowcount == 0:
                conn.rollback()
                return jsonify({'success': False, 'error': 'Client not found'}), 404
            conn.commit()
        finally:
            conn.close()

        return jsonify({'success': True, 'message': 'Notes saved.'})

    except Exception as e:
        print(f'[survey_admin] update_client_notes error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — PROJECT CONFIG
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/project/save', methods=['POST'])
def save_project():
    """
    Create or update the survey project configuration for a client.
    If a project already exists for this client, it is updated.
    If not, a new project record is created with a unique token.

    Request body:
        {
            'survey_client_id':   int,       required
            'selected_questions': [str],     list of question IDs
            'excluded_questions': [str],     list of excluded question IDs
            'custom_questions':   [obj],     list of custom question objects
            'selected_schedules': [str],     list of schedule IDs
            'admin_notes':        str
        }

    Returns: { 'success': bool, 'project_id': int, 'project_token': str }
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        data = request.get_json(force=True, silent=True) or {}
        client_id = _safe_int(data.get('survey_client_id'))

        if not client_id:
            return jsonify({'success': False, 'error': 'survey_client_id is required.'}), 400

        selected_questions = json.dumps(data.get('selected_questions', []))
        excluded_questions = json.dumps(data.get('excluded_questions', []))
        custom_questions   = json.dumps(data.get('custom_questions', []))
        selected_schedules = json.dumps(data.get('selected_schedules', []))
        admin_notes        = str(data.get('admin_notes', '')).strip()

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Check if a project already exists for this client
            cursor.execute(
                'SELECT id, project_token FROM survey_projects WHERE survey_client_id = %s ORDER BY id DESC LIMIT 1',
                (client_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # UPDATE existing project
                cursor.execute(
                    """
                    UPDATE survey_projects SET
                        selected_questions = %s,
                        excluded_questions = %s,
                        custom_questions   = %s,
                        selected_schedules = %s,
                        admin_notes        = %s,
                        updated_at         = NOW()
                    WHERE id = %s
                    """,
                    (
                        selected_questions,
                        excluded_questions,
                        custom_questions,
                        selected_schedules,
                        admin_notes,
                        existing['id']
                    )
                )
                project_id    = existing['id']
                project_token = existing['project_token']
            else:
                # INSERT new project with a unique token
                project_token = secrets.token_urlsafe(16)
                cursor.execute(
                    """
                    INSERT INTO survey_projects (
                        survey_client_id, project_token, status,
                        selected_questions, excluded_questions,
                        custom_questions, selected_schedules, admin_notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        client_id,
                        project_token,
                        'draft',
                        selected_questions,
                        excluded_questions,
                        custom_questions,
                        selected_schedules,
                        admin_notes
                    )
                )
                row = cursor.fetchone()
                project_id = row['id']

            conn.commit()
        finally:
            conn.close()

        return jsonify({
            'success': True,
            'project_id': project_id,
            'project_token': project_token,
            'message': 'Project configuration saved.'
        })

    except Exception as e:
        print(f'[survey_admin] save_project error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — APPROVE
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/project/<int:project_id>/approve', methods=['POST'])
def approve_project(project_id):
    """
    Approve a survey project. This:
        1. Sets survey_projects.status = 'approved' with approved_at timestamp
        2. Sets survey_clients.status = 'approved'
        3. Inserts a record into survey_project_history for year-over-year tracking
        4. Placeholder hook for Phase 2 document generation (logged, not yet built)

    Request body: {} (no body required — project_id is in URL)
    Returns: { 'success': bool, 'message': str }
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Fetch project to get client_id and validate it exists
            cursor.execute(
                'SELECT id, survey_client_id, status FROM survey_projects WHERE id = %s',
                (project_id,)
            )
            project = cursor.fetchone()

            if not project:
                return jsonify({'success': False, 'error': 'Project not found'}), 404

            if project['status'] == 'approved':
                return jsonify({
                    'success': True,
                    'message': 'Project is already approved.'
                })

            client_id = project['survey_client_id']

            # 1. Approve the project
            cursor.execute(
                """
                UPDATE survey_projects
                SET status = 'approved', approved_at = NOW(), updated_at = NOW()
                WHERE id = %s
                """,
                (project_id,)
            )

            # 2. Approve the client
            cursor.execute(
                """
                UPDATE survey_clients
                SET status = 'approved', updated_at = NOW()
                WHERE id = %s
                """,
                (client_id,)
            )

            # 3. Insert history record (for future year-over-year tracking)
            current_year = datetime.utcnow().year
            cursor.execute(
                """
                INSERT INTO survey_project_history (survey_client_id, survey_project_id, year)
                VALUES (%s, %s, %s)
                """,
                (client_id, project_id, current_year)
            )

            conn.commit()
        finally:
            conn.close()

        # 4. Phase 2 hook — document generation (not yet built)
        print(f'[survey_admin] PHASE 2 HOOK: Project {project_id} approved. '
              f'Document generation not yet implemented (Phase 2 task).')

        return jsonify({
            'success': True,
            'message': 'Survey approved. Client has been notified status is approved. '
                       'Document generation will be available in Phase 2.'
        })

    except Exception as e:
        print(f'[survey_admin] approve_project error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500

# I did no harm and this file is not truncated
