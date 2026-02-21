"""
Task Analysis Module - WITH UNIFIED KNOWLEDGE BASE (Project Files + Knowledge Management)
Created: January 21, 2026
Last Updated: February 20, 2026 - WIRED RESEARCH AGENT + SPECIALIST ROUTING RULES

CHANGELOG:

- February 20, 2026: WIRED RESEARCH AGENT INTO SPECIALIST DISPATCH + ROUTING RULES
  PROBLEM 1: research_agent.py (Tavily) was fully built and registered as its own
    route, but it was NEVER dispatched by Sonnet during normal conversations.
    execute_specialist_task() had no entry for "research_agent" in its specialist_map,
    so even if Sonnet tried to assign it, the call would silently fail with
    "ERROR: Unknown specialist".
  FIX 1: Added call_research_agent() wrapper function that calls
    ResearchAgent.research_topic() and normalizes its output dict to the standard
    {'content', 'usage', 'error'} format expected by execute_specialist_task().
    Added "research_agent": call_research_agent to specialist_map.

  PROBLEM 2: Sonnet had no explicit rules about WHEN to use which specialist.
    Its routing prompt listed "gpt4, deepseek, gemini" as options but gave no
    guidance about when each was appropriate - or that research_agent existed at all.
    Result: Sonnet returned specialists_needed=[] on nearly every request.
  FIX 2: Added SPECIALIST ROUTING RULES section to analyze_task_with_sonnet()
    prompt. Sonnet now receives explicit rules:
      - research_agent: current events, news, regulations, studies, anything
                        requiring real-time web data beyond training cutoff
      - gpt4:          document formatting, report writing, structured output
      - deepseek:      code, calculations, data processing, technical analysis
      - gemini:        multimodal tasks involving images or visual content
      - opus:          complex multi-step strategy, high-stakes recommendations
    Same rules added to handle_with_opus() for consistency.

  PROBLEM 3: Sonnet's JSON response schema hint listed only the old specialists.
    Updated the schema comment to include "research_agent" as a valid value.

  NO other logic changed. All existing specialist calls are identical.
  Backward compatible - existing calls unaffected.

- February 20, 2026: FIXED KNOWLEDGE DB PATH IN search_knowledge_management_db()
  BUG: The function defaulted to 'swarm_intelligence.db' (local/ephemeral path).
       config.py sets DATABASE = '/mnt/project/swarm_intelligence.db' (persistent disk).
       Result: Knowledge search silently returned empty results - all 42+ uploaded
       documents were invisible to the AI swarm. The "unified knowledge" system
       was effectively reading from the wrong (or nonexistent) local DB.
  FIX: Import DATABASE from config and use it as the default fallback path.
       The KNOWLEDGE_DB_PATH env var still overrides if explicitly set.
       One-line change: os.environ.get('KNOWLEDGE_DB_PATH', 'swarm_intelligence.db')
                     -> os.environ.get('KNOWLEDGE_DB_PATH', DATABASE)
  NO other logic changed. No function signatures changed. Fully backward compatible.

- February 3, 2026: UNIFIED KNOWLEDGE BASE INTEGRATION
  * Now searches BOTH project_files (35 docs) AND Knowledge Management DB (42 docs)
  * Total of 77+ documents available to every conversation
  * AI acts as senior partner with access to ALL accumulated wisdom
  * Proactive insights: "Based on Acme project..." "Your Lessons Learned says..."
  * Cumulative intelligence - gets smarter with every uploaded document

- January 30, 2026: CRITICAL FIX - FILE CONTENTS IN USER REQUEST
  * Moved file contents from system context INTO the user request
  * AI can no longer give reflexive "I don't see files" responses

- January 30, 2026: CRITICAL FIX - FILE CONTENTS NOW VISIBLE TO AI
  * Added file_contents parameter to analyze_task_with_sonnet()
  * AI now receives ACTUAL FILE CONTENTS in the prompt

- January 29, 2026: FILE ATTACHMENT AWARENESS FIX
  * AI now receives explicit information about attached files
  * When files are uploaded, AI is told: filenames, paths, and file count

Author: Jim @ Shiftwork Solutions LLC
"""

import json
import time
import os
from orchestration.ai_clients import call_claude_sonnet, call_claude_opus
from database import get_db
from config import DATABASE


