"""
routes/learning.py
Learning API Routes — Phase 1 (original) + Phase 5 (new endpoints)
Created: February 2, 2026
Last Updated: March 09, 2026

CHANGELOG:
- March 09, 2026: Phase 5 — Added 5 new endpoints for the adaptive learning
  system (routing preferences, prompt enhancements, weekly review).
  All original Phase 1 endpoints are completely unchanged.
  New endpoints use safe in-function imports so a missing Phase 5 module
  returns a clear error instead of crashing the blueprint at startup.

  NEW ENDPOINTS ADDED:
    GET  /api/learning/routing-preferences  — routing_optimizer data
    GET  /api/learning/enhancements         — prompt_optimizer data
    GET  /api/learning/review/latest        — most recent weekly_review row
    POST /api/learning/review/run           — trigger run_weekly_review()
    GET  /api/learning/dashboard            — combined Phase 5 overview

ORIGINAL PHASE 1 ENDPOINTS (unchanged):
    GET  /api/learning/status
    POST /api/learning/run-cycle
    GET  /api/learning/patterns
    GET  /api/learning/adjustments
    POST /api/learning/adjustments/<id>/approve
    POST /api/learning/adjustments/<id>/reject
    GET  /api/learning/report
    POST /api/learning/enable
    POST /api/learning/disable

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, jsonify, request
from learning_integration import learning_integration
import sqlite3
from datetime import datetime


# Create blueprint
learning_bp = Blueprint('learning', __name__)


# ============================================================================
# PHASE 1 ENDPOINTS — COMPLETELY UNCHANGED
# ============================================================================

@learning_bp.route('/api/learning/status', methods=['GET'])
def get_learning_status():
    """
    Get current learning system status.
    Returns basic metrics about learning activity.
    """
    try:
        report = learning_integration.get_learning_report()
        return jsonify({
            'success': True,
            'enabled': learning_integration.enabled,
            'status': report.get('learning_status', 'unknown'),
            'metrics': {
                'total_outcomes': report.get('total_outcomes', 0),
                'outcomes_analyzed': report.get('learned_outcomes', 0),
                'outcomes_pending': report.get('pending_outcomes', 0),
                'active_patterns': report.get('active_patterns', 0),
                'pending_adjustments': report.get('pending_adjustments', 0),
                'applied_adjustments': report.get('applied_adjustments', 0)
            },
            'needs_action': report.get('pending_adjustments', 0) > 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_bp.route('/api/learning/run-cycle', methods=['POST'])
def run_learning_cycle():
    """
    Manually trigger a learning cycle.
    Query params:
    - min_observations: Minimum outcomes needed (default 10)
    """
    try:
        min_obs = request.args.get('min_observations', 10, type=int)
        results = learning_integration.run_learning_cycle(min_observations=min_obs)
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_bp.route('/api/learning/patterns', methods=['GET'])
def get_patterns():
    """
    Get discovered patterns.
    Query params:
    - min_confidence: Filter by minimum confidence (default 0.75)
    - pattern_type: Filter by type (optional)
    - limit: Max results (default 50)
    """
    try:
        min_confidence = request.args.get('min_confidence', 0.75, type=float)
        pattern_type = request.args.get('pattern_type', None)
        limit = request.args.get('limit', 50, type=int)

        db = sqlite3.connect(learning_integration.engine.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        query = 'SELECT * FROM learned_patterns WHERE active = 1 AND confidence >= ?'
        params = [min_confidence]

        if pattern_type:
            query += ' AND pattern_type = ?'
            params.append(pattern_type)

        query += ' ORDER BY confidence DESC, supporting_evidence DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        patterns = [dict(row) for row in cursor.fetchall()]
        db.close()

        return jsonify({'success': True, 'count': len(patterns), 'patterns': patterns})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_bp.route('/api/learning/adjustments', methods=['GET'])
def get_adjustments():
    """
    Get pending behavior adjustments.
    Query params:
    - include_approved: Include already-approved adjustments (default false)
    """
    try:
        include_approved = request.args.get('include_approved', 'false').lower() == 'true'

        db = sqlite3.connect(learning_integration.engine.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        if include_approved:
            cursor.execute(
                'SELECT * FROM behavior_adjustments WHERE reverted = 0 ORDER BY created_at DESC'
            )
        else:
            cursor.execute(
                'SELECT * FROM behavior_adjustments WHERE approved = 0 AND reverted = 0 ORDER BY created_at DESC'
            )

        adjustments = [dict(row) for row in cursor.fetchall()]
        db.close()

        return jsonify({'success': True, 'count': len(adjustments), 'adjustments': adjustments})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_bp.route('/api/learning/adjustments/<int:adjustment_id>/approve', methods=['POST'])
def approve_adjustment(adjustment_id):
    """
    Approve a suggested behavior adjustment.
    Body (optional):
    - approved_by: Name/ID of person approving (default "system")
    - apply_immediately: Whether to apply now (default true)
    """
    try:
        data = request.get_json() or {}
        approved_by = data.get('approved_by', 'jim')
        apply_immediately = data.get('apply_immediately', True)

        db = sqlite3.connect(learning_integration.engine.db_path)
        cursor = db.cursor()

        cursor.execute(
            'SELECT * FROM behavior_adjustments WHERE id = ? AND approved = 0',
            (adjustment_id,)
        )
        adjustment = cursor.fetchone()
        if not adjustment:
            db.close()
            return jsonify({'success': False, 'error': 'Adjustment not found or already approved'}), 404

        cursor.execute('''
            UPDATE behavior_adjustments
            SET approved = 1,
                approved_by = ?,
                approved_at = ?,
                applied = ?,
                applied_at = ?
            WHERE id = ?
        ''', (
            approved_by,
            datetime.now(),
            1 if apply_immediately else 0,
            datetime.now() if apply_immediately else None,
            adjustment_id
        ))
        db.commit()
        db.close()

        return jsonify({
            'success': True,
            'message': 'Adjustment approved' + (' and applied' if apply_immediately else ''),
            'adjustment_id': adjustment_id,
            'applied': apply_immediately
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_bp.route('/api/learning/adjustments/<int:adjustment_id>/reject', methods=['POST'])
def reject_adjustment(adjustment_id):
    """
    Reject a suggested behavior adjustment.
    Body (optional):
    - reason: Why rejected (for learning)
    """
    try:
        data = request.get_json() or {}

        db = sqlite3.connect(learning_integration.engine.db_path)
        cursor = db.cursor()

        cursor.execute('''
            UPDATE behavior_adjustments
            SET reverted = 1, reverted_at = ?
            WHERE id = ? AND approved = 0
        ''', (datetime.now(), adjustment_id))

        if cursor.rowcount == 0:
            db.close()
            return jsonify({'success': False, 'error': 'Adjustment not found or already processed'}), 404

        db.commit()
        db.close()

        return jsonify({'success': True, 'message': 'Adjustment rejected', 'adjustment_id': adjustment_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_bp.route('/api/learning/report', methods=['GET'])
def get_comprehensive_report():
    """Get comprehensive learning report with all metrics and insights."""
    try:
        report = learning_integration.get_learning_report()
        adjustments = learning_integration.get_pending_adjustments()

        insights = []

        if report.get('pending_outcomes', 0) >= 10:
            insights.append({
                'type': 'ready_for_learning',
                'message': f"Ready to run learning cycle ({report['pending_outcomes']} outcomes available)",
                'action': 'POST /api/learning/run-cycle'
            })

        if report.get('pending_adjustments', 0) > 0:
            insights.append({
                'type': 'pending_adjustments',
                'message': f"{report['pending_adjustments']} behavior adjustments awaiting approval",
                'action': 'GET /api/learning/adjustments'
            })

        if report.get('active_patterns', 0) > 0:
            insights.append({
                'type': 'patterns_active',
                'message': f"{report['active_patterns']} learned patterns active and improving routing",
                'action': 'GET /api/learning/patterns'
            })

        return jsonify({
            'success': True,
            'report': report,
            'pending_adjustments': adjustments,
            'insights': insights,
            'recommendations': _generate_recommendations(report)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_bp.route('/api/learning/enable', methods=['POST'])
def enable_learning():
    """Enable the learning system"""
    try:
        learning_integration.enable()
        return jsonify({'success': True, 'message': 'Learning system enabled'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@learning_bp.route('/api/learning/disable', methods=['POST'])
def disable_learning():
    """Disable the learning system"""
    try:
        learning_integration.disable()
        return jsonify({'success': True, 'message': 'Learning system disabled'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _generate_recommendations(report: dict) -> list:
    """Generate actionable recommendations based on report"""
    recommendations = []

    if report.get('pending_outcomes', 0) >= 10:
        recommendations.append({
            'priority': 'high',
            'category': 'action_needed',
            'title': 'Run Learning Cycle',
            'description': f"You have {report['pending_outcomes']} unanalyzed outcomes. Running a learning cycle could discover new optimization opportunities.",
            'action': 'Run learning cycle',
            'endpoint': 'POST /api/learning/run-cycle'
        })

    if report.get('pending_adjustments', 0) > 0:
        recommendations.append({
            'priority': 'medium',
            'category': 'review_needed',
            'title': 'Review Suggested Optimizations',
            'description': f"The system has identified {report['pending_adjustments']} potential optimizations based on learned patterns. Review and approve to improve performance.",
            'action': 'Review adjustments',
            'endpoint': 'GET /api/learning/adjustments'
        })

    if report.get('total_outcomes', 0) < 50:
        recommendations.append({
            'priority': 'low',
            'category': 'info',
            'title': 'Building Learning Foundation',
            'description': f"Learning system has analyzed {report['total_outcomes']} outcomes. The more data collected, the better the insights. Keep using the system!",
            'action': None,
            'endpoint': None
        })

    if report.get('active_patterns', 0) > 5:
        recommendations.append({
            'priority': 'low',
            'category': 'success',
            'title': 'Learning System Active',
            'description': f"Great! {report['active_patterns']} learned patterns are actively improving routing decisions. The system is learning effectively.",
            'action': None,
            'endpoint': None
        })

    return recommendations


# ============================================================================
# PHASE 5 ENDPOINTS — NEW (March 09, 2026)
# All use safe in-function imports so a missing module returns a clear
# error rather than crashing the blueprint on startup.
# ============================================================================

@learning_bp.route('/api/learning/routing-preferences', methods=['GET'])
def get_routing_preferences():
    """
    GET /api/learning/routing-preferences

    Returns all routing preference data accumulated by routing_optimizer.
    Shows which AI model performs best for each task category based on
    real outcome data recorded per request.

    Response:
    {
      "success": true,
      "count": 6,
      "by_category": {
        "scheduling": [
          {"model": "sonnet", "avg_score": 7.2, "success_count": 4, "total_count": 5}
        ]
      },
      "all_data": [...]
    }
    """
    try:
        from intelligence.routing_optimizer import get_all_routing_data
        rows = get_all_routing_data()

        # Group by category for easy reading
        by_category = {}
        for row in rows:
            cat = row.get('task_category', 'unknown')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                'model': row.get('preferred_model'),
                'avg_score': row.get('avg_score'),
                'success_count': row.get('success_count'),
                'total_count': row.get('total_count'),
                'updated_at': str(row.get('updated_at', '')),
            })

        return jsonify({
            'success': True,
            'count': len(rows),
            'by_category': by_category,
            'all_data': [
                {k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v
                 for k, v in row.items()}
                for row in rows
            ],
            'note': 'Models need 3+ tasks per category to appear in /api/reasoning recommendations. '
                    'All data shown here regardless of count.'
        })
    except ImportError as e:
        return jsonify({
            'success': False,
            'error': f'routing_optimizer module not available: {e}',
            'message': 'Phase 5 routing optimizer not deployed yet'
        }), 503
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e),
                        'traceback': traceback.format_exc()}), 500


@learning_bp.route('/api/learning/enhancements', methods=['GET'])
def get_enhancements():
    """
    GET /api/learning/enhancements

    Returns all active prompt enhancements accumulated by prompt_optimizer.
    These are injected into AI prompts to improve response quality
    based on observed patterns.

    Query params:
    - category: Filter by task_category (optional)
    - active_only: Return only active enhancements (default true)

    Response:
    {
      "success": true,
      "count": 3,
      "by_category": {
        "scheduling": [{"id": 1, "enhancement_text": "...", "times_used": 5}]
      },
      "all_data": [...]
    }
    """
    try:
        from intelligence.prompt_optimizer import get_all_enhancements
        category_filter = request.args.get('category', None)
        active_only = request.args.get('active_only', 'true').lower() != 'false'

        rows = get_all_enhancements()

        # Apply filters
        if active_only:
            rows = [r for r in rows if r.get('active', True)]
        if category_filter:
            rows = [r for r in rows if r.get('task_category') == category_filter]

        # Group by category
        by_category = {}
        for row in rows:
            cat = row.get('task_category', 'unknown')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                'id': row.get('id'),
                'enhancement_text': row.get('enhancement_text'),
                'source': row.get('source'),
                'times_used': row.get('times_used'),
                'avg_improvement': row.get('avg_improvement'),
                'active': row.get('active'),
                'created_at': str(row.get('created_at', '')),
            })

        return jsonify({
            'success': True,
            'count': len(rows),
            'by_category': by_category,
            'all_data': [
                {k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v
                 for k, v in row.items()}
                for row in rows
            ]
        })
    except ImportError as e:
        return jsonify({
            'success': False,
            'error': f'prompt_optimizer module not available: {e}',
            'message': 'Phase 5 prompt optimizer not deployed yet'
        }), 503
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e),
                        'traceback': traceback.format_exc()}), 500


@learning_bp.route('/api/learning/review/latest', methods=['GET'])
def get_latest_review():
    """
    GET /api/learning/review/latest

    Returns the most recent weekly review from the weekly_reviews table.
    Returns 404 with a clear message if no reviews have been run yet.

    Response:
    {
      "success": true,
      "review": {
        "id": 1,
        "run_at": "2026-03-09 10:00:00",
        "health_score": 82,
        "trend": "stable",
        "tasks_processed": 45,
        "success_rate": 93.3,
        "gaps_count": 2,
        "high_priority_gaps_count": 0,
        "actions_taken": {...},
        "full_report": {...}
      }
    }
    """
    try:
        from intelligence.weekly_review import get_latest_review as _get_latest
        review = _get_latest()

        if review is None:
            return jsonify({
                'success': True,
                'review': None,
                'message': 'No weekly reviews have been run yet. '
                           'POST /api/learning/review/run to trigger the first review.'
            }), 404

        return jsonify({'success': True, 'review': review})
    except ImportError as e:
        return jsonify({
            'success': False,
            'error': f'weekly_review module not available: {e}',
            'message': 'Phase 5 weekly review not deployed yet'
        }), 503
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e),
                        'traceback': traceback.format_exc()}), 500


@learning_bp.route('/api/learning/review/run', methods=['POST'])
def run_weekly_review():
    """
    POST /api/learning/review/run

    Triggers the weekly review process synchronously.
    Collects metrics, runs AI analysis, takes Phase 5 actions,
    and saves the result to weekly_reviews table.

    Expect this to take 10-20 seconds (one Sonnet call + DB operations).

    Query params:
    - days: Number of days to analyze (default 7, max 90)

    Response:
    {
      "success": true,
      "review_id": 1,
      "health_score": 82,
      "trend": "stable",
      "executive_summary": "...",
      "recommendations": [...],
      "actions_taken": {
        "enhancements_generated": 2,
        "memory_stored": true,
        "routing_memory_stored": true,
        "old_memories_deactivated": 0,
        "errors": []
      },
      "gaps_count": 2,
      "high_priority_gaps_count": 0,
      "next_week_focus": [...]
    }
    """
    try:
        from intelligence.weekly_review import run_weekly_review as _run_review

        # Validate and clamp days param
        try:
            days = int(request.args.get('days', 7))
            days = max(1, min(90, days))
        except (TypeError, ValueError):
            days = 7

        result = _run_review(days=days)
        status_code = 200 if result.get('success') else 500
        return jsonify(result), status_code

    except ImportError as e:
        return jsonify({
            'success': False,
            'error': f'weekly_review module not available: {e}',
            'message': 'Phase 5 weekly review not deployed yet'
        }), 503
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'error': str(e),
                        'traceback': traceback.format_exc()}), 500


@learning_bp.route('/api/learning/dashboard', methods=['GET'])
def get_phase5_dashboard():
    """
    GET /api/learning/dashboard

    Combined Phase 5 overview: routing preferences, prompt enhancements,
    and the latest weekly review in a single call.

    Each section degrades gracefully — if a module is unavailable,
    that section shows an error without failing the whole response.

    Response:
    {
      "success": true,
      "routing_preferences": {"count": 6, "by_category": {...}},
      "prompt_enhancements": {"count": 3, "by_category": {...}},
      "latest_review": {"health_score": 82, "trend": "stable", ...},
      "phase5_summary": {
        "routing_categories_tracked": 3,
        "active_enhancements": 3,
        "last_review_health_score": 82,
        "last_review_date": "2026-03-09 10:00:00",
        "last_review_trend": "stable"
      }
    }
    """
    response = {'success': True}

    # --- Routing Preferences ---
    try:
        from intelligence.routing_optimizer import get_all_routing_data
        rows = get_all_routing_data()
        by_category = {}
        for row in rows:
            cat = row.get('task_category', 'unknown')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                'model': row.get('preferred_model'),
                'avg_score': row.get('avg_score'),
                'total_count': row.get('total_count'),
            })
        response['routing_preferences'] = {
            'count': len(rows),
            'by_category': by_category,
        }
    except ImportError:
        response['routing_preferences'] = {'error': 'routing_optimizer not available'}
    except Exception as e:
        response['routing_preferences'] = {'error': str(e)}

    # --- Prompt Enhancements ---
    try:
        from intelligence.prompt_optimizer import get_all_enhancements
        rows = get_all_enhancements()
        active_rows = [r for r in rows if r.get('active', True)]
        by_category = {}
        for row in active_rows:
            cat = row.get('task_category', 'unknown')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                'id': row.get('id'),
                'enhancement_text': row.get('enhancement_text'),
                'times_used': row.get('times_used'),
            })
        response['prompt_enhancements'] = {
            'count': len(active_rows),
            'by_category': by_category,
        }
    except ImportError:
        response['prompt_enhancements'] = {'error': 'prompt_optimizer not available'}
    except Exception as e:
        response['prompt_enhancements'] = {'error': str(e)}

    # --- Latest Weekly Review ---
    try:
        from intelligence.weekly_review import get_latest_review as _get_latest
        review = _get_latest()
        response['latest_review'] = review  # None if no reviews yet
    except ImportError:
        response['latest_review'] = {'error': 'weekly_review not available'}
    except Exception as e:
        response['latest_review'] = {'error': str(e)}

    # --- Phase 5 Summary ---
    routing_data = response.get('routing_preferences', {})
    enhancement_data = response.get('prompt_enhancements', {})
    review_data = response.get('latest_review')

    routing_categories = len(routing_data.get('by_category', {})) if isinstance(routing_data, dict) else 0
    active_enhancements = enhancement_data.get('count', 0) if isinstance(enhancement_data, dict) else 0
    last_health = review_data.get('health_score') if isinstance(review_data, dict) and review_data else None
    last_date = review_data.get('run_at') if isinstance(review_data, dict) and review_data else None
    last_trend = review_data.get('trend') if isinstance(review_data, dict) and review_data else None

    response['phase5_summary'] = {
        'routing_categories_tracked': routing_categories,
        'active_enhancements': active_enhancements,
        'last_review_health_score': last_health,
        'last_review_date': last_date,
        'last_review_trend': last_trend,
        'review_endpoint': 'POST /api/learning/review/run',
    }

    return jsonify(response)


# I did no harm and this file is not truncated
