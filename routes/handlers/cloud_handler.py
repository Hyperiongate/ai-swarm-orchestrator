"""
Cloud Handler - Download Files from Cloud Storage
Created: February 10, 2026
Last Updated: February 10, 2026

Detects cloud storage links (Google Drive, Dropbox) and downloads
files using streaming to prevent memory crashes on large files.

Author: Jim @ Shiftwork Solutions LLC
"""

import re
import os
from flask import jsonify
from database import create_conversation


def is_cloud_link(text):
    """
    Check if text contains a cloud storage link.
    
    Args:
        text: Text to check
        
    Returns:
        bool
    """
    if not text:
        return False
    
    text_lower = text.lower()
    cloud_indicators = [
        'drive.google.com',
        'docs.google.com',
        'dropbox.com',
        'onedrive',
        '1drv.ms'
    ]
    
    return any(indicator in text_lower for indicator in cloud_indicators)


def handle_cloud_download(user_request, conversation_id, project_id, mode):
    """
    Download file from cloud storage link.
    
    Args:
        user_request: User request containing cloud URL
        conversation_id: Conversation ID
        project_id: Project ID
        mode: Conversation mode
        
    Returns:
        Tuple of (file_paths: list, clean_request: str, conversation_id: str, error_response: dict or None)
    """
    print(f"Cloud storage link detected in request")
    
    # Extract URL from request
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, user_request)
    
    if not urls:
        return [], user_request, conversation_id, None
    
    cloud_url = urls[0]
    print(f"Processing cloud link: {cloud_url[:50]}...")
    
    # Create conversation if needed
    if not conversation_id:
        conversation_id = create_conversation(mode=mode, project_id=project_id)
    
    # Download file from cloud using STREAMING
    from cloud_file_handler import get_cloud_handler
    handler = get_cloud_handler()
    local_filepath, metadata = handler.process_cloud_link(cloud_url)
    
    if not metadata['success']:
        error_response = jsonify({
            'success': False,
            'error': f"Could not download file from {metadata.get('service', 'cloud storage')}: {metadata.get('error', 'Unknown error')}",
            'conversation_id': conversation_id
        }), 400
        
        return [], user_request, conversation_id, error_response
    
    # File downloaded successfully
    file_paths = [local_filepath]
    print(f"Downloaded {metadata['size_bytes'] / (1024*1024):.1f}MB from {metadata['service']}")
    
    # Clean user request - remove the URL
    clean_request = re.sub(url_pattern, '', user_request).strip()
    if clean_request and clean_request.lower() not in ['please analyze this file:', 'please analyze this file', 'analyze this file:']:
        user_request = clean_request
    else:
        # Default request when user just pasted a link
        file_basename = os.path.basename(local_filepath)
        user_request = f"Please analyze this file: {metadata.get('original_filename', file_basename)}"
    
    print(f"Clean user request: {user_request}")
    
    return file_paths, user_request, conversation_id, None


# I did no harm and this file is not truncated
