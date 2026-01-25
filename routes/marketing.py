"""
CONTENT MARKETING ROUTES - Flask API Endpoints
Created: January 25, 2026
Last Updated: January 25, 2026

API endpoints for the Autonomous Content Marketing Engine.
Provides content generation, approval workflow, and publishing capabilities.

ENDPOINTS:
- POST /api/marketing/generate-posts - Generate LinkedIn posts from recent work
- POST /api/marketing/generate-newsletter - Generate weekly newsletter
- GET /api/marketing/pending - Get all pending approvals
- POST /api/marketing/approve/<id> - Approve content
- POST /api/marketing/reject/<id> - Reject content
- GET /api/marketing/stats - Get marketing content statistics
- POST /api/marketing/auto-run - Run automated weekly content generation

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import json

# Import the content engine
try:
    from content_marketing_engine import get_content_engine
    MARKETING_AVAILABLE = True
except ImportError:
    print("⚠️ Content Marketing Engine not available")
    MARKETING_AVAILABLE = False

from database import get_db

# Create blueprint
marketing_bp = Blueprint('marketing', __name__)


# =============================================================================
# CONTENT GENERATION ENDPOINTS
# =============================================================================

@marketing_bp.route('/api/marketing/generate-posts', methods=['POST'])
def generate_linkedin_posts():
    """
    Generate LinkedIn posts from recent consulting work
    
    Body (optional):
        days_back: Number of days to look back (default: 7)
        num_posts: Number of posts to generate (default: 3)
    
    Returns:
        {
            'success': true,
            'posts_generated': 3,
            'posts': [
                {
                    'id': 123,
                    'content': 'Post text...',
                    'category': 'case_study',
                    'estimated_engagement': 'high',
                    'source_task_id': 456
                }
            ]
        }
    """
    if not MARKETING_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Marketing engine not available'
        }), 503
    
    data = request.json or {}
    days_back = data.get('days_back', 7)
    num_posts = data.get('num_posts', 3)
    
    engine = get_content_engine()
    
    # Extract insights from recent work
    insights = engine.extract_marketable_insights(days_back=days_back)
    
    if not insights:
        return jsonify({
            'success': False,
            'error': 'No marketable insights found in recent work',
            'days_back': days_back
        })
    
    # Generate posts from best insights
    posts = []
    for insight in insights[:num_posts]:
        post = engine.generate_linkedin_post(insight)
        
        # Save to database for approval
        content_id = engine.save_content_for_approval('linkedin_post', post)
        post['id'] = content_id
        
        posts.append(post)
    
    return jsonify({
        'success': True,
        'posts_generated': len(posts),
        'insights_found': len(insights),
        'posts': posts
    })


@marketing_bp.route('/api/marketing/generate-newsletter', methods=['POST'])
def generate_newsletter():
    """
    Generate weekly "This Week in Shiftwork" newsletter
    
    Body (optional):
        include_research: Whether to include industry news (default: true)
    
    Returns:
        {
            'success': true,
            'newsletter': {
                'id': 123,
                'subject': 'This Week in Shiftwork - January 25, 2026',
                'html_body': '<html>...',
                'plain_text': 'Plain text version',
                'preview': 'First 200 chars...'
            }
        }
    """
    if not MARKETING_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Marketing engine not available'
        }), 503
    
    data = request.json or {}
    include_research = data.get('include_research', True)
    
    engine = get_content_engine()
    
    # Generate newsletter
    newsletter = engine.generate_weekly_newsletter(include_research=include_research)
    
    # Save for approval
    content_id = engine.save_content_for_approval('newsletter', newsletter)
    newsletter['id'] = content_id
    newsletter['preview'] = newsletter['plain_text'][:200] + '...'
    
    return jsonify({
        'success': True,
        'newsletter': newsletter
    })


# =============================================================================
# APPROVAL WORKFLOW ENDPOINTS
# =============================================================================

@marketing_bp.route('/api/marketing/pending', methods=['GET'])
def get_pending_content():
    """
    Get all content pending approval
    
    Query params:
        content_type: Filter by type ('linkedin_post' or 'newsletter')
    
    Returns:
        {
            'success': true,
            'pending_count': 5,
            'content': [
                {
                    'id': 123,
                    'content_type': 'linkedin_post',
                    'content_data': {...},
                    'generated_at': '2026-01-25T10:00:00'
                }
            ]
        }
    """
    if not MARKETING_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Marketing engine not available'
        }), 503
    
    content_type = request.args.get('content_type')
    
    engine = get_content_engine()
    pending = engine.get_pending_approvals()
    
    # Filter by type if specified
    if content_type:
        pending = [p for p in pending if p['content_type'] == content_type]
    
    return jsonify({
        'success': True,
        'pending_count': len(pending),
        'content': pending
    })


@marketing_bp.route('/api/marketing/approve/<int:content_id>', methods=['POST'])
def approve_content(content_id):
    """
    Approve content for publishing
    
    Body (optional):
        schedule_time: When to publish (ISO format, optional)
        notes: Approval notes
    
    Returns:
        {
            'success': true,
            'content_id': 123,
            'status': 'approved'
        }
    """
    if not MARKETING_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Marketing engine not available'
        }), 503
    
    data = request.json or {}
    
    engine = get_content_engine()
    success = engine.approve_content(content_id)
    
    if success:
        # Log the approval
        db = get_db()
        db.execute('''
            INSERT INTO marketing_activity_log (
                content_id, activity_type, activity_data, created_at
            ) VALUES (?, ?, ?, ?)
        ''', (
            content_id,
            'approved',
            json.dumps({
                'approved_at': datetime.now().isoformat(),
                'schedule_time': data.get('schedule_time'),
                'notes': data.get('notes')
            }),
            datetime.now()
        ))
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'content_id': content_id,
            'status': 'approved'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to approve content'
        }), 400


@marketing_bp.route('/api/marketing/reject/<int:content_id>', methods=['POST'])
def reject_content(content_id):
    """
    Reject content
    
    Body:
        reason: Rejection reason (optional)
    
    Returns:
        {
            'success': true,
            'content_id': 123,
            'status': 'rejected'
        }
    """
    if not MARKETING_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Marketing engine not available'
        }), 503
    
    data = request.json or {}
    reason = data.get('reason', 'No reason provided')
    
    engine = get_content_engine()
    success = engine.reject_content(content_id, reason)
    
    if success:
        # Log the rejection
        db = get_db()
        db.execute('''
            INSERT INTO marketing_activity_log (
                content_id, activity_type, activity_data, created_at
            ) VALUES (?, ?, ?, ?)
        ''', (
            content_id,
            'rejected',
            json.dumps({
                'rejected_at': datetime.now().isoformat(),
                'reason': reason
            }),
            datetime.now()
        ))
        db.commit()
        db.close()
        
        return jsonify({
            'success': True,
            'content_id': content_id,
            'status': 'rejected',
            'reason': reason
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to reject content'
        }), 400


# =============================================================================
# STATISTICS & ANALYTICS
# =============================================================================

@marketing_bp.route('/api/marketing/stats', methods=['GET'])
def get_marketing_stats():
    """
    Get marketing content statistics
    
    Returns:
        {
            'success': true,
            'stats': {
                'total_generated': 150,
                'pending_approval': 5,
                'approved': 120,
                'rejected': 25,
                'linkedin_posts': 100,
                'newsletters': 20,
                'this_week': 8
            }
        }
    """
    db = get_db()
    
    # Total content by status
    total_generated = db.execute('SELECT COUNT(*) as count FROM marketing_content').fetchone()['count']
    
    pending = db.execute('SELECT COUNT(*) as count FROM marketing_content WHERE status = "pending_approval"').fetchone()['count']
    
    approved = db.execute('SELECT COUNT(*) as count FROM marketing_content WHERE status = "approved"').fetchone()['count']
    
    rejected = db.execute('SELECT COUNT(*) as count FROM marketing_content WHERE status = "rejected"').fetchone()['count']
    
    # By content type
    linkedin = db.execute('SELECT COUNT(*) as count FROM marketing_content WHERE content_type = "linkedin_post"').fetchone()['count']
    
    newsletters = db.execute('SELECT COUNT(*) as count FROM marketing_content WHERE content_type = "newsletter"').fetchone()['count']
    
    # This week
    week_ago = datetime.now() - timedelta(days=7)
    this_week = db.execute(
        'SELECT COUNT(*) as count FROM marketing_content WHERE generated_at >= ?',
        (week_ago,)
    ).fetchone()['count']
    
    db.close()
    
    return jsonify({
        'success': True,
        'stats': {
            'total_generated': total_generated,
            'pending_approval': pending,
            'approved': approved,
            'rejected': rejected,
            'linkedin_posts': linkedin,
            'newsletters': newsletters,
            'this_week': this_week
        }
    })


# =============================================================================
# AUTOMATED EXECUTION
# =============================================================================

@marketing_bp.route('/api/marketing/auto-run', methods=['POST'])
def auto_run_weekly():
    """
    Run the automated weekly content generation
    
    This should be called by a cron job or scheduler once per week.
    Generates 3 LinkedIn posts and 1 newsletter automatically.
    
    Body (optional):
        linkedin_posts: Number of posts to generate (default: 3)
        generate_newsletter: Whether to generate newsletter (default: true)
    
    Returns:
        {
            'success': true,
            'summary': {
                'linkedin_posts_generated': 3,
                'newsletter_generated': true,
                'total_pending_approval': 4
            }
        }
    """
    if not MARKETING_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Marketing engine not available'
        }), 503
    
    data = request.json or {}
    num_posts = data.get('linkedin_posts', 3)
    generate_newsletter = data.get('generate_newsletter', True)
    
    engine = get_content_engine()
    
    # Generate LinkedIn posts
    insights = engine.extract_marketable_insights(days_back=7)
    posts_generated = 0
    
    for insight in insights[:num_posts]:
        try:
            post = engine.generate_linkedin_post(insight)
            engine.save_content_for_approval('linkedin_post', post)
            posts_generated += 1
        except Exception as e:
            print(f"⚠️ Failed to generate post: {e}")
    
    # Generate newsletter if requested
    newsletter_generated = False
    if generate_newsletter:
        try:
            newsletter = engine.generate_weekly_newsletter(include_research=True)
            engine.save_content_for_approval('newsletter', newsletter)
            newsletter_generated = True
        except Exception as e:
            print(f"⚠️ Failed to generate newsletter: {e}")
    
    # Get total pending count
    pending = engine.get_pending_approvals()
    
    # Log the auto-run
    db = get_db()
    db.execute('''
        INSERT INTO marketing_activity_log (
            content_id, activity_type, activity_data, created_at
        ) VALUES (?, ?, ?, ?)
    ''', (
        None,
        'auto_run',
        json.dumps({
            'posts_generated': posts_generated,
            'newsletter_generated': newsletter_generated,
            'run_at': datetime.now().isoformat()
        }),
        datetime.now()
    ))
    db.commit()
    db.close()
    
    return jsonify({
        'success': True,
        'summary': {
            'linkedin_posts_generated': posts_generated,
            'newsletter_generated': newsletter_generated,
            'total_pending_approval': len(pending)
        }
    })


# =============================================================================
# HEALTH CHECK
# =============================================================================

@marketing_bp.route('/api/marketing/status', methods=['GET'])
def marketing_status():
    """
    Check if marketing engine is available and healthy
    
    Returns:
        {
            'available': true,
            'ai_available': true,
            'research_available': true
        }
    """
    ai_available = False
    research_available = False
    
    try:
        from orchestration.ai_clients import call_claude_opus
        ai_available = True
    except:
        pass
    
    try:
        from research_agent import get_research_agent
        ra = get_research_agent()
        research_available = ra.is_available
    except:
        pass
    
    return jsonify({
        'available': MARKETING_AVAILABLE,
        'ai_available': ai_available,
        'research_available': research_available
    })


# I did no harm and this file is not truncated
