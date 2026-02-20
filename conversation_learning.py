"""
UNIFIED CONVERSATION LEARNING SYSTEM
Created: February 3, 2026
Last Updated: February 20, 2026 - CRITICAL BUG FIX (Stress Test)

CHANGELOG:

- February 20, 2026: CRITICAL BUG FIX in analyze_full_conversation_for_lessons()
  BUG: call_claude_sonnet() returns a dict {'content': ..., 'error': ...}.
       The function passed this dict directly to re.search():
         response = call_claude_sonnet(prompt, max_tokens=4000)
         json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
       re.search() expects a string. Passing a dict causes:
         TypeError: expected string or bytes-like object
       This made the manual "Extract Lessons" feature crash on every call.
  FIX: Extract response['content'] before calling re.search(), with proper
       error handling for API failures. Matches the pattern already used
       correctly in extract_conversation_insights() in this same file.
  NO other logic changed. No function signatures changed. Fully backward compatible.

- February 4, 2026: Combined automatic + manual extraction
- February 3, 2026: Initial creation

TWO MODES OF LEARNING:
1. AUTOMATIC (Passive): Learns from every conversation turn in the background
2. MANUAL (Active): User clicks "Extract Lessons" to capture full conversation wisdom

Automatically extracts insights from conversations and stores them in the Knowledge Management DB.
This makes the AI Swarm get smarter with every conversation - true cumulative intelligence.

Every time you teach the Swarm something, it remembers forever.

HOW TO INTEGRATE:
1. Add to core.py: from conversation_learning import learn_from_conversation
2. In the orchestration completion endpoint, after AI responds:
   learn_from_conversation(user_message, ai_response, conversation_context)
3. Register blueprint in app.py:
   from conversation_learning import learning_bp
   app.register_blueprint(learning_bp)

Author: Jim @ Shiftwork Solutions LLC
"""

import os
import json
import hashlib
import re
from datetime import datetime
from flask import Blueprint, request, jsonify

# Try to import AI client
try:
    from orchestration.ai_clients import call_claude_sonnet
    AI_CLIENT_AVAILABLE = True
except ImportError:
    AI_CLIENT_AVAILABLE = False
    print("⚠️ AI client not available for conversation learning")

# Create blueprint for API endpoints
learning_bp = Blueprint('conversation_learning', __name__, url_prefix='/api/conversations')


# ============================================================================
# AUTOMATIC LEARNING (Background - runs after each message)
# ============================================================================

def extract_conversation_insights(user_message, ai_response, conversation_context=""):
    """
    Analyze a conversation turn and extract learnable insights.

    AUTOMATIC MODE: Runs after each AI response to capture quick insights.

    Args:
        user_message: What the user said
        ai_response: How the AI responded
        conversation_context: Optional context about the conversation

    Returns:
        dict with extracted insights or None if nothing worth learning
    """

    if not AI_CLIENT_AVAILABLE:
        return None

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

        # Extract content - call_claude_sonnet returns a dict
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
        db_path = os.environ.get('KNOWLEDGE_DB_PATH', '/mnt/project/swarm_intelligence.db')

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
            'learned_from': 'conversation_automatic',
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
                client, industry, source_hash, metadata, extracted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            document_type,
            document_name,
            json.dumps(extracted_data),
            metadata.get('client'),
            metadata.get('industry'),
            content_hash,
            json.dumps(metadata),
            datetime.now().isoformat()
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
    AUTOMATIC BACKGROUND LEARNING: Extract and store insights from a conversation turn.
    Call this after each AI response for passive learning.

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


# ============================================================================
# MANUAL LEARNING (User-triggered - extracts full conversation)
# ============================================================================

