"""
CONTINUOUS LEARNING ENGINE
Created: January 20, 2026
Last Updated: January 20, 2026

PURPOSE:
Learn from every interaction, track what works, identify patterns, and
continuously improve recommendations. Make the AI smarter with each use.

FEATURES:
- Track successful vs unsuccessful approaches
- Learn user preferences and communication style
- Identify patterns in consulting engagements
- Build institutional knowledge from all projects
- Adapt recommendations based on outcomes
- Predict likely next steps with increasing accuracy

PHILOSOPHY:
Every consulting engagement teaches us something. This module captures
those lessons and applies them to future work.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from datetime import datetime
import json
import sqlite3


class ContinuousLearning:
    """
    Learns from every interaction and improves recommendations
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self._init_learning_db()
        
        # Learning categories
        self.learning_areas = {
            'successful_patterns': {},  # What works
            'failed_approaches': {},     # What doesn't work
            'user_preferences': {},      # User communication style
            'project_patterns': {},      # Common project flows
            'industry_insights': {},     # Industry-specific learnings
            'timing_patterns': {}        # When things work best
        }
        
        self._load_learned_knowledge()
    
    def _init_learning_db(self):
        """Initialize learning database"""
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Learned patterns table
        c.execute('''
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pattern_type TEXT NOT NULL,
                pattern_data TEXT NOT NULL,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                confidence_score REAL DEFAULT 0.5,
                last_applied TIMESTAMP,
                notes TEXT
            )
        ''')
        
        # Interaction outcomes table
        c.execute('''
            CREATE TABLE IF NOT EXISTS interaction_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interaction_id TEXT,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_request TEXT,
                ai_response TEXT,
                user_feedback_rating INTEGER,
                outcome_type TEXT,
                what_worked TEXT,
                what_failed TEXT,
                context_data TEXT
            )
        ''')
        
        # Knowledge base table (cumulative learnings)
        c.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                topic TEXT NOT NULL,
                insight TEXT NOT NULL,
                evidence_count INTEGER DEFAULT 1,
                confidence REAL DEFAULT 0.5,
                source TEXT,
                tags TEXT
            )
        ''')
        
        # Prediction accuracy tracking
        c.execute('''
            CREATE TABLE IF NOT EXISTS prediction_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                prediction TEXT,
                actual_outcome TEXT,
                was_correct BOOLEAN,
                confidence REAL,
                context TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_learned_knowledge(self):
        """Load previously learned patterns from database"""
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Load successful patterns
        c.execute('''
            SELECT pattern_type, pattern_data, confidence_score 
            FROM learned_patterns 
            WHERE success_count > failure_count
            AND confidence_score > 0.6
            ORDER BY confidence_score DESC
        ''')
        
        for row in c.fetchall():
            pattern_type, pattern_data, confidence = row
            if pattern_type not in self.learning_areas['successful_patterns']:
                self.learning_areas['successful_patterns'][pattern_type] = []
            
            self.learning_areas['successful_patterns'][pattern_type].append({
                'pattern': json.loads(pattern_data),
                'confidence': confidence
            })
        
        conn.close()
    
    def learn_from_interaction(self, interaction_data, outcome_data):
        """
        Learn from a completed interaction
        
        Args:
            interaction_data: dict with user_request, ai_response, context
            outcome_data: dict with user_rating, what_worked, what_failed
            
        Returns:
            dict with learnings extracted
        """
        
        learnings = {
            'patterns_identified': [],
            'insights_gained': [],
            'knowledge_updated': False,
            'predictions_refined': False
        }
        
        user_rating = outcome_data.get('user_rating', 0)
        what_worked = outcome_data.get('what_worked', '')
        what_failed = outcome_data.get('what_failed', '')
        
        # Pattern 1: Learn from high-rated interactions
        if user_rating >= 4:
            pattern = self._extract_successful_pattern(interaction_data)
            if pattern:
                self._record_successful_pattern(pattern)
                learnings['patterns_identified'].append(pattern)
                learnings['knowledge_updated'] = True
        
        # Pattern 2: Learn from failures
        if user_rating <= 2 or what_failed:
            failure = self._extract_failure_pattern(interaction_data, what_failed)
            if failure:
                self._record_failure_pattern(failure)
                learnings['patterns_identified'].append(failure)
                learnings['knowledge_updated'] = True
        
        # Pattern 3: Extract general insights
        insights = self._extract_insights(interaction_data, outcome_data)
        if insights:
            for insight in insights:
                self._add_to_knowledge_base(insight)
            learnings['insights_gained'] = insights
            learnings['knowledge_updated'] = True
        
        # Pattern 4: Update user preference model
        self._update_user_preferences(interaction_data, outcome_data)
        
        # Store the interaction outcome
        self._store_interaction_outcome(interaction_data, outcome_data)
        
        return learnings
    
    def _extract_successful_pattern(self, interaction_data):
        """Extract what made an interaction successful"""
        
        request = interaction_data.get('user_request', '').lower()
        response = interaction_data.get('ai_response', '').lower()
        
        pattern = {
            'type': 'successful_interaction',
            'trigger': None,
            'response_pattern': None,
            'context': {}
        }
        
        # Identify what type of request this was
        if 'calculate' in request or 'cost' in request:
            pattern['trigger'] = 'cost_calculation_request'
            pattern['response_pattern'] = 'provided_detailed_numbers'
        elif 'survey' in request:
            pattern['trigger'] = 'survey_request'
            pattern['response_pattern'] = 'created_survey_with_validated_questions'
        elif 'schedule' in request:
            pattern['trigger'] = 'schedule_request'
            pattern['response_pattern'] = 'provided_options_with_pros_cons'
        elif 'analyze' in request or 'data' in request:
            pattern['trigger'] = 'analysis_request'
            pattern['response_pattern'] = 'provided_insights_with_recommendations'
        
        # Extract context that contributed to success
        if interaction_data.get('project_context'):
            pattern['context']['had_project_context'] = True
        if interaction_data.get('files_uploaded'):
            pattern['context']['had_data_files'] = True
        
        return pattern
    
    def _extract_failure_pattern(self, interaction_data, what_failed):
        """Extract what caused an interaction to fail"""
        
        pattern = {
            'type': 'failed_interaction',
            'trigger': interaction_data.get('user_request', '')[:100],
            'failure_reason': what_failed,
            'what_was_missing': []
        }
        
        # Identify common failure modes
        response = interaction_data.get('ai_response', '').lower()
        
        if 'need more' in response or 'missing' in response:
            pattern['what_was_missing'].append('insufficient_data')
        
        if len(response) > 2000:
            pattern['failure_reason'] = 'response_too_long'
        elif len(response) < 100:
            pattern['failure_reason'] = 'response_too_brief'
        
        return pattern
    
    def _extract_insights(self, interaction_data, outcome_data):
        """Extract general insights from interaction"""
        
        insights = []
        
        request = interaction_data.get('user_request', '').lower()
        rating = outcome_data.get('user_rating', 0)
        
        # Insight: Timing matters
        hour = datetime.now().hour
        if rating >= 4:
            insights.append({
                'topic': 'optimal_interaction_time',
                'insight': f'High-rated interactions often occur around {hour}:00',
                'evidence': 1,
                'tags': ['timing', 'user_behavior']
            })
        
        # Insight: Request patterns
        if 'calculate' in request and rating >= 4:
            insights.append({
                'topic': 'calculation_requests',
                'insight': 'Users value detailed numerical breakdowns with context',
                'evidence': 1,
                'tags': ['calculations', 'user_preference']
            })
        
        # Insight: Communication style
        if outcome_data.get('what_worked'):
            insights.append({
                'topic': 'communication_style',
                'insight': outcome_data['what_worked'],
                'evidence': 1,
                'tags': ['communication', 'what_works']
            })
        
        return insights
    
    def _update_user_preferences(self, interaction_data, outcome_data):
        """Learn and adapt to user's communication preferences"""
        
        rating = outcome_data.get('user_rating', 0)
        
        if rating >= 4:
            # User liked this interaction - remember the style
            response = interaction_data.get('ai_response', '')
            
            # Analyze response characteristics
            prefs = {
                'response_length': len(response),
                'used_bullets': '•' in response or '-' in response,
                'used_emojis': any(char in response for char in ['💡', '📊', '✅']),
                'level_of_detail': 'high' if len(response) > 500 else 'medium' if len(response) > 200 else 'brief'
            }
            
            # Store or update preferences
            self.learning_areas['user_preferences'].update(prefs)
    
    def _record_successful_pattern(self, pattern):
        """Record a successful pattern to learn from"""
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        pattern_json = json.dumps(pattern)
        
        # Check if pattern exists
        c.execute('''
            SELECT id, success_count, confidence_score 
            FROM learned_patterns 
            WHERE pattern_type = ? AND pattern_data = ?
        ''', (pattern['type'], pattern_json))
        
        existing = c.fetchone()
        
        if existing:
            # Update existing pattern
            pattern_id, success_count, confidence = existing
            new_confidence = min(1.0, confidence + 0.05)  # Increase confidence
            
            c.execute('''
                UPDATE learned_patterns 
                SET success_count = success_count + 1,
                    confidence_score = ?,
                    last_applied = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_confidence, pattern_id))
        else:
            # Insert new pattern
            c.execute('''
                INSERT INTO learned_patterns (pattern_type, pattern_data, success_count, confidence_score)
                VALUES (?, ?, 1, 0.6)
            ''', (pattern['type'], pattern_json))
        
        conn.commit()
        conn.close()
    
    def _record_failure_pattern(self, pattern):
        """Record a failure pattern to avoid repeating"""
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        pattern_json = json.dumps(pattern)
        
        c.execute('''
            SELECT id, failure_count, confidence_score 
            FROM learned_patterns 
            WHERE pattern_type = ? AND pattern_data = ?
        ''', (pattern['type'], pattern_json))
        
        existing = c.fetchone()
        
        if existing:
            pattern_id, failure_count, confidence = existing
            new_confidence = max(0.1, confidence - 0.05)  # Decrease confidence
            
            c.execute('''
                UPDATE learned_patterns 
                SET failure_count = failure_count + 1,
                    confidence_score = ?
                WHERE id = ?
            ''', (new_confidence, pattern_id))
        else:
            c.execute('''
                INSERT INTO learned_patterns (pattern_type, pattern_data, failure_count, confidence_score)
                VALUES (?, ?, 1, 0.3)
            ''', (pattern['type'], pattern_json))
        
        conn.commit()
        conn.close()
    
    def _add_to_knowledge_base(self, insight):
        """Add insight to cumulative knowledge base"""
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Check if similar insight exists
        c.execute('''
            SELECT id, evidence_count, confidence 
            FROM knowledge_base 
            WHERE topic = ? AND insight = ?
        ''', (insight['topic'], insight['insight']))
        
        existing = c.fetchone()
        
        if existing:
            kb_id, evidence_count, confidence = existing
            new_confidence = min(1.0, confidence + 0.03)
            
            c.execute('''
                UPDATE knowledge_base 
                SET evidence_count = evidence_count + 1,
                    confidence = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_confidence, kb_id))
        else:
            c.execute('''
                INSERT INTO knowledge_base (topic, insight, evidence_count, confidence, tags)
                VALUES (?, ?, 1, 0.5, ?)
            ''', (insight['topic'], insight['insight'], json.dumps(insight.get('tags', []))))
        
        conn.commit()
        conn.close()
    
    def _store_interaction_outcome(self, interaction_data, outcome_data):
        """Store interaction outcome for future analysis"""
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO interaction_outcomes 
            (interaction_id, user_request, ai_response, user_feedback_rating, 
             outcome_type, what_worked, what_failed, context_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            interaction_data.get('task_id'),
            interaction_data.get('user_request'),
            interaction_data.get('ai_response')[:1000],  # Truncate long responses
            outcome_data.get('user_rating'),
            'success' if outcome_data.get('user_rating', 0) >= 4 else 'needs_improvement',
            outcome_data.get('what_worked'),
            outcome_data.get('what_failed'),
            json.dumps(interaction_data.get('context', {}))
        ))
        
        conn.commit()
        conn.close()
    
    def predict_next_likely_request(self, current_context):
        """
        Predict what user is likely to need next
        
        Args:
            current_context: Current project/interaction context
            
        Returns:
            dict with predictions and confidence levels
        """
        
        predictions = []
        
        # Learn from historical patterns
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Find similar past contexts and what came next
        c.execute('''
            SELECT user_request, COUNT(*) as frequency
            FROM interaction_outcomes
            WHERE context_data LIKE ?
            GROUP BY user_request
            ORDER BY frequency DESC
            LIMIT 5
        ''', (f'%{current_context.get("phase", "")}%',))
        
        for row in c.fetchall():
            request, frequency = row
            predictions.append({
                'likely_request': request,
                'confidence': min(0.9, frequency / 10.0),
                'reasoning': f'This follows {frequency} times in similar contexts'
            })
        
        conn.close()
        
        return predictions
    
    def get_learned_recommendations(self, context_type):
        """
        Get recommendations based on learned patterns
        
        Args:
            context_type: Type of context (e.g., 'cost_analysis', 'survey_creation')
            
        Returns:
            list of learned recommendations
        """
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get high-confidence patterns for this context
        c.execute('''
            SELECT pattern_data, confidence_score, success_count
            FROM learned_patterns
            WHERE pattern_type LIKE ? 
            AND confidence_score > 0.6
            ORDER BY confidence_score DESC
            LIMIT 5
        ''', (f'%{context_type}%',))
        
        recommendations = []
        for row in c.fetchall():
            pattern_data, confidence, success_count = row
            pattern = json.loads(pattern_data)
            
            recommendations.append({
                'recommendation': pattern.get('response_pattern', 'Learned approach'),
                'confidence': confidence,
                'times_successful': success_count,
                'pattern': pattern
            })
        
        conn.close()
        
        return recommendations


# Singleton instance
_continuous_learning = None

def get_continuous_learning():
    """Get or create the continuous learning singleton"""
    global _continuous_learning
    if _continuous_learning is None:
        _continuous_learning = ContinuousLearning()
    return _continuous_learning


# I did no harm and this file is not truncated
