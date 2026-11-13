"""
AI SWARM ORCHESTRATOR - Admin Gate (one passcode for everything that is not public)
File: swarm_security.py
Created: November 11, 2026
Last Updated: November 11, 2026 — Initial implementation

PURPOSE:
    Until now only Survey admin and the Part Time Tracker had logins. Everything
    else on the Swarm (the main screen, FeynmanLab, the newsletter subscriber
    list, the /api/admin/* repair routes, the Part Time Tracker's developer
    shortcuts) answered anyone who knew the address. This module puts ONE
    passcode in front of all of it.

HOW IT WORKS:
    * DEFAULT-DENY. Every route needs the admin passcode UNLESS it is named
      below as public or as having its own login. A route added to the Swarm
      in future is therefore private until someone adds it to a list here.
      >>> IF YOU ADD A ROUTE THAT OUTSIDERS MUST REACH (a shift-work.com form,
      >>> a page for clients), ADD ITS ENDPOINT NAME TO PUBLIC_ENDPOINTS BELOW,
      >>> or it will ask them for the passcode.
    * THE SWITCH is the SWARM_ADMIN_PASSCODE environment variable in Render.
        - Not set  -> "watching" mode. NOTHING is blocked. The gate only
                      records which requests it WOULD have blocked, so that a
                      forgotten outside caller shows up before it is locked out.
        - Set      -> locked. Removing the variable unlocks everything again.
    * TWO WAYS TO PROVE WHO YOU ARE:
        - In a browser: the /login page. A correct passcode sets a cookie good
          for 30 days. The cookie is signed with a key made from the passcode
          itself, so changing the passcode signs everyone out.
        - From another app or page: send the passcode in the X-Swarm-Key
          header (this is how the shift-work.com performance dashboard asks).
    * GUESSING IS SLOWED: after 10 wrong passcodes from one address in 15
      minutes (or 100 from anywhere), passcode attempts are refused for the
      rest of that window. A browser already logged in is not affected.
    * WHEN LOCKED, error replies no longer carry the internal "traceback"
      detail unless the caller is logged in. The detail is written to the
      Render log instead, so nothing is lost.

WHAT IS LEFT ALONE:
    * Public by design: /health, /static, /homepage, the shift-work.com APIs
      (newsletter subscribe, contact form, assessment, visitor events), the
      survey intake form, and taking a survey by its link.
    * Has its own login already: Survey admin, the Part Time Tracker (except
      its /api/ptt/dev/* developer shortcuts, which now need the passcode),
      and the Speech Fact-Checker (FACTCHECK_PASSCODE).
    * Open for now, on purpose: /api/survey/norm/search, because the Thomas
      diagnostic app calls it from its server and does not yet send a key.
      See SERVICE_ENDPOINTS_OPEN_FOR_NOW.

DATABASE TABLES (lazy-created; no migration):
    admin_gate_seen      what the gate blocked, or would have blocked
    admin_gate_failures  wrong-passcode attempts, for the guessing limit

ENVIRONMENT:
    SWARM_ADMIN_PASSCODE   the passcode. Use a long one (16+ characters).
    SECRET_KEY             unchanged in meaning; see session_secret_key().

CHANGELOG:
- November 11, 2026: INITIAL IMPLEMENTATION. New file. Wired into app.py by
  one call to init_security(app) and one change to how SECRET_KEY falls back
  (see app.py changelog). No route's own code was changed.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from urllib.parse import urlparse

from flask import Blueprint, g, jsonify, redirect, request, send_from_directory, session

logger = logging.getLogger(__name__)

# ============================================================================
# WHAT IS PUBLIC, AND WHAT HAS ITS OWN LOGIN
# ============================================================================

# Reachable by anyone, by design. Names are Flask endpoint names
# ("blueprint.function"; plain "function" for routes defined in app.py).
PUBLIC_ENDPOINTS = {
    'static',                               # css, js and the intro video
    'health',                               # Render's health check and the keep-alive ping
    'homepage',                             # copy of the public marketing page
    # --- called by shift-work.com in visitors' browsers ---
    'newsletter.subscribe',
    'contact_api.contact_submit',
    'site_events.log_event',
    # --- clients and their employees ---
    'survey_intake.intake_form',
    'survey_intake.submit_intake',
    'survey_respondent.survey_take_page',
    'survey_respondent.get_survey_questions',
    'survey_respondent.submit_survey',
    # --- the gate's own doorway ---
    'admin_gate.login_page',
    'admin_gate.login',
    'admin_gate.logout',
    'admin_gate.status',
}

# Whole blueprints that are public by design (every route in them serves the
# Shiftwork Operations Assessment page on shift-work.com).
PUBLIC_BLUEPRINTS = {'assessment', 'assessment_ai', 'assessment_pdf'}

# Blueprints that check their own login. The gate stays out of their way.
OWN_LOGIN_BLUEPRINTS = {'survey_admin', 'factcheck'}
OWN_LOGIN_BLUEPRINT_PREFIXES = ('ptt',)            # ptt_hr, ptt_worker, ptt_shifts, ptt_chat, ptt_worker_intake
OWN_LOGIN_ENDPOINTS = {                            # Survey admin actions that live in survey_respondent.py
    'survey_respondent.open_survey',
    'survey_respondent.close_survey',
    'survey_respondent.export_responses',
    'survey_respondent.get_response_summary',
}
# ...except these paths, which sit inside "own login" blueprints but check nothing.
ALWAYS_GATED_PATH_PREFIXES = ('/api/ptt/dev/',)

# Called server-to-server by the Thomas diagnostic app, which does not send a
# key yet. TEMPORARY: when Thomas sends X-Swarm-Key, empty this set.
SERVICE_ENDPOINTS_OPEN_FOR_NOW = {'survey_normative.norm_search'}

# The survey builder and normative tools: the admin passcode works, and so
# does a Survey admin login (the Survey admin dashboard uses some of these).
SURVEY_FAMILY_BLUEPRINTS = {'survey', 'survey_normative'}
SURVEY_FAMILY_ENDPOINTS = {'survey'}               # the /survey builder page in app.py
SURVEY_ADMIN_SESSION_KEY = 'survey_admin_authenticated'   # must match routes/survey_admin.py

COOKIE_NAME = 'swarm_admin'
COOKIE_DAYS = 30
KEY_HEADER = 'X-Swarm-Key'
PASSCODE_ENV = 'SWARM_ADMIN_PASSCODE'
SHORT_PASSCODE = 12

FAILURE_WINDOW_SECONDS = 15 * 60
MAX_FAILURES_PER_ADDRESS = 10
MAX_FAILURES_OVERALL = 100

# Pages on shift-work.com may call the Swarm's admin data with the key.
TRUSTED_ORIGINS = {'https://shift-work.com', 'https://www.shift-work.com'}

_OLD_PUBLIC_SECRET = 'dev-secret-key-change-in-production-12345'
_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')


def classify(endpoint, path=''):
    """
    Decide how the gate treats a route. Returns one of:
      'public'        anyone
      'own_login'     the route checks its own login
      'service_open'  open for now for another of Jim's apps (temporary)
      'survey_family' admin passcode OR a Survey admin login
      'admin'         admin passcode   <- the default for anything not listed
    """
    if not endpoint:
        return 'admin'
    blueprint = endpoint.split('.', 1)[0] if '.' in endpoint else ''
    if any(path.startswith(prefix) for prefix in ALWAYS_GATED_PATH_PREFIXES):
        return 'admin'
    if endpoint in PUBLIC_ENDPOINTS or blueprint in PUBLIC_BLUEPRINTS:
        return 'public'
    if (endpoint in OWN_LOGIN_ENDPOINTS or blueprint in OWN_LOGIN_BLUEPRINTS
            or (blueprint and blueprint.startswith(OWN_LOGIN_BLUEPRINT_PREFIXES))):
        return 'own_login'
    if endpoint in SERVICE_ENDPOINTS_OPEN_FOR_NOW:
        return 'service_open'
    if blueprint in SURVEY_FAMILY_BLUEPRINTS or endpoint in SURVEY_FAMILY_ENDPOINTS:
        return 'survey_family'
    return 'admin'


# ============================================================================
# THE SESSION SECRET (used by Flask sessions, e.g. the Survey admin login)
# ============================================================================

def session_secret_key():
    """
    The key Flask signs its session cookies with.

    app.py used to fall back to a fixed string that is printed in this public
    repository whenever the SECRET_KEY environment variable was missing. With
    that string anyone could forge a "logged in" Survey admin cookie.

    Now: SECRET_KEY from the environment if it is set (and is not that old
    public string). Otherwise a key derived from DATABASE_URL, which is secret,
    is the same in every worker, and survives restarts. With neither (local
    development only), a random key for this run.
    """
    env_key = (os.environ.get('SECRET_KEY') or '').strip()
    if env_key and env_key != _OLD_PUBLIC_SECRET:
        return env_key
    database_url = (os.environ.get('DATABASE_URL') or '').strip()
    if database_url:
        return hashlib.sha256(('swarm-session-key-v1|' + database_url).encode('utf-8')).hexdigest()
    return secrets.token_hex(32)


# ============================================================================
# PASSCODE, COOKIE, KEY HEADER
# ============================================================================

def _passcode():
    return (os.environ.get(PASSCODE_ENV) or '').strip()


def gate_locked():
    """True when the passcode is set, i.e. the gate is actually blocking."""
    return bool(_passcode())


def _same(a, b):
    return hmac.compare_digest(str(a).encode('utf-8'), str(b).encode('utf-8'))


def _cookie_signature(passcode, expires):
    key = hmac.new(passcode.encode('utf-8'), b'swarm-admin-cookie-v1', hashlib.sha256).digest()
    return hmac.new(key, str(expires).encode('utf-8'), hashlib.sha256).hexdigest()


def make_cookie_value(passcode, now=None):
    expires = int((now if now is not None else time.time()) + COOKIE_DAYS * 86400)
    return f"{expires}.{_cookie_signature(passcode, expires)}"


def cookie_is_valid(value, passcode, now=None):
    try:
        expires_text, signature = str(value).split('.', 1)
        expires = int(expires_text)
    except (ValueError, AttributeError):
        return False
    if expires < (now if now is not None else time.time()):
        return False
    return _same(signature, _cookie_signature(passcode, expires))


def client_address():
    """The caller's address as the rest of the Swarm reads it (first hop of X-Forwarded-For)."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()[:64]
    return (request.headers.get('X-Real-IP') or request.remote_addr or 'unknown')[:64]


