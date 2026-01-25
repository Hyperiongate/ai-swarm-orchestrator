"""
Database Module
Created: January 21, 2026
Last Updated: January 25, 2026 - ADDED MARKETING TABLES

All database operations isolated here.
No more SQL scattered across 2,500 lines.

CHANGELOG:
- January 25, 2026: ADDED CONTENT MARKETING ENGINE TABLES
  * Added 'marketing_content' table - stores generated posts and newsletters
  * Added 'marketing_activity_log' table - tracks approval workflow
  * Added 'marketing_performance' table - tracks engagement metrics
  * Added indexes for marketing tables

- January 23, 2026: ADDED RESEARCH AGENT TABLES
  * Added 'research_logs' table - tracks all web searches
  * Added 'research_briefings' table - stores daily briefings
  * Added 'research_findings' table - tracks interesting findings
  * Added indexes for research tables

- January 23, 2026: ADDED GENERATED DOCUMENTS TABLE
  * Added 'generated_documents' table - tracks all system-created documents
  * Added save_generated_document() - saves document metadata after creation
  * Added get_generated_documents() - retrieves document list for UI
  * Added get_generated_document() - retrieves single document by ID
  * Added delete_generated_document() - removes document record
  * Added index on generated_documents for fast queries

- January 22, 2026: ADDED PERSISTENT CONVERSATION MEMORY
  * Added 'conversations' table - stores conversation metadata
  * Added 'conversation_messages' table - stores each message
  * Added conversation CRUD functions
  * Added indexes for fast lookups
  * Phase 1 of memory system (Phase 2 will add project-specific memory)

- January 22, 2026: Added proactive intelligence tables (Sprint 1)

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import sqlite3
import json
import os
from datetime import datetime
from config import DATABASE

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initialize database tables"""
    db = get_db()
    
    # Tasks table
    db.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            user_request TEXT NOT NULL,
            task_type TEXT,
            complexity TEXT,
            assigned_orchestrator TEXT,
            orchestrator TEXT,
            status TEXT DEFAULT 'pending',
            result TEXT,
            confidence REAL,
            execution_time_seconds REAL,
            knowledge_used BOOLEAN DEFAULT 0,
            knowledge_sources TEXT,
            conversation_id TEXT
        )
    ''')
    
    # Projects table
    db.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            client_name TEXT,
            industry TEXT,
            facility_type TEXT,
            project_phase TEXT DEFAULT 'initial',
            context_data TEXT,
            uploaded_files TEXT,
            email_context TEXT,
            key_findings TEXT,
            schedules_proposed TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # Specialist assignments (calls)
    db.execute('''
        CREATE TABLE IF NOT EXISTS specialist_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            specialist_name TEXT NOT NULL,
            specialist_role TEXT,
            assigned_reason TEXT,
            prompt_sent TEXT,
            response_received TEXT,
            output TEXT,
            tokens_used INTEGER,
            duration_seconds REAL,
            execution_time_seconds REAL,
            success BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    # Consensus validations
    db.execute('''
        CREATE TABLE IF NOT EXISTS consensus_validations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            ai1_name TEXT,
            ai1_response TEXT,
            ai2_name TEXT,
            ai2_response TEXT,
            validator_ais TEXT,
            agreement_score REAL,
            consensus_achieved BOOLEAN,
            disagreements TEXT,
            final_output TEXT,
            final_decision TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    # Learning records/patterns
    db.execute('''
        CREATE TABLE IF NOT EXISTS learning_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            task_type TEXT,
            pattern_type TEXT,
            pattern_data TEXT,
            success_rate REAL,
            times_used INTEGER DEFAULT 1,
            times_applied INTEGER DEFAULT 1
        )
    ''')
    
    # Learning records (alternate table name used by feedback)
    db.execute('''
        CREATE TABLE IF NOT EXISTS learning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            task_type TEXT,
            pattern_type TEXT,
            pattern_data TEXT,
            success_rate REAL,
            times_used INTEGER DEFAULT 1,
            times_applied INTEGER DEFAULT 1
        )
    ''')
    
    # Escalations
    db.execute('''
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            escalated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT,
            sonnet_confidence REAL,
            opus_analysis TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    # User feedback
    db.execute('''
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            overall_rating INTEGER CHECK(overall_rating >= 1 AND overall_rating <= 5),
            quality_rating INTEGER CHECK(quality_rating >= 1 AND quality_rating <= 5),
            accuracy_rating INTEGER CHECK(accuracy_rating >= 1 AND accuracy_rating <= 5),
            usefulness_rating INTEGER CHECK(usefulness_rating >= 1 AND usefulness_rating <= 5),
            consensus_was_accurate BOOLEAN,
            improvement_categories TEXT,
            user_comment TEXT,
            output_used BOOLEAN,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    # ============================================================================
    # PROACTIVE INTELLIGENCE TABLES (Added January 22, 2026 - Sprint 1)
    # ============================================================================
    
    # Pattern tracking - learns user behavior
    db.execute('''
        CREATE TABLE IF NOT EXISTS user_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_data TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            suggestion_made BOOLEAN DEFAULT 0,
            suggestion_accepted BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Suggestion tracking - tracks what AI suggests
    db.execute('''
        CREATE TABLE IF NOT EXISTS proactive_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            suggestion_type TEXT NOT NULL,
            suggestion_title TEXT NOT NULL,
            suggestion_data TEXT NOT NULL,
            displayed BOOLEAN DEFAULT 0,
            accepted BOOLEAN DEFAULT 0,
            dismissed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    # Clarification history - tracks questions asked
    db.execute('''
        CREATE TABLE IF NOT EXISTS clarification_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            questions_asked TEXT NOT NULL,
            answers_provided TEXT,
            improved_result BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    # ============================================================================
    # PERSISTENT CONVERSATION MEMORY TABLES (Added January 22, 2026)
    # ============================================================================
    
    # Conversations table - stores conversation metadata
    db.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT UNIQUE NOT NULL,
            title TEXT DEFAULT 'New Conversation',
            mode TEXT DEFAULT 'quick',
            project_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            is_archived BOOLEAN DEFAULT 0,
            metadata TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
    ''')
    
    # Conversation messages table - stores each message
    db.execute('''
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            task_id INTEGER,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    # ============================================================================
    # GENERATED DOCUMENTS TABLE (Added January 23, 2026)
    # Tracks all documents created by the AI Swarm for download/print/management
    # ============================================================================
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS generated_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            document_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            task_id INTEGER,
            conversation_id TEXT,
            project_id TEXT,
            title TEXT,
            description TEXT,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP,
            download_count INTEGER DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0,
            metadata TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
    ''')
    
    # ============================================================================
    # RESEARCH AGENT TABLES (Added January 23, 2026)
    # Tracks web research, briefings, and findings
    # ============================================================================
    
    # Research logs - tracks all web searches
    db.execute('''
        CREATE TABLE IF NOT EXISTS research_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            result_count INTEGER DEFAULT 0,
            searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            search_type TEXT,
            user_initiated BOOLEAN DEFAULT 0
        )
    ''')
    
    # Research briefings - stores daily briefings
    db.execute('''
        CREATE TABLE IF NOT EXISTS research_briefings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            briefing_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            was_read BOOLEAN DEFAULT 0,
            read_at TIMESTAMP
        )
    ''')
    
    # Research findings - tracks interesting findings for follow-up
    db.execute('''
        CREATE TABLE IF NOT EXISTS research_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            title TEXT,
            url TEXT,
            summary TEXT,
            relevance_score REAL,
            found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actioned BOOLEAN DEFAULT 0,
            action_taken TEXT,
            actioned_at TIMESTAMP
        )
    ''')
    
    # ============================================================================
    # CONTENT MARKETING ENGINE TABLES (Added January 25, 2026)
    # Tracks generated marketing content (LinkedIn posts, newsletters)
    # ============================================================================
    
    # Marketing Content table - stores all generated marketing content
    db.execute('''
        CREATE TABLE IF NOT EXISTS marketing_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            content_data TEXT NOT NULL,
            status TEXT DEFAULT 'pending_approval',
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            published_at TIMESTAMP,
            rejection_reason TEXT,
            source_task_id INTEGER,
            estimated_engagement TEXT,
            actual_engagement_score REAL,
            category TEXT,
            FOREIGN KEY (source_task_id) REFERENCES tasks (id)
        )
    ''')
    
    # Marketing Activity Log - tracks all actions on marketing content
    db.execute('''
        CREATE TABLE IF NOT EXISTS marketing_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER,
            activity_type TEXT NOT NULL,
            activity_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES marketing_content (id)
        )
    ''')
    
    # Marketing Performance - tracks actual performance metrics
    db.execute('''
        CREATE TABLE IF NOT EXISTS marketing_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            engagement_rate REAL,
            measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES marketing_content (id)
        )
    ''')
    
    # ============================================================================
    # INDEXES FOR PERFORMANCE
    # ============================================================================
    
    # Proactive intelligence indexes
    db.execute('CREATE INDEX IF NOT EXISTS idx_patterns_type ON user_patterns(pattern_type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_patterns_last_seen ON user_patterns(last_seen)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_suggestions_task ON proactive_suggestions(task_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_suggestions_type ON proactive_suggestions(suggestion_type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_clarifications_task ON clarification_history(task_id)')
    
    # Conversation memory indexes
    db.execute('CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_conv_messages_conv_id ON conversation_messages(conversation_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_conv_messages_created ON conversation_messages(created_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_tasks_conversation ON tasks(conversation_id)')
    
    # Generated documents indexes
    db.execute('CREATE INDEX IF NOT EXISTS idx_gen_docs_created ON generated_documents(created_at DESC)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_gen_docs_type ON generated_documents(document_type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_gen_docs_task ON generated_documents(task_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_gen_docs_conversation ON generated_documents(conversation_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_gen_docs_project ON generated_documents(project_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_gen_docs_deleted ON generated_documents(is_deleted)')
    
    # Research agent indexes
    db.execute('CREATE INDEX IF NOT EXISTS idx_research_logs_date ON research_logs(searched_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_research_briefings_date ON research_briefings(created_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_research_findings_category ON research_findings(category)')
    
    # Marketing content indexes
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_content_status ON marketing_content(status)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_content_type ON marketing_content(content_type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_content_generated ON marketing_content(generated_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_activity_content ON marketing_activity_log(content_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_activity_created ON marketing_activity_log(created_at)')
    
    db.commit()
    db.close()
    print("✅ Database initialized (with marketing content tables)")


# ============================================================================
# GENERATED DOCUMENTS FUNCTIONS (Added January 23, 2026)
# ============================================================================

def save_generated_document(filename, original_name, document_type, file_path, file_size=0,
                           task_id=None, conversation_id=None, project_id=None,
                           title=None, description=None, category='general', metadata=None):
    """
    Save a generated document to the database for tracking.
    Called whenever the system creates a downloadable document.
    """
    db = get_db()
    
    # Use original_name as title if not provided
    if not title:
        title = original_name
    
    cursor = db.execute('''
        INSERT INTO generated_documents 
        (filename, original_name, document_type, file_path, file_size,
         task_id, conversation_id, project_id, title, description, category, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        filename, original_name, document_type, file_path, file_size,
        task_id, conversation_id, project_id, title, description, category,
        json.dumps(metadata) if metadata else None
    ))
    
    document_id = cursor.lastrowid
    db.commit()
    db.close()
    
    print(f"📄 Document saved to database: {filename} (ID: {document_id})")
    return document_id


