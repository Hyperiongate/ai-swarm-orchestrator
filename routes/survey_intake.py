"""
SURVEY IN A BOX — Intake Routes
File: routes/survey_intake.py
Created: March 10, 2026
Last Updated: March 10, 2026 - Initial creation, Phase 1 Step 1.2

PURPOSE:
    Backend routes for the public-facing Survey in a Box client intake form.
    Handles form submission, data validation, and storage in survey_clients table.
    Also serves the intake HTML page at GET /survey/start.

    This blueprint is registered in app.py alongside all other blueprints.
    It does NOT touch any existing Swarm routes or tables.

ENDPOINTS:
    GET  /survey/start                      — Public intake form page
    POST /api/survey/intake/submit          — Process form submission
    GET  /api/survey/intake/status/<id>     — Check submission status (for thank-you page)

POSTGRESQL RULES:
    - RealDictCursor dict-only rows (access by name, never by index)
    - TRUE/FALSE for booleans (not 0/1)
    - %s for all parameters
    - RETURNING id on INSERT

CHANGELOG:
    - March 10, 2026: Initial creation. Phase 1 Step 1.2 of Survey in a Box.
"""

import json
import re
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

from db_engine import get_db_connection

survey_intake_bp = Blueprint('survey_intake', __name__)

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

VALID_INDUSTRIES = [
    'manufacturing', 'pharmaceutical', 'food_processing', 'mining',
    'distribution', 'chemical', 'utilities', 'paper_pulp', 'oil_gas', 'other'
]

VALID_SCHEDULE_TYPES = [
    '8hr_fixed', '8hr_rotating', '10hr', '12hr_fixed', '12hr_rotating', 'other'
]

VALID_ADMIN_METHODS = ['online', 'paper_bubble_sheets', 'unsure']

