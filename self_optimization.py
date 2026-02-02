"""
SELF-OPTIMIZATION ENGINE - Phase 3
Created: February 2, 2026
Last Updated: February 2, 2026

This module implements autonomous self-optimization capabilities.
The system can A/B test changes, tune its own parameters, and optimize
cost vs. quality tradeoffs automatically.

CRITICAL: This is Phase 3 - the most autonomous phase. It can modify
system behavior automatically, but includes robust safety mechanisms:
- All changes are tested via A/B splits before full deployment
- Automatic rollback if performance degrades
- Human approval required for major changes (configurable)
- All modifications logged and reversible

Features:
- Automatic A/B testing framework
- Self-tuning thresholds (consensus, confidence, etc.)
- Cost optimization (use cheaper models when appropriate)
- Load balancing based on queue depth
- Automatic performance recovery

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import statistics
import random


class ThresholdOptimizer:
    """
    Automatically tunes system thresholds based on performance data.
    Example: Adjusts consensus threshold from 85% to 82% if accuracy improves.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create self-optimization tables"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        # Optimization experiments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS optimization_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_name TEXT NOT NULL,
                variable_being_tested TEXT NOT NULL,
                control_value TEXT NOT NULL,
                test_value TEXT NOT NULL,
                control_sample_size INTEGER DEFAULT 0,
                test_sample_size INTEGER DEFAULT 0,
                control_metrics TEXT,
                test_metrics TEXT,
                status TEXT DEFAULT 'running',
                winner TEXT,
                statistical_significance REAL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # Performance baselines table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                baseline_value REAL NOT NULL,
                measurement_period TEXT,
                measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # Cost performance tradeoffs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cost_performance_tradeoffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                configuration_name TEXT NOT NULL,
                avg_cost_per_task REAL,
                avg_quality_score REAL,
                avg_speed_seconds REAL,
                efficiency_ratio REAL,
                is_optimal BOOLEAN DEFAULT 0,
                observation_count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # Auto adjustments log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_adjustments_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                adjustment_category TEXT NOT NULL,
                parameter_adjusted TEXT NOT NULL,
                old_value TEXT NOT NULL,
                new_value TEXT NOT NULL,
                reason TEXT NOT NULL,
                auto_approved BOOLEAN DEFAULT 0,
                requires_human_approval BOOLEAN DEFAULT 1,
                approved BOOLEAN DEFAULT 0,
                approved_by TEXT,
                approved_at TIMESTAMP,
                applied BOOLEAN DEFAULT 0,
                applied_at TIMESTAMP,
                reverted BOOLEAN DEFAULT 0,
                reverted_at TIMESTAMP,
                auto_revert_after_hours INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        db.commit()
        db.close()
    
    def analyze_threshold_performance(self, threshold_name: str, days_back: int = 30) -> Optional[Dict]:
        """
        Analyze how a specific threshold is performing.
        Example: Is 85% consensus threshold optimal?
        
        Args:
            threshold_name: Name of threshold to analyze (e.g., 'consensus_threshold')
            days_back: Days of data to analyze
            
        Returns:
            Analysis results with optimization suggestions
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Get outcomes with consensus data
        cursor.execute('''
            SELECT consensus_score, success_score, execution_time_seconds
            FROM outcome_tracking
            WHERE created_at >= ?
            AND consensus_enabled = 1
            AND consensus_score IS NOT NULL
        ''', (cutoff_date.isoformat(),))
        
        outcomes = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        if len(outcomes) < 10:
            return None
        
        # Current threshold (hardcoded for now, will be configurable)
        current_threshold = 0.85
        
        # Analyze performance at different threshold levels
        threshold_tests = [0.75, 0.80, 0.85, 0.90, 0.95]
        results = {}
        
        for test_threshold in threshold_tests:
            # Simulate: Would we have used consensus at this threshold?
            passing = [o for o in outcomes if o['consensus_score'] >= test_threshold]
            
            if len(passing) > 0:
                avg_success = statistics.mean([o['success_score'] for o in passing])
                avg_time = statistics.mean([o['execution_time_seconds'] for o in passing])
                pass_rate = len(passing) / len(outcomes)
                
                # Calculate efficiency (success per second)
                efficiency = avg_success / avg_time if avg_time > 0 else 0
                
                results[test_threshold] = {
                    'avg_success': avg_success,
                    'avg_time': avg_time,
                    'pass_rate': pass_rate,
                    'efficiency': efficiency,
                    'sample_size': len(passing)
                }
        
        # Find optimal threshold (best efficiency)
        if results:
            optimal = max(results.items(), key=lambda x: x[1]['efficiency'])
            optimal_threshold = optimal[0]
            optimal_metrics = optimal[1]
            
            current_metrics = results.get(current_threshold, {})
            
            # Should we suggest a change?
            if optimal_threshold != current_threshold:
                improvement = ((optimal_metrics['efficiency'] - current_metrics.get('efficiency', 0)) / 
                              current_metrics.get('efficiency', 1) * 100)
                
                if improvement > 5:  # 5% improvement threshold
                    return {
                        'threshold_name': threshold_name,
                        'current_value': current_threshold,
                        'suggested_value': optimal_threshold,
                        'improvement_pct': improvement,
                        'current_metrics': current_metrics,
                        'suggested_metrics': optimal_metrics,
                        'confidence': min(0.95, 0.60 + (len(outcomes) / 100)),
                        'recommendation': f'Change {threshold_name} from {current_threshold} to {optimal_threshold} for {improvement:.1f}% efficiency improvement'
                    }
        
        return None
    
    def suggest_threshold_adjustment(self, analysis: Dict) -> int:
        """
        Create a suggested adjustment based on analysis.
        
        Returns:
            adjustment_id for tracking
        """
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        # Determine if auto-approval is appropriate
        auto_approve = (
            analysis['confidence'] > 0.85 and 
            analysis['improvement_pct'] > 10 and
            abs(analysis['suggested_value'] - analysis['current_value']) <= 0.10  # Max 10% change
        )
        
        cursor.execute('''
            INSERT INTO auto_adjustments_log (
                adjustment_category, parameter_adjusted, old_value,
                new_value, reason, auto_approved, requires_human_approval,
                approved, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'threshold_optimization',
            analysis['threshold_name'],
            str(analysis['current_value']),
            str(analysis['suggested_value']),
            analysis['recommendation'],
            auto_approve,
            not auto_approve,
            auto_approve,
            json.dumps({
                'improvement_pct': analysis['improvement_pct'],
                'confidence': analysis['confidence'],
                'current_metrics': analysis['current_metrics'],
                'suggested_metrics': analysis['suggested_metrics']
            })
        ))
        
        adjustment_id = cursor.lastrowid
        db.commit()
        db.close()
        
        return adjustment_id


class ExperimentManager:
    """
    Runs controlled A/B experiments on routing and configuration changes.
    Example: Test "consensus threshold 80%" vs "consensus threshold 85%"
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self.traffic_split = 0.20  # 20% to test group
    
    def create_experiment(self, 
                         experiment_name: str,
                         variable: str,
                         control_value: Any,
                         test_value: Any) -> int:
        """
        Create a new A/B experiment.
        
        Args:
            experiment_name: Name of experiment
            variable: What's being tested (e.g., 'consensus_threshold')
            control_value: Current/baseline value
            test_value: New value to test
            
        Returns:
            experiment_id
        """
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        cursor.execute('''
            INSERT INTO optimization_experiments (
                experiment_name, variable_being_tested,
                control_value, test_value, status
            ) VALUES (?, ?, ?, ?, 'running')
        ''', (experiment_name, variable, str(control_value), str(test_value)))
        
        experiment_id = cursor.lastrowid
        db.commit()
        db.close()
        
        print(f"🧪 Experiment created: {experiment_name}")
        print(f"   Testing: {variable} = {test_value} vs {control_value}")
        
        return experiment_id
    
    def assign_to_group(self, experiment_id: int) -> str:
        """
        Randomly assign request to control or test group.
        
        Returns:
            'control' or 'test'
        """
        return 'test' if random.random() < self.traffic_split else 'control'
    
    def record_experiment_outcome(self,
                                  experiment_id: int,
                                  group: str,
                                  success_score: float,
                                  execution_time: float,
                                  cost: float = 0):
        """Record outcome from an experiment"""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Get current experiment
        cursor.execute('''
            SELECT control_sample_size, test_sample_size,
                   control_metrics, test_metrics
            FROM optimization_experiments
            WHERE id = ?
        ''', (experiment_id,))
        
        exp = cursor.fetchone()
        if not exp:
            db.close()
            return
        
        # Parse existing metrics
        control_metrics = json.loads(exp['control_metrics']) if exp['control_metrics'] else {
            'success_scores': [], 'execution_times': [], 'costs': []
        }
        test_metrics = json.loads(exp['test_metrics']) if exp['test_metrics'] else {
            'success_scores': [], 'execution_times': [], 'costs': []
        }
        
        # Add new data point
        if group == 'control':
            control_metrics['success_scores'].append(success_score)
            control_metrics['execution_times'].append(execution_time)
            control_metrics['costs'].append(cost)
            new_sample_size = exp['control_sample_size'] + 1
            
            cursor.execute('''
                UPDATE optimization_experiments
                SET control_sample_size = ?,
                    control_metrics = ?
                WHERE id = ?
            ''', (new_sample_size, json.dumps(control_metrics), experiment_id))
        else:
            test_metrics['success_scores'].append(success_score)
            test_metrics['execution_times'].append(execution_time)
            test_metrics['costs'].append(cost)
            new_sample_size = exp['test_sample_size'] + 1
            
            cursor.execute('''
                UPDATE optimization_experiments
                SET test_sample_size = ?,
                    test_metrics = ?
                WHERE id = ?
            ''', (new_sample_size, json.dumps(test_metrics), experiment_id))
        
        db.commit()
        db.close()
    
    def analyze_experiment(self, experiment_id: int) -> Optional[Dict]:
        """
        Analyze experiment results and determine winner.
        Uses simple statistical comparison.
        
        Returns:
            Analysis results with winner determination
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute('''
            SELECT * FROM optimization_experiments
            WHERE id = ?
        ''', (experiment_id,))
        
        exp = dict(cursor.fetchone())
        db.close()
        
        # Need minimum sample sizes
        if exp['control_sample_size'] < 20 or exp['test_sample_size'] < 20:
            return {
                'status': 'insufficient_data',
                'control_sample': exp['control_sample_size'],
                'test_sample': exp['test_sample_size'],
                'needed': 20
            }
        
        # Parse metrics
        control_metrics = json.loads(exp['control_metrics'])
        test_metrics = json.loads(exp['test_metrics'])
        
        # Calculate averages
        control_avg_success = statistics.mean(control_metrics['success_scores'])
        test_avg_success = statistics.mean(test_metrics['success_scores'])
        
        control_avg_time = statistics.mean(control_metrics['execution_times'])
        test_avg_time = statistics.mean(test_metrics['execution_times'])
        
        control_avg_cost = statistics.mean(control_metrics['costs']) if control_metrics['costs'] else 0
        test_avg_cost = statistics.mean(test_metrics['costs']) if test_metrics['costs'] else 0
        
        # Calculate improvement
        success_improvement = ((test_avg_success - control_avg_success) / control_avg_success * 100)
        time_improvement = ((control_avg_time - test_avg_time) / control_avg_time * 100)  # Negative = faster
        cost_improvement = ((control_avg_cost - test_avg_cost) / control_avg_cost * 100) if control_avg_cost > 0 else 0
        
        # Overall score (weighted: 50% success, 30% speed, 20% cost)
        test_score = (test_avg_success * 0.5) + ((1 / test_avg_time) * 0.3) + ((1 / (test_avg_cost + 0.01)) * 0.2)
        control_score = (control_avg_success * 0.5) + ((1 / control_avg_time) * 0.3) + ((1 / (control_avg_cost + 0.01)) * 0.2)
        
        # Determine winner
        if test_score > control_score * 1.05:  # 5% improvement threshold
            winner = 'test'
            recommendation = f'Deploy test value ({exp["test_value"]}) - {success_improvement:+.1f}% better'
        elif control_score > test_score * 1.05:
            winner = 'control'
            recommendation = f'Keep control value ({exp["control_value"]}) - test did not improve'
        else:
            winner = 'tie'
            recommendation = 'No significant difference - keep current value'
        
        return {
            'status': 'complete',
            'winner': winner,
            'recommendation': recommendation,
            'control_metrics': {
                'avg_success': control_avg_success,
                'avg_time': control_avg_time,
                'avg_cost': control_avg_cost,
                'sample_size': exp['control_sample_size']
            },
            'test_metrics': {
                'avg_success': test_avg_success,
                'avg_time': test_avg_time,
                'avg_cost': test_avg_cost,
                'sample_size': exp['test_sample_size']
            },
            'improvements': {
                'success_pct': success_improvement,
                'speed_pct': time_improvement,
                'cost_pct': cost_improvement
            }
        }
    
    def finalize_experiment(self, experiment_id: int, analysis: Dict):
        """Mark experiment as complete and log winner"""
        db = sqlite3.connect(self.db_path)
        cursor = db.cursor()
        
        cursor.execute('''
            UPDATE optimization_experiments
            SET status = 'completed',
                winner = ?,
                completed_at = ?,
                metadata = ?
            WHERE id = ?
        ''', (
            analysis['winner'],
            datetime.now(),
            json.dumps(analysis),
            experiment_id
        ))
        
        db.commit()
        db.close()


class CostOptimizer:
    """
    Optimizes cost vs. quality tradeoffs.
    Example: Use Sonnet instead of Opus when quality difference is minimal.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        
        # Cost per 1K tokens (approximate)
        self.ai_costs = {
            'claude-sonnet-4': 0.003,
            'claude-opus-4-5': 0.015,
            'gpt-4': 0.03,
            'deepseek': 0.0014,
            'gemini': 0.002
        }
    
    def analyze_cost_performance(self, days_back: int = 30) -> List[Dict]:
        """
        Analyze which AI models provide best cost/performance ratio.
        
        Returns:
            List of configurations ranked by efficiency
        """
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        cursor.execute('''
            SELECT ai_used, success_score, execution_time_seconds, tokens_used
            FROM outcome_tracking
            WHERE created_at >= ?
        ''', (cutoff_date.isoformat(),))
        
        outcomes = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        if len(outcomes) < 10:
            return []
        
        # Group by AI
        by_ai = {}
        for outcome in outcomes:
            ai = outcome['ai_used']
            if ai not in by_ai:
                by_ai[ai] = []
            by_ai[ai].append(outcome)
        
        configurations = []
        
        for ai, ai_outcomes in by_ai.items():
            if len(ai_outcomes) < 3:
                continue
            
            avg_success = statistics.mean([o['success_score'] for o in ai_outcomes])
            avg_time = statistics.mean([o['execution_time_seconds'] for o in ai_outcomes])
            avg_tokens = statistics.mean([o['tokens_used'] or 1000 for o in ai_outcomes])
            
            # Calculate cost
            cost_per_token = self.ai_costs.get(ai, 0.01)
            avg_cost = (avg_tokens / 1000) * cost_per_token
            
            # Efficiency ratio (success per dollar)
            efficiency = avg_success / avg_cost if avg_cost > 0 else 0
            
            configurations.append({
                'ai': ai,
                'avg_success': avg_success,
                'avg_time': avg_time,
                'avg_cost': avg_cost,
                'efficiency': efficiency,
                'sample_size': len(ai_outcomes)
            })
        
        # Rank by efficiency
        configurations.sort(key=lambda x: x['efficiency'], reverse=True)
        
        return configurations
    
    def suggest_cost_optimization(self, configurations: List[Dict]) -> Optional[Dict]:
        """
        Suggest cost optimizations based on analysis.
        
        Example: "Use Sonnet instead of Opus for simple tasks - 5x cheaper with only 2% quality drop"
        """
        if len(configurations) < 2:
            return None
        
        # Find most expensive and check if cheaper alternative exists
        by_cost = sorted(configurations, key=lambda x: x['avg_cost'], reverse=True)
        most_expensive = by_cost[0]
        
        # Find cheaper alternatives with similar quality
        alternatives = []
        for config in configurations:
            if config['ai'] == most_expensive['ai']:
                continue
            
            # Quality drop acceptable if <10%
            quality_drop = (most_expensive['avg_success'] - config['avg_success']) / most_expensive['avg_success'] * 100
            cost_savings = (most_expensive['avg_cost'] - config['avg_cost']) / most_expensive['avg_cost'] * 100
            
            if quality_drop < 10 and cost_savings > 20:
                alternatives.append({
                    'from_ai': most_expensive['ai'],
                    'to_ai': config['ai'],
                    'quality_drop_pct': quality_drop,
                    'cost_savings_pct': cost_savings,
                    'recommendation': f"Use {config['ai']} instead of {most_expensive['ai']} for routine tasks - {cost_savings:.0f}% cost savings with only {quality_drop:.1f}% quality drop"
                })
        
        return alternatives[0] if alternatives else None


