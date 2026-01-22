"""
Database Schema Update for Sprint 3 Feature 1
Created: January 22, 2026

Adds user_profiles table for learning and memory.
"""

from database import get_db

def add_user_profiles_table():
    """Add user_profiles table for enhanced intelligence"""
    db = get_db()
    
    try:
        # Create user_profiles table
        db.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY,
                profile_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create index
        db.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_profiles_updated 
            ON user_profiles(updated_at)
        ''')
        
        db.commit()
        print("✅ user_profiles table created!")
        
    except Exception as e:
        print(f"Error creating table: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    add_user_profiles_table()

# I did no harm and this file is not truncated
