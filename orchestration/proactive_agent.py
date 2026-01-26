"""
Proactive Intelligence Module
Created: January 22, 2026
Last Updated: January 26, 2026 - DISABLED SCHEDULE CLARIFICATIONS

CHANGE LOG:
- January 26, 2026: DISABLED schedule clarification questions
  * Schedule requests are now handled by schedule_request_handler.py
  * Removed DuPont/Panama/Pitman/industry clarification logic
  * Schedule system now uses conversational pattern-based approach

This module makes the AI Swarm proactive instead of reactive.
It asks questions, suggests next steps, and anticipates user needs.

SPRINT 1 FEATURES:
- Smart questioning when request is ambiguous
- Post-task suggestions based on context
- Pattern tracking for future automation

SPRINT 2 FEATURES:
- Project auto-detection (detects "new client" keywords)
- Automatic project structure creation
- Implementation checklist generation
- Milestone tracking

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import re
from datetime import datetime
from database import get_db
from project_manager import ProjectManager


class SmartQuestioner:
    """Asks clarifying questions instead of guessing"""
    
    def analyze_ambiguity(self, user_request):
        """
        Determine what information is missing from the request
        Returns list of questions to ask user
        
        IMPORTANT: Schedule requests are NO LONGER handled here.
        They are handled by schedule_request_handler.py which uses
        a conversational approach (shift length → pattern selection).
        """
        ambiguities = []
        request_lower = user_request.lower()
        
        # REMOVED: Schedule clarification logic
        # Schedule requests now handled by schedule_request_handler.py
        # which asks for shift length first, then shows available patterns
        
        # Check for missing project context (non-schedule requests)
        if ('implementation' in request_lower or 'rollout' in request_lower) and not self._has_client_context(request_lower):
            ambiguities.append({
                'field': 'client_context',
                'question': 'Is this for an existing client or a new engagement?',
                'options': ['Existing client', 'New client'],
                'why': 'Different approaches for new vs existing clients',
                'required': False
            })
        
        # Check for missing document type
        if 'document' in request_lower and not self._has_document_type(request_lower):
            ambiguities.append({
                'field': 'document_type',
                'question': 'What type of document?',
                'options': ['Data collection', 'Proposal', 'Implementation plan', 'Executive summary'],
                'why': 'Different formats for different document types',
                'required': False
            })
        
        return ambiguities
    
    def _has_schedule_type(self, text):
        """
        DEPRECATED: No longer used for clarifications.
        Schedule handling moved to schedule_request_handler.py
        """
        return True  # Always return True to skip clarifications
    
    def _has_number(self, text):
        """Check if text contains numbers"""
        return bool(re.search(r'\d+', text))
    
    def _has_industry(self, text):
        """
        DEPRECATED for schedule requests: No longer used for clarifications.
        Industry context can be captured in other workflows.
        """
        return True  # Always return True to skip clarifications
    
    def _has_client_context(self, text):
        """Check if client is mentioned"""
        client_indicators = ['for', 'client', 'company', 'facility']
        return any(indicator in text.lower() for indicator in client_indicators)
    
    def _has_document_type(self, text):
        """Check if document type is specified"""
        doc_types = ['proposal', 'plan', 'summary', 'report', 'collection', 'survey']
        return any(doc_type in text.lower() for doc_type in doc_types)
    
    def format_clarification_response(self, ambiguities):
        """
        Format ambiguous questions into structured response
        """
        if not ambiguities:
            return None
        
        response = {
            'needs_clarification': True,
            'clarification_data': {
                'message': 'I need a few details to give you the best result:',
                'required_questions': [],
                'optional_questions': []
            }
        }
        
        for item in ambiguities:
            question_obj = {
                'field': item['field'],
                'question': item['question'],
                'options': item.get('options', []),
                'why': item.get('why', '')
            }
            
            if item.get('required', False):
                response['clarification_data']['required_questions'].append(question_obj)
            else:
                response['clarification_data']['optional_questions'].append(question_obj)
        
        return response


class NextStepSuggester:
    """Suggests logical next steps after completing a task"""
    
    def suggest_next_steps(self, completed_task_type, context=None):
        """
        Based on what was just done, suggest what to do next
        """
        suggestions = []
        
        if completed_task_type == 'schedule_created':
            suggestions = [
                "Would you like me to create a cost analysis for this schedule?",
                "Should I draft a communication plan for rolling this out to employees?",
                "Do you want to compare this to alternative schedule patterns?"
            ]
        
        elif completed_task_type == 'data_collection':
            suggestions = [
                "Would you like me to analyze this data and identify opportunities?",
                "Should I create a findings summary document?",
                "Do you want recommendations based on this data?"
            ]
        
        elif completed_task_type == 'proposal_created':
            suggestions = [
                "Would you like me to create a presentation deck from this proposal?",
                "Should I draft follow-up email templates?",
                "Do you want an FAQ document for common client questions?"
            ]
        
        return suggestions


class PatternTracker:
    """Tracks user patterns to anticipate future needs"""
    
    def __init__(self):
        self.db = get_db()
    
    def record_interaction(self, user_request, response_type, context=None):
        """
        Record this interaction for future pattern learning
        """
        try:
            timestamp = datetime.now().isoformat()
            
            self.db.execute('''
                INSERT INTO interaction_patterns 
                (timestamp, request_type, response_type, context_json)
                VALUES (?, ?, ?, ?)
            ''', (timestamp, user_request, response_type, json.dumps(context or {})))
            
            self.db.commit()
        except Exception as e:
            print(f"Error recording interaction pattern: {e}")
    
    def get_common_patterns(self, limit=10):
        """
        Get most common request patterns
        """
        try:
            patterns = self.db.execute('''
                SELECT request_type, COUNT(*) as frequency
                FROM interaction_patterns
                GROUP BY request_type
                ORDER BY frequency DESC
                LIMIT ?
            ''', (limit,)).fetchall()
            
            return [dict(p) for p in patterns]
        except Exception as e:
            print(f"Error getting patterns: {e}")
            return []
    
    def predict_next_request(self, current_request):
        """
        Based on past patterns, predict what user might ask next
        """
        # TODO: Implement ML-based prediction
        # For now, return None
        return None


# =============================================================================
# PROJECT AUTO-DETECTION (SPRINT 2)
# =============================================================================

class ProjectAutoDetector:
    """
    Automatically detects when user is starting a new project
    and creates project structure without being explicitly asked
    """
    
    def __init__(self):
        self.project_manager = ProjectManager()
    
    def detect_new_project_signal(self, user_request):
        """
        Detect if this message indicates a new project starting
        
        Returns:
            dict or None: Project details if detected, None otherwise
        """
        request_lower = user_request.lower()
        
        # Keywords that indicate new project
        new_project_keywords = [
            'new client',
            'new engagement',
            'starting with',
            'just signed',
            'beginning work with',
            'new facility',
            'new implementation'
        ]
        
        if not any(keyword in request_lower for keyword in new_project_keywords):
            return None
        
        # Extract client name (simple heuristic)
        client_name = self._extract_client_name(user_request)
        industry = self._extract_industry(user_request)
        
        if client_name:
            return {
                'client_name': client_name,
                'industry': industry or 'Manufacturing',
                'auto_detected': True
            }
        
        return None
    
    def _extract_client_name(self, text):
        """Try to extract client name from text"""
        # Look for patterns like "new client ABC Corp" or "working with XYZ Manufacturing"
        patterns = [
            r'new client\s+([A-Z][A-Za-z\s&]+)',
            r'working with\s+([A-Z][A-Za-z\s&]+)',
            r'signed\s+([A-Z][A-Za-z\s&]+)',
            r'starting with\s+([A-Z][A-Za-z\s&]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                # Clean up the match
                name = match.group(1).strip()
                # Remove trailing words like "for", "in", etc
                name = re.sub(r'\s+(for|in|at|with)$', '', name, flags=re.IGNORECASE)
                return name[:100]  # Limit length
        
        return None
    
    def _extract_industry(self, text):
        """Try to extract industry from text"""
        industries = {
            'pharmaceutical': 'Pharmaceutical',
            'pharma': 'Pharmaceutical',
            'food': 'Food Processing',
            'manufacturing': 'Manufacturing',
            'distribution': 'Distribution',
            'mining': 'Mining',
            'chemical': 'Chemical'
        }
        
        text_lower = text.lower()
        for keyword, industry in industries.items():
            if keyword in text_lower:
                return industry
        
        return None
    
    def create_auto_project(self, project_details):
        """
        Automatically create project structure
        
        Returns:
            dict: Created project info
        """
        project_id = self.project_manager.create_project(
            client_name=project_details['client_name'],
            industry=project_details['industry'],
            facility_type='24/7 Operations'
        )
        
        # Create initial checklist
        self.project_manager.create_implementation_checklist(project_id)
        
        return {
            'project_id': project_id,
            'client_name': project_details['client_name'],
            'message': f"✅ I've automatically set up a project structure for {project_details['client_name']}. I've created an implementation checklist to track progress. What would you like to work on first?"
        }


# I did no harm and this file is not truncated
