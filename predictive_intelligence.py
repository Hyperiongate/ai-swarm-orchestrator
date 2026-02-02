"""
PREDICTIVE INTELLIGENCE ENGINE - Phase 2
Created: February 2, 2026
Last Updated: February 2, 2026

This module implements predictive capabilities that anticipate user needs
and pre-stage resources before they're requested.

CRITICAL: This is Phase 2 of the learning system. It works alongside Phase 1
(Adaptive Learning) and uses the outcomes data collected there.

Features:
- User behavior pattern analysis
- Project phase prediction
- Proactive resource staging
- Smart next-step suggestions
- Context pre-loading

Integration: Safe to deploy - only makes predictions, doesn't change behavior
unless predictions are explicitly used by orchestrator.

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
import statistics


class UserBehaviorAnalyzer:
    """
    Analyzes user behavior patterns to predict future needs.
    Learns sequences like: "schedule request → implementation manual → employee survey"
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create predictive intelligence tables"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        # User behavior patterns table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_behavior_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'jim',
                pattern_type TEXT NOT NULL,
                pattern_description TEXT NOT NULL,
                sequence TEXT,
                frequency_per_week REAL DEFAULT 0,
                typical_time_of_day TEXT,
                confidence REAL DEFAULT 0.0,
                last_observed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                observation_count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # Project phase sequences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_phase_sequences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                industry TEXT,
                facility_type TEXT,
                phase_sequence TEXT NOT NULL,
                typical_duration_days INTEGER,
                success_rate REAL DEFAULT 0,
                observation_count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # Prediction accuracy tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prediction_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_type TEXT NOT NULL,
                prediction_made TEXT NOT NULL,
                prediction_confidence REAL,
                actual_outcome TEXT,
                was_accurate BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_at TIMESTAMP
            )
        ''')
        
        # Proactive suggestions tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS proactive_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion_type TEXT NOT NULL,
                suggestion_text TEXT NOT NULL,
                context TEXT,
                user_action TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acted_on_at TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        db.commit()
        db.close()
    
    def analyze_task_sequences(self, days_back: int = 30) -> List[Dict]:
        """
        Analyze sequences of tasks to find patterns.
        Example: "User typically does X, then Y, then Z"
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Get tasks with their types and timestamps
        cursor.execute('''
            SELECT task_type, created_at, task_context
            FROM outcome_tracking
            WHERE created_at >= ?
            ORDER BY created_at ASC
        ''', (cutoff_date.isoformat(),))
        
        tasks = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        if len(tasks) < 3:
            return []
        
        # Find sequences (2-task and 3-task patterns)
        sequences_2 = []
        sequences_3 = []
        
        for i in range(len(tasks) - 1):
            # 2-task sequences
            seq_2 = (tasks[i]['task_type'], tasks[i+1]['task_type'])
            sequences_2.append(seq_2)
            
            # 3-task sequences
            if i < len(tasks) - 2:
                seq_3 = (tasks[i]['task_type'], tasks[i+1]['task_type'], tasks[i+2]['task_type'])
                sequences_3.append(seq_3)
        
        # Count frequency of each sequence
        seq_2_counts = Counter(sequences_2)
        seq_3_counts = Counter(sequences_3)
        
        patterns = []
        
        # Analyze 2-task sequences
        for seq, count in seq_2_counts.items():
            if count >= 2:  # Seen at least twice
                confidence = min(0.95, 0.50 + (count * 0.10))
                patterns.append({
                    'type': 'task_sequence_2',
                    'sequence': list(seq),
                    'description': f"After {seq[0]}, user typically does {seq[1]}",
                    'frequency': count,
                    'confidence': confidence,
                    'prediction': f"Next likely task: {seq[1]}"
                })
        
        # Analyze 3-task sequences
        for seq, count in seq_3_counts.items():
            if count >= 2:
                confidence = min(0.95, 0.60 + (count * 0.10))
                patterns.append({
                    'type': 'task_sequence_3',
                    'sequence': list(seq),
                    'description': f"Typical workflow: {seq[0]} → {seq[1]} → {seq[2]}",
                    'frequency': count,
                    'confidence': confidence,
                    'prediction': f"After {seq[0]} and {seq[1]}, next is typically {seq[2]}"
                })
        
        return patterns
    
    def analyze_time_patterns(self, days_back: int = 30) -> List[Dict]:
        """
        Analyze when user typically does certain tasks.
        Example: "User always works on schedules in the morning"
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        cursor.execute('''
            SELECT task_type, created_at
            FROM outcome_tracking
            WHERE created_at >= ?
        ''', (cutoff_date.isoformat(),))
        
        tasks = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        if len(tasks) < 5:
            return []
        
        # Group by task type and time of day
        task_times = defaultdict(list)
        
        for task in tasks:
            try:
                dt = datetime.fromisoformat(task['created_at'])
                hour = dt.hour
                task_times[task['task_type']].append(hour)
            except:
                continue
        
        patterns = []
        
        for task_type, hours in task_times.items():
            if len(hours) < 3:
                continue
            
            avg_hour = statistics.mean(hours)
            
            # Determine time of day
            if 5 <= avg_hour < 12:
                time_of_day = 'morning'
            elif 12 <= avg_hour < 17:
                time_of_day = 'afternoon'
            elif 17 <= avg_hour < 21:
                time_of_day = 'evening'
            else:
                time_of_day = 'night'
            
            # Calculate consistency
            std_dev = statistics.stdev(hours) if len(hours) > 1 else 0
            consistency = max(0, 1.0 - (std_dev / 12))  # Lower std_dev = higher consistency
            
            if consistency > 0.5:  # Only report consistent patterns
                patterns.append({
                    'type': 'time_pattern',
                    'task_type': task_type,
                    'description': f"{task_type} tasks typically done in {time_of_day}",
                    'time_of_day': time_of_day,
                    'avg_hour': int(avg_hour),
                    'consistency': consistency,
                    'confidence': consistency,
                    'observation_count': len(hours)
                })
        
        return patterns
    
    def save_patterns(self, patterns: List[Dict]):
        """Save discovered patterns to database"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        for pattern in patterns:
            # Check if similar pattern exists
            cursor.execute('''
                SELECT id, observation_count, confidence
                FROM user_behavior_patterns
                WHERE pattern_type = ? AND pattern_description = ?
            ''', (pattern['type'], pattern['description']))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing pattern
                pattern_id, old_count, old_confidence = existing
                new_count = old_count + pattern.get('frequency', 1)
                new_confidence = max(old_confidence, pattern['confidence'])
                
                cursor.execute('''
                    UPDATE user_behavior_patterns
                    SET observation_count = ?,
                        confidence = ?,
                        last_observed = ?,
                        sequence = ?,
                        typical_time_of_day = ?
                    WHERE id = ?
                ''', (
                    new_count,
                    new_confidence,
                    datetime.now(),
                    json.dumps(pattern.get('sequence', [])),
                    pattern.get('time_of_day'),
                    pattern_id
                ))
            else:
                # Insert new pattern
                cursor.execute('''
                    INSERT INTO user_behavior_patterns (
                        pattern_type, pattern_description, sequence,
                        confidence, observation_count, typical_time_of_day,
                        metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    pattern['type'],
                    pattern['description'],
                    json.dumps(pattern.get('sequence', [])),
                    pattern['confidence'],
                    pattern.get('frequency', 1),
                    pattern.get('time_of_day'),
                    json.dumps({
                        'prediction': pattern.get('prediction'),
                        'avg_hour': pattern.get('avg_hour')
                    })
                ))
        
        db.commit()
        db.close()


