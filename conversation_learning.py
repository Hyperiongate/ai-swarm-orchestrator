"""
CONVERSATION LEARNING MODULE
Created: February 3, 2026

Automatically extracts insights from conversations and stores them in the Knowledge Management DB.
This makes the AI Swarm get smarter with every conversation - true cumulative intelligence.

Every time you teach the Swarm something, it remembers forever.

HOW TO INTEGRATE:
1. Add to core.py: from conversation_learning import learn_from_conversation
2. In the orchestration completion endpoint, after AI responds:
   learn_from_conversation(user_message, ai_response, conversation_context)

Author: Jim @ Shiftwork Solutions LLC
"""

import os
import json
import hashlib
from datetime import datetime
from orchestration.ai_clients import call_claude_sonnet


def extract_conversation_insights(user_message, ai_response, conversation_context=""):
    """
    Analyze a conversation turn and extract learnable insights.
    
    Args:
        user_message: What the user said
        ai_response: How the AI responded
        conversation_context: Optional context about the conversation
        
    Returns:
        dict with extracted insights or None if nothing worth learning
    """
    
    # Build extraction prompt
    extraction_prompt = f"""Analyze this conversation exchange and extract any valuable consulting insights that should be remembered for future reference.

CONVERSATION:
User: {user_message}

AI Response: {ai_response}

Extract ONLY if the conversation contains:
- Specific client approaches or strategies mentioned by user
- Project-specific details or outcomes
- Lessons learned or cautionary tales
- Industry-specific practices
- Concrete examples of what worked/didn't work
- Operational details worth remembering

DO NOT extract:
- General questions without specific information
- Generic consulting advice
- Hypothetical scenarios
- Small talk or clarifications

If there's something worth remembering, respond with JSON:
{{
    "worth_learning": true,
    "insight_type": "client_strategy|lesson_learned|industry_practice|operational_detail",
    "summary": "Brief 1-2 sentence summary",
    "key_details": ["detail 1", "detail 2"],
    "client_mentioned": "client name or null",
    "industry": "industry or null",
    "tags": ["tag1", "tag2"]
}}

If nothing worth learning, respond with:
{{
    "worth_learning": false
}}
"""
    
    try:
        response = call_claude_sonnet(extraction_prompt)
        
        # Extract content
        if isinstance(response, dict):
            if response.get('error'):
                return None
            response_text = response.get('content', '')
        else:
            response_text = str(response)
        
        # Clean JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(response_text)
        
        if not result.get('worth_learning'):
            return None
        
        return result
        
    except Exception as e:
        print(f"⚠️ Insight extraction error: {e}")
        return None


def store_conversation_insight(insight, user_message, ai_response):
    """
    Store extracted insight in the Knowledge Management database.
    
    Args:
        insight: Extracted insight dict from extract_conversation_insights()
        user_message: Original user message
        ai_response: Original AI response
    """
    
    try:
        import sqlite3
        
        # Use same database path as Knowledge Management
        db_path = os.environ.get('KNOWLEDGE_DB_PATH', 'swarm_intelligence.db')
        
        # Create a "conversation learned" document
        document_name = f"Conversation_Insight_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        document_type = "conversation_learned"
        
        # Build extracted data
        extracted_data = {
            'patterns': [],
            'insights': [{
                'type': insight.get('insight_type', 'conversation'),
                'summary': insight.get('summary'),
                'details': insight.get('key_details', []),
                'source': 'conversation',
                'learned_at': datetime.now().isoformat()
            }],
            'conversation_snippet': {
                'user': user_message[:500],  # First 500 chars
                'ai': ai_response[:500]
            }
        }
        
        # Create metadata
        metadata = {
            'document_name': document_name,
            'client': insight.get('client_mentioned'),
            'industry': insight.get('industry'),
            'tags': insight.get('tags', []),
            'learned_from': 'conversation',
            'upload_date': datetime.now().isoformat()
        }
        
        # Calculate hash to prevent duplicates
        content_for_hash = f"{insight.get('summary')}{insight.get('key_details')}"
        content_hash = hashlib.md5(content_for_hash.encode()).hexdigest()
        
        # Store in database
        db = sqlite3.connect(db_path)
        cursor = db.cursor()
        
        # Check if already stored (prevent duplicates)
        cursor.execute('SELECT id FROM knowledge_extracts WHERE source_hash = ?', (content_hash,))
        if cursor.fetchone():
            db.close()
            print("ℹ️  Insight already in knowledge base")
            return False
        
        # Insert new insight
        cursor.execute('''
            INSERT INTO knowledge_extracts (
                document_type, document_name, extracted_data,
                client, industry, source_hash, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            document_type,
            document_name,
            json.dumps(extracted_data),
            metadata.get('client'),
            metadata.get('industry'),
            content_hash,
            json.dumps(metadata)
        ))
        
        # Log the learning
        cursor.execute('''
            INSERT INTO ingestion_log (
                document_name, document_type, status,
                patterns_extracted, insights_extracted
            ) VALUES (?, ?, ?, ?, ?)
        ''', (document_name, document_type, 'success', 0, 1))
        
        db.commit()
        db.close()
        
        print(f"✅ Learned from conversation: {insight.get('summary')}")
        return True
        
    except Exception as e:
        print(f"⚠️ Failed to store conversation insight: {e}")
        return False


def learn_from_conversation(user_message, ai_response, conversation_context=""):
    """
    Main function: Extract and store insights from a conversation.
    Call this after each AI response.
    
    Args:
        user_message: What the user said
        ai_response: How the AI responded
        conversation_context: Optional additional context
        
    Returns:
        bool: True if something was learned, False otherwise
    """
    
    # Skip very short exchanges
    if len(user_message) < 20 or len(ai_response) < 50:
        return False
    
    # Extract insights
    insight = extract_conversation_insights(user_message, ai_response, conversation_context)
    
    if not insight:
        return False
    
    # Store in knowledge base
    success = store_conversation_insight(insight, user_message, ai_response)
    
    return success


# I did no harm and this file is not truncated
