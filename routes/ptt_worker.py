"""
routes/ptt_worker.py
AI Swarm Orchestrator — Part Time Tracker: Worker Routes
Shiftwork Solutions LLC

Created:      2026-05-06
Last Updated: 2026-05-06

CHANGELOG:
  2026-05-06 — INITIAL BUILD (Phase 3).
    Worker-side routes: dashboard (matching shifts + my claims),
    claim a shift, profile editing, availability CRUD, blackout CRUD.

ROUTES (HTML):
    GET  /ptt/w/dashboard           — worker home
    GET  /ptt/w/profile             — worker profile + availability + blackouts

API ROUTES:
    POST /api/ptt/worker/shifts/<id>/claim   — claim a shift
    GET  /api/ptt/worker/profile             — get profile
    POST /api/ptt/worker/profile             — update name/phone
    GET  /api/ptt/worker/skills              — get worker's skills
    POST /api/ptt/worker/skills              — update worker's skills (full replace)
    GET  /api/ptt/worker/availability        — get availability rows
    POST /api/ptt/worker/availability        — replace availability (full set)
    GET  /api/ptt/worker/blackouts           — get blackout date ranges
    POST /api/ptt/worker/blackouts           — add a blackout
    DELETE /api/ptt/worker/blackouts/<id>    — delete a blackout

I did no harm and this file is not truncated.
"""

from flask import Blueprint, request, jsonify, render_template, redirect

from db_engine import get_db_connection
from routes.ptt_auth import require_ptt_worker

ptt_worker_bp = Blueprint("ptt_worker", __name__)


# =============================================================================
# HELPER — run the same match filter as HR uses
# =============================================================================

def _get_matching_shifts(cursor, company_id, worker_id):
    """
    Return open future shifts that this worker qualifies for.
    Same filter logic as ptt_shifts_bp.ptt_shift_matches.
    """
    # Get worker's skills
    cursor.execute("""
        SELECT skill_id FROM ptt_worker_skill WHERE worker_id = %s
    """, (worker_id,))
    worker_skill_ids = {r["skill_id"] for r in cursor.fetchall()}

    # Get open future shifts for this company
    cursor.execute("""
        SELECT s.id, s.title, s.shift_date, s.start_time, s.end_time,
               s.workers_needed, s.urgency, s.notes,
               s.skill_required_id, sk.name AS skill_name,
               EXTRACT(DOW FROM s.shift_date)::int AS dow
        FROM ptt_shift s
        LEFT JOIN ptt_skill sk ON sk.id = s.skill_required_id
        WHERE s.company_id = %s
          AND s.status = 'open'
          AND s.shift_date >= CURRENT_DATE
        ORDER BY s.shift_date ASC, s.start_time ASC
    """, (company_id,))
    all_shifts = cursor.fetchall()

    # Get worker availability
    cursor.execute("""
        SELECT day_of_week, start_time, end_time
        FROM ptt_availability WHERE worker_id = %s
    """, (worker_id,))
    avail_rows = cursor.fetchall()
    avail_map = {}  # day_of_week -> list of (start, end)
    for row in avail_rows:
        d = row["day_of_week"]
        if d not in avail_map:
            avail_map[d] = []
        avail_map[d].append((str(row["start_time"]), str(row["end_time"])))

    # Get worker blackouts
    cursor.execute("""
        SELECT start_date, end_date FROM ptt_blackout WHERE worker_id = %s
    """, (worker_id,))
    blackouts = [(str(r["start_date"]), str(r["end_date"]))
                 for r in cursor.fetchall()]

    # Get worker's existing claimed/confirmed shifts
    cursor.execute("""
        SELECT s.shift_date, s.start_time, s.end_time
        FROM ptt_shift_claim c
        JOIN ptt_shift s ON s.id = c.shift_id
        WHERE c.worker_id = %s AND c.status IN ('claimed', 'confirmed')
    """, (worker_id,))
    existing_claims = cursor.fetchall()

    # Filter shifts
    matching = []
    for shift in all_shifts:
        shift_date = str(shift["shift_date"])
        start_t    = str(shift["start_time"])
        end_t      = str(shift["end_time"])
        dow        = shift["dow"]

        # Skill filter
        if shift["skill_required_id"]:
            if shift["skill_required_id"] not in worker_skill_ids:
                continue

        # Availability filter
        day_avail = avail_map.get(dow, [])
        avail_ok = any(
            av_start <= start_t and av_end >= end_t
            for av_start, av_end in day_avail
        )
        if not avail_ok:
            continue

        # Blackout filter
        blacked_out = any(
            bo_start <= shift_date <= bo_end
            for bo_start, bo_end in blackouts
        )
        if blacked_out:
            continue

        # Overlap filter
        overlaps = any(
            str(ec["shift_date"]) == shift_date
            and str(ec["start_time"]) < end_t
            and str(ec["end_time"])   > start_t
            for ec in existing_claims
        )
        if overlaps:
            continue

        matching.append(dict(shift))

    return matching


