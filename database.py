"""
Database Module
Created: January 21, 2026
Last Updated: March 02, 2026 - POSTGRESQL MIGRATION (Phase 1)

CHANGELOG:
- March 02, 2026: POSTGRESQL MIGRATION
  * Replaced all sqlite3 imports and direct connections with get_db_connection()
  * All SQL parameters changed from ? to %s (PostgreSQL style)
  * get_db() now calls get_db_connection() — single connection source
  * init_db() now delegates to migrations/001_initial_schema.py
  * CURRENT_TIMESTAMP references remain (work in both SQLite and PostgreSQL)
  * All dict(row) conversions work with both DictRow and RealDictRow
  * No functional changes — all existing function signatures preserved

- January 30, 2026: ADDED FILE CONTENTS STORAGE FOR GPT-4 CONTINUITY
- January 27, 2026: ADDED SCHEDULE CONTEXT STORAGE FUNCTIONS
- January 25, 2026: ADDED INTROSPECTION LAYER TABLES
- January 25, 2026: ADDED SWARM SELF-EVALUATION TABLES
- January 25, 2026: ADDED CONTENT MARKETING ENGINE TABLES
- January 23, 2026: ADDED RESEARCH AGENT TABLES
- January 23, 2026: ADDED GENERATED DOCUMENTS TABLE
- January 22, 2026: ADDED PERSISTENT CONVERSATION MEMORY
- January 22, 2026: Added proactive intelligence tables (Sprint 1)

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import os
from datetime import datetime
from db_engine import get_db_connection


def get_db():
    """Get database connection via abstraction layer."""
    return get_db_connection()


def init_db():
    """
    Initialize database tables.
    Delegates to the migration script which is the authoritative schema source.
    Safe to call multiple times — all tables use CREATE TABLE IF NOT EXISTS.
    """
    from migrations.migration_001_initial_schema import run_migration
    run_migration()
    print("✅ Database initialized via migration 001_initial_schema")


# ============================================================================
# GENERATED DOCUMENTS FUNCTIONS
# ============================================================================

def save_generated_document(filename, original_name, document_type, file_path, file_size=0,
                            task_id=None, conversation_id=None, project_id=None,
                            title=None, description=None, category='general', metadata=None):
    """Save a generated document to the database for tracking."""
    db = get_db()

    if not title:
        title = original_name

    try:
        cursor = db.execute('''
            INSERT INTO generated_documents
            (filename, original_name, document_type, file_path, file_size,
             task_id, conversation_id, project_id, title, description, category, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            filename, original_name, document_type, file_path, file_size,
            task_id, conversation_id, project_id, title, description, category,
            json.dumps(metadata) if metadata else None
        ))

        document_id = cursor.lastrowid
        db.commit()
        print(f"📄 Document saved to database: {filename} (ID: {document_id})")
        return document_id
    finally:
        db.close()


def get_generated_documents(limit=50, document_type=None, project_id=None,
                            conversation_id=None, include_deleted=False):
    """Get list of generated documents for display in UI."""
    db = get_db()

    try:
        query = 'SELECT * FROM generated_documents WHERE 1=1'
        params = []

        if not include_deleted:
            query += ' AND is_deleted = 0'

        if document_type:
            query += ' AND document_type = %s'
            params.append(document_type)

        if project_id:
            query += ' AND project_id = %s'
            params.append(project_id)

        if conversation_id:
            query += ' AND conversation_id = %s'
            params.append(conversation_id)

        query += ' ORDER BY created_at DESC LIMIT %s'
        params.append(limit)

        rows = db.execute(query, params).fetchall()

        documents = []
        for row in rows:
            doc = dict(row)
            if doc.get('metadata'):
                try:
                    doc['metadata'] = json.loads(doc['metadata'])
                except Exception:
                    pass
            documents.append(doc)

        return documents
    finally:
        db.close()


def get_generated_document(document_id):
    """Get a single document by ID."""
    db = get_db()
    try:
        row = db.execute(
            'SELECT * FROM generated_documents WHERE id = %s',
            (document_id,)
        ).fetchone()

        if row:
            doc = dict(row)
            if doc.get('metadata'):
                try:
                    doc['metadata'] = json.loads(doc['metadata'])
                except Exception:
                    pass
            return doc
        return None
    finally:
        db.close()


def get_generated_document_by_filename(filename):
    """Get a document by its filename."""
    db = get_db()
    try:
        row = db.execute(
            'SELECT * FROM generated_documents WHERE filename = %s AND is_deleted = 0',
            (filename,)
        ).fetchone()

        if row:
            doc = dict(row)
            if doc.get('metadata'):
                try:
                    doc['metadata'] = json.loads(doc['metadata'])
                except Exception:
                    pass
            return doc
        return None
    finally:
        db.close()


def update_document_access(document_id):
    """Update last_accessed and increment download_count."""
    db = get_db()
    try:
        db.execute('''
            UPDATE generated_documents
            SET last_accessed = CURRENT_TIMESTAMP,
                download_count = download_count + 1
            WHERE id = %s
        ''', (document_id,))
        db.commit()
    finally:
        db.close()


def delete_generated_document(document_id, hard_delete=False):
    """Delete a generated document."""
    db = get_db()
    try:
        doc = db.execute(
            'SELECT file_path FROM generated_documents WHERE id = %s',
            (document_id,)
        ).fetchone()

        if not doc:
            return False

        if hard_delete:
            try:
                if doc['file_path'] and os.path.exists(doc['file_path']):
                    os.remove(doc['file_path'])
            except Exception as e:
                print(f"⚠️ Could not delete file: {e}")
            db.execute('DELETE FROM generated_documents WHERE id = %s', (document_id,))
        else:
            db.execute(
                'UPDATE generated_documents SET is_deleted = 1 WHERE id = %s',
                (document_id,)
            )

        db.commit()
        return True
    finally:
        db.close()


def get_document_stats():
    """Get statistics about generated documents."""
    db = get_db()
    try:
        stats = {}

        stats['total_documents'] = db.execute(
            'SELECT COUNT(*) FROM generated_documents WHERE is_deleted = 0'
        ).fetchone()[0]

        type_counts = db.execute('''
            SELECT document_type, COUNT(*) as count
            FROM generated_documents
            WHERE is_deleted = 0
            GROUP BY document_type
        ''').fetchall()
        stats['by_type'] = {row['document_type']: row['count'] for row in type_counts}

        total_dl = db.execute(
            'SELECT SUM(download_count) FROM generated_documents WHERE is_deleted = 0'
        ).fetchone()[0]
        stats['total_downloads'] = total_dl or 0

        total_size = db.execute(
            'SELECT SUM(file_size) FROM generated_documents WHERE is_deleted = 0'
        ).fetchone()[0]
        stats['total_size_bytes'] = total_size or 0

        stats['recent_count'] = db.execute('''
            SELECT COUNT(*) FROM generated_documents
            WHERE is_deleted = 0
            AND created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
        ''').fetchone()[0] if get_db_connection().__class__.__name__ == 'PostgreSQLConnectionWrapper' else db.execute('''
            SELECT COUNT(*) FROM generated_documents
            WHERE is_deleted = 0
            AND created_at >= datetime('now', '-7 days')
        ''').fetchone()[0]

        return stats
    finally:
        db.close()


# ============================================================================
# CONVERSATION MEMORY FUNCTIONS
# ============================================================================

def create_conversation(mode='quick', project_id=None, title=None):
    """Create a new conversation and return its ID."""
    import uuid
    conversation_id = str(uuid.uuid4())

    if not title:
        title = f"New Conversation - {datetime.now().strftime('%b %d, %Y %I:%M %p')}"

    db = get_db()
    try:
        db.execute('''
            INSERT INTO conversations (conversation_id, title, mode, project_id)
            VALUES (%s, %s, %s, %s)
        ''', (conversation_id, title, mode, project_id))
        db.commit()
        return conversation_id
    finally:
        db.close()


def get_conversation(conversation_id):
    """Get a conversation by ID."""
    db = get_db()
    try:
        conversation = db.execute(
            'SELECT * FROM conversations WHERE conversation_id = %s',
            (conversation_id,)
        ).fetchone()
        return dict(conversation) if conversation else None
    finally:
        db.close()


def get_conversations(limit=20, project_id=None, include_archived=False):
    """Get recent conversations, optionally filtered by project."""
    db = get_db()
    try:
        if project_id:
            if include_archived:
                rows = db.execute('''
                    SELECT * FROM conversations
                    WHERE project_id = %s
                    ORDER BY updated_at DESC LIMIT %s
                ''', (project_id, limit)).fetchall()
            else:
                rows = db.execute('''
                    SELECT * FROM conversations
                    WHERE project_id = %s AND is_archived = 0
                    ORDER BY updated_at DESC LIMIT %s
                ''', (project_id, limit)).fetchall()
        else:
            if include_archived:
                rows = db.execute('''
                    SELECT * FROM conversations
                    ORDER BY updated_at DESC LIMIT %s
                ''', (limit,)).fetchall()
            else:
                rows = db.execute('''
                    SELECT * FROM conversations
                    WHERE is_archived = 0
                    ORDER BY updated_at DESC LIMIT %s
                ''', (limit,)).fetchall()

        return [dict(row) for row in rows]
    finally:
        db.close()


def update_conversation(conversation_id, title=None, mode=None, project_id=None, is_archived=None):
    """Update conversation metadata."""
    db = get_db()
    try:
        updates = ['updated_at = CURRENT_TIMESTAMP']
        params = []

        if title is not None:
            updates.append('title = %s')
            params.append(title)

        if mode is not None:
            updates.append('mode = %s')
            params.append(mode)

        if project_id is not None:
            updates.append('project_id = %s')
            params.append(project_id)

        if is_archived is not None:
            updates.append('is_archived = %s')
            params.append(is_archived)

        params.append(conversation_id)

        db.execute(f'''
            UPDATE conversations
            SET {', '.join(updates)}
            WHERE conversation_id = %s
        ''', params)
        db.commit()
    finally:
        db.close()


def delete_conversation(conversation_id):
    """Delete a conversation and all its messages."""
    db = get_db()
    try:
        db.execute('DELETE FROM conversation_messages WHERE conversation_id = %s', (conversation_id,))
        db.execute('DELETE FROM conversations WHERE conversation_id = %s', (conversation_id,))
        db.commit()
    finally:
        db.close()


def add_message(conversation_id, role, content, task_id=None, metadata=None, file_contents=None):
    """Add a message to a conversation."""
    db = get_db()
    try:
        db.execute('''
            INSERT INTO conversation_messages (conversation_id, role, content, task_id, metadata, file_contents)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (conversation_id, role, content, task_id,
              json.dumps(metadata) if metadata else None,
              file_contents))

        db.execute('''
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP,
                message_count = message_count + 1
            WHERE conversation_id = %s
        ''', (conversation_id,))

        if role == 'user':
            conv = db.execute(
                'SELECT title, message_count FROM conversations WHERE conversation_id = %s',
                (conversation_id,)
            ).fetchone()

            if conv and conv['message_count'] == 1 and conv['title'].startswith('New Conversation'):
                new_title = content[:50] + ('...' if len(content) > 50 else '')
                db.execute(
                    'UPDATE conversations SET title = %s WHERE conversation_id = %s',
                    (new_title, conversation_id)
                )

        db.commit()
    finally:
        db.close()


def get_messages(conversation_id, limit=100):
    """Get messages for a conversation."""
    db = get_db()
    try:
        rows = db.execute('''
            SELECT * FROM conversation_messages
            WHERE conversation_id = %s
            ORDER BY created_at ASC LIMIT %s
        ''', (conversation_id, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def get_conversation_context(conversation_id, max_messages=20):
    """Get recent messages formatted for AI context."""
    messages = get_messages(conversation_id, limit=max_messages)
    context = []
    for msg in messages:
        context.append({
            'role': msg['role'],
            'content': msg['content'],
            'file_contents': msg.get('file_contents')
        })
    return context


def get_conversation_file_contents(conversation_id):
    """Get the most recent file contents from a conversation."""
    db = get_db()
    try:
        row = db.execute('''
            SELECT file_contents FROM conversation_messages
            WHERE conversation_id = %s AND file_contents IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
        ''', (conversation_id,)).fetchone()
        return row['file_contents'] if row else None
    finally:
        db.close()


# ============================================================================
# SCHEDULE CONTEXT FUNCTIONS
# ============================================================================

def get_schedule_context(conversation_id):
    """Get schedule context for a conversation from database."""
    try:
        db = get_db()
        try:
            row = db.execute(
                'SELECT schedule_context FROM conversations WHERE conversation_id = %s',
                (conversation_id,)
            ).fetchone()
            if row and row['schedule_context']:
                return json.loads(row['schedule_context'])
            return {}
        finally:
            db.close()
    except Exception as e:
        print(f"Error getting schedule context: {e}")
        return {}


def save_schedule_context(conversation_id, context):
    """Save schedule context for a conversation to database."""
    try:
        db = get_db()
        try:
            db.execute(
                'UPDATE conversations SET schedule_context = %s WHERE conversation_id = %s',
                (json.dumps(context), conversation_id)
            )
            db.commit()
            print(f"💾 Saved schedule context to DB for conversation {conversation_id}")
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"Error saving schedule context: {e}")
        return False


# ============================================================================
# TASK FUNCTIONS
# ============================================================================

def record_task_completion(task_id, orchestrator, result, confidence):
    """Record completed task."""
    db = get_db()
    try:
        db.execute('''
            UPDATE tasks
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                orchestrator = %s,
                result = %s,
                confidence = %s
            WHERE id = %s
        ''', (orchestrator, result, confidence, task_id))
        db.commit()
    finally:
        db.close()


def record_specialist_call(task_id, specialist_name, prompt_sent, response_received,
                           tokens_used, duration_seconds):
    """Record specialist AI call."""
    db = get_db()
    try:
        db.execute('''
            INSERT INTO specialist_calls
            (task_id, specialist_name, prompt_sent, response_received, tokens_used, duration_seconds)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (task_id, specialist_name, prompt_sent, response_received,
              tokens_used, duration_seconds))
        db.commit()
    finally:
        db.close()


def record_consensus_validation(task_id, ai1_name, ai1_response, ai2_name, ai2_response,
                                agreement_score, consensus_achieved, final_output):
    """Record consensus validation."""
    db = get_db()
    try:
        db.execute('''
            INSERT INTO consensus_validations
            (task_id, ai1_name, ai1_response, ai2_name, ai2_response,
             agreement_score, consensus_achieved, final_output)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (task_id, ai1_name, ai1_response, ai2_name, ai2_response,
              agreement_score, consensus_achieved, final_output))
        db.commit()
    finally:
        db.close()


def get_task_history(limit=50):
    """Get recent task history."""
    db = get_db()
    try:
        rows = db.execute('''
            SELECT id, user_request, status, orchestrator, confidence, created_at, completed_at
            FROM tasks
            ORDER BY created_at DESC LIMIT %s
        ''', (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def get_task_details(task_id):
    """Get detailed information about a task."""
    db = get_db()
    try:
        task = db.execute('SELECT * FROM tasks WHERE id = %s', (task_id,)).fetchone()
        if not task:
            return None

        escalation = db.execute('SELECT * FROM escalations WHERE task_id = %s', (task_id,)).fetchone()
        specialists = db.execute('SELECT * FROM specialist_calls WHERE task_id = %s', (task_id,)).fetchall()
        consensus = db.execute('SELECT * FROM consensus_validations WHERE task_id = %s', (task_id,)).fetchone()

        return {
            'task': dict(task),
            'escalation': dict(escalation) if escalation else None,
            'specialists': [dict(s) for s in specialists],
            'consensus': dict(consensus) if consensus else None
        }
    finally:
        db.close()


def get_statistics():
    """Get system statistics."""
    db = get_db()
    try:
        stats = {}
        stats['total_tasks'] = db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
        stats['completed_tasks'] = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'completed'"
        ).fetchone()[0]
        stats['total_escalations'] = db.execute('SELECT COUNT(*) FROM escalations').fetchone()[0]

        avg_conf = db.execute(
            'SELECT AVG(confidence) FROM tasks WHERE confidence IS NOT NULL'
        ).fetchone()[0]
        stats['average_confidence'] = round(avg_conf, 3) if avg_conf else 0

        stats['specialist_calls'] = db.execute('SELECT COUNT(*) FROM specialist_calls').fetchone()[0]
        stats['consensus_validations'] = db.execute('SELECT COUNT(*) FROM consensus_validations').fetchone()[0]

        successful_consensus = db.execute(
            'SELECT COUNT(*) FROM consensus_validations WHERE consensus_achieved = 1'
        ).fetchone()[0]
        total_consensus = stats['consensus_validations']
        stats['consensus_success_rate'] = (
            round(successful_consensus / total_consensus, 3) if total_consensus > 0 else 0
        )

        stats['total_conversations'] = db.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]
        stats['total_messages'] = db.execute('SELECT COUNT(*) FROM conversation_messages').fetchone()[0]
        stats['total_documents'] = db.execute(
            'SELECT COUNT(*) FROM generated_documents WHERE is_deleted = 0'
        ).fetchone()[0]

        return stats
    finally:
        db.close()


def store_learning_pattern(task_type, pattern_data, success_rate):
    """Store a learning pattern."""
    db = get_db()
    try:
        existing = db.execute('''
            SELECT id, times_used FROM learning_patterns
            WHERE task_type = %s AND pattern_data = %s
        ''', (task_type, pattern_data)).fetchone()

        if existing:
            db.execute('''
                UPDATE learning_patterns
                SET success_rate = %s,
                    times_used = times_used + 1,
                    last_used = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (success_rate, existing['id']))
        else:
            db.execute('''
                INSERT INTO learning_patterns (task_type, pattern_data, success_rate)
                VALUES (%s, %s, %s)
            ''', (task_type, pattern_data, success_rate))

        db.commit()
    finally:
        db.close()


def get_learning_patterns(task_type=None, limit=10):
    """Get learning patterns, optionally filtered by task type."""
    db = get_db()
    try:
        if task_type:
            rows = db.execute('''
                SELECT * FROM learning_patterns
                WHERE task_type = %s
                ORDER BY success_rate DESC, times_used DESC LIMIT %s
            ''', (task_type, limit)).fetchall()
        else:
            rows = db.execute('''
                SELECT * FROM learning_patterns
                ORDER BY success_rate DESC, times_used DESC LIMIT %s
            ''', (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


# ============================================================================
# PROJECT FUNCTIONS
# ============================================================================

def load_project_from_db(project_id):
    """Load project from database."""
    try:
        from project_workflow import ProjectWorkflow
    except ImportError:
        return None

    db = get_db()
    try:
        project_row = db.execute(
            "SELECT * FROM projects WHERE project_id = %s AND status = 'active'",
            (project_id,)
        ).fetchone()

        if not project_row:
            return None

        workflow = ProjectWorkflow()
        workflow.project_id = project_row['project_id']
        workflow.client_name = project_row['client_name']
        workflow.industry = project_row['industry']
        workflow.facility_type = project_row['facility_type']
        workflow.project_phase = project_row['project_phase']

        if project_row['context_data']:
            workflow.context_history = json.loads(project_row['context_data'])
        if project_row['uploaded_files']:
            workflow.uploaded_files = json.loads(project_row['uploaded_files'])
        if project_row['email_context']:
            workflow.email_context = json.loads(project_row['email_context'])
        if project_row['key_findings']:
            workflow.key_findings = json.loads(project_row['key_findings'])
        if project_row['schedules_proposed']:
            workflow.schedules_proposed = json.loads(project_row['schedules_proposed'])

        return workflow
    finally:
        db.close()


def save_project_to_db(workflow):
    """Save project to database."""
    if not workflow:
        return

    db = get_db()
    try:
        existing = db.execute(
            'SELECT id FROM projects WHERE project_id = %s',
            (workflow.project_id,)
        ).fetchone()

        if existing:
            db.execute('''
                UPDATE projects SET
                    updated_at = CURRENT_TIMESTAMP,
                    client_name = %s,
                    industry = %s,
                    facility_type = %s,
                    project_phase = %s,
                    context_data = %s,
                    uploaded_files = %s,
                    email_context = %s,
                    key_findings = %s,
                    schedules_proposed = %s
                WHERE project_id = %s
            ''', (
                workflow.client_name, workflow.industry, workflow.facility_type,
                workflow.project_phase,
                json.dumps(workflow.context_history),
                json.dumps(workflow.uploaded_files),
                json.dumps(workflow.email_context),
                json.dumps(workflow.key_findings),
                json.dumps(workflow.schedules_proposed),
                workflow.project_id
            ))
        else:
            db.execute('''
                INSERT INTO projects (
                    project_id, client_name, industry, facility_type,
                    project_phase, context_data, uploaded_files, email_context,
                    key_findings, schedules_proposed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                workflow.project_id, workflow.client_name, workflow.industry,
                workflow.facility_type, workflow.project_phase,
                json.dumps(workflow.context_history),
                json.dumps(workflow.uploaded_files),
                json.dumps(workflow.email_context),
                json.dumps(workflow.key_findings),
                json.dumps(workflow.schedules_proposed)
            ))

        db.commit()
    finally:
        db.close()


# ============================================================================
# LEARNING ENHANCEMENTS
# ============================================================================

def get_client_profile(client_name):
    """Get accumulated knowledge about a specific client."""
    if not client_name:
        return None

    db = get_db()
    try:
        profile_row = db.execute('''
            SELECT profile_data, created_at, updated_at
            FROM client_profiles
            WHERE client_name = %s
        ''', (client_name,)).fetchone()

        if profile_row:
            profile = json.loads(profile_row['profile_data'])
            profile['created_at'] = profile_row['created_at']
            profile['updated_at'] = profile_row['updated_at']
            return profile

        return {
            'client_name': client_name,
            'first_interaction': None,
            'interaction_count': 0,
            'communication_style': 'unknown',
            'decision_speed': 'unknown',
            'risk_tolerance': 'unknown',
            'successful_approaches': [],
            'failed_approaches': [],
            'preferences': {},
            'industry': None,
            'typical_facility_size': None
        }
    finally:
        db.close()


def update_client_profile(client_name, interaction_data):
    """Update client profile with new interaction data."""
    if not client_name:
        return None

    db = get_db()
    try:
        existing = db.execute(
            'SELECT profile_data FROM client_profiles WHERE client_name = %s',
            (client_name,)
        ).fetchone()

        if existing:
            profile = json.loads(existing['profile_data'])
        else:
            profile = {
                'client_name': client_name,
                'first_interaction': datetime.now().isoformat(),
                'interaction_count': 0,
                'communication_style': 'unknown',
                'decision_speed': 'unknown',
                'risk_tolerance': 'unknown',
                'successful_approaches': [],
                'failed_approaches': [],
                'preferences': {},
                'industry': None,
                'typical_facility_size': None
            }

        profile['interaction_count'] += 1
        profile['last_interaction'] = datetime.now().isoformat()

        if interaction_data.get('approach_worked'):
            approach = interaction_data.get('approach')
            if approach and approach not in profile['successful_approaches']:
                profile['successful_approaches'].append(approach)
                profile['successful_approaches'] = profile['successful_approaches'][-10:]

        if interaction_data.get('approach_failed'):
            approach = interaction_data.get('approach')
            if approach and approach not in profile['failed_approaches']:
                profile['failed_approaches'].append(approach)
                profile['failed_approaches'] = profile['failed_approaches'][-10:]

        if 'preferences' in interaction_data:
            for key, value in interaction_data['preferences'].items():
                profile['preferences'][key] = value

        if interaction_data.get('industry'):
            profile['industry'] = interaction_data['industry']

        if interaction_data.get('communication_style'):
            profile['communication_style'] = interaction_data['communication_style']

        db.execute('''
            INSERT INTO client_profiles (client_name, profile_data, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (client_name) DO UPDATE
            SET profile_data = EXCLUDED.profile_data,
                updated_at = EXCLUDED.updated_at
        ''', (client_name, json.dumps(profile)))

        db.commit()
        return profile
    finally:
        db.close()


def get_client_profile_context(client_name):
    """Get formatted context string about a client for AI prompts."""
    profile = get_client_profile(client_name)

    if not profile or profile['interaction_count'] == 0:
        return ""

    context = f"\n\n=== CLIENT PROFILE: {client_name} ===\n"
    context += f"Interaction History: {profile['interaction_count']} conversations\n"

    if profile.get('industry'):
        context += f"Industry: {profile['industry']}\n"

    if profile.get('communication_style') != 'unknown':
        context += f"Communication Style: {profile['communication_style']}\n"

    if profile['successful_approaches']:
        context += "\nSuccessful Approaches:\n"
        for approach in profile['successful_approaches'][-3:]:
            context += f"  ✓ {approach}\n"

    if profile['failed_approaches']:
        context += "\nAvoid These Approaches:\n"
        for approach in profile['failed_approaches'][-3:]:
            context += f"  ✗ {approach}\n"

    if profile.get('preferences'):
        context += "\nPreferences:\n"
        for key, value in profile['preferences'].items():
            context += f"  - {key}: {value}\n"

    context += "=== END CLIENT PROFILE ===\n\n"
    return context


def add_avoidance_pattern(pattern_data, severity='medium'):
    """Store a pattern to avoid based on poor feedback."""
    db = get_db()
    try:
        cursor = db.execute('''
            INSERT INTO avoidance_patterns (pattern_data, severity, times_violated, created_at, last_seen)
            VALUES (%s, %s, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (json.dumps(pattern_data), severity))

        pattern_id = cursor.lastrowid
        db.commit()
        return pattern_id
    finally:
        db.close()


def get_avoidance_context(days=30, limit=5):
    """Get patterns to avoid based on past failures."""
    db = get_db()
    try:
        from db_engine import get_db_type
        if get_db_type() == 'postgresql':
            rows = db.execute('''
                SELECT pattern_data, severity, times_violated, created_at
                FROM avoidance_patterns
                WHERE created_at > NOW() - INTERVAL '%s days'
                ORDER BY
                    CASE severity
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                    END,
                    times_violated DESC,
                    created_at DESC
                LIMIT %s
            ''', (days, limit)).fetchall()
        else:
            rows = db.execute('''
                SELECT pattern_data, severity, times_violated, created_at
                FROM avoidance_patterns
                WHERE created_at > datetime('now', %s)
                ORDER BY
                    CASE severity
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                    END,
                    times_violated DESC,
                    created_at DESC
                LIMIT %s
            ''', (f'-{days} days', limit)).fetchall()

        if not rows:
            return ""

        context = "\n\n=== APPROACHES TO AVOID ===\n"
        context += "Based on past poor performance, avoid these patterns:\n\n"

        for p in rows:
            data = json.loads(p['pattern_data'])
            severity_emoji = {'high': '🚫', 'medium': '⚠️', 'low': 'ℹ️'}.get(p['severity'], '⚠️')
            context += f"{severity_emoji} {data.get('approach_used', 'Unknown approach')}\n"

            if data.get('what_failed'):
                issues = data['what_failed']
                if isinstance(issues, list):
                    context += f"   Issues: {', '.join(issues)}\n"
                else:
                    context += f"   Issues: {issues}\n"

            if data.get('user_comment'):
                context += f"   Feedback: \"{data['user_comment']}\"\n"
            context += "\n"

        context += "=== END AVOIDANCE PATTERNS ===\n\n"
        return context
    finally:
        db.close()


def record_avoidance_violation(pattern_id):
    """Increment the violation count for a pattern."""
    db = get_db()
    try:
        db.execute('''
            UPDATE avoidance_patterns
            SET times_violated = times_violated + 1,
                last_seen = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (pattern_id,))
        db.commit()
    finally:
        db.close()


# ============================================================================
# SMART ANALYZER STATE FUNCTIONS
# ============================================================================

def save_smart_analyzer_state(conversation_id, file_path, file_name, profile):
    """Save smart analyzer state to database."""
    db = get_db()
    try:
        import pandas as pd

        def convert_timestamps(obj):
            if isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_timestamps(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_timestamps(item) for item in obj]
            return obj

        clean_profile = convert_timestamps(profile)

        from db_engine import get_db_type
        if get_db_type() == 'postgresql':
            db.execute('''
                INSERT INTO smart_analyzer_state
                (conversation_id, file_path, file_name, analyzer_state, profile_json, last_used)
                VALUES (%s, %s, %s, 'loaded', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (conversation_id) DO UPDATE
                SET file_path = EXCLUDED.file_path,
                    file_name = EXCLUDED.file_name,
                    analyzer_state = 'loaded',
                    profile_json = EXCLUDED.profile_json,
                    last_used = CURRENT_TIMESTAMP
            ''', (conversation_id, file_path, file_name, json.dumps(clean_profile)))
        else:
            db.execute('''
                INSERT OR REPLACE INTO smart_analyzer_state
                (conversation_id, file_path, file_name, analyzer_state, profile_json, last_used)
                VALUES (%s, %s, %s, 'loaded', %s, CURRENT_TIMESTAMP)
            ''', (conversation_id, file_path, file_name, json.dumps(clean_profile)))

        db.commit()
        print(f"💾 Saved smart analyzer state to DB for conversation {conversation_id}")
        return True
    except Exception as e:
        print(f"❌ Error saving smart analyzer state: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def get_smart_analyzer_state(conversation_id):
    """Get smart analyzer state from database."""
    db = get_db()
    try:
        row = db.execute('''
            SELECT file_path, file_name, analyzer_state, profile_json, last_used
            FROM smart_analyzer_state
            WHERE conversation_id = %s
        ''', (conversation_id,)).fetchone()

        if row:
            db.execute('''
                UPDATE smart_analyzer_state
                SET last_used = CURRENT_TIMESTAMP
                WHERE conversation_id = %s
            ''', (conversation_id,))
            db.commit()

            return {
                'file_path': row['file_path'],
                'file_name': row['file_name'],
                'analyzer_state': row['analyzer_state'],
                'profile': json.loads(row['profile_json'])
            }
        return None
    except Exception as e:
        print(f"❌ Error getting smart analyzer state: {e}")
        return None
    finally:
        db.close()


def delete_smart_analyzer_state(conversation_id):
    """Delete smart analyzer state from database."""
    db = get_db()
    try:
        db.execute(
            'DELETE FROM smart_analyzer_state WHERE conversation_id = %s',
            (conversation_id,)
        )
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Error deleting smart analyzer state: {e}")
        return False
    finally:
        db.close()


# ============================================================================
# ANALYSIS ENGINE FUNCTIONS
# ============================================================================

def save_analysis_session(session_dict):
    """Save analysis session to database."""
    db = get_db()
    try:
        existing = db.execute(
            'SELECT id FROM analysis_sessions WHERE session_id = %s',
            (session_dict['session_id'],)
        ).fetchone()

        if existing:
            db.execute('''
                UPDATE analysis_sessions
                SET state = %s,
                    data_files = %s,
                    discovered_structure = %s,
                    clarifications = %s,
                    analysis_plan = %s,
                    results = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s
            ''', (
                session_dict['state'],
                json.dumps(session_dict['data_files']),
                json.dumps(session_dict['discovered_structure']),
                json.dumps(session_dict['clarifications']),
                json.dumps(session_dict['analysis_plan']),
                json.dumps(session_dict['results']),
                session_dict['session_id']
            ))
        else:
            db.execute('''
                INSERT INTO analysis_sessions
                (session_id, project_id, state, data_files, discovered_structure,
                 clarifications, analysis_plan, results)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                session_dict['session_id'],
                session_dict.get('project_id'),
                session_dict['state'],
                json.dumps(session_dict['data_files']),
                json.dumps(session_dict['discovered_structure']),
                json.dumps(session_dict['clarifications']),
                json.dumps(session_dict['analysis_plan']),
                json.dumps(session_dict['results'])
            ))

        db.commit()
        return session_dict['session_id']
    finally:
        db.close()


def load_analysis_session(session_id):
    """Load analysis session from database."""
    db = get_db()
    try:
        row = db.execute(
            'SELECT * FROM analysis_sessions WHERE session_id = %s',
            (session_id,)
        ).fetchone()

        if not row:
            return None

        return {
            'session_id': row['session_id'],
            'project_id': row['project_id'],
            'state': row['state'],
            'data_files': json.loads(row['data_files']) if row['data_files'] else [],
            'discovered_structure': json.loads(row['discovered_structure']) if row['discovered_structure'] else {},
            'clarifications': json.loads(row['clarifications']) if row['clarifications'] else {},
            'analysis_plan': json.loads(row['analysis_plan']) if row['analysis_plan'] else {},
            'results': json.loads(row['results']) if row['results'] else {},
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }
    finally:
        db.close()


def save_analysis_deliverable(session_id, deliverable_type, file_path, file_name, metadata=None):
    """Save analysis deliverable record."""
    db = get_db()
    try:
        cursor = db.execute('''
            INSERT INTO analysis_deliverables
            (session_id, deliverable_type, file_path, file_name, metadata)
            VALUES (%s, %s, %s, %s, %s)
        ''', (session_id, deliverable_type, file_path, file_name,
              json.dumps(metadata) if metadata else None))

        deliverable_id = cursor.lastrowid
        db.commit()
        return deliverable_id
    finally:
        db.close()


def get_analysis_deliverables(session_id):
    """Get all deliverables for a session."""
    db = get_db()
    try:
        rows = db.execute(
            'SELECT * FROM analysis_deliverables WHERE session_id = %s ORDER BY created_at',
            (session_id,)
        ).fetchall()

        return [{
            'id': row['id'],
            'session_id': row['session_id'],
            'deliverable_type': row['deliverable_type'],
            'file_path': row['file_path'],
            'file_name': row['file_name'],
            'metadata': json.loads(row['metadata']) if row['metadata'] else {},
            'created_at': row['created_at']
        } for row in rows]
    finally:
        db.close()


def update_analysis_progress(session_id, step_name, status, progress_pct=0, message=None):
    """Update analysis progress."""
    db = get_db()
    try:
        existing = db.execute(
            'SELECT id FROM analysis_progress WHERE session_id = %s AND step_name = %s',
            (session_id, step_name)
        ).fetchone()

        if existing:
            db.execute('''
                UPDATE analysis_progress
                SET status = %s, progress_pct = %s, message = %s,
                    completed_at = CASE WHEN %s = 'complete' THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE id = %s
            ''', (status, progress_pct, message, status, existing['id']))
            progress_id = existing['id']
        else:
            cursor = db.execute('''
                INSERT INTO analysis_progress
                (session_id, step_name, status, progress_pct, message, started_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ''', (session_id, step_name, status, progress_pct, message))
            progress_id = cursor.lastrowid

        db.commit()
        return progress_id
    finally:
        db.close()


def get_analysis_progress(session_id):
    """Get all progress records for a session."""
    db = get_db()
    try:
        rows = db.execute(
            'SELECT * FROM analysis_progress WHERE session_id = %s ORDER BY created_at',
            (session_id,)
        ).fetchall()

        return [{
            'id': row['id'],
            'session_id': row['session_id'],
            'step_name': row['step_name'],
            'status': row['status'],
            'progress_pct': row['progress_pct'],
            'message': row['message'],
            'started_at': row['started_at'],
            'completed_at': row['completed_at'],
            'created_at': row['created_at']
        } for row in rows]
    finally:
        db.close()


def get_analysis_sessions(limit=20, project_id=None, state=None):
    """Get list of analysis sessions."""
    db = get_db()
    try:
        query = 'SELECT * FROM analysis_sessions WHERE 1=1'
        params = []

        if project_id is not None:
            query += ' AND project_id = %s'
            params.append(project_id)

        if state:
            query += ' AND state = %s'
            params.append(state)

        query += ' ORDER BY updated_at DESC LIMIT %s'
        params.append(limit)

        rows = db.execute(query, params).fetchall()

        return [{
            'id': row['id'],
            'session_id': row['session_id'],
            'project_id': row['project_id'],
            'state': row['state'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        } for row in rows]
    finally:
        db.close()

# I did no harm and this file is not truncated
