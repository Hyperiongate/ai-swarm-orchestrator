"""
AVATAR CONSULTATION ROUTES - Flask API Endpoints
Created: January 25, 2026
Last Updated: January 25, 2026

API endpoints for David & Sarah AI avatar consultation system.
Powers the interactive consultation experience on shift-work.com

ENDPOINTS:
- POST /api/avatar/start - Start new consultation
- POST /api/avatar/message - Send message to avatars
- GET /api/avatar/conversation/<id> - Get conversation history
- GET /api/avatar/leads - Get captured leads
- GET /api/avatar/stats - Get consultation statistics

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import json

# Import the avatar engine
try:
    from avatar_consultation_engine import get_avatar_engine
    AVATAR_AVAILABLE = True
except ImportError:
    print("⚠️ Avatar Consultation Engine not available")
    AVATAR_AVAILABLE = False

from database import get_db

# Create blueprint
avatar_bp = Blueprint('avatar', __name__)


# =============================================================================
# CONSULTATION ENDPOINTS
# =============================================================================

@avatar_bp.route('/api/avatar/start', methods=['POST'])
def start_consultation():
    """
    Start a new consultation with David & Sarah
    
    Returns:
        {
            'success': true,
            'conversation_id': 'uuid',
            'responses': [
                {'avatar': 'david', 'text': '...', 'audio_url': null, 'video_url': null},
                {'avatar': 'sarah', 'text': '...', 'audio_url': null, 'video_url': null}
            ],
            'stage': 'greeting',
            'awaiting_input': true
        }
    """
    if not AVATAR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Avatar consultation system not available'
        }), 503
    
    engine = get_avatar_engine()
    
    try:
        result = engine.start_conversation()
        
        return jsonify({
            'success': True,
            **result
        })
        
    except Exception as e:
        print(f"❌ Error starting consultation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@avatar_bp.route('/api/avatar/message', methods=['POST'])
def send_message():
    """
    Send a message to David & Sarah
    
    Body:
        conversation_id: UUID of conversation
        message: Visitor's message (text or voice transcript)
        visitor_info: Optional contact info (for lead capture)
            {
                'name': 'John Doe',
                'company': 'ABC Manufacturing',
                'email': 'john@abc.com',
                'phone': '555-1234'
            }
    
    Returns:
        {
            'success': true,
            'conversation_id': 'uuid',
            'responses': [
                {'avatar': 'david', 'text': '...', 'audio_url': null, 'video_url': null}
            ],
            'stage': 'discovery',
            'awaiting_input': true
        }
    """
    if not AVATAR_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Avatar consultation system not available'
        }), 503
    
    data = request.json or {}
    
    conversation_id = data.get('conversation_id')
    message = data.get('message')
    visitor_info = data.get('visitor_info')
    
    if not conversation_id or not message:
        return jsonify({
            'success': False,
            'error': 'conversation_id and message required'
        }), 400
    
    engine = get_avatar_engine()
    
    try:
        result = engine.process_message(conversation_id, message, visitor_info)
        
        return jsonify({
            'success': True,
            **result
        })
        
    except Exception as e:
        print(f"❌ Error processing message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@avatar_bp.route('/api/avatar/conversation/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """
    Get full conversation history
    
    Returns:
        {
            'success': true,
            'conversation_id': 'uuid',
            'messages': [
                {'role': 'visitor', 'content': '...', 'timestamp': '...'},
                {'role': 'avatars', 'content': '...', 'timestamp': '...'}
            ],
            'status': 'active',
            'visitor_info': {...}
        }
    """
    db = get_db()
    
    # Get conversation metadata
    conv = db.execute('''
        SELECT * FROM avatar_conversations WHERE conversation_id = ?
    ''', (conversation_id,)).fetchone()
    
    if not conv:
        db.close()
        return jsonify({
            'success': False,
            'error': 'Conversation not found'
        }), 404
    
    # Get messages
    messages = db.execute('''
        SELECT role, stage, content, created_at
        FROM avatar_messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
    ''', (conversation_id,)).fetchall()
    
    db.close()
    
    return jsonify({
        'success': True,
        'conversation_id': conversation_id,
        'messages': [
            {
                'role': m['role'],
                'stage': m['stage'],
                'content': m['content'],
                'timestamp': m['created_at']
            } for m in messages
        ],
        'status': conv['status'],
        'visitor_info': {
            'name': conv['visitor_name'],
            'company': conv['visitor_company'],
            'email': conv['visitor_email'],
            'phone': conv['visitor_phone']
        } if conv['visitor_name'] else None
    })


# =============================================================================
# LEAD MANAGEMENT ENDPOINTS
# =============================================================================

@avatar_bp.route('/api/avatar/leads', methods=['GET'])
def get_leads():
    """
    Get all captured leads from avatar consultations
    
    Query params:
        status: Filter by status (active, lead_captured, converted)
        limit: Max results (default 50)
    
    Returns:
        {
            'success': true,
            'leads': [
                {
                    'conversation_id': 'uuid',
                    'visitor_name': 'John Doe',
                    'visitor_company': 'ABC Manufacturing',
                    'visitor_email': 'john@abc.com',
                    'visitor_phone': '555-1234',
                    'started_at': '...',
                    'completed_at': '...',
                    'status': 'lead_captured'
                }
            ],
            'total': 25
        }
    """
    status = request.args.get('status')
    limit = int(request.args.get('limit', 50))
    
    db = get_db()
    
    if status:
        rows = db.execute('''
            SELECT * FROM avatar_conversations
            WHERE status = ? AND visitor_email IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT ?
        ''', (status, limit)).fetchall()
    else:
        rows = db.execute('''
            SELECT * FROM avatar_conversations
            WHERE visitor_email IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT ?
        ''', (limit,)).fetchall()
    
    db.close()
    
    leads = []
    for row in rows:
        leads.append({
            'conversation_id': row['conversation_id'],
            'visitor_name': row['visitor_name'],
            'visitor_company': row['visitor_company'],
            'visitor_email': row['visitor_email'],
            'visitor_phone': row['visitor_phone'],
            'started_at': row['started_at'],
            'completed_at': row['completed_at'],
            'status': row['status']
        })
    
    return jsonify({
        'success': True,
        'leads': leads,
        'total': len(leads)
    })


# =============================================================================
# STATISTICS & ANALYTICS
# =============================================================================

@avatar_bp.route('/api/avatar/stats', methods=['GET'])
def get_stats():
    """
    Get avatar consultation statistics
    
    Returns:
        {
            'success': true,
            'stats': {
                'total_conversations': 150,
                'active_conversations': 25,
                'leads_captured': 85,
                'conversion_rate': 0.57,
                'avg_messages_per_conversation': 6.2,
                'today': 8,
                'this_week': 42,
                'this_month': 150
            }
        }
    """
    db = get_db()
    
    # Total conversations
    total = db.execute('SELECT COUNT(*) as count FROM avatar_conversations').fetchone()['count']
    
    # Active conversations
    active = db.execute(
        "SELECT COUNT(*) as count FROM avatar_conversations WHERE status = 'active'"
    ).fetchone()['count']
    
    # Leads captured
    leads = db.execute(
        "SELECT COUNT(*) as count FROM avatar_conversations WHERE status = 'lead_captured'"
    ).fetchone()['count']
    
    # Conversion rate
    conversion_rate = leads / total if total > 0 else 0
    
    # Average messages
    avg_messages = db.execute('''
        SELECT AVG(message_count) as avg FROM (
            SELECT conversation_id, COUNT(*) as message_count
            FROM avatar_messages
            GROUP BY conversation_id
        )
    ''').fetchone()['avg'] or 0
    
    # Today
    today = db.execute('''
        SELECT COUNT(*) as count FROM avatar_conversations
        WHERE DATE(started_at) = DATE('now')
    ''').fetchone()['count']
    
    # This week
    this_week = db.execute('''
        SELECT COUNT(*) as count FROM avatar_conversations
        WHERE started_at >= datetime('now', '-7 days')
    ''').fetchone()['count']
    
    # This month
    this_month = db.execute('''
        SELECT COUNT(*) as count FROM avatar_conversations
        WHERE started_at >= datetime('now', 'start of month')
    ''').fetchone()['count']
    
    db.close()
    
    return jsonify({
        'success': True,
        'stats': {
            'total_conversations': total,
            'active_conversations': active,
            'leads_captured': leads,
            'conversion_rate': round(conversion_rate, 3),
            'avg_messages_per_conversation': round(avg_messages, 1),
            'today': today,
            'this_week': this_week,
            'this_month': this_month
        }
    })


# =============================================================================
# HEALTH CHECK
# =============================================================================

@avatar_bp.route('/api/avatar/status', methods=['GET'])
def avatar_status():
    """
    Check if avatar consultation system is available
    
    Returns:
        {
            'available': true,
            'ai_available': true,
            'avatars': ['david', 'sarah']
        }
    """
    ai_available = False
    
    try:
        from orchestration.ai_clients import call_claude_opus
        ai_available = True
    except:
        pass
    
    return jsonify({
        'available': AVATAR_AVAILABLE,
        'ai_available': ai_available,
        'avatars': ['david', 'sarah']
    })


# I did no harm and this file is not truncated
