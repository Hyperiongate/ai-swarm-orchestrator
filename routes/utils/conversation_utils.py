"""
Conversation Utilities - Context Management
Created: February 10, 2026
Last Updated: February 10, 2026

Functions for managing temporary conversation context during file analysis.

Author: Jim @ Shiftwork Solutions LLC
"""


def store_conversation_context(conversation_id, key, value):
    """
    Save temporary data for this conversation.
    
    Args:
        conversation_id: Conversation ID
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
    finally:
        db.close()


def get_conversation_context(conversation_id, key):
    """
    Get temporary data for this conversation.
    
    Args:
        conversation_id: Conversation ID
        key: Context key
        
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
    finally:
        db.close()


def clear_conversation_context(conversation_id, key):
    """
    Delete temporary data for this conversation.
    
    Args:
        conversation_id: Conversation ID
        key: Context key to clear
    """
    from database import get_db
    db = get_db()
    
    try:
        db.execute(
            'DELETE FROM conversation_context WHERE conversation_id = ? AND key = ?',
            (conversation_id, key)
        )
        db.commit()
    finally:
        db.close()


# I did no harm and this file is not truncated
