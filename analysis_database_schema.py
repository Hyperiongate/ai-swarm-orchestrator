"""
Database Schema for Analysis Engine
Created: February 8, 2026
Last Updated: February 8, 2026

This file defines the database tables needed for the Analysis Engine.
Add these tables to your existing database.py init_db() function.

Author: Shiftwork Solutions LLC
Phase: 0A - Foundation
"""

# SQL for creating analysis_sessions table
CREATE_ANALYSIS_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS analysis_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    project_id INTEGER,
    state TEXT NOT NULL,
    data_files TEXT,  -- JSON array of file paths
    discovered_structure TEXT,  -- JSON object
    clarifications TEXT,  -- JSON object
    analysis_plan TEXT,  -- JSON object
    results TEXT,  -- JSON object
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
"""

# SQL for creating analysis_deliverables table
CREATE_ANALYSIS_DELIVERABLES_TABLE = """
CREATE TABLE IF NOT EXISTS analysis_deliverables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    deliverable_type TEXT NOT NULL,  -- 'chart', 'pptx', 'summary', 'code', 'excel'
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    metadata TEXT,  -- JSON object with additional info
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES analysis_sessions(session_id)
);
"""

# SQL for creating analysis_progress table
CREATE_ANALYSIS_PROGRESS_TABLE = """
CREATE TABLE IF NOT EXISTS analysis_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'pending', 'running', 'complete', 'error'
    progress_pct INTEGER DEFAULT 0,
    message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES analysis_sessions(session_id)
);
"""

# Index for faster lookups
CREATE_ANALYSIS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_analysis_sessions_project ON analysis_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_analysis_sessions_state ON analysis_sessions(state);
CREATE INDEX IF NOT EXISTS idx_analysis_deliverables_session ON analysis_deliverables(session_id);
CREATE INDEX IF NOT EXISTS idx_analysis_progress_session ON analysis_progress(session_id);
"""


# Python functions to add to database.py

def init_analysis_tables(db):
    """
    Initialize analysis engine tables
    
    Args:
        db: Database connection
    """
    db.execute(CREATE_ANALYSIS_SESSIONS_TABLE)
    db.execute(CREATE_ANALYSIS_DELIVERABLES_TABLE)
    db.execute(CREATE_ANALYSIS_PROGRESS_TABLE)
    
    # Create indexes
    for index_sql in CREATE_ANALYSIS_INDEXES.split(';'):
        if index_sql.strip():
            db.execute(index_sql)
    
    db.commit()


