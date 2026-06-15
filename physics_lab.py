"""
FeynmanLab — Physics Thinking Partner Engine
File: physics_lab.py
Created: June 14, 2026
Last Updated: June 14, 2026 — WO-14 Phase 1: conversational core

PURPOSE:
    The reasoning engine for FeynmanLab, a physics thinking partner for Jim:
    an adversary-first interlocutor for thought experiments (relativity and
    astrophysics lean, broad interests). It challenges, clarifies, suggests,
    and does the math inline. Sessions persist, so a thread of reasoning can be
    left and resumed later.

    Phase 1 (this file) is the conversational core — no tools yet. Later phases
    add tools the partner reaches for: research (Tavily, Phase 2), real code
    execution for simulations (Phase 3), and visualization (Phase 4).

ARCHITECTURE NOTE — why this calls Opus directly:
    The swarm's orchestration/ai_clients.call_claude_opus() injects the swarm's
    identity ("you are the AI Swarm Orchestrator for Shiftwork Solutions") and a
    FORMATTING_REQUIREMENTS block into every call. Both would fight the physics
    persona. So this module calls the Anthropic client directly with a clean,
    dedicated system prompt and the full conversation history — the same lean
    approach call_claude_sonnet_raw() uses — so FeynmanLab is purely a physics
    interlocutor with nothing bleeding in from the orchestrator.

DATABASE TABLES (PostgreSQL, lazy-created on first use):
    physics_sessions
        id          SERIAL PRIMARY KEY
        title       TEXT
        created_at  TIMESTAMP DEFAULT NOW()
        updated_at  TIMESTAMP DEFAULT NOW()
    physics_messages
        id          SERIAL PRIMARY KEY
        session_id  INTEGER  (-> physics_sessions.id)
        role        TEXT     ('user' | 'assistant')
        content     TEXT
        created_at  TIMESTAMP DEFAULT NOW()

CHANGELOG:
- June 14, 2026: WO-14 PHASE 1 — INITIAL IMPLEMENTATION
  * New file. Persona system prompt + direct Opus call (config.CLAUDE_OPUS_MODEL,
    no capabilities/formatting injection) + session/message persistence on the
    canonical db_engine / RealDictCursor / %s / RETURNING id pattern.
  * Public API: create_session(), list_sessions(), get_session(), ask(),
    rename_session(), delete_session().
  * No existing file is modified by this module. Rule 1 (do no harm) preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

import anthropic
import config
from db_engine import get_db_connection

logger = logging.getLogger(__name__)

PARTNER_NAME = "FeynmanLab"

# Full history is sent each turn (Opus has a large context window). This cap is
# a safety valve for very long sessions — it keeps the most recent N messages.
MAX_HISTORY_MESSAGES = 60

# Anthropic client — created directly here (clean, no swarm injection).
_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY) if config.ANTHROPIC_API_KEY else None


# ============================================================================
# PERSONA
# ============================================================================

SYSTEM_PROMPT = """You are FeynmanLab, a physics thinking partner.

You are built in the spirit of Richard Feynman's approach to physics — physical \
intuition before formalism, first-principles reasoning, relentless intellectual \
honesty, and a deep allergy to hand-waving and to jargon used as a substitute for \
understanding. You are your own entity, not a simulation of Feynman: never claim to \
be him, never invent quotations, anecdotes, or opinions and attribute them to him or \
to any other real person.

You are talking with Jim, an experienced thinker who runs serious physics thought \
experiments — his interests lean toward astrophysics and relativity but range broadly. \
Treat him as a peer thinking out loud, not a student.

YOUR HIGHEST VALUE IS FINDING THE FLAW. Your most useful move in a thought experiment \
is usually to be the adversary: surface the hidden assumption, propose the limiting or \
boundary case that breaks an intuition, construct the counterexample, steelman an idea \
and then stress-test it to destruction. Agreement teaches nothing; productive friction \
is the whole point. Play the sharp interlocutor — Bohr to Jim's Einstein.

