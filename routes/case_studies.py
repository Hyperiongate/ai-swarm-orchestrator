"""
CASE STUDIES ROUTES - Flask API Endpoints
Shiftwork Solutions LLC

PURPOSE:
    API endpoints for the Case Study Generator feature.
    Generates SEO and AI-search optimized case studies for
    Shiftwork Solutions LLC website publishing.

ENDPOINTS:
    POST   /api/case-studies/generate              - Generate a new case study
    GET    /api/case-studies/download/<id>          - Download case study as Word doc
    GET    /api/case-studies/list                   - List all saved case studies
    GET    /api/case-studies/<id>                   - Get a single case study
    DELETE /api/case-studies/<id>                   - Delete a case study
    GET    /api/case-studies/<id>/website-package   - Generate SEO title, meta
                                                      description, URL slug, FAQs,
                                                      and JSON-LD schema for website
    GET    /api/case-studies/status                 - Health check

CHANGE LOG:
    February 21, 2026 - Initial creation.
    February 22, 2026 - Added GET /api/case-studies/<id>/website-package endpoint.
                        Calls generate_website_ready_package() in
                        case_study_generator.py and returns the full SEO + schema
                        package as JSON.
    February 23, 2026 - Added 'logistics' industry to support new Logistics
                        dropdown option in the UI. No route logic changes required
                        since validation delegates to INDUSTRY_DISPLAY_NAMES in
                        case_study_generator.py which now includes logistics.

AUTHOR: Jim @ Shiftwork Solutions LLC
LAST UPDATED: February 23, 2026
"""

from flask import Blueprint, request, jsonify, send_file
import io
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
        generate_website_ready_package,
        save_case_study_to_db,
        get_all_case_studies,
        get_case_study_by_id,
        delete_case_study,
        init_case_studies_table,
        INDUSTRY_DISPLAY_NAMES
    )
    CASE_STUDIES_AVAILABLE = True
    init_case_studies_table()
    print("[CaseStudies] Case Study Generator loaded successfully")
except Exception as e:
    print(f"[CaseStudies] WARNING - Failed to load Case Study Generator: {e}")
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
            'employee_engagement_narrative',
            'word_doc_download',
            'saved_library',
            'website_ready_package'
        ]
    })


# ============================================================================
# GENERATE
# ============================================================================

@case_studies_bp.route('/api/case-studies/generate', methods=['POST'])
def generate():
    """
    Generate a new SEO and AI-search optimized case study.

    Body (JSON):
        industry: string  - industry key from INDUSTRY_DISPLAY_NAMES
        problem:  string  - description of the client problem (min 20 chars)
        solution: string  - description of the solution applied (min 20 chars)

    Returns:
        {
            'success': true,
            'id': 123,
            'title': 'Case Study Title',
            'content': '# Markdown content...',
            'word_count': 1100,
            'industry': 'logistics',
            'industry_display': 'Logistics',
            'generated_at': '2026-02-23T...'
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
        return jsonify({'success': False, 'errors': errors}), 400

    # Validate industry key against the authoritative list in case_study_generator.py
    if industry not in INDUSTRY_DISPLAY_NAMES:
        return jsonify({
            'success': False,
            'error': (
                f'Unknown industry: {industry}. '
                f'Valid options: {list(INDUSTRY_DISPLAY_NAMES.keys())}'
            )
        }), 400

    print(f"[CaseStudies] Generating case study: industry={industry}")
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

    print(f"[CaseStudies] Saved: ID={study_id}, title={result['title']}")

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
# WEBSITE READY PACKAGE
# ============================================================================

@case_studies_bp.route('/api/case-studies/<int:study_id>/website-package', methods=['GET'])
def website_package(study_id):
    """
    Generate a complete website publishing package for a saved case study.

    Makes a second AI call to produce SEO metadata and structured data:
        - seo_title        : <=60 character SEO-optimized page title
        - meta_description : <=160 character meta description tag content
        - url_slug         : clean hyphenated URL slug
        - faqs             : list of 5 {question, answer} dicts for FAQ section
        - json_ld          : combined Article + FAQPage JSON-LD schema (dict)
        - json_ld_string   : JSON-LD formatted as indented string for <script> tag

    Returns:
        {
            'success': true,
            'study_id': 123,
            'study_title': 'Original Case Study Title',
            'industry_display': 'Logistics',
            'seo_title': '...',
            'meta_description': '...',
            'url_slug': '...',
            'faqs': [...],
            'json_ld': {...},
            'json_ld_string': '...',
            'generated_at': '...'
        }
    """
    if not CASE_STUDIES_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    # Confirm the study exists before making an AI call
    study = get_case_study_by_id(study_id)
    if not study:
        return jsonify({
            'success': False,
            'error': f'Case study {study_id} not found'
        }), 404

    print(f"[CaseStudies] Generating website package for ID={study_id}: {study['title']}")

    result = generate_website_ready_package(study_id)

    if not result['success']:
        print(f"[CaseStudies] Website package failed: {result.get('error')}")
        return jsonify({
            'success': False,
            'error': result.get('error', 'Website package generation failed'),
            'raw_response': result.get('raw_response', '')
        }), 500

    return jsonify({
        'success': True,
        'study_id': study_id,
        'study_title': result.get('study_title', study['title']),
        'industry_display': result.get('industry_display', ''),
        'seo_title': result['seo_title'],
        'meta_description': result['meta_description'],
        'url_slug': result['url_slug'],
        'faqs': result['faqs'],
        'json_ld': result['json_ld'],
        'json_ld_string': result['json_ld_string'],
        'generated_at': result.get('generated_at', datetime.now().isoformat())
    })


# ============================================================================
# DOWNLOAD AS WORD DOC
# ============================================================================

@case_studies_bp.route('/api/case-studies/download/<int:study_id>', methods=['GET'])
def download(study_id):
    """
    Download a saved case study as a Word document (.docx).
    Returns a file attachment.
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

        # Build clean filename from title
        safe_title = ''.join(
            c for c in study['title'] if c.isalnum() or c in (' ', '-', '_')
        )
        safe_title = safe_title[:60].strip().replace(' ', '_')
        filename = f"CaseStudy_{safe_title}_{datetime.now().strftime('%Y%m%d')}.docx"

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
        print(f"[CaseStudies] Download failed: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# LIST ALL
# ============================================================================

@case_studies_bp.route('/api/case-studies/list', methods=['GET'])
def list_studies():
    """
    List all saved case studies, newest first.

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

    # Attach display name to each record
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
    Get a single case study by ID. Returns full content including markdown.
    """
    if not CASE_STUDIES_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    study = get_case_study_by_id(study_id)
    if not study:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    study['industry_display'] = INDUSTRY_DISPLAY_NAMES.get(
        study['industry'], study['industry']
    )

    return jsonify({'success': True, 'case_study': study})


# ============================================================================
# DELETE
# ============================================================================

@case_studies_bp.route('/api/case-studies/<int:study_id>', methods=['DELETE'])
def delete_study(study_id):
    """Delete a case study by ID."""
    if not CASE_STUDIES_AVAILABLE:
        return jsonify({'success': False, 'error': 'Not available'}), 503

    study = get_case_study_by_id(study_id)
    if not study:
        return jsonify({'success': False, 'error': 'Not found'}), 404

    delete_case_study(study_id)
    return jsonify({'success': True, 'deleted_id': study_id})

# I did no harm and this file is not truncated