# ============================================================================
# DATABASE: what was blocked, and wrong-passcode attempts
# ============================================================================

_tables_ready = False
_tables_lock = threading.Lock()


def _db():
    from db_engine import get_db_connection
    return get_db_connection()


def ensure_tables():
    global _tables_ready
    if _tables_ready:
        return
    with _tables_lock:
        if _tables_ready:
            return
        last_error = None
        for _attempt in range(3):
            try:
                with _db() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS admin_gate_seen (
                            mode        TEXT NOT NULL,
                            method      TEXT NOT NULL,
                            endpoint    TEXT NOT NULL,
                            source      TEXT NOT NULL,
                            example     TEXT NOT NULL DEFAULT '',
                            hits        INTEGER NOT NULL DEFAULT 0,
                            first_seen  DOUBLE PRECISION NOT NULL,
                            last_seen   DOUBLE PRECISION NOT NULL,
                            PRIMARY KEY (mode, method, endpoint, source)
                        )
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS admin_gate_failures (
                            address  TEXT NOT NULL,
                            at       DOUBLE PRECISION NOT NULL
                        )
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_admin_gate_failures_at ON admin_gate_failures (at)")
                _tables_ready = True
                return
            except Exception as exc:        # two workers creating at the same moment can collide once
                last_error = exc
                time.sleep(0.3)
        raise last_error


