"""
Orchestration Package
All AI orchestration logic lives here.
"""

from orchestration.ai_clients import (
    call_claude_sonnet,
    call_claude_opus,
    call_gpt4,
    call_deepseek,
    call_gemini
)

from orchestration.task_analysis import (
    analyze_task_with_sonnet,
    handle_with_opus,
    execute_specialist_task,
    get_learning_context
)

from orchestration.consensus import validate_with_consensus

__all__ = [
    'call_claude_sonnet',
    'call_claude_opus',
    'call_gpt4',
    'call_deepseek',
    'call_gemini',
    'analyze_task_with_sonnet',
    'handle_with_opus',
    'execute_specialist_task',
    'get_learning_context',
    'validate_with_consensus'
]

# I did no harm and this file is not truncated
