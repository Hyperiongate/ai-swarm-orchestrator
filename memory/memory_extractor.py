"""
AI SWARM ORCHESTRATOR - Memory Extractor
Phase 2A: Memory System — Extraction Layer

Created: March 05, 2026
Last Updated: March 07, 2026 - DENIAL DETECTION: prevent self-poisoning

CHANGELOG:
- March 07, 2026: DENIAL DETECTION — prevent memory self-poisoning
  PROBLEM: When the AI incorrectly responded "TestCorp not in the knowledge
    base," the extractor faithfully extracted that wrong behavior as a
    PROCEDURAL memory: "When asked about client companies not in the knowledge
    base, acknowledge the limitation." That procedural memory had score 0.7,
    which outranked the correct TestCorp semantic facts at 0.6. The AI then
    followed its own bad lesson on the next request, creating a poisoning loop.
  FIX 1 — DENIAL DETECTION: Added _is_denial_response() which scans the AI
    response for phrases like "not in the knowledge base", "no information about",
    "I don't see any information", etc. If detected, the response is flagged
    as a denial response.
  FIX 2 — SUPPRESSED EXTRACTION: When denial is detected, the extraction
    prompt explicitly instructs Sonnet NOT to create procedural or semantic
    memories from this interaction. Only a low-score episodic record is
    allowed. This prevents the wrong behavior from becoming a learned lesson.
  FIX 3 — NEAR-DUPLICATE SUPPRESSION: Added _is_near_duplicate() which
    checks if a candidate semantic memory's content is substantially similar
    to an already-stored memory. Prevents the 4 near-identical TestCorp
    memories that accumulated from repeated failed test queries.
  NO OTHER CHANGES: API call, JSON parsing, store_memory() calls, thread
    safety, and error handling all unchanged.

- March 06, 2026: SWITCHED TO call_claude_sonnet_raw()
  * Root cause: call_claude_sonnet() injects thousands of tokens of system
    capabilities + FORMATTING_REQUIREMENTS into every call. Running inside a
    background daemon thread with max_tokens=800, the oversized input was
    causing silent failures — the thread would start ("🧠 Memory extraction
    starting...") but never reach the "complete" log line.
  * Fix: Switched from call_claude_sonnet() to the new call_claude_sonnet_raw()
    function in orchestration/ai_clients.py. This calls Claude directly with
    only the extraction system prompt and extraction user prompt — no
    capabilities injection, no formatting requirements, no conversation history.
  * Also increased max_tokens from 800 to 1000 to give Claude a little more
    room for the JSON array response.
  * No logic changes. All extraction prompts, memory types, categories, and
    storage calls unchanged.

- March 06, 2026: ADDED PRINT LOGGING
  * Added print("🧠 Memory extraction starting...") at start of _run_extraction()
  * Added print("🧠 Memory extraction complete - stored X memories") at end
  * Added failure/skip prints at all early-exit paths

- March 05, 2026: Phase 2A initial build
  * New file — part of Phase 2A memory system
  * After each orchestration completes, analyzes the interaction with Claude Sonnet
    and extracts structured memories (episodic, semantic, procedural)
  * Called from a background daemon thread in routes/orchestration_handler.py
  * Uses call_claude_sonnet_raw() from orchestration.ai_clients (updated Mar 06)
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

    DENIAL RESPONSES: If the AI response contains denial language ("not in
    the knowledge base", "no information about", etc.), extraction is
    restricted to a single low-score episodic record. No procedural or
    semantic memories are extracted from denial responses — this prevents
    the wrong behavior from becoming a learned lesson that gets applied to
    future requests.

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

# Phrases that indicate the AI gave a denial/ignorance response.
# If ANY of these appear in the response, extraction is restricted to
# a single low-score episodic record — no procedural or semantic memories.
# This prevents bad "acknowledge the limitation" lessons from being learned.
_DENIAL_PHRASES = [
    "not in the knowledge base",
    "no information about",
    "doesn't appear in",
    "not found in",
    "i don't see any information",
    "have no data",
    "not available in",
    "cannot find",
    "no record of",
    "wasn't discussed",
    "wasn't mentioned",
    "don't have information",
    "no details about",
    "isn't in our knowledge",
    "is not in our knowledge",
    "not included in the knowledge",
    "not part of the knowledge",
    "no specific information",
    "doesn't contain information about",
]

# System prompt for the memory extraction call.
# Kept short to minimize token usage — this runs after every interaction.
_EXTRACTION_SYSTEM_PROMPT = """You are the memory system for the AI Swarm Orchestrator, a consulting tool for Shiftwork Solutions LLC. Your job is to analyze a completed interaction and extract structured memories worth keeping. Be selective — not every interaction needs a memory. Routine questions with routine answers only need a brief episodic record."""

# Template for the standard extraction user prompt.
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

# Template for denial responses — restricts extraction to episodic only.
# Used when the AI response contained denial/ignorance language, to prevent
# extracting bad procedural lessons like "acknowledge the limitation."
_DENIAL_EXTRACTION_PROMPT_TEMPLATE = """Here is a completed interaction from the AI Swarm:

