"""
Routes Package - Flask Blueprint Registration
Created: January 18, 2026
Last Updated: February 19, 2026 - RESTORED correct content (was accidentally overwritten
  with routes/utils/__init__.py content during February 18 commit, causing
  ModuleNotFoundError: No module named 'routes.response_utils' on startup)

CHANGELOG:
- February 19, 2026: RESTORED - File was accidentally overwritten with utils exports.
  Routes package __init__.py should be a simple placeholder only. All utility
  function exports belong in routes/utils/__init__.py, not here.
- January 18, 2026: Created as part of initial routes package structure.

PURPOSE:
This file makes the routes/ directory a Python package.
All blueprint registrations happen in app.py, not here.
Utility function exports live in routes/utils/__init__.py.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

# Blueprints are registered in app.py via explicit imports.
# Do not add blueprint imports here.

# I did no harm and this file is not truncated
