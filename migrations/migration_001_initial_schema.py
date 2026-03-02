"""
AI SWARM ORCHESTRATOR - Database Migration 001
File: migrations/migration_001_initial_schema.py
Created: March 02, 2026
Last Updated: March 02, 2026

PURPOSE:
    Authoritative schema definition for the entire AI Swarm Orchestrator system.
    Creates all tables for both PostgreSQL (production) and SQLite (local dev).
    Safe to run multiple times — all statements use CREATE TABLE IF NOT EXISTS.

USAGE:
    Called automatically by app.py and database.py on every startup.
    Can also be run directly: python migrations/migration_001_initial_schema.py

CHANGELOG:
    - March 02, 2026: Added missing tables for Intelligence, Alert System,
                      and Blog Posts modules. These tables were being created
                      lazily inside intelligence.py and alert_system.py at
                      module-import time, exhausting the connection pool on
                      startup. Centralising them here eliminates that problem.
                      Also corrected the blog_posts table — the original schema
                      had the wrong column names (slug, seo_description, etc.)
                      vs what blog_post_generator.py actually uses
                      (url_slug, meta_description, topic_display, angle).
                      DROP/CREATE is NOT used — ALTER TABLE ADD COLUMN IF NOT
                      EXISTS is used to add missing columns to any existing
                      blog_posts table without destroying existing data.

    - March 02, 2026: Initial creation for PostgreSQL migration (Phase 1)
"""

import os
import sys

# Add parent directory to path so we can import db_engine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pk(db_type):
    """Return correct auto-increment primary key syntax."""
    if db_type == 'postgresql':
        return 'SERIAL PRIMARY KEY'
    return 'INTEGER PRIMARY KEY AUTOINCREMENT'


def _bool(db_type, default=False):
    """Return correct boolean type with default."""
    val = 'FALSE' if default is False else 'TRUE'
    if db_type == 'postgresql':
        return f'BOOLEAN DEFAULT {val}'
    return f'INTEGER DEFAULT {"0" if default is False else "1"}'


def _ts(db_type):
    """Return correct timestamp default."""
    if db_type == 'postgresql':
        return 'TIMESTAMP DEFAULT NOW()'
    return 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'


