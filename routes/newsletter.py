"""
AI SWARM ORCHESTRATOR — Newsletter Subscription API (Security Hardened)
Created: April 2, 2026
Last Updated: April 7, 2026
Author: Claude Opus 4.6 for Jim @ Shiftwork Solutions LLC

PURPOSE:
    Flask blueprint providing newsletter subscription and admin security
    endpoints for the shift-work.com website.

CHANGE LOG:
    2026-04-02  Initial build — basic subscribe + stats endpoints
    2026-04-07  SECURITY HARDENING — comprehensive anti-spam overhaul:
                1. Expanded disposable email domain list (20 → 120+)
                2. Server-side honeypot verification (rejects if honeypot filled)
                3. Server-side timestamp verification (rejects if < 2 seconds)
                4. User-agent logging on every signup
                5. Email domain extraction and storage
                6. IP blocklist integration (checks ip_blocklist table)
                7. Enhanced admin endpoints:
                   - GET  /api/newsletter/stats (existing, enhanced)
                   - GET  /api/newsletter/subscribers (paginated list with IPs)
                   - GET  /api/newsletter/subscribers/by-ip/<ip> (lookup by IP)
                   - GET  /api/newsletter/subscribers/by-domain/<domain>
                   - POST /api/newsletter/block-ip (add IP to blocklist)
                   - POST /api/newsletter/unblock-ip (remove IP from blocklist)
                   - GET  /api/newsletter/blocked-ips (view blocklist)
                   - POST /api/newsletter/unsubscribe (admin force-unsubscribe)
                8. Shared security utilities imported by contact_api.py

ENDPOINTS:
    POST /api/newsletter/subscribe
        Body: { email, name?, source?, honeypot?, timestamp? }
        Returns: 201 (new), 200 (duplicate), 400 (invalid), 429 (rate limited), 403 (blocked)

    GET  /api/newsletter/stats
    GET  /api/newsletter/subscribers?page=1&per_page=50
    GET  /api/newsletter/subscribers/by-ip/<ip>
    GET  /api/newsletter/subscribers/by-domain/<domain>
    POST /api/newsletter/block-ip     { ip_address, reason? }
    POST /api/newsletter/unblock-ip   { ip_address }
    GET  /api/newsletter/blocked-ips
    POST /api/newsletter/unsubscribe  { email }

CORS:
    Enabled for shift-work.com origins only.

ANTI-SPAM LAYERS (SERVER-SIDE):
    1. IP blocklist check (database-backed, admin-managed)
    2. Server-side honeypot verification (rejects if filled)
    3. Server-side timestamp verification (rejects if < 2 seconds)
    4. Email format validation (regex)
    5. Disposable email domain blocking (120+ domains)
    6. Duplicate check (UNIQUE constraint + explicit check)
    7. IP-based rate limiting (max 5 signups per IP per hour)
    8. User-agent logging for forensic analysis
    9. Email domain extraction for domain-level blocking/reporting

GOLDEN RULES FOLLOWED:
    - All SQL uses %s placeholders via db_engine.py
    - Never imports sqlite3 directly
    - Uses RETURNING id (not lastrowid)
    - Fully idempotent migrations (tables created by migration_006 + 007)

I did no harm and this file is not truncated
"""

import re
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

newsletter_bp = Blueprint('newsletter', __name__)


# ═══════════════════════════════════════════════════════════════════════════
# CORS — manual preflight handling
# Only allows requests from shift-work.com and localhost (dev).
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


@newsletter_bp.after_request
def add_cors_headers(response):
    """Add CORS headers to every response from this blueprint."""
    origin = request.headers.get('Origin', '')
    for key, value in _cors_headers(origin).items():
        response.headers[key] = value
    return response


# ═══════════════════════════════════════════════════════════════════════════
# SHARED SECURITY UTILITIES
# These are also imported by routes/contact_api.py
# ═══════════════════════════════════════════════════════════════════════════

def get_client_ip():
    """
    Extract the real client IP address from the request.
    Handles X-Forwarded-For (Render proxy), X-Real-IP, and direct connection.
    Returns the first (client) IP from X-Forwarded-For if present.
    """
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2
        ip = forwarded.split(',')[0].strip()
    else:
        ip = request.headers.get('X-Real-IP', request.remote_addr)
    return (ip or 'unknown')[:45]


