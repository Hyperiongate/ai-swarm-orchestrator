"""
intelligence/weekly_review.py
Weekly Review Engine for AI Swarm Orchestrator
Created: March 09, 2026
Last Updated: March 10, 2026 — Fixed NULL-status legacy tasks polluting success rate

CHANGELOG:
- March 10, 2026: FIX — NULL-status legacy tasks excluded from total task count
  ROOT CAUSE: The total tasks COUNT(*) query counted all 72 tasks including
  65 legacy NULL-status rows inserted before the RETURNING id fix was deployed.
  Those tasks had task_id=0, so their UPDATE SET status='completed' matched
  nothing and their status was never written. The denominator was 72 while
  only 7 tasks had real status data, giving a false 9.72% success rate.
  FIX: Added AND status IS NOT NULL to the total tasks COUNT query only.
  All other queries (completed, failed, avg_time, escalations, orchestrator
  distribution, knowledge_used) already filter by specific column values
  that implicitly exclude NULL-status rows — those are untouched.
  Expected result: health score jumps from ~33 to ~69 (accurate for dev phase,
  limited by zero consensus data and zero user feedback submissions).

- March 09, 2026: Created. Replaces swarm_self_evaluation.py.
  Carries forward: performance metrics collection, gap analysis,
    recommendation engine, health score formula, report structure.
  Changed: PostgreSQL throughout (%s, TRUE/FALSE, AS cnt, RETURNING id,
    information_schema table checks).
  Added Phase 5: generate_enhancements_from_patterns(), routing memory,
    memory relevance pruning, store review as semantic memory,
    weekly_reviews table, run_weekly_review() / get_latest_review() API.

- March 09, 2026: BUG FIX 1 — enhancements_generated stored wrong type
  generate_enhancements_from_patterns() returns a list of dicts, not an int.
  Fixed _take_phase5_actions() to store len(stored) instead of the list itself.

- March 09, 2026: BUG FIX 2 — AI analysis used call_claude_sonnet() which
  injects capabilities + FORMATTING_REQUIREMENTS, corrupting JSON parse.
  Switched _run_ai_analysis() to call_claude_sonnet_raw() with a lean
  system prompt, identical pattern to memory/memory_extractor.py.
  This ensures the weekly review AI call returns clean parseable JSON.

Author: Jim @ Shiftwork Solutions LLC
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from database import get_db
from orchestration.ai_clients import call_claude_sonnet_raw


# ============================================================================
# TABLE SETUP
# ============================================================================

_TABLE_CHECKED = False


def _ensure_table():
    """
    Create weekly_reviews table if it doesn't exist.
    Called once per process via module-level flag.
    Uses information_schema (PostgreSQL) instead of sqlite_master.
    """
    global _TABLE_CHECKED
    if _TABLE_CHECKED:
        return
    try:
        db = get_db()
        try:
            exists = db.execute(
                """SELECT table_name FROM information_schema.tables
                   WHERE table_schema = 'public' AND table_name = 'weekly_reviews'"""
            ).fetchone()
            if not exists:
                db.execute("""
                    CREATE TABLE IF NOT EXISTS weekly_reviews (
                        id                       SERIAL PRIMARY KEY,
                        run_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        period_days              INTEGER,
                        health_score             INTEGER,
                        trend                    VARCHAR(50),
                        tasks_processed          INTEGER,
                        success_rate             FLOAT,
                        gaps_count               INTEGER,
                        high_priority_gaps_count INTEGER,
                        actions_taken            JSONB,
                        full_report              JSONB
                    )
                """)
                db.commit()
                print("weekly_review: created weekly_reviews table")
        finally:
            db.close()
        _TABLE_CHECKED = True
    except Exception as e:
        print(f"weekly_review: _ensure_table failed (non-critical): {e}")


# ============================================================================
# METRICS COLLECTOR
# ============================================================================

def _collect_metrics(days: int = 7) -> Dict[str, Any]:
    """
    Collect performance metrics for the past N days from PostgreSQL.
    All queries use %s placeholders and named column aliases for RealDictCursor.
    Each metric section is wrapped in its own try/except so one missing table
    does not abort the entire collection.

    NOTE on NULL-status exclusion (March 10, 2026):
    The total task count uses AND status IS NOT NULL to exclude legacy rows
    inserted before the RETURNING id fix. Those rows were never properly
    updated (task_id=0 meant the UPDATE matched nothing), so their status
    stayed NULL. They are not failures — they are ghosts from the pre-fix era.
    Counting them as failures produced a false ~10% success rate.
    """
    cutoff = datetime.now() - timedelta(days=days)
    cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')

    metrics = {
        'period_start': cutoff_str,
        'period_end': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'days_analyzed': days,
    }

    db = get_db()
    try:
        # ---- TASK METRICS ----
        try:
            # FIX March 10, 2026: AND status IS NOT NULL excludes legacy NULL-status
            # rows inserted before the RETURNING id fix was deployed. Those tasks
            # were never properly completed or failed — their status was simply
            # never written. Excluding them gives an accurate denominator.
            total = db.execute(
                'SELECT COUNT(*) AS cnt FROM tasks '
                'WHERE created_at >= %s AND status IS NOT NULL',
                (cutoff_str,)
            ).fetchone()
            total_tasks = total['cnt'] if total else 0

            completed = db.execute(
                "SELECT COUNT(*) AS cnt FROM tasks WHERE created_at >= %s AND status = 'completed'",
                (cutoff_str,)
            ).fetchone()
            completed_tasks = completed['cnt'] if completed else 0

            failed = db.execute(
                "SELECT COUNT(*) AS cnt FROM tasks WHERE created_at >= %s AND status = 'failed'",
                (cutoff_str,)
            ).fetchone()
            failed_tasks = failed['cnt'] if failed else 0

            avg_time_row = db.execute(
                'SELECT AVG(duration_seconds) AS avg_time FROM tasks '
                'WHERE created_at >= %s AND duration_seconds IS NOT NULL',
                (cutoff_str,)
            ).fetchone()
            avg_exec_time = avg_time_row['avg_time'] if avg_time_row and avg_time_row['avg_time'] else 0

            metrics['tasks'] = {
                'total': total_tasks,
                'completed': completed_tasks,
                'failed': failed_tasks,
                'success_rate': round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0,
                'avg_execution_time_seconds': round(float(avg_exec_time), 2),
            }
        except Exception as e:
            print(f"weekly_review: task metrics error: {e}")
            db.rollback()
            metrics['tasks'] = {'total': 0, 'completed': 0, 'failed': 0,
                                 'success_rate': 0, 'avg_execution_time_seconds': 0}

        # ---- CONSENSUS METRICS ----
        try:
            total_con = db.execute(
                'SELECT COUNT(*) AS cnt FROM consensus_validations WHERE created_at >= %s',
                (cutoff_str,)
            ).fetchone()
            total_consensus = total_con['cnt'] if total_con else 0

            achieved_con = db.execute(
                'SELECT COUNT(*) AS cnt FROM consensus_validations '
                'WHERE created_at >= %s AND consensus_achieved = TRUE',
                (cutoff_str,)
            ).fetchone()
            achieved_consensus = achieved_con['cnt'] if achieved_con else 0

            avg_agree = db.execute(
                'SELECT AVG(agreement_score) AS avg_score FROM consensus_validations '
                'WHERE created_at >= %s AND agreement_score IS NOT NULL',
                (cutoff_str,)
            ).fetchone()
            avg_agreement = float(avg_agree['avg_score']) if avg_agree and avg_agree['avg_score'] else 0.0

            metrics['consensus'] = {
                'total_validations': total_consensus,
                'consensus_achieved': achieved_consensus,
                'consensus_rate': round((achieved_consensus / total_consensus * 100), 2) if total_consensus > 0 else 0,
                'avg_agreement_score': round(avg_agreement, 3),
            }
        except Exception as e:
            print(f"weekly_review: consensus metrics error: {e}")
            db.rollback()
            metrics['consensus'] = {'total_validations': 0, 'consensus_achieved': 0,
                                     'consensus_rate': 0, 'avg_agreement_score': 0.0}

        # ---- SPECIALIST METRICS ----
        try:
            spec_rows = db.execute("""
                SELECT specialist_name,
                       COUNT(*) AS usage_count,
                       AVG(execution_time_seconds) AS avg_time
                FROM specialist_calls
                WHERE created_at >= %s
                GROUP BY specialist_name
                ORDER BY usage_count DESC
            """, (cutoff_str,)).fetchall()

            specialists = []
            for row in spec_rows:
                usage = row['usage_count'] or 0
                specialists.append({
                    'name': row['specialist_name'],
                    'usage_count': usage,
                    'avg_execution_time': round(float(row['avg_time']), 2) if row['avg_time'] else 0,
                })
            metrics['specialists'] = specialists
        except Exception as e:
            print(f"weekly_review: specialist metrics error: {e}")
            db.rollback()
            metrics['specialists'] = []

        # ---- ESCALATION METRICS ----
        try:
            esc_total = db.execute(
                "SELECT COUNT(*) AS cnt FROM tasks WHERE created_at >= %s "
                "AND assigned_orchestrator = 'opus'",
                (cutoff_str,)
            ).fetchone()
            total_escalations = esc_total['cnt'] if esc_total else 0
            total_tasks_val = metrics['tasks'].get('total', 0)
            escalation_rate = round((total_escalations / total_tasks_val * 100), 2) if total_tasks_val > 0 else 0
            metrics['escalations'] = {
                'total': total_escalations,
                'escalation_rate': escalation_rate,
            }
        except Exception as e:
            print(f"weekly_review: escalation metrics error: {e}")
            db.rollback()
            metrics['escalations'] = {'total': 0, 'escalation_rate': 0}

        # ---- ORCHESTRATOR DISTRIBUTION ----
        try:
            orch_rows = db.execute("""
                SELECT assigned_orchestrator AS orch,
                       COUNT(*) AS cnt
                FROM tasks
                WHERE created_at >= %s AND assigned_orchestrator IS NOT NULL
                GROUP BY assigned_orchestrator
            """, (cutoff_str,)).fetchall()
            metrics['orchestrator_distribution'] = {
                row['orch']: row['cnt'] for row in orch_rows
            }
        except Exception as e:
            print(f"weekly_review: orchestrator distribution error: {e}")
            db.rollback()
            metrics['orchestrator_distribution'] = {}

        # ---- CONVERSATION METRICS ----
        try:
            conv_total = db.execute(
                'SELECT COUNT(*) AS cnt FROM conversations WHERE created_at >= %s',
                (cutoff_str,)
            ).fetchone()
            total_conversations = conv_total['cnt'] if conv_total else 0

            msg_total = db.execute(
                'SELECT COUNT(*) AS cnt FROM conversation_messages WHERE created_at >= %s',
                (cutoff_str,)
            ).fetchone()
            total_messages = msg_total['cnt'] if msg_total else 0

            avg_msg = round(total_messages / total_conversations, 2) if total_conversations > 0 else 0
            metrics['conversations'] = {
                'total': total_conversations,
                'total_messages': total_messages,
                'avg_messages_per_conversation': avg_msg,
            }
        except Exception as e:
            print(f"weekly_review: conversation metrics error: {e}")
            db.rollback()
            metrics['conversations'] = {'total': 0, 'total_messages': 0,
                                         'avg_messages_per_conversation': 0}

        # ---- DOCUMENT METRICS ----
        try:
            doc_total = db.execute(
                'SELECT COUNT(*) AS cnt FROM generated_documents '
                'WHERE created_at >= %s AND is_deleted = FALSE',
                (cutoff_str,)
            ).fetchone()
            total_docs = doc_total['cnt'] if doc_total else 0

            doc_types = db.execute("""
                SELECT document_type AS dtype, COUNT(*) AS cnt
                FROM generated_documents
                WHERE created_at >= %s AND is_deleted = FALSE
                GROUP BY document_type
            """, (cutoff_str,)).fetchall()

            metrics['documents'] = {
                'total_generated': total_docs,
                'by_type': {row['dtype']: row['cnt'] for row in doc_types},
            }
        except Exception as e:
            print(f"weekly_review: document metrics error: {e}")
            db.rollback()
            metrics['documents'] = {'total_generated': 0, 'by_type': {}}

        # ---- USER FEEDBACK METRICS ----
        try:
            fb_row = db.execute(
                'SELECT COUNT(*) AS cnt, AVG(overall_rating) AS avg_overall, '
                'AVG(quality_rating) AS avg_quality, AVG(accuracy_rating) AS avg_accuracy, '
                'AVG(usefulness_rating) AS avg_usefulness '
                'FROM user_feedback WHERE submitted_at >= %s',
                (cutoff_str,)
            ).fetchone()

            if fb_row:
                metrics['feedback'] = {
                    'total_submissions': fb_row['cnt'] or 0,
                    'avg_overall_rating':    round(float(fb_row['avg_overall']),    2) if fb_row['avg_overall']    else 0,
                    'avg_quality_rating':    round(float(fb_row['avg_quality']),    2) if fb_row['avg_quality']    else 0,
                    'avg_accuracy_rating':   round(float(fb_row['avg_accuracy']),   2) if fb_row['avg_accuracy']   else 0,
                    'avg_usefulness_rating': round(float(fb_row['avg_usefulness']), 2) if fb_row['avg_usefulness'] else 0,
                }
            else:
                metrics['feedback'] = {
                    'total_submissions': 0, 'avg_overall_rating': 0,
                    'avg_quality_rating': 0, 'avg_accuracy_rating': 0,
                    'avg_usefulness_rating': 0,
                }
        except Exception as e:
            print(f"weekly_review: feedback metrics error: {e}")
            db.rollback()
            metrics['feedback'] = {
                'total_submissions': 0, 'avg_overall_rating': 0,
                'avg_quality_rating': 0, 'avg_accuracy_rating': 0,
                'avg_usefulness_rating': 0,
            }

        # ---- KNOWLEDGE BASE USAGE ----
        try:
            kb_row = db.execute(
                'SELECT COUNT(*) AS cnt FROM tasks WHERE created_at >= %s AND knowledge_used = TRUE',
                (cutoff_str,)
            ).fetchone()
            kb_count = kb_row['cnt'] if kb_row else 0
            total_tasks_val = metrics['tasks'].get('total', 0)
            kb_rate = round((kb_count / total_tasks_val * 100), 2) if total_tasks_val > 0 else 0
            metrics['knowledge_base'] = {
                'tasks_using_knowledge': kb_count,
                'knowledge_usage_rate': kb_rate,
            }
        except Exception as e:
            print(f"weekly_review: knowledge_base metrics error: {e}")
            db.rollback()
            metrics['knowledge_base'] = {'tasks_using_knowledge': 0, 'knowledge_usage_rate': 0}

        # ---- ROUTING PREFERENCES (Phase 5 data) ----
        try:
            rp_exists = db.execute(
                """SELECT table_name FROM information_schema.tables
                   WHERE table_schema = 'public' AND table_name = 'routing_preferences'"""
            ).fetchone()
            if rp_exists:
                rp_rows = db.execute("""
                    SELECT task_category, preferred_model, avg_score,
                           success_count, total_count
                    FROM routing_preferences
                    WHERE total_count >= 3
                    ORDER BY task_category, avg_score DESC
                """).fetchall()
                routing_data = []
                for row in rp_rows:
                    routing_data.append({
                        'category': row['task_category'],
                        'model': row['preferred_model'],
                        'avg_score': float(row['avg_score']) if row['avg_score'] else 0,
                        'total_count': row['total_count'],
                        'success_count': row['success_count'],
                    })
                metrics['routing_preferences'] = routing_data
            else:
                metrics['routing_preferences'] = []
        except Exception as e:
            print(f"weekly_review: routing_preferences error: {e}")
            db.rollback()
            metrics['routing_preferences'] = []

    finally:
        db.close()

    return metrics


# ============================================================================
# GAP ANALYSIS
# ============================================================================

def _analyze_gaps(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Identify performance and capability gaps.
    Pure logic — no database calls.
    Carried forward from GapAnalyzer.analyze_gaps() in swarm_self_evaluation.py.
    """
    gaps = []

    tasks = metrics.get('tasks', {})
    if tasks.get('success_rate', 100) < 95:
        gaps.append({
            'category': 'performance',
            'gap': 'Task Success Rate Below Target',
            'current': f"{tasks.get('success_rate', 0)}%",
            'target': '95%+',
            'severity': 'high' if tasks.get('success_rate', 100) < 85 else 'medium',
            'recommendation': 'Review failed tasks for patterns; consider adding fallback AI providers',
        })

    if tasks.get('avg_execution_time_seconds', 0) > 20:
        gaps.append({
            'category': 'performance',
            'gap': 'Slow Average Response Time',
            'current': f"{tasks.get('avg_execution_time_seconds', 0):.1f}s",
            'target': '<20s',
            'severity': 'medium',
            'recommendation': 'Consider faster models for simple tasks; optimize prompt lengths',
        })

    consensus = metrics.get('consensus', {})
    if consensus.get('avg_agreement_score', 1) < 0.8:
        gaps.append({
            'category': 'quality',
            'gap': 'Low AI Agreement Scores',
            'current': f"{consensus.get('avg_agreement_score', 0):.2f}",
            'target': '0.80+',
            'severity': 'medium',
            'recommendation': 'Review consensus validation prompts; consider additional validators',
        })

    feedback = metrics.get('feedback', {})
    if feedback.get('avg_quality_rating', 5) < 4.0 and feedback.get('total_submissions', 0) > 0:
        gaps.append({
            'category': 'quality',
            'gap': 'Low Quality Ratings',
            'current': f"{feedback.get('avg_quality_rating', 0):.1f}/5",
            'target': '4.0+/5',
            'severity': 'high',
            'recommendation': 'Review low-rated tasks; improve formatting and completeness',
        })

    if feedback.get('avg_accuracy_rating', 5) < 4.0 and feedback.get('total_submissions', 0) > 0:
        gaps.append({
            'category': 'accuracy',
            'gap': 'Low Accuracy Ratings',
            'current': f"{feedback.get('avg_accuracy_rating', 0):.1f}/5",
            'target': '4.0+/5',
            'severity': 'high',
            'recommendation': 'Increase knowledge base usage; add fact-checking consensus',
        })

    kb = metrics.get('knowledge_base', {})
    if kb.get('knowledge_usage_rate', 100) < 50 and metrics.get('tasks', {}).get('total', 0) >= 10:
        gaps.append({
            'category': 'knowledge',
            'gap': 'Low Knowledge Base Utilization',
            'current': f"{kb.get('knowledge_usage_rate', 0)}%",
            'target': '50%+',
            'severity': 'medium',
            'recommendation': 'Improve knowledge base indexing and relevance matching',
        })

    severity_order = {'high': 0, 'medium': 1, 'low': 2}
    gaps.sort(key=lambda x: severity_order.get(x.get('severity', 'low'), 3))
    return gaps