class ProjectPhasePredictor:
    """
    Predicts what phase comes next in a project based on industry and history.
    Example: "Manufacturing projects typically go: Survey → Schedule Design → Implementation"
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
    
    def analyze_project_progressions(self) -> List[Dict]:
        """
        Analyze how projects typically progress through phases.
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Get all projects with their progression history
        cursor.execute('''
            SELECT project_id, industry, facility_type, project_phase,
                   status, created_at, updated_at
            FROM projects
            WHERE status IN ('active', 'completed')
            ORDER BY created_at ASC
        ''')
        
        projects = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        if len(projects) < 3:
            return []
        
        # Group by industry/facility type
        progressions = defaultdict(list)
        
        for project in projects:
            key = (project.get('industry', 'unknown'), project.get('facility_type', 'unknown'))
            progressions[key].append(project['project_phase'])
        
        patterns = []
        
        for (industry, facility_type), phases in progressions.items():
            if len(phases) < 2:
                continue
            
            # Find common sequences
            phase_counts = Counter(phases)
            most_common_phase = phase_counts.most_common(1)[0][0] if phase_counts else None
            
            if most_common_phase:
                patterns.append({
                    'industry': industry,
                    'facility_type': facility_type,
                    'common_phase': most_common_phase,
                    'observation_count': len(phases),
                    'confidence': min(0.95, 0.50 + (len(phases) * 0.10))
                })
        
        return patterns
    
    def predict_next_phase(self, current_phase: str, industry: str, facility_type: str) -> Optional[Dict]:
        """
        Predict what phase typically comes after the current phase.
        """
        # Common phase progressions (can be learned from data over time)
        typical_progressions = {
            'discovery': 'data_collection',
            'data_collection': 'analysis',
            'analysis': 'schedule_design',
            'schedule_design': 'implementation_planning',
            'implementation_planning': 'implementation',
            'implementation': 'monitoring',
            'monitoring': 'closeout'
        }
        
        next_phase = typical_progressions.get(current_phase.lower())
        
        if next_phase:
            return {
                'current_phase': current_phase,
                'predicted_next_phase': next_phase,
                'confidence': 0.75,
                'reasoning': f'Typical progression after {current_phase} is {next_phase}'
            }
        
        return None


