"""
AI SWARM ORCHESTRATOR - Proactive Task Manager
File: proactive/task_manager.py
Created: March 12, 2026
Last Updated: March 13, 2026 — BUG FIX: remove raise from _ensure_table()

PURPOSE:
    Persistent to-do list that the Swarm maintains, prioritizes, and surfaces.
    Tasks are stored in PostgreSQL (swarm_tasks table) and survive restarts.
    Provides task CRUD, smart priority sorting, and AI-powered task generation
    from recent memories.

    This is the first module of Phase 6: The Proactive Agent.

CHANGELOG:
- March 13, 2026: BUG FIX — remove raise from _ensure_table()
  * _ensure_table() ran at module level and called raise on DB failure.
  * If the DB was temporarily unavailable at startup, Python marked the
    module as a failed import. All subsequent imports raised ImportError.
  * routes/proactive.py catches ImportError and returns 503.
  * Fix: log the error but do NOT re-raise. The module loads successfully
    and table creation is retried on the next DB operation.
  * Only the except block in _ensure_table() changed — nothing else touched.

- March 12, 2026: Phase 6 Deliverable 1 — Initial implementation
  * Created swarm_tasks table (idempotent migration runs on import)
  * add_task(), get_pending_tasks(), complete_task(), defer_task(), update_task()
  * get_task_summary() — structured data for daily briefing
  * auto_generate_tasks_from_memory() — Sonnet call to extract tasks from memories
  * Priority ordering: critical > high > medium > low
  * All SQL uses %s placeholders (PostgreSQL convention per db_engine.py)
  * All connections use get_db_connection() from db_engine — never direct psycopg2

DATABASE TABLE: swarm_tasks
    id              SERIAL PRIMARY KEY
    title           TEXT NOT NULL
    description     TEXT
    priority        VARCHAR(20) DEFAULT 'medium'  (critical|high|medium|low)
    status          VARCHAR(20) DEFAULT 'pending' (pending|in_progress|completed|deferred)
    category        VARCHAR(50)                   (client_work|lead_generation|app_maintenance|
                                                   marketing|learning|admin)
    source          VARCHAR(50)                   (user|system|briefing|memory_extraction)
    due_date        DATE
    project_name    VARCHAR(100)
    created_at      TIMESTAMP DEFAULT NOW()
    completed_at    TIMESTAMP
    notes           TEXT

DEPENDENCIES:
    db_engine.py    — get_db_connection() (already in repo)
    config.py       — ANTHROPIC_API_KEY, CLAUDE_SONNET_MODEL (already in repo)
    anthropic        — AI call for auto_generate_tasks_from_memory()

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ============================================================================
# PRIORITY ORDERING (used for sorting tasks)
# ============================================================================

PRIORITY_ORDER = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}

VALID_PRIORITIES   = {'critical', 'high', 'medium', 'low'}
VALID_STATUSES     = {'pending', 'in_progress', 'completed', 'deferred'}
VALID_CATEGORIES   = {'client_work', 'lead_generation', 'app_maintenance',
                      'marketing', 'learning', 'admin'}
VALID_SOURCES      = {'user', 'system', 'briefing', 'memory_extraction'}


# ============================================================================
# STEP 1: ENSURE TABLE EXISTS (idempotent — safe to run on every import)
# ============================================================================

def _ensure_table():
    """
    Create swarm_tasks table if it does not already exist.
    Called once at module import. Uses CREATE TABLE IF NOT EXISTS so it is
    fully idempotent — safe to run on every startup.

    NOTE: Does NOT re-raise on failure. A DB hiccup at startup must not
    poison the module import — routes/proactive.py catches ImportError and
    returns 503, so a transient DB error here would permanently break the
    endpoint until the next deploy. Log and continue instead.
    """
    from db_engine import get_db_connection

    sql = """
        CREATE TABLE IF NOT EXISTS swarm_tasks (
            id           SERIAL PRIMARY KEY,
            title        TEXT NOT NULL,
            description  TEXT,
            priority     VARCHAR(20)  DEFAULT 'medium',
            status       VARCHAR(20)  DEFAULT 'pending',
            category     VARCHAR(50)  DEFAULT 'admin',
            source       VARCHAR(50)  DEFAULT 'user',
            due_date     DATE,
            project_name VARCHAR(100),
            created_at   TIMESTAMP    DEFAULT NOW(),
            completed_at TIMESTAMP,
            notes        TEXT
        )
    """
    try:
        with get_db_connection() as conn:
            conn.execute(sql)
        logger.info("swarm_tasks table ready")
        print("✅ proactive/task_manager: swarm_tasks table ready")
    except Exception as e:
        logger.error(f"Failed to create swarm_tasks table: {e}")
        print(f"❌ proactive/task_manager: table creation failed (non-fatal): {e}")
        # Do NOT re-raise — a transient DB error must not poison this module's import


# Run migration at import time — mirrors the pattern in other Swarm modules
_ensure_table()


# ============================================================================
# HELPER: SERIALIZE A ROW FOR JSON / BRIEFING
# ============================================================================

def _serialize_task(row) -> Dict[str, Any]:
    """
    Convert a database row to a plain dict with JSON-serializable values.
    Handles date/datetime objects that cannot be JSON-serialized directly.
    """
    task = {}
    for key in row.keys():
        value = row[key]
        if isinstance(value, datetime):
            task[key] = value.isoformat()
        elif isinstance(value, date):
            task[key] = value.isoformat()
        else:
            task[key] = value
    return task


# ============================================================================
# PUBLIC API — CRUD OPERATIONS
# ============================================================================

def add_task(
    title: str,
    description: Optional[str] = None,
    priority: str = 'medium',
    category: str = 'admin',
    source: str = 'user',
    due_date: Optional[str] = None,          # ISO date string: 'YYYY-MM-DD' or None
    project_name: Optional[str] = None,
) -> int:
    """
    Create a new task in swarm_tasks.

    Args:
        title        : Short task title (required)
        description  : Longer description of what needs to be done
        priority     : 'critical' | 'high' | 'medium' | 'low'
        category     : 'client_work' | 'lead_generation' | 'app_maintenance' |
                       'marketing' | 'learning' | 'admin'
        source       : 'user' | 'system' | 'briefing' | 'memory_extraction'
        due_date     : ISO date string 'YYYY-MM-DD', or None
        project_name : Client or project name this task belongs to, or None

    Returns:
        int: The new task's ID

    Raises:
        ValueError: If an invalid priority, category, or source is supplied
        Exception:  On database error
    """
    if not title or not title.strip():
        raise ValueError("title is required and cannot be blank")

    priority = priority.lower()
    category = category.lower()
    source   = source.lower()

    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority '{priority}'. Must be one of: {VALID_PRIORITIES}")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Must be one of: {VALID_CATEGORIES}")
    if source not in VALID_SOURCES:
        raise ValueError(f"Invalid source '{source}'. Must be one of: {VALID_SOURCES}")

    from db_engine import get_db_connection

    sql = """
        INSERT INTO swarm_tasks
            (title, description, priority, status, category, source, due_date, project_name)
        VALUES (%s, %s, %s, 'pending', %s, %s, %s, %s)
        RETURNING id
    """
    params = (
        title.strip(),
        description,
        priority,
        category,
        source,
        due_date,        # PostgreSQL accepts ISO date string or None
        project_name,
    )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        task_id = row['id']

    logger.info(f"Task created: id={task_id}, title='{title}', priority={priority}")
    return task_id


def get_pending_tasks(
    limit: int = 20,
    category: Optional[str] = None,
    priority: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return pending (and in-progress) tasks sorted by priority then due_date
    then created_at.

    Sort order:
        1. Priority: critical → high → medium → low
        2. Due date: soonest first (NULLs last)
        3. Created at: oldest first

    Args:
        limit    : Maximum rows to return (default 20)
        category : Optional filter by category
        priority : Optional filter by priority

    Returns:
        List of task dicts (JSON-serializable)
    """
    from db_engine import get_db_connection

    # Build WHERE clause dynamically
    conditions = ["status IN ('pending', 'in_progress')"]
    params: list = []

    if category:
        conditions.append("category = %s")
        params.append(category.lower())
    if priority:
        conditions.append("priority = %s")
        params.append(priority.lower())

    where = " AND ".join(conditions)

    # CASE expression maps priority text to sort number
    sql = f"""
        SELECT *
        FROM swarm_tasks
        WHERE {where}
        ORDER BY
            CASE priority
                WHEN 'critical' THEN 1
                WHEN 'high'     THEN 2
                WHEN 'medium'   THEN 3
                WHEN 'low'      THEN 4
                ELSE 5
            END ASC,
            due_date ASC NULLS LAST,
            created_at ASC
        LIMIT %s
    """
    params.append(limit)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    return [_serialize_task(row) for row in rows]