# ============================================================================
# RESEARCH AGENT WRAPPER
# Added February 20, 2026
#
# ResearchAgent.research_topic() returns:
#   {'success', 'query', 'summary', 'results', 'result_count', 'topic', ...}
#
# execute_specialist_task() expects the callable to return:
#   {'content', 'usage', 'error'}
#
# This wrapper normalizes the ResearchAgent output into that standard format
# so it drops cleanly into the existing specialist_map without touching any
# other part of execute_specialist_task().
# ============================================================================

def call_research_agent(prompt, max_tokens=4000):
    """
    Wrapper that calls ResearchAgent.research_topic() and normalizes the
    result to the standard {'content', 'usage', 'error'} format.

    The 'prompt' received here is the task_description from execute_specialist_task(),
    which is the user's original request or the specialist sub-task assigned by Sonnet/Opus.

    Returns dict with 'content', 'usage', 'error' (matching ai_clients.py format).
    """
    try:
        from research_agent import get_research_agent
        agent = get_research_agent()

        if not agent.is_available:
            return {
                'content': "ERROR: Research Agent unavailable - TAVILY_API_KEY not configured",
                'usage': {'input_tokens': 0, 'output_tokens': 0},
                'error': True
            }

        result = agent.research_topic(topic=prompt, context="AI Swarm specialist task")

        if not result.get('success'):
            return {
                'content': f"ERROR: Research Agent search failed: {result.get('error', 'Unknown error')}",
                'usage': {'input_tokens': 0, 'output_tokens': 0},
                'error': True
            }

        # Build a readable content string from the research results
        parts = []

        if result.get('summary'):
            parts.append(f"**Research Summary:**\n{result['summary']}\n")

        results_list = result.get('results', [])
        if results_list:
            parts.append(f"**Sources Found ({len(results_list)}):**\n")
            for idx, r in enumerate(results_list, 1):
                title = r.get('title', 'Untitled')
                url = r.get('url', '')
                content_snippet = r.get('content', '')[:300]
                pub_date = r.get('published_date', '')
                date_str = f" ({pub_date})" if pub_date else ""
                parts.append(
                    f"{idx}. **{title}**{date_str}\n"
                    f"   URL: {url}\n"
                    f"   {content_snippet}...\n"
                )

        content = "\n".join(parts) if parts else "No research results found."

        return {
            'content': content,
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': False
        }

    except ImportError:
        return {
            'content': "ERROR: research_agent module not found",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }
    except Exception as e:
        return {
            'content': f"ERROR: Research Agent call failed: {str(e)}",
            'usage': {'input_tokens': 0, 'output_tokens': 0},
            'error': True
        }


# ============================================================================
# SPECIALIST ROUTING RULES
# Added February 20, 2026
#
# Single source of truth for routing rules, injected into both
# analyze_task_with_sonnet() and handle_with_opus() so both orchestrators
# know exactly when to use each specialist.
# ============================================================================

SPECIALIST_ROUTING_RULES = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SPECIALIST ROUTING RULES - READ CAREFULLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You have access to these specialist AIs. Use them when the task genuinely
benefits from their capability. Do NOT default to an empty list.

SPECIALIST: research_agent (Tavily web search)
  USE WHEN:
  - User asks about current events, news, recent developments
  - User asks about regulations, labor laws, OSHA updates (time-sensitive)
  - User asks about research studies, published findings on shift work/fatigue
  - User asks "what's happening in the industry" or competitor questions
  - Any question where your training knowledge may be outdated
  - User asks to "look up", "find", "research", or "search" something
  EXAMPLES: "Any new OSHA fatigue regulations?", "What are the latest studies on
    12-hour shifts?", "What are competitors doing?", "Look up..."

SPECIALIST: gpt4 (OpenAI GPT-4 - document and report specialist)
  USE WHEN:
  - User asks for a formatted report, executive summary, or professional document
  - Task requires creating structured multi-section written output
  - User asks to "format", "write up", "draft", or "create a report"
  - Complex document assembly from multiple inputs
  EXAMPLES: "Write an executive summary of...", "Format this into a report",
    "Draft a proposal for..."
  NOTE: File analysis already goes to GPT-4 via Handler 9 - no need to assign
    gpt4 here for tasks that involve uploaded files

SPECIALIST: deepseek (DeepSeek - code and data specialist)
  USE WHEN:
  - User asks for data calculations, statistical analysis, or number crunching
  - User asks to write, fix, or review code
  - Task involves processing structured data (CSV, Excel formulas, SQL)
  - Complex technical analysis requiring computational precision
  EXAMPLES: "Calculate the cost savings from...", "Write a Python script to...",
    "Analyze this data set..."

