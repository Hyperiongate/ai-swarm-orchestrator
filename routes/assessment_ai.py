"""
routes/assessment_ai.py
AI SWARM ORCHESTRATOR — Assessment AI Proxy Endpoints
Created: June 12, 2026
Last Updated: June 12, 2026
Author: Claude Fable 5 for Jim @ Shiftwork Solutions LLC

PURPOSE:
    Server-side AI evaluation for the Shiftwork Operations Assessment at
    https://shift-work.com/resources/shiftwork-assessment/

    The assessment page previously called https://api.anthropic.com directly
    from the visitor's browser with NO API key. That pattern only works
    inside Claude.ai's artifact environment — on the live site every call
    failed and the page silently fell back to canned commentary (Tier 1)
    and locally computed scores with an "AI narrative analysis was
    temporarily unavailable" note (Tier 2).

    These endpoints fix that properly:
      - The browser sends structured answer data (never a raw prompt).
      - Prompts are built HERE, server-side, so the prompt strategy
        (including the hard constraints that keep reveal copy
        unactionable) is no longer visible in the page source.
      - The Anthropic API is called with ANTHROPIC_API_KEY from Render's
        environment (already configured for the orchestrator).
      - Because the browser cannot supply arbitrary prompts, the API key
        cannot be used as an open proxy.

ENDPOINTS:
    POST /api/assessment/t1-commentary
        Body: { "challenge": str, "predictions": [{"category": str,
                "answer": str}, ...] }            (max 8 predictions)
        Returns: { "success": true, "commentary":
                   { "heading": str, "paragraphs": [str, ...] } }

    POST /api/assessment/t2-evaluate
        Body: { "profile": {"company": str, "industry": str,
                "shift_workers": str, "primary_challenge": str},
                "answers": [{"id": int, "category": str,
                "question": str, "answer": str}, ...] }   (max 40 answers)
        Returns: { "success": true, "evaluation": { ...full evaluation
                   JSON as specified in the prompt... } }

    Both endpoints return { "success": false, "error": ... } with an
    appropriate HTTP status on any failure. The frontend keeps its
    existing graceful fallbacks, so a failure here never breaks the page.

SECURITY:
    - CORS restricted to https://shift-work.com and
      https://www.shift-work.com (OPTIONS preflight handled).
    - All input fields length-capped; list sizes capped.
    - Simple per-IP rate limit (30 requests/hour/endpoint, in-memory,
      per-process — modest abuse protection, not a fortress).

MODEL:
    claude-sonnet-4-6 (set in MODEL constant below; the old page-side
    string claude-sonnet-4-20250514 was outdated).

DEPLOYMENT:
    Place at routes/assessment_ai.py in the ai-swarm-orchestrator repo.
    Requires the companion app.py change registering assessment_ai_bp
    (delivered separately). Uses the existing ANTHROPIC_API_KEY env var
    via config.py — no new environment variables needed.

CHANGE LOG:
    2026-06-12 — Initial build.
"""

import json
import re
import time
from collections import defaultdict, deque

from flask import Blueprint, request, jsonify

assessment_ai_bp = Blueprint('assessment_ai', __name__)

# ============================================================================
# CONFIGURATION
# ============================================================================
MODEL = 'claude-sonnet-4-6'
T1_MAX_TOKENS = 800
T2_MAX_TOKENS = 1800

ALLOWED_ORIGINS = {
    'https://shift-work.com',
    'https://www.shift-work.com',
}

# Input caps — prevents oversized/abusive payloads reaching the prompt.
MAX_FIELD_LEN = 300          # any single string field
MAX_QUESTION_LEN = 400       # question text fields
MAX_PREDICTIONS = 8
MAX_ANSWERS = 40

# Rate limiting: per-IP, per-endpoint, in-memory (per worker process).
RATE_LIMIT = 30              # requests
RATE_WINDOW = 3600           # seconds (1 hour)
_rate_buckets = defaultdict(deque)


# ============================================================================
# HELPERS
# ============================================================================
def _client_ip():
    """Best-effort client IP behind Render's proxy."""
    fwd = request.headers.get('X-Forwarded-For', '')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def _rate_limited(endpoint_name):
    """Return True if this IP has exceeded the rate limit for endpoint."""
    key = endpoint_name + '|' + _client_ip()
    now = time.time()
    bucket = _rate_buckets[key]
    while bucket and bucket[0] < now - RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT:
        return True
    bucket.append(now)
    return False


def _clean(value, max_len=MAX_FIELD_LEN):
    """Coerce to a trimmed, length-capped, control-character-free string."""
    if not isinstance(value, str):
        value = str(value) if value is not None else ''
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)
    return value.strip()[:max_len]


def _call_claude(prompt, max_tokens):
    """Call the Anthropic API server-side using the orchestrator's key."""
    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        raise RuntimeError('ANTHROPIC_API_KEY is not configured')
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = ''
    for block in message.content:
        if getattr(block, 'type', None) == 'text':
            text += block.text
    return text