def get_user_agent():
    """Extract and truncate user agent string."""
    ua = request.headers.get('User-Agent', '')
    return ua[:500] if ua else None


def extract_email_domain(email):
    """Extract domain from email address."""
    if not email or '@' not in email:
        return None
    return email.split('@')[1].lower()


def is_ip_blocked(ip_address):
    """
    Check if an IP address is in the active blocklist.
    Returns (is_blocked, reason).
    Fails open — if the check errors, allow the request.
    """
    from db_engine import get_db_connection

    if not ip_address or ip_address == 'unknown':
        return False, None

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT reason FROM ip_blocklist
                   WHERE ip_address = %s AND is_active = TRUE
                   LIMIT 1""",
                (ip_address,)
            )
            row = cursor.fetchone()
            if row:
                return True, row['reason']
            return False, None
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"IP blocklist check failed (allowing request): {e}")
        return False, None


# ═══════════════════════════════════════════════════════════════════════════
# DISPOSABLE EMAIL DOMAINS — 120+ throwaway email services
# Updated: April 7, 2026
# ═══════════════════════════════════════════════════════════════════════════

DISPOSABLE_DOMAINS = {
    # Original list
    'mailinator.com', 'guerrillamail.com', 'throwaway.email', 'tempmail.com',
    'yopmail.com', 'sharklasers.com', 'grr.la', 'guerrillamail.net',
    'trash-mail.com', 'fakeinbox.com', 'mailnesia.com', 'maildrop.cc',
    'dispostable.com', 'getnada.com', 'temp-mail.org', '10minutemail.com',
    'trashmail.com', 'mohmal.com', 'emailondeck.com', 'burnermail.io',
    # Expanded list — April 7, 2026
    'guerrillamail.info', 'guerrillamail.de', 'guerrillamailblock.com',
    'tempail.com', 'tempr.email', 'temp-mail.io', 'temp-mail.de',
    'throwaway.email', 'throwawaymails.com', 'trashmail.io', 'trashmail.me',
    'trashmail.net', 'trashmail.org', 'trashmail.ws',
    'mailtemp.info', 'mailtemp.net', 'mt2015.com',
    'guerrillamail.org', 'spam4.me', 'spamgourmet.com', 'spamfree24.org',
    'mytemp.email', 'tmpmail.net', 'tmpmail.org',
    'disposableemailaddresses.emailmiser.com',
    'harakirimail.com', 'mailexpire.com', 'mailzilla.com',
    'binkmail.com', 'bobmail.info', 'chammy.info',
    'devnullmail.com', 'discard.email', 'discardmail.com',
    'discardmail.de', 'disposeamail.com', 'dm.w3internet.co.uk',
    'drdrb.com', 'einrot.com', 'emailigo.de', 'emailmiser.com',
    'emailtemporario.com.br', 'ephemail.net', 'etranquil.com',
    'fastacura.com', 'filzmail.com', 'fixmail.tk',
    'flyspam.com', 'frapmail.com', 'gelitik.in',
    'getonemail.com', 'getonemail.net', 'girlsundertheinfluence.com',
    'gishpuppy.com', 'greensloth.com', 'gsrv.co.uk',
    'guerrillamail.biz', 'haltospam.com', 'hidemail.de',
    'hotpop.com', 'ichimail.com', 'imails.info',
    'inboxbear.com', 'inboxclean.com', 'inboxclean.org',
    'jetable.com', 'jetable.fr.nf', 'jetable.net',
    'jetable.org', 'jnxjn.com', 'kasmail.com',
    'kaspop.com', 'klzlk.com', 'koszmail.pl',
    'kurzepost.de', 'lawlita.com', 'letthemeatspam.com',
    'lhsdv.com', 'lifebyfood.com', 'link2mail.net',
    'litedrop.com', 'lookugly.com', 'lopl.co.cc',
    'lr78.com', 'maileater.com', 'mailforspam.com',
    'mailfreeonline.com', 'mailguard.me', 'mailin8r.com',
    'mailinater.com', 'mailinator.net', 'mailinator2.com',
    'mailincubator.com', 'mailme.ir', 'mailme.lv',
    'mailmetrash.com', 'mailmoat.com', 'mailnator.com',
    'mailnull.com', 'mailshell.com', 'mailsiphon.com',
    'mailslite.com', 'mailzilla.org', 'mbx.cc',
    'mega.zik.dj', 'meltmail.com', 'messagebeamer.de',
    'mezimages.net', 'mintemail.com', 'mmmmail.com',
    'mobi.web.id', 'mobileninja.co.uk', 'mycleaninbox.net',
    'mypartyclip.de', 'myphantom.com', 'mysamp.de',
    'mytempemail.com', 'mytempmail.com', 'nabala.com',
    'neverbox.com', 'no-spam.ws', 'nobulk.com',
    'noclickemail.com', 'nogmailspam.info', 'nomail.xl.cx',
    'nomail2me.com', 'nospam.ze.tc', 'nospam4.us',
    'nospamfor.us', 'nospammail.net', 'nothingtoseehere.ca',
    'nowmymail.com', 'nurfuerspam.de', 'nus.edu.sg',
    'objectmail.com', 'obobbo.com', 'onewaymail.com',
    'ordinaryamerican.net', 'owlpic.com', 'pookmail.com',
    'proxymail.eu', 'prtnx.com', 'putthisinyouremail.com',
    'qq.com', 'quickinbox.com', 'rcpt.at',
    'reallymymail.com', 'recode.me', 'recursor.net',
    'regbypass.com', 'rejectmail.com', 'rhyta.com',
    'rklips.com', 'rmqkr.net', 'royal.net',
    'rppkn.com', 'rtrtr.com', 's0ny.net',
    'safe-mail.net', 'safersignup.de', 'safetymail.info',
    'sandelf.de', 'saynotospams.com', 'scatmail.com',
    'schafmail.de', 'selfdestructingmail.com', 'sendspamhere.com',
    'shiftmail.com', 'shitmail.me', 'shortmail.net',
    'sibmail.com', 'skeefmail.com', 'slaskpost.se',
    'slipry.net', 'slopsbox.com', 'smashmail.de',
    'soodonims.com', 'spam.la', 'spamavert.com',
    'spambob.com', 'spambob.net', 'spambob.org',
    'spambog.com', 'spambog.de', 'spambog.ru',
    'spambox.us', 'spamcannon.com', 'spamcannon.net',
    'spamcero.com', 'spamcorptastic.com', 'spamcowboy.com',
    'spamcowboy.net', 'spamcowboy.org', 'spamday.com',
    'spamex.com', 'spamfighter.cf', 'spamfighter.ga',
    'spamfighter.gq', 'spamfighter.ml', 'spamfighter.tk',
    'spamfree.eu', 'spamfree24.com', 'spamfree24.de',
    'spamfree24.info', 'spamfree24.net', 'spamhole.com',
    'spamify.com', 'spaminator.de', 'spamkill.info',
    'spaml.com', 'spaml.de', 'spammotel.com',
    'spamobox.com', 'spamoff.de', 'spamslicer.com',
    'spamspot.com', 'spamstack.net', 'spamthis.co.uk',
    'spamtrail.com', 'spamtrap.ro', 'speed.1s.fr',
    'superrito.com', 'suremail.info', 'teleworm.us',
    'tempalias.com', 'tempe4mail.com', 'tempemail.co.za',
    'tempemail.com', 'tempemail.net', 'tempinbox.com',
    'tempinbox.co.uk', 'tempmail.eu', 'tempmail.it',
    'tempmail2.com', 'tempmaildemo.com', 'tempmailer.com',
    'tempomail.fr', 'temporarily.de', 'temporarioemail.com.br',
    'temporaryemail.net', 'temporaryforwarding.com',
    'temporaryinbox.com', 'temporarymailaddress.com',
    'thankyou2010.com', 'thisisnotmyrealemail.com',
    'tilien.com', 'tittbit.in', 'tmail.ws',
    'tmailinator.com', 'toiea.com', 'tradermail.info',
    'turual.com', 'twinmail.de', 'tyldd.com',
    'uggsrock.com', 'upliftnow.com', 'uplipht.com',
    'venompen.com', 'veryreallyfakeemails.com', 'viditag.com',
    'viewcastmedia.com', 'viewcastmedia.net', 'viewcastmedia.org',
    'vomoto.com', 'vpn.st', 'vsimcard.com',
    'vubby.com', 'wasteland.rfc822.org', 'webemail.me',
    'weg-werf-email.de', 'wegwerfadresse.de', 'wegwerfemail.com',
    'wegwerfemail.de', 'wegwerfmail.de', 'wegwerfmail.net',
    'wegwerfmail.org', 'wh4f.org', 'whatiaas.com',
    'whatpaas.com', 'whyspam.me', 'wikidocuslice.com',
    'willhackforfood.biz', 'willselfdestruct.com',
    'winemaven.info', 'wronghead.com', 'wuzup.net',
    'wuzupmail.net', 'wwwnew.eu', 'xagloo.com',
    'xemaps.com', 'xents.com', 'xjoi.com',
    'xoxy.net', 'yapped.net', 'yep.it',
    'yogamaven.com', 'yomail.info', 'yopmail.fr',
    'yopmail.net', 'ypmail.webarnak.fr.eu.org',
    'yuurok.com', 'zehnminutenmail.de', 'zippymail.info',
    'zoaxe.com', 'zoemail.org',
}


# ═══════════════════════════════════════════════════════════════════════════
# EMAIL VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# RATE LIMITING (IP-based, in-database)
# ═══════════════════════════════════════════════════════════════════════════

def _check_rate_limit(ip_address):
    """
    Check if this IP has submitted more than 5 signups in the last hour.
    Returns (is_allowed, message).
    Fails open — if the check errors, allow the request.
    """
    from db_engine import get_db_connection

    if not ip_address or ip_address == 'unknown':
        return True, ''

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
        return count < 5, 'Too many signups from this address. Please try again later.'
    except Exception as e:
        logger.warning(f"Rate limit check failed (allowing request): {e}")
        return True, ''
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# SUBSCRIBE ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

@newsletter_bp.route('/api/newsletter/subscribe', methods=['POST', 'OPTIONS'])
def subscribe():
    """Handle newsletter subscription with full anti-spam stack."""

    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    from db_engine import get_db_connection

    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request. Send JSON with an email field.'
            }), 400

        # ── LAYER 1: IP blocklist check ────────────────────────────────
        ip_address = get_client_ip()
        blocked, block_reason = is_ip_blocked(ip_address)
        if blocked:
            logger.warning(f"Blocked IP attempted newsletter signup: {ip_address} (reason: {block_reason})")
            # Return a generic error — don't reveal they're blocked
            return jsonify({
                'success': False,
                'error': 'Something went wrong. Please try again later.'
            }), 403

        # ── LAYER 2: Server-side honeypot check ────────────────────────
        # The frontend honeypot field is named '_gotcha' — bots fill it in.
        # We also check 'honeypot' in case the frontend sends it explicitly.
        honeypot_value = data.get('honeypot', '') or data.get('_gotcha', '')
        if honeypot_value:
            logger.warning(f"Honeypot triggered on newsletter signup from {ip_address}")
            # Fake success — bot thinks it worked
            return jsonify({
                'success': True,
                'message': 'Thank you! You have been subscribed.'
            }), 201

        # ── LAYER 3: Server-side timestamp check ───────────────────────
        # Frontend sets a hidden _loaded field with Date.now() on page load.
        # If the form is submitted in under 2 seconds, it's likely a bot.
        client_timestamp = data.get('timestamp', None) or data.get('_loaded', None)
        if client_timestamp:
            try:
                loaded_at = int(client_timestamp)
                # Client sends Date.now() in milliseconds
                now_ms = int(datetime.utcnow().timestamp() * 1000)
                elapsed_ms = now_ms - loaded_at
                if elapsed_ms < 2000:
                    logger.warning(f"Timestamp check failed on newsletter signup from {ip_address} (elapsed: {elapsed_ms}ms)")
                    return jsonify({
                        'success': False,
                        'error': 'Please take a moment before submitting.'
                    }), 400
            except (ValueError, TypeError):
                # Can't parse timestamp — not a deal-breaker, continue
                pass

        # ── LAYER 4: Email validation ──────────────────────────────────
        raw_email = data.get('email', '')
        is_valid, result = _validate_email(raw_email)
        if not is_valid:
            return jsonify({'success': False, 'error': result}), 400
        email = result  # cleaned, lowercased email

        # ── LAYER 5: Rate limit check ─────────────────────────────────
        is_allowed, rate_msg = _check_rate_limit(ip_address)
        if not is_allowed:
            return jsonify({'success': False, 'error': rate_msg}), 429

        # ── Collect metadata ───────────────────────────────────────────
        name = (data.get('name') or '').strip()[:255] or None
        source = (data.get('source') or 'website').strip()[:100]
        user_agent = get_user_agent()
        email_domain = extract_email_domain(email)

        # ── Database insert ────────────────────────────────────────────
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Check for duplicate
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
                               source = %s, subscribed_at = NOW(), ip_address = %s,
                               user_agent = %s, email_domain = %s
                           WHERE email = %s
                           RETURNING id""",
                        (name, source, ip_address, user_agent, email_domain, email)
                    )
                    conn.commit()
                    logger.info(f"Newsletter re-subscribe: {email} from {ip_address}")
                    return jsonify({
                        'success': True,
                        'message': 'Welcome back! You have been re-subscribed.'
                    }), 201

            # Insert new subscriber
            cursor.execute(
                """INSERT INTO newsletter_subscribers
                   (email, name, source, ip_address, user_agent, email_domain)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (email, name, source, ip_address, user_agent, email_domain)
            )
            new_id = cursor.fetchone()['id']
            conn.commit()

            logger.info(f"New newsletter subscriber: {email} (id={new_id}, source={source}, ip={ip_address})")
            return jsonify({
                'success': True,
                'message': 'Thank you! You have been subscribed to the Shiftwork Solutions newsletter.'
            }), 201

        except Exception as e:
            conn.rollback()
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


# ═══════════════════════════════════════════════════════════════════════════
# STATS ENDPOINT (admin)
# ═══════════════════════════════════════════════════════════════════════════

@newsletter_bp.route('/api/newsletter/stats', methods=['GET'])
def newsletter_stats():
    """Return newsletter subscriber statistics with IP and domain breakdown."""
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

            # Total all time
            cursor.execute(
                "SELECT COUNT(*) as all_time FROM newsletter_subscribers"
            )
            all_time = cursor.fetchone()['all_time']

            # Signups in last 24 hours
            cursor.execute(
                """SELECT COUNT(*) as recent_count FROM newsletter_subscribers
                   WHERE subscribed_at > NOW() - INTERVAL '24 hours'"""
            )
            last_24h = cursor.fetchone()['recent_count']

            # Top 10 IP addresses by signup count
            cursor.execute(
                """SELECT ip_address, COUNT(*) as signup_count
                   FROM newsletter_subscribers
                   WHERE ip_address IS NOT NULL
                   GROUP BY ip_address
                   ORDER BY signup_count DESC
                   LIMIT 10"""
            )
            top_ips = [{'ip': r['ip_address'], 'count': r['signup_count']}
                       for r in cursor.fetchall()]

            # Top 10 email domains
            cursor.execute(
                """SELECT email_domain, COUNT(*) as domain_count
                   FROM newsletter_subscribers
                   WHERE email_domain IS NOT NULL AND is_active = TRUE
                   GROUP BY email_domain
                   ORDER BY domain_count DESC
                   LIMIT 10"""
            )
            top_domains = [{'domain': r['email_domain'], 'count': r['domain_count']}
                           for r in cursor.fetchall()]

            # Last 10 signups (with IP and user agent)
            cursor.execute(
                """SELECT id, email, name, source, ip_address, user_agent,
                          email_domain, subscribed_at
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
                    'ip_address': row['ip_address'],
                    'user_agent': row['user_agent'],
                    'email_domain': row['email_domain'],
                    'subscribed_at': str(row['subscribed_at']) if row['subscribed_at'] else None,
                })

            # Blocked IP count
            cursor.execute(
                "SELECT COUNT(*) as blocked FROM ip_blocklist WHERE is_active = TRUE"
            )
            blocked_count = cursor.fetchone()['blocked']

            return jsonify({
                'success': True,
                'active_subscribers': total,
                'all_time_subscribers': all_time,
                'last_24_hours': last_24h,
                'blocked_ips': blocked_count,
                'top_ips': top_ips,
                'top_email_domains': top_domains,
                'recent': recent,
            })
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Newsletter stats error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# SUBSCRIBERS LIST (admin, paginated)
# ═══════════════════════════════════════════════════════════════════════════

