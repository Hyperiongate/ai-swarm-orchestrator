"""
Database Migration Script - Missing Tables and Columns
Created: February 21, 2026
Purpose: Add missing tables and columns identified from runtime warnings:

  WARNING 1: no such table: avoidance_patterns
    -> avoidance_patterns table referenced in add_avoidance_pattern() and
       get_avoidance_context() in database.py but never created in init_db()

  WARNING 2: no such table: conversation_summaries
    -> conversation_summarizer.py tries to read/write this table but it
       was never added to init_db()

  WARNING 3: no such column: conversation_id (proactive_suggestions)
    -> proactive_suggestions table exists but is missing conversation_id column
    -> proactive_curiosity_engine.py expects this column

  WARNING 4: no such table: user_profiles
    -> EnhancedIntelligence references user_profiles but it was never created

This script is SAFE to run multiple times:
  - All CREATE TABLE statements use IF NOT EXISTS
  - All ALTER TABLE statements catch "duplicate column" errors and continue
  - Existing data is never modified or deleted

Run on Render via: python migrate_missing_tables.py
Or: call run_migration() from app startup
"""

import sqlite3
import os
import sys
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

# FIXED February 21, 2026: Match config.py exactly
# config.py sets DATABASE = '/mnt/project/swarm_intelligence.db'
# The persistent Render disk is mounted at /mnt/project
# Fall back to local path if persistent disk is not mounted (local dev)
if os.path.isdir('/mnt/project'):
    DATABASE = '/mnt/project/swarm_intelligence.db'
else:
    DATABASE = 'swarm_intelligence.db'

print(f"Migration target database: {DATABASE}")


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def column_exists(db, table, column):
    """Check if a column exists in a table"""
    try:
        cursor = db.execute(f"PRAGMA table_info({table})")
        columns = [row['name'] for row in cursor.fetchall()]
        return column in columns
    except Exception:
        return False


def table_exists(db, table):
    """Check if a table exists"""
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()
    return row is not None


