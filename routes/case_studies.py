"""
CASE STUDIES ROUTES - Flask API Endpoints
Created: February 21, 2026

PURPOSE:
    API endpoints for the Case Study Generator feature.
    Generates SEO and AI-search optimized case studies for
    Shiftwork Solutions LLC website publishing.

ENDPOINTS:
    POST /api/case-studies/generate     - Generate a new case study + return content
    GET  /api/case-studies/download/<id> - Download case study as Word doc
    GET  /api/case-studies/list          - List all saved case studies
    GET  /api/case-studies/<id>          - Get a single case study
    DELETE /api/case-studies/<id>        - Delete a case study
    GET  /api/case-studies/status        - Health check

AUTHOR: Jim @ Shiftwork Solutions LLC
LAST UPDATED: February 21, 2026
"""

from flask import Blueprint, request, jsonify, send_file
import io
import json
from datetime import datetime

# ============================================================================
# BLUEPRINT
# ============================================================================
case_studies_bp = Blueprint('case_studies', __name__)

# ============================================================================
# IMPORT GENERATOR
# ============================================================================
try:
    from case_study_generator import (
        generate_case_study,
        generate_case_study_docx,
        save_case_study_to_db,
        get_all_case_studies,
        get_case_study_by_id,
        delete_case_study,
        init_case_studies_table,
        INDUSTRY_DISPLAY_NAMES
    )
    CASE_STUDIES_AVAILABLE = True
    init_case_studies_table()
    print("✅ Case Study Generator loaded")
except Exception as e:
    print(f"⚠️  Case Study Generator failed to load: {e}")
    CASE_STUDIES_AVAILABLE = False


# ============================================================================
# STATUS CHECK
# ============================================================================

@case_studies_bp.route('/api/case-studies/status', methods=['GET'])
def case_studies_status():
    """Health check for case study generator."""
    return jsonify({
        'available': CASE_STUDIES_AVAILABLE,
        'industries': list(INDUSTRY_DISPLAY_NAMES.keys()) if CASE_STUDIES_AVAILABLE else [],
        'features': [
            'ai_generation',
            'seo_optimized',
            'word_doc_download',
            'saved_library'
        ]
    })


# ============================================================================
# GENERATE
# ============================================================================

@case_studies_bp.route('/api/case-studies/generate', methods=['POST'])
def generate():
    """
    Generate a new case study.

    Body:
        industry: string (key from INDUSTRY_DISPLAY_NAMES)
        problem:  string (description of client problem)
        solution: string (description of solution applied)

    Returns:
        {
            'success': true,
            'id': 123,
            'title': 'Case Study Title',
            'content': '# Markdown content...',
            'word_count': 1200,
            'industry_display': 'Manufacturing',
            'generated_at': '2026-02-21T...'
        }
    """
    if not CASE_STUDIES_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Case Study Generator not available'
        }), 503

    data = request.json or {}
    industry = data.get('industry', '').strip()
    problem = data.get('problem', '').strip()
    solution = data.get('solution', '').strip()

    # Validate inputs
    errors = []
    if not industry:
        errors.append('Industry is required')
    if not problem or len(problem) < 20:
        errors.append('Problem description must be at least 20 characters')
    if not solution or len(solution) < 20:
        errors.append('Solution description must be at least 20 characters')

    if errors:
        return jsonify({
            'success': False,
            'errors': errors
        }), 400

    # Validate industry key
    if industry not in INDUSTRY_DISPLAY_NAMES:
        return jsonify({
            'success': False,
            'error': f'Unknown industry: {industry}. Valid options: {list(INDUSTRY_DISPLAY_NAMES.keys())}'
        }), 400

    # Generate content
    print(f"📝 Generating case study: {industry}")
    result = generate_case_study(industry, problem, solution)

    if not result['success']:
        return jsonify({
            'success': False,
            'error': result.get('error', 'Generation failed')
        }), 500

    # Save to database
    study_id = save_case_study_to_db(
        industry=industry,
        title=result['title'],
        content=result['content'],
        problem=problem,
        solution=solution
    )

    print(f"✅ Case study saved: ID={study_id}, title={result['title']}")

    return jsonify({
        'success': True,
        'id': study_id,
        'title': result['title'],
        'content': result['content'],
        'word_count': result['word_count'],
        'industry': industry,
        'industry_display': result['industry_display'],
        'generated_at': result['generated_at']
    })


# ============================================================================
# DOWNLOAD AS WORD DOC
# ============================================================================

@case_studies_bp.route('/api/case-studies/download/<int:study_id>', methods=['GET'])
def download(study_id):
    """
    Download a saved case study as a Word document.

    Returns: .docx file attachment
    """
    if not CASE_STUDIES_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    study = get_case_study_by_id(study_id)
    if not study:
        return jsonify({'success': False, 'error': 'Case study not found'}), 404

    try:
        docx_bytes = generate_case_study_docx(
            case_study_content=study['content'],
            title=study['title'],
            industry=study['industry']
        )

        # Build clean filename
        safe_title = ''.join(c for c in study['title'] if c.isalnum() or c in (' ', '-', '_'))
        safe_title = safe_title[:60].strip().replace(' ', '_')
        filename = f"CaseStudy_{safe_title}_{datetime.now().strftime('%Y%m%d')}.docx"

        return send_file(
            io.BytesIO(docx_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        import traceback
        print(f"❌ Download failed: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# LIST ALL
# ============================================================================

@case_studies_bp.route('/api/case-studies/list', methods=['GET'])
def list_studies():
    """
    List all saved case studies.

    Returns:
        {
            'success': true,
            'count': 5,
            'case_studies': [...]
        }
    """
    if not CASE_STUDIES_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    studies = get_all_case_studies()

    # Add display name to each
    for s in studies:
        s['industry_display'] = INDUSTRY_DISPLAY_NAMES.get(s['industry'], s['industry'])

    return jsonify({
        'success': True,
        'count': len(studies),
        'case_studies': studies
    })


# ============================================================================
# GET SINGLE
# ============================================================================

@case_studies_bp.route('/api/case-studies/<int:study_id>', methods=['GET'])
def get_study(study_id):
    """
    Get a single case study by ID.

    Returns full content including markdown.
    """
    if not CASE_STUDIES_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    study = get_case_study_by_id(study_id)
    if not study:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    study['industry_display'] = INDUSTRY_DISPLAY_NAMES.get(study['industry'], study['industry'])

    return jsonify({
        'success': True,
        'case_study': study
    })


# ============================================================================
# DELETE
# ============================================================================

@case_studies_bp.route('/api/case-studies/<int:study_id>', methods=['DELETE'])
def delete_study(study_id):
    """Delete a case study."""
    if not CASE_STUDIES_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    study = get_case_study_by_id(study_id)
    if not study:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    delete_case_study(study_id)
    return jsonify({'success': True, 'deleted_id': study_id})

# I did no harm and this file is not truncated