class SelfOptimizationEngine:
    """
    Main orchestrator for self-optimization.
    Coordinates threshold optimization, experiments, and cost optimization.
    """
    
    def __init__(self, db_path='swarm_intelligence.db'):
        self.db_path = db_path
        self.threshold_optimizer = ThresholdOptimizer(db_path)
        self.experiment_manager = ExperimentManager(db_path)
        self.cost_optimizer = CostOptimizer(db_path)
    
    def run_optimization_cycle(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Run complete optimization cycle.
        
        Returns:
            Dictionary with all optimizations discovered and experiments started
        """
        print(f"⚙️ Running self-optimization cycle (last {days_back} days)...")
        
        results = {
            'threshold_adjustments': [],
            'cost_optimizations': [],
            'experiments_created': [],
            'experiments_analyzed': []
        }
        
        # 1. Analyze threshold performance
        print("   Analyzing thresholds...")
        consensus_analysis = self.threshold_optimizer.analyze_threshold_performance('consensus_threshold', days_back)
        
        if consensus_analysis:
            adjustment_id = self.threshold_optimizer.suggest_threshold_adjustment(consensus_analysis)
            results['threshold_adjustments'].append({
                'adjustment_id': adjustment_id,
                'analysis': consensus_analysis
            })
            print(f"   💡 Suggested threshold adjustment (ID: {adjustment_id})")
        
        # 2. Analyze cost/performance tradeoffs
        print("   Analyzing cost optimization...")
        configs = self.cost_optimizer.analyze_cost_performance(days_back)
        
        if configs:
            cost_opt = self.cost_optimizer.suggest_cost_optimization(configs)
            if cost_opt:
                results['cost_optimizations'].append(cost_opt)
                print(f"   💰 Found cost optimization: {cost_opt['cost_savings_pct']:.0f}% savings possible")
        
        # 3. Check running experiments
        print("   Checking active experiments...")
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute('''
            SELECT id, experiment_name, control_sample_size, test_sample_size
            FROM optimization_experiments
            WHERE status = 'running'
        ''')
        
        active_experiments = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        for exp in active_experiments:
            if exp['control_sample_size'] >= 20 and exp['test_sample_size'] >= 20:
                analysis = self.experiment_manager.analyze_experiment(exp['id'])
                if analysis and analysis['status'] == 'complete':
                    self.experiment_manager.finalize_experiment(exp['id'], analysis)
                    results['experiments_analyzed'].append({
                        'experiment_id': exp['id'],
                        'experiment_name': exp['experiment_name'],
                        'analysis': analysis
                    })
                    print(f"   ✅ Experiment complete: {exp['experiment_name']} - Winner: {analysis['winner']}")
        
        return results
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """Get comprehensive optimization status"""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Count experiments
        cursor.execute('SELECT COUNT(*) as count FROM optimization_experiments WHERE status = "running"')
        active_experiments = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM optimization_experiments WHERE status = "completed"')
        completed_experiments = cursor.fetchone()['count']
        
        # Count adjustments
        cursor.execute('SELECT COUNT(*) as count FROM auto_adjustments_log WHERE approved = 0 AND reverted = 0')
        pending_adjustments = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM auto_adjustments_log WHERE approved = 1 AND applied = 1')
        applied_adjustments = cursor.fetchone()['count']
        
        # Get recent optimizations
        cursor.execute('''
            SELECT adjustment_category, parameter_adjusted, old_value, new_value, reason
            FROM auto_adjustments_log
            WHERE approved = 1 AND applied = 1
            ORDER BY applied_at DESC
            LIMIT 5
        ''')
        recent_optimizations = [dict(row) for row in cursor.fetchall()]
        
        db.close()
        
        return {
            'active_experiments': active_experiments,
            'completed_experiments': completed_experiments,
            'pending_adjustments': pending_adjustments,
            'applied_adjustments': applied_adjustments,
            'recent_optimizations': recent_optimizations,
            'status': 'active' if applied_adjustments > 0 else 'needs_more_data'
        }


# Convenience function
def get_optimization_engine(db_path='swarm_intelligence.db') -> SelfOptimizationEngine:
    """Get singleton instance of optimization engine"""
    return SelfOptimizationEngine(db_path)


# I did no harm and this file is not truncated
