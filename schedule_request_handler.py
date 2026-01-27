"""
SCHEDULE REQUEST HANDLER - FIXED VERSION
Created: January 27, 2026
Last Updated: January 27, 2026 - FIXED context passing bug

CHANGES:
- January 27, 2026: FIXED BUG in context passing
  * Now properly includes updated context in ALL return values
  * This ensures routes/core.py can save the context to session
  * Fixes the "24/7" response bug where context was lost

- January 27, 2026: COMPLETE REBUILD (earlier today)
  * Asks the RIGHT questions based on 30+ years consulting experience
  * Questions: Coverage → Shift Length → Rotation Speed → Weekend Pref → Work/Off Stretch
  * THEN recommends 2-3 patterns that fit their criteria
  * No more "pick from a list of pattern names" nonsense

PURPOSE:
Guide users through PROPER schedule selection by understanding their needs first.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from schedule_generator import get_pattern_generator


class ScheduleRequestHandler:
    """
    Handles conversational schedule generation with CORRECT questions
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
            'help me with scheduling',
            'need a schedule'
        ]
        
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in schedule_keywords)
    
    def build_coverage_question(self):
        """Ask about coverage needs - FIRST question"""
        return """I'll help you find the right schedule pattern. Let's start with your coverage needs:

**What coverage do you need?**

• **24/7** - Round-the-clock, every day of the year
• **24/5** - 24 hours/day, Monday through Friday only  
• **4-days/week** - Just 4 specific days (like Mon-Thu)
• **Custom** - Something else

Just tell me which one."""
    
    def build_shift_length_question(self):
        """Ask about shift length - SECOND question"""
        return """Got it. Now, what **shift length** are you using?

• **8-hour** shifts (typical: 7am-3pm, 3pm-11pm, 11pm-7am)
• **10-hour** shifts  
• **12-hour** shifts (typical: 6am-6pm, 6pm-6am)

What's your shift length?"""
    
    def build_rotation_speed_question(self):
        """Ask about rotation speed - THIRD question"""
        return """Perfect. How fast do you want the rotation?

**Rotation speed** affects how often crews change between day/night or change shifts:

• **Fast rotation** (2-3 days before change) - Less disruption to sleep, but more frequent changes
• **Medium rotation** (4-7 days) - Balance between stability and variety
• **Slow rotation** (2+ weeks) - Long stretches on same shift, allows body to adapt

Which do you prefer?"""
    
    def build_weekend_preference_question(self):
        """Ask about weekend preferences - FOURTH question"""
        return """Good choice. Now about weekends:

**How important is having weekends off?**

• **Alternating weekends off** - Every other weekend free (most popular)
• **Fixed weekends off** - Same crews always get weekends (requires more crews)
• **Don't care** - Weekends treated like any other day

What's your preference?"""
    
    def build_work_stretch_question(self):
        """Ask about work/off stretch preferences - FIFTH question"""
        return """Last question. What's your preference for work stretches?

**Work/Off Pattern:**

• **Long work + Long breaks** (e.g., work 7 days, off 7 days) - Extended time off for life/recovery
• **Short work + Short breaks** (e.g., work 2-3, off 2-3) - Frequent shorter breaks
• **Mixed** - Combination of both

Which appeals to you?"""
    
    def recommend_patterns(self, criteria):
        """
        Based on answers, recommend 2-3 patterns that fit
        
        Args:
            criteria: dict with coverage, shift_length, rotation_speed, weekend_pref, work_stretch
            
        Returns:
            list of pattern recommendations
        """
        recommendations = []
        
        coverage = criteria.get('coverage', '').lower()
        shift_length = criteria.get('shift_length', 12)
        rotation_speed = criteria.get('rotation_speed', '').lower()
        weekend_pref = criteria.get('weekend_pref', '').lower()
        work_stretch = criteria.get('work_stretch', '').lower()
        
        # Pattern matching logic based on criteria
        if shift_length == 12:
            if 'alternating' in weekend_pref:
                if 'fast' in rotation_speed or 'short' in work_stretch:
                    recommendations.append({
                        'pattern': '2-2-3',
                        'why': 'Fast rotation (2-3 days), alternating weekends, short work stretches'
                    })
                    recommendations.append({
                        'pattern': '2-3-2',
                        'why': 'Similar to 2-2-3 but includes day/night rotation'
                    })
                
                if 'medium' in rotation_speed:
                    recommendations.append({
                        'pattern': '3-2-2-3',
                        'why': 'Medium rotation (10-day cycle), balanced work stretches'
                    })
                
                if 'slow' in rotation_speed or 'long' in work_stretch:
                    recommendations.append({
                        'pattern': 'dupont',
                        'why': 'Slow rotation (28 days), includes 7-day break, industry standard'
                    })
            
            if 'long' in work_stretch and '24/7' in coverage:
                recommendations.append({
                    'pattern': '4-4',
                    'why': 'Work 4 days, off 4 days - balanced long stretches'
                })
            
            if 'medium' in rotation_speed and not recommendations:
                recommendations.append({
                    'pattern': '4-3',
                    'why': 'Work 4, off 3 - weekly rotation, good balance'
                })
        
        elif shift_length == 8:
            if '24/7' in coverage:
                if 'slow' in rotation_speed:
                    recommendations.append({
                        'pattern': 'southern_swing',
                        'why': '8-hour rotation classic, proven for 24/7 operations'
                    })
            
            if '24/5' in coverage or '4-days' in coverage:
                recommendations.append({
                    'pattern': '5-2-fixed',
                    'why': 'Fixed shifts, weekends off, Mon-Fri coverage'
                })
        
        # If no matches, provide default recommendations
        if not recommendations:
            if shift_length == 12:
                recommendations = [
                    {'pattern': '2-2-3', 'why': 'Most popular 12-hour pattern'},
                    {'pattern': 'dupont', 'why': 'Industry standard with long breaks'}
                ]
            else:
                recommendations = [
                    {'pattern': 'southern_swing', 'why': 'Proven 8-hour rotation'},
                    {'pattern': '5-2-fixed', 'why': 'Simple fixed schedule'}
                ]
        
        return recommendations[:3]  # Max 3 recommendations
    
    def format_recommendations(self, recommendations, criteria):
        """Format pattern recommendations for user"""
        shift_length = criteria.get('shift_length', 12)
        
        response = f"\n**Based on your needs, here are the patterns I recommend:**\n\n"
        
        for idx, rec in enumerate(recommendations, 1):
            pattern_key = rec['pattern']
            
            if shift_length == 12:
                pattern_data = self.generator.patterns_12_hour.get(pattern_key)
            else:
                pattern_data = self.generator.patterns_8_hour.get(pattern_key)
            
            if pattern_data:
                response += f"**{idx}. {pattern_key.upper().replace('_', ' ')}**\n"
                response += f"   *Why this fits:* {rec['why']}\n"
                response += f"   *Pattern:* {pattern_data['description']}\n"
                response += f"   • {pattern_data['crews']} crews required\n"
                response += f"   • {pattern_data['cycle_days']}-day cycle\n\n"
        
        response += "\nWhich pattern would you like to see? Tell me the number or pattern name, and I'll generate it."
        
        return response
    
    def format_schedule_response(self, shift_length, pattern_key, filepath):
        """Build response message after creating schedule"""
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
        
        response += f"\n**Visual Schedule:** Your {shift_length}-hour {pattern_key} schedule pattern shows {pattern_data['crews']} crews across {pattern_data['cycle_days']} days.\n\n"
        response += "The Excel file includes:\n"
        response += "• Color-coded shifts (Day/Night/Off)\n"
        response += "• Week-by-week layout for each crew\n"
        response += "• Full rotation cycle displayed\n"
        
        return response
    
    def detect_answer(self, user_message, question_type):
        """
        Detect user's answer to a specific question
        
        Args:
            user_message: User's response
            question_type: What we're asking about
            
        Returns:
            Detected value or None
        """
        message_lower = user_message.lower()
        
        if question_type == 'coverage':
            if '24/7' in message_lower or 'twenty four seven' in message_lower or 'around the clock' in message_lower:
                return '24/7'
            if '24/5' in message_lower or 'twenty four five' in message_lower or 'monday through friday' in message_lower:
                return '24/5'
            if '4 day' in message_lower or 'four day' in message_lower:
                return '4-days'
            if 'custom' in message_lower or 'different' in message_lower or 'other' in message_lower:
                return 'custom'
        
        elif question_type == 'shift_length':
            if '12' in message_lower or 'twelve' in message_lower:
                return 12
            if '10' in message_lower or 'ten' in message_lower:
                return 10
            if '8' in message_lower or 'eight' in message_lower:
                return 8
        
        elif question_type == 'rotation_speed':
            if 'fast' in message_lower or 'quick' in message_lower or '2' in message_lower or '3' in message_lower:
                return 'fast'
            if 'medium' in message_lower or 'moderate' in message_lower or 'balance' in message_lower:
                return 'medium'
            if 'slow' in message_lower or 'long' in message_lower or 'week' in message_lower:
                return 'slow'
        
        elif question_type == 'weekend_pref':
            if 'alternat' in message_lower or 'every other' in message_lower:
                return 'alternating'
            if 'fixed' in message_lower or 'same' in message_lower or 'permanent' in message_lower:
                return 'fixed'
            if 'don' in message_lower and 'care' in message_lower or 'doesn' in message_lower:
                return 'dont_care'
        
        elif question_type == 'work_stretch':
            if 'long' in message_lower and ('work' in message_lower or 'break' in message_lower):
                return 'long'
            if 'short' in message_lower:
                return 'short'
            if 'mix' in message_lower or 'both' in message_lower or 'combination' in message_lower:
                return 'mixed'
        
        elif question_type == 'pattern_selection':
            # Detect which pattern they're choosing from recommendations
            if '2-2-3' in message_lower or '223' in message_lower or '1' in message_lower:
                return '2-2-3'
            if '2-3-2' in message_lower or '232' in message_lower or '2' in message_lower:
                return '2-3-2'
            if 'dupont' in message_lower or '3' in message_lower:
                return 'dupont'
            if '4-4' in message_lower:
                return '4-4'
            if '4-3' in message_lower:
                return '4-3'
            if '3-2-2-3' in message_lower or '3223' in message_lower:
                return '3-2-2-3'
            if 'southern' in message_lower or 'swing' in message_lower:
                return 'southern_swing'
        
        return None
    
    def process_request(self, user_message, conversation_context=None):
        """
        Process a schedule request through the CORRECT question flow
        
        Args:
            user_message: User's message
            conversation_context: Dict tracking progress through questions
            
        Returns:
            dict with action, message, and updated context
        """
        if conversation_context is None:
            conversation_context = {}
        
        # Check if this is a schedule request
        if not self.detect_schedule_request(user_message) and not conversation_context.get('in_schedule_flow'):
            return {
                'action': 'not_schedule_request',
                'message': None,
                'context': conversation_context
            }
        
        # Mark that we're in the schedule flow
        conversation_context['in_schedule_flow'] = True
        
        # Question flow: coverage → shift_length → rotation_speed → weekend_pref → work_stretch → recommendations
        
        # 1. Coverage
        if not conversation_context.get('coverage'):
            coverage = self.detect_answer(user_message, 'coverage')
            if coverage:
                conversation_context['coverage'] = coverage
                return {
                    'action': 'ask_question',
                    'message': self.build_shift_length_question(),
                    'context': conversation_context
                }
            else:
                return {
                    'action': 'ask_question',
                    'message': self.build_coverage_question(),
                    'context': conversation_context
                }
        
        # 2. Shift Length
        if not conversation_context.get('shift_length'):
            shift_length = self.detect_answer(user_message, 'shift_length')
            if shift_length:
                conversation_context['shift_length'] = shift_length
                return {
                    'action': 'ask_question',
                    'message': self.build_rotation_speed_question(),
                    'context': conversation_context
                }
            else:
                return {
                    'action': 'ask_question',
                    'message': "I didn't catch that. Please choose **8-hour**, **10-hour**, or **12-hour** shifts.",
                    'context': conversation_context
                }
        
        # 3. Rotation Speed
        if not conversation_context.get('rotation_speed'):
            rotation_speed = self.detect_answer(user_message, 'rotation_speed')
            if rotation_speed:
                conversation_context['rotation_speed'] = rotation_speed
                return {
                    'action': 'ask_question',
                    'message': self.build_weekend_preference_question(),
                    'context': conversation_context
                }
            else:
                return {
                    'action': 'ask_question',
                    'message': "Please choose **fast**, **medium**, or **slow** rotation.",
                    'context': conversation_context
                }
        
        # 4. Weekend Preference
        if not conversation_context.get('weekend_pref'):
            weekend_pref = self.detect_answer(user_message, 'weekend_pref')
            if weekend_pref:
                conversation_context['weekend_pref'] = weekend_pref
                return {
                    'action': 'ask_question',
                    'message': self.build_work_stretch_question(),
                    'context': conversation_context
                }
            else:
                return {
                    'action': 'ask_question',
                    'message': "Please choose **alternating weekends**, **fixed weekends**, or **don't care**.",
                    'context': conversation_context
                }
        
        # 5. Work Stretch Preference
        if not conversation_context.get('work_stretch'):
            work_stretch = self.detect_answer(user_message, 'work_stretch')
            if work_stretch:
                conversation_context['work_stretch'] = work_stretch
                
                # Now we have all criteria - generate recommendations
                recommendations = self.recommend_patterns(conversation_context)
                conversation_context['recommendations'] = recommendations
                
                return {
                    'action': 'show_recommendations',
                    'message': self.format_recommendations(recommendations, conversation_context),
                    'context': conversation_context
                }
            else:
                return {
                    'action': 'ask_question',
                    'message': "Please choose **long work + long breaks**, **short + short**, or **mixed**.",
                    'context': conversation_context
                }
        
        # 6. Pattern Selection (after recommendations shown)
        if conversation_context.get('recommendations') and not conversation_context.get('selected_pattern'):
            pattern_key = self.detect_answer(user_message, 'pattern_selection')
            
            if pattern_key:
                # Generate the schedule
                shift_length = conversation_context['shift_length']
                filepath = self.generator.create_schedule(shift_length, pattern_key)
                
                return {
                    'action': 'generate_schedule',
                    'message': self.format_schedule_response(shift_length, pattern_key, filepath),
                    'shift_length': shift_length,
                    'pattern_key': pattern_key,
                    'filepath': filepath,
                    'context': conversation_context
                }
            else:
                return {
                    'action': 'show_recommendations',
                    'message': "I didn't recognize that pattern. " + self.format_recommendations(conversation_context['recommendations'], conversation_context),
                    'context': conversation_context
                }
        
        # Fallback
        return {
            'action': 'ask_question',
            'message': self.build_coverage_question(),
            'context': {}
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