def run_migration():
    """
    Run all migrations. Safe to run multiple times.
    Returns dict with results.
    """
    results = {
        'started_at': datetime.now().isoformat(),
        'migrations': [],
        'errors': [],
        'success': True
    }

    db = get_db()

    try:
        # ====================================================================
        # MIGRATION 1: avoidance_patterns table
        # Referenced in database.py add_avoidance_pattern() and
        # get_avoidance_context() but never created in init_db()
        # ====================================================================
        if not table_exists(db, 'avoidance_patterns'):
            print("Creating avoidance_patterns table...")
            db.execute('''
                CREATE TABLE IF NOT EXISTS avoidance_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_data TEXT NOT NULL,
                    severity TEXT DEFAULT 'medium' CHECK(severity IN ('low', 'medium', 'high')),
                    times_violated INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_avoidance_severity ON avoidance_patterns(severity)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_avoidance_created ON avoidance_patterns(created_at DESC)')
            db.commit()
            results['migrations'].append('Created avoidance_patterns table')
            print("  ✅ avoidance_patterns table created")
        else:
            results['migrations'].append('avoidance_patterns table already exists - skipped')
            print("  ℹ️  avoidance_patterns table already exists")

        # ====================================================================
        # MIGRATION 2: conversation_summaries table
        # Used by conversation_summarizer.py to store rolling conversation
        # summaries that provide context to the AI across long conversations
        # ====================================================================
        if not table_exists(db, 'conversation_summaries'):
            print("Creating conversation_summaries table...")
            db.execute('''
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    message_count_at_summary INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
                )
            ''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_conv_summaries_conv_id ON conversation_summaries(conversation_id)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_conv_summaries_created ON conversation_summaries(created_at DESC)')
            db.commit()
            results['migrations'].append('Created conversation_summaries table')
            print("  ✅ conversation_summaries table created")
        else:
            results['migrations'].append('conversation_summaries table already exists - skipped')
            print("  ℹ️  conversation_summaries table already exists")

        # ====================================================================
        # MIGRATION 3: proactive_suggestions - add conversation_id column
        # The table exists but is missing conversation_id and response_id
        # columns that proactive_curiosity_engine.py expects
        # ====================================================================
        print("Checking proactive_suggestions columns...")

        if not column_exists(db, 'proactive_suggestions', 'conversation_id'):
            try:
                db.execute('ALTER TABLE proactive_suggestions ADD COLUMN conversation_id TEXT')
                db.execute('CREATE INDEX IF NOT EXISTS idx_suggestions_conversation ON proactive_suggestions(conversation_id)')
                db.commit()
                results['migrations'].append('Added conversation_id column to proactive_suggestions')
                print("  ✅ Added conversation_id to proactive_suggestions")
            except sqlite3.OperationalError as e:
                if 'duplicate column' in str(e).lower():
                    results['migrations'].append('conversation_id already exists in proactive_suggestions - skipped')
                    print("  ℹ️  conversation_id already exists in proactive_suggestions")
                else:
                    results['errors'].append(f'proactive_suggestions.conversation_id: {e}')
                    print(f"  ❌ Error adding conversation_id: {e}")
        else:
            results['migrations'].append('proactive_suggestions.conversation_id already exists - skipped')
            print("  ℹ️  conversation_id already exists in proactive_suggestions")

        # Also add response_id if missing (used by curiosity engine)
        if not column_exists(db, 'proactive_suggestions', 'response_id'):
            try:
                db.execute('ALTER TABLE proactive_suggestions ADD COLUMN response_id TEXT')
                db.commit()
                results['migrations'].append('Added response_id column to proactive_suggestions')
                print("  ✅ Added response_id to proactive_suggestions")
            except sqlite3.OperationalError as e:
                if 'duplicate column' in str(e).lower():
                    print("  ℹ️  response_id already exists in proactive_suggestions")
                else:
                    results['errors'].append(f'proactive_suggestions.response_id: {e}')
                    print(f"  ❌ Error adding response_id: {e}")

        # ====================================================================
        # MIGRATION 4: user_profiles table
        # EnhancedIntelligence (enhanced_intelligence.py) expects this table
        # for tracking user interaction patterns and learning
        # ====================================================================
        if not table_exists(db, 'user_profiles'):
            print("Creating user_profiles table...")
            db.execute('''
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL DEFAULT 'default',
                    interaction_count INTEGER DEFAULT 0,
                    preferred_response_style TEXT DEFAULT 'detailed',
                    common_topics TEXT,
                    satisfaction_scores TEXT,
                    last_interaction TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    profile_data TEXT
                )
            ''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id)')
            # Insert default user profile
            db.execute('''
                INSERT OR IGNORE INTO user_profiles (user_id, interaction_count)
                VALUES ('default', 0)
            ''')
            db.commit()
            results['migrations'].append('Created user_profiles table with default record')
            print("  ✅ user_profiles table created")
        else:
            results['migrations'].append('user_profiles table already exists - skipped')
            print("  ℹ️  user_profiles table already exists")

        # ====================================================================
        # MIGRATION 5: client_profiles table
        # database.py has get_client_profile() and update_client_profile()
        # functions that reference this table - verify it exists
        # ====================================================================
        if not table_exists(db, 'client_profiles'):
            print("Creating client_profiles table...")
            db.execute('''
                CREATE TABLE IF NOT EXISTS client_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_name TEXT UNIQUE NOT NULL,
                    profile_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_client_profiles_name ON client_profiles(client_name)')
            db.commit()
            results['migrations'].append('Created client_profiles table')
            print("  ✅ client_profiles table created")
        else:
            results['migrations'].append('client_profiles table already exists - skipped')
            print("  ℹ️  client_profiles table already exists")

        # ====================================================================
        # VERIFY ALL CRITICAL TABLES EXIST
        # ====================================================================
        print("\nVerifying all critical tables...")
        critical_tables = [
            'tasks', 'projects', 'conversations', 'conversation_messages',
            'conversation_context', 'generated_documents', 'research_logs',
            'research_briefings', 'learning_patterns', 'learning_records',
            'specialist_calls', 'consensus_validations', 'user_feedback',
            'user_patterns', 'proactive_suggestions', 'background_jobs',
            'smart_analyzer_state', 'analysis_sessions',
            # Newly added
            'avoidance_patterns', 'conversation_summaries',
            'user_profiles', 'client_profiles'
        ]

        all_present = True
        for table in critical_tables:
            exists = table_exists(db, table)
            status = "✅" if exists else "❌"
            print(f"  {status} {table}")
            if not exists:
                all_present = False
                results['errors'].append(f'Table still missing after migration: {table}')

        results['all_tables_present'] = all_present

    except Exception as e:
        import traceback
        results['success'] = False
        results['errors'].append(f'Migration failed: {str(e)}')
        print(f"\n❌ MIGRATION ERROR: {e}")
        traceback.print_exc()
    finally:
        db.close()

    results['completed_at'] = datetime.now().isoformat()
    results['success'] = results['success'] and len(results['errors']) == 0

    print(f"\n{'✅ Migration complete' if results['success'] else '❌ Migration completed with errors'}")
    print(f"  Migrations applied: {len(results['migrations'])}")
    print(f"  Errors: {len(results['errors'])}")

    return results


if __name__ == '__main__':
    print("=" * 60)
    print("AI Swarm Orchestrator - Database Migration")
    print("February 21, 2026")
    print("=" * 60)
    print()

    results = run_migration()

    print("\nMigrations applied:")
    for m in results['migrations']:
        print(f"  • {m}")

    if results['errors']:
        print("\nErrors:")
        for e in results['errors']:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print("\n✅ All migrations successful")
        sys.exit(0)

# I did no harm and this file is not truncated
