"""
Conversation Utilities - Context Management
Created: February 10, 2026
Last Updated: March 06, 2026 - POSTGRESQL PLACEHOLDER FIX

CHANGELOG:
- March 06, 2026: POSTGRESQL PLACEHOLDER FIX
  * All 5 SQLite ? placeholders replaced with PostgreSQL %s placeholders.
  * Switched from get_db() (database.py wrapper) to get_db_connection()
    (db_engine.py) with context manager pattern, which correctly issues
    %s placeholders to psycopg2.
  * Replaced SELECT-then-INSERT/UPDATE in store_conversation_context()
    with a single PostgreSQL upsert (ON CONFLICT DO UPDATE).
  * No logic changes. All three function signatures unchanged.
  * Root cause of failure:
      psycopg2.errors.SyntaxError: syntax error at or near "AND"
      LINE 1: ...OM conversation_context WHERE conversation_id = ? AND key = ?
    SQLite uses ? placeholders; PostgreSQL requires %s.

- February 10, 2026: Created for managing temporary conversation context
  during file analysis workflows.

PURPOSE:
Functions for managing temporary conversation context during multi-step
workflows (e.g., labor file detection -> analysis offer -> user confirms
-> analysis runs). Uses the conversation_context database table.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from db_engine import get_db_connection, get_db_type


def store_conversation_context(conversation_id, key, value):
    """
    Save temporary data for this conversation.

    Args:
        conversation_id: Conversation ID
        key:             Context key (e.g., 'pending_analysis_session')
        value:           Value to store (string)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    INSERT INTO conversation_context (conversation_id, key, value, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (conversation_id, key)
                    DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """, (conversation_id, key, value))
            else:
                cursor.execute(
                    'SELECT id FROM conversation_context WHERE conversation_id = ? AND key = ?',
                    (conversation_id, key)
                )
                existing = cursor.fetchone()
                if existing:
                    cursor.execute(
                        'UPDATE conversation_context SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                        (value, existing[0])
                    )
                else:
                    cursor.execute(
                        'INSERT INTO conversation_context (conversation_id, key, value) VALUES (?, ?, ?)',
                        (conversation_id, key, value)
                    )
    except Exception as e:
        print(f"store_conversation_context failed: {e}")


def get_conversation_context(conversation_id, key):
    """
    Get temporary data for this conversation.

    Args:
        conversation_id: Conversation ID
        key:             Context key

    Returns:
        Value string or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    SELECT value FROM conversation_context
                    WHERE conversation_id = %s AND key = %s
                """, (conversation_id, key))
            else:
                cursor.execute(
                    'SELECT value FROM conversation_context WHERE conversation_id = ? AND key = ?',
                    (conversation_id, key)
                )
            row = cursor.fetchone()
            if row:
                return row['value'] if hasattr(row, 'keys') else row[0]
            return None
    except Exception as e:
        print(f"get_conversation_context failed: {e}")
        return None


def clear_conversation_context(conversation_id, key):
    """
    Delete temporary data for this conversation.

    Args:
        conversation_id: Conversation ID
        key:             Context key to clear
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    DELETE FROM conversation_context
                    WHERE conversation_id = %s AND key = %s
                """, (conversation_id, key))
            else:
                cursor.execute(
                    'DELETE FROM conversation_context WHERE conversation_id = ? AND key = ?',
                    (conversation_id, key)
                )
    except Exception as e:
        print(f"clear_conversation_context failed: {e}")

# I did no harm and this file is not truncated