SPECIALIST: gemini (Google Gemini - multimodal specialist)
  USE WHEN:
  - Task involves analyzing images or visual content
  - User uploads an image and asks questions about it
  - Task requires understanding charts, diagrams, or visual schedules
  EXAMPLES: "What does this chart show?", "Analyze this image of our schedule board"

ESCALATE TO OPUS (escalate_to_opus: true) WHEN:
  - Request requires deep multi-step strategic planning
  - High-stakes recommendation affecting many employees or large budget
  - Complex change management planning across multiple phases
  - Request involves significant organizational or political risk
  - Task type is "complex" AND confidence is below 0.6
  EXAMPLES: "Design a complete 5-year implementation roadmap",
    "How do we manage union resistance to a full schedule overhaul?"

FOR MOST STANDARD QUESTIONS: specialists_needed = [] and escalate_to_opus = false
  Simple Q&A, explanations, typical schedule advice → handle with Sonnet directly.
  Only assign specialists when they add genuine value.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def get_learning_context():
    """Retrieve learning patterns to inform orchestration decisions."""
    try:
        db = get_db()

        table_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='learning_records'"
        ).fetchone()

        if not table_check:
            db.close()
            return ""

        patterns = db.execute('''
            SELECT pattern_type, success_rate, times_applied, pattern_data
            FROM learning_records
            WHERE times_applied >= 2
            ORDER BY success_rate DESC
            LIMIT 10
        ''').fetchall()

        db.close()

        if not patterns:
            return ""

        context = "\n\n=== LEARNING FROM PAST TASKS ===\n"
        context += "Your system has learned these patterns:\n\n"

        for p in patterns:
            pattern_data = json.loads(p['pattern_data'])
            context += f"- {p['pattern_type']}: {p['success_rate']*100:.0f}% success rate ({p['times_applied']} times)\n"
            if 'improvement_areas' in pattern_data and pattern_data['improvement_areas']:
                context += f"  Common issues: {', '.join(pattern_data['improvement_areas'])}\n"
            if 'knowledge_usage' in pattern_data:
                context += f"  Knowledge usage: {pattern_data['knowledge_usage']}\n"

        return context
    except Exception as e:
        print(f"⚠️ Learning context unavailable: {e}")
        return ""


def search_knowledge_management_db(user_request, max_results=5):
    """
    Search the Knowledge Management database (uploaded documents).
    Returns extracted knowledge from the 42+ documents in swarm_intelligence.db

    This is the "Shoulders of Giants" cumulative learning system.
    """
    try:
        import sqlite3

        # ================================================================
        # FIX (February 20, 2026): Use config.DATABASE as the default path
        # BEFORE: os.environ.get('KNOWLEDGE_DB_PATH', 'swarm_intelligence.db')
        #   -> defaults to ephemeral local file, not the persistent disk DB
        # AFTER:  os.environ.get('KNOWLEDGE_DB_PATH', DATABASE)
        #   -> DATABASE = '/mnt/project/swarm_intelligence.db' from config.py
        #   -> KNOWLEDGE_DB_PATH env var still overrides if explicitly set
        # ================================================================
        db_path = os.environ.get('KNOWLEDGE_DB_PATH', DATABASE)
        # ================================================================

        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_extracts'")
        if not cursor.fetchone():
            db.close()
            return []

        # Simple keyword search across all documents
        search_terms = user_request.lower().split()[:10]  # Use first 10 words

        results = []
        for term in search_terms:
            if len(term) < 3:  # Skip very short words
                continue

            cursor.execute('''
                SELECT
                    id, document_name, document_type, client, industry,
                    extracted_data, extracted_at
                FROM knowledge_extracts
                WHERE LOWER(extracted_data) LIKE ?
                   OR LOWER(document_name) LIKE ?
                   OR LOWER(client) LIKE ?
                LIMIT ?
            ''', (f'%{term}%', f'%{term}%', f'%{term}%', max_results))

            results.extend([dict(row) for row in cursor.fetchall()])

        db.close()

        # Deduplicate by id
        seen = set()
        unique_results = []
        for r in results:
            if r['id'] not in seen:
                seen.add(r['id'])
                unique_results.append(r)

        return unique_results[:max_results]

    except Exception as e:
        print(f"⚠️ Knowledge Management DB search error: {e}")
        return []


