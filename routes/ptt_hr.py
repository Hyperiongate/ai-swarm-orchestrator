"""
routes/ptt_hr.py  —  Part Time Tracker: HR Admin Routes
Shiftwork Solutions LLC
Created: 2026-05-01  |  Last Updated: 2026-05-04

CHANGELOG:
  2026-05-04 — COOKIE FIX. ONE CHANGE ONLY.
    ptt_auth_redeem now returns a 200 HTML page instead of a 302 redirect.
    Render's proxy strips Set-Cookie headers from 302 responses.
    A 200 response preserves Set-Cookie. JS then navigates to dashboard.
    Two local constants (PTT_COOKIE_NAME, PTT_COOKIE_MAX_AGE) defined
    inline — no import dependency on ptt_auth module-level names.
    All other functions identical to the previously working version.

  2026-05-04 — Phase 2 update. Skills CRUD, worker approval, 14-skill seed.
  2026-05-01 — INITIAL BUILD.

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
    send_magic_link, send_worker_approved, insert_ptt_lead,
    require_ptt_admin,
)

ptt_hr_bp = Blueprint("ptt_hr", __name__)

# Inline cookie constants — must match ptt_auth.py values.
# Hardcoded here to avoid any import-time dependency.
PTT_COOKIE_NAME    = "ptt_session"
PTT_COOKIE_MAX_AGE = 30 * 24 * 3600   # 2592000 seconds

INDUSTRY_OPTIONS = [
    "Manufacturing", "Pharmaceutical", "Food & Beverage", "Chemical",
    "Distribution / Warehouse", "Mining", "Utilities", "Oil & Gas",
    "Healthcare", "Other",
]

FACILITY_SIZE_OPTIONS = [
    "Under 50 employees", "50 – 199 employees", "200 – 499 employees",
    "500 – 999 employees", "1,000+ employees",
]

SKILL_SEED = [
    ("General Labor",
     "Entry-level work including loading, unloading, staging, and other "
     "physical tasks not requiring specific certification.", 1),
    ("Forklift Operator",
     "Certified to operate sit-down, stand-up, or reach forklifts. "
     "Includes pallet jacks where applicable.", 2),
    ("Machine Operator",
     "Trained to run production equipment including setup, monitoring, "
     "basic adjustments, and changeovers.", 3),
    ("Mechanic",
     "Industrial or maintenance mechanic — repairs, preventive maintenance, "
     "and troubleshooting of plant equipment.", 4),
    ("Electrician",
     "Licensed or qualified electrician for industrial electrical work, "
     "wiring, and troubleshooting.", 5),
    ("HVAC Technician",
     "Heating, ventilation, air conditioning, and refrigeration systems — "
     "installation, service, and repair.", 6),
    ("Controls Technician (PLC)",
     "Programs, troubleshoots, and maintains PLCs and industrial control "
     "systems.", 7),
    ("Quality Control Technician",
     "Inspects products, performs testing, documents results, and supports "
     "quality assurance protocols.", 8),
    ("Sanitation",
     "Plant cleaning, sanitization, and food-safety or GMP-compliant "
     "cleaning where applicable.", 9),
    ("Grounds Keeper",
     "Outdoor maintenance — landscaping, snow removal, parking lot upkeep, "
     "exterior facility care.", 10),
    ("Security",
     "Facility security, access control, patrols, and incident response.", 11),
    ("Customer Service",
     "Phone, email, or in-person customer or client interaction including "
     "order support and inquiry handling.", 12),
    ("Data Entry",
     "Keyboarding, data input, basic spreadsheet work, and administrative "
     "documentation.", 13),
    ("Trainer / Lead Worker",
     "Experienced workers qualified to train new hires, lead crews, and "
     "verify task completion.", 14),
]


def _build_magic_link(raw_token: str) -> str:
    base = request.host_url.rstrip("/")
    return f"{base}/ptt/auth?token={raw_token}"


@ptt_hr_bp.route("/ptt/")
@ptt_hr_bp.route("/ptt")
def ptt_landing():
    session = get_current_session()
    if session and session.get("user_type") == "admin":
        return redirect("/ptt/dashboard")
    if session and session.get("user_type") == "worker":
        return redirect("/ptt/w/dashboard")
    return render_template("ptt/signup.html",
                           industry_options=INDUSTRY_OPTIONS,
                           facility_size_options=FACILITY_SIZE_OPTIONS)


@ptt_hr_bp.route("/ptt/login")
def ptt_login_page():
    session = get_current_session()
    if session and session.get("user_type") == "admin":
        return redirect("/ptt/dashboard")
    return render_template("ptt/login.html")


@ptt_hr_bp.route("/ptt/auth")
def ptt_auth_redeem():
    """
    Token redemption. Returns 200 HTML so Render's proxy preserves
    the Set-Cookie header (proxy strips it on 302 redirects).
    JS navigates to the dashboard after cookie is stored.
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

    if user_type == "admin":
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ptt_admin_user SET last_login_at = NOW()
                WHERE id = %s AND company_id = %s
            """, (user_id, company_id))
            conn.commit()
        finally:
            conn.close()

    session_id = create_session(user_type, user_id, company_id)
    dest = "/ptt/dashboard" if user_type == "admin" else "/ptt/w/dashboard"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Logging in...</title>
<style>
body{{font-family:Arial,sans-serif;background:#1F3D5C;display:flex;
     align-items:center;justify-content:center;min-height:100vh;margin:0}}
.msg{{color:#fff;font-size:16px;text-align:center}}
.spinner{{width:36px;height:36px;border:3px solid rgba(255,255,255,.3);
          border-top-color:#E8610A;border-radius:50%;
          animation:spin .7s linear infinite;margin:0 auto 16px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style></head>
<body><div class="msg"><div class="spinner"></div>Logging you in...</div>
<script>setTimeout(function(){{window.location.href="{dest}";}},400);</script>
</body></html>"""

    resp = make_response(html, 200)
    resp.headers["Content-Type"] = "text/html"
    resp.set_cookie(PTT_COOKIE_NAME, session_id,
                    max_age=PTT_COOKIE_MAX_AGE,
                    httponly=True, samesite="Lax", path="/")
    return resp


