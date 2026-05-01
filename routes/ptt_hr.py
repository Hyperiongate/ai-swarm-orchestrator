"""
routes/ptt_hr.py
AI Swarm Orchestrator — Part Time Tracker: HR Admin Routes
Shiftwork Solutions LLC

Created:      2026-05-01
Last Updated: 2026-05-01

CHANGELOG:
  2026-05-01 — INITIAL BUILD (Phase 1).
    HR signup flow end-to-end:
      GET  /ptt/                      — landing / signup page
      POST /api/ptt/lead              — HR signup form submit
      GET  /ptt/login                 — magic link request page
      POST /api/ptt/login-request     — send magic link to existing admin
      GET  /ptt/auth                  — token redemption (from email link)
      GET  /ptt/dashboard             — HR admin dashboard (requires session)
      GET  /ptt/logout                — clear session and redirect to /ptt/

PURPOSE:
    Handles the complete HR admin experience for Phase 1:
    signup, magic-link auth, and the dashboard shell that later
    phases will populate with workers and shifts.

ACCEPTANCE CRITERIA (Phase 1):
    Jim signs up with a test company email, receives the magic link,
    clicks it, lands on /ptt/dashboard. The signup appears in the
    Swarm leads table with source = 'ptt-lite-signup'.
    Jim receives the notification email at jim@shift-work.com.

MULTI-TENANCY:
    Every database read that returns company data is filtered by
    the company_id stored in the session. No cross-tenant leakage.

I did no harm and this file is not truncated.
"""

import json
from datetime import datetime, timezone

from flask import (Blueprint, request, jsonify, render_template,
                   redirect, make_response)

from db_engine import get_db_connection
from routes.ptt_auth import (
    is_free_mail, extract_domain, generate_slug,
    create_magic_token, redeem_magic_token,
    create_session, delete_session, get_current_session,
    set_session_cookie, clear_session_cookie,
    send_hr_signup_confirmation, send_hr_signup_notification,
    send_magic_link, insert_ptt_lead,
    require_ptt_admin,
)


# =============================================================================
# BLUEPRINT
# =============================================================================

ptt_hr_bp = Blueprint("ptt_hr", __name__)

# Default skill names seeded for every new company (user-editable)
DEFAULT_SKILLS = [
    "Skill 1",
    "Skill 2",
    "Skill 3",
    "Skill 4",
    "Skill 5",
]

# Industry options for signup form
INDUSTRY_OPTIONS = [
    "Manufacturing",
    "Pharmaceutical",
    "Food & Beverage",
    "Chemical",
    "Distribution / Warehouse",
    "Mining",
    "Utilities",
    "Oil & Gas",
    "Healthcare",
    "Other",
]

# Facility size options
FACILITY_SIZE_OPTIONS = [
    "Under 50 employees",
    "50 – 199 employees",
    "200 – 499 employees",
    "500 – 999 employees",
    "1,000+ employees",
]


# =============================================================================
# HELPER — build the magic link URL
# =============================================================================

def _build_magic_link(raw_token: str) -> str:
    """Construct the absolute magic link URL from a raw token."""
    base = request.host_url.rstrip("/")
    return f"{base}/ptt/auth?token={raw_token}"


# =============================================================================
# ROUTES — HTML pages
# =============================================================================

@ptt_hr_bp.route("/ptt/")
@ptt_hr_bp.route("/ptt")
def ptt_landing():
    """
    Landing page. If the visitor already has a valid admin session,
    redirect to the dashboard. Otherwise show the signup form.
    """
    session = get_current_session()
    if session and session.get("user_type") == "admin":
        return redirect("/ptt/dashboard")
    if session and session.get("user_type") == "worker":
        return redirect("/ptt/w/dashboard")
    return render_template(
        "ptt/signup.html",
        industry_options=INDUSTRY_OPTIONS,
        facility_size_options=FACILITY_SIZE_OPTIONS,
    )


@ptt_hr_bp.route("/ptt/login")
def ptt_login_page():
    """Magic link request page for returning admins."""
    session = get_current_session()
    if session and session.get("user_type") == "admin":
        return redirect("/ptt/dashboard")
    return render_template("ptt/login.html")


