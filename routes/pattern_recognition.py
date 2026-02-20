"""
PATTERN RECOGNITION API ROUTES
Created: February 5, 2026
Last Updated: February 5, 2026

API endpoints for user pattern recognition and behavioral insights.
Analyzes task history to identify work patterns, preferences, and trends.

Endpoints:
- GET /api/patterns/insights - Get comprehensive pattern dashboard data

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

from flask import Blueprint, jsonify
import sqlite3
from datetime import datetime, timedelta
from collections import Counter, defaultdict


# Create blueprint
pattern_bp = Blueprint('patterns', __name__)


@pattern_bp.route('/api/patterns/insights', methods=['GET'])
def get_pattern_insights():
    """
    Get comprehensive pattern recognition insights for dashboard.
    
    Analyzes user's interaction history to identify:
    - Most common task types
    - Time-of-day patterns
    - Communication style
    - Success rates
    - Workflow trends
    
    Returns:
        JSON with pattern insights and statistics
    """
    try:
        db = sqlite3.connect('swarm_intelligence.db')
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Calculate date range (last 90 days)
        ninety_days_ago = (datetime.now() - timedelta(days=90)).isoformat()
        
        # ==================================================================
        # SUMMARY STATISTICS
        # ==================================================================
        
        # Total interactions
        cursor.execute('''
            SELECT COUNT(*) as total FROM task_history
            WHERE created_at >= ?
        ''', (ninety_days_ago,))
        total_interactions = cursor.fetchone()['total']
        
        # Success rate
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
            FROM task_history
            WHERE created_at >= ?
        ''', (ninety_days_ago,))
        success_data = cursor.fetchone()
        success_rate = 0
        if success_data['total'] > 0:
            success_rate = round((success_data['completed'] / success_data['total']) * 100, 1)
        
        # Average response time
        cursor.execute('''
            SELECT AVG(execution_time) as avg_time
            FROM task_history
            WHERE created_at >= ? AND execution_time IS NOT NULL
        ''', (ninety_days_ago,))
        avg_response_data = cursor.fetchone()
        avg_response_time = round(avg_response_data['avg_time'] or 0, 1)
        
        # Consensus usage rate
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN consensus_result IS NOT NULL THEN 1 ELSE 0 END) as with_consensus
            FROM task_history
            WHERE created_at >= ?
        ''', (ninety_days_ago,))
        consensus_data = cursor.fetchone()
        consensus_rate = 0
        if consensus_data['total'] > 0:
            consensus_rate = round((consensus_data['with_consensus'] / consensus_data['total']) * 100, 1)
        
        summary = {
            'total_interactions': total_interactions,
            'success_rate': success_rate,
            'avg_response_time': avg_response_time,
            'consensus_used': consensus_rate
        }
        
        # ==================================================================
        # TOP TASK TYPES
        # ==================================================================
        
        cursor.execute('''
            SELECT 
                LOWER(TRIM(task_type)) as task_type,
                COUNT(*) as count
            FROM task_history
            WHERE created_at >= ? AND task_type IS NOT NULL
            GROUP BY LOWER(TRIM(task_type))
            ORDER BY count DESC
            LIMIT 10
        ''', (ninety_days_ago,))
        
        task_rows = cursor.fetchall()
        task_total = sum(row['count'] for row in task_rows)
        
        top_tasks = []
        for row in task_rows:
            task_type = row['task_type'] or 'Unknown'
            count = row['count']
            percentage = round((count / task_total * 100), 1) if task_total > 0 else 0
            
            # Clean up task type names
            task_type = task_type.replace('_', ' ').title()
            
            top_tasks.append({
                'task_type': task_type,
                'count': count,
                'percentage': percentage
            })
        
        # ==================================================================
        # TIME PATTERNS (Day of week analysis)
        # ==================================================================
        
        cursor.execute('''
            SELECT 
                strftime('%w', created_at) as day_num,
                COUNT(*) as count
            FROM task_history
            WHERE created_at >= ?
            GROUP BY day_num
            ORDER BY count DESC
        ''', (ninety_days_ago,))
        
        day_rows = cursor.fetchall()
        day_total = sum(row['count'] for row in day_rows)
        
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        
        time_patterns = []
        for row in day_rows[:3]:  # Top 3 days
            day_num = int(row['day_num'])
            count = row['count']
            percentage = round((count / day_total * 100), 1) if day_total > 0 else 0
            
            time_patterns.append({
                'day': day_names[day_num],
                'count': count,
                'percentage': percentage
            })
        
        # ==================================================================
        # COMMUNICATION STYLE
        # ==================================================================
        
        cursor.execute('''
            SELECT AVG(LENGTH(user_request)) as avg_length
            FROM task_history
            WHERE created_at >= ? AND user_request IS NOT NULL
        ''', (ninety_days_ago,))
        
        comm_data = cursor.fetchone()
        avg_message_length = int(comm_data['avg_length'] or 0)
        
        # Determine communication style
        if avg_message_length < 50:
            style = "Concise"
        elif avg_message_length < 150:
            style = "Balanced"
        else:
            style = "Detailed"
        
        communication_style = {
            'avg_message_length': avg_message_length,
            'style': style
        }
        
        db.close()
        
        # ==================================================================
        # RETURN COMPLETE DASHBOARD DATA
        # ==================================================================
        
        return jsonify({
            'success': True,
            'summary': summary,
            'top_task_types': top_tasks,
            'time_patterns': time_patterns,
            'communication_style': communication_style,
            'generated_at': datetime.now().isoformat()
        })
        
    except sqlite3.Error as e:
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


# I did no harm and this file is not truncated