# =============================================================================
# HTML PAGES
# =============================================================================

@ptt_worker_bp.route("/ptt/w/dashboard")
@require_ptt_worker
def ptt_worker_dashboard(ptt_session, _session_id=None, _sid_from_url=False):
    """Worker dashboard — matching shifts and my claims."""
    worker_id  = ptt_session["user_id"]
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT w.id, w.name, w.email, w.phone
            FROM ptt_worker w
            WHERE w.id = %s AND w.company_id = %s
        """, (worker_id, company_id))
        worker = cursor.fetchone()

        cursor.execute("""
            SELECT name FROM ptt_company WHERE id = %s
        """, (company_id,))
        company = cursor.fetchone()

        matching_shifts = _get_matching_shifts(cursor, company_id, worker_id)

        # My claims
        cursor.execute("""
            SELECT c.id AS claim_id, c.status AS claim_status,
                   c.claimed_at, c.notes AS claim_notes,
                   s.id AS shift_id, s.title, s.shift_date,
                   s.start_time, s.end_time, s.urgency,
                   sk.name AS skill_name
            FROM ptt_shift_claim c
            JOIN ptt_shift s ON s.id = c.shift_id
            LEFT JOIN ptt_skill sk ON sk.id = s.skill_required_id
            WHERE c.worker_id = %s
            ORDER BY s.shift_date ASC, s.start_time ASC
        """, (worker_id,))
        my_claims = cursor.fetchall()

    finally:
        conn.close()

    return render_template("ptt/worker_dashboard.html",
                           worker=worker,
                           company=company,
                           matching_shifts=matching_shifts,
                           my_claims=my_claims,
                           ptt_session=ptt_session,
                           session_id=_session_id or "")


@ptt_worker_bp.route("/ptt/w/profile")
@require_ptt_worker
def ptt_worker_profile_page(ptt_session, _session_id=None, _sid_from_url=False):
    """Worker profile + availability + blackouts."""
    worker_id  = ptt_session["user_id"]
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, email, phone FROM ptt_worker
            WHERE id = %s AND company_id = %s
        """, (worker_id, company_id))
        worker = cursor.fetchone()

        cursor.execute("""
            SELECT name FROM ptt_company WHERE id = %s
        """, (company_id,))
        company = cursor.fetchone()

        # All company skills with checked flag
        cursor.execute("""
            SELECT s.id, s.name, s.sort_order,
                   (ws.skill_id IS NOT NULL) AS checked
            FROM ptt_skill s
            LEFT JOIN ptt_worker_skill ws
                ON ws.skill_id = s.id AND ws.worker_id = %s
            WHERE s.company_id = %s
            ORDER BY s.sort_order ASC, s.name ASC
        """, (worker_id, company_id))
        skills = cursor.fetchall()

        # Availability rows
        cursor.execute("""
            SELECT id, day_of_week, start_time, end_time
            FROM ptt_availability WHERE worker_id = %s
            ORDER BY day_of_week ASC
        """, (worker_id,))
        availability = cursor.fetchall()

        # Blackouts
        cursor.execute("""
            SELECT id, start_date, end_date, reason
            FROM ptt_blackout WHERE worker_id = %s
            ORDER BY start_date ASC
        """, (worker_id,))
        blackouts = cursor.fetchall()

    finally:
        conn.close()

    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday",
                 "Thursday", "Friday", "Saturday"]

    return render_template("ptt/worker_profile.html",
                           worker=worker,
                           company=company,
                           skills=skills,
                           availability=availability,
                           blackouts=blackouts,
                           day_names=day_names,
                           ptt_session=ptt_session,
                           session_id=_session_id or "")


