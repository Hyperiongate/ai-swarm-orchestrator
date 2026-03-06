"""
AI Clients Module
Created: January 21, 2026
Last Updated: March 06, 2026 - ADDED call_claude_sonnet_raw() FOR MEMORY EXTRACTION

CHANGELOG:
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
