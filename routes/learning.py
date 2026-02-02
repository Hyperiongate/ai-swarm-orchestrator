"""
LEARNING API ROUTES - Phase 1 API Endpoints
Created: February 2, 2026
Last Updated: February 2, 2026

New Flask blueprint for learning system management.
Provides endpoints to view learning status, run cycles, and manage adjustments.

CRITICAL: This is a completely NEW blueprint that doesn't modify existing routes.

Endpoints:
- GET  /api/learning/status - Get learning system status
- POST /api/learning/run-cycle - Manually trigger learning cycle
- GET  /api/learning/patterns - View discovered patterns
- GET  /api/learning/adjustments - View pending adjustments
- POST /api/learning/adjustments/:id/approve - Approve an adjustment
- POST /api/learning/adjustments/:id/reject - Reject an adjustment
- GET  /api/learning/report - Comprehensive learning report

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

from flask import Blueprint, jsonify, request
from learning_integration import learning_integration
import sqlite3
from datetime import datetime


# Create blueprint
learning_bp = Blueprint('learning', __name__)


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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/api/learning/run-cycle', methods=['POST'])
def run_learning_cycle():
    """
    Manually trigger a learning cycle.
    
    Query params:
    - min_observations: Minimum outcomes needed (default 10)
    
    Returns results of learning cycle including patterns found.
    """
    try:
        min_obs = request.args.get('min_observations', 10, type=int)
        
        results = learning_integration.run_learning_cycle(min_observations=min_obs)
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
        
        query = '''
            SELECT * FROM learned_patterns
            WHERE active = 1 AND confidence >= ?
        '''
        params = [min_confidence]
        
        if pattern_type:
            query += ' AND pattern_type = ?'
            params.append(pattern_type)
        
        query += ' ORDER BY confidence DESC, supporting_evidence DESC LIMIT ?'
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
            cursor.execute('''
                SELECT * FROM behavior_adjustments
                WHERE reverted = 0
                ORDER BY created_at DESC
            ''')
        else:
            cursor.execute('''
                SELECT * FROM behavior_adjustments
                WHERE approved = 0 AND reverted = 0
                ORDER BY created_at DESC
            ''')
        
        adjustments = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        return jsonify({
            'success': True,
            'count': len(adjustments),
            'adjustments': adjustments
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
        
        # Check if adjustment exists and is pending
        cursor.execute('''
            SELECT * FROM behavior_adjustments
            WHERE id = ? AND approved = 0
        ''', (adjustment_id,))
        
        adjustment = cursor.fetchone()
        if not adjustment:
            db.close()
            return jsonify({
                'success': False,
                'error': 'Adjustment not found or already approved'
            }), 404
        
        # Approve the adjustment
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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/api/learning/adjustments/<int:adjustment_id>/reject', methods=['POST'])
def reject_adjustment(adjustment_id):
    """
    Reject a suggested behavior adjustment.
    
    Body (optional):
    - reason: Why rejected (for learning)
    """
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'User rejected')
        
        db = sqlite3.connect(learning_integration.engine.db_path)
        cursor = db.cursor()
        
        # Mark as reverted (we use reverted flag to indicate rejection)
        cursor.execute('''
            UPDATE behavior_adjustments
            SET reverted = 1,
                reverted_at = ?
            WHERE id = ? AND approved = 0
        ''', (datetime.now(), adjustment_id))
        
        if cursor.rowcount == 0:
            db.close()
            return jsonify({
                'success': False,
                'error': 'Adjustment not found or already processed'
            }), 404
        
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'message': 'Adjustment rejected',
            'adjustment_id': adjustment_id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/api/learning/report', methods=['GET'])
def get_comprehensive_report():
    """
    Get comprehensive learning report with all metrics and insights.
    """
    try:
        report = learning_integration.get_learning_report()
        adjustments = learning_integration.get_pending_adjustments()
        
        # Add some computed insights
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
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/api/learning/enable', methods=['POST'])
def enable_learning():
    """Enable the learning system"""
    try:
        learning_integration.enable()
        return jsonify({
            'success': True,
            'message': 'Learning system enabled'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@learning_bp.route('/api/learning/disable', methods=['POST'])
def disable_learning():
    """Disable the learning system"""
    try:
        learning_integration.disable()
        return jsonify({
            'success': True,
            'message': 'Learning system disabled'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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


# I did no harm and this file is not truncated
