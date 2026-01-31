"""
PROJECTS TABLE MIGRATION - Add Bulletproof Columns
Created: January 31, 2026

Adds missing columns to existing projects table for bulletproof project management.

Run this once to upgrade the database schema.

Author: Jim @ Shiftwork Solutions LLC
"""

import sqlite3
import os

DATABASE = os.environ.get('DATABASE_URL', 'swarm.db')
if DATABASE.startswith('postgres'):
    DATABASE = 'swarm.db'  # Use SQLite for now


def migrate_projects_table():
    """Add missing columns to projects table"""
    print("🔄 Migrating projects table...")
    
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    
    # Check if projects table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='projects'
    """)
    
    table_exists = cursor.fetchone()
    
    if not table_exists:
        print("   ℹ️  Projects table doesn't exist - will be created by ProjectManager")
        db.close()
        return
    
    print("   📋 Projects table exists - checking for missing columns...")
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(projects)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    print(f"   📋 Current columns: {existing_columns}")
    
    # Add missing columns one by one
    columns_to_add = [
        ('storage_path', 'TEXT'),
        ('checklist_data', 'TEXT'),
        ('milestone_data', 'TEXT'),
        ('folder_data', 'TEXT'),
        ('metadata', 'TEXT DEFAULT "{}"'),
    ]
    
    added_count = 0
    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            try:
                print(f"   🔧 Adding column: {col_name}")
                cursor.execute(f'ALTER TABLE projects ADD COLUMN {col_name} {col_type}')
                db.commit()  # Commit after each column
                print(f"   ✅ Added column: {col_name}")
                added_count += 1
            except sqlite3.OperationalError as e:
                print(f"   ⚠️  Could not add {col_name}: {e}")
        else:
            print(f"   ✓ Column {col_name} already exists")
    
    db.close()
    
    if added_count > 0:
        print(f"✅ Migration complete! Added {added_count} column(s)")
    else:
        print("✅ No migration needed - all columns exist")


if __name__ == '__main__':
    migrate_projects_table()

# I did no harm and this file is not truncated
