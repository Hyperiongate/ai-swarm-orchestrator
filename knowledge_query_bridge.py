"""
KNOWLEDGE QUERY BRIDGE
Created: February 27, 2026
Last Updated: February 27, 2026

PURPOSE:
    Bridges the gap between the manually-ingested knowledge base
    (knowledge_ingestion.db — 79 documents, 413 patterns as of Feb 27, 2026)
    and the AI orchestration layer (routes/orchestration_handler.py).

    BEFORE this module: Documents uploaded through the Knowledge Management UI
    were stored and indexed but NEVER queried when the AI answered questions.
    Only the GitHub project files (knowledge_integration.py System 1) were
    queried. This module closes that gap.

    AFTER this module: Every AI response in Handler 10 (regular conversation)
    queries BOTH knowledge systems:
      - System 1: knowledge_integration.py (GitHub project files, auto-indexed)
      - System 2: knowledge_ingestion.db (manually uploaded documents via KB UI)
    The combined context is injected into the Sonnet prompt before generation.

HOW IT WORKS:
    1. query_ingested_knowledge(user_request) is called from orchestration_handler.py
       immediately before building the completion_prompt.
    2. It searches knowledge_extracts (full documents) and learned_patterns
       (extracted insights) using keyword matching against the user's query.
    3. Results are ranked by relevance score and formatted as a readable
       context block that Sonnet can cite in its answer.
    4. The formatted block is injected into completion_prompt between
       specialized_context and summary_context.

DESIGN PRINCIPLES:
    - Graceful degradation: any failure returns "" so no existing
      functionality breaks (Rule 1: Do No Harm).
    - Fast: all queries use indexed SQLite with LIKE and scoring, no
      external API calls. Adds <50ms to response time.
    - Capped: max 5 patterns + 3 full document sections per query
      to keep prompt size manageable.
    - Domain-aware: shiftwork-specific terms get priority scoring
      so "2-2-3" or "20/60/20" surface the right lessons.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import os
import json
import re
import sqlite3
from typing import List, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Max number of patterns to include in context
MAX_PATTERNS = 5

# Max number of full document extract sections to include
MAX_EXTRACTS = 3

# Max total character length of the KB context block injected into prompt
MAX_CONTEXT_CHARS = 5000

# Domain-specific terms that get priority scoring (multiplier applied to score)
DOMAIN_PRIORITY_TERMS = {
    # Numeric rules
    '20/60/20', '70/70', '24/7', '24/5',
    # Schedule patterns
    '2-2-3', '3-2-2-3', '4-4', '4-3', '2-2-3', 'dupont', 'panama', 'pitman',
    'continental', 'southern swing',
    # Operational concepts
    'overtime', 'staffing', 'coverage', 'fatigue', 'turnover', 'retention',
    'absenteeism', 'shift differential', 'burden rate', 'adverse cost',
    'change management', 'resistance', 'implementation', 'survey',
    # People concepts
    'employee involvement', 'employee survey', 'preference', 'engagement',
    'satisfaction', 'union', 'grievance',
    # Shift types
    '12-hour', '8-hour', '10-hour', 'rotating', 'fixed',
    # Industries
    'manufacturing', 'pharmaceutical', 'food processing', 'mining',
    'distribution', 'chemical',
}


# ---------------------------------------------------------------------------
# MAIN PUBLIC FUNCTION
# ---------------------------------------------------------------------------

def query_ingested_knowledge(user_request: str) -> str:
    """
    Query the ingested knowledge base for content relevant to user_request.

    Called from routes/orchestration_handler.py in Handler 10 (PATH 3 — Sonnet
    regular conversation) immediately before building completion_prompt.

    Args:
        user_request: The raw user question/request string

    Returns:
        Formatted context string to inject into the Sonnet prompt, or ""
        if nothing relevant is found or any error occurs.
    """
    if not user_request or not user_request.strip():
        return ""

    try:
        db_path = _get_db_path()
        if not db_path or not os.path.exists(db_path):
            return ""

        query_terms = _extract_query_terms(user_request)
        if not query_terms:
            return ""

        patterns = _search_patterns(db_path, query_terms, user_request)
        extracts = _search_extracts(db_path, query_terms, user_request)

        if not patterns and not extracts:
            return ""

        formatted = _format_context_block(patterns, extracts, user_request)
        return formatted

    except Exception as e:
        # Graceful degradation — never break the main request
        print(f"KnowledgeBridge: non-critical error querying ingested KB: {e}")
        return ""


# ---------------------------------------------------------------------------
# DB PATH RESOLUTION
# ---------------------------------------------------------------------------

def _get_db_path() -> Optional[str]:
    """
    Resolve the knowledge database path using the same logic as
    DocumentIngestor in document_ingestion_engine.py.
    Checks KNOWLEDGE_DB_PATH env var first, then falls back to default.
    """
    db_path = os.environ.get('KNOWLEDGE_DB_PATH', '')
    if db_path and os.path.exists(db_path):
        return db_path

    # Fallback candidates (same order as Render deployment)
    candidates = [
        '/opt/render/project/src/knowledge_ingestion.db',
        'swarm_intelligence.db',
        os.path.join(os.getcwd(), 'swarm_intelligence.db'),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return None


# ---------------------------------------------------------------------------
# QUERY TERM EXTRACTION
# ---------------------------------------------------------------------------

def _extract_query_terms(user_request: str) -> List[str]:
    """
    Extract meaningful search terms from the user request.

    Handles:
    - Multi-word domain phrases (2-2-3, 20/60/20, DuPont)
    - Single keywords after stopword removal
    - Numeric shiftwork terms (12-hour, 24/7)

    Returns list of terms sorted by estimated relevance (domain terms first).
    """
    req_lower = user_request.lower()

    found_domain = []
    for term in DOMAIN_PRIORITY_TERMS:
        if term.lower() in req_lower:
            found_domain.append(term.lower())

    # Tokenize: capture hyphenated, slash-separated, and plain words
    raw_tokens = re.findall(r'[a-z0-9]+(?:[-/][a-z0-9]+)*', req_lower)

    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'been', 'be',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
        'could', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
        'it', 'its', 'as', 'if', 'when', 'where', 'which', 'who', 'i', 'me',
        'we', 'us', 'our', 'what', 'how', 'why', 'tell', 'about', 'give',
        'help', 'need', 'want', 'looking', 'information', 'please', 'thank',
        'more', 'some', 'any', 'get', 'just', 'know', 'think', 'like', 'use',
        'using', 'used', 'can', 'my', 'your', 'their', 'his', 'her', 'its'
    }

    plain_terms = [
        t for t in raw_tokens
        if t not in stopwords and len(t) > 2
    ]

    # Combine: domain terms first (highest priority), then plain terms
    # Deduplicate while preserving order
    seen = set()
    combined = []
    for t in found_domain + plain_terms:
        if t not in seen:
            seen.add(t)
            combined.append(t)

    return combined[:20]  # Cap at 20 terms


# ---------------------------------------------------------------------------
# PATTERN SEARCH
# ---------------------------------------------------------------------------

def _search_patterns(db_path: str, query_terms: List[str],
                     user_request: str) -> List[Dict]:
    """
    Search learned_patterns table for relevant extracted knowledge.

    Scoring:
    - +3 per query term found in pattern_name
    - +1 per query term found in pattern_data text
    - +2 bonus for domain priority terms
    - Higher confidence patterns ranked higher (confidence * 2 bonus)

    Returns list of scored pattern dicts, sorted by score descending.
    """
    results = []

    try:
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row

        # Check table exists
        exists = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='learned_patterns'"
        ).fetchone()
        if not exists:
            db.close()
            return []

        # Fetch candidate rows using OR LIKE for efficiency
        # We'll score in Python for accuracy
        like_clauses = ' OR '.join(['pattern_data LIKE ?'] * len(query_terms[:5]))
        params = [f'%{t}%' for t in query_terms[:5]]

        rows = db.execute(
            f'''SELECT id, pattern_type, pattern_name, pattern_data,
                       confidence, supporting_documents
                FROM learned_patterns
                WHERE ({like_clauses})
                   OR pattern_name LIKE ?
                ORDER BY confidence DESC, supporting_documents DESC
                LIMIT 50''',
            params + [f'%{query_terms[0]}%'] if query_terms else params
        ).fetchall()

        db.close()

        req_lower = user_request.lower()

        for row in rows:
            score = 0.0
            pattern_name_lower = (row['pattern_name'] or '').lower()
            pattern_data_str = (row['pattern_data'] or '').lower()

            for i, term in enumerate(query_terms):
                term_lower = term.lower()
                # Name match is strongest signal
                if term_lower in pattern_name_lower:
                    score += 3.0
                # Data content match
                if term_lower in pattern_data_str:
                    score += 1.0
                # Priority domain terms get extra weight
                if term_lower in DOMAIN_PRIORITY_TERMS:
                    score += 2.0

            # Confidence bonus
            score += float(row['confidence'] or 0.5) * 2.0

            # Supporting documents bonus (more evidence = more reliable)
            score += min(float(row['supporting_documents'] or 1), 5.0) * 0.5

            if score > 2.0:  # Only include genuinely relevant patterns
                results.append({
                    'score': score,
                    'pattern_type': row['pattern_type'],
                    'pattern_name': row['pattern_name'],
                    'pattern_data': row['pattern_data'],
                    'confidence': row['confidence'],
                })

    except Exception as e:
        print(f"KnowledgeBridge: pattern search error: {e}")

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:MAX_PATTERNS]


# ---------------------------------------------------------------------------
# EXTRACT SEARCH
# ---------------------------------------------------------------------------

def _search_extracts(db_path: str, query_terms: List[str],
                     user_request: str) -> List[Dict]:
    """
    Search knowledge_extracts table for relevant full document sections.

    Extracts store the full structured output from document ingestion
    (insights, patterns, highlights). We search document_name and
    a portion of extracted_data to find relevant source documents.

    Returns list of scored extract summaries, sorted by score descending.
    """
    results = []

    try:
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row

        exists = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_extracts'"
        ).fetchone()
        if not exists:
            db.close()
            return []

        # Search across document_name and extracted_data
        like_clauses = ' OR '.join(
            ['document_name LIKE ? OR extracted_data LIKE ?'] * len(query_terms[:4])
        )
        params = []
        for t in query_terms[:4]:
            params.extend([f'%{t}%', f'%{t}%'])

        rows = db.execute(
            f'''SELECT id, document_type, document_name, client, industry,
                       extracted_at, extracted_data
                FROM knowledge_extracts
                WHERE {like_clauses}
                ORDER BY extracted_at DESC
                LIMIT 30''',
            params
        ).fetchall()

        db.close()

        for row in rows:
            score = 0.0
            doc_name_lower = (row['document_name'] or '').lower()
            extracted_str = (row['extracted_data'] or '').lower()

            for term in query_terms:
                term_lower = term.lower()
                if term_lower in doc_name_lower:
                    score += 4.0
                if term_lower in extracted_str:
                    score += 1.0
                if term_lower in DOMAIN_PRIORITY_TERMS:
                    score += 1.5

            if score > 2.0:
                # Parse extracted_data to get readable highlights
                summary = _summarize_extract(row['extracted_data'], query_terms)

                results.append({
                    'score': score,
                    'document_name': row['document_name'],
                    'document_type': row['document_type'],
                    'client': row['client'] or '',
                    'industry': row['industry'] or '',
                    'summary': summary,
                })

    except Exception as e:
        print(f"KnowledgeBridge: extract search error: {e}")

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:MAX_EXTRACTS]


def _summarize_extract(extracted_data_json: str, query_terms: List[str]) -> str:
    """
    Parse the extracted_data JSON from knowledge_extracts and produce
    a concise human-readable summary of the most relevant content.

    Prioritizes:
    1. highlights (always shown — they are the top-level summaries)
    2. consulting_lesson patterns (key_principle + situation)
    3. consulting_insight patterns (body_content)
    4. section_content insights
    5. Document structure (headings list)
    """
    try:
        data = json.loads(extracted_data_json)
    except (json.JSONDecodeError, TypeError):
        return str(extracted_data_json)[:300]

    parts = []

    # 1. Highlights (top-level document summary bullets)
    highlights = data.get('highlights', [])
    if highlights:
        parts.append('Key points: ' + ' | '.join(str(h) for h in highlights[:4]))

    # 2. Patterns — consulting lessons are the richest source
    for pattern in data.get('patterns', [])[:8]:
        ptype = pattern.get('type', '')
        pdata = pattern.get('data', {})

        if ptype == 'consulting_lesson':
            principle = pdata.get('key_principle', '')
            situation = pdata.get('situation', '')
            lesson_name = pdata.get('lesson_name', pdata.get('title', ''))
            if principle or situation:
                lesson_text = f"Lesson: {lesson_name}"
                if principle:
                    lesson_text += f" — {principle[:250]}"
                elif situation:
                    lesson_text += f" — {situation[:250]}"
                parts.append(lesson_text)

        elif ptype == 'consulting_insight':
            section = pdata.get('section', '')
            body_content = pdata.get('body_content', [])
            key_principles = pdata.get('key_principles', [])
            if section and (body_content or key_principles):
                insight_text = f"Section '{section}'"
                if key_principles:
                    insight_text += f": {key_principles[0][:200]}"
                elif body_content:
                    insight_text += f": {body_content[0][:200]}"
                parts.append(insight_text)

        elif ptype in ('schedule_patterns_mentioned', 'schedule_patterns_presented'):
            patterns_list = pdata if isinstance(pdata, list) else pdata.get('data', [])
            if patterns_list:
                parts.append(f"Schedules referenced: {', '.join(str(p) for p in patterns_list[:6])}")

        elif ptype == 'operational_metrics':
            metrics_parts = []
            if 'overtime_pct' in pdata:
                metrics_parts.append(f"OT: {pdata['overtime_pct']}%")
            if 'absenteeism_pct' in pdata:
                metrics_parts.append(f"Absenteeism: {pdata['absenteeism_pct']}%")
            if 'turnover_pct' in pdata:
                metrics_parts.append(f"Turnover: {pdata['turnover_pct']}%")
            if metrics_parts:
                client = pdata.get('client', 'client')
                parts.append(f"Metrics ({client}): {', '.join(metrics_parts)}")

    # 3. Insights — section content and document structure
    for insight in data.get('insights', [])[:5]:
        itype = insight.get('type', '')

        if itype == 'section_content':
            heading = insight.get('heading', '')
            body_content = insight.get('body_content', [])
            key_principles = insight.get('key_principles', [])
            if heading and (body_content or key_principles):
                text = f"'{heading}'"
                if key_principles:
                    text += f": {key_principles[0][:200]}"
                elif body_content:
                    text += f": {body_content[0][:200]}"
                parts.append(text)

        elif itype == 'document_structure':
            headings = insight.get('headings', [])
            if headings:
                parts.append(f"Sections covered: {', '.join(headings[:6])}")

        elif itype == 'lessons_learned_summary':
            total = insight.get('total_lessons', 0)
            categories = insight.get('categories', [])
            if total:
                parts.append(
                    f"{total} lessons across: {', '.join(categories[:4])}"
                )

    if not parts:
        return 'Document indexed — see knowledge management for full content.'

    return ' | '.join(parts)[:1500]


# ---------------------------------------------------------------------------
# CONTEXT FORMATTING
# ---------------------------------------------------------------------------

def _format_context_block(patterns: List[Dict], extracts: List[Dict],
                           user_request: str) -> str:
    """
    Format the retrieved patterns and extracts into a readable context block
    suitable for injection into the Sonnet completion prompt.

    The block is labeled clearly so Sonnet knows this is authoritative
    internal knowledge and should be cited/used in its response.
    """
    if not patterns and not extracts:
        return ""

    sep = '=' * 65
    lines = [
        '',
        sep,
        'SHIFTWORK SOLUTIONS INGESTED KNOWLEDGE BASE',
        '  (From manually uploaded consulting documents, lessons learned,',
        '   implementation manuals, contracts, surveys, and guides)',
        '  USE THIS AS A PRIMARY SOURCE when relevant to the question.',
        sep,
        '',
    ]

    if extracts:
        lines.append('--- RELEVANT DOCUMENTS ---')
        for i, ext in enumerate(extracts, 1):
            doc_name = ext.get('document_name', 'Unknown')
            doc_type = ext.get('document_type', '')
            client = ext.get('client', '')
            industry = ext.get('industry', '')
            summary = ext.get('summary', '')

            header_parts = [f"DOC {i}: {doc_name}"]
            if doc_type:
                header_parts.append(f"[{doc_type}]")
            if client:
                header_parts.append(f"Client: {client}")
            if industry:
                header_parts.append(f"Industry: {industry}")

            lines.append(' | '.join(header_parts))
            if summary:
                # Wrap long summary lines
                for chunk in _chunk_text(summary, max_len=500):
                    lines.append(f"  {chunk}")
            lines.append('')

    if patterns:
        lines.append('--- EXTRACTED PATTERNS & LESSONS ---')
        for i, pat in enumerate(patterns, 1):
            ptype = pat.get('pattern_type', '')
            pname = pat.get('pattern_name', '')
            confidence = pat.get('confidence', 0.5)

            lines.append(
                f"PATTERN {i}: {pname} [{ptype}] "
                f"(confidence: {float(confidence):.0%})"
            )

            # Parse pattern_data to extract readable content
            pdata_str = pat.get('pattern_data', '{}')
            try:
                pdata = json.loads(pdata_str) if isinstance(pdata_str, str) else pdata_str
            except (json.JSONDecodeError, TypeError):
                pdata = {}

            readable = _readable_pattern(ptype, pdata)
            if readable:
                for chunk in _chunk_text(readable, max_len=400):
                    lines.append(f"  {chunk}")
            lines.append('')

    lines.extend([
        sep,
        'END INGESTED KNOWLEDGE BASE',
        sep,
        '',
    ])

    full_block = '\n'.join(lines)

    # Cap total length to protect prompt budget
    if len(full_block) > MAX_CONTEXT_CHARS:
        full_block = full_block[:MAX_CONTEXT_CHARS] + '\n  [... additional knowledge truncated for length]\n'

    return full_block


def _readable_pattern(pattern_type: str, pdata: dict) -> str:
    """
    Convert a pattern_data dict into human-readable text for the context block.
    Handles the main pattern types produced by document_ingestion_engine.py.
    """
    parts = []

    if pattern_type == 'consulting_lesson':
        if pdata.get('key_principle'):
            parts.append(f"Key Principle: {pdata['key_principle'][:300]}")
        if pdata.get('situation'):
            parts.append(f"Situation: {pdata['situation'][:200]}")
        if pdata.get('hard_truth'):
            parts.append(f"Hard Truth: {pdata['hard_truth'][:200]}")
        if pdata.get('watch_out_for'):
            parts.append(f"Watch Out For: {pdata['watch_out_for'][:150]}")
        if pdata.get('do_list'):
            dos = pdata['do_list'][:3]
            parts.append(f"DO: {' / '.join(dos)}")
        if pdata.get('dont_list'):
            donts = pdata['dont_list'][:3]
            parts.append(f"DON'T: {' / '.join(donts)}")
        if pdata.get('key_bullets'):
            bullets = pdata['key_bullets'][:3]
            parts.append(f"Rules: {' | '.join(b[:100] for b in bullets)}")

    elif pattern_type == 'consulting_insight':
        if pdata.get('key_principles'):
            parts.append(f"Principle: {pdata['key_principles'][0][:300]}")
        if pdata.get('body_content'):
            parts.append(f"Content: {pdata['body_content'][0][:250]}")
        if pdata.get('expert_quotes'):
            parts.append(f"Quote: {pdata['expert_quotes'][0][:200]}")

    elif pattern_type == 'engagement_fee':
        fee = pdata.get('fee')
        client = pdata.get('client', '')
        weeks = pdata.get('weeks')
        if fee:
            parts.append(
                f"Fee: ${int(fee):,}"
                + (f" | Client: {client}" if client else "")
                + (f" | Weeks: {weeks}" if weeks else "")
            )

    elif pattern_type in ('operational_metrics', 'cost_comparison'):
        items = []
        for key, val in pdata.items():
            if key not in ('client',) and isinstance(val, (int, float)):
                label = key.replace('_', ' ').title()
                items.append(f"{label}: {val}{'%' if 'pct' in key else ''}")
        if pdata.get('client'):
            items.insert(0, f"Client: {pdata['client']}")
        parts.append(' | '.join(items[:5]))

    elif pattern_type == 'schedule_patterns_mentioned':
        schedules = pdata if isinstance(pdata, list) else pdata.get('data', [])
        if schedules:
            parts.append(f"Schedules: {', '.join(str(s) for s in schedules[:8])}")

    elif pattern_type == 'payment_structure':
        milestones = pdata if isinstance(pdata, list) else []
        for m in milestones[:3]:
            if isinstance(m, dict):
                parts.append(
                    f"${m.get('amount', 0):,} due upon {m.get('milestone', '')}"
                )

    elif pattern_type in ('survey_client_result', 'survey_norm'):
        question = pdata.get('question', pdata.get('data', {}).get('question', ''))
        dist = pdata.get('distribution', pdata.get('data', {}).get('distribution', {}))
        if question:
            parts.append(f"Survey Q: {question[:150]}")
        if dist:
            top_items = sorted(dist.items(), key=lambda x: float(x[1]), reverse=True)[:3]
            dist_str = ', '.join(f"{k}: {v}" for k, v in top_items)
            parts.append(f"Distribution: {dist_str}")

    else:
        # Generic fallback — just stringify the most useful fields
        for key in ('summary', 'description', 'text', 'content', 'principle'):
            if pdata.get(key):
                parts.append(str(pdata[key])[:300])
                break
        if not parts:
            parts.append(str(pdata)[:200])

    return ' | '.join(parts)


def _chunk_text(text: str, max_len: int = 400) -> List[str]:
    """Split long text into chunks at sentence or word boundaries."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while len(text) > max_len:
        # Try to break at a sentence boundary
        break_at = text.rfind('. ', 0, max_len)
        if break_at == -1:
            # Fall back to word boundary
            break_at = text.rfind(' ', 0, max_len)
        if break_at == -1:
            break_at = max_len
        chunks.append(text[:break_at + 1].strip())
        text = text[break_at + 1:].strip()
    if text:
        chunks.append(text)
    return chunks