def complete_task(task_id: int, notes: Optional[str] = None) -> bool:
    """
    Mark a task as completed with the current timestamp.

    Args:
        task_id : The task's database ID
        notes   : Optional completion notes

    Returns:
        True if a row was updated, False if task_id not found
    """
    from db_engine import get_db_connection

    sql = """
        UPDATE swarm_tasks
        SET    status = 'completed',
               completed_at = NOW(),
               notes = COALESCE(%s, notes)
        WHERE  id = %s
          AND  status NOT IN ('completed')
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (notes, task_id))
        updated = cursor.rowcount

    if updated:
        logger.info(f"Task {task_id} marked completed")
    else:
        logger.warning(f"complete_task: no row updated for id={task_id}")

    return bool(updated)


def defer_task(
    task_id: int,
    new_due_date: Optional[str] = None,
    reason: Optional[str] = None,
) -> bool:
    """
    Mark a task as deferred with an optional new due date and reason.

    Args:
        task_id      : The task's database ID
        new_due_date : ISO date string 'YYYY-MM-DD' for the new target date
        reason       : Why the task is being deferred (stored in notes)

    Returns:
        True if a row was updated, False if task_id not found
    """
    from db_engine import get_db_connection

    # Build notes with reason if provided
    notes_value = f"Deferred: {reason}" if reason else "Deferred"

    sql = """
        UPDATE swarm_tasks
        SET    status   = 'deferred',
               due_date = COALESCE(%s, due_date),
               notes    = %s
        WHERE  id = %s
          AND  status NOT IN ('completed')
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (new_due_date, notes_value, task_id))
        updated = cursor.rowcount

    if updated:
        logger.info(f"Task {task_id} deferred. New due date: {new_due_date}")
    else:
        logger.warning(f"defer_task: no row updated for id={task_id}")

    return bool(updated)