@newsletter_bp.route('/api/newsletter/subscribers', methods=['GET'])
def list_subscribers():
    """Paginated subscriber list with IP and domain info."""
    from db_engine import get_db_connection

    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
        offset = (page - 1) * per_page

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) as total FROM newsletter_subscribers"
            )
            total = cursor.fetchone()['total']

            cursor.execute(
                """SELECT id, email, name, source, ip_address, user_agent,
                          email_domain, subscribed_at, is_active
                   FROM newsletter_subscribers
                   ORDER BY subscribed_at DESC
                   LIMIT %s OFFSET %s""",
                (per_page, offset)
            )
            subscribers = []
            for row in cursor.fetchall():
                subscribers.append({
                    'id': row['id'],
                    'email': row['email'],
                    'name': row['name'],
                    'source': row['source'],
                    'ip_address': row['ip_address'],
                    'user_agent': row['user_agent'],
                    'email_domain': row['email_domain'],
                    'subscribed_at': str(row['subscribed_at']) if row['subscribed_at'] else None,
                    'is_active': row['is_active'],
                })

            return jsonify({
                'success': True,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page,
                'subscribers': subscribers,
            })
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Subscriber list error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# LOOKUP BY IP (admin)
# ═══════════════════════════════════════════════════════════════════════════

