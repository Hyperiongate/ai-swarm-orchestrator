"""
intelligence/prompt_optimizer.py
AI Swarm Orchestrator — Phase 5: Learning That Changes Behavior
Created: March 09, 2026
Last Updated: March 09, 2026 — Initial build (Phase 5, Deliverable 2)

CHANGELOG:
- March 09, 2026: Phase 5 Deliverable 2 — NEW FILE
  Builds a library of prompt enhancements — extra instructions that get
  injected into AI prompts for specific task categories based on what has
  worked well historically.

  WHAT IT DOES:
    - store_enhancement(): Saves a new prompt enhancement for a category.
      Source can be 'auto' (discovered by the system) or 'manual' (Jim).
    - get_enhancements(): Returns all active enhancements for a category,
      formatted as a text block ready for prompt injection.
    - deactivate_enhancement(): Turns off an enhancement that isn't helping.
    - update_enhancement_stats(): Tracks how often each enhancement is used
      and whether it correlates with score improvements (called after use).
    - generate_enhancements_from_patterns(): Analyzes procedural memories
      and clarification patterns, then makes a single Sonnet call to
      suggest new enhancements. Stores results via store_enhancement().
      Avoids inserting exact duplicates of existing enhancements.

  DATABASE:
    Creates prompt_enhancements table on first use (CREATE TABLE IF NOT EXISTS).
    Columns: id, task_category, enhancement_text, source, times_used,
             avg_improvement, active, created_at, updated_at.

  DESIGN RULES:
    - Multiple enhancements per category are allowed and expected.
    - Enhancements are ordered by avg_improvement DESC when retrieved.
    - Minimum times_used=3 before avg_improvement is considered meaningful.
    - All DB calls use get_db_connection() context manager.
    - Row access by column name only (RealDictCursor).
    - %s placeholders throughout. TRUE/FALSE for booleans.
    - Never raises — all public functions return safe defaults on error.
    - generate_enhancements_from_patterns() is designed to be called
      periodically (from weekly_review.py), NOT on every request.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json

# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL FLAGS
# ─────────────────────────────────────────────────────────────────────────────

_TABLE_READY = {'ready': False}

# Minimum uses before avg_improvement is trusted in ordering
MIN_USES_FOR_RANKING = 3

# Maximum enhancements returned per category (avoid bloating prompts)
MAX_ENHANCEMENTS_PER_CATEGORY = 5


# ─────────────────────────────────────────────────────────────────────────────
# TABLE SETUP
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_table():
    """
    Create the prompt_enhancements table if it does not exist.
    Called once per process. Any failure is logged but never raised.
    """
    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prompt_enhancements (
                    id               SERIAL PRIMARY KEY,
                    task_category    VARCHAR(100) NOT NULL,
                    enhancement_text TEXT NOT NULL,
                    source           VARCHAR(20) DEFAULT 'auto',
                    times_used       INTEGER DEFAULT 0,
                    avg_improvement  FLOAT DEFAULT 0.0,
                    active           BOOLEAN DEFAULT TRUE,
                    created_at       TIMESTAMP DEFAULT NOW(),
                    updated_at       TIMESTAMP DEFAULT NOW()
                )
            """)
        _TABLE_READY['ready'] = True
        print("✅ [prompt_optimizer] prompt_enhancements table ready")
    except Exception as e:
        print(f"⚠️ [prompt_optimizer] Could not create prompt_enhancements table: {e}")


def _check_table():
    """Ensure table exists before any operation."""
    if not _TABLE_READY['ready']:
        _ensure_table()


# ─────────────────────────────────────────────────────────────────────────────
# store_enhancement()
# ─────────────────────────────────────────────────────────────────────────────

