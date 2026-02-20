"""
File Upload Handler - Process Uploaded Files
Created: February 10, 2026
Last Updated: February 19, 2026 - INDEX UPLOADED FILES INTO KNOWLEDGE BASE

CHANGELOG:

- February 19, 2026: INDEX UPLOADED FILES INTO KNOWLEDGE BASE
  * PROBLEM: Files uploaded through the app UI were analyzed on-demand but never
    added to the knowledge base index. They had no lasting value beyond the single
    conversation in which they were uploaded. Future conversations had no awareness
    of previously uploaded documents.
  * FIX: After every successful file save, call knowledge_base.index_single_file()
    to add the file to the live KB index immediately. The file then becomes
    searchable in all future conversations via semantic search and gets injected
    as system prompt context just like the project_files/ documents.
  * Gets the KB singleton via sys.modules['app'].knowledge_base (same pattern
    used throughout orchestration_handler.py) so no new imports or circular deps.
  * Wrapped in try/except - KB indexing failure never breaks an upload. The file
    is always saved successfully regardless of KB outcome.
  * Logs success/failure with word count for visibility in Render logs.
  * Labor detection flow is unchanged - labor files get the analysis offer as
    before, AND are also indexed into the KB.

- February 13, 2026: FIXED LABOR DETECTION RESPONSE FORMAT
  * Added "success": True to labor detection response
  * Added "conversation_id": conversation_id to response
  * Fixes "Error: undefined" bug in frontend

Author: Jim @ Shiftwork Solutions LLC
"""
import os
import sys
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


def _index_file_into_kb(file_path):
    """
    Index a single uploaded file into the live knowledge base.

    Gets the KB singleton from app module (same pattern as orchestration_handler.py).
    Wrapped so any failure is logged but never raises - upload always succeeds.

    Added February 19, 2026.
    """
    try:
        app_module = sys.modules.get('app')
        knowledge_base = getattr(app_module, 'knowledge_base', None) if app_module else None

        if not knowledge_base:
            print(f"KB: Skipping index - knowledge base not available")
            return

        result = knowledge_base.index_single_file(file_path)

        if result['success']:
            print(f"KB: Successfully indexed '{result['filename']}' "
                  f"({result['word_count']} words, category: {result.get('category', 'unknown')})")
        else:
            print(f"KB: Could not index '{result['filename']}': {result.get('error', 'unknown error')}")

    except Exception as e:
        print(f"KB: index_file_into_kb failed for {file_path}: {e}")
        # Never re-raise - upload must succeed regardless of KB outcome


def handle_file_upload(files, project_id, conversation_id):
    """
    Handle file uploads, check for labor data, and index into knowledge base.

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

            print(f"Saved uploaded file: {filename}")

            # ----------------------------------------------------------------
            # INDEX INTO KNOWLEDGE BASE (Added February 19, 2026)
            # Do this immediately after saving, before labor detection,
            # so the file is in the KB regardless of what happens next.
            # ----------------------------------------------------------------
            _index_file_into_kb(file_path)

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
                            # FIXED: Added "success": True and "conversation_id" (Feb 13, 2026)
                            return file_paths, jsonify({
                                "success": True,
                                "response": offer_message,
                                "mode": "analysis_offer",
                                "session_id": session_result['session_id'],
                                "conversation_id": conversation_id
                            })
                except Exception as e:
                    print(f"Labor detection failed: {e}")
                    # If detection fails, just continue normally

            file_paths.append(file_path)

    return file_paths, None


# I did no harm and this file is not truncated
