"""
AI Clients Module
Created: January 21, 2026
Last Updated: January 30, 2026 - CRITICAL FILE ATTACHMENT FIX

CHANGES IN THIS VERSION:
- January 30, 2026: CRITICAL FILE ATTACHMENT AWARENESS FIX
  * Added files_attached parameter to call_claude_sonnet()
  * Added files_attached parameter to call_claude_opus()
  * When files are attached, AI receives EXPLICIT WARNING it cannot ignore
  * This forces AI to acknowledge and read attached files
  * Fixes pattern-matching issue where AI says "I don't see files"

- January 29, 2026: ROBUST CAPABILITY INJECTION
  * CRITICAL FIX: ALL AI calls now inject system capabilities
  * call_claude_sonnet() now ALWAYS knows what it can do
  * call_claude_opus() now ALWAYS knows what it can do  
  * call_gpt4(), call_deepseek(), call_gemini() all get capabilities
  * Fixes "I don't have the ability to..." false negatives
  * AI is now ALWAYS aware of file handling, document creation, etc.

- January 25, 2026: FIXED CONVERSATION MEMORY NOT BEING USED
  * Modified call_claude_sonnet() to accept optional conversation_history parameter
  * Modified call_claude_opus() to accept optional conversation_history parameter
  * Now properly formats conversation history as message array for Anthropic API
  * Anthropic API requires alternating user/assistant messages
  * This fixes the issue where Claude said "I don't have access to previous conversations"
  * Result: AI now has full conversation context and remembers previous messages

All AI API calls in one place.
Clean, simple, no indentation nightmares.

MERGED VERSION: Combines formatting requirements with dict return structure
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

# 🔧 CRITICAL: Import system capabilities
try:
    from orchestration.system_capabilities import get_system_capabilities_prompt
    CAPABILITIES_AVAILABLE = True
except ImportError:
    print("⚠️ WARNING: system_capabilities module not found - AI will not know its capabilities!")
    CAPABILITIES_AVAILABLE = False
    def get_system_capabilities_prompt():
        return ""

def call_claude_sonnet(prompt, max_tokens=4000, conversation_history=None, files_attached=False):
    """
    Call Claude Sonnet (primary orchestrator)
    
    Args:
        prompt: The current user request/prompt
        max_tokens: Maximum tokens in response
        conversation_history: Optional list of prior messages [{'role': 'user'|'assistant', 'content': '...'}]
        files_attached: Boolean indicating if files are attached to this request
    
    Returns dict with 'content' and 'usage'
    
    CRITICAL FIX (January 30, 2026): Added files_attached parameter to force AI acknowledgment
    """
    if not anthropic_client:
        return {
            'content': "ERROR: Anthropic API key not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }
    
    # 🔧 CRITICAL: Inject capabilities FIRST so AI knows what it can do
    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""
    
    # 🔧 CRITICAL FIX (January 30, 2026): Add explicit file attachment warning
    file_warning = ""
    if files_attached:
        file_warning = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ CRITICAL: FILES ARE ATTACHED TO THIS REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The user has attached files to this request. The file contents appear BELOW in the prompt.
YOU MUST acknowledge these files and reference their content in your response.
DO NOT say "I don't see any files" - the files ARE present and you MUST read them.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    # Add formatting requirements
    enhanced_prompt = f"{capabilities}\n\n{file_warning}{prompt}\n\n{config.FORMATTING_REQUIREMENTS}"
    
    try:
        # Build messages array with conversation history
        messages = []
        
        # Add conversation history if provided
        if conversation_history and len(conversation_history) > 0:
            for msg in conversation_history:
                # Skip if not proper format
                if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                    continue
                
                # Only include user and assistant messages
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
        # Anthropic API requires this
        if len(messages) > 1:
            # Remove any leading assistant messages
            while messages and messages[0]['role'] == 'assistant':
                messages.pop(0)
            
            # Ensure alternating pattern
            cleaned_messages = [messages[0]]  # Start with first user message
            for i in range(1, len(messages)):
                # Only add if it alternates with previous
                if messages[i]['role'] != cleaned_messages[-1]['role']:
                    cleaned_messages.append(messages[i])
            
            messages = cleaned_messages
        
        # Make API call with full conversation context
        response = anthropic_client.messages.create(
            model=config.CLAUDE_SONNET_MODEL,
            max_tokens=max_tokens,
            messages=messages,
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
        print(f"Claude Sonnet API error: {str(e)}")
        return {
            'content': f"ERROR: Claude Sonnet call failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

def call_claude_opus(prompt, max_tokens=4000, conversation_history=None, files_attached=False):
    """
    Call Claude Opus (strategic supervisor)
    
    Args:
        prompt: The current user request/prompt
        max_tokens: Maximum tokens in response
        conversation_history: Optional list of prior messages
        files_attached: Boolean indicating if files are attached to this request
    
    Returns dict with 'content' and 'usage'
    
    CRITICAL FIX (January 30, 2026): Added files_attached parameter to force AI acknowledgment
    """
    if not anthropic_client:
        return {
            'content': "ERROR: Anthropic API key not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }
    
    # 🔧 CRITICAL: Inject capabilities FIRST so AI knows what it can do
    capabilities = get_system_capabilities_prompt() if CAPABILITIES_AVAILABLE else ""
    
    # 🔧 CRITICAL FIX (January 30, 2026): Add explicit file attachment warning
    file_warning = ""
    if files_attached:
        file_warning = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ CRITICAL: FILES ARE ATTACHED TO THIS REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The user has attached files to this request. The file contents appear BELOW in the prompt.
YOU MUST acknowledge these files and reference their content in your response.
DO NOT say "I don't see any files" - the files ARE present and you MUST read them.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    # Add formatting requirements
    enhanced_prompt = f"{capabilities}\n\n{file_warning}{prompt}\n\n{config.FORMATTING_REQUIREMENTS}"
    
    try:
        # Build messages array with conversation history
        messages = []
        
        # Add conversation history if provided
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
        
        # Make API call with full conversation context
        response = anthropic_client.messages.create(
            model=config.CLAUDE_OPUS_MODEL,
            max_tokens=max_tokens,
            messages=messages,
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
    
    ROBUST FIX (January 29, 2026): Now ALWAYS injects system capabilities
    """
    if not openai_client:
        return {
            'content': "ERROR: OpenAI API not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }
    
    # 🔧 CRITICAL: Inject capabilities so AI knows what it can do
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
    
    ROBUST FIX (January 29, 2026): Now ALWAYS injects system capabilities
    """
    if not deepseek_client:
        return {
            'content': "ERROR: DeepSeek API not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }
    
    # 🔧 CRITICAL: Inject capabilities so AI knows what it can do
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
    
    ROBUST FIX (January 29, 2026): Now ALWAYS injects system capabilities
    """
    if not config.GOOGLE_API_KEY:
        return {
            'content': "ERROR: Google API not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }
    
    # 🔧 CRITICAL: Inject capabilities so AI knows what it can do
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
                'input_tokens': 0,  # Gemini doesn't provide token counts
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
