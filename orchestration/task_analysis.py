"""
Task Analysis Module - WITH UNIFIED KNOWLEDGE BASE (Project Files + Knowledge Management)
Created: January 21, 2026
Last Updated: February 28, 2026 - IMPROVED CONSULTING INSIGHT CONTENT EXTRACTION

CHANGELOG:

- February 28, 2026 (Pass 2): IMPROVED CONSULTING INSIGHT CONTENT EXTRACTION
  PROBLEM: extract_content_from_extract() was only reading the first 6 patterns
    per document ([:6]) and only the first line of body_content for consulting_insight
    patterns. This caused up to 75% of substantive content to be silently dropped.
    Examples:
      - WP3 (Overtime Strategy) has 24 consulting_insight patterns; only 6 were read,
        missing "The Hidden Complexity of Change", "Best Practice #15 (20/60/20 Rule)",
        "Best Practice #16", and 16 other sections.
      - Pillar_1 (Complete Guide to Schedule Design) had similar truncation.
    Additionally, "cover page" noise patterns (contact info, copyright lines) were
    consuming slots in the 6-pattern budget before substantive content appeared.
    Duplicate section headings were also appearing in output.

  FIX: Modified extract_content_from_extract() consulting_insight branch only:
    1. Increased pattern limit from [:6] to [:15] - reads 2.5x more patterns
    2. Added _is_noise_section() helper - skips cover-page/header patterns that
       contain contact info, copyright lines, or other non-consulting content
    3. Added _get_body_text() helper - joins ALL body_content lines (up to 4 lines,
       500 chars) instead of only showing body[0]
    4. Added seen_sections set within the function - deduplicates identical section
       headings so same content doesn't appear twice
    5. Skips patterns with fewer than 20 chars of content
    6. Includes up to 2 key_principles instead of only the first one
  ALL OTHER FUNCTIONS UNCHANGED. All other pattern type branches UNCHANGED.
  Database: read-only, no schema changes.

- February 28, 2026 (Pass 1): FIXED KM DB CONTENT EXTRACTION
  PROBLEM 1: search_knowledge_management_db() was connecting to the wrong DB.
    config.py DATABASE = '/mnt/project/swarm_intelligence.db' but the knowledge
    database is '/mnt/project/knowledge_ingestion.db'. The February 20 fix used
    DATABASE as the fallback, which pointed to the wrong file. The KNOWLEDGE_DB_PATH
    env var ('/mnt/project/knowledge_ingestion.db') overrides correctly when set,
    but the fallback was silently wrong.
  FIX 1: Added explicit KNOWLEDGE_DB_PATH constant at module level that reads
    the env var with a correct hardcoded fallback to 'knowledge_ingestion.db'
    (not swarm_intelligence.db). Added startup diagnostic print so Render logs
    always show which DB file is being used.

  PROBLEM 2: check_knowledge_base_unified() built useless metadata summaries
    from the Knowledge Management DB instead of extracting actual content.
    It told the AI "3 insights found" and "type: consulting_lesson" — the AI
    could see documents existed but could not read any of their content.
    Result: 218 uploaded documents were effectively invisible to the AI.
  FIX 2: Added extract_content_from_extract() function that reads extracted_data
    JSON from each knowledge record and pulls:
      - consulting_lesson: lesson_name, key_principle, situation, why_matters,
                           hard_truth, key_bullets
      - consulting_insight: section heading, body_preview, body_content,
                            key_principles
      - survey_norm / survey_client_result: question + top answer distribution
      - operational_metrics: metric values
      - contract_terms / engagement_fee: fee, duration
      - lessons_learned_summary: lesson count and categories
      - highlights: top 3 highlight strings
    check_knowledge_base_unified() now calls extract_content_from_extract()
    and injects real readable excerpts into the AI prompt, matching the quality
    of the project files path.

- February 21, 2026: ADDED TIME-SENSITIVE OVERRIDE + DIAGNOSTIC PRINTS
  PROBLEM: Sonnet was answering "What did OSHA announce this week?" from KB at
    90% confidence, never dispatching research_agent. KB data is static and
    cannot contain current week's news.
  FIX: After parsing Sonnet's JSON, detect time-sensitive keywords in user
    request and force research_agent into specialists_needed regardless of what
    Sonnet decided. Added unconditional DIAGNOSTIC print statements to confirm
    this code block executes on every request and to reveal exactly what Sonnet
    returned for specialists_needed.
  IMPACT: Time-sensitive queries now always route to research_agent (Tavily)
    for real-time web results. DIAGNOSTIC prints provide permanent observability.

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

import ast
import json
import re
import time
import os
from orchestration.ai_clients import call_claude_sonnet, call_claude_opus
from database import get_db
from config import DATABASE


# ============================================================================
# KNOWLEDGE DB PATH
# February 28, 2026: Resolved conflict between config.DATABASE (swarm_intelligence.db)
# and the actual knowledge database (knowledge_ingestion.db).
# KNOWLEDGE_DB_PATH env var is authoritative. Fallback uses knowledge_ingestion.db
# explicitly rather than DATABASE (which points to swarm_intelligence.db).
# ============================================================================
_KM_DB_PATH = os.environ.get(
    'KNOWLEDGE_DB_PATH',
    '/mnt/project/knowledge_ingestion.db'   # explicit correct fallback
)
print(f"📚 [task_analysis] Knowledge Management DB path: {_KM_DB_PATH}")


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


# ============================================================================
# HELPERS FOR extract_content_from_extract()
# Added February 28, 2026 (Pass 2)
#
# These two helpers are used ONLY by the consulting_insight branch of
# extract_content_from_extract(). Isolated here for clarity and testability.
# ============================================================================

# Phrases that indicate a pattern is cover-page / header noise with no
# consulting value (contact info, copyright lines, branding text).
_NOISE_PHRASES = (
    'shift-work.com',
    'contact@',
    'all rights reserved',
    '© 20',
    'optimizing 24/7 operations since',
    'covers 9 essential',
    'www.shift',
    'shiftwork solutions llc',
    '(415)',
    '@shift-work',
)


def _is_noise_section(section, body_content):
    """
    Return True if this consulting_insight pattern is cover-page / header noise
    that provides no consulting value to the AI.

    Checks the section heading and the joined body_content against a list of
    known noise phrases (contact info, copyright, branding boilerplate).

    Args:
        section (str): Section heading from pattern_data
        body_content: body_content value (list or str)

    Returns:
        bool: True if the pattern should be skipped
    """
    if isinstance(body_content, list):
        body_str = ' '.join(str(x) for x in body_content)
    else:
        body_str = str(body_content)

    combined = (section + ' ' + body_str).lower()
    return any(phrase in combined for phrase in _NOISE_PHRASES)


def _get_body_text(body_content, max_lines=4, max_chars=500):
    """
    Join body_content lines into a single readable string.

    Handles both list and string formats (the ingestion engine may store
    body_content as a Python-literal string representation of a list).
    Filters out very short lines (< 15 chars) that are typically noise.

    Args:
        body_content: body_content value from pattern_data (list or str)
        max_lines (int): Maximum number of lines to include (default 4)
        max_chars (int): Maximum characters in result (default 500)

    Returns:
        str: Joined readable text, or empty string if nothing useful
    """
    if isinstance(body_content, str):
        try:
            body_content = ast.literal_eval(body_content)
        except Exception:
            # Not a list literal — use the string directly
            return body_content[:max_chars]

    if isinstance(body_content, list):
        lines = [str(x).strip() for x in body_content if str(x).strip()]
        meaningful = [ln for ln in lines if len(ln) > 15][:max_lines]
        return ' '.join(meaningful)[:max_chars]

    return ''


# ============================================================================
# CONTENT EXTRACTOR FOR KNOWLEDGE MANAGEMENT DB RECORDS
# Added February 28, 2026 (Pass 1)
# Updated February 28, 2026 (Pass 2): Improved consulting_insight branch
#
# Reads extracted_data JSON from a knowledge_extracts row and returns a
# readable text excerpt the AI can actually use — not just metadata labels.
# Handles all document types stored by document_ingestion_engine.py:
#   consulting_lesson, consulting_insight, survey_norm, survey_client_result,
#   operational_metrics, cost_model, contract_terms, engagement_fee,
#   payment_structure, schedule_patterns_mentioned, operational_principles,
#   lessons_learned_summary, document_summary, oaf_summary, highlights
# ============================================================================

def extract_content_from_extract(doc):
    """
    Extract meaningful readable text from a knowledge_extracts row.

    Args:
        doc (dict): Row from knowledge_extracts table with keys:
                    document_name, document_type, client, extracted_data

    Returns:
        str: Readable excerpt suitable for inclusion in an AI prompt.
             Returns empty string if nothing useful can be extracted.
    """
    parts = []
    doc_name = doc.get('document_name', 'Unknown')
    doc_type = doc.get('document_type', 'unknown')
    client   = (doc.get('client') or '').strip()

    header = f"Document: {doc_name} (Type: {doc_type})"
    if client:
        header += f" | Client: {client}"
    parts.append(header)

    try:
        raw = doc.get('extracted_data', '')
        extracted = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(extracted, dict):
            return '\n'.join(parts)
    except Exception:
        return '\n'.join(parts)

    # ── PATTERNS ─────────────────────────────────────────────────────────────
    #
    # CHANGED February 28, 2026 (Pass 2):
    #   - Increased from [:6] to [:15] to capture more patterns per document
    #   - consulting_insight branch now uses _is_noise_section(), _get_body_text(),
    #     seen_sections dedup, and reads up to 2 key_principles
    #   - All other branches (consulting_lesson, survey_norm, etc.) UNCHANGED

    seen_sections = set()  # used only by consulting_insight branch

    for pattern in extracted.get('patterns', [])[:15]:
        ptype = pattern.get('type', '')
        data  = pattern.get('data', {})
        if not isinstance(data, dict):
            continue

        if ptype == 'consulting_lesson':
            # UNCHANGED
            name    = data.get('lesson_name', '') or data.get('title', '')
            kp      = data.get('key_principle', '')
            sit     = data.get('situation', '')
            why     = data.get('why_matters', '')
            ht      = data.get('hard_truth', '')
            wo      = data.get('watch_out_for', '')
            bullets = data.get('key_bullets', [])
            do_list = data.get('do_list', [])
            dont    = data.get('dont_list', [])

            if name:
                parts.append(f"  Lesson: {name}")
            if kp:
                parts.append(f"  Key Principle: {kp[:300]}")
            if sit:
                parts.append(f"  Situation: {sit[:200]}")
            if why:
                parts.append(f"  Why It Matters: {why[:200]}")
            if ht:
                parts.append(f"  Hard Truth: {ht[:200]}")
            if wo:
                parts.append(f"  Watch Out For: {wo[:150]}")
            if bullets:
                parts.append(f"  Key Points: {' | '.join(str(b)[:80] for b in bullets[:4])}")
            if do_list:
                parts.append(f"  DO: {' | '.join(str(b)[:60] for b in do_list[:3])}")
            if dont:
                parts.append(f"  DON'T: {' | '.join(str(b)[:60] for b in dont[:3])}")

        elif ptype == 'consulting_insight':
            # UPDATED February 28, 2026 (Pass 2):
            #
            # Previous version:
            #   - Used body[0] only (first line of body_content)
            #   - Used kps[0] only (first key principle)
            #   - No noise filtering
            #   - No deduplication
            #
            # Current version:
            #   - _is_noise_section(): skips cover-page / header patterns
            #   - seen_sections: skips duplicate section headings
            #   - _get_body_text(): joins ALL meaningful body_content lines
            #   - Skips patterns with < 20 chars of content
            #   - Includes up to 2 key_principles

            section = data.get('section', '').strip()
            body    = data.get('body_content', [])
            preview = data.get('body_preview', '').strip()
            kps     = data.get('key_principles', [])
            quotes  = data.get('expert_quotes', [])

            # Skip cover-page noise (contact info, copyright, branding)
            if _is_noise_section(section, body):
                continue

            # Skip duplicate section headings within the same document
            section_key = section.lower()[:50]
            if section_key and section_key in seen_sections:
                continue
            if section_key:
                seen_sections.add(section_key)

            # Build rich body text from all meaningful lines
            body_text = _get_body_text(body, max_lines=4, max_chars=500)

            # Use body_text first; fall back to preview
            content = body_text or preview

            # Skip patterns with no substantive content
            if not content or len(content.strip()) < 20:
                continue

            if section:
                parts.append(f"  Section: {section}")
            parts.append(f"  Content: {content}")

            # Include up to 2 key principles (was 1)
            if isinstance(kps, str):
                try:
                    kps = ast.literal_eval(kps)
                except Exception:
                    kps = [kps]
            for kp in (kps[:2] if isinstance(kps, list) else [kps]):
                kp_text = str(kp).strip()
                if kp_text and len(kp_text) > 20:
                    parts.append(f"  Key Principle: {kp_text[:250]}")

            # Include first expert quote if present
            if quotes:
                if isinstance(quotes, list):
                    q = str(quotes[0]).strip()
                else:
                    q = str(quotes).strip()
                if q and len(q) > 20:
                    parts.append(f"  Expert Quote: {q[:200]}")

        elif ptype in ('survey_norm', 'survey_client_result'):
            # UNCHANGED
            question = data.get('question', '')
            dist     = data.get('distribution', {})
            if question:
                parts.append(f"  Survey Q: {question[:200]}")
            if dist and isinstance(dist, dict):
                top = sorted(dist.items(), key=lambda x: -float(x[1]))[:3]
                parts.append(f"  Results: {', '.join(f'{k}: {v}%' for k, v in top)}")

        elif ptype == 'operational_metrics':
            # UNCHANGED
            metric_pairs = [
                f"{k.replace('_', ' ')}: {v}"
                for k, v in data.items()
                if k not in ('client',) and v is not None
            ]
            if metric_pairs:
                parts.append(f"  Metrics: {', '.join(metric_pairs[:6])}")

        elif ptype == 'cost_model':
            # UNCHANGED
            scenarios = data.get('scenarios', {})
            for sc_name, sc_data in list(scenarios.items())[:2]:
                cst = sc_data.get('Cost of Scheduled Time')
                if cst:
                    parts.append(f"  Cost Model — {sc_name}: ${cst:.2f}/hr")

        elif ptype in ('contract_terms', 'engagement_fee', 'payment_structure'):
            # UNCHANGED
            fee = data.get('fee') or data.get('total_fee')
            wks = data.get('weeks') or data.get('engagement_weeks')
            if fee:
                parts.append(f"  Engagement Fee: ${int(fee):,}")
            if wks:
                parts.append(f"  Duration: {wks} weeks")

        elif ptype == 'schedule_patterns_mentioned':
            # UNCHANGED
            pats = data if isinstance(data, list) else data.get('patterns', [])
            if pats:
                parts.append(f"  Schedule Patterns: {', '.join(str(p) for p in pats[:6])}")

        elif ptype == 'schedule_rotation_library':
            # UNCHANGED
            inner = data.get('patterns', [])
            if inner:
                parts.append(f"  Rotation Patterns: {len(inner)} patterns found")
                for rp in inner[:2]:
                    shift_types = rp.get('shift_types', [])
                    cycle_wks   = rp.get('cycle_weeks', '')
                    if shift_types:
                        parts.append(f"    - {cycle_wks}-week cycle, shifts: {', '.join(shift_types)}")

        elif ptype == 'operational_principles':
            # UNCHANGED
            principles = data.get('principles', [])
            for pr in principles[:3]:
                txt = pr.get('text', '') if isinstance(pr, dict) else str(pr)
                if txt:
                    parts.append(f"  Principle: {txt[:200]}")

        else:
            # Generic fallback: find first string value > 40 chars — UNCHANGED
            for v in data.values():
                if isinstance(v, str) and len(v) > 40:
                    parts.append(f"  Info: {v[:200]}")
                    break

    # ── INSIGHTS ─────────────────────────────────────────────────────────────
    # UNCHANGED
    for insight in extracted.get('insights', [])[:4]:
        if not isinstance(insight, dict):
            continue
        itype = insight.get('type', '')

        if itype == 'lessons_learned_summary':
            total = insight.get('total_lessons', 0)
            cats  = insight.get('categories', [])
            if total:
                parts.append(f"  Contains {total} lessons across: {', '.join(str(c) for c in cats[:5])}")

        elif itype == 'document_summary':
            wc = insight.get('word_count', 0)
            sc = insight.get('section_count', 0)
            if wc:
                parts.append(f"  Document stats: {wc:,} words, {sc} sections")

        elif itype == 'oaf_summary':
            metrics = insight.get('metrics', {})
            if metrics:
                metric_str = ', '.join(f"{k}: {v}" for k, v in metrics.items())
                parts.append(f"  OAF Metrics: {metric_str}")

        elif itype == 'survey_summary':
            n_q   = insight.get('questions_processed', 0)
            norms = insight.get('normative_questions', 0)
            if n_q:
                parts.append(f"  Survey: {n_q} questions processed, {norms} with normative benchmarks")

        elif itype == 'cost_model_summary':
            scenarios = insight.get('scenarios', [])
            if scenarios:
                parts.append(f"  Cost Model Scenarios: {', '.join(str(s) for s in scenarios[:4])}")

        elif itype == 'document_structure':
            headings = insight.get('headings', [])
            if headings:
                parts.append(f"  Sections: {', '.join(str(h)[:50] for h in headings[:5])}")

        elif itype == 'section_content':
            heading  = insight.get('heading', '')
            preview  = insight.get('body_preview', '')
            kps      = insight.get('key_principles', [])
            if heading and preview:
                parts.append(f"  {heading}: {preview[:200]}")
            if kps:
                parts.append(f"    Principle: {str(kps[0])[:150]}")

    # ── HIGHLIGHTS ────────────────────────────────────────────────────────────
    # UNCHANGED
    highlights = extracted.get('highlights', [])
    if highlights:
        parts.append(f"  Highlights: {' | '.join(str(h) for h in highlights[:3])}")

    result = '\n'.join(parts)
    # Return empty string if nothing useful was found beyond the header
    if result.count('\n') == 0:
        return ''
    return result


def search_knowledge_management_db(user_request, max_results=5):
    """
    Search the Knowledge Management database (uploaded documents).
    Returns extracted knowledge from the 218 documents in knowledge_ingestion.db.

    This is the "Shoulders of Giants" cumulative learning system.

    FIXED February 28, 2026 (Pass 1):
    - Uses module-level _KM_DB_PATH constant (reads KNOWLEDGE_DB_PATH env var
      with explicit fallback to knowledge_ingestion.db, not swarm_intelligence.db)
    - Added startup diagnostic print at module level to confirm which DB is used
    """
    try:
        import sqlite3

        db_path = _KM_DB_PATH  # Set at module load — see top of file

        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        # Check if table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_extracts'"
        )
        if not cursor.fetchone():
            db.close()
            print(f"⚠️ [task_analysis] knowledge_extracts table not found in {db_path}")
            return []

        # Simple keyword search across all documents
        search_terms = [t for t in user_request.lower().split()[:10] if len(t) >= 3]

        results = []
        for term in search_terms:
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
    1. Project files knowledge base (34 documents via knowledge_integration.py)
    2. Knowledge Management DB (218 uploaded documents in knowledge_ingestion.db)

    FIXED February 28, 2026 (Pass 1):
    - Knowledge Management DB results now extract ACTUAL CONTENT from extracted_data
      JSON via extract_content_from_extract(). Previously only metadata labels were
      included ("3 insights found", "type: consulting_lesson") which were useless
      to the AI. Now the AI receives lesson principles, survey results, metrics etc.

    IMPROVED February 28, 2026 (Pass 2):
    - extract_content_from_extract() now reads up to 15 patterns per document
      (was 6), filters noise, deduplicates sections, and joins all body_content
      lines for consulting_insight patterns.
    """
    all_sources = []
    all_context = []
    max_confidence = 0.0

    # ============================================================
    # SOURCE 1: Project Files Knowledge Base (34 documents)
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
    # SOURCE 2: Knowledge Management Database (218 documents)
    # FIXED February 28, 2026 (Pass 1): Now extracts actual content
    # IMPROVED February 28, 2026 (Pass 2): Richer consulting_insight extraction
    # ============================================================
    print("🔍 Searching uploaded documents (Knowledge Management DB)...")
    km_results = search_knowledge_management_db(user_request, max_results=5)

    if km_results:
        km_context_parts = ["=== UPLOADED DOCUMENTS (Knowledge Management — 218 documents) ==="]

        for idx, doc in enumerate(km_results, 1):
            # Extract real readable content from this record
            content_excerpt = extract_content_from_extract(doc)
            if content_excerpt:
                km_context_parts.append(f"\n[KM Doc {idx}]")
                km_context_parts.append(content_excerpt)

        km_context = '\n'.join(km_context_parts)

        # Only add if we got real content (more than just the header)
        if len(km_context) > len(km_context_parts[0]) + 10:
            all_context.append(km_context)
            all_sources.extend([doc['document_name'] for doc in km_results])

            km_confidence = min(0.8, len(km_results) * 0.25)
            max_confidence = max(max_confidence, km_confidence)

            print(f"  ✅ Found {len(km_results)} relevant uploaded documents")
            print(f"  📊 KM confidence: {km_confidence*100:.0f}%")
            print(f"  📄 KM context length: {len(km_context)} chars")
        else:
            print(f"  ⚠️ KM search returned {len(km_results)} docs but no extractable content")

    else:
        print(f"  ℹ️ No matching documents in Knowledge Management DB for this query")

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
    print(f"   Total context: {len(combined_context)} chars")

    return {
        'has_relevant_knowledge': True,
        'knowledge_context': combined_context,
        'knowledge_confidence': max_confidence,
        'knowledge_sources': list(set(all_sources)),
        'should_proceed_to_ai': True,
        'reason': f'Found {len(all_sources)} relevant documents across both knowledge bases',
        'source_breakdown': {
            'project_files': len([s for s in all_sources if 'project_files' in str(s)]),
            'uploaded_docs': len(km_results) if km_results else 0
        }
    }


