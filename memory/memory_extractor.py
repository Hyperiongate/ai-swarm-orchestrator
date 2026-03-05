"""
AI SWARM ORCHESTRATOR - Memory Extractor
Phase 2A: Memory System — Extraction Layer

Created: March 05, 2026
Last Updated: March 05, 2026 - Phase 2A initial build

CHANGELOG:
- March 05, 2026: Phase 2A initial build
  * New file — part of Phase 2A memory system
  * After each orchestration completes, analyzes the interaction with Claude Sonnet
    and extracts structured memories (episodic, semantic, procedural)
  * Called from a background daemon thread in routes/orchestration_handler.py
    so memory extraction is non-blocking to the user
  * Uses call_claude_sonnet() from orchestration.ai_clients
  * Uses store_memory() from memory.memory_store
  * Handles all failures gracefully — never crashes the main request

PURPOSE:
    This is the intelligence component that makes the Swarm stop being amnesiac.
    After every successful AI response, Sonnet reviews the interaction and decides
    what is worth remembering. It creates:

    - EPISODIC memory for every interaction (brief record of what happened)
    - SEMANTIC memories when something generalizable is learned (client facts,
      domain rules, user preferences)
    - PROCEDURAL memories when performance patterns are observed (which model
      works best for what, what approaches succeed or fail)

    If Sonnet returns bad JSON or the API call fails, extraction is silently
    skipped. The user never sees memory extraction errors.

CALLED FROM:
    routes/orchestration_handler.py — end of HANDLER 10 (regular conversation)
    in a background daemon thread:

        import threading
        from memory import extract_memories
        t = threading.Thread(target=extract_memories, args=(task_data,), daemon=True)
        t.start()

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

# Maximum characters of the AI response to include in the extraction prompt.
# Keeps token cost low while giving Sonnet enough signal to extract memories.
_RESPONSE_SUMMARY_LENGTH = 800

# System prompt for the memory extraction call.
# Kept short to minimize token usage — this runs after every interaction.
_EXTRACTION_SYSTEM_PROMPT = """You are the memory system for the AI Swarm Orchestrator, a consulting tool for Shiftwork Solutions LLC. Your job is to analyze a completed interaction and extract structured memories worth keeping. Be selective — not every interaction needs a memory. Routine questions with routine answers only need a brief episodic record."""

# Template for the extraction user prompt.
_EXTRACTION_PROMPT_TEMPLATE = """Here is a completed interaction from the AI Swarm:

REQUEST: {user_request}
RESPONSE SUMMARY: {response_summary}
MODEL USED: {model_used}
EXECUTION TIME: {execution_time}s
TASK TYPE: {task_type}
PROJECT ID: {project_id}

Analyze this interaction. Return a JSON array of memories to store. Each memory object must have:
- "memory_type": "episodic", "semantic", or "procedural"
- "category": one of "client_info", "scheduling", "routing_performance", "user_preferences", "project_context", "task_patterns", "system_performance"
- "content": the actual thing to remember (1-3 sentences, concise and specific)
- "relevance_score": 0.0 to 1.0

Guidelines:
- ALWAYS create one EPISODIC memory summarizing what happened (brief, 1 sentence)
- Create SEMANTIC memories only when the interaction reveals something generalizable (a client fact, a user preference, a domain rule, a schedule pattern insight)
- Create PROCEDURAL memories only when the interaction reveals something about how to work better (model performance, effective approaches, things to avoid)
- Episodic memories get relevance_score 0.2-0.4 unless highly significant
- Semantic memories get 0.5-0.9 based on how useful the knowledge is long-term
- Procedural memories get 0.6-0.9 based on how actionable the insight is
- If nothing interesting happened beyond a routine answer, just return the single episodic record
- Keep each content field to 1-3 sentences maximum

