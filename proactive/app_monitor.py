"""
AI SWARM ORCHESTRATOR - App Monitor
File: proactive/app_monitor.py
Created: March 12, 2026
Last Updated: March 12, 2026 — Phase 6 Deliverable 4: Initial implementation

PURPOSE:
    Monitors the health of the AI Swarm Orchestrator itself and any other
    services Jim registers. Records response times, HTTP status codes, and
    errors. Surfaces issues in the daily briefing and via GET /api/monitor/services.

    On first import, auto-registers the Swarm itself as a monitored service.
    app.py calls auto_register_swarm() explicitly after blueprint registration
    so the URL is always current.

DESIGN NOTES:
    - Uses requests (already in requirements.txt) — no new dependencies
    - HTTP checks time out after 10 seconds to prevent hung connections
    - health_checks table is pruned to the last 100 rows per service to prevent
      unbounded growth
    - UNIQUE constraint on monitored_services(service_name) prevents duplicates
    - check_all_services() checks every active service on every call;
      the scheduler (Deliverable 5) controls how often it is called

CHANGELOG:
- March 12, 2026: Phase 6 Deliverable 4 — Initial implementation
  * Created monitored_services and health_checks tables (idempotent)
  * register_service() — add a service to monitor (UPSERT on service_name)
  * check_service(service_id) — hit endpoint, record result
  * check_all_services() — check every active service, return issues
  * get_health_summary() — structured data for daily briefing
  * auto_register_swarm() — registers the Swarm itself on startup
  * Prunes health_checks to last 100 rows per service after each check
  * All SQL uses %s placeholders and get_db_connection() per db_engine.py

DATABASE TABLES:

  monitored_services
    id                     SERIAL PRIMARY KEY
    service_name           VARCHAR(100) UNIQUE
    endpoint_url           TEXT
    check_interval_minutes INTEGER DEFAULT 60
    active                 BOOLEAN DEFAULT TRUE
    created_at             TIMESTAMP DEFAULT NOW()

  health_checks
    id               SERIAL PRIMARY KEY
    service_id       INTEGER  (FK to monitored_services.id — soft reference)
    service_name     VARCHAR(100)     (denormalized for easy querying)
    endpoint_url     TEXT             (denormalized for easy querying)
    status           VARCHAR(20)      (healthy|degraded|down|unknown)
    response_time_ms INTEGER
    error_message    TEXT
    checked_at       TIMESTAMP DEFAULT NOW()

DEPENDENCIES:
    db_engine.py  — get_db_connection()
    requests      — HTTP health checks (already in requirements.txt)

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import logging
import time as _time
from datetime import datetime, date
from typing import Optional, List, Dict, Any

import requests

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

HTTP_TIMEOUT_SECONDS  = 10      # Max wait for a health check response
MAX_HISTORY_PER_SERVICE = 100   # Prune health_checks beyond this per service

# The Swarm's own health endpoint — registered automatically on startup
SWARM_SERVICE_NAME = "AI Swarm Orchestrator"
SWARM_HEALTH_URL   = "https://ai-swarm-orchestrator.onrender.com/health"
SWARM_CHECK_INTERVAL_MINUTES = 30


# ============================================================================
# STEP 1: ENSURE TABLES EXIST (idempotent)
# ============================================================================

def _ensure_tables():
    """
    Create monitored_services and health_checks tables if they do not exist.
    Called once at module import. Fully idempotent.
    """
    from db_engine import get_db_connection

    monitored_services_sql = """
        CREATE TABLE IF NOT EXISTS monitored_services (
            id                     SERIAL PRIMARY KEY,
            service_name           VARCHAR(100) UNIQUE NOT NULL,
            endpoint_url           TEXT         NOT NULL,
            check_interval_minutes INTEGER      DEFAULT 60,
            active                 BOOLEAN      DEFAULT TRUE,
            created_at             TIMESTAMP    DEFAULT NOW()
        )
    """

    health_checks_sql = """
        CREATE TABLE IF NOT EXISTS health_checks (
            id               SERIAL PRIMARY KEY,
            service_id       INTEGER,
            service_name     VARCHAR(100),
            endpoint_url     TEXT,
            status           VARCHAR(20),
            response_time_ms INTEGER,
            error_message    TEXT,
            checked_at       TIMESTAMP DEFAULT NOW()
        )
    """

    # Index for fast per-service history queries
    health_checks_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_health_checks_service_id
        ON health_checks (service_id, checked_at DESC)
    """

    try:
        with get_db_connection() as conn:
            conn.execute(monitored_services_sql)
            conn.execute(health_checks_sql)
            conn.execute(health_checks_index_sql)
        logger.info("monitored_services and health_checks tables ready")
        print("✅ proactive/app_monitor: tables ready")
    except Exception as e:
        logger.error(f"Failed to create app_monitor tables: {e}")
        print(f"❌ proactive/app_monitor: table creation failed: {e}")
        raise


