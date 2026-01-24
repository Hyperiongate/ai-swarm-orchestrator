"""
Alert System API Routes
Created: January 23, 2026
Last Updated: January 23, 2026

PURPOSE:
API endpoints for the Alert System functionality.
Allows frontend to view, manage, and interact with alerts.

ENDPOINTS:
- GET  /api/alerts                  - Get all alerts
- GET  /api/alerts/<id>             - Get single alert
- POST /api/alerts/<id>/read        - Mark as read
- POST /api/alerts/<id>/acknowledge - Acknowledge alert
- POST /api/alerts/<id>/dismiss     - Dismiss alert
- POST /api/alerts/<id>/snooze      - Snooze alert
- POST /api/alerts/<id>/action      - Record action taken
- GET  /api/alerts/counts           - Get alert counts
- GET  /api/alerts/jobs             - Get scheduled jobs
- POST /api/alerts/jobs/<id>/run    - Run job now
- POST /api/alerts/jobs/<id>/enable - Enable job
- POST /api/alerts/jobs/<id>/disable- Disable job
- GET  /api/alerts/monitored        - Get monitored entities
- POST /api/alerts/monitored/client - Add client to monitor
- POST /api/alerts/monitored/competitor - Add competitor to monitor
- DELETE /api/alerts/monitored/<id> - Remove monitored entity
- GET  /api/alerts/status           - Get alert system status

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

from flask import Blueprint, request, jsonify
from datetime import datetime

alerts_bp = Blueprint('alerts', __name__)

# Import alert system components
ALERTS_AVAILABLE = False
alert_manager = None
job_scheduler = None

try:
    from alert_system import (
        get_alert_manager, get_job_scheduler,
        AlertCategory, AlertPriority,
        add_monitored_client, add_monitored_competitor,
        get_monitored_entities, remove_monitored_entity,
        ENABLE_EMAIL_ALERTS, ENABLE_SCHEDULED_JOBS, ALERT_TO_EMAIL
    )
    alert_manager = get_alert_manager()
    job_scheduler = get_job_scheduler()
    ALERTS_AVAILABLE = True
    print("✅ Alert System routes loaded")
except ImportError as e:
    print(f"ℹ️  Alert System not available: {e}")
except Exception as e:
    print(f"⚠️  Alert System error: {e}")


# =============================================================================
# ALERT ENDPOINTS
# =============================================================================

@alerts_bp.route('/api/alerts/status', methods=['GET'])
def get_alert_status():
    """Get alert system status"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': True,
            'available': False,
            'message': 'Alert System not initialized'
        })
    
    return jsonify({
        'success': True,
        'available': True,
        'email_enabled': ENABLE_EMAIL_ALERTS,
        'scheduled_jobs_enabled': ENABLE_SCHEDULED_JOBS,
        'alert_recipient': ALERT_TO_EMAIL if ALERT_TO_EMAIL else 'not configured',
        'features': [
            'Lead monitoring',
            'Competitor tracking',
            'Regulatory updates',
            'Client news monitoring',
            'Daily briefings',
            'Email notifications'
        ]
    })


@alerts_bp.route('/api/alerts', methods=['GET'])
def get_alerts():
    """
    Get alerts with optional filtering.
    
    Query params:
        category: Filter by category
        priority: Filter by priority
        unread: Only unread alerts (true/false)
        limit: Max number of alerts (default 50)
        include_dismissed: Include dismissed alerts (true/false)
    """
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    category = request.args.get('category')
    priority = request.args.get('priority')
    unread_only = request.args.get('unread', 'false').lower() == 'true'
    limit = request.args.get('limit', 50, type=int)
    include_dismissed = request.args.get('include_dismissed', 'false').lower() == 'true'
    
    alerts = alert_manager.get_alerts(
        category=category,
        priority=priority,
        unread_only=unread_only,
        limit=limit,
        include_dismissed=include_dismissed
    )
    
    return jsonify({
        'success': True,
        'alerts': alerts,
        'count': len(alerts)
    })


@alerts_bp.route('/api/alerts/counts', methods=['GET'])
def get_alert_counts():
    """Get alert counts by category and priority"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    counts = alert_manager.get_alert_counts()
    
    return jsonify({
        'success': True,
        **counts
    })


@alerts_bp.route('/api/alerts/<int:alert_id>', methods=['GET'])
def get_alert(alert_id):
    """Get a single alert by ID"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    alert = alert_manager.get_alert(alert_id)
    
    if not alert:
        return jsonify({
            'success': False,
            'error': 'Alert not found'
        }), 404
    
    return jsonify({
        'success': True,
        'alert': alert
    })


@alerts_bp.route('/api/alerts/<int:alert_id>/read', methods=['POST'])
def mark_alert_read(alert_id):
    """Mark an alert as read"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    alert_manager.mark_read(alert_id)
    
    return jsonify({
        'success': True,
        'message': 'Alert marked as read'
    })


@alerts_bp.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    alert_manager.acknowledge_alert(alert_id)
    
    return jsonify({
        'success': True,
        'message': 'Alert acknowledged'
    })


@alerts_bp.route('/api/alerts/<int:alert_id>/dismiss', methods=['POST'])
def dismiss_alert(alert_id):
    """Dismiss an alert"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    alert_manager.dismiss_alert(alert_id)
    
    return jsonify({
        'success': True,
        'message': 'Alert dismissed'
    })


