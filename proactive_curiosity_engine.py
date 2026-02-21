"""
Proactive Curiosity Engine - Phase 1 Component 2
Created: February 5, 2026
Last Updated: February 21, 2026 - FIXED table column migration + curiosity nonsense

CHANGELOG:

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

        # Create/upgrade the proactive_suggestions table
        self._ensure_table()

    def _ensure_table(self):
        """
        Create the proactive_suggestions table if it doesn't exist,
        AND add any missing columns to an already-existing table.

        UPDATED February 21, 2026:
        Added ALTER TABLE migration for conversation_id column.
        CREATE TABLE IF NOT EXISTS is idempotent but won't add columns to
        an existing table. We inspect actual columns after creation and
        ALTER TABLE ADD COLUMN for any that are missing.
        """
        try:
            db = get_db()

            # Step 1: Create table if it doesn't exist at all
            db.execute('''
                CREATE TABLE IF NOT EXISTS proactive_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    suggestion_type TEXT NOT NULL,
                    suggestion_text TEXT NOT NULL,
                    reasoning TEXT,
                    user_action TEXT DEFAULT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            ''')
            db.execute('''
                CREATE INDEX IF NOT EXISTS idx_proactive_suggestions_conversation
                ON proactive_suggestions (conversation_id)
            ''')
            db.commit()

            # Step 2: Inspect actual columns and add any that are missing
            # This handles the case where the table existed before conversation_id
            # was added to the schema.
            existing_cols = {
                row[1] for row in db.execute('PRAGMA table_info(proactive_suggestions)').fetchall()
            }

            required_cols = {
                'conversation_id': 'TEXT NOT NULL DEFAULT ""',
                'suggestion_type': 'TEXT NOT NULL DEFAULT ""',
                'suggestion_text': 'TEXT NOT NULL DEFAULT ""',
                'reasoning':       'TEXT',
                'user_action':     'TEXT DEFAULT NULL',
                'created_at':      "TEXT DEFAULT (datetime('now'))"
            }

            for col_name, col_def in required_cols.items():
                if col_name not in existing_cols:
                    try:
                        db.execute(
                            f'ALTER TABLE proactive_suggestions ADD COLUMN {col_name} {col_def}'
                        )
                        db.commit()
                        print(f"✅ Added missing column to proactive_suggestions: {col_name}")
                    except Exception as alter_err:
                        print(f"⚠️ Could not add column {col_name}: {alter_err}")

            db.close()

        except Exception as e:
            print(f"⚠️ Could not create proactive_suggestions table: {e}")

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
            count = db.execute('''
                SELECT COUNT(*) as cnt FROM proactive_suggestions
                WHERE conversation_id = ?
                AND suggestion_type = 'curious_followup'
            ''', (conversation_id,)).fetchone()
            db.close()
            return count['cnt'] if count else 0
        except Exception as e:
            print(f"⚠️ Could not count curiosity: {e}")
            return 0

    def _log_curiosity(self, conversation_id, question, triggers):
        """Log that we asked a curious question"""
        try:
            db = get_db()
            db.execute('''
                INSERT INTO proactive_suggestions
                (conversation_id, suggestion_type, suggestion_text, reasoning)
                VALUES (?, ?, ?, ?)
            ''', (conversation_id, 'curious_followup', question,
                  json.dumps({'triggers': [t['type'] for t in triggers]})))
            db.commit()
            db.close()
        except Exception as e:
            print(f"⚠️ Could not log curiosity: {e}")

    def get_curiosity_stats(self):
        """Get statistics about curiosity behavior"""
        try:
            db = get_db()
            stats = db.execute('''
                SELECT
                    COUNT(*) as total_questions,
                    COUNT(DISTINCT conversation_id) as conversations_with_curiosity,
                    AVG(CASE WHEN user_action = 'engaged' THEN 1.0 ELSE 0.0 END) as engagement_rate
                FROM proactive_suggestions
                WHERE suggestion_type = 'curious_followup'
            ''').fetchone()
            db.close()
            return dict(stats) if stats else {}
        except Exception as e:
            print(f"⚠️ Could not get curiosity stats: {e}")
            return {}


def get_curiosity_engine():
    """Get singleton instance"""
    return ProactiveCuriosityEngine()


# I did no harm and this file is not truncated