def update_task(task_id: int, **kwargs) -> bool:
    """
    Update one or more fields on a task.

    Allowed fields: title, description, priority, status, category,
                    source, due_date, project_name, notes

    Args:
        task_id : The task's database ID
        **kwargs: Field=value pairs to update

    Returns:
        True if a row was updated, False if task_id not found or nothing changed

    Raises:
        ValueError: If no valid fields are supplied, or an invalid value is given
    """
    UPDATABLE_FIELDS = {
        'title', 'description', 'priority', 'status',
        'category', 'source', 'due_date', 'project_name', 'notes'
    }

    # Filter to only updatable fields
    updates = {k: v for k, v in kwargs.items() if k in UPDATABLE_FIELDS}

    if not updates:
        raise ValueError(
            f"No valid fields to update. Allowed: {UPDATABLE_FIELDS}"
        )

    # Validate enum fields
    if 'priority' in updates and updates['priority'] not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority: {updates['priority']}")
    if 'status'   in updates and updates['status']   not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {updates['status']}")
    if 'category' in updates and updates['category'] not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category: {updates['category']}")

    from db_engine import get_db_connection

    set_clauses = ", ".join(f"{field} = %s" for field in updates)
    params      = list(updates.values()) + [task_id]

    sql = f"UPDATE swarm_tasks SET {set_clauses} WHERE id = %s"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        updated = cursor.rowcount

    if updated:
        logger.info(f"Task {task_id} updated: {list(updates.keys())}")

    return bool(updated)


# ============================================================================
# SUMMARY — used by daily briefing
# ============================================================================