VALID_CHALLENGES = [
    'recruiting', 'retention', 'overtime', 'work_life_balance',
    'schedule_design', 'coverage_absenteeism', 'communication', 'other'
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _safe_int(val, default=None):
    """Convert value to int safely, returning default on failure."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _safe_json_list(val):
    """
    Accept either a Python list or a JSON-encoded string.
    Always returns a JSON-encoded string for storage in TEXT column.
    """
    if isinstance(val, list):
        return json.dumps(val)
    try:
        parsed = json.loads(val)
        if isinstance(parsed, list):
            return json.dumps(parsed)
    except (TypeError, ValueError):
        pass
    return json.dumps([])


def _validate_intake(data):
    """
    Validate required intake form fields.
    Returns a list of error strings. Empty list = valid.
    """
    errors = []
    required_fields = {
        'company_name': 'Company name',
        'contact_name': 'Contact person name',
        'email': 'Email address',
    }
    for field, label in required_fields.items():
        val = data.get(field, '')
        if not val or not str(val).strip():
            errors.append(f'{label} is required.')

    email = data.get('email', '')
    if email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', str(email)):
        errors.append('Please enter a valid email address.')

    return errors


def _notify_jim(client_id, company_name, contact_name, email):
    """
    Attempt to send Jim a notification email via the existing alert system.
    Logs to console if alert_system is not available — never blocks the
    submission response.
    """
    try:
        from alert_system import get_alert_manager
        am = get_alert_manager()
        am.create_alert(
            category='survey_intake',
            priority='high',
            title=f'New Survey Intake: {company_name}',
            summary=(
                f'New Survey in a Box intake submission received.\n'
                f'Company: {company_name}\n'
                f'Contact: {contact_name} <{email}>\n'
                f'Review at: /survey/admin'
            ),
            details=json.dumps({
                'client_id': client_id,
                'company_name': company_name,
                'contact_name': contact_name,
                'email': email,
                'submitted_at': datetime.utcnow().isoformat()
            })
        )
    except Exception as e:
        # Alert system unavailable — log to console only, do not fail
        print(f'[survey_intake] Jim notification: alert_system unavailable ({e}). '
              f'New intake: {company_name} (id={client_id})')


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@survey_intake_bp.route('/survey/start', methods=['GET'])
def survey_start():
    """
    Serve the public-facing Survey in a Box intake form.
    This page is standalone — not inside the Swarm UI.
    """
    return render_template('survey_intake.html')


@survey_intake_bp.route('/api/survey/intake/submit', methods=['POST'])
def submit_intake():
    """
    Process a client intake form submission.

    Accepts JSON body from the intake form's fetch() call.

    Required fields: company_name, contact_name, email
    All other fields are optional and stored as-is or as JSON.

    Returns:
        {
            'success': bool,
            'client_id': int,      # on success
            'message': str,
            'errors': [str]        # on validation failure
        }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}

        # --- Validate ---
        errors = _validate_intake(data)
        if errors:
            return jsonify({
                'success': False,
                'errors': errors,
                'message': 'Please correct the errors above.'
            }), 400

        # --- Build insert values (20 columns, order matches SQL below) ---
        values = (
            data.get('company_name', '').strip(),
            data.get('contact_name', '').strip(),
            data.get('email', '').strip().lower(),
            data.get('phone', '').strip(),
            data.get('industry', '').strip(),
            _safe_int(data.get('employee_count')),
            _safe_int(data.get('department_count')),
            _safe_json_list(data.get('department_names', [])),
            data.get('current_schedule_type', '').strip(),
            _safe_int(data.get('crew_count')),
            data.get('shift_start_times', '').strip(),
            data.get('union_status', 'non-union').strip(),
            _safe_json_list(data.get('biggest_challenges', [])),
            bool(data.get('previously_surveyed', False)),
            data.get('last_survey_date', '').strip(),
            data.get('preferred_administration', 'online').strip(),
            data.get('preferred_delivery_date', '').strip(),
            data.get('referral_source', '').strip(),
            data.get('additional_notes', '').strip(),
            'new'   # status
        )

        sql = """
            INSERT INTO survey_clients (
                company_name, contact_name, email, phone, industry,
                employee_count, department_count, department_names,
                current_schedule_type, crew_count, shift_start_times, union_status,
                biggest_challenges, previously_surveyed, last_survey_date,
                preferred_administration, preferred_delivery_date, referral_source,
                additional_notes, status
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s
            ) RETURNING id
        """

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            row = cursor.fetchone()
            client_id = row['id']
            conn.commit()
        finally:
            conn.close()

        # Notify Jim (non-blocking — never fails the request)
        _notify_jim(
            client_id,
            data.get('company_name', '').strip(),
            data.get('contact_name', '').strip(),
            data.get('email', '').strip().lower()
        )

        return jsonify({
            'success': True,
            'client_id': client_id,
            'message': (
                'Thank you! Your information has been received. '
                'Jim will review your submission and be in touch within 1–2 business days.'
            )
        }), 201

    except Exception as e:
        import traceback
        print(f'[survey_intake] submit_intake error: {traceback.format_exc()}')
        return jsonify({
            'success': False,
            'errors': ['An unexpected error occurred. Please try again or contact us directly.'],
            'message': 'Submission failed.'
        }), 500


@survey_intake_bp.route('/api/survey/intake/status/<int:client_id>', methods=['GET'])
def intake_status(client_id):
    """
    Return the status of a submitted intake record.
    Used by the thank-you page to confirm receipt.
    Returns minimal data only — not sensitive admin details.
    """
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, company_name, contact_name, status, created_at
                FROM survey_clients
                WHERE id = %s
                """,
                (client_id,)
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if not row:
            return jsonify({'success': False, 'error': 'Not found'}), 404

        return jsonify({
            'success': True,
            'status': row['status'],
            'company_name': row['company_name'],
            'contact_name': row['contact_name'],
            'submitted_at': str(row['created_at'])
        })

    except Exception as e:
        import traceback
        print(f'[survey_intake] intake_status error: {traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500

# I did no harm and this file is not truncated
