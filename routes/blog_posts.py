"""
BLOG POSTS ROUTES - Flask API Endpoints
Shiftwork Solutions LLC

PURPOSE:
    API endpoints for the Blog Post Generator feature.
    Generates conversational, SEO and AI-search optimized blog posts for
    the Shiftwork Solutions LLC website. Same audience focus and SEO
    discipline as the Case Study Generator but in a blog/editorial style.

ENDPOINTS:
    GET    /api/blog-posts/status           - Health check and topic list
    POST   /api/blog-posts/generate         - Generate a new blog post
    GET    /api/blog-posts/download/<id>    - Download blog post as Word doc
    GET    /api/blog-posts/list             - List all saved blog posts
    GET    /api/blog-posts/<id>             - Get a single blog post
    DELETE /api/blog-posts/<id>             - Delete a blog post

INPUTS FOR GENERATE:
    topic         : Topic key from BLOG_TOPICS dict (e.g. 'workforce_resistance')
    custom_topic  : Human-readable topic name (required if topic == 'other')
    angle         : Optional — additional context, focus, or angle from Jim

CHANGE LOG:
    February 23, 2026 - Initial creation. Six endpoints matching the Case
                        Study Generator pattern. Blog posts use conversational
                        tone vs case study formality. 12 topic categories + Other.
                        Word download. Library with View / Word / Delete.

AUTHOR: Jim @ Shiftwork Solutions LLC
LAST UPDATED: February 23, 2026
"""

from flask import Blueprint, request, jsonify, send_file
import io
from datetime import datetime

# ============================================================================
# BLUEPRINT
# ============================================================================
blog_posts_bp = Blueprint('blog_posts', __name__)

# ============================================================================
# IMPORT GENERATOR
# ============================================================================
try:
    from blog_post_generator import (
        generate_blog_post,
        generate_blog_post_docx,
        save_blog_post_to_db,
        get_all_blog_posts,
        get_blog_post_by_id,
        delete_blog_post,
        init_blog_posts_table,
        BLOG_TOPICS
    )
    BLOG_POSTS_AVAILABLE = True
    
    # Initialize table (safe - won't crash if already exists)
    try:
        init_blog_posts_table()
    except Exception as table_error:
        print(f"[BlogPosts] Table init warning (may already exist): {table_error}")
    
    print("[BlogPosts] Blog Post Generator loaded successfully")
except Exception as e:
    print(f"[BlogPosts] WARNING - Failed to load Blog Post Generator: {e}")
    import traceback
    print(f"[BlogPosts] Traceback: {traceback.format_exc()}")
    BLOG_POSTS_AVAILABLE = False


# ============================================================================
# STATUS CHECK
# ============================================================================

@blog_posts_bp.route('/api/blog-posts/status', methods=['GET'])
def blog_posts_status():
    """Health check for blog post generator. Returns available topics."""
    topics_list = []
    if BLOG_POSTS_AVAILABLE:
        for key, data in BLOG_TOPICS.items():
            topics_list.append({
                'key': key,
                'display': data['display'],
                'primary_keyword': data['primary_keyword']
            })

    return jsonify({
        'available': BLOG_POSTS_AVAILABLE,
        'topics': topics_list,
        'features': [
            'ai_generation',
            'seo_optimized',
            'employee_engagement_narrative',
            'conversational_tone',
            'word_doc_download',
            'saved_library'
        ]
    })


# ============================================================================
# GENERATE
# ============================================================================

