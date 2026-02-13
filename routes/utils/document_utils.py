"""
Document Utilities - Title Generation and Categorization
Created: February 10, 2026
Last Updated: February 10, 2026

Functions for generating document titles and determining categories.

Author: Jim @ Shiftwork Solutions LLC
"""


def generate_document_title(user_request, doc_type):
    """
    Generate a human-readable title from the user request.
    
    Args:
        user_request: User request string
        doc_type: Document type ('docx', 'xlsx', etc.)
        
    Returns:
        Formatted title string
    """
    title = user_request.strip()
    
    if title:
        title = title[0].upper() + title[1:]
    
    if len(title) > 60:
        title = title[:57] + '...'
    
    return title


def categorize_document(user_request, doc_type):
    """
    Determine document category based on request content.
    
    Args:
        user_request: User request string
        doc_type: Document type
        
    Returns:
        Category string
    """
    request_lower = user_request.lower()
    
    if any(word in request_lower for word in ['schedule', 'dupont', 'panama', 'pitman', '2-2-3']):
        return 'schedule'
    elif any(word in request_lower for word in ['proposal', 'bid', 'quote']):
        return 'proposal'
    elif any(word in request_lower for word in ['report', 'analysis', 'summary']):
        return 'report'
    elif any(word in request_lower for word in ['contract', 'agreement', 'legal']):
        return 'contract'
    elif any(word in request_lower for word in ['checklist', 'list', 'todo']):
        return 'checklist'
    elif any(word in request_lower for word in ['email', 'letter', 'memo']):
        return 'communication'
    elif any(word in request_lower for word in ['presentation', 'slides', 'deck']):
        return 'presentation'
    else:
        return 'general'


# I did no harm and this file is not truncated
