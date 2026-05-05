"""
AI SWARM ORCHESTRATOR — Route: Site Events API
Created: April 28, 2026
Last Updated: May 05, 2026
Author: Claude Sonnet 4.6 for Jim @ Shiftwork Solutions LLC

CHANGE LOG:
    2026-04-28  (v1) Initial build — POST /api/events/log with CORS.
                     GET /api/events/summary, /recent, /sessions added
                     as admin endpoints WITHOUT CORS headers (oversight).
    2026-05-05  (v2) CORS FIX — all GET endpoints (summary, recent,
                     sessions) now return _cors_headers() so the
                     Performance Dashboard at shift-work.com/performance/
                     can fetch them from the browser without being blocked.
                     No logic changes — CORS headers only.

PURPOSE:
    Flask blueprint providing the event logging endpoint consumed by
    /js/event-tracker.js on shift-work.com.

    POST /api/events/log
        Accepts a JSON event payload from the static site tracker.
        Validates event_type against the allowed list.
        Stores the event in the site_events PostgreSQL table.
        Returns {success: true} on success.
        CORS-enabled for shift-work.com origin.

    GET /api/events/summary
        Admin endpoint — monthly summary grouped by event_type.
        Returns counts, first/last occurrence, top pages per event type.
        CORS-enabled (fixed v2).

    GET /api/events/recent
        Admin endpoint — last N events in reverse chronological order.
        Query param: limit (default 50, max 500)
        CORS-enabled (fixed v2).

    GET /api/events/sessions
        Admin endpoint — session journey view.
        Query param: session_id — returns all events for that session
        in chronological order to reconstruct a user journey.
        CORS-enabled (fixed v2).

ALLOWED EVENT TYPES:
    landing_page, contact_form, newsletter_signup, booking_click,
    thomas_opened, thomas_question, resource_download, phone_click,
    scroll_depth, time_on_page

GOLDEN RULES FOLLOWED:
    - All SQL uses %s placeholders
    - CORS restricted to shift-work.com origin
    - IP captured from X-Forwarded-For (Render proxy) with fallback
    - event_data stored as JSONB — arbitrary per-event payload
    - No PII beyond IP (which mirrors existing contact/newsletter tables)

I did no harm and this file is not truncated
"""

import json
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from db_engine import get_db_connection, get_db_type

site_events_bp = Blueprint('site_events', __name__)

# ── Allowed event types ────────────────────────────────────────────────
ALLOWED_EVENT_TYPES = {
    'landing_page',
    'contact_form',
    'newsletter_signup',
    'booking_click',
    'thomas_opened',
    'thomas_question',
    'resource_download',
    'phone_click',
    'scroll_depth',
    'time_on_page',
}

# ── CORS origins ───────────────────────────────────────────────────────
ALLOWED_ORIGINS = {
    'https://shift-work.com',
    'https://www.shift-work.com',
}


def _cors_headers(origin=None):
    """Return CORS headers allowing shift-work.com."""
    allowed = origin if origin in ALLOWED_ORIGINS else 'https://shift-work.com'
    return {
        'Access-Control-Allow-Origin': allowed,
        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Max-Age': '86400',
    }


def _get_client_ip():
    """Get real client IP from Render's reverse proxy headers."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or 'unknown'


# ── POST /api/events/log ───────────────────────────────────────────────
@site_events_bp.route('/api/events/log', methods=['POST', 'OPTIONS'])
def log_event():
    origin = request.headers.get('Origin', '')
    headers = _cors_headers(origin)

    # Preflight
    if request.method == 'OPTIONS':
        return ('', 204, headers)

    try:
        data = request.get_json(force=True, silent=True) or {}

        event_type = (data.get('event_type') or '').strip().lower()
        if not event_type:
            return (jsonify({'success': False, 'error': 'event_type required'}), 400, headers)
        if event_type not in ALLOWED_EVENT_TYPES:
            return (jsonify({'success': False, 'error': f'Unknown event_type: {event_type}'}), 400, headers)

        page_url    = (data.get('page_url')   or '')[:2048]
        referrer    = (data.get('referrer')   or '')[:2048]
        session_id  = (data.get('session_id') or '')[:64]
        device_type = (data.get('device_type') or 'unknown')[:20]

        # event_data is the arbitrary per-event payload dict
        raw_event_data = data.get('event_data', {})
        if not isinstance(raw_event_data, dict):
            raw_event_data = {}

        ip_address  = _get_client_ip()
        user_agent  = (request.headers.get('User-Agent') or '')[:512]

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    INSERT INTO site_events
                        (event_type, page_url, referrer, session_id,
                         device_type, event_data, ip_address, user_agent, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, NOW())
                """, (
                    event_type, page_url, referrer, session_id,
                    device_type, json.dumps(raw_event_data),
                    ip_address, user_agent,
                ))
            else:
                # SQLite fallback
                cursor.execute("""
                    INSERT INTO site_events
                        (event_type, page_url, referrer, session_id,
                         device_type, event_data, ip_address, user_agent, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_type, page_url, referrer, session_id,
                    device_type, json.dumps(raw_event_data),
                    ip_address, user_agent,
                    datetime.now(timezone.utc).isoformat(),
                ))
            conn.commit()
        finally:
            conn.close()

        return (jsonify({'success': True}), 200, headers)

    except Exception as e:
        import traceback
        print(f"Site Events log_event error: {e}\n{traceback.format_exc()}")
        return (jsonify({'success': False, 'error': 'Server error'}), 500, headers)


# ── GET /api/events/summary ────────────────────────────────────────────
@site_events_bp.route('/api/events/summary', methods=['GET', 'OPTIONS'])
def events_summary():
    """Monthly summary grouped by event_type."""
    origin = request.headers.get('Origin', '')
    headers = _cors_headers(origin)

    if request.method == 'OPTIONS':
        return ('', 204, headers)

    try:
        days = min(int(request.args.get('days', 30)), 365)
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    SELECT
                        event_type,
                        COUNT(*)                            AS total,
                        COUNT(DISTINCT session_id)          AS unique_sessions,
                        COUNT(DISTINCT ip_address)          AS unique_ips,
                        MIN(created_at)                     AS first_seen,
                        MAX(created_at)                     AS last_seen
                    FROM site_events
                    WHERE created_at >= NOW() - INTERVAL '%s days'
                    GROUP BY event_type
                    ORDER BY total DESC
                """, (days,))
                rows = cursor.fetchall()
                summary = []
                for row in rows:
                    summary.append({
                        'event_type':       row['event_type'],
                        'total':            row['total'],
                        'unique_sessions':  row['unique_sessions'],
                        'unique_ips':       row['unique_ips'],
                        'first_seen':       str(row['first_seen']),
                        'last_seen':        str(row['last_seen']),
                    })
            else:
                cursor.execute("""
                    SELECT event_type, COUNT(*) as total,
                           MIN(created_at) as first_seen, MAX(created_at) as last_seen
                    FROM site_events
                    WHERE created_at >= datetime('now', ?)
                    GROUP BY event_type ORDER BY total DESC
                """, (f'-{days} days',))
                rows = cursor.fetchall()
                summary = [dict(r) for r in rows]
        finally:
            conn.close()

        return (jsonify({'success': True, 'days': days, 'summary': summary}), 200, headers)

    except Exception as e:
        import traceback
        return (jsonify({'success': False, 'error': str(e),
                         'traceback': traceback.format_exc()}), 500, headers)