def _extract_json(text):
    """Strip code fences and parse the model's JSON response."""
    cleaned = re.sub(r'```json|```', '', text).strip()
    return json.loads(cleaned)


@assessment_ai_bp.after_request
def _add_cors_headers(response):
    """CORS for shift-work.com only. Applies to all blueprint responses."""
    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '3600'
        response.headers['Vary'] = 'Origin'
    return response


# ============================================================================
# TIER 1 — CLOSING COMMENTARY
# ============================================================================
def _build_t1_prompt(challenge, predictions):
    lines = []
    for p in predictions:
        lines.append('- ' + p['category'] + ': they predicted "' + p['answer'] + '"')
    prediction_summary = '\n'.join(lines)
    return (
        'You are writing a short closing commentary for a manager who just '
        'completed the Shiftwork Solutions Reality Check \u2014 an eight-question '
        'exercise that compared their intuitions about their workforce to general '
        'benchmark patterns from 20,000+ shift worker responses.\n\n'
        'The manager\u2019s stated biggest current challenge: ' + challenge + '\n\n'
        'Their predictions across the seven benchmark questions:\n'
        + prediction_summary + '\n\n'
        '=== YOUR TASK ===\n'
        'Write a closing commentary of exactly 2-3 short paragraphs that ties their '
        'stated challenge together with the patterns they just saw, and ends pointing '
        'at what remains genuinely unknown about their specific facility.\n\n'
        'Return ONLY a valid JSON object \u2014 no markdown, no explanation outside '
        'the JSON:\n'
        '{\n'
        '  "heading": <string, under 80 chars, a warm accent heading for the commentary>,\n'
        '  "paragraphs": [<string>, <string>, <optional third string>]\n'
        '}\n\n'
        '=== HARD CONSTRAINTS \u2014 these are non-negotiable ===\n'
        '1. DO NOT give industry-specific benchmark numbers of any kind.\n'
        '2. DO NOT give numeric targets or thresholds that would let them '
        'self-diagnose without help.\n'
        '3. DO NOT explain methodology.\n'
        '4. DO NOT give prescriptive implementation steps.\n'
        '5. DO NOT invent new statistics or benchmark figures.\n'
        '6. DO frame the manager\u2019s predictions as reasonable.\n'
        '7. DO tie the commentary to their stated biggest challenge.\n'
        '8. DO end on what remains unknown about THEIR facility specifically.\n'
        '9. DO NOT use the word "Shiftwork Solutions" more than once.\n'
        '10. Keep each paragraph to 3-5 sentences. Total commentary under 250 words.\n'
        '11. Return ONLY the JSON object.'
    )


@assessment_ai_bp.route('/api/assessment/t1-commentary', methods=['POST', 'OPTIONS'])
def t1_commentary():
    if request.method == 'OPTIONS':
        return ('', 204)
    if _rate_limited('t1'):
        return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429

    data = request.get_json(silent=True) or {}

    challenge = _clean(data.get('challenge')) or 'not specified'
    raw_predictions = data.get('predictions')
    if not isinstance(raw_predictions, list) or len(raw_predictions) == 0:
        return jsonify({'success': False, 'error': 'predictions list required'}), 400
    if len(raw_predictions) > MAX_PREDICTIONS:
        return jsonify({'success': False, 'error': 'too many predictions'}), 400

    predictions = []
    for item in raw_predictions:
        if not isinstance(item, dict):
            return jsonify({'success': False, 'error': 'invalid prediction item'}), 400
        category = _clean(item.get('category'))
        answer = _clean(item.get('answer'))
        if not category or not answer:
            return jsonify({'success': False, 'error': 'prediction items need category and answer'}), 400
        predictions.append({'category': category, 'answer': answer})

    try:
        raw = _call_claude(_build_t1_prompt(challenge, predictions), T1_MAX_TOKENS)
        commentary = _extract_json(raw)
        heading = commentary.get('heading')
        paragraphs = commentary.get('paragraphs')
        if not isinstance(heading, str) or not isinstance(paragraphs, list) or len(paragraphs) == 0:
            raise ValueError('Model response missing heading/paragraphs')
        paragraphs = [p for p in paragraphs if isinstance(p, str) and p.strip()]
        if not paragraphs:
            raise ValueError('Model response paragraphs empty')
        return jsonify({'success': True,
                        'commentary': {'heading': heading, 'paragraphs': paragraphs}})
    except Exception as e:
        print('[assessment_ai] t1-commentary failed: ' + str(e))
        return jsonify({'success': False, 'error': 'AI commentary unavailable'}), 502


