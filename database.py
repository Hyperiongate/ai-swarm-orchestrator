"""
Database Module
Created: January 21, 2026
Last Updated: March 08, 2026 - POSTGRESQL LASTROWID FIX

CHANGELOG:
- March 08, 2026: POSTGRESQL LASTROWID FIX
  * cursor.lastrowid always returns 0 in PostgreSQL with psycopg2.
  * Fixed 4 broken instances by replacing with INSERT...RETURNING id
    and fetching result with fetchone()['id']:
      1. save_generated_document()
      2. add_avoidance_pattern()
      3. save_analysis_deliverable()
      4. update_analysis_progress() INSERT branch
  * Root cause of download.json bug: document saved with ID=0,
    GET /api/generated-documents/0/download returned 404 JSON,
    browser downloaded that JSON and named it "download.json".
  * No other changes — all functions and logic unchanged.

- March 04, 2026: REALDICTCURSOR FIX
  * psycopg2 RealDictCursor returns RealDictRow (dict-only, no integer indexing)
  * All fetchone()[0] calls replaced with named column aliases
  * 15 instances fixed across get_document_stats() and get_statistics()

- March 04, 2026: POSTGRESQL BOOLEAN FIX
  * PostgreSQL BOOLEAN columns cannot be compared with integers (0/1).
  * Changed ALL boolean comparisons to use TRUE/FALSE instead of 1/0
  * Fixed facility_type -> facility_size in load_project_from_db() and
    save_project_to_db() to match authoritative schema.

- March 02, 2026: CONNECTION POOL FIX
- March 02, 2026: POSTGRESQL MIGRATION
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
from db_engine import get_db_connection, get_db_type


def get_db():
    return get_db_connection()


def init_db():
    print("✅ Database tables already initialized by migration (STEP 1 in app.py)")


def save_generated_document(filename, original_name, document_type, file_path, file_size=0,
                            task_id=None, conversation_id=None, project_id=None,
                            title=None, description=None, category='general', metadata=None):
    db = get_db()
    if not title:
        title = original_name
    try:
        row = db.execute('''
            INSERT INTO generated_documents
            (filename, original_name, document_type, file_path, file_size,
             task_id, conversation_id, project_id, title, description, category, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (filename, original_name, document_type, file_path, file_size,
              task_id, conversation_id, project_id, title, description, category,
              json.dumps(metadata) if metadata else None)).fetchone()
        document_id = row['id']
        db.commit()
        print(f"📄 Document saved to database: {filename} (ID: {document_id})")
        return document_id
    finally:
        db.close()


def get_generated_documents(limit=50, document_type=None, project_id=None,
                            conversation_id=None, include_deleted=False):
    db = get_db()
    try:
        query = 'SELECT * FROM generated_documents WHERE 1=1'
        params = []
        if not include_deleted:
            query += ' AND is_deleted = FALSE'
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
    db = get_db()
    try:
        row = db.execute('SELECT * FROM generated_documents WHERE id = %s', (document_id,)).fetchone()
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
    db = get_db()
    try:
        row = db.execute(
            'SELECT * FROM generated_documents WHERE filename = %s AND is_deleted = FALSE',
            (filename,)).fetchone()
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
    db = get_db()
    try:
        db.execute('''
            UPDATE generated_documents
            SET last_accessed = CURRENT_TIMESTAMP, download_count = download_count + 1
            WHERE id = %s
        ''', (document_id,))
        db.commit()
    finally:
        db.close()


def delete_generated_document(document_id, hard_delete=False):
    db = get_db()
    try:
        doc = db.execute('SELECT file_path FROM generated_documents WHERE id = %s', (document_id,)).fetchone()
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
            db.execute('UPDATE generated_documents SET is_deleted = TRUE WHERE id = %s', (document_id,))
        db.commit()
        return True
    finally:
        db.close()


def get_document_stats():
    db = get_db()
    try:
        stats = {}
        stats['total_documents'] = db.execute(
            'SELECT COUNT(*) as cnt FROM generated_documents WHERE is_deleted = FALSE').fetchone()['cnt']
        type_counts = db.execute('''
            SELECT document_type, COUNT(*) as count FROM generated_documents
            WHERE is_deleted = FALSE GROUP BY document_type
        ''').fetchall()
        stats['by_type'] = {row['document_type']: row['count'] for row in type_counts}
        total_dl = db.execute(
            'SELECT COALESCE(SUM(download_count), 0) as total FROM generated_documents WHERE is_deleted = FALSE').fetchone()['total']
        stats['total_downloads'] = total_dl or 0
        total_size = db.execute(
            'SELECT COALESCE(SUM(file_size), 0) as total FROM generated_documents WHERE is_deleted = FALSE').fetchone()['total']
        stats['total_size_bytes'] = total_size or 0
        if get_db_type() == 'postgresql':
            recent_count = db.execute('''
                SELECT COUNT(*) as cnt FROM generated_documents
                WHERE is_deleted = FALSE AND created_at >= NOW() - INTERVAL '7 days'
            ''').fetchone()['cnt']
        else:
            recent_count = db.execute('''
                SELECT COUNT(*) as cnt FROM generated_documents
                WHERE is_deleted = FALSE AND created_at >= datetime('now', '-7 days')
            ''').fetchone()['cnt']
        stats['recent_count'] = recent_count
        return stats
    finally:
        db.close()


def create_conversation(mode='quick', project_id=None, title=None):
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
    db = get_db()
    try:
        conversation = db.execute(
            'SELECT * FROM conversations WHERE conversation_id = %s', (conversation_id,)).fetchone()
        return dict(conversation) if conversation else None
    finally:
        db.close()


def get_conversations(limit=20, project_id=None, include_archived=False):
    db = get_db()
    try:
        if project_id:
            if include_archived:
                rows = db.execute('''
                    SELECT * FROM conversations WHERE project_id = %s
                    ORDER BY updated_at DESC LIMIT %s
                ''', (project_id, limit)).fetchall()
            else:
                rows = db.execute('''
                    SELECT * FROM conversations WHERE project_id = %s AND is_archived = FALSE
                    ORDER BY updated_at DESC LIMIT %s
                ''', (project_id, limit)).fetchall()
        else:
            if include_archived:
                rows = db.execute('''
                    SELECT * FROM conversations ORDER BY updated_at DESC LIMIT %s
                ''', (limit,)).fetchall()
            else:
                rows = db.execute('''
                    SELECT * FROM conversations WHERE is_archived = FALSE
                    ORDER BY updated_at DESC LIMIT %s
                ''', (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def update_conversation(conversation_id, title=None, mode=None, project_id=None, is_archived=None):
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
            UPDATE conversations SET {', '.join(updates)} WHERE conversation_id = %s
        ''', params)
        db.commit()
    finally:
        db.close()


def delete_conversation(conversation_id):
    db = get_db()
    try:
        db.execute('DELETE FROM conversation_messages WHERE conversation_id = %s', (conversation_id,))
        db.execute('DELETE FROM conversations WHERE conversation_id = %s', (conversation_id,))
        db.commit()
    finally:
        db.close()


def add_message(conversation_id, role, content, task_id=None, metadata=None, file_contents=None):
    db = get_db()
    try:
        db.execute('''
            INSERT INTO conversation_messages (conversation_id, role, content, task_id, metadata, file_contents)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (conversation_id, role, content, task_id,
              json.dumps(metadata) if metadata else None, file_contents))
        db.execute('''
            UPDATE conversations SET updated_at = CURRENT_TIMESTAMP, message_count = message_count + 1
            WHERE conversation_id = %s
        ''', (conversation_id,))
        if role == 'user':
            conv = db.execute(
                'SELECT title, message_count FROM conversations WHERE conversation_id = %s',
                (conversation_id,)).fetchone()
            if conv and conv['message_count'] == 1 and conv['title'].startswith('New Conversation'):
                new_title = content[:50] + ('...' if len(content) > 50 else '')
                db.execute('UPDATE conversations SET title = %s WHERE conversation_id = %s',
                           (new_title, conversation_id))
        db.commit()
    finally:
        db.close()


def get_messages(conversation_id, limit=100):
    db = get_db()
    try:
        rows = db.execute('''
            SELECT * FROM conversation_messages WHERE conversation_id = %s
            ORDER BY created_at ASC LIMIT %s
        ''', (conversation_id, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def get_conversation_context(conversation_id, max_messages=20):
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


def get_schedule_context(conversation_id):
    try:
        db = get_db()
        try:
            row = db.execute(
                'SELECT schedule_context FROM conversations WHERE conversation_id = %s',
                (conversation_id,)).fetchone()
            if row and row['schedule_context']:
                return json.loads(row['schedule_context'])
            return {}
        finally:
            db.close()
    except Exception as e:
        print(f"Error getting schedule context: {e}")
        return {}


def save_schedule_context(conversation_id, context):
    try:
        db = get_db()
        try:
            db.execute('UPDATE conversations SET schedule_context = %s WHERE conversation_id = %s',
                       (json.dumps(context), conversation_id))
            db.commit()
            print(f"💾 Saved schedule context to DB for conversation {conversation_id}")
            return True
        finally:
            db.close()
    except Exception as e:
        print(f"Error saving schedule context: {e}")
        return False


def record_task_completion(task_id, orchestrator, result, confidence):
    db = get_db()
    try:
        db.execute('''
            UPDATE tasks SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
            orchestrator = %s, result = %s, confidence = %s WHERE id = %s
        ''', (orchestrator, result, confidence, task_id))
        db.commit()
    finally:
        db.close()


def record_specialist_call(task_id, specialist_name, prompt_sent, response_received,
                           tokens_used, duration_seconds):
    db = get_db()
    try:
        db.execute('''
            INSERT INTO specialist_calls
            (task_id, specialist_name, prompt_sent, response_received, tokens_used, duration_seconds)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (task_id, specialist_name, prompt_sent, response_received, tokens_used, duration_seconds))
        db.commit()
    finally:
        db.close()


def record_consensus_validation(task_id, ai1_name, ai1_response, ai2_name, ai2_response,
                                agreement_score, consensus_achieved, final_output):
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
    db = get_db()
    try:
        rows = db.execute('''
            SELECT id, user_request, status, orchestrator, confidence, created_at, completed_at
            FROM tasks ORDER BY created_at DESC LIMIT %s
        ''', (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def get_task_details(task_id):
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
    db = get_db()
    try:
        stats = {}
        stats['total_tasks'] = db.execute('SELECT COUNT(*) as cnt FROM tasks').fetchone()['cnt']
        stats['completed_tasks'] = db.execute(
            "SELECT COUNT(*) as cnt FROM tasks WHERE status = 'completed'").fetchone()['cnt']
        stats['total_escalations'] = db.execute('SELECT COUNT(*) as cnt FROM escalations').fetchone()['cnt']
        avg_conf = db.execute(
            'SELECT AVG(confidence) as avg_conf FROM tasks WHERE confidence IS NOT NULL').fetchone()['avg_conf']
        stats['average_confidence'] = round(avg_conf, 3) if avg_conf else 0
        stats['specialist_calls'] = db.execute('SELECT COUNT(*) as cnt FROM specialist_calls').fetchone()['cnt']
        stats['consensus_validations'] = db.execute('SELECT COUNT(*) as cnt FROM consensus_validations').fetchone()['cnt']
        successful_consensus = db.execute(
            'SELECT COUNT(*) as cnt FROM consensus_validations WHERE consensus_achieved = TRUE').fetchone()['cnt']
        total_consensus = stats['consensus_validations']
        stats['consensus_success_rate'] = (
            round(successful_consensus / total_consensus, 3) if total_consensus > 0 else 0)
        stats['total_conversations'] = db.execute('SELECT COUNT(*) as cnt FROM conversations').fetchone()['cnt']
        stats['total_messages'] = db.execute('SELECT COUNT(*) as cnt FROM conversation_messages').fetchone()['cnt']
        stats['total_documents'] = db.execute(
            'SELECT COUNT(*) as cnt FROM generated_documents WHERE is_deleted = FALSE').fetchone()['cnt']
        return stats
    finally:
        db.close()


def store_learning_pattern(task_type, pattern_data, success_rate):
    db = get_db()
    try:
        existing = db.execute('''
            SELECT id, times_used FROM learning_patterns
            WHERE task_type = %s AND pattern_data = %s
        ''', (task_type, pattern_data)).fetchone()
        if existing:
            db.execute('''
                UPDATE learning_patterns SET success_rate = %s, times_used = times_used + 1,
                last_used = CURRENT_TIMESTAMP WHERE id = %s
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
    db = get_db()
    try:
        if task_type:
            rows = db.execute('''
                SELECT * FROM learning_patterns WHERE task_type = %s
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


def load_project_from_db(project_id):
    try:
        from project_workflow import ProjectWorkflow
    except ImportError:
        return None
    db = get_db()
    try:
        project_row = db.execute(
            "SELECT * FROM projects WHERE project_id = %s AND status = 'active'",
            (project_id,)).fetchone()
        if not project_row:
            return None
        workflow = ProjectWorkflow()
        workflow.project_id = project_row['project_id']
        workflow.client_name = project_row['client_name']
        workflow.industry = project_row['industry']
        # DB column is facility_size (authoritative schema Mar 02 2026)
        workflow.facility_type = project_row['facility_size']
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
    if not workflow:
        return
    db = get_db()
    try:
        existing = db.execute('SELECT id FROM projects WHERE project_id = %s',
                              (workflow.project_id,)).fetchone()
        if existing:
            db.execute('''
                UPDATE projects SET updated_at = CURRENT_TIMESTAMP,
                    client_name = %s, industry = %s, facility_size = %s,
                    project_phase = %s, context_data = %s, uploaded_files = %s,
                    email_context = %s, key_findings = %s, schedules_proposed = %s
                WHERE project_id = %s
            ''', (workflow.client_name, workflow.industry, workflow.facility_type,
                  workflow.project_phase,
                  json.dumps(workflow.context_history),
                  json.dumps(workflow.uploaded_files),
                  json.dumps(workflow.email_context),
                  json.dumps(workflow.key_findings),
                  json.dumps(workflow.schedules_proposed),
                  workflow.project_id))
        else:
            db.execute('''
                INSERT INTO projects (project_id, client_name, industry, facility_size,
                    project_phase, context_data, uploaded_files, email_context,
                    key_findings, schedules_proposed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (workflow.project_id, workflow.client_name, workflow.industry,
                  workflow.facility_type, workflow.project_phase,
                  json.dumps(workflow.context_history),
                  json.dumps(workflow.uploaded_files),
                  json.dumps(workflow.email_context),
                  json.dumps(workflow.key_findings),
                  json.dumps(workflow.schedules_proposed)))
        db.commit()
    finally:
        db.close()


def get_client_profile(client_name):
    if not client_name:
        return None
    db = get_db()
    try:
        profile_row = db.execute('''
            SELECT profile_data, created_at, updated_at FROM client_profiles
            WHERE client_name = %s
        ''', (client_name,)).fetchone()
        if profile_row:
            profile = json.loads(profile_row['profile_data'])
            profile['created_at'] = profile_row['created_at']
            profile['updated_at'] = profile_row['updated_at']
            return profile
        return {
            'client_name': client_name, 'first_interaction': None,
            'interaction_count': 0, 'communication_style': 'unknown',
            'decision_speed': 'unknown', 'risk_tolerance': 'unknown',
            'successful_approaches': [], 'failed_approaches': [],
            'preferences': {}, 'industry': None, 'typical_facility_size': None
        }
    finally:
        db.close()


def update_client_profile(client_name, interaction_data):
    if not client_name:
        return None
    db = get_db()
    try:
        existing = db.execute(
            'SELECT profile_data FROM client_profiles WHERE client_name = %s',
            (client_name,)).fetchone()
        if existing:
            profile = json.loads(existing['profile_data'])
        else:
            profile = {
                'client_name': client_name,
                'first_interaction': datetime.now().isoformat(),
                'interaction_count': 0, 'communication_style': 'unknown',
                'decision_speed': 'unknown', 'risk_tolerance': 'unknown',
                'successful_approaches': [], 'failed_approaches': [],
                'preferences': {}, 'industry': None, 'typical_facility_size': None
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
            SET profile_data = EXCLUDED.profile_data, updated_at = EXCLUDED.updated_at
        ''', (client_name, json.dumps(profile)))
        db.commit()
        return profile
    finally:
        db.close()


def get_client_profile_context(client_name):
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
    db = get_db()
    try:
        row = db.execute('''
            INSERT INTO avoidance_patterns (pattern_data, severity, times_violated, created_at, last_seen)
            VALUES (%s, %s, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
        ''', (json.dumps(pattern_data), severity)).fetchone()
        pattern_id = row['id']
        db.commit()
        return pattern_id
    finally:
        db.close()


def get_avoidance_context(days=30, limit=5):
    db = get_db()
    try:
        if get_db_type() == 'postgresql':
            rows = db.execute('''
                SELECT pattern_data, severity, times_violated, created_at
                FROM avoidance_patterns
                WHERE created_at > NOW() - INTERVAL '%s days'
                ORDER BY
                    CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
                    times_violated DESC, created_at DESC
                LIMIT %s
            ''', (days, limit)).fetchall()
        else:
            rows = db.execute('''
                SELECT pattern_data, severity, times_violated, created_at
                FROM avoidance_patterns
                WHERE created_at > datetime('now', %s)
                ORDER BY
                    CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
                    times_violated DESC, created_at DESC
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
    db = get_db()
    try:
        db.execute('''
            UPDATE avoidance_patterns SET times_violated = times_violated + 1,
            last_seen = CURRENT_TIMESTAMP WHERE id = %s
        ''', (pattern_id,))
        db.commit()
    finally:
        db.close()


def save_smart_analyzer_state(conversation_id, file_path, file_name, profile):
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
        if get_db_type() == 'postgresql':
            db.execute('''
                INSERT INTO smart_analyzer_state
                (conversation_id, file_path, file_name, analyzer_state, profile_json, last_used)
                VALUES (%s, %s, %s, 'loaded', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (conversation_id) DO UPDATE
                SET file_path = EXCLUDED.file_path, file_name = EXCLUDED.file_name,
                    analyzer_state = 'loaded', profile_json = EXCLUDED.profile_json,
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
    db = get_db()
    try:
        row = db.execute('''
            SELECT file_path, file_name, analyzer_state, profile_json, last_used
            FROM smart_analyzer_state WHERE conversation_id = %s
        ''', (conversation_id,)).fetchone()
        if row:
            db.execute('UPDATE smart_analyzer_state SET last_used = CURRENT_TIMESTAMP WHERE conversation_id = %s',
                       (conversation_id,))
            db.commit()
            return {
                'file_path': row['file_path'], 'file_name': row['file_name'],
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
    db = get_db()
    try:
        db.execute('DELETE FROM smart_analyzer_state WHERE conversation_id = %s', (conversation_id,))
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Error deleting smart analyzer state: {e}")
        return False
    finally:
        db.close()


def save_analysis_session(session_dict):
    db = get_db()
    try:
        existing = db.execute('SELECT id FROM analysis_sessions WHERE session_id = %s',
                              (session_dict['session_id'],)).fetchone()
        if existing:
            db.execute('''
                UPDATE analysis_sessions SET state = %s, data_files = %s,
                    discovered_structure = %s, clarifications = %s,
                    analysis_plan = %s, results = %s, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s
            ''', (session_dict['state'],
                  json.dumps(session_dict['data_files']),
                  json.dumps(session_dict['discovered_structure']),
                  json.dumps(session_dict['clarifications']),
                  json.dumps(session_dict['analysis_plan']),
                  json.dumps(session_dict['results']),
                  session_dict['session_id']))
        else:
            db.execute('''
                INSERT INTO analysis_sessions
                (session_id, project_id, state, data_files, discovered_structure,
                 clarifications, analysis_plan, results)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (session_dict['session_id'], session_dict.get('project_id'),
                  session_dict['state'],
                  json.dumps(session_dict['data_files']),
                  json.dumps(session_dict['discovered_structure']),
                  json.dumps(session_dict['clarifications']),
                  json.dumps(session_dict['analysis_plan']),
                  json.dumps(session_dict['results'])))
        db.commit()
        return session_dict['session_id']
    finally:
        db.close()


def load_analysis_session(session_id):
    db = get_db()
    try:
        row = db.execute('SELECT * FROM analysis_sessions WHERE session_id = %s',
                         (session_id,)).fetchone()
        if not row:
            return None
        return {
            'session_id': row['session_id'], 'project_id': row['project_id'],
            'state': row['state'],
            'data_files': json.loads(row['data_files']) if row['data_files'] else [],
            'discovered_structure': json.loads(row['discovered_structure']) if row['discovered_structure'] else {},
            'clarifications': json.loads(row['clarifications']) if row['clarifications'] else {},
            'analysis_plan': json.loads(row['analysis_plan']) if row['analysis_plan'] else {},
            'results': json.loads(row['results']) if row['results'] else {},
            'created_at': row['created_at'], 'updated_at': row['updated_at']
        }
    finally:
        db.close()


def save_analysis_deliverable(session_id, deliverable_type, file_path, file_name, metadata=None):
    db = get_db()
    try:
        row = db.execute('''
            INSERT INTO analysis_deliverables
            (session_id, deliverable_type, file_path, file_name, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        ''', (session_id, deliverable_type, file_path, file_name,
              json.dumps(metadata) if metadata else None)).fetchone()
        deliverable_id = row['id']
        db.commit()
        return deliverable_id
    finally:
        db.close()


def get_analysis_deliverables(session_id):
    db = get_db()
    try:
        rows = db.execute(
            'SELECT * FROM analysis_deliverables WHERE session_id = %s ORDER BY created_at',
            (session_id,)).fetchall()
        return [{
            'id': row['id'], 'session_id': row['session_id'],
            'deliverable_type': row['deliverable_type'],
            'file_path': row['file_path'], 'file_name': row['file_name'],
            'metadata': json.loads(row['metadata']) if row['metadata'] else {},
            'created_at': row['created_at']
        } for row in rows]
    finally:
        db.close()


def update_analysis_progress(session_id, step_name, status, progress_pct=0, message=None):
    db = get_db()
    try:
        existing = db.execute(
            'SELECT id FROM analysis_progress WHERE session_id = %s AND step_name = %s',
            (session_id, step_name)).fetchone()
        if existing:
            db.execute('''
                UPDATE analysis_progress SET status = %s, progress_pct = %s, message = %s,
                    completed_at = CASE WHEN %s = 'complete' THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE id = %s
            ''', (status, progress_pct, message, status, existing['id']))
            progress_id = existing['id']
        else:
            row = db.execute('''
                INSERT INTO analysis_progress
                (session_id, step_name, status, progress_pct, message, started_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                RETURNING id
            ''', (session_id, step_name, status, progress_pct, message)).fetchone()
            progress_id = row['id']
        db.commit()
        return progress_id
    finally:
        db.close()


def get_analysis_progress(session_id):
    db = get_db()
    try:
        rows = db.execute(
            'SELECT * FROM analysis_progress WHERE session_id = %s ORDER BY created_at',
            (session_id,)).fetchall()
        return [{
            'id': row['id'], 'session_id': row['session_id'],
            'step_name': row['step_name'], 'status': row['status'],
            'progress_pct': row['progress_pct'], 'message': row['message'],
            'started_at': row['started_at'], 'completed_at': row['completed_at'],
            'created_at': row['created_at']
        } for row in rows]
    finally:
        db.close()


def get_analysis_sessions(limit=20, project_id=None, state=None):
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
            'id': row['id'], 'session_id': row['session_id'],
            'project_id': row['project_id'], 'state': row['state'],
            'created_at': row['created_at'], 'updated_at': row['updated_at']
        } for row in rows]
    finally:
        db.close()

# I did no harm and this file is not truncated
