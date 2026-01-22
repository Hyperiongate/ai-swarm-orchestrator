"""
Analytics Engine Module
Created: January 22, 2026
Last Updated: January 22, 2026 - SPRINT 3: Data Visualization & Insights

This module provides comprehensive analytics and visualizations:
- Time saved calculations
- Efficiency trend analysis
- Task type breakdowns
- Pattern heatmaps
- Weekly/monthly reports
- ROI calculations

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

from flask import Blueprint, jsonify, request
from database import get_db
from datetime import datetime, timedelta
import json
from collections import defaultdict

# Create blueprint
analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')


@analytics_bp.route('/overview', methods=['GET'])
def get_overview():
    """
    Get high-level analytics overview
    
    Query params:
        period: 'week', 'month', 'quarter', 'year' (default: month)
    """
    period = request.args.get('period', 'month')
    
    # Calculate date range
    end_date = datetime.now()
    if period == 'week':
        start_date = end_date - timedelta(days=7)
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
    elif period == 'quarter':
        start_date = end_date - timedelta(days=90)
    else:  # year
        start_date = end_date - timedelta(days=365)
    
    db = get_db()
    
    # Total tasks
    total_tasks = db.execute('''
        SELECT COUNT(*) as count
        FROM tasks
        WHERE created_at >= ?
    ''', (start_date,)).fetchone()['count']
    
    # Completed tasks
    completed = db.execute('''
        SELECT COUNT(*) as count
        FROM tasks
        WHERE created_at >= ? AND status = 'completed'
    ''', (start_date,)).fetchone()['count']
    
    # Total time spent
    total_time = db.execute('''
        SELECT SUM(execution_time_seconds) as total
        FROM tasks
        WHERE created_at >= ?
    ''', (start_date,)).fetchone()['total'] or 0
    
    # Time saved from suggestions
    suggestions_accepted = db.execute('''
        SELECT COUNT(*) as count
        FROM proactive_suggestions
        WHERE created_at >= ? AND accepted = 1
    ''', (start_date,)).fetchone()['count']
    
    # Estimate 5 minutes saved per accepted suggestion
    time_saved_minutes = suggestions_accepted * 5
    
    # Projects created
    projects_created = db.execute('''
        SELECT COUNT(*) as count
        FROM projects
        WHERE created_at >= ?
    ''', (start_date,)).fetchone()['count']
    
    db.close()
    
    return jsonify({
        'period': period,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'total_tasks': total_tasks,
        'completed_tasks': completed,
        'completion_rate': round((completed / total_tasks * 100) if total_tasks > 0 else 0, 1),
        'total_time_hours': round(total_time / 3600, 2),
        'time_saved_hours': round(time_saved_minutes / 60, 2),
        'projects_created': projects_created,
        'suggestions_accepted': suggestions_accepted
    })


@analytics_bp.route('/time-series', methods=['GET'])
def get_time_series():
    """
    Get time-series data for charts
    
    Query params:
        metric: 'tasks', 'time', 'efficiency'
        period: 'week', 'month', 'quarter'
        granularity: 'day', 'week'
    """
    metric = request.args.get('metric', 'tasks')
    period = request.args.get('period', 'month')
    granularity = request.args.get('granularity', 'day')
    
    # Calculate date range
    end_date = datetime.now()
    if period == 'week':
        start_date = end_date - timedelta(days=7)
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
    else:  # quarter
        start_date = end_date - timedelta(days=90)
    
    db = get_db()
    
    # Build query based on metric and granularity
    if granularity == 'day':
        date_format = '%Y-%m-%d'
        group_by = "DATE(created_at)"
    else:  # week
        date_format = '%Y-W%W'
        group_by = "strftime('%Y-W%W', created_at)"
    
    if metric == 'tasks':
        data = db.execute(f'''
            SELECT 
                {group_by} as period,
                COUNT(*) as value
            FROM tasks
            WHERE created_at >= ?
            GROUP BY {group_by}
            ORDER BY period
        ''', (start_date,)).fetchall()
    
    elif metric == 'time':
        data = db.execute(f'''
            SELECT 
                {group_by} as period,
                SUM(execution_time_seconds) / 3600.0 as value
            FROM tasks
            WHERE created_at >= ?
            GROUP BY {group_by}
            ORDER BY period
        ''', (start_date,)).fetchall()
    
    else:  # efficiency (tasks per hour)
        data = db.execute(f'''
            SELECT 
                {group_by} as period,
                COUNT(*) * 1.0 / (SUM(execution_time_seconds) / 3600.0) as value
            FROM tasks
            WHERE created_at >= ? AND execution_time_seconds > 0
            GROUP BY {group_by}
            ORDER BY period
        ''', (start_date,)).fetchall()
    
    db.close()
    
    return jsonify({
        'metric': metric,
        'granularity': granularity,
        'data': [
            {'period': row['period'], 'value': round(row['value'], 2)}
            for row in data
        ]
    })


@analytics_bp.route('/task-breakdown', methods=['GET'])
def get_task_breakdown():
    """
    Get task type breakdown
    
    Query params:
        period: 'week', 'month', 'quarter', 'year'
    """
    period = request.args.get('period', 'month')
    
    # Calculate date range
    end_date = datetime.now()
    if period == 'week':
        start_date = end_date - timedelta(days=7)
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
    elif period == 'quarter':
        start_date = end_date - timedelta(days=90)
    else:
        start_date = end_date - timedelta(days=365)
    
    db = get_db()
    
    breakdown = db.execute('''
        SELECT 
            task_type,
            COUNT(*) as count,
            AVG(execution_time_seconds) as avg_time
        FROM tasks
        WHERE created_at >= ?
        GROUP BY task_type
        ORDER BY count DESC
    ''', (start_date,)).fetchall()
    
    db.close()
    
    total = sum(row['count'] for row in breakdown)
    
    return jsonify({
        'breakdown': [
            {
                'type': row['task_type'] or 'unknown',
                'count': row['count'],
                'percentage': round((row['count'] / total * 100) if total > 0 else 0, 1),
                'avg_time_seconds': round(row['avg_time'] or 0, 2)
            }
            for row in breakdown
        ]
    })


@analytics_bp.route('/pattern-heatmap', methods=['GET'])
def get_pattern_heatmap():
    """
    Get usage pattern heatmap data (day of week x hour of day)
    
    Query params:
        weeks: Number of weeks to analyze (default: 4)
    """
    weeks = int(request.args.get('weeks', 4))
    start_date = datetime.now() - timedelta(weeks=weeks)
    
    db = get_db()
    
    # Get tasks by day of week and hour
    heatmap_data = db.execute('''
        SELECT 
            CAST(strftime('%w', created_at) AS INTEGER) as day_of_week,
            CAST(strftime('%H', created_at) AS INTEGER) as hour,
            COUNT(*) as count
        FROM tasks
        WHERE created_at >= ?
        GROUP BY day_of_week, hour
    ''', (start_date,)).fetchall()
    
    db.close()
    
    # Build heatmap matrix
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    matrix = [[0 for _ in range(24)] for _ in range(7)]
    
    for row in heatmap_data:
        matrix[row['day_of_week']][row['hour']] = row['count']
    
    return jsonify({
        'days': days,
        'hours': list(range(24)),
        'matrix': matrix,
        'max_value': max(max(row) for row in matrix) if matrix else 0
    })


@analytics_bp.route('/efficiency-trends', methods=['GET'])
def get_efficiency_trends():
    """
    Calculate efficiency trends over time
    
    Query params:
        metric: 'speed', 'quality', 'automation'
    """
    metric = request.args.get('metric', 'speed')
    
    db = get_db()
    
    if metric == 'speed':
        # Average task completion time trend
        trends = db.execute('''
            SELECT 
                DATE(created_at) as date,
                AVG(execution_time_seconds) as avg_time
            FROM tasks
            WHERE created_at >= datetime('now', '-30 days')
            AND execution_time_seconds > 0
            GROUP BY DATE(created_at)
            ORDER BY date
        ''').fetchall()
        
        data = [
            {'date': row['date'], 'value': round(row['avg_time'], 2)}
            for row in trends
        ]
    
    elif metric == 'quality':
        # Consensus agreement scores trend
        trends = db.execute('''
            SELECT 
                DATE(created_at) as date,
                AVG(agreement_score) as avg_score
            FROM consensus_validations
            WHERE created_at >= datetime('now', '-30 days')
            GROUP BY DATE(created_at)
            ORDER BY date
        ''').fetchall()
        
        data = [
            {'date': row['date'], 'value': round(row['avg_score'], 2)}
            for row in trends
        ]
    
    else:  # automation
        # Percentage of tasks automated/suggested
        trends = db.execute('''
            SELECT 
                DATE(t.created_at) as date,
                COUNT(*) as total_tasks,
                SUM(CASE WHEN ps.id IS NOT NULL THEN 1 ELSE 0 END) as automated_tasks
            FROM tasks t
            LEFT JOIN proactive_suggestions ps ON t.id = ps.task_id
            WHERE t.created_at >= datetime('now', '-30 days')
            GROUP BY DATE(t.created_at)
            ORDER BY date
        ''').fetchall()
        
        data = [
            {
                'date': row['date'], 
                'value': round((row['automated_tasks'] / row['total_tasks'] * 100) if row['total_tasks'] > 0 else 0, 1)
            }
            for row in trends
        ]
    
    db.close()
    
    return jsonify({
        'metric': metric,
        'data': data
    })


@analytics_bp.route('/roi', methods=['GET'])
def calculate_roi():
    """
    Calculate return on investment
    
    Estimates time saved, cost savings, and efficiency gains
    """
    db = get_db()
    
    # Time period (last 90 days)
    start_date = datetime.now() - timedelta(days=90)
    
    # Get accepted suggestions (each saves ~5 minutes)
    suggestions = db.execute('''
        SELECT COUNT(*) as count, suggestion_type
        FROM proactive_suggestions
        WHERE created_at >= ? AND accepted = 1
        GROUP BY suggestion_type
    ''', (start_date,)).fetchall()
    
    time_saved_minutes = sum(row['count'] * 5 for row in suggestions)
    
    # Get automated patterns (each saves ~10 minutes when used)
    patterns = db.execute('''
        SELECT SUM(frequency) as total
        FROM user_patterns
        WHERE suggestion_accepted = 1
        AND last_seen >= ?
    ''', (start_date,)).fetchone()['total'] or 0
    
    time_saved_minutes += patterns * 10
    
    # Get resource searches (saves ~15 minutes when successful)
    searches = db.execute('''
        SELECT COUNT(*) as count
        FROM resource_searches
        WHERE searched_at >= ? AND improved_response = 1
    ''', (start_date,)).fetchone()['count'] or 0
    
    time_saved_minutes += searches * 15
    
    # Calculate value (assuming $100/hour consulting rate)
    hourly_rate = 100
    money_saved = (time_saved_minutes / 60) * hourly_rate
    
    # Efficiency improvement
    total_tasks = db.execute('''
        SELECT COUNT(*) as count
        FROM tasks
        WHERE created_at >= ?
    ''', (start_date,)).fetchone()['count'] or 1
    
    efficiency_gain = round((time_saved_minutes / (total_tasks * 30)) * 100, 1)  # Assuming 30 min avg per task
    
    db.close()
    
    return jsonify({
        'period_days': 90,
        'time_saved_hours': round(time_saved_minutes / 60, 2),
        'time_saved_minutes': time_saved_minutes,
        'estimated_cost_savings': round(money_saved, 2),
        'efficiency_improvement_percent': efficiency_gain,
        'suggestions_accepted': sum(row['count'] for row in suggestions),
        'patterns_automated': patterns,
        'successful_searches': searches
    })


@analytics_bp.route('/top-insights', methods=['GET'])
def get_top_insights():
    """
    Get actionable insights from analytics
    
    Returns top 5 insights with recommendations
    """
    db = get_db()
    insights = []
    
    # Insight 1: Most time-consuming task type
    top_time_consumer = db.execute('''
        SELECT task_type, SUM(execution_time_seconds) as total_time
        FROM tasks
        WHERE created_at >= datetime('now', '-30 days')
        GROUP BY task_type
        ORDER BY total_time DESC
        LIMIT 1
    ''').fetchone()
    
    if top_time_consumer and top_time_consumer['total_time']:
        insights.append({
            'type': 'time_sink',
            'title': f"{top_time_consumer['task_type']} tasks consume the most time",
            'value': f"{round(top_time_consumer['total_time'] / 3600, 1)} hours",
            'recommendation': 'Consider creating templates or workflows to automate this task type'
        })
    
    # Insight 2: Peak productivity time
    peak_hour = db.execute('''
        SELECT CAST(strftime('%H', created_at) AS INTEGER) as hour, COUNT(*) as count
        FROM tasks
        WHERE created_at >= datetime('now', '-30 days')
        GROUP BY hour
        ORDER BY count DESC
        LIMIT 1
    ''').fetchone()
    
    if peak_hour:
        hour_12 = peak_hour['hour'] % 12 or 12
        am_pm = 'AM' if peak_hour['hour'] < 12 else 'PM'
        insights.append({
            'type': 'productivity_pattern',
            'title': f"Peak productivity at {hour_12}:00 {am_pm}",
            'value': f"{peak_hour['count']} tasks",
            'recommendation': 'Schedule important work during this time'
        })
    
    # Insight 3: Suggestion acceptance rate
    suggestion_stats = db.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) as accepted
        FROM proactive_suggestions
        WHERE created_at >= datetime('now', '-30 days')
    ''').fetchone()
    
    if suggestion_stats['total'] > 0:
        acceptance_rate = round((suggestion_stats['accepted'] / suggestion_stats['total']) * 100, 1)
        insights.append({
            'type': 'ai_effectiveness',
            'title': f"{acceptance_rate}% suggestion acceptance rate",
            'value': f"{suggestion_stats['accepted']} of {suggestion_stats['total']} accepted",
            'recommendation': 'High acceptance shows AI is learning your preferences well' if acceptance_rate > 50 else 'Review dismissed suggestions to improve AI learning'
        })
    
    # Insight 4: Automation opportunity
    frequent_patterns = db.execute('''
        SELECT COUNT(*) as count
        FROM user_patterns
        WHERE frequency >= 3 AND suggestion_made = 0
    ''').fetchone()['count']
    
    if frequent_patterns > 0:
        insights.append({
            'type': 'automation_opportunity',
            'title': f"{frequent_patterns} tasks ready for automation",
            'value': f"Potential {frequent_patterns * 10} min/week saved",
            'recommendation': 'Review pattern tracker to create templates'
        })
    
    # Insight 5: Project completion rate
    project_stats = db.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
        FROM projects
        WHERE created_at >= datetime('now', '-90 days')
    ''').fetchone()
    
    if project_stats['total'] > 0:
        completion_rate = round((project_stats['completed'] / project_stats['total']) * 100, 1)
        insights.append({
            'type': 'project_health',
            'title': f"{completion_rate}% project completion rate",
            'value': f"{project_stats['completed']} of {project_stats['total']} completed",
            'recommendation': 'Strong completion rate' if completion_rate > 75 else 'Focus on completing active projects before starting new ones'
        })
    
    db.close()
    
    return jsonify({
        'insights': insights[:5]  # Top 5
    })


# I did no harm and this file is not truncated
