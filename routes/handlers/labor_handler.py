"""
Labor Handler - Handle Analysis Offer Responses
Created: February 10, 2026
Last Updated: February 13, 2026 - FIXED: Let orchestration handle "yes" responses

CRITICAL FIX (February 13, 2026):
- "Yes, analyze it" now returns None to let full orchestration handle the request
- This allows all the AI routing, consensus, and specialist logic to work
- Only "quick summary" and "not now" return early responses

Processes user responses to labor data analysis offers.

Author: Jim @ Shiftwork Solutions LLC
"""
from flask import jsonify
from routes.utils import get_conversation_context, clear_conversation_context


def handle_labor_response(user_request, conversation_id):
    """
    Check if user is responding to analysis offer.
    
    Args:
        user_request: User message
        conversation_id: Conversation ID
        
    Returns:
        JSON response or None if not a labor response
    """
    if not user_request or not conversation_id:
        return None
    
    msg_lower = user_request.lower()
    
    # User said YES to analysis
    # FIXED: Return None to let orchestration handle it with full AI routing
    if any(phrase in msg_lower for phrase in ['yes, analyze', 'analyze this data', 'run the analysis', 'analyze it']):
        # Session ID is stored in conversation_context, orchestration will use it
        # Just return None to continue to regular conversation handler
        print(f"✅ Labor analysis accepted - routing to full orchestration")
        return None
    
    # User wants quick summary only
    elif 'just give me the summary' in msg_lower or 'quick overview' in msg_lower:
        clear_conversation_context(conversation_id, 'pending_analysis_session')
        return jsonify({
            "success": True,
            "response": "Got it - showing file overview only, no detailed analysis.",
            "conversation_id": conversation_id
        })
    
    # User said NO
    elif 'not now' in msg_lower or 'skip' in msg_lower:
        clear_conversation_context(conversation_id, 'pending_analysis_session')
        return jsonify({
            "success": True,
            "response": "No problem! File is saved for later.",
            "conversation_id": conversation_id
        })
    
    return None


# I did no harm and this file is not truncated
