"""
ADAPTIVE LEARNING ENGINE - Phase 1
Created: February 2, 2026
Last Updated: February 2, 2026

This module implements true learning loops for the AI Swarm Orchestrator.
It tracks task outcomes, identifies patterns, and automatically adjusts
system behavior to improve performance over time.

CRITICAL: This is a NEW module that integrates with existing code WITHOUT
modifying any existing functionality (Do No Harm principle).

Integration Points:
- Called AFTER tasks complete to record outcomes
- Provides learned patterns to orchestrator for better routing
- Suggests automatic adjustments (requires approval initially)

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import statistics


class OutcomeTracker:
    """
    Tracks task outcomes with full context to enable learning.
    Records what worked, what didn't, and why.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create learning tables if they don't exist (safe to call repeatedly)"""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Phase 1: Outcome tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS outcome_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                ai_used TEXT NOT NULL,
                task_type TEXT,
                task_context TEXT,
                user_request_length INTEGER,
                success_score REAL DEFAULT 0.5,
                user_feedback_rating INTEGER,
                execution_time_seconds REAL,
                tokens_used INTEGER,
                cost_usd REAL,
                consensus_enabled BOOLEAN,
                consensus_score REAL,
                knowledge_base_used BOOLEAN,
                specialist_used TEXT,
                escalated_to_opus BOOLEAN DEFAULT 0,
                learned_from BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # Learned patterns table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                pattern_description TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                supporting_evidence INTEGER DEFAULT 1,
                last_validated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                times_applied INTEGER DEFAULT 0,
                times_successful INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # Behavior adjustments log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS behavior_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                adjustment_type TEXT NOT NULL,
                parameter_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT NOT NULL,
                reason TEXT NOT NULL,
                pattern_id INTEGER,
                approved BOOLEAN DEFAULT 0,
                approved_by TEXT,
                approved_at TIMESTAMP,
                applied BOOLEAN DEFAULT 0,
                applied_at TIMESTAMP,
                reverted BOOLEAN DEFAULT 0,
                reverted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pattern_id) REFERENCES learned_patterns(id)
            )
        ''')
        
        # Optimization history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS optimization_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                optimization_type TEXT NOT NULL,
                description TEXT,
                baseline_metrics TEXT,
                modified_metrics TEXT,
                improvement_percentage REAL,
                kept_change BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')
        
        db.commit()
        db.close()
    
    def record_outcome(self, task_data: Dict[str, Any]) -> int:
        """
        Record a task outcome for learning.
        
        Args:
            task_data: Dictionary with keys:
                - task_id: Original task ID (optional)
                - ai_used: Which AI handled the task
                - task_type: Classification of task
                - task_context: Relevant context (industry, complexity, etc.)
                - execution_time: Time taken
                - user_feedback_rating: User rating if available
                - consensus_score: Agreement score if consensus used
                - etc.
        
        Returns:
            outcome_id: ID of the recorded outcome
        """
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        # Calculate success score (0.0 to 1.0)
        success_score = self._calculate_success_score(task_data)
        
        cursor.execute('''
            INSERT INTO outcome_tracking (
                task_id, ai_used, task_type, task_context,
                user_request_length, success_score, user_feedback_rating,
                execution_time_seconds, tokens_used, cost_usd,
                consensus_enabled, consensus_score, knowledge_base_used,
                specialist_used, escalated_to_opus, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_data.get('task_id'),
            task_data.get('ai_used', 'claude-sonnet-4'),
            task_data.get('task_type', 'general'),
            json.dumps(task_data.get('task_context', {})),
            task_data.get('user_request_length', 0),
            success_score,
            task_data.get('user_feedback_rating'),
            task_data.get('execution_time_seconds', 0),
            task_data.get('tokens_used', 0),
            task_data.get('cost_usd', 0),
            task_data.get('consensus_enabled', False),
            task_data.get('consensus_score'),
            task_data.get('knowledge_base_used', False),
            task_data.get('specialist_used'),
            task_data.get('escalated_to_opus', False),
            json.dumps(task_data.get('metadata', {}))
        ))
        
        outcome_id = cursor.lastrowid
        db.commit()
        db.close()
        
        return outcome_id
    
    def _calculate_success_score(self, task_data: Dict[str, Any]) -> float:
        """
        Calculate a success score (0.0 to 1.0) from multiple factors.
        This is a composite metric that combines:
        - User feedback rating (if available)
        - Consensus score (if available)
        - Execution time (fast is good)
        - Whether task completed without errors
        """
        score_components = []
        
        # User feedback (weight: 0.5)
        if task_data.get('user_feedback_rating'):
            feedback_normalized = task_data['user_feedback_rating'] / 5.0
            score_components.append(('feedback', feedback_normalized, 0.5))
        
        # Consensus score (weight: 0.3)
        if task_data.get('consensus_score'):
            score_components.append(('consensus', task_data['consensus_score'], 0.3))
        
        # Speed score (weight: 0.2) - faster is better, up to a point
        if task_data.get('execution_time_seconds'):
            # Good: under 5 seconds, Acceptable: under 15, Slow: over 15
            exec_time = task_data['execution_time_seconds']
            if exec_time < 5:
                speed_score = 1.0
            elif exec_time < 15:
                speed_score = 0.7
            else:
                speed_score = 0.4
            score_components.append(('speed', speed_score, 0.2))
        
        # Calculate weighted average
        if score_components:
            total_weight = sum(w for _, _, w in score_components)
            weighted_sum = sum(score * weight for _, score, weight in score_components)
            return weighted_sum / total_weight
        
        # Default neutral score if no data
        return 0.5
    
    def get_outcomes_for_analysis(self, 
                                   min_observations: int = 10,
                                   days_back: int = 30) -> List[Dict]:
        """
        Get recent outcomes for pattern analysis.
        
        Args:
            min_observations: Minimum number of outcomes needed
            days_back: How many days back to look
            
        Returns:
            List of outcome dictionaries
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        cursor.execute('''
            SELECT * FROM outcome_tracking
            WHERE created_at >= ?
            AND learned_from = 0
            ORDER BY created_at DESC
        ''', (cutoff_date.isoformat(),))
        
        outcomes = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        return outcomes
    
    def mark_outcomes_learned(self, outcome_ids: List[int]):
        """Mark outcomes as having been learned from"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        placeholders = ','.join('?' * len(outcome_ids))
        cursor.execute(f'''
            UPDATE outcome_tracking
            SET learned_from = 1
            WHERE id IN ({placeholders})
        ''', outcome_ids)
        
        db.commit()
        db.close()


class PatternRecognizer:
    """
    Analyzes outcomes to identify patterns.
    Discovers what combinations of factors lead to success.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self.min_confidence = 0.75  # 75% confidence threshold
        self.min_observations = 10   # Need 10+ observations
    
    def analyze_patterns(self, outcomes: List[Dict]) -> List[Dict[str, Any]]:
        """
        Analyze outcomes and identify patterns.
        
        Returns:
            List of discovered patterns with confidence scores
        """
        if len(outcomes) < self.min_observations:
            return []
        
        patterns = []
        
        # Pattern 1: Which AI works best for which task types?
        ai_performance_patterns = self._analyze_ai_performance(outcomes)
        patterns.extend(ai_performance_patterns)
        
        # Pattern 2: Does consensus actually improve results?
        consensus_patterns = self._analyze_consensus_value(outcomes)
        patterns.extend(consensus_patterns)
        
        # Pattern 3: When should we escalate to Opus?
        escalation_patterns = self._analyze_escalation_effectiveness(outcomes)
        patterns.extend(escalation_patterns)
        
        # Pattern 4: Does knowledge base usage correlate with success?
        kb_patterns = self._analyze_kb_correlation(outcomes)
        patterns.extend(kb_patterns)
        
        # Pattern 5: Specialist effectiveness
        specialist_patterns = self._analyze_specialist_performance(outcomes)
        patterns.extend(specialist_patterns)
        
        return patterns
    
    def _analyze_ai_performance(self, outcomes: List[Dict]) -> List[Dict]:
        """Analyze which AI performs best for different task types"""
        patterns = []
        
        # Group by task_type and ai_used
        performance_by_type = defaultdict(lambda: defaultdict(list))
        
        for outcome in outcomes:
            task_type = outcome.get('task_type', 'general')
            ai_used = outcome.get('ai_used', 'unknown')
            success_score = outcome.get('success_score', 0.5)
            
            performance_by_type[task_type][ai_used].append(success_score)
        
        # Analyze each task type
        for task_type, ai_scores in performance_by_type.items():
            if len(ai_scores) < 2:  # Need multiple AIs to compare
                continue
            
            # Calculate average performance for each AI
            ai_averages = {}
            for ai, scores in ai_scores.items():
                if len(scores) >= 3:  # Need at least 3 observations
                    ai_averages[ai] = statistics.mean(scores)
            
            if len(ai_averages) >= 2:
                # Find best performer
                best_ai = max(ai_averages.items(), key=lambda x: x[1])
                worst_ai = min(ai_averages.items(), key=lambda x: x[1])
                
                performance_diff = best_ai[1] - worst_ai[1]
                
                # If difference is significant (>10%), create pattern
                if performance_diff > 0.10:
                    confidence = min(0.99, 0.60 + (performance_diff * 2))
                    
                    patterns.append({
                        'type': 'ai_performance',
                        'description': f'For {task_type} tasks, {best_ai[0]} outperforms {worst_ai[0]} by {performance_diff*100:.1f}%',
                        'recommendation': f'Route {task_type} tasks to {best_ai[0]}',
                        'confidence': confidence,
                        'evidence_count': len(ai_scores[best_ai[0]]),
                        'metadata': {
                            'task_type': task_type,
                            'best_ai': best_ai[0],
                            'best_score': best_ai[1],
                            'worst_ai': worst_ai[0],
                            'worst_score': worst_ai[1]
                        }
                    })
        
        return patterns
    
    def _analyze_consensus_value(self, outcomes: List[Dict]) -> List[Dict]:
        """Analyze whether consensus validation actually improves results"""
        patterns = []
        
        with_consensus = [o for o in outcomes if o.get('consensus_enabled')]
        without_consensus = [o for o in outcomes if not o.get('consensus_enabled')]
        
        if len(with_consensus) >= 10 and len(without_consensus) >= 10:
            avg_with = statistics.mean([o.get('success_score', 0.5) for o in with_consensus])
            avg_without = statistics.mean([o.get('success_score', 0.5) for o in without_consensus])
            
            difference = avg_with - avg_without
            
            if abs(difference) > 0.05:  # 5% difference threshold
                if difference > 0:
                    description = f'Consensus validation improves outcomes by {difference*100:.1f}%'
                    recommendation = 'Enable consensus for more tasks'
                else:
                    description = f'Consensus validation reduces outcomes by {abs(difference)*100:.1f}% (overhead not worth it)'
                    recommendation = 'Reduce consensus usage, only for critical tasks'
                
                confidence = min(0.95, 0.60 + abs(difference))
                
                patterns.append({
                    'type': 'consensus_value',
                    'description': description,
                    'recommendation': recommendation,
                    'confidence': confidence,
                    'evidence_count': len(with_consensus) + len(without_consensus),
                    'metadata': {
                        'avg_with_consensus': avg_with,
                        'avg_without_consensus': avg_without,
                        'improvement': difference
                    }
                })
        
        return patterns
    
    def _analyze_escalation_effectiveness(self, outcomes: List[Dict]) -> List[Dict]:
        """Analyze when escalation to Opus is worth it"""
        patterns = []
        
        escalated = [o for o in outcomes if o.get('escalated_to_opus')]
        not_escalated = [o for o in outcomes if not o.get('escalated_to_opus')]
        
        if len(escalated) >= 5:  # Need decent sample
            avg_escalated = statistics.mean([o.get('success_score', 0.5) for o in escalated])
            
            # What kinds of tasks were escalated?
            escalated_contexts = [json.loads(o.get('task_context', '{}')) for o in escalated]
            
            # If escalated tasks have high success, escalation is working
            if avg_escalated > 0.75:
                patterns.append({
                    'type': 'escalation_effectiveness',
                    'description': f'Escalation to Opus achieves {avg_escalated*100:.1f}% success rate',
                    'recommendation': 'Current escalation criteria working well',
                    'confidence': 0.80,
                    'evidence_count': len(escalated),
                    'metadata': {
                        'avg_success': avg_escalated,
                        'escalation_count': len(escalated)
                    }
                })
        
        return patterns
    
    def _analyze_kb_correlation(self, outcomes: List[Dict]) -> List[Dict]:
        """Analyze knowledge base usage correlation with success"""
        patterns = []
        
        with_kb = [o for o in outcomes if o.get('knowledge_base_used')]
        without_kb = [o for o in outcomes if not o.get('knowledge_base_used')]
        
        if len(with_kb) >= 10 and len(without_kb) >= 10:
            avg_with_kb = statistics.mean([o.get('success_score', 0.5) for o in with_kb])
            avg_without_kb = statistics.mean([o.get('success_score', 0.5) for o in without_kb])
            
            difference = avg_with_kb - avg_without_kb
            
            if difference > 0.10:  # 10% improvement
                patterns.append({
                    'type': 'knowledge_base_value',
                    'description': f'Knowledge base usage improves outcomes by {difference*100:.1f}%',
                    'recommendation': 'Increase knowledge base usage in routing logic',
                    'confidence': 0.85,
                    'evidence_count': len(with_kb) + len(without_kb),
                    'metadata': {
                        'avg_with_kb': avg_with_kb,
                        'avg_without_kb': avg_without_kb,
                        'improvement': difference
                    }
                })
        
        return patterns
    
    def _analyze_specialist_performance(self, outcomes: List[Dict]) -> List[Dict]:
        """Analyze which specialists perform well"""
        patterns = []
        
        specialist_outcomes = [o for o in outcomes if o.get('specialist_used')]
        
        if len(specialist_outcomes) >= 10:
            by_specialist = defaultdict(list)
            
            for outcome in specialist_outcomes:
                specialist = outcome.get('specialist_used')
                success = outcome.get('success_score', 0.5)
                by_specialist[specialist].append(success)
            
            for specialist, scores in by_specialist.items():
                if len(scores) >= 5:
                    avg_score = statistics.mean(scores)
                    
                    if avg_score > 0.75:
                        patterns.append({
                            'type': 'specialist_performance',
                            'description': f'{specialist} specialist achieves {avg_score*100:.1f}% success rate',
                            'recommendation': f'Continue using {specialist} for appropriate tasks',
                            'confidence': 0.80,
                            'evidence_count': len(scores),
                            'metadata': {
                                'specialist': specialist,
                                'avg_success': avg_score,
                                'usage_count': len(scores)
                            }
                        })
                    elif avg_score < 0.50:
                        patterns.append({
                            'type': 'specialist_performance',
                            'description': f'{specialist} specialist only achieves {avg_score*100:.1f}% success rate',
                            'recommendation': f'Review {specialist} usage - may need reconfiguration',
                            'confidence': 0.75,
                            'evidence_count': len(scores),
                            'metadata': {
                                'specialist': specialist,
                                'avg_success': avg_score,
                                'usage_count': len(scores)
                            }
                        })
        
        return patterns
    
    def save_patterns(self, patterns: List[Dict]):
        """Save discovered patterns to database"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        for pattern in patterns:
            # Check if similar pattern already exists
            cursor.execute('''
                SELECT id, supporting_evidence, confidence
                FROM learned_patterns
                WHERE pattern_type = ? AND pattern_description = ?
                AND active = 1
            ''', (pattern['type'], pattern['description']))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing pattern
                pattern_id, old_evidence, old_confidence = existing
                new_evidence = old_evidence + pattern['evidence_count']
                new_confidence = max(old_confidence, pattern['confidence'])
                
                cursor.execute('''
                    UPDATE learned_patterns
                    SET supporting_evidence = ?,
                        confidence = ?,
                        last_validated = ?
                    WHERE id = ?
                ''', (new_evidence, new_confidence, datetime.now(), pattern_id))
            else:
                # Insert new pattern
                cursor.execute('''
                    INSERT INTO learned_patterns (
                        pattern_type, pattern_description, confidence,
                        supporting_evidence, metadata
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    pattern['type'],
                    pattern['description'],
                    pattern['confidence'],
                    pattern['evidence_count'],
                    json.dumps(pattern.get('metadata', {}))
                ))
        
        db.commit()
        db.close()


class BehaviorModifier:
    """
    Suggests and applies behavior modifications based on learned patterns.
    All modifications are logged and can be reverted.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
    
    def suggest_adjustments(self, patterns: List[Dict]) -> List[Dict]:
        """
        Based on learned patterns, suggest configuration adjustments.
        
        Returns:
            List of suggested adjustments
        """
        suggestions = []
        
        for pattern in patterns:
            # Only suggest for high-confidence patterns
            if pattern['confidence'] < 0.75:
                continue
            
            adjustment = self._pattern_to_adjustment(pattern)
            if adjustment:
                suggestions.append(adjustment)
        
        return suggestions
    
    def _pattern_to_adjustment(self, pattern: Dict) -> Optional[Dict]:
        """Convert a pattern into a concrete adjustment suggestion"""
        
        pattern_type = pattern['type']
        
        if pattern_type == 'ai_performance':
            # Suggest routing change
            metadata = pattern.get('metadata', {})
            return {
                'type': 'routing',
                'parameter': 'preferred_ai_for_task_type',
                'current_value': 'default',
                'suggested_value': metadata.get('best_ai'),
                'reason': pattern['description'],
                'pattern_id': None,  # Will be set when saved
                'requires_approval': True
            }
        
        elif pattern_type == 'consensus_value':
            metadata = pattern.get('metadata', {})
            improvement = metadata.get('improvement', 0)
            
            if improvement > 0.10:  # Consensus helps
                return {
                    'type': 'threshold',
                    'parameter': 'consensus_threshold',
                    'current_value': '0.85',
                    'suggested_value': '0.80',  # Lower threshold = more consensus use
                    'reason': pattern['description'],
                    'pattern_id': None,
                    'requires_approval': True
                }
            else:  # Consensus doesn't help
                return {
                    'type': 'threshold',
                    'parameter': 'consensus_threshold',
                    'current_value': '0.85',
                    'suggested_value': '0.90',  # Higher threshold = less consensus use
                    'reason': pattern['description'],
                    'pattern_id': None,
                    'requires_approval': True
                }
        
        elif pattern_type == 'knowledge_base_value':
            return {
                'type': 'feature',
                'parameter': 'knowledge_base_priority',
                'current_value': 'normal',
                'suggested_value': 'high',
                'reason': pattern['description'],
                'pattern_id': None,
                'requires_approval': True
            }
        
        return None
    
    def log_adjustment(self, adjustment: Dict) -> int:
        """Log a suggested adjustment to database"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        cursor.execute('''
            INSERT INTO behavior_adjustments (
                adjustment_type, parameter_name, old_value,
                new_value, reason, pattern_id, approved
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            adjustment['type'],
            adjustment['parameter'],
            adjustment['current_value'],
            adjustment['suggested_value'],
            adjustment['reason'],
            adjustment.get('pattern_id'),
            0  # Not approved yet
        ))
        
        adjustment_id = cursor.lastrowid
        db.commit()
        db.close()
        
        return adjustment_id
    
    def get_pending_adjustments(self) -> List[Dict]:
        """Get all adjustments awaiting approval"""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute('''
            SELECT * FROM behavior_adjustments
            WHERE approved = 0 AND reverted = 0
            ORDER BY created_at DESC
        ''')
        
        adjustments = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        return adjustments


class AdaptiveLearningEngine:
    """
    Main orchestrator for the adaptive learning system.
    Coordinates outcome tracking, pattern recognition, and behavior modification.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self.outcome_tracker = OutcomeTracker(db_path)
        self.pattern_recognizer = PatternRecognizer(db_path)
        self.behavior_modifier = BehaviorModifier(db_path)
    
    def record_task_outcome(self, task_data: Dict[str, Any]) -> int:
        """
        Record outcome of a completed task.
        This is the main integration point - call this after each task.
        
        Args:
            task_data: Task information and outcomes
            
        Returns:
            outcome_id
        """
        return self.outcome_tracker.record_outcome(task_data)
    
    def run_learning_cycle(self, min_observations: int = 10) -> Dict[str, Any]:
        """
        Run a complete learning cycle:
        1. Gather recent outcomes
        2. Analyze for patterns
        3. Generate adjustment suggestions
        
        Args:
            min_observations: Minimum outcomes needed for analysis
            
        Returns:
            Dictionary with patterns found and suggestions made
        """
        print(f"🧠 Starting learning cycle...")
        
        # Step 1: Gather outcomes
        outcomes = self.outcome_tracker.get_outcomes_for_analysis(min_observations)
        
        if len(outcomes) < min_observations:
            return {
                'status': 'insufficient_data',
                'outcomes_available': len(outcomes),
                'outcomes_needed': min_observations,
                'patterns_found': [],
                'adjustments_suggested': []
            }
        
        print(f"📊 Analyzing {len(outcomes)} outcomes...")
        
        # Step 2: Recognize patterns
        patterns = self.pattern_recognizer.analyze_patterns(outcomes)
        high_confidence = [p for p in patterns if p['confidence'] >= 0.75]
        
        print(f"🔍 Found {len(patterns)} patterns ({len(high_confidence)} high-confidence)")
        
        # Step 3: Save patterns
        if patterns:
            self.pattern_recognizer.save_patterns(patterns)
        
        # Step 4: Generate adjustment suggestions
        suggestions = self.behavior_modifier.suggest_adjustments(high_confidence)
        
        print(f"💡 Generated {len(suggestions)} adjustment suggestions")
        
        # Step 5: Log suggestions
        suggestion_ids = []
        for suggestion in suggestions:
            adj_id = self.behavior_modifier.log_adjustment(suggestion)
            suggestion_ids.append(adj_id)
        
        # Step 6: Mark outcomes as learned
        outcome_ids = [o['id'] for o in outcomes]
        self.outcome_tracker.mark_outcomes_learned(outcome_ids)
        
        return {
            'status': 'success',
            'outcomes_analyzed': len(outcomes),
            'patterns_found': len(patterns),
            'high_confidence_patterns': len(high_confidence),
            'adjustments_suggested': len(suggestions),
            'patterns': patterns,
            'suggestions': suggestions,
            'suggestion_ids': suggestion_ids
        }
    
    def get_learning_report(self) -> Dict[str, Any]:
        """
        Generate a report on learning status.
        
        Returns:
            Report dictionary with current learning state
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Count outcomes
        cursor.execute('SELECT COUNT(*) as count FROM outcome_tracking')
        total_outcomes = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM outcome_tracking WHERE learned_from = 1')
        learned_outcomes = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM outcome_tracking WHERE learned_from = 0')
        pending_outcomes = cursor.fetchone()['count']
        
        # Count patterns
        cursor.execute('SELECT COUNT(*) as count FROM learned_patterns WHERE active = 1')
        active_patterns = cursor.fetchone()['count']
        
        cursor.execute('''
            SELECT pattern_type, COUNT(*) as count
            FROM learned_patterns
            WHERE active = 1
            GROUP BY pattern_type
        ''')
        patterns_by_type = {row['pattern_type']: row['count'] for row in cursor.fetchall()}
        
        # Count adjustments
        cursor.execute('SELECT COUNT(*) as count FROM behavior_adjustments WHERE approved = 0')
        pending_adjustments = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM behavior_adjustments WHERE approved = 1 AND applied = 1')
        applied_adjustments = cursor.fetchone()['count']
        
        # Get recent high-confidence patterns
        cursor.execute('''
            SELECT pattern_type, pattern_description, confidence, supporting_evidence
            FROM learned_patterns
            WHERE active = 1 AND confidence >= 0.75
            ORDER BY confidence DESC, supporting_evidence DESC
            LIMIT 10
        ''')
        top_patterns = [dict(row) for row in cursor.fetchall()]
        
        db.close()
        
        return {
            'total_outcomes': total_outcomes,
            'learned_outcomes': learned_outcomes,
            'pending_outcomes': pending_outcomes,
            'active_patterns': active_patterns,
            'patterns_by_type': patterns_by_type,
            'pending_adjustments': pending_adjustments,
            'applied_adjustments': applied_adjustments,
            'top_patterns': top_patterns,
            'learning_status': 'active' if pending_outcomes >= 10 else 'needs_more_data'
        }


# Convenience function for integration
def get_learning_engine(db_path='swarm_intelligence.db') -> AdaptiveLearningEngine:
    """Get the singleton learning engine instance"""
    return AdaptiveLearningEngine(db_path)


# I did no harm and this file is not truncated
