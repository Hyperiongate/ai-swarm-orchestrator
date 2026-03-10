"""
AI SWARM ORCHESTRATOR - Main Application
Created: January 18, 2026
Last Updated: March 10, 2026 — Survey in a Box Phase 1: intake + admin blueprints registered

CHANGELOG:
- March 10, 2026: Survey in a Box Phase 1 — THREE CHANGES ONLY:
  1. MIGRATION: Added migration_002_survey_in_a_box.py call in STEP 1,
     immediately after migration_001_initial_schema.py. Creates three new
     tables: survey_clients, survey_projects, survey_project_history.
     Fully idempotent — safe to run on every startup.
  2. BLUEPRINT: Registered survey_intake_bp from routes/survey_intake.py.
     Adds GET /survey/start and POST /api/survey/intake/submit endpoints.
  3. BLUEPRINT: Registered survey_admin_bp from routes/survey_admin.py.
     Adds GET /survey/admin and all /api/survey/admin/* endpoints.
  Both registrations follow the identical try/except pattern used by all
  other blueprints. If the files are missing, startup continues normally.
  NO OTHER CHANGES. All existing routes, blueprints, features, and startup
  sequence are completely unchanged.

- March 08, 2026: Phase 3 Self-Awareness — CAPABILITIES MANIFEST WIRED IN
  THREE CHANGES ONLY — all other code is completely unchanged:
  1. BLUEPRINT: Registered capabilities_bp from routes/capabilities.py.
     Adds GET /api/capabilities, GET /api/capabilities/summary,
     POST /api/capabilities/refresh endpoints.
     Placed after the memory_bp registration block, before background_jobs_bp.
  2. STARTUP: After knowledge base initialization, calls
     generate_capabilities_manifest() once to warm the cache and logs
     the summary to startup output so Jim can verify detection is working.
     Wrapped in try/except — never blocks startup if it fails.
  3. HEALTH CHECK: Added 'capabilities_manifest' section to the /health
     response. Shows status, summary, manifest_length, cached flag,
     and URLs for the full manifest and refresh endpoints.
  NO OTHER CHANGES. All routes, blueprints, features, and startup sequence
  are completely unchanged.

- March 05, 2026: Phase 2A Memory Schema Fix
  * Added /api/admin/fix-memory-schema endpoint.
  * ROOT CAUSE: The memory_store table was created in Phase 1 with columns
    memory_key (NOT NULL) and memory_value (NOT NULL). Phase 2A added the
    correct columns (category, content, source_task_id, updated_at) via
    fix-memory-store, but did NOT remove the old NOT NULL columns.
    Every INSERT from memory_store.py failed with:
    "null value in column 'memory_key' violates not-null constraint"
  * FIX: New endpoint drops the 5 orphaned Phase 1 columns from memory_store:
    memory_key, memory_value, expires_at, access_count, last_accessed.
    Uses DROP COLUMN IF EXISTS — safe to run multiple times.
  * No other changes. All existing routes, blueprints, features unchanged.

- March 05, 2026: Phase 2A - Registered memory blueprint (routes/memory.py)
- March 05, 2026: Phase 1 Log Cleanup (Opus direction pre-Phase 2)
  * Removed 8 legacy SQLite-era migration try/except blocks from STEP 3.
    These scripts (migrate_projects_table, upgrade_database_sprint2,
    add_resource_searches_table, add_improvement_reports_table,
    add_conversation_context_table, add_user_profiles_table,
    add_workflow_tables, add_integration_logs_table) all used SQLite
    syntax (PRAGMA, AUTOINCREMENT) incompatible with PostgreSQL and
    printed errors on every startup. The real schema is fully managed
    by migrations/001_initial_schema.py (56 tables verified at startup).
    These legacy scripts are no longer needed.
  * Kept: add_blog_posts_table, add_missing_columns, fix_broken_tables
    - these three still perform real work on the PostgreSQL schema.
  * self_optimization_engine.py replaced with a Phase 4 stub so that
    routes/optimization.py registers cleanly without ImportError warning.
  * No functional changes to any routes, blueprints, or features.

- March 03, 2026: Phase 9b - FIX BROKEN TABLE SCHEMAS
  * Added fix_broken_tables() call in STEP 3 (after add_missing_columns)
  * Drops and recreates tables that have wrong column structures from
    the old migration (generated_documents, user_feedback,
    introspection_insights, conversations, tasks, etc.)
  * Safe to run every startup - checks before dropping

- March 03, 2026: SCHEMA MIGRATION
  * Added add_missing_columns() call in STEP 3 (legacy migrations)
  * Fixes three UndefinedColumn errors from deployment logs:
      - case_studies: problem_summary, solution_summary
      - blog_posts:   topic_display, url_slug, meta_description (+ 4 more)
      - projects:     project_id
  * No other changes - all routes, blueprints, and features unchanged

- March 02, 2026: POSTGRESQL MIGRATION
  * Added migration runner at the very top of startup sequence
  * migrations/001_initial_schema.py now runs BEFORE init_db() and ProjectManager
  * This ensures all tables exist before any blueprint or module tries to use them
  * Added database type reporting to health check
  * No other changes - all routes, blueprints, and features unchanged

- February 27, 2026: ADDED /api/admin/restore-knowledge ENDPOINT
- February 26, 2026: ADDED /api/admin/clear-knowledge-db ENDPOINT
- February 25, 2026: ADDED /api/admin/kb-diagnose ENDPOINT
- February 23, 2026: ADDED Blog Posts Table Migration
- February 22, 2026: RE-ENABLED Case Study Generator
- February 20, 2026: BUG FIX #1 - intelligence_bp name conflict
- February 20, 2026: BUG FIX #2 - conversation_learning import path
- February 18, 2026: FIXED NameError crash on startup
- February 18, 2026: BACKGROUND KB INIT
- February 5, 2026: INCREASED FILE UPLOAD LIMIT TO 100MB
- January 30, 2026: ADDED BULLETPROOF PROJECT MANAGEMENT

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Flask, render_template, jsonify, request
import os
from flask import send_from_directory

# Initialize Flask
app = Flask(__name__)

# ============================================================================
# CRITICAL FILE UPLOAD CONFIGURATION
# ============================================================================
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
print("File Upload Limit: 100MB (allows large project files)")

# CRITICAL: Configure session for schedule conversation memory
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-12345')
app.config['SESSION_TYPE'] = 'filesystem'

# ============================================================================
# STEP 1: RUN DATABASE MIGRATION FIRST - before anything else
# ============================================================================
print("=" * 60)
print("STEP 1: Running database migration...")
try:
    import importlib.util
    import os as _os
    _migration_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'migrations', 'migration_001_initial_schema.py')
    _spec = importlib.util.spec_from_file_location("migration_001_initial_schema", _migration_path)
    _migration_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_migration_module)
    _migration_module.run_migration()
    print("Database migration complete")
except Exception as e:
    print(f"CRITICAL: Database migration failed: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------------------------
# MIGRATION 002: Survey in a Box tables
# Added: March 10, 2026
# Creates survey_clients, survey_projects, survey_project_history.
# Fully idempotent — safe to run on every startup.
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu
    import os as _os2
    _m002_path = _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)),
                                'migrations', 'migration_002_survey_in_a_box.py')
    _spec002 = _ilu.spec_from_file_location("migration_002_survey_in_a_box", _m002_path)
    _mod002 = _ilu.module_from_spec(_spec002)
    _spec002.loader.exec_module(_mod002)
    _mod002.run_migration()
    print("Survey in a Box migration (002) complete")
except Exception as e:
    print(f"Survey in a Box migration (002) failed: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)

# ============================================================================
# STEP 2: Initialize database (delegates to migration, safe to call again)
# ============================================================================
from database import init_db
from database_survey_additions import add_surveys_table

init_db()

try:
    add_surveys_table()
    print("Survey tables initialized")
except Exception as e:
    print(f"Survey tables: {e}")

# ============================================================================
# STEP 3: RUN REMAINING LEGACY DATABASE MIGRATIONS
# Only migrations that still perform real work on the PostgreSQL schema.
# The 8 SQLite-era scripts (migrate_projects_table, upgrade_database_sprint2,
# add_resource_searches_table, add_improvement_reports_table,
# add_conversation_context_table, add_user_profiles_table,
# add_workflow_tables, add_integration_logs_table) have been removed.
# They used SQLite syntax (PRAGMA, AUTOINCREMENT) and printed errors on
# every startup. The real schema is managed by 001_initial_schema.py.
# ============================================================================
print("Running legacy database migrations...")

print("DEBUG: About to attempt blog_posts migration import...")
try:
    from add_blog_posts_table import add_blog_posts_table
    print("DEBUG: Import successful, calling function...")
    add_blog_posts_table()
    print("Blog Posts table migration complete!")
except ImportError as ie:
    print(f"Blog Posts migration IMPORT ERROR: {ie}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"Blog Posts migration failed: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------------------------
# ADD MISSING COLUMNS - fixes UndefinedColumn errors on case_studies,
# blog_posts, and projects tables (columns existed in code but not in DB)
# Added: March 03, 2026
# ----------------------------------------------------------------------------
try:
    from add_missing_columns import add_missing_columns
    add_missing_columns()
except Exception as e:
    print(f"Missing columns migration: {e}")

# ----------------------------------------------------------------------------
# FIX BROKEN TABLE SCHEMAS - Phase 9b
# Drops and recreates tables that have wrong column structures from the
# old migration. Safe to run every startup (checks before dropping).
# Added: March 03, 2026
# ----------------------------------------------------------------------------
try:
    from fix_broken_tables import fix_broken_tables
    fix_broken_tables()
except Exception as e:
    print(f"Fix broken tables: {e}")

print("Database migrations complete!")

# ============================================================================
# STEP 4: INITIALIZE PROJECT MANAGER (after all migrations)
# ============================================================================
print("Initializing Bulletproof Project Management...")
try:
    from database_file_management import get_project_manager
    pm = get_project_manager()
    app.config['PROJECT_MANAGER'] = pm
    print("Bulletproof Project Manager initialized")
except Exception as e:
    print(f"Project Manager initialization failed: {e}")

# ============================================================================
# INITIALIZE KNOWLEDGE BASE IN BACKGROUND THREAD
# ============================================================================
print("Initializing Project Knowledge Base...")
knowledge_base = None
try:
    from pathlib import Path
    from knowledge_integration import ProjectKnowledgeBase

    project_paths = ["project_files", "./project_files", "/mnt/project"]
    found_path = None

    for path in project_paths:
        if Path(path).exists() and Path(path).is_dir():
            file_count = len(list(Path(path).iterdir()))
            if file_count > 0:
                found_path = path
                print(f"Found directory: {path} ({file_count} files)")
                break

    if not found_path:
        print(f"No project files found. Checked: {project_paths}")
        print(f"Knowledge base features disabled until files are added")
    else:
        knowledge_base = ProjectKnowledgeBase(project_path=found_path)
        knowledge_base.initialize_background()
        print(f"Knowledge Base initializing in background (~30 seconds)...")
        print(f"App is ready to serve requests immediately.")

except Exception as e:
    print(f"Warning: Knowledge Base initialization failed: {e}")
    import traceback
    print(f"Traceback: {traceback.format_exc()}")
    knowledge_base = None

# Load optional modules
SCHEDULE_GENERATOR_AVAILABLE = False
try:
    from schedule_generator import get_pattern_generator
    SCHEDULE_GENERATOR_AVAILABLE = True
    schedule_gen = get_pattern_generator()
    print("Pattern-Based Schedule Generator loaded")
    app.config['SCHEDULE_GENERATOR_AVAILABLE'] = SCHEDULE_GENERATOR_AVAILABLE
    app.config['SCHEDULE_GENERATOR'] = schedule_gen
except ImportError:
    print("Schedule Generator module not found - schedule features disabled")
except Exception as e:
    print(f"Schedule Generator initialization failed: {e}")

OUTPUT_FORMATTER_AVAILABLE = False
try:
    from output_formatter import get_output_formatter
    OUTPUT_FORMATTER_AVAILABLE = True
    output_fmt = get_output_formatter()
    print("Output Formatter loaded")
    app.config['OUTPUT_FORMATTER_AVAILABLE'] = OUTPUT_FORMATTER_AVAILABLE
    app.config['OUTPUT_FORMATTER'] = output_fmt
except ImportError:
    print("Output Formatter module not found - formatting features disabled")
except Exception as e:
    print(f"Output Formatter initialization failed: {e}")

# ============================================================================
# PHASE 3: DEFERRED CAPABILITIES MANIFEST WARM
# The knowledge base initializes in a background thread (~30 seconds).
# We cannot warm the manifest immediately at startup because is_ready will
# be False until the KB thread completes. Instead we launch a daemon thread
# that polls until the KB is ready (up to 120 seconds), then generates the
# manifest with the correct KB stats. By the time the first user request
# arrives, the manifest is cached and correct.
# Updated: March 08, 2026 (Pass 2 — deferred warm replaces immediate warm)
# ============================================================================
print("Scheduling deferred capabilities manifest warm (waiting for KB ready)...")
try:
    import threading as _threading

    def _warm_manifest_when_kb_ready(kb_ref, max_wait=120):
        """
        Background thread: poll until KB is ready, then warm the manifest.
        Falls back to generating without KB stats if KB never becomes ready.
        """
        import time as _time
        deadline = _time.time() + max_wait
        while _time.time() < deadline:
            if kb_ref is not None and getattr(kb_ref, 'is_ready', False):
                break
            _time.sleep(2)

        try:
            from intelligence.capabilities_manifest import (
                generate_capabilities_manifest,
                get_manifest_summary,
            )
            _kb_stats = None
            if kb_ref is not None and getattr(kb_ref, 'is_ready', False):
                _kb_stats = {
                    'doc_count': len(getattr(kb_ref, 'knowledge_index', {})),
                    'is_ready': True,
                }
            generate_capabilities_manifest(kb_stats=_kb_stats)
            _summary = get_manifest_summary()
            print(f"✅ Capabilities manifest ready: {_summary}")
        except Exception as _e:
            print(f"⚠️ Deferred manifest warm failed (non-fatal): {_e}")

    _warm_thread = _threading.Thread(
        target=_warm_manifest_when_kb_ready,
        args=(knowledge_base,),
        daemon=True,
        name='manifest-warmer',
    )
    _warm_thread.start()
    print("Manifest warmer thread started — will log 'Capabilities manifest ready' when KB is loaded.")
except Exception as e:
    print(f"Capabilities manifest warm thread failed to start (non-fatal): {e}")

# Basic routes
@app.route('/')
def index():
    """Main interface"""
    return render_template('index.html')

# =============================================================================
# DOWNLOAD ROUTE FOR DESKTOP APPS
# =============================================================================
@app.route('/downloads/<path:filename>')
def download_file(filename):
    """Serve downloadable files from the /downloads directory."""
    try:
        allowed_extensions = {'.pyw', '.py', '.txt', '.pdf'}
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in allowed_extensions:
            return "File type not allowed", 403
        downloads_dir = os.path.join(app.root_path, 'downloads')
        return send_from_directory(downloads_dir, filename, as_attachment=True)
    except Exception as e:
        print(f"Error serving download file: {str(e)}")
        return "File not found", 404

@app.route('/api/admin/run-missing-tables-migration', methods=['GET'])
def run_missing_tables_migration():
    """One-time migration to add missing tables. Run once after deploy."""
    try:
        from migrate_missing_tables import run_migration
        from io import StringIO
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()
        results = run_migration()
        sys.stdout = old_stdout
        output = captured.getvalue()
        return jsonify({'success': results['success'], 'output': output, 'results': results})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/workflow')
def workflow():
    """Workflow interface"""
    return render_template('index_workflow.html')

@app.route('/memory-admin')
def memory_admin():
    return render_template('memory_admin.html')

@app.route('/api/admin/migrate-storage', methods=['GET', 'POST'])
def migrate_storage():
    """One-time migration endpoint to move projects from /tmp to persistent storage."""
    try:
        import migrate_project_storage
        from io import StringIO
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        migrate_project_storage.migrate_project_storage()
        sys.stdout = old_stdout
        output = captured_output.getvalue()
        return jsonify({'success': True, 'message': 'Migration complete!', 'output': output})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/admin/bootstrap-knowledge', methods=['GET'])
def bootstrap_knowledge_endpoint():
    """One-time endpoint to bootstrap knowledge base."""
    try:
        import bootstrap_knowledge
        from io import StringIO
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        result = bootstrap_knowledge.bootstrap_knowledge_base(project_path='./project_files')
        sys.stdout = old_stdout
        output = captured_output.getvalue()
        return jsonify({
            'success': True,
            'message': 'Bootstrap complete!',
            'output': output,
            'results': {
                'successful': len(result['success']),
                'already_ingested': len(result['already_ingested']),
                'failed': len(result['failed'])
            }
        })
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/admin/list-project-files', methods=['GET'])
def list_project_files():
    """Diagnostic endpoint to see what files are actually accessible."""
    from pathlib import Path
    results = {}
    locations_to_check = [
        '/mnt/project',
        '/mnt/project/project_files',
        'project_files',
        './project_files',
        os.path.join(os.getcwd(), 'project_files')
    ]
    for location in locations_to_check:
        try:
            path = Path(location)
            if path.exists():
                if path.is_dir():
                    files = [f.name for f in path.iterdir() if f.is_file()]
                    results[str(location)] = {
                        'exists': True, 'is_dir': True,
                        'file_count': len(files), 'files': files[:10],
                        'total_files': len(files)
                    }
                else:
                    results[str(location)] = {'exists': True, 'is_dir': False, 'note': 'This is a file, not a directory'}
            else:
                results[str(location)] = {'exists': False}
        except Exception as e:
            results[str(location)] = {'error': str(e)}
    results['current_working_directory'] = os.getcwd()
    return jsonify({'success': True, 'locations_checked': results})

# ============================================================================
# KB DIAGNOSE ENDPOINT
# ============================================================================
@app.route('/api/admin/kb-diagnose', methods=['GET'])
def kb_diagnose():
    """Real-time knowledge base diagnostic endpoint."""
    if knowledge_base is None:
        return jsonify({
            'success': False,
            'error': 'Knowledge base object was never created. Check startup logs.',
            'knowledge_base_initialized': False
        }), 503
    try:
        status = knowledge_base.get_index_status()
        return jsonify({'success': True, 'knowledge_base_initialized': True, **status})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}), 500

# ============================================================================
# CLEAR KNOWLEDGE DB ENDPOINT
# ============================================================================
@app.route('/api/admin/clear-knowledge-db', methods=['GET'])
def clear_knowledge_db():
    """Wipe all uploaded knowledge documents, learned patterns, and ingestion log."""
    try:
        import sqlite3
        from document_ingestion_engine import get_document_ingestor
        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        cursor = db.cursor()
        cursor.execute('DELETE FROM knowledge_extracts')
        extracts_deleted = cursor.rowcount
        cursor.execute('DELETE FROM learned_patterns')
        patterns_deleted = cursor.rowcount
        cursor.execute('DELETE FROM ingestion_log')
        log_deleted = cursor.rowcount
        db.commit()
        db.close()
        return jsonify({
            'success': True,
            'message': 'Knowledge base cleared. Ready for fresh uploads.',
            'deleted': {
                'knowledge_extracts': extracts_deleted,
                'learned_patterns': patterns_deleted,
                'ingestion_log': log_deleted
            }
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# ============================================================================
# RESTORE KNOWLEDGE ENDPOINT
# ============================================================================
@app.route('/api/admin/restore-knowledge', methods=['POST'])
def restore_knowledge():
    """Restore the knowledge base from a JSON export file."""
    try:
        if 'export_file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No export_file field in request. POST multipart/form-data with field name export_file.'
            }), 400

        export_file = request.files['export_file']

        if not export_file.filename.endswith('.json'):
            return jsonify({
                'success': False,
                'error': f'File must be a .json export file. Got: {export_file.filename}'
            }), 400

        import json as json_module
        try:
            export_data = json_module.load(export_file)
        except Exception as parse_err:
            return jsonify({
                'success': False,
                'error': f'Could not parse JSON file: {str(parse_err)}'
            }), 400

        from knowledge_restore import restore_knowledge_from_export
        result = restore_knowledge_from_export(export_data)
        status_code = 200 if result['success'] else 207
        return jsonify(result), status_code

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/admin/fix-patterns-table', methods=['GET'])
def fix_patterns_table():
    """One-time migration to fix learned_patterns table."""
    try:
        import migrate_learned_patterns
        from io import StringIO
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        migrate_learned_patterns.migrate_learned_patterns()
        sys.stdout = old_stdout
        output = captured_output.getvalue()
        return jsonify({'success': True, 'message': 'Migration complete!', 'output': output})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/admin/diagnose-databases', methods=['GET'])
def diagnose_databases():
    """Find all swarm_intelligence.db files and show their contents."""
    import sqlite3
    from pathlib import Path
    results = {}
    search_paths = ['.', '/opt/render/project/src', '/mnt/project', '/tmp']
    for search_path in search_paths:
        try:
            path = Path(search_path)
            if path.exists():
                for db_file in path.rglob('swarm_intelligence.db'):
                    db_path = str(db_file.absolute())
                    try:
                        db = sqlite3.connect(db_path)
                        cursor = db.cursor()
                        cursor.execute('SELECT COUNT(*) FROM knowledge_extracts')
                        doc_count = cursor.fetchone()[0]
                        file_size = os.path.getsize(db_path)
                        db.close()
                        results[db_path] = {
                            'exists': True, 'documents': doc_count,
                            'size_bytes': file_size,
                            'size_mb': round(file_size / 1024 / 1024, 2)
                        }
                    except Exception as e:
                        results[db_path] = {'exists': True, 'error': str(e)}
        except Exception:
            pass
    try:
        from document_ingestion_engine import get_document_ingestor
        ingestor = get_document_ingestor()
        results['api_uses_path'] = ingestor.db_path
    except Exception:
        results['api_uses_path'] = 'error_loading'
    results['current_directory'] = os.getcwd()
    return jsonify({'success': True, 'databases_found': results})

@app.route('/survey')
def survey():
    """Survey builder interface"""
    return render_template('survey.html')

@app.route('/api/patterns', methods=['GET'])
def get_user_patterns():
    """API endpoint to retrieve user patterns for dashboard"""
    try:
        from enhanced_intelligence import EnhancedIntelligence
        intelligence = EnhancedIntelligence()
        patterns = intelligence.get_all_patterns()
        return jsonify({'success': True, 'patterns': patterns})
    except Exception as e:
        import traceback
        print(f"Error fetching patterns: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    from config import ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY, GOOGLE_API_KEY
    from db_engine import get_db_type

    kb_ready = knowledge_base.is_ready if knowledge_base else False
    kb_doc_count = len(knowledge_base.knowledge_index) if knowledge_base else 0
    kb_status = 'initialized' if kb_ready and kb_doc_count > 0 else ('initializing' if knowledge_base else 'not_initialized')

    research_status = 'disabled'
    try:
        from research_agent import get_research_agent
        ra = get_research_agent()
        research_status = 'enabled' if ra.is_available else 'api_key_missing'
    except Exception:
        research_status = 'not_installed'

    alert_status = 'disabled'
    alert_email_enabled = False
    try:
        from alert_system import get_alert_manager, ENABLE_EMAIL_ALERTS
        am = get_alert_manager()
        alert_status = 'enabled'
        alert_email_enabled = ENABLE_EMAIL_ALERTS
    except Exception:
        alert_status = 'not_installed'

    intelligence_status = 'disabled'
    intelligence_companies = 0
    try:
        from intelligence import get_lead_manager, INDUSTRY_CATEGORIES
        lm = get_lead_manager()
        intelligence_status = 'enabled'
        intelligence_companies = sum(len(c) for c in INDUSTRY_CATEGORIES.values())
    except Exception:
        intelligence_status = 'not_installed'

    marketing_status = 'disabled'
    try:
        from content_marketing_engine import get_content_engine
        ce = get_content_engine()
        marketing_status = 'enabled'
    except Exception:
        marketing_status = 'not_installed'

    avatar_status = 'disabled'
    try:
        from avatar_consultation_engine import get_avatar_engine
        ae = get_avatar_engine()
        avatar_status = 'enabled'
    except Exception:
        avatar_status = 'not_installed'

    evaluation_status = 'disabled'
    last_evaluation = None
    try:
        from swarm_self_evaluation import get_swarm_evaluator
        evaluator = get_swarm_evaluator()
        evaluation_status = 'enabled'
        last_eval = evaluator.get_latest_evaluation()
        if last_eval:
            last_evaluation = {
                'date': last_eval.get('evaluation_date'),
                'health_score': last_eval.get('health_score'),
                'trend': last_eval.get('trend')
            }
    except Exception:
        evaluation_status = 'not_installed'

    introspection_status = 'disabled'
    last_introspection = None
    try:
        from introspection import get_introspection_engine, check_introspection_notifications
        intro_engine = get_introspection_engine()
        introspection_status = 'enabled'
        latest_intro = intro_engine.get_latest_introspection()
        if latest_intro:
            last_introspection = {
                'id': latest_intro.get('id'),
                'created_at': latest_intro.get('created_at'),
                'health_score': int(latest_intro.get('confidence_score', 0) * 100)
            }
        notification = check_introspection_notifications()
        if notification.get('has_notification'):
            introspection_status = 'enabled_with_notification'
    except Exception:
        introspection_status = 'not_installed'

    manual_generator_status = 'disabled'
    try:
        from implementation_manual_generator import get_manuals_dashboard
        dashboard = get_manuals_dashboard()
        manual_generator_status = 'enabled'
    except Exception:
        manual_generator_status = 'not_installed'

    project_management_status = 'disabled'
    project_count = 0
    try:
        from database_file_management import get_project_manager
        pm = get_project_manager()
        projects = pm.list_projects(status='all', limit=1000)
        project_count = len(projects)
        project_management_status = 'enabled'
    except Exception:
        project_management_status = 'not_installed'

    case_studies_status = 'disabled'
    try:
        from case_study_generator import INDUSTRY_DISPLAY_NAMES
        case_studies_status = 'enabled'
    except Exception:
        case_studies_status = 'not_installed'

    blog_posts_status = 'disabled'
    try:
        from blog_post_generator import BLOG_TOPICS
        blog_posts_status = 'enabled'
    except Exception:
        blog_posts_status = 'not_installed'

    # =========================================================================
    # PHASE 3: CAPABILITIES MANIFEST STATUS
    # Added: March 08, 2026
    # =========================================================================
    capabilities_manifest_status = {}
    try:
        from intelligence.capabilities_manifest import get_manifest_summary, get_manifest_metadata
        caps_summary = get_manifest_summary()
        caps_meta    = get_manifest_metadata()
        capabilities_manifest_status = {
            'status':          'active',
            'summary':         caps_summary,
            'manifest_length': caps_meta.get('manifest_length', 0),
            'cached':          caps_meta.get('cached', False),
            'refresh_url':     '/api/capabilities/refresh',
            'full_url':        '/api/capabilities',
        }
    except Exception as e:
        capabilities_manifest_status = {
            'status': 'error',
            'error':  str(e),
        }

    return jsonify({
        'status': 'healthy',
        'version': 'Survey in a Box Phase 1 Mar10 + Phase 3 Capabilities Manifest Mar08 + Phase 2A Memory Schema Fix Mar05 + Phase 2A Memory Mar05 + Phase 1 Log Cleanup Mar05 + Phase 9b Schema Fix Mar03 + PostgreSQL Migration Mar02 + Sprint 3 + Research + Alerts + Intelligence + Marketing + Avatars + Evaluation + Pattern Schedules + Manual Generator + LinkedIn Poster + Bulletproof Projects + 100MB Upload + Background KB',
        'database': {
            'type': get_db_type(),
            'backend': 'PostgreSQL (persistent)' if get_db_type() == 'postgresql' else 'SQLite (local dev)'
        },
        'file_upload_limit': '100MB',
        'storage_path': '/mnt/project/swarm_projects/',
        'orchestrators': {
            'sonnet': 'configured' if ANTHROPIC_API_KEY else 'missing',
            'opus': 'configured' if ANTHROPIC_API_KEY else 'missing'
        },
        'specialists': {
            'gpt4': 'configured' if OPENAI_API_KEY else 'missing',
            'deepseek': 'configured' if DEEPSEEK_API_KEY else 'missing',
            'gemini': 'configured' if GOOGLE_API_KEY else 'missing'
        },
        'knowledge_base': {
            'status': kb_status,
            'documents_indexed': kb_doc_count,
            'initialization_complete': kb_ready,
            'diagnose_url': '/api/admin/kb-diagnose'
        },
        'schedule_generator': {
            'status': 'enabled' if SCHEDULE_GENERATOR_AVAILABLE else 'disabled',
            'type': 'pattern_based_conversational'
        },
        'output_formatter': {
            'status': 'enabled' if OUTPUT_FORMATTER_AVAILABLE else 'disabled'
        },
        'research_agent': {'status': research_status},
        'alert_system': {'status': alert_status, 'email_enabled': alert_email_enabled},
        'intelligence_dashboard': {
            'status': intelligence_status,
            'past_clients_indexed': intelligence_companies
        },
        'content_marketing': {'status': marketing_status},
        'avatar_consultation': {'status': avatar_status, 'avatars': ['david', 'sarah']},
        'swarm_evaluation': {'status': evaluation_status, 'last_evaluation': last_evaluation},
        'introspection_layer': {
            'status': introspection_status,
            'last_introspection': last_introspection
        },
        'manual_generator': {'status': manual_generator_status},
        'project_management': {
            'status': project_management_status,
            'total_projects': project_count
        },
        'case_study_generator': {
            'status': case_studies_status,
            'features': ['ai_generation', 'seo_optimized', 'word_doc_download', 'saved_library', '16_industries_supported']
        },
        'blog_post_generator': {
            'status': blog_posts_status,
            'features': ['ai_generation', 'seo_optimized', 'conversational_tone', 'word_doc_download', 'saved_library', '12_topics']
        },
        'knowledge_restore': {
            'status': 'enabled',
            'endpoint': '/api/admin/restore-knowledge',
            'method': 'POST multipart/form-data, field: export_file'
        },
        'capabilities_manifest': capabilities_manifest_status,
        'survey_in_a_box': {
            'status': 'enabled',
            'intake_form': '/survey/start',
            'admin_dashboard': '/survey/admin',
            'phase': '1 - Client Onboarding'
        },
    })

# Register blueprints
from routes.core import core_bp
from routes.analysis import analysis_bp
from routes.survey import survey_bp
app.register_blueprint(core_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(survey_bp)

from routes.orchestration_handler import orchestration_bp
app.register_blueprint(orchestration_bp)
print("Orchestration Handler API registered")

print("DEBUG: About to import bulletproof project routes...")
try:
    from routes.projects_bulletproof import projects_bp
    app.register_blueprint(projects_bp)
    print("Bulletproof Project Management API registered")
except ImportError as e:
    print(f"IMPORT ERROR: Bulletproof Project Management routes not found: {e}")
except Exception as e:
    print(f"EXCEPTION: Bulletproof Project Management registration failed: {e}")

try:
    from routes.voice import voice_bp, register_voice_websocket
    app.register_blueprint(voice_bp)
    register_voice_websocket(app)
    print("Voice Control WebSocket registered")
except ImportError as e:
    print(f"Voice Control routes not found: {e}")
except Exception as e:
    print(f"Voice Control registration failed: {e}")

try:
    from routes.research import research_bp
    app.register_blueprint(research_bp)
    print("Research Agent API registered")
except ImportError:
    print("Research Agent routes not found - research features disabled")
except Exception as e:
    print(f"Research Agent registration failed: {e}")

try:
    from routes.alerts import alerts_bp
    app.register_blueprint(alerts_bp)
    print("Alert System API registered")
except ImportError:
    print("Alert System routes not found - alert features disabled")
except Exception as e:
    print(f"Alert System registration failed: {e}")

try:
    from routes.intelligence import intelligence_bp
    app.register_blueprint(intelligence_bp)
    print("Intelligence Dashboard API registered")
except ImportError as e:
    print(f"Intelligence Dashboard routes not found: {e}")
except Exception as e:
    print(f"Intelligence Dashboard registration failed: {e}")

try:
    from routes.marketing import marketing_bp
    app.register_blueprint(marketing_bp)
    print("Content Marketing Engine API registered")
except ImportError as e:
    print(f"Content Marketing Engine routes not found: {e}")
except Exception as e:
    print(f"Content Marketing Engine registration failed: {e}")

try:
    from routes.avatar import avatar_bp
    app.register_blueprint(avatar_bp)
    print("Avatar Consultation System API registered")
except ImportError as e:
    print(f"Avatar Consultation routes not found: {e}")
except Exception as e:
    print(f"Avatar Consultation registration failed: {e}")

try:
    from routes.evaluation import evaluation_bp
    app.register_blueprint(evaluation_bp)
    print("Swarm Self-Evaluation API registered")
except ImportError as e:
    print(f"Swarm Self-Evaluation routes not found: {e}")
except Exception as e:
    print(f"Swarm Self-Evaluation registration failed: {e}")

try:
    from routes.introspection import introspection_bp
    app.register_blueprint(introspection_bp)
    print("Introspection Layer API registered")
except ImportError as e:
    print(f"Introspection Layer routes not found: {e}")
except Exception as e:
    print(f"Introspection Layer registration failed: {e}")

try:
    from routes.manuals import manuals_bp
    app.register_blueprint(manuals_bp)
    print("Implementation Manual Generator API registered")
except ImportError as e:
    print(f"Implementation Manual Generator routes not found: {e}")
except Exception as e:
    print(f"Implementation Manual Generator registration failed: {e}")

try:
    from routes.learning import learning_bp
    app.register_blueprint(learning_bp)
    print("Adaptive Learning Engine API registered")
except ImportError as e:
    print(f"Adaptive Learning Engine routes not found: {e}")
except Exception as e:
    print(f"Adaptive Learning Engine registration failed: {e}")

try:
    from routes.predictive import predictive_bp
    app.register_blueprint(predictive_bp)
    print("Predictive Intelligence API registered")
except ImportError as e:
    print(f"Predictive Intelligence routes not found: {e}")
except Exception as e:
    print(f"Predictive Intelligence registration failed: {e}")

try:
    from routes.optimization import optimization_bp
    app.register_blueprint(optimization_bp)
    print("Self-Optimization Engine API registered")
except ImportError as e:
    print(f"Self-Optimization Engine routes not found: {e}")
except Exception as e:
    print(f"Self-Optimization Engine registration failed: {e}")

try:
    from routes.ingest import ingest_bp
    app.register_blueprint(ingest_bp)
    print("Knowledge Ingestion API registered")
except ImportError as e:
    print(f"Knowledge Ingestion routes not found: {e}")
except Exception as e:
    print(f"Knowledge Ingestion registration failed: {e}")

try:
    from conversation_learning import learning_bp as conv_learning_bp
    app.register_blueprint(conv_learning_bp)
    print("Unified Conversation Learning API registered")
except ImportError as e:
    print(f"Conversation Learning routes not found: {e}")
except Exception as e:
    print(f"Conversation Learning registration failed: {e}")

try:
    from routes.pattern_recognition import pattern_bp
    app.register_blueprint(pattern_bp)
    print("Pattern Recognition API registered")
except ImportError as e:
    print(f"Pattern Recognition routes not found: {e}")
except Exception as e:
    print(f"Pattern Recognition registration failed: {e}")

try:
    from routes.phase1_intelligence import intelligence_bp as phase1_intelligence_bp
    app.register_blueprint(phase1_intelligence_bp, name='phase1_intelligence')
    print("Phase 1 Intelligence API registered")
except ImportError as e:
    print(f"Phase 1 Intelligence routes not found: {e}")
except Exception as e:
    print(f"Phase 1 Intelligence registration failed: {e}")

try:
    from routes.case_studies import case_studies_bp
    app.register_blueprint(case_studies_bp)
    print("Case Study Generator API registered")
except ImportError as e:
    print(f"Case Study Generator routes not found: {e}")
except Exception as e:
    print(f"Case Study Generator registration failed: {e}")

try:
    from routes.blog_posts import blog_posts_bp
    app.register_blueprint(blog_posts_bp)
    print("Blog Post Generator API registered")
except ImportError as e:
    print(f"Blog Post Generator routes not found: {e}")
except Exception as e:
    print(f"Blog Post Generator registration failed: {e}")

# ----------------------------------------------------------------------------
# Phase 2A: Memory System API
# Provides /api/memory/health, /api/memory/stats, /api/memory/recent,
# /api/memory/search endpoints. Safe to deploy before memory package exists
# - if routes/memory.py is missing, this block silently skips.
# Added: March 05, 2026
# ----------------------------------------------------------------------------
try:
    from routes.memory import memory_bp
    app.register_blueprint(memory_bp)
    print("Phase 2A Memory System API registered")
except ImportError as e:
    print(f"Memory System routes not found: {e}")
except Exception as e:
    print(f"Memory System registration failed: {e}")

# ----------------------------------------------------------------------------
# Phase 3: Capabilities Manifest API
# Provides GET /api/capabilities, GET /api/capabilities/summary,
# POST /api/capabilities/refresh endpoints.
# Added: March 08, 2026
# ----------------------------------------------------------------------------
try:
    from routes.capabilities import capabilities_bp
    app.register_blueprint(capabilities_bp)
    print("Phase 3 Capabilities Manifest API registered")
except ImportError as e:
    print(f"Capabilities Manifest routes not found: {e}")
except Exception as e:
    print(f"Capabilities Manifest registration failed: {e}")

# ----------------------------------------------------------------------------
# Survey in a Box: Intake Form API
# Provides GET /survey/start (public form) and POST /api/survey/intake/submit.
# Added: March 10, 2026
# ----------------------------------------------------------------------------
try:
    from routes.survey_intake import survey_intake_bp
    app.register_blueprint(survey_intake_bp)
    print("Survey in a Box Intake API registered")
except ImportError as e:
    print(f"Survey Intake routes not found: {e}")
except Exception as e:
    print(f"Survey Intake registration failed: {e}")

# ----------------------------------------------------------------------------
# Survey in a Box: Admin Dashboard API
# Provides GET /survey/admin and all /api/survey/admin/* endpoints.
# Added: March 10, 2026
# ----------------------------------------------------------------------------
try:
    from routes.survey_admin import survey_admin_bp
    app.register_blueprint(survey_admin_bp)
    print("Survey in a Box Admin API registered")
except ImportError as e:
    print(f"Survey Admin routes not found: {e}")
except Exception as e:
    print(f"Survey Admin registration failed: {e}")

try:
    from routes.background_jobs import background_jobs_bp
    app.register_blueprint(background_jobs_bp)
    print("Background File Processor API registered")
except ImportError as e:
    print(f"Background File Processor routes not found: {e}")
except Exception as e:
    print(f"Background File Processor registration failed: {e}")

try:
    from knowledge_backup_routes import knowledge_backup_bp
    app.register_blueprint(knowledge_backup_bp)
    print("Knowledge Backup System API registered")
except ImportError as e:
    print("Knowledge Backup: module not enabled (knowledge_backup_system not installed)")
except Exception as e:
    print(f"Knowledge Backup registration failed: {e}")

@app.route('/knowledge')
def knowledge_management():
    """Knowledge Management interface - Shoulders of Giants system"""
    return render_template('knowledge_management.html')

try:
    from project_dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)
    print("Project Dashboard API registered")
except ImportError:
    print("Project Dashboard not found")

try:
    from analytics_engine import analytics_bp
    app.register_blueprint(analytics_bp)
    print("Analytics API registered")
except ImportError:
    print("Analytics Engine not found")

try:
    from workflow_engine import workflow_bp
    app.register_blueprint(workflow_bp)
    print("Workflow Engine API registered")
except ImportError:
    print("Workflow Engine not found")

try:
    from integration_hub import integration_bp
    app.register_blueprint(integration_bp)
    print("Integration Hub API registered")
except ImportError:
    print("Integration Hub not found")

# ============================================================================
# ADMIN: FIX MEMORY STORE COLUMNS (Phase 2A - Add new columns)
# ============================================================================
@app.route('/api/admin/fix-memory-store', methods=['GET'])
def fix_memory_store():
    """One-time fix: add Phase 2A columns to memory_store table."""
    try:
        from db_engine import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        results = []
        columns = [
            ("category",       "TEXT DEFAULT 'general'"),
            ("content",        "TEXT DEFAULT ''"),
            ("source_task_id", "INTEGER"),
            ("updated_at",     "TIMESTAMP DEFAULT NOW()"),
        ]
        for col_name, col_def in columns:
            try:
                cursor.execute(
                    f"ALTER TABLE memory_store ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
                )
                results.append(f"OK: {col_name}")
            except Exception as e:
                results.append(f"SKIP: {col_name} — {e}")
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}), 500

# ============================================================================
# ADMIN: FIX MEMORY SCHEMA (Phase 2A - Drop orphaned Phase 1 columns)
# ============================================================================
@app.route('/api/admin/fix-memory-schema', methods=['GET'])
def fix_memory_schema():
    """
    One-time migration: drop Phase 1 orphan columns from memory_store.
    Run once after deploying this update. Safe to run multiple times.
    """
    try:
        from db_engine import get_db_connection
        results = []
        orphan_columns = [
            'memory_key',
            'memory_value',
            'expires_at',
            'access_count',
            'last_accessed',
        ]
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'memory_store'
                ORDER BY ordinal_position
            """)
            before_cols = [
                {
                    'column': r['column_name'],
                    'type': r['data_type'],
                    'nullable': r['is_nullable']
                }
                for r in cursor.fetchall()
            ]

            for col in orphan_columns:
                try:
                    cursor.execute(
                        f"ALTER TABLE memory_store DROP COLUMN IF EXISTS {col}"
                    )
                    results.append(f"DROPPED: {col}")
                except Exception as col_err:
                    results.append(f"ERROR dropping {col}: {col_err}")

            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'memory_store'
                ORDER BY ordinal_position
            """)
            after_cols = [
                {
                    'column': r['column_name'],
                    'type': r['data_type'],
                    'nullable': r['is_nullable']
                }
                for r in cursor.fetchall()
            ]

        return jsonify({
            'success': True,
            'message': (
                'Phase 1 orphan columns removed. '
                'Memory system should now store memories correctly.'
            ),
            'operations': results,
            'schema_before': before_cols,
            'schema_after': after_cols,
            'next_step': (
                'Send a message to /api/orchestrate, '
                'then check /api/memory/recent to confirm memories are being stored.'
            )
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)

# I did no harm and this file is not truncated