def save_analysis_session(session_dict):
    """
    Save analysis session to database
    
    Args:
        session_dict: Dictionary from AnalysisOrchestrator.to_dict()
        
    Returns:
        Session ID
    """
    import json
    from database import get_db
    
    db = get_db()
    
    # Check if session exists
    existing = db.execute(
        'SELECT id FROM analysis_sessions WHERE session_id = ?',
        (session_dict['session_id'],)
    ).fetchone()
    
    if existing:
        # Update existing
        db.execute('''
            UPDATE analysis_sessions
            SET state = ?,
                data_files = ?,
                discovered_structure = ?,
                clarifications = ?,
                analysis_plan = ?,
                results = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
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
        # Insert new
        db.execute('''
            INSERT INTO analysis_sessions 
            (session_id, project_id, state, data_files, discovered_structure, 
             clarifications, analysis_plan, results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
    db.close()
    
    return session_dict['session_id']


def load_analysis_session(session_id):
    """
    Load analysis session from database
    
    Args:
        session_id: Session ID to load
        
    Returns:
        Dictionary with session data or None
    """
    import json
    from database import get_db
    
    db = get_db()
    row = db.execute(
        'SELECT * FROM analysis_sessions WHERE session_id = ?',
        (session_id,)
    ).fetchone()
    db.close()
    
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


def save_analysis_deliverable(session_id, deliverable_type, file_path, file_name, metadata=None):
    """
    Save analysis deliverable record
    
    Args:
        session_id: Session ID
        deliverable_type: Type of deliverable
        file_path: Path to file
        file_name: Original filename
        metadata: Optional metadata dictionary
        
    Returns:
        Deliverable ID
    """
    import json
    from database import get_db
    
    db = get_db()
    cursor = db.execute('''
        INSERT INTO analysis_deliverables 
        (session_id, deliverable_type, file_path, file_name, metadata)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        session_id,
        deliverable_type,
        file_path,
        file_name,
        json.dumps(metadata) if metadata else None
    ))
    
    deliverable_id = cursor.lastrowid
    db.commit()
    db.close()
    
    return deliverable_id


def get_analysis_deliverables(session_id):
    """
    Get all deliverables for a session
    
    Args:
        session_id: Session ID
        
    Returns:
        List of deliverable dictionaries
    """
    import json
    from database import get_db
    
    db = get_db()
    rows = db.execute(
        'SELECT * FROM analysis_deliverables WHERE session_id = ? ORDER BY created_at',
        (session_id,)
    ).fetchall()
    db.close()
    
    deliverables = []
    for row in rows:
        deliverables.append({
            'id': row['id'],
            'session_id': row['session_id'],
            'deliverable_type': row['deliverable_type'],
            'file_path': row['file_path'],
            'file_name': row['file_name'],
            'metadata': json.loads(row['metadata']) if row['metadata'] else {},
            'created_at': row['created_at']
        })
    
    return deliverables


def update_analysis_progress(session_id, step_name, status, progress_pct=0, message=None):
    """
    Update analysis progress
    
    Args:
        session_id: Session ID
        step_name: Name of the step
        status: Status ('pending', 'running', 'complete', 'error')
        progress_pct: Progress percentage
        message: Optional message
        
    Returns:
        Progress ID
    """
    from database import get_db
    
    db = get_db()
    
    # Check if this step already exists
    existing = db.execute(
        'SELECT id FROM analysis_progress WHERE session_id = ? AND step_name = ?',
        (session_id, step_name)
    ).fetchone()
    
    if existing:
        # Update existing
        db.execute('''
            UPDATE analysis_progress
            SET status = ?, progress_pct = ?, message = ?,
                completed_at = CASE WHEN ? = 'complete' THEN CURRENT_TIMESTAMP ELSE completed_at END
            WHERE id = ?
        ''', (status, progress_pct, message, status, existing['id']))
        progress_id = existing['id']
    else:
        # Insert new
        cursor = db.execute('''
            INSERT INTO analysis_progress 
            (session_id, step_name, status, progress_pct, message, started_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (session_id, step_name, status, progress_pct, message))
        progress_id = cursor.lastrowid
    
    db.commit()
    db.close()
    
    return progress_id


def get_analysis_progress(session_id):
    """
    Get all progress records for a session
    
    Args:
        session_id: Session ID
        
    Returns:
        List of progress dictionaries
    """
    from database import get_db
    
    db = get_db()
    rows = db.execute(
        'SELECT * FROM analysis_progress WHERE session_id = ? ORDER BY created_at',
        (session_id,)
    ).fetchall()
    db.close()
    
    progress = []
    for row in rows:
        progress.append({
            'id': row['id'],
            'session_id': row['session_id'],
            'step_name': row['step_name'],
            'status': row['status'],
            'progress_pct': row['progress_pct'],
            'message': row['message'],
            'started_at': row['started_at'],
            'completed_at': row['completed_at'],
            'created_at': row['created_at']
        })
    
    return progress


# INSTRUCTIONS FOR INTEGRATION:
# 
# 1. Add to database.py init_db() function:
#    - Call init_analysis_tables(db) after existing table creation
#
# 2. Add these functions to database.py:
#    - save_analysis_session()
#    - load_analysis_session()
#    - save_analysis_deliverable()
#    - get_analysis_deliverables()
#    - update_analysis_progress()
#    - get_analysis_progress()
#
# 3. The tables will be created automatically on next app startup

# I did no harm and this file is not truncated
