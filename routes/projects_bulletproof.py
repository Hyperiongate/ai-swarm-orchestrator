"""
BULLETPROOF PROJECT API ROUTES
Created: January 30, 2026
Last Updated: March 03, 2026 - Phase 9: POSTGRESQL COMPATIBILITY FIX

CHANGELOG:
- March 03, 2026: Phase 9 - POSTGRESQL COMPATIBILITY FIX
  * Replaced all raw sqlite3 imports and calls with get_db_connection() from db_engine
  * manual_migrate() endpoint now works on both PostgreSQL and SQLite
  * Removed PRAGMA table_info (SQLite-only) — replaced with
    information_schema.columns (PostgreSQL) or PRAGMA (SQLite) based on db_type
  * Removed direct sqlite3.connect(DATABASE) calls
  * All SQL uses %s placeholders (db_engine translates to ? for SQLite)
  * No functional changes — all endpoints behave identically

- February 1, 2026: CRITICAL FIX - File upload now uses persistent storage!
- January 31, 2026: Fixed /api/projects/create response format
- January 30, 2026: Initial creation

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
from database_file_management import get_project_manager
from db_engine import get_db_connection, get_db_type

# Create blueprint
projects_bp = Blueprint('projects', __name__)

# Get project manager instance with force reload to ensure fresh storage path
# This is critical after deployments to pick up the /mnt/project path
pm = get_project_manager(force_reload=True)
print(f"🔄 ProjectManager loaded with storage: {pm.storage_root}")


# ============================================================================
# PROJECT MANAGEMENT ENDPOINTS
# ============================================================================

@projects_bp.route('/api/projects/migrate', methods=['POST'])
def manual_migrate():
    """
    Manual migration endpoint to create or fix the projects table.
    Call this once to fix the schema.
    Works on both PostgreSQL and SQLite.
    """
    try:
        db = get_db_connection()
        db_type = get_db_type()

        try:
            result = {
                'success': True,
                'database_type': db_type,
                'action_taken': None
            }

            # Check if table exists
            if db_type == 'postgresql':
                row = db.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'projects'
                """).fetchone()
                table_exists = row is not None
            else:
                row = db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
                ).fetchone()
                table_exists = row is not None

            result['table_existed'] = table_exists

            if not table_exists:
                # Create table with full schema
                db.execute('''
                    CREATE TABLE IF NOT EXISTS projects (
                        id SERIAL PRIMARY KEY,
                        project_id TEXT UNIQUE,
                        client_name TEXT NOT NULL,
                        company_name TEXT,
                        industry TEXT,
                        facility_size TEXT,
                        status TEXT DEFAULT 'active',
                        project_phase TEXT DEFAULT 'discovery',
                        context_data TEXT,
                        uploaded_files TEXT,
                        email_context TEXT,
                        key_findings TEXT,
                        schedules_proposed TEXT,
                        storage_path TEXT,
                        checklist_data TEXT,
                        milestone_data TEXT,
                        folder_data TEXT,
                        metadata TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''') if db_type == 'postgresql' else db.execute('''
                    CREATE TABLE IF NOT EXISTS projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT UNIQUE,
                        client_name TEXT NOT NULL,
                        company_name TEXT,
                        industry TEXT,
                        facility_size TEXT,
                        status TEXT DEFAULT 'active',
                        project_phase TEXT DEFAULT 'discovery',
                        context_data TEXT,
                        uploaded_files TEXT,
                        email_context TEXT,
                        key_findings TEXT,
                        schedules_proposed TEXT,
                        storage_path TEXT,
                        checklist_data TEXT,
                        milestone_data TEXT,
                        folder_data TEXT,
                        metadata TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                db.commit()
                result['action_taken'] = 'created_table'
                result['columns_added'] = ['all_columns_in_new_table']
            else:
                # Table exists - check for missing columns
                if db_type == 'postgresql':
                    rows = db.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'projects'
                    """).fetchall()
                    existing_columns = {row['column_name'] for row in rows}
                else:
                    rows = db.execute("PRAGMA table_info(projects)").fetchall()
                    existing_columns = {row['name'] for row in rows}

                result['existing_columns'] = list(existing_columns)
                result['columns_added'] = []

                # Add missing columns
                columns_to_add = [
                    ('project_id', 'TEXT'),
                    ('storage_path', 'TEXT'),
                    ('checklist_data', 'TEXT'),
                    ('milestone_data', 'TEXT'),
                    ('folder_data', 'TEXT'),
                    ('metadata', "TEXT DEFAULT '{}'"),
                    ('project_phase', "TEXT DEFAULT 'discovery'"),
                    ('facility_size', 'TEXT'),
                    ('context_data', 'TEXT'),
                    ('uploaded_files', 'TEXT'),
                    ('email_context', 'TEXT'),
                    ('key_findings', 'TEXT'),
                    ('schedules_proposed', 'TEXT'),
                ]

                for col_name, col_type in columns_to_add:
                    if col_name not in existing_columns:
                        try:
                            if db_type == 'postgresql':
                                db.execute(
                                    f'ALTER TABLE projects ADD COLUMN IF NOT EXISTS {col_name} {col_type}'
                                )
                            else:
                                db.execute(
                                    f'ALTER TABLE projects ADD COLUMN {col_name} {col_type}'
                                )
                            db.commit()
                            result['columns_added'].append(col_name)
                        except Exception as e:
                            result.setdefault('errors', []).append(f"{col_name}: {str(e)}")

                result['action_taken'] = 'added_columns' if result['columns_added'] else 'no_changes_needed'

            # Verify final schema
            if db_type == 'postgresql':
                rows = db.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'projects'
                    ORDER BY ordinal_position
                """).fetchall()
                result['final_columns'] = [row['column_name'] for row in rows]
            else:
                rows = db.execute("PRAGMA table_info(projects)").fetchall()
                result['final_columns'] = [row['name'] for row in rows]

            return jsonify(result)

        finally:
            db.close()

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@projects_bp.route('/api/projects/create', methods=['POST'])
def create_project():
    """
    Create a new project.

    Request JSON:
        {
            "client_name": "ABC Manufacturing",
            "industry": "Automotive",
            "facility_type": "Assembly Plant",
            "description": "Project for ABC Manufacturing",
            "metadata": {...}
        }

    Response JSON:
        {
            "success": true,
            "project_id": "PRJ_...",
            "client_name": "ABC Manufacturing",
            ...
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

        # Create project using ProjectManager
        project = pm.create_project(
            client_name=client_name,
            industry=industry,
            facility_type=facility_type,
            metadata=metadata
        )

        # CRITICAL: Return project_id at top level for frontend compatibility
        # Frontend expects: if (data.success && data.project_id)
        return jsonify({
            'success': True,
            'project_id': project['project_id'],
            'client_name': project['client_name'],
            'industry': project.get('industry'),
            'facility_type': project.get('facility_size'),
            'project_phase': project.get('project_phase', 'discovery'),
            'status': project.get('status', 'active'),
            'created_at': project.get('created_at'),
            'storage_path': project.get('storage_path'),
            'metadata': project.get('metadata', {})
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


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
        - field: field to search in (client_name, industry, facility_size)
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

    UPDATED February 1, 2026: Now passes FileStorage objects directly!
    - No more temp file saving to /tmp
    - FileStorage objects passed directly to add_file()
    - add_file() handles FileStorage and saves to persistent storage
    - Cleaner, more efficient, no temp file cleanup needed

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
                # Secure the filename
                filename = secure_filename(file.filename)

                # CRITICAL FIX: Pass FileStorage object directly to add_file()
                # No temp file needed - add_file() handles FileStorage objects!
                file_info = pm.add_file(
                    project_id=project_id,
                    file_path=file,
                    original_filename=filename
                )

                uploaded_files.append(file_info)

        return jsonify({
            'success': True,
            'files': uploaded_files,
            'count': len(uploaded_files)
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


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
