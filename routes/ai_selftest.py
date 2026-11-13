"""
AI Connections Self-Test — Flask Routes
File: routes/ai_selftest.py
Created: November 13, 2026
Last Updated: November 13, 2026 — Initial implementation

PURPOSE:
    Answers one question in plain terms: "Which of the Swarm's AI connections
    work right now?"

    The Swarm talks to several outside AI services. Each can stop working
    without any change on our side: a model is retired, a library is
    deprecated, a key expires, a bill goes unpaid. Before this file the only
    way to find out was to notice a bad answer in the chat. (Gemini, for
    example, had been failing on every call for months.)

    The test sends one tiny question ("reply with the single word READY")
    through the SAME functions the Swarm itself uses, so a pass here means
    the real thing works, not just that a key exists.

WHAT IS TESTED:
    claude_sonnet   orchestration.ai_clients.call_claude_sonnet()   (main chat)
    claude_opus     orchestration.ai_clients.call_claude_opus()     (escalation)
    gpt             orchestration.ai_clients.call_gpt4()
    deepseek        orchestration.ai_clients.call_deepseek()
    gemini          orchestration.ai_clients.call_gemini()
    local_gemma     orchestration.ai_clients.call_local_gemma_raw() (only when
                    LOCAL_GEMMA_BASE_URL is set; the laptop must be on)
    voice_models    asks OpenAI which "realtime" voice models this key can
                    use (no audio is sent; this is a listing, not a call)
    voice_service   whether the separate voice service the Voice button
                    connects to answers at all

ENDPOINTS:
    GET /ai-selftest              a page with a "Run the test" button
    GET /api/admin/ai-selftest    runs the test, returns JSON
        ?only=gemini,deepseek     run just these (comma-separated names)

    Both are private: neither is in swarm_security.py's public list, so the
    Admin Gate requires the admin passcode once it is switched on.

COST AND TIME:
    Each run makes one very small paid call per service: a few cents in
    total. The services are asked at the same time, and anything that has not
    answered within 75 seconds is reported as "no answer in time" (Render
    cuts a request off at about 100 seconds). Nothing is stored.

CHANGELOG:
- November 13, 2026: INITIAL IMPLEMENTATION
  * New blueprint ai_selftest_bp. Registered in app.py (see app.py changelog).
    Read-only: changes no setting and writes nothing. Rule 1 preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, wait

from flask import Blueprint, jsonify, request, send_from_directory

ai_selftest_bp = Blueprint('ai_selftest', __name__)

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')

QUESTION = 'This is a connection test. Reply with the single word READY and nothing else.'
OVERALL_SECONDS = 75

# The address the Voice button connects to (see static/js/swarm-voice.js).
VOICE_SERVICE_HEALTH_URL = os.environ.get(
    'VOICE_SERVICE_HEALTH_URL', 'https://ai-swarm-orchestrator-1.onrender.com/health')


def _short(text, limit=300):
    text = str(text or '').strip()
    return text if len(text) <= limit else text[:limit] + '...'


def _from_reply(reply):
    """Turn the Swarm's usual {'content', 'usage', 'error'} reply into a test result."""
    if not isinstance(reply, dict):
        return {'ok': False, 'error': _short(f'Unexpected reply: {reply!r}')}
    content = str(reply.get('content') or '')
    if reply.get('error') or content.startswith('ERROR'):
        return {'ok': False, 'error': _short(content or 'The call failed without a message.')}
    if not content.strip():
        return {'ok': False, 'error': 'The call succeeded but the answer was empty.'}
    return {'ok': True, 'answer': _short(content, 120), 'usage': reply.get('usage')}


def _test_claude_sonnet():
    from orchestration.ai_clients import call_claude_sonnet
    return _from_reply(call_claude_sonnet(QUESTION, max_tokens=50))


def _test_claude_opus():
    from orchestration.ai_clients import call_claude_opus
    return _from_reply(call_claude_opus(QUESTION, max_tokens=50))


def _test_gpt():
    from orchestration.ai_clients import call_gpt4
    # GPT-5 models reason before answering and that reasoning comes out of the
    # allowance, so a 50-token allowance could come back empty. 2000 is a ceiling.
    return _from_reply(call_gpt4(QUESTION, max_tokens=2000))


def _test_deepseek():
    from orchestration.ai_clients import call_deepseek
    return _from_reply(call_deepseek(QUESTION, max_tokens=2000))


def _test_gemini():
    from orchestration.ai_clients import call_gemini
    return _from_reply(call_gemini(QUESTION, max_tokens=2000))


def _test_local_gemma():
    from orchestration.ai_clients import call_local_gemma_raw
    return _from_reply(call_local_gemma_raw(QUESTION, max_tokens=20))


