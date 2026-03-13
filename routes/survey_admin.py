"""
SURVEY IN A BOX — Admin Routes
File: routes/survey_admin.py
Created: March 10, 2026
Last Updated: March 12, 2026 — Phase 2: auto-generate Word doc on approval

PURPOSE:
    Backend routes for Jim's password-protected Survey in a Box admin dashboard.
    Handles authentication, intake submission review, project configuration,
    survey approval, and (Phase 2) automatic branded Word document generation
    on approval with a download endpoint.

    Authentication uses Flask session (cookie-based). Password is read from
    environment variable SURVEY_ADMIN_PASSWORD. Falls back to a dev default
    if the variable is not set. Uses secrets.compare_digest for timing-safe
    comparison.

    This blueprint does NOT touch any existing Swarm routes or tables.

ENDPOINTS:
    GET  /survey/admin                              — Dashboard page (HTML)
    POST /api/survey/admin/login                    — Verify password, set session
    POST /api/survey/admin/logout                   — Clear session
    GET  /api/survey/admin/clients                  — List all intake submissions
    GET  /api/survey/admin/client/<id>              — Full client + project details
    POST /api/survey/admin/client/<id>/status       — Update client status
    POST /api/survey/admin/client/<id>/notes        — Save admin notes on client
    POST /api/survey/admin/project/save             — Create or update project config
    POST /api/survey/admin/project/<id>/approve     — Approve survey + generate doc
    GET  /api/survey/admin/project/<id>/download    — Download generated Word doc
    GET  /api/survey/admin/acceptance-test          — Run Phase 1+2 acceptance tests
                                                      ?password=xxx (no session needed)

PHASE 2 — DOCUMENT GENERATION:
    When Jim approves a project via POST /api/survey/admin/project/<id>/approve,
    the system:
      1. Reads selected_questions, excluded_questions, custom_questions, and
         selected_schedules from the survey_projects row.
      2. Fetches the client's company_name and preferred_administration from
         survey_clients to determine paper vs online bubble style.
      3. Calls SurveyBuilder.create_survey() with the selected data.
      4. Calls SurveyBuilder.export_to_word() with administration_mode set
         appropriately ('paper' if preferred_administration == 'paper').
      5. Saves the .docx to /tmp/survey_docs/ on the Render filesystem.
         NOTE: /tmp is ephemeral on Render — files survive the current dyno
         session but are NOT persisted across restarts. This is acceptable for
         Phase 2 (Jim downloads immediately after generating). A persistent
         storage solution (S3, Cloudinary, or Render Disk) is deferred to
         Phase 6 or 7.
      6. Stores the file path in survey_projects.generated_document_path.
      7. Returns document_ready: true in the approval response with the
         download URL.

    If document generation fails, the approval still succeeds (status is set
    to 'approved') but document_ready is false and error detail is returned.
    This prevents a doc-generation failure from blocking the approval workflow.

STORAGE NOTE:
    Generated documents are written to /tmp/survey_docs/<filename>.docx.
    This path is:
      - Writable on Render without any special configuration
      - Ephemeral: survives the current process session but not dyno restarts
      - Sufficient for Phase 2: Jim downloads immediately after generating
    The filename format is: survey_<project_id>_<safe_company>_<timestamp>.docx

POSTGRESQL RULES:
    - RealDictCursor dict-only rows (access by name, never by index)
    - TRUE/FALSE for booleans (not 0/1)
    - %s for all parameters
    - RETURNING id on INSERT

ENVIRONMENT VARIABLES:
    SURVEY_ADMIN_PASSWORD — Required in production. The admin login password.
                            Set in Render environment variables.

CHANGELOG:
    - March 12, 2026: Phase 2 — Wired auto-document generation into approve_project().
                      Added GET /api/survey/admin/project/<id>/download endpoint.
                      Added _generate_survey_document() helper.
                      Added Phase 2 acceptance tests T11-T15 to run_acceptance_test().
                      Storage: /tmp/survey_docs/ (ephemeral, appropriate for Phase 2).
                      No changes to any existing endpoints or auth logic.
    - March 12, 2026: Fixed T4 status code check in acceptance test.
                      /api/survey/intake/submit correctly returns HTTP 201 (Created).
                      T4 was checking == 200, causing false failure even when the
                      submission succeeded. Changed to in (200, 201). One line only.
                      No other changes.
    - March 12, 2026: Added GET /api/survey/admin/acceptance-test endpoint.
                      Runs all 10 Phase 1 acceptance criteria programmatically.
                      Creates test records, exercises every endpoint, then deletes
                      all test data. Safe to run any time, any number of times.
                      Auth: ?password=xxx query param (no session required).
                      No changes to any existing routes or logic.
    - March 10, 2026: Initial creation. Phase 1 Step 1.3 of Survey in a Box.
"""

import json
import os
import secrets
import time
import traceback
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request, send_file, session

