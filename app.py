"""
AI SWARM ORCHESTRATOR - Main Application
Created: January 18, 2026
Last Updated: June 12, 2026 — Assessment AI Proxy (server-side Anthropic calls for the Shiftwork Operations Assessment)

CHANGELOG:
- June 12, 2026: ASSESSMENT AI PROXY — TWO CHANGES ONLY:
  1. BLUEPRINT: Registered assessment_ai_bp from routes/assessment_ai.py.
     Placed immediately AFTER the assessment_pdf_bp registration block.
     Provides POST /api/assessment/t1-commentary and
     POST /api/assessment/t2-evaluate — server-side Anthropic API calls
     for the Shiftwork Operations Assessment page. Fixes the launch-day
     bug where the page called api.anthropic.com directly from the
     visitor's browser with no API key (every call failed and the page
     silently used its fallbacks). Prompts are now built server-side,
     which protects the prompt strategy from page-source inspection and
     prevents the API key from being used as an open proxy. CORS locked
     to shift-work.com. Uses the existing ANTHROPIC_API_KEY env var.
  2. HEALTH CHECK: Updated version string and added 'assessment_ai'
     section.
  NO OTHER CHANGES. Rule 1 (do no harm) preserved.

- May 20, 2026: KNOWLEDGE SEARCH ENDPOINT SUPPORT — ONE CHANGE ONLY:
  1. KB SHARING: Added a single line that stores the existing knowledge_base
     instance in app.config['KNOWLEDGE_BASE'] immediately after it is created.
     This lets the new /api/knowledge/search endpoint in routes/ingest.py read
     the same singleton instance — avoiding creation of a second, duplicate
     knowledge base. The line is additive only. If knowledge_base is None
     (initialization failed), app.config['KNOWLEDGE_BASE'] is set to None
     and the search endpoint will return a graceful "KB not available"
     response — no crashes.
  NO OTHER CHANGES. All migrations, blueprints, routes, helper code, and
  the entire startup sequence are completely untouched. Rule 1 (do no harm)
  preserved.

- May 11, 2026: Part Time Tracker Lite — Phase 3 — see prior entry for details.

- May 04, 2026: Part Time Tracker Lite — Phase 2 fixes — THREE CHANGES ONLY:
  1. MIGRATION: Added migration_010_ptt_phase2.py call in STEP 1,
     immediately after migration_009_ptt.py. Adds approved_by,
     approved_at, rejected_at, rejection_reason columns to ptt_worker.
     Fully idempotent.
  2. BLUEPRINT: Registered ptt_worker_intake_bp from
     routes/ptt_worker_intake.py. Placed immediately AFTER the
     ptt_hr_bp registration block. Provides public GET /ptt/apply/<slug>
     and POST /api/ptt/apply/<slug> endpoints (no auth required).
  3. DEV ENDPOINTS: Added two development-only admin endpoints:
     POST /api/ptt/dev/reset-company — wipe all ptt_* data for a
       company by email (for clean test resets).
     POST /api/ptt/dev/reseed-skills — replace skills for an existing
       company with the 14 Opus-specified skills.
  4. HEALTH CHECK: Updated version string and part_time_tracker section.
  NO OTHER CHANGES. Rule 1 (do no harm) preserved.

- May 01, 2026: Part Time Tracker Lite — Phase 1 — TWO CHANGES ONLY:
  1. MIGRATION: Added migration_009_ptt.py call in STEP 1.
  2. BLUEPRINT: Registered ptt_hr_bp from routes/ptt_hr.py.
  NO OTHER CHANGES. Rule 1 (do no harm) preserved.

- April 28, 2026: Site Events Tracking — TWO CHANGES ONLY:
  1. MIGRATION: Added migration_008_site_events.py call in STEP 1,
     immediately after migration_007_security.py. Creates site_events
     table for shift-work.com visitor event tracking. Stores all 10
     event types captured by /js/event-tracker.js. Fully idempotent.
  2. BLUEPRINT: Registered site_events_bp from routes/site_events.py.
     Placed immediately AFTER the assessment_pdf_bp registration block.
     Provides POST /api/events/log (CORS-enabled for shift-work.com),
     GET /api/events/summary, GET /api/events/recent,
     GET /api/events/sessions.
  3. HEALTH CHECK: Updated version string to mention "Site Events Apr28".
  NO OTHER CHANGES. Rule 1 (do no harm) preserved.

- April 21, 2026: Assessment PDF Generator — ONE CHANGE ONLY:
  1. BLUEPRINT: Registered assessment_pdf_bp from routes/assessment_pdf.py.
     Placed immediately AFTER the assessment_bp registration block.
     Provides POST /api/assessment/generate-pdf. Generates a branded
     multi-section PDF (cover, Reality Check recap, executive summary,
     dimensional scorecard, About Shiftwork Solutions) using ReportLab,
     returns it as a direct download to the user's browser, and emails
     a copy to Contact@shift-work.com via Resend with the user's
     contact info and assessment summary in the body. Uses the existing
     RESEND_API_KEY env var.
  2. HEALTH CHECK: Updated version string to mention "Assessment PDF Apr21".
  NO OTHER CHANGES. Rule 1 (do no harm) preserved.

- April 17, 2026: Assessment Google Sheets API — ONE CHANGE ONLY:
  1. BLUEPRINT: Registered assessment_bp from routes/assessment.py.
     Placed immediately AFTER the contact_api blueprint block.
     Provides POST /api/assessment/lead and
     POST /api/assessment/update-scores.
     Writes shift assessment contact form data and AI scores
     directly to the Shift Assessment Data Google Sheet.
     Requires GOOGLE_SERVICE_ACCOUNT_JSON env var in Render.
  NO OTHER CHANGES.

- April 7, 2026: Security Hardening — THREE CHANGES ONLY:
  1. MIGRATION: Added migration_007_security.py call in STEP 1,
     immediately after migration_006_newsletter.py. Creates
     ip_blocklist table, contact_submissions table. Adds user_agent
     and email_domain columns to newsletter_subscribers.
     Fully idempotent.
  2. BLUEPRINT: Registered contact_api_bp from routes/contact_api.py.
     Placed immediately AFTER the newsletter blueprint block.
     Provides POST /api/contact/submit (logs + forwards to Formspree)
     and GET /api/contact/submissions (admin view).
  3. HEALTH CHECK: Updated version string. Added 'security' section.
  NO OTHER CHANGES.

- April 2, 2026: Newsletter Subscription API — THREE CHANGES ONLY.
- March 27, 2026: Code mode selection — TWO CHANGES ONLY.
- March 26, 2026: Survey in a Box Phase 2 — TWO CHANGES ONLY.
- March 13, 2026: Survey in a Box Phase 3 — THREE CHANGES ONLY.
- March 12, 2026: Phase 6 Deliverable 7 — Scheduler + Swarm self-registration.
- March 12, 2026: Phase 6 Proactive Agent — Registered proactive_bp.
- March 10, 2026: Survey in a Box Phase 1 — THREE CHANGES ONLY.
- March 08, 2026: Phase 3 Self-Awareness — CAPABILITIES MANIFEST WIRED IN.
- March 05, 2026: Phase 2A Memory Schema Fix.
- March 05, 2026: Phase 2A - Registered memory blueprint (routes/memory.py).
- March 03, 2026: Phase 9b - FIX BROKEN TABLE SCHEMAS.
- March 03, 2026: SCHEMA MIGRATION.
- March 02, 2026: POSTGRESQL MIGRATION.
- February 27, 2026: ADDED /api/admin/restore-knowledge ENDPOINT.
- February 26, 2026: ADDED /api/admin/clear-knowledge-db ENDPOINT.
- February 25, 2026: ADDED /api/admin/kb-diagnose ENDPOINT.
- February 23, 2026: ADDED Blog Posts Table Migration.
- February 22, 2026: RE-ENABLED Case Study Generator.
- February 20, 2026: BUG FIX #1 - intelligence_bp name conflict.
- February 20, 2026: BUG FIX #2 - conversation_learning import path.
- February 18, 2026: FIXED NameError crash on startup.
- February 18, 2026: BACKGROUND KB INIT.
- February 5, 2026: INCREASED FILE UPLOAD LIMIT TO 100MB.
- January 30, 2026: ADDED BULLETPROOF PROJECT MANAGEMENT.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Flask, render_template, jsonify, request
import os
from flask import send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

# Initialize Flask
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

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

# ----------------------------------------------------------------------------
# MIGRATION 003: Survey Responses table
# Added: March 13, 2026
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu3
    import os as _os3
    _m003_path = _os3.path.join(_os3.path.dirname(_os3.path.abspath(__file__)),
                                'migrations', 'migration_003_survey_responses.py')
    _spec003 = _ilu3.spec_from_file_location("migration_003_survey_responses", _m003_path)
    _mod003 = _ilu3.module_from_spec(_spec003)
    _spec003.loader.exec_module(_mod003)
    _mod003.run_migration()
    print("Survey Responses migration (003) complete")
except Exception as e:
    print(f"Survey Responses migration (003) failed: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------------------------
# MIGRATION 004: Phase 2 Enhancements
# Added: March 26, 2026
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu4
    import os as _os4
    _m004_path = _os4.path.join(_os4.path.dirname(_os4.path.abspath(__file__)),
                                'migrations', 'migration_004_phase2_enhancements.py')
    _spec004 = _ilu4.spec_from_file_location("migration_004_phase2_enhancements", _m004_path)
    _mod004 = _ilu4.module_from_spec(_spec004)
    _spec004.loader.exec_module(_mod004)
    _mod004.run_migration()
    print("Phase 2 Enhancements migration (004) complete")
except Exception as e:
    print(f"Phase 2 Enhancements migration (004) failed: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------------------------
# MIGRATION 005: Code Mode column
# Added: March 27, 2026
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu5
    import os as _os5
    _m005_path = _os5.path.join(_os5.path.dirname(_os5.path.abspath(__file__)),
                                'migrations', 'migration_005_code_mode.py')
    _spec005 = _ilu5.spec_from_file_location("migration_005_code_mode", _m005_path)
    _mod005 = _ilu5.module_from_spec(_spec005)
    _spec005.loader.exec_module(_mod005)
    _mod005.run_migration()
    print("Code Mode migration (005) complete")
except Exception as e:
    print(f"Code Mode migration (005) failed: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------------------------
# MIGRATION 006: Newsletter Subscribers table
# Added: April 2, 2026
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu6
    import os as _os6
    _m006_path = _os6.path.join(_os6.path.dirname(_os6.path.abspath(__file__)),
                                'migrations', 'migration_006_newsletter.py')
    _spec006 = _ilu6.spec_from_file_location("migration_006_newsletter", _m006_path)
    _mod006 = _ilu6.module_from_spec(_spec006)
    _spec006.loader.exec_module(_mod006)
    _mod006.run_migration()
    print("Newsletter Subscribers migration (006) complete")
except Exception as e:
    print(f"Newsletter Subscribers migration (006) failed: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------------------------
# MIGRATION 007: Security Enhancements
# Added: April 7, 2026
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu7
    import os as _os7
    _m007_path = _os7.path.join(_os7.path.dirname(_os7.path.abspath(__file__)),
                                'migrations', 'migration_007_security.py')
    _spec007 = _ilu7.spec_from_file_location("migration_007_security", _m007_path)
    _mod007 = _ilu7.module_from_spec(_spec007)
    _spec007.loader.exec_module(_mod007)
    _mod007.run_migration()
    print("Security Enhancements migration (007) complete")
except Exception as e:
    print(f"Security Enhancements migration (007) failed: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------------------------
# MIGRATION 008: Site Events Tracking
# Added: April 28, 2026
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu8
    import os as _os8
    _m008_path = _os8.path.join(_os8.path.dirname(_os8.path.abspath(__file__)),
                                'migrations', 'migration_008_site_events.py')
    _spec008 = _ilu8.spec_from_file_location("migration_008_site_events", _m008_path)
    _mod008 = _ilu8.module_from_spec(_spec008)
    _spec008.loader.exec_module(_mod008)
    _mod008.run_migration()
    print("Site Events Tracking migration (008) complete")
except Exception as e:
    print(f"Site Events Tracking migration (008) failed: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------------------------
# MIGRATION 009: Part Time Tracker Lite
# Added: May 01, 2026
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu9
    import os as _os9
    _m009_path = _os9.path.join(_os9.path.dirname(_os9.path.abspath(__file__)),
                                'migrations', 'migration_009_ptt.py')
    _spec009 = _ilu9.spec_from_file_location("migration_009_ptt", _m009_path)
    _mod009 = _ilu9.module_from_spec(_spec009)
    _spec009.loader.exec_module(_mod009)
    _mod009.run_migration()
    print("Part Time Tracker migration (009) complete")
except Exception as e:
    print(f"Part Time Tracker migration (009) failed: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------------------------
# MIGRATION 010: Part Time Tracker Phase 2 — Worker audit columns
# Added: May 04, 2026
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu10
    import os as _os10
    _m010_path = _os10.path.join(_os10.path.dirname(_os10.path.abspath(__file__)),
                                 'migrations', 'migration_010_ptt_phase2.py')
    _spec010 = _ilu10.spec_from_file_location("migration_010_ptt_phase2", _m010_path)
    _mod010 = _ilu10.module_from_spec(_spec010)
    _spec010.loader.exec_module(_mod010)
    _mod010.run_migration()
    print("Part Time Tracker Phase 2 migration (010) complete")
except Exception as e:
    print(f"Part Time Tracker Phase 2 migration (010) failed: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)

# ----------------------------------------------------------------------------
# MIGRATION 011: Part Time Tracker Phase 3 — urgency + skill_required_id
# Added: May 06, 2026
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu11
    import os as _os11
    _m011_path = _os11.path.join(_os11.path.dirname(_os11.path.abspath(__file__)),
                                 'migrations', 'migration_011_ptt_phase3.py')
    _spec011 = _ilu11.spec_from_file_location("migration_011_ptt_phase3", _m011_path)
    _mod011 = _ilu11.module_from_spec(_spec011)
    _spec011.loader.exec_module(_mod011)
    _mod011.run_migration()
    print("Part Time Tracker Phase 3 migration (011) complete")
except Exception as e:
    print(f"Part Time Tracker Phase 3 migration (011) failed: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------------------------
# MIGRATION 012: Fix ptt_worker unique constraint
# Added: May 08, 2026
# ----------------------------------------------------------------------------
try:
    import importlib.util as _ilu12
    import os as _os12
    _m012_path = _os12.path.join(_os12.path.dirname(_os12.path.abspath(__file__)),
                                 'migrations', 'migration_012_ptt_worker_unique.py')
    _spec012 = _ilu12.spec_from_file_location("migration_012_ptt_worker_unique", _m012_path)
    _mod012 = _ilu12.module_from_spec(_spec012)
    _spec012.loader.exec_module(_mod012)
    _mod012.run_migration()
    print("Part Time Tracker worker constraint migration (012) complete")
except Exception as e:
    print(f"Part Time Tracker worker constraint migration (012) failed: {e}")
    import traceback
    traceback.print_exc()

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

try:
    from add_missing_columns import add_missing_columns
    add_missing_columns()
except Exception as e:
    print(f"Missing columns migration: {e}")

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

# ============================================================================
# KB SHARING — Added May 20, 2026
# ============================================================================
# Make the knowledge_base instance accessible to any blueprint that needs it.
# The new /api/knowledge/search endpoint in routes/ingest.py reads this so it
# can call semantic_search() on the same singleton instance — never creating
# a duplicate KB. If knowledge_base is None (init failed or no files found),
# this stores None and the search endpoint returns a graceful 503 response.
# This is the ONLY change to this file from the prior version (May 11, 2026).
# ============================================================================
app.config['KNOWLEDGE_BASE'] = knowledge_base
print(f"KB sharing: app.config['KNOWLEDGE_BASE'] = "
      f"{'<EnhancedProjectKnowledgeBase>' if knowledge_base else 'None'}")

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
# Updated: March 08, 2026
# ============================================================================
print("Scheduling deferred capabilities manifest warm (waiting for KB ready)...")
try:
    import threading as _threading

    def _warm_manifest_when_kb_ready(kb_ref, max_wait=120):
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
            print(f"Capabilities manifest ready: {_summary}")
        except Exception as _e:
            print(f"Deferred manifest warm failed (non-fatal): {_e}")

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

@app.route('/homepage')
def homepage():
    return render_template('homepage.html')

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
        'version': 'Assessment AI Proxy Jun12 + KB Search Endpoint May20 + PTT Lite Phase3 May11 + PTT Lite Phase2 May04 + PTT Lite Phase1 May01 + Site Events Apr28 + Assessment PDF Apr21 + Assessment Sheets Apr17 + Security Hardening Apr07 + Newsletter API Apr02 + Survey in a Box Phase 2 Mar26 + Phase 3 Mar13 + Phase 6 Proactive Agent Mar12 + Phase 1 Onboarding Mar10 + Phase 3 Capabilities Manifest Mar08 + Phase 2A Memory Mar05 + PostgreSQL Migration Mar02',
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
            'diagnose_url': '/api/admin/kb-diagnose',
            'search_url': '/api/knowledge/search',
            'context_url': '/api/knowledge/context'
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
            'phase': '2+3 - Survey Assembly, Code Mode Selection & Online Engine'
        },
        'proactive_agent': {
            'status': 'enabled',
            'briefing_url': '/api/briefing',
            'tasks_url': '/api/tasks',
            'status_url': '/api/proactive/status',
            'phase': '6 - Proactive Agent (Deliverables 1-7 active)',
        },
        'newsletter': {
            'status': 'enabled',
            'subscribe_url': '/api/newsletter/subscribe',
            'stats_url': '/api/newsletter/stats',
        },
        'security': {
            'status': 'enabled',
            'ip_blocklist': '/api/newsletter/blocked-ips',
            'contact_submissions': '/api/contact/submissions',
            'newsletter_subscribers': '/api/newsletter/subscribers',
            'block_ip': '/api/newsletter/block-ip',
            'unblock_ip': '/api/newsletter/unblock-ip',
        },
        'assessment': {
            'status': 'enabled',
            'lead_url': '/api/assessment/lead',
            'scores_url': '/api/assessment/update-scores',
            'pdf_url': '/api/assessment/generate-pdf',
            'sheet': 'Shift Assessment Data',
        },
        'assessment_ai': {
            'status': 'enabled',
            't1_commentary_url': '/api/assessment/t1-commentary',
            't2_evaluate_url': '/api/assessment/t2-evaluate',
            'model': 'claude-sonnet-4-6',
            'note': 'Server-side Anthropic calls for the Shiftwork Operations Assessment (added Jun 12, 2026)',
        },
        'site_events': {
            'status': 'enabled',
            'log_url': '/api/events/log',
            'summary_url': '/api/events/summary',
            'recent_url': '/api/events/recent',
            'sessions_url': '/api/events/sessions',
        },
        'part_time_tracker': {
            'status': 'enabled',
            'phase': 'Lite Phase 3 — Shift Management, Worker Dashboard & Claims',
            'signup_url': '/ptt/',
            'login_url': '/ptt/login',
            'dashboard_url': '/ptt/dashboard',
            'apply_url': '/ptt/apply/<slug>',
            'api_lead': '/api/ptt/lead',
            'api_login_request': '/api/ptt/login-request',
            'api_apply': '/api/ptt/apply/<slug>',
            'dev_reset': '/api/ptt/dev/reset-company (POST {email})',
            'dev_reseed': '/api/ptt/dev/reseed-skills (POST {email})',
            'dev_worker_login_link': '/api/ptt/dev/worker-login-link (POST {worker_id|worker_name})',
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

try:
    from routes.memory import memory_bp
    app.register_blueprint(memory_bp)
    print("Phase 2A Memory System API registered")
except ImportError as e:
    print(f"Memory System routes not found: {e}")
except Exception as e:
    print(f"Memory System registration failed: {e}")

try:
    from routes.capabilities import capabilities_bp
    app.register_blueprint(capabilities_bp)
    print("Phase 3 Capabilities Manifest API registered")
except ImportError as e:
    print(f"Capabilities Manifest routes not found: {e}")
except Exception as e:
    print(f"Capabilities Manifest registration failed: {e}")

try:
    from routes.survey_intake import survey_intake_bp
    app.register_blueprint(survey_intake_bp)
    print("Survey in a Box Intake API registered")
except ImportError as e:
    print(f"Survey Intake routes not found: {e}")
except Exception as e:
    print(f"Survey Intake registration failed: {e}")

try:
    from routes.survey_admin import survey_admin_bp
    app.register_blueprint(survey_admin_bp)
    print("Survey in a Box Admin API registered")
except ImportError as e:
    print(f"Survey Admin routes not found: {e}")
except Exception as e:
    print(f"Survey Admin registration failed: {e}")

try:
    from routes.survey_respondent import survey_respondent_bp
    app.register_blueprint(survey_respondent_bp)
    print("Survey in a Box Respondent API registered")
except ImportError as e:
    print(f"Survey Respondent routes not found: {e}")
except Exception as e:
    print(f"Survey Respondent registration failed: {e}")

try:
    from routes.survey_normative import survey_normative_bp
    app.register_blueprint(survey_normative_bp)
    print("Survey in a Box Normative Database API registered")
except ImportError as e:
    print(f"Survey Normative routes not found: {e}")
except Exception as e:
    print(f"Survey Normative registration failed: {e}")

try:
    from routes.proactive import proactive_bp
    app.register_blueprint(proactive_bp)
    print("Phase 6 Proactive Agent API registered")
except ImportError as e:
    print(f"Proactive Agent routes not found: {e}")
except Exception as e:
    print(f"Proactive Agent registration failed: {e}")

# ----------------------------------------------------------------------------
# FeynmanLab — Physics Thinking Partner (WO-14)
# ----------------------------------------------------------------------------
try:
    from routes.physics import physics_bp
    app.register_blueprint(physics_bp)
    print("FeynmanLab (Physics Lab) API registered")
except ImportError as e:
    print(f"FeynmanLab routes not found: {e}")
except Exception as e:
    print(f"FeynmanLab registration failed: {e}")

try:
    from routes.newsletter import newsletter_bp
    app.register_blueprint(newsletter_bp)
    print("Newsletter Subscription API registered")
except ImportError as e:
    print(f"Newsletter routes not found: {e}")
except Exception as e:
    print(f"Newsletter registration failed: {e}")

try:
    from routes.contact_api import contact_api_bp
    app.register_blueprint(contact_api_bp)
    print("Contact Form API registered")
except ImportError as e:
    print(f"Contact Form API routes not found: {e}")
except Exception as e:
    print(f"Contact Form API registration failed: {e}")

try:
    from routes.assessment import assessment_bp
    app.register_blueprint(assessment_bp)
    print("Assessment Google Sheets API registered")
except ImportError as e:
    print(f"Assessment API routes not found: {e}")
except Exception as e:
    print(f"Assessment API registration failed: {e}")

try:
    from routes.assessment_pdf import assessment_pdf_bp
    app.register_blueprint(assessment_pdf_bp)
    print("Assessment PDF Generator API registered")
except ImportError as e:
    print(f"Assessment PDF routes not found: {e}")
except Exception as e:
    print(f"Assessment PDF registration failed: {e}")

# ----------------------------------------------------------------------------
# Assessment AI Proxy — server-side Anthropic calls for the assessment page
# Added: June 12, 2026
# ----------------------------------------------------------------------------
try:
    from routes.assessment_ai import assessment_ai_bp
    app.register_blueprint(assessment_ai_bp)
    print("Assessment AI Proxy API registered")
except ImportError as e:
    print(f"Assessment AI Proxy routes not found: {e}")
except Exception as e:
    print(f"Assessment AI Proxy registration failed: {e}")

try:
    from routes.site_events import site_events_bp
    app.register_blueprint(site_events_bp)
    print("Site Events Tracking API registered")
except ImportError as e:
    print(f"Site Events routes not found: {e}")
except Exception as e:
    print(f"Site Events registration failed: {e}")

# ----------------------------------------------------------------------------
# Part Time Tracker Lite — HR Admin Routes
# ----------------------------------------------------------------------------
try:
    from routes.ptt_hr import ptt_hr_bp
    app.register_blueprint(ptt_hr_bp)
    print("Part Time Tracker HR Routes registered")
except ImportError as e:
    print(f"Part Time Tracker HR routes not found: {e}")
except Exception as e:
    print(f"Part Time Tracker HR registration failed: {e}")

# ----------------------------------------------------------------------------
# Part Time Tracker Lite — Worker Intake Routes (public, no auth)
# ----------------------------------------------------------------------------
try:
    from routes.ptt_worker_intake import ptt_worker_intake_bp
    app.register_blueprint(ptt_worker_intake_bp)
    print("Part Time Tracker Worker Intake Routes registered")
except ImportError as e:
    print(f"Part Time Tracker Worker Intake routes not found: {e}")
except Exception as e:
    print(f"Part Time Tracker Worker Intake registration failed: {e}")

# Part Time Tracker Lite — Shift Management Routes (HR)
try:
    from routes.ptt_shifts import ptt_shifts_bp
    app.register_blueprint(ptt_shifts_bp)
    print("Part Time Tracker Shifts Routes registered")
except ImportError as e:
    print(f"Part Time Tracker Shifts routes not found: {e}")
except Exception as e:
    print(f"Part Time Tracker Shifts registration failed: {e}")

# Part Time Tracker Lite — Worker Routes (authenticated worker side)
try:
    from routes.ptt_worker import ptt_worker_bp
    app.register_blueprint(ptt_worker_bp)
    print("Part Time Tracker Worker Routes registered")
except ImportError as e:
    print(f"Part Time Tracker Worker routes not found: {e}")
except Exception as e:
    print(f"Part Time Tracker Worker registration failed: {e}")

# Part Time Tracker Lite — AI Chat Advisors (Carolyn + Franklin)
try:
    from routes.ptt_chat import ptt_chat_bp
    app.register_blueprint(ptt_chat_bp)
    print("Part Time Tracker Chat Advisors registered")
except ImportError as e:
    print(f"Part Time Tracker Chat routes not found: {e}")
except Exception as e:
    print(f"Part Time Tracker Chat registration failed: {e}")

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
# ADMIN: FIX MEMORY STORE COLUMNS (Phase 2A)
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
# ADMIN: FIX MEMORY SCHEMA (Phase 2A)
# ============================================================================
@app.route('/api/admin/fix-memory-schema', methods=['GET'])
def fix_memory_schema():
    """One-time migration: drop Phase 1 orphan columns from memory_store."""
    try:
        from db_engine import get_db_connection
        results = []
        orphan_columns = ['memory_key', 'memory_value', 'expires_at',
                          'access_count', 'last_accessed']
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'memory_store'
                ORDER BY ordinal_position
            """)
            before_cols = [{'column': r['column_name'], 'type': r['data_type'],
                            'nullable': r['is_nullable']} for r in cursor.fetchall()]
            for col in orphan_columns:
                try:
                    cursor.execute(f"ALTER TABLE memory_store DROP COLUMN IF EXISTS {col}")
                    results.append(f"DROPPED: {col}")
                except Exception as col_err:
                    results.append(f"ERROR dropping {col}: {col_err}")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'memory_store'
                ORDER BY ordinal_position
            """)
            after_cols = [{'column': r['column_name'], 'type': r['data_type'],
                           'nullable': r['is_nullable']} for r in cursor.fetchall()]
        return jsonify({
            'success': True,
            'message': 'Phase 1 orphan columns removed.',
            'operations': results,
            'schema_before': before_cols,
            'schema_after': after_cols,
        })
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e),
                        'traceback': traceback.format_exc()}), 500

# ============================================================================
# PTT DEV ENDPOINTS — development/testing only
# ============================================================================
@app.route('/api/ptt/dev/reset-company', methods=['POST'])
def ptt_dev_reset_company():
    """
    DEV ONLY — wipe all ptt_* data for a company by admin email.
    """
    from db_engine import get_db_connection
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email required"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.id AS admin_id, a.company_id
            FROM ptt_admin_user a WHERE a.email = %s
        """, (email,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": f"No PTT admin found for {email}"}), 404

        company_id = row["company_id"]
        counts = {}

        cursor.execute("DELETE FROM ptt_session    WHERE company_id = %s", (company_id,))
        counts["sessions"] = cursor.rowcount
        cursor.execute("DELETE FROM ptt_magic_token WHERE company_id = %s", (company_id,))
        counts["tokens"] = cursor.rowcount

        cursor.execute("DELETE FROM ptt_worker WHERE company_id = %s", (company_id,))
        counts["workers"] = cursor.rowcount

        cursor.execute("DELETE FROM ptt_shift WHERE company_id = %s", (company_id,))
        counts["shifts"] = cursor.rowcount

        cursor.execute("DELETE FROM ptt_skill WHERE company_id = %s", (company_id,))
        counts["skills"] = cursor.rowcount

        cursor.execute("DELETE FROM ptt_admin_user WHERE company_id = %s", (company_id,))
        counts["admins"] = cursor.rowcount

        cursor.execute("DELETE FROM ptt_company WHERE id = %s", (company_id,))
        counts["companies"] = cursor.rowcount

        conn.commit()
        print(f"[ptt_dev] reset-company for {email}: {counts}")
        return jsonify({"status": "ok", "deleted": counts}), 200

    except Exception as e:
        conn.rollback()
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
    finally:
        conn.close()


@app.route('/api/ptt/dev/reseed-skills', methods=['POST'])
def ptt_dev_reseed_skills():
    """
    DEV ONLY — replace skill list for a company with the 14 Opus-specified
    industry skills.
    """
    from db_engine import get_db_connection
    from routes.ptt_hr import SKILL_SEED

    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "email required"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.company_id FROM ptt_admin_user a WHERE a.email = %s
        """, (email,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": f"No PTT admin found for {email}"}), 404

        company_id = row["company_id"]

        cursor.execute("DELETE FROM ptt_skill WHERE company_id = %s", (company_id,))
        deleted = cursor.rowcount

        for skill_name, skill_desc, sort_order in SKILL_SEED:
            cursor.execute("""
                INSERT INTO ptt_skill (company_id, name, description, sort_order)
                VALUES (%s, %s, %s, %s)
            """, (company_id, skill_name, skill_desc, sort_order))

        conn.commit()
        print(f"[ptt_dev] reseed-skills for {email}: deleted {deleted}, seeded {len(SKILL_SEED)}")
        return jsonify({
            "status":  "ok",
            "deleted": deleted,
            "seeded":  len(SKILL_SEED),
        }), 200

    except Exception as e:
        conn.rollback()
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
    finally:
        conn.close()

@app.route('/api/ptt/dev/reset-shift', methods=['POST'])
def ptt_dev_reset_shift():
    """
    DEV ONLY — reset a single shift back to 'open' status and delete
    all claims against it.
    """
    from db_engine import get_db_connection
    data     = request.get_json(silent=True) or {}
    shift_id = data.get("shift_id")
    if not shift_id:
        return jsonify({"error": "shift_id required"}), 400
    try:
        shift_id = int(shift_id)
    except (TypeError, ValueError):
        return jsonify({"error": "shift_id must be an integer"}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT id, title, company_id FROM ptt_shift WHERE id = %s",
                       (shift_id,))
        shift = cursor.fetchone()
        if not shift:
            return jsonify({"error": f"Shift {shift_id} not found"}), 404

        cursor.execute("DELETE FROM ptt_shift_claim WHERE shift_id = %s", (shift_id,))
        claims_deleted = cursor.rowcount

        cursor.execute("""
            UPDATE ptt_shift SET status = 'open', updated_at = NOW()
            WHERE id = %s
        """, (shift_id,))

        conn.commit()
        print(f"[ptt_dev] reset-shift {shift_id} ('{shift['title']}'): "
              f"deleted {claims_deleted} claims, status -> open")
        return jsonify({
            "status":         "ok",
            "shift_id":       shift_id,
            "title":          shift["title"],
            "claims_deleted": claims_deleted,
            "shift_status":   "open",
        }), 200

    except Exception as e:
        conn.rollback()
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
    finally:
        conn.close()
# ============================================================================
# PHASE 6: BACKGROUND SCHEDULER INIT
# ============================================================================
try:
    from proactive.scheduler import init_scheduler
    init_scheduler(app)
except ImportError as e:
    print(f"Scheduler not found (non-fatal): {e}")
except Exception as e:
    print(f"Scheduler init failed (non-fatal): {e}")

# ============================================================================
# PHASE 6: SWARM SELF-REGISTRATION
# ============================================================================
try:
    from proactive.app_monitor import auto_register_swarm
    auto_register_swarm()
except ImportError as e:
    print(f"App Monitor not found (non-fatal): {e}")
except Exception as e:
    print(f"Swarm self-registration failed (non-fatal): {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)

# I did no harm and this file is not truncated.
