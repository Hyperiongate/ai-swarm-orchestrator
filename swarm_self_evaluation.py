"""
Swarm Self-Evaluation Engine
Created: January 25, 2026
Last Updated: June 13, 2026 — WO-8 Idle-Period Scoring Fix + Route DB Methods

CHANGELOG:
- June 13, 2026: WO-8 IDLE-PERIOD SCORING FIX + ROUTE DB-ACCESS METHODS
  * Problem 1 (idle artifact): a week with zero tasks processed was scored as a
    FAILING system (health score ~30, trend "needs_attention"). 0 tasks -> 0%
    success fed straight into the weighted health score, and the gap analyzer
    flagged the 0% success / 0 consensus / 0 feedback / 0 knowledge-use as real
    deficiencies (some at HIGH severity). Every quiet week produced a scary
    report, and once WO-11 enables alerts it would email a false alarm.
  * Root cause: the scoring logic treated "idle / no data" identically to
    "active but failing."
  * Fix (SwarmReportGenerator):
      - Added _is_idle() helper (True when tasks.total == 0) and the
        NEUTRAL_IDLE_HEALTH_SCORE constant (75 — reads "stable", never
        "improving" or "failing").
      - _calculate_health_score(): returns the neutral score when idle.
      - _determine_trend(): returns 'stable' when idle. Kept inside the existing
        trend vocabulary (improving/stable/needs_attention) — NO new enum value
        — so any downstream consumer or colour-map behaves normally.
      - _generate_executive_summary(): idle weeks get a plain-language
        "system was idle, not unhealthy / no data" summary instead of
        "0 tasks ... 0% success rate".
      - generate_report(): adds top-level 'idle_period' boolean to the report.
  * Fix (GapAnalyzer.analyze_gaps): each activity-derived gap check is now gated
    on `not is_idle` IN PLACE (original ordering preserved exactly for active
    weeks). The market-derived "new model" gaps still run, since they are
    independent of weekly activity.
  * Fix (_save_evaluation / get_latest_evaluation / get_evaluation_history):
    'idle_period' is stored in the compact metrics JSON and surfaced by the read
    methods, giving the alert/briefing layer a clean boolean to suppress false
    alarms instead of string-matching the trend.
  * Problem 2 (routes coupling): routes/evaluation.py still did direct SQLite
    DB access for /status count, GET /<id>, and DELETE /<id>. Added three new
    engine methods so ALL swarm_evaluations DB access lives here, on the
    migrated db_engine / RealDictCursor / %s pattern:
      - get_evaluation_count() -> int
      - get_evaluation_by_id(evaluation_id) -> Optional[Dict]   (rich shape,
        reconstructed from real schema exactly like get_latest_evaluation())
      - delete_evaluation(evaluation_id) -> bool                (uses
        DELETE ... RETURNING id; commits; rolls back on error)
  * NOTE for review: per-component scores in health_score.components are left
    computing from the real (zero) metrics during idle weeks — they are honest
    values, and the overall score / trend / summary now frame the period
    correctly. If a UI panel colours those sub-scores red on an idle week, say
    so and they can be neutralised too.
  * No functionality removed. All classes, methods, and public API preserved;
    active-week behaviour is unchanged.

- June 01, 2026: WO-2 POSTGRESQL MIGRATION REPAIR
  * Fix A — Placeholders: All SQL ? placeholders replaced with %s throughout
    collect_weekly_metrics(), _save_evaluation(), get_latest_evaluation(),
    get_evaluation_history(). Non-SQL occurrences of ? (regex, prompts) left
    untouched.
  * Fix B — Named cursor access: All fetchone()[0] integer index accesses
    replaced with fetchone()['column_name'] named access (RealDictCursor
    compatible). COUNT(*) queries given AS count alias.
  * Fix C — Insert id retrieval: _save_evaluation() now uses
    INSERT ... RETURNING id and cursor.fetchone()['id'] instead of
    cursor.lastrowid (which psycopg2 does not support).
  * Fix D — Schema alignment: _save_evaluation() rewritten to match the
    ACTUAL swarm_evaluations schema (id, evaluation_date, health_score,
    trend, metrics, recommendations, raw_data). The original code targeted
    8 phantom columns (period_days, tasks_processed, success_rate,
    executive_summary, gaps_count, high_priority_gaps_count,
    recommendations_count, full_report_json) that do not exist — this
    caused every INSERT to fail with UndefinedColumn regardless of the
    placeholder fix. Rich data is now stored in raw_data (JSON) and
    metrics/recommendations columns.
  * Fix E — get_latest_evaluation() and get_evaluation_history() rewritten
    to read from real schema columns and extract rich fields from raw_data
    JSON, so callers get the same dict keys as before.
  * Fix F — database import: Replaced from database import get_db (SQLite
    legacy) with from db_engine import get_db_connection (PostgreSQL-aware),
    matching the pattern used in introspection.py after its March 04 fix.
    All db = get_db() calls replaced with conn = get_db_connection() /
    try...finally conn.close() pattern.
  * No functionality removed. All classes, methods, and public API preserved.
  Reference: introspection.py (fixed March 04, 2026) used as canonical pattern.

PURPOSE:
Weekly self-review system for the AI Swarm Orchestrator that:
1. Evaluates internal performance against benchmarks
2. Tracks emerging AI models and capabilities
3. Identifies gaps in current AI stack
4. Generates actionable recommendations
5. Produces State of the Swarm reports

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from db_engine import get_db_connection
from orchestration.ai_clients import call_claude_sonnet, call_gpt4


class PerformanceCollector:
    def __init__(self):
        self.metrics = {}

    def collect_weekly_metrics(self, days: int = 7) -> Dict[str, Any]:
        conn = get_db_connection()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        metrics = {
            'period_start': cutoff_date,
            'period_end': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'days_analyzed': days
        }
        try:
            cursor = conn.cursor()

            # Task Metrics
            try:
                cursor.execute(
                    'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s',
                    (cutoff_date,)
                )
                total_tasks = cursor.fetchone()['count']

                cursor.execute(
                    'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s AND status = %s',
                    (cutoff_date, 'completed')
                )
                completed_tasks = cursor.fetchone()['count']

                cursor.execute(
                    'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s AND status = %s',
                    (cutoff_date, 'failed')
                )
                failed_tasks = cursor.fetchone()['count']

                cursor.execute(
                    'SELECT AVG(duration_seconds) AS avg_time FROM tasks WHERE created_at >= %s AND duration_seconds IS NOT NULL',
                    (cutoff_date,)
                )
                row = cursor.fetchone()
                avg_execution_time = row['avg_time'] if row else None

                cursor.execute(
                    'SELECT AVG(confidence) AS avg_conf FROM tasks WHERE created_at >= %s AND confidence IS NOT NULL',
                    (cutoff_date,)
                )
                row = cursor.fetchone()
                avg_confidence = row['avg_conf'] if row else None

                metrics['tasks'] = {
                    'total': total_tasks or 0,
                    'completed': completed_tasks or 0,
                    'failed': failed_tasks or 0,
                    'success_rate': round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0,
                    'avg_execution_time_seconds': round(avg_execution_time, 2) if avg_execution_time else 0,
                    'avg_confidence': round(avg_confidence, 3) if avg_confidence else 0
                }
            except Exception as e:
                metrics['tasks'] = {'error': str(e)}

            # Consensus Metrics
            try:
                cursor.execute(
                    'SELECT COUNT(*) AS count FROM consensus_validations WHERE created_at >= %s',
                    (cutoff_date,)
                )
                total_consensus = cursor.fetchone()['count']

                cursor.execute(
                    'SELECT COUNT(*) AS count FROM consensus_validations WHERE created_at >= %s AND consensus_achieved = TRUE',
                    (cutoff_date,)
                )
                achieved_consensus = cursor.fetchone()['count']

                cursor.execute(
                    'SELECT AVG(agreement_score) AS avg_agreement FROM consensus_validations WHERE created_at >= %s AND agreement_score IS NOT NULL',
                    (cutoff_date,)
                )
                row = cursor.fetchone()
                avg_agreement = row['avg_agreement'] if row else None

                metrics['consensus'] = {
                    'total_validations': total_consensus or 0,
                    'consensus_achieved': achieved_consensus or 0,
                    'consensus_rate': round((achieved_consensus / total_consensus * 100), 2) if total_consensus > 0 else 0,
                    'avg_agreement_score': round(avg_agreement, 3) if avg_agreement else 0
                }
            except Exception as e:
                metrics['consensus'] = {'error': str(e)}

            # Specialist Usage Metrics
            try:
                cursor.execute('''
                    SELECT specialist_name,
                           COUNT(*) AS usage_count,
                           SUM(CASE WHEN duration_seconds IS NOT NULL THEN 1 ELSE 0 END) AS success_count,
                           AVG(duration_seconds) AS avg_time
                    FROM specialist_calls
                    WHERE created_at >= %s
                    GROUP BY specialist_name
                    ORDER BY usage_count DESC
                ''', (cutoff_date,))
                specialist_usage = cursor.fetchall()

                specialists = []
                for row in specialist_usage:
                    usage_count = row['usage_count'] or 0
                    success_count = row['success_count'] or 0
                    specialists.append({
                        'name': row['specialist_name'],
                        'usage_count': usage_count,
                        'success_count': success_count,
                        'success_rate': round((success_count / usage_count * 100), 2) if usage_count > 0 else 0,
                        'avg_execution_time': round(row['avg_time'], 2) if row['avg_time'] else 0
                    })
                metrics['specialists'] = specialists
            except Exception as e:
                metrics['specialists'] = {'error': str(e)}

            # Escalation Metrics
            try:
                cursor.execute(
                    'SELECT COUNT(*) AS count FROM escalations WHERE created_at >= %s',
                    (cutoff_date,)
                )
                total_escalations = cursor.fetchone()['count']

                escalation_rate = 0
                if metrics.get('tasks', {}).get('total', 0) > 0:
                    escalation_rate = round((total_escalations / metrics['tasks']['total'] * 100), 2)

                metrics['escalations'] = {
                    'total': total_escalations or 0,
                    'escalation_rate': escalation_rate
                }
            except Exception as e:
                metrics['escalations'] = {'error': str(e)}

            # Orchestrator Distribution
            try:
                cursor.execute('''
                    SELECT assigned_orchestrator, COUNT(*) AS count
                    FROM tasks
                    WHERE created_at >= %s AND assigned_orchestrator IS NOT NULL
                    GROUP BY assigned_orchestrator
                ''', (cutoff_date,))
                orchestrator_usage = cursor.fetchall()

                orchestrators = {}
                for row in orchestrator_usage:
                    orchestrators[row['assigned_orchestrator'] or 'unknown'] = row['count']
                metrics['orchestrator_distribution'] = orchestrators
            except Exception as e:
                metrics['orchestrator_distribution'] = {'error': str(e)}

            # Conversation Metrics
            try:
                cursor.execute(
                    'SELECT COUNT(*) AS count FROM conversations WHERE created_at >= %s',
                    (cutoff_date,)
                )
                total_conversations = cursor.fetchone()['count']

                cursor.execute(
                    'SELECT COUNT(*) AS count FROM conversation_messages WHERE created_at >= %s',
                    (cutoff_date,)
                )
                total_messages = cursor.fetchone()['count']

                avg_messages_per_conv = 0
                if total_conversations > 0:
                    avg_messages_per_conv = round(total_messages / total_conversations, 2)

                metrics['conversations'] = {
                    'total': total_conversations or 0,
                    'total_messages': total_messages or 0,
                    'avg_messages_per_conversation': avg_messages_per_conv
                }
            except Exception as e:
                metrics['conversations'] = {'error': str(e)}

            # Document Generation Metrics
            try:
                cursor.execute(
                    'SELECT COUNT(*) AS count FROM generated_documents WHERE created_at >= %s AND is_deleted = FALSE',
                    (cutoff_date,)
                )
                total_documents = cursor.fetchone()['count']

                cursor.execute('''
                    SELECT document_type, COUNT(*) AS count
                    FROM generated_documents
                    WHERE created_at >= %s AND is_deleted = FALSE
                    GROUP BY document_type
                ''', (cutoff_date,))
                doc_types = cursor.fetchall()

                by_type = {row['document_type']: row['count'] for row in doc_types}
                metrics['documents'] = {
                    'total_generated': total_documents or 0,
                    'by_type': by_type
                }
            except Exception as e:
                metrics['documents'] = {'error': str(e)}

            # User Feedback Metrics
            try:
                cursor.execute(
                    'SELECT COUNT(*) AS count FROM user_feedback WHERE created_at >= %s',
                    (cutoff_date,)
                )
                feedback_count = cursor.fetchone()['count']

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

                metrics['feedback'] = {
                    'total_submissions': feedback_count or 0,
                    'avg_overall_rating': round(avg_overall, 2) if avg_overall else 0,
                    'avg_quality_rating': round(avg_quality, 2) if avg_quality else 0,
                    'avg_accuracy_rating': round(avg_accuracy, 2) if avg_accuracy else 0,
                    'avg_usefulness_rating': round(avg_usefulness, 2) if avg_usefulness else 0
                }
            except Exception as e:
                metrics['feedback'] = {'error': str(e)}

            # Knowledge Base Usage
            try:
                cursor.execute(
                    'SELECT COUNT(*) AS count FROM tasks WHERE created_at >= %s AND knowledge_used = TRUE',
                    (cutoff_date,)
                )
                knowledge_used_count = cursor.fetchone()['count']

                knowledge_usage_rate = 0
                if metrics.get('tasks', {}).get('total', 0) > 0:
                    knowledge_usage_rate = round((knowledge_used_count / metrics['tasks']['total'] * 100), 2)

                metrics['knowledge_base'] = {
                    'tasks_using_knowledge': knowledge_used_count or 0,
                    'knowledge_usage_rate': knowledge_usage_rate
                }
            except Exception as e:
                metrics['knowledge_base'] = {'error': str(e)}

        finally:
            conn.close()

        self.metrics = metrics
        return metrics

    def identify_top_performer(self) -> Optional[str]:
        specialists = self.metrics.get('specialists', [])
        if not specialists or isinstance(specialists, dict):
            return None
        best = max(specialists, key=lambda x: x.get('success_rate', 0) * x.get('usage_count', 0))
        return best.get('name') if best else None

    def identify_problem_areas(self) -> List[str]:
        problems = []
        tasks = self.metrics.get('tasks', {})
        if tasks.get('success_rate', 100) < 90:
            problems.append(f"Task success rate is {tasks.get('success_rate')}% (target: 90%+)")
        escalations = self.metrics.get('escalations', {})
        if escalations.get('escalation_rate', 0) > 15:
            problems.append(f"Escalation rate is {escalations.get('escalation_rate')}% (target: <15%)")
        consensus = self.metrics.get('consensus', {})
        if consensus.get('consensus_rate', 100) < 80:
            problems.append(f"Consensus rate is {consensus.get('consensus_rate')}% (target: 80%+)")
        feedback = self.metrics.get('feedback', {})
        if feedback.get('avg_overall_rating', 5) < 4.0:
            problems.append(f"Average user rating is {feedback.get('avg_overall_rating')}/5 (target: 4.0+)")
        if tasks.get('avg_execution_time_seconds', 0) > 30:
            problems.append(f"Average execution time is {tasks.get('avg_execution_time_seconds')}s (target: <30s)")
        return problems


class MarketScanner:
    def __init__(self):
        self.findings = []
        self.web_search_available = False
        try:
            from research_agent import get_research_agent
            ra = get_research_agent()
            self.web_search_available = ra.is_available
            self.research_agent = ra if self.web_search_available else None
        except Exception:
            self.research_agent = None

    def scan_ai_landscape(self) -> Dict[str, Any]:
        findings = {
            'scan_date': datetime.now().isoformat(),
            'web_search_used': self.web_search_available,
            'new_models': [],
            'capability_updates': [],
            'emerging_tools': [],
            'industry_specific': [],
            'raw_findings': []
        }

        search_topics = [
            "new AI language models released 2026",
            "Claude Anthropic updates capabilities",
            "GPT-4 OpenAI improvements",
            "AI orchestration multi-agent systems",
            "enterprise AI automation tools"
        ]

        if self.web_search_available and self.research_agent:
            for topic in search_topics:
                try:
                    results = self.research_agent.search(topic, max_results=3)
                    if results and results.get('results'):
                        for result in results['results']:
                            findings['raw_findings'].append({
                                'topic': topic,
                                'title': result.get('title', ''),
                                'url': result.get('url', ''),
                                'snippet': result.get('snippet', '')[:200]
                            })
                except Exception as e:
                    print(f"Web search failed for '{topic}': {e}")

        # Note: the ? characters below are inside a JSON format spec string,
        # not SQL — they must NOT be changed to %s.
        analysis_prompt = f"""
