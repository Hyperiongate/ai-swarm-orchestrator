"""
Database Migration: High Priority Learning Features
Created: February 4, 2026
Purpose: Add tables for Fixes #4, #5, and #6

- conversation_summaries (Fix #5: Multi-turn context)
- proactive_suggestions (Fix #4: Proactive recommendations)
- specialized_knowledge_cache (Fix #6: Industry expertise)

Author: Jim @ Shiftwork Solutions LLC
"""

import sqlite3
import os
from datetime import datetime


def run_high_priority_migration():
    """Add high priority learning enhancement tables"""
    
    db_path = os.environ.get('DATABASE_PATH', 'swarm_orchestrator.db')
    
    print(f"🔄 Running high priority migration on {db_path}...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # ========================================================================
    # TABLE 1: Conversation Summaries (Fix #5)
    # Compresses old conversations into key facts for context
    # ========================================================================
    print("📊 Creating conversation_summaries table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversation_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            summary_text TEXT NOT NULL,
            key_decisions TEXT,
            mentioned_entities TEXT,
            message_range TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_conv_summaries_conversation 
        ON conversation_summaries(conversation_id)
    ''')
    
    print("   ✅ conversation_summaries table ready")
    
    # ========================================================================
    # TABLE 2: Proactive Suggestions (Fix #4)
    # Stores suggestions made and tracks if user acted on them
    # ========================================================================
    print("📊 Creating proactive_suggestions table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proactive_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            task_id INTEGER,
            suggestion_type TEXT NOT NULL,
            suggestion_text TEXT NOT NULL,
            reasoning TEXT,
            user_action TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acted_on_at TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_proactive_suggestions_conversation 
        ON proactive_suggestions(conversation_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_proactive_suggestions_type 
        ON proactive_suggestions(suggestion_type)
    ''')
    
    print("   ✅ proactive_suggestions table ready")
    
    # ========================================================================
    # TABLE 3: Specialized Knowledge Cache (Fix #6)
    # Caches industry-specific knowledge for fast retrieval
    # ========================================================================
    print("📊 Creating specialized_knowledge_cache table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS specialized_knowledge_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_type TEXT NOT NULL,
            industry TEXT,
            topic TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT,
            relevance_score REAL DEFAULT 1.0,
            usage_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_specialized_knowledge_industry 
        ON specialized_knowledge_cache(industry)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_specialized_knowledge_topic 
        ON specialized_knowledge_cache(topic)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_specialized_knowledge_type 
        ON specialized_knowledge_cache(knowledge_type)
    ''')
    
    print("   ✅ specialized_knowledge_cache table ready")
    
    # ========================================================================
    # Verify tables were created
    # ========================================================================
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        AND name IN ('conversation_summaries', 'proactive_suggestions', 'specialized_knowledge_cache')
    """)
    
    tables = [row[0] for row in cursor.fetchall()]
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*70)
    print("✅ HIGH PRIORITY MIGRATION COMPLETE")
    print("="*70)
    print(f"Tables created: {', '.join(tables)}")
    print(f"Database: {db_path}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*70)
    
    return True


if __name__ == '__main__':
    try:
        run_high_priority_migration()
        print("\n🎉 Migration successful! Deploy your code changes now.")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()


# I did no harm and this file is not truncated