def get_generated_documents(limit=50, document_type=None, project_id=None, 
                           conversation_id=None, include_deleted=False):
    """Get list of generated documents for display in UI."""
    db = get_db()
    
    query = 'SELECT * FROM generated_documents WHERE 1=1'
    params = []
    
    if not include_deleted:
        query += ' AND is_deleted = 0'
    
    if document_type:
        query += ' AND document_type = ?'
        params.append(document_type)
    
    if project_id:
        query += ' AND project_id = ?'
        params.append(project_id)
    
    if conversation_id:
        query += ' AND conversation_id = ?'
        params.append(conversation_id)
    
    query += ' ORDER BY created_at DESC LIMIT ?'
    params.append(limit)
    
    rows = db.execute(query, params).fetchall()
    db.close()
    
    documents = []
    for row in rows:
        doc = dict(row)
        # Parse metadata if present
        if doc.get('metadata'):
            try:
                doc['metadata'] = json.loads(doc['metadata'])
            except:
                pass
        documents.append(doc)
    
    return documents


def get_generated_document(document_id):
    """Get a single document by ID"""
    db = get_db()
    row = db.execute(
        'SELECT * FROM generated_documents WHERE id = ?', 
        (document_id,)
    ).fetchone()
    db.close()
    
    if row:
        doc = dict(row)
        if doc.get('metadata'):
            try:
                doc['metadata'] = json.loads(doc['metadata'])
            except:
                pass
        return doc
    return None