# ============================================================================
# HEALTH SCORE
# ============================================================================

def _calculate_health_score(metrics: Dict[str, Any]) -> int:
    """
    Calculate overall swarm health score (0-100).
    Weights: task success 40%, response time 20%, consensus 20%, satisfaction 20%.
    Carried forward from original formula in swarm_self_evaluation.py.
    """
    scores = []

    task_success = metrics.get('tasks', {}).get('success_rate', 0)
    scores.append(min(task_success, 100) * 0.4)

    avg_time = metrics.get('tasks', {}).get('avg_execution_time_seconds', 60)
    time_score = max(0, 100 - (avg_time * 2))
    scores.append(time_score * 0.2)

    consensus_rate = metrics.get('consensus', {}).get('consensus_rate', 0)
    scores.append(min(consensus_rate, 100) * 0.2)

    avg_rating = metrics.get('feedback', {}).get('avg_overall_rating', 0)
    satisfaction = (avg_rating / 5) * 100 if avg_rating else 50
    scores.append(satisfaction * 0.2)

    return int(sum(scores))


def _determine_trend(health_score: int, gaps: List[Dict]) -> str:
    """Determine trend label from health score and gap count."""
    high_gaps = sum(1 for g in gaps if g.get('severity') == 'high')
    if health_score >= 80 and high_gaps == 0:
        return 'improving'
    elif health_score >= 60 and high_gaps <= 2:
        return 'stable'
    else:
        return 'needs_attention'


