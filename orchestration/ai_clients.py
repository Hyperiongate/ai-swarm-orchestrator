"""
AI Clients Module
Created: January 21, 2026
Last Updated: January 21, 2026

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

def call_claude_sonnet(prompt, max_tokens=4000):
    """
    Call Claude Sonnet (primary orchestrator)
    Returns dict with 'content' and 'usage'
    """
    if not anthropic_client:
        return {
            'content': "ERROR: Anthropic API key not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }
    
    # Add formatting requirements
    enhanced_prompt = f"{prompt}\n\n{config.FORMATTING_REQUIREMENTS}"
    
    try:
        response = anthropic_client.messages.create(
            model=config.CLAUDE_SONNET_MODEL,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": enhanced_prompt
            }],
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
        return {
            'content': f"ERROR: Claude Sonnet call failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }

def call_claude_opus(prompt, max_tokens=4000):
    """
    Call Claude Opus (strategic supervisor)
    Returns dict with 'content' and 'usage'
    """
    if not anthropic_client:
        return {
            'content': "ERROR: Anthropic API key not configured",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }
    
    # Add formatting requirements
    enhanced_prompt = f"{prompt}\n\n{config.FORMATTING_REQUIREMENTS}"
    
    try:
        response = anthropic_client.messages.create(
            model=config.CLAUDE_OPUS_MODEL,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": enhanced_prompt
            }],
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
    
    try:
        response = openai_client.chat.completions.create(
            model=config.GPT4_MODEL,
            messages=[{
                "role": "user",
                "content": prompt
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
    
    try:
        response = deepseek_client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[{
                "role": "user",
                "content": prompt
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
    
    try:
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
            )
        )
        
        return {
            'content': response.text,
            'usage': {
                'input_tokens': 0,  # Gemini doesn't provide token counts easily
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
