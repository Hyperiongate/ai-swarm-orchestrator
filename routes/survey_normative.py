"""
SURVEY IN A BOX — NORMATIVE API
File: routes/survey_normative.py
Repo: ai-swarm-orchestrator

CHANGELOG:
- 2026-03-13: Initial creation (Phase 5, Step 5.1)
  * GET  /api/survey/norm/status  — verify database loaded, question count,
                                    facility count, sample comparisons
  * POST /api/survey/norm/compare — compare a single numeric question
  * POST /api/survey/norm/compare-categorical — compare a categorical question
  * POST /api/survey/norm/batch   — compare multiple numeric questions at once
  * POST /api/survey/norm/significant — return only significant deviations
  * GET  /api/survey/norm/search  — search questions by keyword
  All endpoints load the normative database via the singleton
  get_normative_database(). Database is loaded once on first request
  and cached for all subsequent requests.

PURPOSE:
Exposes the normative benchmarking capabilities of normative_database.py
as REST endpoints for the Survey in a Box admin dashboard and future
report generation pipeline.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, jsonify, request

survey_normative_bp = Blueprint('survey_normative', __name__)


def _get_db():
    """
    Return the loaded normative database singleton.
    Returns (db, error_response) tuple.
    If db is None, error_response is a ready-to-return jsonify tuple.
    """
    try:
        from normative_database import get_normative_database
        db = get_normative_database()
    except Exception as e:
        return None, (jsonify({
            'success': False,
            'error': f'Failed to import normative_database module: {e}'
        }), 500)

    if db is None:
        return None, (jsonify({
            'success': False,
            'error': 'Normative database module returned None — check startup logs'
        }), 503)

    if not db.loaded:
        return None, (jsonify({
            'success': False,
            'error': db.load_error or 'Normative database failed to load',
            'hint': 'Ensure data/norms_overall.xlsx is committed to the repo root'
        }), 503)

    return db, None


# ---------------------------------------------------------------------------
# GET /api/survey/norm/status
# ---------------------------------------------------------------------------

@survey_normative_bp.route('/api/survey/norm/status', methods=['GET'])
def norm_status():
    """
    Verify that the normative database loaded correctly on Render.
    Returns question count, facility count, sections, and 3 sample
    comparisons to confirm the math is working.

    This is the Step 5.1 acceptance test endpoint.
    """
    try:
        from normative_database import get_normative_database
        db = get_normative_database()
    except Exception as e:
        return jsonify({
            'success': False,
            'loaded': False,
            'error': f'Cannot import normative_database: {e}'
        }), 500

    if db is None:
        return jsonify({
            'success': False,
            'loaded': False,
            'error': 'Normative database module returned None — check Render logs'
        }), 503

    status = db.get_status()

    return jsonify({
        'success': status['loaded'],
        **status
    }), 200 if status['loaded'] else 503


# ---------------------------------------------------------------------------
# POST /api/survey/norm/compare
# ---------------------------------------------------------------------------

@survey_normative_bp.route('/api/survey/norm/compare', methods=['POST'])
def norm_compare():
    """
    Compare a single numeric/Likert client value to the industry norm.

    Request JSON:
        {
            "question": "I like my current schedule",   // partial match OK
            "client_value": 3.2                         // client mean score
        }

    Response:
        {
            "success": true,
            "question": "...",
            "section": "Shift Schedule Features",
            "client_value": 3.2,
            "norm_mean": 3.6627,
            "norm_std_dev": 0.4821,
            "deviation": -0.4627,
            "deviation_pct": -12.63,
            "z_score": -0.96,
            "percentile": 18.4,
            "interpretation": "Significant — 12.6% below industry norm",
            "company_data_count": 148
        }
    """
    db, err = _get_db()
    if err:
        return err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body must be JSON'}), 400

    question = data.get('question', '').strip()
    client_value = data.get('client_value')

    if not question:
        return jsonify({'success': False, 'error': 'question is required'}), 400
    if client_value is None:
        return jsonify({'success': False, 'error': 'client_value is required'}), 400

    try:
        client_value = float(client_value)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'client_value must be numeric'}), 400

    result = db.compare_numeric(question, client_value)
    status_code = 200 if result['success'] else 404
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# POST /api/survey/norm/compare-categorical
# ---------------------------------------------------------------------------

@survey_normative_bp.route('/api/survey/norm/compare-categorical', methods=['POST'])
def norm_compare_categorical():
    """
    Compare a client's option distribution to normative distribution
    for a Yes/No or multiple-choice question.

    Request JSON:
        {
            "question": "Which would you prefer",
            "client_options": {
                "Fixed or \"steady\" shifts": 84.5,
                "Rotating shifts": 15.5
            }
        }

    Response:
        {
            "success": true,
            "question": "...",
            "section": "Shift Schedule Features",
            "type": "categorical",
            "comparisons": [
                {
                    "option": "Fixed or \"steady\" shifts",
                    "client_pct": 84.5,
                    "norm_pct": 84.45,
                    "difference": 0.05,
                    "direction": "above norm"
                },
                ...
            ],
            "norm_options": [...]
        }
    """
    db, err = _get_db()
    if err:
        return err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body must be JSON'}), 400

    question = data.get('question', '').strip()
    client_options = data.get('client_options')

    if not question:
        return jsonify({'success': False, 'error': 'question is required'}), 400
    if not client_options or not isinstance(client_options, dict):
        return jsonify({'success': False, 'error': 'client_options must be a dict of {option: pct}'}), 400

    result = db.compare_categorical(question, client_options)
    status_code = 200 if result['success'] else 404
    return jsonify(result), status_code


# ---------------------------------------------------------------------------
# POST /api/survey/norm/batch
# ---------------------------------------------------------------------------

@survey_normative_bp.route('/api/survey/norm/batch', methods=['POST'])
def norm_batch():
    """
    Compare multiple numeric client responses to norms in one call.
    Only returns successful matches — unmatched questions are silently skipped.

    Request JSON:
        {
            "responses": {
                "Overall, this is a safe place to work": 4.1,
                "I like my current schedule": 3.2,
                "The pay here is good": 2.8
            }
        }

    Response:
        {
            "success": true,
            "compared": 3,
            "results": [ ...compare_numeric() results... ]
        }
    """
    db, err = _get_db()
    if err:
        return err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body must be JSON'}), 400

    responses = data.get('responses')
    if not responses or not isinstance(responses, dict):
        return jsonify({'success': False, 'error': 'responses must be a dict of {question: value}'}), 400

    # Validate all values are numeric
    clean = {}
    errors = []
    for q, v in responses.items():
        try:
            clean[q] = float(v)
        except (TypeError, ValueError):
            errors.append(f'Non-numeric value for question: {q[:60]}')

    if errors:
        return jsonify({'success': False, 'error': '; '.join(errors)}), 400

    results = db.batch_compare_numeric(clean)

    return jsonify({
        'success': True,
        'compared': len(results),
        'submitted': len(clean),
        'results': results
    }), 200


# ---------------------------------------------------------------------------
# POST /api/survey/norm/significant
# ---------------------------------------------------------------------------

@survey_normative_bp.route('/api/survey/norm/significant', methods=['POST'])
def norm_significant():
    """
    From a dict of client responses, return only the questions where
    |z_score| >= threshold, sorted by magnitude (largest first).

    Request JSON:
        {
            "responses": {
                "I like my current schedule": 2.1,
                "Overall, this is a safe place to work": 4.5,
                "The pay here is good": 2.2
            },
            "threshold_z": 1.0   // optional, default 1.0
        }

    Response:
        {
            "success": true,
            "threshold_z": 1.0,
            "significant_count": 2,
            "results": [ ...sorted by |z_score| descending... ]
        }
    """
    db, err = _get_db()
    if err:
        return err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body must be JSON'}), 400

    responses = data.get('responses')
    threshold_z = data.get('threshold_z', 1.0)

    if not responses or not isinstance(responses, dict):
        return jsonify({'success': False, 'error': 'responses must be a dict of {question: value}'}), 400

    try:
        threshold_z = float(threshold_z)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'threshold_z must be numeric'}), 400

    clean = {}
    for q, v in responses.items():
        try:
            clean[q] = float(v)
        except (TypeError, ValueError):
            pass  # skip non-numeric silently

    results = db.get_significant_deviations(clean, threshold_z=threshold_z)

    return jsonify({
        'success': True,
        'threshold_z': threshold_z,
        'submitted': len(clean),
        'significant_count': len(results),
        'results': results
    }), 200


# ---------------------------------------------------------------------------
# GET /api/survey/norm/search?q=<term>&limit=<n>
# ---------------------------------------------------------------------------

@survey_normative_bp.route('/api/survey/norm/search', methods=['GET'])
def norm_search():
    """
    Search the normative database for questions matching a keyword.

    Query params:
        q     (str):  Search term (required)
        limit (int):  Max results to return (default 10, max 50)

    Response:
        {
            "success": true,
            "query": "schedule",
            "count": 8,
            "results": [
                {
                    "question": "...",
                    "section": "Shift Schedule Features",
                    "type": "numeric",
                    "norm_mean": 3.66,
                    "norm_std_dev": 0.48,
                    "company_data_count": 148,
                    "options_count": 5
                },
                ...
            ]
        }
    """
    db, err = _get_db()
    if err:
        return err

    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'success': False, 'error': 'q parameter is required'}), 400

    try:
        limit = min(int(request.args.get('limit', 10)), 50)
    except (TypeError, ValueError):
        limit = 10

    results = db.search_questions(query, limit=limit)

    return jsonify({
        'success': True,
        'query': query,
        'count': len(results),
        'results': results
    }), 200


# I did no harm and this file is not truncated