def analyze_task_with_sonnet(user_request, knowledge_base=None, file_paths=None, file_contents=None):
    """
    Sonnet analyzes task WITH unified knowledge + system capabilities + FILE ATTACHMENTS.

    NOW SEARCHES BOTH:
    - Project files knowledge base (34 documents)
    - Knowledge Management DB (218 uploaded documents)

    Total: 250+ documents available for every request.

    UPDATED February 28, 2026 (Pass 2):
    - extract_content_from_extract() now delivers richer consulting_insight
      content: up to 15 patterns, noise filtered, sections deduped, full
      body_content text joined (up to 4 lines per section, 500 chars).

    UPDATED February 28, 2026 (Pass 1):
    - check_knowledge_base_unified() now returns real content excerpts from
      the Knowledge Management DB (218 docs). Previously returned metadata only.

    UPDATED February 21, 2026:
    - Added TIME-SENSITIVE OVERRIDE: after parsing Sonnet's JSON, detects time-
      sensitive keywords in the user request and forces research_agent into
      specialists_needed. Fixes: Sonnet was answering "What did OSHA announce
      this week?" from KB content at 90% confidence, never dispatching
      research_agent even though KB data is static.

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
    analysis_prompt = f"""{capabilities}

You are the primary orchestrator in an AI swarm system for Shiftwork Solutions LLC.