def check_knowledge_base_unified(user_request, project_knowledge_base):
    """
    UNIFIED knowledge search across BOTH sources:
    1. Project files knowledge base (35 documents)
    2. Knowledge Management DB (42+ uploaded documents)

    This gives the AI access to ALL accumulated wisdom - 77+ documents total.
    """
    all_sources = []
    all_context = []
    max_confidence = 0.0

    # ============================================================
    # SOURCE 1: Project Files Knowledge Base (35 documents)
    # ============================================================
    if project_knowledge_base:
        try:
            print("🔍 Searching project files knowledge base...")

            if hasattr(project_knowledge_base, 'semantic_search'):
                search_results = project_knowledge_base.semantic_search(user_request, max_results=3)
            else:
                search_results = project_knowledge_base.search(user_request, max_results=3)

            if search_results:
                top_score = search_results[0].get('score', 0)

                if top_score >= 50:
                    confidence = 0.9
                elif top_score >= 25:
                    confidence = 0.75
                elif top_score >= 10:
                    confidence = 0.6
                else:
                    confidence = 0.4

                max_confidence = max(max_confidence, confidence)

                kb_context = project_knowledge_base.get_context_for_task(
                    user_request,
                    max_context=3000,
                    max_results=3
                )

                if kb_context:
                    all_context.append("=== PROJECT FILES KNOWLEDGE ===")
                    all_context.append(kb_context)

                all_sources.extend([r['filename'] for r in search_results[:3]])

                print(f"  ✅ Found {len(search_results)} relevant project files")
                print(f"  📊 Confidence: {confidence*100:.0f}%")

        except Exception as e:
            print(f"⚠️ Project knowledge search error: {e}")

    # ============================================================
    # SOURCE 2: Knowledge Management Database (42+ documents)
    # ============================================================
    print("🔍 Searching uploaded documents (Knowledge Management DB)...")
    km_results = search_knowledge_management_db(user_request, max_results=3)

    if km_results:
        # Build context from Knowledge Management results
        km_context_parts = ["=== UPLOADED DOCUMENTS (Knowledge Management) ==="]

        for idx, doc in enumerate(km_results, 1):
            doc_name = doc['document_name']
            doc_type = doc['document_type']
            client = doc['client'] or 'Unknown'

            # Parse extracted_data JSON
            try:
                extracted = json.loads(doc['extracted_data'])
                insights = extracted.get('insights', [])
                patterns = extracted.get('patterns', [])

                km_context_parts.append(f"\n📄 Document {idx}: {doc_name}")
                km_context_parts.append(f"   Type: {doc_type} | Client: {client}")

                # Add insights
                if insights:
                    km_context_parts.append(f"   Insights: {len(insights)} found")
                    for insight in insights[:2]:  # Top 2 insights
                        if isinstance(insight, dict):
                            insight_type = insight.get('type', 'general')
                            km_context_parts.append(f"     - {insight_type}")

                # Add patterns
                if patterns:
                    km_context_parts.append(f"   Patterns: {len(patterns)} found")
                    for pattern in patterns[:2]:  # Top 2 patterns
                        if isinstance(pattern, dict):
                            pattern_name = pattern.get('name', 'unknown')
                            km_context_parts.append(f"     - {pattern_name}")

            except Exception:
                km_context_parts.append(f"\n📄 Document {idx}: {doc_name} (Type: {doc_type})")

        km_context = '\n'.join(km_context_parts)
        all_context.append(km_context)
        all_sources.extend([doc['document_name'] for doc in km_results])

        # Estimate confidence based on number of results
        km_confidence = min(0.8, len(km_results) * 0.25)
        max_confidence = max(max_confidence, km_confidence)

        print(f"  ✅ Found {len(km_results)} relevant uploaded documents")
        print(f"  📊 Confidence: {km_confidence*100:.0f}%")

    # ============================================================
    # COMBINE RESULTS
    # ============================================================
    if not all_sources:
        return {
            'has_relevant_knowledge': False,
            'knowledge_context': '',
            'knowledge_confidence': 0.0,
            'knowledge_sources': [],
            'should_proceed_to_ai': True,
            'reason': 'No relevant knowledge found in either source'
        }

    combined_context = '\n\n'.join(all_context)

    print(f"📚 UNIFIED KNOWLEDGE: {len(all_sources)} documents from {len(all_context)} sources")
    print(f"   Overall Confidence: {max_confidence*100:.0f}%")

    return {
        'has_relevant_knowledge': True,
        'knowledge_context': combined_context,
        'knowledge_confidence': max_confidence,
        'knowledge_sources': list(set(all_sources)),  # Deduplicate
        'should_proceed_to_ai': True,
        'reason': f'Found {len(all_sources)} relevant documents across both knowledge bases',
        'source_breakdown': {
            'project_files': len([s for s in all_sources if 'project_files' in str(s)]),
            'uploaded_docs': len(km_results)
        }
    }


