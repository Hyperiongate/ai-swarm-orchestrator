"""
Background Jobs API Routes
Created: February 5, 2026
Last Updated: February 5, 2026

API endpoints for managing background file processing jobs:
- POST /api/jobs/submit - Submit a new job
- GET /api/jobs/<job_id>/status - Get job status
- GET /api/jobs/list - List all jobs for user

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify
from background_file_processor import get_background_processor
from database import get_db
import uuid
from datetime import datetime


# Create blueprint
background_jobs_bp = Blueprint('background_jobs', __name__)


@background_jobs_bp.route('/api/jobs/submit', methods=['POST'])
def submit_background_job():
    """
    Submit a file for background processing.
    
    Request JSON:
        file_path: str - Path to uploaded file
        user_request: str - User's original request
        conversation_id: str - Conversation ID
        task_id: int - Task ID
        user_name: str (optional) - User's name
    
    Returns:
        JSON with job_id and estimated_minutes
    """
    try:
        data = request.json
        
        # Validate required fields
        required = ['file_path', 'user_request', 'conversation_id', 'task_id']
        for field in required:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Generate job ID
        job_id = f"JOB_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Submit job
        processor = get_background_processor()
        result = processor.submit_job(
            job_id=job_id,
            file_path=data['file_path'],
            user_request=data['user_request'],
            conversation_id=data['conversation_id'],
            task_id=data['task_id'],
            user_name=data.get('user_name', 'User')
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@background_jobs_bp.route('/api/jobs/<job_id>/status', methods=['GET'])
def get_job_status(job_id):
    """
    Get current status of a background job.
    
    Args:
        job_id: Job identifier
    
    Returns:
        JSON with job status and progress
    """
    try:
        processor = get_background_processor()
        job = processor.get_job_status(job_id)
        
        if job:
            return jsonify({
                'success': True,
                'job': {
                    'job_id': job['job_id'],
                    'file_name': job['file_name'],
                    'file_size_mb': job['file_size_mb'],
                    'status': job['status'],
                    'progress': job['progress'],
                    'current_step': job['current_step'],
                    'estimated_minutes': job['estimated_minutes'],
                    'submitted_at': job['submitted_at'],
                    'started_at': job['started_at'],
                    'completed_at': job['completed_at']
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@background_jobs_bp.route('/api/jobs/list', methods=['GET'])
def list_jobs():
    """
    List all background jobs (or filter by conversation_id).
    
    Query params:
        conversation_id (optional): Filter by conversation
        limit (optional): Max number of jobs to return (default: 10)
    
    Returns:
        JSON with list of jobs
    """
    try:
        conversation_id = request.args.get('conversation_id')
        limit = int(request.args.get('limit', 10))
        
        db = get_db()
        
        if conversation_id:
            jobs = db.execute('''
                SELECT * FROM background_jobs 
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (conversation_id, limit)).fetchall()
        else:
            jobs = db.execute('''
                SELECT * FROM background_jobs 
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()
        
        db.close()
        
        # Convert to list of dicts
        jobs_list = []
        for job in jobs:
            jobs_list.append({
                'job_id': job['job_id'],
                'file_name': job['file_name'],
                'file_size_mb': job['file_size_mb'],
                'status': job['status'],
                'progress': job['progress'],
                'current_step': job['current_step'],
                'estimated_minutes': job['estimated_minutes'],
                'created_at': job['created_at'],
                'updated_at': job['updated_at']
            })
        
        return jsonify({
            'success': True,
            'jobs': jobs_list,
            'count': len(jobs_list)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# I did no harm and this file is not truncated
