"""
Utilities Package - Helper Functions for Orchestration
Created: February 10, 2026

Exports all utility functions for use in handlers.

Author: Jim @ Shiftwork Solutions LLC
"""

from .response_utils import (
    convert_markdown_to_html,
    should_create_document
)

from .conversation_utils import (
    store_conversation_context,
    get_conversation_context,
    clear_conversation_context
)

from .document_utils import (
    generate_document_title,
    categorize_document
)

__all__ = [
    'convert_markdown_to_html',
    'should_create_document',
    'store_conversation_context',
    'get_conversation_context',
    'clear_conversation_context',
    'generate_document_title',
    'categorize_document'
]

# I did no harm and this file is not truncated
