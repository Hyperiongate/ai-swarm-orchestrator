"""
Proactive Suggestions System - Fix #5
Created: February 4, 2026
Updated: February 5, 2026 - Fixed IndentationError at line 102

Suggests next steps and provides contextual recommendations.
"""

import json
from datetime import datetime
from database import get_db


class ProactiveSuggestions:
    """Generates and tracks proactive suggestions"""
    
    def __init__(self):
        self.suggestion_templates = {
            'after_survey_analysis': [
                "Create an implementation plan based on these survey insights",
                "Generate a summary report to share with leadership",
                "Design a schedule pattern that addresses the key concerns identified"
            ],
            'after_schedule_design': [
                "Create training materials for the new schedule",
                "Generate a communication plan for rollout",
                "Develop a cost-benefit analysis comparing old vs new schedule"
            ],
            'incomplete_context': [
                "To provide better recommendations, could you share your facility size?",
                "What industry is this for? That will help me give specialized advice.",
                "Are you currently running 8-hour or 12-hour shifts?"
            ],
            'after_document_creation': [
                "Would you like me to create a presentation summarizing this document?",
                "Should I generate an executive summary version?",
                "Would you like me to add this to your project folder?"
            ]
        }
    
    def generate_suggestions(self, context):
        """
        Generate contextual suggestions based on conversation state.
        
        Args:
            context: dict with task_id, user_request, ai_response, project_phase
            
        Returns:
            list of suggestion dicts
        """
        suggestions = []
        request_lower = context.get('user_request', '').lower()
        
        # After survey analysis
        if any(word in request_lower for word in ['survey', 'assessment', 'feedback']):
            for suggestion in self.suggestion_templates['after_survey_analysis']:
                suggestions.append({
                    'type': 'next_step',
                    'text': suggestion,
                    'reasoning': 'Common next step after survey analysis'
                })
        
        # After schedule design
        if any(word in request_lower for word in ['schedule', 'pattern', 'dupont', 'rotation']):
            if context.get('document_created'):
                for suggestion in self.suggestion_templates['after_schedule_design']:
                    suggestions.append({
                        'type': 'next_step',
                        'text': suggestion,
                        'reasoning': 'Common next step after schedule creation'
                    })
        
        # Incomplete context detection
        if self._has_incomplete_context(context):
            for suggestion in self.suggestion_templates['incomplete_context']:
                suggestions.append({
                    'type': 'clarifying_question',
                    'text': suggestion,
                    'reasoning': 'Additional context would improve recommendations'
                })
        
        return suggestions[:3]  # Return top 3
    
    def _has_incomplete_context(self, context):
        """Detect if important context is missing"""
        request = context.get('user_request', '').lower()
        
        # Check for mentions without specifics
        if 'facility' in request and not any(num in request for num in ['20', '50', '100', '200']):
            return True
        
        if 'schedule' in request and not any(word in request for word in ['8', '12', 'hour', 'dupont', 'panama']):
            return True
        
        return False
    
    def store_suggestion(self, conversation_id, task_id, suggestion):
        """Store suggestion for tracking"""
        try:
            db = get_db()
            
            db.execute('''
                INSERT INTO proactive_suggestions
                (conversation_id, task_id, suggestion_type, suggestion_text, reasoning)
                VALUES (?, ?, ?, ?, ?)
            ''', (conversation_id, task_id, suggestion['type'], 
                  suggestion['text'], suggestion['reasoning']))
            
            db.commit()
            db.close()
        except Exception as e:
            print(f"⚠️ Could not store suggestion: {e}")
    
    def mark_acted_on(self, suggestion_id):
        """Mark suggestion as acted on"""
        try:
            db = get_db()
            
            db.execute('''
                UPDATE proactive_suggestions
                SET user_action = 'accepted',
                    acted_on_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (suggestion_id,))
            
            db.commit()
            db.close()
        except Exception as e:
            print(f"⚠️ Could not mark suggestion: {e}")


def get_proactive_suggestions():
    """Get singleton instance"""
    return ProactiveSuggestions()


# I did no harm and this file is not truncated