Return ONLY a valid JSON array. No markdown fences, no explanation, no preamble. Just the JSON array starting with [ and ending with ]."""


def extract_memories(task_data):
    """
    Analyze a completed orchestration interaction and store relevant memories.

    This function is designed to run in a background daemon thread. It will
    never raise an exception — all errors are logged and silently swallowed
    so the main request thread is never affected.

    Args:
        task_data (dict): Information about the completed interaction. Expected keys:
            user_request (str):      The user's original request text
            ai_response (str):       The full AI response text
            model_used (str):        Which model handled the request ('sonnet', 'opus', etc.)
            task_type (str):         Task classification from task_analysis ('general', etc.)
            execution_time (float):  How long the request took in seconds
            task_id (int|None):      Database task ID (becomes source_task_id in memory_store)
            project_id (str|None):   Project ID if the request was project-scoped
            consensus_score (float|None): Consensus agreement score if consensus ran

    Returns:
        list[dict]: The memory dicts that were successfully stored, or [] on any failure.
                    (Return value is primarily for testing — callers in background threads
                     typically ignore it.)
    """
    try:
        return _run_extraction(task_data)
    except Exception as e:
        logger.error(f"extract_memories: unexpected top-level failure: {e}")
        return []


def _run_extraction(task_data):
    """
    Internal implementation — called by extract_memories() inside a try/except.
    """
    # ----------------------------------------------------------------
    # 1. Validate and unpack inputs
    # ----------------------------------------------------------------
    user_request = (task_data.get('user_request') or '').strip()
    ai_response = (task_data.get('ai_response') or '').strip()
    model_used = (task_data.get('model_used') or 'sonnet').strip()
    task_type = (task_data.get('task_type') or 'general').strip()
    project_id = task_data.get('project_id') or 'none'
    source_task_id = task_data.get('task_id')

    try:
        execution_time = round(float(task_data.get('execution_time') or 0), 1)
    except (TypeError, ValueError):
        execution_time = 0.0

    # Skip extraction for empty or error responses
    if not user_request:
        logger.debug("extract_memories: skipping — no user_request")
        return []

    if not ai_response or ai_response.startswith('Error:'):
        logger.debug("extract_memories: skipping — no ai_response or response was an error")
        return []

    # ----------------------------------------------------------------
    # 2. Build the extraction prompt
    # ----------------------------------------------------------------
    response_summary = ai_response[:_RESPONSE_SUMMARY_LENGTH]
    if len(ai_response) > _RESPONSE_SUMMARY_LENGTH:
        response_summary += '...'

    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
        user_request=user_request[:500],
        response_summary=response_summary,
        model_used=model_used,
        execution_time=execution_time,
        task_type=task_type,
        project_id=project_id
    )

    # ----------------------------------------------------------------
    # 3. Call Claude Sonnet for extraction
    # ----------------------------------------------------------------
    logger.info(f"extract_memories: calling Sonnet for task_id={source_task_id}")

    try:
        from orchestration.ai_clients import call_claude_sonnet
        response = call_claude_sonnet(
            prompt,
            max_tokens=800,
            system_prompt=_EXTRACTION_SYSTEM_PROMPT
        )
    except Exception as api_err:
        logger.error(f"extract_memories: Sonnet call failed: {api_err}")
        return []

    if not response or response.get('error'):
        logger.error(f"extract_memories: Sonnet returned error: {response.get('content', 'unknown')}")
        return []

    raw_text = (response.get('content') or '').strip()
    if not raw_text:
        logger.warning("extract_memories: Sonnet returned empty response")
        return []

    # ----------------------------------------------------------------
    # 4. Parse the JSON response
    # ----------------------------------------------------------------
    memories_data = _parse_memories_json(raw_text)
    if memories_data is None:
        logger.warning(f"extract_memories: could not parse Sonnet response as JSON. Raw: {raw_text[:300]}")
        # Fall back to storing a minimal episodic record so something is captured
        memories_data = [
            {
                'memory_type': 'episodic',
                'category': 'task_patterns',
                'content': f"Request processed: {user_request[:150]}",
                'relevance_score': 0.2
            }
        ]

    # ----------------------------------------------------------------
    # 5. Store each memory
    # ----------------------------------------------------------------
    from memory.memory_store import store_memory

    stored = []
    for mem in memories_data:
        if not isinstance(mem, dict):
            continue

        memory_type = mem.get('memory_type', 'episodic')
        category = mem.get('category', 'task_patterns')
        content = mem.get('content', '')
        relevance_score = mem.get('relevance_score', 0.3)

        if not content:
            continue

        memory_id = store_memory(
            memory_type=memory_type,
            category=category,
            content=content,
            source_task_id=source_task_id,
            relevance_score=relevance_score
        )

        if memory_id:
            stored.append({
                'id': memory_id,
                'memory_type': memory_type,
                'category': category,
                'content': content,
                'relevance_score': relevance_score
            })
            logger.debug(f"extract_memories: stored {memory_type}/{category} id={memory_id}")

    logger.info(
        f"extract_memories: stored {len(stored)} memories for task_id={source_task_id} "
        f"(model={model_used}, time={execution_time}s)"
    )
    return stored


def _parse_memories_json(raw_text):
    """
    Attempt to parse Sonnet's response as a JSON array of memory objects.

    Handles common LLM formatting issues:
    - Markdown code fences (```json ... ```)
    - Leading/trailing whitespace
    - Response that is a JSON object instead of array (wraps in list)

    Returns:
        list[dict] on success, None on failure
    """
    if not raw_text:
        return None

    text = raw_text.strip()

    # Strip markdown fences if present
    # Handles: ```json\n...\n``` or ```\n...\n```
    fence_pattern = re.compile(r'^```(?:json)?\s*(.*?)\s*```$', re.DOTALL)
    match = fence_pattern.match(text)
    if match:
        text = match.group(1).strip()

    # Attempt direct JSON parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            # Single memory returned as object instead of array
            return [parsed]
        logger.warning(f"_parse_memories_json: unexpected JSON type {type(parsed)}")
        return None
    except json.JSONDecodeError:
        pass

    # Try to extract a JSON array from within the text (handles preamble/postamble)
    # Find the first [ and last ]
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try to extract a JSON object
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass

    return None


# I did no harm and this file is not truncated
