"""
routes/ptt_auth.py
AI Swarm Orchestrator — Part Time Tracker: Auth Utilities
Shiftwork Solutions LLC

Created:      2026-05-01
Last Updated: 2026-05-04

CHANGELOG:
  2026-05-04 — Phase 2 update.
    Removed DEFAULT_SKILLS list. Skill seeding now lives entirely in
    ptt_hr.py inside the signup transaction where it belongs. Auth
    module should not contain business content. No other changes.

  2026-05-01 — INITIAL BUILD (Phase 1).
    Magic link token generation and redemption.
    Server-side session cookie management.
    Email send wrapper for all 6 PTT email templates.
    Shared auth decorators (require_ptt_admin, require_ptt_worker).

PURPOSE:
    Centralizes all authentication logic for Part Time Tracker Lite so
    that ptt_hr.py and future ptt_worker.py can import clean decorators
    and helper functions without duplicating code.

DESIGN DECISIONS:
    - Tokens are stored as SHA-256 hash, never plaintext
    - Session stored server-side in ptt_session table; cookie holds UUID only
    - Cookie: HttpOnly, Secure, SameSite=Lax, 30-day rolling expiry
    - Token expiry: 30 minutes
    - Email sent via Resend using existing RESEND_API_KEY
    - Email failures never block user flow — logged and silently skipped
    - Free-mail domain blocklist enforced server-side (15 domains)

DEPENDENCIES:
    - db_engine.py (existing, not modified)
    - RESEND_API_KEY environment variable (already set in Render)

I did no harm and this file is not truncated.
"""

import os
import hashlib
import secrets
import json
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import request, jsonify, redirect, make_response

from db_engine import get_db_connection, get_db_type


# =============================================================================
# CONSTANTS
# =============================================================================

PTT_SESSION_COOKIE   = "ptt_session"
SESSION_DAYS         = 30
TOKEN_MINUTES        = 30
EMAIL_FROM           = "Part Time Tracker <contact@shift-work.com>"
NOTIFICATION_EMAIL   = "jim@shift-work.com"

# Free-mail domain blocklist — enforced server-side on HR signup
FREE_MAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com",
    "icloud.com", "proton.me", "protonmail.com", "mail.com", "msn.com",
    "live.com", "ymail.com", "gmx.com", "zoho.com", "yandex.com",
}


# =============================================================================
# TOKEN HELPERS
# =============================================================================

def _hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of a raw token string."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_magic_token(user_type: str, user_id: int, company_id: int) -> str:
    """
    Generate a cryptographically random token, store its hash in
    ptt_magic_token, and return the raw token for inclusion in the
    email link.

    user_type: 'admin' or 'worker'
    Returns: raw token string (URL-safe, 48 bytes of entropy)
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ptt_magic_token
                (token_hash, user_type, user_id, company_id, expires_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (token_hash, user_type, user_id, company_id, expires_at))
        conn.commit()
    finally:
        conn.close()

    return raw_token


def redeem_magic_token(raw_token: str):
    """
    Look up the token by its hash. If valid (exists + not expired),
    delete it (single-use) and return a dict with
    {user_type, user_id, company_id}. Returns None if invalid.
    """
    token_hash = _hash_token(raw_token)
    now = datetime.now(timezone.utc)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_type, user_id, company_id, expires_at
            FROM ptt_magic_token
            WHERE token_hash = %s
        """, (token_hash,))
        row = cursor.fetchone()

        if not row:
            return None

        expires_at = row["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            cursor.execute("DELETE FROM ptt_magic_token WHERE id = %s", (row["id"],))
            conn.commit()
            return None

        # Valid — delete (single-use) and return payload
        cursor.execute("DELETE FROM ptt_magic_token WHERE id = %s", (row["id"],))
        conn.commit()

        return {
            "user_type":  row["user_type"],
            "user_id":    row["user_id"],
            "company_id": row["company_id"],
        }
    finally:
        conn.close()


# =============================================================================
# SESSION HELPERS
# =============================================================================

def create_session(user_type: str, user_id: int, company_id: int) -> str:
    """
    Create a server-side session row in ptt_session.
    Returns the raw session_id UUID to store in the cookie.
    """
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    payload = json.dumps({
        "user_type":  user_type,
        "user_id":    user_id,
        "company_id": company_id,
    })

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ptt_session
                (session_id, user_type, user_id, company_id, payload, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session_id, user_type, user_id, company_id, payload, expires_at))
        conn.commit()
    finally:
        conn.close()

    return session_id