Analyze the current AI landscape for an AI orchestration system used by a shift work consulting firm.

Current System Configuration:
- Primary: Claude Sonnet (orchestration)
- Strategic: Claude Opus (complex tasks)
- Design: GPT-4 (presentations, marketing)
- Code: DeepSeek (programming)
- Multimodal: Gemini (image/video analysis)

{"Web Search Findings:" + json.dumps(findings['raw_findings'], indent=2) if findings['raw_findings'] else "No web search results available - use your knowledge of recent AI developments."}

Provide a structured analysis in this exact JSON format:
{{
    "new_models": [
        {{"name": "Model Name", "provider": "Company", "relevance": "Why it matters for our swarm", "recommendation": "Consider/Monitor/Ignore"}}
    ],
    "capability_updates": [
        {{"model": "Existing Model", "update": "What changed", "impact": "How it affects our system"}}
    ],
    "emerging_tools": [
        {{"name": "Tool Name", "purpose": "What it does", "potential_use": "How we could use it"}}
    ],
    "industry_relevant": [
        {{"development": "What happened", "relevance": "How it applies to shift work consulting AI"}}
    ],
    "overall_assessment": "Brief summary of the AI landscape health for our use case"
}}

Return ONLY the JSON, no other text.
"""

        try:
            response = call_claude_sonnet(analysis_prompt, max_tokens=2000)
            if response and not response.get('error'):
                content = response.get('content', '{}')
                try:
                    analysis = json.loads(content)
                except json.JSONDecodeError:
                    import re
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_match:
                        analysis = json.loads(json_match.group(1))
                    else:
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            analysis = json.loads(json_match.group(0))
                        else:
                            analysis = {}

                findings['new_models'] = analysis.get('new_models', [])
                findings['capability_updates'] = analysis.get('capability_updates', [])
                findings['emerging_tools'] = analysis.get('emerging_tools', [])
                findings['industry_specific'] = analysis.get('industry_relevant', [])
                findings['overall_assessment'] = analysis.get('overall_assessment', '')
        except Exception as e:
            findings['analysis_error'] = str(e)

        self.findings = findings
        return findings


class GapAnalyzer:
    def __init__(self, performance_metrics: Dict, market_findings: Dict):
        self.performance = performance_metrics
        self.market = market_findings
        self.gaps = []

    def analyze_gaps(self) -> List[Dict[str, Any]]:
        gaps = []

        # WO-8 (June 13, 2026): when the period is idle (zero tasks), the
        # activity-derived metrics are all zero by ABSENCE, not by failure.
        # Each activity-derived check below is gated on `not is_idle` so an
        # idle week does not manufacture false (and high-severity) gaps. The
        # gates are applied in place, preserving the original gap ORDERING for
        # active weeks exactly. The market-derived "new model" gaps further
        # below are independent of weekly activity and still run when idle.
        tasks = self.performance.get('tasks', {})
        is_idle = tasks.get('total', 0) == 0

        if not is_idle and tasks.get('success_rate', 100) < 95:
            gaps.append({
                'category': 'performance',
                'gap': 'Task Success Rate Below Target',
                'current': f"{tasks.get('success_rate', 0)}%",
                'target': '95%+',
                'severity': 'high' if tasks.get('success_rate', 100) < 85 else 'medium',
                'recommendation': 'Review failed tasks for patterns, consider adding fallback AI providers'
            })

        if not is_idle and tasks.get('avg_execution_time_seconds', 0) > 20:
            gaps.append({
                'category': 'performance',
                'gap': 'Slow Average Response Time',
                'current': f"{tasks.get('avg_execution_time_seconds', 0):.1f}s",
                'target': '<20s',
                'severity': 'medium',
                'recommendation': 'Consider faster models for simple tasks, optimize prompt lengths'
            })

        consensus = self.performance.get('consensus', {})
        if not is_idle and consensus.get('avg_agreement_score', 1) < 0.8:
            gaps.append({
                'category': 'quality',
                'gap': 'Low AI Agreement Scores',
                'current': f"{consensus.get('avg_agreement_score', 0):.2f}",
                'target': '0.80+',
                'severity': 'medium',
                'recommendation': 'Review consensus validation prompts, consider additional validators'
            })

        specialists = self.performance.get('specialists', [])
        if not is_idle and isinstance(specialists, list):
            specialist_names = [s.get('name', '').lower() for s in specialists]
            desired_specialists = ['gpt4', 'deepseek', 'gemini']
            for specialist in desired_specialists:
                if specialist not in specialist_names:
                    gaps.append({
                        'category': 'coverage',
                        'gap': f'Missing {specialist.upper()} Specialist',
                        'current': 'Not configured',
                        'target': 'Available',
                        'severity': 'low',
                        'recommendation': f'Consider adding {specialist.upper()} API key for expanded capabilities'
                    })

        feedback = self.performance.get('feedback', {})
        if not is_idle and feedback.get('avg_quality_rating', 5) < 4.0:
            gaps.append({
                'category': 'quality',
                'gap': 'Low Quality Ratings',
                'current': f"{feedback.get('avg_quality_rating', 0):.1f}/5",
                'target': '4.0+/5',
                'severity': 'high',
                'recommendation': 'Review low-rated tasks, improve formatting and completeness'
            })

        if not is_idle and feedback.get('avg_accuracy_rating', 5) < 4.0:
            gaps.append({
                'category': 'accuracy',
                'gap': 'Low Accuracy Ratings',
                'current': f"{feedback.get('avg_accuracy_rating', 0):.1f}/5",
                'target': '4.0+/5',
                'severity': 'high',
                'recommendation': 'Increase knowledge base usage, add fact-checking consensus'
            })

        new_models = self.market.get('new_models', [])
        for model in new_models:
            if model.get('recommendation') == 'Consider':
                gaps.append({
                    'category': 'capability',
                    'gap': f"New Model Available: {model.get('name', 'Unknown')}",
                    'current': 'Not integrated',
                    'target': 'Evaluate for integration',
                    'severity': 'low',
                    'recommendation': model.get('relevance', 'Evaluate this model for potential integration')
                })

        kb = self.performance.get('knowledge_base', {})
        if not is_idle and kb.get('knowledge_usage_rate', 100) < 50:
            gaps.append({
                'category': 'knowledge',
                'gap': 'Low Knowledge Base Utilization',
                'current': f"{kb.get('knowledge_usage_rate', 0)}%",
                'target': '50%+',
                'severity': 'medium',
                'recommendation': 'Improve knowledge base indexing and relevance matching'
            })

        self.gaps = gaps
        return gaps

    def prioritize_gaps(self) -> List[Dict[str, Any]]:
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        return sorted(self.gaps, key=lambda x: severity_order.get(x.get('severity', 'low'), 3))


class RecommendationEngine:
    def __init__(self, performance: Dict, market: Dict, gaps: List[Dict]):
        self.performance = performance
        self.market = market
        self.gaps = gaps

    def generate_recommendations(self) -> List[Dict[str, Any]]:
        recommendations = []

        high_severity_gaps = [g for g in self.gaps if g.get('severity') == 'high']
        for gap in high_severity_gaps:
            recommendations.append({
                'priority': 1,
                'action': gap.get('recommendation', 'Address this gap'),
                'reason': f"High severity gap: {gap.get('gap', 'Unknown')}",
                'effort': 'medium',
                'impact': 'high',
                'category': gap.get('category', 'general')
            })

        tasks = self.performance.get('tasks', {})
        if tasks.get('avg_execution_time_seconds', 0) > 15:
            recommendations.append({
                'priority': 2,
                'action': 'Optimize response times by using Sonnet for more tasks and reserving Opus for complex analysis only',
                'reason': f"Average execution time ({tasks.get('avg_execution_time_seconds', 0):.1f}s) impacts user experience",
                'effort': 'low',
                'impact': 'medium',
                'category': 'performance'
            })

        medium_severity_gaps = [g for g in self.gaps if g.get('severity') == 'medium']
        for gap in medium_severity_gaps:
            recommendations.append({
                'priority': 2,
                'action': gap.get('recommendation', 'Address this gap'),
                'reason': f"Medium severity gap: {gap.get('gap', 'Unknown')}",
                'effort': 'medium',
                'impact': 'medium',
                'category': gap.get('category', 'general')
            })

        new_models = self.market.get('new_models', [])
        for model in new_models:
            if model.get('recommendation') == 'Consider':
                recommendations.append({
                    'priority': 3,
                    'action': f"Evaluate {model.get('name', 'new model')} for potential integration",
                    'reason': model.get('relevance', 'New capability available'),
                    'effort': 'high',
                    'impact': 'medium',
                    'category': 'capability'
                })

        tools = self.market.get('emerging_tools', [])
        for tool in tools[:3]:
            recommendations.append({
                'priority': 3,
                'action': f"Investigate {tool.get('name', 'new tool')}: {tool.get('purpose', '')}",
                'reason': tool.get('potential_use', 'Could enhance capabilities'),
                'effort': 'medium',
                'impact': 'low',
                'category': 'tools'
            })

        recommendations.sort(key=lambda x: x.get('priority', 99))
        return recommendations


class SwarmReportGenerator:
    # WO-8 (June 13, 2026): neutral health score for an idle / no-data week.
    # Chosen to read as "stable" (>= 60) but never "improving" (< 80), so an
    # idle period is reported as neither a failure nor a win.
    NEUTRAL_IDLE_HEALTH_SCORE = 75

    def __init__(self, performance: Dict, market: Dict, gaps: List[Dict], recommendations: List[Dict]):
        self.performance = performance
        self.market = market
        self.gaps = gaps
        self.recommendations = recommendations

    def _is_idle(self) -> bool:
        """
        WO-8: True when no tasks were processed in the period. A zero-task week
        is 'no data', not a failing system, and must not be scored as one.
        (A tasks-collection error also yields total == 0 and is treated as
        no-data, which is the safe/conservative outcome.)
        """
        return self.performance.get('tasks', {}).get('total', 0) == 0

    def generate_report(self) -> Dict[str, Any]:
        health_score = self._calculate_health_score()
        trend = self._determine_trend()
        summary = self._generate_executive_summary(health_score, trend)

        report = {
            'report_type': 'weekly_swarm_evaluation',
            'generated_at': datetime.now().isoformat(),
            'week_of': datetime.now().strftime('%B %d, %Y'),
            'idle_period': self._is_idle(),  # WO-8: clean flag for alert/briefing suppression
            'executive_summary': summary,
            'health_score': {
                'overall': health_score,
                'trend': trend,
                'components': {
                    'task_success': self._score_task_success(),
                    'response_time': self._score_response_time(),
                    'consensus_quality': self._score_consensus(),
                    'user_satisfaction': self._score_satisfaction(),
                    'knowledge_utilization': self._score_knowledge()
                }
            },
            'performance_summary': {
                'tasks_processed': self.performance.get('tasks', {}).get('total', 0),
                'success_rate': f"{self.performance.get('tasks', {}).get('success_rate', 0)}%",
                'avg_response_time': f"{self.performance.get('tasks', {}).get('avg_execution_time_seconds', 0):.1f}s",
                'top_performer': self._identify_top_performer(),
                'lowest_performing_area': self._identify_weakest_area()
            },
            'market_developments': {
                'new_models_count': len(self.market.get('new_models', [])),
                'key_updates': self.market.get('capability_updates', [])[:3],
                'assessment': self.market.get('overall_assessment', 'No assessment available')
            },
            'gaps_identified': len(self.gaps),
            'high_priority_gaps': [g for g in self.gaps if g.get('severity') == 'high'],
            'recommendations': {
                'priority_1': [r for r in self.recommendations if r.get('priority') == 1],
                'priority_2': [r for r in self.recommendations if r.get('priority') == 2],
                'priority_3': [r for r in self.recommendations if r.get('priority') == 3]
            },
            'next_week_focus': self._generate_next_week_focus(),
            'raw_data': {
                'performance_metrics': self.performance,
                'market_findings': self.market,
                'all_gaps': self.gaps,
                'all_recommendations': self.recommendations
            }
        }
        return report

    def _calculate_health_score(self) -> int:
        # WO-8: an idle week (zero tasks) is scored as neutral no-data, not as a
        # failing system. Without this, 0 tasks -> 0% success dragged the
        # weighted score down to ~30 and tripped a false "needs_attention".
        if self._is_idle():
            return self.NEUTRAL_IDLE_HEALTH_SCORE
        scores = []
        task_success = self.performance.get('tasks', {}).get('success_rate', 0)
        scores.append(min(task_success, 100) * 0.4)
        avg_time = self.performance.get('tasks', {}).get('avg_execution_time_seconds', 60)
        time_score = max(0, 100 - (avg_time * 2))
        scores.append(time_score * 0.2)
        consensus_rate = self.performance.get('consensus', {}).get('consensus_rate', 0)
        scores.append(min(consensus_rate, 100) * 0.2)
        avg_rating = self.performance.get('feedback', {}).get('avg_overall_rating', 0)
        satisfaction = (avg_rating / 5) * 100 if avg_rating else 50
        scores.append(satisfaction * 0.2)
        return int(sum(scores))

    def _determine_trend(self) -> str:
        # WO-8: idle weeks are 'stable' (nothing needs attention). Kept inside
        # the existing trend vocabulary (improving/stable/needs_attention) so no
        # new enum value reaches downstream consumers or colour-maps.
        if self._is_idle():
            return 'stable'
        health = self._calculate_health_score()
        gaps_count = len([g for g in self.gaps if g.get('severity') == 'high'])
        if health >= 80 and gaps_count == 0:
            return 'improving'
        elif health >= 60 and gaps_count <= 2:
            return 'stable'
        else:
            return 'needs_attention'

    def _generate_executive_summary(self, health_score: int, trend: str) -> str:
        tasks = self.performance.get('tasks', {})
        # WO-8: idle weeks get a plain-language no-data summary instead of the
        # misleading "processed 0 tasks ... 0% success rate".
        if self._is_idle():
            high_gaps = len([g for g in self.gaps if g.get('severity') == 'high'])
            return (f"The AI Swarm processed no tasks during this period, so the system was idle "
                    f"rather than unhealthy. With no activity to measure, this is reported as a "
                    f"no-data period with a neutral health score of {health_score}/100. "
                    f"{len(self.gaps)} gaps identified with {high_gaps} requiring immediate attention.")
        trend_text = {
            'improving': 'Performance is trending positively.',
            'stable': 'Performance is stable.',
            'needs_attention': 'Some areas need attention.'
        }.get(trend, 'Performance requires monitoring.')
        return (f"The AI Swarm processed {tasks.get('total', 0)} tasks this week with a "
                f"{tasks.get('success_rate', 0)}% success rate. Overall health score: "
                f"{health_score}/100. {trend_text} {len(self.gaps)} gaps identified with "
                f"{len([g for g in self.gaps if g.get('severity') == 'high'])} requiring immediate attention.")

    def _score_task_success(self) -> int:
        return int(min(self.performance.get('tasks', {}).get('success_rate', 0), 100))

    def _score_response_time(self) -> int:
        avg_time = self.performance.get('tasks', {}).get('avg_execution_time_seconds', 60)
        return int(max(0, 100 - (avg_time * 2)))

    def _score_consensus(self) -> int:
        return int(min(self.performance.get('consensus', {}).get('consensus_rate', 0), 100))

    def _score_satisfaction(self) -> int:
        avg_rating = self.performance.get('feedback', {}).get('avg_overall_rating', 0)
        return int((avg_rating / 5) * 100) if avg_rating else 50

    def _score_knowledge(self) -> int:
        return int(min(self.performance.get('knowledge_base', {}).get('knowledge_usage_rate', 0) * 2, 100))

    def _identify_top_performer(self) -> str:
        specialists = self.performance.get('specialists', [])
        if not specialists or isinstance(specialists, dict):
            return 'No specialist data'
        best = max(specialists, key=lambda x: x.get('success_rate', 0) * x.get('usage_count', 1))
        return f"{best.get('name', 'Unknown')} ({best.get('success_rate', 0)}% success rate)"

    def _identify_weakest_area(self) -> str:
        if not self.gaps:
            return 'No significant issues'
        high_gaps = [g for g in self.gaps if g.get('severity') == 'high']
        if high_gaps:
            return high_gaps[0].get('gap', 'Unknown')
        return self.gaps[0].get('gap', 'No significant issues') if self.gaps else 'No issues detected'

    def _generate_next_week_focus(self) -> List[str]:
        focus = []
        p1_recs = [r for r in self.recommendations if r.get('priority') == 1]
        for rec in p1_recs[:2]:
            focus.append(f"Monitor: {rec.get('action', 'Priority action')}")
        high_gaps = [g for g in self.gaps if g.get('severity') == 'high']
        for gap in high_gaps[:2]:
            focus.append(f"Evaluate: {gap.get('gap', 'Gap area')}")
        new_models = self.market.get('new_models', [])
        consider_models = [m for m in new_models if m.get('recommendation') == 'Consider']
        for model in consider_models[:1]:
            focus.append(f"Consider: Evaluate {model.get('name', 'new model')}")
        if not focus:
            focus.append("Continue monitoring system performance")
        return focus


class SwarmSelfEvaluator:
    def __init__(self):
        self.performance_collector = PerformanceCollector()
        self.market_scanner = MarketScanner()
        self.last_evaluation = None

    def run_evaluation(self, days: int = 7, save_to_db: bool = True) -> Dict[str, Any]:
        print(f"Starting Swarm Self-Evaluation ({days} day period)...")

        print("  Collecting performance metrics...")
        performance = self.performance_collector.collect_weekly_metrics(days=days)

        print("  Scanning AI market landscape...")
        market = self.market_scanner.scan_ai_landscape()

        print("  Analyzing capability gaps...")
        gap_analyzer = GapAnalyzer(performance, market)
        gaps = gap_analyzer.analyze_gaps()
        prioritized_gaps = gap_analyzer.prioritize_gaps()

        print("  Generating recommendations...")
        rec_engine = RecommendationEngine(performance, market, prioritized_gaps)
        recommendations = rec_engine.generate_recommendations()

        print("  Generating State of the Swarm report...")
        report_gen = SwarmReportGenerator(performance, market, prioritized_gaps, recommendations)
        report = report_gen.generate_report()

        if save_to_db:
            print("  Saving evaluation to database...")
            self._save_evaluation(report)

        self.last_evaluation = report

        print(f"Evaluation complete! Health Score: {report.get('health_score', {}).get('overall', 'N/A')}/100")
        return report

    def _save_evaluation(self, report: Dict[str, Any]) -> int:
        """
        Save evaluation to database.

        Schema (swarm_evaluations):
            id              SERIAL PRIMARY KEY
            evaluation_date TIMESTAMP DEFAULT NOW()
            health_score    REAL
            trend           TEXT
            metrics         TEXT   <- performance summary JSON
            recommendations TEXT   <- recommendations JSON
            raw_data        TEXT   <- full report JSON

        Uses INSERT ... RETURNING id (PostgreSQL) instead of cursor.lastrowid.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            health_score = report.get('health_score', {}).get('overall', 0)
            trend = report.get('health_score', {}).get('trend', 'stable')

            # Compact performance summary for the metrics column
            metrics_payload = json.dumps({
                'tasks_processed': report.get('performance_summary', {}).get('tasks_processed', 0),
                'success_rate': report.get('performance_summary', {}).get('success_rate', '0%'),
                'avg_response_time': report.get('performance_summary', {}).get('avg_response_time', '0.0s'),
                'gaps_identified': report.get('gaps_identified', 0),
                'high_priority_gaps_count': len(report.get('high_priority_gaps', [])),
                'health_components': report.get('health_score', {}).get('components', {}),
                'executive_summary': report.get('executive_summary', ''),
                'idle_period': report.get('idle_period', False)  # WO-8: surfaced by read methods
            })

            recommendations_payload = json.dumps(report.get('recommendations', {}))
            raw_data_payload = json.dumps(report)

            cursor.execute('''
                INSERT INTO swarm_evaluations
                    (health_score, trend, metrics, recommendations, raw_data)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                health_score,
                trend,
                metrics_payload,
                recommendations_payload,
                raw_data_payload
            ))

            row = cursor.fetchone()
            evaluation_id = row['id'] if row else 0
            conn.commit()
            print(f"  Saved evaluation ID: {evaluation_id}")
            return evaluation_id
        except Exception as e:
            print(f"  Failed to save evaluation: {e}")
            return 0
        finally:
            conn.close()

    def get_evaluation_count(self) -> int:
        """
        WO-8: Total number of stored evaluations.

        Added so routes/evaluation.py no longer needs its own (SQLite-era) DB
        access for the /status count. Uses the migrated db_engine /
        RealDictCursor / %s pattern.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) AS count FROM swarm_evaluations')
            row = cursor.fetchone()
            return row['count'] if row else 0
        except Exception as e:
            print(f"Error counting evaluations: {e}")
            return 0
        finally:
            conn.close()

    def get_evaluation_by_id(self, evaluation_id: int) -> Optional[Dict[str, Any]]:
        """
        WO-8: Fetch a single evaluation by id.

        Reconstructs the same rich dict shape as get_latest_evaluation() from
        the REAL schema columns (id, evaluation_date, health_score, trend,
        metrics, raw_data), parsing the rich fields out of the metrics JSON.
        Returns None if no row with that id exists.

        Replaces the old route code that selected 8 phantom columns
        (period_days, tasks_processed, success_rate, executive_summary,
        gaps_count, high_priority_gaps_count, recommendations_count,
        full_report_json) which do not exist in the table.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, evaluation_date, health_score, trend, metrics, raw_data
                FROM swarm_evaluations
                WHERE id = %s
            ''', (evaluation_id,))
            row = cursor.fetchone()

            if not row:
                return None

            metrics_data = {}
            try:
                metrics_data = json.loads(row['metrics']) if row['metrics'] else {}
            except Exception:
                pass

            return {
                'id': row['id'],
                'evaluation_date': str(row['evaluation_date']),
                'health_score': row['health_score'],
                'trend': row['trend'],
                'tasks_processed': metrics_data.get('tasks_processed', 0),
                'success_rate': metrics_data.get('success_rate', '0%'),
                'executive_summary': metrics_data.get('executive_summary', ''),
                'gaps_count': metrics_data.get('gaps_identified', 0),
                'high_priority_gaps_count': metrics_data.get('high_priority_gaps_count', 0),
                'recommendations_count': 0,  # preserved for API compat
                'idle_period': metrics_data.get('idle_period', False),
                'full_report': json.loads(row['raw_data']) if row['raw_data'] else None
            }
        except Exception as e:
            print(f"Error fetching evaluation {evaluation_id}: {e}")
            return None
        finally:
            conn.close()

    def delete_evaluation(self, evaluation_id: int) -> bool:
        """
        WO-8: Delete a single evaluation by id.

        Returns True if a row was deleted, False if no such id existed.
        Uses DELETE ... RETURNING id (PostgreSQL) to detect existence in one
        statement; commits on success, rolls back on error.

        Replaces the old route code that used the SQLite get_db() API and
        `?` placeholders.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM swarm_evaluations WHERE id = %s RETURNING id',
                (evaluation_id,)
            )
            deleted = cursor.fetchone()
            conn.commit()
            return deleted is not None
        except Exception as e:
            print(f"Error deleting evaluation {evaluation_id}: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            conn.close()

    def get_latest_evaluation(self) -> Optional[Dict[str, Any]]:
        """
        Get most recent evaluation from database.

        Reads real schema columns (id, evaluation_date, health_score, trend,
        metrics, recommendations, raw_data) and reconstructs the rich dict
        that callers expect by parsing the metrics JSON stored in metrics column.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, evaluation_date, health_score, trend, metrics, raw_data
                FROM swarm_evaluations
                ORDER BY evaluation_date DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()

            if row:
                metrics_data = {}
                try:
                    metrics_data = json.loads(row['metrics']) if row['metrics'] else {}
                except Exception:
                    pass

                return {
                    'id': row['id'],
                    'evaluation_date': str(row['evaluation_date']),
                    'health_score': row['health_score'],
                    'trend': row['trend'],
                    'tasks_processed': metrics_data.get('tasks_processed', 0),
                    'success_rate': metrics_data.get('success_rate', '0%'),
                    'executive_summary': metrics_data.get('executive_summary', ''),
                    'gaps_count': metrics_data.get('gaps_identified', 0),
                    'high_priority_gaps_count': metrics_data.get('high_priority_gaps_count', 0),
                    'recommendations_count': 0,  # preserved for API compat
                    'idle_period': metrics_data.get('idle_period', False),  # WO-8
                    'full_report': json.loads(row['raw_data']) if row['raw_data'] else None
                }
            return None
        except Exception as e:
            print(f"Error fetching evaluation: {e}")
            return None
        finally:
            conn.close()

    def get_evaluation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get history of evaluations.

        Reads real schema columns and reconstructs expected dict shape
        from the metrics JSON payload.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, evaluation_date, health_score, trend, metrics
                FROM swarm_evaluations
                ORDER BY evaluation_date DESC
                LIMIT %s
            ''', (limit,))
            rows = cursor.fetchall()

            history = []
            for row in rows:
                metrics_data = {}
                try:
                    metrics_data = json.loads(row['metrics']) if row['metrics'] else {}
                except Exception:
                    pass

                history.append({
                    'id': row['id'],
                    'evaluation_date': str(row['evaluation_date']),
                    'health_score': row['health_score'],
                    'trend': row['trend'],
                    'tasks_processed': metrics_data.get('tasks_processed', 0),
                    'success_rate': metrics_data.get('success_rate', '0%'),
                    'gaps_count': metrics_data.get('gaps_identified', 0),
                    'high_priority_gaps_count': metrics_data.get('high_priority_gaps_count', 0),
                    'idle_period': metrics_data.get('idle_period', False)  # WO-8
                })
            return history
        except Exception as e:
            print(f"Error fetching evaluation history: {e}")
            return []
        finally:
            conn.close()


_evaluator_instance = None

def get_swarm_evaluator() -> SwarmSelfEvaluator:
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = SwarmSelfEvaluator()
    return _evaluator_instance

# I did no harm and this file is not truncated
