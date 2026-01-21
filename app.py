"""
AI SWARM ORCHESTRATOR - Main Application (REFACTORED)
Created: January 18, 2026
Last Updated: January 21, 2026

MAJOR REFACTORING:
- Broke up 2,500 line monster file into logical modules
- No more indentation nightmares
- Easy to find and fix things
- Each file is ~100-300 lines instead of thousands

ARCHITECTURE:
- config.py: All configuration
- database.py: All database operations  
- orchestration/: All AI logic
- routes/: All Flask endpoints
- app.py (this file): Just imports and runs

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Flask, render_template, jsonify
from database import init_db
import os

# Initialize Flask
app = Flask(__name__)

# Initialize database
init_db()

# Initialize knowledge base
print("🔍 Initializing Project Knowledge Base...")
knowledge_base = None
try:
    from pathlib import Path
    from knowledge_integration import get_knowledge_base
    
    project_paths = ["/mnt/project", "project_files", "./project_files"]
    found_path = None
    
    for path in project_paths:
        if Path(path).exists():
            found_path = path
            file_count = len(list(Path(path).iterdir())) if Path(path).is_dir() else 0
            print(f"  📁 Found directory: {path} ({file_count} files)")
            break
    
    if not found_path:
        print(f"  ⚠️ No project files found. Checked: {project_paths}")
        print(f"  ℹ️  Knowledge base features disabled until files are added")
    else:
        knowledge_base = get_knowledge_base()
        print(f"  ✅ Knowledge Base Ready: {len(knowledge_base.knowledge_index)} documents indexed")
        
except Exception as e:
    print(f"  ⚠️ Warning: Knowledge Base initialization failed: {e}")
    knowledge_base = None

# Load optional modules
SCHEDULE_GENERATOR_AVAILABLE = False
try:
    from schedule_generator import get_schedule_generator
    SCHEDULE_GENERATOR_AVAILABLE = True
    schedule_gen = get_schedule_generator()
    print("✅ Schedule Generator loaded")
except ImportError:
    print("⚠️ Warning: schedule_generator module not found")

OUTPUT_FORMATTER_AVAILABLE = False
try:
    from output_formatter import get_output_formatter
    OUTPUT_FORMATTER_AVAILABLE = True
    print("✅ Output Formatter loaded")
except ImportError:
    print("⚠️ Warning: output_formatter module not found")

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
    """Health check"""
    from config import ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY, GOOGLE_API_KEY
    
    kb_status = 'initialized' if knowledge_base and len(knowledge_base.knowledge_index) > 0 else 'not_initialized'
    kb_doc_count = len(knowledge_base.knowledge_index) if knowledge_base else 0
    
    return jsonify({
        'status': 'healthy',
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
        'output_formatter': {
            'status': 'enabled' if OUTPUT_FORMATTER_AVAILABLE else 'disabled'
        }
    })

# Register blueprints (CRITICAL - THIS MAKES THE API WORK)
from routes.core import core_bp
app.register_blueprint(core_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# I did no harm and this file is not truncated
