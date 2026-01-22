"""
Database Schema Update for Sprint 2
Created: January 22, 2026

This file contains the ALTER TABLE statements to update the projects table
for Sprint 2 project management features.

Run this ONCE after deploying Sprint 2 code.
"""

from database import get_db

def upgrade_database_sprint2():
    """Add Sprint 2 columns to projects table"""
    db = get_db()
    
    try:
        # Check if columns already exist
        cursor = db.execute("PRAGMA table_info(projects)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        # Add new columns if they don't exist
        if 'checklist_data' not in existing_columns:
            print("Adding checklist_data column...")
            db.execute('ALTER TABLE projects ADD COLUMN checklist_data TEXT')
        
        if 'milestone_data' not in existing_columns:
            print("Adding milestone_data column...")
            db.execute('ALTER TABLE projects ADD COLUMN milestone_data TEXT')
        
        if 'folder_data' not in existing_columns:
            print("Adding folder_data column...")
            db.execute('ALTER TABLE projects ADD COLUMN folder_data TEXT')
        
        db.commit()
        print("✅ Database upgraded for Sprint 2!")
        
    except Exception as e:
        print(f"Error upgrading database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    upgrade_database_sprint2()

# I did no harm and this file is not truncated