@learning_bp.route('/<conversation_id>/extract-lessons', methods=['POST'])
def extract_lessons_from_conversation(conversation_id):
    """
    MANUAL EXTRACTION: Extract comprehensive lessons from entire conversation.
    User clicks "Extract Lessons" button to trigger this.

    This is more thorough than automatic learning - analyzes the full conversation
    thread and extracts structured lessons matching Jim's Lessons Learned format.

    Request body:
    {
        "conversation": [
            {"role": "user", "message": "..."},
            {"role": "assistant", "message": "..."}
        ],
        "metadata": {
            "topic": "schedule design",
            "client": "Acme Manufacturing",
            "industry": "manufacturing"
        }
    }

    Returns:
    {
        "success": true,
        "lessons_extracted": 5,
        "categories": ["schedule_design", "client_communication"],
        "message": "Conversation wisdom captured"
    }
    """

    if not AI_CLIENT_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'AI analysis system not available'
        }), 503

    try:
        data = request.get_json()

        if not data.get('conversation'):
            return jsonify({
                'success': False,
                'error': 'Conversation data required'
            }), 400

        conversation = data['conversation']
        metadata = data.get('metadata', {})

        # Step 1: Analyze full conversation with Claude
        print(f"🧠 Analyzing conversation {conversation_id} for comprehensive lessons...")

        analysis_result = analyze_full_conversation_for_lessons(conversation, metadata)

        if not analysis_result['success']:
            return jsonify({
                'success': False,
                'error': analysis_result.get('error', 'Analysis failed')
            }), 500

        # Step 2: Format as comprehensive Lessons Learned document
        lessons_document = format_lessons_as_document(
            analysis_result['lessons'],
            conversation_id,
            metadata
        )

        # Step 3: Store in knowledge base
        if analysis_result['lessons']:
            success = store_comprehensive_lessons(
                lessons_document,
                conversation_id,
                metadata,
                len(analysis_result['lessons'])
            )

            if success:
                print(f"✅ {len(analysis_result['lessons'])} comprehensive lessons added to knowledge base")

                return jsonify({
                    'success': True,
                    'lessons_extracted': len(analysis_result['lessons']),
                    'categories': analysis_result['categories'],
                    'patterns_extracted': len(analysis_result['lessons']),
                    'insights_extracted': len(analysis_result['lessons']),
                    'message': f"Captured {len(analysis_result['lessons'])} lessons from conversation",
                    'preview': analysis_result['lessons'][:3] if len(analysis_result['lessons']) > 3 else analysis_result['lessons']
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to store lessons'
                }), 500
        else:
            return jsonify({
                'success': True,
                'lessons_extracted': 0,
                'message': 'No significant lessons found in this conversation'
            }), 200

    except Exception as e:
        import traceback
        print(f"❌ Manual lesson extraction error: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Failed to extract lessons: {str(e)}'
        }), 500


