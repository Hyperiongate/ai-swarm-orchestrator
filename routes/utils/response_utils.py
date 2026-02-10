"""
Response Utilities - Formatting and Conversion
Created: February 10, 2026
Last Updated: February 10, 2026

Functions for converting and formatting AI responses for display.

Author: Jim @ Shiftwork Solutions LLC
"""


def convert_markdown_to_html(text):
    """
    Convert markdown text to styled HTML.
    
    Args:
        text: Markdown-formatted text
        
    Returns:
        HTML-formatted string with styling
    """
    if not text:
        return text
    
    import markdown
    html = markdown.markdown(text, extensions=['extra', 'nl2br'])
    return f'<div style="line-height: 1.8; color: #333;">{html}</div>'


def should_create_document(user_request):
    """
    Determine if we should create a downloadable document.
    
    Args:
        user_request: User request string
        
    Returns:
        Tuple of (should_create: bool, doc_type: str or None)
        
    Examples:
        >>> should_create_document("create a report")
        (True, 'docx')
        >>> should_create_document("what is the weather")
        (False, None)
    """
    doc_keywords = [
        'create', 'generate', 'make', 'write', 'draft', 'prepare',
        'document', 'report', 'proposal', 'presentation', 'schedule',
        'contract', 'agreement', 'summary', 'analysis'
    ]
    
    request_lower = user_request.lower()
    
    for keyword in doc_keywords:
        if keyword in request_lower:
            # Determine document type
            if 'presentation' in request_lower or 'powerpoint' in request_lower or 'slides' in request_lower:
                return True, 'pptx'
            elif 'spreadsheet' in request_lower or 'excel' in request_lower:
                return True, 'xlsx'
            elif 'pdf' in request_lower:
                return True, 'pdf'
            else:
                return True, 'docx'
    
    return False, None


# I did no harm and this file is not truncated