@blog_posts_bp.route('/api/blog-posts/generate', methods=['POST'])
def generate():
    """
    Generate a new SEO and AI-search optimized blog post.

    Body (JSON):
        topic         : string  - topic key from BLOG_TOPICS
        custom_topic  : string  - required if topic == 'other'
        angle         : string  - optional additional context or angle

    Returns:
        {
            'success': true,
            'id': 123,
            'title': 'Blog Post Title',
            'topic': 'workforce_resistance',
            'topic_display': 'Workforce Resistance to Schedule Change',
            'content': '# Markdown content...',
            'word_count': 850,
            'generated_at': '2026-02-23T...'
        }
    """
    if not BLOG_POSTS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Blog Post Generator not available'
        }), 503

    data = request.json or {}
    topic = data.get('topic', '').strip()
    custom_topic = data.get('custom_topic', '').strip()
    angle = data.get('angle', '').strip()

    # Validate inputs
    errors = []
    if not topic:
        errors.append('Topic is required')
    elif topic not in BLOG_TOPICS:
        errors.append(
            f'Unknown topic: {topic}. '
            f'Valid options: {list(BLOG_TOPICS.keys())}'
        )

    # If topic is 'other', custom_topic is required
    if topic == 'other' and not custom_topic:
        errors.append('Please describe your topic in the "Other" field')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    print(f"[BlogPosts] Generating blog post: topic={topic}")

    result = generate_blog_post(
        topic=topic,
        custom_topic=custom_topic,
        angle=angle
    )

    if not result['success']:
        return jsonify({
            'success': False,
            'error': result.get('error', 'Generation failed'),
            'traceback': result.get('traceback', '')
        }), 500

    print(f"[BlogPosts] Generated: ID={result['id']}, title={result['title']}")

    return jsonify({
        'success': True,
        'id': result['id'],
        'title': result['title'],
        'topic': result['topic'],
        'topic_display': result['topic_display'],
        'content': result['content'],
        'word_count': result['word_count'],
        'generated_at': datetime.now().isoformat()
    })


# ============================================================================
# DOWNLOAD AS WORD DOC
# ============================================================================

@blog_posts_bp.route('/api/blog-posts/download/<int:post_id>', methods=['GET'])
def download(post_id):
    """
    Download a saved blog post as a Word document (.docx).
    Returns a file attachment.
    Styled consistently with Case Study Generator DOCX output.
    """
    if not BLOG_POSTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    post = get_blog_post_by_id(post_id)
    if not post:
        return jsonify({'success': False, 'error': 'Blog post not found'}), 404

    try:
        docx_bytes = generate_blog_post_docx(
            post_content=post['content'],
            title=post['title'],
            topic_display=post['topic_display']
        )

        # Build clean filename from title
        safe_title = ''.join(
            c for c in post['title'] if c.isalnum() or c in (' ', '-', '_')
        )
        safe_title = safe_title[:60].strip().replace(' ', '_')
        filename = f"BlogPost_{safe_title}_{datetime.now().strftime('%Y%m%d')}.docx"

        return send_file(
            io.BytesIO(docx_bytes),
            mimetype=(
                'application/vnd.openxmlformats-officedocument'
                '.wordprocessingml.document'
            ),
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        import traceback
        print(f"[BlogPosts] Download failed: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# LIST ALL
# ============================================================================

@blog_posts_bp.route('/api/blog-posts/list', methods=['GET'])
def list_posts():
    """
    List all saved blog posts, newest first.

    Returns:
        {
            'success': true,
            'count': 5,
            'blog_posts': [...]
        }
    """
    if not BLOG_POSTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    posts = get_all_blog_posts()

    return jsonify({
        'success': True,
        'count': len(posts),
        'blog_posts': posts
    })


# ============================================================================
# GET SINGLE
# ============================================================================

@blog_posts_bp.route('/api/blog-posts/<int:post_id>', methods=['GET'])
def get_post(post_id):
    """
    Get a single blog post by ID. Returns full content including markdown.
    """
    if not BLOG_POSTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    post = get_blog_post_by_id(post_id)
    if not post:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    return jsonify({'success': True, 'blog_post': post})


# ============================================================================
# DELETE
# ============================================================================

@blog_posts_bp.route('/api/blog-posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    """Delete a blog post by ID."""
    if not BLOG_POSTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    post = get_blog_post_by_id(post_id)
    if not post:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    delete_blog_post(post_id)
    return jsonify({'success': True, 'deleted_id': post_id})

# I did no harm and this file is not truncated