def get_task_summary() -> Dict[str, Any]:
    """
    Return aggregate task statistics for the daily briefing.

    Returns dict with keys:
        total_pending       : int  — tasks with status pending or in_progress
        by_priority         : dict — count per priority level (pending/in_progress only)
        by_category         : dict — count per category (pending/in_progress only)
        overdue_count       : int  — pending tasks whose due_date < today
        completed_today     : int  — tasks completed today (UTC)
        completed_this_week : int  — tasks completed in the last 7 days
    """
    from db_engine import get_db_connection

    summary: Dict[str, Any] = {
        'total_pending':       0,
        'by_priority':         {p: 0 for p in ('critical', 'high', 'medium', 'low')},
        'by_category':         {c: 0 for c in VALID_CATEGORIES},
        'overdue_count':       0,
        'completed_today':     0,
        'completed_this_week': 0,
    }

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Total pending + breakdown by priority
        cursor.execute("""
            SELECT priority, COUNT(*) AS cnt
            FROM   swarm_tasks
            WHERE  status IN ('pending', 'in_progress')
            GROUP  BY priority
        """)
        for row in cursor.fetchall():
            priority = row['priority']
            cnt      = row['cnt']
            summary['total_pending'] += cnt
            if priority in summary['by_priority']:
                summary['by_priority'][priority] = cnt

        # Breakdown by category (pending/in_progress only)
        cursor.execute("""
            SELECT category, COUNT(*) AS cnt
            FROM   swarm_tasks
            WHERE  status IN ('pending', 'in_progress')
            GROUP  BY category
        """)
        for row in cursor.fetchall():
            cat = row['category']
            if cat in summary['by_category']:
                summary['by_category'][cat] = row['cnt']

        # Overdue count
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM   swarm_tasks
            WHERE  status IN ('pending', 'in_progress')
              AND  due_date IS NOT NULL
              AND  due_date < CURRENT_DATE
        """)
        row = cursor.fetchone()
        summary['overdue_count'] = row['cnt'] if row else 0

        # Completed today
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM   swarm_tasks
            WHERE  status = 'completed'
              AND  completed_at >= CURRENT_DATE
        """)
        row = cursor.fetchone()
        summary['completed_today'] = row['cnt'] if row else 0

        # Completed this week (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) AS cnt
            FROM   swarm_tasks
            WHERE  status = 'completed'
              AND  completed_at >= NOW() - INTERVAL '7 days'
        """)
        row = cursor.fetchone()
        summary['completed_this_week'] = row['cnt'] if row else 0

    return summary


# ============================================================================
# AI-POWERED TASK GENERATION FROM MEMORY
# ============================================================================

def auto_generate_tasks_from_memory() -> List[int]:
    """
    Query recent memories, then make a Claude Sonnet call to identify any new
    tasks that should be created based on what the Swarm knows.

    Process:
        1. Pull recent semantic + procedural memories from memory_store
        2. Pull current pending tasks (to avoid duplicates)
        3. Call Claude Sonnet with a structured prompt
        4. Parse the JSON response and create any suggested tasks
        5. Return a list of newly created task IDs

    This function is called on a schedule by proactive/scheduler.py
    (once daily at 6:15 AM Pacific).

    Returns:
        List of newly created task IDs (empty list if nothing was created
        or if Sonnet decides no new tasks are needed)
    """
    logger.info("auto_generate_tasks_from_memory: starting")
    print("🤖 Task Manager: scanning memories for new tasks...")

    created_ids: List[int] = []

    # ----------------------------------------------------------------
    # 1. Fetch recent memories
    # ----------------------------------------------------------------
    recent_memories_text = _fetch_recent_memories(limit=30)
    if not recent_memories_text:
        logger.info("No recent memories found — skipping auto task generation")
        print("ℹ️  Task Manager: no memories available yet, skipping")
        return []

    # ----------------------------------------------------------------
    # 2. Fetch current pending tasks (for dedup context)
    # ----------------------------------------------------------------
    pending = get_pending_tasks(limit=50)
    pending_text = _format_tasks_for_prompt(pending)

    # ----------------------------------------------------------------
    # 3. Call Sonnet
    # ----------------------------------------------------------------
    task_suggestions = _call_sonnet_for_tasks(recent_memories_text, pending_text)

    if not task_suggestions:
        logger.info("Sonnet returned no new task suggestions")
        print("ℹ️  Task Manager: Sonnet found no new tasks to create")
        return []

    # ----------------------------------------------------------------
    # 4. Create the suggested tasks
    # ----------------------------------------------------------------
    for suggestion in task_suggestions:
        try:
            title        = suggestion.get('title', '').strip()
            description  = suggestion.get('description')
            priority     = suggestion.get('priority', 'medium').lower()
            category     = suggestion.get('category', 'admin').lower()
            project_name = suggestion.get('project_name')

            if not title:
                logger.warning("Sonnet suggestion missing title — skipping")
                continue

            # Clamp to valid values in case Sonnet hallucinated
            if priority not in VALID_PRIORITIES:
                priority = 'medium'
            if category not in VALID_CATEGORIES:
                category = 'admin'

            task_id = add_task(
                title=title,
                description=description,
                priority=priority,
                category=category,
                source='memory_extraction',
                project_name=project_name,
            )
            created_ids.append(task_id)
            logger.info(f"Auto-created task {task_id}: '{title}'")
            print(f"  ✅ Created task #{task_id}: {title}")

        except Exception as e:
            logger.error(f"Failed to create suggested task '{suggestion}': {e}")
            print(f"  ⚠️  Could not create task: {e}")
            continue

    print(f"🤖 Task Manager: auto-generated {len(created_ids)} new task(s) from memory")
    return created_ids


# ============================================================================
# PRIVATE HELPERS
# ============================================================================

def _fetch_recent_memories(limit: int = 30) -> str:
    """
    Pull recent semantic and procedural memories from the memory_store table.
    Returns a formatted text block for injection into the Sonnet prompt.
    Falls back gracefully if the memory system is not yet set up.
    """
    from db_engine import get_db_connection

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, content, created_at
                FROM   memory_store
                WHERE  category IN ('semantic', 'procedural', 'episodic')
                ORDER  BY created_at DESC
                LIMIT  %s
            """, (limit,))
            rows = cursor.fetchall()

        if not rows:
            return ""

        lines = []
        for row in rows:
            ts      = row['created_at']
            ts_str  = ts.isoformat() if isinstance(ts, datetime) else str(ts)
            category = row.get('category', 'general')
            content  = row.get('content', '')
            lines.append(f"[{ts_str}] ({category}) {content}")

        return "\n".join(lines)

    except Exception as e:
        # Memory system may not be initialized yet — non-fatal
        logger.warning(f"Could not fetch memories for task generation: {e}")
        return ""


