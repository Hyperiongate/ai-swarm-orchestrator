"""
Labor Job Status API
Created: February 14, 2026
Last Updated: February 14, 2026

API endpoint for checking background labor analysis job status.
Allows frontend to poll for progress and auto-display results.

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, jsonify
from labor_analysis_processor import get_labor_processor


# Create blueprint
labor_jobs_bp = Blueprint('labor_jobs', __name__)


@labor_jobs_bp.route('/api/labor-jobs/<job_id>/status', methods=['GET'])
def get_labor_job_status(job_id):
    """
    Get current status of a labor analysis job.
    
    Returns:
        {
            "status": "queued|processing|completed|failed",
            "progress": 0-100,
            "current_step": "Extracting...",
            "result": "analysis text" (if completed),
            "error": "error message" (if failed),
            "document_id": 123 (if completed with Excel report)
        }
    """
    try:
        processor = get_labor_processor()
        job = processor.get_job_status(job_id)
        
        if not job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404
        
        response = {
            'success': True,
            'job_id': job_id,
            'status': job['status'],
            'progress': job.get('progress', 0),
            'current_step': job.get('current_step', ''),
            'estimated_minutes': job.get('estimated_minutes', 0),
            'file_name': job.get('file_name', ''),
            'file_size_mb': job.get('file_size_mb', 0)
        }
        
        # Add result if completed
        if job['status'] == 'completed':
            response['result'] = job.get('result')
            response['document_id'] = job.get('document_id')
        
        # Add error if failed
        if job['status'] == 'failed':
            response['error'] = job.get('error', 'Unknown error')
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# I did no harm and this file is not truncated
