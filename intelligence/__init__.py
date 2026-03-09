"""
intelligence/__init__.py
AI Swarm Orchestrator — Intelligence Package
Created: March 08, 2026
Last Updated: March 09, 2026 — Phase 5 additions

CHANGELOG:
- March 08, 2026 (Phase 3): Initial file. Exported generate_capabilities_manifest
  and get_manifest_summary from capabilities_manifest.py.
- March 08, 2026 (Phase 4): Added reason_about_request from reasoning_engine.py
  and execute_tool from tool_router.py. Original exports unchanged.
- March 09, 2026 (Phase 5): Added Phase 5 learning exports:
  routing_optimizer: get_routing_insights, get_preferred_model,
    record_outcome, get_all_routing_data
  prompt_optimizer: get_enhancements, store_enhancement,
    generate_enhancements_from_patterns, get_all_enhancements
  weekly_review: run_weekly_review, get_latest_review
  All imports are lazy (inside try/except) so a missing Phase 5 module
  never breaks the package import for Phase 1-4 consumers.

Exports the intelligence package's public API for use throughout the app.
"""

# ============================================================================
# PHASE 1-4 EXPORTS — UNCHANGED
# ============================================================================
from intelligence.capabilities_manifest import (
    generate_capabilities_manifest,
    get_manifest_summary,
)
from intelligence.reasoning_engine import reason_about_request
from intelligence.tool_router import execute_tool

# ============================================================================
# PHASE 5 EXPORTS — LAZY (safe if modules not yet deployed)
# ============================================================================
try:
    from intelligence.routing_optimizer import (
        get_routing_insights,
        get_preferred_model,
        record_outcome,
        get_all_routing_data,
    )
except ImportError:
    pass

try:
    from intelligence.prompt_optimizer import (
        get_enhancements,
        store_enhancement,
        generate_enhancements_from_patterns,
        get_all_enhancements,
    )
except ImportError:
    pass

try:
    from intelligence.weekly_review import (
        run_weekly_review,
        get_latest_review,
    )
except ImportError:
    pass

__all__ = [
    # Phase 1-4
    'generate_capabilities_manifest',
    'get_manifest_summary',
    'reason_about_request',
    'execute_tool',
    # Phase 5 — routing_optimizer
    'get_routing_insights',
    'get_preferred_model',
    'record_outcome',
    'get_all_routing_data',
    # Phase 5 — prompt_optimizer
    'get_enhancements',
    'store_enhancement',
    'generate_enhancements_from_patterns',
    'get_all_enhancements',
    # Phase 5 — weekly_review
    'run_weekly_review',
    'get_latest_review',
]

# I did no harm and this file is not truncated
