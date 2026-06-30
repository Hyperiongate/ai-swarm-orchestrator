"""
Local Gemma Test — Browser Diagnostic Endpoint
Created: June 30, 2026

CHANGELOG:
- June 30, 2026: INITIAL BUILD (Local AI Engine, Phase 5)
  * Purpose: A browser-visitable diagnostic that proves the cloud Swarm can
    reach the locally-hosted Gemma model (running in LM Studio on Jim's laptop,
    exposed via an ngrok tunnel). Visiting the endpoint runs a real call through
    config.py -> orchestration/ai_clients.py -> call_local_gemma() -> ngrok ->
    laptop -> Gemma, and returns the result as clean JSON.
  * Style: Mirrors the existing /api/admin/* diagnostic endpoints already defined
    in app.py (kb-diagnose, list-project-files, diagnose-databases). Read-only.
    Touches nothing, writes nothing — it only reports.
  * Reusable: Refresh the page any time to check "is the laptop reachable right
    now?" The endpoint reports whether LOCAL_GEMMA_BASE_URL is configured, which
    model is targeted, the round-trip time, and Gemma's actual answer (or a clean
    error if the laptop/tunnel is offline).
  * Optional query param: ?q=<your question>  (defaults to a shift-work prompt)
  * SELF-CONTAINED. Registered by a single additive block in app.py. Does no harm
    to any existing functionality. Rule 1 preserved.

DEPLOYMENT:
    Place this file at: routes/local_gemma_test.py
    Then ensure app.py registers it (one additive block — see app.py changelog).
    After deploy, visit:
        https://ai-swarm-orchestrator.onrender.com/api/admin/test-local-gemma

Author: Jim @ Shiftwork Solutions LLC
"""

import time
from flask import Blueprint, request, jsonify

local_gemma_test_bp = Blueprint('local_gemma_test', __name__)


@local_gemma_test_bp.route('/api/admin/test-local-gemma', methods=['GET'])
def test_local_gemma():
    """
    Browser diagnostic: call the local Gemma model and report the result.

    Returns JSON describing:
      - configured:   whether LOCAL_GEMMA_BASE_URL is set (and the client built)
      - base_url:     the ngrok URL the swarm will call (not a secret)
      - model:        the model identifier being targeted
      - timeout:      the configured local-call timeout in seconds
      - prompt:       the test prompt that was sent
      - success:      True if Gemma answered, False on any error
      - response:     Gemma's answer text (on success) or the error text
      - elapsed_seconds: round-trip time, so you can see the latency

    Optional query param:
      ?q=<question>   override the default test prompt
    """
    # Read config defensively so this endpoint never 500s on a config issue.
    try:
        import config
        base_url = getattr(config, 'LOCAL_GEMMA_BASE_URL', None)
        model = getattr(config, 'LOCAL_GEMMA_MODEL', '(not set)')
        timeout = getattr(config, 'LOCAL_GEMMA_TIMEOUT', '(not set)')
    except Exception as cfg_err:
        return jsonify({
            'success': False,
            'configured': False,
            'error': f'Could not read config: {cfg_err}',
        }), 500

    # If the base URL isn't set, report that clearly without attempting a call.
    if not base_url:
        return jsonify({
            'success': False,
            'configured': False,
            'base_url': None,
            'model': model,
            'message': (
                "LOCAL_GEMMA_BASE_URL is not set in the environment. "
                "Add it in Render (Environment tab) as your ngrok URL ending in /v1, "
                "e.g. https://your-domain.ngrok-free.dev/v1, then redeploy."
            ),
        }), 200

    # Determine the test prompt (allow override via ?q= for reuse).
    prompt = request.args.get('q') or "In one sentence, what is shift work scheduling?"

    # Import the client function and make the call, timing the round trip.
    try:
        from orchestration.ai_clients import call_local_gemma
    except Exception as import_err:
        return jsonify({
            'success': False,
            'configured': True,
            'base_url': base_url,
            'model': model,
            'error': f'Could not import call_local_gemma: {import_err}',
        }), 500

    start = time.time()
    try:
        result = call_local_gemma(prompt)
    except Exception as call_err:
        # call_local_gemma already guards itself, but double-protect the endpoint.
        return jsonify({
            'success': False,
            'configured': True,
            'base_url': base_url,
            'model': model,
            'timeout': timeout,
            'prompt': prompt,
            'error': f'Unexpected error calling Gemma: {call_err}',
            'elapsed_seconds': round(time.time() - start, 2),
        }), 200

    elapsed = round(time.time() - start, 2)

    # call_local_gemma returns {'content', 'usage', and 'error' (only on failure)}
    is_error = bool(result.get('error'))
    content = result.get('content', '')

    return jsonify({
        'success': not is_error,
        'configured': True,
        'base_url': base_url,
        'model': model,
        'timeout': timeout,
        'prompt': prompt,
        'response': content,
        'usage': result.get('usage', {}),
        'elapsed_seconds': elapsed,
        'message': (
            'Gemma answered — the cloud Swarm reached your laptop successfully.'
            if not is_error else
            'Call did not succeed. Most likely LM Studio or the ngrok tunnel is not '
            'running, or LOCAL_GEMMA_BASE_URL is wrong. See the response field for details.'
        ),
    }), 200


# I did no harm and this file is not truncated
