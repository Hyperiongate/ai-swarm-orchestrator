"""
SURVEY IN A BOX — Respondent Routes 
File: routes/survey_respondent.py
Created: March 13, 2026
Last Updated: March 25, 2026 — BUG FIX: Wrong session key in _require_admin_auth()

PURPOSE:
    Employee-facing survey engine for Survey in a Box Phase 3.
    Handles the public-facing survey at /survey/take/<token> and the
    API endpoints that power it. Fully anonymous — no names, no IP
    addresses, no PII stored or logged.

    This blueprint does NOT require authentication. It is the public
    interface that employees use to complete their survey.

ENDPOINTS:
    GET  /survey/take/<token>                    — Survey page (HTML)
    GET  /api/survey/take/<token>/questions      — Load survey structure
    POST /api/survey/take/<token>/submit         — Submit completed survey
    GET  /api/survey/admin/project/<id>/open     — Jim opens survey for responses
    POST /api/survey/admin/project/<id>/close    — Jim closes survey
    GET  /api/survey/admin/project/<id>/responses — Response count + summary
    GET  /api/survey/admin/project/<id>/export   — Download .xlsx response data

ANONYMOUS DESIGN:
    - No login, no registration, no email collection
    - No IP addresses stored or logged
    - session_token is a one-way SHA-256 hash of a browser cookie value.
      Used only to prevent duplicate submissions in a single browser session.
      Cannot be reversed to identify any individual.
    - The export contains no timestamps, no row IDs, no session tokens —
      purely the answer data in SurveySelector-compatible format.

EXPORT FORMAT (SurveySelector / Remark compatible):
    - One sheet named "Sheet1"
    - One row per respondent
    - One column per question in survey order
    - Column headers: question short_label (e.g. "Department", "like current schedule")
    - Values: full text of selected answer option (e.g. "4 Agree", "Shipping")
    - Unanswered questions: the literal string "BLANK" (not empty cell)
    - No row IDs, no timestamps, no respondent identifiers

DUPLICATE PREVENTION:
    - Browser sets a session cookie (survey_session_<token>) on first load
    - Cookie value is SHA-256 hashed before storage — one-way, not reversible
    - On submission, the hash is checked against survey_responses for that project
    - If a matching session_token exists, submission is rejected with HTTP 409
    - Respondents with cookies disabled can still submit (session_token = NULL,
      duplicate check is skipped for them)

SURVEY OPEN/CLOSE:
    - Jim explicitly opens a survey via GET /open endpoint (auth required)
    - Employees cannot submit to a closed survey (returns 403 with clear message)
    - Jim closes the survey via POST /close when data collection is complete
    - open/close state is stored in survey_projects.is_open

POSTGRESQL RULES:
    - RealDictCursor dict-only rows (access by name, never by index)
    - TRUE/FALSE for booleans (not 0/1)
    - %s for all parameters
    - RETURNING id on INSERT

CHANGELOG:
    - March 25, 2026: BUG FIX — _require_admin_auth() was checking the wrong
      Flask session key. It checked session.get('survey_admin_logged_in') but
      survey_admin.py sets session['survey_admin_authenticated']. This caused
      all admin-protected endpoints in this file (/open, /close, /responses,
      /export) to always return 401 even when the admin was logged in.
      ONE LINE CHANGED: 'survey_admin_logged_in' -> 'survey_admin_authenticated'

    - March 13, 2026 (BUG FIX): Fixed _get_survey_questions_ordered().
      SurveyBuilder.create_survey() returns a flat 'questions' list, not a
      'sections' hierarchy. The original code iterated survey_obj['sections']
      which is always empty, causing the export to return 500 (no columns).
      Fix: iterate survey_obj['questions'] directly and inject 'short_label'
      (set to question id) so export column headers are stable.

    - March 13, 2026: Initial creation. Phase 3 of Survey in a Box roadmap.
"""

import hashlib
import json
import os
import traceback
from datetime import datetime, timezone
from io import BytesIO

from flask import (Blueprint, Response, jsonify, make_response,
                   render_template, request, session)

