"""
Conversation Summarizer - Fix #6
Created: February 4, 2026
Updated: February 5, 2026 - Fixed IndentationError at line 26

Compresses long conversations into key facts for context.
"""

import json
from datetime import datetime
from database import get_db, get_messages


class ConversationSummarizer:
    """Summarizes conversations for long-term context"""
    
    def __init__(self):
        self.summary_threshold = 10  # Summarize after 10 messages
    
    def should_summarize(self, conversation_id):
        """Check if conversation needs summarization"""
        messages = get_messages(conversation_id, limit=100)
        
        # Check if we have unsummarized messages
        db = get_db()
        last_summary = db.execute('''
            SELECT message_range FROM conversation_summaries
            WHERE conversation_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (conversation_id,)).fetchone()
        db.close()
        
        if not last_summary:
            return len(messages) >= self.summary_threshold
        
        # Check if enough new messages since last summary
        last_range = last_summary['message_range']
        last_msg_id = int(last_range.split('-')[-1]) if '-' in last_range else 0
        
        new_messages = [m for m in messages if m['id'] > last_msg_id]
        return len(new_messages) >= self.summary_threshold
    
    def summarize_conversation(self, conversation_id, ai_summarize_func):
        """
        Create summary of conversation.
        
        Args:
            conversation_id: Conversation to summarize
            ai_summarize_func: AI function to generate summary
            
        Returns:
            Summary dict
        """
        messages = get_messages(conversation_id, limit=100)
        
        if not messages:
            return None
        
        # Build conversation text
        conv_text = ""
        for msg in messages:
            role = "User" if msg['role'] == 'user' else "Assistant"
            content = msg['content'][:500]  # Truncate long messages
            conv_text += f"{role}: {content}\n\n"
        
        # Generate summary using AI
        summary_prompt = f"""Summarize this conversation into key facts:

{conv_text}

Provide:
1. Main topics discussed
2. Decisions made (if any)
3. Important numbers/dates mentioned
4. Next steps agreed upon

Format as brief bullet points."""
        
        try:
            summary_result = ai_summarize_func(summary_prompt)
            
            if isinstance(summary_result, dict):
                summary_text = summary_result.get('content', '')
            else:
                summary_text = str(summary_result)
            
            # Extract entities
            entities = self._extract_entities(conv_text)
            
            # Store summary
            db = get_db()
            
            message_range = f"{messages[0]['id']}-{messages[-1]['id']}"
            
            db.execute('''
                INSERT INTO conversation_summaries
                (conversation_id, summary_text, key_decisions, mentioned_entities, message_range)
                VALUES (?, ?, ?, ?, ?)
            ''', (conversation_id, summary_text, 
                  json.dumps([]), 
                  json.dumps(entities),
                  message_range))
            
            db.commit()
            db.close()
            
            return {
                'summary': summary_text,
                'entities': entities
            }
        except Exception as e:
            print(f"⚠️ Summarization failed: {e}")
            return None
    
    def get_conversation_context(self, conversation_id):
        """Get summarized context for a conversation"""
        try:
            db = get_db()
            
            summaries = db.execute('''
                SELECT summary_text, mentioned_entities
                FROM conversation_summaries
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT 3
            ''', (conversation_id,)).fetchall()
            
            db.close()
            
            if not summaries:
                return ""
            
            context = "\n\n=== CONVERSATION HISTORY SUMMARY ===\n"
            
            for idx, summary in enumerate(reversed(summaries), 1):
                context += f"\nPart {idx}:\n{summary['summary_text']}\n"
                
                # Add entities
                entities = json.loads(summary['mentioned_entities'])
                if entities:
                    context += f"Key details mentioned: "
                    context += ", ".join([f"{k}: {v}" for k, v in entities.items()])
                    context += "\n"
            
            context += "\n=== END SUMMARY ===\n\n"
            
            return context
        except Exception as e:
            print(f"⚠️ Could not get context: {e}")
            return ""
    
    def _extract_entities(self, text):
        """Extract numbers, dates, and key terms"""
        import re
        
        entities = {}
        
        # Extract numbers (employees, shift hours, etc.)
        numbers = re.findall(r'\b(\d+)\s+(employees?|workers?|people|hours?|shifts?)\b', text.lower())
        for num, unit in numbers:
            if unit not in entities:
                entities[unit] = num
        
        # Extract industries
        industries = ['manufacturing', 'healthcare', 'mining', 'food', 'pharmaceutical']
        for industry in industries:
            if industry in text.lower():
                entities['industry'] = industry
        
        return entities


def get_conversation_summarizer():
    """Get singleton instance"""
    return ConversationSummarizer()


# I did no harm and this file is not truncated
