"""
Introspection Package
Created: January 25, 2026
Last Updated: January 25, 2026

Emulated self-awareness for the AI Swarm Orchestrator.
This package provides self-monitoring, boundary awareness, confidence calibration,
self-modification proposals, and goal alignment reflection.

DESIGN PRINCIPLE: Observer Pattern
- Introspection watches the swarm but never interferes
- All insights are advisory - Jim decides what to implement
- Can be completely disabled without affecting core operations

COMPONENTS:
- self_monitor.py: Performance trend analysis (Component 1)
- boundary_tracker.py: Capability limitation mapping (Component 2)
- confidence_calibrator.py: Calibration analysis (Component 3)
- proposal_generator.py: Self-modification proposals (Component 4)
- goal_aligner.py: Objective alignment reflection (Component 5)
- reflection_synthesizer.py: Combines all into narrative

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from introspection.self_monitor import SelfMonitor, get_self_monitor
from introspection.introspection_engine import (
    IntrospectionEngine,
    get_introspection_engine,
    check_introspection_notifications,
    is_introspection_request
)

__all__ = [
    'SelfMonitor',
    'get_self_monitor',
    'IntrospectionEngine',
    'get_introspection_engine',
    'check_introspection_notifications',
    'is_introspection_request'
]

# I did no harm and this file is not truncated