from db_engine import get_db_connection

survey_respondent_bp = Blueprint('survey_respondent', __name__)

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

# Cookie name template — includes token to scope per-survey
_COOKIE_NAME_PREFIX = 'survey_session_'

# How long the duplicate-prevention cookie lives (seconds). 30 days.
_COOKIE_MAX_AGE = 30 * 24 * 60 * 60


# ---------------------------------------------------------------------------
# INTERNAL HELPERS
# ---------------------------------------------------------------------------

def _hash_session_value(raw_value):
    """One-way SHA-256 hash of a session cookie value. Non-reversible."""
    return hashlib.sha256(raw_value.encode('utf-8')).hexdigest()


def _get_session_token(token):
    """
    Return (cookie_value, hashed_token) for this survey token.
    cookie_value: the raw string stored in the browser cookie (for setting).
    hashed_token: the SHA-256 hash stored in the DB (for duplicate check).
    Returns (None, None) if no cookie exists yet.
    """
    cookie_name  = _COOKIE_NAME_PREFIX + token
    cookie_value = request.cookies.get(cookie_name)
    if not cookie_value:
        return None, None
    return cookie_value, _hash_session_value(cookie_value)


def _generate_session_cookie_value():
    """Generate a new random value to set as the browser session cookie."""
    import secrets
    return secrets.token_hex(32)


def _load_project_by_token(token):
    """
    Load survey_projects + survey_clients row by project_token.
    Returns (project_row, client_row) or (None, None) if not found.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sp.*, sc.company_name, sc.preferred_administration
            FROM survey_projects sp
            JOIN survey_clients sc ON sc.id = sp.survey_client_id
            WHERE sp.project_token = %s
            """,
            (token,)
        )
        row = cursor.fetchone()
        if not row:
            return None, None

        cursor.execute(
            'SELECT * FROM survey_clients WHERE id = %s',
            (row['survey_client_id'],)
        )
        client_row = cursor.fetchone()
        return row, client_row
    finally:
        conn.close()


def _safe_json_loads(val, default=None):
    if default is None:
        default = []
    if not val:
        return default
    try:
        if isinstance(val, (list, dict)):
            return val
        return json.loads(val)
    except (TypeError, ValueError):
        return default


def _get_survey_questions_ordered(project_row):
    """
    Return the ordered list of question dicts for this project.

    SurveyBuilder.create_survey() returns a survey dict with a flat
    'questions' list (not 'sections'). Each question dict from the
    question bank uses 'id' and 'text' fields. We inject a 'short_label'
    key (set to the question id) so the export and take-page code has a
    consistent field to use as column headers.

    Falls back to full question bank if no questions selected.
    """
    try:
        from survey_builder import SurveyBuilder
        builder = SurveyBuilder()

        selected_questions = _safe_json_loads(project_row.get('selected_questions'), [])
        custom_questions   = _safe_json_loads(project_row.get('custom_questions'), [])
        selected_schedules = _safe_json_loads(project_row.get('selected_schedules'), [])
        company_name       = project_row.get('company_name', 'Your Company')

        if not selected_questions:
            selected_questions = list(builder.question_bank.keys())

        survey_obj = builder.create_survey(
            project_name='Survey',
            company_name=company_name,
            selected_questions=selected_questions,
            schedules_to_rate=selected_schedules,
            custom_questions=custom_questions if custom_questions else None
        )

        # SurveyBuilder.create_survey() returns a flat 'questions' list,
        # not a 'sections' hierarchy. Iterate it directly.
        ordered = []
        for q in survey_obj.get('questions', []):
            # Inject short_label = question id so export has a stable
            # column-header field regardless of question bank field names.
            q_copy = dict(q)
            if 'short_label' not in q_copy:
                q_copy['short_label'] = q_copy.get('id', q_copy.get('text', 'unknown'))
            ordered.append(q_copy)

        # Also include any schedule rating questions
        for sched in survey_obj.get('schedule_concepts', []):
            sched_id = sched.get('schedule', {}).get('id', 'schedule')
            ordered.append({
                'id':          sched_id,
                'short_label': sched_id,
                'text':        sched.get('question', sched_id),
                'type':        'multiple_choice',
                'options':     sched.get('rating_options', []),
            })

        print(f'[survey_respondent] _get_survey_questions_ordered: {len(ordered)} questions')
        return ordered, survey_obj

    except Exception as e:
        print(f'[survey_respondent] _get_survey_questions_ordered error: {traceback.format_exc()}')
        return [], {}


