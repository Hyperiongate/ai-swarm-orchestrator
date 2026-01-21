"""
AI SWARM ORCHESTRATOR - Configuration
Created: January 18, 2026
Last Updated: January 21, 2026 - FIXED: Updated to Claude Opus 4.5 model name

CRITICAL FIX: Changed CLAUDE_OPUS_MODEL from claude-opus-4-20241229 (doesn't exist) 
to claude-opus-4-5-20251101 (Opus 4.5)

All API keys, model names, and system configuration.
AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import os

# ============================================================================
# API KEYS - FROM ENVIRONMENT VARIABLES
# ============================================================================

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

# Microsoft 365
MS365_CLIENT_ID = os.environ.get('MS365_CLIENT_ID')
MS365_CLIENT_SECRET = os.environ.get('MS365_CLIENT_SECRET')
MS365_TENANT_ID = os.environ.get('MS365_TENANT_ID')

# LinkedIn
LINKEDIN_ACCESS_TOKEN = os.environ.get('LINKEDIN_ACCESS_TOKEN')

# ============================================================================
# DATABASE
# ============================================================================

DATABASE = 'swarm_intelligence.db'

# ============================================================================
# FORMATTING REQUIREMENTS (Added to every prompt)
# ============================================================================

FORMATTING_REQUIREMENTS = """
FORMAT YOUR RESPONSE PROFESSIONALLY:

1. Use clear paragraphs, NOT walls of text
2. Use markdown headers (##) sparingly - only for major sections
3. Use bullet points for lists of 3+ items
4. Keep paragraphs under 4 sentences
5. Use bold (**text**) only for critical emphasis
6. Break up dense content with whitespace
Maximum line length: 100 characters (wrap longer content)
7. For professional consulting outputs, use clean prose without formatting symbols

YOUR OUTPUT WILL BE CHECKED. If it contains excessive markdown, walls of text, or
poor formatting, it will be automatically reformatted, which wastes processing time.
Format your response professionally from the start.
"""

# ============================================================================
# API TIMEOUTS
# ============================================================================

ANTHROPIC_TIMEOUT = 180  # seconds
OPENAI_TIMEOUT = 120
DEEPSEEK_TIMEOUT = 120
GEMINI_TIMEOUT = 120

# ============================================================================
# MODEL CONFIGURATIONS - CRITICAL FIX: Updated Opus to 4.5
# ============================================================================

CLAUDE_SONNET_MODEL = "claude-sonnet-4-20250514"  # Sonnet 4
CLAUDE_OPUS_MODEL = "claude-opus-4-5-20251101"    # FIXED: Opus 4.5 (was using non-existent 20241229)
GPT4_MODEL = "gpt-4-turbo-preview"
DEEPSEEK_MODEL = "deepseek-chat"
GEMINI_MODEL = "gemini-1.5-pro"

# ============================================================================
# DEFAULT TOKENS
# ============================================================================

DEFAULT_MAX_TOKENS = 4000
SONNET_MAX_TOKENS = 4000
OPUS_MAX_TOKENS = 4000

# ============================================================================
# ESCALATION THRESHOLDS
# ============================================================================

CONFIDENCE_THRESHOLD_LOW = 0.7  # Below this = escalate to Opus
COMPLEXITY_THRESHOLD = 0.8      # Above this = escalate to Opus

# ============================================================================
# CONSENSUS VALIDATION
# ============================================================================

CONSENSUS_THRESHOLD = 0.85  # 85% agreement required
ENABLE_CONSENSUS_BY_DEFAULT = True

# ============================================================================
# DEEPSEEK CONFIGURATION
# ============================================================================

DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ============================================================================
# KNOWLEDGE BASE
# ============================================================================

KNOWLEDGE_BASE_PATHS = [
    "/mnt/project",
    "project_files",
    "./project_files"
]

# ============================================================================
# OPTIONAL INTEGRATIONS
# ============================================================================

MICROSOFT_365_ENABLED = False
SOCIAL_MEDIA_ENABLED = False
CALCULATOR_ENABLED = True
SURVEY_BUILDER_ENABLED = False

# I did no harm and this file is not truncated
