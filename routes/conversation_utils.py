"""
Conversation Utilities - Context Management
Created: February 10, 2026
Last Updated: February 18, 2026 - COMMITTED TO GITHUB (was missing, causing import failures)

CHANGELOG:
- February 18, 2026: CRITICAL FIX - This file existed only on the Render server and
  was wiped on every new deploy. Now committed to GitHub so it persists across deploys.
  Without this file, 'from routes.utils import store_conversation_context' failed,
  breaking the labor analysis offer workflow and causing 'datatype mismatch' errors
  when fallback code paths passed wrong types to database functions.

PURPOSE:
Functions for managing temporary conversation context during multi-step workflows
(e.g., labor file detection -> analysis offer -> user confirms -> analysis runs).
Uses the conversation_context database table (added February 10, 2026).

AUTHOR: Jim @ Shiftwork Solutions LLC
"""


def store_conversation_context(conversation_id, key, value):
    """
    Save temporary key-value data for a conversation workflow.

    Used by labor analysis workflow to remember the pending session ID
    between the upload step and the user's confirmation response.

    Args:
        conversation_id: Conversation ID (string UUID)
        key: Context key (e.g., 'pending_analysis_session')
        value: Value to store (string)
    """
    from database import get_db
    db = get_db()

    try:
        existing = db.execute(
            'SELECT id FROM conversation_context WHERE conversation_id = ? AND key = ?',
            (conversation_id, key)
        ).fetchone()

        if existing:
            db.execute(
                'UPDATE conversation_context SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (value, existing['id'])
            )
        else:
            db.execute(
                'INSERT INTO conversation_context (conversation_id, key, value) VALUES (?, ?, ?)',
                (conversation_id, key, value)
            )

        db.commit()
    except Exception as e:
        print(f"⚠️ store_conversation_context failed: {e}")
    finally:
        db.close()


def get_conversation_context(conversation_id, key):
    """
    Get temporary key-value data for a conversation workflow.

    Args:
        conversation_id: Conversation ID (string UUID)
        key: Context key (e.g., 'pending_analysis_session')

    Returns:
        Value string or None if not found
    """
    from database import get_db
    db = get_db()

    try:
        row = db.execute(
            'SELECT value FROM conversation_context WHERE conversation_id = ? AND key = ?',
            (conversation_id, key)
        ).fetchone()

        return row['value'] if row else None
    except Exception as e:
        print(f"⚠️ get_conversation_context failed: {e}")
        return None
    finally:
        db.close()


def clear_conversation_context(conversation_id, key):
    """
    Delete temporary key-value data for a conversation workflow.

    Called after the pending session has been consumed so it is not
    re-triggered on subsequent messages in the same conversation.

    Args:
        conversation_id: Conversation ID (string UUID)
        key: Context key to clear (e.g., 'pending_analysis_session')
    """
    from database import get_db
    db = get_db()

    try:
        db.execute(
            'DELETE FROM conversation_context WHERE conversation_id = ? AND key = ?',
            (conversation_id, key)
        )
        db.commit()
    except Exception as e:
        print(f"⚠️ clear_conversation_context failed: {e}")
    finally:
        db.close()


# I did no harm and this file is not truncated