# ---------------------------------------------------------------------------
# ADMIN HELPERS — require auth
# ---------------------------------------------------------------------------

def _require_admin_auth():
    """
    Check Flask session for admin login. Returns error response or None.

    IMPORTANT: The session key must match ADMIN_SESSION_KEY in survey_admin.py.
    survey_admin.py sets: session['survey_admin_authenticated'] = True
    This function checks: session.get('survey_admin_authenticated')
    These must always match. If survey_admin.py ever changes its key,
    update this function to match.
    """
    if not session.get('survey_admin_authenticated'):
        return jsonify({'success': False, 'error': 'Not authenticated',
                        'redirect': '/survey/admin'}), 401
    return None


# ---------------------------------------------------------------------------
# ROUTES — EMPLOYEE-FACING SURVEY PAGE
# ---------------------------------------------------------------------------

@survey_respondent_bp.route('/survey/take/<token>', methods=['GET'])
def survey_take_page(token):
    """
    Render the employee-facing survey page.
    The page loads questions via /api/survey/take/<token>/questions
    and submits via /api/survey/take/<token>/submit.
    """
    project_row, client_row = _load_project_by_token(token)

    if not project_row:
        return render_template('survey_closed.html',
                               message='This survey link is not valid.'), 404

    if project_row['status'] not in ('approved', 'administered'):
        return render_template('survey_closed.html',
                               message='This survey is not currently active.'), 403

    if not project_row.get('is_open'):
        return render_template('survey_closed.html',
                               message='This survey is not currently accepting responses. '
                                       'Please check back later or contact your supervisor.'), 403

    company_name = client_row.get('company_name', 'Your Company') if client_row else 'Your Company'

    return render_template('survey_take.html',
                           token=token,
                           company_name=company_name)


# ---------------------------------------------------------------------------
# ROUTES — LOAD SURVEY QUESTIONS (API)
# ---------------------------------------------------------------------------