def get_generated_document_by_filename(filename):
    """Get a document by its filename"""
    db = get_db()
    row = db.execute(
        'SELECT * FROM generated_documents WHERE filename = ? AND is_deleted = 0', 
        (filename,)
    ).fetchone()
    db.close()
    
    if row:
        doc = dict(row)
        if doc.get('metadata'):
            try:
                doc['metadata'] = json.loads(doc['metadata'])
            except:
                pass
        return doc
    return None


def update_document_access(document_id):
    """Update last_accessed and increment download_count"""
    db = get_db()
    db.execute('''
        UPDATE generated_documents 
        SET last_accessed = CURRENT_TIMESTAMP,
            download_count = download_count + 1
        WHERE id = ?
    ''', (document_id,))
    db.commit()
    db.close()


def delete_generated_document(document_id, hard_delete=False):
    """Delete a generated document."""
    db = get_db()
    
    # Get the document first to find the file path
    doc = db.execute(
        'SELECT file_path FROM generated_documents WHERE id = ?',
        (document_id,)
    ).fetchone()
    
    if not doc:
        db.close()
        return False
    
    if hard_delete:
        # Delete the actual file
        try:
            if doc['file_path'] and os.path.exists(doc['file_path']):
                os.remove(doc['file_path'])
        except Exception as e:
            print(f"⚠️ Could not delete file: {e}")
        
        # Delete from database
        db.execute('DELETE FROM generated_documents WHERE id = ?', (document_id,))
    else:
        # Soft delete - just mark as deleted
        db.execute(
            'UPDATE generated_documents SET is_deleted = 1 WHERE id = ?',
            (document_id,)
        )
    
    db.commit()
    db.close()
    return True


