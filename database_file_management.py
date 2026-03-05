"""
Database File Management - UNIFIED PRODUCTION VERSION
Created: January 28, 2026
Last Updated: March 05, 2026 - POSTGRESQL BOOLEAN FIX (minimal)

CHANGELOG:
- March 05, 2026: POSTGRESQL BOOLEAN FIX (minimal change only)
  * is_deleted = 0 → is_deleted = FALSE (get_file, list_files)
  * is_deleted = 1 → is_deleted = TRUE (delete_file)
  * is_analyzed = 1 → is_analyzed = TRUE (mark_file_as_analyzed)
  * NO other changes from the March 03 version. All function structures,
    OR id = %s patterns, and parameter handling are IDENTICAL to the
    working March 03 deploy.

- March 03, 2026: SCHEMA FIX Phase 8
  * Fixed facility_type -> facility_size in create_project() INSERT column name
  * Fixed facility_type -> facility_size in create_project() return dict key
  * Fixed facility_type -> facility_size in get_project() response dict key
  * Fixed facility_type -> facility_size in update_project() allowed_fields list
  * Fixed id::text = %s -> id = %s in get_project(), update_project(),
    update_checklist() — id column is TEXT type, the ::text cast is invalid
    against a TEXT primary key in PostgreSQL and caused query failures.
  * All missing columns (project_phase, storage_path, checklist_data,
    milestone_data, folder_data, metadata, project_id) are added to the
    projects table by add_missing_columns.py at startup.
  * No functional changes — all methods behave identically after fix.

- March 02, 2026: POSTGRESQL MIGRATION (Phase 1)
  * Replaced all sqlite3.connect(DATABASE) calls with get_db_connection()
  * All SQL parameters changed from ? to %s (PostgreSQL style)
  * STORAGE_PATH now imported from config.py
  * ON CONFLICT syntax for PostgreSQL upserts
  * All existing functionality preserved

- February 5, 2026: FIXED FILE SELECTION EXCEL EXTRACTION
- February 1, 2026: CRITICAL FIX - add_file() handles Flask FileStorage objects
- February 1, 2026: CRITICAL FIX - Proper persistent storage instead of /tmp
- January 31, 2026: Added file_ids parameter to get_files_for_ai_context()
- January 30, 2026: COMPLETE REBUILD - Merged Sprint 2 features + bulletproof persistence

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import re
import os
import shutil
import hashlib
from datetime import datetime, timedelta
from config import STORAGE_PATH
from db_engine import get_db_connection


class ProjectManager:
    PROJECT_KEYWORDS = [
        'new client', 'new facility', 'new customer', 'new project',
        'kick off', 'kickoff', 'starting work with', 'beginning work',
        'new engagement', 'new implementation', 'project start'
    ]

    def __init__(self, storage_root=None):
        print("=" * 80)
        print("🔧 INITIALIZING PROJECT MANAGER - STORAGE DIAGNOSTICS")
        print("=" * 80)

        if storage_root is None:
            env_storage = os.environ.get('STORAGE_ROOT')
            if env_storage:
                storage_root = env_storage
                print(f"   ✅ Using STORAGE_ROOT from environment: {storage_root}")
            else:
                storage_root = STORAGE_PATH
                print(f"   ✅ Using STORAGE_PATH from config: {storage_root}")
        else:
            print(f"   ✅ Using provided storage_root: {storage_root}")

        self.storage_root = storage_root
        print(f"\n✅ FINAL STORAGE LOCATION: {storage_root}")
        print("=" * 80)

        try:
            os.makedirs(storage_root, exist_ok=True)
            test_file = os.path.join(storage_root, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"✅ Storage directory exists and is writable: {storage_root}")
        except PermissionError as e:
            print(f"❌ ERROR: Cannot write to storage directory: {storage_root}")
            print(f"   Permission denied: {e}")
            raise
        except Exception as e:
            print(f"❌ ERROR: Failed to initialize storage: {e}")
            raise

        print("=" * 80)

    def _get_db(self):
        return get_db_connection()

    def _generate_id(self, prefix=''):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_hash = hashlib.md5(os.urandom(16)).hexdigest()[:8]
        return f"{prefix}{timestamp}_{random_hash}"

    # ========================================================================
    # PROJECT DETECTION
    # ========================================================================

    def detect_new_project(self, user_request):
        request_lower = user_request.lower()
        detected = any(keyword in request_lower for keyword in self.PROJECT_KEYWORDS)
        if not detected:
            return {'detected': False}
        client_name = self._extract_client_name(user_request)
        industry = self._extract_industry(user_request)
        return {
            'detected': True,
            'client_name': client_name,
            'industry': industry,
            'confidence': 0.9 if client_name else 0.7
        }

    def _extract_client_name(self, text):
        patterns = [
            r'(?:new client|new facility|new customer|kickoff)\s+(?:for\s+)?([A-Z][A-Za-z\s&]+?)(?:\s+in|\s+at|\s+facility|$|\.)',
            r'(?:starting work with|beginning work|engagement with)\s+([A-Z][A-Za-z\s&]+?)(?:\s+in|\s+at|$|\.)',
            r'([A-Z][A-Za-z\s&]{2,})\s+(?:project|facility|plant|site)'
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'\s+(is|has|will|wants|needs)$', '', name)
                if len(name) > 2:
                    return name
        return None

    def _extract_industry(self, text):
        industries = {
            'manufacturing': ['manufacturing', 'factory', 'plant', 'production'],
            'pharmaceutical': ['pharmaceutical', 'pharma', 'drug', 'biotech'],
            'food processing': ['food', 'processing', 'beverage', 'bottling'],
            'distribution': ['distribution', 'warehouse', 'logistics', 'fulfillment'],
            'mining': ['mining', 'quarry', 'extraction'],
            'chemical': ['chemical', 'refinery', 'petrochemical'],
            'automotive': ['automotive', 'auto', 'assembly']
        }
        text_lower = text.lower()
        for industry, keywords in industries.items():
            if any(keyword in text_lower for keyword in keywords):
                return industry.title()
        return None

    # ========================================================================
    # PROJECT CREATION
    # ========================================================================

    def create_project(self, client_name, industry=None, facility_type=None,
                       additional_context=None, metadata=None):
        """
        Create complete project structure.
        Parameter facility_type kept for API backward compatibility with callers.
        Stored in facility_size column (authoritative schema Mar 2026).
        """
        project_id = self._generate_id('PRJ_')
        storage_path = os.path.join(self.storage_root, project_id)
        os.makedirs(storage_path, exist_ok=True)

        checklist = self._generate_checklist()
        milestones = self._generate_milestones()
        folders = self._generate_folder_structure(client_name)

        if metadata is None:
            metadata = {}
        metadata['templates'] = self._list_available_templates()
        metadata['next_steps'] = self._suggest_next_steps()

        db = self._get_db()
        try:
            db.execute('''
                INSERT INTO projects (
                    project_id, client_name, industry, facility_size,
                    status, project_phase, storage_path,
                    checklist_data, milestone_data, folder_data, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                project_id, client_name, industry, facility_type,
                'active', 'discovery', storage_path,
                json.dumps(checklist), json.dumps(milestones),
                json.dumps(folders), json.dumps(metadata)
            ))
            db.commit()
        finally:
            db.close()

        print(f"✅ Created project {project_id} for {client_name}")

        return {
            'project_id': project_id,
            'id': project_id,
            'client_name': client_name,
            'industry': industry,
            'facility_size': facility_type,
            'storage_path': storage_path,
            'status': 'active',
            'project_phase': 'discovery',
            'checklist': checklist,
            'milestones': milestones,
            'folders': folders,
            'templates': metadata['templates'],
            'next_steps': metadata['next_steps']
        }

    def _generate_checklist(self):
        return [
            {
                'phase': 'Discovery',
                'status': 'not_started',
                'items': [
                    {'task': 'Schedule kickoff meeting', 'complete': False},
                    {'task': 'Collect organizational charts', 'complete': False},
                    {'task': 'Gather payroll data', 'complete': False},
                    {'task': 'Analyze current schedules', 'complete': False},
                    {'task': 'Conduct stakeholder interviews', 'complete': False}
                ]
            },
            {
                'phase': 'Assessment',
                'status': 'not_started',
                'items': [
                    {'task': 'Deploy employee survey', 'complete': False},
                    {'task': 'Calculate labor costs', 'complete': False},
                    {'task': 'Analyze overtime patterns', 'complete': False},
                    {'task': 'Identify regulatory constraints', 'complete': False},
                    {'task': 'Document current pain points', 'complete': False}
                ]
            },
            {
                'phase': 'Design',
                'status': 'not_started',
                'items': [
                    {'task': 'Create schedule options', 'complete': False},
                    {'task': 'Model cost comparisons', 'complete': False},
                    {'task': 'Develop implementation plan', 'complete': False},
                    {'task': 'Prepare employee communications', 'complete': False},
                    {'task': 'Create training materials', 'complete': False}
                ]
            },
            {
                'phase': 'Implementation',
                'status': 'not_started',
                'items': [
                    {'task': 'Present to leadership', 'complete': False},
                    {'task': 'Conduct employee info sessions', 'complete': False},
                    {'task': 'Execute rollout plan', 'complete': False},
                    {'task': 'Monitor first 30 days', 'complete': False},
                    {'task': 'Collect feedback and adjust', 'complete': False}
                ]
            }
        ]

    def _generate_milestones(self):
        today = datetime.now()
        return [
            {'name': 'Kickoff Meeting', 'target_date': (today + timedelta(days=3)).isoformat(), 'status': 'pending'},
            {'name': 'Data Collection Complete', 'target_date': (today + timedelta(days=14)).isoformat(), 'status': 'pending'},
            {'name': 'Survey Deployment', 'target_date': (today + timedelta(days=21)).isoformat(), 'status': 'pending'},
            {'name': 'Schedule Design Complete', 'target_date': (today + timedelta(days=35)).isoformat(), 'status': 'pending'},
            {'name': 'Leadership Presentation', 'target_date': (today + timedelta(days=42)).isoformat(), 'status': 'pending'},
            {'name': 'Go-Live', 'target_date': (today + timedelta(days=56)).isoformat(), 'status': 'pending'}
        ]

    def _generate_folder_structure(self, client_name):
        safe_name = re.sub(r'[^a-zA-Z0-9\s]', '', client_name).replace(' ', '_')
        return {
            'root': f'/projects/{safe_name}',
            'folders': [
                'Data_Collection', 'Survey_Results', 'Schedule_Designs',
                'Cost_Analysis', 'Communications', 'Presentations',
                'Contracts', 'Implementation_Materials'
            ]
        }

    def _list_available_templates(self):
        return [
            {'name': 'Implementation Manual', 'file': 'Implementation_Manual.docx'},
            {'name': 'Employee Survey', 'file': 'Schedule_Survey.docx'},
            {'name': 'Executive Summary', 'file': 'Example_Client_facing_executive_summary.docx'},
            {'name': 'Contract Template', 'file': 'Contract_without_name.docx'},
            {'name': 'Project Kickoff Bulletin', 'file': 'Project_kickoff_bulletin.docx'}
        ]

    def _suggest_next_steps(self):
        return [
            'Schedule kickoff meeting with client stakeholders',
            'Request organizational charts and payroll data',
            'Prepare data collection checklist',
            'Draft project scope document',
            'Set up project tracking dashboard'
        ]

    # ========================================================================
    # PROJECT RETRIEVAL & MANAGEMENT
    # ========================================================================

    def get_project(self, project_id):
        """Retrieve project from database."""
        db = self._get_db()
        try:
            # FIXED: was 'id::text = %s' — id is TEXT type, ::text cast is invalid
            project = db.execute(
                'SELECT * FROM projects WHERE project_id = %s OR id = %s',
                (project_id, str(project_id))
            ).fetchone()

            if not project:
                return None

            project_data = {
                'id': project['id'],
                'project_id': project['project_id'] or str(project['id']),
                'client_name': project['client_name'],
                'industry': project['industry'],
                'facility_size': project['facility_size'],
                'status': project['status'],
                'project_phase': project['project_phase'],
                'storage_path': project['storage_path'],
                'created_at': project['created_at'],
                'updated_at': project['updated_at']
            }

            for field, key in [('checklist_data', 'checklist'), ('milestone_data', 'milestones'), ('folder_data', 'folders')]:
                if project[field]:
                    try:
                        project_data[key] = json.loads(project[field])
                    except Exception:
                        project_data[key] = [] if key != 'folders' else {}

            if project['metadata']:
                try:
                    meta = json.loads(project['metadata'])
                    project_data.update(meta)
                except Exception:
                    pass

            return project_data
        finally:
            db.close()

    def list_projects(self, status='active', limit=50):
        """List all projects."""
        db = self._get_db()
        try:
            if status == 'all':
                rows = db.execute(
                    'SELECT * FROM projects ORDER BY updated_at DESC LIMIT %s',
                    (limit,)
                ).fetchall()
            else:
                rows = db.execute(
                    'SELECT * FROM projects WHERE status = %s ORDER BY updated_at DESC LIMIT %s',
                    (status, limit)
                ).fetchall()
            return [self._row_to_project(row) for row in rows]
        finally:
            db.close()

    def _row_to_project(self, row):
        """Convert database row to project dict."""
        return {
            'id': row['id'],
            'project_id': row['project_id'] or str(row['id']),
            'client_name': row['client_name'],
            'industry': row['industry'],
            'status': row['status'],
            'project_phase': row['project_phase'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }

    def update_project(self, project_id, **kwargs):
        """Update project fields."""
        # FIXED: was 'facility_type' in allowed_fields — DB column is facility_size
        allowed_fields = ['client_name', 'industry', 'facility_size', 'project_phase', 'status']
        updates = []
        values = []

        for field in allowed_fields:
            if field in kwargs:
                updates.append(f'{field} = %s')
                values.append(kwargs[field])

        # Accept legacy facility_type key from callers
        if 'facility_type' in kwargs and 'facility_size' not in kwargs:
            updates.append('facility_size = %s')
            values.append(kwargs['facility_type'])

        if 'metadata' in kwargs:
            updates.append('metadata = %s')
            values.append(json.dumps(kwargs['metadata']))

        if not updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            values.extend([project_id, str(project_id)])
        else:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            values.extend([project_id, str(project_id)])

        db = self._get_db()
        try:
            # FIXED: was 'id::text = %s' — id is TEXT type, ::text cast is invalid
            db.execute(
                f"UPDATE projects SET {', '.join(updates)} WHERE project_id = %s OR id = %s",
                values
            )
            db.commit()
            return True
        finally:
            db.close()

    def update_checklist(self, project_id, phase_index, item_index, complete=True):
        """Mark checklist item as complete."""
        project = self.get_project(project_id)
        if not project or 'checklist' not in project:
            return False

        project['checklist'][phase_index]['items'][item_index]['complete'] = complete

        db = self._get_db()
        try:
            # FIXED: was 'id::text = %s' — id is TEXT type, ::text cast is invalid
            db.execute(
                'UPDATE projects SET checklist_data = %s, updated_at = CURRENT_TIMESTAMP WHERE project_id = %s OR id = %s',
                (json.dumps(project['checklist']), project_id, str(project_id))
            )
            db.commit()
            return True
        finally:
            db.close()

    def search_projects(self, search_term, search_in='client_name'):
        """Search for projects."""
        db = self._get_db()
        try:
            rows = db.execute(
                f"SELECT * FROM projects WHERE {search_in} ILIKE %s AND status = 'active' ORDER BY updated_at DESC",
                (f'%{search_term}%',)
            ).fetchall()
            return [self._row_to_project(row) for row in rows]
        finally:
            db.close()

    # ========================================================================
    # FILE MANAGEMENT
    # ========================================================================

    def add_file(self, project_id, file_path, original_filename=None,
                 file_type=None, metadata=None):
        """
        Add a file to a project.
        Accepts both file path strings and Flask FileStorage objects.
        Files stored at STORAGE_PATH on persistent disk.
        """
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        if not project.get('storage_path'):
            storage_path = os.path.join(self.storage_root, project_id)
            os.makedirs(storage_path, exist_ok=True)
            self.update_project(project_id, metadata={'storage_path': storage_path})
            project['storage_path'] = storage_path

        is_file_storage = hasattr(file_path, 'save') and hasattr(file_path, 'filename')
        print(f"📥 add_file called: is_file_storage={is_file_storage}")

        file_id = self._generate_id('FILE_')

        if is_file_storage:
            if not original_filename:
                original_filename = file_path.filename
            file_ext = os.path.splitext(original_filename)[1]
            stored_filename = f"{file_id}{file_ext}"
            storage_path = os.path.join(project['storage_path'], stored_filename)
            print(f"📁 Saving FileStorage to: {storage_path}")
            file_path.save(storage_path)
            file_size = os.path.getsize(storage_path)
            print(f"✅ FileStorage saved: {file_size} bytes")
        else:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            if not original_filename:
                original_filename = os.path.basename(file_path)
            file_ext = os.path.splitext(original_filename)[1]
            stored_filename = f"{file_id}{file_ext}"
            storage_path = os.path.join(project['storage_path'], stored_filename)
            print(f"📁 Copying file to: {storage_path}")
            shutil.copy2(file_path, storage_path)
            file_size = os.path.getsize(storage_path)
            print(f"✅ File copied: {file_size} bytes")

        import mimetypes
        mime_type, _ = mimetypes.guess_type(original_filename)

        actual_project_id = project['project_id']

        db = self._get_db()
        try:
            db.execute('''
                INSERT INTO project_files
                (project_id, file_id, filename, original_filename, file_path, file_size,
                 file_type, mime_type, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (actual_project_id, file_id, stored_filename, original_filename,
                  storage_path, file_size, file_type, mime_type,
                  json.dumps(metadata) if metadata else None))
            db.commit()
        finally:
            db.close()

        self.update_project(project_id)
        print(f"✅ Added file {original_filename} to project {project_id}")

        return {
            'file_id': file_id,
            'filename': stored_filename,
            'original_filename': original_filename,
            'file_path': storage_path,
            'file_size': file_size,
            'file_type': file_type,
            'mime_type': mime_type
        }

    def get_file(self, file_id):
        """Get file information by file_id OR filename."""
        db = self._get_db()
        try:
            row = db.execute('''
                SELECT * FROM project_files
                WHERE (file_id = %s OR filename = %s)
                AND is_deleted = FALSE
            ''', (file_id, file_id)).fetchone()

            if not row:
                return None

            file_info = dict(row)
            if file_info.get('metadata'):
                try:
                    file_info['metadata'] = json.loads(file_info['metadata'])
                except Exception:
                    pass
            return file_info
        finally:
            db.close()

    def list_files(self, project_id, include_deleted=False):
        """List all files in a project."""
        db = self._get_db()
        try:
            if include_deleted:
                rows = db.execute(
                    'SELECT * FROM project_files WHERE project_id = %s ORDER BY uploaded_at DESC',
                    (project_id,)
                ).fetchall()
            else:
                rows = db.execute(
                    'SELECT * FROM project_files WHERE project_id = %s AND is_deleted = FALSE ORDER BY uploaded_at DESC',
                    (project_id,)
                ).fetchall()

            files = []
            for row in rows:
                file_info = dict(row)
                if file_info.get('metadata'):
                    try:
                        file_info['metadata'] = json.loads(file_info['metadata'])
                    except Exception:
                        pass
                files.append(file_info)
            return files
        finally:
            db.close()

    def get_file_content(self, file_id):
        """Get actual file content."""
        file_info = self.get_file(file_id)
        if not file_info:
            raise FileNotFoundError(f"File {file_id} not found")
        if not os.path.exists(file_info['file_path']):
            raise FileNotFoundError(f"File storage missing: {file_info['file_path']}")
        with open(file_info['file_path'], 'rb') as f:
            return f.read()

    def delete_file(self, file_id, hard_delete=False):
        """Delete a file."""
        file_info = self.get_file(file_id)
        if not file_info:
            return False

        db = self._get_db()
        try:
            if hard_delete:
                try:
                    if os.path.exists(file_info['file_path']):
                        os.remove(file_info['file_path'])
                except Exception as e:
                    print(f"⚠️ Could not delete physical file: {e}")
                db.execute('DELETE FROM project_files WHERE file_id = %s', (file_id,))
            else:
                db.execute(
                    'UPDATE project_files SET is_deleted = TRUE WHERE file_id = %s',
                    (file_id,)
                )
            db.commit()
        finally:
            db.close()

        self.update_project(file_info['project_id'])
        return True

    # ========================================================================
    # CONVERSATION MANAGEMENT
    # ========================================================================

    def add_message(self, project_id, conversation_id, role, content,
                    file_ids=None, metadata=None):
        """Add a message to project conversation."""
        db = self._get_db()
        try:
            db.execute('''
                INSERT INTO project_conversations
                (project_id, conversation_id, role, content, file_ids, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (project_id, conversation_id, role, content,
                  json.dumps(file_ids) if file_ids else None,
                  json.dumps(metadata) if metadata else None))
            db.commit()
        finally:
            db.close()
        self.update_project(project_id)

    def get_conversation_history(self, project_id, conversation_id=None, limit=100):
        """Get conversation history."""
        db = self._get_db()
        try:
            if conversation_id:
                rows = db.execute('''
                    SELECT * FROM project_conversations
                    WHERE project_id = %s AND conversation_id = %s
                    ORDER BY created_at ASC LIMIT %s
                ''', (project_id, conversation_id, limit)).fetchall()
            else:
                rows = db.execute('''
                    SELECT * FROM project_conversations
                    WHERE project_id = %s
                    ORDER BY created_at DESC LIMIT %s
                ''', (project_id, limit)).fetchall()

            messages = []
            for row in rows:
                message = dict(row)
                for field in ['file_ids', 'metadata']:
                    if message.get(field):
                        try:
                            message[field] = json.loads(message[field])
                        except Exception:
                            pass
                messages.append(message)
            return messages
        finally:
            db.close()

    # ========================================================================
    # CONTEXT MANAGEMENT
    # ========================================================================

    def set_context(self, project_id, key, value):
        """Set context value."""
        db = self._get_db()
        value_json = json.dumps(value) if not isinstance(value, str) else value
        try:
            from db_engine import get_db_type
            if get_db_type() == 'postgresql':
                db.execute('''
                    INSERT INTO project_context (project_id, context_key, context_value, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (project_id, context_key) DO UPDATE
                    SET context_value = EXCLUDED.context_value,
                        updated_at = CURRENT_TIMESTAMP
                ''', (project_id, key, value_json))
            else:
                db.execute('''
                    INSERT OR REPLACE INTO project_context
                    (project_id, context_key, context_value, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ''', (project_id, key, value_json))
            db.commit()
        finally:
            db.close()

    def get_context(self, project_id, key):
        """Get context value."""
        db = self._get_db()
        try:
            row = db.execute('''
                SELECT context_value FROM project_context
                WHERE project_id = %s AND context_key = %s
            ''', (project_id, key)).fetchone()

            if not row:
                return None
            try:
                return json.loads(row['context_value'])
            except Exception:
                return row['context_value']
        finally:
            db.close()

    def get_all_context(self, project_id):
        """Get all context."""
        db = self._get_db()
        try:
            rows = db.execute(
                'SELECT context_key, context_value FROM project_context WHERE project_id = %s',
                (project_id,)
            ).fetchall()

            context = {}
            for row in rows:
                try:
                    context[row['context_key']] = json.loads(row['context_value'])
                except Exception:
                    context[row['context_key']] = row['context_value']
            return context
        finally:
            db.close()

    # ========================================================================
    # SUMMARY & UTILITIES
    # ========================================================================

    def get_project_summary(self, project_id):
        """Get complete project summary."""
        project = self.get_project(project_id)
        if not project:
            return None

        files = self.list_files(project_id)
        messages = self.get_conversation_history(project_id, limit=1000)
        context = self.get_all_context(project_id)

        return {
            'project': project,
            'file_count': len(files),
            'files': files,
            'message_count': len(messages),
            'latest_messages': messages[-10:] if messages else [],
            'context': context
        }


# ============================================================================
# SINGLETON & BACKWARD COMPATIBLE FUNCTIONS
# ============================================================================

_project_manager = None


def get_project_manager(storage_root=None, force_reload=False):
    global _project_manager

    if force_reload:
        print("🔄 Force reloading ProjectManager singleton...")
        _project_manager = None

    if _project_manager is None:
        _project_manager = ProjectManager(storage_root)

    return _project_manager


def add_project_files_table():
    print("✅ Tables managed via migrations/001_initial_schema.py")


def save_project_file(project_id, filename, original_filename, file_type, file_path, **kwargs):
    pm = get_project_manager()
    return pm.add_file(project_id, file_path, original_filename, file_type)


def get_project_files(project_id, include_deleted=False, file_type=None):
    pm = get_project_manager()
    return pm.list_files(project_id, include_deleted)


def get_project_file_by_id(file_id):
    pm = get_project_manager()
    return pm.get_file(file_id)


def delete_project_file(file_id, hard_delete=False):
    pm = get_project_manager()
    return pm.delete_file(file_id, hard_delete)


def get_all_projects_with_files():
    pm = get_project_manager()
    projects = pm.list_projects(status='active', limit=1000)

    result = []
    for proj in projects:
        files = pm.list_files(proj['project_id'])
        result.append({
            'project_id': proj['project_id'],
            'client_name': proj['client_name'],
            'industry': proj.get('industry'),
            'project_phase': proj.get('project_phase'),
            'file_count': len(files)
        })
    return result


def get_project_file_by_name(project_id, filename):
    pm = get_project_manager()
    files = pm.list_files(project_id)

    for file in files:
        if file['filename'] == filename or file['original_filename'] == filename:
            return file
    for file in files:
        if filename in file['filename'] or filename in file['original_filename']:
            return file
    return None


def get_file_stats_by_project(project_id):
    pm = get_project_manager()
    files = pm.list_files(project_id)

    stats = {
        'total_files': len(files),
        'by_type': {},
        'total_size_bytes': 0,
        'uploaded_files': 0,
        'generated_files': 0
    }

    for file in files:
        file_type = file.get('file_type', 'unknown')
        stats['by_type'][file_type] = stats['by_type'].get(file_type, 0) + 1
        stats['total_size_bytes'] += file.get('file_size', 0)
        if file.get('is_generated'):
            stats['generated_files'] += 1
        else:
            stats['uploaded_files'] += 1

    return stats


def get_files_for_ai_context(project_id, max_files=5, max_chars_per_file=50000, file_ids=None):
    """
    Extract file content for AI context.
    Uses file_content_reader for consistent extraction quality.
    Files retrieved from STORAGE_PATH on persistent disk.
    """
    try:
        from file_content_reader import extract_file_content
        HAS_FILE_READER = True
    except ImportError:
        print("⚠️  file_content_reader not available - using pandas fallback")
        HAS_FILE_READER = False
        extract_file_content = None

    pm = get_project_manager()

    if file_ids:
        files = []
        for file_id in file_ids:
            print(f"🔍 Looking for file_id: {file_id}")
            file_info = pm.get_file(file_id)
            if file_info:
                files.append(file_info)
                print(f"✅ Found file: {file_info.get('original_filename')} at {file_info.get('file_path')}")
            else:
                print(f"❌ File not found for file_id: {file_id}")
        print(f"✅ Retrieved {len(files)} specific file(s) by ID")
    else:
        files = pm.list_files(project_id)[:max_files]

    if not files:
        print(f"⚠️ No file context retrieved for file_ids: {file_ids}")
        return ""

    context = "\n\n=== PROJECT FILES CONTEXT ===\n"
    context += f"This project has {len(files)} file(s) available:\n\n"

    for file in files:
        print(f"\n📁 Processing file: {file['original_filename']}")
        context += f"📄 {file['original_filename']} ({file.get('file_type', 'unknown')})\n"

        if file.get('description'):
            context += f"   Description: {file['description']}\n"
        if file.get('analysis_summary'):
            context += f"   Summary: {file['analysis_summary']}\n"

        try:
            file_path = file['file_path']
            print(f"   📍 File path: {file_path}")
            print(f"   📏 File exists: {os.path.exists(file_path)}")

            if os.path.exists(file_path):
                if HAS_FILE_READER and extract_file_content:
                    extraction_result = extract_file_content(file_path)
                else:
                    file_ext = os.path.splitext(file_path)[1].lower()
                    if file_ext in ['.xlsx', '.xls']:
                        try:
                            import pandas as pd
                            df = pd.read_excel(file_path)
                            content = f"Excel file with {len(df)} rows and {len(df.columns)} columns\n"
                            content += f"Columns: {', '.join([str(col) for col in df.columns.tolist()])}\n\n"
                            content += "Sample data (first 50 rows):\n"
                            content += df.head(50).to_string()
                            extraction_result = {'success': True, 'text': content, 'data': None}
                        except Exception as e:
                            extraction_result = {'success': False, 'error': str(e)}
                    else:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(max_chars_per_file)
                            extraction_result = {'success': True, 'text': content, 'data': None}
                        except Exception as e:
                            extraction_result = {'success': False, 'error': str(e)}

                if extraction_result.get('success'):
                    content = extraction_result['text']

                    if extraction_result.get('data'):
                        data = extraction_result['data']
                        if 'sheets' in data:
                            context += f"   📊 Excel file with {data['num_sheets']} worksheet(s): {', '.join(data['sheet_names'])}\n"
                        elif 'num_pages' in data:
                            context += f"   📄 PDF with {data['num_pages']} page(s)\n"
                        elif 'num_paragraphs' in data:
                            context += f"   📝 Word document with {data['num_paragraphs']} paragraph(s)\n"

                    print(f"   ✅ Extracted {len(content)} chars")

                    if len(content) > max_chars_per_file:
                        original_len = len(content)
                        content = content[:max_chars_per_file] + f"\n\n... (truncated {original_len - max_chars_per_file} chars)\n"
                        print(f"   ✂️ Truncated to {max_chars_per_file} chars")

                    context += f"   Content:\n{content}\n"
                else:
                    print(f"   ❌ Extraction failed: {extraction_result.get('error')}")
                    context += f"   (Could not extract content: {extraction_result.get('error')})\n"
            else:
                print(f"   ❌ File does not exist at path: {file_path}")
                context += f"   (File not found at expected location)\n"

        except Exception as e:
            print(f"   ❌ ERROR reading file {file['original_filename']}: {e}")
            import traceback
            traceback.print_exc()
            context += f"   (File content could not be extracted: {str(e)})\n"

        context += "\n"

    print(f"✅ Generated context with {len(context)} total characters")
    return context


def mark_file_as_analyzed(file_id, analysis_summary=None):
    pm = get_project_manager()
    file_info = pm.get_file(file_id)
    if not file_info:
        return False

    metadata = file_info.get('metadata', {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    metadata['is_analyzed'] = True
    metadata['analysis_summary'] = analysis_summary
    metadata['analyzed_at'] = datetime.now().isoformat()

    db = get_db_connection()
    try:
        db.execute('''
            UPDATE project_files
            SET is_analyzed = TRUE,
                analysis_summary = %s,
                analyzed_at = CURRENT_TIMESTAMP,
                metadata = %s
            WHERE file_id = %s
        ''', (analysis_summary, json.dumps(metadata), file_id))
        db.commit()
        return True
    finally:
        db.close()


def search_project_files(project_id, search_term):
    pm = get_project_manager()
    all_files = pm.list_files(project_id)
    search_lower = search_term.lower()

    return [
        file for file in all_files
        if (search_lower in file['filename'].lower() or
            search_lower in file['original_filename'].lower() or
            (file.get('description') and search_lower in file['description'].lower()) or
            (file.get('analysis_summary') and search_lower in file['analysis_summary'].lower()))
    ]


def update_file_metadata(file_id, **kwargs):
    allowed_fields = ['description', 'category']
    updates = []
    values = []

    for field, value in kwargs.items():
        if field in allowed_fields:
            updates.append(f"{field} = %s")
            values.append(value)
        elif field == 'metadata':
            updates.append("metadata = %s")
            values.append(json.dumps(value) if isinstance(value, dict) else value)

    if not updates:
        return False

    values.append(file_id)

    db = get_db_connection()
    try:
        db.execute(
            f"UPDATE project_files SET {', '.join(updates)} WHERE file_id = %s",
            values
        )
        db.commit()
        return True
    finally:
        db.close()


if __name__ == '__main__':
    print("🔧 Initializing project management system...")
    pm = get_project_manager()
    print("✅ System ready!")

# I did no harm and this file is not truncated