@ptt_hr_bp.route("/ptt/dashboard")
@require_ptt_admin
def ptt_dashboard(ptt_session):
    company_id = ptt_session["company_id"]
    admin_id   = ptt_session["user_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name, slug, industry, facility_size, created_at "
                       "FROM ptt_company WHERE id = %s", (company_id,))
        company = cursor.fetchone()

        cursor.execute("SELECT name, email FROM ptt_admin_user "
                       "WHERE id = %s AND company_id = %s", (admin_id, company_id))
        admin = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) AS total FROM ptt_worker "
                       "WHERE company_id = %s AND status = 'active'", (company_id,))
        active_workers = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM ptt_worker "
                       "WHERE company_id = %s AND status = 'pending'", (company_id,))
        pending_workers = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM ptt_shift "
                       "WHERE company_id = %s AND status = 'open'", (company_id,))
        open_shifts = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM ptt_skill "
                       "WHERE company_id = %s", (company_id,))
        skill_count = cursor.fetchone()["total"]

        cursor.execute("""SELECT id, name, email, phone, created_at
            FROM ptt_worker WHERE company_id = %s AND status = 'pending'
            ORDER BY created_at ASC LIMIT 10""", (company_id,))
        pending_list = cursor.fetchall()

        cursor.execute("""SELECT id, name, description, sort_order
            FROM ptt_skill WHERE company_id = %s
            ORDER BY sort_order ASC, name ASC""", (company_id,))
        skills = cursor.fetchall()
    finally:
        conn.close()

    apply_url = f"{request.host_url.rstrip('/')}/ptt/apply/{company['slug']}"
    return render_template("ptt/dashboard.html",
                           company=company, admin=admin,
                           active_workers=active_workers,
                           pending_workers=pending_workers,
                           open_shifts=open_shifts,
                           skill_count=skill_count,
                           apply_url=apply_url,
                           pending_list=pending_list,
                           skills=skills)


