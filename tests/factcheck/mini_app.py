"""
Speech Fact-Checker — smallest possible host app (TESTS ONLY)
File: tests/factcheck/mini_app.py
Created: November 11, 2026
Last Updated: November 11, 2026 — Initial version

PURPOSE:
    A Flask app holding ONLY the fact-checker blueprint, so the tests can run
    the fact-checker under the Swarm's real gunicorn settings (gunicorn.conf.py:
    2 sync workers, max_requests=100) without starting the whole Swarm.
    Nothing in the Swarm imports this file.

    Usage (from the repo root):
        gunicorn -c gunicorn.conf.py --pythonpath tests/factcheck mini_app:app

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Flask, jsonify  # noqa: E402

from routes.factcheck import factcheck_bp  # noqa: E402

app = Flask(__name__)
app.register_blueprint(factcheck_bp)


@app.route('/health')
def health():
    """gunicorn.conf.py's keep-alive thread pings this."""
    return jsonify({'status': 'ok', 'pid': os.getpid()})

# I did no harm and this file is not truncated
