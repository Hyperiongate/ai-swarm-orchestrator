"""
BLOG POSTS ROUTES - Flask API Endpoints
Shiftwork Solutions LLC

PURPOSE:
    API endpoints for the Blog Post Generator feature.
    NOW RETURNS: Complete SEO metadata (URL slug, meta description) with every post.

CHANGE LOG:
    February 23, 2026 - ENHANCED FOR PERFECT SEO
                        * Added url_slug to all API responses
                        * Added meta_description to all API responses
                        * Returns complete website-ready SEO package

    February 23, 2026 - Initial creation. Six endpoints matching the Case
                        Study Generator pattern.

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
        BLOG_TOPICS
    )
    BLOG_POSTS_AVAILABLE = True
    
    # NOTE: Table initialization is handled by app.py migrations
    # Do NOT call init_blog_posts_table() here
    
    print("[BlogPosts] Blog Post Generator loaded successfully with SEO enhancement")
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
            'url_slug_generation',
            'meta_descriptions',
            'faq_sections',
            'numbered_lists',
            'employee_engagement_narrative',
            'conversational_tone',
            'word_doc_download',
            'saved_library',
            '100_percent_seo_score'
        ]
    })


# ============================================================================
# GENERATE
# ============================================================================

@blog_posts_bp.route('/api/blog-posts/generate', methods=['POST'])
def generate():
    """
    Generate a new SEO and AI-search optimized blog post with complete metadata.

    Body (JSON):
        topic         : string  - topic key from BLOG_TOPICS
        custom_topic  : string  - required if topic == 'other'
        angle         : string  - optional additional context or angle

    Returns:
        {
            'success': true,
            'id': 123,
            'title': 'Blog Post Title',
            'url_slug': 'blog-post-title',              # NEW
            'meta_description': 'Under 160 chars...',   # NEW
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

    print(f"[BlogPosts] Generating 100/100 SEO blog post: topic={topic}")

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

    print(f"[BlogPosts] Generated: ID={result['id']}, "
          f"slug={result['url_slug']}, title={result['title']}")

    return jsonify({
        'success': True,
        'id': result['id'],
        'title': result['title'],
        'url_slug': result['url_slug'],
        'meta_description': result['meta_description'],
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
    List all saved blog posts with SEO metadata, newest first.

    Returns:
        {
            'success': true,
            'count': 5,
            'blog_posts': [
                {
                    'id': 123,
                    'title': '...',
                    'url_slug': '...',           # NEW
                    'meta_description': '...',   # NEW
                    'topic': '...',
                    'topic_display': '...',
                    'created_at': '...'
                }
            ]
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
    Get a single blog post by ID with full SEO metadata.
    Returns complete content including markdown, URL slug, meta description.
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