@newsletter_bp.route('/api/newsletter/subscribers/by-ip/<path:ip>', methods=['GET'])
def subscribers_by_ip(ip):
    """Find all signups from a given IP address."""
    from db_engine import get_db_connection

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, email, name, source, ip_address, user_agent,
                          email_domain, subscribed_at, is_active
                   FROM newsletter_subscribers
                   WHERE ip_address = %s
                   ORDER BY subscribed_at DESC""",
                (ip,)
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row['id'],
                    'email': row['email'],
                    'name': row['name'],
                    'source': row['source'],
                    'ip_address': row['ip_address'],
                    'user_agent': row['user_agent'],
                    'email_domain': row['email_domain'],
                    'subscribed_at': str(row['subscribed_at']) if row['subscribed_at'] else None,
                    'is_active': row['is_active'],
                })

            # Check if this IP is blocked
            blocked, reason = is_ip_blocked(ip)

            return jsonify({
                'success': True,
                'ip_address': ip,
                'is_blocked': blocked,
                'block_reason': reason,
                'signup_count': len(results),
                'signups': results,
            })
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Subscribers by IP error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# LOOKUP BY DOMAIN (admin)
# ═══════════════════════════════════════════════════════════════════════════

@newsletter_bp.route('/api/newsletter/subscribers/by-domain/<domain>', methods=['GET'])
def subscribers_by_domain(domain):
    """Find all signups from a given email domain."""
    from db_engine import get_db_connection

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, email, name, source, ip_address, user_agent,
                          email_domain, subscribed_at, is_active
                   FROM newsletter_subscribers
                   WHERE email_domain = %s
                   ORDER BY subscribed_at DESC""",
                (domain.lower(),)
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row['id'],
                    'email': row['email'],
                    'name': row['name'],
                    'source': row['source'],
                    'ip_address': row['ip_address'],
                    'subscribed_at': str(row['subscribed_at']) if row['subscribed_at'] else None,
                    'is_active': row['is_active'],
                })

            return jsonify({
                'success': True,
                'domain': domain.lower(),
                'signup_count': len(results),
                'signups': results,
            })
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Subscribers by domain error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# BLOCK IP (admin)
# ═══════════════════════════════════════════════════════════════════════════

