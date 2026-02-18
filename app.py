"""
AI SWARM ORCHESTRATOR - Main Application   
Created: January 18, 2026
Last Updated: February 18, 2026 - BACKGROUND KNOWLEDGE BASE INITIALIZATION FIX

CRITICAL UPDATE (February 18, 2026):
- FIXED: App not loading after deploy (blank page / 30-second timeout)
- ROOT CAUSE: knowledge_base.initialize() was blocking gunicorn for ~30 seconds
  while indexing 34 documents including a 56MB Excel file. Render's port scanner
  fired during this window and found nothing, and the first real page request
  timed out at 30 seconds returning only 29 bytes.
- FIX: Changed knowledge_base.initialize() to knowledge_base.initialize_background()
  Gunicorn now binds and accepts connections immediately. The knowledge index
  becomes available ~30 seconds later. Search calls before that return empty
  results gracefully instead of blocking.
- ONLY ONE LINE CHANGED in this file (see "BACKGROUND INIT FIX" comment below)

CRITICAL UPDATE (February 5, 2026):
- Added Flask MAX_CONTENT_LENGTH configuration
- Increased file upload limit from default to 100MB
- Allows large Excel files (56MB+) to be uploaded to project folders
- Required for Definitive Schedules v2.xlsx (56.22 MB) and similar large files

@app.route('/survey')
CHANGES IN THIS VERSION:
- February 18, 2026: BACKGROUND KNOWLEDGE BASE INITIALIZATION FIX
  * Changed knowledge_base.initialize() to knowledge_base.initialize_background()
  * Gunicorn no longer blocked during startup - page loads immediately
  * Knowledge base becomes available ~30 seconds after startup
  * No other changes to this file

- February 5, 2026: INCREASED FILE UPLOAD LIMIT TO 100MB
  * Added app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
  * Allows uploading large files (56MB+) to project folders
  * Frontend and backend file size validations updated
  
- January 30, 2026: ADDED BULLETPROOF PROJECT MANAGEMENT
  * Added projects_bp blueprint for complete project lifecycle management
  * Project creation, updates, search, and retrieval
  * File upload/download with proper storage
  * Conversation tracking with message history
  * Context management (key-value storage)
  * Complete project summaries
  * Backward compatible with existing database_file_management.py
  * Fixes all 5 critical issues: project recall, file upload, file download, file retrieval, conversation context

- January 29, 2026: ADDED LINKEDIN POSTER DOWNLOAD BUTTON
  * Added download button for linkedin_poster.pyw in Marketing Info Panel (templates/index.html)
  * Desktop app with 120 pre-written posts tailored to 12 LinkedIn groups
  * Styled consistently with Calculator and Survey app download sections
  * Includes app description and Python requirements
  * Download route already configured in app.py (see /downloads/<filename> route below)
  * File should be placed in /downloads/linkedin_poster.pyw

- January 28, 2026: ADDED IMPLEMENTATION MANUAL GENERATOR
  * Added manuals_bp blueprint for conversational manual generation
  * Question-driven data collection for implementation manuals
  * Section-by-section drafting and refinement
  * Iterative editing through conversation
  * Lessons learned tracking
  * Word document generation integration

- January 26, 2026: UPDATED FOR PATTERN-BASED SCHEDULE SYSTEM
  * Added Flask session configuration (required for multi-turn schedule conversations)
  * Session stores schedule conversation state between requests
  * Required for new conversational schedule generator

- January 25, 2026: ADDED SWARM SELF-EVALUATION SYSTEM
  * Added evaluation_bp blueprint for weekly self-reviews
  * Evaluates internal performance against benchmarks
  * Tracks emerging AI models and capabilities
  * Identifies gaps in current AI stack
  * Generates "State of the Swarm" reports with recommendations
  * Can run manually or be scheduled weekly

- January 25, 2026: ADDED CONTENT MARKETING ENGINE
  * Added marketing_bp blueprint for autonomous content generation
  * Auto-generates LinkedIn posts from consulting work
  * Creates weekly "This Week in Shiftwork" newsletters
  * Approval workflow for one-click content publishing
  * Learns what content performs well over time

- January 23, 2026: ADDED CLIENT INTELLIGENCE DASHBOARD
  * Added intelligence_bp blueprint for lead pipeline management
  * Lead scoring based on 202-company normative database
  * Kanban pipeline: Detected → Qualified → Contacted → Proposal → Won/Lost
  * AI-powered actions: draft emails, proposals, research
  * Convert alerts to leads with automatic scoring

- January 23, 2026: ADDED ALERT SYSTEM (Autonomous Monitoring)
  * Added alerts_bp blueprint for automated monitoring and notifications
  * Alert System provides scheduled monitoring jobs
  * Lead alerts, competitor tracking, regulatory updates
  * Email notifications for high-priority alerts
  * Requires SMTP configuration for email delivery (optional)
  * New environment variables: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    ALERT_FROM_EMAIL, ALERT_TO_EMAIL, ENABLE_EMAIL_ALERTS, ENABLE_SCHEDULED_JOBS

- January 23, 2026: ADDED RESEARCH AGENT
  * Added research_bp blueprint for web research capabilities
  * Research Agent provides real-time industry news, regulations, studies
  * Proactive intelligence for monitoring shift work industry
  * Requires TAVILY_API_KEY environment variable

- January 22, 2026: SPRINT 3 - ALL 5 ADVANCED FEATURES
  * Enhanced Intelligence (learning & memory)
  * Project Dashboard (visual management)
  * Analytics Dashboard (data visualization)
  * Smart Workflows (multi-step automation)
  * Integration Hub (external services)

- January 22, 2026: SPRINT 2 - PROACTIVE INTELLIGENCE
  * Project auto-detection
  * Resource finder (auto web search)
  * Improvement engine (weekly reports)

- January 22, 2026: SPRINT 1 - PROACTIVE INTELLIGENCE
  * Smart questioning before task execution
  * Post-task suggestions for next steps
  * Pattern tracking for automation opportunities

ARCHITECTURE:
- config.py: All configuration
- database.py: All database operations
- database_file_management.py: Bulletproof project & file management (NEW)
- orchestration/: All AI logic + proactive_agent.py
- routes/: All Flask endpoints
- routes/projects_bulletproof.py: Project management API (NEW)
- schedule_generator.py: Pattern-based schedule generation (UPDATED)
- schedule_request_handler.py: Conversational schedule handler (NEW)
- implementation_manual_generator.py: Conversational manual generation (NEW)
- routes/manuals.py: Manual generator API endpoints (NEW)
- swarm_self_evaluation.py: Weekly self-evaluation engine
- routes/evaluation.py: Evaluation API endpoints
- content_marketing_engine.py: Autonomous content generation
- routes/marketing.py: Marketing API endpoints
- intelligence.py: Lead scoring & pipeline management
- routes/intelligence.py: Intelligence API endpoints
- alert_system.py: Automated monitoring & alerts
- routes/alerts.py: Alert API endpoints
- research_agent.py: Web research capabilities
- routes/research.py: Research API endpoints
- project_manager.py: Project detection & management
- resource_finder.py: Automatic web search
- improvement_engine.py: Efficiency analysis
- enhanced_intelligence.py: Learning & memory
- project_dashboard.py: Project API
- analytics_engine.py: Analytics API
- workflow_engine.py: Automation engine
- integration_hub.py: External integrations
- app.py (this file): Bootstrap and initialization

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Flask, render_template, jsonify
from database import init_db
from database_survey_additions import add_surveys_table
import os
from flask import send_from_directory
import os

# Initialize Flask
app = Flask(__name__)

# ============================================================================
# CRITICAL FILE UPLOAD CONFIGURATION (Added February 5, 2026)
# ============================================================================
# This setting controls the maximum size of uploaded files
# Default Flask limit is typically 16MB, which blocks large Excel files
# Setting to 100MB to allow files like Definitive Schedules v2.xlsx (56.22 MB)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
print("📤 File Upload Limit: 100MB (allows large project files)")
# ============================================================================

# CRITICAL: Configure session for schedule conversation memory (Added January 26, 2026)
# This is REQUIRED for the new pattern-based schedule system to work
# Without this, the system cannot remember multi-turn conversations
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-12345')
app.config['SESSION_TYPE'] = 'filesystem'

# Initialize database (includes all tables from all sprints)
init_db()

# Initialize survey tables
try:
    add_surveys_table()
    print("✅ Survey tables initialized")
except Exception as e:
    print(f"⚠️  Survey tables: {e}")

# ============================================================================
# AUTO-RUN ALL DATABASE MIGRATIONS (SPRINTS 2 & 3)
# ============================================================================
print("🔄 Running database migrations...")
try:
    # Projects table migration (CRITICAL - must run FIRST)
    from migrate_projects_table import migrate_projects_table
    migrate_projects_table()
    
    # Sprint 2 migrations
    from upgrade_database_sprint2 import upgrade_database_sprint2
    from add_resource_searches_table import add_resource_searches_table
    from add_improvement_reports_table import add_improvement_reports_table
    
    upgrade_database_sprint2()
    add_resource_searches_table()
    add_improvement_reports_table()
    print("✅ Sprint 2 migrations complete!")
    add_conversation_context_table()
    print("✅ Conversation context table added!")
    
    # Sprint 3 migrations
    from add_user_profiles_table import add_user_profiles_table
    from add_workflow_tables import add_workflow_tables
    from add_integration_logs_table import add_integration_logs_table
    from add_conversation_context_table import add_conversation_context_table
    
    add_user_profiles_table()
    add_workflow_tables()
    add_integration_logs_table()
    print("✅ Sprint 3 migrations complete!")
    
except ImportError as e:
    print(f"ℹ️  Some migrations not found: {e}")
except Exception as e:
    print(f"⚠️  Migration warning: {e}")
# ============================================================================

# ============================================================================
# INITIALIZE BULLETPROOF PROJECT MANAGEMENT (Added January 30, 2026)
# MUST come AFTER migrations so table columns exist
# ============================================================================
print("🔧 Initializing Bulletproof Project Management...")
try:
    from database_file_management import get_project_manager
    pm = get_project_manager()
    app.config['PROJECT_MANAGER'] = pm
    print("✅ Bulletproof Project Manager initialized")
    print("   - Projects with full lifecycle management")
    print("   - File upload/download with storage")
    print("   - Conversation tracking")
    print("   - Context management")
except Exception as e:
    print(f"⚠️  Project Manager initialization failed: {e}")
# ============================================================================

# ============================================================================
# INITIALIZE KNOWLEDGE BASE IN BACKGROUND THREAD (Fixed February 18, 2026)
# ============================================================================
# PREVIOUS BEHAVIOR: knowledge_base.initialize() ran synchronously, blocking
#   gunicorn for ~30 seconds while indexing 34 documents. The first page request
#   timed out. Render's port scanner found "No open HTTP ports".
#
# NEW BEHAVIOR: initialize_background() starts a daemon thread and returns
#   immediately. Gunicorn binds and accepts connections right away. The
#   knowledge index becomes available ~30 seconds later. Any search before
#   that returns empty results gracefully.
# ============================================================================
print("🔍 Initializing Project Knowledge Base...")
knowledge_base = None
try:
    from pathlib import Path
    from knowledge_integration import ProjectKnowledgeBase
    
    # Check for project_files first, then fall back to /mnt/project
    project_paths = ["project_files", "./project_files", "/mnt/project"]
    found_path = None
    
    for path in project_paths:
        if Path(path).exists() and Path(path).is_dir():
            file_count = len(list(Path(path).iterdir()))
            if file_count > 0:  # Only use paths with actual files
                found_path = path
                print(f"  📁 Found directory: {path} ({file_count} files)")
                break
    
    if not found_path:
        print(f"  ⚠️ No project files found. Checked: {project_paths}")
        print(f"  ℹ️  Knowledge base features disabled until files are added")
    else:
        # Pass the found path to ProjectKnowledgeBase constructor
        knowledge_base = ProjectKnowledgeBase(project_path=found_path)

        # =================================================================
        # BACKGROUND INIT FIX (February 18, 2026) - THE ONE LINE THAT CHANGED
        # Was: knowledge_base.initialize()
        # Now: knowledge_base.initialize_background()
        # =================================================================
        knowledge_base.initialize_background()
        # =================================================================

        print(f"  🔄 Knowledge Base initializing in background (~30 seconds)...")
        print(f"  ℹ️  App is ready to serve requests immediately.")
        
except Exception as e:
    print(f"  ⚠️ Warning: Knowledge Base initialization failed: {e}")
    import traceback
    print(f"  Traceback: {traceback.format_exc()}")
    knowledge_base = None
# ============================================================================

# Load optional modules
SCHEDULE_GENERATOR_AVAILABLE = False
try:
    from schedule_generator import get_pattern_generator
    SCHEDULE_GENERATOR_AVAILABLE = True
    schedule_gen = get_pattern_generator()
    print("✅ Pattern-Based Schedule Generator loaded")
    
    # CRITICAL: Make schedule generator available to routes
    app.config['SCHEDULE_GENERATOR_AVAILABLE'] = SCHEDULE_GENERATOR_AVAILABLE
    app.config['SCHEDULE_GENERATOR'] = schedule_gen
except ImportError:
    print("ℹ️  Schedule Generator module not found - schedule features disabled")
except Exception as e:
    print(f"⚠️  Schedule Generator initialization failed: {e}")

OUTPUT_FORMATTER_AVAILABLE = False
try:
    from output_formatter import get_output_formatter
    OUTPUT_FORMATTER_AVAILABLE = True
    output_fmt = get_output_formatter()
    print("✅ Output Formatter loaded")
    
    # Make output formatter available to routes
    app.config['OUTPUT_FORMATTER_AVAILABLE'] = OUTPUT_FORMATTER_AVAILABLE
    app.config['OUTPUT_FORMATTER'] = output_fmt
except ImportError:
    print("ℹ️  Output Formatter module not found - formatting features disabled")
except Exception as e:
    print(f"⚠️  Output Formatter initialization failed: {e}")

# Basic routes
@app.route('/')
def index():
    """Main interface"""
    return render_template('index.html')

# =============================================================================
# DOWNLOAD ROUTE FOR DESKTOP APPS - Updated January 29, 2026
# =============================================================================
# This route allows users to download desktop apps from the Marketing tab:
# - LinkedIn Poster (linkedin_poster.pyw) - 120 pre-written posts for 12 groups
# - Cost Calculator (cost_of_time_calculator_v3_3_2.pyw)
# - Survey App (SurveySelector_v88_FIXED.pyw)
# 
# Files are served from the /downloads folder in your repository
# =============================================================================

@app.route('/downloads/<path:filename>')
def download_file(filename):
    """
    Serve downloadable files from the /downloads directory.
    Allows downloading .pyw, .py, .txt, and .pdf files only.
    
    IMPORTANT: Place downloaded files in a /downloads folder at your project root:
    /downloads/
        linkedin_poster.pyw
        cost_of_time_calculator_v3_3_2.pyw
        SurveySelector_v87_FINAL.pyw
    """
    try:
        # Security: Define allowed file extensions
        allowed_extensions = {'.pyw', '.py', '.txt', '.pdf'}
        
        # Get the file extension
        file_ext = os.path.splitext(filename)[1].lower()
        
        # Check if file extension is allowed
        if file_ext not in allowed_extensions:
            return "File type not allowed", 403
        
        # Get the path to the downloads directory
        downloads_dir = os.path.join(app.root_path, 'downloads')
        
        # Serve the file with forced download
        return send_from_directory(
            downloads_dir, 
            filename, 
            as_attachment=True
        )
        
    except Exception as e:
        # Log the error and return 404
        print(f"Error serving download file: {str(e)}")
        return "File not found", 404

# =============================================================================
# END DOWNLOAD ROUTE
# =============================================================================

@app.route('/workflow')
def workflow():
    """Workflow interface"""
    return render_template('index_workflow.html')

# =============================================================================
# ONE-TIME STORAGE MIGRATION ENDPOINT - Added February 1, 2026
# =============================================================================
@app.route('/api/admin/migrate-storage', methods=['GET', 'POST'])
def migrate_storage():
    """
    One-time migration endpoint to move projects from /tmp to persistent storage.
    Run this ONCE after deploying persistent storage fix.
    
    USAGE:
    Just visit: https://ai-swarm-orchestrator.onrender.com/api/admin/migrate-storage
    
    Or use curl: curl https://ai-swarm-orchestrator.onrender.com/api/admin/migrate-storage
    """
    try:
        import migrate_project_storage
        from io import StringIO
        import sys
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        # Run migration
        migrate_project_storage.migrate_project_storage()
        
        # Restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()
        
        return jsonify({
            'success': True,
            'message': 'Migration complete! Check logs for details.',
            'output': output
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/admin/bootstrap-knowledge', methods=['GET'])
def bootstrap_knowledge_endpoint():
    """
    One-time endpoint to bootstrap knowledge base.
    Just visit this URL to load all existing documents.
    
    USAGE: https://ai-swarm-orchestrator.onrender.com/api/admin/bootstrap-knowledge
    """
    try:
        import bootstrap_knowledge
        from io import StringIO
        import sys
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        # Run bootstrap
        result = bootstrap_knowledge.bootstrap_knowledge_base(project_path='./project_files')
        
        # Restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()
        
        return jsonify({
            'success': True,
            'message': 'Bootstrap complete! Check output for details.',
            'output': output,
            'results': {
                'successful': len(result['success']),
                'already_ingested': len(result['already_ingested']),
                'failed': len(result['failed'])
            }
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/admin/list-project-files', methods=['GET'])
def list_project_files():
    """
    Diagnostic endpoint to see what files are actually accessible.
    """
    import os
    from pathlib import Path
    
    results = {}
    
    # Check multiple possible locations
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
                        'exists': True,
                        'is_dir': True,
                        'file_count': len(files),
                        'files': files[:10],  # First 10 files
                        'total_files': len(files)
                    }
                else:
                    results[str(location)] = {
                        'exists': True,
                        'is_dir': False,
                        'note': 'This is a file, not a directory'
                    }
            else:
                results[str(location)] = {
                    'exists': False
                }
        except Exception as e:
            results[str(location)] = {
                'error': str(e)
            }
    
    # Also check current working directory
    results['current_working_directory'] = os.getcwd()
    
    return jsonify({
        'success': True,
        'locations_checked': results
    })

@app.route('/api/admin/fix-patterns-table', methods=['GET'])
def fix_patterns_table():
    """
    One-time migration to fix learned_patterns table.
    Adds missing supporting_documents column.
    
    USAGE: https://ai-swarm-orchestrator.onrender.com/api/admin/fix-patterns-table
    """
    try:
        import migrate_learned_patterns
        from io import StringIO
        import sys
        
        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        # Run migration
        migrate_learned_patterns.migrate_learned_patterns()
        
        # Restore stdout
        sys.stdout = old_stdout
        output = captured_output.getvalue()
        
        return jsonify({
            'success': True,
            'message': 'Migration complete!',
            'output': output
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/admin/diagnose-databases', methods=['GET'])
def diagnose_databases():
    """
    Find all swarm_intelligence.db files and show their contents.
    """
    import os
    import sqlite3
    from pathlib import Path
    
    results = {}
    
    # Search for database files
    search_paths = [
        '.',
        '/opt/render/project/src',
        '/mnt/project',
        '/tmp'
    ]
    
    for search_path in search_paths:
        try:
            path = Path(search_path)
            if path.exists():
                # Look for swarm_intelligence.db files
                for db_file in path.rglob('swarm_intelligence.db'):
                    db_path = str(db_file.absolute())
                    
                    try:
                        db = sqlite3.connect(db_path)
                        cursor = db.cursor()
                        
                        # Count documents
                        cursor.execute('SELECT COUNT(*) FROM knowledge_extracts')
                        doc_count = cursor.fetchone()[0]
                        
                        # Get file size
                        file_size = os.path.getsize(db_path)
                        
                        db.close()
                        
                        results[db_path] = {
                            'exists': True,
                            'documents': doc_count,
                            'size_bytes': file_size,
                            'size_mb': round(file_size / 1024 / 1024, 2)
                        }
                    except Exception as e:
                        results[db_path] = {
                            'exists': True,
                            'error': str(e)
                        }
        except:
            pass
    
    # Also check what path document_ingestion_engine is using
    try:
        from document_ingestion_engine import get_document_ingestor
        ingestor = get_document_ingestor()
        results['api_uses_path'] = ingestor.db_path
    except:
        results['api_uses_path'] = 'error_loading'
    
    # Check current working directory
    results['current_directory'] = os.getcwd()
    
    return jsonify({
        'success': True,
        'databases_found': results
    })

@app.route('/survey')
def survey():
    """Survey builder interface"""
    return render_template('survey.html')
 
# ============================================================================
# PATTERN RECOGNITION DASHBOARD API (Added February 5, 2026)
# ============================================================================
@app.route('/api/patterns', methods=['GET'])
def get_user_patterns():
    """
    API endpoint to retrieve user patterns for dashboard
    
    Returns:
        JSON with categorized patterns and statistics
    """
    try:
        # Initialize intelligence engine
        from enhanced_intelligence import EnhancedIntelligence
        intelligence = EnhancedIntelligence()
        
        # Get all patterns
        patterns = intelligence.get_all_patterns()
        
        return jsonify({
            'success': True,
            'patterns': patterns
        })
        
    except Exception as e:
        import traceback
        print(f"Error fetching patterns: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
# ============================================================================


@app.route('/health')
def health():
    """Health check endpoint"""
    from config import ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY, GOOGLE_API_KEY
    
    kb_ready = knowledge_base.is_ready if knowledge_base else False
    kb_doc_count = len(knowledge_base.knowledge_index) if knowledge_base else 0
    kb_status = 'initialized' if kb_ready and kb_doc_count > 0 else ('initializing' if knowledge_base else 'not_initialized')
    
    # Check Research Agent status
    research_status = 'disabled'
    try:
        from research_agent import get_research_agent
        ra = get_research_agent()
        research_status = 'enabled' if ra.is_available else 'api_key_missing'
    except:
        research_status = 'not_installed'
    
    # Check Alert System status
    alert_status = 'disabled'
    alert_email_enabled = False
    try:
        from alert_system import get_alert_manager, ENABLE_EMAIL_ALERTS
        am = get_alert_manager()
        alert_status = 'enabled'
        alert_email_enabled = ENABLE_EMAIL_ALERTS
    except:
        alert_status = 'not_installed'
    
    # Check Intelligence Dashboard status
    intelligence_status = 'disabled'
    intelligence_companies = 0
    try:
        from intelligence import get_lead_manager, INDUSTRY_CATEGORIES
        lm = get_lead_manager()
        intelligence_status = 'enabled'
        intelligence_companies = sum(len(c) for c in INDUSTRY_CATEGORIES.values())
    except:
        intelligence_status = 'not_installed'
    
    # Check Marketing Engine status
    marketing_status = 'disabled'
    try:
        from content_marketing_engine import get_content_engine
        ce = get_content_engine()
        marketing_status = 'enabled'
    except:
        marketing_status = 'not_installed'
    
    # Check Avatar Consultation status
    avatar_status = 'disabled'
    try:
        from avatar_consultation_engine import get_avatar_engine
        ae = get_avatar_engine()
        avatar_status = 'enabled'
    except:
        avatar_status = 'not_installed'
    
    # Check Swarm Self-Evaluation status
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
    except:
        evaluation_status = 'not_installed'
    
    # Check Introspection Layer status
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
        # Check for pending notification
        notification = check_introspection_notifications()
        if notification.get('has_notification'):
            introspection_status = 'enabled_with_notification'
    except:
        introspection_status = 'not_installed'
    
    # Check Manual Generator status
    manual_generator_status = 'disabled'
    try:
        from implementation_manual_generator import get_manuals_dashboard
        dashboard = get_manuals_dashboard()
        manual_generator_status = 'enabled'
    except:
        manual_generator_status = 'not_installed'
    
    # Check Project Management status
    project_management_status = 'disabled'
    project_count = 0
    try:
        from database_file_management import get_project_manager
        pm = get_project_manager()
        projects = pm.list_projects(status='all', limit=1000)
        project_count = len(projects)
        project_management_status = 'enabled'
    except:
        project_management_status = 'not_installed'
    
    return jsonify({
        'status': 'healthy',
        'version': 'Sprint 3 Complete + Research + Alerts + Intelligence + Marketing + Avatars + Evaluation + Pattern Schedules + Manual Generator + LinkedIn Poster + Bulletproof Projects + 100MB Upload Limit + Background KB Init',
        'file_upload_limit': '100MB',
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
            'initialization_complete': kb_ready
        },
        'schedule_generator': {
            'status': 'enabled' if SCHEDULE_GENERATOR_AVAILABLE else 'disabled',
            'type': 'pattern_based_conversational'
        },
        'output_formatter': {
            'status': 'enabled' if OUTPUT_FORMATTER_AVAILABLE else 'disabled'
        },
        'research_agent': {
            'status': research_status
        },
        'alert_system': {
            'status': alert_status,
            'email_enabled': alert_email_enabled
        },
        'intelligence_dashboard': {
            'status': intelligence_status,
            'past_clients_indexed': intelligence_companies
        },
        'content_marketing': {
            'status': marketing_status
        },
        'avatar_consultation': {
            'status': avatar_status,
            'avatars': ['david', 'sarah']
        },
        'swarm_evaluation': {
            'status': evaluation_status,
            'last_evaluation': last_evaluation
        },
        'introspection_layer': {
            'status': introspection_status,
            'last_introspection': last_introspection,
            'components': {
                'self_monitoring': 'active',
                'capability_boundaries': 'phase_2',
                'confidence_calibration': 'phase_2',
                'proposals': 'phase_3',
                'goal_alignment': 'active'
            }
        },
        'manual_generator': {
            'status': manual_generator_status,
            'features': [
                'conversational_data_collection',
                'section_drafting',
                'iterative_refinement',
                'lessons_learned',
                'docx_generation'
            ]
        },
        'project_management': {
            'status': project_management_status,
            'total_projects': project_count,
            'features': [
                'project_creation',
                'file_upload_download',
                'conversation_tracking',
                'context_management',
                'project_summaries',
                'checklists_milestones',
                'auto_detection'
            ]
        },
        'features': {
            'sprint_1': {
                'smart_questioning': 'enabled',
                'suggestions': 'enabled', 
                'pattern_tracking': 'enabled'
            },
            'sprint_2': {
                'project_auto_detection': 'enabled',
                'resource_finder': 'enabled',
                'improvement_engine': 'enabled'
            },
            'sprint_3': {
                'enhanced_intelligence': 'enabled',
                'project_dashboard': 'enabled',
                'analytics_dashboard': 'enabled',
                'smart_workflows': 'enabled',
                'integration_hub': 'enabled'
            },
            'research': {
                'industry_news': research_status,
                'regulations': research_status,
                'studies': research_status,
                'competitor_analysis': research_status,
                'lead_finder': research_status
            },
            'alerts': {
                'lead_alerts': alert_status,
                'competitor_alerts': alert_status,
                'regulatory_alerts': alert_status,
                'email_notifications': 'enabled' if alert_email_enabled else 'disabled',
                'scheduled_jobs': alert_status
            },
            'intelligence': {
                'lead_scoring': intelligence_status,
                'pipeline_management': intelligence_status,
                'industry_matching': intelligence_status,
                'ai_actions': intelligence_status
            },
            'marketing': {
                'linkedin_posts': marketing_status,
                'newsletters': marketing_status,
                'content_extraction': marketing_status,
                'approval_workflow': marketing_status,
                'linkedin_poster_download': 'enabled'
            },
            'avatar_consultation': {
                'tag_team_avatars': avatar_status,
                'voice_text_input': avatar_status,
                'smart_questioning': avatar_status,
                'lead_capture': avatar_status,
                'conversation_logging': avatar_status
            },
            'swarm_evaluation': {
                'performance_metrics': evaluation_status,
                'market_scanning': evaluation_status,
                'gap_analysis': evaluation_status,
                'recommendations': evaluation_status,
                'weekly_reports': evaluation_status
            },
            'introspection': {
                'self_monitoring': introspection_status,
                'capability_boundaries': 'phase_2',
                'confidence_calibration': 'phase_2',
                'self_modification_proposals': 'phase_3',
                'goal_alignment': introspection_status,
                'reflection_narrative': introspection_status,
                'notification_system': introspection_status
            },
            'schedule_generator': {
                'pattern_based': SCHEDULE_GENERATOR_AVAILABLE,
                'conversational': SCHEDULE_GENERATOR_AVAILABLE,
                'shift_lengths': ['8_hour', '12_hour'],
                'patterns_12hr': ['2-2-3', '2-3-2', '3-2-2-3', '4-3', '4-4', 'dupont'],
                'patterns_8hr': ['5-2-fixed', '6-3-fixed', 'southern_swing', '6-2-rotating'],
                'visual_excel_output': True,
                'color_coded': True
            },
            'manual_generator': {
                'conversational_flow': manual_generator_status,
                'question_driven': manual_generator_status,
                'section_drafting': manual_generator_status,
                'iterative_refinement': manual_generator_status,
                'lessons_learned': manual_generator_status,
                'docx_output': manual_generator_status
            },
            'project_management': {
                'create_projects': project_management_status,
                'file_upload': project_management_status,
                'file_download': project_management_status,
                'conversation_tracking': project_management_status,
                'context_management': project_management_status,
                'project_summaries': project_management_status,
                'search': project_management_status,
                'checklists': project_management_status,
                'milestones': project_management_status
            },
            'desktop_apps': {
                'linkedin_poster': 'available',
                'cost_calculator': 'available',
                'survey_processor': 'available'
            }
        }
    })

# Register blueprints (CRITICAL - THIS MAKES THE API WORK)
from routes.core import core_bp
from routes.analysis import analysis_bp
from routes.survey import survey_bp
app.register_blueprint(core_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(survey_bp)

# ============================================================================
# ORCHESTRATION HANDLER BLUEPRINT (Main AI Processing) - February 1, 2026
# ============================================================================
from routes.orchestration_handler import orchestration_bp
app.register_blueprint(orchestration_bp)
print("✅ Orchestration Handler API registered")
# ============================================================================

# ============================================================================
# BULLETPROOF PROJECT MANAGEMENT BLUEPRINT (Added January 30, 2026)
# ============================================================================
print("🔍 DEBUG: About to import bulletproof project routes...")
try:
    print("🔍 DEBUG: Attempting import from routes.projects_bulletproof...")
    from routes.projects_bulletproof import projects_bp
    print("🔍 DEBUG: Import successful! projects_bp =", projects_bp)
    print("🔍 DEBUG: Registering blueprint...")
    app.register_blueprint(projects_bp)
    print("✅ Bulletproof Project Management API registered")
    print("   - 15 production-ready endpoints")
    print("   - Complete project lifecycle")
    print("   - File management that actually works")
    print("   - Conversation tracking")
    print("   - Context persistence")
except ImportError as e:
    print(f"❌ IMPORT ERROR: Bulletproof Project Management routes not found")
    print(f"   Error details: {e}")
    import traceback
    print(f"   Traceback: {traceback.format_exc()}")
except Exception as e:
    print(f"❌ EXCEPTION: Bulletproof Project Management registration failed")
    print(f"   Error details: {e}")
    import traceback
    print(f"   Traceback: {traceback.format_exc()}")
# ============================================================================

# ============================================================================
# VOICE CONTROL WEBSOCKET (Added January 27, 2026)
# ============================================================================
try:
    from routes.voice import voice_bp, register_voice_websocket
    app.register_blueprint(voice_bp)
    register_voice_websocket(app)
    print("✅ Voice Control WebSocket registered")
except ImportError as e:
    print(f"ℹ️  Voice Control routes not found: {e}")
except Exception as e:
    print(f"⚠️  Voice Control registration failed: {e}")
# ============================================================================
# RESEARCH AGENT BLUEPRINT (Added January 23, 2026)
# ============================================================================
try:
    from routes.research import research_bp
    app.register_blueprint(research_bp)
    print("✅ Research Agent API registered")
except ImportError:
    print("ℹ️  Research Agent routes not found - research features disabled")
except Exception as e:
    print(f"⚠️  Research Agent registration failed: {e}")

# ============================================================================
# ALERT SYSTEM BLUEPRINT (Added January 23, 2026)
# ============================================================================
try:
    from routes.alerts import alerts_bp
    app.register_blueprint(alerts_bp)
    print("✅ Alert System API registered")
except ImportError:
    print("ℹ️  Alert System routes not found - alert features disabled")
except Exception as e:
    print(f"⚠️  Alert System registration failed: {e}")

# ============================================================================
# INTELLIGENCE DASHBOARD BLUEPRINT (Added January 23, 2026)
# ============================================================================
try:
    from routes.intelligence import intelligence_bp
    app.register_blueprint(intelligence_bp)
    print("✅ Intelligence Dashboard API registered")
except ImportError as e:
    print(f"ℹ️  Intelligence Dashboard routes not found: {e}")
except Exception as e:
    print(f"⚠️  Intelligence Dashboard registration failed: {e}")

# ============================================================================
# CONTENT MARKETING ENGINE BLUEPRINT (Added January 25, 2026)
# ============================================================================
try:
    from routes.marketing import marketing_bp
    app.register_blueprint(marketing_bp)
    print("✅ Content Marketing Engine API registered")
except ImportError as e:
    print(f"ℹ️  Content Marketing Engine routes not found: {e}")
except Exception as e:
    print(f"⚠️  Content Marketing Engine registration failed: {e}")

# ============================================================================
# AVATAR CONSULTATION SYSTEM BLUEPRINT (Added January 25, 2026)
# ============================================================================
try:
    from routes.avatar import avatar_bp
    app.register_blueprint(avatar_bp)
    print("✅ Avatar Consultation System API registered")
except ImportError as e:
    print(f"ℹ️  Avatar Consultation routes not found: {e}")
except Exception as e:
    print(f"⚠️  Avatar Consultation registration failed: {e}")

# ============================================================================
# SWARM SELF-EVALUATION BLUEPRINT (Added January 25, 2026)
# ============================================================================
try:
    from routes.evaluation import evaluation_bp
    app.register_blueprint(evaluation_bp)
    print("✅ Swarm Self-Evaluation API registered")
except ImportError as e:
    print(f"ℹ️  Swarm Self-Evaluation routes not found: {e}")
except Exception as e:
    print(f"⚠️  Swarm Self-Evaluation registration failed: {e}")

# ============================================================================
# INTROSPECTION LAYER BLUEPRINT (Added January 25, 2026)
# ============================================================================
try:
    from routes.introspection import introspection_bp
    app.register_blueprint(introspection_bp)
    print("✅ Introspection Layer API registered")
except ImportError as e:
    print(f"ℹ️  Introspection Layer routes not found: {e}")
except Exception as e:
    print(f"⚠️  Introspection Layer registration failed: {e}")

# ============================================================================
# IMPLEMENTATION MANUAL GENERATOR BLUEPRINT (Added January 28, 2026)
# ============================================================================
try:
    from routes.manuals import manuals_bp
    app.register_blueprint(manuals_bp)
    print("✅ Implementation Manual Generator API registered")
except ImportError as e:
    print(f"ℹ️  Implementation Manual Generator routes not found: {e}")
except Exception as e:
    print(f"⚠️  Implementation Manual Generator registration failed: {e}")

# ============================================================================
# ADAPTIVE LEARNING ENGINE BLUEPRINT (Added February 2, 2026 - PHASE 1)
# ============================================================================
try:
    from routes.learning import learning_bp
    app.register_blueprint(learning_bp)
    print("✅ Adaptive Learning Engine API registered")
except ImportError as e:
    print(f"ℹ️  Adaptive Learning Engine routes not found: {e}")
except Exception as e:
    print(f"⚠️  Adaptive Learning Engine registration failed: {e}")

# ============================================================================
# PREDICTIVE INTELLIGENCE BLUEPRINT (Added February 2, 2026 - PHASE 2)
# ============================================================================
try:
    from routes.predictive import predictive_bp
    app.register_blueprint(predictive_bp)
    print("✅ Predictive Intelligence API registered")
except ImportError as e:
    print(f"ℹ️  Predictive Intelligence routes not found: {e}")
except Exception as e:
    print(f"⚠️  Predictive Intelligence registration failed: {e}")

# ============================================================================
# SELF-OPTIMIZATION ENGINE BLUEPRINT (Added February 2, 2026 - PHASE 3)
# ============================================================================
try:
    from routes.optimization import optimization_bp
    app.register_blueprint(optimization_bp)
    print("✅ Self-Optimization Engine API registered")
except ImportError as e:
    print(f"ℹ️  Self-Optimization Engine routes not found: {e}")
except Exception as e:
    print(f"⚠️  Self-Optimization Engine registration failed: {e}")


# ============================================================================
# KNOWLEDGE INGESTION SYSTEM BLUEPRINT (Added February 2, 2026)
# ============================================================================
try:
    from routes.ingest import ingest_bp
    app.register_blueprint(ingest_bp)
    print("✅ Knowledge Ingestion API registered")
except ImportError as e:
    print(f"ℹ️  Knowledge Ingestion routes not found: {e}")
except Exception as e:
    print(f"⚠️  Knowledge Ingestion registration failed: {e}")

# ============================================================================
# CONVERSATION LEARNING SYSTEM BLUEPRINT (Added February 4, 2026)
# Combines automatic background learning + manual extraction
# ============================================================================
try:
    from routes.conversation_learning import learning_bp
    app.register_blueprint(learning_bp)
    print("✅ Unified Conversation Learning API registered")
    print("   - Automatic: learn_from_conversation()")
    print("   - Manual: /api/conversations/{id}/extract-lessons")
except ImportError as e:
    print(f"ℹ️  Conversation Learning routes not found: {e}")
except Exception as e:
    print(f"⚠️  Conversation Learning registration failed: {e}")

# ============================================================================
# PATTERN RECOGNITION ROUTES (Added February 5, 2026)
# ============================================================================
try:
    from routes.pattern_recognition import pattern_bp
    app.register_blueprint(pattern_bp)
    print("✅ Pattern Recognition API registered")
except ImportError as e:
    print(f"ℹ️  Pattern Recognition routes not found: {e}")
except Exception as e:
    print(f"⚠️  Pattern Recognition registration failed: {e}")

# ============================================================================
# PHASE 1 INTELLIGENCE UPGRADES (Added February 5, 2026)
# Voice learning, proactive curiosity, pattern recognition dashboard
# ============================================================================
try:
    from routes.phase1_intelligence import intelligence_bp
    app.register_blueprint(intelligence_bp)
    print("✅ Phase 1 Intelligence API registered")
    print("   - Voice conversation learning")
    print("   - Proactive curiosity engine")
    print("   - Pattern recognition dashboard")
except ImportError as e:
    print(f"ℹ️  Phase 1 Intelligence routes not found: {e}")
except Exception as e:
    print(f"⚠️  Phase 1 Intelligence registration failed: {e}")

# ============================================================================
# BACKGROUND FILE PROCESSOR BLUEPRINT (Added February 5, 2026)
# Handles large files (50MB+) in background threads
# ============================================================================
try:
    from routes.background_jobs import background_jobs_bp
    app.register_blueprint(background_jobs_bp)
    print("✅ Background File Processor API registered")
    print("   - Process files 50MB+ in background")
    print("   - 1,000 row chunks")
    print("   - Progress tracking")
    print("   - Job status API")
except ImportError as e:
    print(f"ℹ️  Background File Processor routes not found: {e}")
except Exception as e:
    print(f"⚠️  Background File Processor registration failed: {e}")

# ============================================================================
# KNOWLEDGE BACKUP SYSTEM BLUEPRINT (Added February 4, 2026)
# ============================================================================
try:
    from knowledge_backup_routes import knowledge_backup_bp
    app.register_blueprint(knowledge_backup_bp)
    print("✅ Knowledge Backup System API registered")
except ImportError as e:
    print(f"ℹ️  Knowledge Backup routes not found: {e}")
except Exception as e:
    print(f"⚠️  Knowledge Backup registration failed: {e}")

# Add HTML route for Knowledge Management UI
@app.route('/knowledge')
def knowledge_management():
    """Knowledge Management interface - Shoulders of Giants system"""
    return render_template('knowledge_management.html')

# Sprint 3 blueprints
try:
    from project_dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)
    print("✅ Project Dashboard API registered")
except ImportError:
    print("ℹ️  Project Dashboard not found")

try:
    from analytics_engine import analytics_bp
    app.register_blueprint(analytics_bp)
    print("✅ Analytics API registered")
except ImportError:
    print("ℹ️  Analytics Engine not found")

try:
    from workflow_engine import workflow_bp
    app.register_blueprint(workflow_bp)
    print("✅ Workflow Engine API registered")
except ImportError:
    print("ℹ️  Workflow Engine not found")

try:
    from integration_hub import integration_bp
    app.register_blueprint(integration_bp)
    print("✅ Integration Hub API registered")
except ImportError:
    print("ℹ️  Integration Hub not found")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)

# I did no harm and this file is not truncated
