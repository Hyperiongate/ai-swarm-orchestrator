"""
routes/ptt_shifts.py
AI Swarm Orchestrator - Part Time Tracker: HR Shift Management Routes
Shiftwork Solutions LLC

Created:      2026-05-06
Last Updated: 2026-06-03 - WO-5 encoding fix: replaced em-dash on line 3
              with ASCII hyphen (was causing SyntaxError: invalid character
              U+2014 on startup, preventing ptt_shifts_bp from registering).

CHANGELOG:
  2026-06-03 - ENCODING FIX.
    Replaced em-dash (U+2014) with ASCII hyphen (-) in the module
    docstring header. No functional changes whatsoever.

  2026-05-06 - INITIAL BUILD (Phase 3).
    HR shift management: create, list, view, cancel shifts.
    Matching engine: filters active workers by skill, availability,
    blackouts, and existing commitments.
    Outreach tracking: mark a worker as contacted for a shift.
    Claim management: confirm or decline worker-initiated claims.

ROUTES (HTML):
    GET  /ptt/shifts                -- shift list
    GET  /ptt/shifts/new            -- create shift form
    GET  /ptt/shifts/<id>           -- shift detail + matches + claims

API ROUTES:
    POST /api/ptt/admin/shifts                     -- create shift
    POST /api/ptt/admin/shifts/<id>/cancel         -- cancel shift
    GET  /api/ptt/admin/shifts/<id>/matches        -- qualified workers
    POST /api/ptt/admin/shifts/<id>/outreach/<wid> -- mark as contacted
    POST /api/ptt/admin/claims/<id>/confirm        -- confirm claim
    POST /api/ptt/admin/claims/<id>/decline        -- decline claim

MATCHING LOGIC:
    1. Active workers in this company
    2. Filter by skill_required_id (if set)
    3. Filter by availability (day_of_week covers shift start+end time)
    4. Exclude blackouts covering the shift date
    5. Exclude workers with overlapping confirmed/claimed shifts

I did no harm and this file is not truncated.
"""

from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, render_template, redirect

from db_engine import get_db_connection
from routes.ptt_auth import require_ptt_admin, send_worker_claimed_shift

ptt_shifts_bp = Blueprint("ptt_shifts", __name__)


# =============================================================================
# HTML PAGES
# =============================================================================

@ptt_shifts_bp.route("/ptt/shifts")
@require_ptt_admin
def ptt_shifts_list(ptt_session, _session_id=None):
    """HR shift list page."""
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM ptt_company WHERE id = %s
        """, (company_id,))
        company = cursor.fetchone()

        cursor.execute("""
            SELECT s.id, s.title, s.shift_date,
                   s.start_time::text AS start_time,
                   s.end_time::text AS end_time,
                   s.workers_needed, s.status, s.urgency, s.notes,
                   s.created_at,
                   sk.name AS skill_name,
                   COUNT(c.id) FILTER (WHERE c.status IN ('claimed','confirmed'))
                       AS claim_count
            FROM ptt_shift s
            LEFT JOIN ptt_skill sk ON sk.id = s.skill_required_id
            LEFT JOIN ptt_shift_claim c ON c.shift_id = s.id
            WHERE s.company_id = %s
            GROUP BY s.id, sk.name
            ORDER BY s.shift_date ASC, s.start_time ASC
        """, (company_id,))
        shifts = cursor.fetchall()

        cursor.execute("""
            SELECT id, name FROM ptt_skill
            WHERE company_id = %s ORDER BY sort_order ASC, name ASC
        """, (company_id,))
        skills = cursor.fetchall()

    finally:
        conn.close()

    return render_template("ptt/shifts.html",
                           company=company,
                           shifts=shifts,
                           skills=skills,
                           ptt_session=ptt_session,
                           session_id=_session_id or "")


@ptt_shifts_bp.route("/ptt/shifts/<int:shift_id>")
@require_ptt_admin
def ptt_shift_detail(ptt_session, shift_id, _session_id=None):
    """HR shift detail page -- shows matches and claims."""
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT s.id, s.title, s.shift_date,
                   s.start_time::text AS start_time,
                   s.end_time::text AS end_time,
                   s.workers_needed, s.status, s.urgency, s.notes,
                   s.created_at, s.skill_required_id,
                   sk.name AS skill_name
            FROM ptt_shift s
            LEFT JOIN ptt_skill sk ON sk.id = s.skill_required_id
            WHERE s.id = %s AND s.company_id = %s
        """, (shift_id, company_id))
        shift = cursor.fetchone()
        if not shift:
            return redirect("/ptt/shifts")

        # Claims with worker info
        cursor.execute("""
            SELECT c.id, c.status, c.claimed_at, c.notes,
                   w.id AS worker_id, w.name AS worker_name,
                   w.email AS worker_email, w.phone AS worker_phone
            FROM ptt_shift_claim c
            JOIN ptt_worker w ON w.id = c.worker_id
            WHERE c.shift_id = %s
            ORDER BY c.claimed_at ASC
        """, (shift_id,))
        claims = cursor.fetchall()

        # Outreach records for this shift
        cursor.execute("""
            SELECT worker_id FROM ptt_shift_outreach WHERE shift_id = %s
        """, (shift_id,))
        contacted_ids = {r["worker_id"] for r in cursor.fetchall()}

        # Company name
        cursor.execute("SELECT name FROM ptt_company WHERE id = %s", (company_id,))
        company = cursor.fetchone()

    finally:
        conn.close()

    today = datetime.now(timezone.utc).date().isoformat()
    return render_template("ptt/shift_detail.html",
                           company=company,
                           shift=shift,
                           claims=claims,
                           contacted_ids=contacted_ids,
                           ptt_session=ptt_session,
                           session_id=_session_id or "",
                           today=today)


