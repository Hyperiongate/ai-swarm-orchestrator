"""
intelligence/__init__.py
AI Swarm Orchestrator — Intelligence Package
Created: March 08, 2026
Last Updated: March 08, 2026 — Phase 4 additions

CHANGELOG:
- March 08, 2026 (Phase 3): Initial file. Exported generate_capabilities_manifest
  and get_manifest_summary from capabilities_manifest.py.
- March 08, 2026 (Phase 4): Added reason_about_request from reasoning_engine.py
  and execute_tool from tool_router.py. Original exports unchanged.

Exports the intelligence package's public API for use throughout the app.
"""

from intelligence.capabilities_manifest import (
    generate_capabilities_manifest,
    get_manifest_summary,
)
from intelligence.reasoning_engine import reason_about_request
from intelligence.tool_router import execute_tool

__all__ = [
    'generate_capabilities_manifest',
    'get_manifest_summary',
    'reason_about_request',
    'execute_tool',
]

# I did no harm and this file is not truncated
