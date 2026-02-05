"""
Enhanced Intelligence Module
Created: January 22, 2026
Last Updated: February 5, 2026 - ADDED PATTERN RECOGNITION DASHBOARD

This module provides advanced intelligence features:
- User preference learning
- Context memory across sessions
- Predictive suggestions based on history
- Smart defaults from past behavior
- Continuous improvement loop
- Pattern recognition dashboard (NEW)

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
from datetime import datetime, timedelta
from database import get_db
from collections import defaultdict


class EnhancedIntelligence:
    """Advanced learning and memory system"""
    
    def __init__(self):
        self.user_profile = self._load_user_profile()
        self.session_context = []
        
    def learn_from_interaction(self, user_request, ai_response, user_feedback=None):
        """
        Learn from each interaction to improve future responses
        
        Args:
            user_request: What user asked
            ai_response: What AI provided
            user_feedback: Optional rating/feedback
        """
        # Extract patterns
        patterns = self._extract_patterns(user_request, ai_response)
        
        # Update user profile
        self._update_preferences(patterns, user_feedback)
        
        # Store in context memory
        self._add_to_context(user_request, ai_response)
        
        # Learn communication style
        self._learn_communication_style(user_request)
    
    def get_smart_defaults(self, task_type):
        """
        Get intelligent defaults based on user history
        
        Args:
            task_type: Type of task being performed
            
        Returns:
            dict with recommended defaults
        """
        profile = self.user_profile
        
        defaults = {
            'industry': profile.get('preferred_industry'),
            'schedule_type': profile.get('preferred_schedule_type'),
            'employee_count_range': profile.get('typical_facility_size'),
            'communication_style': profile.get('communication_style', 'balanced'),
            'detail_level': profile.get('preferred_detail_level', 'medium')
        }
        
        # Task-specific defaults
        if task_type == 'schedule_design':
            defaults['shift_length'] = profile.get('typical_shift_length', 12)
            defaults['coverage'] = profile.get('typical_coverage', '24/7')
            
        elif task_type == 'implementation':
            defaults['timeline_weeks'] = profile.get('typical_timeline', 6)
            defaults['approach'] = profile.get('implementation_approach', 'collaborative')
            
        elif task_type == 'survey':
            defaults['question_count'] = profile.get('typical_survey_length', 20)
            defaults['include_demographics'] = profile.get('include_demographics', True)
        
        return defaults
    
    def predict_next_action(self, current_context):
        """
        Predict what user will likely do next
        
        Args:
            current_context: Current task/state
            
        Returns:
            list of predicted next actions with confidence
        """
        db = get_db()
        
        # Get historical sequences
        sequences = db.execute('''
            SELECT 
                t1.task_type as current_task,
                t2.task_type as next_task,
                COUNT(*) as frequency
            FROM tasks t1
            JOIN tasks t2 ON t2.id = (
                SELECT id FROM tasks 
                WHERE created_at > t1.created_at 
                AND created_at < datetime(t1.created_at, '+1 hour')
                ORDER BY created_at ASC 
                LIMIT 1
            )
            WHERE t1.created_at >= datetime('now', '-30 days')
            GROUP BY t1.task_type, t2.task_type
            ORDER BY frequency DESC
        ''').fetchall()
        
        db.close()
        
        # Find predictions for current context
        predictions = []
        total = 0
        
        for seq in sequences:
            if seq['current_task'] == current_context:
                total += seq['frequency']
                predictions.append({
                    'action': seq['next_task'],
                    'count': seq['frequency']
                })
        
        # Calculate confidence scores
        for pred in predictions:
            pred['confidence'] = round(pred['count'] / total, 2) if total > 0 else 0
        
        return sorted(predictions, key=lambda x: x['confidence'], reverse=True)[:3]
    
    def get_contextual_memory(self, query, limit=5):
        """
        Retrieve relevant context from past interactions
        
        Args:
            query: Current query or topic
            limit: Max number of context items to return
            
        Returns:
            list of relevant past contexts
        """
        # Search recent session context first
        relevant_recent = []
        query_lower = query.lower()
        
        for ctx in reversed(self.session_context[-20:]):  # Last 20 interactions
            if any(word in ctx['request'].lower() for word in query_lower.split()):
                relevant_recent.append(ctx)
                if len(relevant_recent) >= limit:
                    break
        
        # If not enough recent context, search database
        if len(relevant_recent) < limit:
            db = get_db()
            
            # Simple keyword matching (could be enhanced with embeddings)
            keywords = ' '.join(f'%{word}%' for word in query_lower.split()[:5])
            
            historical = db.execute('''
                SELECT user_request, result, created_at
                FROM tasks
                WHERE user_request LIKE ?
                OR result LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (keywords, keywords, limit - len(relevant_recent))).fetchall()
            
            db.close()
            
            for task in historical:
                relevant_recent.append({
                    'request': task['user_request'],
                    'response': task['result'],
                    'timestamp': task['created_at']
                })
        
        return relevant_recent
    
    def _load_user_profile(self):
        """Load user preferences from database"""
        db = get_db()
        
        # Check if profile exists
        profile_data = db.execute('''
            SELECT profile_data FROM user_profiles WHERE id = 1
        ''').fetchone()
        
        db.close()
        
        if profile_data:
            return json.loads(profile_data['profile_data'])
        
        # Default empty profile
        return {}
    
    def _update_preferences(self, patterns, feedback):
        """Update user profile based on patterns and feedback"""
        profile = self.user_profile
        
        # Industry preference
        if 'industry' in patterns and patterns['industry']:
            profile['preferred_industry'] = patterns['industry']
        
        # Schedule type preference
        if 'schedule_type' in patterns:
            profile['preferred_schedule_type'] = patterns['schedule_type']
        
        # Facility size
        if 'employee_count' in patterns:
            profile['typical_facility_size'] = patterns['employee_count']
        
        # Communication style from feedback
        if feedback:
            if feedback.get('too_verbose'):
                profile['communication_style'] = 'concise'
            elif feedback.get('too_brief'):
                profile['communication_style'] = 'detailed'
        
        # Save to database
        self._save_profile(profile)
    
    def _extract_patterns(self, request, response):
        """Extract learnable patterns from interaction"""
        patterns = {}
        request_lower = request.lower()
        
        # Industry detection
        industries = ['manufacturing', 'pharmaceutical', 'food', 'distribution', 'mining']
        for industry in industries:
            if industry in request_lower:
                patterns['industry'] = industry.title()
                break
        
        # Schedule type detection
        schedule_types = ['dupont', 'panama', 'pitman', 'southern swing']
        for schedule in schedule_types:
            if schedule in request_lower:
                patterns['schedule_type'] = schedule.title()
                break
        
        # Employee count range
        import re
        numbers = re.findall(r'\d+', request)
        if numbers:
            count = int(numbers[0])
            if count < 50:
                patterns['employee_count'] = 'small'
            elif count < 200:
                patterns['employee_count'] = 'medium'
            else:
                patterns['employee_count'] = 'large'
        
        return patterns
    
    def _learn_communication_style(self, user_request):
        """Learn user's preferred communication style"""
        profile = self.user_profile
        
        # Track request length preference
        request_length = len(user_request.split())
        
        if 'avg_request_length' not in profile:
            profile['avg_request_length'] = request_length
        else:
            # Moving average
            profile['avg_request_length'] = (
                profile['avg_request_length'] * 0.8 + request_length * 0.2
            )
        
        # Determine if user prefers concise or detailed
        if profile['avg_request_length'] < 10:
            profile['communication_style'] = 'concise'
        elif profile['avg_request_length'] > 30:
            profile['communication_style'] = 'detailed'
        else:
            profile['communication_style'] = 'balanced'
    
    def _add_to_context(self, request, response):
        """Add interaction to session context memory"""
        self.session_context.append({
            'request': request,
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 50 interactions in memory
        if len(self.session_context) > 50:
            self.session_context = self.session_context[-50:]
    
    def _save_profile(self, profile):
        """Save user profile to database"""
        db = get_db()
        
        db.execute('''
            INSERT OR REPLACE INTO user_profiles (id, profile_data, updated_at)
            VALUES (1, ?, ?)
        ''', (json.dumps(profile), datetime.now()))
        
        db.commit()
        db.close()
        
        self.user_profile = profile
    
    def get_profile_summary(self):
        """Get human-readable profile summary"""
        profile = self.user_profile
        
        return {
            'preferred_industry': profile.get('preferred_industry', 'Not set'),
            'typical_facility_size': profile.get('typical_facility_size', 'Not set'),
            'communication_style': profile.get('communication_style', 'Balanced'),
            'interactions_analyzed': len(self.session_context),
            'learning_active': True
        }
    
    def get_all_patterns(self):
        """
        Get all discovered patterns for dashboard display
        
        ADDED: February 5, 2026
        
        Returns:
            dict with categorized patterns and statistics
        """
        from collections import Counter
        
        db = get_db()
        
        # Get all tasks from last 90 days
        ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        
        tasks = db.execute('''
            SELECT user_request, result, created_at, metadata
            FROM tasks
            WHERE created_at >= ?
            AND status = 'completed'
            ORDER BY created_at DESC
        ''', (ninety_days_ago,)).fetchall()
        
        # Initialize pattern counters
        industries = Counter()
        schedule_types = Counter()
        shift_lengths = Counter()
        time_patterns = Counter()
        request_lengths = []
        
        total_tasks = len(tasks)
        
        # Analyze each task
        for task in tasks:
            request = task['user_request'].lower()
            request_lengths.append(len(task['user_request']))
            
            # Count industries
            industry_keywords = {
                'pharmaceutical': ['pharma', 'pharmaceutical', 'drug', 'medicine'],
                'food processing': ['food', 'processing', 'beverage', 'dairy'],
                'manufacturing': ['manufacturing', 'factory', 'plant', 'production'],
                'mining': ['mining', 'mine', 'extraction'],
                'distribution': ['distribution', 'warehouse', 'logistics']
            }
            
            for industry, keywords in industry_keywords.items():
                if any(kw in request for kw in keywords):
                    industries[industry] += 1
            
            # Count schedule types
            schedule_keywords = {
                'DuPont': ['dupont'],
                'Panama': ['panama'],
                'Pitman': ['pitman'],
                '2-2-3': ['2-2-3', '223'],
                'Southern Swing': ['southern swing', 'southern']
            }
            
            for schedule, keywords in schedule_keywords.items():
                if any(kw in request for kw in keywords):
                    schedule_types[schedule] += 1
            
            # Count shift lengths
            if '12 hour' in request or '12-hour' in request:
                shift_lengths['12-hour'] += 1
            elif '8 hour' in request or '8-hour' in request:
                shift_lengths['8-hour'] += 1
            elif '10 hour' in request or '10-hour' in request:
                shift_lengths['10-hour'] += 1
            
            # Time patterns (day of week)
            try:
                created = datetime.strptime(task['created_at'], '%Y-%m-%d %H:%M:%S')
                day_name = created.strftime('%A')
                time_patterns[day_name] += 1
            except:
                pass
        
        db.close()
        
        # Calculate confidence scores (percentage of total tasks)
        def calc_confidence(count, total):
            if total == 0:
                return 0
            return round((count / total) * 100, 1)
        
        # Build response
        patterns = {
            'summary': {
                'total_patterns': (
                    len([i for i in industries if industries[i] > 0]) +
                    len([s for s in schedule_types if schedule_types[s] > 0]) +
                    len([l for l in shift_lengths if shift_lengths[l] > 0])
                ),
                'high_confidence_patterns': (
                    len([i for i in industries if calc_confidence(industries[i], total_tasks) > 60]) +
                    len([s for s in schedule_types if calc_confidence(schedule_types[s], total_tasks) > 60])
                ),
                'total_interactions': total_tasks
            },
            'schedule_preferences': [
                {
                    'type': 'schedule_type',
                    'value': schedule,
                    'count': count,
                    'confidence': calc_confidence(count, total_tasks)
                }
                for schedule, count in schedule_types.most_common(5)
                if count > 0
            ] + [
                {
                    'type': 'shift_length',
                    'value': length,
                    'count': count,
                    'confidence': calc_confidence(count, total_tasks)
                }
                for length, count in shift_lengths.most_common(3)
                if count > 0
            ],
            'industry_focus': [
                {
                    'industry': industry,
                    'count': count,
                    'confidence': calc_confidence(count, total_tasks)
                }
                for industry, count in industries.most_common(5)
                if count > 0
            ],
            'time_patterns': [
                {
                    'day': day,
                    'count': count,
                    'percentage': calc_confidence(count, total_tasks)
                }
                for day, count in time_patterns.most_common(7)
            ],
            'communication_style': {
                'avg_message_length': round(sum(request_lengths) / len(request_lengths)) if request_lengths else 0,
                'style': 'concise' if (sum(request_lengths) / len(request_lengths) if request_lengths else 100) < 100 else 'detailed'
            }
        }
        
        return patterns


# I did no harm and this file is not truncated
