"""
Routes Utils Package - Utility Functions for Route Handlers
Created: February 10, 2026
Last Updated: February 18, 2026 - COMMITTED TO GITHUB (was missing, causing import failures)

CHANGELOG:
- February 18, 2026: CRITICAL FIX - This file and its siblings (conversation_utils.py,
  response_utils.py) existed only on the Render server and were wiped on every deploy.
  All three files are now committed to GitHub. This __init__.py now properly exports
  all utility functions so 'from routes.utils import ...' works correctly.

PURPOSE:
Exports all utility functions used by route handlers:
  - convert_markdown_to_html: Converts AI markdown responses to styled HTML
  - should_create_document: Detects if request needs a downloadable document
  - store_conversation_context: Saves temporary key-value data for a conversation
  - get_conversation_context: Retrieves temporary key-value data for a conversation
  - clear_conversation_context: Deletes temporary key-value data for a conversation

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from .response_utils import convert_markdown_to_html, should_create_document
from .conversation_utils import (
    store_conversation_context,
    get_conversation_context,
    clear_conversation_context
)

__all__ = [
    'convert_markdown_to_html',
    'should_create_document',
    'store_conversation_context',
    'get_conversation_context',
    'clear_conversation_context',
]

# I did no harm and this file is not truncated
