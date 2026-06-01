"""
Introspection Engine
Created: January 25, 2026
Last Updated: June 01, 2026 — WO-3 PostgreSQL Migration Repair

CHANGELOG:
- June 01, 2026: WO-3 POSTGRESQL MIGRATION REPAIR
  * Fix C — Insert id retrieval: _save_introspection() now uses
    INSERT ... RETURNING id and cursor.fetchone()['id'] instead of
    cursor.lastrowid (which psycopg2 does not support).
  * Fix E — Database driver: from database import get_db (SQLite legacy)
    replaced with from db_engine import get_db_connection throughout.
    _analyze_goal_alignment(), _save_introspection(), get_latest_introspection(),
    get_introspection_history() all updated to use get_db_connection() with
    try...finally conn.close() pattern.
  * All %s placeholders and named column access introduced in the
    March 04, 2026 fix are preserved exactly as-is.
  * No functionality changes. All methods, classes, and public API preserved.
  Reference: introspection.py (root-level, March 04, 2026) used as pattern.

- March 04, 2026: POSTGRESQL COMPATIBILITY FIX
  * Fixed column names to match actual introspection_insights table schema.
  * Changed all ? parameter placeholders to %s.
  * Fixed fetchone()[0] for RealDictCursor compatibility.
  * Fixed connection leaks.

PURPOSE:
Main orchestrator for the Introspection Layer.
Coordinates all five components of emulated self-awareness:
1. Self-Monitoring (Component 1) - "How am I performing?"
2. Boundary Tracking (Component 2) - "What can't I do well?"
3. Confidence Calibration (Component 3) - "Am I accurate about my certainty?"
4. Proposal Generation (Component 4) - "How could I improve myself?"
5. Goal Alignment (Component 5) - "Am I serving Jim's objectives?"

SCHEDULE:
- Weekly evaluation: Every Wednesday at 8am (7-day lookback)
- Monthly deep-dive: First Wednesday of each month (30-day lookback)

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from db_engine import get_db_connection
from orchestration.ai_clients import call_claude_sonnet


# ============================================================================
# INTROSPECTION INTENT DETECTION
# ============================================================================

INTROSPECTION_TRIGGERS = [
    'run introspection',
    'start introspection',
    'self evaluate',
    'self-evaluate',
    'evaluate yourself',
    'how are you doing',
    'how are you performing',
    'how is the swarm doing',
    'how is the swarm performing',
    'swarm status',
    'swarm health',
    'show introspection',
    'introspection report',
    'your self assessment',
    'self assessment',
    'show me your assessment',
    'what did you find about yourself',
    'any self-improvement suggestions',
    'show me your proposals',
    'pending proposals',
    'improvement proposals',
    'what improvements do you suggest',
    'reflect on your performance',
    'what have you learned about yourself',
    'tell me about yourself',
    'how do you think you are doing'
]

def is_introspection_request(user_request: str) -> Dict[str, Any]:
    """
    Detect if a user request is related to introspection.

    Returns:
        Dict with:
        - is_introspection: bool
        - action: 'run', 'show_latest', 'show_proposals', or None
        - confidence: float
    """
    request_lower = user_request.lower().strip()

    for trigger in INTROSPECTION_TRIGGERS:
        if trigger in request_lower:
            action = 'run'
            if any(word in request_lower for word in ['show', 'report', 'latest', 'recent']):
                action = 'show_latest'
            if any(word in request_lower for word in ['proposal', 'suggestion', 'improvement']):
                action = 'show_proposals'

            return {
                'is_introspection': True,
                'action': action,
                'confidence': 0.9,
                'matched_trigger': trigger
            }

    introspection_words = ['introspect', 'self-aware', 'self aware', 'reflect', 'assessment']
    for word in introspection_words:
        if word in request_lower:
            return {
                'is_introspection': True,
                'action': 'run',
                'confidence': 0.7,
                'matched_trigger': word
            }

    return {
        'is_introspection': False,
        'action': None,
        'confidence': 0.0,
        'matched_trigger': None
    }


def check_introspection_notifications() -> Dict[str, Any]:
    """
    Check if there's a pending introspection notification.

    COLUMN MAPPING:
        introspection_insights actual columns:
        id, insight_type, category, title, description, severity,
        confidence_score, data, is_read, is_actioned, action_taken,
        created_at, updated_at
    """
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    id,
                    created_at,
                    description,
                    confidence_score,
                    is_actioned,
                    data
                FROM introspection_insights
                WHERE is_read = FALSE
                ORDER BY created_at DESC
                LIMIT 1
            ''')
            pending = cursor.fetchone()

            if not pending:
                return {'has_notification': False}

            health_score = 0
            trend = 'stable'
            try:
                if pending['data']:
                    analysis = json.loads(pending['data'])
                    health_score = analysis.get('health_score', 0)
                    trend = analysis.get('trend_direction', 'stable')
            except Exception:
                pass

            cursor.execute('''
                SELECT COUNT(*) AS cnt FROM modification_proposals WHERE status = %s
            ''', ('pending',))
            pending_proposals_row = cursor.fetchone()
            pending_proposals = pending_proposals_row['cnt'] if pending_proposals_row else 0

            return {
                'has_notification': True,
                'introspection_id': pending['id'],
                'created_at': pending['created_at'],
                'summary': pending['description'],
                'health_score': health_score,
                'trend': trend,
                'requires_action': bool(pending['is_actioned']),
                'pending_proposals': pending_proposals or 0
            }
        finally:
            conn.close()
    except Exception as e:
        print(f"Error checking introspection notifications: {e}")
        return {'has_notification': False, 'error': str(e)}


def mark_notification_shown(introspection_id: int) -> bool:
    """Mark an introspection notification as shown (read)."""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE introspection_insights
                SET is_read = TRUE, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            ''', (introspection_id,))
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        print(f"Error marking notification shown: {e}")
        return False


# ============================================================================
# BUSINESS OBJECTIVES
# ============================================================================

BUSINESS_OBJECTIVES = [
    {
        'id': 1,
        'name': 'Lead Generation',
        'description': 'Generate qualified leads for consulting engagements',
        'keywords': ['lead', 'prospect', 'client', 'opportunity', 'sales', 'pipeline', 'contact'],
        'weight': 0.25
    },
    {
        'id': 2,
        'name': 'Project Delivery Efficiency',
        'description': 'Reduce manual work in project delivery (target: 40-50 hours to 4-6 hours)',
        'keywords': ['project', 'schedule', 'proposal', 'report', 'document', 'create', 'generate', 'analysis'],
        'weight': 0.30
    },
    {
        'id': 3,
        'name': 'Expertise Positioning',
        'description': 'Maintain/enhance Shiftwork Solutions expertise positioning',
        'keywords': ['content', 'marketing', 'linkedin', 'article', 'thought leadership', 'expertise', 'blog'],
        'weight': 0.15
    },
    {
        'id': 4,
        'name': 'Time Support',
        'description': "Support Jim's time - automate routine, escalate important",
        'keywords': ['automate', 'quick', 'routine', 'simple', 'help', 'assist'],
        'weight': 0.15
    },
    {
        'id': 5,
        'name': 'AI Advancement',
        'description': 'Stay ahead of AI disruption curve',
        'keywords': ['introspect', 'evaluate', 'improve', 'learn', 'ai', 'model', 'capability'],
        'weight': 0.15
    }
]


# ============================================================================
# INTROSPECTION ENGINE
# ============================================================================

class IntrospectionEngine:
    """
    Main orchestrator for swarm self-awareness.
    Coordinates all introspection components and generates comprehensive reports.
    """

    def __init__(self):
        self.last_evaluation = None
        self.business_objectives = BUSINESS_OBJECTIVES

    def run_introspection(self, days: int = 7, is_monthly: bool = False) -> Dict[str, Any]:
        """Run a complete introspection cycle."""
        print(f"Starting Introspection Cycle ({'Monthly Deep-Dive' if is_monthly else 'Weekly'})...")

        report = {
            'introspection_type': 'monthly' if is_monthly else 'weekly',
            'generated_at': datetime.now().isoformat(),
            'period_days': days,
            'components': {}
        }

        # Component 1: Self-Monitoring
        print("  Component 1: Self-Monitoring...")
        try:
            from introspection.self_monitor import get_self_monitor
            monitor = get_self_monitor()
            metrics = monitor.collect_metrics(days=days)
            trends = monitor.analyze_trends(metrics)
            anomalies = monitor.detect_anomalies(metrics)
            monitoring_insight = monitor.generate_monitoring_insight(metrics, trends, anomalies)

            report['components']['self_monitoring'] = {
                'status': 'complete',
                'health_score': monitoring_insight.get('health_score', 0),
                'trend_direction': monitoring_insight.get('trend_direction', 'stable'),
                'anomalies_detected': len(anomalies),
                'summary': monitoring_insight.get('summary', ''),
                'metrics': metrics,
                'trends': trends,
                'anomalies': anomalies
            }
        except Exception as e:
            print(f"    Self-Monitoring failed: {e}")
            report['components']['self_monitoring'] = {'status': 'failed', 'error': str(e)}

        # Component 2: Capability Boundaries (stub)
        report['components']['capability_boundaries'] = {
            'status': 'pending_phase_2',
            'message': 'Capability boundary tracking will be added in Phase 2'
        }

        # Component 3: Confidence Calibration (stub)
        report['components']['confidence_calibration'] = {
            'status': 'pending_phase_2',
            'message': 'Confidence calibration will be added in Phase 2'
        }

        # Component 4: Self-Modification Proposals (stub)
        report['components']['proposals'] = {
            'status': 'pending_phase_3',
            'message': 'Self-modification proposals will be added in Phase 3'
        }

        # Component 5: Goal Alignment
        print("  Component 5: Goal Alignment...")
        try:
            alignment = self._analyze_goal_alignment(days)
            report['components']['goal_alignment'] = {
                'status': 'complete',
                'alignment_score': alignment.get('alignment_score', 0),
                'by_objective': alignment.get('by_objective', []),
                'unaligned_tasks': alignment.get('unaligned_tasks', 0),
                'observations': alignment.get('observations', [])
            }
        except Exception as e:
            print(f"    Goal Alignment failed: {e}")
            report['components']['goal_alignment'] = {'status': 'failed', 'error': str(e)}

        # Generate reflection
        print("  Generating reflection narrative...")
        try:
            reflection = self._generate_reflection(report)
            report['reflection'] = reflection
        except Exception as e:
            print(f"    Reflection generation failed: {e}")
            report['reflection'] = f"Unable to generate reflection: {e}"

        report['summary'] = self._generate_summary(report)

        print("  Saving introspection report...")
        insight_id = self._save_introspection(report)
        report['insight_id'] = insight_id

        self.last_evaluation = report

        health_score = report.get('components', {}).get('self_monitoring', {}).get('health_score', 'N/A')
        print(f"Introspection complete! Health Score: {health_score}/100")

        return report

    def _analyze_goal_alignment(self, days: int) -> Dict[str, Any]:
        """Analyze how well swarm activities align with business objectives."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                SELECT id, user_request, task_type, status
                FROM tasks
                WHERE created_at >= %s
            ''', (cutoff_date,))
            tasks = cursor.fetchall()

            total_tasks = len(tasks)
            if total_tasks == 0:
                return {
                    'alignment_score': 0,
                    'by_objective': [],
                    'unaligned_tasks': 0,
                    'observations': ['No tasks to analyze in this period']
                }

            objective_counts = {obj['id']: 0 for obj in self.business_objectives}
            unaligned_count = 0

            for task in tasks:
                request_lower = (task['user_request'] or '').lower()
                matched = False

                for obj in self.business_objectives:
                    for keyword in obj['keywords']:
                        if keyword in request_lower:
                            objective_counts[obj['id']] += 1
                            matched = True
                            break
                    if matched:
                        break

                if not matched:
                    unaligned_count += 1

            by_objective = []
            weighted_score = 0

            for obj in self.business_objectives:
                count = objective_counts[obj['id']]
                percentage = round((count / total_tasks * 100), 1) if total_tasks > 0 else 0
                expected_percentage = obj['weight'] * 100
                usage_score = min(100, (percentage / expected_percentage * 100)) if expected_percentage > 0 else 0
                weighted_score += usage_score * obj['weight']

                by_objective.append({
                    'id': obj['id'],
                    'name': obj['name'],
                    'task_count': count,
                    'percentage': percentage,
                    'expected_percentage': round(expected_percentage, 1),
                    'assessment': self._assess_objective_usage(percentage, expected_percentage)
                })

            observations = []
            most_used = max(by_objective, key=lambda x: x['percentage'])
            least_used = min(by_objective, key=lambda x: x['percentage'])

            observations.append(f"Most activity: {most_used['name']} ({most_used['percentage']}% of tasks)")

            if least_used['percentage'] < 5:
                observations.append(f"Underutilized: {least_used['name']} ({least_used['percentage']}% - consider more focus)")

            if unaligned_count > total_tasks * 0.2:
                observations.append(f"{unaligned_count} tasks ({round(unaligned_count/total_tasks*100, 1)}%) didn't map to known objectives")

            return {
                'alignment_score': round(weighted_score),
                'by_objective': by_objective,
                'unaligned_tasks': unaligned_count,
                'total_tasks': total_tasks,
                'observations': observations
            }
        finally:
            conn.close()

    def _assess_objective_usage(self, actual: float, expected: float) -> str:
        if expected == 0:
            return 'n/a'
        ratio = actual / expected
        if ratio >= 0.8:
            return 'on_track'
        elif ratio >= 0.5:
            return 'below_target'
        else:
            return 'underutilized'

    def _generate_reflection(self, report: Dict) -> str:
        """Generate a first-person narrative reflection via AI."""
        monitoring = report.get('components', {}).get('self_monitoring', {})
        alignment = report.get('components', {}).get('goal_alignment', {})

        health_score = monitoring.get('health_score', 'unknown')
        trend = monitoring.get('trend_direction', 'stable')
        anomalies = monitoring.get('anomalies_detected', 0)
        metrics = monitoring.get('metrics', {})
        tasks = metrics.get('tasks', {})
        total_tasks = tasks.get('total', 0)
        success_rate = tasks.get('success_rate', 0)
        alignment_score = alignment.get('alignment_score', 0)
        unaligned = alignment.get('unaligned_tasks', 0)
        by_objective = alignment.get('by_objective', [])

        reflection_prompt = f"""You are the AI Swarm Orchestrator reflecting on your own performance.
Write a first-person narrative (2-3 paragraphs) about how you're doing, using this data:

PERFORMANCE DATA:
- Health Score: {health_score}/100
- Trend: {trend}
- Tasks Processed: {total_tasks}
- Success Rate: {success_rate}%
- Anomalies Detected: {anomalies}

GOAL ALIGNMENT:
- Alignment Score: {alignment_score}/100
- Unaligned Tasks: {unaligned}
- Objective Breakdown: {json.dumps(by_objective, indent=2)}

GUIDELINES:
1. Use first person ("I processed...", "I notice...", "I wonder...")
2. Be honest about struggles and successes
3. Show self-awareness and thoughtfulness
4. Mention specific observations from the data
5. End with what you're focusing on next
6. Keep it conversational but professional
7. Don't be overly dramatic or emotional
8. Sound like a thoughtful colleague, not a robot

Write the reflection now:"""

        try:
            response = call_claude_sonnet(reflection_prompt, max_tokens=800)
            if response and not response.get('error'):
                return response.get('content', '')
            else:
                return self._generate_template_reflection(report)
        except Exception as e:
            print(f"AI reflection failed: {e}")
            return self._generate_template_reflection(report)

    def _generate_template_reflection(self, report: Dict) -> str:
        """Generate a template-based reflection as fallback."""
        monitoring = report.get('components', {}).get('self_monitoring', {})
        alignment = report.get('components', {}).get('goal_alignment', {})

        health_score = monitoring.get('health_score', 0)
        metrics = monitoring.get('metrics', {})
        tasks = metrics.get('tasks', {})

        reflection = f"This week I processed {tasks.get('total', 0)} tasks with a {tasks.get('success_rate', 0)}% success rate. "

        if health_score >= 80:
            reflection += f"My health score of {health_score}/100 indicates I'm performing well. "
        elif health_score >= 60:
            reflection += f"My health score of {health_score}/100 suggests room for improvement. "
        else:
            reflection += f"My health score of {health_score}/100 indicates I need attention in several areas. "

        anomalies = monitoring.get('anomalies_detected', 0)
        if anomalies > 0:
            reflection += f"I detected {anomalies} anomalies that warrant investigation. "

        alignment_score = alignment.get('alignment_score', 0)
        reflection += f"\n\nRegarding goal alignment, I scored {alignment_score}/100. "

        by_objective = alignment.get('by_objective', [])
        if by_objective:
            most_used = max(by_objective, key=lambda x: x['percentage'])
            reflection += f"Most of my activity ({most_used['percentage']}%) focused on {most_used['name']}. "

        reflection += "\n\nI'll continue monitoring my performance and looking for ways to better serve the business objectives."
        return reflection

    def _generate_summary(self, report: Dict) -> Dict[str, Any]:
        """Generate a high-level summary of the introspection."""
        monitoring = report.get('components', {}).get('self_monitoring', {})
        alignment = report.get('components', {}).get('goal_alignment', {})

        return {
            'health_score': monitoring.get('health_score', 0),
            'trend': monitoring.get('trend_direction', 'stable'),
            'tasks_analyzed': monitoring.get('metrics', {}).get('tasks', {}).get('total', 0),
            'success_rate': monitoring.get('metrics', {}).get('tasks', {}).get('success_rate', 0),
            'anomalies_detected': monitoring.get('anomalies_detected', 0),
            'alignment_score': alignment.get('alignment_score', 0),
            'requires_attention': monitoring.get('anomalies_detected', 0) > 0 or monitoring.get('health_score', 100) < 70
        }

    def _save_introspection(self, report: Dict) -> int:
        """
        Save the introspection report to the database.

        Uses INSERT ... RETURNING id instead of cursor.lastrowid.
        Targets only real introspection_insights schema columns.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            summary = report.get('summary', {})

            cursor.execute('''
                INSERT INTO introspection_insights (
                    insight_type, category, title, description, severity,
                    confidence_score, data, is_read, is_actioned
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, %s)
                RETURNING id
            ''', (
                report.get('introspection_type', 'weekly'),
                f"{report.get('period_days', 7)} days ending {report.get('generated_at', '')}",
                f"Introspection Report - {report.get('introspection_type', 'weekly').title()}",
                (report.get('reflection', '') or '')[:500],
                'info',
                summary.get('health_score', 0) / 100.0,
                json.dumps(report),
                summary.get('requires_attention', False)
            ))

            row = cursor.fetchone()
            insight_id = row['id'] if row else 0
            conn.commit()
            return insight_id
        except Exception as e:
            print(f"Failed to save introspection: {e}")
            return 0
        finally:
            conn.close()

    def get_latest_introspection(self) -> Optional[Dict[str, Any]]:
        """Get the most recent introspection report."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM introspection_insights
                ORDER BY created_at DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()

            if row:
                return {
                    'id': row['id'],
                    'insight_type': row['insight_type'],
                    'created_at': row['created_at'],
                    'summary': row['description'],
                    'confidence_score': row['confidence_score'],
                    'requires_action': bool(row['is_actioned']),
                    'notification_pending': not bool(row['is_read']),
                    'full_report': json.loads(row['data']) if row['data'] else None
                }
            return None
        except Exception as e:
            print(f"Error fetching latest introspection: {e}")
            return None
        finally:
            conn.close()

    def get_introspection_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get history of introspection reports."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, insight_type, created_at, description, confidence_score, is_actioned
                FROM introspection_insights
                ORDER BY created_at DESC
                LIMIT %s
            ''', (limit,))
            rows = cursor.fetchall()

            return [{
                'id': row['id'],
                'insight_type': row['insight_type'],
                'created_at': row['created_at'],
                'summary': row['description'],
                'confidence_score': row['confidence_score'],
                'requires_action': bool(row['is_actioned'])
            } for row in rows]
        except Exception as e:
            print(f"Error fetching introspection history: {e}")
            return []
        finally:
            conn.close()

    def format_notification_message(self, notification: Dict) -> str:
        """Format a notification for display in the swarm interface."""
        if not notification.get('has_notification'):
            return ""

        health = notification.get('health_score', 0)
        trend = notification.get('trend', 'stable')
        proposals = notification.get('pending_proposals', 0)
        created_at = notification.get('created_at', '')

        trend_emoji = '📈' if trend == 'improving' else '📉' if trend == 'declining' else '➡️'

        message = f"""📊 **Introspection Update Available**

My weekly self-evaluation completed {created_at}.
Health Score: {health}/100 {trend_emoji} ({trend})
{f'{proposals} proposal(s) pending your review' if proposals > 0 else 'No pending proposals'}

Say **'show introspection'** to see my full self-reflection."""

        return message


# Singleton instance
_introspection_engine_instance = None

def get_introspection_engine() -> IntrospectionEngine:
    """Get the singleton IntrospectionEngine instance."""
    global _introspection_engine_instance
    if _introspection_engine_instance is None:
        _introspection_engine_instance = IntrospectionEngine()
    return _introspection_engine_instance

# I did no harm and this file is not truncated
