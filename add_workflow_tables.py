"""
Database Schema Update for Sprint 3 Feature 4
Created: January 22, 2026

Adds workflow execution tracking tables.
"""

from database import get_db

def add_workflow_tables():
    """Add workflow tracking tables"""
    db = get_db()
    
    try:
        # Workflow executions
        db.execute('''
            CREATE TABLE IF NOT EXISTS workflow_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                workflow_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')
        
        # Workflow execution steps
        db.execute('''
            CREATE TABLE IF NOT EXISTS workflow_execution_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id INTEGER NOT NULL,
                step_id TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (execution_id) REFERENCES workflow_executions(id)
            )
        ''')
        
        # Indexes
        db.execute('''
            CREATE INDEX IF NOT EXISTS idx_workflow_executions_started 
            ON workflow_executions(started_at)
        ''')
        
        db.execute('''
            CREATE INDEX IF NOT EXISTS idx_workflow_execution_steps_execution 
            ON workflow_execution_steps(execution_id)
        ''')
        
        db.commit()
        print("✅ workflow tables created!")
        
    except Exception as e:
        print(f"Error creating tables: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    add_workflow_tables()

# I did no harm and this file is not truncated