# ============================================================================
# AI ANALYSIS
# ============================================================================

def _run_ai_analysis(metrics: Dict[str, Any], gaps: List[Dict],
                     health_score: int) -> Dict[str, Any]:
    """
    Make a single Sonnet call to analyze metrics and produce recommendations.

    Uses call_claude_sonnet_raw() (not call_claude_sonnet()) so the response
    is clean JSON without capabilities/formatting injection corrupting the parse.
    This is the same pattern used by memory/memory_extractor.py.

    Returns a dict with keys:
        executive_summary, recommendations, prompt_enhancement_suggestions,
        routing_patterns, next_week_focus, raw_analysis
    """
    tasks = metrics.get('tasks', {})
    consensus = metrics.get('consensus', {})
    escalations = metrics.get('escalations', {})
    feedback = metrics.get('feedback', {})
    routing = metrics.get('routing_preferences', [])
    orchestrators = metrics.get('orchestrator_distribution', {})

    system_prompt = (
        "You are a performance analyst for the AI Swarm Orchestrator at "
        "Shiftwork Solutions LLC, a 24/7 shift operations consulting firm. "
        "You analyze system metrics and return structured JSON recommendations. "
        "Return ONLY valid JSON — no markdown, no preamble, no trailing text."
    )

    user_prompt = f"""Analyze the weekly performance of the AI Swarm Orchestrator.

=== PERFORMANCE METRICS (last {metrics.get('days_analyzed', 7)} days) ===

TASKS:
- Total: {tasks.get('total', 0)}
- Success Rate: {tasks.get('success_rate', 0)}%
- Failed: {tasks.get('failed', 0)}
- Avg Response Time: {tasks.get('avg_execution_time_seconds', 0):.1f}s

ORCHESTRATOR DISTRIBUTION:
{json.dumps(orchestrators, indent=2)}

ESCALATIONS TO OPUS:
- Total: {escalations.get('total', 0)} ({escalations.get('escalation_rate', 0):.1f}% of tasks)

CONSENSUS VALIDATION:
- Consensus Rate: {consensus.get('consensus_rate', 0)}%
- Avg Agreement Score: {consensus.get('avg_agreement_score', 0):.3f}

USER FEEDBACK:
- Submissions: {feedback.get('total_submissions', 0)}
- Overall: {feedback.get('avg_overall_rating', 0):.2f}/5
- Quality: {feedback.get('avg_quality_rating', 0):.2f}/5
- Accuracy: {feedback.get('avg_accuracy_rating', 0):.2f}/5

HEALTH SCORE: {health_score}/100

ROUTING PREFERENCES ACCUMULATED:
{json.dumps(routing, indent=2) if routing else 'Not enough data yet (need 3+ tasks per category)'}

GAPS IDENTIFIED:
{json.dumps(gaps, indent=2) if gaps else 'No significant gaps detected'}

=== REQUIRED RESPONSE FORMAT ===

Return this exact JSON structure with no other text:

{{
  "executive_summary": "2-3 sentence summary of the week",
  "recommendations": [
    {{
      "priority": 1,
      "action": "Specific actionable recommendation",
      "reason": "Why this matters",
      "category": "performance|quality|routing|capability|knowledge"
    }}
  ],
  "prompt_enhancement_suggestions": [
    {{
      "task_category": "scheduling|survey|code|research|client_consulting|content|analysis|labor|document|general",
      "enhancement_text": "Specific instruction to add to prompts for this category",
      "reason": "Why this enhancement would help"
    }}
  ],
  "routing_patterns": "Plain text 2-4 sentence summary of routing patterns: which models perform best for which task types, escalation patterns, what the reasoning engine should know",
  "next_week_focus": ["Focus area 1", "Focus area 2", "Focus area 3"]
}}

Rules:
- Only suggest prompt_enhancement_suggestions if real patterns in the data support them
- Keep enhancement_text under 150 words
- Limit recommendations to 5 maximum, ordered by impact
- Return ONLY the JSON object, nothing else"""

    try:
        response = call_claude_sonnet_raw(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=2000,
        )

        if not response or response.get('error'):
            print(f"weekly_review: AI analysis call failed: {response}")
            return _fallback_analysis(metrics, gaps, health_score)

        content = response.get('content', '{}')

        # Strip code fences if present
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        # Find first complete JSON object
        start = content.find('{')
        if start >= 0:
            depth, in_string, escape_next = 0, False, False
            for i, ch in enumerate(content[start:], start):
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\' and in_string:
                    escape_next = True
                    continue
                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        content = content[start:i + 1]
                        break

        analysis = json.loads(content)
        analysis['raw_analysis'] = response.get('content', '')
        return analysis

    except (json.JSONDecodeError, Exception) as e:
        print(f"weekly_review: AI analysis parse error: {e}")
        return _fallback_analysis(metrics, gaps, health_score)