@ptt_hr_bp.route("/ptt/logout")
def ptt_logout():
    session_id = request.cookies.get(PTT_COOKIE_NAME)
    if session_id:
        delete_session(session_id)
    resp = make_response(redirect("/ptt/"))
    clear_session_cookie(resp)
    return resp


@ptt_hr_bp.route("/api/ptt/lead", methods=["POST"])
def ptt_lead_signup():
    data = request.get_json(silent=True) or {}
    name          = (data.get("name")          or "").strip()
    email         = (data.get("email")         or "").strip().lower()
    company_name  = (data.get("company_name")  or "").strip()
    industry      = (data.get("industry")      or "").strip()
    facility_size = (data.get("facility_size") or "").strip()

    if not name:
        return jsonify({"error": "Name is required"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "A valid email address is required"}), 400
    if is_free_mail(email):
        return jsonify({"error": "Please use your work email address. "
                                 "Free email services (Gmail, Yahoo, etc.) are not accepted."}), 400
    if not company_name:
        return jsonify({"error": "Company name is required"}), 400

    email_domain = extract_domain(email)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ptt_admin_user WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": "An account with this email already exists. "
                                     "Use the login page to request a new link."}), 409

        slug = generate_slug(company_name)
        for _ in range(5):
            cursor.execute("SELECT id FROM ptt_company WHERE slug = %s", (slug,))
            if not cursor.fetchone():
                break
            slug = generate_slug(company_name)

        cursor.execute("""INSERT INTO ptt_company
            (name, slug, email_domain, signup_email, industry, facility_size)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (company_name, slug, email_domain, email, industry, facility_size))
        company_id = cursor.fetchone()["id"]

        cursor.execute("""INSERT INTO ptt_admin_user (company_id, email, name)
            VALUES (%s,%s,%s) RETURNING id""", (company_id, email, name))
        admin_id = cursor.fetchone()["id"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM ptt_skill WHERE company_id = %s",
                       (company_id,))
        if cursor.fetchone()["cnt"] == 0:
            for sname, sdesc, sorder in SKILL_SEED:
                cursor.execute("""INSERT INTO ptt_skill
                    (company_id, name, description, sort_order) VALUES (%s,%s,%s,%s)""",
                    (company_id, sname, sdesc, sorder))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_hr] signup DB error: {e}")
        return jsonify({"error": "An error occurred. Please try again."}), 500
    finally:
        conn.close()

    try:
        insert_ptt_lead(company_name, name, email, industry, facility_size)
    except Exception as e:
        print(f"[ptt_hr] lead insert error (non-fatal): {e}")

    try:
        raw_token  = create_magic_token("admin", admin_id, company_id)
        magic_link = _build_magic_link(raw_token)
    except Exception as e:
        print(f"[ptt_hr] token creation error: {e}")
        return jsonify({"error": "Account created but login link failed. "
                                  "Please use the login page."}), 500

    try:
        ok, info = send_hr_signup_confirmation(email, name, company_name, magic_link)
        print(f"[ptt_hr] signup confirmation email: ok={ok}, {info}")
    except Exception as e:
        print(f"[ptt_hr] signup confirmation email exception (non-fatal): {e}")

    try:
        ok, info = send_hr_signup_notification(name, email, company_name,
                                               industry, facility_size)
        print(f"[ptt_hr] Jim notification email: ok={ok}, {info}")
    except Exception as e:
        print(f"[ptt_hr] Jim notification email exception (non-fatal): {e}")

    return jsonify({"status": "ok", "id": company_id,
                    "message": f"Account created for {company_name}. "
                               "Check your email for the login link."}), 200


@ptt_hr_bp.route("/api/ptt/login-request", methods=["POST"])
def ptt_login_request():
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"status": "ok"}), 200

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT a.id AS user_id, a.company_id FROM ptt_admin_user a "
                       "WHERE a.email = %s", (email,))
        admin_row = cursor.fetchone()
        if admin_row:
            user_type, user_id, company_id = "admin", admin_row["user_id"], admin_row["company_id"]
        else:
            cursor.execute("SELECT id AS user_id, company_id FROM ptt_worker "
                           "WHERE email = %s AND status = 'active'", (email,))
            worker_row = cursor.fetchone()
            if worker_row:
                user_type, user_id, company_id = "worker", worker_row["user_id"], worker_row["company_id"]
            else:
                return jsonify({"status": "ok"}), 200
    finally:
        conn.close()

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
    company_id = ptt_session["company_id"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT
            COUNT(*) FILTER (WHERE status='active')   AS active_workers,
            COUNT(*) FILTER (WHERE status='pending')  AS pending_workers,
            COUNT(*) FILTER (WHERE status='inactive') AS inactive_workers
            FROM ptt_worker WHERE company_id=%s""", (company_id,))
        wc = cursor.fetchone()

        cursor.execute("""SELECT
            COUNT(*) FILTER (WHERE status='open')      AS open_shifts,
            COUNT(*) FILTER (WHERE status='filled')    AS filled_shifts,
            COUNT(*) FILTER (WHERE status='cancelled') AS cancelled_shifts
            FROM ptt_shift WHERE company_id=%s""", (company_id,))
        sc = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) AS total FROM ptt_skill WHERE company_id=%s",
                       (company_id,))
        skill_count = cursor.fetchone()["total"]
    finally:
        conn.close()

    return jsonify({"workers": {"active": wc["active_workers"],
                                "pending": wc["pending_workers"],
                                "inactive": wc["inactive_workers"]},
                    "shifts":  {"open": sc["open_shifts"],
                                "filled": sc["filled_shifts"],
                                "cancelled": sc["cancelled_shifts"]},
                    "skills": skill_count}), 200