@ptt_hr_bp.route("/ptt/auth")
def ptt_auth_redeem():
    """
    Token redemption endpoint. Called when the user clicks the
    magic link in their email.
    On success: creates a server-side session, sets the cookie,
    and redirects to the appropriate dashboard.
    On failure: redirects to /ptt/ with an error query param.
    """
    raw_token = request.args.get("token", "").strip()
    if not raw_token:
        return redirect("/ptt/?error=missing_token")

    payload = redeem_magic_token(raw_token)
    if not payload:
        return redirect("/ptt/?error=invalid_or_expired_token")

    user_type  = payload["user_type"]
    user_id    = payload["user_id"]
    company_id = payload["company_id"]

    # Update last_login_at for admin users
    if user_type == "admin":
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ptt_admin_user
                SET last_login_at = NOW()
                WHERE id = %s AND company_id = %s
            """, (user_id, company_id))
            conn.commit()
        finally:
            conn.close()

    session_id = create_session(user_type, user_id, company_id)

    if user_type == "admin":
        dest = "/ptt/dashboard"
    else:
        dest = "/ptt/w/dashboard"

    resp = make_response(redirect(dest))
    set_session_cookie(resp, session_id)
    return resp


@ptt_hr_bp.route("/ptt/dashboard")
@require_ptt_admin
def ptt_dashboard(ptt_session):
    """
    HR Admin dashboard. Requires a valid admin session.
    Phase 1: renders the shell with company info and empty state cards.
    Later phases populate workers, shifts, and activity.
    """
    company_id = ptt_session["company_id"]
    admin_id   = ptt_session["user_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Company info
        cursor.execute("""
            SELECT name, slug, industry, facility_size, created_at
            FROM ptt_company
            WHERE id = %s
        """, (company_id,))
        company = cursor.fetchone()

        # Admin info
        cursor.execute("""
            SELECT name, email FROM ptt_admin_user
            WHERE id = %s AND company_id = %s
        """, (admin_id, company_id))
        admin = cursor.fetchone()

        # Dashboard summary counts
        cursor.execute("""
            SELECT COUNT(*) AS total FROM ptt_worker
            WHERE company_id = %s AND status = 'active'
        """, (company_id,))
        active_workers = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total FROM ptt_worker
            WHERE company_id = %s AND status = 'pending'
        """, (company_id,))
        pending_workers = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total FROM ptt_shift
            WHERE company_id = %s AND status = 'open'
        """, (company_id,))
        open_shifts = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total FROM ptt_skill
            WHERE company_id = %s
        """, (company_id,))
        skill_count = cursor.fetchone()["total"]

    finally:
        conn.close()

    apply_url = f"{request.host_url.rstrip('/')}/ptt/apply/{company['slug']}"

    return render_template(
        "ptt/dashboard.html",
        company=company,
        admin=admin,
        active_workers=active_workers,
        pending_workers=pending_workers,
        open_shifts=open_shifts,
        skill_count=skill_count,
        apply_url=apply_url,
    )


@ptt_hr_bp.route("/ptt/logout")
def ptt_logout():
    """Clear the session cookie and server-side session row."""
    session_id = request.cookies.get("ptt_session")
    if session_id:
        delete_session(session_id)
    resp = make_response(redirect("/ptt/"))
    clear_session_cookie(resp)
    return resp


# =============================================================================
# ROUTES — API endpoints
# =============================================================================

@ptt_hr_bp.route("/api/ptt/lead", methods=["POST"])
def ptt_lead_signup():
    """
    HR signup intake.
    Body: { name, email, company_name, industry, facility_size }
    Flow:
      1. Validate email (not blank, not free-mail domain)
      2. Check company slug uniqueness (retry with new suffix if clash)
      3. INSERT ptt_company
      4. INSERT ptt_admin_user
      5. Seed 5 default skills
      6. INSERT into Swarm leads table (source = ptt-lite-signup)
      7. Send HR signup confirmation email with magic link
      8. Send Jim notification email
    Returns: { id, status: "ok" } or { error: "..." }
    """
    data = request.get_json(silent=True) or {}

    name          = (data.get("name")         or "").strip()
    email         = (data.get("email")        or "").strip().lower()
    company_name  = (data.get("company_name") or "").strip()
    industry      = (data.get("industry")     or "").strip()
    facility_size = (data.get("facility_size") or "").strip()

    # ── Validation ───────────────────────────────────────────────────────────
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400
    if is_free_mail(email):
        return jsonify({
            "error": "Please use your work email address. "
                     "Free email services (Gmail, Yahoo, etc.) are not accepted."
        }), 400
    if not company_name:
        return jsonify({"error": "Company name is required"}), 400

    email_domain = extract_domain(email)

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Check if this email already has an account
        cursor.execute("""
            SELECT id FROM ptt_admin_user WHERE email = %s
        """, (email,))
        if cursor.fetchone():
            return jsonify({
                "error": "An account with this email already exists. "
                         "Use the login page to request a new link."
            }), 409

        # Generate a unique slug
        slug = generate_slug(company_name)
        for _ in range(5):  # retry up to 5 times on collision
            cursor.execute("""
                SELECT id FROM ptt_company WHERE slug = %s
            """, (slug,))
            if not cursor.fetchone():
                break
            slug = generate_slug(company_name)

        # ── INSERT ptt_company ───────────────────────────────────────────────
        cursor.execute("""
            INSERT INTO ptt_company
                (name, slug, email_domain, signup_email, industry, facility_size)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (company_name, slug, email_domain, email, industry, facility_size))
        company_row = cursor.fetchone()
        company_id  = company_row["id"]

        # ── INSERT ptt_admin_user ────────────────────────────────────────────
        cursor.execute("""
            INSERT INTO ptt_admin_user (company_id, email, name)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (company_id, email, name))
        admin_row = cursor.fetchone()
        admin_id  = admin_row["id"]

        # ── Seed default skills ──────────────────────────────────────────────
        for i, skill_name in enumerate(DEFAULT_SKILLS):
            cursor.execute("""
                INSERT INTO ptt_skill (company_id, name, sort_order)
                VALUES (%s, %s, %s)
                ON CONFLICT (company_id, name) DO NOTHING
            """, (company_id, skill_name, i))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"[ptt_hr] signup DB error: {e}")
        return jsonify({"error": "An error occurred. Please try again."}), 500
    finally:
        conn.close()

    # ── Lead pipeline insert (non-fatal) ─────────────────────────────────────
    try:
        insert_ptt_lead(company_name, name, email, industry, facility_size)
    except Exception as e:
        print(f"[ptt_hr] lead insert error (non-fatal): {e}")

    # ── Create magic link ─────────────────────────────────────────────────────
    try:
        raw_token  = create_magic_token("admin", admin_id, company_id)
        magic_link = _build_magic_link(raw_token)
    except Exception as e:
        print(f"[ptt_hr] token creation error: {e}")
        return jsonify({"error": "Account created but login link failed. "
                                  "Please use the login page."}), 500

    # ── Send emails (non-fatal) ───────────────────────────────────────────────
    try:
        ok, info = send_hr_signup_confirmation(email, name, company_name,
                                               magic_link)
        print(f"[ptt_hr] signup confirmation email: ok={ok}, {info}")
    except Exception as e:
        print(f"[ptt_hr] signup confirmation email exception (non-fatal): {e}")

    try:
        ok, info = send_hr_signup_notification(name, email, company_name,
                                               industry, facility_size)
        print(f"[ptt_hr] Jim notification email: ok={ok}, {info}")
    except Exception as e:
        print(f"[ptt_hr] Jim notification email exception (non-fatal): {e}")

    return jsonify({
        "status": "ok",
        "id":     company_id,
        "message": (
            f"Account created for {company_name}. "
            "Check your email for the login link."
        ),
    }), 200