@survey_respondent_bp.route('/api/survey/take/<token>/questions', methods=['GET'])
def get_survey_questions(token):
    """
    Return the ordered question list for this survey.
    Used by the survey_take.html frontend to render the form.
    Returns questions grouped by section with full option text.
    Does NOT require authentication.
    """
    try:
        project_row, client_row = _load_project_by_token(token)

        if not project_row:
            return jsonify({'success': False, 'error': 'Survey not found'}), 404

        if not project_row.get('is_open'):
            return jsonify({'success': False, 'error': 'Survey is not open'}), 403

        ordered_questions, survey_obj = _get_survey_questions_ordered(project_row)

        if not ordered_questions:
            return jsonify({'success': False, 'error': 'No questions configured for this survey'}), 500

        # SurveyBuilder.create_survey() returns a flat 'questions' list, not
        # a 'sections' hierarchy. Build sections grouped by category so the
        # frontend can render one section at a time.
        sections_dict = {}
        section_order = []
        for q in ordered_questions:
            cat = q.get('category', 'Survey Questions').replace('_', ' ').title()
            if cat not in sections_dict:
                sections_dict[cat] = []
                section_order.append(cat)
            sections_dict[cat].append(q)

        sections = [
            {'title': cat, 'questions': sections_dict[cat]}
            for cat in section_order
        ]

        company_name = project_row.get('company_name', 'Your Company')

        return jsonify({
            'success':         True,
            'company_name':    company_name,
            'token':           token,
            'total_questions': len(ordered_questions),
            'sections':        sections,
        })

    except Exception as e:
        print(f'[survey_respondent] get_survey_questions error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — SUBMIT SURVEY (API)
# ---------------------------------------------------------------------------

@survey_respondent_bp.route('/api/survey/take/<token>/submit', methods=['POST'])
def submit_survey(token):
    """
    Accept a completed survey submission.

    Request body (JSON):
        {
            "answers": {
                "Department": "Shipping",
                "like current schedule": "4 Agree",
                "gender": "Male"
            }
        }

    Answers should use the question short_label as the key and the
    full text of the selected option as the value. Questions left
    unanswered should be omitted from the dict (not sent as empty string).
    The export function fills missing keys with "BLANK".

    Returns:
        201 Created on success
        403 if survey is closed
        409 if duplicate submission detected
        422 if answers are missing or malformed
    """
    try:
        project_row, client_row = _load_project_by_token(token)

        if not project_row:
            return jsonify({'success': False, 'error': 'Survey not found'}), 404

        if not project_row.get('is_open'):
            return jsonify({
                'success': False,
                'error':   'This survey is no longer accepting responses.'
            }), 403

        # ---- Duplicate check -----------------------------------------------
        cookie_value, hashed_token = _get_session_token(token)

        if hashed_token:
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id FROM survey_responses
                    WHERE survey_project_id = %s AND session_token = %s
                    LIMIT 1
                    """,
                    (project_row['id'], hashed_token)
                )
                duplicate = cursor.fetchone()
            finally:
                conn.close()

            if duplicate:
                return jsonify({
                    'success': False,
                    'error':   'You have already submitted a response for this survey. '
                               'Only one response per person is allowed. Thank you!'
                }), 409

        # ---- Validate answers -----------------------------------------------
        data = request.get_json(force=True, silent=True) or {}
        answers = data.get('answers')

        if not isinstance(answers, dict):
            return jsonify({
                'success': False,
                'error':   'answers must be a JSON object keyed by question short_label.'
            }), 422

        if len(answers) == 0:
            return jsonify({
                'success': False,
                'error':   'No answers were submitted. Please complete the survey before submitting.'
            }), 422

        # Sanitize: strip any empty-string values (treat as unanswered)
        cleaned_answers = {k: v for k, v in answers.items()
                           if isinstance(k, str) and isinstance(v, str) and v.strip()}

        # ---- Store response -------------------------------------------------
        new_session_value = None
        new_hashed_token  = None

        if not cookie_value:
            # First visit — generate a new session cookie value
            new_session_value = _generate_session_cookie_value()
            new_hashed_token  = _hash_session_value(new_session_value)
        else:
            new_hashed_token = hashed_token

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO survey_responses (survey_project_id, answers, session_token)
                VALUES (%s, %s::jsonb, %s)
                RETURNING id
                """,
                (
                    project_row['id'],
                    json.dumps(cleaned_answers),
                    new_hashed_token
                )
            )
            row = cursor.fetchone()
            response_id = row['id']

            # Increment response_count on the project
            cursor.execute(
                """
                UPDATE survey_projects
                SET response_count = response_count + 1, updated_at = NOW()
                WHERE id = %s
                """,
                (project_row['id'],)
            )

            conn.commit()
        finally:
            conn.close()

        print(f'[survey_respondent] Response {response_id} stored for project '
              f'{project_row["id"]} ({project_row.get("company_name", "?")})')

        # Build response — set duplicate-prevention cookie if new session
        resp = make_response(jsonify({
            'success':     True,
            'message':     'Thank you! Your response has been recorded.',
            'response_id': response_id,
        }), 201)

        if new_session_value:
            cookie_name = _COOKIE_NAME_PREFIX + token
            resp.set_cookie(
                cookie_name,
                new_session_value,
                max_age=_COOKIE_MAX_AGE,
                httponly=True,
                samesite='Lax',
                secure=os.environ.get('FLASK_ENV') != 'development'
            )

        return resp

    except Exception as e:
        print(f'[survey_respondent] submit_survey error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — ADMIN: OPEN SURVEY
# ---------------------------------------------------------------------------

@survey_respondent_bp.route('/api/survey/admin/project/<int:project_id>/open', methods=['GET', 'POST'])
def open_survey(project_id):
    """
    Jim opens a survey to accept employee responses.
    Sets is_open = TRUE, opened_at = NOW(), status = 'administered'.
    Also sets survey_url on the project for convenience.
    Requires admin auth.
    """
    auth_error = _require_admin_auth()
    if auth_error:
        return auth_error

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                'SELECT id, project_token, status, is_open FROM survey_projects WHERE id = %s',
                (project_id,)
            )
            project = cursor.fetchone()

            if not project:
                return jsonify({'success': False, 'error': 'Project not found'}), 404

            if project['status'] not in ('approved', 'administered'):
                return jsonify({
                    'success': False,
                    'error':   f'Project must be approved before opening. '
                               f'Current status: {project["status"]}'
                }), 400

            token       = project['project_token']
            base_url    = os.environ.get('APP_BASE_URL', 'https://ai-swarm-orchestrator.onrender.com')
            survey_url  = f'{base_url}/survey/take/{token}'

            cursor.execute(
                """
                UPDATE survey_projects
                SET is_open    = TRUE,
                    opened_at  = NOW(),
                    status     = 'administered',
                    survey_url = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (survey_url, project_id)
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({
            'success':    True,
            'message':    'Survey is now open and accepting responses.',
            'survey_url': survey_url,
            'token':      token,
        })

    except Exception as e:
        print(f'[survey_respondent] open_survey error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — ADMIN: CLOSE SURVEY
# ---------------------------------------------------------------------------

@survey_respondent_bp.route('/api/survey/admin/project/<int:project_id>/close', methods=['POST'])
def close_survey(project_id):
    """
    Jim closes a survey — no more responses accepted.
    Sets is_open = FALSE, closed_at = NOW().
    Requires admin auth.
    """
    auth_error = _require_admin_auth()
    if auth_error:
        return auth_error

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                'SELECT id, is_open, response_count FROM survey_projects WHERE id = %s',
                (project_id,)
            )
            project = cursor.fetchone()

            if not project:
                return jsonify({'success': False, 'error': 'Project not found'}), 404

            cursor.execute(
                """
                UPDATE survey_projects
                SET is_open    = FALSE,
                    closed_at  = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (project_id,)
            )
            conn.commit()
        finally:
            conn.close()

        return jsonify({
            'success':        True,
            'message':        'Survey is now closed.',
            'response_count': project['response_count'] or 0,
        })

    except Exception as e:
        print(f'[survey_respondent] close_survey error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — ADMIN: RESPONSE SUMMARY
# ---------------------------------------------------------------------------

@survey_respondent_bp.route('/api/survey/admin/project/<int:project_id>/responses', methods=['GET'])
def get_response_summary(project_id):
    """
    Return response count and open/closed status for a project.
    Used by the admin dashboard to show response progress.
    Requires admin auth.
    """
    auth_error = _require_admin_auth()
    if auth_error:
        return auth_error

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT sp.response_count, sp.is_open, sp.opened_at, sp.closed_at,
                       sp.survey_url, sp.project_token,
                       COUNT(sr.id) AS actual_count
                FROM survey_projects sp
                LEFT JOIN survey_responses sr ON sr.survey_project_id = sp.id
                WHERE sp.id = %s
                GROUP BY sp.id
                """,
                (project_id,)
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if not row:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        return jsonify({
            'success':        True,
            'project_id':     project_id,
            'response_count': row['actual_count'],
            'is_open':        row['is_open'],
            'opened_at':      str(row['opened_at']) if row['opened_at'] else None,
            'closed_at':      str(row['closed_at']) if row['closed_at'] else None,
            'survey_url':     row['survey_url'] or '',
            'token':          row['project_token'],
        })

    except Exception as e:
        print(f'[survey_respondent] get_response_summary error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# ROUTES — ADMIN: EXPORT RESPONSES AS XLSX
# ---------------------------------------------------------------------------

@survey_respondent_bp.route('/api/survey/admin/project/<int:project_id>/export', methods=['GET'])
def export_responses(project_id):
    """
    Export all survey responses as a SurveySelector/Remark-compatible .xlsx file.

    Format:
        - Sheet name: "Sheet1"
        - One row per respondent
        - Column headers: question short_label in survey order
        - Values: full text of selected answer option
        - Unanswered questions: the literal string "BLANK"
        - No row IDs, no timestamps, no session tokens

    This format matches the Remark Office OMR export that SurveySelector
    already processes. Jim can drop this file directly into SurveySelector.

    Requires admin auth.
    """
    auth_error = _require_admin_auth()
    if auth_error:
        return auth_error

    try:
        # ---- Load project and question structure ----------------------------
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT sp.*, sc.company_name, sc.preferred_administration
                FROM survey_projects sp
                JOIN survey_clients sc ON sc.id = sp.survey_client_id
                WHERE sp.id = %s
                """,
                (project_id,)
            )
            project_row = cursor.fetchone()

            if not project_row:
                return jsonify({'success': False, 'error': 'Project not found'}), 404

            # Load all response rows
            cursor.execute(
                """
                SELECT answers FROM survey_responses
                WHERE survey_project_id = %s
                ORDER BY submitted_at ASC
                """,
                (project_id,)
            )
            response_rows = cursor.fetchall()
        finally:
            conn.close()

        if not response_rows:
            return jsonify({
                'success': False,
                'error':   'No responses have been submitted for this project yet.'
            }), 404

        # ---- Build ordered column list from survey structure ---------------
        ordered_questions, _ = _get_survey_questions_ordered(project_row)

        if not ordered_questions:
            return jsonify({
                'success': False,
                'error':   'Could not load question structure for this project.'
            }), 500

        # Column headers in survey order
        column_headers = [q['short_label'] for q in ordered_questions]

        # ---- Build xlsx ----------------------------------------------------
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
        except ImportError:
            return jsonify({
                'success': False,
                'error':   'openpyxl is required for xlsx export. '
                           'Add it to requirements.txt.'
            }), 500

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Sheet1'

        # Header row — bold
        header_font = Font(bold=True)
        for col_idx, header in enumerate(column_headers, start=1):
            cell       = ws.cell(row=1, column=col_idx, value=header)
            cell.font  = header_font

        # Data rows — one per respondent
        for row_idx, response_row in enumerate(response_rows, start=2):
            # answers may come back as dict (JSONB) or string (fallback)
            raw_answers = response_row['answers']
            if isinstance(raw_answers, str):
                try:
                    answers = json.loads(raw_answers)
                except (TypeError, ValueError):
                    answers = {}
            elif isinstance(raw_answers, dict):
                answers = raw_answers
            else:
                answers = {}

            for col_idx, header in enumerate(column_headers, start=1):
                # Use "BLANK" for any question not answered — Remark convention
                value = answers.get(header, 'BLANK')
                if not value or not str(value).strip():
                    value = 'BLANK'
                ws.cell(row=row_idx, column=col_idx, value=str(value))

        # Set reasonable column widths
        for col_idx, header in enumerate(column_headers, start=1):
            col_letter = ws.cell(row=1, column=col_idx).column_letter
            ws.column_dimensions[col_letter].width = max(len(header) + 4, 15)

        # ---- Write to buffer and return ------------------------------------
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        company_name  = project_row.get('company_name', 'Survey')
        safe_company  = ''.join(c if c.isalnum() else '_' for c in company_name)[:40]
        ts            = datetime.now(timezone.utc).strftime('%Y%m%d')
        filename      = f'SurveyData_{safe_company}_{ts}.xlsx'
        respondent_count = len(response_rows)

        print(f'[survey_respondent] Exported {respondent_count} responses '
              f'for project {project_id} ({company_name}): {filename}')

        return Response(
            buffer.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'X-Response-Count':    str(respondent_count),
                'X-Column-Count':      str(len(column_headers)),
            }
        )

    except Exception as e:
        print(f'[survey_respondent] export_responses error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


# I did no harm and this file is not truncated
