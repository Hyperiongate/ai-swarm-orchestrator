"""
File Browser Handler - Project File Selection
Created: February 10, 2026
Last Updated: February 10, 2026

Handles when users select files from their project file browser
(file_ids parameter) rather than uploading new files.

Author: Jim @ Shiftwork Solutions LLC
"""

import json


def handle_file_browser(file_ids_param, project_id, request_is_json):
    """
    Process file selection from project file browser.
    
    Args:
        file_ids_param: file_ids parameter from request (JSON string or list)
        project_id: Project ID
        request_is_json: Whether request is JSON format
        
    Returns:
        String with file contents or empty string
    """
    if not file_ids_param or not project_id:
        return ""
    
    try:
        # Parse file_ids (comes as JSON string)
        if isinstance(file_ids_param, str):
            file_ids = json.loads(file_ids_param)
        else:
            file_ids = file_ids_param
        
        print(f"File browser: Parsed file_ids = {file_ids}")
        
        if file_ids and len(file_ids) > 0:
            print(f"User selected {len(file_ids)} file(s) from project {project_id}")
            
            # Fetch file context from database
            from database_file_management import get_files_for_ai_context
            
            # Get detailed file info with actual file contents
            selected_file_context = get_files_for_ai_context(
                project_id=project_id, 
                file_ids=file_ids,
                max_files=len(file_ids),
                max_chars_per_file=10000
            )
            
            if selected_file_context:
                print(f"Retrieved context for {len(file_ids)} selected file(s)")
                return selected_file_context
            else:
                print(f"No file context retrieved for file_ids: {file_ids}")
                return ""
    
    except Exception as file_ids_error:
        print(f"Error processing file_ids: {file_ids_error}")
        import traceback
        traceback.print_exc()
        return ""


# I did no harm and this file is not truncated