def analyze_task_with_sonnet(user_request, knowledge_base=None, file_paths=None, file_contents=None):
    """
    Sonnet analyzes task WITH unified knowledge + system capabilities + FILE ATTACHMENTS.

    NOW SEARCHES BOTH:
    - Project files knowledge base (35 documents)
    - Knowledge Management DB (42+ uploaded documents)

    Total: 77+ documents available for every request!

    UPDATED February 20, 2026:
    - Added SPECIALIST_ROUTING_RULES to prompt so Sonnet knows WHEN to use each AI
    - Added "research_agent" as a valid specialist in the JSON schema hint

    Args:
        user_request (str): The user's request
        knowledge_base: Project knowledge base instance (optional)
        file_paths (list): List of file paths that were uploaded (optional)
        file_contents (str): Extracted contents from uploaded files (optional)

    Returns:
        dict: Analysis results with task routing decisions
    """

    # 🔧 CRITICAL: Import and inject system capabilities
    from orchestration.system_capabilities import get_system_capabilities_prompt
    capabilities = get_system_capabilities_prompt()

    # 🎯 Unified knowledge search across BOTH sources
    kb_check = check_knowledge_base_unified(user_request, knowledge_base)
    learning_context = get_learning_context()

    # Build prompt with CAPABILITIES FIRST (so AI knows what it can do)
    # UPDATED February 20, 2026: Added SPECIALIST_ROUTING_RULES block
    analysis_prompt = f"""{capabilities}

You are the primary orchestrator in an AI swarm system for Shiftwork Solutions LLC.

🎯 CRITICAL: You have access to extensive accumulated knowledge from:
   - Project files (implementation manuals, contracts, proposals)
   - Uploaded documents (lessons learned, assessments, client work)
   - Total: 77+ documents spanning hundreds of projects

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 STRICT GROUNDING RULES - MANDATORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are a SENIOR CONSULTING PARTNER, not a marketing brochure. Follow these rules:

1. ONLY cite what's ACTUALLY in the documents provided above
   - Never invent numbers, percentages, or statistics
   - Never fabricate client names or project details
   - If you don't have specific data, say "I'd need to review the project files" or "In my experience..."

2. ADMIT UNCERTAINTY like a real consultant
   - "I don't see specific data on that in the files"
   - "That would depend on the specific operational context"
   - "I'd want to analyze your situation before recommending"

3. AVOID VAGUE BUZZWORDS
   - Don't say "overlapping crew structures" - be specific or don't mention it
   - Don't say "strategic optimization" - explain what you actually mean
   - Concrete examples only

4. GIVE HONEST ADVICE, not sales pitches
   - This is internal consulting, not marketing
   - If something is situational, say so
   - If approaches have tradeoffs, acknowledge them
   - Never oversell with ungrounded claims

5. SPEAK LIKE A PARTNER
   - "In my experience across hundreds of projects..."
   - "I've seen this work when..."
   - "The challenge you'll face is..."
   - "Let me look at what we learned from similar situations..."

6. ASK CLARIFYING QUESTIONS when needed
   - Don't make assumptions
   - Get context before recommending

VIOLATION OF THESE RULES = LOSS OF CREDIBILITY

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{SPECIALIST_ROUTING_RULES}

{learning_context}

{kb_check['knowledge_context']}

"""

    # File contents handling
    file_section = ""
    if file_contents:
        file_section = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📎 ATTACHED FILES - CONTENT BELOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{file_contents}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    elif file_paths and len(file_paths) > 0:
        analysis_prompt += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📎 FILES ATTACHED TO THIS REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ CRITICAL: The user has attached {len(file_paths)} file(s) to this request.
You MUST work with these files. They are available and accessible.

