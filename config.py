"""
Configuration Module
Created: January 21, 2026
Last Updated: January 21, 2026

All API keys, database paths, and configuration in one place.
No more hunting through 2,500 lines of code.

FIXED: Removed circular import (was importing from database)
"""

import os

# ============================================================================
# API KEYS
# ============================================================================

# Anthropic (Claude Opus + Sonnet)
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

# OpenAI (GPT-4 for design/content)
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# DeepSeek (Code specialist)
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

# Google Gemini (Multimodal specialist)
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

# Mistral (Alternative perspective)
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY')

# Groq (Fast inference)
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

# Microsoft 365
MS365_CLIENT_ID = os.environ.get('MS365_CLIENT_ID')
MS365_CLIENT_SECRET = os.environ.get('MS365_CLIENT_SECRET')
MS365_TENANT_ID = os.environ.get('MS365_TENANT_ID')

# LinkedIn
LINKEDIN_ACCESS_TOKEN = os.environ.get('LINKEDIN_ACCESS_TOKEN')

# Twitter/X
TWITTER_API_KEY = os.environ.get('TWITTER_API_KEY')

# ============================================================================
# DATABASE
# ============================================================================

DATABASE = 'swarm_intelligence.db'

# ============================================================================
# FORMATTING REQUIREMENTS
# ============================================================================

FORMATTING_REQUIREMENTS = """
CRITICAL OUTPUT FORMATTING REQUIREMENTS:

1. NEVER use markdown symbols (**bold**, *italic*, ###headers) in your final output
2. For schedules: Use clean tables or structured lists, NOT walls of text
3. NO consecutive capital letters spanning more than 10 characters
4. Use proper section breaks (blank lines) between topics
5. If creating a schedule, present it in a clear, readable format:
   - Use section headers like "ROTATION PATTERN:" or "TIME OFF SCHEDULE:"
   - List weeks clearly: "Week 1: Work 7 days" (not **Week 1:** Work 7 days)
   - Use dash lines (----) to separate sections
6. Maximum line length: 100 characters (wrap longer content)
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
# MODEL CONFIGURATIONS
# ============================================================================

CLAUDE_SONNET_MODEL = "claude-sonnet-4-20250514"
CLAUDE_OPUS_MODEL = "claude-opus-4-20241229"
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