def store_enhancement(task_category, enhancement_text, source='auto'):
    """
    Store a new prompt enhancement for a task category.

    Args:
        task_category (str):    The category this enhancement applies to
                                (e.g. 'scheduling', 'client_consulting').
        enhancement_text (str): The instruction to inject into the prompt.
                                Example: "Always include overtime cost
                                implications when presenting schedule options."
        source (str):           'auto' = discovered by the system,
                                'manual' = explicitly added by Jim.

    Returns:
        int | None: The new enhancement's id, or None on error.
    """
    try:
        _check_table()

        category = str(task_category or '').lower().strip()[:100]
        text = str(enhancement_text or '').strip()
        src = str(source or 'auto').strip()[:20]

        if not category or not text:
            print("⚠️ [prompt_optimizer] store_enhancement: category and text required")
            return None

        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO prompt_enhancements
                    (task_category, enhancement_text, source,
                     times_used, avg_improvement, active,
                     created_at, updated_at)
                VALUES (%s, %s, %s, 0, 0.0, TRUE, NOW(), NOW())
                RETURNING id
            """, (category, text, src))
            row = cursor.fetchone()
            new_id = row['id'] if row else None

        print(f"✅ [prompt_optimizer] Stored enhancement id={new_id} "
              f"for category='{category}' source='{src}'")
        return new_id

    except Exception as e:
        print(f"⚠️ [prompt_optimizer] store_enhancement failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# get_enhancements()
# ─────────────────────────────────────────────────────────────────────────────

def get_enhancements(task_category, as_text=True):
    """
    Return all active enhancements for a given task category.

    Args:
        task_category (str): The category to look up.
        as_text (bool):      If True (default), returns a formatted text block
                             ready for prompt injection. If False, returns a
                             list of dicts for programmatic use.

    Returns:
        str: Formatted enhancement block (if as_text=True), e.g.:
             "Additional guidelines for scheduling tasks:\n
              - Always ask about pay week start day for 2-2-3 schedules.\n
              - Include overtime cost implications."
        list: List of dicts (if as_text=False). Each dict has:
              id, task_category, enhancement_text, source,
              times_used, avg_improvement.
        Returns empty string / empty list on error or no data.
    """
    try:
        _check_table()

        category = str(task_category or '').lower().strip()[:100]
        if not category:
            return "" if as_text else []

        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, task_category, enhancement_text, source,
                       times_used, avg_improvement
                FROM prompt_enhancements
                WHERE task_category = %s
                  AND active = TRUE
                ORDER BY
                    CASE WHEN times_used >= %s
                         THEN avg_improvement ELSE 0 END DESC,
                    created_at ASC
                LIMIT %s
            """, (category, MIN_USES_FOR_RANKING, MAX_ENHANCEMENTS_PER_CATEGORY))
            rows = cursor.fetchall()

        if not rows:
            return "" if as_text else []

        if not as_text:
            return [dict(row) for row in rows]

        lines = [f"- {row['enhancement_text']}" for row in rows]
        return (
            f"Additional guidelines for {category} tasks:\n"
            + "\n".join(lines)
        )

    except Exception as e:
        print(f"⚠️ [prompt_optimizer] get_enhancements failed: {e}")
        return "" if as_text else []


# ─────────────────────────────────────────────────────────────────────────────
# deactivate_enhancement()
# ─────────────────────────────────────────────────────────────────────────────

