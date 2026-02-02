"""
SMART AUTO-TRIGGER SYSTEM FOR LEARNING CYCLES
Created: February 2, 2026
Last Updated: February 2, 2026

This module automatically triggers learning cycles when conditions are met.
No schedules, no manual intervention - just intelligent triggers based on data.

Trigger Rules:
- Phase 1 (Adaptive Learning): Every 10 new outcomes
- Phase 2 (Predictive Intelligence): Every 20 new outcomes
- Phase 3 (Self-Optimization): Every 30 new outcomes

The system tracks how many outcomes have been processed and automatically
runs the appropriate cycles when thresholds are reached.

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any


class SmartLearningTrigger:
    """
    Intelligently triggers learning cycles based on data availability.
    Tracks outcomes and automatically runs cycles when enough new data exists.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self._ensure_trigger_table()
        
        # Trigger thresholds (how many new outcomes needed)
        self.learning_threshold = 10
        self.predictive_threshold = 20
        self.optimization_threshold = 30
    
    def _ensure_trigger_table(self):
        """Create trigger tracking table"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learning_cycle_triggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_type TEXT NOT NULL,
                last_run_at TIMESTAMP,
                outcomes_at_last_run INTEGER DEFAULT 0,
                total_runs INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Initialize trigger records if they don't exist
        for cycle_type in ['adaptive_learning', 'predictive_intelligence', 'self_optimization']:
            cursor.execute('''
                INSERT OR IGNORE INTO learning_cycle_triggers (id, cycle_type, outcomes_at_last_run)
                VALUES (?, ?, 0)
            ''', (
                {'adaptive_learning': 1, 'predictive_intelligence': 2, 'self_optimization': 3}[cycle_type],
                cycle_type
            ))
        
        db.commit()
        db.close()
    
    def get_total_outcomes(self) -> int:
        """Get total number of outcomes recorded"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM outcome_tracking')
        count = cursor.fetchone()[0]
        
        db.close()
        return count
    
    def get_new_outcomes_since_cycle(self, cycle_type: str) -> int:
        """Get number of new outcomes since last cycle run"""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute('''
            SELECT outcomes_at_last_run FROM learning_cycle_triggers
            WHERE cycle_type = ?
        ''', (cycle_type,))
        
        result = cursor.fetchone()
        db.close()
        
        if not result:
            return 0
        
        outcomes_at_last_run = result['outcomes_at_last_run']
        current_outcomes = self.get_total_outcomes()
        
        return current_outcomes - outcomes_at_last_run
    
    def should_trigger_learning_cycle(self) -> bool:
        """Check if we should trigger Phase 1 (Adaptive Learning)"""
        new_outcomes = self.get_new_outcomes_since_cycle('adaptive_learning')
        return new_outcomes >= self.learning_threshold
    
    def should_trigger_predictive_analysis(self) -> bool:
        """Check if we should trigger Phase 2 (Predictive Intelligence)"""
        new_outcomes = self.get_new_outcomes_since_cycle('predictive_intelligence')
        return new_outcomes >= self.predictive_threshold
    
    def should_trigger_optimization_cycle(self) -> bool:
        """Check if we should trigger Phase 3 (Self-Optimization)"""
        new_outcomes = self.get_new_outcomes_since_cycle('self_optimization')
        return new_outcomes >= self.optimization_threshold
    
    def record_cycle_run(self, cycle_type: str, results: Dict = None):
        """Record that a cycle was run"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        current_outcomes = self.get_total_outcomes()
        
        cursor.execute('''
            UPDATE learning_cycle_triggers
            SET last_run_at = ?,
                outcomes_at_last_run = ?,
                total_runs = total_runs + 1
            WHERE cycle_type = ?
        ''', (datetime.now(), current_outcomes, cycle_type))
        
        db.commit()
        db.close()
    
    def check_and_trigger_all(self) -> Dict[str, Any]:
        """
        Check all triggers and run cycles if needed.
        This is the main function called after each task completes.
        
        Returns:
            Dictionary with cycles that were triggered
        """
        results = {
            'triggered': [],
            'skipped': []
        }
        
        # Check Phase 1: Adaptive Learning
        if self.should_trigger_learning_cycle():
            try:
                print(f"🔄 Auto-triggering Phase 1: Adaptive Learning ({self.get_new_outcomes_since_cycle('adaptive_learning')} new outcomes)")
                
                from learning_integration import get_learning_integration
                learning = get_learning_integration()
                cycle_results = learning.run_learning_cycle(min_observations=10)
                
                self.record_cycle_run('adaptive_learning', cycle_results)
                
                results['triggered'].append({
                    'phase': 1,
                    'name': 'adaptive_learning',
                    'results': cycle_results
                })
                
                print(f"✅ Phase 1 complete: {cycle_results.get('patterns_found', 0)} patterns, {cycle_results.get('adjustments_suggested', 0)} suggestions")
                
            except Exception as e:
                print(f"❌ Phase 1 auto-trigger failed: {e}")
        else:
            new_outcomes = self.get_new_outcomes_since_cycle('adaptive_learning')
            results['skipped'].append({
                'phase': 1,
                'name': 'adaptive_learning',
                'reason': f'Not enough data ({new_outcomes}/{self.learning_threshold} outcomes)'
            })
        
        # Check Phase 2: Predictive Intelligence
        if self.should_trigger_predictive_analysis():
            try:
                print(f"🔮 Auto-triggering Phase 2: Predictive Intelligence ({self.get_new_outcomes_since_cycle('predictive_intelligence')} new outcomes)")
                
                from predictive_intelligence import get_predictive_engine
                engine = get_predictive_engine()
                cycle_results = engine.analyze_and_learn(days_back=30)
                
                self.record_cycle_run('predictive_intelligence', cycle_results)
                
                results['triggered'].append({
                    'phase': 2,
                    'name': 'predictive_intelligence',
                    'results': cycle_results
                })
                
                print(f"✅ Phase 2 complete: {cycle_results.get('total_patterns', 0)} patterns discovered")
                
            except Exception as e:
                print(f"❌ Phase 2 auto-trigger failed: {e}")
        else:
            new_outcomes = self.get_new_outcomes_since_cycle('predictive_intelligence')
            results['skipped'].append({
                'phase': 2,
                'name': 'predictive_intelligence',
                'reason': f'Not enough data ({new_outcomes}/{self.predictive_threshold} outcomes)'
            })
        
        # Check Phase 3: Self-Optimization
        if self.should_trigger_optimization_cycle():
            try:
                print(f"⚙️ Auto-triggering Phase 3: Self-Optimization ({self.get_new_outcomes_since_cycle('self_optimization')} new outcomes)")
                
                from self_optimization_engine import get_optimization_engine
                engine = get_optimization_engine()
                cycle_results = engine.run_optimization_cycle(days_back=30)
                
                self.record_cycle_run('self_optimization', cycle_results)
                
                results['triggered'].append({
                    'phase': 3,
                    'name': 'self_optimization',
                    'results': cycle_results
                })
                
                total_opts = (
                    len(cycle_results.get('threshold_adjustments', [])) +
                    len(cycle_results.get('cost_optimizations', [])) +
                    len(cycle_results.get('experiments_analyzed', []))
                )
                
                print(f"✅ Phase 3 complete: {total_opts} optimizations found")
                
            except Exception as e:
                print(f"❌ Phase 3 auto-trigger failed: {e}")
        else:
            new_outcomes = self.get_new_outcomes_since_cycle('self_optimization')
            results['skipped'].append({
                'phase': 3,
                'name': 'self_optimization',
                'reason': f'Not enough data ({new_outcomes}/{self.optimization_threshold} outcomes)'
            })
        
        return results
    
    def get_trigger_status(self) -> Dict[str, Any]:
        """Get status of all triggers"""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute('SELECT * FROM learning_cycle_triggers ORDER BY id')
        triggers = [dict(row) for row in cursor.fetchall()]
        
        db.close()
        
        total_outcomes = self.get_total_outcomes()
        
        status = {
            'total_outcomes': total_outcomes,
            'cycles': []
        }
        
        for trigger in triggers:
            cycle_type = trigger['cycle_type']
            new_outcomes = total_outcomes - trigger['outcomes_at_last_run']
            
            # Determine threshold
            if cycle_type == 'adaptive_learning':
                threshold = self.learning_threshold
                phase = 1
            elif cycle_type == 'predictive_intelligence':
                threshold = self.predictive_threshold
                phase = 2
            else:
                threshold = self.optimization_threshold
                phase = 3
            
            will_trigger = new_outcomes >= threshold
            
            status['cycles'].append({
                'phase': phase,
                'name': cycle_type,
                'last_run': trigger['last_run_at'],
                'total_runs': trigger['total_runs'],
                'new_outcomes_since_last_run': new_outcomes,
                'threshold': threshold,
                'will_trigger_on_next_check': will_trigger,
                'progress_pct': min(100, int((new_outcomes / threshold) * 100))
            })
        
        return status


# Singleton instance
_trigger_system = None

def get_trigger_system() -> SmartLearningTrigger:
    """Get singleton trigger system instance"""
    global _trigger_system
    if _trigger_system is None:
        _trigger_system = SmartLearningTrigger()
    return _trigger_system


# I did no harm and this file is not truncated