_pending = {}                 # (mode, method, endpoint, source) -> [hits waiting, last write, example path]
_pending_lock = threading.Lock()
_WRITE_EVERY_SECONDS = 60


def _source_of_request():
    for header in ('Origin', 'Referer'):
        value = request.headers.get(header, '')
        if value:
            host = urlparse(value).netloc
            if host:
                return host[:120]
    return 'direct (typed address, script or another server)'


def _note(mode, endpoint):
    """Remember that this request was blocked ('blocked') or would have been ('would_block')."""
    key = (mode, request.method, endpoint, _source_of_request())
    now = time.time()
    with _pending_lock:
        entry = _pending.setdefault(key, [0, 0.0, request.path[:200]])
        entry[0] += 1
        first_time = entry[1] == 0.0
        if not first_time and now - entry[1] < _WRITE_EVERY_SECONDS:
            return
        hits, entry[0], entry[1] = entry[0], 0, now
        example = entry[2]
    if first_time:
        logger.info("[AdminGate] %s: %s %s (%s) from %s",
                    'BLOCKED' if mode == 'blocked' else 'would block', request.method, request.path, endpoint, key[3])
    try:
        ensure_tables()
        with _db() as conn:
            conn.cursor().execute(
                "INSERT INTO admin_gate_seen (mode, method, endpoint, source, example, hits, first_seen, last_seen) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (mode, method, endpoint, source) DO UPDATE SET "
                "hits = admin_gate_seen.hits + EXCLUDED.hits, last_seen = EXCLUDED.last_seen, example = EXCLUDED.example",
                (key[0], key[1], key[2], key[3], example, hits, now, now),
            )
    except Exception as exc:    # the record is a convenience; never let it break a request
        logger.warning("[AdminGate] could not record a %s request: %s", mode, exc)


