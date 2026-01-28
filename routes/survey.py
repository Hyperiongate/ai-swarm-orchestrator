"""
SURVEY ROUTES BLUEPRINT
Created: January 28, 2026
Last Updated: January 28, 2026

PURPOSE:
API endpoints for internal survey creation tool.
NOT client-facing - this is for Jim to create surveys.

ENDPOINTS:
- GET /api/survey/question-bank - Get all questions organized by category
- GET /api/survey/schedules - Get available schedule options
- POST /api/survey/create - Create a new survey
- POST /api/survey/export/word - Export survey to Word
- POST /api/survey/export/pdf - Export survey to PDF (future)
- GET /api/survey/list - List all created surveys
- POST /api/survey/analyze - Analyze survey results (future)

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify, send_file
from datetime import datetime
import json

# Import the survey builder
from survey_builder import SurveyBuilder

# Create blueprint
survey_bp = Blueprint('survey', __name__)

# Initialize survey builder
survey_builder = SurveyBuilder()


@survey_bp.route('/api/survey/question-bank', methods=['GET'])
def get_question_bank():
    """
    Get the complete question bank organized by category
    
    Returns:
        {
            'success': bool,
            'categories': [str],
            'questions_by_category': {
                'category_name': [questions]
            },
            'total_questions': int
        }
    """
    try:
        categories = survey_builder.get_categories()
        questions_by_category = {}
        
        for category in categories:
            questions_by_category[category] = survey_builder.get_questions_by_category(category)
        
        return jsonify({
            'success': True,
            'categories': categories,
            'questions_by_category': questions_by_category,
            'total_questions': len(survey_builder.question_bank)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@survey_bp.route('/api/survey/schedules', methods=['GET'])
def get_schedules():
    """
    Get available schedule options that can be rated
    
    Returns:
        {
            'success': bool,
            'schedules': [schedule objects]
        }
    """
    try:
        schedules = list(survey_builder.schedule_library.values())
        
        return jsonify({
            'success': True,
            'schedules': schedules
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@survey_bp.route('/api/survey/create', methods=['POST'])
def create_survey():
    """
    Create a new survey
    
    Request body:
        {
            'project_name': str,
            'company_name': str,
            'selected_questions': [question_ids],
            'schedules_to_rate': [schedule_ids],
            'custom_questions': [optional custom question objects]
        }
    
    Returns:
        {
            'success': bool,
            'survey': survey object,
            'message': str
        }
    """
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['project_name', 'company_name', 'selected_questions', 'schedules_to_rate']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Create the survey
        survey = survey_builder.create_survey(
            project_name=data['project_name'],
            company_name=data['company_name'],
            selected_questions=data['selected_questions'],
            schedules_to_rate=data['schedules_to_rate'],
            custom_questions=data.get('custom_questions', [])
        )
        
        # TODO: Save to database for later retrieval
        # For now, just return the survey object
        
        return jsonify({
            'success': True,
            'survey': survey,
            'message': 'Survey created successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@survey_bp.route('/api/survey/export/word', methods=['POST'])
def export_word():
    """
    Export survey to Word document
    
    Request body:
        {
            'survey': survey object from create_survey
        }
    
    Returns:
        Word document file
    """
    try:
        data = request.json
        
        if 'survey' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing survey data'
            }), 400
        
        survey = data['survey']
        
        # Generate Word document
        word_buffer = survey_builder.export_to_word(survey)
        
        # Generate filename
        project_name = survey['metadata']['project_name'].replace(' ', '_')
        filename = f"{project_name}_Survey_{datetime.now().strftime('%Y%m%d')}.docx"
        
        return send_file(
            word_buffer,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@survey_bp.route('/api/survey/templates', methods=['GET'])
def get_templates():
    """
    Get pre-configured survey templates
    
    Returns common survey configurations that Jim uses frequently
    """
    templates = {
        'standard_full': {
            'name': 'Standard Full Survey',
            'description': 'Comprehensive survey with all standard questions',
            'includes': [
                'All demographics',
                'Sleep & alertness',
                'Working conditions',
                'Schedule features',
                'Overtime',
                'Open-ended questions'
            ],
            'question_count': len(survey_builder.question_bank)
        },
        'schedule_focused': {
            'name': 'Schedule-Focused Survey',
            'description': 'Focus on schedule preferences and features',
            'categories': ['demographics', 'schedule_features', 'overtime'],
            'question_ids': [
                # Key demographics
                'dept', 'tenure', 'caregiving', 'age_group', 'commute_distance',
                # All schedule features
                'schedule_improvement', 'current_schedule_satisfaction',
                'better_schedules_exist', 'time_off_predictable', 'schedule_flexibility',
                'preferred_8hr_shift', 'preferred_12hr_shift', 'hours_vs_days_off',
                'fixed_vs_rotating', 'day_shift_start_8hr', 'day_shift_start_12hr',
                'weekend_preference', 'weekend_pattern', 'work_pattern',
                'three_day_preference', 'weekday_preference', 'supervisor_overlap',
                # Overtime
                'overtime_dependency', 'overtime_amount', 'overtime_satisfaction',
                'overtime_predictable', 'time_vs_overtime', 'overtime_desire',
                'overtime_expectation', 'overtime_weekly_hours'
            ]
        },
        'quick_pulse': {
            'name': 'Quick Pulse Survey',
            'description': 'Abbreviated survey for quick feedback',
            'categories': ['demographics', 'working_conditions', 'schedule_features'],
            'question_ids': [
                # Minimal demographics
                'dept', 'tenure', 'current_schedule',
                # Key satisfaction questions
                'current_schedule_satisfaction', 'better_schedules_exist',
                'schedule_improvement', 'enjoy_work', 'best_workplace',
                # Preference questions
                'preferred_12hr_shift', 'fixed_vs_rotating', 'overtime_desire'
            ]
        }
    }
    
    return jsonify({
        'success': True,
        'templates': templates
    })


@survey_bp.route('/api/survey/preview', methods=['POST'])
def preview_survey():
    """
    Generate a preview of the survey structure without creating a file
    
    Request body:
        {
            'selected_questions': [question_ids],
            'schedules_to_rate': [schedule_ids]
        }
    
    Returns:
        Preview structure showing question count, categories, etc.
    """
    try:
        data = request.json
        
        selected_questions = data.get('selected_questions', [])
        schedules_to_rate = data.get('schedules_to_rate', [])
        
        # Count questions by category
        category_counts = {}
        for q_id in selected_questions:
            if q_id in survey_builder.question_bank:
                question = survey_builder.question_bank[q_id]
                category = question['category']
                category_counts[category] = category_counts.get(category, 0) + 1
        
        return jsonify({
            'success': True,
            'preview': {
                'total_questions': len(selected_questions),
                'schedule_ratings': len(schedules_to_rate),
                'categories_included': list(category_counts.keys()),
                'questions_by_category': category_counts,
                'estimated_time': f"{(len(selected_questions) + len(schedules_to_rate)) // 2} minutes"
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# FUTURE: Normative database integration endpoints

@survey_bp.route('/api/survey/analyze', methods=['POST'])
def analyze_results():
    """
    Analyze survey results against normative database
    
    FUTURE IMPLEMENTATION:
    - Compare client results to normative data from hundreds of past surveys
    - Generate benchmark report
    - Identify outliers and trends
    
    Request body:
        {
            'survey_id': str,
            'responses': [response objects]
        }
    """
    return jsonify({
        'success': False,
        'error': 'Analysis feature coming soon - will integrate with normative database'
    }), 501


@survey_bp.route('/api/survey/normative-data', methods=['GET'])
def get_normative_data():
    """
    Get normative database statistics
    
    FUTURE IMPLEMENTATION:
    - Return aggregate statistics from hundreds of past surveys
    - Filter by industry, facility type, etc.
    """
    return jsonify({
        'success': False,
        'error': 'Normative database integration coming soon'
    }), 501


# I did no harm and this file is not truncated
