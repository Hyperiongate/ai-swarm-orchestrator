"""
AI SWARM ORCHESTRATOR - Main Application
Created: January 18, 2026
Last Updated: January 22, 2026 - SPRINT 2: Auto-Migration Added

CHANGES IN THIS VERSION:
- January 22, 2026: SPRINT 2 AUTO-MIGRATIONS
  * Database upgrades run automatically on startup
  * No manual migration commands needed
  * Safe to run multiple times (checks before adding)

- January 22, 2026: PROACTIVE INTELLIGENCE FULLY INTEGRATED
  * Smart questioning before task execution
  * Post-task suggestions for next steps
  * Pattern tracking for automation opportunities
  * Seamless integration with routes/core.py

ARCHITECTURE:
- config.py: All configuration
- database.py: All database operations (now includes proactive tables)
- orchestration/: All AI logic + NEW proactive_agent.py
- routes/: All Flask endpoints (core.py uses ProactiveAgent)
- app.py (this file): Bootstrap and initialization

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Flask, render_template, jsonify
from database import init_db
import os

# Initialize Flask
app = Flask(__name__)

# Initialize database (includes proactive intelligence tables)
init_db()

# ============================================================================
# SPRINT 2: AUTO-RUN DATABASE MIGRATIONS
# ============================================================================
print("🔄 Checking for Sprint 2 database upgrades...")
try:
    from upgrade_database_sprint2 import upgrade_database_sprint2
    from add_resource_searches_table import add_resource_searches_table
    from add_improvement_reports_table import add_improvement_reports_table
    
    # Run migrations automatically
    upgrade_database_sprint2()
    add_resource_searches_table()
    add_improvement_reports_table()
    print("✅ Sprint 2 database migrations complete!")
    
except ImportError as e:
    print(f"ℹ️  Sprint 2 migrations not found yet: {e}")
except Exception as e:
    print(f"⚠️  Sprint 2 migration warning: {e}")
# ============================================================================

# Initialize knowledge base
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
        knowledge_base.initialize()
        print(f"  ✅ Knowledge Base Ready: {len(knowledge_base.knowledge_index)} documents indexed")
        
except Exception as e:
    print(f"  ⚠️ Warning: Knowledge Base initialization failed: {e}")
    import traceback
    print(f"  Traceback: {traceback.format_exc()}")
    knowledge_base = None

# Load optional modules
SCHEDULE_GENERATOR_AVAILABLE = False
try:
    from schedule_generator import get_schedule_generator
    SCHEDULE_GENERATOR_AVAILABLE = True
    schedule_gen = get_schedule_generator()
    print("✅ Schedule Generator loaded")
    
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

@app.route('/workflow')
def workflow():
    """Workflow interface"""
    return render_template('index_workflow.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    from config import ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY, GOOGLE_API_KEY
    
    kb_status = 'initialized' if knowledge_base and len(knowledge_base.knowledge_index) > 0 else 'not_initialized'
    kb_doc_count = len(knowledge_base.knowledge_index) if knowledge_base else 0
    
    return jsonify({
        'status': 'healthy',
        'version': 'Sprint 2 - Project Auto-Detection + Resource Finder + Improvement Engine',
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
            'documents_indexed': kb_doc_count
        },
        'schedule_generator': {
            'status': 'enabled' if SCHEDULE_GENERATOR_AVAILABLE else 'disabled'
        },
        'output_formatter': {
            'status': 'enabled' if OUTPUT_FORMATTER_AVAILABLE else 'disabled'
        },
        'proactive_intelligence': {
            'status': 'enabled',
            'features': [
                'smart_questioning',
                'suggestions', 
                'pattern_tracking',
                'project_auto_detection',      # Sprint 2
                'resource_finder',              # Sprint 2
                'improvement_engine'            # Sprint 2
            ]
        }
    })

# Register blueprints (CRITICAL - THIS MAKES THE API WORK)
# Now includes proactive intelligence in routes/core.py
from routes.core import core_bp
app.register_blueprint(core_bp)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)

# I did no harm and this file is not truncated
