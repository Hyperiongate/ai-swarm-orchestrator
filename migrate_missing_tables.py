"""
AI SWARM ORCHESTRATOR - Configuration
Created: January 18, 2026
Last Updated: January 31, 2026 - FIXED DATABASE PATH FOR PERSISTENCE

CHANGES IN THIS VERSION:
- January 31, 2026: FIXED DATABASE PATH FOR PERSISTENCE
  * Changed DATABASE from 'swarm_intelligence.db' (ephemeral) 
  * To '/mnt/project/swarm_intelligence.db' (persistent disk)
  * Projects and files now survive server restarts and deployments
  * Uses Render's persistent disk mounted at /mnt/project

- January 23, 2026: ADDED ALERT SYSTEM CONFIGURATION
  * Added SMTP configuration for email alerts (SendGrid, Gmail, custom)
  * Added alert recipient email configuration
  * Added enable flags for email alerts and scheduled jobs
  * Added alert check interval configuration

- January 21, 2026: FIXED - Updated to Claude Opus 4.5 model name

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

# Tavily API (Research Agent)
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')

# Microsoft 365
MS365_CLIENT_ID = os.environ.get('MS365_CLIENT_ID')
MS365_CLIENT_SECRET = os.environ.get('MS365_CLIENT_SECRET')
MS365_TENANT_ID = os.environ.get('MS365_TENANT_ID')

# LinkedIn
LINKEDIN_ACCESS_TOKEN = os.environ.get('LINKEDIN_ACCESS_TOKEN')

# ============================================================================
# EMAIL / SMTP CONFIGURATION (Alert System)
# ============================================================================

# SMTP Server Configuration
# For SendGrid: smtp.sendgrid.net, port 587, user='apikey', password=SENDGRID_API_KEY
# For Gmail: smtp.gmail.com, port 587, use app password
# For custom SMTP: set appropriate values
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.sendgrid.net')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'apikey')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or os.environ.get('SENDGRID_API_KEY')

# Alert Email Configuration
ALERT_FROM_EMAIL = os.environ.get('ALERT_FROM_EMAIL', 'alerts@shiftworksolutions.com')
ALERT_TO_EMAIL = os.environ.get('ALERT_TO_EMAIL', '')  # Set to Jim's email

# Alert System Feature Flags
ENABLE_EMAIL_ALERTS = os.environ.get('ENABLE_EMAIL_ALERTS', 'false').lower() == 'true'
ENABLE_SCHEDULED_JOBS = os.environ.get('ENABLE_SCHEDULED_JOBS', 'false').lower() == 'true'

# Alert Check Interval (in minutes)
ALERT_CHECK_INTERVAL = int(os.environ.get('ALERT_CHECK_INTERVAL', 60))

# ============================================================================
# DATABASE - FIXED January 31, 2026
# ============================================================================

# CRITICAL: Database must be on persistent disk to survive restarts
# Render persistent disk is mounted at /mnt/project
DATABASE = '/mnt/project/swarm_intelligence.db'

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

# ============================================================================
# ALERT SYSTEM DEFAULTS
# ============================================================================

# Default scheduled job times (24-hour format, server timezone)
DEFAULT_LEAD_SCAN_TIME = '07:00'
DEFAULT_REGULATORY_SCAN_TIME = '06:00'
DEFAULT_COMPETITOR_SCAN_TIME = '08:00'  # Weekly (Monday)
DEFAULT_BRIEFING_TIME = '07:30'

# Alert priority thresholds for email notification
# Alerts at or above this priority will trigger immediate email
EMAIL_PRIORITY_THRESHOLD = 'high'  # 'critical', 'high', 'medium', 'low'

# Maximum alerts per category in daily briefing
MAX_ALERTS_PER_CATEGORY = 5

# Days to keep dismissed alerts before cleanup
DISMISSED_ALERT_RETENTION_DAYS = 30

# I did no harm and this file is not truncated
