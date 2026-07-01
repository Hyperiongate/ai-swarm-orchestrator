"""
AI Clients Module
Created: January 21, 2026
Last Updated: June 30, 2026 - STREAMING for local calls (beats ngrok idle timeout)

CHANGELOG:
- June 30, 2026 (later same day, #2): STREAMING FOR LOCAL GEMMA CALLS
  * Problem: Even the lean call timed out through the tunnel. Direct testing
    proved the cause precisely: a direct localhost call to Gemma completed fine
    in 28s, but the SAME call through the ngrok tunnel was force-closed at ~6s
    ("connection closed unexpectedly"). Root cause: ngrok's FREE tier closes a
    connection that sits idle with no data flowing — and in non-streaming mode
    nothing comes back until the whole answer is done (~20-30s), so the tunnel
    goes silent and ngrok kills it. LM Studio and the model are healthy; the
    tunnel was the bottleneck.
  * Fix: Both call_local_gemma() and call_local_gemma_raw() now request the
    response as a TOKEN STREAM (stream=True). Tokens flow back continuously as
    the model generates them, so the tunnel connection is never idle and ngrok
    does not close it. The streamed chunks are re-assembled into the SAME return
    dict shape ({'content', 'usage', 'error'}) every caller already expects —
    so nothing downstream changes. stream_options include_usage is requested so
    token counts still populate (they arrive on the final chunk).
  * This also future-proofs the local model against any tunnel's idle limits and
    makes it feel responsive once escalation is wired.
  * Change confined to the two local-gemma functions. Every other function is
    untouched. Rule 1 preserved.

- June 30, 2026 (later same day): ADDED call_local_gemma_raw() — LEAN LOCAL CALL
  * Problem: The first diagnostic test of the local model timed out at Render's
    HTTP gateway (Bad Gateway). Root cause confirmed from the ngrok request log:
    GET /v1/models returned 200 instantly, but POST /v1/chat/completions never
    completed in time. call_local_gemma() injects the full system-capabilities
    prompt (thousands of tokens) into every call — harmless on a fast cloud API,
    but on the laptop (~9 tokens/sec) the model must first ingest all that prompt
    bloat before it even starts answering, pushing a single response past Render's
    ~100-second gateway limit.
  * Fix: Added call_local_gemma_raw(prompt, max_tokens, system_prompt=None) — a
    lean call with NO capabilities injection and NO identity block, sending only
    the prompt (and an optional system message). This is the SAME proven pattern
    already used by call_claude_sonnet_raw() for background memory extraction,
    which had the identical "prompt bloat causes timeout" problem.
  * call_local_gemma() is UNCHANGED — the full-context version is still the right
    one for real orchestration once escalation is wired. call_local_gemma_raw()
    is used by the diagnostic endpoint (routes/local_gemma_test.py) to prove the
    pipe works fast and cleanly within Render's gateway window.
  * PURELY ADDITIVE. One new function. Nothing else changed. Rule 1 preserved.

- June 30, 2026: ADDED call_local_gemma() — LOCAL OFFLINE MODEL CLIENT
  * Purpose: Wire the locally-hosted Gemma model (running in LM Studio on Jim's
    LG Gram, exposed to the internet via an ngrok tunnel) into the swarm as a
    callable model, exactly like the other specialists. This is the "local
    engine" node of the Local AI Engine project — free, private, offline-capable
    inference that the swarm can call instead of (or before) a paid cloud API.
  * Design: Gemma is served by LM Studio over an OpenAI-COMPATIBLE endpoint, so
    call_local_gemma() is modeled directly on call_deepseek() — same OpenAI()
    client pattern, same role='system' identity injection, same return shape
    ({'content', 'usage', 'error'}). It behaves as a true sibling of the other
    client functions.
  * Connection details all come from config.py (which reads them from Render
    environment variables) — NOTHING is hardcoded:
      - config.LOCAL_GEMMA_BASE_URL   the ngrok URL + /v1
      - config.LOCAL_GEMMA_MODEL      "google/gemma-4-e4b"
      - config.LOCAL_GEMMA_API_KEY    dummy/door-password (LM Studio ignores it
                                      unless a lock is set; ngrok basic-auth, if
                                      enabled later, is carried separately)
      - config.LOCAL_GEMMA_TIMEOUT    longer than cloud APIs (laptop is slower)
      - config.LOCAL_GEMMA_SKIP_NGROK_WARNING_HEADER  the header dict that tells
                                      ngrok's free tier NOT to serve the browser
                                      interstitial warning page to automated calls
  * Graceful absence: if LOCAL_GEMMA_BASE_URL is not configured, the module-level
    client is None and call_local_gemma() returns a clean error dict — it never
    crashes the swarm. Identical safety pattern to deepseek_client / openai_client.
  * PURELY ADDITIVE. One new client initializer (local_gemma_client) and one new
    function (call_local_gemma). Every pre-existing function is byte-for-byte
    unchanged. Rule 1 (do no harm) fully preserved.

- March 06, 2026: ADDED call_claude_sonnet_raw()
  * Root cause: Memory extraction thread was silently dying after "🧠 Memory
    extraction starting..." because call_claude_sonnet() injects thousands of
    tokens of system capabilities + FORMATTING_REQUIREMENTS into every call.
    For memory extraction (which only needs a lean JSON response), this bloated
    the input beyond what the daemon thread could reliably handle within the
    30-second timeout window.
  * Fix: Added call_claude_sonnet_raw(prompt, system_prompt, max_tokens) that
    calls the Anthropic API directly with ONLY the provided system_prompt and
    prompt — no capabilities injection, no formatting requirements, no
    conversation history overhead.
  * Used exclusively by memory/memory_extractor.py. All other callers continue
    to use call_claude_sonnet() unchanged.
  * No changes to any existing functions. Fully backward compatible.

- February 28, 2026: FIXED IDENTITY IN GPT-4, DEEPSEEK, AND GEMINI CALLS
  * Added IDENTITY_SYSTEM_MESSAGE as role='system' in call_gpt4(), call_deepseek(),
    and call_gemini() so all models identify as Shiftwork Solutions AI Swarm.

- February 19, 2026: ADDED SYSTEM PROMPT PARAMETER FOR KNOWLEDGE BASE INJECTION
  * Added optional system_prompt parameter to call_claude_sonnet() and
    call_claude_opus(). When provided, passed as Anthropic API system= parameter.

- January 30, 2026: CRITICAL FILE ATTACHMENT FIX
  * Added files_attached parameter to call_claude_sonnet() and call_claude_opus()

- January 29, 2026: ROBUST CAPABILITY INJECTION
  * ALL AI calls now inject system capabilities

- January 25, 2026: FIXED CONVERSATION MEMORY NOT BEING USED
  * Modified call_claude_sonnet() and call_claude_opus() to accept
    optional conversation_history parameter

Author: Jim @ Shiftwork Solutions LLC
"""