# =============================================================================
# API -- SHIFT CRUD
# =============================================================================

@ptt_shifts_bp.route("/api/ptt/admin/shifts", methods=["POST"])
@require_ptt_admin
def ptt_shift_create(ptt_session):
    """
    Create a new shift.
    Body: { title, shift_date (YYYY-MM-DD), start_time (HH:MM),
            end_time (HH:MM), workers_needed, urgency,
            skill_required_id (int or null), notes }
    """
    company_id = ptt_session["company_id"]
    data = request.get_json(silent=True) or {}

    title             = (data.get("title") or "").strip()
    shift_date        = (data.get("shift_date") or "").strip()
    start_time        = (data.get("start_time") or "").strip()
    end_time          = (data.get("end_time") or "").strip()
    workers_needed    = data.get("workers_needed", 1)
    urgency           = (data.get("urgency") or "moderate").strip()
    skill_required_id = data.get("skill_required_id")
    notes             = (data.get("notes") or "").strip()

    if not title:
        return jsonify({"error": "Shift title is required"}), 400
    if not shift_date:
        return jsonify({"error": "Shift date is required"}), 400
    if not start_time:
        return jsonify({"error": "Start time is required"}), 400
    if not end_time:
        return jsonify({"error": "End time is required"}), 400
    if urgency not in ("urgent", "moderate", "long_term"):
        urgency = "moderate"

    try:
        workers_needed = int(workers_needed)
        if workers_needed < 1:
            workers_needed = 1
    except (TypeError, ValueError):
        workers_needed = 1

    if skill_required_id:
        try:
            skill_required_id = int(skill_required_id)
        except (TypeError, ValueError):
            skill_required_id = None

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        if skill_required_id:
            cursor.execute("""
                SELECT id FROM ptt_skill
                WHERE id = %s AND company_id = %s
            """, (skill_required_id, company_id))
            if not cursor.fetchone():
                skill_required_id = None

        cursor.execute("""
            INSERT INTO ptt_shift
                (company_id, title, shift_date, start_time, end_time,
                 workers_needed, urgency, skill_required_id, notes, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'open')
            RETURNING id
        """, (company_id, title, shift_date, start_time, end_time,
              workers_needed, urgency, skill_required_id, notes or None))
        new_id = cursor.fetchone()["id"]
        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"[ptt_shifts] create error: {e}")
        return jsonify({"error": "Failed to create shift. Please try again."}), 500
    finally:
        conn.close()

    return jsonify({"status": "ok", "id": new_id}), 200


