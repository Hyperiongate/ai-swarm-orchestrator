"""
BULLETPROOF PROJECT API ROUTES
Created: January 30, 2026
Last Updated: January 30, 2026

Complete Flask blueprint for project management.
Integrates with ProjectManager for reliable project handling.

ENDPOINTS:
- POST   /api/projects/create          - Create new project
- GET    /api/projects                 - List all projects
- GET    /api/projects/<id>            - Get project details
- PUT    /api/projects/<id>            - Update project
- POST   /api/projects/<id>/files      - Upload files
- GET    /api/projects/<id>/files      - List files
- GET    /api/projects/<id>/files/<id> - Download file
- DELETE /api/projects/<id>/files/<id> - Delete file
- GET    /api/projects/<id>/conversation - Get conversation history
- POST   /api/projects/<id>/conversation - Add message
- GET    /api/projects/<id>/context    - Get all context
- PUT    /api/projects/<id>/context    - Set context value
- GET    /api/projects/<id>/summary    - Get complete summary

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
from project_manager_bulletproof import get_project_manager

# Create blueprint
projects_bp = Blueprint('projects', __name__)

# Get project manager instance
pm = get_project_manager()


# ============================================================================
# PROJECT MANAGEMENT ENDPOINTS
# ============================================================================

@projects_bp.route('/api/projects/create', methods=['POST'])
def create_project():
    """
    Create a new project.
    
    Request JSON:
        {
            "client_name": "ABC Manufacturing",
            "industry": "Automotive",
            "facility_type": "Assembly Plant",
            "metadata": {...}
        }
    """
    try:
        data = request.json or {}
        
        client_name = data.get('client_name')
        if not client_name:
            return jsonify({'success': False, 'error': 'client_name required'}), 400
        
        industry = data.get('industry')
        facility_type = data.get('facility_type')
        metadata = data.get('metadata')
        
        project = pm.create_project(
            client_name=client_name,
            industry=industry,
            facility_type=facility_type,
            metadata=metadata
        )
        
        return jsonify({
            'success': True,
            'project': project
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects', methods=['GET'])
def list_projects():
    """
    List all projects.
    
    Query params:
        - status: 'active', 'archived', 'all' (default: 'active')
        - limit: max results (default: 50)
    """
    try:
        status = request.args.get('status', 'active')
        limit = request.args.get('limit', 50, type=int)
        
        projects = pm.list_projects(status=status, limit=limit)
        
        return jsonify({
            'success': True,
            'projects': projects,
            'count': len(projects)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get a single project by ID"""
    try:
        project = pm.get_project(project_id)
        
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        return jsonify({
            'success': True,
            'project': project
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/<project_id>', methods=['PUT'])
def update_project(project_id):
    """
    Update project fields.
    
    Request JSON:
        {
            "client_name": "Updated Name",
            "project_phase": "implementation",
            "status": "active",
            "metadata": {...}
        }
    """
    try:
        data = request.json or {}
        
        success = pm.update_project(project_id, **data)
        
        if not success:
            return jsonify({'success': False, 'error': 'Update failed'}), 400
        
        # Get updated project
        project = pm.get_project(project_id)
        
        return jsonify({
            'success': True,
            'project': project
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/search', methods=['GET'])
def search_projects():
    """
    Search for projects.
    
    Query params:
        - q: search term
        - field: field to search in (client_name, industry, facility_type)
    """
    try:
        search_term = request.args.get('q', '')
        search_field = request.args.get('field', 'client_name')
        
        if not search_term:
            return jsonify({'success': False, 'error': 'Search term required'}), 400
        
        projects = pm.search_projects(search_term, search_in=search_field)
        
        return jsonify({
            'success': True,
            'projects': projects,
            'count': len(projects),
            'search_term': search_term
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# FILE MANAGEMENT ENDPOINTS
# ============================================================================

@projects_bp.route('/api/projects/<project_id>/files', methods=['POST'])
def upload_files(project_id):
    """
    Upload files to a project.
    
    Expects multipart/form-data with 'files' field.
    """
    try:
        # Verify project exists
        project = pm.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        # Check for files
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        
        if not files or files[0].filename == '':
            return jsonify({'success': False, 'error': 'No files selected'}), 400
        
        uploaded_files = []
        
        for file in files:
            if file and file.filename:
                # Save to temp location first
                filename = secure_filename(file.filename)
                temp_path = f'/tmp/{filename}'
                file.save(temp_path)
                
                try:
                    # Add to project
                    file_info = pm.add_file(
                        project_id=project_id,
                        file_path=temp_path,
                        original_filename=filename
                    )
                    
                    uploaded_files.append(file_info)
                    
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
        
        return jsonify({
            'success': True,
            'files': uploaded_files,
            'count': len(uploaded_files)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/<project_id>/files', methods=['GET'])
def list_files(project_id):
    """List all files in a project"""
    try:
        # Verify project exists
        project = pm.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        include_deleted = request.args.get('include_deleted', 'false').lower() == 'true'
        
        files = pm.list_files(project_id, include_deleted=include_deleted)
        
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/<project_id>/files/<file_id>', methods=['GET'])
def download_file(project_id, file_id):
    """Download a file from a project"""
    try:
        file_info = pm.get_file(file_id)
        
        if not file_info:
            return jsonify({'error': 'File not found'}), 404
        
        # Verify file belongs to this project
        if file_info['project_id'] != project_id:
            return jsonify({'error': 'File does not belong to this project'}), 403
        
        # Send file
        return send_file(
            file_info['file_path'],
            as_attachment=True,
            download_name=file_info['original_filename'],
            mimetype=file_info.get('mime_type', 'application/octet-stream')
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/api/projects/<project_id>/files/<file_id>', methods=['DELETE'])
def delete_file(project_id, file_id):
    """Delete a file from a project"""
    try:
        file_info = pm.get_file(file_id)
        
        if not file_info:
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Verify file belongs to this project
        if file_info['project_id'] != project_id:
            return jsonify({'success': False, 'error': 'File does not belong to this project'}), 403
        
        hard_delete = request.args.get('hard', 'false').lower() == 'true'
        
        success = pm.delete_file(file_id, hard_delete=hard_delete)
        
        return jsonify({
            'success': success,
            'message': 'File deleted successfully' if success else 'Delete failed'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# CONVERSATION MANAGEMENT ENDPOINTS
# ============================================================================

@projects_bp.route('/api/projects/<project_id>/conversation', methods=['GET'])
def get_conversation(project_id):
    """
    Get conversation history for a project.
    
    Query params:
        - conversation_id: filter by conversation ID
        - limit: max messages (default: 100)
    """
    try:
        # Verify project exists
        project = pm.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        conversation_id = request.args.get('conversation_id')
        limit = request.args.get('limit', 100, type=int)
        
        messages = pm.get_conversation_history(
            project_id=project_id,
            conversation_id=conversation_id,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'messages': messages,
            'count': len(messages)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/<project_id>/conversation', methods=['POST'])
def add_message(project_id):
    """
    Add a message to project conversation.
    
    Request JSON:
        {
            "conversation_id": "conv_123",
            "role": "user",
            "content": "Message text",
            "file_ids": ["file_1", "file_2"],
            "metadata": {...}
        }
    """
    try:
        # Verify project exists
        project = pm.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        data = request.json or {}
        
        conversation_id = data.get('conversation_id')
        role = data.get('role')
        content = data.get('content')
        
        if not all([conversation_id, role, content]):
            return jsonify({'success': False, 'error': 'conversation_id, role, and content required'}), 400
        
        if role not in ['user', 'assistant', 'system']:
            return jsonify({'success': False, 'error': 'role must be user, assistant, or system'}), 400
        
        file_ids = data.get('file_ids')
        metadata = data.get('metadata')
        
        pm.add_message(
            project_id=project_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            file_ids=file_ids,
            metadata=metadata
        )
        
        return jsonify({
            'success': True,
            'message': 'Message added successfully'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# CONTEXT MANAGEMENT ENDPOINTS
# ============================================================================

@projects_bp.route('/api/projects/<project_id>/context', methods=['GET'])
def get_context(project_id):
    """
    Get all context for a project.
    
    Or get specific key with ?key=<key>
    """
    try:
        # Verify project exists
        project = pm.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        key = request.args.get('key')
        
        if key:
            # Get specific key
            value = pm.get_context(project_id, key)
            return jsonify({
                'success': True,
                'key': key,
                'value': value
            })
        else:
            # Get all context
            context = pm.get_all_context(project_id)
            return jsonify({
                'success': True,
                'context': context
            })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/api/projects/<project_id>/context', methods=['PUT'])
def set_context(project_id):
    """
    Set context value for a project.
    
    Request JSON:
        {
            "key": "context_key",
            "value": "context_value" or {...}
        }
    """
    try:
        # Verify project exists
        project = pm.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        data = request.json or {}
        
        key = data.get('key')
        value = data.get('value')
        
        if not key:
            return jsonify({'success': False, 'error': 'key required'}), 400
        
        pm.set_context(project_id, key, value)
        
        return jsonify({
            'success': True,
            'message': f'Context {key} set successfully'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# SUMMARY ENDPOINT
# ============================================================================

@projects_bp.route('/api/projects/<project_id>/summary', methods=['GET'])
def get_summary(project_id):
    """Get complete project summary with files, messages, and context"""
    try:
        summary = pm.get_project_summary(project_id)
        
        if not summary:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        return jsonify({
            'success': True,
            'summary': summary
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# I did no harm and this file is not truncated