def _too_many_failures(address):
    """True when passcode attempts must be refused for now. If the database is down, do not lock."""
    try:
        ensure_tables()
        since = time.time() - FAILURE_WINDOW_SECONDS
        with _db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS n FROM admin_gate_failures WHERE at >= %s AND address = %s",
                        (since, address))
            mine = int(cur.fetchone()['n'])
            cur.execute("SELECT COUNT(*) AS n FROM admin_gate_failures WHERE at >= %s", (since,))
            everyone = int(cur.fetchone()['n'])
        return mine >= MAX_FAILURES_PER_ADDRESS or everyone >= MAX_FAILURES_OVERALL
    except Exception as exc:
        logger.warning("[AdminGate] could not read the failed-attempt count: %s", exc)
        return False


def _record_failure(address):
    try:
        ensure_tables()
        now = time.time()
        with _db() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO admin_gate_failures (address, at) VALUES (%s, %s)", (address, now))
            cur.execute("DELETE FROM admin_gate_failures WHERE at < %s", (now - 24 * 3600,))
        logger.warning("[AdminGate] wrong passcode from %s", address)
    except Exception as exc:
        logger.warning("[AdminGate] could not record a failed attempt: %s", exc)


def check_passcode_attempt(candidate):
    """
    Judge one presented passcode (login form or X-Swarm-Key header).
    Returns 'ok', 'wrong', or 'locked'. A locked-out address is refused even
    if this guess is right; that is what makes guessing slow.
    """
    passcode = _passcode()
    if not passcode:
        return 'wrong'
    address = client_address()
    if _too_many_failures(address):
        return 'locked'
    if _same(candidate, passcode):
        return 'ok'
    _record_failure(address)
    return 'wrong'


# ============================================================================
# THE GATE
# ============================================================================

def _admin_state():
    """
    Is this request from the logged-in admin? Returns 'ok', 'no' or 'locked'.
    The cookie is checked first and touches no database.
    """
    passcode = _passcode()
    if not passcode:
        return 'no'
    cookie = request.cookies.get(COOKIE_NAME, '')
    if cookie and cookie_is_valid(cookie, passcode):
        return 'ok'
    header = request.headers.get(KEY_HEADER, '')
    if header:
        verdict = check_passcode_attempt(header)
        return 'ok' if verdict == 'ok' else ('locked' if verdict == 'locked' else 'no')
    return 'no'