# ---------------------------------------------------------------------------
# UTILITY: QUICK STATS (for diagnostics / admin endpoints)
# ---------------------------------------------------------------------------

def get_ingested_kb_stats() -> Dict:
    """
    Return summary statistics about the ingested knowledge base.
    Used by diagnostic endpoints to verify the KB is populated.
    """
    try:
        db_path = _get_db_path()
        if not db_path or not os.path.exists(db_path):
            return {'available': False, 'reason': 'Database not found'}

        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row

        stats = {'available': True, 'db_path': db_path}

        try:
            row = db.execute('SELECT COUNT(*) as c FROM knowledge_extracts').fetchone()
            stats['total_documents'] = row['c'] if row else 0
        except Exception:
            stats['total_documents'] = 0

        try:
            row = db.execute('SELECT COUNT(*) as c FROM learned_patterns').fetchone()
            stats['total_patterns'] = row['c'] if row else 0
        except Exception:
            stats['total_patterns'] = 0

        try:
            rows = db.execute(
                'SELECT document_type, COUNT(*) as c FROM knowledge_extracts GROUP BY document_type'
            ).fetchall()
            stats['by_type'] = {r['document_type']: r['c'] for r in rows}
        except Exception:
            stats['by_type'] = {}

        db.close()
        return stats

    except Exception as e:
        return {'available': False, 'reason': str(e)}


# I did no harm and this file is not truncated