@ptt_hr_bp.route("/api/ptt/admin/skills", methods=["GET"])
@require_ptt_admin
def ptt_skills_list(ptt_session):
    company_id = ptt_session["company_id"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT id, name, description, sort_order FROM ptt_skill
            WHERE company_id=%s ORDER BY sort_order ASC, name ASC""", (company_id,))
        rows = cursor.fetchall()
    finally:
        conn.close()
    return jsonify({"skills": [{"id": r["id"], "name": r["name"],
                                "description": r["description"] or "",
                                "sort_order": r["sort_order"]} for r in rows]}), 200


@ptt_hr_bp.route("/api/ptt/admin/skills", methods=["POST"])
@require_ptt_admin
def ptt_skill_create(ptt_session):
    company_id = ptt_session["company_id"]
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    desc = (data.get("description") or "").strip()
    if not name:
        return jsonify({"error": "Skill name is required"}), 400
    if len(name) > 120:
        return jsonify({"error": "Skill name must be 120 characters or fewer"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ptt_skill WHERE company_id=%s AND LOWER(name)=LOWER(%s)",
                       (company_id, name))
        if cursor.fetchone():
            return jsonify({"error": f"A skill named '{name}' already exists"}), 409
        cursor.execute("SELECT COALESCE(MAX(sort_order),0) AS max_order FROM ptt_skill "
                       "WHERE company_id=%s", (company_id,))
        next_order = cursor.fetchone()["max_order"] + 1
        cursor.execute("""INSERT INTO ptt_skill (company_id, name, description, sort_order)
            VALUES (%s,%s,%s,%s) RETURNING id""", (company_id, name, desc, next_order))
        new_id = cursor.fetchone()["id"]
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_hr] skill create error: {e}")
        return jsonify({"error": "Failed to create skill. Please try again."}), 500
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": new_id}), 200


@ptt_hr_bp.route("/api/ptt/admin/skills/<int:skill_id>", methods=["PUT"])
@require_ptt_admin
def ptt_skill_update(ptt_session, skill_id):
    company_id = ptt_session["company_id"]
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    desc = (data.get("description") or "").strip()
    if not name:
        return jsonify({"error": "Skill name is required"}), 400
    if len(name) > 120:
        return jsonify({"error": "Skill name must be 120 characters or fewer"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ptt_skill WHERE id=%s AND company_id=%s",
                       (skill_id, company_id))
        if not cursor.fetchone():
            return jsonify({"error": "Skill not found"}), 404
        cursor.execute("SELECT id FROM ptt_skill WHERE company_id=%s AND LOWER(name)=LOWER(%s) AND id!=%s",
                       (company_id, name, skill_id))
        if cursor.fetchone():
            return jsonify({"error": f"A skill named '{name}' already exists"}), 409
        cursor.execute("UPDATE ptt_skill SET name=%s, description=%s WHERE id=%s AND company_id=%s",
                       (name, desc, skill_id, company_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_hr] skill update error: {e}")
        return jsonify({"error": "Failed to update skill. Please try again."}), 500
    finally:
        conn.close()
    return jsonify({"status": "ok"}), 200


@ptt_hr_bp.route("/api/ptt/admin/skills/reorder", methods=["POST"])
@require_ptt_admin
def ptt_skills_reorder(ptt_session):
    company_id  = ptt_session["company_id"]
    data        = request.get_json(silent=True) or {}
    ordered_ids = data.get("ordered_ids") or []
    if not ordered_ids or not isinstance(ordered_ids, list):
        return jsonify({"error": "ordered_ids array is required"}), 400
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        for position, skill_id in enumerate(ordered_ids, start=1):
            cursor.execute("UPDATE ptt_skill SET sort_order=%s WHERE id=%s AND company_id=%s",
                           (position, skill_id, company_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_hr] skills reorder error: {e}")
        return jsonify({"error": "Failed to save order. Please try again."}), 500
    finally:
        conn.close()
    return jsonify({"status": "ok"}), 200


@ptt_hr_bp.route("/api/ptt/admin/skills/<int:skill_id>", methods=["DELETE"])
@require_ptt_admin
def ptt_skill_delete(ptt_session, skill_id):
    company_id = ptt_session["company_id"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ptt_skill WHERE id=%s AND company_id=%s",
                       (skill_id, company_id))
        if cursor.rowcount == 0:
            return jsonify({"error": "Skill not found"}), 404
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_hr] skill delete error: {e}")
        return jsonify({"error": "Failed to delete skill. Please try again."}), 500
    finally:
        conn.close()
    return jsonify({"status": "ok"}), 200


@ptt_hr_bp.route("/api/ptt/admin/workers/pending", methods=["GET"])
@require_ptt_admin
def ptt_workers_pending(ptt_session):
    company_id = ptt_session["company_id"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT id, name, email, phone, notes, created_at
            FROM ptt_worker WHERE company_id=%s AND status='pending'
            ORDER BY created_at ASC""", (company_id,))
        workers = cursor.fetchall()
        result = []
        for w in workers:
            cursor.execute("""SELECT s.id, s.name FROM ptt_worker_skill ws
                JOIN ptt_skill s ON s.id=ws.skill_id WHERE ws.worker_id=%s
                ORDER BY s.sort_order ASC""", (w["id"],))
            skills = [{"id": r["id"], "name": r["name"]} for r in cursor.fetchall()]
            result.append({
                "id": w["id"], "name": w["name"], "email": w["email"],
                "phone": w["phone"] or "", "notes": w["notes"] or "",
                "skills": skills,
                "applied_at": w["created_at"].isoformat()
                              if hasattr(w["created_at"], "isoformat")
                              else str(w["created_at"]),
            })
    finally:
        conn.close()
    return jsonify({"workers": result}), 200


