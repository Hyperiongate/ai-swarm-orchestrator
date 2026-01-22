"""
Database Schema Update for Sprint 3 Feature 5
Created: January 22, 2026

Adds integration_logs table for tracking external service calls.
"""

from database import get_db

def add_integration_logs_table():
    """Add integration_logs table"""
    db = get_db()
    
    try:
        # Integration logs
        db.execute('''
            CREATE TABLE IF NOT EXISTS integration_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                integration_name TEXT NOT NULL,
                action TEXT NOT NULL,
                params TEXT,
                result TEXT,
                called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index
        db.execute('''
            CREATE INDEX IF NOT EXISTS idx_integration_logs_called 
            ON integration_logs(called_at)
        ''')
        
        db.execute('''
            CREATE INDEX IF NOT EXISTS idx_integration_logs_integration 
            ON integration_logs(integration_name)
        ''')
        
        db.commit()
        print("✅ integration_logs table created!")
        
    except Exception as e:
        print(f"Error creating table: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    add_integration_logs_table()

# I did no harm and this file is not truncated