REQUEST: {user_request}
RESPONSE SUMMARY: {response_summary}
MODEL USED: {model_used}
EXECUTION TIME: {execution_time}s
TASK TYPE: {task_type}
PROJECT ID: {project_id}

IMPORTANT: The AI response above contained uncertainty or denial language (e.g., "not in
the knowledge base", "no information about"). This means the AI may have given an
incorrect or incomplete answer. DO NOT extract procedural lessons from denial responses —
doing so would teach the system to repeat incorrect behavior.

For this interaction, return ONLY a single episodic memory recording what was asked.
Do NOT create semantic or procedural memories from this interaction.

Return a JSON array containing exactly one memory object:
- "memory_type": "episodic"
- "category": "task_patterns"
- "content": one sentence summarizing what the user asked (do not characterize the answer as correct)
- "relevance_score": 0.2

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
        print(f"🧠 Memory extraction failed — unexpected error: {e}")
        return []


def _run_extraction(task_data):
    """
    Internal implementation — called by extract_memories() inside a try/except.
    """
    print("🧠 Memory extraction starting...")

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
        print("🧠 Memory extraction skipped — no user_request")
        return []

    if not ai_response or ai_response.startswith('Error:'):
        logger.debug("extract_memories: skipping — no ai_response or response was an error")
        print("🧠 Memory extraction skipped — no ai_response or error response")
        return []

    # ----------------------------------------------------------------
    # 2. Detect denial responses
    #    If the AI said "not in the knowledge base" or similar, restrict
    #    extraction to a single low-score episodic record only.
    #    This prevents bad procedural lessons from being learned.
    # ----------------------------------------------------------------
    is_denial = _is_denial_response(ai_response)
    if is_denial:
        print(f"🧠 Memory extraction: DENIAL RESPONSE detected — restricting to episodic only")
        logger.info(f"extract_memories: denial response detected for task_id={source_task_id}, "
                    f"suppressing procedural/semantic extraction")

    # ----------------------------------------------------------------
    # 3. Build the extraction prompt
    # ----------------------------------------------------------------
    response_summary = ai_response[:_RESPONSE_SUMMARY_LENGTH]
    if len(ai_response) > _RESPONSE_SUMMARY_LENGTH:
        response_summary += '...'

    prompt_template = _DENIAL_EXTRACTION_PROMPT_TEMPLATE if is_denial else _EXTRACTION_PROMPT_TEMPLATE

    prompt = prompt_template.format(
        user_request=user_request[:500],
        response_summary=response_summary,
        model_used=model_used,
        execution_time=execution_time,
        task_type=task_type,
        project_id=project_id
    )

    # ----------------------------------------------------------------
    # 4. Call Claude Sonnet (RAW — no capabilities/formatting overhead)
    #    Using call_claude_sonnet_raw() so the daemon thread is not
    #    burdened with thousands of tokens of capabilities injection.
    # ----------------------------------------------------------------
    logger.info(f"extract_memories: calling Sonnet (raw) for task_id={source_task_id}")
    print(f"🧠 Calling Sonnet for memory extraction (task_id={source_task_id}, "
          f"denial={is_denial})...")

    try:
        from orchestration.ai_clients import call_claude_sonnet_raw
        response = call_claude_sonnet_raw(
            prompt=prompt,
            system_prompt=_EXTRACTION_SYSTEM_PROMPT,
            max_tokens=1000
        )
    except Exception as api_err:
        logger.error(f"extract_memories: Sonnet call failed: {api_err}")
        print(f"🧠 Memory extraction failed — Sonnet API error: {api_err}")
        return []

    if not response or response.get('error'):
        logger.error(f"extract_memories: Sonnet returned error: {response.get('content', 'unknown')}")
        print(f"🧠 Memory extraction failed — Sonnet response error: "
              f"{response.get('content', 'unknown')[:100]}")
        return []

    raw_text = (response.get('content') or '').strip()
    if not raw_text:
        logger.warning("extract_memories: Sonnet returned empty response")
        print("🧠 Memory extraction failed — empty Sonnet response")
        return []

    # ----------------------------------------------------------------
    # 5. Parse the JSON response
    # ----------------------------------------------------------------
    memories_data = _parse_memories_json(raw_text)
    if memories_data is None:
        logger.warning(f"extract_memories: could not parse Sonnet response as JSON. "
                       f"Raw: {raw_text[:300]}")
        print("🧠 Memory extraction — JSON parse failed, using fallback episodic record")
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
    # 6. Safety filter: if denial was detected, enforce episodic-only
    #    even if Sonnet ignored the instruction in the prompt.
    #    Also enforce: episodic score capped at 0.3 for denial responses.
    # ----------------------------------------------------------------
    if is_denial:
        memories_data = _enforce_episodic_only(memories_data)

    # ----------------------------------------------------------------
    # 7. Store each memory, with near-duplicate suppression for semantics
    # ----------------------------------------------------------------
    from memory.memory_store import store_memory, search_memories

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

        # Near-duplicate suppression for semantic memories:
        # Don't store a semantic memory if a very similar one already exists.
        if memory_type == 'semantic':
            if _is_near_duplicate(content, search_memories):
                print(f"🧠 Memory extraction: skipping near-duplicate semantic memory: "
                      f"{content[:80]}...")
                logger.debug(f"extract_memories: near-duplicate suppressed: {content[:80]}")
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

    print(f"🧠 Memory extraction complete - stored {len(stored)} memories")
    logger.info(
        f"extract_memories: stored {len(stored)} memories for task_id={source_task_id} "
        f"(model={model_used}, time={execution_time}s, denial={is_denial})"
    )
    return stored


# ============================================================================
# DENIAL DETECTION
# ============================================================================

def _is_denial_response(ai_response):
    """
    Detect whether the AI response contains denial/ignorance language.

    Returns True if the response contains any phrase from _DENIAL_PHRASES,
    indicating the AI claimed it had no information about the topic.
    These responses should not generate procedural or semantic memories,
    as the AI may have been wrong and we don't want to codify wrong behavior.

    Args:
        ai_response (str): The full AI response text

    Returns:
        bool: True if denial language detected, False otherwise
    """
    if not ai_response:
        return False
    response_lower = ai_response.lower()
    for phrase in _DENIAL_PHRASES:
        if phrase in response_lower:
            logger.debug(f"_is_denial_response: matched phrase '{phrase}'")
            return True
    return False


def _enforce_episodic_only(memories_data):
    """
    Filter a list of memory dicts to keep only episodic memories,
    and cap their relevance_score at 0.3.

    Called when a denial response was detected, to ensure Sonnet's output
    does not include procedural or semantic memories even if it ignored
    the prompt instruction.

    Args:
        memories_data (list[dict]): Raw memory dicts from Sonnet

    Returns:
        list[dict]: Filtered list with only episodic memories, score capped at 0.3
    """
    filtered = []
    for mem in memories_data:
        if not isinstance(mem, dict):
            continue
        if mem.get('memory_type') == 'episodic':
            # Cap relevance score
            mem['relevance_score'] = min(float(mem.get('relevance_score') or 0.2), 0.3)
            filtered.append(mem)

    # If Sonnet returned nothing episodic, create a minimal fallback
    if not filtered:
        filtered = [
            {
                'memory_type': 'episodic',
                'category': 'task_patterns',
                'content': 'User asked a question; system response indicated uncertainty.',
                'relevance_score': 0.2
            }
        ]

    return filtered


# ============================================================================
# NEAR-DUPLICATE SUPPRESSION
# ============================================================================

def _is_near_duplicate(content, search_memories_fn, similarity_threshold=0.7):
    """
    Check whether a candidate semantic memory is substantially similar
    to an already-stored memory.

    Uses word overlap (Jaccard similarity) between the candidate content
    and the top search result for the same content. If similarity exceeds
    the threshold, the candidate is considered a near-duplicate.

    This prevents accumulation of near-identical memories like:
      "TestCorp is a bottling plant with 4 crews..."
      "TestCorp operates a bottling plant with 4 crews..."
      "TestCorp is a bottling plant operation with 4 crews..."

    Args:
        content (str): The candidate memory content
        search_memories_fn (callable): search_memories() from memory_store
        similarity_threshold (float): Jaccard similarity threshold (default 0.7)

    Returns:
        bool: True if a near-duplicate exists, False otherwise (store it)
    """
    if not content or not content.strip():
        return False

    try:
        # Search for the most similar existing memories
        results = search_memories_fn(content, limit=5)
        if not results:
            return False

        candidate_words = set(_tokenize(content))
        if not candidate_words:
            return False

        for existing in results:
            existing_content = existing.get('content', '')
            if not existing_content:
                continue
            existing_words = set(_tokenize(existing_content))
            if not existing_words:
                continue

            # Jaccard similarity: |intersection| / |union|
            intersection = candidate_words & existing_words
            union = candidate_words | existing_words
            similarity = len(intersection) / len(union) if union else 0.0

            if similarity >= similarity_threshold:
                logger.debug(
                    f"_is_near_duplicate: similarity={similarity:.2f} "
                    f"candidate='{content[:60]}' existing='{existing_content[:60]}'"
                )
                return True

        return False

    except Exception as e:
        # On any error, allow the memory to be stored (fail open)
        logger.debug(f"_is_near_duplicate: error during check (allowing store): {e}")
        return False


def _tokenize(text):
    """
    Tokenize text into lowercase words for Jaccard similarity comparison.
    Strips punctuation and filters short/stop words.
    """
    _STOP = frozenset({
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
        'for', 'of', 'with', 'is', 'are', 'was', 'has', 'that', 'this',
        'it', 'its', 'be', 'by', 'from', 'as', 'about',
    })
    tokens = []
    for token in text.lower().split():
        clean = token.strip('.,!?;:\'"()[]{}')
        if len(clean) >= 3 and clean not in _STOP:
            tokens.append(clean)
    return tokens


# ============================================================================
# JSON PARSING
# ============================================================================

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
