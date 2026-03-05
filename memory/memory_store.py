"""
AI SWARM ORCHESTRATOR - Memory Store
Phase 2A: Memory System — Store Layer

Created: March 05, 2026
Last Updated: March 05, 2026 - Phase 2A initial build

CHANGELOG:
- March 05, 2026: Phase 2A initial build
  * New file — part of Phase 2A memory system
  * Provides all CRUD operations against the memory_store PostgreSQL table
  * Table already exists (created by migrations/001_initial_schema.py, 56-table schema)
  * Uses get_db_connection() from db_engine.py — %s params, dict-like rows
  * Functions: store_memory, get_memories_by_type, get_memories_by_category,
    search_memories, get_memory_stats, update_relevance, delete_old_memories
  * No changes to any existing file

PURPOSE:
    Low-level data access layer for the memory system.
    All functions use the db_engine abstraction layer (PostgreSQL in prod,
    SQLite in local dev). Never import psycopg2 or sqlite3 directly.

MEMORY TYPES:
    episodic   — Records of specific interactions (what happened)
    semantic   — Generalized knowledge extracted from episodes (what we know)
    procedural — How to do things well (how to work better)

CATEGORIES:
    client_info         — Facts about specific clients
    scheduling          — Schedule design knowledge
    routing_performance — Which AI handles which task best
    user_preferences    — Jim's working preferences
    project_context     — Active project details
    task_patterns       — Patterns in what gets requested
    system_performance  — How the system is performing

USAGE:
    from memory.memory_store import store_memory, search_memories

    memory_id = store_memory(
        memory_type='semantic',
        category='client_info',
        content='Acme Corp runs a 24/7 bottling operation with 4 crews on DuPont.',
        source_task_id=42,
        relevance_score=0.85
    )

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Valid enumerations — used for input validation
VALID_MEMORY_TYPES = {'episodic', 'semantic', 'procedural'}
VALID_CATEGORIES = {
    'client_info', 'scheduling', 'routing_performance',
    'user_preferences', 'project_context', 'task_patterns', 'system_performance'
}


# ============================================================================
# STORE
# ============================================================================

def store_memory(memory_type, category, content, source_task_id=None, relevance_score=0.5):
    """
    Insert a new memory into the memory_store table.

    Args:
        memory_type (str): 'episodic', 'semantic', or 'procedural'
        category (str): One of the VALID_CATEGORIES set
        content (str): The actual memory text (1-3 sentences, concise but specific)
        source_task_id (int|None): Optional FK to the tasks table row that created this memory
        relevance_score (float): 0.0 to 1.0, how important this is to retain long-term

    Returns:
        int: The new memory's id, or None on failure
    """
    # Sanitize inputs
    memory_type = memory_type.strip().lower() if memory_type else 'episodic'
    category = category.strip().lower() if category else 'task_patterns'

    if memory_type not in VALID_MEMORY_TYPES:
        logger.warning(f"store_memory: invalid memory_type '{memory_type}', defaulting to 'episodic'")
        memory_type = 'episodic'

    if category not in VALID_CATEGORIES:
        logger.warning(f"store_memory: invalid category '{category}', defaulting to 'task_patterns'")
        category = 'task_patterns'

    # Clamp relevance_score to [0.0, 1.0]
    try:
        relevance_score = max(0.0, min(1.0, float(relevance_score)))
    except (TypeError, ValueError):
        relevance_score = 0.5

    if not content or not content.strip():
        logger.warning("store_memory: empty content — skipping")
        return None

    content = content.strip()

    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO memory_store
                    (memory_type, category, content, relevance_score, source_task_id,
                     created_at, updated_at)
                VALUES
                    (%s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
                """,
                (memory_type, category, content, relevance_score, source_task_id)
            )
            row = cursor.fetchone()
            if row:
                memory_id = row['id'] if hasattr(row, '__getitem__') and 'id' in row else row[0]
                logger.info(f"Stored {memory_type}/{category} memory id={memory_id}")
                return memory_id
            return None

    except Exception as e:
        logger.error(f"store_memory failed: {e}")
        return None


# ============================================================================
# RETRIEVAL BY TYPE
# ============================================================================

