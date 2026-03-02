"""
AI SWARM ORCHESTRATOR - Configuration
Created: January 18, 2026
Last Updated: March 02, 2026 - POSTGRESQL MIGRATION (Phase 1)

CHANGELOG:
- March 02, 2026: POSTGRESQL MIGRATION
  * Removed hardcoded DATABASE = '/mnt/project/swarm_intelligence.db'
  * DATABASE now set based on DATABASE_URL env var (PostgreSQL) or SQLite fallback
  * Added STORAGE_PATH = '/mnt/project/swarm_projects/' for persistent file storage
  * Added get_db_connection() import from db_engine — all modules import from here
  * get_db_type() exposed for health check reporting
  * DATABASE kept as legacy variable pointing to SQLite path (for modules not yet
    migrated to get_db_connection — they will continue to work during transition)

- January 31, 2026: FIXED DATABASE PATH FOR PERSISTENCE
  * Changed DATABASE from 'swarm_intelligence.db' (ephemeral)
  * To '/mnt/project/swarm_intelligence.db' (persistent disk)

- January 23, 2026: ADDED ALERT SYSTEM CONFIGURATION
- January 21, 2026: FIXED - Updated to Claude Opus 4.5 model name

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import os

# ============================================================================
# DATABASE ENGINE — import and re-export for all modules
# ============================================================================
# All modules that need a database connection should do:
#   from config import get_db_connection
# or import directly:
#   from db_engine import get_db_connection

from db_engine import get_db_connection, get_db_type

# Legacy DATABASE variable kept for any migration scripts or modules
# that still reference it directly. Points to SQLite path.
# In production, get_db_connection() uses PostgreSQL regardless of this value.
DATABASE = '/mnt/project/swarm_intelligence.db'

# ============================================================================
# PERSISTENT FILE STORAGE PATH
# ============================================================================
# Uploaded and generated files are stored here on the persistent disk.
# This replaces all previous /tmp/swarm_projects/ references.
STORAGE_PATH = '/mnt/project/swarm_projects/'

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

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.sendgrid.net')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'apikey')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or os.environ.get('SENDGRID_API_KEY')

ALERT_FROM_EMAIL = os.environ.get('ALERT_FROM_EMAIL', 'alerts@shiftworksolutions.com')
ALERT_TO_EMAIL = os.environ.get('ALERT_TO_EMAIL', '')

ENABLE_EMAIL_ALERTS = os.environ.get('ENABLE_EMAIL_ALERTS', 'false').lower() == 'true'
ENABLE_SCHEDULED_JOBS = os.environ.get('ENABLE_SCHEDULED_JOBS', 'false').lower() == 'true'

ALERT_CHECK_INTERVAL = int(os.environ.get('ALERT_CHECK_INTERVAL', 60))

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

ANTHROPIC_TIMEOUT = 180
OPENAI_TIMEOUT = 120
DEEPSEEK_TIMEOUT = 120
GEMINI_TIMEOUT = 120

# ============================================================================
# MODEL CONFIGURATIONS
# ============================================================================

CLAUDE_SONNET_MODEL = "claude-sonnet-4-20250514"
CLAUDE_OPUS_MODEL = "claude-opus-4-5-20251101"
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

CONFIDENCE_THRESHOLD_LOW = 0.7
COMPLEXITY_THRESHOLD = 0.8

# ============================================================================
# CONSENSUS VALIDATION
# ============================================================================

CONSENSUS_THRESHOLD = 0.85
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

DEFAULT_LEAD_SCAN_TIME = '07:00'
DEFAULT_REGULATORY_SCAN_TIME = '06:00'
DEFAULT_COMPETITOR_SCAN_TIME = '08:00'
DEFAULT_BRIEFING_TIME = '07:30'

EMAIL_PRIORITY_THRESHOLD = 'high'
MAX_ALERTS_PER_CATEGORY = 5
DISMISSED_ALERT_RETENTION_DAYS = 30

# I did no harm and this file is not truncated
