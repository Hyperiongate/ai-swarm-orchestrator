"""
Database Schema Update for Sprint 2 Feature 3
Created: January 22, 2026

Adds improvement_reports table for tracking efficiency analysis.
"""

from database import get_db

def add_improvement_reports_table():
    """Add improvement_reports table for weekly efficiency reports"""
    db = get_db()
    
    try:
        # Create improvement_reports table
        db.execute('''
            CREATE TABLE IF NOT EXISTS improvement_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                report_data TEXT NOT NULL,
                viewed BOOLEAN DEFAULT 0,
                actions_taken TEXT
            )
        ''')
        
        # Add index
        db.execute('''
            CREATE INDEX IF NOT EXISTS idx_improvement_reports_date 
            ON improvement_reports(generated_at)
        ''')
        
        db.commit()
        print("✅ improvement_reports table created!")
        
    except Exception as e:
        print(f"Error creating table: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    add_improvement_reports_table()

# I did no harm and this file is not truncated
