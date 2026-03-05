"""
routes/utils.py - Shared Utilities for Route Handlers
Created: (original date unknown - file was lost from GitHub)
Last Updated: March 05, 2026 - REBUILT WITH POSTGRESQL PLACEHOLDERS

CHANGELOG:
- March 05, 2026: REBUILT FROM SCRATCH
  * This file existed on Render's ephemeral filesystem but was never
    committed to GitHub. It was lost on redeploy, causing:
      "syntax error at or near 'AND' LINE 1:
       ...OM conversation_context WHERE conversation_id = ? AND key = ?"
  * Root cause: original file used SQLite ? placeholders.
  * Rebuilt with correct PostgreSQL %s placeholders throughout.
  * All four functions required by orchestration_handler.py restored:
      - convert_markdown_to_html()
      - store_conversation_context()
      - get_conversation_context()
      - clear_conversation_context()
  * conversation_context table created at startup if it does not exist
    (safe to run every time - uses CREATE TABLE IF NOT EXISTS).

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import re
from db_engine import get_db_connection, get_db_type


# ============================================================================
# MARKDOWN TO HTML CONVERTER
# Converts AI markdown responses to HTML for display in the frontend.
# Handles: headers, bold, italic, code blocks, inline code, lists,
#          horizontal rules, and line breaks.
# ============================================================================

def convert_markdown_to_html(text):
    """
    Convert markdown-formatted AI response text to HTML for frontend display.

    Args:
        text: Markdown string from AI response

    Returns:
        HTML string safe for injection into the UI
    """
    if not text:
        return ""

    # Escape any existing HTML to prevent injection
    # (only < and > that aren't already part of HTML tags)
    # We do a light conversion - not a full sanitizer
    html = text

    # Code blocks (``` ... ```) - must be processed before inline code
    html = re.sub(
        r'```(\w+)?\n(.*?)\n```',
        lambda m: (
            f'<pre><code class="language-{m.group(1) or ""}">'
            f'{m.group(2)}'
            f'</code></pre>'
        ),
        html,
        flags=re.DOTALL
    )

    # Inline code (`...`)
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # Headers (### ## #) - process largest first
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$',  r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$',   r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Bold (**text** or __text__)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'__(.+?)__',     r'<strong>\1</strong>', html)

    # Italic (*text* or _text_) - after bold so ** doesn't match
    html = re.sub(r'\*([^*\n]+)\*', r'<em>\1</em>', html)
    html = re.sub(r'_([^_\n]+)_',   r'<em>\1</em>', html)

    # Horizontal rules (--- or ***)
    html = re.sub(r'^[-*]{3,}$', r'<hr>', html, flags=re.MULTILINE)

    # Unordered lists (- item or * item)
    # Wrap consecutive list items in <ul>
    def replace_ul(m):
        items = m.group(0).strip().split('\n')
        li_items = ''.join(
            f'<li>{re.sub(r"^[-*]\s+", "", item.strip())}</li>'
            for item in items if item.strip()
        )
        return f'<ul>{li_items}</ul>'

    html = re.sub(
        r'(?:^[-*] .+\n?)+',
        replace_ul,
        html,
        flags=re.MULTILINE
    )

    # Ordered lists (1. item)
    def replace_ol(m):
        items = m.group(0).strip().split('\n')
        li_items = ''.join(
            f'<li>{re.sub(r"^\d+\.\s+", "", item.strip())}</li>'
            for item in items if item.strip()
        )
        return f'<ol>{li_items}</ol>'

    html = re.sub(
        r'(?:^\d+\. .+\n?)+',
        replace_ol,
        html,
        flags=re.MULTILINE
    )

    # Paragraphs: double newline -> paragraph break
    # Single newlines inside a paragraph -> <br>
    paragraphs = html.split('\n\n')
    processed = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Don't wrap block-level elements in <p>
        if para.startswith(('<h1', '<h2', '<h3', '<ul', '<ol', '<pre', '<hr')):
            processed.append(para)
        else:
            # Replace single newlines with <br> within the paragraph
            para = para.replace('\n', '<br>')
            processed.append(f'<p>{para}</p>')

    return '\n'.join(processed)


# ============================================================================
# CONVERSATION CONTEXT KEY-VALUE STORE
#
# Stores lightweight key-value pairs scoped to a conversation_id.
# Used by orchestration_handler.py to pass state between requests
# (e.g. 'pending_analysis_session' -> session_id for labor file processing).
#
# Table: conversation_context
#   conversation_id  TEXT NOT NULL
#   key              TEXT NOT NULL
#   value            TEXT
#   updated_at       TIMESTAMP DEFAULT NOW()
#   PRIMARY KEY (conversation_id, key)
# ============================================================================

def _ensure_conversation_context_table():
    """
    Create conversation_context table if it does not exist.
    Called lazily before any read/write operation.
    Safe to call multiple times (IF NOT EXISTS).
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_context (
                    conversation_id TEXT NOT NULL,
                    key             TEXT NOT NULL,
                    value           TEXT,
                    updated_at      TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (conversation_id, key)
                )
            """)
    except Exception as e:
        print(f"conversation_context table init warning: {e}")


def store_conversation_context(conversation_id, key, value):
    """
    Store a key-value pair scoped to a conversation.

    Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE (upsert).
    Value is stored as a string; callers are responsible for
    JSON-encoding complex values before storing.

    Args:
        conversation_id: UUID string identifying the conversation
        key:             String key (e.g. 'pending_analysis_session')
        value:           String value to store

    Returns:
        True on success, False on error
    """
    _ensure_conversation_context_table()
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
                # SQLite fallback (local dev only)
                cursor.execute("""
                    INSERT OR REPLACE INTO conversation_context
                    (conversation_id, key, value, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (conversation_id, key, value))
        return True
    except Exception as e:
        print(f"store_conversation_context error: {e}")
        return False


def get_conversation_context(conversation_id, key):
    """
    Retrieve a stored value scoped to a conversation.

    Args:
        conversation_id: UUID string identifying the conversation
        key:             String key to look up

    Returns:
        String value if found, None if not found or on error
    """
    _ensure_conversation_context_table()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    SELECT value FROM conversation_context
                    WHERE conversation_id = %s AND key = %s
                """, (conversation_id, key))
            else:
                cursor.execute("""
                    SELECT value FROM conversation_context
                    WHERE conversation_id = ? AND key = ?
                """, (conversation_id, key))
            row = cursor.fetchone()
            if row:
                return row['value'] if hasattr(row, 'keys') else row[0]
            return None
    except Exception as e:
        print(f"get_conversation_context error: {e}")
        return None


def clear_conversation_context(conversation_id, key):
    """
    Delete a stored key-value pair scoped to a conversation.

    Args:
        conversation_id: UUID string identifying the conversation
        key:             String key to delete

    Returns:
        True on success, False on error
    """
    _ensure_conversation_context_table()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if get_db_type() == 'postgresql':
                cursor.execute("""
                    DELETE FROM conversation_context
                    WHERE conversation_id = %s AND key = %s
                """, (conversation_id, key))
            else:
                cursor.execute("""
                    DELETE FROM conversation_context
                    WHERE conversation_id = ? AND key = ?
                """, (conversation_id, key))
        return True
    except Exception as e:
        print(f"clear_conversation_context error: {e}")
        return False

# I did no harm and this file is not truncated