def get_memories_by_type(memory_type, limit=20):
    """
    Return recent memories of a given type, ordered by recency.

    Args:
        memory_type (str): 'episodic', 'semantic', or 'procedural'
        limit (int): Maximum number of rows to return

    Returns:
        list[dict]: Each dict has id, memory_type, category, content,
                    relevance_score, source_task_id, created_at, updated_at
    """
    memory_type = memory_type.strip().lower() if memory_type else ''
    if memory_type not in VALID_MEMORY_TYPES:
        logger.warning(f"get_memories_by_type: invalid type '{memory_type}'")
        return []

    try:
        limit = max(1, min(int(limit), 200))
    except (TypeError, ValueError):
        limit = 20

    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, memory_type, category, content, relevance_score,
                       source_task_id, created_at, updated_at
                FROM memory_store
                WHERE memory_type = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (memory_type, limit)
            )
            rows = cursor.fetchall()
            return [_row_to_dict(r) for r in rows]

    except Exception as e:
        logger.error(f"get_memories_by_type failed: {e}")
        return []


# ============================================================================
# RETRIEVAL BY CATEGORY
# ============================================================================

def get_memories_by_category(category, limit=20):
    """
    Return recent memories in a given category, ordered by relevance then recency.

    Args:
        category (str): One of VALID_CATEGORIES
        limit (int): Maximum number of rows to return

    Returns:
        list[dict]: Memory rows as dicts
    """
    category = category.strip().lower() if category else ''
    if category not in VALID_CATEGORIES:
        logger.warning(f"get_memories_by_category: invalid category '{category}'")
        return []

    try:
        limit = max(1, min(int(limit), 200))
    except (TypeError, ValueError):
        limit = 20

    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, memory_type, category, content, relevance_score,
                       source_task_id, created_at, updated_at
                FROM memory_store
                WHERE category = %s
                ORDER BY relevance_score DESC, created_at DESC
                LIMIT %s
                """,
                (category, limit)
            )
            rows = cursor.fetchall()
            return [_row_to_dict(r) for r in rows]

    except Exception as e:
        logger.error(f"get_memories_by_category failed: {e}")
        return []


# ============================================================================
# KEYWORD SEARCH
# ============================================================================

def search_memories(query_text, limit=10):
    """
    Simple keyword search across memory content using PostgreSQL ILIKE.

    Strategy: tokenize the query, run an ILIKE search for each word,
    score each row by how many words it matches, return highest-scoring
    rows ordered by match_count DESC, relevance_score DESC, created_at DESC.

    Args:
        query_text (str): Free-text search query
        limit (int): Maximum number of results to return

    Returns:
        list[dict]: Memory rows as dicts, best matches first
    """
    if not query_text or not query_text.strip():
        return []

    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 10

    # Tokenize: split on whitespace, remove empties, keep words 2+ chars
    words = [w.strip() for w in query_text.strip().split() if len(w.strip()) >= 2]
    if not words:
        return []

    # Cap at 10 words to avoid absurdly long queries
    words = words[:10]

    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Build a CASE expression that adds 1 for each word match.
            # This gives us a relevance ranking without full-text search infrastructure.
            case_parts = []
            params = []
            for word in words:
                case_parts.append("CASE WHEN content ILIKE %s THEN 1 ELSE 0 END")
                params.append(f"%{word}%")

            match_score_expr = " + ".join(case_parts)

            # WHERE clause: at least one word must match
            where_parts = ["content ILIKE %s" for _ in words]
            where_expr = " OR ".join(where_parts)
            where_params = [f"%{w}%" for w in words]

            sql = f"""
                SELECT id, memory_type, category, content, relevance_score,
                       source_task_id, created_at, updated_at,
                       ({match_score_expr}) AS match_count
                FROM memory_store
                WHERE {where_expr}
                ORDER BY match_count DESC, relevance_score DESC, created_at DESC
                LIMIT %s
            """

            all_params = params + where_params + [limit]
            cursor.execute(sql, all_params)
            rows = cursor.fetchall()
            return [_row_to_dict(r) for r in rows]

    except Exception as e:
        logger.error(f"search_memories failed: {e}")
        return []


# ============================================================================
# STATISTICS
# ============================================================================

def get_memory_stats():
    """
    Return aggregate statistics about the memory store.

    Returns:
        dict with keys:
            total_memories (int)
            by_type (dict): {memory_type: count}
            by_category (dict): {category: count}
            oldest_memory (str|None): ISO timestamp
            newest_memory (str|None): ISO timestamp
            avg_relevance (float): average relevance_score across all memories
            operational (bool): True if the table is accessible
    """
    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Total count
            cursor.execute("SELECT COUNT(*) AS cnt FROM memory_store")
            total = cursor.fetchone()['cnt']

            # Count by type
            cursor.execute(
                """
                SELECT memory_type, COUNT(*) AS cnt
                FROM memory_store
                GROUP BY memory_type
                ORDER BY cnt DESC
                """
            )
            by_type = {row['memory_type']: row['cnt'] for row in cursor.fetchall()}

            # Count by category
            cursor.execute(
                """
                SELECT category, COUNT(*) AS cnt
                FROM memory_store
                GROUP BY category
                ORDER BY cnt DESC
                """
            )
            by_category = {row['category']: row['cnt'] for row in cursor.fetchall()}

            # Date range and avg relevance
            cursor.execute(
                """
                SELECT
                    MIN(created_at) AS oldest,
                    MAX(created_at) AS newest,
                    AVG(relevance_score) AS avg_rel
                FROM memory_store
                """
            )
            agg = cursor.fetchone()

            oldest = str(agg['oldest']) if agg and agg['oldest'] else None
            newest = str(agg['newest']) if agg and agg['newest'] else None
            avg_rel = round(float(agg['avg_rel']), 3) if agg and agg['avg_rel'] else 0.0

            return {
                'total_memories': total,
                'by_type': by_type,
                'by_category': by_category,
                'oldest_memory': oldest,
                'newest_memory': newest,
                'avg_relevance': avg_rel,
                'operational': True
            }

    except Exception as e:
        logger.error(f"get_memory_stats failed: {e}")
        return {
            'total_memories': 0,
            'by_type': {},
            'by_category': {},
            'oldest_memory': None,
            'newest_memory': None,
            'avg_relevance': 0.0,
            'operational': False,
            'error': str(e)
        }


# ============================================================================
# UPDATE RELEVANCE
# ============================================================================

def update_relevance(memory_id, new_score):
    """
    Update the relevance_score of a specific memory.
    Also bumps updated_at to NOW().

    Args:
        memory_id (int): The memory's primary key
        new_score (float): New relevance score, clamped to [0.0, 1.0]

    Returns:
        bool: True on success, False on failure
    """
    try:
        new_score = max(0.0, min(1.0, float(new_score)))
    except (TypeError, ValueError):
        logger.warning(f"update_relevance: invalid score '{new_score}'")
        return False

    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE memory_store
                SET relevance_score = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (new_score, memory_id)
            )
            return cursor.rowcount > 0

    except Exception as e:
        logger.error(f"update_relevance failed for id={memory_id}: {e}")
        return False


# ============================================================================
# PRUNE OLD MEMORIES
# ============================================================================

def delete_old_memories(days=90, min_relevance=0.3):
    """
    Delete EPISODIC memories older than `days` days with relevance_score
    below `min_relevance`. Semantic and procedural memories are NEVER
    deleted automatically — they represent hard-won knowledge.

    Args:
        days (int): Age threshold in days (default: 90)
        min_relevance (float): Relevance threshold (default: 0.3 — delete below this)

    Returns:
        int: Number of rows deleted, or -1 on failure
    """
    try:
        days = max(1, int(days))
    except (TypeError, ValueError):
        days = 90

    try:
        min_relevance = max(0.0, min(1.0, float(min_relevance)))
    except (TypeError, ValueError):
        min_relevance = 0.3

    cutoff = datetime.utcnow() - timedelta(days=days)

    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM memory_store
                WHERE memory_type = 'episodic'
                  AND relevance_score < %s
                  AND created_at < %s
                """,
                (min_relevance, cutoff)
            )
            deleted = cursor.rowcount
            logger.info(
                f"delete_old_memories: removed {deleted} episodic memories "
                f"older than {days} days with relevance < {min_relevance}"
            )
            return deleted

    except Exception as e:
        logger.error(f"delete_old_memories failed: {e}")
        return -1


# ============================================================================
# PRIVATE HELPERS
# ============================================================================

def _row_to_dict(row):
    """
    Convert a database row (dict-like from db_engine) to a plain Python dict.
    Ensures created_at and updated_at are serializable strings.
    Removes internal match_count column if present (used only for scoring).
    """
    if row is None:
        return {}

    d = dict(row) if hasattr(row, 'items') else {}

    # Remove internal scoring column — not part of the public schema
    d.pop('match_count', None)

    # Serialize datetime objects to ISO strings
    for key in ('created_at', 'updated_at'):
        val = d.get(key)
        if val and not isinstance(val, str):
            try:
                d[key] = val.isoformat()
            except AttributeError:
                d[key] = str(val)

    return d


# I did no harm and this file is not truncated
