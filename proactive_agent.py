"""
Proactive Intelligence Module
Created: January 22, 2026
Last Updated: January 22, 2026 - SPRINT 1: Smart Questioning + Suggestions

This module makes the AI Swarm proactive instead of reactive.
It asks questions, suggests next steps, and anticipates user needs.

SPRINT 1 FEATURES:
- Smart questioning when request is ambiguous
- Post-task suggestions based on context
- Pattern tracking for future automation

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import re
from datetime import datetime
from database import get_db


class SmartQuestioner:
    """Asks clarifying questions instead of guessing"""
    
    def analyze_ambiguity(self, user_request):
        """
        Determine what information is missing from the request
        Returns list of questions to ask user
        """
        ambiguities = []
        request_lower = user_request.lower()
        
        # Check for schedule requests without type
        if 'schedule' in request_lower and not self._has_schedule_type(request_lower):
            ambiguities.append({
                'field': 'schedule_type',
                'question': 'Which schedule type?',
                'options': ['DuPont 12-hour', 'Panama', 'Pitman', 'Southern Swing', '2-2-3', '4-crew rotation'],
                'why': 'Different schedules fit different operational needs',
                'required': True
            })
        
        # Check for missing employee count
        if ('schedule' in request_lower or 'facility' in request_lower) and not self._has_number(request_lower):
            ambiguities.append({
                'field': 'employee_count',
                'question': 'How many employees?',
                'options': ['Under 20', '20-50', '50-100', 'Over 100', 'Not sure yet'],
                'why': 'Affects crew sizing and coverage calculations',
                'required': False
            })
        
        # Check for missing industry context
        if ('schedule' in request_lower or 'facility' in request_lower or 'implementation' in request_lower) and not self._has_industry(request_lower):
            ambiguities.append({
                'field': 'industry',
                'question': 'What industry?',
                'options': ['Manufacturing', 'Pharmaceutical', 'Food Processing', 'Distribution', 'Mining', 'Chemical', 'Other'],
                'why': 'Different industries have different regulatory and operational constraints',
                'required': False
            })
        
        # Check for implementation without current state
        if 'implementation' in request_lower or 'change' in request_lower:
            if not self._mentions_current_state(request_lower):
                ambiguities.append({
                    'field': 'current_schedule',
                    'question': 'What schedule are they currently using?',
                    'options': ['5-day/8-hour', '4-day/10-hour', 'Rotating shifts', '12-hour shifts', 'Don\'t know'],
                    'why': 'Helps me calculate impact and create comparison',
                    'required': False
                })
        
        return ambiguities
    
    def _has_schedule_type(self, text):
        """Check if schedule type is mentioned"""
        schedule_types = ['dupont', 'panama', 'pitman', 'southern swing', '2-2-3', '2-3-2', '4-crew']
        return any(stype in text for stype in schedule_types)
    
    def _has_number(self, text):
        """Check if any number is mentioned"""
        return bool(re.search(r'\d+', text))
    
    def _has_industry(self, text):
        """Check if industry is mentioned"""
        industries = ['manufacturing', 'pharma', 'food', 'distribution', 'mining', 'chemical', 'automotive']
        return any(ind in text for ind in industries)
    
    def _mentions_current_state(self, text):
        """Check if current state is described"""
        current_indicators = ['currently', 'now', 'existing', 'current schedule', 'right now']
        return any(ind in text for ind in current_indicators)


class SuggestionEngine:
    """Generates proactive suggestions based on context"""
    
    def generate_suggestions(self, task_id, user_request, result):
        """
        Generate contextual suggestions after task completion
        Returns list of suggestion objects
        """
        suggestions = []
        request_lower = user_request.lower()
        
        # Schedule-specific suggestions
        if 'schedule' in request_lower:
            suggestions.extend(self._get_schedule_suggestions(task_id))
        
        # Implementation-specific suggestions
        if 'implementation' in request_lower or 'rollout' in request_lower:
            suggestions.extend(self._get_implementation_suggestions(task_id))
        
        # Survey-specific suggestions
        if 'survey' in request_lower:
            suggestions.extend(self._get_survey_suggestions(task_id))
        
        # Cost analysis suggestions
        if 'cost' in request_lower or 'overtime' in request_lower:
            suggestions.extend(self._get_cost_suggestions(task_id))
        
        # Generic follow-up suggestions
        suggestions.extend(self._get_generic_suggestions(user_request, result))
        
        return suggestions
    
    def _get_schedule_suggestions(self, task_id):
        """Suggestions specific to schedule creation"""
        return [
            {
                'type': 'immediate_next_step',
                'icon': '📋',
                'title': 'Create Implementation Checklist',
                'description': 'A new schedule needs an implementation plan. I can create a step-by-step checklist to track your progress.',
                'action': 'create_implementation_checklist',
                'action_params': {'task_id': task_id},
                'priority': 'high',
                'time_estimate': '30 seconds'
            },
            {
                'type': 'immediate_next_step',
                'icon': '💰',
                'title': 'Generate Cost Comparison',
                'description': 'Show your client the financial impact. Compare new schedule vs. current costs.',
                'action': 'create_cost_comparison',
                'action_params': {'task_id': task_id},
                'priority': 'high',
                'time_estimate': '1 minute'
            },
            {
                'type': 'next_step',
                'icon': '📊',
                'title': 'Create Employee Survey',
                'description': 'Get employee input on the new schedule before implementation.',
                'action': 'create_schedule_survey',
                'action_params': {'task_id': task_id},
                'priority': 'medium',
                'time_estimate': '2 minutes'
            }
        ]
    
    def _get_implementation_suggestions(self, task_id):
        """Suggestions for implementation planning"""
        return [
            {
                'type': 'next_step',
                'icon': '📧',
                'title': 'Draft Employee Communications',
                'description': 'Create announcement email and FAQ for employees.',
                'action': 'create_communications',
                'action_params': {'task_id': task_id},
                'priority': 'high',
                'time_estimate': '2 minutes'
            },
            {
                'type': 'next_step',
                'icon': '📅',
                'title': 'Create Implementation Timeline',
                'description': 'Build a week-by-week rollout plan with milestones.',
                'action': 'create_timeline',
                'action_params': {'task_id': task_id},
                'priority': 'medium',
                'time_estimate': '1 minute'
            }
        ]
    
    def _get_survey_suggestions(self, task_id):
        """Suggestions for survey work"""
        return [
            {
                'type': 'next_step',
                'icon': '📊',
                'title': 'Analyze Survey Results',
                'description': 'Once responses come in, I can analyze and visualize the data.',
                'action': 'analyze_survey',
                'action_params': {'task_id': task_id},
                'priority': 'medium',
                'time_estimate': '2 minutes'
            }
        ]
    
    def _get_cost_suggestions(self, task_id):
        """Suggestions for cost analysis"""
        return [
            {
                'type': 'next_step',
                'icon': '📈',
                'title': 'Create Executive Summary',
                'description': 'Package the cost analysis into a client-ready presentation.',
                'action': 'create_executive_summary',
                'action_params': {'task_id': task_id},
                'priority': 'high',
                'time_estimate': '3 minutes'
            }
        ]
    
    def _get_generic_suggestions(self, user_request, result):
        """General suggestions that apply to most tasks"""
        suggestions = []
        
        # Check if result looks like it should be a document
        if len(result) > 500 and not result.startswith('<'):
            suggestions.append({
                'type': 'process_improvement',
                'icon': '📄',
                'title': 'Save as Document',
                'description': 'This looks document-worthy. Want me to create a Word file?',
                'action': 'convert_to_document',
                'priority': 'low',
                'time_estimate': '15 seconds'
            })
        
        return suggestions


class PatternTracker:
    """Tracks user patterns for future automation suggestions"""
    
    def track_task(self, user_request, task_type):
        """Record a task for pattern analysis"""
        db = get_db()
        
        # Normalize request for pattern matching
        normalized = self._normalize_request(user_request)
        
        # Check if pattern exists
        existing = db.execute('''
            SELECT id, frequency FROM user_patterns
            WHERE pattern_type = 'frequent_task'
            AND pattern_data LIKE ?
        ''', (f'%{normalized}%',)).fetchone()
        
        if existing:
            # Increment frequency
            db.execute('''
                UPDATE user_patterns
                SET frequency = frequency + 1,
                    last_seen = ?
                WHERE id = ?
            ''', (datetime.now(), existing['id']))
        else:
            # Create new pattern
            pattern_data = json.dumps({
                'normalized_request': normalized,
                'task_type': task_type,
                'first_seen': datetime.now().isoformat()
            })
            
            db.execute('''
                INSERT INTO user_patterns (pattern_type, pattern_data, frequency)
                VALUES (?, ?, ?)
            ''', ('frequent_task', pattern_data, 1))
        
        db.commit()
        db.close()
    
    def _normalize_request(self, request):
        """Normalize request for pattern matching"""
        # Remove numbers, dates, client names
        normalized = re.sub(r'\d+', '', request)
        normalized = re.sub(r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b', 'CLIENT_NAME', normalized)
        normalized = normalized.lower().strip()
        return normalized
    
    def check_for_automation_opportunities(self):
        """Find tasks that are repeated frequently"""
        db = get_db()
        
        frequent_patterns = db.execute('''
            SELECT * FROM user_patterns
            WHERE pattern_type = 'frequent_task'
            AND frequency >= 3
            AND suggestion_made = 0
            ORDER BY frequency DESC
            LIMIT 5
        ''').fetchall()
        
        db.close()
        
        opportunities = []
        for pattern in frequent_patterns:
            data = json.loads(pattern['pattern_data'])
            opportunities.append({
                'pattern_id': pattern['id'],
                'task': data['normalized_request'],
                'frequency': pattern['frequency'],
                'suggestion': f'You\'ve done this {pattern["frequency"]} times. Want to create a template?'
            })
        
        return opportunities


class ProactiveAgent:
    """Main orchestrator for proactive intelligence"""
    
    def __init__(self):
        self.questioner = SmartQuestioner()
        self.suggester = SuggestionEngine()
        self.tracker = PatternTracker()
    
    def pre_process_request(self, user_request):
        """
        Analyze request BEFORE execution
        Returns action: 'ask_questions', 'detect_project', or 'execute'
        """
        # Check for ambiguity
        questions = self.questioner.analyze_ambiguity(user_request)
        
        if questions:
            return {
                'action': 'ask_questions',
                'data': {
                    'message': 'I need a few details to give you the best result:',
                    'required_questions': [q for q in questions if q.get('required')],
                    'optional_questions': [q for q in questions if not q.get('required')]
                }
            }
        
        # Check for new project indicators
        new_project_keywords = ['new client', 'new facility', 'kick off', 'kickoff', 'starting work with']
        if any(keyword in user_request.lower() for keyword in new_project_keywords):
            return {
                'action': 'detect_project',
                'data': {
                    'message': '🎯 I detected you might be starting a new project!',
                    'suggestion': 'Want me to set up a complete project structure with checklist, templates, and tracking?'
                }
            }
        
        # No intervention needed - proceed with task
        return {
            'action': 'execute',
            'data': None
        }
    
    def post_process_result(self, task_id, user_request, result):
        """
        Analyze result AFTER execution
        Generate proactive suggestions
        """
        # Generate suggestions
        suggestions = self.suggester.generate_suggestions(task_id, user_request, result)
        
        # Track pattern
        task_type = self._classify_task(user_request)
        self.tracker.track_task(user_request, task_type)
        
        # Check for automation opportunities
        automation_opps = self.tracker.check_for_automation_opportunities()
        if automation_opps:
            for opp in automation_opps:
                suggestions.append({
                    'type': 'automation_opportunity',
                    'icon': '⚡',
                    'title': 'Create Template',
                    'description': opp['suggestion'],
                    'action': 'create_template',
                    'action_params': {'pattern_id': opp['pattern_id']},
                    'priority': 'medium'
                })
        
        # Store suggestions in database
        self._store_suggestions(task_id, suggestions)
        
        return suggestions
    
    def _classify_task(self, user_request):
        """Classify task type for pattern tracking"""
        request_lower = user_request.lower()
        
        if 'schedule' in request_lower:
            return 'schedule_design'
        elif 'survey' in request_lower:
            return 'survey'
        elif 'implementation' in request_lower:
            return 'implementation'
        elif 'cost' in request_lower or 'overtime' in request_lower:
            return 'cost_analysis'
        else:
            return 'general'
    
    def _store_suggestions(self, task_id, suggestions):
        """Store suggestions in database for tracking"""
        db = get_db()
        
        for sug in suggestions:
            db.execute('''
                INSERT INTO proactive_suggestions
                (task_id, suggestion_type, suggestion_title, suggestion_data)
                VALUES (?, ?, ?, ?)
            ''', (
                task_id,
                sug['type'],
                sug['title'],
                json.dumps(sug)
            ))
        
        db.commit()
        db.close()


# I did no harm and this file is not truncated
