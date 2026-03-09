"""
intelligence/reasoning_engine.py 
AI Swarm Orchestrator — Phase 4: The Reasoning Loop
Created: March 08, 2026
Last Updated: March 08, 2026 — Initial build (Phase 4)

CHANGELOG:
- March 08, 2026: Phase 4 initial build
  NEW FILE. Replaces the straight-line classify-and-route pattern with a
  single Sonnet call that reasons through the request before acting.

  THE REASONING CHAIN (5 steps, one AI call):
    Step 1 — Memory Check: What do we already know about this?
    Step 2 — Sufficiency Check: Do we have enough info to answer well?
    Step 3 — Tool Check: Does this need a tool (schedule generator, research)?
    Step 4 — Routing Decision: RESPOND_DIRECTLY / NEEDS_CLARIFICATION /
              USE_TOOL / ESCALATE_TO_OPUS
    Step 5 — Post-response logging: decision stored in reasoning_log table

  PERFORMANCE: ONE Sonnet call total. If decision == RESPOND_DIRECTLY, the
  response is already in the JSON — no second AI call needed.

  FALLBACK: If the reasoning call fails for any reason (API error, bad JSON,
  timeout), returns a FALLBACK dict. The caller (orchestration_handler.py)
  detects FALLBACK and routes through the original analyze_task_with_sonnet()
  path. The system NEVER breaks because of this module.

  LOGGING: Every reasoning decision is stored in the reasoning_log table.
  Table is auto-created on first use if missing. Failure to log never
  breaks the response path.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json
import time

# =============================================================================
# JSON EXTRACTOR (same logic as task_analysis.py _extract_json_object)
# Handles trailing text, fenced JSON, nested braces in strings.
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
                             kb_context, conversation_history=None):
    """
    Build the single comprehensive prompt that drives the 5-step reasoning chain.
    All context is assembled here into one structured prompt.
    """
    # --- Conversation history block ---
    history_block = ""
    if conversation_history and len(conversation_history) > 1:
        history_block = "\n\nCONVERSATION HISTORY (most recent messages):\n"
        for msg in conversation_history[-4:]:  # last 4 messages for context
            role_label = "User" if msg.get('role') == 'user' else "Assistant"
            content = msg.get('content', '')
            preview = content[:300] + '...' if len(content) > 300 else content
            history_block += f"{role_label}: {preview}\n"

    # --- Memory block ---
    memory_block = ""
    if memories:
        memory_block = f"\n\nPERSISTENT MEMORY CONTEXT:\n{memories}\n"

    # --- Knowledge base block ---
    kb_block = ""
    if kb_context:
        kb_block = f"\n\nKNOWLEDGE BASE CONTEXT:\n{kb_context}\n"

    # --- Capabilities block ---
    caps_block = ""
    if capabilities_manifest:
        caps_block = f"\n\n{capabilities_manifest}\n"

    prompt = f"""{caps_block}{memory_block}{kb_block}{history_block}

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
                         kb_context="", conversation_history=None):
    """
    Phase 4 reasoning engine. Makes ONE Sonnet call that reasons through
    the request and returns a structured decision.

    Args:
        user_request (str): The user's message.
        memories (str): Formatted memory context from memory_retriever.
        capabilities_manifest (str): Live capabilities manifest from Phase 3.
        kb_context (str): Knowledge base context from check_knowledge_base_unified.
        conversation_history (list|None): Recent conversation messages.

    Returns:
        dict: Always returns a dict. Key fields:
            'decision': one of RESPOND_DIRECTLY / NEEDS_CLARIFICATION /
                        USE_TOOL / ESCALATE_TO_OPUS / FALLBACK
            'reasoning': dict with memory_check, sufficiency, tool_check, conflicts
            'tool_name': str or None
            'tool_parameters': dict or None
            'clarification_questions': list or None
            'response': str or None (populated for RESPOND_DIRECTLY)
            'execution_time_ms': int
            'error': str or None (populated on FALLBACK)

    Never raises. Always returns a usable dict. FALLBACK means the caller
    should use the original analyze_task_with_sonnet() path.
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

        # Validate decision field
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

        print(f"🧠 [reasoning_engine] Decision: {decision} "
              f"({execution_ms}ms)")

        # Log the decision (non-blocking, non-critical)
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
# REASONING LOG — stored in PostgreSQL reasoning_log table
# Table is auto-created on first use. Logging failure never breaks anything.
# =============================================================================

def _ensure_reasoning_log_table():
    """
    Create the reasoning_log table if it does not exist.
    Uses PostgreSQL syntax. Called once per process (cached after first run).
    """
    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reasoning_log (
                    id SERIAL PRIMARY KEY,
                    user_request TEXT,
                    memory_check TEXT,
                    sufficiency TEXT,
                    tool_check TEXT,
                    conflicts TEXT,
                    decision VARCHAR(50),
                    tool_name VARCHAR(50),
                    response_time_ms INTEGER,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
        _TABLE_READY['ready'] = True
        print("✅ [reasoning_engine] reasoning_log table ready")
    except Exception as e:
        print(f"⚠️ [reasoning_engine] Could not create reasoning_log table: {e}")


# Module-level flag so we only run CREATE TABLE IF NOT EXISTS once per process
_TABLE_READY = {'ready': False}


def _log_reasoning_decision(user_request, result):
    """
    Store a reasoning decision in the reasoning_log table.
    Completely non-critical — any failure is silently logged and ignored.
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
        # Log to console only — never raise, never affect the caller
        print(f"⚠️ [reasoning_engine] Logging failed (non-critical): {e}")


# =============================================================================
# RECENT REASONING LOG RETRIEVAL
# Called by GET /api/reasoning/recent endpoint (added in orchestration_handler)
# =============================================================================

def get_recent_reasoning_log(limit=10):
    """
    Return the last N reasoning decisions from reasoning_log.

    Args:
        limit (int): Number of records to return (1–50).

    Returns:
        list of dicts: Each dict has id, user_request, memory_check,
            sufficiency, tool_check, conflicts, decision, tool_name,
            response_time_ms, error, created_at.
        Empty list on any error.
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
