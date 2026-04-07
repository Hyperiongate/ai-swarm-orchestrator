"""
AI SWARM ORCHESTRATOR — Contact Form API (Security Layer)
Created: April 7, 2026
Last Updated: April 7, 2026
Author: Claude Opus 4.6 for Jim @ Shiftwork Solutions LLC

PURPOSE:
    Flask blueprint that sits between the shift-work.com contact form
    and Formspree. The contact form now POSTs here first. This endpoint:

    1. Logs the submission with IP, user agent, email domain
    2. Runs server-side anti-spam checks (blocklist, honeypot, timestamp,
       disposable email, rate limiting)
    3. If clean, forwards the form data to Formspree for delivery
    4. Returns success/error to the frontend

    This gives Jim the same IP-level visibility on contact form senders
    that he already has on newsletter signups, plus the ability to block
    spammers before they reach his inbox.

ENDPOINT:
    POST /api/contact/submit
    Content-Type: application/json
    Body: {
        name, email, company, message (required)
        phone, employees (optional)
        honeypot, timestamp (anti-spam fields)
    }

    Returns:
        201  { success: true }      — submitted and forwarded
        400  { success: false }     — validation error
        403  { success: false }     — blocked IP
        429  { success: false }     — rate limited
        500  { success: false }     — server error

    GET /api/contact/submissions?page=1&per_page=50
        Admin: paginated list of all contact form submissions with IPs.

    GET /api/contact/submissions/by-ip/<ip>
        Admin: all submissions from a given IP.

CORS:
    Same origin policy as newsletter — shift-work.com + dev origins.

FORMSPREE FORWARDING:
    After logging and spam checks, this endpoint forwards the form data
    to Formspree via POST. The Formspree form ID is configured as an
    environment variable (FORMSPREE_FORM_ID) or falls back to the
    hardcoded ID. Formspree handles the actual email delivery to
    Contact@shift-work.com.

ANTI-SPAM LAYERS:
    Uses shared utilities from routes/newsletter.py:
    - get_client_ip(), get_user_agent(), extract_email_domain()
    - is_ip_blocked()
    Plus its own:
    - Server-side honeypot check
    - Server-side timestamp check
    - Email validation (format + disposable domains)
    - IP-based rate limiting (max 3 contact form submissions per IP per hour)

GOLDEN RULES FOLLOWED:
    - All SQL uses %s placeholders via db_engine.py
    - Never imports sqlite3 directly
    - Uses RETURNING id (not lastrowid)
    - Table created by migration_007_security.py

I did no harm and this file is not truncated
"""

import os
import re
import logging
import requests
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

contact_api_bp = Blueprint('contact_api', __name__)

# Formspree form ID — set in Render env vars, or use hardcoded fallback
FORMSPREE_FORM_ID = os.environ.get('FORMSPREE_FORM_ID', 'xwvwnwea')
FORMSPREE_URL = f'https://formspree.io/f/{FORMSPREE_FORM_ID}'


# ═══════════════════════════════════════════════════════════════════════════
# CORS — same policy as newsletter
# ═══════════════════════════════════════════════════════════════════════════

ALLOWED_ORIGINS = [
    'https://shift-work.com',
    'https://www.shift-work.com',
    'http://localhost:3000',
    'http://localhost:5000',
    'http://127.0.0.1:5500',
    'null',
]


def _cors_headers(origin=None):
    """Return CORS headers dict for the given origin."""
    headers = {
        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Accept',
        'Access-Control-Max-Age': '86400',
    }
    if origin in ALLOWED_ORIGINS:
        headers['Access-Control-Allow-Origin'] = origin
    elif origin and (origin.endswith('.shift-work.com') or origin.endswith('.onrender.com')):
        headers['Access-Control-Allow-Origin'] = origin
    else:
        headers['Access-Control-Allow-Origin'] = 'https://shift-work.com'
    return headers


@contact_api_bp.after_request
def add_cors_headers(response):
    """Add CORS headers to every response from this blueprint."""
    origin = request.headers.get('Origin', '')
    for key, value in _cors_headers(origin).items():
        response.headers[key] = value
    return response


# ═══════════════════════════════════════════════════════════════════════════
# EMAIL VALIDATION (uses newsletter's disposable list)
# ═══════════════════════════════════════════════════════════════════════════

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def _validate_contact_email(email):
    """Validate email format and check disposable domains."""
    if not email or not isinstance(email, str):
        return False, 'Email is required.'
    email = email.strip().lower()
    if len(email) > 254:
        return False, 'Email address is too long.'
    if not EMAIL_REGEX.match(email):
        return False, 'Please enter a valid email address.'
    # Import disposable list from newsletter module
    try:
        from routes.newsletter import DISPOSABLE_DOMAINS
        domain = email.split('@')[1]
        if domain in DISPOSABLE_DOMAINS:
            return False, 'Please use a permanent email address.'
    except ImportError:
        pass
    return True, email


# ═══════════════════════════════════════════════════════════════════════════
# CONTACT-SPECIFIC RATE LIMITING
# Stricter than newsletter: max 3 submissions per IP per hour
# ═══════════════════════════════════════════════════════════════════════════