import anthropic
import openai
from openai import OpenAI
import google.generativeai as genai
import config

# Initialize Anthropic client
anthropic_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY) if config.ANTHROPIC_API_KEY else None

# Initialize OpenAI client
openai_client = OpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None

# Initialize DeepSeek client
deepseek_client = OpenAI(
    api_key=config.DEEPSEEK_API_KEY,
    base_url=config.DEEPSEEK_BASE_URL
) if config.DEEPSEEK_API_KEY else None

# ============================================================================
# Initialize Local Gemma client (Added June 30, 2026)
# ----------------------------------------------------------------------------
# Gemma runs in LM Studio on Jim's laptop and is exposed via an ngrok tunnel.
# LM Studio serves an OpenAI-COMPATIBLE endpoint, so we use the same OpenAI()
# client class as DeepSeek, just pointed at the local/tunnel base URL.
#
# Two extras vs. the DeepSeek client:
#   1. default_headers carries the ngrok-skip-browser-warning header so ngrok's
#      free tier does NOT serve its HTML interstitial warning page to our
#      automated JSON calls (which would otherwise break parsing).
#   2. api_key uses LOCAL_GEMMA_API_KEY. LM Studio ignores this unless a lock is
#      configured; it is sent so that, if a key-style lock is added later, the
#      code already carries it — no future edit to this file needed.
#
# If LOCAL_GEMMA_BASE_URL is not set in the environment, this stays None and
# call_local_gemma() returns a clean error dict (never crashes the swarm).
# ============================================================================
local_gemma_client = None
try:
    if getattr(config, 'LOCAL_GEMMA_BASE_URL', None):
        local_gemma_client = OpenAI(
            api_key=getattr(config, 'LOCAL_GEMMA_API_KEY', 'lm-studio'),
            base_url=config.LOCAL_GEMMA_BASE_URL,
            default_headers=getattr(config, 'LOCAL_GEMMA_SKIP_NGROK_WARNING_HEADER', None),
        )
        print(f"Local Gemma client initialized -> {config.LOCAL_GEMMA_BASE_URL}")
    else:
        print("Local Gemma client NOT initialized (LOCAL_GEMMA_BASE_URL not set) - local model disabled")
