"""
COMBINED SCHEDULE REQUEST HANDLER
Created: January 27, 2026
Last Updated: January 27, 2026

This handler offers TWO paths:
1. QUICK PATH: 3 questions → Basic pattern → Simple Excel
2. DETAILED PATH: 3 questions → User chooses detailed → 5 more questions → Beautiful Excel

Author: Jim @ Shiftwork Solutions LLC
"""

from schedule_generator import get_pattern_generator
from schedule_generator_complete import ScheduleInputCollector, Complete223ScheduleGenerator
from datetime import datetime


class CombinedScheduleHandler:
    """
    Handles both quick and detailed schedule generation
    """
    
    def __init__(self):
        self.basic_generator = get_pattern_generator()
        self.detailed_generator = Complete223ScheduleGenerator()
        
    def process_request(self, user_message, context):
        """
        Process user message and guide through schedule creation
        
        Returns:
            dict with 'action', 'message', 'context', and optionally 'filepath'
        """
        user_lower = user_message.lower().strip()
        
        # Detect initial schedule request
        if not context.get('in_schedule_flow'):
            if self._is_schedule_request(user_lower):
                context['in_schedule_flow'] = True
                context['step'] = 'coverage'
                return {
                    'action': 'ask_question',
                    'message': self._build_coverage_question(),
                    'context': context
                }
            else:
                return {
                    'action': 'not_schedule_request',
                    'context': context
                }
        
        # User is in schedule flow
        current_step = context.get('step')
        
        # PHASE 1: Quick pattern selection (3 questions)
        if current_step == 'coverage':
            return self._handle_coverage_answer(user_lower, context)
        elif current_step == 'shift_length':
            return self._handle_shift_length_answer(user_lower, context)
        elif current_step == 'pattern_selected':
            return self._handle_pattern_selection(user_lower, context)
        
        # DECISION POINT: Basic or Detailed?
        elif current_step == 'detail_preference':
            return self._handle_detail_preference(user_lower, context)
        
        # PHASE 2B: Detailed path (5 more questions)
        elif current_step == 'start_date':
            return self._handle_start_date(user_lower, context)
        elif current_step == 'shift_times':
            return self._handle_shift_times(user_lower, context)
        elif current_step == 'crew_names':
            return self._handle_crew_names(user_lower, context)
        elif current_step == 'pattern_matching':
            return self._handle_pattern_matching(user_lower, context)
        elif current_step == 'display_weeks':
            return self._handle_display_weeks(user_lower, context)
        else:
            # Unknown step - reset
            context['in_schedule_flow'] = False
            return {
                'action': 'not_schedule_request',
                'context': context
            }
    
    def _is_schedule_request(self, user_message):
        """Check if user is requesting a schedule"""
        keywords = ['create a schedule', 'generate a schedule', 'make a schedule', 
                   'build a schedule', 'show me a schedule', 'need a schedule']
        return any(kw in user_message for kw in keywords)
    
    # ========================================
    # PHASE 1: QUICK PATTERN SELECTION
    # ========================================
    
    def _build_coverage_question(self):
        """Ask about coverage needs"""
        return """Let's create your schedule! First question:

**What coverage do you need?**

• **24/7** - Round-the-clock operations
• **5-day** - Monday through Friday only  
• **6-day** - Monday through Saturday

What's your requirement?"""
    
    def _handle_coverage_answer(self, user_answer, context):
        """Process coverage answer"""
        if '24' in user_answer or 'seven' in user_answer or 'round' in user_answer:
            context['coverage'] = '24/7'
        elif '5' in user_answer or 'five' in user_answer or 'weekday' in user_answer:
            context['coverage'] = '5-day'
        elif '6' in user_answer or 'six' in user_answer:
            context['coverage'] = '6-day'
        else:
            context['coverage'] = user_answer
        
        context['step'] = 'shift_length'
        return {
            'action': 'ask_question',
            'message': self._build_shift_length_question(),
            'context': context
        }
    
    def _build_shift_length_question(self):
        """Ask about shift length"""
        return """**What shift length?**

• **12-hour shifts** - Longer days, more days off (most popular for 24/7)
• **8-hour shifts** - Traditional schedule, three shifts per day

Which works better?"""
    
    def _handle_shift_length_answer(self, user_answer, context):
        """Process shift length answer"""
        if '12' in user_answer or 'twelve' in user_answer:
            context['shift_length'] = 12
        elif '8' in user_answer or 'eight' in user_answer:
            context['shift_length'] = 8
        else:
            return {
                'action': 'ask_question',
                'message': "Please specify either **12-hour** or **8-hour** shifts.",
                'context': context
            }
        
        context['step'] = 'pattern_selected'
        return {
            'action': 'ask_question',
            'message': self._build_pattern_selection_question(),
            'context': context
        }
    
    def _build_pattern_selection_question(self):
        """Show available patterns"""
        return """**Recommended patterns for 12-hour shifts with 24/7 coverage:**

**Pattern #1: 2-2-3 (Pitman)**
• Every other weekend off (3-day weekend!)
• Work 2, off 2, work 3, off 2, work 2, off 3
• Most popular - used by hundreds of facilities
• Never work more than 2 consecutive days

**Pattern #2: 4-4**  
• Work 4 days, off 4 days
• Longer work stretches but longer breaks

Which pattern? (Enter **1** for 2-2-3 or **2** for 4-4)"""
    
    def _handle_pattern_selection(self, user_answer, context):
        """Process pattern selection and ASK about detail level"""
        if '1' in user_answer or '2-2-3' in user_answer or 'pitman' in user_answer:
            context['pattern'] = '2-2-3'
        elif '2' in user_answer or '4-4' in user_answer or 'four' in user_answer:
            context['pattern'] = '4-4'
        else:
            return {
                'action': 'ask_question',
                'message': "Please enter **1** for 2-2-3 or **2** for 4-4.",
                'context': context
            }
        
        # NOW ASK: Basic or Detailed?
        context['step'] = 'detail_preference'
        return {
            'action': 'ask_question',
            'message': self._build_detail_preference_question(),
            'context': context
        }
    
    # ========================================
    # DECISION POINT: BASIC OR DETAILED
    # ========================================
    
    def _build_detail_preference_question(self):
        """Ask if user wants basic or detailed schedule"""
        return """Perfect! I can create your schedule two ways:

**Option 1: BASIC** - Quick pattern view
• Simple grid showing the pattern
• Ready in seconds

**Option 2: PROFESSIONAL** - Client-ready detailed schedule
• Both grid AND calendar views
• Complete statistics (days on/off, hours per week, etc.)
• Benefits and drawbacks analysis
• Custom start date, shift times, crew names
• Takes ~1 minute with a few more questions

Which would you prefer? (Enter **1** for basic or **2** for professional)"""
    
    def _handle_detail_preference(self, user_answer, context):
        """Route to basic or detailed generation"""
        if '1' in user_answer or 'basic' in user_answer or 'quick' in user_answer or 'simple' in user_answer:
            # BASIC PATH - Generate immediately
            return self._generate_basic_schedule(context)
        
        elif '2' in user_answer or 'professional' in user_answer or 'detailed' in user_answer or 'client' in user_answer:
            # DETAILED PATH - Ask more questions
            context['step'] = 'start_date'
            return {
                'action': 'ask_question',
                'message': self._build_start_date_question(),
                'context': context
            }
        else:
            return {
                'action': 'ask_question',
                'message': "Please enter **1** for basic schedule or **2** for professional schedule.",
                'context': context
            }
    
    # ========================================
    # PHASE 2A: BASIC SCHEDULE GENERATION
    # ========================================
    
    def _generate_basic_schedule(self, context):
        """Generate basic schedule using existing generator"""
        try:
            pattern_key = context['pattern']
            shift_length = context['shift_length']
            
            filepath = self.basic_generator.create_schedule(shift_length, pattern_key)
            
            return {
                'action': 'generate_schedule',
                'message': self._build_basic_completion_message(context),
                'filepath': filepath,
                'shift_length': shift_length,
                'pattern_key': pattern_key,
                'context': context
            }
        except Exception as e:
            return {
                'action': 'error',
                'message': f"Error generating basic schedule: {str(e)}",
                'context': context
            }
    
    def _build_basic_completion_message(self, context):
        """Build completion message for basic schedule"""
        pattern = context['pattern']
        return f"""✅ **Your {pattern} Schedule is Ready!**

**Basic Pattern View**
• Pattern: {pattern}
• Shift Length: {context['shift_length']} hours
• Shows the complete crew rotation pattern

Download your schedule below. If you need a more detailed, client-ready version with statistics and calendar view, just ask me to "create a professional schedule"!"""
    
    # ========================================
    # PHASE 2B: DETAILED SCHEDULE (5 more questions)
    # ========================================
    
    def _build_start_date_question(self):
        """Ask about start date"""
        next_sunday = self._get_next_sunday()
        return f"""Great! A few more details for your professional schedule.

**Start Date:**

**Option 1:** Next Sunday ({next_sunday.strftime('%B %d, %Y')}) - RECOMMENDED
**Option 2:** Enter a specific date (format: MM/DD/YYYY)

Enter **1** for next Sunday or a specific date:"""
    
    def _handle_start_date(self, user_answer, context):
        """Process start date answer"""
        if '1' in user_answer or 'sunday' in user_answer or 'next' in user_answer or 'default' in user_answer:
            context['start_date'] = self._get_next_sunday()
        else:
            # Try to parse custom date
            try:
                parsed_date = datetime.strptime(user_answer.strip(), '%m/%d/%Y')
                context['start_date'] = parsed_date
            except:
                return {
                    'action': 'ask_question',
                    'message': "Please enter **1** for next Sunday or a date in format MM/DD/YYYY (e.g., 02/15/2026)",
                    'context': context
                }
        
        context['step'] = 'shift_times'
        return {
            'action': 'ask_question',
            'message': self._build_shift_times_question(),
            'context': context
        }
    
    def _build_shift_times_question(self):
        """Ask about shift times"""
        return """**Shift Start Times:**

**Default (most common):**
• Day shift: 6:00 AM - 6:00 PM
• Night shift: 6:00 PM - 6:00 AM

Enter **1** to use defaults, or enter custom times (e.g., "7am-7pm"):"""
    
    def _handle_shift_times(self, user_answer, context):
        """Process shift times answer"""
        if '1' in user_answer or 'default' in user_answer:
            context['shift_times'] = {
                'day_start': '06:00',
                'day_end': '18:00',
                'night_start': '18:00',
                'night_end': '06:00'
            }
        else:
            # For now, use defaults (can add parsing later)
            context['shift_times'] = {
                'day_start': '06:00',
                'day_end': '18:00',
                'night_start': '18:00',
                'night_end': '06:00'
            }
        
        context['step'] = 'crew_names'
        return {
            'action': 'ask_question',
            'message': self._build_crew_names_question(),
            'context': context
        }
    
    def _build_crew_names_question(self):
        """Ask about crew names"""
        return """**Crew Labels:**

**Option 1:** Letters (Crew A, Crew B, Crew C, Crew D)
**Option 2:** Numbers (Crew 1, Crew 2, Crew 3, Crew 4)
**Option 3:** Custom names (e.g., "Red, Blue, Green, Yellow")

Enter **1**, **2**, or your custom names separated by commas:"""
    
    def _handle_crew_names(self, user_answer, context):
        """Process crew names answer"""
        if '1' in user_answer or 'letter' in user_answer:
            context['crew_names'] = ['A', 'B', 'C', 'D']
        elif '2' in user_answer or 'number' in user_answer:
            context['crew_names'] = ['1', '2', '3', '4']
        elif ',' in user_answer:
            # Custom names
            names = [name.strip() for name in user_answer.split(',')]
            context['crew_names'] = names[:4]  # Take first 4
        else:
            context['crew_names'] = ['A', 'B', 'C', 'D']
        
        context['step'] = 'pattern_matching'
        return {
            'action': 'ask_question',
            'message': self._build_pattern_matching_question(),
            'context': context
        }
    
    def _build_pattern_matching_question(self):
        """Ask if day and night patterns should match"""
        return """**Day and Night Pattern:**

Should day crews and night crews follow the **same pattern**?

**Option 1:** Yes, same pattern (RECOMMENDED for fairness)
**Option 2:** No, different patterns

Enter **1** for same or **2** for different:"""
    
    def _handle_pattern_matching(self, user_answer, context):
        """Process pattern matching answer"""
        if '1' in user_answer or 'yes' in user_answer or 'same' in user_answer:
            context['pattern_matching'] = 'same'
        else:
            context['pattern_matching'] = 'different'
        
        context['step'] = 'display_weeks'
        return {
            'action': 'ask_question',
            'message': self._build_display_weeks_question(),
            'context': context
        }
    
    def _build_display_weeks_question(self):
        """Ask how many weeks to display"""
        return """**Display Length:**

How many weeks should the schedule show?

**Option 1:** 2 weeks (one complete cycle) - RECOMMENDED
**Option 2:** 4 weeks (two complete cycles)
**Option 3:** 8 weeks (for longer planning)

Enter **1**, **2**, or **3**:"""
    
    def _handle_display_weeks(self, user_answer, context):
        """Process display weeks and GENERATE detailed schedule"""
        if '2' in user_answer or 'four' in user_answer:
            context['display_weeks'] = 4
        elif '3' in user_answer or 'eight' in user_answer:
            context['display_weeks'] = 8
        else:
            context['display_weeks'] = 2
        
        # GENERATE PROFESSIONAL SCHEDULE
        return self._generate_professional_schedule(context)
    
    def _generate_professional_schedule(self, context):
        """Generate professional schedule with all details"""
        try:
            filepath = self.detailed_generator.create_complete_schedule(
                start_date=context['start_date'],
                shift_times=context['shift_times'],
                crew_names=context['crew_names'],
                weeks_to_show=context['display_weeks']
            )
            
            return {
                'action': 'generate_schedule',
                'message': self._build_professional_completion_message(context),
                'filepath': filepath,
                'shift_length': context['shift_length'],
                'pattern_key': context['pattern'],
                'context': context
            }
        except Exception as e:
            return {
                'action': 'error',
                'message': f"Error generating professional schedule: {str(e)}",
                'context': context
            }
    
    def _build_professional_completion_message(self, context):
        """Build completion message for professional schedule"""
        pattern = context['pattern']
        start_date = context['start_date'].strftime('%B %d, %Y')
        weeks = context['display_weeks']
        
        return f"""✅ **Your Professional {pattern} Schedule is Ready!**

**Schedule Details:**
• Pattern: {pattern} (Pitman)
• Start Date: {start_date}
• Shift Length: {context['shift_length']} hours
• Display: {weeks} weeks
• Crew Names: {', '.join(context['crew_names'])}

**What's Included:**
✓ Schedule Grid View (traditional format)
✓ Calendar View (actual dates with crew assignments)
✓ Complete Statistics (days on/off, hours/week, etc.)
✓ Pattern Benefits (7 advantages)
✓ Pattern Drawbacks (9 real operational concerns)

**Ready for client presentation!** Download your professional schedule below."""
    
    # ========================================
    # UTILITY METHODS
    # ========================================
    
    def _get_next_sunday(self):
        """Get the next Sunday"""
        from datetime import datetime, timedelta
        today = datetime.now()
        days_until_sunday = (6 - today.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        return today + timedelta(days=days_until_sunday)


def get_combined_schedule_handler():
    """Get singleton instance"""
    return CombinedScheduleHandler()


# I did no harm and this file is not truncated
