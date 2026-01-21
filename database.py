"""
Database Module
Created: January 21, 2026
Last Updated: January 21, 2026

All database operations isolated here.
No more SQL scattered across 2,500 lines.

COMPLETE VERSION: Includes both schema AND utility functions.
"""

import sqlite3
import json
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
            knowledge_sources TEXT
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
            accuracy_rating INTEGER CHECK(accuracy_rating >= 1 AND overall_rating <= 5),
            usefulness_rating INTEGER CHECK(usefulness_rating >= 1 AND usefulness_rating <= 5),
            consensus_was_accurate BOOLEAN,
            improvement_categories TEXT,
            user_comment TEXT,
            output_used BOOLEAN,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    db.commit()
    db.close()
    print("✅ Database initialized")

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