def get_document_stats():
    """Get statistics about generated documents"""
    db = get_db()
    
    stats = {}
    
    # Total documents (not deleted)
    stats['total_documents'] = db.execute(
        'SELECT COUNT(*) FROM generated_documents WHERE is_deleted = 0'
    ).fetchone()[0]
    
    # Documents by type
    type_counts = db.execute('''
        SELECT document_type, COUNT(*) as count 
        FROM generated_documents 
        WHERE is_deleted = 0 
        GROUP BY document_type
    ''').fetchall()
    stats['by_type'] = {row['document_type']: row['count'] for row in type_counts}
    
    # Total downloads
    stats['total_downloads'] = db.execute(
        'SELECT SUM(download_count) FROM generated_documents WHERE is_deleted = 0'
    ).fetchone()[0] or 0
    
    # Total size
    stats['total_size_bytes'] = db.execute(
        'SELECT SUM(file_size) FROM generated_documents WHERE is_deleted = 0'
    ).fetchone()[0] or 0
    
    # Recent documents (last 7 days)
    stats['recent_count'] = db.execute('''
        SELECT COUNT(*) FROM generated_documents 
        WHERE is_deleted = 0 
        AND created_at >= datetime('now', '-7 days')
    ''').fetchone()[0]
    
    db.close()
    return stats


# ============================================================================
# CONVERSATION MEMORY FUNCTIONS (Added January 22, 2026)
# ============================================================================

def create_conversation(mode='quick', project_id=None, title=None):
    """Create a new conversation and return its ID"""
    import uuid
    
    conversation_id = str(uuid.uuid4())
    
    if not title:
        title = f"New Conversation - {datetime.now().strftime('%b %d, %Y %I:%M %p')}"
    
    db = get_db()
    db.execute('''
        INSERT INTO conversations (conversation_id, title, mode, project_id)
        VALUES (?, ?, ?, ?)
    ''', (conversation_id, title, mode, project_id))
    db.commit()
    db.close()
    
    return conversation_id