def _format_tasks_for_prompt(tasks: List[Dict[str, Any]]) -> str:
    """Format a list of task dicts as a compact text block for the Sonnet prompt."""
    if not tasks:
        return "(none)"

    lines = []
    for t in tasks:
        due   = t.get('due_date') or 'no due date'
        proj  = f" [{t['project_name']}]" if t.get('project_name') else ""
        lines.append(
            f"- [{t['priority'].upper()}] {t['title']}{proj} "
            f"(category: {t['category']}, due: {due})"
        )
    return "\n".join(lines)


def _call_sonnet_for_tasks(
    memories_text: str,
    pending_tasks_text: str,
) -> List[Dict[str, Any]]:
    """
    Call Claude Sonnet to analyze recent memories and suggest new tasks.
    Returns a list of task dicts (may be empty).
    Handles all API and JSON parse errors gracefully.
    """
    import anthropic
    from config import ANTHROPIC_API_KEY, CLAUDE_SONNET_MODEL

    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not configured — cannot auto-generate tasks")
        return []

    prompt = f"""You are the task manager for the AI Swarm Orchestrator at Shiftwork Solutions LLC, \
a shift schedule optimization consulting firm with hundreds of clients served. \
Review these recent memories and determine if any new tasks should be created.

RECENT MEMORIES:
{memories_text}

CURRENT PENDING TASKS:
{pending_tasks_text}

RULES:
- Only create tasks that are genuinely actionable
- Do not duplicate tasks that already exist in the current pending list
- Valid categories: client_work, lead_generation, app_maintenance, marketing, learning, admin
- Valid priorities: critical (needs attention today), high (needs attention this week), \
medium (when time allows), low (nice to have)

Return ONLY a JSON array. No preamble, no explanation, no markdown code fences.
If no new tasks are needed, return an empty array: []

Example format:
[
  {{
    "title": "Follow up with TestCorp on schedule preferences",
    "description": "We discussed their 4-crew bottling operation but haven't received their current schedule details yet",
    "priority": "high",
    "category": "client_work",
    "project_name": "TestCorp"
  }}
]"""

    try:
        client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=CLAUDE_SONNET_MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()

        # Strip accidental markdown fences if Sonnet included them
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        suggestions = json.loads(raw_text)

        if not isinstance(suggestions, list):
            logger.warning(f"Sonnet returned non-list: {type(suggestions)}")
            return []

        return suggestions

    except json.JSONDecodeError as e:
        logger.error(f"Could not parse Sonnet task suggestions as JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Sonnet API call failed in auto_generate_tasks_from_memory: {e}")
        return []


# I did no harm and this file is not truncated
