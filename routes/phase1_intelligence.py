"""
Phase 1 Intelligence API Endpoints
Created: February 5, 2026

API routes for:
1. Voice Learning Integration
2. Proactive Curiosity Engine  
3. Pattern Recognition Dashboard

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify
from voice_learning_integration import get_voice_learning_integration
from proactive_curiosity_engine import get_curiosity_engine
from pattern_recognition_dashboard import get_pattern_dashboard

# Create blueprint
intelligence_bp = Blueprint('intelligence', __name__, url_prefix='/api/intelligence')


# =============================================================================
# VOICE LEARNING ENDPOINTS
# =============================================================================

@intelligence_bp.route('/voice/learn', methods=['POST'])
def learn_from_voice():
    """
    Learn from a voice conversation exchange.
    
    Request body:
    {
        "user_transcript": "...",
        "ai_transcript": "...",
        "voice_metadata": {
            "duration_seconds": 45,
            "wake_word_used": true
        }
    }
    
    Returns:
    {
        "success": true,
        "learned": true,
        "voice_context": {
            "tone": "enthusiastic",
            "urgency_level": "normal"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data.get('user_transcript') or not data.get('ai_transcript'):
            return jsonify({
                'success': False,
                'error': 'Both user_transcript and ai_transcript required'
            }), 400
        
        voice_integration = get_voice_learning_integration()
        
        learned = voice_integration.learn_from_voice_exchange(
            data['user_transcript'],
            data['ai_transcript'],
            data.get('voice_metadata', {})
        )
        
        return jsonify({
            'success': True,
            'learned': learned
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@intelligence_bp.route('/voice/session-summary', methods=['POST'])
def voice_session_summary():
    """
    Extract lessons from a complete voice session.
    
    Request body:
    {
        "messages": [
            {"user": "...", "assistant": "..."},
            {"user": "...", "assistant": "..."}
        ],
        "session_metadata": {
            "duration_minutes": 15,
            "wake_word_count": 3
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data.get('messages'):
            return jsonify({
                'success': False,
                'error': 'messages array required'
            }), 400
        
        voice_integration = get_voice_learning_integration()
        
        summary = voice_integration.extract_voice_session_lessons(
            data['messages'],
            data.get('session_metadata', {})
        )
        
        return jsonify({
            'success': True,
            'summary': summary
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# PROACTIVE CURIOSITY ENDPOINTS
# =============================================================================

@intelligence_bp.route('/curiosity/check', methods=['POST'])
def check_curiosity():
    """
    Check if AI should ask a curious follow-up question.
    
    Request body:
    {
        "conversation_id": "abc123",
        "user_request": "Design a DuPont schedule for 200 employees",
        "ai_response": "Here's the schedule...",
        "task_completed": true
    }
    
    Returns:
    {
        "should_ask": true,
        "question": "How did the team react to this schedule when you've used it before?",
        "reason": "triggered_by_after_schedule_design"
    }
    """
    try:
        data = request.get_json()
        
        if not data.get('conversation_id'):
            return jsonify({
                'success': False,
                'error': 'conversation_id required'
            }), 400
        
        curiosity_engine = get_curiosity_engine()
        
        result = curiosity_engine.should_be_curious(
            data['conversation_id'],
            {
                'user_request': data.get('user_request', ''),
                'ai_response': data.get('ai_response', ''),
                'task_completed': data.get('task_completed', False)
            }
        )
        
        return jsonify({
            'success': True,
            **result
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@intelligence_bp.route('/curiosity/stats', methods=['GET'])
def curiosity_stats():
    """Get statistics about curiosity behavior"""
    try:
        curiosity_engine = get_curiosity_engine()
        stats = curiosity_engine.get_curiosity_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# PATTERN RECOGNITION DASHBOARD ENDPOINTS
# =============================================================================

@intelligence_bp.route('/patterns/dashboard', methods=['GET'])
def pattern_dashboard():
    """
    Get comprehensive pattern recognition dashboard.
    
    Query params:
    - days_back: Number of days to analyze (default: 90)
    
    Returns:
    {
        "success": true,
        "patterns": {
            "schedule_preferences": {...},
            "industry_focus": {...},
            "time_patterns": {...},
            "communication_style": {...},
            "summary": {
                "total_patterns_found": 15,
                "high_confidence_patterns": 8,
                "key_insights": [...]
            }
        }
    }
    """
    try:
        days_back = request.args.get('days_back', 90, type=int)
        
        dashboard = get_pattern_dashboard()
        patterns = dashboard.get_pattern_dashboard(days_back)
        
        return jsonify({
            'success': True,
            'patterns': patterns
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@intelligence_bp.route('/patterns/schedule-preferences', methods=['GET'])
def schedule_preferences():
    """Get just schedule preferences"""
    try:
        days_back = request.args.get('days_back', 90, type=int)
        
        dashboard = get_pattern_dashboard()
        patterns = dashboard._analyze_schedule_patterns(days_back)
        
        return jsonify({
            'success': True,
            **patterns
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@intelligence_bp.route('/patterns/industry-focus', methods=['GET'])
def industry_focus():
    """Get industry focus patterns"""
    try:
        days_back = request.args.get('days_back', 90, type=int)
        
        dashboard = get_pattern_dashboard()
        patterns = dashboard._analyze_industry_patterns(days_back)
        
        return jsonify({
            'success': True,
            **patterns
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@intelligence_bp.route('/patterns/time-patterns', methods=['GET'])
def time_patterns():
    """Get time-based behavior patterns"""
    try:
        days_back = request.args.get('days_back', 90, type=int)
        
        dashboard = get_pattern_dashboard()
        patterns = dashboard._analyze_time_patterns(days_back)
        
        return jsonify({
            'success': True,
            **patterns
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# I did no harm and this file is not truncated
