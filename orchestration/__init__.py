"""
Orchestration Package
Created: January 21, 2026
Last Updated: January 29, 2026 - ADDED SYSTEM CAPABILITIES

All AI orchestration logic lives here.

CRITICAL UPDATE (January 29, 2026):
- Added system_capabilities module for AI self-awareness
- AI now knows what it can do (file handling, folders, analysis)
- Capability manifest injected into all AI calls

Author: Jim @ Shiftwork Solutions LLC
"""

# Import existing AI clients
from orchestration.ai_clients import (
    call_claude_sonnet,
    call_claude_opus,
    call_gpt4,
    call_deepseek,
    call_gemini
)

# Import existing task analysis
from orchestration.task_analysis import (
    analyze_task_with_sonnet,
    handle_with_opus,
    execute_specialist_task,
    get_learning_context
)

# Import existing consensus validation
from orchestration.consensus import validate_with_consensus

# Import NEW capability system (January 29, 2026)
from orchestration.system_capabilities import (
    get_system_capabilities_prompt,
    inject_capabilities_into_prompt,
    can_handle_files,
    can_create_folders,
    can_save_files,
    can_access_files,
    can_analyze_files,
    get_supported_file_types,
    get_capability_summary
)

# Export everything (existing + new)
__all__ = [
    # Existing AI clients
    'call_claude_sonnet',
    'call_claude_opus',
    'call_gpt4',
    'call_deepseek',
    'call_gemini',
    # Existing task analysis
    'analyze_task_with_sonnet',
    'handle_with_opus',
    'execute_specialist_task',
    'get_learning_context',
    # Existing consensus
    'validate_with_consensus',
    # NEW capability system
    'get_system_capabilities_prompt',
    'inject_capabilities_into_prompt',
    'can_handle_files',
    'can_create_folders',
    'can_save_files',
    'can_access_files',
    'can_analyze_files',
    'get_supported_file_types',
    'get_capability_summary'
]

# I did no harm and this file is not truncated
