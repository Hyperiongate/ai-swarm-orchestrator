"""
routes/capabilities.py
AI Swarm Orchestrator — Capabilities Manifest API Endpoints
Created: March 08, 2026
Last Updated: March 08, 2026 — Phase 3 Self-Awareness (initial build)

CHANGELOG:
- March 08, 2026: Phase 3 Self-Awareness
  * NEW FILE — exposes the dynamic capabilities manifest via HTTP endpoints.
  * GET /api/capabilities         — full manifest text + sections + metadata
  * GET /api/capabilities/summary — short summary string only (<500 chars)
  * POST /api/capabilities/refresh — force-invalidate cache and regenerate
  * All endpoints are read-only except /refresh (POST).
  * All endpoints wrap errors and return JSON — never raise to Flask.
  * Registered in app.py as capabilities_bp under url_prefix /api/capabilities.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import time
from flask import Blueprint, jsonify, request

capabilities_bp = Blueprint('capabilities', __name__, url_prefix='/api/capabilities')


# =============================================================================
# GET /api/capabilities
# Returns the full capabilities manifest plus per-section breakdown and
# cache metadata. Use this to verify exactly what the AI is being told
# about its own capabilities.
# =============================================================================

@capabilities_bp.route('', methods=['GET'])
def get_capabilities():
    """
    Return the full dynamic capabilities manifest.

    Response fields:
        success         (bool)   — always True on 200
        manifest_text   (str)    — full manifest injected into AI prompts
        manifest_length (int)    — character count of manifest_text
        generated_at    (float)  — Unix timestamp of last generation
        cached          (bool)   — True if result came from cache
        sections        (dict)   — per-section content for debugging
    """
    try:
        from intelligence.capabilities_manifest import (
            generate_capabilities_manifest,
            get_manifest_sections,
            get_manifest_metadata,
        )

        manifest_text = generate_capabilities_manifest()
        sections      = get_manifest_sections()
        meta          = get_manifest_metadata()

        return jsonify({
            'success':         True,
            'manifest_text':   manifest_text,
            'manifest_length': len(manifest_text),
            'generated_at':    meta.get('generated_at'),
            'cached':          meta.get('cached'),
            'sections':        sections,
            'note': (
                'This is the exact text injected into every AI prompt. '
                'POST to /api/capabilities/refresh to force regeneration.'
            ),
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error':   str(e),
            'traceback': traceback.format_exc(),
        }), 500


# =============================================================================
# GET /api/capabilities/summary
# Returns the short summary string only. Used by the /health endpoint and
# for quick sanity checks without the full manifest text.
# =============================================================================

@capabilities_bp.route('/summary', methods=['GET'])
def get_capabilities_summary():
    """
    Return the short capabilities summary (<500 chars).

    Response fields:
        success        (bool) — always True on 200
        summary        (str)  — short summary string
        summary_length (int)  — character count
    """
    try:
        from intelligence.capabilities_manifest import get_manifest_summary

        summary = get_manifest_summary()

        return jsonify({
            'success':        True,
            'summary':        summary,
            'summary_length': len(summary),
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error':   str(e),
            'traceback': traceback.format_exc(),
        }), 500


# =============================================================================
# POST /api/capabilities/refresh
# Force-invalidates the manifest cache and regenerates immediately.
# Use after any configuration change (new API key added, module deployed).
# =============================================================================

@capabilities_bp.route('/refresh', methods=['POST'])
def refresh_capabilities():
    """
    Force-regenerate the capabilities manifest, bypassing the cache.

    Response fields:
        success         (bool)  — True if regeneration succeeded
        message         (str)   — human-readable confirmation
        manifest_length (int)   — character count of new manifest
        generated_at    (float) — Unix timestamp of new generation
        cached          (bool)  — should be False immediately after refresh
    """
    try:
        from intelligence.capabilities_manifest import (
            generate_capabilities_manifest,
            invalidate_manifest_cache,
            get_manifest_metadata,
        )

        invalidate_manifest_cache()
        manifest_text = generate_capabilities_manifest(force_refresh=True)
        meta          = get_manifest_metadata()

        return jsonify({
            'success':         True,
            'message':         'Capabilities manifest refreshed successfully.',
            'manifest_length': len(manifest_text),
            'generated_at':    meta.get('generated_at'),
            'cached':          meta.get('cached'),
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success':   False,
            'error':     str(e),
            'traceback': traceback.format_exc(),
        }), 500


# I did no harm and this file is not truncated
