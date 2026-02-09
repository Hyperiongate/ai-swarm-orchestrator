"""
Add conversation_context table for Analysis Engine integration
Created: February 9, 2026
"""

import sqlite3

def add_conversation_context_table():
    """Add table for storing temporary conversation data"""
    db = sqlite3.connect('swarm_intelligence.db')
    db.row_factory = sqlite3.Row
    
    # Create table
    db.execute('''
        CREATE TABLE IF NOT EXISTS conversation_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(conversation_id, key)
        )
    ''')
    
    # Create index
    db.execute('''
        CREATE INDEX IF NOT EXISTS idx_conversation_context_lookup 
        ON conversation_context(conversation_id, key)
    ''')
    
    db.commit()
    db.close()
    print("✅ conversation_context table created")

if __name__ == '__main__':
    add_conversation_context_table()