def _check_contact_rate_limit(ip_address):
    """
    Check if this IP has submitted more than 3 contact forms in the last hour.
    Returns (is_allowed, message).
    """
    from db_engine import get_db_connection

    if not ip_address or ip_address == 'unknown':
        return True, ''

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            cursor.execute(
                """SELECT COUNT(*) as cnt FROM contact_submissions
                   WHERE ip_address = %s AND submitted_at > %s""",
                (ip_address, one_hour_ago)
            )
            row = cursor.fetchone()
            count = row['cnt'] if row else 0
            return count < 3, 'Too many submissions from this address. Please try again later.'
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Contact rate limit check failed (allowing): {e}")
        return True, ''


# ═══════════════════════════════════════════════════════════════════════════
# FORWARD TO FORMSPREE
# ═══════════════════════════════════════════════════════════════════════════

def _forward_to_formspree(form_data):
    """
    Forward the contact form data to Formspree for email delivery.
    Returns (success, status_code, error_message).
    """
    try:
        # Formspree expects form-encoded data or JSON
        payload = {
            'name': form_data.get('name', ''),
            'email': form_data.get('email', ''),
            'company': form_data.get('company', ''),
            'phone': form_data.get('phone', ''),
            'employees': form_data.get('employees', ''),
            'message': form_data.get('message', ''),
            '_subject': 'New Contact Form — shift-work.com',
        }

        response = requests.post(
            FORMSPREE_URL,
            json=payload,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            timeout=10
        )

        if response.status_code in (200, 201, 302):
            return True, response.status_code, None
        else:
            error_text = response.text[:200]
            logger.error(f"Formspree forwarding failed ({response.status_code}): {error_text}")
            return False, response.status_code, f'Formspree error: {response.status_code}'

    except requests.exceptions.Timeout:
        logger.error("Formspree forwarding timed out")
        return False, 504, 'Email delivery timed out'
    except Exception as e:
        logger.error(f"Formspree forwarding exception: {e}")
        return False, 500, str(e)


# ═══════════════════════════════════════════════════════════════════════════
# SUBMIT ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

@contact_api_bp.route('/api/contact/submit', methods=['POST', 'OPTIONS'])
def contact_submit():
    """Handle contact form submission with full anti-spam stack."""

    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    from db_engine import get_db_connection
    from routes.newsletter import get_client_ip, get_user_agent, extract_email_domain, is_ip_blocked

    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request. Send JSON with name, email, company, and message.'
            }), 400

        # ── LAYER 1: IP blocklist check ────────────────────────────────
        ip_address = get_client_ip()
        blocked, block_reason = is_ip_blocked(ip_address)
        if blocked:
            logger.warning(f"Blocked IP attempted contact form: {ip_address}")
            return jsonify({
                'success': False,
                'error': 'Something went wrong. Please try again later.'
            }), 403

        # ── LAYER 2: Server-side honeypot ──────────────────────────────
        honeypot_value = data.get('honeypot', '') or data.get('_gotcha', '')
        if honeypot_value:
            logger.warning(f"Honeypot triggered on contact form from {ip_address}")
            return jsonify({
                'success': True,
                'message': 'Thank you! Your message has been sent.'
            }), 201

        # ── LAYER 3: Server-side timestamp check ───────────────────────
        client_timestamp = data.get('timestamp', None) or data.get('_loaded', None)
        if client_timestamp:
            try:
                loaded_at = int(client_timestamp)
                now_ms = int(datetime.utcnow().timestamp() * 1000)
                elapsed_ms = now_ms - loaded_at
                if elapsed_ms < 3000:
                    logger.warning(f"Timestamp check failed on contact form from {ip_address} (elapsed: {elapsed_ms}ms)")
                    return jsonify({
                        'success': False,
                        'error': 'Please take a moment to fill out the form completely.'
                    }), 400
            except (ValueError, TypeError):
                pass

        # ── LAYER 4: Validate required fields ──────────────────────────
        name = (data.get('name') or '').strip()[:255]
        raw_email = data.get('email', '')
        company = (data.get('company') or '').strip()[:255]
        message = (data.get('message') or '').strip()[:5000]
        phone = (data.get('phone') or '').strip()[:50] or None
        employees = (data.get('employees') or '').strip()[:50] or None

        if not name or not raw_email or not company or not message:
            return jsonify({
                'success': False,
                'error': 'Please fill in all required fields (name, email, company, message).'
            }), 400

        # ── LAYER 5: Email validation ──────────────────────────────────
        is_valid, result = _validate_contact_email(raw_email)
        if not is_valid:
            return jsonify({'success': False, 'error': result}), 400
        email = result

        # ── LAYER 6: Rate limit check ─────────────────────────────────
        is_allowed, rate_msg = _check_contact_rate_limit(ip_address)
        if not is_allowed:
            return jsonify({'success': False, 'error': rate_msg}), 429

        # ── Collect metadata ───────────────────────────────────────────
        user_agent = get_user_agent()
        email_domain = extract_email_domain(email)
        source = (data.get('source') or 'website-contact').strip()[:100]

        # ── Determine spam status ──────────────────────────────────────
        is_spam = False
        spam_reason = None

        # ── Log the submission ─────────────────────────────────────────
        conn = get_db_connection()
        submission_id = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO contact_submissions
                   (name, email, email_domain, company, phone, employees,
                    message, source, ip_address, user_agent, is_spam, spam_reason)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (name, email, email_domain, company, phone, employees,
                 message, source, ip_address, user_agent, is_spam, spam_reason)
            )
            submission_id = cursor.fetchone()['id']
            conn.commit()
            logger.info(f"Contact form logged: id={submission_id}, email={email}, ip={ip_address}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Contact form logging failed: {e}")
            # Continue to forward even if logging fails — don't lose the lead
        finally:
            conn.close()

        # ── Forward to Formspree ───────────────────────────────────────
        forwarded_ok, status, error_msg = _forward_to_formspree({
            'name': name,
            'email': email,
            'company': company,
            'phone': phone or '',
            'employees': employees or '',
            'message': message,
        })

        # Update forwarded status
        if submission_id:
            try:
                conn2 = get_db_connection()
                try:
                    cursor2 = conn2.cursor()
                    cursor2.execute(
                        "UPDATE contact_submissions SET forwarded = %s WHERE id = %s",
                        (forwarded_ok, submission_id)
                    )
                    conn2.commit()
                except Exception:
                    conn2.rollback()
                finally:
                    conn2.close()
            except Exception:
                pass

        if forwarded_ok:
            return jsonify({
                'success': True,
                'message': 'Thank you! Your message has been sent. We typically respond within one business day.'
            }), 201
        else:
            # Formspree failed, but we logged the submission — still tell user we got it
            logger.error(f"Formspree forwarding failed for submission {submission_id}: {error_msg}")
            return jsonify({
                'success': True,
                'message': 'Thank you! Your message has been received. We typically respond within one business day.'
            }), 201

    except Exception as e:
        logger.error(f"Contact submit error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Something went wrong. Please try again or email Contact@shift-work.com directly.'
        }), 500