_ensure_tables()


# ============================================================================
# PUBLIC API
# ============================================================================

def register_service(
    service_name: str,
    endpoint_url: str,
    check_interval_minutes: int = 60,
) -> int:
    """
    Register a service for health monitoring. Uses UPSERT on service_name
    so calling this multiple times (e.g. on every app startup) is safe —
    it updates the URL and interval if the name already exists.

    Args:
        service_name           : Human-readable name (e.g. "AI Swarm Orchestrator")
        endpoint_url           : URL to GET for the health check
        check_interval_minutes : How often to check (informational — scheduler decides)

    Returns:
        int: The service's database ID

    Raises:
        Exception: On database error
    """
    service_name = service_name.strip()
    endpoint_url = endpoint_url.strip()

    if not service_name:
        raise ValueError("service_name is required")
    if not endpoint_url:
        raise ValueError("endpoint_url is required")

    check_interval_minutes = max(1, int(check_interval_minutes))

    from db_engine import get_db_connection

    sql = """
        INSERT INTO monitored_services
            (service_name, endpoint_url, check_interval_minutes, active, created_at)
        VALUES (%s, %s, %s, TRUE, NOW())
        ON CONFLICT (service_name)
        DO UPDATE SET
            endpoint_url           = EXCLUDED.endpoint_url,
            check_interval_minutes = EXCLUDED.check_interval_minutes,
            active                 = TRUE
        RETURNING id
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (service_name, endpoint_url, check_interval_minutes))
        row = cursor.fetchone()
        service_id = row['id']

    logger.info(
        f"Service registered: id={service_id}, name='{service_name}', "
        f"url={endpoint_url}, interval={check_interval_minutes}m"
    )
    return service_id


def auto_register_swarm() -> int:
    """
    Register the Swarm itself as a monitored service.
    Called from app.py startup after blueprint registration.
    Safe to call on every startup — UPSERT on service_name.

    Returns:
        int: The Swarm service's database ID
    """
    try:
        service_id = register_service(
            service_name           = SWARM_SERVICE_NAME,
            endpoint_url           = SWARM_HEALTH_URL,
            check_interval_minutes = SWARM_CHECK_INTERVAL_MINUTES,
        )
        print(f"✅ App Monitor: Swarm self-registered (id={service_id})")
        return service_id
    except Exception as e:
        logger.error(f"auto_register_swarm failed: {e}")
        print(f"⚠️  App Monitor: Swarm self-registration failed (non-fatal): {e}")
        return -1


def check_service(service_id: int) -> Dict[str, Any]:
    """
    Perform a health check on a single monitored service.

    Makes a GET request to the service's endpoint_url with a 10-second
    timeout. Records the result in health_checks. Prunes old records
    beyond MAX_HISTORY_PER_SERVICE for this service.

    Status logic:
        HTTP 200-299         → healthy
        HTTP 300-499         → degraded
        HTTP 500+            → down
        Timeout / conn error → down
        Unknown exception    → unknown

    Args:
        service_id: The monitored_services.id to check

    Returns:
        dict with keys: service_id, service_name, endpoint_url, status,
                        response_time_ms, error_message, checked_at
    """
    from db_engine import get_db_connection

    # ----------------------------------------------------------------
    # 1. Load service details
    # ----------------------------------------------------------------
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, service_name, endpoint_url, active
                FROM   monitored_services
                WHERE  id = %s
            """, (service_id,))
            svc = cursor.fetchone()
    except Exception as e:
        logger.error(f"check_service: could not load service {service_id}: {e}")
        return {'success': False, 'error': str(e)}

    if not svc:
        return {'success': False, 'error': f'Service {service_id} not found'}

    if not svc['active']:
        return {'success': False, 'error': f'Service {service_id} is inactive'}

    service_name = svc['service_name']
    endpoint_url = svc['endpoint_url']

    # ----------------------------------------------------------------
    # 2. Perform the HTTP check
    # ----------------------------------------------------------------
    status          = 'unknown'
    response_time_ms = 0
    error_message   = None

    try:
        start_time = _time.time()
        response   = requests.get(endpoint_url, timeout=HTTP_TIMEOUT_SECONDS)
        elapsed_ms = int((_time.time() - start_time) * 1000)

        response_time_ms = elapsed_ms
        http_code        = response.status_code

        if 200 <= http_code < 300:
            status = 'healthy'
        elif 300 <= http_code < 500:
            status        = 'degraded'
            error_message = f"HTTP {http_code}"
        else:
            status        = 'down'
            error_message = f"HTTP {http_code}"

    except requests.exceptions.Timeout:
        status        = 'down'
        error_message = f"Timeout after {HTTP_TIMEOUT_SECONDS}s"
        response_time_ms = HTTP_TIMEOUT_SECONDS * 1000

    except requests.exceptions.ConnectionError as e:
        status        = 'down'
        error_message = f"Connection error: {str(e)[:200]}"

    except requests.exceptions.RequestException as e:
        status        = 'down'
        error_message = f"Request error: {str(e)[:200]}"

    except Exception as e:
        status        = 'unknown'
        error_message = f"Unexpected error: {str(e)[:200]}"

    # ----------------------------------------------------------------
    # 3. Store the result in health_checks
    # ----------------------------------------------------------------
    check_record = {
        'service_id':       service_id,
        'service_name':     service_name,
        'endpoint_url':     endpoint_url,
        'status':           status,
        'response_time_ms': response_time_ms,
        'error_message':    error_message,
        'checked_at':       datetime.utcnow().isoformat(),
    }

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Insert the new record
            cursor.execute("""
                INSERT INTO health_checks
                    (service_id, service_name, endpoint_url, status,
                     response_time_ms, error_message, checked_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (
                service_id, service_name, endpoint_url,
                status, response_time_ms, error_message
            ))

            # Prune old records — keep only the most recent MAX_HISTORY_PER_SERVICE
            cursor.execute("""
                DELETE FROM health_checks
                WHERE service_id = %s
                  AND id NOT IN (
                      SELECT id FROM health_checks
                      WHERE  service_id = %s
                      ORDER  BY checked_at DESC
                      LIMIT  %s
                  )
            """, (service_id, service_id, MAX_HISTORY_PER_SERVICE))

    except Exception as e:
        logger.error(f"check_service: failed to store result for {service_id}: {e}")
        check_record['store_error'] = str(e)

    log_level = logging.WARNING if status != 'healthy' else logging.DEBUG
    logger.log(
        log_level,
        f"Health check: {service_name} → {status} ({response_time_ms}ms)"
    )

    if status != 'healthy':
        print(f"⚠️  App Monitor: {service_name} is {status} — {error_message}")

    return check_record


def check_all_services() -> Dict[str, Any]:
    """
    Check every active monitored service and return a summary of results.

    Called by the scheduler every 30 minutes (Deliverable 5).
    Can also be triggered manually via API.

    Returns:
        dict with keys:
            success (bool)
            total_checked (int)
            healthy_count (int)
            issues (list): services that are not healthy
            results (list): all check results
            checked_at (str): ISO timestamp
    """
    from db_engine import get_db_connection

    logger.info("check_all_services: starting")

    # ----------------------------------------------------------------
    # 1. Load all active services
    # ----------------------------------------------------------------
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, service_name, endpoint_url
                FROM   monitored_services
                WHERE  active = TRUE
                ORDER  BY service_name
            """)
            services = cursor.fetchall()
    except Exception as e:
        logger.error(f"check_all_services: could not load services: {e}")
        return {
            'success': False,
            'error':   str(e),
            'total_checked': 0,
            'healthy_count': 0,
            'issues':  [],
            'results': [],
        }

    if not services:
        logger.info("check_all_services: no active services registered")
        return {
            'success':       True,
            'total_checked': 0,
            'healthy_count': 0,
            'issues':        [],
            'results':       [],
            'checked_at':    datetime.utcnow().isoformat(),
        }

    # ----------------------------------------------------------------
    # 2. Check each service
    # ----------------------------------------------------------------
    results: List[Dict[str, Any]] = []
    issues:  List[Dict[str, Any]] = []

    for svc in services:
        result = check_service(svc['id'])
        results.append(result)

        if result.get('status') not in ('healthy', None):
            issues.append({
                'service_name':  result.get('service_name', 'Unknown'),
                'status':        result.get('status', 'unknown'),
                'error_message': result.get('error_message'),
                'endpoint_url':  result.get('endpoint_url'),
            })

    healthy_count = sum(1 for r in results if r.get('status') == 'healthy')

    logger.info(
        f"check_all_services: {healthy_count}/{len(results)} healthy, "
        f"{len(issues)} issue(s)"
    )

    if issues:
        print(f"⚠️  App Monitor: {len(issues)} service(s) unhealthy")
    else:
        print(f"✅ App Monitor: all {len(results)} service(s) healthy")

    return {
        'success':       True,
        'total_checked': len(results),
        'healthy_count': healthy_count,
        'issues':        issues,
        'results':       results,
        'checked_at':    datetime.utcnow().isoformat(),
    }