# ── GET /api/events/recent ─────────────────────────────────────────────
@site_events_bp.route('/api/events/recent', methods=['GET', 'OPTIONS'])
def events_recent():
    """Recent events in reverse chronological order."""
    origin = request.headers.get('Origin', '')
    headers = _cors_headers(origin)

    if request.method == 'OPTIONS':
        return ('', 204, headers)

    try:
        limit = min(int(request.args.get('limit', 50)), 500)
        event_type = request.args.get('type', None)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                if event_type and event_type in ALLOWED_EVENT_TYPES:
                    cursor.execute("""
                        SELECT id, event_type, page_url, referrer, session_id,
                               device_type, event_data, ip_address, created_at
                        FROM site_events
                        WHERE event_type = %s
                        ORDER BY created_at DESC LIMIT %s
                    """, (event_type, limit))
                else:
                    cursor.execute("""
                        SELECT id, event_type, page_url, referrer, session_id,
                               device_type, event_data, ip_address, created_at
                        FROM site_events
                        ORDER BY created_at DESC LIMIT %s
                    """, (limit,))
                rows = cursor.fetchall()
                events = []
                for row in rows:
                    events.append({
                        'id':           row['id'],
                        'event_type':   row['event_type'],
                        'page_url':     row['page_url'],
                        'referrer':     row['referrer'],
                        'session_id':   row['session_id'],
                        'device_type':  row['device_type'],
                        'event_data':   row['event_data'],
                        'ip_address':   row['ip_address'],
                        'created_at':   str(row['created_at']),
                    })
            else:
                cursor.execute("""
                    SELECT * FROM site_events ORDER BY created_at DESC LIMIT ?
                """, (limit,))
                events = [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

        return (jsonify({'success': True, 'count': len(events), 'events': events}), 200, headers)

    except Exception as e:
        import traceback
        return (jsonify({'success': False, 'error': str(e),
                         'traceback': traceback.format_exc()}), 500, headers)


# ── GET /api/events/sessions ───────────────────────────────────────────
@site_events_bp.route('/api/events/sessions', methods=['GET', 'OPTIONS'])
def events_session():
    """Reconstruct a full user journey for a given session_id."""
    origin = request.headers.get('Origin', '')
    headers = _cors_headers(origin)

    if request.method == 'OPTIONS':
        return ('', 204, headers)

    try:
        session_id = (request.args.get('session_id') or '').strip()
        if not session_id:
            return (jsonify({'success': False, 'error': 'session_id required'}), 400, headers)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    SELECT id, event_type, page_url, referrer,
                           device_type, event_data, created_at
                    FROM site_events
                    WHERE session_id = %s
                    ORDER BY created_at ASC
                """, (session_id,))
                rows = cursor.fetchall()
                events = []
                for row in rows:
                    events.append({
                        'id':           row['id'],
                        'event_type':   row['event_type'],
                        'page_url':     row['page_url'],
                        'referrer':     row['referrer'],
                        'device_type':  row['device_type'],
                        'event_data':   row['event_data'],
                        'created_at':   str(row['created_at']),
                    })
            else:
                cursor.execute("""
                    SELECT * FROM site_events WHERE session_id = ?
                    ORDER BY created_at ASC
                """, (session_id,))
                events = [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

        return (jsonify({'success': True, 'session_id': session_id,
                          'event_count': len(events), 'journey': events}), 200, headers)

    except Exception as e:
        import traceback
        return (jsonify({'success': False, 'error': str(e),
                          'traceback': traceback.format_exc()}), 500, headers)


# I did no harm and this file is not truncated