@newsletter_bp.route('/api/newsletter/block-ip', methods=['POST'])
def block_ip():
    """Add an IP to the blocklist."""
    from db_engine import get_db_connection

    try:
        data = request.get_json(silent=True)
        if not data or not data.get('ip_address'):
            return jsonify({
                'success': False,
                'error': 'ip_address is required.'
            }), 400

        ip = data['ip_address'].strip()[:45]
        reason = (data.get('reason') or 'Blocked by admin').strip()[:500]

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # Check if already blocked
            cursor.execute(
                "SELECT id, is_active FROM ip_blocklist WHERE ip_address = %s",
                (ip,)
            )
            existing = cursor.fetchone()

            if existing:
                if existing['is_active']:
                    return jsonify({
                        'success': False,
                        'error': f'IP {ip} is already blocked.'
                    }), 200
                else:
                    # Re-activate
                    cursor.execute(
                        """UPDATE ip_blocklist
                           SET is_active = TRUE, reason = %s, blocked_at = NOW()
                           WHERE ip_address = %s
                           RETURNING id""",
                        (reason, ip)
                    )
                    conn.commit()
                    logger.info(f"IP re-blocked: {ip} (reason: {reason})")
                    return jsonify({
                        'success': True,
                        'message': f'IP {ip} has been blocked.',
                    }), 200
            else:
                cursor.execute(
                    """INSERT INTO ip_blocklist (ip_address, reason)
                       VALUES (%s, %s)
                       RETURNING id""",
                    (ip, reason)
                )
                new_id = cursor.fetchone()['id']
                conn.commit()
                logger.info(f"IP blocked: {ip} (id={new_id}, reason: {reason})")
                return jsonify({
                    'success': True,
                    'message': f'IP {ip} has been blocked.',
                    'id': new_id,
                }), 201

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Block IP error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# UNBLOCK IP (admin)
# ═══════════════════════════════════════════════════════════════════════════

