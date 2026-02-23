"""
DATABASE MIGRATION - Add blog_posts Table
Created: February 23, 2026

Adds the blog_posts table for the Blog Post Generator feature.

USAGE:
This migration runs automatically on app startup via app.py.
Can also be run manually: python add_blog_posts_table.py

AUTHOR: Jim @ Shiftwork Solutions LLC
LAST UPDATED: February 23, 2026
"""

import sqlite3
import os


def add_blog_posts_table():
    """
    Create the blog_posts table if it doesn't exist.
    Safe to run multiple times - only creates if missing.
    """
    
    # Determine database path
    db_path = os.environ.get('DATABASE_PATH', 'swarm_intelligence.db')
    
    print(f"📊 Checking blog_posts table in {db_path}...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='blog_posts'
        """)
        
        if cursor.fetchone():
            print("✅ blog_posts table already exists")
            conn.close()
            return True
        
        # Create table
        print("🔨 Creating blog_posts table...")
        cursor.execute('''
            CREATE TABLE blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                topic_display TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                angle TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX idx_blog_posts_topic
            ON blog_posts(topic)
        ''')
        
        cursor.execute('''
            CREATE INDEX idx_blog_posts_created
            ON blog_posts(created_at DESC)
        ''')
        
        conn.commit()
        print("✅ blog_posts table created successfully!")
        print("   - Columns: id, topic, topic_display, title, content, angle, created_at, updated_at")
        print("   - Indexes: topic, created_at")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating blog_posts table: {e}")
        import traceback
        print(traceback.format_exc())
        return False


if __name__ == '__main__':
    add_blog_posts_table()

# I did no harm and this file is not truncated