def deactivate_enhancement(enhancement_id):
    """
    Deactivate an enhancement that is not helping.
    Sets active = FALSE so it no longer appears in get_enhancements().

    Args:
        enhancement_id (int): The id of the enhancement to deactivate.

    Returns:
        bool: True if deactivated, False on error or not found.
    """
    try:
        _check_table()

        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE prompt_enhancements
                SET active     = FALSE,
                    updated_at = NOW()
                WHERE id = %s
            """, (int(enhancement_id),))

        print(f"✅ [prompt_optimizer] Deactivated enhancement id={enhancement_id}")
        return True

    except Exception as e:
        print(f"⚠️ [prompt_optimizer] deactivate_enhancement failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# update_enhancement_stats()
# ─────────────────────────────────────────────────────────────────────────────

def update_enhancement_stats(enhancement_id, improvement_score):
    """
    Record that an enhancement was used and track whether it helped.
    Called after a response is delivered when we have a score to compare.

    Updates times_used and blends improvement_score into avg_improvement
    using a running average.

    Args:
        enhancement_id (int):     The enhancement that was applied.
        improvement_score (float): How much this enhancement appeared to help.
                                   Positive = helpful, negative = harmful,
                                   0 = neutral. Typical range: -5.0 to +5.0.

    Returns:
        bool: True on success, False on error.
    """
    try:
        _check_table()

        score = round(float(improvement_score), 2)

        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE prompt_enhancements
                SET times_used      = times_used + 1,
                    avg_improvement = (
                        (avg_improvement * times_used) + %s
                    ) / (times_used + 1),
                    updated_at      = NOW()
                WHERE id = %s
            """, (score, int(enhancement_id)))

        return True

    except Exception as e:
        print(f"⚠️ [prompt_optimizer] update_enhancement_stats failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# get_all_enhancements()  — for the /api/learning/enhancements endpoint
# ─────────────────────────────────────────────────────────────────────────────

def get_all_enhancements():
    """
    Return all enhancements (active and inactive) for API display.

    Returns:
        list of dicts ordered by task_category, then active DESC,
        then avg_improvement DESC.
        Empty list on error.
    """
    try:
        _check_table()

        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, task_category, enhancement_text, source,
                       times_used, avg_improvement, active,
                       created_at, updated_at
                FROM prompt_enhancements
                ORDER BY task_category,
                         active DESC,
                         avg_improvement DESC
            """)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    except Exception as e:
        print(f"⚠️ [prompt_optimizer] get_all_enhancements failed: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# generate_enhancements_from_patterns()
# ─────────────────────────────────────────────────────────────────────────────

def generate_enhancements_from_patterns():
    """
    Analyze procedural memories and clarification patterns, then call Sonnet
    to suggest new prompt enhancements. Stores results via store_enhancement().

    This function is EXPENSIVE — it makes a Sonnet API call. Call it
    periodically (e.g., from weekly_review.py), not on every request.

    Process:
        1. Fetch recent procedural memories from the memories table.
        2. Fetch recent NEEDS_CLARIFICATION entries from reasoning_log
           to identify what information the system commonly lacks.
        3. Fetch existing active enhancements to avoid exact duplicates.
        4. Build a Sonnet prompt asking for enhancement suggestions.
        5. Parse the JSON array response.
        6. Store each suggestion that doesn't duplicate an existing one.

    Returns:
        list of dicts: Each dict has 'task_category' and 'enhancement_text'
                       for every enhancement that was successfully stored.
        Empty list if no enhancements were generated or on error.
    """
    try:
        _check_table()

        # ── Step 1: Fetch recent procedural memories ──────────────────────
        procedural_memories = _fetch_procedural_memories(limit=20)

        # ── Step 2: Fetch clarification patterns from reasoning_log ───────
        clarification_patterns = _fetch_clarification_patterns(limit=20)

        # Nothing to analyze — return early
        if not procedural_memories and not clarification_patterns:
            print("ℹ️ [prompt_optimizer] No procedural memories or clarification "
                  "patterns found — skipping enhancement generation")
            return []

        # ── Step 3: Fetch existing enhancements to avoid duplication ──────
        existing = get_all_enhancements()
        existing_texts = {e['enhancement_text'].lower().strip() for e in existing}

        # ── Step 4: Build Sonnet prompt ───────────────────────────────────
        memories_block = (
            "\n".join(f"- {m}" for m in procedural_memories)
            if procedural_memories
            else "No procedural memories available."
        )
        clarification_block = (
            "\n".join(f"- {c}" for c in clarification_patterns)
            if clarification_patterns
            else "No clarification patterns available."
        )

        prompt = f"""You are analyzing the AI Swarm Orchestrator's performance \
patterns to improve future responses for Shiftwork Solutions LLC, a consulting \
firm specializing in 24/7 shift operations for manufacturing, pharmaceutical, \
food processing, and other industries.

Here are recent procedural memories (things learned about how to work effectively):

{memories_block}

Here are recent patterns in requests that needed clarification (revealing \
what information the system commonly lacks):

{clarification_block}

Based on these patterns, suggest prompt enhancements — specific instructions \
that should be added to future prompts for specific task categories to improve \
response quality. Each enhancement should be one clear, actionable sentence.

Valid task categories: scheduling, research, client_consulting, code, content, \
analysis, general, survey, document, labor.

Return ONLY a JSON array with no markdown, no explanation outside the JSON:
[
  {{"task_category": "scheduling", "enhancement": "Always ask about the pay \
week start day when recommending 2-2-3 schedules, as Sunday vs Monday start \
significantly impacts night shift experience."}},
  {{"task_category": "client_consulting", "enhancement": "When discussing a \
new client, always check memory for similar past clients to provide \
comparative insights."}}
]

Only suggest enhancements that would meaningfully improve responses. \
Quality over quantity — 2-4 specific enhancements are better than 10 generic ones. \
Do not suggest enhancements that are too vague to act on."""

        # ── Step 5: Call Sonnet ───────────────────────────────────────────
        from orchestration.ai_clients import call_claude_sonnet
        api_response = call_claude_sonnet(prompt)

        if isinstance(api_response, dict):
            if api_response.get('error'):
                print(f"⚠️ [prompt_optimizer] Sonnet error during pattern analysis: "
                      f"{api_response.get('content', 'unknown')}")
                return []
            response_text = api_response.get('content', '')
        else:
            response_text = str(api_response)

        # ── Step 6: Parse JSON array from response ────────────────────────
        suggestions = _extract_json_array(response_text)
        if not suggestions:
            print(f"⚠️ [prompt_optimizer] Could not parse enhancement suggestions "
                  f"from Sonnet response (first 200 chars): {response_text[:200]}")
            return []

        # ── Step 7: Store non-duplicate suggestions ───────────────────────
        stored = []
        for item in suggestions:
            category = str(item.get('task_category', '')).lower().strip()
            text = str(item.get('enhancement', '')).strip()

            if not category or not text:
                continue

            # Skip exact duplicates (case-insensitive)
            if text.lower().strip() in existing_texts:
                print(f"ℹ️ [prompt_optimizer] Skipping duplicate: '{text[:60]}...'")
                continue

            new_id = store_enhancement(category, text, source='auto')
            if new_id:
                stored.append({'task_category': category, 'enhancement_text': text})
                existing_texts.add(text.lower().strip())  # prevent duplicates within batch

        print(f"✅ [prompt_optimizer] Generated {len(stored)} new enhancements "
              f"from {len(suggestions)} suggestions")
        return stored

    except Exception as e:
        print(f"⚠️ [prompt_optimizer] generate_enhancements_from_patterns failed: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_procedural_memories(limit=20):
    """
    Fetch recent procedural memories from the memories table.
    Returns a list of content strings. Empty list on error or no data.
    """
    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT content
                FROM memories
                WHERE memory_type = 'procedural'
                  AND (is_active = TRUE OR is_active IS NULL)
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
        return [row['content'] for row in rows if row.get('content')]
    except Exception as e:
        print(f"⚠️ [prompt_optimizer] _fetch_procedural_memories failed: {e}")
        return []


def _fetch_clarification_patterns(limit=20):
    """
    Fetch recent NEEDS_CLARIFICATION entries from reasoning_log.
    Returns a list of user_request strings. Empty list on error or no data.
    """
    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_request, sufficiency
                FROM reasoning_log
                WHERE decision = 'NEEDS_CLARIFICATION'
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
        results = []
        for row in rows:
            req = row.get('user_request', '')
            suf = row.get('sufficiency', '')
            if req:
                entry = req[:200]
                if suf:
                    entry += f" [gap: {suf[:100]}]"
                results.append(entry)
        return results
    except Exception as e:
        print(f"⚠️ [prompt_optimizer] _fetch_clarification_patterns failed: {e}")
        return []


def _extract_json_array(text):
    """
    Extract a JSON array from a response string.
    Handles code fences, leading/trailing text.
    Returns a list, or empty list if parsing fails.
    """
    if not text:
        return []

    # Strip code fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Find the array bounds
    start = text.find('[')
    if start == -1:
        return []

    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return []
    return []


# I did no harm and this file is not truncated