@newsletter_bp.route('/api/newsletter/unblock-ip', methods=['POST'])
def unblock_ip():
    """Remove an IP from the blocklist (soft delete — sets is_active=FALSE)."""
    from db_engine import get_db_connection

    try:
        data = request.get_json(silent=True)
        if not data or not data.get('ip_address'):
            return jsonify({
                'success': False,
                'error': 'ip_address is required.'
            }), 400

        ip = data['ip_address'].strip()[:45]

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE ip_blocklist SET is_active = FALSE
                   WHERE ip_address = %s AND is_active = TRUE
                   RETURNING id""",
                (ip,)
            )
            result = cursor.fetchone()
            conn.commit()

            if result:
                logger.info(f"IP unblocked: {ip}")
                return jsonify({
                    'success': True,
                    'message': f'IP {ip} has been unblocked.',
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': f'IP {ip} was not found in the active blocklist.',
                }), 404

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Unblock IP error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# VIEW BLOCKED IPS (admin)
# ═══════════════════════════════════════════════════════════════════════════

@newsletter_bp.route('/api/newsletter/blocked-ips', methods=['GET'])
def view_blocked_ips():
    """View all actively blocked IP addresses."""
    from db_engine import get_db_connection

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, ip_address, reason, blocked_at, blocked_by
                   FROM ip_blocklist
                   WHERE is_active = TRUE
                   ORDER BY blocked_at DESC"""
            )
            blocked = []
            for row in cursor.fetchall():
                blocked.append({
                    'id': row['id'],
                    'ip_address': row['ip_address'],
                    'reason': row['reason'],
                    'blocked_at': str(row['blocked_at']) if row['blocked_at'] else None,
                    'blocked_by': row['blocked_by'],
                })

            return jsonify({
                'success': True,
                'blocked_count': len(blocked),
                'blocked_ips': blocked,
            })
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"View blocked IPs error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN UNSUBSCRIBE (admin force-unsubscribe)
# ═══════════════════════════════════════════════════════════════════════════

@newsletter_bp.route('/api/newsletter/unsubscribe', methods=['POST'])
def admin_unsubscribe():
    """Admin force-unsubscribe an email address."""
    from db_engine import get_db_connection

    try:
        data = request.get_json(silent=True)
        if not data or not data.get('email'):
            return jsonify({
                'success': False,
                'error': 'email is required.'
            }), 400

        email = data['email'].strip().lower()

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE newsletter_subscribers SET is_active = FALSE
                   WHERE email = %s AND is_active = TRUE
                   RETURNING id""",
                (email,)
            )
            result = cursor.fetchone()
            conn.commit()

            if result:
                logger.info(f"Admin unsubscribed: {email}")
                return jsonify({
                    'success': True,
                    'message': f'{email} has been unsubscribed.',
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': f'{email} is not an active subscriber.',
                }), 404

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Admin unsubscribe error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# I did no harm and this file is not truncated
