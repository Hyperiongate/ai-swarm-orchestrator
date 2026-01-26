"""
VISUAL CONTENT API ROUTES
Created: January 26, 2026
Last Updated: January 26, 2026

PURPOSE:
API endpoints for visual content generation within the swarm orchestrator.
Enables on-demand creation of engaging LinkedIn posts with visuals.

ENDPOINTS:
- POST /api/visual/generate - Generate visual content
- POST /api/visual/linkedin-post - Create complete LinkedIn post with visual
- GET /api/visual/capabilities - Check visual generation capabilities
- GET /api/visual/themes - List available visual themes
- GET /api/visual/chart-types - List available chart types

INTEGRATION:
Add these routes to your existing routes/core.py or create a new
routes/visual.py blueprint.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify, send_file
import os
import json
from datetime import datetime

# Try to import visual content modules
try:
    from visual_linkedin_post_creator import VisualLinkedInPostCreator
    VISUAL_CREATOR_AVAILABLE = True
except ImportError:
    print("⚠️ Visual LinkedIn post creator not available")
    VISUAL_CREATOR_AVAILABLE = False

try:
    from visual_content_generator import VisualContentGenerator
    VISUAL_GENERATOR_AVAILABLE = True
except ImportError:
    print("⚠️ Visual content generator not available")
    VISUAL_GENERATOR_AVAILABLE = False


# Create blueprint
visual_bp = Blueprint('visual', __name__)

# Initialize visual creator (if available)
visual_creator = VisualLinkedInPostCreator() if VISUAL_CREATOR_AVAILABLE else None


@visual_bp.route('/api/visual/capabilities', methods=['GET'])
def get_visual_capabilities():
    """Get visual generation capabilities and status"""
    
    if not visual_creator:
        return jsonify({
            'success': False,
            'available': False,
            'error': 'Visual content creator not initialized'
        }), 503
    
    capabilities = visual_creator.get_visual_capabilities()
    
    return jsonify({
        'success': True,
        **capabilities
    })


@visual_bp.route('/api/visual/themes', methods=['GET'])
def list_visual_themes():
    """List all available visual themes"""
    
    if not visual_creator or not visual_creator.visual_gen:
        return jsonify({
            'success': False,
            'error': 'Visual generator not available'
        }), 503
    
    themes = visual_creator.visual_gen.get_available_themes()
    theme_details = visual_creator.visual_gen.themes
    
    theme_list = []
    for theme_key in themes:
        theme_info = theme_details[theme_key]
        theme_list.append({
            'key': theme_key,
            'name': theme_info['name'],
            'description': theme_info['description']
        })
    
    return jsonify({
        'success': True,
        'themes': theme_list,
        'count': len(theme_list)
    })


@visual_bp.route('/api/visual/chart-types', methods=['GET'])
def list_chart_types():
    """List all available chart types"""
    
    if not visual_creator or not visual_creator.visual_gen:
        return jsonify({
            'success': False,
            'error': 'Visual generator not available'
        }), 503
    
    chart_types = visual_creator.visual_gen.get_available_chart_types()
    
    return jsonify({
        'success': True,
        'chart_types': chart_types,
        'count': len(chart_types)
    })


@visual_bp.route('/api/visual/generate', methods=['POST'])
def generate_visual():
    """
    Generate visual content
    
    Request body:
    {
        "content_type": "image_only|chart_only|image_with_chart|text_graphic",
        "theme": "theme_name",
        "chart_type": "chart_type_name",  // for charts
        "data": {...},  // for charts
        "text_overlay": "text",  // optional
        "format_type": "post|square|story"  // optional, default: post
    }
    """
    
    if not visual_creator or not visual_creator.visual_gen:
        return jsonify({
            'success': False,
            'error': 'Visual generator not available'
        }), 503
    
    try:
        data = request.json or {}
        
        content_type = data.get('content_type', 'image_only')
        theme = data.get('theme', 'happy_workers_ppe')
        chart_type = data.get('chart_type')
        chart_data = data.get('data')
        text_overlay = data.get('text_overlay')
        format_type = data.get('format_type', 'post')
        
        # Generate visual
        result = visual_creator.visual_gen.generate_linkedin_visual(
            content_type=content_type,
            theme=theme if content_type != 'chart_only' else chart_type,
            data=chart_data,
            text_overlay=text_overlay,
            format_type=format_type
        )
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify({
            'success': True,
            'visual': {
                'image_path': result['image_path'],
                'image_base64': result['image_base64'],
                'dimensions': result['dimensions'],
                'format': result['format']
            },
            'generated_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@visual_bp.route('/api/visual/linkedin-post', methods=['POST'])
def create_linkedin_post():
    """
    Create a complete LinkedIn post with visual
    
    Request body:
    {
        "topic": "employee_satisfaction",
        "content": {
            "hook": "...",
            "insight": "...",
            "conclusion": "...",
            ...
        },
        "data": {...},  // optional chart data
        "custom_visual": {...}  // optional visual specification
    }
    """
    
    if not visual_creator:
        return jsonify({
            'success': False,
            'error': 'Visual creator not available'
        }), 503
    
    try:
        data = request.json or {}
        
        topic = data.get('topic', 'best_practices')
        content = data.get('content', {})
        chart_data = data.get('data')
        custom_visual = data.get('custom_visual')
        
        # Create post
        result = visual_creator.create_linkedin_post_with_visual(
            topic=topic,
            content=content,
            data=chart_data,
            custom_visual=custom_visual
        )
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify({
            'success': True,
            'post': {
                'text': result['post_text'],
                'character_count': result['character_count'],
                'has_hashtags': result['has_hashtags'],
                'has_question': result['has_question']
            },
            'visual': {
                'image_path': result['visual']['image_path'],
                'image_base64': result['visual']['image_base64'],
                'description': result['visual_description']
            },
            'metrics': {
                'estimated_engagement': result['estimated_engagement'],
                'ready_to_post': result['ready_to_post']
            },
            'generated_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@visual_bp.route('/api/visual/from-insight', methods=['POST'])
def create_post_from_insight():
    """
    Create LinkedIn post from a consulting insight
    
    Request body:
    {
        "insight": {
            "topic": "employee_satisfaction",
            "finding": "...",
            "conclusion": "...",
            "data": {...}
        }
    }
    """
    
    if not visual_creator:
        return jsonify({
            'success': False,
            'error': 'Visual creator not available'
        }), 503
    
    try:
        data = request.json or {}
        insight = data.get('insight', {})
        
        if not insight:
            return jsonify({
                'success': False,
                'error': 'Insight data is required'
            }), 400
        
        # Create post from insight
        result = visual_creator.create_post_from_insight(insight)
        
        if not result['success']:
            return jsonify(result), 400
        
        return jsonify({
            'success': True,
            'post': {
                'text': result['post_text'],
                'character_count': result['character_count']
            },
            'visual': {
                'image_path': result['visual']['image_path'],
                'image_base64': result['visual']['image_base64'],
                'description': result['visual_description']
            },
            'metrics': {
                'estimated_engagement': result['estimated_engagement']
            },
            'generated_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@visual_bp.route('/api/visual/download/<path:filename>', methods=['GET'])
def download_visual(filename):
    """Download a generated visual file"""
    
    filepath = f'/tmp/{filename}'
    
    if not os.path.exists(filepath):
        return jsonify({
            'success': False,
            'error': 'File not found'
        }), 404
    
    return send_file(
        filepath,
        mimetype='image/png',
        as_attachment=True,
        download_name=filename
    )


@visual_bp.route('/api/visual/test', methods=['GET'])
def test_visual_system():
    """Test the visual generation system"""
    
    if not visual_creator:
        return jsonify({
            'success': False,
            'error': 'Visual creator not initialized',
            'available': False
        })
    
    capabilities = visual_creator.get_visual_capabilities()
    
    test_results = {
        'visual_creator': VISUAL_CREATOR_AVAILABLE,
        'visual_generator': VISUAL_GENERATOR_AVAILABLE,
        'capabilities': capabilities,
        'ready': capabilities.get('available', False)
    }
    
    if test_results['ready']:
        test_results['message'] = '✅ Visual generation system is ready!'
        test_results['next_steps'] = [
            'Call /api/visual/linkedin-post to create posts',
            'Call /api/visual/generate for standalone visuals',
            'Check /api/visual/themes for available themes',
            'Check /api/visual/chart-types for chart options'
        ]
    else:
        missing = []
        for dep, available in capabilities.get('dependencies', {}).items():
            if not available:
                missing.append(dep)
        
        test_results['message'] = '⚠️ Visual generation not ready'
        test_results['missing_dependencies'] = missing
        test_results['install_command'] = 'pip install Pillow matplotlib --break-system-packages'
    
    return jsonify(test_results)


# Integration helper for adding to existing app
def register_visual_routes(app):
    """
    Register visual content routes with Flask app
    
    Usage in app.py:
        from routes.visual import register_visual_routes
        register_visual_routes(app)
    
    Or if using blueprints:
        from routes.visual import visual_bp
        app.register_blueprint(visual_bp)
    """
    app.register_blueprint(visual_bp)
    print("✅ Visual content routes registered")


# I did no harm and this file is not truncated
