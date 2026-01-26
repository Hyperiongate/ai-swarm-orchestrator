"""
SCHEDULE REQUEST HANDLER
Created: January 26, 2026
Last Updated: January 26, 2026

CHANGES:
- January 26, 2026: Initial creation
  * Detects schedule requests
  * Asks for shift length (8 or 12 hours)
  * Shows available patterns for that shift length
  * Generates visual Excel output

PURPOSE:
Handles conversational schedule generation requests.
Guides users through: shift length → pattern selection → schedule creation

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from schedule_generator_v2 import get_pattern_generator


class ScheduleRequestHandler:
    """
    Handles multi-turn conversation for schedule generation
    """
    
    def __init__(self):
        self.generator = get_pattern_generator()
        
    def detect_schedule_request(self, user_message):
        """
        Detect if user is asking for a schedule
        
        Returns:
            bool: True if schedule request detected
        """
        schedule_keywords = [
            'create a schedule',
            'generate a schedule',
            'make a schedule',
            'show me a schedule',
            'build a schedule',
            'design a schedule',
            'schedule pattern',
            'shift pattern',
            'crew rotation',
            'dupont',
            'southern swing'
        ]
        
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in schedule_keywords)
    
    def detect_shift_length(self, user_message):
        """
        Try to detect shift length from message
        
        Returns:
            int or None: 8, 12, or None if not detected
        """
        message_lower = user_message.lower()
        
        # Check for explicit mentions
        if '12 hour' in message_lower or '12-hour' in message_lower or 'twelve hour' in message_lower:
            return 12
        if '8 hour' in message_lower or '8-hour' in message_lower or 'eight hour' in message_lower:
            return 8
        
        # Check for pattern names that imply shift length
        if 'dupont' in message_lower:
            return 12
        if 'southern swing' in message_lower:
            return 8
        
        return None
    
    def detect_pattern_preference(self, user_message, shift_length):
        """
        Try to detect pattern preference from message
        
        Returns:
            str or None: pattern key or None if not detected
        """
        message_lower = user_message.lower()
        
        # Check for specific pattern mentions
        if shift_length == 12:
            patterns = self.generator.patterns_12_hour
            
            # Check for named patterns
            if 'dupont' in message_lower or 'du pont' in message_lower:
                return 'dupont'
            
            # Check for pattern descriptions
            if '2-2-3' in message_lower or '223' in message_lower:
                return '2-2-3'
            if '2-3-2' in message_lower or '232' in message_lower:
                return '2-3-2'
            if '3-2-2-3' in message_lower or '3223' in message_lower:
                return '3-2-2-3'
            if '4-3' in message_lower or 'four three' in message_lower:
                return '4-3'
            if '4-4' in message_lower or 'four four' in message_lower:
                return '4-4'
        
        elif shift_length == 8:
            patterns = self.generator.patterns_8_hour
            
            # Check for named patterns
            if 'southern swing' in message_lower:
                return 'southern_swing'
            
            # Check for pattern descriptions
            if '5-2' in message_lower and 'fixed' in message_lower:
                return '5-2-fixed'
            if '6-3' in message_lower and 'fixed' in message_lower:
                return '6-3-fixed'
            if '6-2' in message_lower and 'rotat' in message_lower:
                return '6-2-rotating'
        
        return None
    
    def build_shift_length_prompt(self):
        """
        Build prompt asking user for shift length
        
        Returns:
            str: Formatted prompt
        """
        return """I'll help you create a schedule pattern. First, what shift length are you using?

**Choose one:**
• **12-hour shifts** (typical times: 6am-6pm / 6pm-6am)
• **8-hour shifts** (typical times: Days 7am-3pm, Evenings 3pm-11pm, Nights 11pm-7am)

