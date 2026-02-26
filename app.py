"""
AI SWARM ORCHESTRATOR - Main Application   
Created: January 18, 2026
Last Updated: February 25, 2026 - ADDED /api/admin/kb-diagnose ENDPOINT

CHANGELOG:

- February 25, 2026: ADDED /api/admin/kb-diagnose ENDPOINT
  Added a real-time diagnostic endpoint that calls knowledge_base.get_index_status()
  to show exactly what the KB loaded, from which path, how many files it found,
  and whether the safety guard triggered. Use this after every deploy to confirm
  the KB initialized correctly without reading Render logs line by line.
  Visit: /api/admin/kb-diagnose in browser after deploy.

- February 23, 2026: ADDED Blog Posts Table Migration
  Added add_blog_posts_table() migration to run on startup. This creates the
  blog_posts table required by the Blog Post Generator feature. Migration runs
  automatically after Sprint 3 migrations.

- February 22, 2026: RE-ENABLED Case Study Generator (routes/case_studies.py)
  Was temporarily disabled during crash debugging. Root cause of crash was unrelated.
  Generator re-enabled with full try/except protection as originally designed.
  Also removed the 3-line stderr->stdout diagnostic added earlier today (no longer needed).

- February 20, 2026: BUG FIX #1 - intelligence_bp name conflict (CRITICAL - CRASH ON STARTUP)
- February 20, 2026: BUG FIX #2 - conversation_learning import path (SILENT FEATURE FAILURE)
- February 18, 2026: FIXED NameError crash on startup
- February 18, 2026: BACKGROUND KB INIT
- February 5, 2026: INCREASED FILE UPLOAD LIMIT TO 100MB
- January 30, 2026: ADDED BULLETPROOF PROJECT MANAGEMENT
- January 29, 2026: ADDED LINKEDIN POSTER DOWNLOAD BUTTON
- January 28, 2026: ADDED IMPLEMENTATION MANUAL GENERATOR
- January 26, 2026: UPDATED FOR PATTERN-BASED SCHEDULE SYSTEM
- January 25, 2026: ADDED SWARM SELF-EVALUATION SYSTEM
- January 25, 2026: ADDED CONTENT MARKETING ENGINE
- January 23, 2026: ADDED CLIENT INTELLIGENCE DASHBOARD
- January 23, 2026: ADDED ALERT SYSTEM (Autonomous Monitoring)
- January 23, 2026: ADDED RESEARCH AGENT
- January 22, 2026: SPRINT 3 - ALL 5 ADVANCED FEATURES
- January 22, 2026: SPRINT 2 - PROACTIVE INTELLIGENCE
- January 22, 2026: SPRINT 1 - PROACTIVE INTELLIGENCE

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Flask, render_template, jsonify
from database import init_db
from database_survey_additions import add_surveys_table
import os
from flask import send_from_directory

# Initialize Flask
app = Flask(__name__)

# ============================================================================
# CRITICAL FILE UPLOAD CONFIGURATION (Added February 5, 2026)
# ============================================================================
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
print("📤 File Upload Limit: 100MB (allows large project files)")
# ============================================================================

# CRITICAL: Configure session for schedule conversation memory (Added January 26, 2026)
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
# AUTO-RUN ALL DATABASE MIGRATIONS (SPRINTS 2 & 3 + BLOG POSTS)
# ============================================================================
print("🔄 Running database migrations...")

# Projects table migration (CRITICAL - runs first)
try:
    from migrate_projects_table import migrate_projects_table
    migrate_projects_table()
except Exception as e:
    print(f"ℹ️  Projects migration: {e}")

# Blog Posts table migration (CRITICAL - for SEO optimization)
print("🔍 DEBUG: About to attempt blog_posts migration import...")
try:
    from add_blog_posts_table import add_blog_posts_table
    print("🔍 DEBUG: Import successful, calling function...")
    add_blog_posts_table()
    print("✅ Blog Posts table migration complete!")
except ImportError as ie:
    print(f"❌ Blog Posts migration IMPORT ERROR: {ie}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"⚠️  Blog Posts migration failed: {e}")
    import traceback
    traceback.print_exc()

# Sprint 2 migrations (safe to fail if files missing)
try:
    from upgrade_database_sprint2 import upgrade_database_sprint2
    upgrade_database_sprint2()
except Exception as e:
    print(f"ℹ️  Sprint 2 core migration: {e}")

try:
    from add_resource_searches_table import add_resource_searches_table
    add_resource_searches_table()
except Exception as e:
    print(f"ℹ️  Resource searches migration: {e}")

try:
    from add_improvement_reports_table import add_improvement_reports_table
    add_improvement_reports_table()
except Exception as e:
    print(f"ℹ️  Improvement reports migration: {e}")

try:
    from add_conversation_context_table import add_conversation_context_table
    add_conversation_context_table()
    print("✅ Conversation context table added!")
except Exception as e:
    print(f"ℹ️  Conversation context migration: {e}")

# Sprint 3 migrations (safe to fail if files missing)
try:
    from add_user_profiles_table import add_user_profiles_table
    add_user_profiles_table()
except Exception as e:
    print(f"ℹ️  User profiles migration: {e}")

try:
    from add_workflow_tables import add_workflow_tables
    add_workflow_tables()
except Exception as e:
    print(f"ℹ️  Workflow tables migration: {e}")

try:
    from add_integration_logs_table import add_integration_logs_table
    add_integration_logs_table()
except Exception as e:
    print(f"ℹ️  Integration logs migration: {e}")

print("✅ Database migrations complete!")

# ============================================================================

# ============================================================================
# INITIALIZE BULLETPROOF PROJECT MANAGEMENT (Added January 30, 2026)
# ============================================================================
print("🔧 Initializing Bulletproof Project Management...")
try:
    from database_file_management import get_project_manager
    pm = get_project_manager()
    app.config['PROJECT_MANAGER'] = pm
    print("✅ Bulletproof Project Manager initialized")
except Exception as e:
    print(f"⚠️  Project Manager initialization failed: {e}")
# ============================================================================

# ============================================================================
# INITIALIZE KNOWLEDGE BASE IN BACKGROUND THREAD
# ============================================================================
print("🔍 Initializing Project Knowledge Base...")
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
                print(f"  📁 Found directory: {path} ({file_count} files)")
                break

    if not found_path:
        print(f"  ⚠️ No project files found. Checked: {project_paths}")
        print(f"  ℹ️  Knowledge base features disabled until files are added")
    else:
        knowledge_base = ProjectKnowledgeBase(project_path=found_path)
        knowledge_base.initialize_background()
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
# =============================================================================

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
# KB DIAGNOSE ENDPOINT (Added February 25, 2026)
# ============================================================================
@app.route('/api/admin/kb-diagnose', methods=['GET'])
def kb_diagnose():
    """
    Real-time knowledge base diagnostic endpoint.

    Shows exactly what the KB loaded, from which path, how many files were
    found, whether the safety guard triggered, and what's currently in the
    database. Use this after every deploy to confirm KB health without
    reading Render logs line by line.

    Usage: Visit /api/admin/kb-diagnose in browser after deploy.
    """
    if knowledge_base is None:
        return jsonify({
            'success': False,
            'error': 'Knowledge base object was never created. Check startup logs.',
            'knowledge_base_initialized': False
        }), 503

    try:
        status = knowledge_base.get_index_status()
        return jsonify({
            'success': True,
            'knowledge_base_initialized': True,
            **status
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500
# ============================================================================

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
        except:
            pass

    try:
        from document_ingestion_engine import get_document_ingestor
        ingestor = get_document_ingestor()
        results['api_uses_path'] = ingestor.db_path
    except:
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

    kb_ready = knowledge_base.is_ready if knowledge_base else False
    kb_doc_count = len(knowledge_base.knowledge_index) if knowledge_base else 0
    kb_status = 'initialized' if kb_ready and kb_doc_count > 0 else ('initializing' if knowledge_base else 'not_initialized')

    research_status = 'disabled'
    try:
        from research_agent import get_research_agent
        ra = get_research_agent()
        research_status = 'enabled' if ra.is_available else 'api_key_missing'
    except:
        research_status = 'not_installed'

    alert_status = 'disabled'
    alert_email_enabled = False
    try:
        from alert_system import get_alert_manager, ENABLE_EMAIL_ALERTS
        am = get_alert_manager()
        alert_status = 'enabled'
        alert_email_enabled = ENABLE_EMAIL_ALERTS
    except:
        alert_status = 'not_installed'

    intelligence_status = 'disabled'
    intelligence_companies = 0
    try:
        from intelligence import get_lead_manager, INDUSTRY_CATEGORIES
        lm = get_lead_manager()
        intelligence_status = 'enabled'
        intelligence_companies = sum(len(c) for c in INDUSTRY_CATEGORIES.values())
    except:
        intelligence_status = 'not_installed'

    marketing_status = 'disabled'
    try:
        from content_marketing_engine import get_content_engine
        ce = get_content_engine()
        marketing_status = 'enabled'
    except:
        marketing_status = 'not_installed'

    avatar_status = 'disabled'
    try:
        from avatar_consultation_engine import get_avatar_engine
        ae = get_avatar_engine()
        avatar_status = 'enabled'
    except:
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
    except:
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
    except:
        introspection_status = 'not_installed'

    manual_generator_status = 'disabled'
    try:
        from implementation_manual_generator import get_manuals_dashboard
        dashboard = get_manuals_dashboard()
        manual_generator_status = 'enabled'
    except:
        manual_generator_status = 'not_installed'

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

    case_studies_status = 'disabled'
    try:
        from case_study_generator import INDUSTRY_DISPLAY_NAMES
        case_studies_status = 'enabled'
    except:
        case_studies_status = 'not_installed'
        
    blog_posts_status = 'disabled'
    try:
        from blog_post_generator import BLOG_TOPICS
        blog_posts_status = 'enabled'
    except:
        blog_posts_status = 'not_installed'

    return jsonify({
        'status': 'healthy',
        'version': 'Sprint 3 Complete + Research + Alerts + Intelligence + Marketing + Avatars + Evaluation + Pattern Schedules + Manual Generator + LinkedIn Poster + Bulletproof Projects + 100MB Upload Limit + Background KB Init + NameError Fix Feb18 + Blueprint Fix Feb20 + Case Studies Feb21 + Blog Posts Feb23 + KB Safety Guard + KB Diagnose Feb25',
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
        }
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
print("✅ Orchestration Handler API registered")

print("🔍 DEBUG: About to import bulletproof project routes...")
try:
    from routes.projects_bulletproof import projects_bp
    app.register_blueprint(projects_bp)
    print("✅ Bulletproof Project Management API registered")
except ImportError as e:
    print(f"❌ IMPORT ERROR: Bulletproof Project Management routes not found: {e}")
except Exception as e:
    print(f"❌ EXCEPTION: Bulletproof Project Management registration failed: {e}")

try:
    from routes.voice import voice_bp, register_voice_websocket
    app.register_blueprint(voice_bp)
    register_voice_websocket(app)
    print("✅ Voice Control WebSocket registered")
except ImportError as e:
    print(f"ℹ️  Voice Control routes not found: {e}")
except Exception as e:
    print(f"⚠️  Voice Control registration failed: {e}")

try:
    from routes.research import research_bp
    app.register_blueprint(research_bp)
    print("✅ Research Agent API registered")
except ImportError:
    print("ℹ️  Research Agent routes not found - research features disabled")
except Exception as e:
    print(f"⚠️  Research Agent registration failed: {e}")

try:
    from routes.alerts import alerts_bp
    app.register_blueprint(alerts_bp)
    print("✅ Alert System API registered")
except ImportError:
    print("ℹ️  Alert System routes not found - alert features disabled")
except Exception as e:
    print(f"⚠️  Alert System registration failed: {e}")

try:
    from routes.intelligence import intelligence_bp
    app.register_blueprint(intelligence_bp)
    print("✅ Intelligence Dashboard API registered")
except ImportError as e:
    print(f"ℹ️  Intelligence Dashboard routes not found: {e}")
except Exception as e:
    print(f"⚠️  Intelligence Dashboard registration failed: {e}")

try:
    from routes.marketing import marketing_bp
    app.register_blueprint(marketing_bp)
    print("✅ Content Marketing Engine API registered")
except ImportError as e:
    print(f"ℹ️  Content Marketing Engine routes not found: {e}")
except Exception as e:
    print(f"⚠️  Content Marketing Engine registration failed: {e}")

try:
    from routes.avatar import avatar_bp
    app.register_blueprint(avatar_bp)
    print("✅ Avatar Consultation System API registered")
except ImportError as e:
    print(f"ℹ️  Avatar Consultation routes not found: {e}")
except Exception as e:
    print(f"⚠️  Avatar Consultation registration failed: {e}")

try:
    from routes.evaluation import evaluation_bp
    app.register_blueprint(evaluation_bp)
    print("✅ Swarm Self-Evaluation API registered")
except ImportError as e:
    print(f"ℹ️  Swarm Self-Evaluation routes not found: {e}")
except Exception as e:
    print(f"⚠️  Swarm Self-Evaluation registration failed: {e}")

try:
    from routes.introspection import introspection_bp
    app.register_blueprint(introspection_bp)
    print("✅ Introspection Layer API registered")
except ImportError as e:
    print(f"ℹ️  Introspection Layer routes not found: {e}")
except Exception as e:
    print(f"⚠️  Introspection Layer registration failed: {e}")

try:
    from routes.manuals import manuals_bp
    app.register_blueprint(manuals_bp)
    print("✅ Implementation Manual Generator API registered")
except ImportError as e:
    print(f"ℹ️  Implementation Manual Generator routes not found: {e}")
except Exception as e:
    print(f"⚠️  Implementation Manual Generator registration failed: {e}")

try:
    from routes.learning import learning_bp
    app.register_blueprint(learning_bp)
    print("✅ Adaptive Learning Engine API registered")
except ImportError as e:
    print(f"ℹ️  Adaptive Learning Engine routes not found: {e}")
except Exception as e:
    print(f"⚠️  Adaptive Learning Engine registration failed: {e}")

try:
    from routes.predictive import predictive_bp
    app.register_blueprint(predictive_bp)
    print("✅ Predictive Intelligence API registered")
except ImportError as e:
    print(f"ℹ️  Predictive Intelligence routes not found: {e}")
except Exception as e:
    print(f"⚠️  Predictive Intelligence registration failed: {e}")

try:
    from routes.optimization import optimization_bp
    app.register_blueprint(optimization_bp)
    print("✅ Self-Optimization Engine API registered")
except ImportError as e:
    print(f"ℹ️  Self-Optimization Engine routes not found: {e}")
except Exception as e:
    print(f"⚠️  Self-Optimization Engine registration failed: {e}")

try:
    from routes.ingest import ingest_bp
    app.register_blueprint(ingest_bp)
    print("✅ Knowledge Ingestion API registered")
except ImportError as e:
    print(f"ℹ️  Knowledge Ingestion routes not found: {e}")
except Exception as e:
    print(f"⚠️  Knowledge Ingestion registration failed: {e}")

try:
    from conversation_learning import learning_bp as conv_learning_bp
    app.register_blueprint(conv_learning_bp)
    print("✅ Unified Conversation Learning API registered")
except ImportError as e:
    print(f"ℹ️  Conversation Learning routes not found: {e}")
except Exception as e:
    print(f"⚠️  Conversation Learning registration failed: {e}")

try:
    from routes.pattern_recognition import pattern_bp
    app.register_blueprint(pattern_bp)
    print("✅ Pattern Recognition API registered")
except ImportError as e:
    print(f"ℹ️  Pattern Recognition routes not found: {e}")
except Exception as e:
    print(f"⚠️  Pattern Recognition registration failed: {e}")

try:
    from routes.phase1_intelligence import intelligence_bp as phase1_intelligence_bp
    app.register_blueprint(phase1_intelligence_bp, name='phase1_intelligence')
    print("✅ Phase 1 Intelligence API registered")
except ImportError as e:
    print(f"ℹ️  Phase 1 Intelligence routes not found: {e}")
except Exception as e:
    print(f"⚠️  Phase 1 Intelligence registration failed: {e}")

try:
    from routes.case_studies import case_studies_bp
    app.register_blueprint(case_studies_bp)
    print("✅ Case Study Generator API registered")
except ImportError as e:
    print(f"ℹ️  Case Study Generator routes not found: {e}")
except Exception as e:
    print(f"⚠️  Case Study Generator registration failed: {e}")

# ============================================================================
# BLOG POST GENERATOR BLUEPRINT (Added February 23, 2026)
# ============================================================================
try:
    from routes.blog_posts import blog_posts_bp
    app.register_blueprint(blog_posts_bp)
    print("✅ Blog Post Generator API registered")
except ImportError as e:
    print(f"ℹ️  Blog Post Generator routes not found: {e}")
except Exception as e:
    print(f"⚠️  Blog Post Generator registration failed: {e}")
# ============================================================================

try:
    from routes.background_jobs import background_jobs_bp
    app.register_blueprint(background_jobs_bp)
    print("✅ Background File Processor API registered")
except ImportError as e:
    print(f"ℹ️  Background File Processor routes not found: {e}")
except Exception as e:
    print(f"⚠️  Background File Processor registration failed: {e}")

try:
    from knowledge_backup_routes import knowledge_backup_bp
    app.register_blueprint(knowledge_backup_bp)
    print("✅ Knowledge Backup System API registered")
except ImportError as e:
    print(f"ℹ️  Knowledge Backup routes not found: {e}")
except Exception as e:
    print(f"⚠️  Knowledge Backup registration failed: {e}")

@app.route('/knowledge')
def knowledge_management():
    """Knowledge Management interface - Shoulders of Giants system"""
    return render_template('knowledge_management.html')

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
