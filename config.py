"""
AI SWARM ORCHESTRATOR - Configuration
Created: January 18, 2026
Last Updated: July 01, 2026 - GPT4_MODEL -> gpt-5.5 (current OpenAI flagship)

CHANGELOG:
- July 01, 2026 (later same day): GPT4_MODEL -> "gpt-5.5"
  * "gpt-4-turbo-preview" was stale. GPT4_MODEL now defaults to the current OpenAI
    flagship "gpt-5.5" and is env-overridable via the GPT4_MODEL environment var.
  * PAIRED CODE CHANGE: call_gpt4() in ai_clients.py switched from 'max_tokens' to
    'max_completion_tokens' because the GPT-5 series rejects 'max_tokens' (HTTP 400).
  * GEMINI_MODEL intentionally left as-is: "gemini-1.5-pro" is shut down (404) and
    its SDK is deprecated; that fix is a separate google-genai migration step.
  * PURELY CORRECTIVE. No other setting changed. Rule 1 preserved.

- July 01, 2026: FIXED RETIRED ANTHROPIC MODEL STRINGS
  * Problem: CLAUDE_SONNET_MODEL was "claude-sonnet-4-20250514", which Anthropic
    has RETIRED. Live calls returned HTTP 404 not_found_error. Because every
    orchestration request goes through analyze_task_with_sonnet() (a Sonnet call)
    FIRST, this broke the entire swarm's orchestration, not just one path.
  * Fix: CLAUDE_SONNET_MODEL -> "claude-sonnet-4-6" (current valid string,
    verified against Anthropic's model list; matches app.py's health check).
  * Also fixed CLAUDE_OPUS_MODEL: "claude-opus-4-5-20251101" -> "claude-opus-4-8"
    (current flagship). The old Opus snapshot date was almost certainly invalid
    and would have 404'd on the next escalation to Opus.
  * Both are now os.environ.get(...) with the current strings as defaults, so a
    future model retirement can be handled by setting a Render env var
    (CLAUDE_SONNET_MODEL / CLAUDE_OPUS_MODEL) instead of a code deploy.
  * GPT4_MODEL ("gpt-4-turbo-preview") and GEMINI_MODEL ("gemini-1.5-pro") are
    likely also stale but are NOT the cause of this error and only run if a task
    is routed to those specialists. Left unchanged pending verification of the
    current OpenAI/Google strings.
  * PURELY CORRECTIVE. No other setting changed. Rule 1 preserved.

- June 30, 2026 - ADDED LOCAL GEMMA SETTINGS (Local AI Engine, Phase 5)

CHANGELOG:
- June 30, 2026: ADDED LOCAL GEMMA SETTINGS — LOCAL OFFLINE MODEL
  * Purpose: Configure the locally-hosted Gemma model (running in LM Studio on
    Jim's LG Gram, exposed to the internet via an ngrok tunnel) so the swarm can
    call it through orchestration/ai_clients.py -> call_local_gemma(). This is
    the "local engine" node of the Local AI Engine project: free, private,
    offline-capable inference.
  * Mirrors the existing DeepSeek provider pattern exactly — its pieces live in
    the matching sections of this file:
      - API KEYS section .......... LOCAL_GEMMA_API_KEY (dummy/door-password)
      - API TIMEOUTS section ...... LOCAL_GEMMA_TIMEOUT (longer than cloud APIs)
      - MODEL CONFIGURATIONS ...... LOCAL_GEMMA_MODEL ("google/gemma-4-e4b")
      - NEW dedicated block ....... LOCAL GEMMA CONFIGURATION
                                    (LOCAL_GEMMA_BASE_URL + ngrok header dict)
  * LOCAL_GEMMA_BASE_URL is read from a Render environment variable and defaults
    to None. When it is None, ai_clients.py leaves the local client disabled and
    call_local_gemma() returns a clean error dict — the swarm runs normally
    whether the laptop/tunnel is up or down.
  * NOTHING hardcoded. The ngrok URL and the optional door-password are read from
    the environment, exactly like every other secret in this file.
  * PURELY ADDITIVE. No existing variable, value, or line was changed or removed.
    Rule 1 (do no harm) preserved.

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

# ----------------------------------------------------------------------------
# Local Gemma "API key" (Added June 30, 2026)
# ----------------------------------------------------------------------------
# LM Studio does NOT require an API key by default, but the OpenAI client class
# we use to call it requires a non-empty string. So this defaults to the
# harmless placeholder 'lm-studio'.
#
# DOOR-PASSWORD (optional, future): if you later put a key-style lock on the
# tunnel/server, set the LOCAL_GEMMA_API_KEY environment variable in Render to
# that secret and the swarm will send it automatically — no code change needed.
LOCAL_GEMMA_API_KEY = os.environ.get('LOCAL_GEMMA_API_KEY', 'lm-studio')

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

# Local Gemma timeout (Added June 30, 2026)
# Set higher than the cloud APIs: the laptop generates ~5-15 tokens/sec, and the
# request also travels through the ngrok tunnel, so a generous ceiling avoids
# premature timeouts on longer answers. Overridable via env var.
LOCAL_GEMMA_TIMEOUT = int(os.environ.get('LOCAL_GEMMA_TIMEOUT', 300))

# ============================================================================
# MODEL CONFIGURATIONS
# ============================================================================

# Anthropic model strings (Updated July 01, 2026).
# FIX: "claude-sonnet-4-20250514" was RETIRED by Anthropic and returned a 404
# ("not_found_error"), which broke Sonnet — and because every orchestration
# request goes through Sonnet classification first, it broke the whole swarm.
# Corrected to the current valid string "claude-sonnet-4-6" (verified against
# Anthropic's model list; this is the same string app.py's health check already
# uses). Opus updated to the current flagship "claude-opus-4-8" — the old
# "claude-opus-4-5-20251101" snapshot date was almost certainly invalid too and
# would have 404'd on the next escalation. Both are now read from environment
# variables so a future model retirement is a Render env-var change, not a code
# deploy. Defaults are the current valid strings.
CLAUDE_SONNET_MODEL = os.environ.get('CLAUDE_SONNET_MODEL', 'claude-sonnet-4-6')
CLAUDE_OPUS_MODEL = os.environ.get('CLAUDE_OPUS_MODEL', 'claude-opus-4-8')
# GPT4_MODEL -> "gpt-5.5" (Updated July 01, 2026, later same day).
# "gpt-4-turbo-preview" was stale. GPT4_MODEL now defaults to the current OpenAI
# flagship "gpt-5.5" and is env-overridable (set GPT4_MODEL in Render to change it
# without a code deploy). IMPORTANT: the GPT-5 series requires
# 'max_completion_tokens' instead of 'max_tokens' on the chat.completions endpoint
# — call_gpt4() in ai_clients.py was updated in the same change to send that.
GPT4_MODEL = os.environ.get('GPT4_MODEL', 'gpt-5.5')
DEEPSEEK_MODEL = "deepseek-chat"
# GEMINI_MODEL: "gemini-1.5-pro" is SHUT DOWN by Google (requests return 404) and
# the old google-generativeai SDK that call_gemini() uses is deprecated. Fixing
# Gemini requires migrating to the new google-genai SDK + a current model
# ("gemini-2.5-flash") + a requirements.txt change — that is a SEPARATE step and is
# intentionally NOT done here so this change stays GPT-5.5-only and nothing
# half-changes. Left exactly as-is until the Gemini migration lands.
GEMINI_MODEL = "gemini-1.5-pro"

# Local Gemma model identifier (Added June 30, 2026)
# This must match the "API Model Identifier" shown in LM Studio's Developer panel
# exactly. Overridable via env var in case the local model is swapped later
# (e.g. to a Qwen3 model) without a code change.
LOCAL_GEMMA_MODEL = os.environ.get('LOCAL_GEMMA_MODEL', 'google/gemma-4-e4b')

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
# LOCAL GEMMA CONFIGURATION (LOCAL OFFLINE MODEL)  — Added June 30, 2026
# ============================================================================
# Gemma runs in LM Studio on Jim's laptop and is reachable over the internet via
# an ngrok tunnel. LM Studio serves an OpenAI-COMPATIBLE endpoint, so ai_clients.py
# talks to it with the same OpenAI() client class used for DeepSeek.
#
# LOCAL_GEMMA_BASE_URL must be the ngrok HTTPS URL with /v1 on the end, e.g.:
#       https://isolated-museum-likewise.ngrok-free.dev/v1
# It is read from the environment (set it in Render) and defaults to None. When
# None, the local client stays disabled and the swarm is completely unaffected.
LOCAL_GEMMA_BASE_URL = os.environ.get('LOCAL_GEMMA_BASE_URL')

# ngrok's FREE tier serves an HTML "browser warning" interstitial before letting
# a request through. That breaks automated JSON API calls. Sending this header
# tells ngrok to skip the interstitial and pass the request straight through.
# ai_clients.py attaches this as default_headers on the local Gemma client.
LOCAL_GEMMA_SKIP_NGROK_WARNING_HEADER = {"ngrok-skip-browser-warning": "true"}

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
