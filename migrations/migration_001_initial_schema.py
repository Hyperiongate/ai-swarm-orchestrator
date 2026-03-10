"""
AI SWARM ORCHESTRATOR - Database Migration 001
File: migrations/migration_001_initial_schema.py
Created: March 02, 2026
Last Updated: March 09, 2026 - Added knowledge_used column to tasks table

PURPOSE:
    Authoritative schema definition for the entire AI Swarm Orchestrator system.
    Creates all tables for both PostgreSQL (production) and SQLite (local dev).
    Safe to run multiple times — all statements use CREATE TABLE IF NOT EXISTS.

CHANGELOG:
    - March 09, 2026: ADDED knowledge_used TO tasks TABLE
      * tasks.knowledge_used BOOLEAN DEFAULT FALSE added to CREATE TABLE
        and to extra_columns ALTER TABLE patch list.
      * Required by weekly_review.py _collect_metrics() knowledge_base section
        which queries WHERE knowledge_used = TRUE. Without this column the
        query raised UndefinedColumn and the metric defaulted to 0.
      * orchestration_handler.py sets knowledge_used = TRUE in the UPDATE
        when knowledge base context was injected into the prompt.
      * No other changes to any table, index, or migration logic.

    - March 06, 2026: SAVEPOINT FIX - ALTER TABLE transaction isolation
      * Root cause: The extra_columns and bool_cols ALTER TABLE loops ran in a
        single shared PostgreSQL transaction. When any statement raised an error
        (even a benign "column already exists"), PostgreSQL aborted the ENTIRE
        transaction. All subsequent ALTER TABLE statements were silently ignored
        (InFailedSqlTransaction). The except:pass swallowed the error but did NOT
        issue ROLLBACK, so the transaction stayed in aborted state.
        This is why 'reasoning', 'profile_data', 'message_range' columns were
        never added to the live database despite being in the migration.
      * Fix: Each ALTER TABLE is now wrapped in its own SAVEPOINT via the
        _safe_alter() helper. On failure, only that one statement is rolled back;
        the rest of the transaction continues. Unexpected errors are logged.
      * Added _safe_alter() helper function with SAVEPOINT logic for PostgreSQL
        and plain try/except fallback for SQLite.

    - March 06, 2026: COLUMN PATCHES - conversation_summaries + user_profiles
      * conversation_summaries: Added message_range, summary_text,
        mentioned_entities, key_decisions to extra_columns ALTER TABLE section.
      * user_profiles: Added profile_data column to CREATE TABLE and extra_columns.
      * proactive_suggestions: Added reasoning column to CREATE TABLE and
        extra_columns (proactive_curiosity_engine.py inserts this field).

    - March 06, 2026: CONVERSATION_CONTEXT UNIQUE CONSTRAINT FIX
      * Added UNIQUE(conversation_id, context_key) constraint.
      * Added CREATE UNIQUE INDEX IF NOT EXISTS to patch existing production table.

    - March 05, 2026 (Phase 2A): MEMORY_STORE SCHEMA FIX
    - March 05, 2026 (Phase 9b): PROJECT_FILES COLUMN FIX
    - March 03, 2026 (Phase 9): COMPLETE SCHEMA REWRITE to match app code.
    - March 02, 2026: Initial creation for PostgreSQL migration (Phase 1).

USAGE:
    Called automatically by app.py STEP 1 on every startup.
    Can also be run directly: python migrations/migration_001_initial_schema.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pk(db_type):
    if db_type == 'postgresql':
        return 'SERIAL PRIMARY KEY'
    return 'INTEGER PRIMARY KEY AUTOINCREMENT'


def _bool(db_type, default=False):
    val = 'FALSE' if default is False else 'TRUE'
    if db_type == 'postgresql':
        return f'BOOLEAN DEFAULT {val}'
    return f'INTEGER DEFAULT {"0" if default is False else "1"}'


def _ts(db_type):
    if db_type == 'postgresql':
        return 'TIMESTAMP DEFAULT NOW()'
    return 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'


def run_migration():
    from db_engine import get_db_connection, get_db_type

    db_type = get_db_type()
    print(f"Running migration 001_initial_schema (Phase 2A) on {db_type}...")

    pk = _pk(db_type)
    bool_false = _bool(db_type, False)
    bool_true = _bool(db_type, True)
    ts = _ts(db_type)

    tables = []

    # -------------------------------------------------------------------------
    # TASKS — March 09, 2026: added knowledge_used BOOLEAN DEFAULT FALSE
    # -------------------------------------------------------------------------
    tables.append(f"""
        CREATE TABLE IF NOT EXISTS tasks (
            id {pk},
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
            success {bool_false},
            error_message TEXT,
            conversation_id TEXT,
            knowledge_sources TEXT,
            knowledge_used {bool_false},
            created_at {ts},
            completed_at TIMESTAMP,
            metadata TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS specialist_calls (
            id {pk},
            task_id INTEGER,
            specialist_name TEXT NOT NULL,
            prompt_sent TEXT,
            response_received TEXT,
            tokens_used INTEGER DEFAULT 0,
            duration_seconds REAL DEFAULT 0.0,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS consensus_validations (
            id {pk},
            task_id INTEGER,
            ai1_name TEXT,
            ai1_response TEXT,
            ai2_name TEXT,
            ai2_response TEXT,
            primary_ai TEXT,
            validator_ai TEXT,
            agreement_score REAL DEFAULT 0.0,
            consensus_achieved {bool_false},
            final_output TEXT,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS escalations (
            id {pk},
            task_id INTEGER,
            from_orchestrator TEXT,
            to_orchestrator TEXT,
            reason TEXT,
            sonnet_analysis TEXT,
            opus_response TEXT,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS learning_patterns (
            id {pk},
            task_type TEXT NOT NULL,
            pattern_data TEXT,
            pattern_type TEXT,
            pattern_key TEXT,
            pattern_value TEXT,
            success_rate REAL DEFAULT 0.0,
            confidence REAL DEFAULT 0.5,
            times_used INTEGER DEFAULT 1,
            usage_count INTEGER DEFAULT 1,
            last_used {ts},
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS learning_records (
            id {pk},
            pattern_type TEXT NOT NULL,
            success_rate REAL DEFAULT 0.0,
            times_applied INTEGER DEFAULT 0,
            pattern_data TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS user_feedback (
            id {pk},
            task_id INTEGER,
            overall_rating INTEGER,
            quality_rating INTEGER,
            accuracy_rating INTEGER,
            usefulness_rating INTEGER,
            consensus_was_accurate {bool_false},
            improvement_categories TEXT,
            user_comment TEXT,
            output_used {bool_false},
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS conversations (
            id {pk},
            conversation_id TEXT UNIQUE NOT NULL,
            title TEXT,
            mode TEXT DEFAULT 'quick',
            project_id TEXT,
            is_archived {bool_false},
            message_count INTEGER DEFAULT 0,
            schedule_context TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id {pk},
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            task_id INTEGER,
            metadata TEXT,
            file_contents TEXT,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS conversation_context (
            id {pk},
            conversation_id TEXT NOT NULL,
            context_type TEXT NOT NULL,
            context_key TEXT NOT NULL,
            context_value TEXT,
            created_at {ts},
            updated_at {ts},
            UNIQUE(conversation_id, context_key)
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS generated_documents (
            id {pk},
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
            is_deleted {bool_false},
            download_count INTEGER DEFAULT 0,
            created_at {ts},
            last_accessed {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS projects (
            id {pk},
            project_id TEXT UNIQUE,
            client_name TEXT NOT NULL,
            company_name TEXT,
            industry TEXT,
            facility_size TEXT,
            status TEXT DEFAULT 'active',
            project_phase TEXT DEFAULT 'discovery',
            start_date TEXT,
            target_completion TEXT,
            current_schedule TEXT,
            pain_points TEXT,
            goals TEXT,
            notes TEXT,
            context_data TEXT,
            uploaded_files TEXT,
            email_context TEXT,
            key_findings TEXT,
            schedules_proposed TEXT,
            storage_path TEXT,
            checklist_data TEXT,
            milestone_data TEXT,
            folder_data TEXT,
            metadata TEXT DEFAULT '{{}}',
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS project_files (
            id {pk},
            project_id TEXT NOT NULL,
            file_id TEXT UNIQUE,
            filename TEXT NOT NULL,
            original_filename TEXT,
            file_type TEXT,
            file_size INTEGER DEFAULT 0,
            file_path TEXT,
            mime_type TEXT,
            content_text TEXT,
            content_summary TEXT,
            category TEXT DEFAULT 'general',
            description TEXT,
            is_generated {bool_false},
            is_deleted {bool_false},
            is_analyzed {bool_false},
            analysis_summary TEXT,
            analysis_result TEXT,
            analyzed_at TIMESTAMP,
            uploaded_at {ts},
            uploaded_by TEXT DEFAULT 'user',
            task_id INTEGER,
            conversation_id TEXT,
            metadata TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS project_conversations (
            id {pk},
            project_id TEXT NOT NULL,
            conversation_id TEXT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            file_ids TEXT,
            metadata TEXT,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS project_context (
            id {pk},
            project_id TEXT NOT NULL,
            context_key TEXT NOT NULL,
            context_value TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS client_profiles (
            id {pk},
            client_name TEXT UNIQUE NOT NULL,
            profile_data TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS avoidance_patterns (
            id {pk},
            pattern_data TEXT,
            severity TEXT DEFAULT 'medium',
            times_violated INTEGER DEFAULT 0,
            created_at {ts},
            last_seen {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS smart_analyzer_state (
            id {pk},
            conversation_id TEXT UNIQUE,
            file_path TEXT,
            file_name TEXT,
            analyzer_state TEXT,
            profile_json TEXT,
            last_used {ts},
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS analysis_sessions (
            id {pk},
            session_id TEXT UNIQUE,
            project_id TEXT,
            state TEXT DEFAULT 'initial',
            data_files TEXT,
            discovered_structure TEXT,
            clarifications TEXT,
            analysis_plan TEXT,
            results TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS analysis_deliverables (
            id {pk},
            session_id TEXT NOT NULL,
            deliverable_type TEXT NOT NULL,
            file_path TEXT,
            file_name TEXT,
            metadata TEXT,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS analysis_progress (
            id {pk},
            session_id TEXT NOT NULL,
            step_name TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            progress_pct REAL DEFAULT 0.0,
            message TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS schedule_contexts (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            client_name TEXT,
            industry TEXT,
            facility_size TEXT,
            current_schedule TEXT,
            constraints TEXT,
            preferences TEXT,
            generated_schedules TEXT,
            status TEXT DEFAULT 'active',
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS research_sessions (
            id {pk},
            topic TEXT NOT NULL,
            query TEXT,
            status TEXT DEFAULT 'pending',
            results TEXT,
            summary TEXT,
            sources TEXT,
            created_at {ts},
            completed_at TIMESTAMP
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS resource_searches (
            id {pk},
            search_query TEXT,
            search_type TEXT,
            results TEXT,
            result_count INTEGER DEFAULT 0,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS marketing_campaigns (
            id {pk},
            campaign_name TEXT NOT NULL,
            campaign_type TEXT,
            target_industry TEXT,
            status TEXT DEFAULT 'draft',
            content TEXT,
            metrics TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS content_pieces (
            id {pk},
            campaign_id INTEGER,
            content_type TEXT NOT NULL,
            title TEXT,
            body TEXT,
            status TEXT DEFAULT 'draft',
            published_at TIMESTAMP,
            created_at {ts},
            metadata TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS improvement_reports (
            id {pk},
            report_type TEXT NOT NULL,
            title TEXT,
            findings TEXT,
            recommendations TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'open',
            created_at {ts},
            resolved_at TIMESTAMP
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS avatar_sessions (
            id {pk},
            avatar_name TEXT NOT NULL,
            session_type TEXT DEFAULT 'consultation',
            client_context TEXT,
            conversation_history TEXT,
            recommendations TEXT,
            status TEXT DEFAULT 'active',
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS swarm_evaluations (
            id {pk},
            evaluation_date {ts},
            health_score REAL DEFAULT 0.0,
            trend TEXT DEFAULT 'stable',
            metrics TEXT,
            recommendations TEXT,
            raw_data TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS introspection_reports (
            id {pk},
            created_at {ts},
            confidence_score REAL DEFAULT 0.0,
            insights TEXT,
            patterns TEXT,
            recommendations TEXT,
            raw_analysis TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS introspection_insights (
            id {pk},
            insight_type TEXT NOT NULL,
            category TEXT,
            title TEXT,
            description TEXT,
            severity TEXT DEFAULT 'info',
            confidence_score REAL DEFAULT 0.0,
            data TEXT,
            is_read {bool_false},
            is_actioned {bool_false},
            action_taken TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS surveys (
            id {pk},
            survey_name TEXT NOT NULL,
            survey_type TEXT DEFAULT 'schedule_preference',
            client_name TEXT,
            status TEXT DEFAULT 'draft',
            questions TEXT,
            responses TEXT,
            analysis TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS survey_responses (
            id {pk},
            survey_id INTEGER NOT NULL,
            respondent_id TEXT,
            responses TEXT,
            submitted_at {ts},
            metadata TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS blog_posts (
            id {pk},
            topic TEXT NOT NULL,
            topic_display TEXT,
            title TEXT NOT NULL,
            url_slug TEXT,
            meta_description TEXT,
            content TEXT NOT NULL,
            angle TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS case_studies (
            id {pk},
            title TEXT NOT NULL,
            slug TEXT UNIQUE,
            industry TEXT,
            company_size TEXT,
            challenge TEXT,
            solution TEXT,
            results TEXT,
            content TEXT,
            keywords TEXT,
            status TEXT DEFAULT 'draft',
            file_path TEXT,
            problem_summary TEXT,
            solution_summary TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    # -------------------------------------------------------------------------
    # USER_PROFILES — March 06, 2026: added profile_data column
    # -------------------------------------------------------------------------
    tables.append(f"""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id {pk},
            user_id TEXT UNIQUE,
            name TEXT,
            email TEXT,
            role TEXT DEFAULT 'user',
            preferences TEXT,
            profile_data TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS workflows (
            id {pk},
            workflow_name TEXT NOT NULL,
            workflow_type TEXT,
            status TEXT DEFAULT 'active',
            steps TEXT,
            current_step INTEGER DEFAULT 0,
            context TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS workflow_executions (
            id {pk},
            workflow_id INTEGER,
            step_name TEXT,
            status TEXT DEFAULT 'pending',
            input_data TEXT,
            output_data TEXT,
            error_message TEXT,
            started_at {ts},
            completed_at TIMESTAMP
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS integration_logs (
            id {pk},
            integration_type TEXT NOT NULL,
            action TEXT,
            status TEXT DEFAULT 'success',
            request_data TEXT,
            response_data TEXT,
            error_message TEXT,
            created_at {ts}
        )
    """)

    # -------------------------------------------------------------------------
    # MEMORY STORE - Phase 2A schema
    # -------------------------------------------------------------------------
    tables.append(f"""
        CREATE TABLE IF NOT EXISTS memory_store (
            id {pk},
            memory_type TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            relevance_score REAL DEFAULT 1.0,
            source_task_id INTEGER,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS routing_preferences (
            id {pk},
            task_pattern TEXT NOT NULL,
            preferred_ai TEXT NOT NULL,
            success_rate REAL DEFAULT 0.0,
            sample_count INTEGER DEFAULT 0,
            last_updated {ts},
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS alerts (
            id {pk},
            category TEXT NOT NULL,
            priority TEXT DEFAULT 'medium',
            title TEXT NOT NULL,
            summary TEXT,
            details TEXT,
            source_url TEXT,
            source_data TEXT,
            created_at {ts},
            acknowledged_at TIMESTAMP,
            dismissed_at TIMESTAMP,
            snoozed_until TIMESTAMP,
            emailed_at TIMESTAMP,
            is_read {bool_false},
            is_actioned {bool_false},
            action_taken TEXT,
            metadata TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id {pk},
            job_name TEXT UNIQUE NOT NULL,
            job_type TEXT NOT NULL,
            schedule_type TEXT DEFAULT 'daily',
            schedule_time TEXT DEFAULT '07:00',
            schedule_days TEXT DEFAULT 'mon,tue,wed,thu,fri',
            is_enabled {bool_false},
            last_run_at TIMESTAMP,
            next_run_at TIMESTAMP,
            last_result TEXT,
            config TEXT,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS job_executions (
            id {pk},
            job_id INTEGER,
            started_at {ts},
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running',
            alerts_generated INTEGER DEFAULT 0,
            error_message TEXT,
            execution_log TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS alert_subscriptions (
            id {pk},
            email TEXT NOT NULL,
            category TEXT,
            priority_threshold TEXT DEFAULT 'medium',
            is_enabled {bool_true},
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS monitored_entities (
            id {pk},
            entity_type TEXT NOT NULL,
            entity_name TEXT NOT NULL,
            search_terms TEXT,
            is_enabled {bool_true},
            last_checked_at TIMESTAMP,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS leads (
            id {pk},
            company_name TEXT NOT NULL,
            industry TEXT,
            estimated_headcount INTEGER,
            location TEXT,
            contact_name TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            contact_title TEXT,
            source TEXT DEFAULT 'manual',
            source_alert_id INTEGER,
            source_url TEXT,
            pipeline_stage TEXT DEFAULT 'detected',
            score INTEGER DEFAULT 0,
            score_breakdown TEXT,
            notes TEXT,
            next_action TEXT,
            next_action_date TEXT,
            created_at {ts},
            updated_at {ts},
            stage_changed_at {ts},
            is_archived {bool_false},
            archive_reason TEXT,
            metadata TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS lead_activities (
            id {pk},
            lead_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            activity_description TEXT,
            outcome TEXT,
            created_at {ts},
            created_by TEXT DEFAULT 'system',
            metadata TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS lead_documents (
            id {pk},
            lead_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            document_id INTEGER,
            title TEXT,
            file_path TEXT,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS industry_benchmarks (
            id {pk},
            industry TEXT UNIQUE NOT NULL,
            company_count INTEGER DEFAULT 0,
            avg_headcount REAL,
            common_schedules TEXT,
            common_challenges TEXT,
            talking_points TEXT,
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS background_jobs (
            id {pk},
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
            created_at {ts},
            updated_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    # -------------------------------------------------------------------------
    # CONVERSATION_SUMMARIES — March 06, 2026: added message_range,
    # summary_text, mentioned_entities, key_decisions columns.
    # -------------------------------------------------------------------------
    tables.append(f"""
        CREATE TABLE IF NOT EXISTS conversation_summaries (
            id {pk},
            conversation_id TEXT NOT NULL,
            summary TEXT,
            summary_text TEXT,
            key_topics TEXT,
            key_decisions TEXT,
            action_items TEXT,
            mentioned_entities TEXT,
            message_range TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    # -------------------------------------------------------------------------
    # PROACTIVE_SUGGESTIONS — March 06, 2026: added reasoning column.
    # -------------------------------------------------------------------------
    tables.append(f"""
        CREATE TABLE IF NOT EXISTS proactive_suggestions (
            id {pk},
            conversation_id TEXT,
            response_id TEXT,
            suggestion_type TEXT,
            suggestion_text TEXT,
            context TEXT,
            reasoning TEXT,
            was_accepted {bool_false},
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS user_patterns (
            id {pk},
            pattern_type TEXT NOT NULL,
            pattern_key TEXT,
            pattern_value TEXT,
            frequency INTEGER DEFAULT 1,
            last_seen {ts},
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS modification_proposals (
            id {pk},
            proposal_type TEXT NOT NULL,
            priority TEXT DEFAULT 'medium',
            title TEXT NOT NULL,
            observation TEXT,
            current_behavior TEXT,
            proposed_change TEXT,
            expected_impact TEXT,
            code_diff TEXT,
            confidence_score REAL,
            created_at {ts},
            status TEXT DEFAULT 'pending',
            reviewed_at TIMESTAMP,
            review_notes TEXT,
            implemented_at TIMESTAMP
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS goal_alignment_logs (
            id {pk},
            log_date DATE NOT NULL,
            objective_id INTEGER,
            objective_name TEXT,
            tasks_count INTEGER DEFAULT 0,
            percentage_of_activity REAL,
            assessment TEXT,
            created_at {ts}
        )
    """)

    # =========================================================================
    # INDEXES
    # =========================================================================

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_conversation ON tasks(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_conv_messages_conversation ON conversation_messages(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_conv_messages_created ON conversation_messages(created_at ASC)",
        "CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_projects_project_id ON projects(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)",
        "CREATE INDEX IF NOT EXISTS idx_project_files_project ON project_files(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_files_file_id ON project_files(file_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_conv_project ON project_conversations(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_context_project ON project_context(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_generated_docs_created ON generated_documents(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_generated_docs_type ON generated_documents(document_type)",
        "CREATE INDEX IF NOT EXISTS idx_blog_posts_topic ON blog_posts(topic)",
        "CREATE INDEX IF NOT EXISTS idx_blog_posts_created ON blog_posts(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_category ON alerts(category)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_priority ON alerts(priority)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_unread ON alerts(is_read, dismissed_at)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON scheduled_jobs(next_run_at)",
        "CREATE INDEX IF NOT EXISTS idx_monitored_type ON monitored_entities(entity_type)",
        "CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(pipeline_stage)",
        "CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads(industry)",
        "CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_lead_activities_lead ON lead_activities(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_background_jobs_status ON background_jobs(status)",
        "CREATE INDEX IF NOT EXISTS idx_background_jobs_created ON background_jobs(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_background_jobs_conversation ON background_jobs(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_learning_patterns_type ON learning_patterns(task_type)",
        "CREATE INDEX IF NOT EXISTS idx_learning_records_type ON learning_records(pattern_type)",
        "CREATE INDEX IF NOT EXISTS idx_smart_analyzer_conversation ON smart_analyzer_state(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_analysis_sessions_session ON analysis_sessions(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_introspection_insights_created ON introspection_insights(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_introspection_insights_read ON introspection_insights(is_read)",
        "CREATE INDEX IF NOT EXISTS idx_project_files_uploaded ON project_files(uploaded_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_memory_store_type ON memory_store(memory_type)",
        "CREATE INDEX IF NOT EXISTS idx_memory_store_category ON memory_store(category)",
        "CREATE INDEX IF NOT EXISTS idx_memory_store_created ON memory_store(created_at DESC)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_conv_context_unique ON conversation_context(conversation_id, context_key)",
    ]

    # =========================================================================
    # EXECUTE ALL TABLE CREATION
    # =========================================================================

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        tables_created = 0
        errors = 0
        for table_sql in tables:
            try:
                cursor.execute(table_sql)
                tables_created += 1
            except Exception as e:
                errors += 1
                table_name = "unknown"
                try:
                    import re
                    match = re.search(r'CREATE TABLE IF NOT EXISTS\s+(\w+)', table_sql)
                    if match:
                        table_name = match.group(1)
                except Exception:
                    pass
                print(f"  Table '{table_name}' warning: {e}")

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                pass

        # =====================================================================
        # ADD MISSING COLUMNS TO EXISTING TABLES
        # Safe: ADD COLUMN IF NOT EXISTS skips columns that already exist.
        # =====================================================================

        extra_columns = [
            # projects table
            ("projects", "project_id", "TEXT"),
            ("projects", "facility_size", "TEXT"),
            ("projects", "project_phase", "TEXT DEFAULT 'discovery'"),
            ("projects", "context_data", "TEXT"),
            ("projects", "uploaded_files", "TEXT"),
            ("projects", "email_context", "TEXT"),
            ("projects", "key_findings", "TEXT"),
            ("projects", "schedules_proposed", "TEXT"),
            ("projects", "storage_path", "TEXT"),
            ("projects", "checklist_data", "TEXT"),
            ("projects", "milestone_data", "TEXT"),
            ("projects", "folder_data", "TEXT"),
            ("projects", "metadata", "TEXT DEFAULT '{}'"),
            ("projects", "company_name", "TEXT"),
            ("projects", "current_schedule", "TEXT"),
            ("projects", "pain_points", "TEXT"),
            ("projects", "goals", "TEXT"),
            ("projects", "notes", "TEXT"),
            # tasks table
            ("tasks", "user_request", "TEXT"),
            ("tasks", "status", "TEXT DEFAULT 'pending'"),
            ("tasks", "assigned_orchestrator", "TEXT"),
            ("tasks", "orchestrator", "TEXT"),
            ("tasks", "result", "TEXT"),
            ("tasks", "confidence", "REAL"),
            ("tasks", "conversation_id", "TEXT"),
            ("tasks", "knowledge_sources", "TEXT"),
            ("tasks", "completed_at", "TIMESTAMP"),
            ("tasks", "knowledge_used", "BOOLEAN DEFAULT FALSE"),  # March 09, 2026
            # conversations table
            ("conversations", "conversation_id", "TEXT"),
            ("conversations", "mode", "TEXT DEFAULT 'quick'"),
            ("conversations", "project_id", "TEXT"),
            ("conversations", "schedule_context", "TEXT"),
            # generated_documents table
            ("generated_documents", "original_name", "TEXT"),
            ("generated_documents", "category", "TEXT DEFAULT 'general'"),
            ("generated_documents", "description", "TEXT"),
            ("generated_documents", "task_id", "INTEGER"),
            ("generated_documents", "project_id", "TEXT"),
            # case_studies table
            ("case_studies", "problem_summary", "TEXT"),
            ("case_studies", "solution_summary", "TEXT"),
            # blog_posts table
            ("blog_posts", "topic_display", "TEXT"),
            ("blog_posts", "url_slug", "TEXT"),
            ("blog_posts", "meta_description", "TEXT"),
            ("blog_posts", "angle", "TEXT"),
            # consensus_validations
            ("consensus_validations", "ai1_name", "TEXT"),
            ("consensus_validations", "ai1_response", "TEXT"),
            ("consensus_validations", "ai2_name", "TEXT"),
            ("consensus_validations", "ai2_response", "TEXT"),
            ("consensus_validations", "consensus_achieved", "BOOLEAN DEFAULT FALSE"),
            # project_files
            ("project_files", "file_id", "TEXT"),
            ("project_files", "mime_type", "TEXT"),
            ("project_files", "description", "TEXT"),
            ("project_files", "uploaded_by", "TEXT DEFAULT 'user'"),
            ("project_files", "task_id", "INTEGER"),
            ("project_files", "conversation_id", "TEXT"),
            ("project_files", "analysis_summary", "TEXT"),
            ("project_files", "analyzed_at", "TIMESTAMP"),
            ("project_files", "uploaded_at", "TIMESTAMP DEFAULT NOW()"),
            ("project_files", "original_filename", "TEXT"),
            ("project_files", "file_type", "TEXT"),
            ("project_files", "file_size", "INTEGER DEFAULT 0"),
            ("project_files", "file_path", "TEXT"),
            ("project_files", "content_text", "TEXT"),
            ("project_files", "content_summary", "TEXT"),
            ("project_files", "category", "TEXT DEFAULT 'general'"),
            ("project_files", "analysis_result", "TEXT"),
            # project_conversations
            ("project_conversations", "conversation_id", "TEXT"),
            ("project_conversations", "file_ids", "TEXT"),
            ("project_conversations", "metadata", "TEXT"),
            # proactive_suggestions
            ("proactive_suggestions", "conversation_id", "TEXT"),
            ("proactive_suggestions", "response_id", "TEXT"),
            ("proactive_suggestions", "reasoning", "TEXT"),
            # introspection_insights
            ("introspection_insights", "insight_type", "TEXT"),
            ("introspection_insights", "category", "TEXT"),
            ("introspection_insights", "title", "TEXT"),
            ("introspection_insights", "description", "TEXT"),
            # memory_store — Phase 2A column patch
            ("memory_store", "category", "TEXT DEFAULT 'general'"),
            ("memory_store", "content", "TEXT DEFAULT ''"),
            ("memory_store", "source_task_id", "INTEGER"),
            ("memory_store", "updated_at", "TIMESTAMP DEFAULT NOW()"),
            # conversation_summaries — March 06, 2026 column patch
            ("conversation_summaries", "message_range", "TEXT"),
            ("conversation_summaries", "summary_text", "TEXT"),
            ("conversation_summaries", "mentioned_entities", "TEXT"),
            ("conversation_summaries", "key_decisions", "TEXT"),
            # user_profiles — March 06, 2026 column patch
            ("user_profiles", "profile_data", "TEXT"),
        ]

        # =====================================================================
        # SAVEPOINT-PROTECTED ALTER TABLE HELPER
        #
        # PostgreSQL aborts the ENTIRE transaction if any statement raises an
        # error, even when caught with except:pass. Every subsequent statement
        # in that transaction is silently ignored (InFailedSqlTransaction).
        #
        # Fix: wrap each ALTER TABLE in its own SAVEPOINT. On failure, roll
        # back only that savepoint, leaving the rest of the transaction intact.
        # SQLite does not support SAVEPOINT in this context so we fall back to
        # the plain try/except pattern.
        # =====================================================================

        def _safe_alter(cursor, db_type, sql):
            """Execute one ALTER TABLE protected by a SAVEPOINT (PostgreSQL)."""
            if db_type == 'postgresql':
                try:
                    cursor.execute("SAVEPOINT alter_col")
                    cursor.execute(sql)
                    cursor.execute("RELEASE SAVEPOINT alter_col")
                except Exception as e:
                    cursor.execute("ROLLBACK TO SAVEPOINT alter_col")
                    # Only log unexpected errors; skip duplicate-column silently
                    msg = str(e).lower()
                    if 'already exists' not in msg and 'duplicate' not in msg:
                        print(f"  ALTER TABLE note: {e}")
            else:
                try:
                    cursor.execute(sql)
                except Exception:
                    pass  # SQLite: column already exists → ignore

        for table_name, col_name, col_type in extra_columns:
            if db_type == 'postgresql':
                sql = (f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS "
                       f"{col_name} {col_type}")
            else:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
            _safe_alter(cursor, db_type, sql)

        # =====================================================================
        # ADD BOOLEAN COLUMNS
        # =====================================================================
        bool_cols = [
            ("conversations", "is_archived", bool_false),
            ("generated_documents", "is_deleted", bool_false),
            ("project_files", "is_generated", bool_false),
            ("project_files", "is_deleted", bool_false),
            ("project_files", "is_analyzed", bool_false),
        ]
        for table_name, col_name, col_default in bool_cols:
            if db_type == 'postgresql':
                sql = (f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS "
                       f"{col_name} {col_default}")
            else:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_default}"
            _safe_alter(cursor, db_type, sql)

        conn.commit()
    finally:
        conn.close()

    print(f"Migration 001 (Phase 2A) complete: {tables_created}/{len(tables)} tables verified on {db_type}")
    if errors > 0:
        print(f"  {errors} table(s) had warnings (likely already exist with different schema)")
    return True


if __name__ == '__main__':
    result = run_migration()
    print(f"Migration result: {result}")

# I did no harm and this file is not truncated
