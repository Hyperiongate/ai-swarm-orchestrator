"""
Introspection Package
Created: January 25, 2026
Last Updated: February 27, 2026 - FIXED package exports so INTROSPECTION_AVAILABLE=True

PURPOSE:
Emulated self-awareness for the AI Swarm Orchestrator.
Provides self-monitoring, confidence calibration, and goal alignment reflection.

CHANGELOG:
- February 27, 2026: FIXED __init__.py exports
  PROBLEM: Previous __init__.py (created in error by Claude) imported symbols
    that didn't exist OR didn't export the symbols that routes/introspection.py
    needed. This caused ImportError at startup, setting INTROSPECTION_AVAILABLE=False,
    silently disabling all introspection endpoints with 503 responses.
  FIX: Export exactly the four symbols routes/introspection.py imports:
    - get_introspection_engine
    - check_introspection_notifications
    - is_introspection_request
    - IntrospectionEngine (for type hints)
  Also export SelfMonitor for direct use if needed.
  All imports come from modules that actually exist on disk.

DESIGN PRINCIPLE: Observer Pattern
- Introspection watches the swarm but never interferes
- All insights are advisory - Jim decides what to implement
- Can be completely disabled without affecting core operations

COMPONENTS CURRENTLY ACTIVE (Phase 1):
- self_monitor.py: Performance trend analysis (Component 1)  ACTIVE
- introspection_engine.py: Main orchestrator                 ACTIVE

COMPONENTS STUBBED (future phases, handled inside introspection_engine.py):
- boundary_tracker.py: Capability limitation mapping         Phase 2
- confidence_calibrator.py: Calibration analysis             Phase 2
- proposal_generator.py: Self-modification proposals         Phase 3
- goal_aligner.py: Objective alignment reflection            Phase 3
- reflection_synthesizer.py: Narrative synthesis             Phase 3

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from introspection.self_monitor import SelfMonitor, get_self_monitor

from introspection.introspection_engine import (
    IntrospectionEngine,
    get_introspection_engine,
    check_introspection_notifications,
    is_introspection_request,
    mark_notification_shown,
    BUSINESS_OBJECTIVES,
    INTROSPECTION_TRIGGERS
)

__all__ = [
    # Self Monitor
    'SelfMonitor',
    'get_self_monitor',

    # Introspection Engine - main orchestrator
    'IntrospectionEngine',
    'get_introspection_engine',

    # Utility functions used by routes/introspection.py
    'check_introspection_notifications',
    'is_introspection_request',
    'mark_notification_shown',

    # Constants
    'BUSINESS_OBJECTIVES',
    'INTROSPECTION_TRIGGERS',
]

# I did no harm and this file is not truncated
