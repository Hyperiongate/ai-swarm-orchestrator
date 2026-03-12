"""
AI SWARM ORCHESTRATOR - Daily Briefing Generator
File: proactive/daily_briefing.py
Created: March 12, 2026
Last Updated: March 12, 2026 — Phase 6 Deliverable 2: Initial implementation

PURPOSE:
    Assembles a daily morning briefing from all proactive data sources and
    stores it in the daily_briefings PostgreSQL table. Jim sees this the
    moment he opens the Swarm — it is the first thing on the page.

    Data sources assembled:
        - Task summary + top priority tasks (from proactive/task_manager.py)
        - Memory statistics (from memory/memory_store.py)
        - Routing learning insights (from intelligence/routing_optimizer.py)

    Lead scanner and app monitor data will be incorporated in later deliverables
    once those modules exist. The briefing degrades gracefully — if any source
    fails, the briefing is still generated from whatever data is available.

CHANGELOG:
- March 12, 2026: Phase 6 Deliverable 2 — Initial implementation
  * Created daily_briefings table (idempotent migration on import)
  * generate_daily_briefing() — gathers data, calls Sonnet, stores result
  * get_latest_briefing() — returns most recent stored briefing
  * get_briefing_for_date(date_str) — returns briefing for a specific date
  * get_briefing_history(days) — returns last N days of briefings
  * All data sources wrapped in try/except — one failing source never
    prevents the briefing from generating
  * UPSERT on briefing_date — regenerating today overwrites cleanly
  * All SQL uses %s placeholders and get_db_connection() per db_engine.py

DATABASE TABLE: daily_briefings
    id             SERIAL PRIMARY KEY
    briefing_date  DATE UNIQUE            — one briefing per calendar day
    content        TEXT                   — the full briefing text for Jim
    data_summary   JSONB                  — structured data used to build it
    generated_at   TIMESTAMP DEFAULT NOW()

DEPENDENCIES:
    proactive/task_manager.py           — get_task_summary(), get_pending_tasks()
    memory/memory_store.py              — get_memory_stats()
    intelligence/routing_optimizer.py   — get_routing_insights()
    db_engine.py                        — get_db_connection()
    config.py                           — ANTHROPIC_API_KEY, CLAUDE_SONNET_MODEL

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


# ============================================================================
# STEP 1: ENSURE TABLE EXISTS (idempotent)
# ============================================================================

def _ensure_table():
    """
    Create daily_briefings table if it does not already exist.
    Called once at module import. Fully idempotent.
    """
    from db_engine import get_db_connection

    sql = """
        CREATE TABLE IF NOT EXISTS daily_briefings (
            id            SERIAL PRIMARY KEY,
            briefing_date DATE        UNIQUE NOT NULL,
            content       TEXT,
            data_summary  JSONB,
            generated_at  TIMESTAMP   DEFAULT NOW()
        )
    """
    try:
        with get_db_connection() as conn:
            conn.execute(sql)
        logger.info("daily_briefings table ready")
        print("✅ proactive/daily_briefing: daily_briefings table ready")
    except Exception as e:
        logger.error(f"Failed to create daily_briefings table: {e}")
        print(f"❌ proactive/daily_briefing: table creation failed: {e}")
        raise


_ensure_table()


# ============================================================================
# DATA GATHERING — each source isolated in its own try/except
# ============================================================================

def _gather_task_data() -> Dict[str, Any]:
    """
    Pull task summary and top-priority tasks from task_manager.
    Returns empty structure on any failure — never raises.
    """
    result = {
        'summary': {},
        'critical_tasks': [],
        'high_tasks': [],
        'available': False,
    }
    try:
        from proactive.task_manager import get_task_summary, get_pending_tasks

        result['summary']        = get_task_summary()
        result['critical_tasks'] = get_pending_tasks(limit=10, priority='critical')
        result['high_tasks']     = get_pending_tasks(limit=5,  priority='high')
        result['available']      = True

    except Exception as e:
        logger.warning(f"_gather_task_data failed (non-fatal): {e}")
        result['error'] = str(e)

    return result


def _gather_memory_data() -> Dict[str, Any]:
    """
    Pull memory statistics from memory_store.
    Returns empty structure on any failure — never raises.
    """
    result = {'stats': {}, 'available': False}
    try:
        from memory.memory_store import get_memory_stats
        result['stats']     = get_memory_stats()
        result['available'] = True
    except Exception as e:
        logger.warning(f"_gather_memory_data failed (non-fatal): {e}")
        result['error'] = str(e)
    return result


def _gather_learning_data() -> Dict[str, Any]:
    """
    Pull routing insights from routing_optimizer.
    Returns empty structure on any failure — never raises.
    """
    result = {'insights': '', 'available': False}
    try:
        from intelligence.routing_optimizer import get_routing_insights
        result['insights']  = get_routing_insights()
        result['available'] = True
    except Exception as e:
        logger.warning(f"_gather_learning_data failed (non-fatal): {e}")
        result['error'] = str(e)
    return result


def _gather_lead_data() -> Dict[str, Any]:
    """
    Pull new lead data from lead_scanner (Phase 6 Deliverable 3).
    Returns graceful empty structure until lead_scanner module exists.
    """
    result = {'new_leads': [], 'lead_count': 0, 'available': False}
    try:
        from proactive.lead_scanner import get_new_leads, get_lead_summary
        result['new_leads']   = get_new_leads(limit=5)
        result['lead_count']  = len(result['new_leads'])
        result['available']   = True
    except ImportError:
        # lead_scanner not yet deployed — expected until Deliverable 3
        pass
    except Exception as e:
        logger.warning(f"_gather_lead_data failed (non-fatal): {e}")
        result['error'] = str(e)
    return result


def _gather_health_data() -> Dict[str, Any]:
    """
    Pull service health data from app_monitor (Phase 6 Deliverable 4).
    Returns graceful empty structure until app_monitor module exists.
    """
    result = {'health_summary': {}, 'available': False}
    try:
        from proactive.app_monitor import get_health_summary
        result['health_summary'] = get_health_summary()
        result['available']      = True
    except ImportError:
        # app_monitor not yet deployed — expected until Deliverable 4
        pass
    except Exception as e:
        logger.warning(f"_gather_health_data failed (non-fatal): {e}")
        result['error'] = str(e)
    return result


# ============================================================================
# PROMPT FORMATTERS — convert gathered data into readable text for Sonnet
# ============================================================================

def _format_task_section(task_data: Dict[str, Any]) -> str:
    """Format task data into a text block for the Sonnet prompt."""
    if not task_data.get('available'):
        return "Task data unavailable."

    summary = task_data.get('summary', {})
    critical = task_data.get('critical_tasks', [])
    high     = task_data.get('high_tasks', [])

    lines = []

    total   = summary.get('total_pending', 0)
    overdue = summary.get('overdue_count', 0)
    done_today = summary.get('completed_today', 0)
    done_week  = summary.get('completed_this_week', 0)

    lines.append(f"Total pending tasks: {total}")
    if overdue:
        lines.append(f"⚠️  OVERDUE: {overdue} task(s) past their due date")
    lines.append(f"Completed today: {done_today}  |  Completed this week: {done_week}")

    by_priority = summary.get('by_priority', {})
    priority_parts = []
    for p in ('critical', 'high', 'medium', 'low'):
        cnt = by_priority.get(p, 0)
        if cnt:
            priority_parts.append(f"{cnt} {p}")
    if priority_parts:
        lines.append("Priority breakdown: " + ", ".join(priority_parts))

    if critical:
        lines.append("\nCRITICAL TASKS (need attention today):")
        for t in critical:
            proj = f" [{t['project_name']}]" if t.get('project_name') else ""
            due  = f" — due {t['due_date']}" if t.get('due_date') else ""
            lines.append(f"  • {t['title']}{proj}{due}")

    if high:
        lines.append("\nHIGH PRIORITY TASKS (this week):")
        for t in high:
            proj = f" [{t['project_name']}]" if t.get('project_name') else ""
            due  = f" — due {t['due_date']}" if t.get('due_date') else ""
            lines.append(f"  • {t['title']}{proj}{due}")

    return "\n".join(lines) if lines else "No pending tasks."


def _format_memory_section(memory_data: Dict[str, Any]) -> str:
    """Format memory stats into a text block for the Sonnet prompt."""
    if not memory_data.get('available'):
        return "Memory system data unavailable."

    stats = memory_data.get('stats', {})
    total = stats.get('total_memories', 0)
    by_type = stats.get('by_type', {})
    avg_rel = stats.get('avg_relevance', 0.0)

    parts = [f"Total memories stored: {total}"]
    if by_type:
        type_parts = [f"{k}: {v}" for k, v in by_type.items()]
        parts.append("By type: " + ", ".join(type_parts))
    if avg_rel:
        parts.append(f"Average relevance score: {avg_rel:.2f}")

    return "\n".join(parts)


def _format_learning_section(learning_data: Dict[str, Any]) -> str:
    """Format routing insights into a text block for the Sonnet prompt."""
    if not learning_data.get('available'):
        return "Learning data unavailable."

    insights = learning_data.get('insights', '')
    return insights if insights else "Not enough routing data yet to identify patterns."


def _format_lead_section(lead_data: Dict[str, Any]) -> str:
    """Format lead data into a text block for the Sonnet prompt."""
    if not lead_data.get('available'):
        return "Lead scanner not yet active."

    leads = lead_data.get('new_leads', [])
    if not leads:
        return "No new leads since last briefing."

    lines = [f"{len(leads)} new lead(s) found:"]
    for lead in leads:
        score    = lead.get('relevance_score', 0)
        industry = lead.get('industry', 'Unknown industry')
        location = lead.get('location', 'Unknown location')
        title    = lead.get('title', 'Untitled lead')
        lines.append(f"  • [{score:.0f}/10] {title} — {industry}, {location}")

    return "\n".join(lines)


def _format_health_section(health_data: Dict[str, Any]) -> str:
    """Format health summary into a text block for the Sonnet prompt."""
    if not health_data.get('available'):
        return "App monitor not yet active."

    health = health_data.get('health_summary', {})
    services = health.get('services', [])
    issues   = [s for s in services if s.get('status') not in ('healthy', 'unknown')]

    if not issues:
        return "All monitored services are healthy."

    lines = [f"⚠️ {len(issues)} service issue(s) detected:"]
    for svc in issues:
        lines.append(
            f"  • {svc.get('service_name', 'Unknown')}: "
            f"{svc.get('status', 'unknown')} — {svc.get('error_message', 'no details')}"
        )
    return "\n".join(lines)


# ============================================================================
# SONNET CALL — compose the briefing text
# ============================================================================

def _call_sonnet_for_briefing(
    task_section: str,
    memory_section: str,
    learning_section: str,
    lead_section: str,
    health_section: str,
    today_str: str,
) -> str:
    """
    Call Claude Sonnet to compose the morning briefing from the assembled data.
    Returns the briefing text, or a plain-text fallback if the API call fails.
    """
    import anthropic
    from config import ANTHROPIC_API_KEY, CLAUDE_SONNET_MODEL

    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not configured — returning raw briefing")
        return _plain_text_fallback(
            task_section, lead_section, health_section, today_str
        )

    prompt = f"""You are the AI Swarm Orchestrator's daily briefing system for Jim at \
Shiftwork Solutions LLC, a shift schedule optimization consulting firm with hundreds \
of client facilities served over 30+ years.