ATTACHED FILES:
"""
        for idx, fp in enumerate(file_paths, 1):
            filename = os.path.basename(fp)
            file_ext = os.path.splitext(filename)[1].lower()
            try:
                file_size = os.path.getsize(fp)
                size_mb = file_size / (1024 * 1024)
                analysis_prompt += f"{idx}. {filename} ({size_mb:.2f} MB) - Type: {file_ext}\n"
                analysis_prompt += f"   Path: {fp}\n"
            except Exception:
                analysis_prompt += f"{idx}. {filename} - Type: {file_ext}\n"
                analysis_prompt += f"   Path: {fp}\n"

        analysis_prompt += f"""
INSTRUCTIONS FOR HANDLING ATTACHED FILES:
- These files are REAL and ACCESSIBLE - you can work with them
- The user expects you to analyze, process, or reference these files
- Use your file analysis capabilities to extract content
- If the user's request is vague, analyze the files and provide insights
- Never say "I cannot access files" - you have these files available

"""

    # Add user request WITH file contents
    analysis_prompt += f"""USER REQUEST: {user_request}{file_section}

"""

    if kb_check['has_relevant_knowledge']:
        analysis_prompt += f"""
KNOWLEDGE BASE STATUS:
✅ Relevant knowledge found (Confidence: {kb_check['knowledge_confidence']*100:.0f}%)
📚 Sources ({len(kb_check['knowledge_sources'])}): {', '.join(kb_check['knowledge_sources'][:3])}
"""
        if kb_check.get('source_breakdown'):
            breakdown = kb_check['source_breakdown']
            analysis_prompt += f"   - Project files: {breakdown.get('project_files', 0)}\n"
            analysis_prompt += f"   - Uploaded docs: {breakdown.get('uploaded_docs', 0)}\n"

        analysis_prompt += "\nACT AS A SENIOR PARTNER: Reference this knowledge proactively when relevant.\n"
    else:
        analysis_prompt += f"""
KNOWLEDGE BASE STATUS:
ℹ️  No directly relevant knowledge found
"""

    # UPDATED February 20, 2026: Added "research_agent" to valid specialists list
    analysis_prompt += """
Analyze this request and determine:
1. Task type (strategy, schedule_design, implementation, survey, content, code, analysis, complex)
2. Your confidence (0.0-1.0)
3. Required specialists - valid values: "research_agent", "gpt4", "deepseek", "gemini", or []
   Use the SPECIALIST ROUTING RULES above to decide. Be specific - don't default to empty.
4. Escalate to Opus? (true/false) - use the escalation rules above
5. Reasoning

Respond ONLY with valid JSON:
{
    "task_type": "string",
    "confidence": 0.0-1.0,
    "specialists_needed": ["research_agent"|"gpt4"|"deepseek"|"gemini", ...],
    "escalate_to_opus": boolean,
    "reasoning": "string",
    "knowledge_applied": boolean
}"""

    start_time = time.time()
    api_response = call_claude_sonnet(analysis_prompt)
    execution_time = time.time() - start_time

    # Extract content from dict response
    if isinstance(api_response, dict):
        if api_response.get('error'):
            return {
                "task_type": "error",
                "confidence": 0.0,
                "specialists_needed": [],
                "escalate_to_opus": False,
                "reasoning": f"API error: {api_response.get('content')}",
                "execution_time": execution_time,
                "knowledge_applied": kb_check['has_relevant_knowledge'],
                "knowledge_sources": kb_check['knowledge_sources'],
                "files_attached": len(file_paths) if file_paths else 0
            }
        response_text = api_response.get('content', '')
    else:
        response_text = str(api_response)

    try:
        # Clean JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        analysis = json.loads(response_text)
        analysis['execution_time'] = execution_time
        analysis['knowledge_applied'] = kb_check['has_relevant_knowledge']
        analysis['knowledge_sources'] = kb_check['knowledge_sources']
        analysis['knowledge_confidence'] = kb_check['knowledge_confidence']
        analysis['files_attached'] = len(file_paths) if file_paths else 0

        # Boost confidence if strong knowledge match
        if kb_check['knowledge_confidence'] > 0.7:
            original = analysis.get('confidence', 0.5)
            analysis['confidence'] = min(0.95, original + 0.2)

        return analysis

    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parse error: {e}")
        return {
            "task_type": "complex",
            "confidence": 0.5,
            "specialists_needed": [],
            "escalate_to_opus": True,
            "reasoning": "Parse error - escalating",
            "execution_time": execution_time,
            "knowledge_applied": kb_check['has_relevant_knowledge'],
            "knowledge_sources": kb_check['knowledge_sources'],
            "files_attached": len(file_paths) if file_paths else 0
        }


def handle_with_opus(user_request, sonnet_analysis, knowledge_base=None, file_paths=None, file_contents=None):
    """
    Opus handles complex requests WITH unified knowledge + system capabilities + FILES.

    NOW SEARCHES BOTH knowledge sources for complete context.

    UPDATED February 20, 2026: Added SPECIALIST_ROUTING_RULES to Opus prompt
    for consistency with Sonnet routing logic.

    Args:
        user_request (str): The user's request
        sonnet_analysis (dict): Sonnet's analysis results
        knowledge_base: Knowledge base instance (optional)
        file_paths (list): List of file paths that were uploaded (optional)
        file_contents (str): Extracted contents from uploaded files (optional)
    """

    # 🔧 CRITICAL: Import and inject system capabilities
    from orchestration.system_capabilities import get_system_capabilities_prompt
    capabilities = get_system_capabilities_prompt()

    # 🎯 Unified knowledge search
    kb_check = check_knowledge_base_unified(user_request, knowledge_base)
    learning_context = get_learning_context()

    # Build prompt with CAPABILITIES FIRST
    # UPDATED February 20, 2026: Added SPECIALIST_ROUTING_RULES block
    opus_prompt = f"""{capabilities}