def analyze_full_conversation_for_lessons(conversation, metadata):
    """
    Use Claude to analyze ENTIRE conversation and extract structured lessons.

    This is more comprehensive than automatic learning - it looks at the full
    context and extracts lessons in Jim's Lessons Learned format.
    """

    try:
        # Format conversation for analysis
        conversation_text = format_conversation_for_analysis(conversation)

        # Create comprehensive analysis prompt
        prompt = f"""You are analyzing a conversation between Jim (a shift work consulting expert with 30+ years experience) and an AI assistant to extract valuable lessons learned that should be preserved in the knowledge base.

CONVERSATION CONTEXT:
Topic: {metadata.get('topic', 'Not specified')}
Client: {metadata.get('client', 'Not specified')}
Industry: {metadata.get('industry', 'Not specified')}

CONVERSATION TRANSCRIPT:
{conversation_text}

YOUR TASK:
Extract concrete, actionable lessons learned from this conversation. Focus on:

1. **Decision Heuristics** - When Jim made a judgment call or explained WHY something should be done a certain way
2. **Best Practices** - Specific approaches Jim endorsed or recommended
3. **Common Mistakes** - Problems Jim warned about or corrected
4. **Client-Specific Insights** - Important context about how this client/industry operates
5. **Process Improvements** - Better ways to do something that Jim identified
6. **Data Validation Rules** - What data to request and why
7. **Implementation Wisdom** - Practical tips for executing projects

IGNORE:
- Generic pleasantries or small talk
- Technical troubleshooting of the AI system itself
- Obvious facts that don't add new insight
- Repetition of well-known consulting basics

OUTPUT FORMAT (JSON):
{{
    "lessons": [
        {{
            "category": "data_validation|schedule_design|client_communication|implementation|cost_analysis|political_dynamics|project_management",
            "title": "Brief title of the lesson",
            "situation": "What triggered this lesson or when to apply it",
            "insight": "The actual lesson - what Jim said/decided/recommended",
            "why_it_matters": "Why this is important",
            "confidence": 0.0-1.0
        }}
    ],
    "categories": ["list of unique categories"],
    "conversation_summary": "One sentence summary of what this conversation accomplished"
}}

Only extract lessons with confidence >= 0.7. Be selective - quality over quantity.
"""

        # ====================================================================
        # FIX (February 20, 2026): Extract response content BEFORE re.search()
        # BEFORE: response = call_claude_sonnet(prompt, max_tokens=4000)
        #         json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
        #         ^ TypeError: expected string, got dict
        # AFTER:  raw_response = call_claude_sonnet(...)
        #         response = raw_response.get('content', '')  <- extract string first
        #         json_match = re.search(..., response, ...)  <- now correct
        # ====================================================================
        raw_response = call_claude_sonnet(prompt, max_tokens=4000)

        if isinstance(raw_response, dict):
            if raw_response.get('error'):
                return {
                    'success': False,
                    'error': f"AI API error: {raw_response.get('content', 'unknown error')}"
                }
            response = raw_response.get('content', '')
        else:
            # Fallback: already a string
            response = str(raw_response)
        # ====================================================================

        # Parse JSON response (now operating on a string - correct)
        json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                return {
                    'success': False,
                    'error': 'Could not parse AI response as JSON'
                }

        analysis = json.loads(json_str)

        # Filter lessons by confidence
        high_confidence_lessons = [
            lesson for lesson in analysis.get('lessons', [])
            if lesson.get('confidence', 0) >= 0.7
        ]

        return {
            'success': True,
            'lessons': high_confidence_lessons,
            'categories': analysis.get('categories', []),
            'summary': analysis.get('conversation_summary', '')
        }

    except Exception as e:
        import traceback
        print(f"❌ Full conversation analysis error: {traceback.format_exc()}")
        return {
            'success': False,
            'error': str(e)
        }


def format_conversation_for_analysis(conversation):
    """Convert conversation array to readable text format"""

    formatted = []

    for turn in conversation:
        role = turn.get('role', 'unknown')
        message = turn.get('message', '')

        if role == 'user':
            formatted.append(f"JIM: {message}")
        elif role == 'assistant':
            formatted.append(f"AI: {message}")

    return '\n\n'.join(formatted)


def format_lessons_as_document(lessons, conversation_id, metadata):
    """
    Format extracted lessons as a proper Lessons Learned document.

    This creates a document that matches Jim's existing Lessons Learned format.
    """

    doc = f"""# Lessons Learned from Conversation
**Conversation ID:** {conversation_id}
**Date:** {datetime.now().strftime('%B %d, %Y')}
**Topic:** {metadata.get('topic', 'General')}
**Client:** {metadata.get('client', 'N/A')}
**Industry:** {metadata.get('industry', 'N/A')}

**Source:** Manual extraction from AI Swarm conversation
**Extracted By:** Conversation Learning System (User-Triggered)

---

"""

    # Group lessons by category
    by_category = {}
    for lesson in lessons:
        category = lesson.get('category', 'general')
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(lesson)

    # Format each category
    category_names = {
        'data_validation': 'Data Collection & Validation',
        'schedule_design': 'Schedule Design Decisions',
        'client_communication': 'Client Communication',
        'implementation': 'Implementation & Change Management',
        'cost_analysis': 'Cost Analysis & Financial Modeling',
        'political_dynamics': 'Political & Organizational Dynamics',
        'project_management': 'Project Management & Workflow'
    }

    for category, category_lessons in by_category.items():
        category_name = category_names.get(category, category.replace('_', ' ').title())
        doc += f"## {category_name}\n\n"

        for i, lesson in enumerate(category_lessons, 1):
            doc += f"### Lesson #{i}: {lesson['title']}\n\n"
            doc += f"**Situation/Trigger:**\n{lesson['situation']}\n\n"
            doc += f"**The Insight:**\n{lesson['insight']}\n\n"
            doc += f"**Why It Matters:**\n{lesson['why_it_matters']}\n\n"
            doc += f"**Confidence:** {int(lesson['confidence'] * 100)}%\n\n"
            doc += "---\n\n"

    doc += f"""
## Metadata
- **Extracted:** {datetime.now().isoformat()}
- **Total Lessons:** {len(lessons)}
- **Categories:** {', '.join(by_category.keys())}
- **Source Conversation:** {conversation_id}

---

*This document was automatically generated by the Conversation Learning System.*
*It captures decision heuristics and practical wisdom from real consulting conversations.*
"""

    return doc


