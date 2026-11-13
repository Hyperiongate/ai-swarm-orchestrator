"""
Performance Dashboard — Flask Route
File: routes/performance.py
Created: November 13, 2026
Last Updated: November 13, 2026 — Initial implementation

PURPOSE:
    Serves the Performance Dashboard (newsletter subscribers, contact
    submissions, visitor events, blocked addresses) at /performance.

    The page used to live on the public website at shift-work.com/performance/,
    protected only by a 4-digit PIN written in its own source, and it read its
    data from the Swarm across sites. It now lives here, so the Admin Gate
    (swarm_security.py) is its lock: /performance is NOT in the gate's public
    list, which makes it private by default. No passcode is handled by the
    page itself.

    The data routes it calls are unchanged and already exist:
    /api/newsletter/*, /api/contact/submissions, /api/events/*.

ENDPOINTS:
    GET /performance    — the dashboard page

CHANGELOG:
- November 13, 2026: INITIAL IMPLEMENTATION
  * New blueprint performance_bp. Registered in app.py (see app.py changelog).
    No existing route touched. Rule 1 (do no harm) preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os

from flask import Blueprint, send_from_directory

performance_bp = Blueprint('performance', __name__)

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')


@performance_bp.route('/performance', methods=['GET'])
@performance_bp.route('/performance/', methods=['GET'])
def performance_page():
    """The dashboard. A plain file: nothing in it is filled in by the server."""
    response = send_from_directory(_TEMPLATES_DIR, 'performance.html', mimetype='text/html')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


# I did no harm and this file is not truncated
