"""
Survey in a Box — Intake Form Routes
File: routes/survey_intake.py
Created: March 16, 2026
Last Updated: March 16, 2026 — Phase 1, Step 1.2: Initial creation

PURPOSE:
    Handles the public-facing client intake form for Survey in a Box.
    Two endpoints:
        GET  /survey/start            — Renders the intake form (survey_intake.html)
        POST /api/survey/intake/submit — Saves submission to survey_clients table,
                                         sends Jim a notification email (or logs to console),
                                         returns JSON {success, client_id, message}

DESIGN RULES:
    - PostgreSQL only: RealDictCursor, %s params, RETURNING id
    - All list fields (department_names, biggest_challenges, shift_start_times)
      stored as JSON strings in TEXT columns — parsed in Python on read
    - SMTP notification: tries alert_system SMTP first, falls back to console log
    - No changes to any existing Swarm table or route
    - Blueprint prefix: none (routes defined with full paths)

CHANGELOG:
    - March 16, 2026: Initial creation for Phase 1, Step 1.2.
"""

import json
import os
import traceback
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify

survey_intake_bp = Blueprint('survey_intake', __name__)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _safe_int(value, default=None):
    """Parse a form value to int, returning default on failure."""
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default


def _get_db():
    """Return a fresh psycopg2 connection with RealDictCursor support."""
    from db_engine import get_db_connection
    return get_db_connection()


def _notify_jim(client_id, company_name, contact_name, email, industry):
    """
    Send Jim an email notification that a new intake form was submitted.
    Falls back to a console log if SMTP is not configured.
    """
    subject = f"[Survey in a Box] New Intake: {company_name}"
    body = (
        f"A new survey intake form was submitted.\n\n"
        f"Company:  {company_name}\n"
        f"Contact:  {contact_name}\n"
        f"Email:    {email}\n"
        f"Industry: {industry}\n"
        f"Client ID: {client_id}\n\n"
        f"Review at: /survey/admin\n"
    )

    # Try alert_system SMTP first
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_host = os.environ.get('SMTP_HOST', '')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_user = os.environ.get('SMTP_USER', '')
        smtp_pass = os.environ.get('SMTP_PASS', '')
        jim_email = os.environ.get('ADMIN_EMAIL', 'jim@shift-work.com')

        if smtp_host and smtp_user and smtp_pass:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = jim_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            print(f"[survey_intake] Notification email sent to {jim_email} for client_id={client_id}")
            return
    except Exception as e:
        print(f"[survey_intake] SMTP not available ({e}) — logging notification to console")

    # Console fallback
    print("=" * 60)
    print(f"[survey_intake] NEW INTAKE SUBMISSION — client_id={client_id}")
    print(f"  {subject}")
    print(body)
    print("=" * 60)


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@survey_intake_bp.route('/survey/start', methods=['GET'])
def intake_form():
    """Render the public intake form."""
    return render_template('survey_intake.html')


@survey_intake_bp.route('/api/survey/intake/submit', methods=['POST'])
def submit_intake():
    """
    Process the intake form submission.
    Accepts JSON or multipart/form-data.
    Saves to survey_clients. Returns {success, client_id, message}.
    """
    try:
        # ------------------------------------------------------------------
        # Parse form data (supports both JSON body and HTML form POST)
        # ------------------------------------------------------------------
        if request.is_json:
            data = request.get_json(force=True) or {}
            def get_field(key, default=''):
                return data.get(key, default)
            def get_list(key):
                val = data.get(key, [])
                return val if isinstance(val, list) else [val] if val else []
        else:
            def get_field(key, default=''):
                return (request.form.get(key) or '').strip() or default
            def get_list(key):
                # HTML multi-select sends multiple values under same key
                vals = request.form.getlist(key)
                if not vals:
                    # Also try key[] convention
                    vals = request.form.getlist(key + '[]')
                return [v.strip() for v in vals if v.strip()]

        # ------------------------------------------------------------------
        # Required fields validation
        # ------------------------------------------------------------------
        company_name = get_field('company_name')
        contact_name = get_field('contact_name')
        email        = get_field('email')

        if not company_name or not contact_name or not email:
            return jsonify({
                'success': False,
                'error': 'company_name, contact_name, and email are required.'
            }), 400

        # ------------------------------------------------------------------
        # Extract all fields
        # ------------------------------------------------------------------
        phone                  = get_field('phone', None) or None
        industry               = get_field('industry', None) or None
        employee_count         = _safe_int(get_field('employee_count'))
        department_count       = _safe_int(get_field('department_count'))

        # Department names: dynamic multi-field
        department_names_list  = get_list('department_names')
        department_names       = json.dumps(department_names_list)

        current_schedule_type  = get_field('current_schedule_type', None) or None
        crew_count             = _safe_int(get_field('crew_count'))

        # Shift start times: stored as plain text (user enters free-form)
        shift_start_times      = get_field('shift_start_times', None) or None

        union_status           = get_field('union_status', 'non-union')

        # Biggest challenges: multi-select checkboxes
        challenges_list        = get_list('biggest_challenges')
        biggest_challenges     = json.dumps(challenges_list)

        # Previous survey
        previously_surveyed_raw = get_field('previously_surveyed', 'no')
        previously_surveyed    = previously_surveyed_raw.lower() in ('yes', 'true', '1')
        last_survey_date       = get_field('last_survey_date', None) or None

        preferred_administration = get_field('preferred_administration', 'online')
        preferred_delivery_date  = get_field('preferred_delivery_date', None) or None
        referral_source          = get_field('referral_source', None) or None
        additional_notes         = get_field('additional_notes', None) or None

        # ------------------------------------------------------------------
        # Insert into survey_clients
        # ------------------------------------------------------------------
        conn = _get_db()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO survey_clients (
                    company_name, contact_name, email, phone, industry,
                    employee_count, department_count, department_names,
                    current_schedule_type, crew_count, shift_start_times,
                    union_status, biggest_challenges, previously_surveyed,
                    last_survey_date, preferred_administration, preferred_delivery_date,
                    referral_source, additional_notes,
                    status, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    'new', NOW(), NOW()
                )
                RETURNING id
            """, (
                company_name, contact_name, email, phone, industry,
                employee_count, department_count, department_names,
                current_schedule_type, crew_count, shift_start_times,
                union_status, biggest_challenges, previously_surveyed,
                last_survey_date, preferred_administration, preferred_delivery_date,
                referral_source, additional_notes
            ))
            row = cursor.fetchone()
            client_id = row['id'] if isinstance(row, dict) else row[0]
            conn.commit()
        finally:
            conn.close()

        # ------------------------------------------------------------------
        # Notify Jim (non-fatal — we already saved successfully)
        # ------------------------------------------------------------------
        try:
            _notify_jim(client_id, company_name, contact_name, email, industry or 'not specified')
        except Exception as notify_err:
            print(f"[survey_intake] Notification failed (non-fatal): {notify_err}")

        return jsonify({
            'success': True,
            'client_id': client_id,
            'message': (
                f"Thank you, {contact_name}! We received your survey request for "
                f"{company_name} and will be in touch within 1-2 business days."
            )
        })

    except Exception as e:
        print(f"[survey_intake] submit_intake error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'An internal error occurred. Please try again or contact jim@shift-work.com.'
        }), 500

# I did no harm and this file is not truncated
