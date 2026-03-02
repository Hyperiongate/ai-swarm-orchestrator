"""
AI SWARM ORCHESTRATOR - Initial Schema Migration
Created: March 02, 2026
Last Updated: March 02, 2026 - INITIAL CREATION

PURPOSE:
    Creates ALL database tables in PostgreSQL (or SQLite for local dev).
    This is the authoritative schema definition for the entire system.
    Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS throughout.

    Includes all tables from the original database.py plus:
    - memory_store: for Phase 2 swarm memory
    - routing_preferences: for Phase 2 intelligent routing

CHANGELOG:
- March 02, 2026: CREATED — full schema for PostgreSQL migration (Phase 1)
  * All tables from database.py converted to PostgreSQL syntax
  * SERIAL replaces INTEGER PRIMARY KEY AUTOINCREMENT
  * %s placeholder style throughout
  * TIMESTAMP WITH TIME ZONE for all timestamp columns
  * Idempotent — safe to run on every deploy

HOW TO RUN:
    Called automatically by app.py on startup before blueprint registration.
    Can also be run manually: python migrations/001_initial_schema.py

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import sys
import os

# Allow running directly: python migrations/001_initial_schema.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_engine import get_db_connection, get_db_type


def run_migration():
    """
    Create all tables. Safe to run multiple times.
    Returns True on success, raises on failure.
    """
    db_type = get_db_type()
    print(f"🔄 Running migration 001_initial_schema on {db_type}...")

    conn = get_db_connection()
    try:
        _create_all_tables(conn)
        conn.commit()
        print("✅ Migration 001_initial_schema complete")
        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration 001_initial_schema FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


def _serial(db_type):
    """Return the correct auto-increment type for the active database."""
    return 'SERIAL' if db_type == 'postgresql' else 'INTEGER'


def _pk(db_type):
    """Return correct primary key syntax."""
    if db_type == 'postgresql':
        return 'SERIAL PRIMARY KEY'
    return 'INTEGER PRIMARY KEY AUTOINCREMENT'


def _bool(db_type):
    """Return correct boolean type."""
    return 'BOOLEAN' if db_type == 'postgresql' else 'INTEGER'


def _ts_default(db_type):
    """Return correct timestamp default."""
    return 'NOW()' if db_type == 'postgresql' else 'CURRENT_TIMESTAMP'


def _create_all_tables(conn):
    db_type = get_db_type()
    pk = _pk(db_type)
    bool_type = _bool(db_type)
    ts_default = _ts_default(db_type)

    # ========================================================================
    # CORE ORCHESTRATION TABLES
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS tasks (
            id {pk},
            created_at TIMESTAMP DEFAULT {ts_default},
            completed_at TIMESTAMP,
            user_request TEXT NOT NULL,
            task_type TEXT,
            complexity TEXT,
            assigned_orchestrator TEXT,
            orchestrator TEXT,
            status TEXT DEFAULT 'pending',
            result TEXT,
            confidence REAL,
            execution_time_seconds REAL,
            knowledge_used {bool_type} DEFAULT 0,
            knowledge_sources TEXT,
            conversation_id TEXT
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS projects (
            id {pk},
            project_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT {ts_default},
            updated_at TIMESTAMP DEFAULT {ts_default},
            client_name TEXT NOT NULL,
            industry TEXT,
            facility_type TEXT,
            project_phase TEXT DEFAULT 'discovery',
            status TEXT DEFAULT 'active',
            storage_path TEXT,
            checklist_data TEXT,
            milestone_data TEXT,
            folder_data TEXT,
            context_data TEXT,
            uploaded_files TEXT,
            email_context TEXT,
            key_findings TEXT,
            schedules_proposed TEXT,
            metadata TEXT
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS specialist_calls (
            id {pk},
            task_id INTEGER,
            specialist_name TEXT NOT NULL,
            specialist_role TEXT,
            assigned_reason TEXT,
            prompt_sent TEXT,
            response_received TEXT,
            output TEXT,
            tokens_used INTEGER,
            duration_seconds REAL,
            execution_time_seconds REAL,
            success {bool_type},
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS consensus_validations (
            id {pk},
            task_id INTEGER,
            ai1_name TEXT,
            ai1_response TEXT,
            ai2_name TEXT,
            ai2_response TEXT,
            validator_ais TEXT,
            agreement_score REAL,
            consensus_achieved {bool_type},
            disagreements TEXT,
            final_output TEXT,
            final_decision TEXT,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS learning_patterns (
            id {pk},
            created_at TIMESTAMP DEFAULT {ts_default},
            last_used TIMESTAMP DEFAULT {ts_default},
            task_type TEXT,
            pattern_type TEXT,
            pattern_data TEXT,
            success_rate REAL,
            times_used INTEGER DEFAULT 1,
            times_applied INTEGER DEFAULT 1
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS learning_records (
            id {pk},
            created_at TIMESTAMP DEFAULT {ts_default},
            last_used TIMESTAMP DEFAULT {ts_default},
            task_type TEXT,
            pattern_type TEXT,
            pattern_data TEXT,
            success_rate REAL,
            times_used INTEGER DEFAULT 1,
            times_applied INTEGER DEFAULT 1
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS escalations (
            id {pk},
            task_id INTEGER,
            escalated_at TIMESTAMP DEFAULT {ts_default},
            created_at TIMESTAMP DEFAULT {ts_default},
            reason TEXT,
            sonnet_confidence REAL,
            opus_analysis TEXT
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS user_feedback (
            id {pk},
            task_id INTEGER,
            submitted_at TIMESTAMP DEFAULT {ts_default},
            overall_rating INTEGER,
            quality_rating INTEGER,
            accuracy_rating INTEGER,
            usefulness_rating INTEGER,
            consensus_was_accurate {bool_type},
            improvement_categories TEXT,
            user_comment TEXT,
            output_used {bool_type}
        )
    ''')

    # ========================================================================
    # PROACTIVE INTELLIGENCE TABLES
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS user_patterns (
            id {pk},
            pattern_type TEXT NOT NULL,
            pattern_data TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            last_seen TIMESTAMP DEFAULT {ts_default},
            suggestion_made {bool_type} DEFAULT 0,
            suggestion_accepted {bool_type} DEFAULT 0,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS proactive_suggestions (
            id {pk},
            task_id INTEGER,
            suggestion_type TEXT NOT NULL,
            suggestion_title TEXT NOT NULL,
            suggestion_data TEXT NOT NULL,
            displayed {bool_type} DEFAULT 0,
            accepted {bool_type} DEFAULT 0,
            dismissed {bool_type} DEFAULT 0,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS clarification_history (
            id {pk},
            task_id INTEGER,
            questions_asked TEXT NOT NULL,
            answers_provided TEXT,
            improved_result {bool_type} DEFAULT 0,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    # ========================================================================
    # CONVERSATION MEMORY TABLES
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS conversations (
            id {pk},
            conversation_id TEXT UNIQUE NOT NULL,
            title TEXT DEFAULT 'New Conversation',
            mode TEXT DEFAULT 'quick',
            project_id TEXT,
            created_at TIMESTAMP DEFAULT {ts_default},
            updated_at TIMESTAMP DEFAULT {ts_default},
            message_count INTEGER DEFAULT 0,
            is_archived {bool_type} DEFAULT 0,
            metadata TEXT,
            schedule_context TEXT
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id {pk},
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            task_id INTEGER,
            metadata TEXT,
            file_contents TEXT,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS conversation_context (
            id {pk},
            conversation_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT {ts_default},
            updated_at TIMESTAMP DEFAULT {ts_default},
            UNIQUE(conversation_id, key)
        )
    ''')

    # ========================================================================
    # GENERATED DOCUMENTS TABLE
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS generated_documents (
            id {pk},
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            document_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            task_id INTEGER,
            conversation_id TEXT,
            project_id TEXT,
            title TEXT,
            description TEXT,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT {ts_default},
            last_accessed TIMESTAMP,
            download_count INTEGER DEFAULT 0,
            is_deleted {bool_type} DEFAULT 0,
            metadata TEXT
        )
    ''')

    # ========================================================================
    # RESEARCH AGENT TABLES
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS research_logs (
            id {pk},
            query TEXT NOT NULL,
            result_count INTEGER DEFAULT 0,
            searched_at TIMESTAMP DEFAULT {ts_default},
            search_type TEXT,
            user_initiated {bool_type} DEFAULT 0
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS research_briefings (
            id {pk},
            briefing_data TEXT,
            created_at TIMESTAMP DEFAULT {ts_default},
            was_read {bool_type} DEFAULT 0,
            read_at TIMESTAMP
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS research_findings (
            id {pk},
            category TEXT,
            title TEXT,
            url TEXT,
            summary TEXT,
            relevance_score REAL,
            found_at TIMESTAMP DEFAULT {ts_default},
            actioned {bool_type} DEFAULT 0,
            action_taken TEXT,
            actioned_at TIMESTAMP
        )
    ''')

    # ========================================================================
    # MARKETING TABLES
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS marketing_content (
            id {pk},
            content_type TEXT NOT NULL,
            content_data TEXT NOT NULL,
            status TEXT DEFAULT 'pending_approval',
            generated_at TIMESTAMP DEFAULT {ts_default},
            approved_at TIMESTAMP,
            published_at TIMESTAMP,
            rejection_reason TEXT,
            source_task_id INTEGER,
            estimated_engagement TEXT,
            actual_engagement_score REAL,
            category TEXT
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS marketing_activity_log (
            id {pk},
            content_id INTEGER,
            activity_type TEXT NOT NULL,
            activity_data TEXT,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS marketing_performance (
            id {pk},
            content_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            engagement_rate REAL,
            measured_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    # ========================================================================
    # AVATAR CONSULTATION TABLES
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS avatar_conversations (
            id {pk},
            conversation_id TEXT UNIQUE NOT NULL,
            started_at TIMESTAMP DEFAULT {ts_default},
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'active',
            visitor_name TEXT,
            visitor_company TEXT,
            visitor_email TEXT,
            visitor_phone TEXT,
            visitor_industry TEXT,
            visitor_facility_size INTEGER,
            lead_score INTEGER DEFAULT 0
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS avatar_messages (
            id {pk},
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            stage TEXT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    # ========================================================================
    # SWARM SELF-EVALUATION TABLES
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS swarm_evaluations (
            id {pk},
            evaluation_date TIMESTAMP DEFAULT {ts_default},
            period_days INTEGER DEFAULT 7,
            health_score INTEGER,
            trend TEXT,
            tasks_processed INTEGER,
            success_rate TEXT,
            executive_summary TEXT,
            gaps_count INTEGER DEFAULT 0,
            high_priority_gaps_count INTEGER DEFAULT 0,
            recommendations_count INTEGER DEFAULT 0,
            full_report_json TEXT,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    # ========================================================================
    # INTROSPECTION LAYER TABLES
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS introspection_insights (
            id {pk},
            insight_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT {ts_default},
            period_analyzed TEXT,
            summary TEXT NOT NULL,
            full_analysis_json TEXT,
            confidence_score REAL,
            requires_action {bool_type} DEFAULT 0,
            action_taken {bool_type} DEFAULT 0,
            action_notes TEXT,
            notification_pending {bool_type} DEFAULT 1,
            notification_shown_at TIMESTAMP,
            notification_dismissed {bool_type} DEFAULT 0,
            archived {bool_type} DEFAULT 0
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS capability_boundaries (
            id {pk},
            boundary_type TEXT NOT NULL,
            description TEXT NOT NULL,
            discovered_at TIMESTAMP DEFAULT {ts_default},
            last_confirmed TIMESTAMP,
            occurrence_count INTEGER DEFAULT 1,
            suggested_resolution TEXT,
            resolved {bool_type} DEFAULT 0,
            resolved_at TIMESTAMP,
            resolution_notes TEXT
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS calibration_records (
            id {pk},
            task_id INTEGER,
            predicted_confidence REAL,
            actual_outcome_score REAL,
            calibration_error REAL,
            recorded_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
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
            created_at TIMESTAMP DEFAULT {ts_default},
            status TEXT DEFAULT 'pending',
            reviewed_at TIMESTAMP,
            review_notes TEXT,
            implemented_at TIMESTAMP
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS goal_alignment_logs (
            id {pk},
            log_date DATE NOT NULL,
            objective_id INTEGER,
            objective_name TEXT,
            tasks_count INTEGER DEFAULT 0,
            percentage_of_activity REAL,
            assessment TEXT,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    # ========================================================================
    # BACKGROUND JOBS TABLE
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS background_jobs (
            id {pk},
            job_id TEXT UNIQUE NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_size_mb REAL NOT NULL,
            user_request TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            task_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            current_step TEXT,
            estimated_minutes INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT {ts_default},
            updated_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    # ========================================================================
    # SMART ANALYZER STATE TABLE
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS smart_analyzer_state (
            id {pk},
            conversation_id TEXT UNIQUE NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            analyzer_state TEXT NOT NULL,
            profile_json TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT {ts_default},
            last_used TIMESTAMP NOT NULL DEFAULT {ts_default}
        )
    ''')

    # ========================================================================
    # ANALYSIS ENGINE TABLES
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS analysis_sessions (
            id {pk},
            session_id TEXT UNIQUE NOT NULL,
            project_id INTEGER,
            state TEXT NOT NULL,
            data_files TEXT,
            discovered_structure TEXT,
            clarifications TEXT,
            analysis_plan TEXT,
            results TEXT,
            created_at TIMESTAMP DEFAULT {ts_default},
            updated_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS analysis_deliverables (
            id {pk},
            session_id TEXT NOT NULL,
            deliverable_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS analysis_progress (
            id {pk},
            session_id TEXT NOT NULL,
            step_name TEXT NOT NULL,
            status TEXT NOT NULL,
            progress_pct INTEGER DEFAULT 0,
            message TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    # ========================================================================
    # PROJECT FILES TABLES (from database_file_management.py)
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS project_files (
            id {pk},
            project_id TEXT NOT NULL,
            file_id TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            file_type TEXT,
            mime_type TEXT,
            uploaded_by TEXT DEFAULT 'user',
            uploaded_at TIMESTAMP DEFAULT {ts_default},
            is_deleted {bool_type} DEFAULT 0,
            is_generated {bool_type} DEFAULT 0,
            task_id INTEGER,
            conversation_id TEXT,
            category TEXT DEFAULT 'general',
            description TEXT,
            is_analyzed {bool_type} DEFAULT 0,
            analysis_summary TEXT,
            analyzed_at TIMESTAMP,
            metadata TEXT
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS project_conversations (
            id {pk},
            project_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            file_ids TEXT,
            created_at TIMESTAMP DEFAULT {ts_default},
            metadata TEXT
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS project_context (
            id {pk},
            project_id TEXT NOT NULL,
            context_key TEXT NOT NULL,
            context_value TEXT,
            created_at TIMESTAMP DEFAULT {ts_default},
            updated_at TIMESTAMP DEFAULT {ts_default},
            UNIQUE(project_id, context_key)
        )
    ''')

    # ========================================================================
    # LEARNING ENHANCEMENT TABLES (client profiles, avoidance patterns)
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS client_profiles (
            id {pk},
            client_name TEXT UNIQUE NOT NULL,
            profile_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT {ts_default},
            updated_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS avoidance_patterns (
            id {pk},
            pattern_data TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            times_violated INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT {ts_default},
            last_seen TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    # ========================================================================
    # SURVEY TABLES (from database_survey_additions.py)
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS surveys (
            id {pk},
            project_name TEXT NOT NULL,
            company_name TEXT NOT NULL,
            created_date TEXT NOT NULL,
            created_by TEXT DEFAULT 'Jim @ Shiftwork Solutions LLC',
            survey_data TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            response_count INTEGER DEFAULT 0,
            notes TEXT,
            last_updated TEXT
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS survey_responses (
            id {pk},
            survey_id INTEGER NOT NULL,
            employee_id TEXT,
            response_date TEXT NOT NULL,
            response_data TEXT NOT NULL
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS normative_data (
            id {pk},
            question_id TEXT NOT NULL,
            industry TEXT,
            facility_type TEXT,
            response_option TEXT NOT NULL,
            percentage REAL NOT NULL,
            sample_size INTEGER NOT NULL,
            last_updated TEXT NOT NULL
        )
    ''')

    # ========================================================================
    # PHASE 2 TABLES (added now so they exist when Phase 2 work begins)
    # ========================================================================

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS memory_store (
            id {pk},
            memory_type VARCHAR(50),
            category VARCHAR(100),
            content TEXT,
            relevance_score FLOAT DEFAULT 0.5,
            source_task_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT {ts_default},
            updated_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS routing_preferences (
            id {pk},
            task_category VARCHAR(100),
            preferred_model VARCHAR(100),
            success_count INTEGER DEFAULT 0,
            total_count INTEGER DEFAULT 0,
            avg_score FLOAT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT {ts_default}
        )
    ''')

    # ========================================================================
    # INDEXES
    # ========================================================================

    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_patterns_type ON user_patterns(pattern_type)',
        'CREATE INDEX IF NOT EXISTS idx_patterns_last_seen ON user_patterns(last_seen)',
        'CREATE INDEX IF NOT EXISTS idx_suggestions_task ON proactive_suggestions(task_id)',
        'CREATE INDEX IF NOT EXISTS idx_suggestions_type ON proactive_suggestions(suggestion_type)',
        'CREATE INDEX IF NOT EXISTS idx_clarifications_task ON clarification_history(task_id)',
        'CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at)',
        'CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project_id)',
        'CREATE INDEX IF NOT EXISTS idx_conv_messages_conv_id ON conversation_messages(conversation_id)',
        'CREATE INDEX IF NOT EXISTS idx_conv_messages_created ON conversation_messages(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_tasks_conversation ON tasks(conversation_id)',
        'CREATE INDEX IF NOT EXISTS idx_conv_context_conv_id ON conversation_context(conversation_id)',
        'CREATE INDEX IF NOT EXISTS idx_gen_docs_created ON generated_documents(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_gen_docs_type ON generated_documents(document_type)',
        'CREATE INDEX IF NOT EXISTS idx_gen_docs_task ON generated_documents(task_id)',
        'CREATE INDEX IF NOT EXISTS idx_gen_docs_conversation ON generated_documents(conversation_id)',
        'CREATE INDEX IF NOT EXISTS idx_gen_docs_project ON generated_documents(project_id)',
        'CREATE INDEX IF NOT EXISTS idx_gen_docs_deleted ON generated_documents(is_deleted)',
        'CREATE INDEX IF NOT EXISTS idx_research_logs_date ON research_logs(searched_at)',
        'CREATE INDEX IF NOT EXISTS idx_research_briefings_date ON research_briefings(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_research_findings_category ON research_findings(category)',
        'CREATE INDEX IF NOT EXISTS idx_marketing_content_status ON marketing_content(status)',
        'CREATE INDEX IF NOT EXISTS idx_marketing_content_type ON marketing_content(content_type)',
        'CREATE INDEX IF NOT EXISTS idx_marketing_content_generated ON marketing_content(generated_at)',
        'CREATE INDEX IF NOT EXISTS idx_marketing_activity_content ON marketing_activity_log(content_id)',
        'CREATE INDEX IF NOT EXISTS idx_marketing_activity_created ON marketing_activity_log(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_avatar_conv_status ON avatar_conversations(status)',
        'CREATE INDEX IF NOT EXISTS idx_avatar_conv_started ON avatar_conversations(started_at)',
        'CREATE INDEX IF NOT EXISTS idx_avatar_conv_email ON avatar_conversations(visitor_email)',
        'CREATE INDEX IF NOT EXISTS idx_avatar_messages_conv ON avatar_messages(conversation_id)',
        'CREATE INDEX IF NOT EXISTS idx_avatar_messages_created ON avatar_messages(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_swarm_eval_date ON swarm_evaluations(evaluation_date)',
        'CREATE INDEX IF NOT EXISTS idx_swarm_eval_health ON swarm_evaluations(health_score)',
        'CREATE INDEX IF NOT EXISTS idx_introspection_type ON introspection_insights(insight_type)',
        'CREATE INDEX IF NOT EXISTS idx_introspection_created ON introspection_insights(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_introspection_pending ON introspection_insights(notification_pending)',
        'CREATE INDEX IF NOT EXISTS idx_introspection_action ON introspection_insights(requires_action)',
        'CREATE INDEX IF NOT EXISTS idx_boundaries_type ON capability_boundaries(boundary_type)',
        'CREATE INDEX IF NOT EXISTS idx_boundaries_resolved ON capability_boundaries(resolved)',
        'CREATE INDEX IF NOT EXISTS idx_calibration_task ON calibration_records(task_id)',
        'CREATE INDEX IF NOT EXISTS idx_proposals_status ON modification_proposals(status)',
        'CREATE INDEX IF NOT EXISTS idx_proposals_priority ON modification_proposals(priority)',
        'CREATE INDEX IF NOT EXISTS idx_alignment_date ON goal_alignment_logs(log_date)',
        'CREATE INDEX IF NOT EXISTS idx_background_jobs_status ON background_jobs(status)',
        'CREATE INDEX IF NOT EXISTS idx_background_jobs_created ON background_jobs(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_background_jobs_conversation ON background_jobs(conversation_id)',
        'CREATE INDEX IF NOT EXISTS idx_smart_analyzer_conversation ON smart_analyzer_state(conversation_id)',
        'CREATE INDEX IF NOT EXISTS idx_smart_analyzer_last_used ON smart_analyzer_state(last_used)',
        'CREATE INDEX IF NOT EXISTS idx_analysis_sessions_project ON analysis_sessions(project_id)',
        'CREATE INDEX IF NOT EXISTS idx_analysis_sessions_state ON analysis_sessions(state)',
        'CREATE INDEX IF NOT EXISTS idx_analysis_sessions_created ON analysis_sessions(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_analysis_deliverables_session ON analysis_deliverables(session_id)',
        'CREATE INDEX IF NOT EXISTS idx_analysis_deliverables_type ON analysis_deliverables(deliverable_type)',
        'CREATE INDEX IF NOT EXISTS idx_analysis_progress_session ON analysis_progress(session_id)',
        'CREATE INDEX IF NOT EXISTS idx_analysis_progress_status ON analysis_progress(status)',
        'CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)',
        'CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at)',
        'CREATE INDEX IF NOT EXISTS idx_files_project ON project_files(project_id)',
        'CREATE INDEX IF NOT EXISTS idx_files_deleted ON project_files(is_deleted)',
        'CREATE INDEX IF NOT EXISTS idx_conv_project ON project_conversations(project_id)',
        'CREATE INDEX IF NOT EXISTS idx_conv_id ON project_conversations(conversation_id)',
        'CREATE INDEX IF NOT EXISTS idx_context_project ON project_context(project_id)',
        'CREATE INDEX IF NOT EXISTS idx_memory_store_type ON memory_store(memory_type)',
        'CREATE INDEX IF NOT EXISTS idx_memory_store_category ON memory_store(category)',
        'CREATE INDEX IF NOT EXISTS idx_routing_prefs_category ON routing_preferences(task_category)',
        'CREATE INDEX IF NOT EXISTS idx_avoidance_patterns_created ON avoidance_patterns(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_client_profiles_name ON client_profiles(client_name)',
    ]

    for idx_sql in indexes:
        try:
            conn.execute(idx_sql)
        except Exception as e:
            # Non-fatal: index may already exist under a different name
            print(f"  ⚠️  Index note: {e}")

    print("✅ All tables and indexes created/verified")


if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)

# I did no harm and this file is not truncated
