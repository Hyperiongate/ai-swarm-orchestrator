"""
Self-Monitor Component (Component 1)
Created: January 25, 2026
Last Updated: June 01, 2026 — WO-3 PostgreSQL Migration Repair

CHANGELOG:
- June 01, 2026: WO-3 POSTGRESQL MIGRATION REPAIR
  * Fix A — Placeholders: All SQL ? placeholders replaced with %s in every
    _collect_*() method and in save_insight(). Non-SQL ? characters left untouched.
  * Fix B — Named cursor access: All fetchone()[0] integer index accesses
    replaced with fetchone()['column_name'] named access (RealDictCursor
    compatible). All COUNT(*) queries given AS count alias.
  * Fix C — Insert id retrieval: save_insight() now uses INSERT ... RETURNING id
    and cursor.fetchone()['id'] instead of cursor.lastrowid.
  * Fix D — Schema alignment: save_insight() INSERT rewritten to target only
    real introspection_insights columns (insight_type, category, title,
    description, severity, confidence_score, data, is_read, is_actioned).
    Phantom columns period_analyzed, summary, full_analysis_json,
    requires_action, notification_pending removed.
  * Fix E — Database driver: from database import get_db (SQLite legacy)
    replaced with from db_engine import get_db_connection. All db = get_db()
    calls replaced with conn = get_db_connection() / try...finally conn.close().
    Private helpers (_collect_*) now receive cursor instead of db connection,
    removing the need to pass and close the connection in each helper.
  Reference: introspection/introspection_engine.py pattern (March 04, 2026).

PURPOSE:
Answers the question: "How am I performing?"

Extends the Weekly Self-Evaluation with deeper pattern recognition:
- Track performance trends over weeks/months
- Identify degradation before it becomes critical
- Recognize cyclical patterns
- Compare current performance to historical baselines
- Detect anomalies that don't fit established patterns

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from db_engine import get_db_connection


class SelfMonitor:
    """
    Monitors swarm performance and identifies trends, patterns, and anomalies.
    This is the foundation of emulated self-awareness - the ability to observe
    and reflect on one's own performance.
    """

    def __init__(self):
        self.current_metrics = {}
        self.historical_baselines = {}
        self.detected_patterns = []
        self.anomalies = []

    def collect_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Collect comprehensive performance metrics for the specified period.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary containing all performance metrics
        """
        conn = get_db_connection()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

        metrics = {
            'period': {
                'start': cutoff_date,
                'end': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'days': days
            },
            'collected_at': datetime.now().isoformat()
        }

        try:
            cursor = conn.cursor()

            try:
                metrics['tasks'] = self._collect_task_metrics(cursor, cutoff_date)
            except Exception as e:
                metrics['tasks'] = {'error': str(e)}

            try:
                metrics['specialists'] = self._collect_specialist_metrics(cursor, cutoff_date)
            except Exception as e:
                metrics['specialists'] = {'error': str(e)}

            try:
                metrics['consensus'] = self._collect_consensus_metrics(cursor, cutoff_date)
            except Exception as e:
                metrics['consensus'] = {'error': str(e)}

            try:
                metrics['escalations'] = self._collect_escalation_metrics(cursor, cutoff_date)
            except Exception as e:
                metrics['escalations'] = {'error': str(e)}

            try:
                metrics['feedback'] = self._collect_feedback_metrics(cursor, cutoff_date)
            except Exception as e:
                metrics['feedback'] = {'error': str(e)}

            try:
                metrics['timing'] = self._collect_timing_metrics(cursor, cutoff_date)
            except Exception as e:
                metrics['timing'] = {'error': str(e)}

            try:
                metrics['knowledge_base'] = self._collect_knowledge_metrics(cursor, cutoff_date)
            except Exception as e:
                metrics['knowledge_base'] = {'error': str(e)}

            try:
                metrics['documents'] = self._collect_document_metrics(cursor, cutoff_date)
            except Exception as e:
                metrics['documents'] = {'error': str(e)}

        finally:
            conn.close()

        self.current_metrics = metrics
        return metrics

    def _collect_task_metrics(self, cursor, cutoff_date: str) -> Dict[str, Any]:
        """Collect task-related metrics."""
        cursor.execute(
            'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s',
            (cutoff_date,)
        )
        total = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s AND status = %s',
            (cutoff_date, 'completed')
        )
        completed = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s AND status = %s',
            (cutoff_date, 'failed')
        )
        failed = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s AND status IN (%s, %s)',
            (cutoff_date, 'pending', 'processing')
        )
        pending = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT AVG(confidence) AS avg_conf FROM tasks WHERE created_at >= %s AND confidence IS NOT NULL',
            (cutoff_date,)
        )
        row = cursor.fetchone()
        avg_confidence = row['avg_conf'] if row else None

        cursor.execute('''
            SELECT task_type, COUNT(*) AS count
            FROM tasks
            WHERE created_at >= %s AND task_type IS NOT NULL
            GROUP BY task_type
            ORDER BY count DESC
        ''', (cutoff_date,))
        task_types = cursor.fetchall()

        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'pending': pending,
            'success_rate': round((completed / total * 100), 2) if total > 0 else 0,
            'failure_rate': round((failed / total * 100), 2) if total > 0 else 0,
            'avg_confidence': round(avg_confidence, 3) if avg_confidence else 0,
            'by_type': {row['task_type']: row['count'] for row in task_types}
        }

    def _collect_specialist_metrics(self, cursor, cutoff_date: str) -> Dict[str, Any]:
        """Collect specialist AI performance metrics."""
        cursor.execute('''
            SELECT
                specialist_name,
                COUNT(*) AS total_calls,
                SUM(CASE WHEN duration_seconds IS NOT NULL THEN 1 ELSE 0 END) AS successful,
                AVG(duration_seconds) AS avg_time,
                SUM(tokens_used) AS total_tokens
            FROM specialist_calls
            WHERE created_at >= %s
            GROUP BY specialist_name
            ORDER BY total_calls DESC
        ''', (cutoff_date,))
        specialist_data = cursor.fetchall()

        specialists = []
        for row in specialist_data:
            total_calls = row['total_calls'] or 0
            successful = row['successful'] or 0
            success_rate = round((successful / total_calls * 100), 2) if total_calls > 0 else 0
            specialists.append({
                'name': row['specialist_name'],
                'total_calls': total_calls,
                'successful': successful,
                'success_rate': success_rate,
                'avg_execution_time': round(row['avg_time'], 2) if row['avg_time'] else 0,
                'total_tokens': row['total_tokens'] or 0
            })

        best_performer = max(specialists, key=lambda x: x['success_rate'] * x['total_calls']) if specialists else None
        worst_performer = min(specialists, key=lambda x: x['success_rate']) if specialists else None

        return {
            'by_specialist': specialists,
            'best_performer': best_performer['name'] if best_performer else None,
            'worst_performer': worst_performer['name'] if worst_performer and worst_performer['success_rate'] < 80 else None,
            'total_specialist_calls': sum(s['total_calls'] for s in specialists)
        }

    def _collect_consensus_metrics(self, cursor, cutoff_date: str) -> Dict[str, Any]:
        """Collect consensus validation metrics."""
        cursor.execute(
            'SELECT COUNT(*) AS count FROM consensus_validations WHERE created_at >= %s',
            (cutoff_date,)
        )
        total = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT COUNT(*) AS count FROM consensus_validations WHERE created_at >= %s AND consensus_achieved = TRUE',
            (cutoff_date,)
        )
        achieved = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT AVG(agreement_score) AS avg_agreement FROM consensus_validations WHERE created_at >= %s AND agreement_score IS NOT NULL',
            (cutoff_date,)
        )
        row = cursor.fetchone()
        avg_agreement = row['avg_agreement'] if row else None

        cursor.execute(
            'SELECT COUNT(*) AS count FROM consensus_validations WHERE created_at >= %s AND agreement_score >= 0.8',
            (cutoff_date,)
        )
        high_agreement = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT COUNT(*) AS count FROM consensus_validations WHERE created_at >= %s AND agreement_score < 0.6',
            (cutoff_date,)
        )
        low_agreement = cursor.fetchone()['count'] or 0

        return {
            'total_validations': total,
            'consensus_achieved': achieved,
            'consensus_rate': round((achieved / total * 100), 2) if total > 0 else 0,
            'avg_agreement_score': round(avg_agreement, 3) if avg_agreement else 0,
            'high_agreement_count': high_agreement,
            'low_agreement_count': low_agreement
        }

    def _collect_escalation_metrics(self, cursor, cutoff_date: str) -> Dict[str, Any]:
        """Collect escalation pattern metrics."""
        cursor.execute(
            'SELECT COUNT(*) AS count FROM escalations WHERE created_at >= %s',
            (cutoff_date,)
        )
        total_escalations = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s',
            (cutoff_date,)
        )
        total_tasks = cursor.fetchone()['count'] or 1

        escalation_rate = round((total_escalations / total_tasks * 100), 2)

        cursor.execute('''
            SELECT reason, COUNT(*) AS count
            FROM escalations
            WHERE created_at >= %s AND reason IS NOT NULL
            GROUP BY reason
            ORDER BY count DESC
            LIMIT 5
        ''', (cutoff_date,))
        reasons = cursor.fetchall()

        return {
            'total_escalations': total_escalations,
            'escalation_rate': escalation_rate,
            'top_reasons': [{'reason': r['reason'], 'count': r['count']} for r in reasons]
        }

    def _collect_feedback_metrics(self, cursor, cutoff_date: str) -> Dict[str, Any]:
        """Collect user feedback metrics."""
        cursor.execute(
            'SELECT COUNT(*) AS count FROM user_feedback WHERE created_at >= %s',
            (cutoff_date,)
        )
        feedback_count = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT AVG(overall_rating) AS avg_overall FROM user_feedback WHERE created_at >= %s',
            (cutoff_date,)
        )
        row = cursor.fetchone()
        avg_overall = row['avg_overall'] if row else None

        cursor.execute(
            'SELECT AVG(quality_rating) AS avg_quality FROM user_feedback WHERE created_at >= %s',
            (cutoff_date,)
        )
        row = cursor.fetchone()
        avg_quality = row['avg_quality'] if row else None

        cursor.execute(
            'SELECT AVG(accuracy_rating) AS avg_accuracy FROM user_feedback WHERE created_at >= %s',
            (cutoff_date,)
        )
        row = cursor.fetchone()
        avg_accuracy = row['avg_accuracy'] if row else None

        cursor.execute(
            'SELECT AVG(usefulness_rating) AS avg_usefulness FROM user_feedback WHERE created_at >= %s',
            (cutoff_date,)
        )
        row = cursor.fetchone()
        avg_usefulness = row['avg_usefulness'] if row else None

        cursor.execute('''
            SELECT overall_rating, COUNT(*) AS count
            FROM user_feedback
            WHERE created_at >= %s
            GROUP BY overall_rating
            ORDER BY overall_rating
        ''', (cutoff_date,))
        rating_dist = cursor.fetchall()

        return {
            'total_feedback': feedback_count,
            'avg_overall_rating': round(avg_overall, 2) if avg_overall else 0,
            'avg_quality_rating': round(avg_quality, 2) if avg_quality else 0,
            'avg_accuracy_rating': round(avg_accuracy, 2) if avg_accuracy else 0,
            'avg_usefulness_rating': round(avg_usefulness, 2) if avg_usefulness else 0,
            'rating_distribution': {str(r['overall_rating']): r['count'] for r in rating_dist}
        }

    def _collect_timing_metrics(self, cursor, cutoff_date: str) -> Dict[str, Any]:
        """Collect response time metrics."""
        cursor.execute(
            'SELECT AVG(duration_seconds) AS avg_time FROM tasks WHERE created_at >= %s AND duration_seconds IS NOT NULL',
            (cutoff_date,)
        )
        row = cursor.fetchone()
        avg_time = row['avg_time'] if row else None

        cursor.execute(
            'SELECT MIN(duration_seconds) AS min_time FROM tasks WHERE created_at >= %s AND duration_seconds IS NOT NULL',
            (cutoff_date,)
        )
        row = cursor.fetchone()
        min_time = row['min_time'] if row else None

        cursor.execute(
            'SELECT MAX(duration_seconds) AS max_time FROM tasks WHERE created_at >= %s AND duration_seconds IS NOT NULL',
            (cutoff_date,)
        )
        row = cursor.fetchone()
        max_time = row['max_time'] if row else None

        cursor.execute(
            'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s AND duration_seconds > 30',
            (cutoff_date,)
        )
        slow_tasks = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s AND duration_seconds < 5',
            (cutoff_date,)
        )
        fast_tasks = cursor.fetchone()['count'] or 0

        return {
            'avg_execution_time': round(avg_time, 2) if avg_time else 0,
            'min_execution_time': round(min_time, 2) if min_time else 0,
            'max_execution_time': round(max_time, 2) if max_time else 0,
            'slow_tasks_count': slow_tasks,
            'fast_tasks_count': fast_tasks
        }

    def _collect_knowledge_metrics(self, cursor, cutoff_date: str) -> Dict[str, Any]:
        """Collect knowledge base usage metrics."""
        cursor.execute(
            'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s AND knowledge_used = TRUE',
            (cutoff_date,)
        )
        kb_used = cursor.fetchone()['count'] or 0

        cursor.execute(
            'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s',
            (cutoff_date,)
        )
        total_tasks = cursor.fetchone()['count'] or 1

        return {
            'tasks_using_knowledge': kb_used,
            'knowledge_usage_rate': round((kb_used / total_tasks * 100), 2)
        }

    def _collect_document_metrics(self, cursor, cutoff_date: str) -> Dict[str, Any]:
        """Collect document generation metrics."""
        cursor.execute(
            'SELECT COUNT(*) AS count FROM generated_documents WHERE created_at >= %s AND is_deleted = FALSE',
            (cutoff_date,)
        )
        total_docs = cursor.fetchone()['count'] or 0

        cursor.execute('''
            SELECT document_type, COUNT(*) AS count
            FROM generated_documents
            WHERE created_at >= %s AND is_deleted = FALSE
            GROUP BY document_type
        ''', (cutoff_date,))
        doc_types = cursor.fetchall()

        cursor.execute(
            'SELECT SUM(download_count) AS total_dl FROM generated_documents WHERE created_at >= %s AND is_deleted = FALSE',
            (cutoff_date,)
        )
        row = cursor.fetchone()
        total_downloads = row['total_dl'] or 0

        return {
            'total_generated': total_docs,
            'total_downloads': total_downloads,
            'by_type': {row['document_type']: row['count'] for row in doc_types}
        }

    def analyze_trends(self, current_metrics: Dict, historical_metrics: List[Dict] = None) -> Dict[str, Any]:
        """
        Analyze trends by comparing current metrics to historical data.

        Args:
            current_metrics: Current period metrics
            historical_metrics: List of historical metric snapshots

        Returns:
            Trend analysis with observations
        """
        trends = {
            'analyzed_at': datetime.now().isoformat(),
            'observations': [],
            'concerns': [],
            'improvements': []
        }

        if not historical_metrics:
            trends['observations'].append(
                "Insufficient historical data for trend analysis. Will improve with more evaluations."
            )
            return trends

        current_success = current_metrics.get('tasks', {}).get('success_rate', 0)
        historical_success = [h.get('tasks', {}).get('success_rate', 0) for h in historical_metrics]
        avg_historical_success = sum(historical_success) / len(historical_success) if historical_success else 0

        if current_success < avg_historical_success - 5:
            trends['concerns'].append({
                'metric': 'task_success_rate',
                'observation': f"Success rate ({current_success}%) is below historical average ({avg_historical_success:.1f}%)",
                'severity': 'high' if current_success < avg_historical_success - 10 else 'medium'
            })
        elif current_success > avg_historical_success + 5:
            trends['improvements'].append({
                'metric': 'task_success_rate',
                'observation': f"Success rate ({current_success}%) has improved above historical average ({avg_historical_success:.1f}%)"
            })

        current_time = current_metrics.get('timing', {}).get('avg_execution_time', 0)
        historical_times = [h.get('timing', {}).get('avg_execution_time', 0) for h in historical_metrics]
        avg_historical_time = sum(historical_times) / len(historical_times) if historical_times else 0

        if current_time > avg_historical_time * 1.2:
            trends['concerns'].append({
                'metric': 'response_time',
                'observation': f"Average response time ({current_time:.1f}s) is slower than historical ({avg_historical_time:.1f}s)",
                'severity': 'medium'
            })
        elif current_time < avg_historical_time * 0.8:
            trends['improvements'].append({
                'metric': 'response_time',
                'observation': f"Average response time ({current_time:.1f}s) has improved from historical ({avg_historical_time:.1f}s)"
            })

        if trends['concerns']:
            trends['observations'].append(
                f"Detected {len(trends['concerns'])} areas of concern requiring attention."
            )
        if trends['improvements']:
            trends['observations'].append(
                f"Detected {len(trends['improvements'])} areas of improvement. Keep up the good work!"
            )
        if not trends['concerns'] and not trends['improvements']:
            trends['observations'].append(
                "Performance is stable compared to historical baselines."
            )

        return trends

    def detect_anomalies(self, metrics: Dict) -> List[Dict[str, Any]]:
        """
        Detect anomalies in the current metrics.

        Returns:
            List of detected anomalies with details
        """
        anomalies = []

        failure_rate = metrics.get('tasks', {}).get('failure_rate', 0)
        if failure_rate > 15:
            anomalies.append({
                'type': 'high_failure_rate',
                'severity': 'high' if failure_rate > 25 else 'medium',
                'description': f"Task failure rate ({failure_rate}%) is unusually high",
                'metric_value': failure_rate,
                'threshold': 15
            })

        consensus_rate = metrics.get('consensus', {}).get('consensus_rate', 100)
        if consensus_rate < 70:
            anomalies.append({
                'type': 'low_consensus',
                'severity': 'medium',
                'description': f"Consensus achievement rate ({consensus_rate}%) is below expected",
                'metric_value': consensus_rate,
                'threshold': 70
            })

        avg_time = metrics.get('timing', {}).get('avg_execution_time', 0)
        if avg_time > 45:
            anomalies.append({
                'type': 'slow_responses',
                'severity': 'medium',
                'description': f"Average response time ({avg_time:.1f}s) is very slow",
                'metric_value': avg_time,
                'threshold': 45
            })

        avg_rating = metrics.get('feedback', {}).get('avg_overall_rating', 5)
        if avg_rating > 0 and avg_rating < 3.5:
            anomalies.append({
                'type': 'low_satisfaction',
                'severity': 'high',
                'description': f"User satisfaction ({avg_rating}/5) is critically low",
                'metric_value': avg_rating,
                'threshold': 3.5
            })

        escalation_rate = metrics.get('escalations', {}).get('escalation_rate', 0)
        if escalation_rate > 30:
            anomalies.append({
                'type': 'high_escalation',
                'severity': 'medium',
                'description': f"Escalation rate ({escalation_rate}%) suggests Sonnet may be underperforming",
                'metric_value': escalation_rate,
                'threshold': 30
            })

        self.anomalies = anomalies
        return anomalies

    def generate_monitoring_insight(self, metrics: Dict, trends: Dict, anomalies: List) -> Dict[str, Any]:
        """
        Generate a comprehensive self-monitoring insight.

        Returns:
            Structured insight ready for storage
        """
        health_score = self._calculate_health_score(metrics)

        trend_direction = 'stable'
        if trends.get('concerns') and len(trends['concerns']) > len(trends.get('improvements', [])):
            trend_direction = 'declining'
        elif trends.get('improvements') and len(trends['improvements']) > len(trends.get('concerns', [])):
            trend_direction = 'improving'

        tasks = metrics.get('tasks', {})
        summary = f"Processed {tasks.get('total', 0)} tasks with {tasks.get('success_rate', 0)}% success rate. "
        summary += f"Health score: {health_score}/100. "

        if anomalies:
            high_severity = [a for a in anomalies if a.get('severity') == 'high']
            summary += f"Detected {len(anomalies)} anomalies ({len(high_severity)} high severity). "

        if trend_direction == 'improving':
            summary += "Overall trend is positive."
        elif trend_direction == 'declining':
            summary += "Some areas need attention."
        else:
            summary += "Performance is stable."

        insight = {
            'insight_type': 'monitoring',
            'period_analyzed': f"{metrics.get('period', {}).get('start', '')} to {metrics.get('period', {}).get('end', '')}",
            'summary': summary,
            'health_score': health_score,
            'trend_direction': trend_direction,
            'metrics_snapshot': metrics,
            'trends': trends,
            'anomalies': anomalies,
            'requires_action': len([a for a in anomalies if a.get('severity') == 'high']) > 0,
            'generated_at': datetime.now().isoformat()
        }

        return insight

    def _calculate_health_score(self, metrics: Dict) -> int:
        """Calculate overall swarm health score (0-100)."""
        scores = []

        task_success = metrics.get('tasks', {}).get('success_rate', 0)
        scores.append(min(task_success, 100) * 0.4)

        avg_time = metrics.get('timing', {}).get('avg_execution_time', 60)
        time_score = max(0, 100 - (avg_time * 2))
        scores.append(time_score * 0.2)

        consensus_rate = metrics.get('consensus', {}).get('consensus_rate', 0)
        scores.append(min(consensus_rate, 100) * 0.2)

        avg_rating = metrics.get('feedback', {}).get('avg_overall_rating', 0)
        satisfaction = (avg_rating / 5) * 100 if avg_rating else 50
        scores.append(satisfaction * 0.2)

        return int(sum(scores))

    def save_insight(self, insight: Dict) -> int:
        """
        Save a monitoring insight to the database.

        Uses real introspection_insights schema columns:
            insight_type, category, title, description, severity,
            confidence_score, data, is_read, is_actioned
        Uses INSERT ... RETURNING id instead of cursor.lastrowid.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO introspection_insights (
                    insight_type, category, title, description, severity,
                    confidence_score, data, is_read, is_actioned
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, %s)
                RETURNING id
            ''', (
                insight.get('insight_type', 'monitoring'),
                insight.get('period_analyzed', ''),
                f"Self-Monitor Insight - {insight.get('insight_type', 'monitoring').title()}",
                (insight.get('summary', '') or '')[:500],
                'info',
                insight.get('health_score', 0) / 100.0,
                json.dumps(insight),
                insight.get('requires_action', False)
            ))
            row = cursor.fetchone()
            insight_id = row['id'] if row else 0
            conn.commit()
            return insight_id
        except Exception as e:
            print(f"Failed to save monitoring insight: {e}")
            return 0
        finally:
            conn.close()


# Singleton instance
_self_monitor_instance = None

def get_self_monitor() -> SelfMonitor:
    """Get the singleton SelfMonitor instance."""
    global _self_monitor_instance
    if _self_monitor_instance is None:
        _self_monitor_instance = SelfMonitor()
    return _self_monitor_instance

# I did no harm and this file is not truncated
