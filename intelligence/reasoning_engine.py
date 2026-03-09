"""
intelligence/reasoning_engine.py
AI Swarm Orchestrator — Phase 4: The Reasoning Loop
Created: March 08, 2026
Last Updated: March 09, 2026 — Phase 5 routing_insights + commit fixes

CHANGELOG:
- March 08, 2026: Phase 4 initial build
  NEW FILE. Replaces the straight-line classify-and-route pattern with a
  single Sonnet call that reasons through the request before acting.

- March 09, 2026: Phase 5 additions + bug fixes
  1. Added routing_insights="" parameter to _build_reasoning_prompt() and
     reason_about_request(). When routing_insights is non-empty, a ROUTING
     INTELLIGENCE block is injected into the prompt so the engine can factor
     in which models have historically performed best per category.

  2. BUG FIX — Missing conn.commit() in write operations:
     _ensure_reasoning_log_table(): Added commit() after CREATE TABLE.
     _log_reasoning_decision(): Added commit() after INSERT.
     Root cause same as routing_optimizer: psycopg2 does not auto-commit;
     the get_db_connection() context manager closes without committing,
     silently rolling back all writes.

  All Phase 4 logic, fallback behavior, and logging structure unchanged.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json
import time


# =============================================================================
# JSON EXTRACTOR
# =============================================================================

def _extract_json_object(text):
    """
    Extract the first complete JSON object from a response string.
    Handles code fences, trailing text, and nested braces inside strings.
    Returns the JSON string, or None if no complete object found.
    """
    if not text:
        return None
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    start = text.find('{')
    if start == -1:
        return None
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
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


# =============================================================================
# REASONING PROMPT BUILDER
# =============================================================================

def _build_reasoning_prompt(user_request, memories, capabilities_manifest,
                             kb_context, conversation_history=None,
                             routing_insights=""):
    """
    Build the single comprehensive prompt that drives the 5-step reasoning chain.

    Args:
        routing_insights (str): Phase 5 routing intelligence string. When
            non-empty, injected as a ROUTING INTELLIGENCE block so the
            reasoning engine can bias its routing decision toward historically
            better-performing models for this task category.
    """
    history_block = ""
    if conversation_history and len(conversation_history) > 1:
        history_block = "\n\nCONVERSATION HISTORY (most recent messages):\n"
        for msg in conversation_history[-4:]:
            role_label = "User" if msg.get('role') == 'user' else "Assistant"
            content = msg.get('content', '')
            preview = content[:300] + '...' if len(content) > 300 else content
            history_block += f"{role_label}: {preview}\n"

    memory_block = ""
    if memories:
        memory_block = f"\n\nPERSISTENT MEMORY CONTEXT:\n{memories}\n"

    kb_block = ""
    if kb_context:
        kb_block = f"\n\nKNOWLEDGE BASE CONTEXT:\n{kb_context}\n"

    caps_block = ""
    if capabilities_manifest:
        caps_block = f"\n\n{capabilities_manifest}\n"

    routing_block = ""
    if routing_insights and routing_insights.strip():
        routing_block = (
            f"\n\nROUTING INTELLIGENCE (from past performance data):\n"
            f"{routing_insights}\n"
            f"Use this to inform your routing decision in Step 4. "
            f"If a preferred model is indicated for this task type, "
            f"factor that into your decision.\n"
        )

    prompt = f"""{caps_block}{memory_block}{kb_block}{routing_block}{history_block}

A user has sent the following request to the AI Swarm Orchestrator for \
Shiftwork Solutions LLC:

REQUEST: {user_request}

Before responding, reason through this request step by step:

STEP 1 — MEMORY CHECK:
Do you have any relevant memories about this request? If the user mentions \
a client, project, person, or topic you have memories about, note what you \
already know. If you have no relevant memories, say so.

STEP 2 — SUFFICIENCY CHECK:
Do you have enough information to answer this request well? Consider:
- Is the request specific enough to act on?
- Are there critical details missing (e.g., number of crews, shift length, \
industry type)?
- Would asking a clarifying question produce a significantly better answer?
If the request is clear and actionable, proceed. If critical information \
is missing, note what questions you would ask.

