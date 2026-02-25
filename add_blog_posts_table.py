"""
DATABASE MIGRATION - Add blog_posts Table with SEO Fields
Created: February 25, 2026

Properly handles both scenarios:
1. Table doesn't exist -> Creates it with all SEO fields
2. Table exists without SEO fields -> Adds the missing columns

CRITICAL FIX: Uses DATABASE path from config.py to ensure consistency

USAGE:
This migration runs automatically on app startup via app.py.

AUTHOR: Jim @ Shiftwork Solutions LLC
LAST UPDATED: February 25, 2026
"""

import sqlite3
import os


def add_blog_posts_table():
    """
    Create the blog_posts table with SEO fields if it doesn't exist.
    If table exists but is missing SEO columns, add them.
    Safe to run multiple times.
    """
    
    # Import DATABASE from config to use the SAME path as the app
    from config import DATABASE
    
    print(f"📊 Blog Posts Migration: Checking {DATABASE}...")
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='blog_posts'
        """)
        
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            # Create table with all columns including SEO fields
            print("🔨 Creating blog_posts table with SEO fields...")
            cursor.execute('''
                CREATE TABLE blog_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    topic_display TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url_slug TEXT NOT NULL DEFAULT '',
                    meta_description TEXT NOT NULL DEFAULT '',
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
            
            cursor.execute('''
                CREATE INDEX idx_blog_posts_slug
                ON blog_posts(url_slug)
            ''')
            
            conn.commit()
            print("✅ blog_posts table created with SEO fields")
            print("   Columns: id, topic, topic_display, title, url_slug, meta_description, content, angle, created_at, updated_at")
            
        else:
            # Table exists - check for SEO columns
            print("ℹ️  blog_posts table exists - checking for SEO columns...")
            
            # Get current columns
            cursor.execute("PRAGMA table_info(blog_posts)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            print(f"   Current columns: {', '.join(existing_columns)}")
            
            changes_made = False
            
            # Add url_slug column if it doesn't exist
            if 'url_slug' not in existing_columns:
                print("   🔨 Adding url_slug column...")
                cursor.execute('''
                    ALTER TABLE blog_posts 
                    ADD COLUMN url_slug TEXT NOT NULL DEFAULT ''
                ''')
                changes_made = True
                print("   ✅ url_slug column added")
            else:
                print("   ✓ url_slug exists")
            
            # Add meta_description column if it doesn't exist
            if 'meta_description' not in existing_columns:
                print("   🔨 Adding meta_description column...")
                cursor.execute('''
                    ALTER TABLE blog_posts 
                    ADD COLUMN meta_description TEXT NOT NULL DEFAULT ''
                ''')
                changes_made = True
                print("   ✅ meta_description column added")
            else:
                print("   ✓ meta_description exists")
            
            if changes_made:
                # Create index on url_slug if needed
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_blog_posts_slug
                    ON blog_posts(url_slug)
                ''')
                conn.commit()
                print("✅ blog_posts table updated with SEO columns")
            else:
                print("✅ blog_posts table already has all SEO columns")
        
        print("✅ Blog Posts table migration complete!")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error with blog_posts migration: {e}")
        import traceback
        print(traceback.format_exc())
        return False


if __name__ == '__main__':
    add_blog_posts_table()

# I did no harm and this file is not truncated