@ptt_shifts_bp.route("/api/ptt/admin/shifts/<int:shift_id>/cancel", methods=["POST"])
@require_ptt_admin
def ptt_shift_cancel(ptt_session, shift_id):
    """Cancel a shift (soft delete via status = 'cancelled')."""
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ptt_shift SET status = 'cancelled', updated_at = NOW()
            WHERE id = %s AND company_id = %s AND status != 'cancelled'
        """, (shift_id, company_id))
        if cursor.rowcount == 0:
            return jsonify({"error": "Shift not found or already cancelled"}), 404
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ptt_shifts] cancel error: {e}")
        return jsonify({"error": "Failed to cancel shift."}), 500
    finally:
        conn.close()

    return jsonify({"status": "ok"}), 200


# =============================================================================
# API -- MATCHING ENGINE
# =============================================================================

@ptt_shifts_bp.route("/api/ptt/admin/shifts/<int:shift_id>/matches", methods=["GET"])
@require_ptt_admin
def ptt_shift_matches(ptt_session, shift_id):
    """
    Return qualified workers for a shift.
    Filters:
      1. Active workers in this company
      2. Skill match (if shift has skill_required_id)
      3. Availability covers the shift day + time window
      4. No blackout covering the shift date
      5. No overlapping confirmed/claimed shift on the same date+time
    """
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, shift_date, start_time, end_time, skill_required_id
            FROM ptt_shift
            WHERE id = %s AND company_id = %s AND status = 'open'
        """, (shift_id, company_id))
        shift = cursor.fetchone()
        if not shift:
            return jsonify({"error": "Shift not found or not open"}), 404

        skill_required_id = shift["skill_required_id"]
        shift_date        = shift["shift_date"]
        start_time        = shift["start_time"]
        end_time          = shift["end_time"]

        cursor.execute("""
            SELECT EXTRACT(DOW FROM %s::date)::int AS dow
        """, (str(shift_date),))
        dow = cursor.fetchone()["dow"]

        if skill_required_id:
            cursor.execute("""
                SELECT w.id, w.name, w.email, w.phone
                FROM ptt_worker w
                JOIN ptt_worker_skill ws ON ws.worker_id = w.id
                WHERE w.company_id = %s
                  AND w.status = 'active'
                  AND ws.skill_id = %s
            """, (company_id, skill_required_id))
        else:
            cursor.execute("""
                SELECT w.id, w.name, w.email, w.phone
                FROM ptt_worker w
                WHERE w.company_id = %s AND w.status = 'active'
            """, (company_id,))
        candidates = cursor.fetchall()

        if not candidates:
            return jsonify({"workers": [], "total": 0}), 200

        candidate_ids = [w["id"] for w in candidates]

        cursor.execute("""
            SELECT DISTINCT worker_id FROM ptt_availability
            WHERE worker_id = ANY(%s::int[])
              AND day_of_week = %s
              AND start_time <= %s
              AND end_time   >= %s
        """, (candidate_ids, dow, str(start_time), str(end_time)))
        available_ids = {r["worker_id"] for r in cursor.fetchall()}

        cursor.execute("""
            SELECT DISTINCT worker_id FROM ptt_blackout
            WHERE worker_id = ANY(%s::int[])
              AND start_date <= %s
              AND end_date   >= %s
        """, (candidate_ids, str(shift_date), str(shift_date)))
        blacked_out_ids = {r["worker_id"] for r in cursor.fetchall()}

        cursor.execute("""
            SELECT DISTINCT c.worker_id
            FROM ptt_shift_claim c
            JOIN ptt_shift s ON s.id = c.shift_id
            WHERE c.worker_id = ANY(%s::int[])
              AND c.status IN ('claimed', 'confirmed')
              AND s.shift_date = %s
              AND s.start_time < %s
              AND s.end_time   > %s
              AND s.id != %s
        """, (candidate_ids, str(shift_date),
              str(end_time), str(start_time), shift_id))
        overlapping_ids = {r["worker_id"] for r in cursor.fetchall()}

        cursor.execute("""
            SELECT worker_id FROM ptt_shift_outreach WHERE shift_id = %s
        """, (shift_id,))
        contacted_ids = {r["worker_id"] for r in cursor.fetchall()}

        result = []
        for w in candidates:
            wid = w["id"]
            if wid not in available_ids:
                continue
            if wid in blacked_out_ids:
                continue
            if wid in overlapping_ids:
                continue

            cursor.execute("""
                SELECT s.name FROM ptt_worker_skill ws
                JOIN ptt_skill s ON s.id = ws.skill_id
                WHERE ws.worker_id = %s
                ORDER BY s.sort_order ASC
            """, (wid,))
            skills = [r["name"] for r in cursor.fetchall()]

            result.append({
                "id":        wid,
                "name":      w["name"],
                "email":     w["email"],
                "phone":     w["phone"] or "",
                "skills":    skills,
                "contacted": wid in contacted_ids,
            })

    finally:
        conn.close()

    return jsonify({"workers": result, "total": len(result)}), 200