except Exception as _local_gemma_init_err:
    print(f"Local Gemma client init failed (non-fatal): {_local_gemma_init_err}")
    local_gemma_client = None

# Initialize Google Gemini
if config.GOOGLE_API_KEY:
    genai.configure(api_key=config.GOOGLE_API_KEY)

# Import system capabilities
try:
    from orchestration.system_capabilities import get_system_capabilities_prompt, get_identity_system_message
    CAPABILITIES_AVAILABLE = True
except ImportError:
    print("WARNING: system_capabilities module not found - AI will not know its capabilities!")
    CAPABILITIES_AVAILABLE = False
    def get_system_capabilities_prompt():
        return ""
    def get_identity_system_message():
        return "You are the AI Swarm Orchestrator for Shiftwork Solutions LLC."


def call_claude_sonnet(prompt, max_tokens=4000, conversation_history=None, files_attached=False, system_prompt=None):
    """
    Call Claude Sonnet (primary orchestrator).

    Args:
        prompt: The current user request/prompt
        max_tokens: Maximum tokens in response
        conversation_history: Optional list of prior messages [{'role': 'user'|'assistant', 'content': '...'}]
        files_attached: Boolean indicating if files are attached to this request
        system_prompt: Optional system prompt string. When provided, passed as the Anthropic API
                       system= parameter so Claude treats it as authoritative instructions.
                       Used by orchestration_handler.py to inject knowledge base content
                       and identity block at the highest priority level. (Added Feb 19, 2026)

    Returns dict with 'content' and 'usage'
    """
    if not anthropic_client:
        return {
            'content': "ERROR: Anthropic API key not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    # Inject capabilities so AI knows what it can do
    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""

    # Add explicit file attachment warning when files present
    file_warning = ""
    if files_attached:
        file_warning = """
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
CRITICAL: FILES ARE ATTACHED TO THIS REQUEST
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

The user has attached files to this request. The file contents appear BELOW in the prompt.
YOU MUST acknowledge these files and reference their content in your response.
DO NOT say "I don't see any files" - the files ARE present and you MUST read them.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

"""

    # Build the user-turn prompt with capabilities and formatting
    enhanced_prompt = f"{capabilities}\n\n{file_warning}{prompt}\n\n{config.FORMATTING_REQUIREMENTS}"

    try:
        # Build messages array with conversation history
        messages = []

        if conversation_history and len(conversation_history) > 0:
            for msg in conversation_history:
                if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                    continue
                if msg['role'] in ['user', 'assistant']:
                    messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })

        # Add current prompt as final user message
        messages.append({
            'role': 'user',
            'content': enhanced_prompt
        })

        # Ensure messages alternate user/assistant and start with user
        if len(messages) > 1:
            while messages and messages[0]['role'] == 'assistant':
                messages.pop(0)

            cleaned_messages = [messages[0]]
            for i in range(1, len(messages)):
                if messages[i]['role'] != cleaned_messages[-1]['role']:
                    cleaned_messages.append(messages[i])

            messages = cleaned_messages

        # ====================================================================
        # Pass system_prompt as Anthropic system= parameter when provided.
        # When system_prompt is provided (knowledge base context + identity
        # from orchestration_handler.py), it goes into system= and Claude
        # treats it as highest-priority instructions.
        # ====================================================================
        api_kwargs = {
            'model': config.CLAUDE_SONNET_MODEL,
            'max_tokens': max_tokens,
            'messages': messages,
            'timeout': config.ANTHROPIC_TIMEOUT
        }

        if system_prompt:
            api_kwargs['system'] = system_prompt
            print(f"Using system prompt ({len(system_prompt)} chars) for KB injection")

        response = anthropic_client.messages.create(**api_kwargs)

        return {
            'content': response.content[0].text,
            'usage': {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens
            }
        }
    except Exception as e:
        print(f"Claude Sonnet API error: {str(e)}")
        return {
            'content': f"ERROR: Claude Sonnet call failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }


def call_claude_sonnet_raw(prompt, system_prompt, max_tokens=1000):
    """
    Call Claude Sonnet with NO capabilities injection, NO formatting requirements.

    This is a lean internal function designed exclusively for background tasks
    like memory extraction that need a clean JSON response from Claude without
    the overhead of the full capabilities and formatting blocks injected by
    call_claude_sonnet().

    call_claude_sonnet() adds thousands of tokens of capabilities + formatting
    to every call. For a background daemon thread calling Claude just to extract
    a small JSON array of memories, that overhead can cause timeouts or silent
    failures. This function bypasses all that.

    Args:
        prompt (str):        The full user prompt to send
        system_prompt (str): System-level instructions (required — no default)
        max_tokens (int):    Maximum response tokens (default 1000)

    Returns:
        dict with keys:
            'content' (str):  The model's text response, or error message
            'usage'   (dict): {'input_tokens': int, 'output_tokens': int}
            'error'   (bool): True if the call failed (key absent on success)

    Added: March 06, 2026
    Used by: memory/memory_extractor.py
    """
    if not anthropic_client:
        return {
            'content': "ERROR: Anthropic API key not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    try:
        response = anthropic_client.messages.create(
            model=config.CLAUDE_SONNET_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {'role': 'user', 'content': prompt}
            ],
            timeout=config.ANTHROPIC_TIMEOUT
        )

        return {
            'content': response.content[0].text,
            'usage': {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens
            }
        }
    except Exception as e:
        print(f"call_claude_sonnet_raw error: {str(e)}")
        return {
            'content': f"ERROR: call_claude_sonnet_raw failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }


def call_claude_opus(prompt, max_tokens=4000, conversation_history=None, files_attached=False, system_prompt=None):
    """
    Call Claude Opus (strategic supervisor).

    Args:
        prompt: The current user request/prompt
        max_tokens: Maximum tokens in response
        conversation_history: Optional list of prior messages
        files_attached: Boolean indicating if files are attached to this request
        system_prompt: Optional system prompt string. When provided, passed as the Anthropic API
                       system= parameter so Claude treats it as authoritative instructions.

    Returns dict with 'content' and 'usage'
    """
    if not anthropic_client:
        return {
            'content': "ERROR: Anthropic API key not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""

    file_warning = ""
    if files_attached:
        file_warning = """
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
CRITICAL: FILES ARE ATTACHED TO THIS REQUEST
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

The user has attached files to this request. The file contents appear BELOW in the prompt.
YOU MUST acknowledge these files and reference their content in your response.
DO NOT say "I don't see any files" - the files ARE present and you MUST read them.

\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501

"""

    enhanced_prompt = f"{capabilities}\n\n{file_warning}{prompt}\n\n{config.FORMATTING_REQUIREMENTS}"

    try:
        messages = []

        if conversation_history and len(conversation_history) > 0:
            for msg in conversation_history:
                if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                    continue
                if msg['role'] in ['user', 'assistant']:
                    messages.append({
                        'role': msg['role'],
                        'content': msg['content']
                    })

        messages.append({
            'role': 'user',
            'content': enhanced_prompt
        })

        if len(messages) > 1:
            while messages and messages[0]['role'] == 'assistant':
                messages.pop(0)

            cleaned_messages = [messages[0]]
            for i in range(1, len(messages)):
                if messages[i]['role'] != cleaned_messages[-1]['role']:
                    cleaned_messages.append(messages[i])

            messages = cleaned_messages

        api_kwargs = {
            'model': config.CLAUDE_OPUS_MODEL,
            'max_tokens': max_tokens,
            'messages': messages,
            'timeout': config.ANTHROPIC_TIMEOUT
        }

        if system_prompt:
            api_kwargs['system'] = system_prompt
            print(f"Using system prompt ({len(system_prompt)} chars) for KB injection")

        response = anthropic_client.messages.create(**api_kwargs)

        return {
            'content': response.content[0].text,
            'usage': {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens
            }
        }
    except Exception as e:
        print(f"Claude Opus API error: {str(e)}")
        return {
            'content': f"ERROR: Claude Opus call failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }


def call_gpt4(prompt, max_tokens=4000):
    """
    Call GPT-4 (design specialist)

    UPDATED February 28, 2026: Added identity system message as role='system'
    so GPT-4 identifies as Shiftwork Solutions AI Swarm, not as an OpenAI product.
    The identity is passed at the system level where it takes precedence over
    GPT-4's default training behavior of saying "As an AI developed by OpenAI..."

    Returns dict with 'content' and 'usage'
    """
    if not openai_client:
        return {
            'content': "ERROR: OpenAI API not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""
    identity = get_identity_system_message() if CAPABILITIES_AVAILABLE else ""
    enhanced_prompt = f"{capabilities}\n\n{prompt}"

    try:
        response = openai_client.chat.completions.create(
            model=config.GPT4_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": identity
                },
                {
                    "role": "user",
                    "content": enhanced_prompt
                }
            ],
            max_tokens=max_tokens,
            timeout=config.OPENAI_TIMEOUT
        )

        return {
            'content': response.choices[0].message.content,
            'usage': {
                'input_tokens': response.usage.prompt_tokens,
                'output_tokens': response.usage.completion_tokens
            }
        }
    except Exception as e:
        return {
            'content': f"ERROR: GPT-4 call failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }


def call_deepseek(prompt, max_tokens=4000):
    """
    Call DeepSeek (code specialist)

    UPDATED February 28, 2026: Added identity system message as role='system'
    so DeepSeek identifies as Shiftwork Solutions AI Swarm.
    DeepSeek uses the OpenAI-compatible API so role='system' works identically.

    Returns dict with 'content' and 'usage'
    """
    if not deepseek_client:
        return {
            'content': "ERROR: DeepSeek API not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""
    identity = get_identity_system_message() if CAPABILITIES_AVAILABLE else ""
    enhanced_prompt = f"{capabilities}\n\n{prompt}"

    try:
        response = deepseek_client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": identity
                },
                {
                    "role": "user",
                    "content": enhanced_prompt
                }
            ],
            max_tokens=max_tokens,
            timeout=config.DEEPSEEK_TIMEOUT
        )

        return {
            'content': response.choices[0].message.content,
            'usage': {
                'input_tokens': response.usage.prompt_tokens,
                'output_tokens': response.usage.completion_tokens
            }
        }
    except Exception as e:
        return {
            'content': f"ERROR: DeepSeek call failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }


def call_local_gemma(prompt, max_tokens=4000):
    """
    Call the LOCAL Gemma model (offline / local engine).

    Gemma runs in LM Studio on Jim's laptop and is reachable over the internet
    through an ngrok tunnel. LM Studio exposes an OpenAI-COMPATIBLE endpoint, so
    this function mirrors call_deepseek() almost exactly: same OpenAI() client
    pattern, same role='system' identity injection, same return shape.

    WHY THIS EXISTS (Local AI Engine project):
        Gives the swarm a free, private, offline-capable model node it can call
        instead of (or before) a paid cloud API. The swarm decides WHEN to use it;
        this function just makes the call when asked.

    CONNECTION (all from config.py / Render env vars — nothing hardcoded):
        config.LOCAL_GEMMA_BASE_URL    ngrok URL + /v1
        config.LOCAL_GEMMA_MODEL       "google/gemma-4-e4b"
        config.LOCAL_GEMMA_TIMEOUT     longer than cloud (laptop inference is slower)
        ngrok-skip-browser-warning header is set on the client (see top of file)
        so ngrok's free tier does not serve its HTML interstitial to API calls.

    GRACEFUL ABSENCE:
        If LOCAL_GEMMA_BASE_URL is not configured, local_gemma_client is None and
        this returns a clean error dict. The swarm keeps running whether the
        tunnel/laptop is up or down — exactly like the other optional clients.

    Added: June 30, 2026

    Returns dict with 'content' and 'usage'
    """
    if not local_gemma_client:
        return {
            'content': "ERROR: Local Gemma not configured (LOCAL_GEMMA_BASE_URL not set, "
                       "or the laptop/ngrok tunnel is offline)",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""
    identity = get_identity_system_message() if CAPABILITIES_AVAILABLE else ""
    enhanced_prompt = f"{capabilities}\n\n{prompt}"

    # STREAMING (added June 30, 2026): request the response as a token stream so
    # data flows continuously through the ngrok tunnel. This prevents ngrok's
    # free-tier idle-connection timeout from closing the connection while the
    # local model is still generating. The streamed chunks are re-assembled into
    # the SAME dict shape callers already expect — nothing downstream changes.
    try:
        stream = local_gemma_client.chat.completions.create(
            model=config.LOCAL_GEMMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": identity
                },
                {
                    "role": "user",
                    "content": enhanced_prompt
                }
            ],
            max_tokens=max_tokens,
            timeout=getattr(config, 'LOCAL_GEMMA_TIMEOUT', 300),
            stream=True,
            stream_options={"include_usage": True},
        )

        content_parts = []
        input_tokens = 0
        output_tokens = 0
        for chunk in stream:
            # Usage totals arrive on a final chunk whose choices list is empty.
            chunk_usage = getattr(chunk, 'usage', None)
            if chunk_usage:
                input_tokens = getattr(chunk_usage, 'prompt_tokens', 0) or input_tokens
                output_tokens = getattr(chunk_usage, 'completion_tokens', 0) or output_tokens
            choices = getattr(chunk, 'choices', None)
            if choices:
                delta = getattr(choices[0], 'delta', None)
                if delta is not None:
                    piece = getattr(delta, 'content', None)
                    if piece:
                        content_parts.append(piece)

        return {
            'content': "".join(content_parts),
            'usage': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens
            }
        }
    except Exception as e:
        return {
            'content': f"ERROR: Local Gemma call failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }


def call_local_gemma_raw(prompt, max_tokens=512, system_prompt=None):
    """
    Call the LOCAL Gemma model with NO capabilities injection, NO identity block.

    This is the LEAN counterpart to call_local_gemma(), designed for speed on the
    laptop. call_local_gemma() prepends the full system-capabilities prompt
    (thousands of tokens) to every request. On a fast cloud API that is fine, but
    on the local model (~9 tokens/sec) the model must ingest all that prompt bloat
    before it starts answering — which pushed the first diagnostic test past
    Render's ~100-second HTTP gateway limit and produced a Bad Gateway.

    This function sends ONLY the prompt (and an optional system message), exactly
    the way call_claude_sonnet_raw() does for background memory extraction — the
    same proven fix for the same "prompt bloat causes timeout" problem.

    Used by: routes/local_gemma_test.py (the browser diagnostic). It is the
    appropriate call for reachability/latency checks, where the capabilities
    payload is irrelevant. Real orchestration can still use the full-context
    call_local_gemma() once escalation is wired.

    Args:
        prompt (str):        The user prompt to send.
        max_tokens (int):    Max response tokens (default 512 — small and fast).
        system_prompt (str): Optional system message. Defaults to None (leanest).

    GRACEFUL ABSENCE:
        If LOCAL_GEMMA_BASE_URL is not configured, local_gemma_client is None and
        this returns a clean error dict — never crashes.

    Added: June 30, 2026

    Returns dict with 'content' and 'usage'
    """
    if not local_gemma_client:
        return {
            'content': "ERROR: Local Gemma not configured (LOCAL_GEMMA_BASE_URL not set, "
                       "or the laptop/ngrok tunnel is offline)",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    # Build a minimal messages array — no capabilities, no identity bloat.
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # STREAMING (added June 30, 2026): stream tokens so data flows continuously
    # through the ngrok tunnel and its free-tier idle timeout never fires. The
    # streamed chunks are collected back into the same return dict shape.
    try:
        stream = local_gemma_client.chat.completions.create(
            model=config.LOCAL_GEMMA_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            timeout=getattr(config, 'LOCAL_GEMMA_TIMEOUT', 300),
            stream=True,
            stream_options={"include_usage": True},
        )

        content_parts = []
        input_tokens = 0
        output_tokens = 0
        for chunk in stream:
            # Usage totals arrive on a final chunk whose choices list is empty.
            chunk_usage = getattr(chunk, 'usage', None)
            if chunk_usage:
                input_tokens = getattr(chunk_usage, 'prompt_tokens', 0) or input_tokens
                output_tokens = getattr(chunk_usage, 'completion_tokens', 0) or output_tokens
            choices = getattr(chunk, 'choices', None)
            if choices:
                delta = getattr(choices[0], 'delta', None)
                if delta is not None:
                    piece = getattr(delta, 'content', None)
                    if piece:
                        content_parts.append(piece)

        return {
            'content': "".join(content_parts),
            'usage': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens
            }
        }
    except Exception as e:
        return {
            'content': f"ERROR: Local Gemma raw call failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }


def call_gemini(prompt, max_tokens=4000):
    """
    Call Google Gemini (multimodal specialist)

    UPDATED February 28, 2026: Added identity message prepended to prompt.
    Gemini's GenerativeModel API does not have a dedicated system role in the
    same way as OpenAI-compatible APIs, so the identity is prepended to the
    prompt text as the next best approach.

    Returns dict with 'content' and 'usage'
    """
    if not config.GOOGLE_API_KEY:
        return {
            'content': "ERROR: Google API not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""
    identity = get_identity_system_message() if CAPABILITIES_AVAILABLE else ""

    # Prepend identity then capabilities then prompt
    enhanced_prompt = f"{identity}\n\n{capabilities}\n\n{prompt}"

    try:
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        response = model.generate_content(
            enhanced_prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
            )
        )

        return {
            'content': response.text,
            'usage': {
                'input_tokens': 0,
                'output_tokens': 0
            }
        }
    except Exception as e:
        return {
            'content': f"ERROR: Gemini call failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }


# I did no harm and this file is not truncated
