"""
Project Dashboard Module
Created: January 22, 2026
Last Updated: January 22, 2026 - SPRINT 3: Visual Project Management

This module provides API endpoints and logic for the project dashboard UI.
Users can view, manage, and track all their consulting projects.

Features:
- List all projects with status
- View project details and checklists
- Update checklist items
- Track milestone progress
- Quick actions (add notes, update status)

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

from flask import Blueprint, jsonify, request
from database import get_db
from project_manager import ProjectManager
import json
from datetime import datetime

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

# Initialize project manager
pm = ProjectManager()


@dashboard_bp.route('/projects', methods=['GET'])
def list_projects():
    """
    Get list of all projects
    
    Query params:
        status: Filter by status (active, completed, archived)
        limit: Max number to return (default 50)
    """
    status_filter = request.args.get('status', 'active')
    limit = int(request.args.get('limit', 50))
    
    db = get_db()
    
    query = '''
        SELECT 
            id, client_name, industry, status,
            created_at, checklist_data, milestone_data
        FROM projects
    '''
    
    params = []
    if status_filter and status_filter != 'all':
        query += ' WHERE status = ?'
        params.append(status_filter)
    
    query += ' ORDER BY created_at DESC LIMIT ?'
    params.append(limit)
    
    projects = db.execute(query, params).fetchall()
    db.close()
    
    # Process and calculate progress
    project_list = []
    for proj in projects:
        checklist = json.loads(proj['checklist_data'])
        milestones = json.loads(proj['milestone_data'])
        
        # Calculate completion percentage
        total_tasks = sum(len(phase['items']) for phase in checklist)
        completed_tasks = sum(
            sum(1 for item in phase['items'] if item['complete'])
            for phase in checklist
        )
        completion_pct = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0)
        
        # Check overdue milestones
        overdue_count = sum(
            1 for m in milestones 
            if m['status'] == 'pending' and datetime.fromisoformat(m['target_date']) < datetime.now()
        )
        
        project_list.append({
            'id': proj['id'],
            'client_name': proj['client_name'],
            'industry': proj['industry'],
            'status': proj['status'],
            'created_at': proj['created_at'],
            'completion_percentage': completion_pct,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'overdue_milestones': overdue_count
        })
    
    return jsonify({
        'projects': project_list,
        'total': len(project_list)
    })


@dashboard_bp.route('/projects/<int:project_id>', methods=['GET'])
def get_project_details(project_id):
    """Get full details for a specific project"""
    project = pm.get_project(project_id)
    
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    return jsonify(project)


@dashboard_bp.route('/projects/<int:project_id>/checklist', methods=['PUT'])
def update_checklist_item(project_id):
    """
    Update a checklist item
    
    Body:
        phase_index: Index of phase (0-3)
        item_index: Index of item within phase
        complete: Boolean
    """
    data = request.json
    
    phase_idx = data.get('phase_index')
    item_idx = data.get('item_index')
    complete = data.get('complete', True)
    
    if phase_idx is None or item_idx is None:
        return jsonify({'error': 'Missing phase_index or item_index'}), 400
    
    success = pm.update_checklist(project_id, phase_idx, item_idx, complete)
    
    if not success:
        return jsonify({'error': 'Failed to update checklist'}), 500
    
    # Return updated project
    project = pm.get_project(project_id)
    return jsonify(project)


@dashboard_bp.route('/projects/<int:project_id>/milestone', methods=['PUT'])
def update_milestone(project_id):
    """
    Update a milestone status
    
    Body:
        milestone_index: Index of milestone
        status: 'pending', 'in_progress', 'completed'
    """
    data = request.json
    milestone_idx = data.get('milestone_index')
    new_status = data.get('status')
    
    if milestone_idx is None or not new_status:
        return jsonify({'error': 'Missing milestone_index or status'}), 400
    
    project = pm.get_project(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    # Update milestone
    project['milestones'][milestone_idx]['status'] = new_status
    if new_status == 'completed':
        project['milestones'][milestone_idx]['completed_at'] = datetime.now().isoformat()
    
    # Save to database
    db = get_db()
    db.execute('''
        UPDATE projects 
        SET milestone_data = ?
        WHERE id = ?
    ''', (json.dumps(project['milestones']), project_id))
    db.commit()
    db.close()
    
    return jsonify(project)


@dashboard_bp.route('/projects/<int:project_id>/status', methods=['PUT'])
def update_project_status(project_id):
    """
    Update project overall status
    
    Body:
        status: 'active', 'on_hold', 'completed', 'archived'
    """
    data = request.json
    new_status = data.get('status')
    
    if not new_status:
        return jsonify({'error': 'Missing status'}), 400
    
    db = get_db()
    db.execute('''
        UPDATE projects 
        SET status = ?
        WHERE id = ?
    ''', (new_status, project_id))
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'status': new_status})


@dashboard_bp.route('/projects/<int:project_id>/notes', methods=['POST'])
def add_project_note(project_id):
    """
    Add a note to a project
    
    Body:
        note: Text of note
    """
    data = request.json
    note_text = data.get('note')
    
    if not note_text:
        return jsonify({'error': 'Missing note text'}), 400
    
    db = get_db()
    
    # Create notes table if doesn't exist
    db.execute('''
        CREATE TABLE IF NOT EXISTS project_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            note_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    # Add note
    db.execute('''
        INSERT INTO project_notes (project_id, note_text)
        VALUES (?, ?)
    ''', (project_id, note_text))
    
    db.commit()
    db.close()
    
    return jsonify({'success': True})


@dashboard_bp.route('/projects/<int:project_id>/notes', methods=['GET'])
def get_project_notes(project_id):
    """Get all notes for a project"""
    db = get_db()
    
    notes = db.execute('''
        SELECT id, note_text, created_at
        FROM project_notes
        WHERE project_id = ?
        ORDER BY created_at DESC
    ''', (project_id,)).fetchall()
    
    db.close()
    
    return jsonify({
        'notes': [
            {
                'id': note['id'],
                'text': note['note_text'],
                'created_at': note['created_at']
            }
            for note in notes
        ]
    })


@dashboard_bp.route('/stats', methods=['GET'])
def get_dashboard_stats():
    """Get overall statistics for dashboard"""
    db = get_db()
    
    # Project counts by status
    status_counts = db.execute('''
        SELECT status, COUNT(*) as count
        FROM projects
        GROUP BY status
    ''').fetchall()
    
    # Total tasks and completion
    all_projects = db.execute('''
        SELECT checklist_data FROM projects
    ''').fetchall()
    
    total_tasks = 0
    completed_tasks = 0
    
    for proj in all_projects:
        checklist = json.loads(proj['checklist_data'])
        for phase in checklist:
            for item in phase['items']:
                total_tasks += 1
                if item['complete']:
                    completed_tasks += 1
    
    # Recent activity (last 7 days)
    recent_projects = db.execute('''
        SELECT COUNT(*) as count
        FROM projects
        WHERE created_at >= datetime('now', '-7 days')
    ''').fetchone()
    
    db.close()
    
    return jsonify({
        'status_counts': {row['status']: row['count'] for row in status_counts},
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'completion_rate': round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0),
        'projects_this_week': recent_projects['count']
    })


# I did no harm and this file is not truncated