Just reply with "12-hour" or "8-hour" and I'll show you the available patterns."""
    
    def build_pattern_selection_prompt(self, shift_length):
        """
        Build prompt showing available patterns for shift length
        
        Returns:
            str: Formatted prompt with pattern options
        """
        patterns = self.generator.get_available_patterns(shift_length)
        
        prompt = f"Great! For {shift_length}-hour shifts, here are the available patterns:\n\n"
        
        if shift_length == 12:
            pattern_data = self.generator.patterns_12_hour
        else:
            pattern_data = self.generator.patterns_8_hour
        
        for idx, pattern_key in enumerate(patterns, start=1):
            data = pattern_data[pattern_key]
            prompt += f"**{idx}. {pattern_key.upper().replace('_', ' ')}**\n"
            prompt += f"   {data['description']}\n"
            prompt += f"   • {data['crews']} crews required\n"
            prompt += f"   • {data['cycle_days']}-day rotation cycle\n\n"
        
        prompt += "Which pattern would you like to see? Just tell me the number or pattern name."
        
        return prompt
    
    def format_schedule_response(self, shift_length, pattern_key, filepath):
        """
        Build response message after creating schedule
        
        Returns:
            str: Formatted response
        """
        if shift_length == 12:
            pattern_data = self.generator.patterns_12_hour[pattern_key]
        else:
            pattern_data = self.generator.patterns_8_hour[pattern_key]
        
        response = f"# {shift_length}-Hour Schedule Pattern Created\n\n"
        response += f"**Pattern:** {pattern_key.upper().replace('_', ' ')}\n"
        response += f"**Description:** {pattern_data['description']}\n\n"
        
        response += "**Key Features:**\n"
        for note in pattern_data['notes']:
            response += f"• {note}\n"
        
        response += f"\n**Visual Schedule:** Your {shift_length}-hour {pattern_key} schedule pattern has been created with 8 weeks of coverage showing the complete rotation cycle.\n\n"
        response += "The Excel file includes:\n"
        response += "• Color-coded shifts (Day/Evening/Night/Off)\n"
        response += "• Week-by-week layout for each crew\n"
        response += "• Full legend explaining shift codes and times\n"
        response += "• Complete rotation cycle displayed\n"
        
        return response
    
    def process_request(self, user_message, conversation_context=None):
        """
        Process a schedule request and determine next step
        
        Args:
            user_message: User's message
            conversation_context: Dict with 'shift_length' and 'pattern_key' if already chosen
            
        Returns:
            dict with:
                - action: 'ask_shift_length', 'ask_pattern', 'generate_schedule', or 'not_schedule_request'
                - message: Response message to user
                - shift_length: If detected
                - pattern_key: If detected
                - filepath: If schedule was generated
        """
        if conversation_context is None:
            conversation_context = {}
        
        # Check if this is a schedule request
        if not self.detect_schedule_request(user_message) and not conversation_context.get('waiting_for'):
            return {
                'action': 'not_schedule_request',
                'message': None
            }
        
        # If we're waiting for shift length
        if conversation_context.get('waiting_for') == 'shift_length':
            shift_length = self.detect_shift_length(user_message)
            if shift_length:
                return {
                    'action': 'ask_pattern',
                    'message': self.build_pattern_selection_prompt(shift_length),
                    'shift_length': shift_length,
                    'waiting_for': 'pattern'
                }
            else:
                return {
                    'action': 'ask_shift_length',
                    'message': "I didn't catch that. Please choose either **12-hour** or **8-hour** shifts.",
                    'waiting_for': 'shift_length'
                }
        
        # If we're waiting for pattern
        if conversation_context.get('waiting_for') == 'pattern':
            shift_length = conversation_context.get('shift_length')
            pattern_key = self.detect_pattern_preference(user_message, shift_length)
            
            if pattern_key:
                # Generate the schedule
                filepath = self.generator.create_schedule(shift_length, pattern_key)
                return {
                    'action': 'generate_schedule',
                    'message': self.format_schedule_response(shift_length, pattern_key, filepath),
                    'shift_length': shift_length,
                    'pattern_key': pattern_key,
                    'filepath': filepath
                }
            else:
                return {
                    'action': 'ask_pattern',
                    'message': f"I didn't recognize that pattern. Here are the available {shift_length}-hour patterns:\n\n" + 
                              self.build_pattern_selection_prompt(shift_length),
                    'shift_length': shift_length,
                    'waiting_for': 'pattern'
                }
        
        # First message - check what we can detect
        shift_length = self.detect_shift_length(user_message)
        
        if shift_length:
            # Shift length detected, check for pattern
            pattern_key = self.detect_pattern_preference(user_message, shift_length)
            
            if pattern_key:
                # Both detected - generate immediately
                filepath = self.generator.create_schedule(shift_length, pattern_key)
                return {
                    'action': 'generate_schedule',
                    'message': self.format_schedule_response(shift_length, pattern_key, filepath),
                    'shift_length': shift_length,
                    'pattern_key': pattern_key,
                    'filepath': filepath
                }
            else:
                # Just shift length - ask for pattern
                return {
                    'action': 'ask_pattern',
                    'message': self.build_pattern_selection_prompt(shift_length),
                    'shift_length': shift_length,
                    'waiting_for': 'pattern'
                }
        else:
            # No shift length detected - ask for it
            return {
                'action': 'ask_shift_length',
                'message': self.build_shift_length_prompt(),
                'waiting_for': 'shift_length'
            }


# Singleton instance
_handler = None

def get_schedule_handler():
    """Get or create schedule request handler instance"""
    global _handler
    if _handler is None:
        _handler = ScheduleRequestHandler()
    return _handler


# I did no harm and this file is not truncated
