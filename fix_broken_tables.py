"""
AI SWARM ORCHESTRATOR - Fix Broken Tables (Phase 9b + 9c + 9d)
File: fix_broken_tables.py
Created: March 03, 2026
Last Updated: March 05, 2026 - Phase 9d: Added missing project_files columns

PURPOSE:
    One-time cleanup to DROP and RECREATE tables that were created by the
    old migration_001_initial_schema.py with wrong column structures.

    Phase 9b: Drops and recreates tables with wrong column names.
    Phase 9c: Fixes missing SERIAL sequences on id columns for tables
              that were created by legacy code before migration_001 ran.
              This fixes: "null value in column id violates not-null constraint"
    Phase 9d: Adds missing columns to project_files that were not included
              in the original bool_columns_needed list. This fixes:
              "column uploaded_at does not exist" on list/upload operations.

CHANGELOG:
    - March 05, 2026: Phase 9d — Added missing project_files columns
      * uploaded_at, original_filename, file_type, file_size, file_path,
        content_text, content_summary, file_id, mime_type were missing
        from the bool_columns_needed list causing persistent 500 errors
        on GET /projects/<id>/files and POST /projects/<id>/files
    - March 04, 2026: Phase 9c — SERIAL sequence fix
    - March 03, 2026: Phase 9b — Created for broken table schema cleanup

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

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

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

        def table_exists(table_name):
            try:
                cursor.execute("""
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                """, (table_name,))
                return cursor.fetchone() is not None
            except Exception:
                return False

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
        # 1. generated_documents
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
        # 2. user_feedback
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
        # 3. introspection_insights
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
        # 4. conversations
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
        # 5. conversation_messages
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
        # 6. tasks
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
        # 7. specialist_calls
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
        # 8. escalations
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
        # 9. learning_patterns
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
        # 10. learning_records
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
        # 11. avoidance_patterns
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
        # 12. smart_analyzer_state
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
        # 13. analysis_sessions
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
        # 14. background_jobs
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
        # 15. proactive_suggestions
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
        # 16. conversation_summaries
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
        # 17. user_patterns
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
        # 18. consensus_validations
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
                pass

        conn.commit()

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

        # ====================================================================
        # PHASE 9c: Fix missing SERIAL sequences on id columns
        # ====================================================================

        if db_type == 'postgresql':
            print()
            print("=" * 60)
            print("🔧 Phase 9c: Fixing missing SERIAL sequences...")
            print("=" * 60)

            serial_tables = [
                'tasks', 'specialist_calls', 'consensus_validations',
                'escalations', 'learning_patterns', 'learning_records',
                'user_feedback', 'conversations', 'conversation_messages',
                'conversation_context', 'generated_documents', 'projects',
                'project_files', 'project_conversations', 'project_context',
                'client_profiles', 'avoidance_patterns', 'smart_analyzer_state',
                'analysis_sessions', 'analysis_deliverables', 'analysis_progress',
                'research_sessions', 'resource_searches', 'marketing_campaigns',
                'content_pieces', 'improvement_reports', 'avatar_sessions',
                'swarm_evaluations', 'introspection_reports',
                'introspection_insights', 'surveys', 'survey_responses',
                'blog_posts', 'case_studies', 'user_profiles', 'workflows',
                'workflow_executions', 'integration_logs', 'memory_store',
                'routing_preferences', 'alerts', 'scheduled_jobs',
                'job_executions', 'alert_subscriptions', 'monitored_entities',
                'leads', 'lead_activities', 'lead_documents',
                'industry_benchmarks', 'background_jobs',
                'conversation_summaries', 'proactive_suggestions',
                'user_patterns', 'modification_proposals', 'goal_alignment_logs',
            ]

            sequences_fixed = 0
            sequences_ok = 0
            sequences_errors = 0

            for table_name in serial_tables:
                try:
                    cursor.execute(f"SAVEPOINT sp_{table_name}")

                    cursor.execute("""
                        SELECT column_default, data_type
                        FROM information_schema.columns
                        WHERE table_name = %s
                          AND column_name = 'id'
                          AND table_schema = 'public'
                    """, (table_name,))
                    row = cursor.fetchone()

                    if row is None:
                        cursor.execute(f"RELEASE SAVEPOINT sp_{table_name}")
                        continue

                    col_default = row['column_default'] if row else None
                    data_type = row['data_type'] if row else None

                    if col_default and 'nextval' in str(col_default):
                        sequences_ok += 1
                        cursor.execute(f"RELEASE SAVEPOINT sp_{table_name}")
                        continue

                    if data_type and data_type.lower() in ('text', 'character varying'):
                        cursor.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
                        row_count = cursor.fetchone()['cnt']

                        if row_count == 0:
                            cursor.execute(
                                f"ALTER TABLE {table_name} "
                                f"ALTER COLUMN id TYPE INTEGER USING 0"
                            )
                            print(f"  🔄 {table_name}.id: converted TEXT → INTEGER (empty table)")
                        else:
                            try:
                                cursor.execute(
                                    f"ALTER TABLE {table_name} "
                                    f"ALTER COLUMN id TYPE INTEGER USING id::INTEGER"
                                )
                                print(f"  🔄 {table_name}.id: converted TEXT → INTEGER ({row_count} rows)")
                            except Exception as cast_err:
                                print(f"  ⚠️  {table_name}.id: cannot convert TEXT→INTEGER ({cast_err})")
                                cursor.execute(f"ROLLBACK TO SAVEPOINT sp_{table_name}")
                                sequences_errors += 1
                                continue

                    seq_name = f"{table_name}_id_seq"
                    cursor.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}")
                    cursor.execute(
                        f"ALTER TABLE {table_name} "
                        f"ALTER COLUMN id SET DEFAULT nextval('{seq_name}')"
                    )
                    cursor.execute(
                        f"SELECT setval('{seq_name}', "
                        f"COALESCE((SELECT MAX(id) FROM {table_name}), 0) + 1, false)"
                    )
                    cursor.execute(
                        f"ALTER TABLE {table_name} ALTER COLUMN id SET NOT NULL"
                    )
                    cursor.execute(
                        f"ALTER SEQUENCE {seq_name} OWNED BY {table_name}.id"
                    )

                    cursor.execute(f"RELEASE SAVEPOINT sp_{table_name}")
                    sequences_fixed += 1
                    print(f"  🔧 {table_name}.id: attached sequence {seq_name}")

                except Exception as seq_err:
                    try:
                        cursor.execute(f"ROLLBACK TO SAVEPOINT sp_{table_name}")
                    except Exception:
                        pass
                    sequences_errors += 1
                    print(f"  ⚠️  {table_name}.id: {seq_err}")

            conn.commit()

            print(f"  Sequences fixed: {sequences_fixed}")
            print(f"  Sequences OK:    {sequences_ok}")
            if sequences_errors:
                print(f"  Errors:          {sequences_errors}")
            print("=" * 60)

        # ====================================================================
        # PHASE 9d: Add missing columns to project_files
        # March 05, 2026 — expanded to include ALL columns referenced by
        # database_file_management.py that were missing from the original list.
        # This fixes "column uploaded_at does not exist" and related errors.
        # ====================================================================

        if db_type == 'postgresql':
            print()
            print("=" * 60)
            print("🔧 Phase 9d: Adding missing project_files columns...")
            print("=" * 60)

            bool_columns_needed = [
                # Boolean columns
                ('project_files', 'is_deleted',        'BOOLEAN DEFAULT FALSE'),
                ('project_files', 'is_generated',      'BOOLEAN DEFAULT FALSE'),
                ('project_files', 'is_analyzed',       'BOOLEAN DEFAULT FALSE'),
                # Timestamp columns — uploaded_at is the critical one that was missing
                ('project_files', 'uploaded_at',       'TIMESTAMP DEFAULT NOW()'),
                ('project_files', 'analyzed_at',       'TIMESTAMP'),
                # Text columns used in queries and SELECT *
                ('project_files', 'analysis_summary',  'TEXT'),
                ('project_files', 'analysis_result',   'TEXT'),
                ('project_files', 'uploaded_by',       "TEXT DEFAULT 'user'"),
                ('project_files', 'task_id',            'INTEGER'),
                ('project_files', 'conversation_id',   'TEXT'),
                ('project_files', 'description',       'TEXT'),
                ('project_files', 'category',          "TEXT DEFAULT 'general'"),
                ('project_files', 'file_id',           'TEXT'),
                ('project_files', 'mime_type',         'TEXT'),
                ('project_files', 'original_filename', 'TEXT'),
                ('project_files', 'file_type',         'TEXT'),
                ('project_files', 'file_size',         'INTEGER DEFAULT 0'),
                ('project_files', 'file_path',         'TEXT'),
                ('project_files', 'content_text',      'TEXT'),
                ('project_files', 'content_summary',   'TEXT'),
            ]

            cols_added = 0
            cols_ok = 0

            for table_name, col_name, col_type in bool_columns_needed:
                try:
                    cursor.execute(f"SAVEPOINT sp_col_{col_name}")

                    cursor.execute("""
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = %s
                          AND column_name = %s
                    """, (table_name, col_name))

                    if cursor.fetchone():
                        cols_ok += 1
                        cursor.execute(f"RELEASE SAVEPOINT sp_col_{col_name}")
                        continue

                    cursor.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                    )
                    cursor.execute(f"RELEASE SAVEPOINT sp_col_{col_name}")
                    cols_added += 1
                    print(f"  🔧 Added {table_name}.{col_name} ({col_type})")

                except Exception as col_err:
                    try:
                        cursor.execute(f"ROLLBACK TO SAVEPOINT sp_col_{col_name}")
                    except Exception:
                        pass
                    print(f"  ⚠️  {table_name}.{col_name}: {col_err}")

            conn.commit()
            print(f"  Columns added: {cols_added}")
            print(f"  Columns OK:    {cols_ok}")
            print("=" * 60)

    except Exception as e:
        import traceback
        print(f"❌ fix_broken_tables failed: {e}")
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
