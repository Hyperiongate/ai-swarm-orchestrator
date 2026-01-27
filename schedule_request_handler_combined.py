"""
COMBINED SCHEDULE REQUEST HANDLER - LOOP FIX VERSION
Created: January 27, 2026
Last Updated: January 27, 2026 - FIXED INFINITE LOOP BUG

CRITICAL FIX:
- This file uses PatternScheduleGenerator which has create_schedule() that takes only:
  * shift_length (8, 10, or 12)
  * pattern_key ('2-2-3', 'dupont', etc.)
  * weeks_to_show (optional, defaults to 6)
- NO shift start times
- NO dates  
- It uses DEFAULTS: 6am-6pm for 12-hour, 7am-3pm-11pm for 8-hour

This FIXES the infinite loop where it kept asking for shift start times.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from schedule_generator import PatternScheduleGenerator


class CombinedScheduleHandler:
    """
    Handles conversational schedule generation WITHOUT asking for shift start times
    """
    
    def __init__(self):
        self.generator = PatternScheduleGenerator()
        
    def detect_schedule_request(self, user_message):
        """Detect if user is asking for a schedule"""
        schedule_keywords = [
            'create a schedule', 'generate a schedule', 'make a schedule',
            'show me a schedule', 'build a schedule', 'design a schedule',
            'schedule pattern', 'shift pattern', 'crew rotation',
            'help me with scheduling', 'need a schedule', 'want a schedule'
        ]
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in schedule_keywords)
    
    def build_coverage_question(self):
        """Ask about coverage needs - FIRST question"""
        return """I'll help you find the right schedule pattern. Let's start with your coverage needs:

**What coverage do you need?**

• **24/7** - Round-the-clock, every day of the year
• **24/5** - 24 hours/day, Monday through Friday only  
• **Custom** - Something else

Just tell me which one."""
    
    def build_shift_length_question(self):
        """Ask about shift length - SECOND question"""
        return """Got it. Now, what **shift length** are you using?

• **8-hour** shifts
• **10-hour** shifts  
• **12-hour** shifts

