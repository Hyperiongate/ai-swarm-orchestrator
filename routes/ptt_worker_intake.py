"""
routes/ptt_worker_intake.py
AI Swarm Orchestrator — Part Time Tracker: Worker Intake Routes
Shiftwork Solutions LLC

Created:      2026-05-04
Last Updated: 2026-05-28

CHANGELOG:
  2026-05-28 — APPLICANT CONFIRMATION EMAIL.
    After a successful application submission, send a confirmation email
    to the applicant via send_applicant_received(). The email:
      - Confirms their application was received
      - Names the company they applied to
      - Says the team will be reaching out directly
    Fire-and-forget (non-fatal) — never blocks or breaks the submission.
    Added send_applicant_received to the import from routes.ptt_auth.

  2026-05-08 — REVIEW URL FIX.
    Changed _build_review_url to point to /ptt/login instead of
    /ptt/dashboard. The dashboard requires an active session, so
    clicking the link from email was redirecting to the signup page.
    Now it goes to the login page where HR can authenticate first.

  2026-05-05 — DUPLICATE CHECK FIX.
    Changed duplicate application check from email-only to name+email
    combination. The same email can appear with different names (e.g.,
    two people sharing an email address). Only the exact name+email
    pair is treated as a duplicate for a given company.

  2026-05-04 — INITIAL BUILD (Phase 2).
    Public-facing worker application flow.

I did no harm and this file is not truncated.
"""

from flask import Blueprint, request, jsonify, render_template

from db_engine import get_db_connection
from routes.ptt_auth import (
    send_worker_application_received,
    send_applicant_received,
)


ptt_worker_intake_bp = Blueprint("ptt_worker_intake", __name__)


def _build_review_url(company_slug: str) -> str:
    """
    Build the HR review URL for the pending workers notification email.
    Points to /ptt/login so the admin is prompted to log in first.
    After login they land on /ptt/dashboard where the pending panel is.
    """
    base = request.host_url.rstrip("/")
    return f"{base}/ptt/login"


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

    On success:
      - Notifies HR admin by email (existing behaviour)
      - Sends confirmation email to the applicant (new — non-fatal)

    DUPLICATE LOGIC:
    Duplicates are detected on name+email combination per company, NOT
    email alone. Two people sharing an email address are allowed to apply
    as long as their names differ. Only the exact name+email pair is
    considered a duplicate.
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

        # Check for duplicate: same name AND same email for this company.
        cursor.execute("""
            SELECT id, status FROM ptt_worker
            WHERE company_id = %s
              AND LOWER(email) = %s
              AND LOWER(name)  = LOWER(%s)
        """, (company_id, email, name))
        existing = cursor.fetchone()

        if existing:
            if existing["status"] == "active":
                return jsonify({
                    "error": "An active pool member with this name and email already exists."
                }), 409
            if existing["status"] == "pending":
                return jsonify({
                    "error": "An application with this name and email is already under review."
                }), 409
            # inactive (rejected) — allow re-application by updating the row
            cursor.execute("""
                UPDATE ptt_worker
                SET phone = %s, notes = %s,
                    status = 'pending',
                    rejected_at = NULL, rejection_reason = NULL,
                    approved_by = NULL, approved_at = NULL,
                    created_at = NOW()
                WHERE id = %s AND company_id = %s
                RETURNING id
            """, (phone or None, notes or None,
                  existing["id"], company_id))
            worker_id = cursor.fetchone()["id"]

            # Refresh skill assignments
            cursor.execute("""
                DELETE FROM ptt_worker_skill WHERE worker_id = %s
            """, (worker_id,))
        else:
            # New worker row
            cursor.execute("""
                INSERT INTO ptt_worker
                    (company_id, name, email, phone, notes, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                RETURNING id
            """, (company_id, name, email,
                  phone or None, notes or None))
            worker_id = cursor.fetchone()["id"]

        # Insert skill associations
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

    # Send confirmation email to applicant (non-fatal)
    try:
        ok, info = send_applicant_received(email, name, company_name)
        print(f"[ptt_worker_intake] applicant confirmation: ok={ok}, {info}")
    except Exception as e:
        print(f"[ptt_worker_intake] applicant confirmation exception (non-fatal): {e}")

    return jsonify({
        "status":  "ok",
        "message": "Your application has been submitted. "
                   "You will receive a confirmation email shortly.",
    }), 200

# I did no harm and this file is not truncated.
