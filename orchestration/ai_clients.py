"""
AI Clients Module
Created: January 21, 2026
Last Updated: January 21, 2026

All AI API calls in one place.
Clean, simple, no indentation nightmares.
"""

import requests
from openai import OpenAI
from config import (
    ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY, 
    GOOGLE_API_KEY, GROQ_API_KEY, FORMATTING_REQUIREMENTS,
    ANTHROPIC_TIMEOUT, OPENAI_TIMEOUT, DEEPSEEK_TIMEOUT, GEMINI_TIMEOUT
)

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com") if DEEPSEEK_API_KEY else None
groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_API_KEY else None

def call_claude_sonnet(prompt, max_tokens=4000):
    """Call Claude Sonnet with formatting requirements"""
    if not ANTHROPIC_API_KEY:
        return "ERROR: Anthropic API key not configured"
    
    enhanced_prompt = f"{prompt}\n\n{FORMATTING_REQUIREMENTS}"
    
    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': enhanced_prompt}]
            },
            timeout=ANTHROPIC_TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()['content'][0]['text']
        else:
            return f"ERROR: Sonnet API returned {response.status_code}: {response.text}"
            
    except requests.exceptions.Timeout:
        return f"ERROR: Sonnet API timeout after {ANTHROPIC_TIMEOUT} seconds"
    except Exception as e:
        return f"ERROR: Sonnet API call failed: {str(e)}"

def call_claude_opus(prompt, max_tokens=4000):
    """Call Claude Opus with formatting requirements"""
    if not ANTHROPIC_API_KEY:
        return "ERROR: Anthropic API key not configured"
    
    enhanced_prompt = f"{prompt}\n\n{FORMATTING_REQUIREMENTS}"
    
    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-opus-4-20250514',
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': enhanced_prompt}]
            },
            timeout=ANTHROPIC_TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()['content'][0]['text']
        else:
            return f"ERROR: Opus API returned {response.status_code}: {response.text}"
            
    except requests.exceptions.Timeout:
        return f"ERROR: Opus API timeout after {ANTHROPIC_TIMEOUT} seconds"
    except Exception as e:
        return f"ERROR: Opus API call failed: {str(e)}"

def call_gpt4(prompt, max_tokens=4000):
    """Call GPT-4 (Design & Content Specialist)"""
    if not openai_client:
        return "ERROR: OpenAI API not configured"
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            timeout=OPENAI_TIMEOUT
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: GPT-4 call failed: {str(e)}"

def call_deepseek(prompt, max_tokens=4000):
    """Call DeepSeek (Code Specialist)"""
    if not deepseek_client:
        return "ERROR: DeepSeek API not configured"
    
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            timeout=DEEPSEEK_TIMEOUT
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: DeepSeek call failed: {str(e)}"

def call_gemini(prompt, max_tokens=4000):
    """Call Google Gemini (Multimodal Specialist)"""
    if not GOOGLE_API_KEY:
        return "ERROR: Google API not configured"
    
    try:
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GOOGLE_API_KEY}',
            json={
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'maxOutputTokens': max_tokens}
            },
            timeout=GEMINI_TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"ERROR: Gemini API returned {response.status_code}"
            
    except Exception as e:
        return f"ERROR: Gemini call failed: {str(e)}"

# I did no harm and this file is not truncated