You are the strategic supervisor in the AI Swarm for Shiftwork Solutions LLC.

🎯 You have access to 77+ documents of accumulated expertise. Act as a senior consulting partner.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 GROUNDING RULES - SENIOR PARTNER STANDARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ONLY cite actual document contents. Never fabricate:
- Numbers, percentages, or statistics
- Client names or project details
- Recommendations not grounded in provided knowledge

Admit uncertainty: "I'd need to review specific files" or "That depends on context"
Avoid buzzwords: Be specific or don't mention it
Give honest advice: This is internal consulting, not marketing
Acknowledge tradeoffs: Real consulting means honest tradeoffs
Ask questions: Don't assume - clarify before recommending

SPEAK LIKE AN EXPERIENCED PARTNER, NOT A SALES BROCHURE.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{SPECIALIST_ROUTING_RULES}

{learning_context}

{kb_check['knowledge_context']}

"""

    # File handling
    file_section = ""
    if file_contents:
        file_section = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📎 ATTACHED FILES - CONTENT BELOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{file_contents}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    elif file_paths and len(file_paths) > 0:
        opus_prompt += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📎 FILES ATTACHED TO THIS REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The user has attached {len(file_paths)} file(s). These files are available and accessible.

ATTACHED FILES:
"""
        for idx, fp in enumerate(file_paths, 1):
            filename = os.path.basename(fp)
            opus_prompt += f"{idx}. {filename} (Path: {fp})\n"

        opus_prompt += "\n"

    if kb_check['has_relevant_knowledge']:
        opus_prompt += f"""
KNOWLEDGE: {len(kb_check['knowledge_sources'])} relevant documents (Confidence: {kb_check['knowledge_confidence']*100:.0f}%)
Sources: {', '.join(kb_check['knowledge_sources'][:3])}
"""

    opus_prompt += f"""
Sonnet escalated this request to you.

USER REQUEST: {user_request}{file_section}

SONNET'S ANALYSIS:
{json.dumps(sonnet_analysis, indent=2)}

Provide strategic response with:
1. Deep analysis (reference specific projects/documents when relevant)
2. Specialist assignments - valid values: "research_agent", "gpt4", "deepseek", "gemini"
   Use the SPECIALIST ROUTING RULES above when assigning specialists.
3. Expected workflow
4. Learning for Sonnet
5. Methodology applied

Respond in JSON:
{{
    "strategic_analysis": "string",
    "specialist_assignments": [{{"ai": "research_agent"|"gpt4"|"deepseek"|"gemini", "task": "description", "reason": "why"}}],
    "workflow": ["step1", "step2"],
    "learning_for_sonnet": "pattern to learn",
    "methodology_applied": "principles used"
}}"""

    start_time = time.time()
    api_response = call_claude_opus(opus_prompt)
    execution_time = time.time() - start_time

    # Extract content
    if isinstance(api_response, dict):
        if api_response.get('error'):
            return {
                "strategic_analysis": f"API error: {api_response.get('content')}",
                "specialist_assignments": [],
                "workflow": ["Manual handling required"],
                "execution_time": execution_time,
                "knowledge_applied": kb_check['has_relevant_knowledge'],
                "files_attached": len(file_paths) if file_paths else 0
            }
        response_text = api_response.get('content', '')
    else:
        response_text = str(api_response)

    try:
        # Clean JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        opus_plan = json.loads(response_text)
        opus_plan['execution_time'] = execution_time
        opus_plan['knowledge_applied'] = kb_check['has_relevant_knowledge']
        opus_plan['knowledge_sources'] = kb_check['knowledge_sources']
        opus_plan['files_attached'] = len(file_paths) if file_paths else 0

        return opus_plan

    except json.JSONDecodeError:
        return {
            "strategic_analysis": response_text,
            "specialist_assignments": [],
            "workflow": ["Manual handling"],
            "execution_time": execution_time,
            "knowledge_applied": kb_check['has_relevant_knowledge'],
            "files_attached": len(file_paths) if file_paths else 0
        }