def get_conversation(conversation_id):
    """Get a conversation by ID"""
    db = get_db()
    conversation = db.execute('''
        SELECT * FROM conversations WHERE conversation_id = ?
    ''', (conversation_id,)).fetchone()
    db.close()
    
    return dict(conversation) if conversation else None


def get_conversations(limit=20, project_id=None, include_archived=False):
    """Get recent conversations, optionally filtered by project"""
    db = get_db()
    
    if project_id:
        if include_archived:
            rows = db.execute('''
                SELECT * FROM conversations 
                WHERE project_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (project_id, limit)).fetchall()
        else:
            rows = db.execute('''
                SELECT * FROM conversations 
                WHERE project_id = ? AND is_archived = 0
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (project_id, limit)).fetchall()
    else:
        if include_archived:
            rows = db.execute('''
                SELECT * FROM conversations 
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()
        else:
            rows = db.execute('''
                SELECT * FROM conversations 
                WHERE is_archived = 0
                ORDER BY updated_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()
    
    db.close()
    return [dict(row) for row in rows]


def update_conversation(conversation_id, title=None, mode=None, project_id=None, is_archived=None):
    """Update conversation metadata"""
    db = get_db()
    
    updates = ['updated_at = CURRENT_TIMESTAMP']
    params = []
    
    if title is not None:
        updates.append('title = ?')
        params.append(title)
    
    if mode is not None:
        updates.append('mode = ?')
        params.append(mode)
    
    if project_id is not None:
        updates.append('project_id = ?')
        params.append(project_id)
    
    if is_archived is not None:
        updates.append('is_archived = ?')
        params.append(is_archived)
    
    params.append(conversation_id)
    
    db.execute(f'''
        UPDATE conversations 
        SET {', '.join(updates)}
        WHERE conversation_id = ?
    ''', params)
    db.commit()
    db.close()


def delete_conversation(conversation_id):
    """Delete a conversation and all its messages"""
    db = get_db()
    
    # Delete messages first (foreign key constraint)
    db.execute('DELETE FROM conversation_messages WHERE conversation_id = ?', (conversation_id,))
    
    # Delete conversation
    db.execute('DELETE FROM conversations WHERE conversation_id = ?', (conversation_id,))
    
    db.commit()
    db.close()


def add_message(conversation_id, role, content, task_id=None, metadata=None):
    """Add a message to a conversation"""
    db = get_db()
    
    # Insert message
    db.execute('''
        INSERT INTO conversation_messages (conversation_id, role, content, task_id, metadata)
        VALUES (?, ?, ?, ?, ?)
    ''', (conversation_id, role, content, task_id, json.dumps(metadata) if metadata else None))
    
    # Update conversation's updated_at and message_count
    db.execute('''
        UPDATE conversations 
        SET updated_at = CURRENT_TIMESTAMP,
            message_count = message_count + 1
        WHERE conversation_id = ?
    ''', (conversation_id,))
    
    # Auto-generate title from first user message if title is default
    if role == 'user':
        conv = db.execute('''
            SELECT title, message_count FROM conversations WHERE conversation_id = ?
        ''', (conversation_id,)).fetchone()
        
        if conv and conv['message_count'] == 1 and conv['title'].startswith('New Conversation'):
            # Generate title from first message (first 50 chars)
            new_title = content[:50] + ('...' if len(content) > 50 else '')
            db.execute('''
                UPDATE conversations SET title = ? WHERE conversation_id = ?
            ''', (new_title, conversation_id))
    
    db.commit()
    db.close()


def get_messages(conversation_id, limit=100):
    """Get messages for a conversation"""
    db = get_db()
    rows = db.execute('''
        SELECT * FROM conversation_messages 
        WHERE conversation_id = ?
        ORDER BY created_at ASC
        LIMIT ?
    ''', (conversation_id, limit)).fetchall()
    db.close()
    
    return [dict(row) for row in rows]


def get_conversation_context(conversation_id, max_messages=20):
    """Get recent messages formatted for AI context"""
    messages = get_messages(conversation_id, limit=max_messages)
    
    context = []
    for msg in messages:
        context.append({
            'role': msg['role'],
            'content': msg['content']
        })
    
    return context


# ============================================================================
# TASK FUNCTIONS (needed by routes/core.py)
# ============================================================================

def record_task_completion(task_id, orchestrator, result, confidence):
    """Record completed task"""
    db = get_db()
    db.execute('''
        UPDATE tasks 
        SET status = 'completed',
            completed_at = ?,
            orchestrator = ?,
            result = ?,
            confidence = ?
        WHERE id = ?
    ''', (datetime.now(), orchestrator, result, confidence, task_id))
    db.commit()
    db.close()

def record_specialist_call(task_id, specialist_name, prompt_sent, response_received, tokens_used, duration_seconds):
    """Record specialist AI call"""
    db = get_db()
    db.execute('''
        INSERT INTO specialist_calls 
        (task_id, specialist_name, prompt_sent, response_received, tokens_used, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (task_id, specialist_name, prompt_sent, response_received, tokens_used, duration_seconds))
    db.commit()
    db.close()

def record_consensus_validation(task_id, ai1_name, ai1_response, ai2_name, ai2_response, 
                                agreement_score, consensus_achieved, final_output):
    """Record consensus validation"""
    db = get_db()
    db.execute('''
        INSERT INTO consensus_validations 
        (task_id, ai1_name, ai1_response, ai2_name, ai2_response, 
         agreement_score, consensus_achieved, final_output)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (task_id, ai1_name, ai1_response, ai2_name, ai2_response, 
          agreement_score, consensus_achieved, final_output))
    db.commit()
    db.close()

def get_task_history(limit=50):
    """Get recent task history"""
    db = get_db()
    rows = db.execute('''
        SELECT id, user_request, status, orchestrator, confidence, created_at, completed_at
        FROM tasks
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,)).fetchall()
    db.close()
    return [dict(row) for row in rows]

def get_task_details(task_id):
    """Get detailed information about a task"""
    db = get_db()
    
    # Get task
    task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        db.close()
        return None
    
    # Get escalation if exists
    escalation = db.execute('SELECT * FROM escalations WHERE task_id = ?', (task_id,)).fetchone()
    
    # Get specialist calls
    specialists = db.execute('SELECT * FROM specialist_calls WHERE task_id = ?', (task_id,)).fetchall()
    
    # Get consensus validation if exists
    consensus = db.execute('SELECT * FROM consensus_validations WHERE task_id = ?', (task_id,)).fetchone()
    
    db.close()
    
    return {
        'task': dict(task),
        'escalation': dict(escalation) if escalation else None,
        'specialists': [dict(s) for s in specialists],
        'consensus': dict(consensus) if consensus else None
    }

def get_statistics():
    """Get system statistics"""
    db = get_db()
    
    stats = {}
    
    # Total tasks
    stats['total_tasks'] = db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    
    # Completed tasks
    stats['completed_tasks'] = db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'").fetchone()[0]
    
    # Escalations
    stats['total_escalations'] = db.execute('SELECT COUNT(*) FROM escalations').fetchone()[0]
    
    # Average confidence
    avg_conf = db.execute('SELECT AVG(confidence) FROM tasks WHERE confidence IS NOT NULL').fetchone()[0]
    stats['average_confidence'] = round(avg_conf, 3) if avg_conf else 0
    
    # Specialist usage
    stats['specialist_calls'] = db.execute('SELECT COUNT(*) FROM specialist_calls').fetchone()[0]
    
    # Consensus validations
    stats['consensus_validations'] = db.execute('SELECT COUNT(*) FROM consensus_validations').fetchone()[0]
    
    # Success rate
    successful_consensus = db.execute('SELECT COUNT(*) FROM consensus_validations WHERE consensus_achieved = 1').fetchone()[0]
    total_consensus = stats['consensus_validations']
    stats['consensus_success_rate'] = round(successful_consensus / total_consensus, 3) if total_consensus > 0 else 0
    
    # Conversation stats
    stats['total_conversations'] = db.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]
    stats['total_messages'] = db.execute('SELECT COUNT(*) FROM conversation_messages').fetchone()[0]
    
    # Document stats
    stats['total_documents'] = db.execute('SELECT COUNT(*) FROM generated_documents WHERE is_deleted = 0').fetchone()[0]
    
    db.close()
    return stats

def store_learning_pattern(task_type, pattern_data, success_rate):
    """Store a learning pattern"""
    db = get_db()
    
    # Check if pattern exists
    existing = db.execute('''
        SELECT id, times_used FROM learning_patterns 
        WHERE task_type = ? AND pattern_data = ?
    ''', (task_type, pattern_data)).fetchone()
    
    if existing:
        # Update existing pattern
        db.execute('''
            UPDATE learning_patterns 
            SET success_rate = ?,
                times_used = times_used + 1,
                last_used = ?
            WHERE id = ?
        ''', (success_rate, datetime.now(), existing[0]))
    else:
        # Insert new pattern
        db.execute('''
            INSERT INTO learning_patterns (task_type, pattern_data, success_rate)
            VALUES (?, ?, ?)
        ''', (task_type, pattern_data, success_rate))
    
    db.commit()
    db.close()

def get_learning_patterns(task_type=None, limit=10):
    """Get learning patterns, optionally filtered by task type"""
    db = get_db()
    
    if task_type:
        rows = db.execute('''
            SELECT * FROM learning_patterns 
            WHERE task_type = ?
            ORDER BY success_rate DESC, times_used DESC
            LIMIT ?
        ''', (task_type, limit)).fetchall()
    else:
        rows = db.execute('''
            SELECT * FROM learning_patterns 
            ORDER BY success_rate DESC, times_used DESC
            LIMIT ?
        ''', (limit,)).fetchall()
    
    db.close()
    return [dict(row) for row in rows]

# ============================================================================
# PROJECT FUNCTIONS (for workflow management)
# ============================================================================

def load_project_from_db(project_id):
    """Load project from database"""
    try:
        from project_workflow import ProjectWorkflow
    except ImportError:
        return None
    
    db = get_db()
    project_row = db.execute(
        'SELECT * FROM projects WHERE project_id = ? AND status = "active"',
        (project_id,)
    ).fetchone()
    db.close()
    
    if not project_row:
        return None
    
    workflow = ProjectWorkflow()
    workflow.project_id = project_row['project_id']
    workflow.client_name = project_row['client_name']
    workflow.industry = project_row['industry']
    workflow.facility_type = project_row['facility_type']
    workflow.project_phase = project_row['project_phase']
    
    # Load JSON data
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

def save_project_to_db(workflow):
    """Save project to database"""
    if not workflow:
        return
    
    db = get_db()
    
    # Check if project exists
    existing = db.execute(
        'SELECT id FROM projects WHERE project_id = ?',
        (workflow.project_id,)
    ).fetchone()
    
    if existing:
        # Update existing
        db.execute('''
            UPDATE projects SET
                updated_at = CURRENT_TIMESTAMP,
                client_name = ?,
                industry = ?,
                facility_type = ?,
                project_phase = ?,
                context_data = ?,
                uploaded_files = ?,
                email_context = ?,
                key_findings = ?,
                schedules_proposed = ?
            WHERE project_id = ?
        ''', (
            workflow.client_name,
            workflow.industry,
            workflow.facility_type,
            workflow.project_phase,
            json.dumps(workflow.context_history),
            json.dumps(workflow.uploaded_files),
            json.dumps(workflow.email_context),
            json.dumps(workflow.key_findings),
            json.dumps(workflow.schedules_proposed),
            workflow.project_id
        ))
    else:
        # Insert new
        db.execute('''
            INSERT INTO projects (
                project_id, client_name, industry, facility_type, 
                project_phase, context_data, uploaded_files, email_context,
                key_findings, schedules_proposed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            workflow.project_id,
            workflow.client_name,
            workflow.industry,
            workflow.facility_type,
            workflow.project_phase,
            json.dumps(workflow.context_history),
            json.dumps(workflow.uploaded_files),
            json.dumps(workflow.email_context),
            json.dumps(workflow.key_findings),
            json.dumps(workflow.schedules_proposed)
        ))
    
    db.commit()
    db.close()


# I did no harm and this file is not truncated
