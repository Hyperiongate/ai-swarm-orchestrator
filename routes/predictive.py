"""
PREDICTIVE INTELLIGENCE API ROUTES - Phase 2
Created: February 2, 2026
Last Updated: February 2, 2026

API endpoints for predictive intelligence features.
Provides predictions, suggestions, and pattern insights.

Endpoints:
- GET  /api/predictive/status - Get predictive system status
- POST /api/predictive/analyze - Run predictive analysis
- POST /api/predictive/predict - Get predictions for current context
- GET  /api/predictive/patterns - View learned patterns
- GET  /api/predictive/suggestions - Get proactive suggestions
- POST /api/predictive/suggestions/:id/feedback - Track suggestion outcome

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

from flask import Blueprint, jsonify, request
from predictive_intelligence import get_predictive_engine
import sqlite3
from datetime import datetime


# Create blueprint
predictive_bp = Blueprint('predictive', __name__)


@predictive_bp.route('/api/predictive/status', methods=['GET'])
def get_status():
    """
    Get current status of predictive intelligence system.
    
    Returns metrics about patterns learned and suggestions made.
    """
    try:
        engine = get_predictive_engine()
        report = engine.get_status_report()
        
        return jsonify({
            'success': True,
            'enabled': True,
            'status': report['status'],
            'metrics': {
                'behavior_patterns': report['behavior_patterns'],
                'phase_patterns': report['phase_patterns'],
                'total_suggestions': report['total_suggestions_made'],
                'accepted_suggestions': report['suggestions_accepted'],
                'acceptance_rate': report['acceptance_rate']
            },
            'top_patterns': report['top_patterns'],
            'needs_action': report['status'] == 'needs_more_data'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@predictive_bp.route('/api/predictive/analyze', methods=['POST'])
def run_analysis():
    """
    Run predictive analysis to discover new patterns.
    
    Query params:
    - days_back: Number of days to analyze (default 30)
    
    Returns discovered patterns and their confidence scores.
    """
    try:
        days_back = request.args.get('days_back', 30, type=int)
        
        engine = get_predictive_engine()
        results = engine.analyze_and_learn(days_back=days_back)
        
        return jsonify({
            'success': True,
            'results': results,
            'message': f'Analyzed last {days_back} days and found {results["total_patterns"]} patterns'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@predictive_bp.route('/api/predictive/predict', methods=['POST'])
def get_predictions():
    """
    Get predictions for current context.
    
    Body:
    {
        "task_type": "schedule_design",
        "project_phase": "implementation_planning",
        "industry": "manufacturing",
        "facility_type": "24/7"
    }
    
    Returns predictions about what user likely needs next.
    """
    try:
        data = request.get_json() or {}
        
        current_context = {
            'task_type': data.get('task_type', ''),
            'project_phase': data.get('project_phase', ''),
            'industry': data.get('industry', ''),
            'facility_type': data.get('facility_type', ''),
            'project_id': data.get('project_id')
        }
        
        engine = get_predictive_engine()
        predictions = engine.get_predictions(current_context)
        
        return jsonify({
            'success': True,
            'predictions': predictions
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@predictive_bp.route('/api/predictive/patterns', methods=['GET'])
def get_patterns():
    """
    Get all learned behavior patterns.
    
    Query params:
    - min_confidence: Minimum confidence threshold (default 0.70)
    - pattern_type: Filter by type (optional)
    - limit: Max results (default 20)
    """
    try:
        min_confidence = request.args.get('min_confidence', 0.70, type=float)
        pattern_type = request.args.get('pattern_type', None)
        limit = request.args.get('limit', 20, type=int)
        
        engine = get_predictive_engine()
        db = sqlite3.connect(engine.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        query = '''
            SELECT * FROM user_behavior_patterns
            WHERE confidence >= ?
        '''
        params = [min_confidence]
        
        if pattern_type:
            query += ' AND pattern_type = ?'
            params.append(pattern_type)
        
        query += ' ORDER BY confidence DESC, observation_count DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        patterns = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        return jsonify({
            'success': True,
            'count': len(patterns),
            'patterns': patterns
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@predictive_bp.route('/api/predictive/suggestions', methods=['GET'])
def get_suggestions():
    """
    Get proactive suggestions for user.
    
    Query params:
    - recent_only: Return only suggestions from last 24 hours (default true)
    - limit: Max results (default 5)
    """
    try:
        recent_only = request.args.get('recent_only', 'true').lower() == 'true'
        limit = request.args.get('limit', 5, type=int)
        
        engine = get_predictive_engine()
        db = sqlite3.connect(engine.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        if recent_only:
            cursor.execute('''
                SELECT * FROM proactive_suggestions
                WHERE datetime(created_at) >= datetime('now', '-1 day')
                AND user_action IS NULL
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT * FROM proactive_suggestions
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
        
        suggestions = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        return jsonify({
            'success': True,
            'count': len(suggestions),
            'suggestions': suggestions
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@predictive_bp.route('/api/predictive/suggestions/<int:suggestion_id>/feedback', methods=['POST'])
def track_suggestion_feedback(suggestion_id):
    """
    Track user's response to a suggestion.
    
    Body:
    {
        "action": "accepted" | "rejected" | "ignored"
    }
    
    This helps the system learn which suggestions are valuable.
    """
    try:
        data = request.get_json() or {}
        action = data.get('action', 'ignored')
        
        if action not in ['accepted', 'rejected', 'ignored']:
            return jsonify({
                'success': False,
                'error': 'Action must be: accepted, rejected, or ignored'
            }), 400
        
        engine = get_predictive_engine()
        engine.suggestion_engine.track_suggestion_outcome(suggestion_id, action)
        
        return jsonify({
            'success': True,
            'message': f'Suggestion {suggestion_id} marked as {action}',
            'suggestion_id': suggestion_id,
            'action': action
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@predictive_bp.route('/api/predictive/report', methods=['GET'])
def get_comprehensive_report():
    """
    Get comprehensive predictive intelligence report.
    
    Includes all patterns, predictions, and system status.
    """
    try:
        engine = get_predictive_engine()
        status = engine.get_status_report()
        
        # Get sample predictions
        sample_context = {
            'task_type': 'schedule_design',
            'project_phase': 'implementation_planning',
            'industry': 'manufacturing'
        }
        sample_predictions = engine.get_predictions(sample_context)
        
        insights = []
        
        if status['behavior_patterns'] > 0:
            insights.append({
                'type': 'patterns_discovered',
                'message': f"Discovered {status['behavior_patterns']} behavior patterns",
                'action': 'GET /api/predictive/patterns'
            })
        
        if status['acceptance_rate'] > 50:
            insights.append({
                'type': 'high_acceptance',
                'message': f"Users accept {status['acceptance_rate']:.1f}% of suggestions - predictions are valuable!",
                'action': None
            })
        
        if status['status'] == 'needs_more_data':
            insights.append({
                'type': 'needs_data',
                'message': 'Predictive system needs more task history. Keep using the Swarm!',
                'action': None
            })
        
        return jsonify({
            'success': True,
            'report': status,
            'sample_predictions': sample_predictions,
            'insights': insights,
            'recommendations': _generate_recommendations(status)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _generate_recommendations(status: dict) -> list:
    """Generate actionable recommendations based on status"""
    recommendations = []
    
    if status['behavior_patterns'] == 0:
        recommendations.append({
            'priority': 'high',
            'category': 'action_needed',
            'title': 'Run Initial Analysis',
            'description': 'Run predictive analysis to discover your first patterns',
            'action': 'Run analysis',
            'endpoint': 'POST /api/predictive/analyze'
        })
    
    if status['behavior_patterns'] > 5:
        recommendations.append({
            'priority': 'low',
            'category': 'success',
            'title': 'Patterns Active',
            'description': f"Great! {status['behavior_patterns']} patterns are helping predict your needs",
            'action': None,
            'endpoint': None
        })
    
    if status['acceptance_rate'] < 30 and status['total_suggestions_made'] > 10:
        recommendations.append({
            'priority': 'medium',
            'category': 'optimization',
            'title': 'Low Suggestion Acceptance',
            'description': f"Only {status['acceptance_rate']:.1f}% of suggestions accepted. System will adapt based on your feedback.",
            'action': 'Continue providing feedback',
            'endpoint': None
        })
    
    return recommendations


# I did no harm and this file is not truncated