class ResourcePreStager:
    """
    Pre-loads likely-needed resources based on predictions.
    Example: "Jim's working on schedule, pre-load normative data"
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
    
    def predict_needed_resources(self, current_context: Dict) -> List[Dict]:
        """
        Based on current context, predict what resources user will need next.
        
        Args:
            current_context: Current state (task_type, project_phase, industry, etc.)
            
        Returns:
            List of resources to pre-stage
        """
        task_type = current_context.get('task_type', '')
        project_phase = current_context.get('project_phase', '')
        industry = current_context.get('industry', '')
        
        resources = []
        
        # Rule-based predictions (will be learned from data over time)
        if task_type == 'schedule_design':
            resources.append({
                'resource_type': 'knowledge_base',
                'resource_name': 'normative_data',
                'reason': 'Schedule design typically needs normative comparison data',
                'confidence': 0.85,
                'priority': 'high'
            })
            resources.append({
                'resource_type': 'template',
                'resource_name': 'implementation_manual',
                'reason': 'Implementation manual typically follows schedule design',
                'confidence': 0.70,
                'priority': 'medium'
            })
        
        if task_type == 'analysis':
            resources.append({
                'resource_type': 'knowledge_base',
                'resource_name': 'survey_data',
                'reason': 'Analysis tasks often reference survey results',
                'confidence': 0.75,
                'priority': 'high'
            })
        
        if project_phase == 'implementation_planning':
            resources.append({
                'resource_type': 'template',
                'resource_name': 'employee_communication',
                'reason': 'Implementation requires employee communication materials',
                'confidence': 0.80,
                'priority': 'high'
            })
        
        if industry == 'manufacturing':
            resources.append({
                'resource_type': 'knowledge_base',
                'resource_name': 'manufacturing_best_practices',
                'reason': 'Manufacturing projects have industry-specific considerations',
                'confidence': 0.70,
                'priority': 'medium'
            })
        
        return resources


class ProactiveSuggestionEngine:
    """
    Generates proactive suggestions for next actions.
    Example: "Ready to draft employee communication email?"
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
    
    def generate_suggestions(self, current_context: Dict, recent_tasks: List[Dict]) -> List[Dict]:
        """
        Generate proactive suggestions based on context and recent activity.
        
        Args:
            current_context: Current state
            recent_tasks: List of recent task outcomes
            
        Returns:
            List of suggestions
        """
        suggestions = []
        
        if not recent_tasks:
            return suggestions
        
        last_task = recent_tasks[-1] if recent_tasks else None
        last_task_type = last_task.get('task_type', '') if last_task else ''
        
        # Suggestion rules (will be learned from acceptance patterns)
        if last_task_type == 'schedule_design':
            suggestions.append({
                'type': 'next_step',
                'suggestion': 'Ready to create an implementation manual for this schedule?',
                'action': 'create_implementation_manual',
                'confidence': 0.85,
                'context': 'Implementation manuals typically follow schedule creation'
            })
            suggestions.append({
                'type': 'next_step',
                'suggestion': 'Would you like to draft employee communication about the new schedule?',
                'action': 'draft_employee_communication',
                'confidence': 0.75,
                'context': 'Clear communication helps with schedule adoption'
            })
        
        if last_task_type == 'analysis':
            suggestions.append({
                'type': 'next_step',
                'suggestion': 'Ready to generate an executive summary of the findings?',
                'action': 'create_executive_summary',
                'confidence': 0.80,
                'context': 'Executive summaries help communicate analysis results'
            })
        
        if last_task_type == 'survey_creation':
            suggestions.append({
                'type': 'next_step',
                'suggestion': 'Need help planning survey distribution and timeline?',
                'action': 'plan_survey_distribution',
                'confidence': 0.70,
                'context': 'Survey distribution planning often follows survey creation'
            })
        
        # Check for incomplete workflows
        if len(recent_tasks) >= 2:
            task_types = [t.get('task_type', '') for t in recent_tasks[-3:]]
            
            # Detect: schedule created but no implementation manual yet
            if 'schedule_design' in task_types and 'manual_creation' not in task_types:
                suggestions.append({
                    'type': 'workflow_completion',
                    'suggestion': 'You created a schedule but haven\'t created an implementation manual yet. Ready to create one?',
                    'action': 'create_implementation_manual',
                    'confidence': 0.75,
                    'context': 'Completing the documentation workflow'
                })
        
        return suggestions
    
    def track_suggestion_outcome(self, suggestion_id: int, user_action: str):
        """Track whether user accepted/rejected a suggestion"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        cursor.execute('''
            UPDATE proactive_suggestions
            SET user_action = ?,
                acted_on_at = ?
            WHERE id = ?
        ''', (user_action, datetime.now(), suggestion_id))
        
        db.commit()
        db.close()


class PredictiveIntelligenceEngine:
    """
    Main orchestrator for predictive intelligence.
    Coordinates behavior analysis, predictions, and proactive suggestions.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self.behavior_analyzer = UserBehaviorAnalyzer(db_path)
        self.phase_predictor = ProjectPhasePredictor(db_path)
        self.resource_stager = ResourcePreStager(db_path)
        self.suggestion_engine = ProactiveSuggestionEngine(db_path)
    
    def analyze_and_learn(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Run complete predictive analysis.
        
        Returns:
            Dictionary with all discovered patterns and predictions
        """
        print(f"🔮 Running predictive intelligence analysis (last {days_back} days)...")
        
        # Analyze task sequences
        task_sequences = self.behavior_analyzer.analyze_task_sequences(days_back)
        print(f"   Found {len(task_sequences)} task sequence patterns")
        
        # Analyze time patterns
        time_patterns = self.behavior_analyzer.analyze_time_patterns(days_back)
        print(f"   Found {len(time_patterns)} time-based patterns")
        
        # Save patterns
        all_patterns = task_sequences + time_patterns
        if all_patterns:
            self.behavior_analyzer.save_patterns(all_patterns)
            print(f"   Saved {len(all_patterns)} patterns to database")
        
        # Analyze project progressions
        project_patterns = self.phase_predictor.analyze_project_progressions()
        print(f"   Found {len(project_patterns)} project progression patterns")
        
        return {
            'status': 'success',
            'task_sequences': task_sequences,
            'time_patterns': time_patterns,
            'project_patterns': project_patterns,
            'total_patterns': len(all_patterns) + len(project_patterns)
        }
    
    def get_predictions(self, current_context: Dict) -> Dict[str, Any]:
        """
        Get predictions for current context.
        
        Args:
            current_context: Current state (task_type, project_phase, etc.)
            
        Returns:
            Predictions and suggestions
        """
        predictions = {}
        
        # Predict next phase if in a project
        if current_context.get('project_phase'):
            next_phase = self.phase_predictor.predict_next_phase(
                current_context['project_phase'],
                current_context.get('industry', ''),
                current_context.get('facility_type', '')
            )
            if next_phase:
                predictions['next_phase'] = next_phase
        
        # Predict needed resources
        resources = self.resource_stager.predict_needed_resources(current_context)
        predictions['recommended_resources'] = resources
        
        # Get recent tasks for suggestion context
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute('''
            SELECT task_type, created_at
            FROM outcome_tracking
            ORDER BY created_at DESC
            LIMIT 5
        ''')
        
        recent_tasks = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        # Generate proactive suggestions
        suggestions = self.suggestion_engine.generate_suggestions(current_context, recent_tasks)
        predictions['suggestions'] = suggestions
        
        return predictions
    
    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive status of predictive intelligence"""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Count patterns
        cursor.execute('SELECT COUNT(*) as count FROM user_behavior_patterns')
        behavior_patterns = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM project_phase_sequences')
        phase_patterns = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM proactive_suggestions')
        total_suggestions = cursor.fetchone()['count']
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM proactive_suggestions
            WHERE user_action = 'accepted'
        ''')
        accepted_suggestions = cursor.fetchone()['count']
        
        # Get top patterns
        cursor.execute('''
            SELECT pattern_type, pattern_description, confidence, observation_count
            FROM user_behavior_patterns
            WHERE confidence >= 0.70
            ORDER BY confidence DESC, observation_count DESC
            LIMIT 5
        ''')
        top_patterns = [dict(row) for row in cursor.fetchall()]
        
        db.close()
        
        acceptance_rate = (accepted_suggestions / total_suggestions * 100) if total_suggestions > 0 else 0
        
        return {
            'behavior_patterns': behavior_patterns,
            'phase_patterns': phase_patterns,
            'total_suggestions_made': total_suggestions,
            'suggestions_accepted': accepted_suggestions,
            'acceptance_rate': round(acceptance_rate, 1),
            'top_patterns': top_patterns,
            'status': 'active' if behavior_patterns > 0 else 'needs_more_data'
        }


# Convenience function
def get_predictive_engine(db_path='swarm_intelligence.db') -> PredictiveIntelligenceEngine:
    """Get singleton instance of predictive engine"""
    return PredictiveIntelligenceEngine(db_path)


# I did no harm and this file is not truncated