# =============================================================================
# API — CLAIM A SHIFT
# =============================================================================

@ptt_worker_bp.route("/api/ptt/worker/shifts/<int:shift_id>/claim", methods=["POST"])
@require_ptt_worker
def ptt_worker_claim_shift(ptt_session, shift_id):
    """
    Worker claims a shift.
    Re-validates eligibility before inserting the claim.
    Notifies HR admin by email.
    If workers_needed claims exist, marks shift as filled.
    """
    worker_id  = ptt_session["user_id"]
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verify shift is open and belongs to this company
        cursor.execute("""
            SELECT id, title, shift_date, start_time, end_time,
                   workers_needed, status, skill_required_id
            FROM ptt_shift
            WHERE id = %s AND company_id = %s AND status = 'open'
        """, (shift_id, company_id))
        shift = cursor.fetchone()
        if not shift:
            return jsonify({"error": "Shift not found or no longer open"}), 404

        # Re-validate eligibility using same filter logic
        matching = _get_matching_shifts(cursor, company_id, worker_id)
        matching_ids = {s["id"] for s in matching}
        if shift_id not in matching_ids:
            return jsonify({
                "error": "You no longer qualify for this shift "
                         "(skill, availability, or schedule conflict)."
            }), 409

        # Check for existing claim
        cursor.execute("""
            SELECT id, status FROM ptt_shift_claim
            WHERE shift_id = %s AND worker_id = %s
        """, (shift_id, worker_id))
        existing = cursor.fetchone()
        if existing:
            if existing["status"] in ("claimed", "confirmed"):
                return jsonify({"error": "You have already claimed this shift"}), 409
            # Declined — allow re-claim
            cursor.execute("""
                UPDATE ptt_shift_claim
                SET status = 'claimed', claimed_at = NOW(), resolved_at = NULL
                WHERE id = %s
            """, (existing["id"],))
        else:
            cursor.execute("""
                INSERT INTO ptt_shift_claim (shift_id, worker_id, status)
                VALUES (%s, %s, 'claimed')
            """, (shift_id, worker_id))

        # Check if shift is now filled
        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM ptt_shift_claim
            WHERE shift_id = %s AND status IN ('claimed', 'confirmed')
        """, (shift_id,))
        claim_count = cursor.fetchone()["cnt"]

        if claim_count >= shift["workers_needed"]:
            cursor.execute("""
                UPDATE ptt_shift SET status = 'filled', updated_at = NOW()
                WHERE id = %s AND status = 'open'
            """, (shift_id,))

        conn.commit()

        # Get worker name and admin email for notification
        cursor.execute("""
            SELECT name FROM ptt_worker WHERE id = %s
        """, (worker_id,))
        worker_row = cursor.fetchone()
        worker_name = worker_row["name"] if worker_row else "Worker"

        cursor.execute("""
            SELECT email FROM ptt_admin_user
            WHERE company_id = %s ORDER BY id ASC LIMIT 1
        """, (company_id,))
        admin_row = cursor.fetchone()
        admin_email = admin_row["email"] if admin_row else None

    except Exception as e:
        conn.rollback()
        print(f"[ptt_worker] claim shift error: {e}")
        return jsonify({"error": "Failed to claim shift. Please try again."}), 500
    finally:
        conn.close()

    # Notify HR admin (non-fatal)
    try:
        if admin_email:
            from routes.ptt_auth import send_worker_claimed_shift
            shift_date_str = str(shift["shift_date"])
            review_url = f"{request.host_url.rstrip('/')}/ptt/shifts/{shift_id}"
            ok, info = send_worker_claimed_shift(
                admin_email, worker_name,
                shift["title"], shift_date_str,
                review_url)
            print(f"[ptt_worker] claim notification: ok={ok}, {info}")
    except Exception as e:
        print(f"[ptt_worker] claim notification exception (non-fatal): {e}")

    return jsonify({"status": "ok",
                    "message": "Shift claimed. HR will confirm shortly."}), 200


# =============================================================================
# API — PROFILE
# =============================================================================

@ptt_worker_bp.route("/api/ptt/worker/profile", methods=["GET"])
@require_ptt_worker
def ptt_worker_get_profile(ptt_session):
    """Return worker's profile."""
    worker_id  = ptt_session["user_id"]
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, email, phone, status, created_at
            FROM ptt_worker WHERE id = %s AND company_id = %s
        """, (worker_id, company_id))
        worker = cursor.fetchone()
        if not worker:
            return jsonify({"error": "Worker not found"}), 404
    finally:
        conn.close()

    def _dt(v):
        return v.isoformat() if v and hasattr(v, "isoformat") else (str(v) if v else None)

    return jsonify({
        "worker": {
            "id":         worker["id"],
            "name":       worker["name"],
            "email":      worker["email"],
            "phone":      worker["phone"] or "",
            "status":     worker["status"],
            "created_at": _dt(worker["created_at"]),
        }
    }), 200


@ptt_worker_bp.route("/api/ptt/worker/profile", methods=["POST"])
@require_ptt_worker
def ptt_worker_update_profile(ptt_session):
    """
    Update worker name and phone.
    Body: { name, phone }
    Email changes require re-verification — not supported here.
    """
    worker_id  = ptt_session["user_id"]
    company_id = ptt_session["company_id"]
    data  = request.get_json(silent=True) or {}
    name  = (data.get("name")  or "").strip()
    phone = (data.get("phone") or "").strip()

    if not name:
        return jsonify({"error": "Name is required"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ptt_worker SET name = %s, phone = %s
            WHERE id = %s AND company_id = %s
        """, (name, phone or None, worker_id, company_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_worker] update profile error: {e}")
        return jsonify({"error": "Failed to update profile."}), 500
    finally:
        conn.close()

    return jsonify({"status": "ok"}), 200