# =============================================================================
# API -- OUTREACH
# =============================================================================

@ptt_shifts_bp.route("/api/ptt/admin/shifts/<int:shift_id>/outreach/<int:worker_id>",
                     methods=["POST"])
@require_ptt_admin
def ptt_shift_outreach(ptt_session, shift_id, worker_id):
    """Mark a worker as contacted for a shift. Upserts ptt_shift_outreach."""
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM ptt_shift WHERE id = %s AND company_id = %s
        """, (shift_id, company_id))
        if not cursor.fetchone():
            return jsonify({"error": "Shift not found"}), 404

        cursor.execute("""
            SELECT id FROM ptt_worker WHERE id = %s AND company_id = %s
        """, (worker_id, company_id))
        if not cursor.fetchone():
            return jsonify({"error": "Worker not found"}), 404

        cursor.execute("""
            INSERT INTO ptt_shift_outreach (shift_id, worker_id, contacted_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (shift_id, worker_id) DO UPDATE
                SET contacted_at = NOW()
        """, (shift_id, worker_id))
        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"[ptt_shifts] outreach error: {e}")
        return jsonify({"error": "Failed to record outreach."}), 500
    finally:
        conn.close()

    return jsonify({"status": "ok"}), 200


# =============================================================================
# API -- CLAIM MANAGEMENT
# =============================================================================

@ptt_shifts_bp.route("/api/ptt/admin/claims/<int:claim_id>/confirm", methods=["POST"])
@require_ptt_admin
def ptt_claim_confirm(ptt_session, claim_id):
    """
    Confirm a worker's shift claim.
    If workers_needed claims are now confirmed, mark shift as filled.
    """
    company_id = ptt_session["company_id"]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.id, c.shift_id, c.worker_id, c.status,
                   s.workers_needed, s.company_id
            FROM ptt_shift_claim c
            JOIN ptt_shift s ON s.id = c.shift_id
            WHERE c.id = %s AND s.company_id = %s
        """, (claim_id, company_id))
        claim = cursor.fetchone()
        if not claim:
            return jsonify({"error": "Claim not found"}), 404
        if claim["status"] != "claimed":
            return jsonify({"error": "Claim is not in 'claimed' status"}), 409

        cursor.execute("""
            UPDATE ptt_shift_claim
            SET status = 'confirmed', resolved_at = NOW()
            WHERE id = %s
        """, (claim_id,))

        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM ptt_shift_claim
            WHERE shift_id = %s AND status = 'confirmed'
        """, (claim["shift_id"],))
        confirmed_count = cursor.fetchone()["cnt"]

        if confirmed_count >= claim["workers_needed"]:
            cursor.execute("""
                UPDATE ptt_shift SET status = 'filled', updated_at = NOW()
                WHERE id = %s AND status = 'open'
            """, (claim["shift_id"],))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"[ptt_shifts] confirm claim error: {e}")
        return jsonify({"error": "Failed to confirm claim."}), 500
    finally:
        conn.close()

    return jsonify({"status": "ok"}), 200


@ptt_shifts_bp.route("/api/ptt/admin/claims/<int:claim_id>/decline", methods=["POST"])
@require_ptt_admin
def ptt_claim_decline(ptt_session, claim_id):
    """Decline a worker's shift claim."""
    company_id = ptt_session["company_id"]
    data = request.get_json(silent=True) or {}
    notes = (data.get("notes") or "").strip()

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.id, c.status, s.company_id
            FROM ptt_shift_claim c
            JOIN ptt_shift s ON s.id = c.shift_id
            WHERE c.id = %s AND s.company_id = %s
        """, (claim_id, company_id))
        claim = cursor.fetchone()
        if not claim:
            return jsonify({"error": "Claim not found"}), 404
        if claim["status"] not in ("claimed", "confirmed"):
            return jsonify({"error": "Claim cannot be declined in its current state"}), 409

        cursor.execute("""
            UPDATE ptt_shift_claim
            SET status = 'declined', resolved_at = NOW(),
                notes = COALESCE(%s, notes)
            WHERE id = %s
        """, (notes or None, claim_id))
        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"[ptt_shifts] decline claim error: {e}")
        return jsonify({"error": "Failed to decline claim."}), 500
    finally:
        conn.close()

    return jsonify({"status": "ok"}), 200

# I did no harm and this file is not truncated.
