"""
AI SWARM ORCHESTRATOR - Memory Retriever
Phase 2B: Memory Retrieval & Context Injection

Created: March 07, 2026
Last Updated: March 07, 2026 - FRAMING FIX: memory presented as established facts

CHANGELOG:
- March 07, 2026 (Pass 2): FRAMING FIX
  PROBLEM: AI was contradicting injected memory facts, saying "TestCorp was
    never discussed" even though the memory block contained "TestCorp operates
    a bottling plant with 4 crews." Root cause: the prompt framing said "You
    have the following knowledge from previous interactions" which is weak — the
    AI was weighting an empty in-session conversation_history more heavily than
    the memory context, concluding the topic had not come up in THIS chat.
  FIX: Replaced prompt framing in both _format() and _truncate_to_budget() with
    explicit language:
      - "facts come from your persistent memory system"
      - "YOU ALREADY KNOW from prior sessions, completely independent of the
         current conversation"
      - "Do NOT say these topics were never discussed"
      - "Do NOT say you have no memory of them"
      - "Treat these as established facts you possess"
  This framing makes clear that memory facts are authoritative, independent of
  what appears in the visible conversation history, and must not be contradicted.
  NO OTHER CHANGES: All retrieval logic, strategies, category detection,
    keyword extraction, sorting, and character budget enforcement unchanged.

- March 07, 2026 (Pass 1): Phase 2B initial build
  * New file — wires the memory store into the orchestration flow
  * retrieve_relevant_memories(): three-strategy search returning deduplicated,
    relevance-ranked memory list capped at `limit` entries
  * format_memories_for_prompt(): formats memory list into a clean text block
    for injection into the AI system prompt; returns "" if no memories
  * Category detector maps request text to VALID_CATEGORIES keyword sets
  * Total memory context capped at 2000 characters (token budget)
  * Target latency: <200ms — uses efficient indexed queries via memory_store.py
  * All failures are caught and logged; callers always get a safe return value

PURPOSE:
    Before any AI call is made, this module searches the memory_store table
    for context relevant to the current user request and formats it for
    injection into the AI system prompt. This is what makes the Swarm
    remember past interactions instead of starting cold every time.

STRATEGIES:
    1. Keyword search  — extract meaningful words from request, search content
    2. Category match  — detect topic category, pull high-relevance category memories
    3. Recent procedural — always include 3 most recent procedural memories
                          (these carry "how to work better" knowledge)

CALLED FROM:
    orchestration/task_analysis.py — analyze_task_with_sonnet() and handle_with_opus()
    routes/orchestration_handler.py — Handler 10, directly into completion_prompt
    routes/memory.py               — GET /api/memory/preview?q= (debug endpoint)

USAGE:
    from memory.memory_retriever import retrieve_relevant_memories, format_memories_for_prompt

    memories = retrieve_relevant_memories(user_request, limit=10)
    context  = format_memories_for_prompt(memories)
    # context is either a formatted string block or "" if nothing relevant

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Maximum characters allowed in the formatted memory context block.
# Keeps token usage predictable — memory must not crowd out the actual task.
_MAX_CONTEXT_CHARS = 2000

# Number of procedural memories always pulled regardless of topic match.
# These carry "how to work better" knowledge and are always relevant.
_PROCEDURAL_ALWAYS_PULL = 3

# Keyword sets used to detect which category best matches the user's request.
# Order matters: first match wins in _detect_category().
_CATEGORY_KEYWORDS = [
    ('client_info', {
        'client', 'company', 'facility', 'plant', 'site', 'operation',
        'corp', 'inc', 'llc', 'manufacturer', 'testcorp', 'acme',
        'customer', 'account',
    }),
    ('scheduling', {
        'schedule', 'shift', 'rotation', 'dupont', '2-2-3', '4-3',
        'hours', '8-hour', '12-hour', 'crew', 'coverage', 'pattern',
        'days off', 'weekend', 'overtime', 'staffing', 'cyclical',
    }),
    ('user_preferences', {
        'prefer', 'format', 'style', 'template', 'layout', 'present',
        'excel', 'powerpoint', 'report', 'how you', 'the way',
    }),
    ('project_context', {
        'project', 'engagement', 'phase', 'milestone', 'deliverable',
        'proposal', 'scope', 'contract', 'kickoff', 'timeline',
    }),
    ('routing_performance', {
        'gpt', 'deepseek', 'gemini', 'opus', 'sonnet', 'model', 'ai',
        'specialist', 'which ai', 'better', 'faster',
    }),
    ('system_performance', {
        'slow', 'fast', 'error', 'fail', 'crash', 'timeout', 'latency',
        'performance', 'memory', 'database',
    }),
    ('task_patterns', {
        'how do i', 'how to', 'what is', 'explain', 'describe',
        'question', 'ask',
    }),
]


# ============================================================================
# PUBLIC API
# ============================================================================

def retrieve_relevant_memories(user_request, limit=10):
    """
    Search the memory store for memories relevant to the user's request.

    Uses three strategies and deduplicates results:
      Strategy 1: Keyword search — meaningful words from request text
      Strategy 2: Category match — memories from the detected topic category
      Strategy 3: Recent procedural — always pull the N most recent procedural
                  memories (how-to-work-better knowledge, always useful)

    Results are sorted by relevance_score descending, then by recency.
    Returns at most `limit` memories.

    Args:
        user_request (str): The user's original request text
        limit (int): Maximum memories to return (default 10, capped at 20)

    Returns:
        list[dict]: Memory dicts with keys:
            id, memory_type, category, content, relevance_score,
            source_task_id, created_at, updated_at
        Returns [] on any error — never raises.
    """
    if not user_request or not user_request.strip():
        return []

    try:
        limit = max(1, min(int(limit), 20))
    except (TypeError, ValueError):
        limit = 10

    try:
        return _retrieve(user_request.strip(), limit)
    except Exception as e:
        logger.error(f"retrieve_relevant_memories: unexpected failure: {e}")
        return []


def format_memories_for_prompt(memories):
    """
    Format a list of memory dicts into a text block for AI system prompt injection.

    The block is structured as:
        --- SWARM MEMORY CONTEXT ---
        IMPORTANT: [authoritative framing — do not contradict these facts]
        [RECENT KNOWLEDGE]          <- episodic + semantic memories
        [HOW TO WORK EFFECTIVELY]   <- procedural memories
        --- END MEMORY CONTEXT ---

    The framing explicitly tells the AI that these facts come from persistent
    memory independent of the current conversation, and must NOT be contradicted
    even if the in-session conversation history appears to show the topic was
    never discussed.

    Total output is capped at _MAX_CONTEXT_CHARS characters. If truncation
    is needed, lower-relevance memories are dropped first (list is
    pre-sorted by relevance descending from retrieve_relevant_memories).

    Args:
        memories (list[dict]): Output of retrieve_relevant_memories()

    Returns:
        str: Formatted block ready to append to a system prompt,
             or "" if memories is empty or None.
    """
    if not memories:
        return ""

    try:
        return _format(memories)
    except Exception as e:
        logger.error(f"format_memories_for_prompt: unexpected failure: {e}")
        return ""


# ============================================================================
# INTERNAL IMPLEMENTATION
# ============================================================================

def _retrieve(user_request, limit):
    """Core retrieval logic — called inside try/except by retrieve_relevant_memories."""
    from memory.memory_store import (
        search_memories,
        get_memories_by_type,
        get_memories_by_category,
    )

    seen_ids = set()
    candidates = []

    # ------------------------------------------------------------------
    # Strategy 1: Keyword search
    # Extract meaningful tokens (3+ chars, not stop words) and search.
    # ------------------------------------------------------------------
    keywords = _extract_keywords(user_request)
    if keywords:
        keyword_query = ' '.join(keywords[:8])  # cap at 8 terms
        kw_results = search_memories(keyword_query, limit=limit)
        for mem in kw_results:
            if mem.get('id') not in seen_ids:
                seen_ids.add(mem['id'])
                candidates.append(mem)

    # ------------------------------------------------------------------
    # Strategy 2: Category match
    # Detect the topic category of the request and pull high-quality
    # memories from that category.
    # ------------------------------------------------------------------
    detected_category = _detect_category(user_request)
    if detected_category:
        cat_results = get_memories_by_category(detected_category, limit=limit)
        for mem in cat_results:
            if mem.get('id') not in seen_ids:
                seen_ids.add(mem['id'])
                candidates.append(mem)

    # ------------------------------------------------------------------
    # Strategy 3: Recent procedural memories
    # Always pull the most recent procedural memories — they carry
    # "how to work better" knowledge that is useful for every request.
    # ------------------------------------------------------------------
    procedural_results = get_memories_by_type('procedural', limit=_PROCEDURAL_ALWAYS_PULL)
    for mem in procedural_results:
        if mem.get('id') not in seen_ids:
            seen_ids.add(mem['id'])
            candidates.append(mem)

    if not candidates:
        return []

    # ------------------------------------------------------------------
    # Sort: relevance_score descending, then created_at descending
    # ------------------------------------------------------------------
    def sort_key(m):
        score = float(m.get('relevance_score') or 0)
        # Parse ISO date string for secondary sort
        created = m.get('created_at') or ''
        return (score, created)

    candidates.sort(key=sort_key, reverse=True)

    return candidates[:limit]


def _format(memories):
    """Core formatting logic — called inside try/except by format_memories_for_prompt."""
    knowledge_lines = []   # episodic + semantic
    procedural_lines = []  # procedural

    for mem in memories:
        content = (mem.get('content') or '').strip()
        if not content:
            continue

        memory_type = (mem.get('memory_type') or 'episodic').strip()

        # Format the date as "Month DD" e.g. "March 5"
        date_label = _format_date(mem.get('created_at', ''))

        line = f"- {content}"
        if date_label:
            line += f" (learned {date_label})"

        if memory_type == 'procedural':
            procedural_lines.append(line)
        else:
            knowledge_lines.append(line)

    # If nothing to show, return empty string (no empty section headers)
    if not knowledge_lines and not procedural_lines:
        return ""

    # Build the block
    # =========================================================================
    # FRAMING (updated March 07, 2026 Pass 2):
    # Explicit language telling the AI these facts are authoritative and
    # independent of the current conversation history. Prevents the AI from
    # saying "this was never discussed" when the in-session history is empty.
    # =========================================================================
    parts = [
        "--- SWARM MEMORY CONTEXT ---",
        "IMPORTANT: The following facts come from your persistent memory system -- "
        "they are things YOU ALREADY KNOW from prior sessions, completely independent "
        "of the current conversation. Do NOT say these topics were never discussed. "
        "Do NOT say you have no memory of them. Treat these as established facts "
        "you possess. Use them naturally without mentioning the memory system "
        "unless directly asked.",
        "",
    ]

    if knowledge_lines:
        parts.append("[RECENT KNOWLEDGE]")
        parts.extend(knowledge_lines)
        parts.append("")

    if procedural_lines:
        parts.append("[HOW TO WORK EFFECTIVELY]")
        parts.extend(procedural_lines)
        parts.append("")

    parts.append("--- END MEMORY CONTEXT ---")

    result = "\n".join(parts)

    # Enforce character budget — truncate from the end of the knowledge lines
    # (procedural lines are preserved as they are always high value)
    if len(result) > _MAX_CONTEXT_CHARS:
        result = _truncate_to_budget(knowledge_lines, procedural_lines)

    return result


def _truncate_to_budget(knowledge_lines, procedural_lines):
    """
    Rebuild the memory block staying under _MAX_CONTEXT_CHARS.
    Drops knowledge lines from the end (lowest relevance, since list is
    sorted by relevance desc) until it fits. Procedural lines are never dropped.
    Returns "" if even the header + procedural lines exceed the budget.
    """
    # Try progressively fewer knowledge lines
    for cutoff in range(len(knowledge_lines), -1, -1):
        trimmed_knowledge = knowledge_lines[:cutoff]
        parts = [
            "--- SWARM MEMORY CONTEXT ---",
            "IMPORTANT: The following facts come from your persistent memory system -- "
            "they are things YOU ALREADY KNOW from prior sessions, completely independent "
            "of the current conversation. Do NOT say these topics were never discussed. "
            "Do NOT say you have no memory of them. Treat these as established facts "
            "you possess. Use them naturally without mentioning the memory system "
            "unless directly asked.",
            "",
        ]
        if trimmed_knowledge:
            parts.append("[RECENT KNOWLEDGE]")
            parts.extend(trimmed_knowledge)
            parts.append("")
        if procedural_lines:
            parts.append("[HOW TO WORK EFFECTIVELY]")
            parts.extend(procedural_lines)
            parts.append("")
        parts.append("--- END MEMORY CONTEXT ---")

        candidate = "\n".join(parts)
        if len(candidate) <= _MAX_CONTEXT_CHARS:
            return candidate

    return ""


def _extract_keywords(text):
    """
    Extract meaningful search terms from request text.
    Filters stop words and short tokens. Returns list of lowercase strings.
    """
    _STOP_WORDS = frozenset({
        'the', 'and', 'for', 'are', 'was', 'has', 'had', 'have', 'not',
        'but', 'you', 'all', 'can', 'any', 'how', 'who', 'what', 'when',
        'where', 'why', 'with', 'this', 'that', 'they', 'from', 'will',
        'would', 'should', 'could', 'been', 'being', 'does', 'did', 'its',
        'our', 'your', 'their', 'about', 'into', 'than', 'then', 'also',
        'more', 'some', 'such', 'like', 'just', 'very', 'each', 'both',
        'only', 'same', 'over', 'most', 'much', 'even', 'here', 'there',
        'which', 'these', 'those', 'give', 'get', 'use', 'let', 'per',
    })

    tokens = []
    for token in text.lower().split():
        clean = token.strip('.,!?;:\'"()[]{}')
        if len(clean) >= 3 and clean not in _STOP_WORDS:
            tokens.append(clean)

    return tokens


def _detect_category(text):
    """
    Detect the best-matching VALID_CATEGORY for the request text.
    Returns the category string, or None if no strong match.
    """
    text_lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return category
    return None


def _format_date(created_at_str):
    """
    Parse an ISO datetime string and return a short human-readable date.
    e.g. "2026-03-05T14:22:11.123456" -> "March 5"
    Returns "" on any parse failure.
    """
    if not created_at_str:
        return ""
    try:
        # Take first 10 chars: "YYYY-MM-DD"
        date_part = str(created_at_str)[:10]
        dt = datetime.strptime(date_part, "%Y-%m-%d")
        return dt.strftime("%B %-d")   # "March 5" on Linux
    except Exception:
        try:
            # Fallback: just return YYYY-MM-DD
            return str(created_at_str)[:10]
        except Exception:
            return ""


# I did no harm and this file is not truncated
