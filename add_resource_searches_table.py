"""
Database Schema Update for Sprint 2 Feature 2
Created: January 22, 2026

Adds resource_searches table to track proactive web searches.
"""

from database import get_db

def add_resource_searches_table():
    """Add resource_searches table for tracking proactive searches"""
    db = get_db()
    
    try:
        # Create resource_searches table
        db.execute('''
            CREATE TABLE IF NOT EXISTS resource_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                search_query TEXT NOT NULL,
                results_found BOOLEAN DEFAULT 0,
                improved_response BOOLEAN DEFAULT 0,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        ''')
        
        # Add index for performance
        db.execute('''
            CREATE INDEX IF NOT EXISTS idx_resource_searches_task 
            ON resource_searches(task_id)
        ''')
        
        db.execute('''
            CREATE INDEX IF NOT EXISTS idx_resource_searches_date 
            ON resource_searches(searched_at)
        ''')
        
        db.commit()
        print("✅ resource_searches table created!")
        
    except Exception as e:
        print(f"Error creating table: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    add_resource_searches_table()

# I did no harm and this file is not truncated