NEVER FLATTER. Do not pad responses with praise like "brilliant," "great insight," or \
"fascinating." Engage the idea on its merits and move straight to the substance. If an \
idea is good, the way you show it is by failing to break it, not by complimenting it.

BE RIGOROUSLY HONEST — you must not fool yourself, and you must not let Jim fool himself. \
Sharply distinguish established physics from speculation. When an idea conflicts with a \
well-established result or observation, say so plainly and name the specific evidence or \
theorem it runs into — not to shut the idea down, but because honest testing against what \
is actually known is exactly the service. Flag your own uncertainty rather than \
papering over it. Never fabricate data, measurements, citations, or results.

DO THE MATH. When a question has a quantitative core, actually work it: set it up, carry \
the numbers, keep units, give the result, and do an order-of-magnitude sanity check. Don't \
retreat to "it can be shown." Write mathematics in LaTeX — inline as $...$ and display as \
$$...$$ — so it renders cleanly.

You also clarify when asked (explain with concrete physical pictures, not jargon), suggest \
variations and follow-on experiments, and point to what would be worth computing or checking \
next. When a question would genuinely benefit from a calculation you should actually run, or \
from current data or the literature you should actually look up, say so explicitly — e.g. \
"here's where we'd want to run the real numbers" or "this turns on what the measurements \
actually say" — but keep that brief and only when it matters.