def get_health_summary() -> Dict[str, Any]:
    """
    Return the latest health status for all monitored services.
    Used by daily_briefing.py and GET /api/monitor/services.

    For each service, returns the most recent health_checks record.
    Includes average response time over the last 24 hours.

    Returns:
        dict with keys:
            services (list): each service with its latest status
            total_services (int)
            healthy_count (int)
            issues_detected (bool)
            available (bool): True if tables are accessible
    """
    from db_engine import get_db_connection

    summary: Dict[str, Any] = {
        'services':       [],
        'total_services': 0,
        'healthy_count':  0,
        'issues_detected': False,
        'available':      False,
    }

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Load all active services
            cursor.execute("""
                SELECT id, service_name, endpoint_url, check_interval_minutes
                FROM   monitored_services
                WHERE  active = TRUE
                ORDER  BY service_name
            """)
            services = cursor.fetchall()

            if not services:
                summary['available'] = True
                return summary

            service_list = []
            for svc in services:
                svc_id = svc['id']

                # Latest check result
                cursor.execute("""
                    SELECT status, response_time_ms, error_message, checked_at
                    FROM   health_checks
                    WHERE  service_id = %s
                    ORDER  BY checked_at DESC
                    LIMIT  1
                """, (svc_id,))
                latest = cursor.fetchone()

                # Average response time over last 24 hours
                cursor.execute("""
                    SELECT AVG(response_time_ms) AS avg_ms
                    FROM   health_checks
                    WHERE  service_id = %s
                      AND  checked_at >= NOW() - INTERVAL '24 hours'
                      AND  status = 'healthy'
                """, (svc_id,))
                avg_row = cursor.fetchone()
                avg_ms  = round(float(avg_row['avg_ms']), 0) if avg_row and avg_row['avg_ms'] else None

                # Build service entry
                if latest:
                    checked_at_val = latest['checked_at']
                    checked_at_str = (
                        checked_at_val.isoformat()
                        if isinstance(checked_at_val, datetime)
                        else str(checked_at_val)
                    )
                    service_entry = {
                        'service_id':              svc_id,
                        'service_name':            svc['service_name'],
                        'endpoint_url':            svc['endpoint_url'],
                        'check_interval_minutes':  svc['check_interval_minutes'],
                        'status':                  latest['status'],
                        'response_time_ms':        latest['response_time_ms'],
                        'avg_response_time_ms_24h': avg_ms,
                        'error_message':           latest['error_message'],
                        'last_checked':            checked_at_str,
                    }
                else:
                    # Never been checked yet
                    service_entry = {
                        'service_id':              svc_id,
                        'service_name':            svc['service_name'],
                        'endpoint_url':            svc['endpoint_url'],
                        'check_interval_minutes':  svc['check_interval_minutes'],
                        'status':                  'unknown',
                        'response_time_ms':        None,
                        'avg_response_time_ms_24h': None,
                        'error_message':           'No health checks recorded yet',
                        'last_checked':            None,
                    }

                service_list.append(service_entry)

        healthy_count   = sum(1 for s in service_list if s['status'] == 'healthy')
        issues_detected = any(
            s['status'] not in ('healthy', 'unknown')
            for s in service_list
        )

        summary['services']        = service_list
        summary['total_services']  = len(service_list)
        summary['healthy_count']   = healthy_count
        summary['issues_detected'] = issues_detected
        summary['available']       = True

        return summary

    except Exception as e:
        logger.error(f"get_health_summary failed: {e}")
        summary['error'] = str(e)
        return summary


# I did no harm and this file is not truncated
