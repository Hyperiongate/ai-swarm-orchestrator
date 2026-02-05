"""
Proactive Curiosity Engine - Phase 1 Component 2
Created: February 5, 2026

Makes the AI naturally curious like a senior consultant.
Asks follow-up questions even when NOT explicitly needed for task execution.

BEHAVIOR:
- After completing tasks, asks curious follow-up questions
- Digs deeper into interesting topics
- Shows genuine interest in outcomes and context
- Learns Jim's preferences for when curiosity is welcome

Author: Jim @ Shiftwork Solutions LLC
"""

import json
import random
from datetime import datetime
from database import get_db


class ProactiveCuriosityEngine:
    """Generates natural, contextual follow-up questions"""
    
    def __init__(self):
        # Curiosity templates organized by context
        self.curiosity_patterns = {
            'after_schedule_design': [
                "How did the team react to this schedule when you've used it before?",
                "What's the most interesting challenge you've faced implementing this type of schedule?",
                "I'm curious - what made you lean toward this pattern specifically?"
            ],
            'after_client_mention': [
                "Tell me more about {client} - what makes them unique?",
                "How long have you been working with {client}?",
                "What's the most interesting thing about {client}'s operation?"
            ],
            'after_problem_solved': [
                "I'm curious - what led to this situation in the first place?",
                "Have you seen this pattern before with other clients?",
                "What would you have done differently if you had to do it again?"
            ],
            'after_numbers_mentioned': [
                "That's interesting - how does {number} compare to typical operations?",
                "What drove the decision to go with {number}?",
                "I'm curious about the story behind that number"
            ],
            'after_industry_mentioned': [
                "What's unique about scheduling in {industry} compared to other industries?",
                "How has {industry} changed in terms of shift work over the years?",
                "What's the biggest scheduling challenge in {industry}?"
            ],
            'general_curiosity': [
                "What's on your mind about this project?",
                "Is there anything about this situation that's particularly tricky?",
                "What would you want people to learn from this experience?"
            ]
        }
        
        # Track when curiosity was expressed to avoid being annoying
        self.curiosity_history = []
        self.max_curiosity_per_conversation = 3
    
    def should_be_curious(self, conversation_id, response_context):
        """
        Determine if AI should ask a curious follow-up question.
        
        Args:
            conversation_id: Current conversation
            response_context: Context from the just-completed response
            
        Returns:
            dict with {should_ask: bool, question: str or None, reason: str}
        """
        
        # Check curiosity budget for this conversation
        recent_questions = self._get_recent_curiosity_count(conversation_id)
        
        if recent_questions >= self.max_curiosity_per_conversation:
            return {
                'should_ask': False,
                'question': None,
                'reason': 'curiosity_budget_exhausted'
            }
        
        # Analyze context for curiosity triggers
        triggers = self._detect_curiosity_triggers(response_context)
        
        if not triggers:
            return {
                'should_ask': False,
                'question': None,
                'reason': 'no_curiosity_triggers'
            }
        
        # Select best question based on triggers
        question = self._select_curious_question(triggers, response_context)
        
        if question:
            # Log this curiosity expression
            self._log_curiosity(conversation_id, question, triggers)
            
            return {
                'should_ask': True,
                'question': question,
                'reason': f"triggered_by_{triggers[0]['type']}"
            }
        
        return {
            'should_ask': False,
            'question': None,
            'reason': 'no_good_question_found'
        }
    
    def _detect_curiosity_triggers(self, context):
        """
        Detect what aspects of the context warrant curiosity.
        
        Returns:
            list of trigger dicts: [{type, data, priority}]
        """
        
        triggers = []
        user_request = context.get('user_request', '').lower()
        ai_response = context.get('ai_response', '').lower()
        
        # Trigger 1: Schedule was designed
        if any(word in user_request for word in ['schedule', 'dupont', 'panama', 'rotation']):
            triggers.append({
                'type': 'after_schedule_design',
                'data': {},
                'priority': 8
            })
        
        # Trigger 2: Client mentioned
        # Look for capitalized words that might be client names
        import re
        potential_clients = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', context.get('user_request', ''))
        if potential_clients and len(potential_clients[0]) > 3:
            triggers.append({
                'type': 'after_client_mention',
                'data': {'client': potential_clients[0]},
                'priority': 7
            })
        
        # Trigger 3: Problem was solved
        if any(word in user_request for word in ['fix', 'problem', 'issue', 'error']):
            triggers.append({
                'type': 'after_problem_solved',
                'data': {},
                'priority': 6
            })
        
        # Trigger 4: Numbers mentioned (employees, hours, etc.)
        numbers = re.findall(r'(\d+)\s*(employees?|workers?|people|hours?|shifts?)', user_request.lower())
        if numbers:
            triggers.append({
                'type': 'after_numbers_mentioned',
                'data': {'number': f"{numbers[0][0]} {numbers[0][1]}"},
                'priority': 5
            })
        
        # Trigger 5: Industry mentioned
        industries = ['manufacturing', 'healthcare', 'mining', 'food', 'pharmaceutical', 'distribution']
        mentioned_industries = [ind for ind in industries if ind in user_request.lower()]
        if mentioned_industries:
            triggers.append({
                'type': 'after_industry_mentioned',
                'data': {'industry': mentioned_industries[0]},
                'priority': 4
            })
        
        # Sort by priority (highest first)
        triggers.sort(key=lambda x: x['priority'], reverse=True)
        
        return triggers
    
    def _select_curious_question(self, triggers, context):
        """
        Select the best curious question based on triggers.
        
        Returns:
            str: The question to ask, or None
        """
        
        if not triggers:
            # Use general curiosity as fallback
            return random.choice(self.curiosity_patterns['general_curiosity'])
        
        # Use highest priority trigger
        top_trigger = triggers[0]
        trigger_type = top_trigger['type']
        
        if trigger_type not in self.curiosity_patterns:
            return None
        
        # Get question template
        question_templates = self.curiosity_patterns[trigger_type]
        question_template = random.choice(question_templates)
        
        # Fill in placeholders
        data = top_trigger.get('data', {})
        question = question_template.format(**data) if data else question_template
        
        return question
    
    def _get_recent_curiosity_count(self, conversation_id):
        """Count how many curious questions asked in this conversation"""
        try:
            db = get_db()
            
            count = db.execute('''
                SELECT COUNT(*) as cnt FROM proactive_suggestions
                WHERE conversation_id = ?
                AND suggestion_type = 'curious_followup'
            ''', (conversation_id,)).fetchone()
            
            db.close()
            
            return count['cnt'] if count else 0
        except:
            return 0
    
    def _log_curiosity(self, conversation_id, question, triggers):
        """Log that we asked a curious question"""
        try:
            db = get_db()
            
            db.execute('''
                INSERT INTO proactive_suggestions
                (conversation_id, suggestion_type, suggestion_text, reasoning)
                VALUES (?, ?, ?, ?)
            ''', (conversation_id, 'curious_followup', question,
                  json.dumps({'triggers': [t['type'] for t in triggers]})))
            
            db.commit()
            db.close()
        except Exception as e:
            print(f"⚠️ Could not log curiosity: {e}")
    
    def get_curiosity_stats(self):
        """Get statistics about curiosity behavior"""
        try:
            db = get_db()
            
            stats = db.execute('''
                SELECT 
                    COUNT(*) as total_questions,
                    COUNT(DISTINCT conversation_id) as conversations_with_curiosity,
                    AVG(CASE WHEN user_action = 'engaged' THEN 1.0 ELSE 0.0 END) as engagement_rate
                FROM proactive_suggestions
                WHERE suggestion_type = 'curious_followup'
            ''').fetchone()
            
            db.close()
            
            return dict(stats) if stats else {}
        except:
            return {}


def get_curiosity_engine():
    """Get singleton instance"""
    return ProactiveCuriosityEngine()


# I did no harm and this file is not truncated
