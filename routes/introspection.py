"""
Introspection Routes
Created: January 25, 2026
Last Updated: January 25, 2026

API endpoints for the Introspection Layer - emulated self-awareness.

ENDPOINTS:
- GET  /api/introspection/status       - Get introspection system status
- POST /api/introspection/run          - Trigger an introspection cycle
- GET  /api/introspection/latest       - Get most recent introspection report
- GET  /api/introspection/history      - Get introspection history
- GET  /api/introspection/<id>         - Get specific introspection by ID
- GET  /api/introspection/notification - Check for pending notification
- POST /api/introspection/notification/dismiss - Dismiss a notification
- GET  /api/introspection/reflection   - Get just the reflection narrative

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import json

introspection_bp = Blueprint('introspection', __name__)


# ============================================================================
# IMPORT INTROSPECTION ENGINE
# ============================================================================

INTROSPECTION_AVAILABLE = False
engine = None

try:
    from introspection import (
        get_introspection_engine,
        check_introspection_notifications,
        is_introspection_request
    )
    from introspection.introspection_engine import mark_notification_shown
    engine = get_introspection_engine()
    INTROSPECTION_AVAILABLE = True
    print("✅ Introspection Layer loaded")
except ImportError as e:
    print(f"ℹ️  Introspection Layer not available: {e}")
except Exception as e:
    print(f"⚠️  Introspection Layer error: {e}")


# ============================================================================
# STATUS ENDPOINT
# ============================================================================

@introspection_bp.route('/api/introspection/status', methods=['GET'])
def get_introspection_status():
    """
    Get the status of the introspection system.
    
    Returns:
    - available: Whether introspection is operational
    - last_introspection: Most recent report summary
    - components: Status of each introspection component
    - schedule: When evaluations run
    """
    try:
        if not INTROSPECTION_AVAILABLE or not engine:
            return jsonify({
                'success': True,
                'available': False,
                'message': 'Introspection Layer not installed'
            })
        
        # Get latest introspection
        latest = engine.get_latest_introspection()
        
        # Get introspection count
        from database import get_db
        db = get_db()
        try:
            count = db.execute('SELECT COUNT(*) FROM introspection_insights').fetchone()[0]
        except:
            count = 0
        finally:
            db.close()
        
        return jsonify({
            'success': True,
            'available': True,
            'last_introspection': {
                'id': latest.get('id') if latest else None,
                'created_at': latest.get('created_at') if latest else None,
                'insight_type': latest.get('insight_type') if latest else None,
                'health_score': int(latest.get('confidence_score', 0) * 100) if latest else None,
                'requires_action': latest.get('requires_action') if latest else None
            } if latest else None,
            'total_introspections': count,
            'components': {
                'self_monitoring': 'active',
                'capability_boundaries': 'phase_2',
                'confidence_calibration': 'phase_2',
                'proposals': 'phase_3',
                'goal_alignment': 'active'
            },
            'schedule': {
                'weekly': 'Wednesday 8:00 AM',
                'monthly_deep_dive': 'First Wednesday of month'
            },
            'version': '1.0 (Phase 1)'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# RUN INTROSPECTION ENDPOINT
# ============================================================================

@introspection_bp.route('/api/introspection/run', methods=['POST'])
def run_introspection():
    """
    Trigger an introspection cycle.
    
    Request Body (optional):
    {
        "days": 7,           // Number of days to analyze (default: 7, max: 90)
        "is_monthly": false  // Whether this is a monthly deep-dive
    }
    
    Returns:
    - Complete introspection report with health score, alignment, and reflection
    """
    try:
        if not INTROSPECTION_AVAILABLE or not engine:
            return jsonify({
                'success': False,
                'error': 'Introspection Layer not available'
            }), 503
        
        # Parse request parameters
        data = request.json or {}
        days = data.get('days', 7)
        is_monthly = data.get('is_monthly', False)
        
        # Validate days
        if not isinstance(days, int) or days < 1 or days > 90:
            return jsonify({
                'success': False,
                'error': 'Days must be an integer between 1 and 90'
            }), 400
        
        # Auto-detect monthly if 30 days requested
        if days >= 28 and not is_monthly:
            is_monthly = True
        
        # Run the introspection
        report = engine.run_introspection(days=days, is_monthly=is_monthly)
        
        return jsonify({
            'success': True,
            'introspection': {
                'id': report.get('insight_id'),
                'type': report.get('introspection_type'),
                'generated_at': report.get('generated_at'),
                'period_days': report.get('period_days'),
                'summary': report.get('summary'),
                'reflection': report.get('reflection'),
                'components': {
                    'self_monitoring': report.get('components', {}).get('self_monitoring', {}).get('status'),
                    'goal_alignment': report.get('components', {}).get('goal_alignment', {}).get('status')
                }
            }
        })
    except Exception as e:
        import traceback
        print(f"Introspection run error: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET LATEST INTROSPECTION
# ============================================================================

@introspection_bp.route('/api/introspection/latest', methods=['GET'])
def get_latest_introspection():
    """
    Get the most recent introspection report.
    
    Query Parameters:
    - full: If 'true', include complete raw data (default: false)
    
    Returns:
    - Latest introspection summary or full report
    """
    try:
        if not INTROSPECTION_AVAILABLE or not engine:
            return jsonify({
                'success': False,
                'error': 'Introspection Layer not available'
            }), 503
        
        include_full = request.args.get('full', 'false').lower() == 'true'
        
        latest = engine.get_latest_introspection()
        
        if not latest:
            return jsonify({
                'success': True,
                'introspection': None,
                'message': 'No introspections found. Run an introspection first.'
            })
        
        response = {
            'success': True,
            'introspection': {
                'id': latest.get('id'),
                'type': latest.get('insight_type'),
                'created_at': latest.get('created_at'),
                'summary': latest.get('summary'),
                'health_score': int(latest.get('confidence_score', 0) * 100),
                'requires_action': latest.get('requires_action'),
                'notification_pending': latest.get('notification_pending')
            }
        }
        
        if include_full and latest.get('full_report'):
            response['full_report'] = latest.get('full_report')
        
        return jsonify(response)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET INTROSPECTION HISTORY
# ============================================================================

@introspection_bp.route('/api/introspection/history', methods=['GET'])
def get_introspection_history():
    """
    Get history of past introspections.
    
    Query Parameters:
    - limit: Maximum number to return (default: 10, max: 50)
    
    Returns:
    - List of introspection summaries (newest first)
    """
    try:
        if not INTROSPECTION_AVAILABLE or not engine:
            return jsonify({
                'success': False,
                'error': 'Introspection Layer not available'
            }), 503
        
        limit = request.args.get('limit', 10, type=int)
        limit = min(max(limit, 1), 50)
        
        history = engine.get_introspection_history(limit=limit)
        
        return jsonify({
            'success': True,
            'introspections': history,
            'count': len(history)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET SPECIFIC INTROSPECTION
# ============================================================================

@introspection_bp.route('/api/introspection/<int:introspection_id>', methods=['GET'])
def get_introspection_by_id(introspection_id):
    """
    Get a specific introspection by ID.
    
    Returns:
    - Full introspection report
    """
    try:
        if not INTROSPECTION_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Introspection Layer not available'
            }), 503
        
        from database import get_db
        db = get_db()
        
        try:
            row = db.execute('''
                SELECT * FROM introspection_insights WHERE id = ?
            ''', (introspection_id,)).fetchone()
            
            if not row:
                return jsonify({
                    'success': False,
                    'error': f'Introspection {introspection_id} not found'
                }), 404
            
            introspection = {
                'id': row['id'],
                'insight_type': row['insight_type'],
                'created_at': row['created_at'],
                'period_analyzed': row['period_analyzed'],
                'summary': row['summary'],
                'health_score': int(row['confidence_score'] * 100) if row['confidence_score'] else 0,
                'requires_action': bool(row['requires_action']),
                'notification_pending': bool(row['notification_pending']),
                'full_report': json.loads(row['full_analysis_json']) if row['full_analysis_json'] else None
            }
            
            return jsonify({
                'success': True,
                'introspection': introspection
            })
        finally:
            db.close()
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# CHECK NOTIFICATION
# ============================================================================

@introspection_bp.route('/api/introspection/notification', methods=['GET'])
def check_notification():
    """
    Check if there's a pending introspection notification.
    
    Returns:
    - has_notification: boolean
    - notification details if pending
    - formatted_message: Ready to display message
    """
    try:
        if not INTROSPECTION_AVAILABLE or not engine:
            return jsonify({
                'success': True,
                'has_notification': False
            })
        
        notification = check_introspection_notifications()
        
        if notification.get('has_notification'):
            notification['formatted_message'] = engine.format_notification_message(notification)
        
        return jsonify({
            'success': True,
            **notification
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'has_notification': False,
            'error': str(e)
        }), 500


# ============================================================================
# DISMISS NOTIFICATION
# ============================================================================

@introspection_bp.route('/api/introspection/notification/dismiss', methods=['POST'])
def dismiss_notification():
    """
    Dismiss (mark as shown) a pending introspection notification.
    
    Request Body:
    {
        "introspection_id": 123
    }
    """
    try:
        if not INTROSPECTION_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Introspection Layer not available'
            }), 503
        
        data = request.json or {}
        introspection_id = data.get('introspection_id')
        
        if not introspection_id:
            return jsonify({
                'success': False,
                'error': 'introspection_id is required'
            }), 400
        
        success = mark_notification_shown(introspection_id)
        
        return jsonify({
            'success': success,
            'message': 'Notification dismissed' if success else 'Failed to dismiss notification'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET REFLECTION NARRATIVE
# ============================================================================

@introspection_bp.route('/api/introspection/reflection', methods=['GET'])
def get_reflection():
    """
    Get just the reflection narrative from the latest introspection.
    This is the first-person self-assessment text.
    
    Returns:
    - reflection: The narrative text
    - health_score: Current health score
    - generated_at: When the reflection was generated
    """
    try:
        if not INTROSPECTION_AVAILABLE or not engine:
            return jsonify({
                'success': False,
                'error': 'Introspection Layer not available'
            }), 503
        
        latest = engine.get_latest_introspection()
        
        if not latest or not latest.get('full_report'):
            return jsonify({
                'success': True,
                'reflection': None,
                'message': 'No reflection available. Run an introspection first.'
            })
        
        full_report = latest.get('full_report', {})
        
        return jsonify({
            'success': True,
            'reflection': full_report.get('reflection', ''),
            'health_score': full_report.get('summary', {}).get('health_score', 0),
            'generated_at': full_report.get('generated_at', ''),
            'introspection_id': latest.get('id')
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# GET GOAL ALIGNMENT DETAILS
# ============================================================================

@introspection_bp.route('/api/introspection/alignment', methods=['GET'])
def get_goal_alignment():
    """
    Get detailed goal alignment analysis from the latest introspection.
    
    Returns:
    - alignment_score: Overall alignment percentage
    - by_objective: Breakdown by business objective
    - observations: Key findings
    """
    try:
        if not INTROSPECTION_AVAILABLE or not engine:
            return jsonify({
                'success': False,
                'error': 'Introspection Layer not available'
            }), 503
        
        latest = engine.get_latest_introspection()
        
        if not latest or not latest.get('full_report'):
            return jsonify({
                'success': True,
                'alignment': None,
                'message': 'No alignment data available. Run an introspection first.'
            })
        
        full_report = latest.get('full_report', {})
        alignment = full_report.get('components', {}).get('goal_alignment', {})
        
        return jsonify({
            'success': True,
            'alignment': {
                'score': alignment.get('alignment_score', 0),
                'by_objective': alignment.get('by_objective', []),
                'unaligned_tasks': alignment.get('unaligned_tasks', 0),
                'total_tasks': alignment.get('total_tasks', 0),
                'observations': alignment.get('observations', [])
            },
            'business_objectives': engine.business_objectives,
            'introspection_id': latest.get('id')
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# DETECT INTROSPECTION INTENT
# ============================================================================

@introspection_bp.route('/api/introspection/detect', methods=['POST'])
def detect_intent():
    """
    Detect if a user message is an introspection request.
    Used by the orchestrator to route introspection commands.
    
    Request Body:
    {
        "message": "how are you doing?"
    }
    
    Returns:
    - is_introspection: boolean
    - action: 'run', 'show_latest', 'show_proposals', or null
    - confidence: float
    """
    try:
        if not INTROSPECTION_AVAILABLE:
            return jsonify({
                'success': True,
                'is_introspection': False,
                'message': 'Introspection Layer not available'
            })
        
        data = request.json or {}
        message = data.get('message', '')
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'message is required'
            }), 400
        
        result = is_introspection_request(message)
        
        return jsonify({
            'success': True,
            **result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# I did no harm and this file is not truncated