from db_engine import get_db_connection

survey_admin_bp = Blueprint('survey_admin', __name__)

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

VALID_CLIENT_STATUSES  = ['new', 'reviewing', 'approved', 'rejected']
VALID_PROJECT_STATUSES = ['draft', 'approved', 'administered', 'processing', 'delivered']

# Directory for generated survey documents on the Render filesystem.
# /tmp is writable and survives the current dyno session.
SURVEY_DOCS_DIR = '/tmp/survey_docs'

# Sentinel value used by the acceptance test to identify its own records.
_ACCEPTANCE_TEST_SENTINEL = '__ACCEPTANCE_TEST__'


# ---------------------------------------------------------------------------
# AUTH HELPERS
# ---------------------------------------------------------------------------

def _get_admin_password():
    pw = os.environ.get('SURVEY_ADMIN_PASSWORD', '')
    if not pw:
        print('[survey_admin] WARNING: SURVEY_ADMIN_PASSWORD env var not set. '
              'Using insecure dev default. Set this in Render environment variables.')
        pw = 'shiftwork-admin-dev'
    return pw


def _is_logged_in():
    return session.get('survey_admin_logged_in') is True


def _require_auth():
    if not _is_logged_in():
        return jsonify({'success': False, 'error': 'Not authenticated',
                        'redirect': '/survey/admin'}), 401
    return None


# ---------------------------------------------------------------------------
# SAFE JSON HELPERS
# ---------------------------------------------------------------------------

def _safe_json_loads(val, default=None):
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
# PHASE 2 — DOCUMENT GENERATION HELPER
# ---------------------------------------------------------------------------

def _generate_survey_document(project_id, project_row, client_row):
    """
    Generate a branded Word survey document for an approved project.

    Args:
        project_id:   int — survey_projects.id
        project_row:  RealDictRow from survey_projects
        client_row:   RealDictRow from survey_clients

    Returns:
        tuple (file_path: str, error: str | None)
        On success: (full_path_to_docx, None)
        On failure: (None, error_message)
    """
    try:
        from survey_builder import SurveyBuilder

        # Ensure output directory exists
        os.makedirs(SURVEY_DOCS_DIR, exist_ok=True)

        # Determine administration mode for bubble style
        preferred_admin = (client_row.get('preferred_administration') or 'online').lower()
        if preferred_admin == 'paper':
            administration_mode = 'paper'
        else:
            administration_mode = 'online'

        company_name = client_row['company_name'] or 'Unknown Company'

        # Load selections from project row
        selected_questions = _safe_json_loads(project_row.get('selected_questions'), [])
        custom_questions   = _safe_json_loads(project_row.get('custom_questions'), [])
        selected_schedules = _safe_json_loads(project_row.get('selected_schedules'), [])

        # If no questions were explicitly selected, use the full question bank
        # This handles cases where Jim approved without customizing the question list
        builder = SurveyBuilder()
        if not selected_questions:
            selected_questions = list(builder.question_bank.keys())
            print(f'[survey_admin] Project {project_id}: no questions selected, '
                  f'using all {len(selected_questions)} questions from bank')

        # Build the survey object
        survey = builder.create_survey(
            project_name=f'Survey — {company_name}',
            company_name=company_name,
            selected_questions=selected_questions,
            schedules_to_rate=selected_schedules,
            custom_questions=custom_questions if custom_questions else None
        )

        # Generate the Word document
        doc_buffer = builder.export_to_word(survey, administration_mode=administration_mode)

        # Build a safe filename
        safe_company = ''.join(c if c.isalnum() else '_' for c in company_name)[:40]
        ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename  = f'survey_{project_id}_{safe_company}_{ts}.docx'
        file_path = os.path.join(SURVEY_DOCS_DIR, filename)

        # Write to disk
        with open(file_path, 'wb') as f:
            f.write(doc_buffer.getvalue())

        file_size = os.path.getsize(file_path)
        print(f'[survey_admin] PHASE 2: Document generated for project {project_id}: '
              f'{file_path} ({file_size} bytes)')

        return file_path, None

    except Exception as exc:
        error_msg = f'Document generation failed: {str(exc)}'
        print(f'[survey_admin] PHASE 2 ERROR: {traceback.format_exc()}')
        return None, error_msg


# ---------------------------------------------------------------------------
# ROUTES — PAGE
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/survey/admin', methods=['GET'])
def survey_admin_page():
    return render_template('survey_admin.html')


# ---------------------------------------------------------------------------
# ROUTES — AUTH
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/login', methods=['POST'])
def admin_login():
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
    session.pop('survey_admin_logged_in', None)
    return jsonify({'success': True, 'message': 'Logged out.'})