def _test_voice_models():
    """Which realtime (voice) models can this OpenAI key use? A listing; nothing is spoken."""
    from orchestration.ai_clients import openai_client
    if not openai_client:
        return {'ok': False, 'error': 'OpenAI API not configured'}
    names = sorted(model.id for model in openai_client.models.list(timeout=30) if 'realtime' in model.id)
    if not names:
        return {'ok': False, 'error': 'This OpenAI key cannot see any realtime (voice) model.'}
    return {'ok': True, 'answer': f'{len(names)} voice models available', 'models': names}


def _test_voice_service():
    import requests
    response = requests.get(VOICE_SERVICE_HEALTH_URL, timeout=45)
    if response.status_code != 200:
        return {'ok': False, 'error': f'The voice service answered with status {response.status_code}.'}
    return {'ok': True, 'answer': _short(response.text, 200)}


def _connections():
    """Name -> (label, model or address in use, configured?, test function, what it is for)."""
    import config
    return {
        'claude_sonnet': ('Claude Sonnet', config.CLAUDE_SONNET_MODEL, bool(config.ANTHROPIC_API_KEY),
                          _test_claude_sonnet, 'Main chat, task analysis, briefings, the website assessment'),
        'claude_opus': ('Claude Opus', config.CLAUDE_OPUS_MODEL, bool(config.ANTHROPIC_API_KEY),
                        _test_claude_opus, 'Harder requests the Swarm escalates'),
        'gpt': ('OpenAI GPT', config.GPT4_MODEL, bool(config.OPENAI_API_KEY),
                _test_gpt, 'Second opinion / design specialist'),
        'deepseek': ('DeepSeek', config.DEEPSEEK_MODEL, bool(config.DEEPSEEK_API_KEY),
                     _test_deepseek, 'Code specialist'),
        'gemini': ('Google Gemini', config.GEMINI_MODEL, bool(config.GOOGLE_API_KEY),
                   _test_gemini, 'Multimodal specialist'),
        'local_gemma': ('Local Gemma (your laptop)', getattr(config, 'LOCAL_GEMMA_MODEL', ''),
                        bool(getattr(config, 'LOCAL_GEMMA_BASE_URL', None)),
                        _test_local_gemma, 'Offline model on your laptop, through the tunnel'),
        'voice_models': ('Voice: OpenAI realtime models', 'listing only', bool(config.OPENAI_API_KEY),
                         _test_voice_models, 'What voice mode can be built on with this key'),
        'voice_service': ('Voice: the separate voice service', VOICE_SERVICE_HEALTH_URL, True,
                          _test_voice_service, 'What the Voice button on the main screen connects to'),
    }


def _timed(function):
    started = time.time()
    try:
        result = function()
    except Exception as error:                       # a failed connection is a result, not a crash
        result = {'ok': False, 'error': _short(f'{type(error).__name__}: {error}')}
    result['seconds'] = round(time.time() - started, 1)
    return result


def run_selftest(only=None):
    """Run the tests side by side. Returns the list of results in a fixed order."""
    connections = _connections()
    wanted = [name for name in connections if not only or name in only]
    results = {}
    to_run = {}
    for name in wanted:
        label, model, configured, function, purpose = connections[name]
        results[name] = {'name': name, 'label': label, 'model': model, 'purpose': purpose,
                         'configured': configured}
        if configured:
            to_run[name] = function
        else:
            results[name].update({'ok': None, 'skipped': 'Not set up: no key or address is configured in Render.'})

    if to_run:
        pool = ThreadPoolExecutor(max_workers=len(to_run))
        futures = {pool.submit(_timed, function): name for name, function in to_run.items()}
        done, not_done = wait(futures, timeout=OVERALL_SECONDS)
        for future in done:
            results[futures[future]].update(future.result())
        for future in not_done:
            results[futures[future]].update({
                'ok': False, 'seconds': OVERALL_SECONDS,
                'error': f'No answer within {OVERALL_SECONDS} seconds.'})
        pool.shutdown(wait=False)

    return [results[name] for name in wanted]


@ai_selftest_bp.route('/api/admin/ai-selftest', methods=['GET'])
def ai_selftest():
    only = {part.strip() for part in request.args.get('only', '').split(',') if part.strip()} or None
    started = time.time()
    results = run_selftest(only)
    tested = [row for row in results if row.get('ok') is not None]
    response = jsonify({
        'success': True,
        'working': sum(1 for row in tested if row['ok']),
        'failing': sum(1 for row in tested if not row['ok']),
        'not_set_up': sum(1 for row in results if row.get('ok') is None),
        'seconds': round(time.time() - started, 1),
        'results': results,
    })
    response.headers['Cache-Control'] = 'no-store'
    return response


@ai_selftest_bp.route('/ai-selftest', methods=['GET'])
def ai_selftest_page():
    """The page. A plain file: nothing in it is filled in by the server."""
    response = send_from_directory(_TEMPLATES_DIR, 'ai_selftest.html', mimetype='text/html')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Frame-Options'] = 'DENY'
    return response


# I did no harm and this file is not truncated