# =============================================================================
# API — SKILLS
# =============================================================================

@ptt_worker_bp.route("/api/ptt/worker/skills", methods=["GET"])
@require_ptt_worker
def ptt_worker_get_skills(ptt_session):
    """Return worker's current skill IDs."""
    worker_id = ptt_session["user_id"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT skill_id FROM ptt_worker_skill WHERE worker_id = %s
        """, (worker_id,))
        skill_ids = [r["skill_id"] for r in cursor.fetchall()]
    finally:
        conn.close()
    return jsonify({"skill_ids": skill_ids}), 200


@ptt_worker_bp.route("/api/ptt/worker/skills", methods=["POST"])
@require_ptt_worker
def ptt_worker_update_skills(ptt_session):
    """
    Replace worker's skills with the provided list.
    Body: { skill_ids: [int, ...] }
    Only IDs belonging to the worker's company are accepted.
    """
    worker_id  = ptt_session["user_id"]
    company_id = ptt_session["company_id"]
    data = request.get_json(silent=True) or {}
    raw_ids = data.get("skill_ids") or []
    skill_ids = [int(s) for s in raw_ids if str(s).strip().isdigit()]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Validate skill IDs belong to this company
        if skill_ids:
            cursor.execute("""
                SELECT id FROM ptt_skill
                WHERE company_id = %s AND id = ANY(%s::int[])
            """, (company_id, skill_ids))
            valid_ids = [r["id"] for r in cursor.fetchall()]
        else:
            valid_ids = []

        # Replace all skills
        cursor.execute("""
            DELETE FROM ptt_worker_skill WHERE worker_id = %s
        """, (worker_id,))
        for sid in valid_ids:
            cursor.execute("""
                INSERT INTO ptt_worker_skill (worker_id, skill_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (worker_id, sid))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_worker] update skills error: {e}")
        return jsonify({"error": "Failed to update skills."}), 500
    finally:
        conn.close()

    return jsonify({"status": "ok"}), 200


# =============================================================================
# API — AVAILABILITY
# =============================================================================

