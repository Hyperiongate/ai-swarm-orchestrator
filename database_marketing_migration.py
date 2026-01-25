"""
DATABASE.PY UPDATE - Add Marketing Tables
Created: January 25, 2026
Last Updated: January 25, 2026

INSTRUCTIONS:
Add this code to your existing database.py file's init_db() function.
These tables enable the Autonomous Content Marketing Engine.

Find your init_db() function and add these table definitions AFTER your existing tables.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

# ===================================================================
# ADD THESE TABLES TO YOUR database.py init_db() FUNCTION
# ===================================================================

def add_marketing_tables_to_init_db():
    """
    Add these CREATE TABLE statements to your init_db() function in database.py
    Place them after your existing table definitions.
    """
    
    # Marketing Content table
    # Stores all generated marketing content (LinkedIn posts, newsletters)
    db.execute('''
        CREATE TABLE IF NOT EXISTS marketing_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            content_data TEXT NOT NULL,
            status TEXT DEFAULT 'pending_approval',
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            published_at TIMESTAMP,
            rejection_reason TEXT,
            source_task_id INTEGER,
            estimated_engagement TEXT,
            actual_engagement_score REAL,
            category TEXT,
            FOREIGN KEY (source_task_id) REFERENCES tasks (id)
        )
    ''')
    
    # Marketing Activity Log
    # Tracks all actions taken on marketing content
    db.execute('''
        CREATE TABLE IF NOT EXISTS marketing_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER,
            activity_type TEXT NOT NULL,
            activity_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES marketing_content (id)
        )
    ''')
    
    # Marketing Performance (for future use)
    # Tracks actual performance metrics after publishing
    db.execute('''
        CREATE TABLE IF NOT EXISTS marketing_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            engagement_rate REAL,
            measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES marketing_content (id)
        )
    ''')
    
    # Indexes for better performance
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_content_status ON marketing_content(status)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_content_type ON marketing_content(content_type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_content_generated ON marketing_content(generated_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_activity_content ON marketing_activity_log(content_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_activity_created ON marketing_activity_log(created_at)')


# ===================================================================
# EXAMPLE: HOW YOUR UPDATED init_db() SHOULD LOOK
# ===================================================================

"""
def init_db():
    '''Initialize database with all required tables'''
    db = get_db()
    
    # Your existing tables here...
    db.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request TEXT NOT NULL,
            ...
        )
    ''')
    
    # ... more existing tables ...
    
    # NEW MARKETING TABLES - Add these at the end
    db.execute('''
        CREATE TABLE IF NOT EXISTS marketing_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            content_data TEXT NOT NULL,
            status TEXT DEFAULT 'pending_approval',
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            published_at TIMESTAMP,
            rejection_reason TEXT,
            source_task_id INTEGER,
            estimated_engagement TEXT,
            actual_engagement_score REAL,
            category TEXT,
            FOREIGN KEY (source_task_id) REFERENCES tasks (id)
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS marketing_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER,
            activity_type TEXT NOT NULL,
            activity_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES marketing_content (id)
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS marketing_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            engagement_rate REAL,
            measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES marketing_content (id)
        )
    ''')
    
    # Indexes
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_content_status ON marketing_content(status)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_content_type ON marketing_content(content_type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_content_generated ON marketing_content(generated_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_activity_content ON marketing_activity_log(content_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_marketing_activity_created ON marketing_activity_log(created_at)')
    
    db.commit()
    db.close()
"""

# I did no harm and this file is not truncated