🎯 CRITICAL: You have access to extensive accumulated knowledge from:
   - Project files (implementation manuals, contracts, proposals)
   - Uploaded documents (lessons learned, assessments, client work)
   - Total: 250+ documents spanning hundreds of projects

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

        # ================================================================
        # TIME-SENSITIVE OVERRIDE (Added February 21, 2026)
        # PROBLEM: Sonnet was answering time-sensitive questions ("What did
        #   OSHA announce this week?") from KB content at 90% confidence,
        #   never dispatching research_agent even though KB data is static.
        # FIX: After parsing Sonnet's JSON, detect time-sensitive keywords
        #   in the user request and force research_agent into specialists_needed
        #   regardless of what Sonnet decided. This bypasses Sonnet's routing
        #   ONLY for requests where KB knowledge is structurally unsuitable
        #   (current events, recent announcements, breaking news).
        # ================================================================
        TIME_SENSITIVE_KEYWORDS = [
            'this week', 'this month', 'this year', 'today', 'yesterday',
            'latest', 'recent', 'just announced', 'just released', 'new rule',
            'new regulation', 'current', 'now', 'right now', 'breaking',
            'announced', 'updated', '2025', '2026', 'last week', 'last month',
            'what did', 'what has', 'what have', 'did osha', 'did dol',
            'did congress', 'news on', 'update on', 'status of'
        ]
        request_lower_ts = user_request.lower()
        is_time_sensitive = any(kw in request_lower_ts for kw in TIME_SENSITIVE_KEYWORDS)

        # DIAGNOSTIC: unconditional prints — fires on every request
        print(f"DIAGNOSTIC: is_time_sensitive={is_time_sensitive} | request={user_request[:50]}")
        print(f"DIAGNOSTIC: specialists_needed={analysis.get('specialists_needed', [])}")

        if is_time_sensitive:
            specialists = analysis.get('specialists_needed', [])
            if 'research_agent' not in specialists:
                specialists = ['research_agent'] + specialists
                analysis['specialists_needed'] = specialists
                print(f"TIME-SENSITIVE OVERRIDE: forced research_agent for: {user_request[:60]}")
            else:
                print(f"TIME-SENSITIVE: research_agent already in specialists - no override needed")
        else:
            print(f"NOT TIME-SENSITIVE: no research_agent override applied")
        # ================================================================

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

    UPDATED February 28, 2026 (Pass 2): extract_content_from_extract() now
    delivers richer consulting_insight content for Knowledge Management DB docs.

    UPDATED February 28, 2026 (Pass 1): check_knowledge_base_unified() now returns
    real content excerpts from Knowledge Management DB (218 docs).

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
    opus_prompt = f"""{capabilities}

You are the strategic supervisor in the AI Swarm for Shiftwork Solutions LLC.

🎯 You have access to 250+ documents of accumulated expertise. Act as a senior consulting partner.

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

    specialist_map = {
        "research_agent": call_research_agent,   # Tavily web search
        "gpt4": call_gpt4,
        "deepseek": call_deepseek,
        "gemini": call_gemini,
        "sonnet": call_claude_sonnet,
        "opus": call_claude_opus
    }

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