Compose a concise, actionable morning briefing from the following data. \
Today is {today_str}.

TASK STATUS:
{task_section}

NEW BUSINESS LEADS:
{lead_section}

SYSTEM HEALTH:
{health_section}

MEMORY & LEARNING:
{memory_section}
{learning_section}

RULES FOR THE BRIEFING:
- Open with a friendly greeting using today's date
- Lead with the most important/urgent items
- Be concise — this is a briefing, not a report
- For tasks: list them with priority and what needs to happen
- For leads: briefly describe each with why it's relevant to a shift scheduling firm
- For system health: only mention if something is wrong; skip if all healthy
- For memory/learning: only mention if there is a notable insight worth sharing
- Close with a prompt like "What would you like to tackle first?"
- Keep the total briefing under 500 words
- Tone: professional but warm, like a trusted colleague giving a morning update
- Do NOT use markdown headers or bullet symbols — write in natural flowing text \
  with paragraph breaks

Return the briefing as plain text only. No markdown, no headers, no bullet points."""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=CLAUDE_SONNET_MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        briefing_text = response.content[0].text.strip()
        logger.info(f"Briefing generated by Sonnet ({len(briefing_text)} chars)")
        return briefing_text

    except Exception as e:
        logger.error(f"Sonnet briefing call failed: {e}")
        return _plain_text_fallback(
            task_section, lead_section, health_section, today_str
        )


def _plain_text_fallback(
    task_section: str,
    lead_section: str,
    health_section: str,
    today_str: str,
) -> str:
    """
    Fallback briefing when the Sonnet call fails.
    Assembles a readable plain-text briefing directly from the data sections.
    """
    return (
        f"Good morning! Here is your briefing for {today_str}.\n\n"
        f"TASKS:\n{task_section}\n\n"
        f"LEADS:\n{lead_section}\n\n"
        f"SYSTEM HEALTH:\n{health_section}\n\n"
        "What would you like to tackle first?"
    )


# ============================================================================
# PUBLIC API
# ============================================================================

def generate_daily_briefing() -> Dict[str, Any]:
    """
    Gather all available data, call Sonnet to compose the briefing, store it
    in daily_briefings, and return the result.

    The briefing is stored with UPSERT on briefing_date — calling this function
    multiple times on the same day overwrites the previous briefing cleanly.

    Called by:
        - proactive/scheduler.py at 6:30 AM Pacific (automatic)
        - GET /api/briefing when no today-briefing exists (on-demand)
        - GET /api/briefing/generate (force refresh)

    Returns:
        dict with keys:
            success (bool)
            briefing_date (str): ISO date
            content (str): Full briefing text
            data_summary (dict): Structured data used to build the briefing
            generated_at (str): ISO timestamp
            error (str): Only present on failure
    """
    today     = date.today()
    today_str = today.strftime("%A, %B %d, %Y")   # "Thursday, March 12, 2026"
    today_iso = today.isoformat()                  # "2026-03-12"

    logger.info(f"generate_daily_briefing: starting for {today_iso}")
    print(f"📋 Daily Briefing: generating for {today_str}...")

    # ----------------------------------------------------------------
    # 1. Gather data from all sources (each isolated — none can crash us)
    # ----------------------------------------------------------------
    task_data     = _gather_task_data()
    memory_data   = _gather_memory_data()
    learning_data = _gather_learning_data()
    lead_data     = _gather_lead_data()
    health_data   = _gather_health_data()

    # ----------------------------------------------------------------
    # 2. Format each section as prompt-ready text
    # ----------------------------------------------------------------
    task_section     = _format_task_section(task_data)
    memory_section   = _format_memory_section(memory_data)
    learning_section = _format_learning_section(learning_data)
    lead_section     = _format_lead_section(lead_data)
    health_section   = _format_health_section(health_data)

    # ----------------------------------------------------------------
    # 3. Build structured data_summary for storage and API response
    # ----------------------------------------------------------------
    data_summary = {
        'generated_date': today_iso,
        'task_summary':   task_data.get('summary', {}),
        'task_count': {
            'critical': len(task_data.get('critical_tasks', [])),
            'high':     len(task_data.get('high_tasks', [])),
        },
        'lead_count':       lead_data.get('lead_count', 0),
        'memory_total':     memory_data.get('stats', {}).get('total_memories', 0),
        'health_available': health_data.get('available', False),
        'sources_available': {
            'tasks':    task_data.get('available',    False),
            'memory':   memory_data.get('available',  False),
            'learning': learning_data.get('available', False),
            'leads':    lead_data.get('available',    False),
            'health':   health_data.get('available',  False),
        },
    }

    # ----------------------------------------------------------------
    # 4. Call Sonnet to compose the briefing
    # ----------------------------------------------------------------
    content = _call_sonnet_for_briefing(
        task_section=task_section,
        memory_section=memory_section,
        learning_section=learning_section,
        lead_section=lead_section,
        health_section=health_section,
        today_str=today_str,
    )

    # ----------------------------------------------------------------
    # 5. Store in database (UPSERT — one row per calendar day)
    # ----------------------------------------------------------------
    try:
        from db_engine import get_db_connection

        upsert_sql = """
            INSERT INTO daily_briefings
                (briefing_date, content, data_summary, generated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (briefing_date)
            DO UPDATE SET
                content      = EXCLUDED.content,
                data_summary = EXCLUDED.data_summary,
                generated_at = NOW()
            RETURNING id, generated_at
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(upsert_sql, (today_iso, content, json.dumps(data_summary)))
            row = cursor.fetchone()
            briefing_id  = row['id']
            generated_at = row['generated_at']

        generated_at_str = (
            generated_at.isoformat()
            if isinstance(generated_at, datetime)
            else str(generated_at)
        )

        logger.info(f"Daily briefing stored: id={briefing_id} for {today_iso}")
        print(f"✅ Daily Briefing: stored (id={briefing_id}) for {today_iso}")

        return {
            'success':       True,
            'briefing_id':   briefing_id,
            'briefing_date': today_iso,
            'content':       content,
            'data_summary':  data_summary,
            'generated_at':  generated_at_str,
        }

    except Exception as e:
        logger.error(f"Failed to store daily briefing: {e}")
        print(f"⚠️  Daily Briefing: storage failed — returning content anyway: {e}")
        # Return the briefing even if storage failed — Jim still needs his morning info
        return {
            'success':       False,
            'briefing_date': today_iso,
            'content':       content,
            'data_summary':  data_summary,
            'generated_at':  datetime.utcnow().isoformat(),
            'error':         str(e),
        }


def get_latest_briefing() -> Optional[Dict[str, Any]]:
    """
    Return the most recently stored briefing (any date).

    Returns:
        dict with briefing data, or None if no briefings exist yet
    """
    from db_engine import get_db_connection

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, briefing_date, content, data_summary, generated_at
                FROM   daily_briefings
                ORDER  BY briefing_date DESC
                LIMIT  1
            """)
            row = cursor.fetchone()

        if not row:
            return None

        return _serialize_briefing_row(row)

    except Exception as e:
        logger.error(f"get_latest_briefing failed: {e}")
        return None


def get_briefing_for_date(date_str: str) -> Optional[Dict[str, Any]]:
    """
    Return the briefing for a specific calendar date.

    Args:
        date_str: ISO date string 'YYYY-MM-DD'

    Returns:
        dict with briefing data, or None if no briefing exists for that date
    """
    from db_engine import get_db_connection

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, briefing_date, content, data_summary, generated_at
                FROM   daily_briefings
                WHERE  briefing_date = %s
            """, (date_str,))
            row = cursor.fetchone()

        if not row:
            return None

        return _serialize_briefing_row(row)

    except Exception as e:
        logger.error(f"get_briefing_for_date({date_str}) failed: {e}")
        return None


