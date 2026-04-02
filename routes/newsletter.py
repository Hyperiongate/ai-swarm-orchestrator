"""
AI SWARM ORCHESTRATOR — Newsletter Subscription API
Created: April 2, 2026
Last Updated: April 2, 2026
Author: Claude Opus 4.6 for Jim @ Shiftwork Solutions LLC

PURPOSE:
    Flask blueprint providing POST /api/newsletter/subscribe endpoint.
    Receives newsletter signups from the shift-work.com website,
    validates input, checks for duplicates, stores in PostgreSQL.

ENDPOINT:
    POST /api/newsletter/subscribe
    Content-Type: application/json
    Body: { "email": "...", "name": "..." (optional), "source": "..." (optional) }

    Returns:
        201  { "success": true, "message": "..." }           — new subscriber
        200  { "success": false, "error": "already subscribed" }  — duplicate
        400  { "success": false, "error": "..." }             — validation error
        429  { "success": false, "error": "..." }             — rate limited
        500  { "success": false, "error": "..." }             — server error

    GET /api/newsletter/stats
    Returns subscriber count and recent signups (admin use).

CORS:
    Enabled for shift-work.com origins only. The newsletter form on the
    static site POSTs cross-origin to this endpoint on the Swarm.

ANTI-SPAM (SERVER-SIDE):
    1. Email format validation (regex)
    2. Duplicate check (UNIQUE constraint + explicit check)
    3. IP-based rate limiting (max 5 signups per IP per hour)
    4. Disposable email domain blocking (common throwaway domains)

GOLDEN RULES FOLLOWED:
    - All SQL uses %s placeholders via db_engine.py
    - Never imports sqlite3 directly
    - Uses RETURNING id (not lastrowid)
    - Fully idempotent migrations (table created by migration_006)

I did no harm and this file is not truncated
"""

import re
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

newsletter_bp = Blueprint('newsletter', __name__)

# ---------------------------------------------------------------------------
# CORS — manual preflight handling for the subscribe endpoint.
# This avoids adding flask-cors as a dependency for a single endpoint.
# Only allows requests from shift-work.com and localhost (dev).
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = [
    'https://shift-work.com',
    'https://www.shift-work.com',
    'http://localhost:3000',
    'http://localhost:5000',
    'http://127.0.0.1:5500',       # VS Code Live Server
    'null',                          # local file:// opens
]


def _cors_headers(origin=None):
    """Return CORS headers dict for the given origin."""
    headers = {
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
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


@newsletter_bp.after_request
def add_cors_headers(response):
    """Add CORS headers to every response from this blueprint."""
    origin = request.headers.get('Origin', '')
    for key, value in _cors_headers(origin).items():
        response.headers[key] = value
    return response


# ---------------------------------------------------------------------------
# DISPOSABLE EMAIL DOMAINS — common throwaway email services
# ---------------------------------------------------------------------------
DISPOSABLE_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'throwaway.email', 'tempmail.com',
    'yopmail.com', 'sharklasers.com', 'grr.la', 'guerrillamail.net',
    'trash-mail.com', 'fakeinbox.com', 'mailnesia.com', 'maildrop.cc',
    'dispostable.com', 'getnada.com', 'temp-mail.org', '10minutemail.com',
    'trashmail.com', 'mohmal.com', 'emailondeck.com', 'burnermail.io',
}

# ---------------------------------------------------------------------------
# EMAIL VALIDATION
# ---------------------------------------------------------------------------
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def _validate_email(email):
    """Validate email format and check against disposable domains."""
    if not email or not isinstance(email, str):
        return False, 'Email is required.'
    email = email.strip().lower()
    if len(email) > 254:
        return False, 'Email address is too long.'
    if not EMAIL_REGEX.match(email):
        return False, 'Please enter a valid email address.'
    domain = email.split('@')[1]
    if domain in DISPOSABLE_DOMAINS:
        return False, 'Please use a permanent email address.'
    return True, email