@ptt_hr_bp.route("/api/ptt/admin/workers/<int:worker_id>/approve", methods=["POST"])
@require_ptt_admin
def ptt_worker_approve(ptt_session, worker_id):
    company_id = ptt_session["company_id"]
    admin_id   = ptt_session["user_id"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email FROM ptt_worker "
                       "WHERE id=%s AND company_id=%s AND status='pending'",
                       (worker_id, company_id))
        worker = cursor.fetchone()
        if not worker:
            return jsonify({"error": "Worker not found or already processed"}), 404
        cursor.execute("SELECT name FROM ptt_company WHERE id=%s", (company_id,))
        co = cursor.fetchone()
        company_name = co["name"] if co else ""
        cursor.execute("""UPDATE ptt_worker SET status='active',
            approved_by=%s, approved_at=NOW() WHERE id=%s AND company_id=%s""",
            (admin_id, worker_id, company_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_hr] worker approve DB error: {e}")
        return jsonify({"error": "Failed to approve worker. Please try again."}), 500
    finally:
        conn.close()
    try:
        raw_token  = create_magic_token("worker", worker_id, company_id)
        magic_link = _build_magic_link(raw_token)
        ok, info   = send_worker_approved(worker["email"], worker["name"],
                                          company_name, magic_link)
        print(f"[ptt_hr] worker approved email: ok={ok}, {info}")
    except Exception as e:
        print(f"[ptt_hr] worker approved email exception (non-fatal): {e}")
    return jsonify({"status": "ok"}), 200


@ptt_hr_bp.route("/api/ptt/admin/workers/<int:worker_id>/reject", methods=["POST"])
@require_ptt_admin
def ptt_worker_reject(ptt_session, worker_id):
    company_id = ptt_session["company_id"]
    data   = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ptt_worker WHERE id=%s AND company_id=%s AND status='pending'",
                       (worker_id, company_id))
        if not cursor.fetchone():
            return jsonify({"error": "Worker not found or already processed"}), 404
        cursor.execute("""UPDATE ptt_worker SET status='inactive',
            rejected_at=NOW(), rejection_reason=%s WHERE id=%s AND company_id=%s""",
            (reason or None, worker_id, company_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_hr] worker reject DB error: {e}")
        return jsonify({"error": "Failed to reject worker. Please try again."}), 500
    finally:
        conn.close()
    return jsonify({"status": "ok"}), 200


@ptt_hr_bp.route("/api/ptt/admin/workers/<int:worker_id>", methods=["GET"])
@require_ptt_admin
def ptt_worker_detail(ptt_session, worker_id):
    company_id = ptt_session["company_id"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT w.id, w.name, w.email, w.phone, w.status, w.notes,
            w.created_at, w.approved_at, w.rejected_at, w.rejection_reason,
            a.name AS approved_by_name FROM ptt_worker w
            LEFT JOIN ptt_admin_user a ON a.id=w.approved_by
            WHERE w.id=%s AND w.company_id=%s""", (worker_id, company_id))
        worker = cursor.fetchone()
        if not worker:
            return jsonify({"error": "Worker not found"}), 404
        cursor.execute("""SELECT s.id, s.name FROM ptt_worker_skill ws
            JOIN ptt_skill s ON s.id=ws.skill_id WHERE ws.worker_id=%s
            ORDER BY s.sort_order ASC""", (worker_id,))
        skills = [{"id": r["id"], "name": r["name"]} for r in cursor.fetchall()]
        cursor.execute("""SELECT id, day_of_week, start_time, end_time
            FROM ptt_availability WHERE worker_id=%s
            ORDER BY day_of_week ASC, start_time ASC""", (worker_id,))
        day_names = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
        availability = [{"id": r["id"], "day_of_week": r["day_of_week"],
                         "day_name": day_names[r["day_of_week"]],
                         "start_time": str(r["start_time"]),
                         "end_time": str(r["end_time"])}
                        for r in cursor.fetchall()]
    finally:
        conn.close()

    def _dt(v):
        return v.isoformat() if v and hasattr(v, "isoformat") else (str(v) if v else None)

    return jsonify({"worker": {
        "id": worker["id"], "name": worker["name"], "email": worker["email"],
        "phone": worker["phone"] or "", "status": worker["status"],
        "notes": worker["notes"] or "",
        "created_at": _dt(worker["created_at"]),
        "approved_at": _dt(worker["approved_at"]),
        "rejected_at": _dt(worker["rejected_at"]),
        "rejection_reason": worker["rejection_reason"] or "",
        "approved_by_name": worker["approved_by_name"] or "",
        "skills": skills, "availability": availability,
    }}), 200

# I did no harm and this file is not truncated.
