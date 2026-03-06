"""
Conversation Utilities - Context Management
Created: February 10, 2026
Last Updated: March 06, 2026 - COLUMN NAME FIX

CHANGELOG:
- March 06, 2026: COLUMN NAME FIX
  * Root cause: conversation_context table uses columns context_key and
    context_value (not key and value). All queries were referencing the
    wrong column names, causing:
      psycopg2.errors.UndefinedColumn: column "value" does not exist
  * Fix: Updated all SELECT, INSERT, UPDATE, DELETE queries to use the
    correct column names: context_key and context_value.
  * Also fixed ON CONFLICT clause to use (conversation_id, context_key)
    which matches the UNIQUE constraint added to the migration.
  * SQLite fallback paths updated with the same column name corrections.

- March 06, 2026: POSTGRESQL PLACEHOLDER FIX
  * All SQLite ? placeholders replaced with PostgreSQL %s placeholders.
  * Switched from get_db() to get_db_connection() with context manager.

- February 10, 2026: Created for managing temporary conversation context
  during file analysis workflows.

PURPOSE:
Functions for managing temporary conversation context during multi-step
workflows (e.g., labor file detection -> analysis offer -> user confirms
-> analysis runs). Uses the conversation_context database table.

TABLE SCHEMA (conversation_context):
    id               SERIAL PRIMARY KEY
    conversation_id  TEXT NOT NULL
    context_type     TEXT NOT NULL  (always stored as 'workflow')
    context_key      TEXT NOT NULL  (the key parameter)
    context_value    TEXT           (the value parameter)
    created_at       TIMESTAMP
    updated_at       TIMESTAMP
    UNIQUE(conversation_id, context_key)

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from db_engine import get_db_connection, get_db_type


def store_conversation_context(conversation_id, key, value):
    """
    Save temporary key-value data for a conversation workflow.

    Args:
        conversation_id: Conversation ID (string UUID)
        key:             Context key (e.g., 'pending_analysis_session')
        value:           Value to store (string)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    INSERT INTO conversation_context
                        (conversation_id, context_type, context_key, context_value, updated_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (conversation_id, context_key)
                    DO UPDATE SET context_value = EXCLUDED.context_value, updated_at = NOW()
                """, (conversation_id, 'workflow', key, value))
            else:
                # SQLite fallback for local development only
                cursor.execute(
                    'SELECT id FROM conversation_context WHERE conversation_id = ? AND context_key = ?',
                    (conversation_id, key)
                )
                existing = cursor.fetchone()
                if existing:
                    cursor.execute(
                        'UPDATE conversation_context SET context_value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                        (value, existing[0])
                    )
                else:
                    cursor.execute(
                        'INSERT INTO conversation_context (conversation_id, context_type, context_key, context_value) VALUES (?, ?, ?, ?)',
                        (conversation_id, 'workflow', key, value)
                    )
    except Exception as e:
        print(f"store_conversation_context failed: {e}")


def get_conversation_context(conversation_id, key):
    """
    Get temporary key-value data for a conversation workflow.

    Args:
        conversation_id: Conversation ID (string UUID)
        key:             Context key (e.g., 'pending_analysis_session')

    Returns:
        Value string or None if not found
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    SELECT context_value FROM conversation_context
                    WHERE conversation_id = %s AND context_key = %s
                """, (conversation_id, key))
            else:
                cursor.execute(
                    'SELECT context_value FROM conversation_context WHERE conversation_id = ? AND context_key = ?',
                    (conversation_id, key)
                )
            row = cursor.fetchone()
            if row:
                return row['context_value'] if hasattr(row, 'keys') else row[0]
            return None
    except Exception as e:
        print(f"get_conversation_context failed: {e}")
        return None


def clear_conversation_context(conversation_id, key):
    """
    Delete temporary key-value data for a conversation workflow.

    Args:
        conversation_id: Conversation ID (string UUID)
        key:             Context key to clear (e.g., 'pending_analysis_session')
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    DELETE FROM conversation_context
                    WHERE conversation_id = %s AND context_key = %s
                """, (conversation_id, key))
            else:
                cursor.execute(
                    'DELETE FROM conversation_context WHERE conversation_id = ? AND context_key = ?',
                    (conversation_id, key)
                )
    except Exception as e:
        print(f"clear_conversation_context failed: {e}")

# I did no harm and this file is not truncated