def get_briefing_history(days: int = 7) -> List[Dict[str, Any]]:
    """
    Return briefings from the past N days, newest first.

    Args:
        days: How many days back to look (default 7, max 90)

    Returns:
        List of briefing dicts (may be empty if no briefings stored yet)
    """
    days = max(1, min(int(days), 90))
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    from db_engine import get_db_connection

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, briefing_date, content, data_summary, generated_at
                FROM   daily_briefings
                WHERE  briefing_date >= %s
                ORDER  BY briefing_date DESC
            """, (cutoff,))
            rows = cursor.fetchall()

        return [_serialize_briefing_row(row) for row in rows]

    except Exception as e:
        logger.error(f"get_briefing_history({days}) failed: {e}")
        return []


# ============================================================================
# PRIVATE HELPERS
# ============================================================================

def _serialize_briefing_row(row) -> Dict[str, Any]:
    """
    Convert a daily_briefings DB row to a plain JSON-serializable dict.
    Parses the JSONB data_summary back to a dict if it came back as a string.
    """
    result = {}
    for key in row.keys():
        value = row[key]
        if isinstance(value, (datetime, date)):
            result[key] = value.isoformat()
        else:
            result[key] = value

    # data_summary may arrive as a string from psycopg2 depending on driver version
    ds = result.get('data_summary')
    if isinstance(ds, str):
        try:
            result['data_summary'] = json.loads(ds)
        except (json.JSONDecodeError, TypeError):
            result['data_summary'] = {}
    elif ds is None:
        result['data_summary'] = {}

    return result


# I did no harm and this file is not truncated
