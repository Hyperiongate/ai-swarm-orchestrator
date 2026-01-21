"""
AI SWARM ORCHESTRATOR - Main Application (REFACTORED)
Created: January 18, 2026
Last Updated: January 21, 2026

MAJOR REFACTORING:
- Broke up 2,500 line monster file into logical modules
- No more indentation nightmares
- Easy to find and fix things
- Each file is ~100-300 lines instead of thousands

SCHEDULE GENERATOR FIX (January 21, 2026):
- Added proper schedule_generator module loading
- Fixed SCHEDULE_GENERATOR_AVAILABLE flag
- Enables Excel file generation for schedule requests

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
        print(f"  ⚠️ No project files found in checked paths")
        found_path = "."
    
    kb = get_knowledge_base(found_path)
    if kb and kb.documents:
        knowledge_base = kb
        print(f"  ✅ Loaded {len(knowledge_base.documents)} documents")
    else:
        print(f"  ⚠️ Knowledge base initialized but no documents loaded")
        
except Exception as e:
    print(f"  ❌ Could not initialize knowledge base: {e}")

# SCHEDULE GENERATOR MODULE - Load it properly
SCHEDULE_GENERATOR_AVAILABLE = False
try:
    from schedule_generator import get_schedule_generator
    SCHEDULE_GENERATOR_AVAILABLE = True
    print("✅ Schedule Generator loaded successfully")
except ImportError as e:
    print(f"⚠️  Warning: schedule_generator module not found: {e}")
    print("   Schedule generation will not be available")

# OUTPUT FORMATTER MODULE - Optional enhancement
OUTPUT_FORMATTER_AVAILABLE = False
try:
    from output_formatter import get_output_formatter
    OUTPUT_FORMATTER_AVAILABLE = True
    print("✅ Output Formatter loaded")
except ImportError:
    print("⚠️  Output Formatter not available")

# Register blueprints
from routes.core import core_bp
app.register_blueprint(core_bp)

# Make schedule generator available to routes
app.config['SCHEDULE_GENERATOR_AVAILABLE'] = SCHEDULE_GENERATOR_AVAILABLE
if SCHEDULE_GENERATOR_AVAILABLE:
    app.config['SCHEDULE_GENERATOR'] = get_schedule_generator()

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
    return jsonify({
        'status': 'healthy',
        'knowledge_base': len(knowledge_base.documents) if knowledge_base else 0,
        'schedule_generator': SCHEDULE_GENERATOR_AVAILABLE,
        'output_formatter': OUTPUT_FORMATTER_AVAILABLE
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

# I did no harm and this file is not truncated
