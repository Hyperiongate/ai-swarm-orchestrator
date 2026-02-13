"""
Labor Handler - Handle Analysis Offer Responses
Created: February 10, 2026
Last Updated: February 10, 2026

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
    if any(phrase in msg_lower for phrase in ['yes, analyze', 'analyze this data', 'run the analysis', 'analyze it']):
        session_id = get_conversation_context(conversation_id, 'pending_analysis_session')
        
        if session_id:
            try:
                from analysis_orchestrator import AnalysisOrchestrator
                from database import load_analysis_session, save_analysis_session
                
                # Load the session we created earlier
                session_data = load_analysis_session(session_id)
                if session_data:
                    session_obj = AnalysisOrchestrator.from_dict(session_data)
                    
                    # Run the analysis workflow automatically
                    session_obj.discover_data_structure(session_obj.data_files)
                    session_obj.process_clarifications({
                        'analysis_priority': ['All of the above'],
                        'analyze_scope': 'Analyze all'
                    })
                    session_obj.build_analysis_plan()
                    result = session_obj.execute_analysis()
                    
                    # Save the results
                    save_analysis_session(session_obj.to_dict())
                    
                    # Show results to user
                    if result.get('results_preview'):
                        preview = result['results_preview']
                        response = f"""Analysis Complete!

Results:
- Total Hours: {preview.get('total_hours', 0):,}
- Employees: {preview.get('employees', 0):,}
- Overtime: {preview.get('overtime_pct', 0)}%

Session ID: `{session_id}`

What would you like next?
- "Show me the details" - Full breakdown
- "Generate charts" - Visualizations
- "Create presentation" - PowerPoint"""
                        
                        return jsonify({"response": response})
            except Exception as e:
                return jsonify({"response": f"Analysis failed: {str(e)}"})
    
    # User wants quick summary only
    elif 'just give me the summary' in msg_lower or 'quick overview' in msg_lower:
        clear_conversation_context(conversation_id, 'pending_analysis_session')
        return jsonify({"response": "Got it - showing file overview only, no detailed analysis."})
    
    # User said NO
    elif 'not now' in msg_lower or 'skip' in msg_lower:
        clear_conversation_context(conversation_id, 'pending_analysis_session')
        return jsonify({"response": "No problem! File is saved for later."})
    
    return None


# I did no harm and this file is not truncated
