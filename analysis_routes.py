"""
Analysis Engine API Routes
Created: February 8, 2026
Last Updated: February 8, 2026

Flask blueprint for analysis workflow endpoints.
Provides the API layer for the Analysis Orchestrator.

Author: Shiftwork Solutions LLC
Phase: 0A - Foundation
"""

from flask import Blueprint, request, jsonify, send_file, current_app
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
import traceback

# Import analysis orchestrator (will be added to repo)
try:
    from analysis_orchestrator import (
        AnalysisOrchestrator, 
        AnalysisState,
        create_analysis_session
    )
except ImportError:
    # Fallback for development
    AnalysisOrchestrator = None
    AnalysisState = None
    create_analysis_session = None

# Import database functions (will be added to database.py)
try:
    from database import (
        save_analysis_session,
        load_analysis_session,
        save_analysis_deliverable,
        get_analysis_deliverables,
        update_analysis_progress,
        get_analysis_progress
    )
except ImportError:
    # Fallback - these will be implemented
    save_analysis_session = None
    load_analysis_session = None
    save_analysis_deliverable = None
    get_analysis_deliverables = None
    update_analysis_progress = None
    get_analysis_progress = None

# Create blueprint
analysis_bp = Blueprint('analysis', __name__, url_prefix='/api/analysis')