def get_session(session_id: str):
    """
    Validate and return session data dict, or None if not found/expired.
    Rolls the expiry window on each successful read (30-day rolling).
    """
    if not session_id:
        return None

    now = datetime.now(timezone.utc)
    new_expires = now + timedelta(days=SESSION_DAYS)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_type, user_id, company_id, payload, expires_at
            FROM ptt_session
            WHERE session_id = %s
        """, (session_id,))
        row = cursor.fetchone()

        if not row:
            return None

        expires_at = row["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            cursor.execute("DELETE FROM ptt_session WHERE session_id = %s",
                           (session_id,))
            conn.commit()
            return None

        # Roll expiry
        cursor.execute("""
            UPDATE ptt_session
            SET expires_at = %s, last_seen_at = NOW()
            WHERE session_id = %s
        """, (new_expires, session_id))
        conn.commit()

        return {
            "user_type":  row["user_type"],
            "user_id":    row["user_id"],
            "company_id": row["company_id"],
        }
    finally:
        conn.close()


def delete_session(session_id: str):
    """Delete a session row (logout)."""
    if not session_id:
        return
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ptt_session WHERE session_id = %s",
                       (session_id,))
        conn.commit()
    finally:
        conn.close()


def set_session_cookie(response, session_id: str):
    """Attach the PTT session cookie to a Flask response object."""
    response.set_cookie(
        PTT_SESSION_COOKIE,
        session_id,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        secure=True,
        samesite="Lax",
        path="/ptt",
    )
    return response


def clear_session_cookie(response):
    """Expire the PTT session cookie."""
    response.delete_cookie(PTT_SESSION_COOKIE, path="/ptt")
    return response


def get_current_session():
    """Read and validate the session from the incoming request cookie."""
    session_id = request.cookies.get(PTT_SESSION_COOKIE)
    if not session_id:
        return None
    return get_session(session_id)


# =============================================================================
# AUTH DECORATORS
# =============================================================================

def require_ptt_admin(f):
    """
    Decorator: require a valid admin session.
    Injects session dict as keyword argument `ptt_session` into the view.
    Returns 401 JSON for API routes, redirects to /ptt/ for HTML routes.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        session = get_current_session()
        if not session or session.get("user_type") != "admin":
            if request.path.startswith("/api/ptt/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect("/ptt/")
        kwargs["ptt_session"] = session
        return f(*args, **kwargs)
    return decorated


def require_ptt_worker(f):
    """
    Decorator: require a valid worker session.
    Injects session dict as keyword argument `ptt_session` into the view.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        session = get_current_session()
        if not session or session.get("user_type") != "worker":
            if request.path.startswith("/api/ptt/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect("/ptt/")
        kwargs["ptt_session"] = session
        return f(*args, **kwargs)
    return decorated


# =============================================================================
# DOMAIN VALIDATION
# =============================================================================

def is_free_mail(email: str) -> bool:
    """Return True if the email's domain is in the free-mail blocklist."""
    try:
        domain = email.strip().lower().split("@")[1]
        return domain in FREE_MAIL_DOMAINS
    except (IndexError, AttributeError):
        return False


def extract_domain(email: str) -> str:
    """Return the lowercased domain portion of an email address."""
    try:
        return email.strip().lower().split("@")[1]
    except (IndexError, AttributeError):
        return ""


# =============================================================================
# SLUG GENERATOR
# =============================================================================

def generate_slug(company_name: str) -> str:
    """
    Convert a company name into a URL-safe slug.
    E.g. 'Acme Corp.' -> 'acme-corp-a1b2c3'
    Appends a random suffix to guarantee uniqueness.
    """
    import re
    base = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
    base = base[:40]
    suffix = secrets.token_hex(3)
    return f"{base}-{suffix}"


# =============================================================================
# EMAIL SEND WRAPPER
# =============================================================================

def _send_email(to_address: str, subject: str, html_body: str,
                text_body: str) -> tuple:
    """
    Send an email via Resend.
    Returns (success: bool, info: str).
    Never raises — failures are logged and returned as (False, reason).
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return (False, "RESEND_API_KEY not configured")

    try:
        import resend
    except ImportError:
        return (False, "resend library not installed")

    try:
        resend.api_key = api_key
        params = {
            "from":    EMAIL_FROM,
            "to":      [to_address],
            "subject": subject,
            "text":    text_body,
            "html":    html_body,
        }
        result = resend.Emails.send(params)
        msg_id = (result or {}).get("id", "")
        return (True, f"sent id={msg_id}")
    except Exception as e:
        return (False, f"resend error: {str(e)}")


def _email_header(title_line: str) -> str:
    """Reusable HTML email header block."""
    return f"""
    <div style="background:#1F3D5C; padding:18px 24px; border-left:4px solid #E8610A;">
      <div style="color:#EEAE26; font-size:16px; font-weight:700; letter-spacing:.02em;">
        SHIFTWORK SOLUTIONS
      </div>
      <div style="color:#85B7EB; font-size:11px; font-weight:700;
                  text-transform:uppercase; letter-spacing:.12em; margin-top:4px;">
        Part Time Tracker &mdash; {title_line}
      </div>
    </div>
    """


def _email_footer() -> str:
    """Reusable HTML email footer block."""
    return """
    <div style="background:#1F3D5C; padding:12px 24px;
                font-size:11px; color:rgba(255,255,255,.55);">
      Shiftwork Solutions LLC &nbsp;&middot;&nbsp; (415) 265-1621
      &nbsp;&middot;&nbsp; shift-work.com
    </div>
    """


def _email_wrap(header: str, body_html: str) -> str:
    """Wrap header + body + footer in a consistent container."""
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif; color:#1A1A1A;
                max-width:600px; border:1px solid #E0E0E0; border-radius:4px;
                overflow:hidden;">
      {header}
      <div style="padding:24px;">
        {body_html}
      </div>
      {_email_footer()}
    </div>
    """


# ---------------------------------------------------------------------------
# Template 1: HR signup confirmation (to admin, with magic link)
# ---------------------------------------------------------------------------
def send_hr_signup_confirmation(admin_email: str, admin_name: str,
                                company_name: str, magic_link: str) -> tuple:
    subject = "Part Time Tracker: Your login link"
    header  = _email_header("Welcome")
    body    = f"""
      <p style="font-size:15px; line-height:1.6;">Hi {admin_name},</p>
      <p style="font-size:14px; line-height:1.6;">
        Your Part Time Tracker account for <strong>{company_name}</strong>
        has been created. Click the button below to log in and get started.
        This link expires in 30 minutes.
      </p>
      <p style="text-align:center; margin:28px 0;">
        <a href="{magic_link}"
           style="background:#E8610A; color:#FFFFFF; font-size:15px;
                  font-weight:700; padding:14px 32px; border-radius:4px;
                  text-decoration:none; display:inline-block;">
          Log In to Part Time Tracker
        </a>
      </p>
      <p style="font-size:12px; color:#666; line-height:1.5;">
        If the button doesn't work, copy and paste this link into your browser:<br>
        <a href="{magic_link}" style="color:#1F3D5C;">{magic_link}</a>
      </p>
    """
    html = _email_wrap(header, body)
    text = (
        f"Hi {admin_name},\n\n"
        f"Your Part Time Tracker account for {company_name} has been created.\n\n"
        f"Log in here (link expires in 30 minutes):\n{magic_link}\n\n"
        "Shiftwork Solutions LLC | (415) 265-1621 | shift-work.com"
    )
    return _send_email(admin_email, subject, html, text)


# ---------------------------------------------------------------------------
# Template 2: HR signup notification (to Jim)
# ---------------------------------------------------------------------------
def send_hr_signup_notification(admin_name: str, admin_email: str,
                                company_name: str, industry: str,
                                facility_size: str) -> tuple:
    subject = f"Part Time Tracker signup — {company_name}"
    header  = _email_header("New Signup")
    body    = f"""
      <p style="font-size:14px; line-height:1.6;">
        A new company has signed up for Part Time Tracker Lite.
      </p>
      <div style="background:#F4F6F8; border-left:3px solid #1F3D5C;
                  padding:14px 18px; border-radius:0 6px 6px 0; margin:16px 0;">
        <table style="font-size:13px; line-height:1.7; border-collapse:collapse;">
          <tr><td style="color:#666; padding-right:14px;">Name:</td>
              <td><strong>{admin_name}</strong></td></tr>
          <tr><td style="color:#666; padding-right:14px;">Email:</td>
              <td>{admin_email}</td></tr>
          <tr><td style="color:#666; padding-right:14px;">Company:</td>
              <td>{company_name}</td></tr>
          <tr><td style="color:#666; padding-right:14px;">Industry:</td>
              <td>{industry or '(not provided)'}</td></tr>
          <tr><td style="color:#666; padding-right:14px;">Facility size:</td>
              <td>{facility_size or '(not provided)'}</td></tr>
        </table>
      </div>
    """
    html = _email_wrap(header, body)
    text = (
        f"New Part Time Tracker Lite signup.\n\n"
        f"Name:          {admin_name}\n"
        f"Email:         {admin_email}\n"
        f"Company:       {company_name}\n"
        f"Industry:      {industry or '(not provided)'}\n"
        f"Facility size: {facility_size or '(not provided)'}\n\n"
        "Shiftwork Solutions LLC | (415) 265-1621 | shift-work.com"
    )
    return _send_email(NOTIFICATION_EMAIL, subject, html, text)


# ---------------------------------------------------------------------------
# Template 3: Worker application received (to admin)
# ---------------------------------------------------------------------------
def send_worker_application_received(admin_email: str, worker_name: str,
                                     worker_email: str, company_name: str,
                                     review_url: str) -> tuple:
    subject = f"Part Time Tracker: {worker_name} applied to your pool"
    header  = _email_header("New Worker Application")
    body    = f"""
      <p style="font-size:14px; line-height:1.6;">
        <strong>{worker_name}</strong> ({worker_email}) just applied to join
        the part-time pool for <strong>{company_name}</strong>.
      </p>
      <p style="text-align:center; margin:24px 0;">
        <a href="{review_url}"
           style="background:#E8610A; color:#FFFFFF; font-size:14px;
                  font-weight:700; padding:12px 28px; border-radius:4px;
                  text-decoration:none; display:inline-block;">
          Review Application
        </a>
      </p>
    """
    html = _email_wrap(header, body)
    text = (
        f"{worker_name} ({worker_email}) applied to your part-time pool "
        f"at {company_name}.\n\n"
        f"Review: {review_url}\n\n"
        "Shiftwork Solutions LLC | (415) 265-1621 | shift-work.com"
    )
    return _send_email(admin_email, subject, html, text)


# ---------------------------------------------------------------------------
# Template 4: Worker approved (to worker, with magic link)
# ---------------------------------------------------------------------------
def send_worker_approved(worker_email: str, worker_name: str,
                         company_name: str, magic_link: str) -> tuple:
    subject = f"Part Time Tracker: You have been approved by {company_name}"
    header  = _email_header("Application Approved")
    body    = f"""
      <p style="font-size:15px; line-height:1.6;">Hi {worker_name},</p>
      <p style="font-size:14px; line-height:1.6;">
        Your application to join the part-time pool at
        <strong>{company_name}</strong> has been approved.
        Click the button below to log in and complete your profile.
        This link expires in 30 minutes.
      </p>
      <p style="text-align:center; margin:28px 0;">
        <a href="{magic_link}"
           style="background:#E8610A; color:#FFFFFF; font-size:15px;
                  font-weight:700; padding:14px 32px; border-radius:4px;
                  text-decoration:none; display:inline-block;">
          Log In to Part Time Tracker
        </a>
      </p>
      <p style="font-size:12px; color:#666; line-height:1.5;">
        If the button doesn't work, copy and paste this link:<br>
        <a href="{magic_link}" style="color:#1F3D5C;">{magic_link}</a>
      </p>
    """
    html = _email_wrap(header, body)
    text = (
        f"Hi {worker_name},\n\n"
        f"Your application at {company_name} has been approved.\n\n"
        f"Log in here (expires in 30 minutes):\n{magic_link}\n\n"
        "Shiftwork Solutions LLC | (415) 265-1621 | shift-work.com"
    )
    return _send_email(worker_email, subject, html, text)


# ---------------------------------------------------------------------------
# Template 5: Worker claimed a shift (to admin)
# ---------------------------------------------------------------------------
def send_worker_claimed_shift(admin_email: str, worker_name: str,
                              shift_title: str, shift_date: str,
                              review_url: str) -> tuple:
    subject = f"Part Time Tracker: {worker_name} claimed {shift_title}"
    header  = _email_header("Shift Claim")
    body    = f"""
      <p style="font-size:14px; line-height:1.6;">
        <strong>{worker_name}</strong> has claimed the shift
        <strong>{shift_title}</strong> on <strong>{shift_date}</strong>.
      </p>
      <p style="text-align:center; margin:24px 0;">
        <a href="{review_url}"
           style="background:#E8610A; color:#FFFFFF; font-size:14px;
                  font-weight:700; padding:12px 28px; border-radius:4px;
                  text-decoration:none; display:inline-block;">
          Review &amp; Confirm
        </a>
      </p>
    """
    html = _email_wrap(header, body)
    text = (
        f"{worker_name} claimed {shift_title} on {shift_date}.\n\n"
        f"Review: {review_url}\n\n"
        "Shiftwork Solutions LLC | (415) 265-1621 | shift-work.com"
    )
    return _send_email(admin_email, subject, html, text)


# ---------------------------------------------------------------------------
# Template 6: Generic magic link (repeat logins for either side)
# ---------------------------------------------------------------------------
def send_magic_link(to_email: str, magic_link: str,
                    user_type: str = "admin") -> tuple:
    label   = "HR Admin" if user_type == "admin" else "Worker"
    subject = "Part Time Tracker: Your login link"
    header  = _email_header("Login Link")
    body    = f"""
      <p style="font-size:14px; line-height:1.6;">
        You requested a login link for Part Time Tracker ({label}).
        Click the button below to log in. This link expires in 30 minutes.
      </p>
      <p style="text-align:center; margin:28px 0;">
        <a href="{magic_link}"
           style="background:#E8610A; color:#FFFFFF; font-size:15px;
                  font-weight:700; padding:14px 32px; border-radius:4px;
                  text-decoration:none; display:inline-block;">
          Log In
        </a>
      </p>
      <p style="font-size:12px; color:#666; line-height:1.5;">
        If you did not request this link, you can ignore this email.<br>
        If the button doesn't work:<br>
        <a href="{magic_link}" style="color:#1F3D5C;">{magic_link}</a>
      </p>
    """
    html = _email_wrap(header, body)
    text = (
        f"Your Part Time Tracker login link ({label}).\n\n"
        f"Expires in 30 minutes:\n{magic_link}\n\n"
        "If you did not request this, ignore this email.\n\n"
        "Shiftwork Solutions LLC | (415) 265-1621 | shift-work.com"
    )
    return _send_email(to_email, subject, html, text)


# =============================================================================
# LEADS TABLE HELPER
# =============================================================================

def insert_ptt_lead(company_name: str, admin_name: str, admin_email: str,
                    industry: str, facility_size: str) -> int:
    """
    Insert a row into the existing Swarm leads table with
    source = 'ptt-lite-signup'. Returns the new lead id.
    Does not modify the leads table schema.
    """
    import json as _json
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO leads
                (company_name, industry, facility_size,
                 contact_name, contact_email,
                 source, pipeline_stage, score, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            company_name,
            industry or "",
            facility_size or "",
            admin_name,
            admin_email,
            "ptt-lite-signup",
            "detected",
            0,
            _json.dumps({"product": "ptt-lite"}),
        ))
        row = cursor.fetchone()
        conn.commit()
        return row["id"] if row else None
    except Exception as e:
        print(f"[ptt_auth] insert_ptt_lead error (non-fatal): {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

# I did no harm and this file is not truncated.