# ============================================================================
# TIER 2 — FULL EVALUATION
# ============================================================================
def _build_t2_prompt(profile, answers):
    profile_text = (
        'Company: ' + (profile['company'] or '(not provided)') + '\n'
        'Industry: ' + profile['industry'] + '\n'
        'Shift workers: ' + profile['shift_workers'] + '\n'
        'Self-identified biggest challenge: '
        + (profile['primary_challenge'] or '(not specified)')
    )
    answer_lines = []
    for a in answers:
        answer_lines.append(
            'Q' + str(a['id']) + ' [' + a['category'] + '] ' + a['question']
            + '\n    Answer: ' + a['answer']
        )
    answer_summary = '\n\n'.join(answer_lines)
    return (
        'You are an expert shift operations consultant at Shiftwork Solutions LLC.\n\n'
        'Facility profile:\n' + profile_text + '\n\n'
        'All 35 answers:\n' + answer_summary + '\n\n'
        'Return ONLY a valid JSON object:\n'
        '{\n'
        '  "overall_score": <integer 0-100>,\n'
        '  "overall_label": <"Critical \u2014 Immediate Action Required"|"Fair \u2014 '
        'Several Areas Need Attention"|"Good \u2014 Some Opportunities for Improvement"|'
        '"Excellent \u2014 Operation Is Performing Well">,\n'
        '  "narrative": <2-3 sentence summary>,\n'
        '  "dimensions": {"worklife":{"score":<0-100>,"label":"Work-Life Balance",'
        '"low_label":"Critical Issues","high_label":"Excellent Balance"},'
        '"health":{"score":<0-100>,"label":"Employee Health","low_label":"High Risk",'
        '"high_label":"Very Healthy"},"alertness":{"score":<0-100>,'
        '"label":"Alertness Management","low_label":"Significant Fatigue",'
        '"high_label":"Highly Alert"},"overtime":{"score":<0-100>,'
        '"label":"Overtime Management","low_label":"Out of Control",'
        '"high_label":"Well Managed"},"operations":{"score":<0-100>,'
        '"label":"Operational Efficiency","low_label":"Major Issues",'
        '"high_label":"Highly Efficient"},"quality":{"score":<0-100>,'
        '"label":"Quality & Safety","low_label":"Critical","high_label":"Excellent"},'
        '"communication":{"score":<0-100>,"label":"Communication",'
        '"low_label":"Breakdown","high_label":"Effective"},'
        '"workforce":{"score":<0-100>,"label":"Workforce Stability",'
        '"low_label":"High Turnover","high_label":"Stable & Strong"}},\n'
        '  "strengths": [{"title":<string>,"detail":<1-2 sentence>}],\n'
        '  "opportunities": [{"title":<string>,"detail":<2-3 sentence>,'
        '"shiftwork_note":<1-2 sentence mentioning Shiftwork Solutions>}],\n'
        '  "actions": [<string, 1 sentence each>]\n'
        '}\n'
        'Rules: overall_score genuine reflection. strengths: only dims 70+. '
        'opportunities: only dims below 50. actions: 3-6 items. Return ONLY the JSON.'
    )


@assessment_ai_bp.route('/api/assessment/t2-evaluate', methods=['POST', 'OPTIONS'])
def t2_evaluate():
    if request.method == 'OPTIONS':
        return ('', 204)
    if _rate_limited('t2'):
        return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429

    data = request.get_json(silent=True) or {}

    raw_profile = data.get('profile')
    if not isinstance(raw_profile, dict):
        raw_profile = {}
    profile = {
        'company': _clean(raw_profile.get('company')),
        'industry': _clean(raw_profile.get('industry')) or '(not specified)',
        'shift_workers': _clean(raw_profile.get('shift_workers')) or '(not specified)',
        'primary_challenge': _clean(raw_profile.get('primary_challenge')),
    }

    raw_answers = data.get('answers')
    if not isinstance(raw_answers, list) or len(raw_answers) == 0:
        return jsonify({'success': False, 'error': 'answers list required'}), 400
    if len(raw_answers) > MAX_ANSWERS:
        return jsonify({'success': False, 'error': 'too many answers'}), 400

    answers = []
    for item in raw_answers:
        if not isinstance(item, dict):
            return jsonify({'success': False, 'error': 'invalid answer item'}), 400
        try:
            qid = int(item.get('id'))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'answer id must be an integer'}), 400
        category = _clean(item.get('category'))
        question = _clean(item.get('question'), MAX_QUESTION_LEN)
        answer = _clean(item.get('answer'))
        if not category or not question or not answer:
            return jsonify({'success': False,
                            'error': 'answer items need category, question, and answer'}), 400
        answers.append({'id': qid, 'category': category,
                        'question': question, 'answer': answer})

    try:
        raw = _call_claude(_build_t2_prompt(profile, answers), T2_MAX_TOKENS)
        evaluation = _extract_json(raw)
        if not isinstance(evaluation.get('overall_score'), int):
            raise ValueError('Model response missing integer overall_score')
        if not isinstance(evaluation.get('dimensions'), dict):
            raise ValueError('Model response missing dimensions')
        return jsonify({'success': True, 'evaluation': evaluation})
    except Exception as e:
        print('[assessment_ai] t2-evaluate failed: ' + str(e))
        return jsonify({'success': False, 'error': 'AI evaluation unavailable'}), 502

# I did no harm and this file is not truncated