def execute_specialist_task(specialist_ai, task_description, knowledge_context="", file_paths=None, file_contents=None):
    """
    Execute task with specialist AI.

    UPDATED February 20, 2026: Added "research_agent" to specialist_map.
    The call_research_agent() wrapper normalizes ResearchAgent output to the
    standard {'content', 'usage', 'error'} format so it integrates cleanly.

    Args:
        specialist_ai (str): Name of the specialist AI to use
                             Valid: "research_agent", "gpt4", "deepseek",
                                   "gemini", "sonnet", "opus"
        task_description (str): Description of the task
        knowledge_context (str): Optional knowledge context
        file_paths (list): Optional list of attached file paths
        file_contents (str): Optional extracted file contents
    """
    from orchestration.ai_clients import call_gpt4, call_deepseek, call_gemini

    # 🔧 CRITICAL: Inject capabilities for specialists too
    from orchestration.system_capabilities import get_system_capabilities_prompt
    capabilities = get_system_capabilities_prompt()

    # ================================================================
    # UPDATED February 20, 2026: Added research_agent to specialist_map
    # ================================================================
    specialist_map = {
        "research_agent": call_research_agent,   # NEW - Tavily web search
        "gpt4": call_gpt4,
        "deepseek": call_deepseek,
        "gemini": call_gemini,
        "sonnet": call_claude_sonnet,
        "opus": call_claude_opus
    }
    # ================================================================

    ai_function = specialist_map.get(specialist_ai.lower())
    if not ai_function:
        return {
            "specialist": specialist_ai,
            "output": f"ERROR: Unknown specialist '{specialist_ai}'. "
                      f"Valid options: {', '.join(specialist_map.keys())}",
            "execution_time": 0,
            "success": False
        }

    # Build prompt with capabilities
    # research_agent gets the raw task_description since call_research_agent()
    # uses it as the topic for ResearchAgent.research_topic()
    if specialist_ai.lower() == "research_agent":
        full_prompt = task_description
    else:
        full_prompt = f"{capabilities}\n\n"

        if knowledge_context:
            full_prompt += f"{knowledge_context}\n\n"

        # Build file section for task description
        file_section = ""
        if file_contents:
            file_section = f"\n\n📎 ATTACHED FILES:\n{file_contents}\n\n"
        elif file_paths and len(file_paths) > 0:
            file_section = f"\n\n📎 ATTACHED FILES ({len(file_paths)}):\n"
            for fp in file_paths:
                file_section += f"- {os.path.basename(fp)} (Path: {fp})\n"
            file_section += "\n"

        full_prompt += f"TASK: {task_description}{file_section}"

    start_time = time.time()
    api_response = ai_function(full_prompt)
    execution_time = time.time() - start_time

    # Extract content
    if isinstance(api_response, dict):
        output_text = api_response.get('content', '')
        has_error = api_response.get('error', False)
    else:
        output_text = str(api_response)
        has_error = output_text.startswith("ERROR")

    return {
        "specialist": specialist_ai,
        "output": output_text,
        "execution_time": execution_time,
        "success": not has_error,
        "had_knowledge_context": bool(knowledge_context),
        "files_available": len(file_paths) if file_paths else 0
    }


# I did no harm and this file is not truncated
