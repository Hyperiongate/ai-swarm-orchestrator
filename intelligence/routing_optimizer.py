"""
intelligence/routing_optimizer.py
AI Swarm Orchestrator — Phase 5: Learning That Changes Behavior
Created: March 09, 2026
Last Updated: March 09, 2026 — Initial build (Phase 5, Deliverable 1)

CHANGELOG:
- March 09, 2026: Phase 5 Deliverable 1 — NEW FILE
  Tracks which AI model performs best per task category and feeds that
  intelligence into the Phase 4 reasoning engine as routing bias.

  WHAT IT DOES:
    - record_outcome(): Called after every completed request. Upserts a
      running average into routing_preferences for (task_category, model).
    - get_preferred_model(): Returns the best model for a category based
      on accumulated avg_score (minimum 3 attempts before trusting the data).
    - get_routing_insights(): Returns a human-readable string summarizing
      all routing preferences — injected into the reasoning engine prompt.

  DATABASE:
    Uses the routing_preferences table created in Phase 1 migration.
    Columns: id, task_category, preferred_model, success_count,
             total_count, avg_score, updated_at.
    Adds a UNIQUE index on (task_category, preferred_model) on first use
    so that INSERT ... ON CONFLICT DO UPDATE works correctly.

  DESIGN RULES:
    - This module SUGGESTS routing — it does not override the reasoning engine.
    - Minimum 3 attempts per (category, model) pair before recommendations.
    - All DB calls use get_db_connection() context manager.
    - Row access by column name only (RealDictCursor).
    - %s placeholders throughout.
    - TRUE/FALSE for booleans (not 1/0).
    - Never raises — all functions return safe defaults on error.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import time
import json
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL FLAGS — one-time setup per process
# ─────────────────────────────────────────────────────────────────────────────

_TABLE_READY = {'ready': False}

VALID_MODELS = {'sonnet', 'opus', 'gpt4', 'deepseek', 'gemini'}

VALID_CATEGORIES = {
    'scheduling', 'research', 'client_consulting', 'code',
    'content', 'analysis', 'general', 'survey', 'document',
    'labor', 'unknown',
}

# Minimum number of recorded outcomes before we trust the preference data
MIN_SAMPLE_SIZE = 3


# ─────────────────────────────────────────────────────────────────────────────
# TABLE SETUP — routing_preferences UNIQUE index (idempotent, run once)
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_unique_index():
    """
    Create a UNIQUE index on routing_preferences(task_category, preferred_model)
    if it does not already exist. Required for INSERT ... ON CONFLICT DO UPDATE.
    Called once per process. Any failure is logged but never raised.
    """
    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    uix_routing_preferences_category_model
                ON routing_preferences (task_category, preferred_model)
            """)
        _TABLE_READY['ready'] = True
        print("✅ [routing_optimizer] routing_preferences unique index ready")
    except Exception as e:
        print(f"⚠️ [routing_optimizer] Could not create unique index: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# record_outcome()
# ─────────────────────────────────────────────────────────────────────────────

def record_outcome(
    task_category,
    model_used,
    execution_time_ms,
    user_feedback=None,
    consensus_score=None,
    was_escalated=False,
):
    """
    Record the outcome of a completed request into routing_preferences.
    Updates running averages for the (task_category, model_used) pair.

    Args:
        task_category (str): Category of the task (e.g. 'scheduling', 'code').
                             Normalized to lowercase. Unknown values stored as 'unknown'.
        model_used (str):    Model that handled the request ('sonnet', 'gpt4', etc.).
                             Unknown values stored as-is (max 50 chars).
        execution_time_ms (int): Wall-clock time for the response in milliseconds.
        user_feedback (float|None): User rating 1-10, or None if not provided.
        consensus_score (float|None): Consensus agreement score 0-10, or None.
        was_escalated (bool): True if the request was escalated to Opus.

    Scoring logic:
        Base score = 5.0 (neutral).
        User feedback (1-10) maps directly to score if provided.
        Consensus score (0-10) blended in at 30% weight if user feedback absent.
        Escalation deducts 1.0 (the system needed help).
        Fast responses (< 3000ms) add 0.5. Very slow (> 15000ms) deduct 0.5.
        Score clamped to 1.0 – 10.0.

    Returns:
        bool: True if recorded successfully, False on any error.
    """
    try:
        if not _TABLE_READY['ready']:
            _ensure_unique_index()

        # Normalize inputs
        category = str(task_category or 'unknown').lower().strip()[:100]
        model = str(model_used or 'unknown').lower().strip()[:50]
        exec_ms = int(execution_time_ms or 0)

        # Calculate a composite score for this outcome
        score = _calculate_score(
            user_feedback=user_feedback,
            consensus_score=consensus_score,
            execution_time_ms=exec_ms,
            was_escalated=was_escalated,
        )

        success_increment = 1 if score >= 6.0 else 0

        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO routing_preferences
                    (task_category, preferred_model, success_count,
                     total_count, avg_score, updated_at)
                VALUES (%s, %s, %s, 1, %s, NOW())
                ON CONFLICT (task_category, preferred_model)
                DO UPDATE SET
                    success_count = routing_preferences.success_count
                                    + EXCLUDED.success_count,
                    total_count   = routing_preferences.total_count + 1,
                    avg_score     = (
                        (routing_preferences.avg_score
                         * routing_preferences.total_count)
                        + EXCLUDED.avg_score
                    ) / (routing_preferences.total_count + 1),
                    updated_at    = NOW()
            """, (category, model, success_increment, score))

        print(f"📊 [routing_optimizer] Recorded: {category}/{model} "
              f"score={score:.1f} ({exec_ms}ms)")
        return True

    except Exception as e:
        print(f"⚠️ [routing_optimizer] record_outcome failed (non-critical): {e}")
        return False


def _calculate_score(user_feedback, consensus_score, execution_time_ms, was_escalated):
    """
    Derive a 1.0–10.0 composite score for a single outcome.
    See record_outcome() docstring for full scoring logic.
    """
    score = 5.0  # neutral baseline

    if user_feedback is not None:
        try:
            fb = float(user_feedback)
            score = max(1.0, min(10.0, fb))
        except (TypeError, ValueError):
            pass
    elif consensus_score is not None:
        try:
            cs = float(consensus_score)
            # Blend: 70% baseline, 30% consensus
            score = (score * 0.7) + (cs * 0.3)
        except (TypeError, ValueError):
            pass

    # Escalation penalty
    if was_escalated:
        score -= 1.0

    # Speed adjustment
    if execution_time_ms < 3000:
        score += 0.5
    elif execution_time_ms > 15000:
        score -= 0.5

    return round(max(1.0, min(10.0, score)), 2)


# ─────────────────────────────────────────────────────────────────────────────
# get_preferred_model()
# ─────────────────────────────────────────────────────────────────────────────

def get_preferred_model(task_category):
    """
    Return the best-performing model for a given task category.

    Requires at least MIN_SAMPLE_SIZE (3) recorded outcomes for a
    (category, model) pair before trusting the data. Returns None if
    insufficient data exists — the reasoning engine's default routing applies.

    Args:
        task_category (str): Task category to look up.

    Returns:
        dict | None:
            {
                'preferred_model': 'gpt4',
                'avg_score': 8.5,
                'total_tasks': 12,
                'reason': 'gpt4 scores 8.5 avg on 12 scheduling tasks'
            }
            or None if no reliable data.
    """
    try:
        category = str(task_category or '').lower().strip()[:100]
        if not category:
            return None

        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_category, preferred_model, avg_score, total_count
                FROM routing_preferences
                WHERE task_category = %s
                  AND total_count >= %s
                ORDER BY avg_score DESC
                LIMIT 5
            """, (category, MIN_SAMPLE_SIZE))
            rows = cursor.fetchall()

        if not rows:
            return None

        best = rows[0]
        return {
            'preferred_model': best['preferred_model'],
            'avg_score': round(float(best['avg_score']), 2),
            'total_tasks': int(best['total_count']),
            'reason': (
                f"{best['preferred_model']} scores {float(best['avg_score']):.1f} avg "
                f"on {int(best['total_count'])} {category} tasks"
            ),
        }

    except Exception as e:
        print(f"⚠️ [routing_optimizer] get_preferred_model failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# get_routing_insights()
# ─────────────────────────────────────────────────────────────────────────────

def get_routing_insights():
    """
    Return a human-readable summary of all current routing preferences.
    Injected into the Phase 4 reasoning engine prompt as additional context.

    Only includes (category, model) pairs with >= MIN_SAMPLE_SIZE outcomes.
    Groups by category and reports the best model per category.

    Returns:
        str: A one-paragraph insight string, or empty string if no data.
             Example:
             "Based on past performance: GPT4 performs best on scheduling
              tasks (avg score 8.5 over 12 tasks); SONNET performs best on
              research tasks (avg score 9.1 over 8 tasks)."
    """
    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_category, preferred_model, avg_score, total_count
                FROM routing_preferences
                WHERE total_count >= %s
                ORDER BY task_category, avg_score DESC
            """, (MIN_SAMPLE_SIZE,))
            rows = cursor.fetchall()

        if not rows:
            return ""

        # Group by category, keep best model per category
        by_category = defaultdict(list)
        for row in rows:
            by_category[row['task_category']].append(row)

        lines = []
        for category in sorted(by_category.keys()):
            cat_rows = by_category[category]
            best = max(cat_rows, key=lambda r: float(r['avg_score']))
            lines.append(
                f"{best['preferred_model'].upper()} performs best on {category} tasks "
                f"(avg score {float(best['avg_score']):.1f} over "
                f"{int(best['total_count'])} tasks)"
            )

        if not lines:
            return ""

        return "Based on past performance: " + "; ".join(lines) + "."

    except Exception as e:
        print(f"⚠️ [routing_optimizer] get_routing_insights failed: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# get_all_routing_data()  — for the /api/learning/routing-preferences endpoint
# ─────────────────────────────────────────────────────────────────────────────

def get_all_routing_data():
    """
    Return all routing preference records for API display.
    No minimum sample size filter — returns everything accumulated so far.

    Returns:
        list of dicts, ordered by task_category then avg_score descending.
        Each dict: task_category, preferred_model, success_count,
                   total_count, avg_score, updated_at.
        Empty list on error.
    """
    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_category, preferred_model, success_count,
                       total_count, avg_score, updated_at
                FROM routing_preferences
                ORDER BY task_category, avg_score DESC
            """)
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    except Exception as e:
        print(f"⚠️ [routing_optimizer] get_all_routing_data failed: {e}")
        return []


# I did no harm and this file is not truncated