def store_comprehensive_lessons(document_content, conversation_id, metadata, lesson_count):
    """Store comprehensive lessons document in knowledge base"""

    try:
        import sqlite3

        db_path = os.environ.get('KNOWLEDGE_DB_PATH', '/mnt/project/swarm_intelligence.db')

        document_name = f"Conversation_Lessons_{conversation_id[:8]}_{datetime.now().strftime('%Y%m%d')}"
        document_type = "lessons_learned"

        # Create metadata
        full_metadata = {
            'document_name': document_name,
            'conversation_id': conversation_id,
            'topic': metadata.get('topic', 'general'),
            'client': metadata.get('client'),
            'industry': metadata.get('industry'),
            'uploaded_by': 'conversation_learning_system',
            'upload_date': datetime.now().isoformat(),
            'source_type': 'conversation_extraction_manual',
            'lesson_count': lesson_count
        }

        # Calculate hash
        content_hash = hashlib.md5(document_content.encode()).hexdigest()

        # Store in database
        db = sqlite3.connect(db_path)
        cursor = db.cursor()

        # Check for duplicates
        cursor.execute('SELECT id FROM knowledge_extracts WHERE source_hash = ?', (content_hash,))
        if cursor.fetchone():
            db.close()
            print("ℹ️  Lessons already in knowledge base")
            return False

        # Insert
        cursor.execute('''
            INSERT INTO knowledge_extracts (
                document_type, document_name, extracted_data,
                client, industry, source_hash, metadata, extracted_at, file_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            document_type,
            document_name,
            json.dumps({'content': document_content}),
            full_metadata.get('client'),
            full_metadata.get('industry'),
            content_hash,
            json.dumps(full_metadata),
            datetime.now().isoformat(),
            len(document_content)
        ))

        # Log the ingestion
        cursor.execute('''
            INSERT INTO ingestion_log (
                document_name, document_type, status,
                patterns_extracted, insights_extracted
            ) VALUES (?, ?, ?, ?, ?)
        ''', (document_name, document_type, 'success', lesson_count, lesson_count))

        db.commit()
        db.close()

        print(f"✅ Stored comprehensive lessons: {document_name}")
        return True

    except Exception as e:
        import traceback
        print(f"❌ Failed to store comprehensive lessons: {traceback.format_exc()}")
        return False


@learning_bp.route('/learning-stats', methods=['GET'])
def get_learning_stats():
    """Get statistics about all conversation-based learning (automatic + manual)"""

    try:
        import sqlite3

        db_path = os.environ.get('KNOWLEDGE_DB_PATH', '/mnt/project/swarm_intelligence.db')
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        # Count automatic insights
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM knowledge_extracts
            WHERE metadata LIKE '%conversation_automatic%'
        ''')
        automatic_count = cursor.fetchone()['count']

        # Count manual lessons
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM knowledge_extracts
            WHERE metadata LIKE '%conversation_extraction_manual%'
        ''')
        manual_count = cursor.fetchone()['count']

        # Get recent learning (both types)
        cursor.execute('''
            SELECT document_name, document_type, extracted_at, metadata
            FROM knowledge_extracts
            WHERE metadata LIKE '%conversation%'
            ORDER BY extracted_at DESC
            LIMIT 10
        ''')

        recent_learning = [dict(row) for row in cursor.fetchall()]
        db.close()

        return jsonify({
            'success': True,
            'total_lessons': automatic_count + manual_count,
            'automatic_insights': automatic_count,
            'manual_lessons': manual_count,
            'recent_learning': recent_learning,
            'message': f'Learning from {automatic_count} automatic insights + {manual_count} manual extractions'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# I did no harm and this file is not truncated
