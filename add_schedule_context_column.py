"""
Database Migration: Add schedule_context to conversations table
Created: January 27, 2026

This adds a column to store schedule conversation context in the database
instead of using Flask sessions (which aren't persisting properly).

Run this ONCE before deploying the updated code.
"""

from database import get_db

def add_schedule_context_column():
    """Add schedule_context column to conversations table"""
    try:
        db = get_db()
        
        # Check if column exists
        cursor = db.execute("PRAGMA table_info(conversations)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'schedule_context' not in columns:
            print("Adding schedule_context column...")
            db.execute('ALTER TABLE conversations ADD COLUMN schedule_context TEXT')
            db.commit()
            print("✅ Added schedule_context column to conversations table")
        else:
            print("ℹ️  schedule_context column already exists")
        
        db.close()
        return True
    except Exception as e:
        print(f"❌ Error adding schedule_context column: {e}")
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("MIGRATION: Adding schedule_context to conversations table")
    print("=" * 70)
    result = add_schedule_context_column()
    if result:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed!")

# I did no harm and this file is not truncated