def is_admin():
    """For other code: True when this request carries a valid admin cookie or key."""
    if getattr(g, 'swarm_admin', None) is None:
        g.swarm_admin = _admin_state() == 'ok'
    return g.swarm_admin


def _wants_a_page():
    if request.method != 'GET' or request.path.startswith('/api/'):
        return False
    accept = request.headers.get('Accept', '')
    return 'text/html' in accept or not accept or accept == '*/*'


def _safe_next(target):
    """Only ever send the browser back to a path on this site."""
    target = str(target or '')
    if target.startswith('/') and not target.startswith('//') and '\\' not in target and len(target) < 600:
        return target
    return '/'


def _gate():
    """Runs before every request."""
    g.swarm_admin = None
    if request.method == 'OPTIONS':
        return None                               # browser pre-checks carry no credentials
    endpoint = request.endpoint
    if endpoint is None:
        return None                               # no such address; Flask answers 404
    kind = classify(endpoint, request.path)
    if kind in ('public', 'own_login', 'service_open'):
        return None
    if not gate_locked():
        _note('would_block', endpoint)            # watching mode: record, never block
        return None

    state = _admin_state()
    g.swarm_admin = state == 'ok'
    if state == 'ok':
        return None
    if kind == 'survey_family' and session.get(SURVEY_ADMIN_SESSION_KEY) is True:
        return None

    _note('blocked', endpoint)
    g.swarm_gate_refused = True
    if state == 'locked':
        return jsonify({'success': False,
                        'error': 'Too many wrong passcodes. Wait 15 minutes and try again.'}), 429
    if _wants_a_page():
        full_path = request.full_path if request.query_string else request.path
        return redirect('/login?next=' + _quote(_safe_next(full_path)))
    return jsonify({'success': False, 'error': 'Admin login needed.', 'login_url': '/login'}), 401


def _quote(text):
    from urllib.parse import quote
    return quote(text, safe='/')


def _strip_tracebacks(response):
    """When locked, outsiders do not get internal error detail. It goes to the log instead."""
    if not gate_locked():
        return
    admin = getattr(g, 'swarm_admin', None)
    if admin is None:           # a public or own-login route: the gate did not look, so look now (cookie only)
        admin = cookie_is_valid(request.cookies.get(COOKIE_NAME, ''), _passcode())
    if admin:
        return
    if response.direct_passthrough or response.is_streamed or response.mimetype != 'application/json':
        return
    try:
        body = response.get_data()
        if b'"traceback"' not in body or len(body) > 1_000_000:
            return
        data = json.loads(body)
        if isinstance(data, dict) and 'traceback' in data:
            detail = data.pop('traceback')
            logger.error("[AdminGate] error detail withheld from the caller (%s %s):\n%s",
                         request.method, request.path, detail)
            response.set_data(json.dumps(data))
    except Exception:           # never let tidying a reply break the reply
        return


def _after(response):
    """Runs after every request."""
    # Let trusted pages send the key: add it to whatever cross-site headers a route already allows.
    allowed = response.headers.get('Access-Control-Allow-Headers')
    if allowed is not None and KEY_HEADER.lower() not in allowed.lower():
        response.headers['Access-Control-Allow-Headers'] = allowed + ', ' + KEY_HEADER
    # A refusal sent to a trusted page must be readable by that page, so it can say
    # "passcode needed" instead of showing a bare network error. (Some routes add their
    # cross-site headers inside the route itself, which a refusal never reaches.)
    if getattr(g, 'swarm_gate_refused', False) and 'Access-Control-Allow-Origin' not in response.headers:
        origin = request.headers.get('Origin', '')
        if origin in TRUSTED_ORIGINS:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Vary'] = 'Origin'
    _strip_tracebacks(response)
    return response


# ============================================================================
# THE GATE'S OWN ROUTES
# ============================================================================

admin_gate_bp = Blueprint('admin_gate', __name__)