This is a conversation, not a lecture. Be substantive but don't over-explain — one sharp \
challenge or one clean derivation beats a survey. Build on the thread as it develops. It is \
entirely fine, and often best, to say "I don't know," "that's beyond what's settled," or \
"let's actually work that out before either of us trusts the intuition."
"""


# ============================================================================
# TABLE INIT (lazy)
# ============================================================================

_tables_initialized = False


def _ensure_tables():
    """Create the FeynmanLab tables on first use. Idempotent."""
    global _tables_initialized
    if _tables_initialized:
        return
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS physics_sessions (
                id          SERIAL PRIMARY KEY,
                title       TEXT,
                created_at  TIMESTAMP DEFAULT NOW(),
                updated_at  TIMESTAMP DEFAULT NOW()
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS physics_messages (
                id          SERIAL PRIMARY KEY,
                session_id  INTEGER NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT NOW()
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_physics_messages_session
            ON physics_messages (session_id, id)
        ''')
        conn.commit()
        _tables_initialized = True
    finally:
        conn.close()


# ============================================================================
# SESSION CRUD
# ============================================================================

def create_session(title: Optional[str] = None) -> Dict[str, Any]:
    """Create a new session and return it as a dict (id, title, created_at)."""
    _ensure_tables()
    title = (title or "").strip() or f"Session — {datetime.now().strftime('%b %d, %Y %H:%M')}"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO physics_sessions (title) VALUES (%s) RETURNING id, title, created_at',
            (title,)
        )
        row = cursor.fetchone()
        conn.commit()
        return {
            'id': row['id'],
            'title': row['title'],
            'created_at': _iso(row['created_at']),
        }
    finally:
        conn.close()


def list_sessions(limit: int = 100) -> List[Dict[str, Any]]:
    """Return sessions newest-activity first, each with a message count."""
    _ensure_tables()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.id, s.title, s.created_at, s.updated_at,
                   COUNT(m.id) AS message_count
            FROM physics_sessions s
            LEFT JOIN physics_messages m ON m.session_id = s.id
            GROUP BY s.id, s.title, s.created_at, s.updated_at
            ORDER BY s.updated_at DESC, s.id DESC
            LIMIT %s
        ''', (limit,))
        rows = cursor.fetchall()
        return [{
            'id': r['id'],
            'title': r['title'],
            'created_at': _iso(r['created_at']),
            'updated_at': _iso(r['updated_at']),
            'message_count': r['message_count'],
        } for r in rows]
    finally:
        conn.close()


def get_session(session_id: int) -> Optional[Dict[str, Any]]:
    """Return a session with its full ordered message list, or None if absent."""
    _ensure_tables()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, title, created_at, updated_at FROM physics_sessions WHERE id = %s',
            (session_id,)
        )
        s = cursor.fetchone()
        if not s:
            return None
        cursor.execute(
            'SELECT id, role, content, created_at FROM physics_messages '
            'WHERE session_id = %s ORDER BY id ASC',
            (session_id,)
        )
        msgs = cursor.fetchall()
        return {
            'id': s['id'],
            'title': s['title'],
            'created_at': _iso(s['created_at']),
            'updated_at': _iso(s['updated_at']),
            'messages': [{
                'id': m['id'],
                'role': m['role'],
                'content': m['content'],
                'created_at': _iso(m['created_at']),
            } for m in msgs],
        }
    finally:
        conn.close()


def rename_session(session_id: int, title: str) -> bool:
    """Rename a session. Returns True if a row was updated."""
    _ensure_tables()
    title = (title or "").strip()
    if not title:
        return False
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE physics_sessions SET title = %s, updated_at = NOW() '
            'WHERE id = %s RETURNING id',
            (title, session_id)
        )
        updated = cursor.fetchone() is not None
        conn.commit()
        return updated
    finally:
        conn.close()


def delete_session(session_id: int) -> bool:
    """Delete a session and its messages. Returns True if the session existed."""
    _ensure_tables()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM physics_messages WHERE session_id = %s', (session_id,))
        cursor.execute(
            'DELETE FROM physics_sessions WHERE id = %s RETURNING id',
            (session_id,)
        )
        existed = cursor.fetchone() is not None
        conn.commit()
        return existed
    finally:
        conn.close()


# ============================================================================
# THE PARTNER
# ============================================================================

def ask(session_id: int, user_message: str) -> Dict[str, Any]:
    """
    Send a user message to FeynmanLab within a session, persist both the user
    message and the partner's reply, and return the reply.

    Returns dict: {success, reply, session_id} on success, or
    {success: False, error} on failure. The user message is persisted even if
    the model call fails, so the thread is never silently lost.
    """
    _ensure_tables()

    user_message = (user_message or "").strip()
    if not user_message:
        return {'success': False, 'error': 'Empty message'}

    # Confirm the session exists.
    session = get_session(session_id)
    if session is None:
        return {'success': False, 'error': f'Session {session_id} not found'}

    if _client is None:
        return {'success': False, 'error': 'ANTHROPIC_API_KEY not configured'}

    # Persist the user message first (so it survives a model failure).
    _add_message(session_id, 'user', user_message)

    # Build the message history for the API from stored messages (already
    # includes the user message we just added).
    history = _load_history(session_id)
    api_messages = [{'role': m['role'], 'content': m['content']} for m in history]

    try:
        response = _client.messages.create(
            model=config.CLAUDE_OPUS_MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=api_messages,
            timeout=config.ANTHROPIC_TIMEOUT,
        )
        reply = response.content[0].text
    except Exception as e:
        logger.error(f"[FeynmanLab] Opus call failed: {e}")
        return {'success': False, 'error': f'Model call failed: {e}', 'session_id': session_id}

    _add_message(session_id, 'assistant', reply)
    _touch_session(session_id)

    return {'success': True, 'reply': reply, 'session_id': session_id}


# ============================================================================
# PRIVATE HELPERS
# ============================================================================

def _add_message(session_id: int, role: str, content: str) -> None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO physics_messages (session_id, role, content) VALUES (%s, %s, %s)',
            (session_id, role, content)
        )
        conn.commit()
    finally:
        conn.close()


def _load_history(session_id: int) -> List[Dict[str, str]]:
    """Load the recent message history (oldest-first), capped to MAX_HISTORY_MESSAGES."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT role, content FROM physics_messages '
            'WHERE session_id = %s ORDER BY id ASC',
            (session_id,)
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    history = [{'role': r['role'], 'content': r['content']} for r in rows]
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
        # The API requires the first message to be from the user.
        while history and history[0]['role'] != 'user':
            history.pop(0)
    return history


def _touch_session(session_id: int) -> None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE physics_sessions SET updated_at = NOW() WHERE id = %s',
            (session_id,)
        )
        conn.commit()
    finally:
        conn.close()


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


# I did no harm and this file is not truncated