@ptt_hr_bp.route("/api/ptt/login-request", methods=["POST"])
def ptt_login_request():
    """
    Magic link request for existing admins or workers.
    Body: { email }
    Always returns { status: "ok" } — no enumeration leak.
    """
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or "@" not in email:
        # Still return ok — no enumeration
        return jsonify({"status": "ok"}), 200

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Check admin users first
        cursor.execute("""
            SELECT a.id AS user_id, a.company_id, a.name
            FROM ptt_admin_user a
            WHERE a.email = %s
        """, (email,))
        admin_row = cursor.fetchone()

        if admin_row:
            user_type  = "admin"
            user_id    = admin_row["user_id"]
            company_id = admin_row["company_id"]
            user_name  = admin_row["name"]
        else:
            # Check worker pool
            cursor.execute("""
                SELECT id AS user_id, company_id, name
                FROM ptt_worker
                WHERE email = %s AND status = 'active'
            """, (email,))
            worker_row = cursor.fetchone()
            if worker_row:
                user_type  = "worker"
                user_id    = worker_row["user_id"]
                company_id = worker_row["company_id"]
                user_name  = worker_row["name"]
            else:
                # No match — return ok silently
                return jsonify({"status": "ok"}), 200

    finally:
        conn.close()

    # Create and send magic link (non-fatal)
    try:
        raw_token  = create_magic_token(user_type, user_id, company_id)
        magic_link = _build_magic_link(raw_token)
        ok, info   = send_magic_link(email, magic_link, user_type)
        print(f"[ptt_hr] login-request email: ok={ok}, {info}")
    except Exception as e:
        print(f"[ptt_hr] login-request email exception (non-fatal): {e}")

    return jsonify({"status": "ok"}), 200


@ptt_hr_bp.route("/api/ptt/admin/dashboard-summary", methods=["GET"])
@require_ptt_admin
def ptt_dashboard_summary(ptt_session):
    """
    Returns JSON counts for the dashboard cards.
    Used by the dashboard JS for dynamic refresh (future phases).
    """
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'active')  AS active_workers,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending_workers,
                COUNT(*) FILTER (WHERE status = 'inactive') AS inactive_workers
            FROM ptt_worker
            WHERE company_id = %s
        """, (company_id,))
        worker_counts = cursor.fetchone()

        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'open')      AS open_shifts,
                COUNT(*) FILTER (WHERE status = 'filled')    AS filled_shifts,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_shifts
            FROM ptt_shift
            WHERE company_id = %s
        """, (company_id,))
        shift_counts = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) AS total FROM ptt_skill
            WHERE company_id = %s
        """, (company_id,))
        skill_count = cursor.fetchone()["total"]

    finally:
        conn.close()

    return jsonify({
        "workers": {
            "active":   worker_counts["active_workers"],
            "pending":  worker_counts["pending_workers"],
            "inactive": worker_counts["inactive_workers"],
        },
        "shifts": {
            "open":      shift_counts["open_shifts"],
            "filled":    shift_counts["filled_shifts"],
            "cancelled": shift_counts["cancelled_shifts"],
        },
        "skills": skill_count,
    }), 200

# I did no harm and this file is not truncated.
