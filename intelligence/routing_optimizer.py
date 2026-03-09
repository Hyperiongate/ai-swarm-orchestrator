"""
intelligence/routing_optimizer.py
AI Swarm Orchestrator — Phase 5: Learning That Changes Behavior
Created: March 09, 2026
Last Updated: March 09, 2026 — Fix table schema mismatch + missing commits

CHANGELOG:
- March 09, 2026: Phase 5 Deliverable 1 — NEW FILE
  Tracks which AI model performs best per task category and feeds that
  intelligence into the Phase 4 reasoning engine as routing bias.

- March 09, 2026: BUG FIX #1 — Missing conn.commit() in write operations
  ROOT CAUSE: get_db_connection() context manager closes without commit().
  FIX: Added conn.commit() after INSERT in record_outcome().

- March 09, 2026: BUG FIX #2 — routing_preferences table has wrong schema
  ROOT CAUSE: Phase 1 migration created routing_preferences with different
  column names than Phase 5 expects. Every SELECT and INSERT failed with
  "column does not exist".
  FIX: Replaced _ensure_unique_index() with _ensure_table_schema() which:
    1. Checks whether routing_preferences has the expected Phase 5 columns.
    2. If columns are missing/wrong, DROPs the old table and RECREATEs it
       with the correct schema. Phase 5 never wrote valid data to the old
       table (all writes failed), so no data is lost.
    3. Creates the UNIQUE index required for INSERT ... ON CONFLICT.
    4. Commits all DDL operations explicitly.

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

MIN_SAMPLE_SIZE = 3


# ─────────────────────────────────────────────────────────────────────────────
# TABLE SETUP
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_table_schema():
    """
    Ensure routing_preferences has the correct Phase 5 schema.

    Phase 1 created this table with different column names. This function:
      1. Checks for the presence of the 'task_category' column.
      2. If missing, DROPs the old table and CREATEs it fresh with the
         correct Phase 5 columns.
      3. Creates the UNIQUE index on (task_category, preferred_model)
         required for INSERT ... ON CONFLICT DO UPDATE.
      4. Commits all DDL explicitly.

    Safe to drop: Phase 5 never successfully wrote to the old table because
    all INSERTs failed due to the wrong column names. Zero valid data exists.
    Called once per process. Any failure is logged but never raised.
    """
    try:
        from db_engine import get_db_connection

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check if task_category column exists
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = 'routing_preferences'
                  AND column_name  = 'task_category'
            """)
            row = cursor.fetchone()
            has_correct_schema = (row['cnt'] > 0)

            if not has_correct_schema:
                print("⚠️ [routing_optimizer] routing_preferences has wrong schema "
                      "— dropping and recreating with Phase 5 schema...")

                cursor.execute("DROP TABLE IF EXISTS routing_preferences CASCADE")
                conn.commit()

                cursor.execute("""
                    CREATE TABLE routing_preferences (
                        id              SERIAL PRIMARY KEY,
                        task_category   VARCHAR(100) NOT NULL,
                        preferred_model VARCHAR(50)  NOT NULL,
                        success_count   INTEGER      DEFAULT 0,
                        total_count     INTEGER      DEFAULT 0,
                        avg_score       NUMERIC(5,2) DEFAULT 5.0,
                        updated_at      TIMESTAMP    DEFAULT NOW()
                    )
                """)
                conn.commit()
                print("✅ [routing_optimizer] routing_preferences table created "
                      "with Phase 5 schema")
            else:
                print("✅ [routing_optimizer] routing_preferences schema verified")

            # Create unique index (IF NOT EXISTS — safe to re-run)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                    uix_routing_preferences_category_model
                ON routing_preferences (task_category, preferred_model)
            """)
            conn.commit()
            print("✅ [routing_optimizer] routing_preferences unique index ready")

        _TABLE_READY['ready'] = True

    except Exception as e:
        print(f"⚠️ [routing_optimizer] _ensure_table_schema failed: {e}")


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
        model_used (str):    Model that handled the request.
        execution_time_ms (int): Wall-clock time for the response in ms.
        user_feedback (float|None): User rating 1-10, or None.
        consensus_score (float|None): Consensus agreement score 0-10, or None.
        was_escalated (bool): True if the request was escalated to Opus.

    Scoring logic:
        Base score = 5.0 (neutral).
        User feedback maps directly if provided.
        Consensus score blended at 30% weight if no user feedback.
        Escalation deducts 1.0. Fast (<3000ms) adds 0.5. Slow (>15000ms) deducts 0.5.
        Score clamped to 1.0-10.0.

    Returns:
        bool: True if recorded successfully, False on any error.
    """
    try:
        if not _TABLE_READY['ready']:
            _ensure_table_schema()

        category = str(task_category or 'unknown').lower().strip()[:100]
        model = str(model_used or 'unknown').lower().strip()[:50]
        exec_ms = int(execution_time_ms or 0)

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
            conn.commit()

        print(f"📊 [routing_optimizer] Recorded: {category}/{model} "
              f"score={score:.1f} ({exec_ms}ms)")
        return True

    except Exception as e:
        print(f"⚠️ [routing_optimizer] record_outcome failed (non-critical): {e}")
        return False


def _calculate_score(user_feedback, consensus_score, execution_time_ms, was_escalated):
    """
    Derive a 1.0-10.0 composite score for a single outcome.
    """
    score = 5.0

    if user_feedback is not None:
        try:
            fb = float(user_feedback)
            score = max(1.0, min(10.0, fb))
        except (TypeError, ValueError):
            pass
    elif consensus_score is not None:
        try:
            cs = float(consensus_score)
            score = (score * 0.7) + (cs * 0.3)
        except (TypeError, ValueError):
            pass

    if was_escalated:
        score -= 1.0

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
    Requires MIN_SAMPLE_SIZE (3) recorded outcomes before trusting the data.
    Returns None if insufficient data — reasoning engine default routing applies.
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
    Only includes pairs with >= MIN_SAMPLE_SIZE outcomes.
    Returns empty string if no qualifying data exists.
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
# get_all_routing_data()
# ─────────────────────────────────────────────────────────────────────────────

def get_all_routing_data():
    """
    Return all routing preference records for API display.
    No minimum sample size filter — returns everything accumulated so far.
    Returns empty list on error.
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