def _fallback_analysis(metrics: Dict, gaps: List[Dict], health_score: int) -> Dict[str, Any]:
    """Minimal fallback if Sonnet call fails or JSON parse fails."""
    tasks = metrics.get('tasks', {})
    return {
        'executive_summary': (
            f"The AI Swarm processed {tasks.get('total', 0)} tasks this week with a "
            f"{tasks.get('success_rate', 0)}% success rate. "
            f"Health score: {health_score}/100. "
            f"{len(gaps)} gaps identified."
        ),
        'recommendations': [
            {
                'priority': 1,
                'action': g.get('recommendation', 'Address gap'),
                'reason': g.get('gap', 'Performance gap'),
                'category': g.get('category', 'general'),
            }
            for g in gaps[:3] if g.get('severity') == 'high'
        ],
        'prompt_enhancement_suggestions': [],
        'routing_patterns': 'Insufficient data for routing pattern analysis.',
        'next_week_focus': ['Monitor system performance', 'Review failed tasks'],
        'raw_analysis': '',
    }


# ============================================================================
# PHASE 5 ACTIONS
# ============================================================================

def _take_phase5_actions(analysis: Dict[str, Any], metrics: Dict[str, Any],
                          health_score: int) -> Dict[str, Any]:
    """
    After generating the report, take 4 concrete Phase 5 learning actions:

    1. generate_enhancements_from_patterns() — weekly trigger for prompt_optimizer.
    2. Store routing_patterns as a semantic memory for the reasoning engine.
    3. Deactivate memories older than 60 days with low relevance (< 0.3).
    4. Store the review executive_summary as a semantic memory.

    Returns dict describing what was done (stored in weekly_reviews.actions_taken).
    All actions are individually wrapped in try/except — any failure is logged
    and skipped without aborting the review.
    """
    actions = {
        'enhancements_generated': 0,
        'memory_stored': False,
        'routing_memory_stored': False,
        'old_memories_deactivated': 0,
        'errors': [],
    }

    # ------------------------------------------------------------------
    # ACTION 1: Generate prompt enhancements from patterns
    # generate_enhancements_from_patterns() returns a LIST of stored dicts.
    # Store the count (len), not the list itself.
    # ------------------------------------------------------------------
    try:
        from intelligence.prompt_optimizer import generate_enhancements_from_patterns
        stored = generate_enhancements_from_patterns()
        actions['enhancements_generated'] = len(stored) if isinstance(stored, list) else 0
        print(f"weekly_review: Phase 5 Action 1 — generated "
              f"{actions['enhancements_generated']} prompt enhancements")
    except Exception as e:
        msg = f"generate_enhancements_from_patterns failed: {e}"
        print(f"weekly_review: {msg}")
        actions['errors'].append(msg)

    # ------------------------------------------------------------------
    # ACTION 2: Store routing patterns as semantic memory
    # ------------------------------------------------------------------
    routing_patterns = analysis.get('routing_patterns', '').strip()
    if routing_patterns and len(routing_patterns) > 20:
        try:
            db = get_db()
            try:
                mem_exists = db.execute(
                    """SELECT table_name FROM information_schema.tables
                       WHERE table_schema = 'public' AND table_name = 'memories'"""
                ).fetchone()
                if mem_exists:
                    db.execute("""
                        INSERT INTO memories
                            (memory_type, category, content, relevance_score,
                             source_task_id, created_at)
                        VALUES
                            ('semantic', 'routing_intelligence', %s, 0.8,
                             NULL, CURRENT_TIMESTAMP)
                    """, (routing_patterns,))
                    db.commit()
                    actions['routing_memory_stored'] = True
                    print("weekly_review: Phase 5 Action 2 — routing patterns stored as memory")
                else:
                    print("weekly_review: memories table not found — skipping routing memory")
            finally:
                db.close()
        except Exception as e:
            msg = f"routing memory storage failed: {e}"
            print(f"weekly_review: {msg}")
            actions['errors'].append(msg)

    # ------------------------------------------------------------------
    # ACTION 3: Deactivate old low-relevance memories
    # ------------------------------------------------------------------
    try:
        cutoff_60 = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')
        db = get_db()
        try:
            mem_exists = db.execute(
                """SELECT table_name FROM information_schema.tables
                   WHERE table_schema = 'public' AND table_name = 'memories'"""
            ).fetchone()
            if mem_exists:
                col_exists = db.execute(
                    """SELECT column_name FROM information_schema.columns
                       WHERE table_schema = 'public'
                         AND table_name = 'memories'
                         AND column_name = 'is_active'"""
                ).fetchone()
                if col_exists:
                    cursor = db.execute("""
                        UPDATE memories
                        SET is_active = FALSE
                        WHERE created_at < %s
                          AND relevance_score < 0.3
                          AND is_active = TRUE
                          AND memory_type NOT IN ('procedural', 'semantic')
                    """, (cutoff_60,))
                    db.commit()
                    deactivated = getattr(cursor, 'rowcount', 0) or 0
                    actions['old_memories_deactivated'] = deactivated
                    print(f"weekly_review: Phase 5 Action 3 — deactivated {deactivated} old memories")
                else:
                    print("weekly_review: memories.is_active column not found — skipping pruning")
        finally:
            db.close()
    except Exception as e:
        msg = f"memory pruning failed: {e}"
        print(f"weekly_review: {msg}")
        actions['errors'].append(msg)

    # ------------------------------------------------------------------
    # ACTION 4: Store executive summary as semantic memory
    # ------------------------------------------------------------------
    summary_text = analysis.get('executive_summary', '').strip()
    if summary_text and len(summary_text) > 20:
        try:
            week_label = datetime.now().strftime('%Y-W%W')
            memory_content = (
                f"[Weekly Review {week_label}] "
                f"Health Score: {health_score}/100. "
                f"{summary_text}"
            )
            db = get_db()
            try:
                mem_exists = db.execute(
                    """SELECT table_name FROM information_schema.tables
                       WHERE table_schema = 'public' AND table_name = 'memories'"""
                ).fetchone()
                if mem_exists:
                    db.execute("""
                        INSERT INTO memories
                            (memory_type, category, content, relevance_score,
                             source_task_id, created_at)
                        VALUES
                            ('semantic', 'system_review', %s, 0.7,
                             NULL, CURRENT_TIMESTAMP)
                    """, (memory_content,))
                    db.commit()
                    actions['memory_stored'] = True
                    print("weekly_review: Phase 5 Action 4 — review summary stored as memory")
                else:
                    print("weekly_review: memories table not found — skipping summary memory")
            finally:
                db.close()
        except Exception as e:
            msg = f"review memory storage failed: {e}"
            print(f"weekly_review: {msg}")
            actions['errors'].append(msg)

    return actions


