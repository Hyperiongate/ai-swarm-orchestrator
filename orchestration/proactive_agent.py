"""
Proactive Intelligence Module
Created: January 22, 2026
Last Updated: February 28, 2026 - ADDED SURVEY CLARIFICATION LOGIC

CHANGELOG:

- February 28, 2026: ADDED SURVEY CLARIFICATION LOGIC
  PROBLEM: Typing "provide me with a survey" in the Quick Tasks tab produced
    a generic, wrong-type survey with no clarifying questions asked first.
    SmartQuestioner.analyze_ambiguity() had no detection for survey requests.
    The word 'survey' was actually listed in _has_document_type() as already
    resolved, which suppressed even the generic document-type question.
  FIX: Added survey/questionnaire detection block to analyze_ambiguity().
    When the request contains 'survey' or 'questionnaire' (and does not already
    specify a survey type), the system now asks:
      1. What type of survey? (with Shiftwork Solutions-specific options)
      2. How many employees will complete it?
      3. How will it be distributed?
      4. What shift length are employees on?
      5. Is this pre- or post-implementation?
    Also added 'survey_created' task type to NextStepSuggester so meaningful
    follow-on suggestions appear after a survey is built.
    Also removed 'survey' from _has_document_type() since survey requests need
    their own dedicated questions, not the generic document-type question.

- February 21, 2026: ADDED MISSING INTERFACE METHODS
  PROBLEM: orchestration_handler.py calls pre_process_request() and
    post_process_result() which never existed on ProactiveAgent.
  FIX: Added both methods as the interface orchestration_handler.py expects.

- January 26, 2026: DISABLED SCHEDULE CLARIFICATIONS
  * Schedule requests now handled by schedule_request_handler.py

Author: Jim @ Shiftwork Solutions LLC
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
        Determine what information is missing from the request.
        Returns list of questions to ask user.

        IMPORTANT: Schedule requests are NO LONGER handled here.
        They are handled by schedule_request_handler.py which uses
        a conversational approach (shift length -> pattern selection).

        UPDATED February 28, 2026: Added survey/questionnaire detection.
        """
        ambiguities = []
        request_lower = user_request.lower()

        # =====================================================================
        # SURVEY / QUESTIONNAIRE DETECTION
        # Added February 28, 2026
        #
        # Fires when the request mentions survey or questionnaire but does NOT
        # already specify a survey type. We ask up to 5 targeted questions so
        # the AI generates the right survey for the right audience.
        # =====================================================================
        SURVEY_KEYWORDS = ['survey', 'questionnaire']
        SURVEY_TYPE_KEYWORDS = [
            'schedule preference', 'overtime preference', 'ot preference',
            'satisfaction', 'shift preference', 'pre-implementation',
            'post-implementation', 'pre implementation', 'post implementation',
            'employee satisfaction', 'custom'
        ]

        is_survey_request = any(kw in request_lower for kw in SURVEY_KEYWORDS)
        survey_type_specified = any(kw in request_lower for kw in SURVEY_TYPE_KEYWORDS)

        if is_survey_request and not survey_type_specified:
            ambiguities.append({
                'field': 'survey_type',
                'question': 'What type of survey do you need?',
                'options': [
                    'Schedule Preference (which schedules employees prefer)',
                    'Overtime Preference (OT willingness and preferences)',
                    'Employee Satisfaction (satisfaction with current schedule)',
                    'Shift Preference (days/shifts employees prefer)',
                    'Pre-Implementation (baseline before a schedule change)',
                    'Post-Implementation (feedback after a schedule change)',
                    'Custom (I will describe it)'
                ],
                'why': 'Different survey types have very different questions — the wrong type will miss critical data',
                'required': True
            })

            ambiguities.append({
                'field': 'employee_count',
                'question': 'Approximately how many employees will complete this survey?',
                'options': ['Under 50', '50-150', '150-500', 'Over 500'],
                'why': 'Affects survey length and complexity',
                'required': False
            })

            ambiguities.append({
                'field': 'distribution_method',
                'question': 'How will the survey be distributed?',
                'options': ['Paper forms (printed)', 'Email link', 'In-person / kiosk', 'Not sure yet'],
                'why': 'Paper surveys need different formatting than digital ones',
                'required': False
            })

            ambiguities.append({
                'field': 'shift_length',
                'question': 'What shift length are these employees working?',
                'options': ['8-hour shifts', '10-hour shifts', '12-hour shifts', 'Mixed / not sure'],
                'why': 'Shift length affects which schedule options appear in the survey',
                'required': False
            })

            ambiguities.append({
                'field': 'implementation_timing',
                'question': 'Is this survey before or after a schedule change?',
                'options': [
                    'Before — gathering preferences prior to a change',
                    'After — collecting feedback on a recent change',
                    'No schedule change planned — general pulse check'
                ],
                'why': 'Determines whether to include baseline or change-specific questions',
                'required': False
            })

            # Return early — survey questions are sufficient, no need to check further
            return ambiguities

        # =====================================================================
        # END SURVEY DETECTION
        # =====================================================================

        # Check for missing project context (non-schedule requests)
        if ('implementation' in request_lower or 'rollout' in request_lower) and not self._has_client_context(request_lower):
            ambiguities.append({
                'field': 'client_context',
                'question': 'Is this for an existing client or a new engagement?',
                'options': ['Existing client', 'New client'],
                'why': 'Different approaches for new vs existing clients',
                'required': False
            })

        # Check for missing document type (excluding survey — handled above)
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
        """DEPRECATED - schedule handling moved to schedule_request_handler.py"""
        return True

    def _has_number(self, text):
        """Check if text contains numbers"""
        return bool(re.search(r'\d+', text))

    def _has_industry(self, text):
        """DEPRECATED for schedule requests"""
        return True

    def _has_client_context(self, text):
        """Check if client is mentioned"""
        client_indicators = ['for', 'client', 'company', 'facility']
        return any(indicator in text.lower() for indicator in client_indicators)

    def _has_document_type(self, text):
        """
        Check if document type is specified.

        UPDATED February 28, 2026: Removed 'survey' from this list.
        Survey requests need their own dedicated clarification block above,
        not the generic document-type question. Previously, 'survey' here
        caused survey requests to appear already resolved and skip questions.
        """
        doc_types = ['proposal', 'plan', 'summary', 'report', 'collection']
        return any(doc_type in text.lower() for doc_type in doc_types)

    def format_clarification_response(self, ambiguities):
        """Format ambiguous questions into structured response"""
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
        Based on what was just done, suggest what to do next.

        UPDATED February 28, 2026: Added 'survey_created' suggestions.
        """
        suggestions = []

        if completed_task_type == 'schedule_created':
            suggestions = [
                "Would you like me to create a cost analysis for this schedule?",
                "Should I draft a communication plan for rolling this out to employees?",
                "Do you want to compare this to alternative schedule patterns?"
            ]

        elif completed_task_type == 'survey_created':
            suggestions = [
                "Would you like me to format this as a printable paper survey?",
                "Should I create a summary template for recording and analyzing the results?",
                "Do you want a cover letter to send with the survey explaining its purpose?"
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

    def infer_task_type(self, user_request):
        """
        Infer completed task type from user request text.
        Used by post_process_result() to choose the right suggestions.

        UPDATED February 28, 2026: Added survey detection.
        """
        request_lower = user_request.lower()

        if any(w in request_lower for w in ['survey', 'questionnaire']):
            return 'survey_created'
        elif any(w in request_lower for w in ['schedule', 'dupont', 'panama', 'pitman', 'rotation', 'shift pattern']):
            return 'schedule_created'
        elif any(w in request_lower for w in ['data', 'collect', 'gather']):
            return 'data_collection'
        elif any(w in request_lower for w in ['proposal', 'bid', 'quote', 'scope']):
            return 'proposal_created'

        return 'general'


class PatternTracker:
    """Tracks user patterns to anticipate future needs"""

    def record_interaction(self, user_request, response_type, context=None):
        """Record this interaction for future pattern learning"""
        try:
            db = get_db()
            timestamp = datetime.now().isoformat()
            db.execute('''
                INSERT INTO interaction_patterns
                (timestamp, request_type, response_type, context_json)
                VALUES (?, ?, ?, ?)
            ''', (timestamp, user_request, response_type, json.dumps(context or {})))
            db.commit()
            db.close()
        except Exception as e:
            print(f"Error recording interaction pattern: {e}")

    def get_common_patterns(self, limit=10):
        """Get most common request patterns"""
        try:
            db = get_db()
            patterns = db.execute('''
                SELECT request_type, COUNT(*) as frequency
                FROM interaction_patterns
                GROUP BY request_type
                ORDER BY frequency DESC
                LIMIT ?
            ''', (limit,)).fetchall()
            db.close()
            return [dict(p) for p in patterns]
        except Exception as e:
            print(f"Error getting patterns: {e}")
            return []

    def predict_next_request(self, current_request):
        """Based on past patterns, predict what user might ask next"""
        return None


class ProjectAutoDetector:
    """
    Automatically detects when user is starting a new project
    and creates project structure without being explicitly asked.
    """

    def __init__(self):
        self.project_manager = ProjectManager()

    def detect_new_project_signal(self, user_request):
        """Detect if this message indicates a new project starting"""
        request_lower = user_request.lower()

        new_project_keywords = [
            'new client', 'new engagement', 'starting with',
            'just signed', 'beginning work with', 'new facility', 'new implementation'
        ]

        if not any(keyword in request_lower for keyword in new_project_keywords):
            return None

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
        patterns = [
            r'new client\s+([A-Z][A-Za-z\s&]+)',
            r'working with\s+([A-Z][A-Za-z\s&]+)',
            r'signed\s+([A-Z][A-Za-z\s&]+)',
            r'starting with\s+([A-Z][A-Za-z\s&]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'\s+(for|in|at|with)$', '', name, flags=re.IGNORECASE)
                return name[:100]

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
        """Automatically create project structure"""
        project_id = self.project_manager.create_project(
            client_name=project_details['client_name'],
            industry=project_details['industry'],
            facility_type='24/7 Operations'
        )
        self.project_manager.create_implementation_checklist(project_id)

        return {
            'project_id': project_id,
            'client_name': project_details['client_name'],
            'message': f"I've automatically set up a project structure for {project_details['client_name']}. I've created an implementation checklist to track progress. What would you like to work on first?"
        }


# =============================================================================
# MAIN PROACTIVE AGENT CLASS
# =============================================================================

class ProactiveAgent:
    """
    Main class that orchestrates all proactive features.

    UPDATED February 28, 2026: Survey clarification now flows through
    pre_process_request() -> analyze_ambiguity() -> survey detection block.

    UPDATED February 21, 2026: Added pre_process_request() and
    post_process_result() as the interface methods orchestration_handler.py
    expects. Previously only process_request() and suggest_next_steps() existed.
    """

    def __init__(self):
        self.questioner = SmartQuestioner()
        self.suggester = NextStepSuggester()
        self.tracker = PatternTracker()
        self.project_detector = ProjectAutoDetector()

    # =========================================================================
    # Interface methods for orchestration_handler.py
    # =========================================================================

    def pre_process_request(self, user_request):
        """
        Called by orchestration_handler.py BEFORE sending the request to AI.
        Checks for clarification needs and new project signals.

        Returns dict with 'action' key:
          {'action': 'ask_questions', 'data': clarification_data}
          {'action': 'detect_project', 'data': project_data}
          {'action': 'proceed'}  <- most common, means no intervention needed
        """
        # Check for new project signal
        project_signal = self.project_detector.detect_new_project_signal(user_request)
        if project_signal:
            try:
                project_data = self.project_detector.create_auto_project(project_signal)
                return {'action': 'detect_project', 'data': project_data}
            except Exception as e:
                print(f"Auto project creation failed: {e}")

        # Check for clarification needs (includes survey detection as of Feb 28, 2026)
        ambiguities = self.questioner.analyze_ambiguity(user_request)
        if ambiguities:
            clarification = self.questioner.format_clarification_response(ambiguities)
            if clarification:
                return {'action': 'ask_questions', 'data': clarification}

        # No intervention needed
        return {'action': 'proceed'}

    def post_process_result(self, task_id, user_request, actual_output):
        """
        Called by orchestration_handler.py AFTER the AI response is generated.
        Returns a list of suggestion strings for what to do next.

        Args:
            task_id: The task ID (for future logging use)
            user_request: Original user request text
            actual_output: The AI response text

        Returns:
            list of suggestion strings (may be empty)
        """
        try:
            task_type = self.suggester.infer_task_type(user_request)
            suggestions = self.suggester.suggest_next_steps(task_type)
            return suggestions
        except Exception as e:
            print(f"post_process_result failed: {e}")
            return []

    # =========================================================================
    # Original methods - unchanged
    # =========================================================================

    def process_request(self, user_request, context=None):
        """
        Original entry point for proactive intelligence.
        Still used directly in some contexts.
        """
        project_signal = self.project_detector.detect_new_project_signal(user_request)
        if project_signal:
            return {
                'type': 'auto_project',
                'data': self.project_detector.create_auto_project(project_signal)
            }

        ambiguities = self.questioner.analyze_ambiguity(user_request)
        if ambiguities:
            return {
                'type': 'clarification',
                'data': self.questioner.format_clarification_response(ambiguities)
            }

        self.tracker.record_interaction(user_request, 'processed', context)
        return None

    def suggest_next_steps(self, completed_task_type, context=None):
        """Get suggestions for what to do next"""
        return self.suggester.suggest_next_steps(completed_task_type, context)

    def get_common_patterns(self, limit=10):
        """Get most common user request patterns"""
        return self.tracker.get_common_patterns(limit)


# I did no harm and this file is not truncated