@alerts_bp.route('/api/alerts/<int:alert_id>/snooze', methods=['POST'])
def snooze_alert(alert_id):
    """
    Snooze an alert for specified hours.
    
    Body:
        hours: Number of hours to snooze (default 24)
    """
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    data = request.json or {}
    hours = data.get('hours', 24)
    
    alert_manager.snooze_alert(alert_id, hours=hours)
    
    return jsonify({
        'success': True,
        'message': f'Alert snoozed for {hours} hours'
    })


@alerts_bp.route('/api/alerts/<int:alert_id>/action', methods=['POST'])
def action_alert(alert_id):
    """
    Record action taken on an alert.
    
    Body:
        action: Description of action taken
    """
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    data = request.json or {}
    action = data.get('action')
    
    if not action:
        return jsonify({
            'success': False,
            'error': 'Action description required'
        }), 400
    
    alert_manager.action_alert(alert_id, action)
    
    return jsonify({
        'success': True,
        'message': 'Action recorded'
    })


# =============================================================================
# CREATE TEST ALERT (for testing)
# =============================================================================

@alerts_bp.route('/api/alerts/test', methods=['POST'])
def create_test_alert():
    """Create a test alert (for development/testing)"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    data = request.json or {}
    
    alert_id = alert_manager.create_alert(
        category=data.get('category', AlertCategory.SYSTEM),
        title=data.get('title', 'Test Alert'),
        summary=data.get('summary', 'This is a test alert from the Alert System.'),
        priority=data.get('priority', AlertPriority.MEDIUM),
        details=data.get('details', 'Test alert details.'),
        send_email=data.get('send_email', False)
    )
    
    return jsonify({
        'success': True,
        'alert_id': alert_id,
        'message': 'Test alert created'
    })


# =============================================================================
# JOB ENDPOINTS
# =============================================================================

@alerts_bp.route('/api/alerts/jobs', methods=['GET'])
def get_jobs():
    """Get all scheduled jobs"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
    jobs = job_scheduler.get_jobs(enabled_only=enabled_only)
    
    return jsonify({
        'success': True,
        'jobs': jobs
    })


@alerts_bp.route('/api/alerts/jobs/<int:job_id>', methods=['GET'])
def get_job(job_id):
    """Get a single job by ID"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    job = job_scheduler.get_job(job_id)
    
    if not job:
        return jsonify({
            'success': False,
            'error': 'Job not found'
        }), 404
    
    return jsonify({
        'success': True,
        'job': job
    })


@alerts_bp.route('/api/alerts/jobs/<int:job_id>/run', methods=['POST'])
def run_job(job_id):
    """Manually trigger a job to run immediately"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    result = job_scheduler.run_job_now(job_id)
    
    return jsonify(result)


@alerts_bp.route('/api/alerts/jobs/<int:job_id>/enable', methods=['POST'])
def enable_job(job_id):
    """Enable a scheduled job"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    job_scheduler.enable_job(job_id)
    
    return jsonify({
        'success': True,
        'message': 'Job enabled'
    })


@alerts_bp.route('/api/alerts/jobs/<int:job_id>/disable', methods=['POST'])
def disable_job(job_id):
    """Disable a scheduled job"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    job_scheduler.disable_job(job_id)
    
    return jsonify({
        'success': True,
        'message': 'Job disabled'
    })


# =============================================================================
# MONITORED ENTITIES ENDPOINTS
# =============================================================================

@alerts_bp.route('/api/alerts/monitored', methods=['GET'])
def get_monitored():
    """Get all monitored entities"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    entity_type = request.args.get('type')
    entities = get_monitored_entities(entity_type=entity_type)
    
    return jsonify({
        'success': True,
        'entities': entities
    })


@alerts_bp.route('/api/alerts/monitored/client', methods=['POST'])
def add_client():
    """
    Add a client to monitor for news.
    
    Body:
        name: Client name (required)
        search_terms: Custom search terms (optional)
    """
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    data = request.json or {}
    name = data.get('name')
    
    if not name:
        return jsonify({
            'success': False,
            'error': 'Client name required'
        }), 400
    
    result = add_monitored_client(
        client_name=name,
        search_terms=data.get('search_terms')
    )
    
    return jsonify(result)


@alerts_bp.route('/api/alerts/monitored/competitor', methods=['POST'])
def add_competitor():
    """
    Add a competitor to monitor.
    
    Body:
        name: Competitor name (required)
        search_terms: Custom search terms (optional)
    """
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    data = request.json or {}
    name = data.get('name')
    
    if not name:
        return jsonify({
            'success': False,
            'error': 'Competitor name required'
        }), 400
    
    result = add_monitored_competitor(
        competitor_name=name,
        search_terms=data.get('search_terms')
    )
    
    return jsonify(result)


@alerts_bp.route('/api/alerts/monitored/<int:entity_id>', methods=['DELETE'])
def remove_entity(entity_id):
    """Remove a monitored entity"""
    if not ALERTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Alert System not available'
        }), 503
    
    result = remove_monitored_entity(entity_id)
    
    return jsonify(result)


# I did no harm and this file is not truncated