# Storage configuration
UPLOAD_FOLDER = os.environ.get('STORAGE_PATH', '/tmp/swarm_projects')
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@analysis_bp.route('/upload', methods=['POST'])
def upload_data_files():
    """
    Upload data files to start analysis
    
    Request:
        - multipart/form-data with file(s)
        - Optional: project_id
    
    Response:
        {
            "session_id": "uuid",
            "files_uploaded": 2,
            "next_step": "discovery"
        }
    """
    try:
        # Check if files were uploaded
        if 'files' not in request.files and 'file' not in request.files:
            return jsonify({'error': 'No files uploaded'}), 400
        
        # Get files (handle both 'files' and 'file' keys)
        files = request.files.getlist('files') or request.files.getlist('file')
        
        if not files or files[0].filename == '':
            return jsonify({'error': 'No files selected'}), 400
        
        # Get optional project_id
        project_id = request.form.get('project_id', type=int)
        
        # Create new analysis session
        session = create_analysis_session(project_id)
        
        # Create session directory
        session_dir = os.path.join(UPLOAD_FOLDER, session.session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        # Save uploaded files
        uploaded_paths = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(session_dir, filename)
                file.save(filepath)
                uploaded_paths.append(filepath)
                current_app.logger.info(f"Saved file: {filepath}")
        
        if not uploaded_paths:
            return jsonify({'error': 'No valid files uploaded'}), 400
        
        # Update session with file paths
        session.data_files = uploaded_paths
        
        # Save session to database
        if save_analysis_session:
            save_analysis_session(session.to_dict())
        
        return jsonify({
            'session_id': session.session_id,
            'project_id': session.project_id,
            'files_uploaded': len(uploaded_paths),
            'filenames': [os.path.basename(p) for p in uploaded_paths],
            'next_step': 'discovery',
            'state': session.state
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Upload error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/discover', methods=['POST'])
def discover_data():
    """
    Discover data structure and generate questions
    
    Request:
        {
            "session_id": "uuid"
        }
    
    Response:
        {
            "discovered": {
                "files": [...],
                "data_types": [...],
                "questions": [...]
            }
        }
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        # Load session from database
        if load_analysis_session:
            session_data = load_analysis_session(session_id)
            if not session_data:
                return jsonify({'error': 'Session not found'}), 404
            session = AnalysisOrchestrator.from_dict(session_data)
        else:
            return jsonify({'error': 'Database functions not available'}), 500
        
        # Discover data structure
        discovered = session.discover_data_structure(session.data_files)
        
        # Save updated session
        if save_analysis_session:
            save_analysis_session(session.to_dict())
        
        return jsonify({
            'session_id': session_id,
            'state': session.state,
            'discovered': discovered
        })
        
    except Exception as e:
        current_app.logger.error(f"Discovery error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/clarify', methods=['POST'])
def submit_clarifications():
    """
    Submit answers to clarification questions
    
    Request:
        {
            "session_id": "uuid",
            "responses": {
                "has_productivity": "Yes - I will upload them",
                "analysis_priority": ["All of the above"]
            }
        }
    
    Response:
        {
            "session_id": "uuid",
            "state": "PLAN_APPROVAL",
            "message": "Clarifications received"
        }
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        responses = data.get('responses', {})
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        # Load session
        session_data = load_analysis_session(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found'}), 404
        
        session = AnalysisOrchestrator.from_dict(session_data)
        
        # Process clarifications
        result = session.process_clarifications(responses)
        
        # Save updated session
        save_analysis_session(session.to_dict())
        
        return jsonify({
            'session_id': session_id,
            'state': session.state,
            'message': 'Clarifications received',
            'next_step': result['next_step']
        })
        
    except Exception as e:
        current_app.logger.error(f"Clarification error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/plan', methods=['POST'])
def build_plan():
    """
    Build analysis plan for approval
    
    Request:
        {
            "session_id": "uuid"
        }
    
    Response:
        {
            "plan": {
                "analyses": [...],
                "deliverables": [...],
                "estimated_time": 300
            }
        }
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        # Load session
        session_data = load_analysis_session(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found'}), 404
        
        session = AnalysisOrchestrator.from_dict(session_data)
        
        # Build plan
        plan = session.build_analysis_plan()
        
        # Save updated session
        save_analysis_session(session.to_dict())
        
        return jsonify({
            'session_id': session_id,
            'state': session.state,
            'plan': plan
        })
        
    except Exception as e:
        current_app.logger.error(f"Planning error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/execute', methods=['POST'])
def execute_analysis():
    """
    Execute the approved analysis plan
    
    Request:
        {
            "session_id": "uuid",
            "approved": true
        }
    
    Response:
        {
            "session_id": "uuid",
            "state": "ANALYSIS_RUNNING",
            "message": "Analysis started"
        }
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        approved = data.get('approved', False)
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        if not approved:
            return jsonify({'error': 'Plan must be approved'}), 400
        
        # Load session
        session_data = load_analysis_session(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found'}), 404
        
        session = AnalysisOrchestrator.from_dict(session_data)
        
        # Start execution
        result = session.execute_analysis()
        
        # Save updated session
        save_analysis_session(session.to_dict())
        
        # Initialize progress tracking
        if update_analysis_progress:
            update_analysis_progress(session_id, 'analysis_execution', 'running', 0, 'Analysis started')
        
        return jsonify({
            'session_id': session_id,
            'state': session.state,
            'message': result['message'],
            'progress': result['progress'],
            'total_steps': result['total_steps']
        })
        
    except Exception as e:
        current_app.logger.error(f"Execution error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/<session_id>/status', methods=['GET'])
def get_status(session_id):
    """
    Get current analysis status
    
    Response:
        {
            "session_id": "uuid",
            "state": "ANALYSIS_RUNNING",
            "progress": [...],
            "updated_at": "2026-02-08T12:00:00"
        }
    """
    try:
        # Load session
        session_data = load_analysis_session(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get progress
        progress = get_analysis_progress(session_id) if get_analysis_progress else []
        
        return jsonify({
            'session_id': session_id,
            'state': session_data['state'],
            'progress': progress,
            'updated_at': session_data['updated_at']
        })
        
    except Exception as e:
        current_app.logger.error(f"Status error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/<session_id>/results', methods=['GET'])
def get_results(session_id):
    """
    Get analysis results and deliverables
    
    Response:
        {
            "session_id": "uuid",
            "state": "COMPLETE",
            "deliverables": [
                {
                    "type": "powerpoint",
                    "file_name": "Analysis.pptx",
                    "download_url": "/api/analysis/uuid/download/1"
                }
            ]
        }
    """
    try:
        # Load session
        session_data = load_analysis_session(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get deliverables
        deliverables = get_analysis_deliverables(session_id) if get_analysis_deliverables else []
        
        # Format for response
        formatted_deliverables = []
        for d in deliverables:
            formatted_deliverables.append({
                'id': d['id'],
                'type': d['deliverable_type'],
                'file_name': d['file_name'],
                'download_url': f"/api/analysis/{session_id}/download/{d['id']}",
                'created_at': d['created_at']
            })
        
        return jsonify({
            'session_id': session_id,
            'state': session_data['state'],
            'deliverables': formatted_deliverables,
            'results': session_data['results']
        })
        
    except Exception as e:
        current_app.logger.error(f"Results error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/<session_id>/download/<int:deliverable_id>', methods=['GET'])
def download_deliverable(session_id, deliverable_id):
    """
    Download a specific deliverable
    
    Response:
        File download
    """
    try:
        # Get deliverable info
        deliverables = get_analysis_deliverables(session_id) if get_analysis_deliverables else []
        
        deliverable = None
        for d in deliverables:
            if d['id'] == deliverable_id:
                deliverable = d
                break
        
        if not deliverable:
            return jsonify({'error': 'Deliverable not found'}), 404
        
        # Check if file exists
        file_path = deliverable['file_path']
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        # Determine MIME type
        mime_types = {
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'txt': 'text/plain',
            'py': 'text/x-python',
            'png': 'image/png',
            'pdf': 'application/pdf'
        }
        
        ext = file_path.rsplit('.', 1)[1].lower() if '.' in file_path else ''
        mime_type = mime_types.get(ext, 'application/octet-stream')
        
        return send_file(
            file_path,
            mimetype=mime_type,
            as_attachment=True,
            download_name=deliverable['file_name']
        )
        
    except Exception as e:
        current_app.logger.error(f"Download error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


@analysis_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """
    List all analysis sessions (optionally filtered by project)
    
    Query params:
        - project_id: Filter by project
        - state: Filter by state
        - limit: Max results (default 20)
    
    Response:
        {
            "sessions": [...]
        }
    """
    try:
        # This would need a database query function
        # For now, return placeholder
        return jsonify({
            'sessions': [],
            'message': 'Session listing not yet implemented'
        })
        
    except Exception as e:
        current_app.logger.error(f"List sessions error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500


# Health check for this module
@analysis_bp.route('/health', methods=['GET'])
def health():
    """Analysis engine health check"""
    return jsonify({
        'status': 'ok',
        'module': 'analysis_engine',
        'version': '0.1.0',
        'orchestrator_available': AnalysisOrchestrator is not None,
        'database_functions_available': save_analysis_session is not None
    })


# INTEGRATION INSTRUCTIONS:
#
# 1. Copy this file to: routes/analysis.py
#
# 2. In app.py, register the blueprint:
#    from routes.analysis import analysis_bp
#    app.register_blueprint(analysis_bp)
#
# 3. Ensure these modules are available:
#    - analysis_orchestrator.py (in root directory)
#    - Database functions in database.py
#
# 4. Set STORAGE_PATH environment variable for file storage
#
# 5. Test with: GET /api/analysis/health

# I did no harm and this file is not truncated