STEP 3 — TOOL CHECK:
Does this request require an internal tool rather than a text response?
- If the user asks to GENERATE a schedule → needs schedule_generator tool
- If the user asks about recent news, regulations, or current events → \
needs research_agent
- If the user asks a general shift work question → knowledge base context \
is sufficient for a text response
- If no special tool is needed, a text response is appropriate

STEP 4 — ROUTING DECISION:
Based on the above, choose exactly one:
- RESPOND_DIRECTLY: Answer well with a text response using your knowledge, \
memories, and the knowledge base context provided. Include your FULL \
response in the "response" field.
- NEEDS_CLARIFICATION: Critical information is missing. Return specific \
questions to ask the user. Do NOT attempt to answer yet.
- USE_TOOL: This request requires a specific tool. Specify tool_name and \
extract tool_parameters from the request.
- ESCALATE_TO_OPUS: This is a complex, multi-part strategic request \
requiring deep analysis (e.g., full implementation plan, financial model, \
multi-phase change management across a large workforce).

STEP 5 — RETURN JSON:
Return your reasoning and decision as JSON with this EXACT structure. \
Return ONLY valid JSON. No markdown, no explanation outside the JSON.

{{
  "reasoning": {{
    "memory_check": "What you found in memory, or 'no relevant memories'",
    "sufficiency": "Whether you have enough info and what is missing if not",
    "tool_check": "Whether a tool is needed and which one, or 'text response sufficient'",
    "conflicts": "Any contradictions with existing knowledge, or 'none detected'"
  }},
  "decision": "RESPOND_DIRECTLY or NEEDS_CLARIFICATION or USE_TOOL or ESCALATE_TO_OPUS",
  "tool_name": "schedule_generator or research_agent or null",
  "tool_parameters": {{ "shift_length": 12, "pattern_key": "2-2-3" }} or null,
  "clarification_questions": ["question 1", "question 2"] or null,
  "response": "If RESPOND_DIRECTLY, your complete response here. Otherwise null."
}}"""

    return prompt


# =============================================================================
# MAIN REASONING FUNCTION
# =============================================================================

def reason_about_request(user_request, memories="", capabilities_manifest="",
                         kb_context="", conversation_history=None,
                         routing_insights=""):
    """
    Phase 4/5 reasoning engine. Makes ONE Sonnet call that reasons through
    the request and returns a structured decision.

    Args:
        user_request (str): The user's message.
        memories (str): Formatted memory context from memory_retriever.
        capabilities_manifest (str): Live capabilities manifest from Phase 3.
        kb_context (str): Knowledge base context from check_knowledge_base_unified.
        conversation_history (list|None): Recent conversation messages.
        routing_insights (str): Phase 5 routing intelligence. When non-empty,
            injected into the prompt to bias routing toward historically
            better-performing models. Empty string = no effect on Phase 4 behavior.

    Returns:
        dict with keys: decision, reasoning, tool_name, tool_parameters,
            clarification_questions, response, execution_time_ms, error.
        decision is one of: RESPOND_DIRECTLY / NEEDS_CLARIFICATION /
            USE_TOOL / ESCALATE_TO_OPUS / FALLBACK.
        Never raises. FALLBACK means caller should use analyze_task_with_sonnet().
    """
    start_ms = time.time()

    try:
        from orchestration.ai_clients import call_claude_sonnet

        prompt = _build_reasoning_prompt(
            user_request=user_request,
            memories=memories,
            capabilities_manifest=capabilities_manifest,
            kb_context=kb_context,
            conversation_history=conversation_history,
            routing_insights=routing_insights,
        )

        print(f"🧠 [reasoning_engine] Calling Sonnet for reasoning "
              f"({len(prompt)} char prompt)...")

        api_response = call_claude_sonnet(prompt)

        if isinstance(api_response, dict):
            if api_response.get('error'):
                raise RuntimeError(
                    f"Sonnet API error: {api_response.get('content', 'unknown')}"
                )
            response_text = api_response.get('content', '')
        else:
            response_text = str(api_response)

        json_str = _extract_json_object(response_text)
        if json_str is None:
            raise ValueError(
                f"No JSON object found in Sonnet response "
                f"(first 200 chars): {response_text[:200]}"
            )

        parsed = json.loads(json_str)

        valid_decisions = {
            'RESPOND_DIRECTLY', 'NEEDS_CLARIFICATION',
            'USE_TOOL', 'ESCALATE_TO_OPUS'
        }
        decision = parsed.get('decision', '').strip().upper()
        if decision not in valid_decisions:
            raise ValueError(
                f"Invalid decision value: '{decision}'. "
                f"Expected one of {valid_decisions}"
            )

        execution_ms = int((time.time() - start_ms) * 1000)

        result = {
            'decision': decision,
            'reasoning': parsed.get('reasoning', {
                'memory_check': 'not provided',
                'sufficiency': 'not provided',
                'tool_check': 'not provided',
                'conflicts': 'none detected',
            }),
            'tool_name': parsed.get('tool_name'),
            'tool_parameters': parsed.get('tool_parameters'),
            'clarification_questions': parsed.get('clarification_questions'),
            'response': parsed.get('response'),
            'execution_time_ms': execution_ms,
            'error': None,
        }

        print(f"🧠 [reasoning_engine] Decision: {decision} ({execution_ms}ms)")

        _log_reasoning_decision(user_request, result)

        return result

    except Exception as e:
        execution_ms = int((time.time() - start_ms) * 1000)
        print(f"⚠️ [reasoning_engine] Failed ({execution_ms}ms): {e} — "
              f"returning FALLBACK for original routing")
        return {
            'decision': 'FALLBACK',
            'reasoning': {
                'memory_check': 'reasoning engine failed',
                'sufficiency': 'reasoning engine failed',
                'tool_check': 'reasoning engine failed',
                'conflicts': 'none detected',
            },
            'tool_name': None,
            'tool_parameters': None,
            'clarification_questions': None,
            'response': None,
            'execution_time_ms': execution_ms,
            'error': str(e),
        }


# =============================================================================
# REASONING LOG
# =============================================================================

_TABLE_READY = {'ready': False}


def _ensure_reasoning_log_table():
    """
    Create the reasoning_log table if it does not exist.
    Called once per process. Commits explicitly — psycopg2 does not auto-commit.
    """
    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reasoning_log (
                    id               SERIAL PRIMARY KEY,
                    user_request     TEXT,
                    memory_check     TEXT,
                    sufficiency      TEXT,
                    tool_check       TEXT,
                    conflicts        TEXT,
                    decision         VARCHAR(50),
                    tool_name        VARCHAR(50),
                    response_time_ms INTEGER,
                    error            TEXT,
                    created_at       TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
        _TABLE_READY['ready'] = True
        print("✅ [reasoning_engine] reasoning_log table ready")
    except Exception as e:
        print(f"⚠️ [reasoning_engine] Could not create reasoning_log table: {e}")


def _log_reasoning_decision(user_request, result):
    """
    Store a reasoning decision in the reasoning_log table.
    Non-critical — any failure is silently logged and ignored.
    Commits explicitly — psycopg2 does not auto-commit.
    """
    try:
        if not _TABLE_READY['ready']:
            _ensure_reasoning_log_table()

        from db_engine import get_db_connection
        reasoning = result.get('reasoning', {})

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reasoning_log
                    (user_request, memory_check, sufficiency, tool_check,
                     conflicts, decision, tool_name, response_time_ms, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_request[:500] if user_request else '',
                str(reasoning.get('memory_check', ''))[:500],
                str(reasoning.get('sufficiency', ''))[:500],
                str(reasoning.get('tool_check', ''))[:500],
                str(reasoning.get('conflicts', ''))[:300],
                result.get('decision', 'UNKNOWN')[:50],
                result.get('tool_name', '')[:50] if result.get('tool_name') else None,
                result.get('execution_time_ms', 0),
                result.get('error', '')[:500] if result.get('error') else None,
            ))
            conn.commit()

    except Exception as e:
        print(f"⚠️ [reasoning_engine] Logging failed (non-critical): {e}")


# =============================================================================
# RECENT REASONING LOG RETRIEVAL
# =============================================================================

def get_recent_reasoning_log(limit=10):
    """
    Return the last N reasoning decisions from reasoning_log.
    Returns empty list on any error.
    """
    try:
        limit = max(1, min(50, int(limit)))
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_request, memory_check, sufficiency,
                       tool_check, conflicts, decision, tool_name,
                       response_time_ms, error, created_at
                FROM reasoning_log
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"⚠️ [reasoning_engine] get_recent_reasoning_log failed: {e}")
        return []


# I did no harm and this file is not truncated
