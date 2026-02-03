"""
DATABASE MIGRATION - Add supporting_documents column
Created: February 3, 2026

Run this to fix the learned_patterns table error.
"""

import sqlite3

def migrate_learned_patterns():
    """Add supporting_documents column if missing"""
    db = sqlite3.connect('swarm_intelligence.db')
    cursor = db.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(learned_patterns)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'supporting_documents' not in columns:
            print("Adding supporting_documents column...")
            cursor.execute('''
                ALTER TABLE learned_patterns 
                ADD COLUMN supporting_documents INTEGER DEFAULT 1
            ''')
            db.commit()
            print("✅ Migration complete!")
        else:
            print("✅ Column already exists - no migration needed")
    
    except sqlite3.OperationalError as e:
        if 'no such table' in str(e):
            print("ℹ️  Table doesn't exist yet - will be created on first use")
        else:
            print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == '__main__':
    migrate_learned_patterns()
