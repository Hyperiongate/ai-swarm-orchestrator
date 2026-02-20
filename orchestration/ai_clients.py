"""
AI Clients Module
Created: January 21, 2026
Last Updated: February 19, 2026 - ADDED SYSTEM PROMPT PARAMETER FOR KB INJECTION

CHANGELOG:

- February 19, 2026: ADDED SYSTEM PROMPT PARAMETER FOR KNOWLEDGE BASE INJECTION
  * PROBLEM: Knowledge base content and identity instructions were being injected
    into the user message turn, where they competed with capabilities and formatting
    blocks and were treated as optional context by the AI. The AI defaulted to its
    generic training knowledge instead of Shiftwork Solutions proprietary content.
  * FIX: Added optional system_prompt parameter to call_claude_sonnet() and
    call_claude_opus(). When provided, this is passed as the Anthropic API's
    system= parameter, which Claude treats as authoritative instructions that
    override user-turn content. The knowledge base content and identity block
    from orchestration_handler.py now travel as the system prompt, making them
    the highest-priority instructions Claude receives.
  * orchestration_handler.py passes knowledge_context + identity_block as the
    system_prompt argument. No other behavior changes.
  * Backward compatible - system_prompt defaults to None, existing calls unaffected.

- January 30, 2026: CRITICAL FILE ATTACHMENT FIX
  * Added files_attached parameter to call_claude_sonnet() and call_claude_opus()
  * When files are attached, AI receives EXPLICIT WARNING it cannot ignore
  * Fixes pattern-matching issue where AI says "I don't see files"

- January 29, 2026: ROBUST CAPABILITY INJECTION
  * ALL AI calls now inject system capabilities
  * call_claude_sonnet() now ALWAYS knows what it can do
  * call_claude_opus() now ALWAYS knows what it can do
  * call_gpt4(), call_deepseek(), call_gemini() all get capabilities
  * Fixes "I don't have the ability to..." false negatives

- January 25, 2026: FIXED CONVERSATION MEMORY NOT BEING USED
  * Modified call_claude_sonnet() to accept optional conversation_history parameter
  * Modified call_claude_opus() to accept optional conversation_history parameter
  * Now properly formats conversation history as message array for Anthropic API
  * Anthropic API requires alternating user/assistant messages
  * Fixes the issue where Claude said "I don't have access to previous conversations"

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
    from orchestration.system_capabilities import get_system_capabilities_prompt
    CAPABILITIES_AVAILABLE = True
except ImportError:
    print("WARNING: system_capabilities module not found - AI will not know its capabilities!")
    CAPABILITIES_AVAILABLE = False
    def get_system_capabilities_prompt():
        return ""


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
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL: FILES ARE ATTACHED TO THIS REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The user has attached files to this request. The file contents appear BELOW in the prompt.
YOU MUST acknowledge these files and reference their content in your response.
DO NOT say "I don't see any files" - the files ARE present and you MUST read them.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
        # FIXED February 19, 2026: Pass system_prompt as Anthropic system= param
        #
        # When system_prompt is provided (knowledge base context + identity block
        # from orchestration_handler.py), it goes into the system= parameter of
        # the API call. The Anthropic API treats this as the highest-priority
        # instruction set that Claude must follow. This is why it works when
        # injecting the same content into the user message did not - the system
        # prompt cannot be overridden by user-turn content.
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
                       (Added Feb 19, 2026 - mirrors call_claude_sonnet behavior)

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
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL: FILES ARE ATTACHED TO THIS REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The user has attached files to this request. The file contents appear BELOW in the prompt.
YOU MUST acknowledge these files and reference their content in your response.
DO NOT say "I don't see any files" - the files ARE present and you MUST read them.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

        # Pass system_prompt as Anthropic system= parameter when provided
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
    Returns dict with 'content' and 'usage'
    """
    if not openai_client:
        return {
            'content': "ERROR: OpenAI API not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""
    enhanced_prompt = f"{capabilities}\n\n{prompt}"

    try:
        response = openai_client.chat.completions.create(
            model=config.GPT4_MODEL,
            messages=[{
                "role": "user",
                "content": enhanced_prompt
            }],
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
    Returns dict with 'content' and 'usage'
    """
    if not deepseek_client:
        return {
            'content': "ERROR: DeepSeek API not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""
    enhanced_prompt = f"{capabilities}\n\n{prompt}"

    try:
        response = deepseek_client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[{
                "role": "user",
                "content": enhanced_prompt
            }],
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
    Returns dict with 'content' and 'usage'
    """
    if not config.GOOGLE_API_KEY:
        return {
            'content': "ERROR: Google API not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""
    enhanced_prompt = f"{capabilities}\n\n{prompt}"

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
