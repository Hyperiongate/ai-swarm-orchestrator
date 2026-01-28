"""
ASGI Application Wrapper
Created: January 28, 2026
Last Updated: January 28, 2026

This file provides an ASGI interface for the Flask application,
enabling async WebSocket support through Hypercorn.

CHANGES:
- January 28, 2026: Initial creation for async WebSocket support
  * Wraps Flask app with ASGI adapter
  * Enables async route handlers
  * Required for OpenAI Realtime Voice API

DEPLOYMENT:
This file enables Hypercorn to serve the Flask app with async support.
The Render start command should be:
  hypercorn asgi:app --bind 0.0.0.0:$PORT --workers 2

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from app import app
from asgiref.wsgi import WsgiToAsgi

# Wrap Flask WSGI app with ASGI adapter
asgi_app = WsgiToAsgi(app)

# Export for Hypercorn
app = asgi_app

# I did no harm and this file is not truncated