# ============================================================================
# SAVE TO DB
# ============================================================================

def _save_review(period_days: int, health_score: int, trend: str,
                 metrics: Dict, gaps: List[Dict], analysis: Dict,
                 actions: Dict) -> Optional[int]:
    """
    Save the completed review to weekly_reviews table.
    Returns the new row id, or None on failure.
    """
    tasks = metrics.get('tasks', {})
    try:
        full_report = {
            'metrics': metrics,
            'gaps': gaps,
            'analysis': {k: v for k, v in analysis.items() if k != 'raw_analysis'},
        }
        db = get_db()
        try:
            row = db.execute("""
                INSERT INTO weekly_reviews
                    (period_days, health_score, trend, tasks_processed,
                     success_rate, gaps_count, high_priority_gaps_count,
                     actions_taken, full_report)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                period_days,
                health_score,
                trend,
                tasks.get('total', 0),
                float(tasks.get('success_rate', 0)),
                len(gaps),
                sum(1 for g in gaps if g.get('severity') == 'high'),
                json.dumps(actions),
                json.dumps(full_report),
            )).fetchone()
            db.commit()
            new_id = row['id'] if row else None
            print(f"weekly_review: saved to weekly_reviews id={new_id}")
            return new_id
        finally:
            db.close()
    except Exception as e:
        print(f"weekly_review: _save_review failed: {e}")
        return None


# ============================================================================
# PUBLIC API
# ============================================================================

def run_weekly_review(days: int = 7) -> Dict[str, Any]:
    """
    Run the complete weekly review.

    Steps:
    1. Ensure weekly_reviews table exists
    2. Collect metrics from PostgreSQL
    3. Analyze gaps (pure logic, no DB)
    4. Calculate health score and trend
    5. Make ONE Sonnet call for analysis, recommendations, enhancements
    6. Take Phase 5 actions (enhancements, memories, pruning)
    7. Save to weekly_reviews table
    8. Return complete result dict

    Args:
        days (int): Number of days to analyze. Default 7, max 90.

    Returns:
        dict with keys: success, review_id, health_score, trend,
        executive_summary, recommendations, actions_taken,
        gaps_count, high_priority_gaps_count, next_week_focus,
        metrics_summary
    """
    print(f"🔍 weekly_review: Starting {days}-day review...")
    _ensure_table()

    try:
        print("  📊 Collecting metrics...")
        metrics = _collect_metrics(days=days)

        print("  🔎 Analyzing gaps...")
        gaps = _analyze_gaps(metrics)

        health_score = _calculate_health_score(metrics)
        trend = _determine_trend(health_score, gaps)
        print(f"  💊 Health score: {health_score}/100, trend: {trend}")

        print("  🤖 Running AI analysis (1 Sonnet call)...")
        analysis = _run_ai_analysis(metrics, gaps, health_score)

        print("  ⚡ Taking Phase 5 actions...")
        actions = _take_phase5_actions(analysis, metrics, health_score)

        print("  💾 Saving review...")
        review_id = _save_review(days, health_score, trend, metrics, gaps, analysis, actions)

        print(f"✅ weekly_review: Complete. Health={health_score}/100, "
              f"Gaps={len(gaps)}, Enhancements={actions.get('enhancements_generated', 0)}")

        return {
            'success': True,
            'review_id': review_id,
            'health_score': health_score,
            'trend': trend,
            'executive_summary': analysis.get('executive_summary', ''),
            'recommendations': analysis.get('recommendations', []),
            'prompt_enhancement_suggestions': analysis.get('prompt_enhancement_suggestions', []),
            'routing_patterns': analysis.get('routing_patterns', ''),
            'next_week_focus': analysis.get('next_week_focus', []),
            'actions_taken': actions,
            'gaps_count': len(gaps),
            'high_priority_gaps_count': sum(1 for g in gaps if g.get('severity') == 'high'),
            'gaps': gaps,
            'metrics_summary': {
                'tasks_total': metrics.get('tasks', {}).get('total', 0),
                'success_rate': metrics.get('tasks', {}).get('success_rate', 0),
                'avg_response_time': metrics.get('tasks', {}).get('avg_execution_time_seconds', 0),
                'escalation_rate': metrics.get('escalations', {}).get('escalation_rate', 0),
                'consensus_rate': metrics.get('consensus', {}).get('consensus_rate', 0),
                'user_rating': metrics.get('feedback', {}).get('avg_overall_rating', 0),
            },
        }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"weekly_review: run_weekly_review failed: {tb}")
        return {
            'success': False,
            'error': str(e),
            'health_score': 0,
            'trend': 'unknown',
            'executive_summary': f'Review failed: {str(e)}',
            'recommendations': [],
            'actions_taken': {},
            'gaps_count': 0,
            'high_priority_gaps_count': 0,
        }


def get_latest_review() -> Optional[Dict[str, Any]]:
    """
    Retrieve the most recent weekly review from the database.
    Returns dict with review data, or None if no reviews exist yet.
    """
    _ensure_table()
    try:
        db = get_db()
        try:
            row = db.execute("""
                SELECT id, run_at, period_days, health_score, trend,
                       tasks_processed, success_rate, gaps_count,
                       high_priority_gaps_count, actions_taken, full_report
                FROM weekly_reviews
                ORDER BY run_at DESC
                LIMIT 1
            """).fetchone()

            if not row:
                return None

            return {
                'id': row['id'],
                'run_at': str(row['run_at']),
                'period_days': row['period_days'],
                'health_score': row['health_score'],
                'trend': row['trend'],
                'tasks_processed': row['tasks_processed'],
                'success_rate': row['success_rate'],
                'gaps_count': row['gaps_count'],
                'high_priority_gaps_count': row['high_priority_gaps_count'],
                'actions_taken': row['actions_taken'],
                'full_report': row['full_report'],
            }
        finally:
            db.close()
    except Exception as e:
        print(f"weekly_review: get_latest_review failed: {e}")
        return None


# I did no harm and this file is not truncated
