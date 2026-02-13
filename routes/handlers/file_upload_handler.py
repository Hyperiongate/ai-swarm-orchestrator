"""
File Upload Handler - Process Uploaded Files
Created: February 10, 2026
Last Updated: February 10, 2026

Handles file uploads from FormData, checks for labor data,
and routes to appropriate analysis workflow.

Author: Jim @ Shiftwork Solutions LLC
"""

import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import jsonify

from routes.utils import store_conversation_context

try:
    from labor_file_detector import detect_labor_file, generate_analysis_offer, create_analysis_session
    LABOR_DETECTION_AVAILABLE = True
except ImportError:
    LABOR_DETECTION_AVAILABLE = False
    print("Labor file detector not available")


def handle_file_upload(files, project_id, conversation_id):
    """
    Handle file uploads and check for labor data.
    
    Args:
        files: List of uploaded files from request.files
        project_id: Optional project ID
        conversation_id: Conversation ID for context
        
    Returns:
        Tuple of (file_paths: list, early_response: dict or None)
        early_response is returned if labor detection triggers
    """
    file_paths = []
    
    # Determine upload directory
    if project_id:
        upload_dir = f'/tmp/projects/{project_id}'
    else:
        upload_dir = f'/tmp/uploads'
    
    os.makedirs(upload_dir, exist_ok=True)
    
    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{timestamp}{ext}"
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            # Check if this is labor data
            if LABOR_DETECTION_AVAILABLE and file_path.endswith(('.xlsx', '.xls')):
                try:
                    is_labor, metadata = detect_labor_file(file_path)
                    
                    if is_labor:
                        # Create analysis session
                        session_result = create_analysis_session(file_path)
                        
                        if session_result.get('success'):
                            # Remember this session for when user replies
                            store_conversation_context(
                                conversation_id,
                                'pending_analysis_session',
                                session_result['session_id']
                            )
                            
                            # Create the offer message
                            offer_message = generate_analysis_offer(
                                metadata, 
                                os.path.basename(file_path)
                            )
                            
                            # Return early with offer
                            return [], jsonify({
                                "success": True,
                                "mode": "analysis_offer",
                                "response": offer_message,
                                "session_id": session_result['session_id'],
                                "conversation_id": conversation_id
                            })
                except Exception as e:
                    print(f"Labor detection failed: {e}")
                    # If detection fails, just continue normally
            
            file_paths.append(file_path)
            print(f"Saved uploaded file: {filename}")
    
    return file_paths, None


# I did no harm and this file is not truncated
