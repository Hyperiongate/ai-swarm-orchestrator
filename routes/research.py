"""
Research Agent API Routes
Created: January 23, 2026
Last Updated: January 23, 2026

PURPOSE:
API endpoints for the Research Agent functionality.
Allows frontend to trigger searches and view results.

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

from flask import Blueprint, request, jsonify
from datetime import datetime

research_bp = Blueprint('research', __name__)

# Import research agent
RESEARCH_AVAILABLE = False
research_agent = None
try:
    from research_agent import get_research_agent
    research_agent = get_research_agent()
    RESEARCH_AVAILABLE = research_agent.is_available
    print("✅ Research Agent routes loaded")
except ImportError:
    print("ℹ️  Research Agent not available")
except Exception as e:
    print(f"⚠️  Research Agent error: {e}")


@research_bp.route('/api/research/status', methods=['GET'])
def get_research_status():
    """Get research agent status"""
    if not research_agent:
        return jsonify({
            'success': True,
            'available': False,
            'message': 'Research Agent not initialized'
        })
    
    status = research_agent.get_status()
    return jsonify({
        'success': True,
        **status
    })


@research_bp.route('/api/research/search', methods=['POST'])
def perform_search():
    """
    Perform a general research search.
    
    Body:
        query: Search query (required)
        search_depth: "basic" or "advanced" (optional, default: basic)
        max_results: 1-10 (optional, default: 5)
    """
    if not RESEARCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Research Agent not available. Configure TAVILY_API_KEY.'
        }), 503
    
    data = request.json or {}
    query = data.get('query')
    
    if not query:
        return jsonify({'success': False, 'error': 'Query is required'}), 400
    
    search_depth = data.get('search_depth', 'basic')
    max_results = data.get('max_results', 5)
    
    result = research_agent.search(
        query=query,
        search_depth=search_depth,
        max_results=max_results
    )
    
    return jsonify(result)


@research_bp.route('/api/research/topic', methods=['POST'])
def research_topic():
    """
    Research a specific topic with shiftwork context.
    
    Body:
        topic: Topic to research (required)
        context: Why we need this info (optional)
    """
    if not RESEARCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Research Agent not available. Configure TAVILY_API_KEY.'
        }), 503
    
    data = request.json or {}
    topic = data.get('topic')
    context = data.get('context')
    
    if not topic:
        return jsonify({'success': False, 'error': 'Topic is required'}), 400
    
    result = research_agent.research_topic(topic, context)
    
    return jsonify(result)


@research_bp.route('/api/research/industry-news', methods=['GET'])
def get_industry_news():
    """Get latest industry news about shift work and scheduling"""
    if not RESEARCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Research Agent not available'
        }), 503
    
    topic = request.args.get('topic')
    days_back = request.args.get('days', 7, type=int)
    
    result = research_agent.search_industry_news(
        specific_topic=topic,
        days_back=days_back
    )
    
    return jsonify(result)


@research_bp.route('/api/research/regulations', methods=['GET'])
def get_regulations():
    """Get regulatory updates affecting shift operations"""
    if not RESEARCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Research Agent not available'
        }), 503
    
    topic = request.args.get('topic')
    
    result = research_agent.search_regulations(topic=topic)
    
    return jsonify(result)


@research_bp.route('/api/research/studies', methods=['GET'])
def get_research_studies():
    """Get academic and industry research on shift work"""
    if not RESEARCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Research Agent not available'
        }), 503
    
    topic = request.args.get('topic')
    
    result = research_agent.search_research_studies(topic=topic)
    
    return jsonify(result)


@research_bp.route('/api/research/competitors', methods=['GET'])
def get_competitors():
    """Search for competitor activity and products"""
    if not RESEARCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Research Agent not available'
        }), 503
    
    result = research_agent.search_competitors()
    
    return jsonify(result)


@research_bp.route('/api/research/leads', methods=['GET'])
def find_leads():
    """Search for potential clients discussing scheduling challenges"""
    if not RESEARCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Research Agent not available'
        }), 503
    
    industry = request.args.get('industry')
    
    result = research_agent.search_potential_leads(industry=industry)
    
    return jsonify(result)


@research_bp.route('/api/research/briefing', methods=['GET'])
def get_daily_briefing():
    """
    Generate or retrieve today's briefing.
    This is the proactive intelligence feature.
    """
    if not RESEARCH_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Research Agent not available'
        }), 503
    
    # Check if we want to force a fresh briefing
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    if force_refresh:
        briefing = research_agent.get_daily_briefing()
    else:
        # Try to get today's briefing from database first
        from database import get_db
        db = get_db()
        today = datetime.now().strftime('%Y-%m-%d')
        
        existing = db.execute('''
            SELECT briefing_data FROM research_briefings 
            WHERE date(created_at) = ?
            ORDER BY created_at DESC LIMIT 1
        ''', (today,)).fetchone()
        
        db.close()
        
        if existing:
            import json
            briefing = json.loads(existing['briefing_data'])
        else:
            briefing = research_agent.get_daily_briefing()
    
    return jsonify({
        'success': True,
        'briefing': briefing
    })


# I did no harm and this file is not truncated
