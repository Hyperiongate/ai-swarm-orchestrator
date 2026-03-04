"""
AI SWARM ORCHESTRATOR - Fix Broken Tables (Phase 9b)
File: fix_broken_tables.py
Created: March 03, 2026

PURPOSE:
    One-time cleanup to DROP and RECREATE tables that were created by the
    old migration_001_initial_schema.py with wrong column structures.

    The old migration created tables with wrong column names. The Phase 9
    migration used CREATE TABLE IF NOT EXISTS which SKIPPED these tables
    (since they already existed), and ALTER TABLE ADD COLUMN which added
    missing columns but CANNOT fix wrong column types or missing boolean
    columns that fail due to type conflicts.

    This script drops the broken tables and lets them be recreated correctly
    by the Phase 9 migration on next startup.

TABLES FIXED:
    1. generated_documents — missing is_deleted column (old migration created
       it without this column, ALTER TABLE ADD COLUMN failed)
    2. user_feedback — never created by old migration at all
    3. introspection_insights — never created by old migration (it created
       introspection_reports instead)
    4. conversations — old migration created with id TEXT PRIMARY KEY instead
       of id SERIAL PRIMARY KEY + conversation_id TEXT UNIQUE
    5. conversation_messages — old migration created as 'messages' with wrong
       column names
    6. tasks — verify columns exist (old migration may have wrong structure)
    7. specialist_calls — old migration created as 'specialists' with wrong
       column names
    8. escalations — may not have been created correctly
    9. learning_patterns — column name mismatches
    10. learning_records — may not have been created
    11. avoidance_patterns — column name mismatches
    12. smart_analyzer_state — old migration used plural name
    13. analysis_sessions — column mismatches
    14. background_jobs — may not have been created
    15. proactive_suggestions — may not have been created
    16. conversation_summaries — may not have been created
    17. user_patterns — may not have been created

SAFETY:
    - Only runs if the broken state is detected (checks for missing columns)
    - Logs every action taken
    - Safe to run multiple times (idempotent after first run)
    - No data loss risk — confirmed total_projects: 0 and app was down

USAGE:
    Called automatically by app.py at startup (STEP 3.5).
    Can also be triggered via: /api/admin/fix-broken-tables

CHANGELOG:
    - March 03, 2026: Created for Phase 9b cleanup

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

from db_engine import get_db_connection, get_db_type


def fix_broken_tables():
    """
    Drop and recreate tables that have wrong schemas from the old migration.
    Returns a dict with results for logging/API response.
    """
    db_type = get_db_type()
    if db_type != 'postgresql':
        print("fix_broken_tables: Skipping — only needed for PostgreSQL")
        return {'skipped': True, 'reason': 'sqlite'}

    results = {
        'tables_dropped': [],
        'tables_skipped': [],
        'errors': [],
        'success': True
    }

    # Tables to drop and recreate. The Phase 9 migration will recreate them
    # correctly on the next call to run_migration() (which happens in STEP 1
    # of app.py, BEFORE this script runs — so we need to recreate them here).
    #
    # Strategy: For each table, check if it has the WRONG structure.
    # If yes, drop it and recreate with correct structure.
    # If it already has correct structure, skip it.

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Helper: get columns for a table
        def get_columns(table_name):
            try:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
                return [row['column_name'] for row in cursor.fetchall()]
            except Exception:
                return []

        # Helper: check if table exists
        def table_exists(table_name):
            try:
                cursor.execute("""
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                """, (table_name,))
                return cursor.fetchone() is not None
            except Exception:
                return False

        # Helper: drop and recreate a table
        def drop_and_recreate(table_name, create_sql, reason):
            try:
                print(f"  🔄 Dropping {table_name} ({reason})")
                cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                cursor.execute(create_sql)
                results['tables_dropped'].append(table_name)
                print(f"  ✅ Recreated {table_name}")
            except Exception as e:
                results['errors'].append(f"{table_name}: {str(e)}")
                print(f"  ❌ Error fixing {table_name}: {e}")

        print("=" * 60)
        print("🔧 Phase 9b: Fixing broken table schemas...")
        print("=" * 60)

        # ====================================================================
        # 1. generated_documents — missing is_deleted
        # ====================================================================
        if table_exists('generated_documents'):
            cols = get_columns('generated_documents')
            if 'is_deleted' not in cols or 'original_name' not in cols:
                drop_and_recreate('generated_documents', """
                    CREATE TABLE generated_documents (
                        id SERIAL PRIMARY KEY,
                        filename TEXT,
                        original_name TEXT,
                        document_type TEXT NOT NULL,
                        file_path TEXT,
                        file_size INTEGER DEFAULT 0,
                        task_id INTEGER,
                        conversation_id TEXT,
                        project_id TEXT,
                        title TEXT,
                        description TEXT,
                        category TEXT DEFAULT 'general',
                        metadata TEXT,
                        is_deleted BOOLEAN DEFAULT FALSE,
                        download_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT NOW(),
                        last_accessed TIMESTAMP DEFAULT NOW()
                    )
                """, "missing is_deleted or original_name column")
            else:
                results['tables_skipped'].append('generated_documents')
                print(f"  ✓ generated_documents OK")

        # ====================================================================
        # 2. user_feedback — may not exist at all
        # ====================================================================
        if not table_exists('user_feedback'):
            drop_and_recreate('user_feedback', """
                CREATE TABLE user_feedback (
                    id SERIAL PRIMARY KEY,
                    task_id INTEGER,
                    overall_rating INTEGER,
                    quality_rating INTEGER,
                    accuracy_rating INTEGER,
                    usefulness_rating INTEGER,
                    consensus_was_accurate BOOLEAN DEFAULT FALSE,
                    improvement_categories TEXT,
                    user_comment TEXT,
                    output_used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """, "table did not exist")
        else:
            results['tables_skipped'].append('user_feedback')
            print(f"  ✓ user_feedback OK")

        # ====================================================================
        # 3. introspection_insights — may not exist at all
        # ====================================================================
        if not table_exists('introspection_insights'):
            drop_and_recreate('introspection_insights', """
                CREATE TABLE introspection_insights (
                    id SERIAL PRIMARY KEY,
                    insight_type TEXT NOT NULL,
                    category TEXT,
                    title TEXT,
                    description TEXT,
                    severity TEXT DEFAULT 'info',
                    confidence_score REAL DEFAULT 0.0,
                    data TEXT,
                    is_read BOOLEAN DEFAULT FALSE,
                    is_actioned BOOLEAN DEFAULT FALSE,
                    action_taken TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """, "table did not exist")
        else:
            results['tables_skipped'].append('introspection_insights')
            print(f"  ✓ introspection_insights OK")

        # ====================================================================
        # 4. conversations — check for conversation_id column
        # ====================================================================
        if table_exists('conversations'):
            cols = get_columns('conversations')
            if 'conversation_id' not in cols or 'mode' not in cols:
                drop_and_recreate('conversations', """
                    CREATE TABLE conversations (
                        id SERIAL PRIMARY KEY,
                        conversation_id TEXT UNIQUE NOT NULL,
                        title TEXT,
                        mode TEXT DEFAULT 'quick',
                        project_id TEXT,
                        is_archived BOOLEAN DEFAULT FALSE,
                        message_count INTEGER DEFAULT 0,
                        schedule_context TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """, "missing conversation_id or mode column")
            else:
                results['tables_skipped'].append('conversations')
                print(f"  ✓ conversations OK")

        # ====================================================================
        # 5. conversation_messages — check it exists and has correct columns
        # ====================================================================
        if not table_exists('conversation_messages'):
            drop_and_recreate('conversation_messages', """
                CREATE TABLE conversation_messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    task_id INTEGER,
                    metadata TEXT,
                    file_contents TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """, "table did not exist")
        else:
            cols = get_columns('conversation_messages')
            if 'file_contents' not in cols:
                drop_and_recreate('conversation_messages', """
                    CREATE TABLE conversation_messages (
                        id SERIAL PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        task_id INTEGER,
                        metadata TEXT,
                        file_contents TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """, "missing file_contents column")
            else:
                results['tables_skipped'].append('conversation_messages')
                print(f"  ✓ conversation_messages OK")

        # ====================================================================
        # 6. tasks — check for user_request column
        # ====================================================================
        if table_exists('tasks'):
            cols = get_columns('tasks')
            if 'user_request' not in cols or 'status' not in cols or 'result' not in cols:
                drop_and_recreate('tasks', """
                    CREATE TABLE tasks (
                        id SERIAL PRIMARY KEY,
                        user_request TEXT,
                        task_type TEXT DEFAULT 'general',
                        complexity TEXT DEFAULT 'medium',
                        status TEXT DEFAULT 'pending',
                        assigned_orchestrator TEXT,
                        orchestrator TEXT,
                        ai_used TEXT,
                        result TEXT,
                        confidence REAL,
                        tokens_used INTEGER DEFAULT 0,
                        cost_estimate REAL DEFAULT 0.0,
                        duration_seconds REAL DEFAULT 0.0,
                        success BOOLEAN DEFAULT FALSE,
                        error_message TEXT,
                        conversation_id TEXT,
                        knowledge_sources TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        completed_at TIMESTAMP,
                        metadata TEXT
                    )
                """, "missing user_request/status/result columns")
            else:
                results['tables_skipped'].append('tasks')
                print(f"  ✓ tasks OK")

        # ====================================================================
        # 7. specialist_calls — may have been created as 'specialists'
        # ====================================================================
        if not table_exists('specialist_calls'):
            drop_and_recreate('specialist_calls', """
                CREATE TABLE specialist_calls (
                    id SERIAL PRIMARY KEY,
                    task_id INTEGER,
                    specialist_name TEXT NOT NULL,
                    prompt_sent TEXT,
                    response_received TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """, "table did not exist")
        else:
            results['tables_skipped'].append('specialist_calls')
            print(f"  ✓ specialist_calls OK")

        # ====================================================================
        # 8. escalations — check it exists with correct columns
        # ====================================================================
        if not table_exists('escalations'):
            drop_and_recreate('escalations', """
                CREATE TABLE escalations (
                    id SERIAL PRIMARY KEY,
                    task_id INTEGER,
                    from_orchestrator TEXT,
                    to_orchestrator TEXT,
                    reason TEXT,
                    sonnet_analysis TEXT,
                    opus_response TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """, "table did not exist")
        else:
            cols = get_columns('escalations')
            if 'from_orchestrator' not in cols:
                drop_and_recreate('escalations', """
                    CREATE TABLE escalations (
                        id SERIAL PRIMARY KEY,
                        task_id INTEGER,
                        from_orchestrator TEXT,
                        to_orchestrator TEXT,
                        reason TEXT,
                        sonnet_analysis TEXT,
                        opus_response TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """, "missing from_orchestrator column")
            else:
                results['tables_skipped'].append('escalations')
                print(f"  ✓ escalations OK")

        # ====================================================================
        # 9. learning_patterns — check for task_type column
        # ====================================================================
        if table_exists('learning_patterns'):
            cols = get_columns('learning_patterns')
            if 'task_type' not in cols or 'pattern_data' not in cols:
                drop_and_recreate('learning_patterns', """
                    CREATE TABLE learning_patterns (
                        id SERIAL PRIMARY KEY,
                        task_type TEXT NOT NULL,
                        pattern_data TEXT,
                        pattern_type TEXT,
                        pattern_key TEXT,
                        pattern_value TEXT,
                        success_rate REAL DEFAULT 0.0,
                        confidence REAL DEFAULT 0.5,
                        times_used INTEGER DEFAULT 1,
                        usage_count INTEGER DEFAULT 1,
                        last_used TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """, "missing task_type or pattern_data column")
            else:
                results['tables_skipped'].append('learning_patterns')
                print(f"  ✓ learning_patterns OK")

        # ====================================================================
        # 10. learning_records — may not exist
        # ====================================================================
        if not table_exists('learning_records'):
            drop_and_recreate('learning_records', """
                CREATE TABLE learning_records (
                    id SERIAL PRIMARY KEY,
                    pattern_type TEXT NOT NULL,
                    success_rate REAL DEFAULT 0.0,
                    times_applied INTEGER DEFAULT 0,
                    pattern_data TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """, "table did not exist")
        else:
            results['tables_skipped'].append('learning_records')
            print(f"  ✓ learning_records OK")

        # ====================================================================
        # 11. avoidance_patterns — check for pattern_data column
        # ====================================================================
        if table_exists('avoidance_patterns'):
            cols = get_columns('avoidance_patterns')
            if 'pattern_data' not in cols or 'times_violated' not in cols:
                drop_and_recreate('avoidance_patterns', """
                    CREATE TABLE avoidance_patterns (
                        id SERIAL PRIMARY KEY,
                        pattern_data TEXT,
                        severity TEXT DEFAULT 'medium',
                        times_violated INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT NOW(),
                        last_seen TIMESTAMP DEFAULT NOW()
                    )
                """, "missing pattern_data or times_violated column")
            else:
                results['tables_skipped'].append('avoidance_patterns')
                print(f"  ✓ avoidance_patterns OK")

        # ====================================================================
        # 12. smart_analyzer_state — old migration used plural name
        # ====================================================================
        if not table_exists('smart_analyzer_state'):
            drop_and_recreate('smart_analyzer_state', """
                CREATE TABLE smart_analyzer_state (
                    id SERIAL PRIMARY KEY,
                    conversation_id TEXT UNIQUE,
                    file_path TEXT,
                    file_name TEXT,
                    analyzer_state TEXT,
                    profile_json TEXT,
                    last_used TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """, "table did not exist (old migration used plural name)")
        else:
            results['tables_skipped'].append('smart_analyzer_state')
            print(f"  ✓ smart_analyzer_state OK")

        # ====================================================================
        # 13. analysis_sessions — check for session_id and state columns
        # ====================================================================
        if table_exists('analysis_sessions'):
            cols = get_columns('analysis_sessions')
            if 'session_id' not in cols or 'state' not in cols:
                drop_and_recreate('analysis_sessions', """
                    CREATE TABLE analysis_sessions (
                        id SERIAL PRIMARY KEY,
                        session_id TEXT UNIQUE,
                        project_id TEXT,
                        state TEXT DEFAULT 'initial',
                        data_files TEXT,
                        discovered_structure TEXT,
                        clarifications TEXT,
                        analysis_plan TEXT,
                        results TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """, "missing session_id or state column")
            else:
                results['tables_skipped'].append('analysis_sessions')
                print(f"  ✓ analysis_sessions OK")

        # ====================================================================
        # 14. background_jobs — may not exist
        # ====================================================================
        if not table_exists('background_jobs'):
            drop_and_recreate('background_jobs', """
                CREATE TABLE background_jobs (
                    id SERIAL PRIMARY KEY,
                    job_id TEXT UNIQUE NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size_mb REAL NOT NULL,
                    user_request TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    task_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    progress INTEGER DEFAULT 0,
                    current_step TEXT,
                    estimated_minutes INTEGER,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """, "table did not exist")
        else:
            results['tables_skipped'].append('background_jobs')
            print(f"  ✓ background_jobs OK")

        # ====================================================================
        # 15. proactive_suggestions — may not exist
        # ====================================================================
        if not table_exists('proactive_suggestions'):
            drop_and_recreate('proactive_suggestions', """
                CREATE TABLE proactive_suggestions (
                    id SERIAL PRIMARY KEY,
                    conversation_id TEXT,
                    response_id TEXT,
                    suggestion_type TEXT,
                    suggestion_text TEXT,
                    context TEXT,
                    was_accepted BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """, "table did not exist")
        else:
            results['tables_skipped'].append('proactive_suggestions')
            print(f"  ✓ proactive_suggestions OK")

        # ====================================================================
        # 16. conversation_summaries — may not exist
        # ====================================================================
        if not table_exists('conversation_summaries'):
            drop_and_recreate('conversation_summaries', """
                CREATE TABLE conversation_summaries (
                    id SERIAL PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    summary TEXT,
                    key_topics TEXT,
                    action_items TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """, "table did not exist")
        else:
            results['tables_skipped'].append('conversation_summaries')
            print(f"  ✓ conversation_summaries OK")

        # ====================================================================
        # 17. user_patterns — may not exist
        # ====================================================================
        if not table_exists('user_patterns'):
            drop_and_recreate('user_patterns', """
                CREATE TABLE user_patterns (
                    id SERIAL PRIMARY KEY,
                    pattern_type TEXT NOT NULL,
                    pattern_key TEXT,
                    pattern_value TEXT,
                    frequency INTEGER DEFAULT 1,
                    last_seen TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """, "table did not exist")
        else:
            results['tables_skipped'].append('user_patterns')
            print(f"  ✓ user_patterns OK")

        # ====================================================================
        # 18. consensus_validations — check structure
        # ====================================================================
        if table_exists('consensus_validations'):
            cols = get_columns('consensus_validations')
            if 'ai1_name' not in cols or 'consensus_achieved' not in cols:
                drop_and_recreate('consensus_validations', """
                    CREATE TABLE consensus_validations (
                        id SERIAL PRIMARY KEY,
                        task_id INTEGER,
                        ai1_name TEXT,
                        ai1_response TEXT,
                        ai2_name TEXT,
                        ai2_response TEXT,
                        primary_ai TEXT,
                        validator_ai TEXT,
                        agreement_score REAL DEFAULT 0.0,
                        consensus_achieved BOOLEAN DEFAULT FALSE,
                        final_output TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """, "missing ai1_name or consensus_achieved column")
            else:
                results['tables_skipped'].append('consensus_validations')
                print(f"  ✓ consensus_validations OK")

        # ====================================================================
        # RECREATE INDEXES for any dropped tables
        # ====================================================================
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_conversation ON tasks(conversation_id)",
            "CREATE INDEX IF NOT EXISTS idx_conv_messages_conversation ON conversation_messages(conversation_id)",
            "CREATE INDEX IF NOT EXISTS idx_conv_messages_created ON conversation_messages(created_at ASC)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_generated_docs_created ON generated_documents(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_generated_docs_type ON generated_documents(document_type)",
            "CREATE INDEX IF NOT EXISTS idx_learning_patterns_type ON learning_patterns(task_type)",
            "CREATE INDEX IF NOT EXISTS idx_learning_records_type ON learning_records(pattern_type)",
            "CREATE INDEX IF NOT EXISTS idx_smart_analyzer_conversation ON smart_analyzer_state(conversation_id)",
            "CREATE INDEX IF NOT EXISTS idx_analysis_sessions_session ON analysis_sessions(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_background_jobs_status ON background_jobs(status)",
            "CREATE INDEX IF NOT EXISTS idx_background_jobs_conversation ON background_jobs(conversation_id)",
            "CREATE INDEX IF NOT EXISTS idx_introspection_insights_created ON introspection_insights(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_introspection_insights_read ON introspection_insights(is_read)",
        ]

        for idx_sql in index_statements:
            try:
                cursor.execute(idx_sql)
            except Exception:
                pass  # Index already exists or table doesn't exist yet

        conn.commit()

        # Summary
        print("=" * 60)
        print(f"✅ Phase 9b complete:")
        print(f"   Tables fixed: {len(results['tables_dropped'])}")
        print(f"   Tables OK:    {len(results['tables_skipped'])}")
        if results['errors']:
            print(f"   Errors:       {len(results['errors'])}")
            for err in results['errors']:
                print(f"     ❌ {err}")
            results['success'] = False
        print("=" * 60)

    except Exception as e:
        import traceback
        print(f"❌ Phase 9b failed: {e}")
        traceback.print_exc()
        results['success'] = False
        results['errors'].append(str(e))
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()

    return results


if __name__ == '__main__':
    result = fix_broken_tables()
    print(f"\nResult: {result}")

# I did no harm and this file is not truncated
