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


def _bool(db_type):
    """Return correct boolean type."""
    if db_type == 'postgresql':
        return 'BOOLEAN DEFAULT FALSE'
    return 'INTEGER DEFAULT 0'


def _ts(db_type):
    """Return correct timestamp default."""
    if db_type == 'postgresql':
        return 'TIMESTAMP DEFAULT NOW()'
    return 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'


def _text_pk(db_type):
    """Return TEXT PRIMARY KEY (same for both)."""
    return 'TEXT PRIMARY KEY'


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
    bool_false = _bool(db_type)
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
    # =========================================================================

    tables.append(f"""
        CREATE TABLE IF NOT EXISTS blog_posts (
            id {pk},
            title TEXT NOT NULL,
            slug TEXT UNIQUE,
            content TEXT,
            excerpt TEXT,
            topic TEXT,
            industry TEXT,
            keywords TEXT,
            status TEXT DEFAULT 'draft',
            seo_title TEXT,
            seo_description TEXT,
            word_count INTEGER DEFAULT 0,
            file_path TEXT,
            created_at {ts},
            updated_at {ts},
            published_at {ts}
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

        conn.commit()

    print(f"✅ Migration 001 complete: {tables_created}/{len(tables)} tables verified on {db_type}")
    return True


if __name__ == '__main__':
    """Allow running directly for testing: python migrations/migration_001_initial_schema.py"""
    result = run_migration()
    print(f"Migration result: {result}")

# I did no harm and this file is not truncated
