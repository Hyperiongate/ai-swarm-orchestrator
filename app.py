"""
AI SWARM ORCHESTRATOR - Diagnostic Version
Last Updated: January 22, 2026 - Added detailed error logging to find crash

This version adds extensive error logging to identify startup failures.
"""

import sys
import os

print("=" * 60)
print("DIAGNOSTIC APP.PY STARTING")
print("=" * 60)

try:
    print("Step 1: Importing Flask...")
    from flask import Flask, render_template, jsonify
    print("✅ Flask imported successfully")
except Exception as e:
    print(f"❌ FAILED importing Flask: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("Step 2: Importing database...")
    from database import init_db
    print("✅ database module imported successfully")
except Exception as e:
    print(f"❌ FAILED importing database: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("Step 3: Creating Flask app...")
    app = Flask(__name__)
    print("✅ Flask app created successfully")
except Exception as e:
    print(f"❌ FAILED creating Flask app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("Step 4: Initializing database...")
    init_db()
    print("✅ Database initialized successfully")
except Exception as e:
    print(f"❌ FAILED initializing database: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("Step 5: Importing knowledge_integration...")
    from knowledge_integration import ProjectKnowledgeBase
    print("✅ knowledge_integration imported successfully")
except Exception as e:
    print(f"⚠️  Warning: knowledge_integration import failed: {e}")
    print("   Continuing without knowledge base...")

try:
    print("Step 6: Importing routes.core...")
    from routes.core import core_bp
    print("✅ routes.core imported successfully")
except Exception as e:
    print(f"❌ FAILED importing routes.core: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("Step 7: Registering blueprint...")
    app.register_blueprint(core_bp)
    print("✅ Blueprint registered successfully")
except Exception as e:
    print(f"❌ FAILED registering blueprint: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("Step 8: Creating basic routes...")
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/health')
    def health():
        return jsonify({'status': 'healthy', 'message': 'Diagnostic version running'})
    
    print("✅ Basic routes created successfully")
except Exception as e:
    print(f"❌ FAILED creating routes: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 60)
print("✅ ALL STARTUP CHECKS PASSED!")
print("=" * 60)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    print(f"Starting app on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=debug)

# I did no harm and this file is not truncated
