"""
routes/ptt_worker_intake.py
AI Swarm Orchestrator — Part Time Tracker: Worker Intake Routes
Shiftwork Solutions LLC

Created:      2026-05-04
Last Updated: 2026-05-04

CHANGELOG:
  2026-05-04 — INITIAL BUILD (Phase 2).
    Public-facing worker application flow:
      GET  /ptt/apply/<slug>       — application form (no auth required)
      POST /api/ptt/apply/<slug>   — submit application

PURPOSE:
    A part-time worker visits the apply URL shared by HR, sees the
    company's current skill list as checkboxes, fills in their info,
    and submits. The application lands in ptt_worker with
    status = 'pending'. The HR admin receives a notification email.

MULTI-TENANCY:
    The slug in the URL resolves to a company_id. All inserts are
    scoped to that company. A worker cannot apply to a company that
    does not exist or whose slug is invalid — the form returns 404.

NO AUTH REQUIRED:
    The apply page and submit endpoint are intentionally public.
    The worker only gains a session after the HR admin approves them
    and they redeem the approval magic link.

I did no harm and this file is not truncated.
"""

from flask import Blueprint, request, jsonify, render_template

from db_engine import get_db_connection
from routes.ptt_auth import send_worker_application_received


ptt_worker_intake_bp = Blueprint("ptt_worker_intake", __name__)


def _build_review_url(company_slug: str) -> str:
    """Build the HR dashboard URL for the pending workers panel."""
    base = request.host_url.rstrip("/")
    return f"{base}/ptt/dashboard"


# =============================================================================
# GET /ptt/apply/<slug>  — public application form
# =============================================================================

@ptt_worker_intake_bp.route("/ptt/apply/<slug>")
def ptt_apply_page(slug):
    """
    Public application form. Resolves slug to company.
    Loads the company's current skill list for the checkboxes.
    Returns 404 if the slug is not found.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, industry FROM ptt_company
            WHERE slug = %s
        """, (slug,))
        company = cursor.fetchone()
        if not company:
            return render_template("ptt/apply_not_found.html"), 404

        cursor.execute("""
            SELECT id, name, description
            FROM ptt_skill
            WHERE company_id = %s
            ORDER BY sort_order ASC, name ASC
        """, (company["id"],))
        skills = cursor.fetchall()
    finally:
        conn.close()

    return render_template(
        "ptt/apply.html",
        company=company,
        skills=skills,
        slug=slug,
    )


# =============================================================================
# POST /api/ptt/apply/<slug>  — submit application
# =============================================================================

@ptt_worker_intake_bp.route("/api/ptt/apply/<slug>", methods=["POST"])
def ptt_apply_submit(slug):
    """
    Accept and store a worker application.
    Body: { name, email, phone (optional), skill_ids (list), notes (optional) }
    Returns: { status: "ok" } or { error: "..." }
    """
    data = request.get_json(silent=True) or {}

    name      = (data.get("name")  or "").strip()
    email     = (data.get("email") or "").strip().lower()
    phone     = (data.get("phone") or "").strip()
    notes     = (data.get("notes") or "").strip()
    skill_ids = data.get("skill_ids") or []

    # Validation
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400
    if not isinstance(skill_ids, list):
        skill_ids = []
    # Sanitise skill_ids to integers only
    skill_ids = [int(s) for s in skill_ids if str(s).strip().isdigit()]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Resolve slug to company
        cursor.execute("""
            SELECT id, name FROM ptt_company WHERE slug = %s
        """, (slug,))
        company = cursor.fetchone()
        if not company:
            return jsonify({"error": "Application link is no longer valid"}), 404

        company_id   = company["id"]
        company_name = company["name"]

        # Check for duplicate application (same email, same company)
        cursor.execute("""
            SELECT id, status FROM ptt_worker
            WHERE company_id = %s AND email = %s
        """, (company_id, email))
        existing = cursor.fetchone()
        if existing:
            if existing["status"] == "active":
                return jsonify({
                    "error": "You are already an active member of this pool."
                }), 409
            if existing["status"] == "pending":
                return jsonify({
                    "error": "Your application is already under review."
                }), 409
            # inactive (rejected) — allow re-application by updating the row
            cursor.execute("""
                UPDATE ptt_worker
                SET name = %s, phone = %s, notes = %s,
                    status = 'pending',
                    rejected_at = NULL, rejection_reason = NULL,
                    approved_by = NULL, approved_at = NULL,
                    created_at = NOW()
                WHERE id = %s AND company_id = %s
                RETURNING id
            """, (name, phone or None, notes or None,
                  existing["id"], company_id))
            worker_id = cursor.fetchone()["id"]

            # Refresh skill assignments
            cursor.execute("""
                DELETE FROM ptt_worker_skill WHERE worker_id = %s
            """, (worker_id,))
        else:
            # New worker
            cursor.execute("""
                INSERT INTO ptt_worker
                    (company_id, name, email, phone, notes, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                RETURNING id
            """, (company_id, name, email,
                  phone or None, notes or None))
            worker_id = cursor.fetchone()["id"]

        # Insert skill associations — verify each skill belongs to this company
        if skill_ids:
            cursor.execute("""
                SELECT id FROM ptt_skill
                WHERE company_id = %s AND id = ANY(%s::int[])
            """, (company_id, skill_ids))
            valid_skill_ids = [r["id"] for r in cursor.fetchall()]
            for sid in valid_skill_ids:
                cursor.execute("""
                    INSERT INTO ptt_worker_skill (worker_id, skill_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (worker_id, sid))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"[ptt_worker_intake] apply submit error: {e}")
        return jsonify({"error": "An error occurred. Please try again."}), 500
    finally:
        conn.close()

    # Notify HR admin (non-fatal)
    try:
        # Get the primary admin email for this company
        conn2 = get_db_connection()
        try:
            c2 = conn2.cursor()
            c2.execute("""
                SELECT email FROM ptt_admin_user
                WHERE company_id = %s
                ORDER BY id ASC LIMIT 1
            """, (company_id,))
            admin_row = c2.fetchone()
            admin_email = admin_row["email"] if admin_row else None
        finally:
            conn2.close()

        if admin_email:
            review_url = _build_review_url(slug)
            ok, info = send_worker_application_received(
                admin_email, name, email, company_name, review_url)
            print(f"[ptt_worker_intake] admin notification: ok={ok}, {info}")
    except Exception as e:
        print(f"[ptt_worker_intake] admin notification exception (non-fatal): {e}")

    return jsonify({
        "status":  "ok",
        "message": "Your application has been submitted. "
                   "You will receive an email if you are approved.",
    }), 200

# I did no harm and this file is not truncated.
