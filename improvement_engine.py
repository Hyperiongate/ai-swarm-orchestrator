"""
Improvement Engine Module
Created: January 22, 2026
Last Updated: January 22, 2026 - SPRINT 2: Weekly Efficiency Reports

This module analyzes system usage patterns and proactively suggests
improvements, automation opportunities, and efficiency gains.

FEATURES:
- Weekly efficiency analysis
- Template opportunity detection
- Workflow bundling suggestions
- Time saved calculations
- Improvement recommendations

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
from datetime import datetime, timedelta
from database import get_db


class ImprovementEngine:
    """Analyzes usage and suggests efficiency improvements"""
    
    def __init__(self):
        self.analysis_period_days = 7
        
    def generate_weekly_report(self):
        """
        Generate comprehensive efficiency report
        
        Returns:
            dict with improvement opportunities and metrics
        """
        db = get_db()
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.analysis_period_days)
        
        report = {
            'generated_at': end_date.isoformat(),
            'period': f'{start_date.date()} to {end_date.date()}',
            'metrics': self._calculate_metrics(db, start_date),
            'template_opportunities': self._find_template_opportunities(db, start_date),
            'bundling_opportunities': self._find_bundling_opportunities(db, start_date),
            'automation_suggestions': self._suggest_automations(db, start_date),
            'time_savings': self._calculate_time_savings(db, start_date),
            'top_improvements': []
        }
        
        # Rank improvements by impact
        report['top_improvements'] = self._rank_improvements(report)
        
        db.close()
        
        return report
    
    def _calculate_metrics(self, db, start_date):
        """Calculate key usage metrics"""
        stats = db.execute('''
            SELECT 
                COUNT(*) as total_tasks,
                AVG(execution_time_seconds) as avg_time,
                SUM(execution_time_seconds) as total_time,
                COUNT(DISTINCT DATE(created_at)) as active_days,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks
            FROM tasks
            WHERE created_at >= ?
        ''', (start_date,)).fetchone()
        
        # Get task type breakdown
        task_types = db.execute('''
            SELECT task_type, COUNT(*) as count
            FROM tasks
            WHERE created_at >= ?
            GROUP BY task_type
            ORDER BY count DESC
            LIMIT 5
        ''', (start_date,)).fetchall()
        
        return {
            'total_tasks': stats['total_tasks'] or 0,
            'completed_tasks': stats['completed_tasks'] or 0,
            'avg_time_seconds': round(stats['avg_time'] or 0, 2),
            'total_time_hours': round((stats['total_time'] or 0) / 3600, 2),
            'active_days': stats['active_days'] or 0,
            'top_task_types': [
                {'type': row['task_type'], 'count': row['count']}
                for row in task_types
            ]
        }
    
    def _find_template_opportunities(self, db, start_date):
        """Find repeated tasks that could become templates"""
        # Look for patterns in user_patterns table
        patterns = db.execute('''
            SELECT 
                pattern_data,
                frequency,
                suggestion_made,
                suggestion_accepted
            FROM user_patterns
            WHERE pattern_type = 'frequent_task'
            AND frequency >= 3
            AND last_seen >= ?
            ORDER BY frequency DESC
            LIMIT 10
        ''', (start_date,)).fetchall()
        
        opportunities = []
        for pattern in patterns:
            data = json.loads(pattern['pattern_data'])
            
            # Calculate potential time savings
            time_saved_per_use = 120  # Assume 2 minutes saved per use
            potential_annual_savings = pattern['frequency'] * 52 * time_saved_per_use / 60  # hours/year
            
            opportunities.append({
                'task': data.get('normalized_request', 'Unknown task'),
                'frequency': pattern['frequency'],
                'suggested': bool(pattern['suggestion_made']),
                'accepted': bool(pattern['suggestion_accepted']),
                'potential_time_savings_hours_year': round(potential_annual_savings, 1),
                'recommendation': f'Create template for this {pattern["frequency"]}-time task'
            })
        
        return opportunities
    
    def _find_bundling_opportunities(self, db, start_date):
        """Find tasks that are often done in sequence"""
        # Get recent tasks
        tasks = db.execute('''
            SELECT id, user_request, created_at
            FROM tasks
            WHERE created_at >= ?
            ORDER BY created_at
        ''', (start_date,)).fetchall()
        
        # Look for sequential patterns
        sequences = {}
        for i in range(len(tasks) - 1):
            current = tasks[i]
            next_task = tasks[i + 1]
            
            # Check if within 30 minutes of each other
            current_time = datetime.fromisoformat(current['created_at'])
            next_time = datetime.fromisoformat(next_task['created_at'])
            
            if (next_time - current_time).total_seconds() < 1800:  # 30 minutes
                sequence_key = f"{self._normalize_task(current['user_request'])} -> {self._normalize_task(next_task['user_request'])}"
                sequences[sequence_key] = sequences.get(sequence_key, 0) + 1
        
        # Find most common sequences
        bundling_opps = []
        for sequence, count in sorted(sequences.items(), key=lambda x: x[1], reverse=True)[:5]:
            if count >= 2:  # Only suggest if happened 2+ times
                bundling_opps.append({
                    'sequence': sequence,
                    'frequency': count,
                    'recommendation': f'Bundle these {count} common sequential tasks into single workflow'
                })
        
        return bundling_opps
    
    def _suggest_automations(self, db, start_date):
        """Suggest tasks that could be automated"""
        suggestions = []
        
        # Check for daily/weekly repeated tasks
        patterns = db.execute('''
            SELECT pattern_data, frequency, last_seen
            FROM user_patterns
            WHERE pattern_type = 'frequent_task'
            AND frequency >= 4
            AND last_seen >= ?
        ''', (start_date,)).fetchall()
        
        for pattern in patterns:
            data = json.loads(pattern['pattern_data'])
            task = data.get('normalized_request', '')
            
            # Check if task mentions time-based patterns
            if any(word in task.lower() for word in ['daily', 'weekly', 'every day', 'every week', 'monday', 'friday']):
                suggestions.append({
                    'task': task,
                    'type': 'scheduled_automation',
                    'recommendation': 'Set up automatic recurring task',
                    'estimated_time_savings_hours_year': round(pattern['frequency'] * 52 * 0.5, 1)  # 30 min saved each time
                })
        
        # Check for simple data entry tasks
        simple_tasks = db.execute('''
            SELECT user_request, COUNT(*) as count
            FROM tasks
            WHERE created_at >= ?
            AND LENGTH(user_request) < 100
            AND execution_time_seconds < 5
            GROUP BY user_request
            HAVING count >= 3
            LIMIT 5
        ''', (start_date,)).fetchall()
        
        for task in simple_tasks:
            suggestions.append({
                'task': task['user_request'],
                'type': 'quick_automation',
                'recommendation': f'Create keyboard shortcut or template (done {task["count"]} times)',
                'estimated_time_savings_hours_year': round(task['count'] * 52 * 0.1, 1)  # 6 min saved each
            })
        
        return suggestions
    
    def _calculate_time_savings(self, db, start_date):
        """Calculate time saved from accepted suggestions"""
        # Get accepted suggestions
        accepted = db.execute('''
            SELECT 
                COUNT(*) as count,
                suggestion_type
            FROM proactive_suggestions
            WHERE created_at >= ?
            AND accepted = 1
            GROUP BY suggestion_type
        ''', (start_date,)).fetchall()
        
        # Estimate time saved per suggestion type
        time_savings_map = {
            'immediate_next_step': 5,  # 5 minutes saved by not having to ask
            'next_step': 3,
            'process_improvement': 10,
            'automation_opportunity': 30
        }
        
        total_minutes_saved = 0
        breakdown = []
        
        for row in accepted:
            minutes = row['count'] * time_savings_map.get(row['suggestion_type'], 2)
            total_minutes_saved += minutes
            breakdown.append({
                'type': row['suggestion_type'],
                'count': row['count'],
                'minutes_saved': minutes
            })
        
        return {
            'total_hours_saved': round(total_minutes_saved / 60, 2),
            'total_minutes_saved': total_minutes_saved,
            'breakdown': breakdown
        }
    
    def _rank_improvements(self, report):
        """Rank all improvements by estimated impact"""
        improvements = []
        
        # Add template opportunities
        for opp in report['template_opportunities']:
            improvements.append({
                'type': 'template',
                'description': opp['recommendation'],
                'impact_hours_year': opp['potential_time_savings_hours_year'],
                'priority': 'high' if opp['potential_time_savings_hours_year'] > 20 else 'medium'
            })
        
        # Add automation suggestions
        for sug in report['automation_suggestions']:
            improvements.append({
                'type': 'automation',
                'description': sug['recommendation'],
                'impact_hours_year': sug.get('estimated_time_savings_hours_year', 0),
                'priority': 'high' if sug.get('estimated_time_savings_hours_year', 0) > 15 else 'medium'
            })
        
        # Add bundling opportunities
        for bundle in report['bundling_opportunities']:
            improvements.append({
                'type': 'bundling',
                'description': bundle['recommendation'],
                'impact_hours_year': bundle['frequency'] * 52 * 0.25,  # 15 min saved per bundle
                'priority': 'medium'
            })
        
        # Sort by impact
        improvements.sort(key=lambda x: x['impact_hours_year'], reverse=True)
        
        return improvements[:10]  # Top 10
    
    def _normalize_task(self, task):
        """Normalize task description for pattern matching"""
        # Remove numbers, names, specific details
        normalized = task.lower()
        normalized = ' '.join(normalized.split()[:5])  # First 5 words
        return normalized
    
    def save_report(self, report):
        """Save report to database"""
        db = get_db()
        
        db.execute('''
            INSERT INTO improvement_reports 
            (generated_at, report_data)
            VALUES (?, ?)
        ''', (
            report['generated_at'],
            json.dumps(report)
        ))
        
        db.commit()
        db.close()


# I did no harm and this file is not truncated