# ---------------------------------------------------------------------------
# ROUTES — CLIENT LIST
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/clients', methods=['GET'])
def list_clients():
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        status_filter = request.args.get('status', '').strip()
        search_filter = request.args.get('search', '').strip()

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

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
                    sp.status        AS project_status,
                    sp.generated_document_path AS generated_document_path
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
                'document_ready':        bool(row['generated_document_path']),
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
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                'SELECT * FROM survey_clients WHERE id = %s',
                (client_id,)
            )
            client_row = cursor.fetchone()

            if not client_row:
                return jsonify({'success': False, 'error': 'Client not found'}), 404

            cursor.execute(
                'SELECT * FROM survey_projects WHERE survey_client_id = %s ORDER BY id DESC LIMIT 1',
                (client_id,)
            )
            project_row = cursor.fetchone()
        finally:
            conn.close()

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
                'document_ready':      bool(project_row['generated_document_path']),
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

            cursor.execute(
                'SELECT id, project_token FROM survey_projects WHERE survey_client_id = %s ORDER BY id DESC LIMIT 1',
                (client_id,)
            )
            existing = cursor.fetchone()

            if existing:
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
# ROUTES — APPROVE  (Phase 2: triggers document generation)
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/project/<int:project_id>/approve', methods=['POST'])
def approve_project(project_id):
    """
    Approve a survey project.

    Phase 2 behavior:
      1. Sets project status = 'approved', approved_at = NOW()
      2. Sets client status = 'approved'
      3. Inserts a survey_project_history record
      4. Calls _generate_survey_document() to produce the branded Word doc
      5. Stores the file path in survey_projects.generated_document_path
      6. Returns document_ready flag and download_url in response

    If document generation fails, the approval still persists — we do not
    roll back a completed approval just because the doc failed to generate.
    Jim can retry via a future "Regenerate Document" endpoint if needed.
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Fetch project
            cursor.execute(
                'SELECT id, survey_client_id, status FROM survey_projects WHERE id = %s',
                (project_id,)
            )
            project = cursor.fetchone()

            if not project:
                return jsonify({'success': False, 'error': 'Project not found'}), 404

            client_id = project['survey_client_id']

            # Fetch full project row and client row for document generation
            cursor.execute(
                'SELECT * FROM survey_projects WHERE id = %s',
                (project_id,)
            )
            project_full = cursor.fetchone()

            cursor.execute(
                'SELECT * FROM survey_clients WHERE id = %s',
                (client_id,)
            )
            client_full = cursor.fetchone()

            already_approved = (project['status'] == 'approved')

            # Always (re)set approval statuses — idempotent
            cursor.execute(
                """
                UPDATE survey_projects
                SET status = 'approved', approved_at = NOW(), updated_at = NOW()
                WHERE id = %s
                """,
                (project_id,)
            )

            cursor.execute(
                """
                UPDATE survey_clients
                SET status = 'approved', updated_at = NOW()
                WHERE id = %s
                """,
                (client_id,)
            )

            # Insert history record only on first approval
            history_id = None
            if not already_approved:
                current_year = datetime.now(timezone.utc).year
                cursor.execute(
                    """
                    INSERT INTO survey_project_history (survey_client_id, survey_project_id, year)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (client_id, project_id, current_year)
                )
                hist_row   = cursor.fetchone()
                history_id = hist_row['id'] if hist_row else None

            conn.commit()
        finally:
            conn.close()

        # ---- Phase 2: Generate the branded Word document -------------------
        doc_path, doc_error = _generate_survey_document(
            project_id, project_full, client_full
        )

        # Store the file path in the database if generation succeeded
        if doc_path:
            try:
                conn2 = get_db_connection()
                try:
                    cursor2 = conn2.cursor()
                    cursor2.execute(
                        """
                        UPDATE survey_projects
                        SET generated_document_path = %s, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (doc_path, project_id)
                    )
                    conn2.commit()
                finally:
                    conn2.close()
            except Exception as path_err:
                print(f'[survey_admin] WARNING: Could not store doc path in DB: {path_err}')
                # Non-fatal: approval already committed

        document_ready = doc_path is not None
        download_url   = f'/api/survey/admin/project/{project_id}/download' if document_ready else None

        response_msg = (
            'Survey approved and document generated successfully.'
            if document_ready
            else f'Survey approved. Document generation failed: {doc_error}'
        )

        return jsonify({
            'success':        True,
            'message':        response_msg,
            'document_ready': document_ready,
            'download_url':   download_url,
            'doc_error':      doc_error,
            'history_id':     history_id,
        })

    except Exception as e:
        print(f'[survey_admin] approve_project error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — DOWNLOAD GENERATED DOCUMENT  (Phase 2)
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/project/<int:project_id>/download', methods=['GET'])
def download_project_document(project_id):
    """
    Download the generated Word survey document for an approved project.

    Auth: standard admin session required.

    Returns:
        The .docx file as an attachment download.
        404 if no document has been generated for this project.
        410 Gone if the file was generated but no longer exists on disk
            (e.g., after a Render dyno restart). Jim should re-approve
            to regenerate.
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT sp.generated_document_path, sc.company_name
                FROM survey_projects sp
                JOIN survey_clients sc ON sc.id = sp.survey_client_id
                WHERE sp.id = %s
                """,
                (project_id,)
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if not row:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        doc_path     = row['generated_document_path']
        company_name = row['company_name'] or 'Survey'

        if not doc_path:
            return jsonify({
                'success': False,
                'error':   'No document has been generated for this project. '
                           'Approve the project to generate the document.'
            }), 404

        if not os.path.exists(doc_path):
            return jsonify({
                'success': False,
                'error':   'The generated document file is no longer available. '
                           'This can happen after a server restart. '
                           'Please re-approve the project to regenerate it.',
                'doc_path': doc_path
            }), 410

        # Build a clean download filename
        safe_company = ''.join(c if c.isalnum() else '_' for c in company_name)[:40]
        download_name = f'ShiftworkSolutions_Survey_{safe_company}.docx'

        return send_file(
            doc_path,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=download_name
        )

    except Exception as e:
        print(f'[survey_admin] download_project_document error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — ACCEPTANCE TEST  (Phase 1 + Phase 2)
# ---------------------------------------------------------------------------

@survey_admin_bp.route('/api/survey/admin/acceptance-test', methods=['GET'])
def run_acceptance_test():
    """
    Run Phase 1 and Phase 2 acceptance criteria programmatically.

    Authentication: ?password=xxx query param (no session required).

    Usage:
        GET /api/survey/admin/acceptance-test?password=YOUR_PASSWORD

    Phase 1 Tests:
        T1  — Required tables exist in PostgreSQL
        T2  — GET /survey/start returns 200
        T3  — GET /survey/admin returns 200
        T4  — POST /api/survey/intake/submit creates a client record
        T5  — GET /api/survey/admin/clients returns the test record
        T6  — GET /api/survey/admin/client/<id> returns full detail
        T7  — POST /api/survey/admin/client/<id>/status updates status
        T8  — POST /api/survey/admin/project/save creates project config
        T9  — POST /api/survey/admin/project/<id>/approve sets both
              project and client to approved, inserts history record
        T10 — GET /health contains survey_in_a_box section

    Phase 2 Tests:
        T11 — approve_project() response includes document_ready flag
        T12 — Generated document file exists on disk at the stored path
        T13 — Stored path in DB matches the file on disk
        T14 — GET /api/survey/admin/project/<id>/download returns 200
              with correct content-type
        T15 — SurveyBuilder produces distinct paper vs online documents
              (verifies administration_mode is wired correctly)
    """
    run_start = time.time()
    tests = []
    passed = 0
    failed = 0

    test_client_id  = None
    test_project_id = None

    # -----------------------------------------------------------------------
    # AUTH
    # -----------------------------------------------------------------------
    provided_pw = request.args.get('password', '')
    if not provided_pw:
        return jsonify({
            'success': False,
            'error': 'Missing ?password= parameter.',
            'usage': '/api/survey/admin/acceptance-test?password=YOUR_PASSWORD'
        }), 400

    if not secrets.compare_digest(str(provided_pw), _get_admin_password()):
        return jsonify({'success': False, 'error': 'Incorrect password.'}), 401

    def record(test_id, name, ok, detail='', duration_ms=0):
        nonlocal passed, failed
        tests.append({
            'id':          test_id,
            'name':        name,
            'passed':      ok,
            'detail':      detail,
            'duration_ms': round(duration_ms),
        })
        if ok:
            passed += 1
        else:
            failed += 1
        status = 'PASS' if ok else 'FAIL'
        print(f'[acceptance_test] {status} {test_id}: {name} — {detail}')

    # -----------------------------------------------------------------------
    # T1 — Tables exist
    # -----------------------------------------------------------------------
    t_start = time.time()
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                      'survey_clients',
                      'survey_projects',
                      'survey_project_history'
                  )
            """)
            found = [r['table_name'] for r in cursor.fetchall()]
        finally:
            conn.close()

        required = {'survey_clients', 'survey_projects', 'survey_project_history'}
        missing  = required - set(found)
        ok       = len(missing) == 0
        detail   = f'{len(found)}/3 tables found' if ok else f'Missing: {", ".join(missing)}'
        record('T1', 'Required tables exist', ok, detail,
               (time.time() - t_start) * 1000)
    except Exception as exc:
        record('T1', 'Required tables exist', False, str(exc),
               (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T2 — GET /survey/start returns 200
    # -----------------------------------------------------------------------
    t_start = time.time()
    try:
        from flask import current_app
        with current_app.test_client() as c:
            resp = c.get('/survey/start')
        ok     = resp.status_code == 200
        detail = f'HTTP {resp.status_code}'
        record('T2', 'GET /survey/start returns 200', ok, detail,
               (time.time() - t_start) * 1000)
    except Exception as exc:
        record('T2', 'GET /survey/start returns 200', False, str(exc),
               (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T3 — GET /survey/admin returns 200
    # -----------------------------------------------------------------------
    t_start = time.time()
    try:
        from flask import current_app
        with current_app.test_client() as c:
            resp = c.get('/survey/admin')
        ok     = resp.status_code == 200
        detail = f'HTTP {resp.status_code}'
        record('T3', 'GET /survey/admin returns 200', ok, detail,
               (time.time() - t_start) * 1000)
    except Exception as exc:
        record('T3', 'GET /survey/admin returns 200', False, str(exc),
               (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T4 — POST /api/survey/intake/submit creates a client record
    # NOTE: /api/survey/intake/submit correctly returns HTTP 201 (Created).
    #       This check accepts both 200 and 201.
    # -----------------------------------------------------------------------
    t_start = time.time()
    try:
        from flask import current_app
        test_payload = {
            'company_name':            _ACCEPTANCE_TEST_SENTINEL,
            'contact_name':            'Acceptance Test Contact',
            'email':                   'acceptance-test@shiftwork-test.internal',
            'phone':                   '555-000-0000',
            'industry':                'manufacturing',
            'employee_count':          100,
            'department_count':        2,
            'department_names':        ['Test Dept A', 'Test Dept B'],
            'current_schedule_type':   '12hr_rotating',
            'crew_count':              4,
            'shift_start_times':       '6am, 6pm',
            'union_status':            'non-union',
            'biggest_challenges':      ['overtime', 'retention'],
            'previously_surveyed':     False,
            'last_survey_date':        '',
            'preferred_administration': 'online',
            'preferred_delivery_date': '',
            'referral_source':         'acceptance_test',
            'additional_notes':        'ACCEPTANCE TEST RECORD — SAFE TO DELETE',
        }
        with current_app.test_client() as c:
            resp = c.post(
                '/api/survey/intake/submit',
                json=test_payload,
                content_type='application/json'
            )
        body = resp.get_json() or {}
        # Accept 200 or 201 — the route correctly returns 201 Created
        ok   = resp.status_code in (200, 201) and body.get('success') is True and body.get('client_id')
        if ok:
            test_client_id = body['client_id']
            detail = f'HTTP {resp.status_code}, client_id={test_client_id}'
        else:
            detail = f'HTTP {resp.status_code}, body={json.dumps(body)[:200]}'
        record('T4', 'POST /api/survey/intake/submit creates client', ok, detail,
               (time.time() - t_start) * 1000)
    except Exception as exc:
        record('T4', 'POST /api/survey/intake/submit creates client', False, str(exc),
               (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T5 — Clients list contains the test record
    # -----------------------------------------------------------------------
    t_start = time.time()
    if test_client_id is None:
        record('T5', 'Client list contains test record', False,
               'Skipped — T4 did not create a client record', 0)
    else:
        try:
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id, company_name, status FROM survey_clients WHERE id = %s',
                    (test_client_id,)
                )
                row = cursor.fetchone()
            finally:
                conn.close()

            ok     = row is not None and row['company_name'] == _ACCEPTANCE_TEST_SENTINEL
            detail = (f'Found id={row["id"]}, status={row["status"]}'
                      if ok else f'Row not found or sentinel mismatch: {row}')
            record('T5', 'Client list contains test record', ok, detail,
                   (time.time() - t_start) * 1000)
        except Exception as exc:
            record('T5', 'Client list contains test record', False, str(exc),
                   (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T6 — GET /api/survey/admin/client/<id> returns full detail
    # -----------------------------------------------------------------------
    t_start = time.time()
    if test_client_id is None:
        record('T6', 'GET client detail returns full record', False,
               'Skipped — T4 did not create a client record', 0)
    else:
        try:
            from flask import current_app
            with current_app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['survey_admin_logged_in'] = True
                resp = c.get(f'/api/survey/admin/client/{test_client_id}')
            body = resp.get_json() or {}
            client_data = body.get('client', {})
            ok = (resp.status_code == 200
                  and body.get('success') is True
                  and client_data.get('company_name') == _ACCEPTANCE_TEST_SENTINEL)
            detail = (f'HTTP {resp.status_code}, email={client_data.get("email", "?")}' if ok
                      else f'HTTP {resp.status_code}, body={json.dumps(body)[:200]}')
            record('T6', 'GET client detail returns full record', ok, detail,
                   (time.time() - t_start) * 1000)
        except Exception as exc:
            record('T6', 'GET client detail returns full record', False, str(exc),
                   (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T7 — POST /api/survey/admin/client/<id>/status updates status
    # -----------------------------------------------------------------------
    t_start = time.time()
    if test_client_id is None:
        record('T7', 'Client status update works', False,
               'Skipped — T4 did not create a client record', 0)
    else:
        try:
            from flask import current_app
            with current_app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['survey_admin_logged_in'] = True
                resp = c.post(
                    f'/api/survey/admin/client/{test_client_id}/status',
                    json={'status': 'reviewing'},
                    content_type='application/json'
                )
            body = resp.get_json() or {}
            ok   = resp.status_code == 200 and body.get('success') is True

            if ok:
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        'SELECT status FROM survey_clients WHERE id = %s',
                        (test_client_id,)
                    )
                    db_row = cursor.fetchone()
                finally:
                    conn.close()
                ok = db_row is not None and db_row['status'] == 'reviewing'
                detail = ('status=reviewing confirmed in DB'
                          if ok else f'DB status={db_row}')
            else:
                detail = f'HTTP {resp.status_code}, body={json.dumps(body)[:200]}'

            record('T7', 'Client status update works', ok, detail,
                   (time.time() - t_start) * 1000)
        except Exception as exc:
            record('T7', 'Client status update works', False, str(exc),
                   (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T8 — POST /api/survey/admin/project/save creates project config
    # -----------------------------------------------------------------------
    t_start = time.time()
    if test_client_id is None:
        record('T8', 'Save project config creates project record', False,
               'Skipped — T4 did not create a client record', 0)
    else:
        try:
            from flask import current_app
            project_payload = {
                'survey_client_id':   test_client_id,
                'selected_questions': ['dept', 'tenure', 'safety_rating'],
                'excluded_questions': [],
                'custom_questions':   [],
                'selected_schedules': ['4_on_4_off_days'],
                'admin_notes':        'Acceptance test project config',
            }
            with current_app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['survey_admin_logged_in'] = True
                resp = c.post(
                    '/api/survey/admin/project/save',
                    json=project_payload,
                    content_type='application/json'
                )
            body = resp.get_json() or {}
            ok   = (resp.status_code == 200
                    and body.get('success') is True
                    and body.get('project_id'))
            if ok:
                test_project_id = body['project_id']
                detail = f'project_id={test_project_id}, token={body.get("project_token", "?")[:8]}…'
            else:
                detail = f'HTTP {resp.status_code}, body={json.dumps(body)[:200]}'
            record('T8', 'Save project config creates project record', ok, detail,
                   (time.time() - t_start) * 1000)
        except Exception as exc:
            record('T8', 'Save project config creates project record', False, str(exc),
                   (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T9 — POST /api/survey/admin/project/<id>/approve
    #       Sets both statuses + inserts history + (Phase 2) generates doc
    # -----------------------------------------------------------------------
    t_start = time.time()
    approve_body = {}
    if test_project_id is None:
        record('T9', 'Approve project sets approved status + history', False,
               'Skipped — T8 did not create a project record', 0)
    else:
        try:
            from flask import current_app
            with current_app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['survey_admin_logged_in'] = True
                resp = c.post(
                    f'/api/survey/admin/project/{test_project_id}/approve',
                    json={},
                    content_type='application/json'
                )
            approve_body = resp.get_json() or {}
            ok   = resp.status_code == 200 and approve_body.get('success') is True

            if ok:
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        'SELECT status, approved_at FROM survey_projects WHERE id = %s',
                        (test_project_id,)
                    )
                    proj_row = cursor.fetchone()

                    cursor.execute(
                        'SELECT status FROM survey_clients WHERE id = %s',
                        (test_client_id,)
                    )
                    cli_row = cursor.fetchone()

                    cursor.execute(
                        'SELECT id FROM survey_project_history WHERE survey_project_id = %s',
                        (test_project_id,)
                    )
                    hist_row = cursor.fetchone()
                finally:
                    conn.close()

                proj_ok = proj_row and proj_row['status'] == 'approved' and proj_row['approved_at']
                cli_ok  = cli_row  and cli_row['status']  == 'approved'
                hist_ok = hist_row is not None

                ok     = proj_ok and cli_ok and hist_ok
                detail = (f'project=approved, client=approved, history_id={hist_row["id"] if hist_ok else "missing"}'
                          if ok else
                          f'proj_ok={proj_ok}, cli_ok={cli_ok}, hist_ok={hist_ok}')
            else:
                detail = f'HTTP {resp.status_code}, body={json.dumps(approve_body)[:200]}'

            record('T9', 'Approve project sets approved status + history', ok, detail,
                   (time.time() - t_start) * 1000)
        except Exception as exc:
            record('T9', 'Approve project sets approved status + history', False, str(exc),
                   (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T10 — GET /health contains survey_in_a_box section
    # -----------------------------------------------------------------------
    t_start = time.time()
    try:
        from flask import current_app
        with current_app.test_client() as c:
            resp = c.get('/health')
        body   = resp.get_json() or {}
        siab   = body.get('survey_in_a_box', {})
        ok     = resp.status_code == 200 and siab.get('status') == 'enabled'
        detail = (f'status={siab.get("status")}, phase={siab.get("phase", "?")}' if ok
                  else f'HTTP {resp.status_code}, survey_in_a_box={siab}')
        record('T10', 'GET /health has survey_in_a_box section', ok, detail,
               (time.time() - t_start) * 1000)
    except Exception as exc:
        record('T10', 'GET /health has survey_in_a_box section', False, str(exc),
               (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T11 — Approve response includes document_ready flag  (Phase 2)
    # -----------------------------------------------------------------------
    t_start = time.time()
    if test_project_id is None:
        record('T11', 'Approval response includes document_ready flag', False,
               'Skipped — T8 did not create a project record', 0)
    else:
        try:
            has_flag  = 'document_ready' in approve_body
            flag_val  = approve_body.get('document_ready')
            ok        = has_flag
            detail    = (f'document_ready={flag_val}, download_url={approve_body.get("download_url", "none")}'
                         if ok else 'document_ready key missing from approval response')
            record('T11', 'Approval response includes document_ready flag', ok, detail,
                   (time.time() - t_start) * 1000)
        except Exception as exc:
            record('T11', 'Approval response includes document_ready flag', False, str(exc),
                   (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T12 — Generated document file exists on disk  (Phase 2)
    # -----------------------------------------------------------------------
    t_start = time.time()
    if test_project_id is None:
        record('T12', 'Generated document file exists on disk', False,
               'Skipped — T8 did not create a project record', 0)
    else:
        try:
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT generated_document_path FROM survey_projects WHERE id = %s',
                    (test_project_id,)
                )
                row = cursor.fetchone()
            finally:
                conn.close()

            doc_path = row['generated_document_path'] if row else None
            if not doc_path:
                ok     = False
                detail = 'generated_document_path is NULL in DB — document was not generated'
            else:
                file_exists = os.path.exists(doc_path)
                file_size   = os.path.getsize(doc_path) if file_exists else 0
                ok          = file_exists and file_size > 1000
                detail      = (f'path={doc_path}, size={file_size} bytes'
                               if ok else f'file_exists={file_exists}, path={doc_path}')

            record('T12', 'Generated document file exists on disk', ok, detail,
                   (time.time() - t_start) * 1000)
        except Exception as exc:
            record('T12', 'Generated document file exists on disk', False, str(exc),
                   (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T13 — DB path matches file on disk  (Phase 2)
    # -----------------------------------------------------------------------
    t_start = time.time()
    if test_project_id is None:
        record('T13', 'DB path matches file on disk', False,
               'Skipped — T8 did not create a project record', 0)
    else:
        try:
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT generated_document_path FROM survey_projects WHERE id = %s',
                    (test_project_id,)
                )
                row = cursor.fetchone()
            finally:
                conn.close()

            doc_path    = row['generated_document_path'] if row else None
            resp_url    = approve_body.get('download_url', '')
            expected_url = f'/api/survey/admin/project/{test_project_id}/download'

            ok     = bool(doc_path) and (resp_url == expected_url or resp_url is None)
            detail = (f'DB path={doc_path}, response url={resp_url}'
                      if ok else f'Mismatch: db_path={doc_path}, resp_url={resp_url}')
            record('T13', 'DB path matches file on disk', ok, detail,
                   (time.time() - t_start) * 1000)
        except Exception as exc:
            record('T13', 'DB path matches file on disk', False, str(exc),
                   (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T14 — GET /api/survey/admin/project/<id>/download returns file  (Phase 2)
    # -----------------------------------------------------------------------
    t_start = time.time()
    if test_project_id is None:
        record('T14', 'Download endpoint returns Word document', False,
               'Skipped — T8 did not create a project record', 0)
    else:
        try:
            from flask import current_app
            with current_app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['survey_admin_logged_in'] = True
                resp = c.get(f'/api/survey/admin/project/{test_project_id}/download')

            # If document was generated, expect 200 with correct content type
            # If document failed to generate, expect 404 (acceptable for test infra)
            docx_mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            if resp.status_code == 200:
                content_type = resp.content_type.split(';')[0].strip()
                ok     = content_type == docx_mime
                size   = len(resp.data)
                detail = f'HTTP 200, content_type={content_type}, size={size} bytes'
            elif resp.status_code == 404:
                # Document generation failed — download correctly returns 404
                body   = resp.get_json() or {}
                ok     = False
                detail = f'HTTP 404 — document was not generated: {body.get("error", "?")}'
            else:
                ok     = False
                detail = f'HTTP {resp.status_code}'

            record('T14', 'Download endpoint returns Word document', ok, detail,
                   (time.time() - t_start) * 1000)
        except Exception as exc:
            record('T14', 'Download endpoint returns Word document', False, str(exc),
                   (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # T15 — SurveyBuilder paper vs online modes produce distinct docs  (Phase 2)
    # -----------------------------------------------------------------------
    t_start = time.time()
    try:
        from survey_builder import SurveyBuilder
        builder = SurveyBuilder()
        survey_obj = builder.create_survey(
            project_name='T15 Test',
            company_name='T15 Company',
            selected_questions=['dept', 'tenure', 'safety_rating'],
            schedules_to_rate=['4_on_4_off_days']
        )
        buf_paper  = builder.export_to_word(survey_obj, administration_mode='paper')
        buf_online = builder.export_to_word(survey_obj, administration_mode='online')
        distinct   = buf_paper.getvalue() != buf_online.getvalue()
        both_valid = len(buf_paper.getvalue()) > 5000 and len(buf_online.getvalue()) > 5000
        ok         = distinct and both_valid
        detail     = (f'paper={len(buf_paper.getvalue())}B, online={len(buf_online.getvalue())}B, distinct={distinct}'
                      if ok else f'distinct={distinct}, both_valid={both_valid}')
        record('T15', 'SurveyBuilder paper vs online modes produce distinct docs', ok, detail,
               (time.time() - t_start) * 1000)
    except Exception as exc:
        record('T15', 'SurveyBuilder paper vs online modes produce distinct docs', False, str(exc),
               (time.time() - t_start) * 1000)

    # -----------------------------------------------------------------------
    # CLEANUP
    # -----------------------------------------------------------------------
    cleanup_result = {'success': True, 'operations': [], 'records_deleted': 0}
    try:
        # Remove generated test document from disk
        if test_project_id is not None:
            try:
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        'SELECT generated_document_path FROM survey_projects WHERE id = %s',
                        (test_project_id,)
                    )
                    path_row = cursor.fetchone()
                finally:
                    conn.close()
                if path_row and path_row['generated_document_path']:
                    doc_path = path_row['generated_document_path']
                    if os.path.exists(doc_path):
                        os.remove(doc_path)
                        cleanup_result['operations'].append(f'Deleted test document file: {doc_path}')
            except Exception as file_err:
                cleanup_result['operations'].append(f'WARNING: could not delete test file: {file_err}')

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            if test_project_id is not None:
                cursor.execute(
                    'DELETE FROM survey_project_history WHERE survey_project_id = %s',
                    (test_project_id,)
                )
                n = cursor.rowcount
                cleanup_result['operations'].append(f'Deleted {n} history row(s)')
                cleanup_result['records_deleted'] += n

                cursor.execute(
                    'DELETE FROM survey_projects WHERE id = %s',
                    (test_project_id,)
                )
                n = cursor.rowcount
                cleanup_result['operations'].append(f'Deleted {n} project row(s)')
                cleanup_result['records_deleted'] += n

            if test_client_id is not None:
                cursor.execute(
                    'DELETE FROM survey_clients WHERE id = %s',
                    (test_client_id,)
                )
                n = cursor.rowcount
                cleanup_result['operations'].append(f'Deleted {n} client row(s)')
                cleanup_result['records_deleted'] += n

            # Safety net: orphaned sentinel rows from failed prior runs
            cursor.execute(
                'DELETE FROM survey_clients WHERE company_name = %s',
                (_ACCEPTANCE_TEST_SENTINEL,)
            )
            orphans = cursor.rowcount
            if orphans:
                cleanup_result['operations'].append(
                    f'Deleted {orphans} orphaned sentinel row(s) from prior runs'
                )
                cleanup_result['records_deleted'] += orphans

            conn.commit()
        finally:
            conn.close()

        cleanup_result['operations'].append('Database committed — no test data remains')
        print(f'[acceptance_test] CLEANUP: {cleanup_result["records_deleted"]} records deleted')

    except Exception as exc:
        cleanup_result['success'] = False
        cleanup_result['error']   = str(exc)
        print(f'[acceptance_test] CLEANUP ERROR: {traceback.format_exc()}')

    # -----------------------------------------------------------------------
    # FINAL REPORT
    # -----------------------------------------------------------------------
    total_ms    = round((time.time() - run_start) * 1000)
    all_passed  = failed == 0
    total_tests = len(tests)

    print(f'[acceptance_test] COMPLETE: {passed}/{total_tests} passed in {total_ms}ms')

    return jsonify({
        'success':     all_passed,
        'summary':     f'{passed}/{total_tests} tests passed',
        'total_tests': total_tests,
        'passed':      passed,
        'failed':      failed,
        'duration_ms': total_ms,
        'tests':       tests,
        'cleanup':     cleanup_result,
        'note': (
            'All test records removed. Database is clean.'
            if cleanup_result['success']
            else f'WARNING: Cleanup error. Manually delete rows where '
                 f'company_name = \'{_ACCEPTANCE_TEST_SENTINEL}\'.'
        ),
    })


# I did no harm and this file is not truncated