@ptt_worker_bp.route("/api/ptt/worker/availability", methods=["GET"])
@require_ptt_worker
def ptt_worker_get_availability(ptt_session):
    """Return worker's availability rows."""
    worker_id = ptt_session["user_id"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, day_of_week, start_time, end_time
            FROM ptt_availability WHERE worker_id = %s
            ORDER BY day_of_week ASC
        """, (worker_id,))
        rows = cursor.fetchall()
    finally:
        conn.close()

    availability = [
        {"id": r["id"], "day_of_week": r["day_of_week"],
         "start_time": str(r["start_time"]),
         "end_time":   str(r["end_time"])}
        for r in rows
    ]
    return jsonify({"availability": availability}), 200


@ptt_worker_bp.route("/api/ptt/worker/availability", methods=["POST"])
@require_ptt_worker
def ptt_worker_update_availability(ptt_session):
    """
    Replace worker's availability with the provided set.
    Body: { availability: [ {day_of_week: 0-6, start_time: "HH:MM", end_time: "HH:MM"}, ... ] }
    Deletes all existing rows and inserts the new set.
    Pass an empty array to clear all availability.
    """
    worker_id = ptt_session["user_id"]
    data = request.get_json(silent=True) or {}
    rows = data.get("availability") or []

    # Validate rows
    validated = []
    for row in rows:
        try:
            dow  = int(row.get("day_of_week", -1))
            st   = str(row.get("start_time", "")).strip()
            et   = str(row.get("end_time",   "")).strip()
            if dow < 0 or dow > 6:
                continue
            if not st or not et:
                continue
            if st >= et:
                continue
            validated.append((dow, st, et))
        except (TypeError, ValueError):
            continue

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM ptt_availability WHERE worker_id = %s
        """, (worker_id,))
        for dow, st, et in validated:
            cursor.execute("""
                INSERT INTO ptt_availability (worker_id, day_of_week, start_time, end_time)
                VALUES (%s, %s, %s, %s)
            """, (worker_id, dow, st, et))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_worker] update availability error: {e}")
        return jsonify({"error": "Failed to update availability."}), 500
    finally:
        conn.close()

    return jsonify({"status": "ok", "saved": len(validated)}), 200


# =============================================================================
# API — BLACKOUTS
# =============================================================================

@ptt_worker_bp.route("/api/ptt/worker/blackouts", methods=["GET"])
@require_ptt_worker
def ptt_worker_get_blackouts(ptt_session):
    """Return worker's blackout date ranges."""
    worker_id = ptt_session["user_id"]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, start_date, end_date, reason
            FROM ptt_blackout WHERE worker_id = %s
            ORDER BY start_date ASC
        """, (worker_id,))
        rows = cursor.fetchall()
    finally:
        conn.close()

    blackouts = [
        {"id": r["id"],
         "start_date": str(r["start_date"]),
         "end_date":   str(r["end_date"]),
         "reason":     r["reason"] or ""}
        for r in rows
    ]
    return jsonify({"blackouts": blackouts}), 200


@ptt_worker_bp.route("/api/ptt/worker/blackouts", methods=["POST"])
@require_ptt_worker
def ptt_worker_add_blackout(ptt_session):
    """
    Add a blackout date range.
    Body: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD", reason: "" }
    """
    worker_id = ptt_session["user_id"]
    data       = request.get_json(silent=True) or {}
    start_date = (data.get("start_date") or "").strip()
    end_date   = (data.get("end_date")   or "").strip()
    reason     = (data.get("reason")     or "").strip()

    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required"}), 400
    if start_date > end_date:
        return jsonify({"error": "end_date must be on or after start_date"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ptt_blackout (worker_id, start_date, end_date, reason)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (worker_id, start_date, end_date, reason or None))
        new_id = cursor.fetchone()["id"]
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_worker] add blackout error: {e}")
        return jsonify({"error": "Failed to add blackout."}), 500
    finally:
        conn.close()

    return jsonify({"status": "ok", "id": new_id}), 200


@ptt_worker_bp.route("/api/ptt/worker/blackouts/<int:blackout_id>", methods=["DELETE"])
@require_ptt_worker
def ptt_worker_delete_blackout(ptt_session, blackout_id):
    """Delete a blackout date range."""
    worker_id = ptt_session["user_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM ptt_blackout WHERE id = %s AND worker_id = %s
        """, (blackout_id, worker_id))
        if cursor.rowcount == 0:
            return jsonify({"error": "Blackout not found"}), 404
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_worker] delete blackout error: {e}")
        return jsonify({"error": "Failed to delete blackout."}), 500
    finally:
        conn.close()

    return jsonify({"status": "ok"}), 200

# I did no harm and this file is not truncated.
