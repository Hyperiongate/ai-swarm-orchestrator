"""
Proactive Curiosity Engine - Phase 1 Component 2
Created: February 5, 2026
Last Updated: March 06, 2026 - POSTGRESQL FIX

CHANGELOG:

- March 06, 2026: POSTGRESQL FIX - Full PostgreSQL compatibility
  PROBLEM: Three separate errors fired on every request:
    1. "syntax error at or near AUTOINCREMENT" - _ensure_table() used SQLite-only
       AUTOINCREMENT syntax in CREATE TABLE. get_db() returns a PostgreSQL
       connection, not SQLite.
    2. "syntax error at or near AND" - _get_recent_curiosity_count() used ?
       placeholder which PostgreSQL does not accept; also the WHERE clause
       continuation was malformed.
    3. "syntax error at or near ','" with VALUES (?, ?, ?, ?) - _log_curiosity()
       used ? placeholders throughout.
  FIX:
    - _ensure_table(): Completely rewritten for PostgreSQL.
        * Removed AUTOINCREMENT (PostgreSQL uses SERIAL, handled by migration).
        * Removed PRAGMA table_info (SQLite-only); replaced with
          information_schema.columns query.
        * Removed datetime('now') SQLite default; uses NOW().
        * Simplified: migration_001 already creates proactive_suggestions with
          the correct PostgreSQL schema. _ensure_table() now just verifies the
          table exists and adds any missing columns via ALTER TABLE IF NOT EXISTS.
    - _get_recent_curiosity_count(): ? -> %s, fixed WHERE clause formatting,
      fetchone()[0] instead of fetchone()['cnt'] (psycopg2 positional rows).
    - _log_curiosity(): ? -> %s throughout.
    - get_curiosity_stats(): Replaced dict(stats) with explicit column mapping
      since psycopg2 rows are positional, not named dicts.
  No logic changes. No function signature changes. Fully backward compatible.

- February 21, 2026: FIXED proactive_suggestions COLUMN MIGRATION + CLIENT NAME STOPWORDS
  PROBLEM 1: _ensure_table() used CREATE TABLE IF NOT EXISTS which is idempotent -
    it will NOT add a missing column to an already-existing table. The table was
    originally created without the conversation_id column in an earlier migration.
    Result: Every _log_curiosity() and _get_recent_curiosity_count() call failed
    with "no such column: conversation_id" despite _ensure_table() running at init.
  FIX 1: Added ALTER TABLE fallback in _ensure_table(). After CREATE TABLE IF NOT
    EXISTS runs, we inspect the actual columns and ADD any that are missing. This
    safely upgrades the existing table schema without dropping data.

  PROBLEM 2: _detect_curiosity_triggers() used re.findall to find "client names"
    but matched common English question words (What, How, When, Where, Who, Why)
    because they are Capitalized at the start of sentences.
    Result: "What did OSHA announce this week?" triggered after_client_mention
    with client="What", producing "What's the most interesting thing about
    What's operation?" as the curious follow-up.
  FIX 2: Added QUESTION_WORD_STOPWORDS set. Client name candidates are filtered
    against this set before triggering after_client_mention. Any single word
    matching a stopword is discarded. Multi-word matches are also checked
    so "What Is" doesn't slip through.

- February 20, 2026: FIXED missing proactive_suggestions table
  BUG: _get_recent_curiosity_count() and _log_curiosity() both reference the
       'proactive_suggestions' table, which was never created by any migration.
  FIX: Added _ensure_table() called from __init__.

Author: Jim @ Shiftwork Solutions LLC
"""

import json
import re
import random
from datetime import datetime
from database import get_db


# =============================================================================
# STOPWORDS FOR CLIENT NAME DETECTION
# Added February 21, 2026
# These are common English words that appear capitalized at sentence start
# and should never be treated as client names.
# =============================================================================
QUESTION_WORD_STOPWORDS = {
    'What', 'How', 'When', 'Where', 'Who', 'Why', 'Which', 'Is', 'Are',
    'Does', 'Did', 'Do', 'Was', 'Were', 'Has', 'Have', 'Had', 'Can',
    'Could', 'Would', 'Should', 'Will', 'Shall', 'May', 'Might', 'Must',
    'Any', 'Some', 'The', 'This', 'That', 'These', 'Those', 'Please',
    'Tell', 'Show', 'Give', 'Find', 'Look', 'Search', 'Help', 'Create',
    'Make', 'Write', 'Draft', 'Generate', 'Explain', 'Describe', 'List',
    'OSHA', 'DOL', 'EPA'  # Agencies that shouldn't trigger client curiosity
}