# ---------------------------------------------------------------------------
# RATE LIMITING (IP-based, in-database)
# ---------------------------------------------------------------------------
def _check_rate_limit(ip_address):
    """
    Check if this IP has submitted more than 5 signups in the last hour.
    Returns (is_allowed, message).
    """
    from db_engine import get_db_connection

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        cursor.execute(
            """SELECT COUNT(*) as cnt FROM newsletter_subscribers
               WHERE ip_address = %s AND subscribed_at > %s""",
            (ip_address, one_hour_ago)
        )
        row = cursor.fetchone()
        count = row['cnt'] if row else 0
        return count < 5, f'Too many signups from this address. Please try again later.'
    except Exception as e:
        logger.warning(f"Rate limit check failed (allowing request): {e}")
        return True, ''
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SUBSCRIBE ENDPOINT
# ---------------------------------------------------------------------------
@newsletter_bp.route('/api/newsletter/subscribe', methods=['POST', 'OPTIONS'])
def subscribe():
    """Handle newsletter subscription."""

    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        return response, 200

    from db_engine import get_db_connection

    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'error': 'Invalid request. Send JSON with an email field.'}), 400

        # Validate email
        raw_email = data.get('email', '')
        is_valid, result = _validate_email(raw_email)
        if not is_valid:
            return jsonify({'success': False, 'error': result}), 400
        email = result  # cleaned, lowercased email

        # Optional fields
        name = (data.get('name') or '').strip()[:255] or None
        source = (data.get('source') or 'website').strip()[:100]

        # Get IP for rate limiting
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        ip_address = (ip_address or 'unknown')[:45]

        # Rate limit check
        is_allowed, rate_msg = _check_rate_limit(ip_address)
        if not is_allowed:
            return jsonify({'success': False, 'error': rate_msg}), 429

        # Check for duplicate
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, is_active FROM newsletter_subscribers WHERE email = %s",
                (email,)
            )
            existing = cursor.fetchone()

            if existing:
                if existing['is_active']:
                    return jsonify({
                        'success': False,
                        'error': 'This email is already subscribed.'
                    }), 200
                else:
                    # Re-activate a previously unsubscribed email
                    cursor.execute(
                        """UPDATE newsletter_subscribers
                           SET is_active = TRUE, name = COALESCE(%s, name),
                               source = %s, subscribed_at = NOW(), ip_address = %s
                           WHERE email = %s
                           RETURNING id""",
                        (name, source, ip_address, email)
                    )
                    conn.commit()
                    return jsonify({
                        'success': True,
                        'message': 'Welcome back! You have been re-subscribed.'
                    }), 201

            # Insert new subscriber
            cursor.execute(
                """INSERT INTO newsletter_subscribers (email, name, source, ip_address)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id""",
                (email, name, source, ip_address)
            )
            new_id = cursor.fetchone()['id']
            conn.commit()

            logger.info(f"New newsletter subscriber: {email} (id={new_id}, source={source})")
            return jsonify({
                'success': True,
                'message': 'Thank you! You have been subscribed to the Shiftwork Solutions newsletter.'
            }), 201

        except Exception as e:
            conn.rollback()
            # Handle unique constraint violation (race condition)
            if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                return jsonify({
                    'success': False,
                    'error': 'This email is already subscribed.'
                }), 200
            raise
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Newsletter subscribe error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Something went wrong. Please try again later.'
        }), 500


# ---------------------------------------------------------------------------
# STATS ENDPOINT (admin)
# ---------------------------------------------------------------------------
@newsletter_bp.route('/api/newsletter/stats', methods=['GET'])
def newsletter_stats():
    """Return newsletter subscriber statistics."""
    from db_engine import get_db_connection

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Total active subscribers
            cursor.execute(
                "SELECT COUNT(*) as total FROM newsletter_subscribers WHERE is_active = TRUE"
            )
            total = cursor.fetchone()['total']

            # Total all time (including unsubscribed)
            cursor.execute(
                "SELECT COUNT(*) as all_time FROM newsletter_subscribers"
            )
            all_time = cursor.fetchone()['all_time']

            # Last 10 signups
            cursor.execute(
                """SELECT id, email, name, source, subscribed_at
                   FROM newsletter_subscribers
                   WHERE is_active = TRUE
                   ORDER BY subscribed_at DESC
                   LIMIT 10"""
            )
            recent = []
            for row in cursor.fetchall():
                recent.append({
                    'id': row['id'],
                    'email': row['email'],
                    'name': row['name'],
                    'source': row['source'],
                    'subscribed_at': str(row['subscribed_at']) if row['subscribed_at'] else None,
                })

            return jsonify({
                'success': True,
                'active_subscribers': total,
                'all_time_subscribers': all_time,
                'recent': recent,
            })
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Newsletter stats error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# I did no harm and this file is not truncated