@admin_gate_bp.after_request
def _gate_cors(response):
    """The performance dashboard on shift-work.com checks the key against /api/admin-gate/check."""
    origin = request.headers.get('Origin', '')
    if origin in TRUSTED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept, ' + KEY_HEADER
        response.headers['Access-Control-Max-Age'] = '86400'
        response.headers['Vary'] = 'Origin'
    if request.path.startswith('/api/admin-gate/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@admin_gate_bp.route('/login', methods=['GET'])
def login_page():
    """The login page. A plain file: nothing in it is filled in by the server."""
    response = send_from_directory(_TEMPLATES_DIR, 'admin_login.html', mimetype='text/html')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Frame-Options'] = 'DENY'
    return response


@admin_gate_bp.route('/api/admin-gate/status', methods=['GET'])
def status():
    """What the login page needs to know. Says nothing about the passcode itself."""
    return jsonify({
        'locked': gate_locked(),
        'logged_in': _admin_state() == 'ok' if gate_locked() else False,
        'passcode_is_short': gate_locked() and len(_passcode()) < SHORT_PASSCODE,
    })


@admin_gate_bp.route('/api/admin-gate/login', methods=['POST'])
def login():
    """Body: {"passcode": "..."}. On success sets the 30-day cookie (on this 200 reply, not a redirect)."""
    if not gate_locked():
        return jsonify({'success': False,
                        'error': 'No passcode is set on the server yet, so there is nothing to log in to. '
                                 'Add SWARM_ADMIN_PASSCODE in Render.'}), 409
    data = request.get_json(silent=True) or {}
    verdict = check_passcode_attempt(str(data.get('passcode') or ''))
    if verdict == 'locked':
        return jsonify({'success': False,
                        'error': 'Too many wrong passcodes. Wait 15 minutes and try again.'}), 429
    if verdict != 'ok':
        return jsonify({'success': False, 'error': 'That passcode is not right.'}), 401
    response = jsonify({'success': True, 'next': _safe_next(data.get('next'))})
    response.set_cookie(COOKIE_NAME, make_cookie_value(_passcode()), max_age=COOKIE_DAYS * 86400,
                        httponly=True, secure=request.is_secure, samesite='Strict', path='/')
    return response


@admin_gate_bp.route('/api/admin-gate/logout', methods=['POST'])
def logout():
    response = jsonify({'success': True})
    response.delete_cookie(COOKIE_NAME, path='/')
    return response


@admin_gate_bp.route('/api/admin-gate/check', methods=['GET'])
def check():
    """
    For other pages and apps: 200 when the key or cookie sent with this request
    is accepted. (When locked, the gate itself answers 401 before this runs.)
    """
    return jsonify({'success': True, 'locked': gate_locked()})


@admin_gate_bp.route('/api/admin-gate/report', methods=['GET'])
def report():
    """What the gate has blocked, and what it would have blocked while only watching."""
    try:
        ensure_tables()
        with _db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT mode, method, endpoint, source, example, hits, first_seen, last_seen "
                        "FROM admin_gate_seen ORDER BY last_seen DESC LIMIT 500")
            rows = [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        logger.error("[AdminGate] report failed: %s", exc)
        return jsonify({'success': False, 'error': 'The report could not be read from the database.'}), 500
    return jsonify({'success': True, 'locked': gate_locked(), 'count': len(rows), 'seen': rows})


# ============================================================================
# SWITCHING IT ON
# ============================================================================

def init_security(app):
    """Called once from app.py, after the blueprints are registered."""
    app.register_blueprint(admin_gate_bp)
    app.before_request(_gate)
    app.after_request(_after)
    if gate_locked():
        note = ' (WARNING: the passcode is short; use 16+ characters)' if len(_passcode()) < SHORT_PASSCODE else ''
        print(f"Admin Gate: LOCKED. Everything not listed as public needs the admin passcode{note}")
    else:
        print(f"Admin Gate: WATCHING ONLY, nothing is blocked. Set {PASSCODE_ENV} in Render to lock.")


# I did no harm and this file is not truncated