class ProactiveCuriosityEngine:
    """Generates natural, contextual follow-up questions"""

    def __init__(self):
        self.curiosity_patterns = {
            'after_schedule_design': [
                "How did the team react to this schedule when you've used it before?",
                "What's the most interesting challenge you've faced implementing this type of schedule?",
                "I'm curious - what made you lean toward this pattern specifically?"
            ],
            'after_client_mention': [
                "Tell me more about {client} - what makes them unique?",
                "How long have you been working with {client}?",
                "What's the most interesting thing about {client}'s operation?"
            ],
            'after_problem_solved': [
                "I'm curious - what led to this situation in the first place?",
                "Have you seen this pattern before with other clients?",
                "What would you have done differently if you had to do it again?"
            ],
            'after_numbers_mentioned': [
                "That's interesting - how does {number} compare to typical operations?",
                "What drove the decision to go with {number}?",
                "I'm curious about the story behind that number"
            ],
            'after_industry_mentioned': [
                "What's unique about scheduling in {industry} compared to other industries?",
                "How has {industry} changed in terms of shift work over the years?",
                "What's the biggest scheduling challenge in {industry}?"
            ],
            'general_curiosity': [
                "What's on your mind about this project?",
                "Is there anything about this situation that's particularly tricky?",
                "What would you want people to learn from this experience?"
            ]
        }

        self.curiosity_history = []
        self.max_curiosity_per_conversation = 3

        # Verify/upgrade the proactive_suggestions table
        self._ensure_table()

    def _ensure_table(self):
        """
        Verify the proactive_suggestions table exists and has all required columns.

        REWRITTEN March 06, 2026 for PostgreSQL compatibility:
        - migration_001_initial_schema.py creates proactive_suggestions with the
          correct PostgreSQL schema (SERIAL PRIMARY KEY, BOOLEAN, NOW()).
        - This method just verifies the table is present and adds any missing
          columns. Uses information_schema instead of SQLite PRAGMA table_info.
        - No CREATE TABLE here - that is the migration's responsibility.
        """
        try:
            db = get_db()

            # Check if table exists (PostgreSQL information_schema)
            table_check = db.execute(
                """SELECT table_name FROM information_schema.tables
                   WHERE table_schema = 'public'
                   AND table_name = 'proactive_suggestions'"""
            ).fetchone()

            if not table_check:
                # Table doesn't exist yet - migration will create it on next
                # startup. Log a warning and return gracefully.
                print("⚠️ proactive_suggestions table not found - will be created by migration")
                db.close()
                return

            # Check existing columns via information_schema
            col_rows = db.execute(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema = 'public'
                   AND table_name = 'proactive_suggestions'"""
            ).fetchall()
            existing_cols = {row[0] for row in col_rows}

            # Required columns with PostgreSQL-compatible defaults
            required_cols = {
                'conversation_id': 'TEXT',
                'response_id':     'TEXT',
                'suggestion_type': 'TEXT',
                'suggestion_text': 'TEXT',
                'context':         'TEXT',
                'was_accepted':    'BOOLEAN DEFAULT FALSE',
                'reasoning':       'TEXT',
                'created_at':      'TIMESTAMP DEFAULT NOW()',
            }

            for col_name, col_def in required_cols.items():
                if col_name not in existing_cols:
                    try:
                        db.execute(
                            f'ALTER TABLE proactive_suggestions '
                            f'ADD COLUMN IF NOT EXISTS {col_name} {col_def}'
                        )
                        db.commit()
                        print(f"✅ Added missing column to proactive_suggestions: {col_name}")
                    except Exception as alter_err:
                        print(f"⚠️ Could not add column {col_name}: {alter_err}")

            db.close()

        except Exception as e:
            print(f"⚠️ Could not verify proactive_suggestions table: {e}")

    def should_be_curious(self, conversation_id, response_context):
        """
        Determine if AI should ask a curious follow-up question.

        Returns:
            dict with {should_ask: bool, question: str or None, reason: str}
        """
        recent_questions = self._get_recent_curiosity_count(conversation_id)

        if recent_questions >= self.max_curiosity_per_conversation:
            return {
                'should_ask': False,
                'question': None,
                'reason': 'curiosity_budget_exhausted'
            }

        triggers = self._detect_curiosity_triggers(response_context)

        if not triggers:
            return {
                'should_ask': False,
                'question': None,
                'reason': 'no_curiosity_triggers'
            }

        question = self._select_curious_question(triggers, response_context)

        if question:
            self._log_curiosity(conversation_id, question, triggers)
            return {
                'should_ask': True,
                'question': question,
                'reason': f"triggered_by_{triggers[0]['type']}"
            }

        return {
            'should_ask': False,
            'question': None,
            'reason': 'no_good_question_found'
        }

    def _detect_curiosity_triggers(self, context):
        """
        Detect what aspects of the context warrant curiosity.

        UPDATED February 21, 2026:
        Added QUESTION_WORD_STOPWORDS filter for client name detection.
        Previously "What", "How", "Where" etc. were being detected as client
        names because they appear capitalized at the start of sentences.

        Returns:
            list of trigger dicts sorted by priority (highest first)
        """
        triggers = []
        user_request = context.get('user_request', '')
        user_request_lower = user_request.lower()

        # Trigger 1: Schedule was designed
        if any(word in user_request_lower for word in ['schedule', 'dupont', 'panama', 'rotation']):
            triggers.append({
                'type': 'after_schedule_design',
                'data': {},
                'priority': 8
            })

        # Trigger 2: Client mentioned
        # FIXED: filter out question words and common stopwords before triggering
        potential_clients = re.findall(
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
            user_request
        )
        valid_clients = [
            c for c in potential_clients
            if len(c) > 3
            and c not in QUESTION_WORD_STOPWORDS
            and c.split()[0] not in QUESTION_WORD_STOPWORDS  # Check first word of multi-word
        ]
        if valid_clients:
            triggers.append({
                'type': 'after_client_mention',
                'data': {'client': valid_clients[0]},
                'priority': 7
            })

        # Trigger 3: Problem was solved
        if any(word in user_request_lower for word in ['fix', 'problem', 'issue', 'error']):
            triggers.append({
                'type': 'after_problem_solved',
                'data': {},
                'priority': 6
            })

        # Trigger 4: Numbers mentioned (employees, hours, etc.)
        numbers = re.findall(r'(\d+)\s*(employees?|workers?|people|hours?|shifts?)', user_request_lower)
        if numbers:
            triggers.append({
                'type': 'after_numbers_mentioned',
                'data': {'number': f"{numbers[0][0]} {numbers[0][1]}"},
                'priority': 5
            })

        # Trigger 5: Industry mentioned
        industries = ['manufacturing', 'healthcare', 'mining', 'food', 'pharmaceutical', 'distribution']
        mentioned_industries = [ind for ind in industries if ind in user_request_lower]
        if mentioned_industries:
            triggers.append({
                'type': 'after_industry_mentioned',
                'data': {'industry': mentioned_industries[0]},
                'priority': 4
            })

        triggers.sort(key=lambda x: x['priority'], reverse=True)
        return triggers

    def _select_curious_question(self, triggers, context):
        """Select the best curious question based on triggers"""
        if not triggers:
            return random.choice(self.curiosity_patterns['general_curiosity'])

        top_trigger = triggers[0]
        trigger_type = top_trigger['type']

        if trigger_type not in self.curiosity_patterns:
            return None

        question_templates = self.curiosity_patterns[trigger_type]
        question_template = random.choice(question_templates)

        data = top_trigger.get('data', {})
        question = question_template.format(**data) if data else question_template

        return question

    def _get_recent_curiosity_count(self, conversation_id):
        """Count how many curious questions asked in this conversation"""
        try:
            db = get_db()
            result = db.execute(
                """SELECT COUNT(*) FROM proactive_suggestions
                   WHERE conversation_id = %s
                   AND suggestion_type = 'curious_followup'""",
                (conversation_id,)
            ).fetchone()
            db.close()
            # psycopg2 returns positional tuples, not named dicts
            return result[0] if result else 0
        except Exception as e:
            print(f"⚠️ Could not count curiosity: {e}")
            return 0

    def _log_curiosity(self, conversation_id, question, triggers):
        """Log that we asked a curious question"""
        try:
            db = get_db()
            db.execute(
                """INSERT INTO proactive_suggestions
                   (conversation_id, suggestion_type, suggestion_text, reasoning)
                   VALUES (%s, %s, %s, %s)""",
                (
                    conversation_id,
                    'curious_followup',
                    question,
                    json.dumps({'triggers': [t['type'] for t in triggers]})
                )
            )
            db.commit()
            db.close()
        except Exception as e:
            print(f"⚠️ Could not log curiosity: {e}")

    def get_curiosity_stats(self):
        """Get statistics about curiosity behavior"""
        try:
            db = get_db()
            result = db.execute(
                """SELECT
                       COUNT(*) AS total_questions,
                       COUNT(DISTINCT conversation_id) AS conversations_with_curiosity,
                       AVG(CASE WHEN was_accepted = TRUE THEN 1.0 ELSE 0.0 END) AS engagement_rate
                   FROM proactive_suggestions
                   WHERE suggestion_type = 'curious_followup'"""
            ).fetchone()
            db.close()
            if result:
                return {
                    'total_questions': result[0],
                    'conversations_with_curiosity': result[1],
                    'engagement_rate': result[2]
                }
            return {}
        except Exception as e:
            print(f"⚠️ Could not get curiosity stats: {e}")
            return {}


def get_curiosity_engine():
    """Get singleton instance"""
    return ProactiveCuriosityEngine()


# I did no harm and this file is not truncated