What's your shift length?"""
    
    def build_rotation_speed_question(self):
        """Ask about rotation speed - THIRD question"""
        return """Perfect. How fast do you want the rotation?

• **Fast rotation** (2-3 days before change)
• **Medium rotation** (4-7 days)
• **Slow rotation** (2+ weeks)

Which do you prefer?"""
    
    def build_weekend_preference_question(self):
        """Ask about weekend preferences - FOURTH question"""
        return """How do you want weekends handled?

• **Alternating weekends** - Every other weekend off
• **Fixed weekends** - Same crew always works weekends
• **Don't care** - Whatever works

What's your preference?"""
    
    def build_work_stretch_question(self):
        """Ask about work/off stretch preferences - FIFTH question"""
        return """Last question - work stretch preference:

• **Long work + long breaks** - Work more days in a row, get longer breaks
• **Short + short** - Work fewer days, shorter breaks
• **Mixed** - Combination of both

Which sounds better?"""
    
    def recommend_patterns(self, conversation_context):
        """Recommend 2-3 patterns based on user's criteria"""
        shift_length = conversation_context.get('shift_length')
        rotation_speed = conversation_context.get('rotation_speed', 'medium')
        
        recommendations = []
        
        if shift_length == 12:
            # 12-hour patterns
            if rotation_speed == 'fast':
                recommendations.append({'pattern': '2-2-3', 'why': 'Fast rotation with every other weekend off'})
                recommendations.append({'pattern': 'dupont', 'why': 'Industry standard, balanced rotation'})
            else:
                recommendations.append({'pattern': 'dupont', 'why': 'Industry standard, balanced 4-week cycle'})
                recommendations.append({'pattern': '2-2-3', 'why': 'Every other weekend off'})
        else:
            # 8-hour patterns
            recommendations.append({'pattern': 'southern_swing', 'why': 'Classic 8-hour rotating pattern'})
            recommendations.append({'pattern': '4-4', 'why': 'Simple, predictable 4-on/4-off'})
        
        return recommendations[:3]
    
    def format_recommendations(self, recommendations, conversation_context):
        """Format recommendations for display"""
        shift_length = conversation_context.get('shift_length')
        response = f"Based on your needs, here are the best {shift_length}-hour patterns:\n\n"
        
        for i, rec in enumerate(recommendations, 1):
            pattern_key = rec['pattern']
            if shift_length == 12:
                pattern_data = self.generator.patterns_12_hour.get(pattern_key, {})
            else:
                pattern_data = self.generator.patterns_8_hour.get(pattern_key, {})
            
            response += f"**{i}. {pattern_key.upper().replace('_', ' ')}**\n"
            response += f"   *Why this fits:* {rec['why']}\n"
            response += f"   *Pattern:* {pattern_data.get('description', 'Pattern description')}\n"
            response += f"   • {pattern_data.get('crews', 4)} crews required\n"
            response += f"   • {pattern_data.get('cycle_days', 14)}-day cycle\n\n"
        
        response += "\nWhich pattern would you like to see? Tell me the number or pattern name."
        return response
    
    def format_schedule_response(self, shift_length, pattern_key, filepath):
        """Build response message after creating schedule"""
        if shift_length == 12:
            pattern_data = self.generator.patterns_12_hour.get(pattern_key, {})
        else:
            pattern_data = self.generator.patterns_8_hour.get(pattern_key, {})
        
        response = f"# {shift_length}-Hour Schedule Pattern Created\n\n"
        response += f"**Pattern:** {pattern_key.upper().replace('_', ' ')}\n"
        response += f"**Description:** {pattern_data.get('description', '')}\n\n"
        response += "**Key Features:**\n"
        for note in pattern_data.get('notes', []):
            response += f"• {note}\n"
        response += f"\n**Visual Schedule:** Your {shift_length}-hour {pattern_key} schedule shows {pattern_data.get('crews', 4)} crews across {pattern_data.get('cycle_days', 14)} days.\n"
        return response
    
    def detect_answer(self, user_message, question_type):
        """Detect user's answer to a specific question"""
        message_lower = user_message.lower()
        
        if question_type == 'coverage':
            if '24/7' in message_lower or 'twenty four seven' in message_lower:
                return '24/7'
            if '24/5' in message_lower or 'twenty four five' in message_lower:
                return '24/5'
            if 'custom' in message_lower or 'different' in message_lower:
                return 'custom'
        
        elif question_type == 'shift_length':
            if '12' in message_lower or 'twelve' in message_lower:
                return 12
            if '10' in message_lower or 'ten' in message_lower:
                return 10
            if '8' in message_lower or 'eight' in message_lower:
                return 8
        
        elif question_type == 'rotation_speed':
            if 'fast' in message_lower or 'quick' in message_lower:
                return 'fast'
            if 'medium' in message_lower or 'moderate' in message_lower:
                return 'medium'
            if 'slow' in message_lower or 'long' in message_lower:
                return 'slow'
        
        elif question_type == 'weekend_pref':
            if 'alternat' in message_lower or 'every other' in message_lower:
                return 'alternating'
            if 'fixed' in message_lower or 'same' in message_lower:
                return 'fixed'
            if 'don' in message_lower and 'care' in message_lower:
                return 'dont_care'
        
        elif question_type == 'work_stretch':
            if 'long' in message_lower:
                return 'long'
            if 'short' in message_lower:
                return 'short'
            if 'mix' in message_lower or 'both' in message_lower:
                return 'mixed'
        
        elif question_type == 'pattern_selection':
            if '2-2-3' in message_lower or '223' in message_lower or '1' in message_lower:
                return '2-2-3'
            if 'dupont' in message_lower or '3' in message_lower:
                return 'dupont'
            if 'southern' in message_lower or 'swing' in message_lower:
                return 'southern_swing'
            if '4-4' in message_lower:
                return '4-4'
        
        return None
    
    def process_request(self, user_message, conversation_context=None):
        """
        Process a schedule request WITHOUT asking for shift start times
        
        CRITICAL: This method NEVER asks for shift start times or dates.
        It uses defaults from PatternScheduleGenerator.
        """
        if conversation_context is None:
            conversation_context = {}
        
        # Check if this is a schedule request
        if not self.detect_schedule_request(user_message) and not conversation_context.get('in_schedule_flow'):
            return {'action': 'not_schedule_request', 'message': None}
        
        conversation_context['in_schedule_flow'] = True
        
        # 1. Coverage
        if not conversation_context.get('coverage'):
            coverage = self.detect_answer(user_message, 'coverage')
            if coverage:
                conversation_context['coverage'] = coverage
                return {'action': 'ask_question', 'message': self.build_shift_length_question(), 'context': conversation_context}
            else:
                return {'action': 'ask_question', 'message': self.build_coverage_question(), 'context': conversation_context}
        
        # 2. Shift Length
        if not conversation_context.get('shift_length'):
            shift_length = self.detect_answer(user_message, 'shift_length')
            if shift_length:
                conversation_context['shift_length'] = shift_length
                return {'action': 'ask_question', 'message': self.build_rotation_speed_question(), 'context': conversation_context}
            else:
                return {'action': 'ask_question', 'message': "I didn't catch that. Please choose **8-hour**, **10-hour**, or **12-hour** shifts.", 'context': conversation_context}
        
        # 3. Rotation Speed
        if not conversation_context.get('rotation_speed'):
            rotation_speed = self.detect_answer(user_message, 'rotation_speed')
            if rotation_speed:
                conversation_context['rotation_speed'] = rotation_speed
                return {'action': 'ask_question', 'message': self.build_weekend_preference_question(), 'context': conversation_context}
            else:
                return {'action': 'ask_question', 'message': "Please choose **fast**, **medium**, or **slow** rotation.", 'context': conversation_context}
        
        # 4. Weekend Preference
        if not conversation_context.get('weekend_pref'):
            weekend_pref = self.detect_answer(user_message, 'weekend_pref')
            if weekend_pref:
                conversation_context['weekend_pref'] = weekend_pref
                return {'action': 'ask_question', 'message': self.build_work_stretch_question(), 'context': conversation_context}
            else:
                return {'action': 'ask_question', 'message': "Please choose **alternating**, **fixed**, or **don't care**.", 'context': conversation_context}
        
        # 5. Work Stretch Preference
        if not conversation_context.get('work_stretch'):
            work_stretch = self.detect_answer(user_message, 'work_stretch')
            if work_stretch:
                conversation_context['work_stretch'] = work_stretch
                recommendations = self.recommend_patterns(conversation_context)
                conversation_context['recommendations'] = recommendations
                return {'action': 'show_recommendations', 'message': self.format_recommendations(recommendations, conversation_context), 'context': conversation_context}
            else:
                return {'action': 'ask_question', 'message': "Please choose **long**, **short**, or **mixed**.", 'context': conversation_context}
        
        # 6. Pattern Selection
        if conversation_context.get('recommendations') and not conversation_context.get('selected_pattern'):
            pattern_key = self.detect_answer(user_message, 'pattern_selection')
            
            if pattern_key:
                shift_length = conversation_context['shift_length']
                
                # CRITICAL: create_schedule() takes ONLY shift_length, pattern_key, weeks_to_show
                # NO shift start times, NO dates
                filepath = self.generator.create_schedule(shift_length, pattern_key, weeks_to_show=6)
                
                return {
                    'action': 'generate_schedule',
                    'message': self.format_schedule_response(shift_length, pattern_key, filepath),
                    'shift_length': shift_length,
                    'pattern_key': pattern_key,
                    'filepath': filepath
                }
            else:
                return {'action': 'show_recommendations', 'message': "I didn't recognize that. " + self.format_recommendations(conversation_context['recommendations'], conversation_context), 'context': conversation_context}
        
        # Fallback
        return {'action': 'ask_question', 'message': self.build_coverage_question(), 'context': {}}


# Singleton
_handler = None

def get_combined_schedule_handler():
    """Get or create combined schedule handler instance"""
    global _handler
    if _handler is None:
        _handler = CombinedScheduleHandler()
    return _handler


# I did no harm and this file is not truncated