# ═══════════════════════════════════════════════════════════════════════════
# SUBMISSIONS LIST (admin, paginated)
# ═══════════════════════════════════════════════════════════════════════════

@contact_api_bp.route('/api/contact/submissions', methods=['GET'])
def list_submissions():
    """Paginated list of contact form submissions with IPs."""
    from db_engine import get_db_connection

    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
        offset = (page - 1) * per_page

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as total FROM contact_submissions")
            total = cursor.fetchone()['total']

            cursor.execute(
                """SELECT id, name, email, email_domain, company, phone,
                          employees, message, source, ip_address, user_agent,
                          submitted_at, is_spam, spam_reason, forwarded
                   FROM contact_submissions
                   ORDER BY submitted_at DESC
                   LIMIT %s OFFSET %s""",
                (per_page, offset)
            )
            submissions = []
            for row in cursor.fetchall():
                submissions.append({
                    'id': row['id'],
                    'name': row['name'],
                    'email': row['email'],
                    'email_domain': row['email_domain'],
                    'company': row['company'],
                    'phone': row['phone'],
                    'employees': row['employees'],
                    'message': row['message'][:200] + '...' if row['message'] and len(row['message']) > 200 else row['message'],
                    'source': row['source'],
                    'ip_address': row['ip_address'],
                    'user_agent': row['user_agent'],
                    'submitted_at': str(row['submitted_at']) if row['submitted_at'] else None,
                    'is_spam': row['is_spam'],
                    'spam_reason': row['spam_reason'],
                    'forwarded': row['forwarded'],
                })

            return jsonify({
                'success': True,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page,
                'submissions': submissions,
            })
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Contact submissions list error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# SUBMISSIONS BY IP (admin)
# ═══════════════════════════════════════════════════════════════════════════

@contact_api_bp.route('/api/contact/submissions/by-ip/<path:ip>', methods=['GET'])
def submissions_by_ip(ip):
    """Find all contact form submissions from a given IP."""
    from db_engine import get_db_connection
    from routes.newsletter import is_ip_blocked

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, name, email, email_domain, company, phone,
                          employees, message, source, ip_address, user_agent,
                          submitted_at, is_spam, forwarded
                   FROM contact_submissions
                   WHERE ip_address = %s
                   ORDER BY submitted_at DESC""",
                (ip,)
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row['id'],
                    'name': row['name'],
                    'email': row['email'],
                    'company': row['company'],
                    'submitted_at': str(row['submitted_at']) if row['submitted_at'] else None,
                    'is_spam': row['is_spam'],
                    'forwarded': row['forwarded'],
                })

            blocked, reason = is_ip_blocked(ip)

            return jsonify({
                'success': True,
                'ip_address': ip,
                'is_blocked': blocked,
                'block_reason': reason,
                'submission_count': len(results),
                'submissions': results,
            })
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Contact submissions by IP error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# I did no harm and this file is not truncated