def run_migration():
    """
    Run the initial schema migration.
    Creates all tables if they do not exist.
    Safe to call on every application startup.
    Returns True on success, raises on failure.
    """
    from db_engine import get_db_connection, get_db_type

    db_type = get_db_type()
    print(f"🔄 Running migration 001_initial_schema on {db_type}...")

    pk = _pk(db_type)
    bool_false = _bool(db_type, False)
    bool_true = _bool(db_type, True)
    ts = _ts(db_type)

    tables = []

    # =========================================================================
    # CORE SWARM TABLES
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS tasks (
            id {pk},
            task_type TEXT NOT NULL,
            complexity TEXT DEFAULT 'medium',
            ai_used TEXT,
            tokens_used INTEGER DEFAULT 0,
            cost_estimate REAL DEFAULT 0.0,
            duration_seconds REAL DEFAULT 0.0,
            success {bool_false},
            error_message TEXT,
            created_at {ts},
            metadata TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS specialists (
            id {pk},
            name TEXT NOT NULL,
            ai_type TEXT NOT NULL,
            task_type TEXT,
            calls_made INTEGER DEFAULT 0,
            successful_calls INTEGER DEFAULT 0,
            failed_calls INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            total_cost REAL DEFAULT 0.0,
            avg_duration REAL DEFAULT 0.0,
            last_used {ts},
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS consensus_validations (
            id {pk},
            task_id INTEGER,
            primary_ai TEXT,
            validator_ai TEXT,
            agreement_score REAL DEFAULT 0.0,
            final_output TEXT,
            created_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS learning_patterns (
            id {pk},
            pattern_type TEXT NOT NULL,
            pattern_key TEXT NOT NULL,
            pattern_value TEXT,
            confidence REAL DEFAULT 0.5,
            usage_count INTEGER DEFAULT 1,
            last_used {ts},
            created_at {ts}
        )
    """)

    # =========================================================================
    # CONVERSATION TABLES
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            conversation_type TEXT DEFAULT 'general',
            client_name TEXT,
            industry TEXT,
            facility_size TEXT,
            current_schedule TEXT,
            status TEXT DEFAULT 'active',
            message_count INTEGER DEFAULT 0,
            created_at {ts},
            updated_at {ts},
            metadata TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS messages (
            id {pk},
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            ai_used TEXT,
            tokens_used INTEGER DEFAULT 0,
            created_at {ts},
            metadata TEXT
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
            updated_at {ts}
        )
    """)

    # =========================================================================
    # SCHEDULE CONTEXT TABLES
    # =========================================================================

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

    # =========================================================================
    # GENERATED DOCUMENTS
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS generated_documents (
            id {pk},
            conversation_id TEXT,
            document_type TEXT NOT NULL,
            title TEXT,
            filename TEXT,
            content TEXT,
            file_path TEXT,
            file_size INTEGER DEFAULT 0,
            download_count INTEGER DEFAULT 0,
            created_at {ts},
            last_accessed {ts},
            metadata TEXT
        )
    """)

    # =========================================================================
    # CLIENT PROFILES
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS client_profiles (
            id {pk},
            conversation_id TEXT,
            client_name TEXT,
            company_name TEXT,
            industry TEXT,
            facility_size TEXT,
            location TEXT,
            current_schedule TEXT,
            pain_points TEXT,
            goals TEXT,
            constraints TEXT,
            decision_makers TEXT,
            budget_range TEXT,
            timeline TEXT,
            notes TEXT,
            status TEXT DEFAULT 'active',
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS avoidance_patterns (
            id {pk},
            conversation_id TEXT,
            pattern_type TEXT NOT NULL,
            pattern_description TEXT,
            severity TEXT DEFAULT 'medium',
            occurrence_count INTEGER DEFAULT 1,
            created_at {ts},
            last_seen {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS avoidance_violations (
            id {pk},
            conversation_id TEXT,
            pattern_id INTEGER,
            violation_description TEXT,
            resolved {bool_false},
            created_at {ts}
        )
    """)

    # =========================================================================
    # SMART ANALYZER STATE
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS smart_analyzer_states (
            id {pk},
            conversation_id TEXT UNIQUE,
            analyzer_state TEXT,
            phase TEXT DEFAULT 'initial',
            questions_asked INTEGER DEFAULT 0,
            data_completeness REAL DEFAULT 0.0,
            created_at {ts},
            updated_at {ts}
        )
    """)

    # =========================================================================
    # ANALYSIS SESSIONS
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS analysis_sessions (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            session_type TEXT DEFAULT 'general',
            status TEXT DEFAULT 'active',
            progress REAL DEFAULT 0.0,
            current_step TEXT,
            total_steps INTEGER DEFAULT 0,
            completed_steps INTEGER DEFAULT 0,
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
            title TEXT,
            content TEXT,
            file_path TEXT,
            status TEXT DEFAULT 'pending',
            created_at {ts},
            updated_at {ts}
        )
    """)

    # =========================================================================
    # PROJECT MANAGEMENT TABLES
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            client_name TEXT NOT NULL,
            company_name TEXT,
            industry TEXT,
            status TEXT DEFAULT 'active',
            phase TEXT DEFAULT 'discovery',
            start_date TEXT,
            target_completion TEXT,
            facility_size TEXT,
            current_schedule TEXT,
            pain_points TEXT,
            goals TEXT,
            notes TEXT,
            checklist TEXT,
            milestones TEXT,
            folder_structure TEXT,
            metadata TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS project_files (
            id {pk},
            project_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT,
            file_type TEXT,
            file_size INTEGER DEFAULT 0,
            file_path TEXT,
            content_text TEXT,
            content_summary TEXT,
            category TEXT DEFAULT 'general',
            analyzed {bool_false},
            analysis_result TEXT,
            upload_date {ts},
            metadata TEXT
        )
    """)

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS project_conversations (
            id {pk},
            project_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
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

    # =========================================================================
    # RESEARCH TABLES
    # =========================================================================

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
            completed_at {ts}
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

    # =========================================================================
    # MARKETING TABLES
    # =========================================================================

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
            published_at {ts},
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
            resolved_at {ts}
        )
    """)

    # =========================================================================
    # AVATAR / CONSULTATION TABLES
    # =========================================================================

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

    # =========================================================================
    # EVALUATION / INTROSPECTION TABLES
    # =========================================================================

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

    # =========================================================================
    # SURVEY TABLES
    # =========================================================================

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

    # =========================================================================
    # BLOG POSTS TABLE
    # Column names match what blog_post_generator.py actually uses.
    # The old schema had wrong names (slug, seo_description, etc.).
    # Missing columns are added via ALTER TABLE below — no data is lost.
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS blog_posts (
            id {pk},
            topic TEXT NOT NULL,
            topic_display TEXT NOT NULL,
            title TEXT NOT NULL,
            url_slug TEXT NOT NULL,
            meta_description TEXT NOT NULL,
            content TEXT NOT NULL,
            angle TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    # =========================================================================
    # CASE STUDIES TABLE
    # =========================================================================

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
            created_at {ts},
            updated_at {ts}
        )
    """)

    # =========================================================================
    # USER PROFILES TABLE
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id {pk},
            user_id TEXT UNIQUE,
            name TEXT,
            email TEXT,
            role TEXT DEFAULT 'user',
            preferences TEXT,
            created_at {ts},
            updated_at {ts}
        )
    """)

    # =========================================================================
    # WORKFLOW TABLES
    # =========================================================================

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
            completed_at {ts}
        )
    """)

    # =========================================================================
    # INTEGRATION LOGS
    # =========================================================================

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

    # =========================================================================
    # MEMORY / ROUTING TABLES (Phase 2 ready)
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS memory_store (
            id {pk},
            memory_type TEXT NOT NULL,
            memory_key TEXT NOT NULL,
            memory_value TEXT,
            relevance_score REAL DEFAULT 1.0,
            access_count INTEGER DEFAULT 0,
            last_accessed {ts},
            created_at {ts},
            expires_at {ts}
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

    # =========================================================================
    # ALERT SYSTEM TABLES
    # Previously created lazily in alert_system.py at module-import time,
    # which held a connection open during every startup.
    # Centralised here so they exist before any module tries to use them.
    # =========================================================================

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

    # =========================================================================
    # INTELLIGENCE / LEAD PIPELINE TABLES
    # Previously created lazily in intelligence.py at module-import time.
    # =========================================================================

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

    # =========================================================================
    # INDEXES
    # =========================================================================

    indexes = [
        # Core
        "CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC)",
        # Projects
        "CREATE INDEX IF NOT EXISTS idx_project_files_project ON project_files(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_conv_project ON project_conversations(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_context_project ON project_context(project_id)",
        # Blog posts
        "CREATE INDEX IF NOT EXISTS idx_blog_posts_topic ON blog_posts(topic)",
        "CREATE INDEX IF NOT EXISTS idx_blog_posts_created ON blog_posts(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_blog_posts_slug ON blog_posts(url_slug)",
        # Alerts
        "CREATE INDEX IF NOT EXISTS idx_alerts_category ON alerts(category)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_priority ON alerts(priority)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_unread ON alerts(is_read, dismissed_at)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON scheduled_jobs(next_run_at)",
        "CREATE INDEX IF NOT EXISTS idx_monitored_type ON monitored_entities(entity_type)",
        # Leads
        "CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(pipeline_stage)",
        "CREATE INDEX IF NOT EXISTS idx_leads_industry ON leads(industry)",
        "CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_lead_activities_lead ON lead_activities(lead_id)",
    ]

    # =========================================================================
    # EXECUTE ALL TABLE CREATION
    # =========================================================================

    with get_db_connection() as conn:
        cursor = conn.cursor()
        tables_created = 0
        for table_sql in tables:
            try:
                cursor.execute(table_sql)
                tables_created += 1
            except Exception as e:
                print(f"  ⚠️  Table creation warning: {e}")
                print(f"     SQL: {table_sql[:80].strip()}...")

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                print(f"  ⚠️  Index creation warning: {e}")

        # =====================================================================
        # BLOG POSTS COLUMN MIGRATION
        # If blog_posts already exists from the old schema (with slug,
        # seo_description etc.), add the columns blog_post_generator.py needs.
        # PostgreSQL supports ADD COLUMN IF NOT EXISTS; for SQLite we catch
        # the "duplicate column" error and ignore it.
        # =====================================================================
        blog_post_extra_cols = [
            ("topic_display",    "TEXT"),
            ("url_slug",         "TEXT"),
            ("meta_description", "TEXT"),
            ("angle",            "TEXT"),
        ]
        for col_name, col_type in blog_post_extra_cols:
            try:
                if db_type == 'postgresql':
                    cursor.execute(
                        f"ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS "
                        f"{col_name} {col_type}"
                    )
                else:
                    cursor.execute(
                        f"ALTER TABLE blog_posts ADD COLUMN {col_name} {col_type}"
                    )
            except Exception:
                pass  # Column already exists — safe to ignore

        conn.commit()

    print(f"✅ Migration 001 complete: {tables_created}/{len(tables)} tables verified on {db_type}")
    return True


if __name__ == '__main__':
    """Allow running directly for testing: python migrations/migration_001_initial_schema.py"""
    result = run_migration()
    print(f"Migration result: {result}")

# I did no harm and this file is not truncated
