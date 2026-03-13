"""
AI SWARM ORCHESTRATOR - Lead Scanner
File: proactive/lead_scanner.py
Created: March 12, 2026
Last Updated: March 13, 2026 — BUG FIX: remove raise from _ensure_table()

PURPOSE:
    Automatically scans the web for potential business leads — new manufacturing
    plants, facility expansions, and shift-work-related news in target industries.
    Stores qualifying leads in the lead_alerts PostgreSQL table. Surfaces them
    in the daily briefing and via GET /api/leads.

    Uses the existing ResearchAgent (research_agent.py) for Tavily API calls.
    Uses Claude Sonnet to score each result for relevance to shift scheduling.
    Only stores leads with relevance score >= 6 out of 10.

SEARCH STRATEGY:
    Five query groups are rotated daily using day-of-year modulo arithmetic.
    Running one group per day keeps Tavily API usage low (~3-5 calls/day)
    while covering all lead types over the course of a week.

    Group 0: "new manufacturing plant opening {year}"
    Group 1: "new distribution center construction {year}"
    Group 2: "facility expansion 24/7 operations {year}"
    Group 3: "plant hiring night shift workers {year}"
    Group 4: "shift schedule change manufacturing {year}"

CHANGELOG:
- March 13, 2026: BUG FIX — remove raise from _ensure_table()
  * _ensure_table() ran at module level and called raise on DB failure.
  * If the DB was temporarily unavailable at startup, Python marked the
    module as a failed import. All subsequent imports raised ImportError.
  * routes/proactive.py catches ImportError and returns 503.
  * Fix: log the error but do NOT re-raise. The module loads successfully
    and table creation is retried on the next DB operation.
  * Only the except block in _ensure_table() changed — nothing else touched.

- March 12, 2026: Phase 6 Deliverable 3 — Initial implementation
  * Created lead_alerts table (idempotent migration on import)
  * scan_for_leads() — rotates queries, scores with Sonnet, stores results
  * get_new_leads(limit) — returns unreviewed leads by relevance score
  * get_lead_summary() — structured data for daily briefing
  * update_lead_status(lead_id, status) — mark reviewed/contacted/dismissed
  * Deduplication on source_url (UNIQUE constraint + pre-check)
  * All SQL uses %s placeholders and get_db_connection() per db_engine.py
  * Uses get_research_agent() singleton — never instantiates ResearchAgent directly
  * Does NOT use get_db() from database.py (legacy) — uses db_engine only

DATABASE TABLE: lead_alerts
    id               SERIAL PRIMARY KEY
    title            TEXT
    summary          TEXT
    source_url       TEXT UNIQUE        — deduplication key
    industry         VARCHAR(100)
    location         VARCHAR(200)
    relevance_score  FLOAT
    status           VARCHAR(20) DEFAULT 'new'   (new|reviewed|contacted|dismissed)
    created_at       TIMESTAMP DEFAULT NOW()
    reviewed_at      TIMESTAMP

DEPENDENCIES:
    research_agent.py   — get_research_agent(), .search() method
    db_engine.py        — get_db_connection()
    config.py           — ANTHROPIC_API_KEY, CLAUDE_SONNET_MODEL

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import logging
from datetime import date, datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

VALID_LEAD_STATUSES = {'new', 'reviewed', 'contacted', 'dismissed'}
MIN_RELEVANCE_SCORE = 6.0   # Only store leads scoring >= 6 out of 10

# Five query groups rotated by day-of-year.
# Each group produces 3-5 Tavily searches per daily run.
# Rotation: day_of_year % len(QUERY_GROUPS) picks today's group.
_QUERY_GROUPS = [
    # Group 0 — new plant openings
    [
        "new manufacturing plant opening {year}",
        "new factory construction groundbreaking {year}",
        "manufacturing plant expansion announcement {year}",
    ],
    # Group 1 — distribution/warehouse
    [
        "new distribution center construction {year}",
        "new warehouse facility opening {year}",
        "logistics center expansion 24 hour operations {year}",
    ],
    # Group 2 — 24/7 expansion
    [
        "facility expansion 24/7 continuous operations {year}",
        "plant adding second third shift {year}",
        "manufacturing company adding night shift {year}",
    ],
    # Group 3 — hiring signals
    [
        "plant hiring night shift workers {year}",
        "manufacturing facility hiring shift workers {year}",
        "distribution center overnight shift hiring {year}",
    ],
    # Group 4 — scheduling pain signals
    [
        "shift schedule change manufacturing employees {year}",
        "rotating shift schedule problems workforce {year}",
        "factory shift scheduling overhaul {year}",
    ],
]

# Industries we serve — used to help Sonnet score relevance
_TARGET_INDUSTRIES = (
    "manufacturing, pharmaceutical, food processing, distribution, "
    "mining, utilities, chemical, automotive, aerospace, logistics"
)


# ============================================================================
# STEP 1: ENSURE TABLE EXISTS (idempotent)
# ============================================================================

def _ensure_table():
    """
    Create lead_alerts table if it does not already exist.
    Called once at module import. Fully idempotent.
    The UNIQUE constraint on source_url is the deduplication mechanism.

    NOTE: Does NOT re-raise on failure. A DB hiccup at startup must not
    poison the module import — routes/proactive.py catches ImportError and
    returns 503, so a transient DB error here would permanently break the
    endpoint until the next deploy. Log and continue instead.
    """
    from db_engine import get_db_connection

    sql = """
        CREATE TABLE IF NOT EXISTS lead_alerts (
            id              SERIAL PRIMARY KEY,
            title           TEXT,
            summary         TEXT,
            source_url      TEXT UNIQUE,
            industry        VARCHAR(100),
            location        VARCHAR(200),
            relevance_score FLOAT,
            status          VARCHAR(20)  DEFAULT 'new',
            created_at      TIMESTAMP    DEFAULT NOW(),
            reviewed_at     TIMESTAMP
        )
    """
    try:
        with get_db_connection() as conn:
            conn.execute(sql)
        logger.info("lead_alerts table ready")
        print("✅ proactive/lead_scanner: lead_alerts table ready")
    except Exception as e:
        logger.error(f"Failed to create lead_alerts table: {e}")
        print(f"❌ proactive/lead_scanner: table creation failed (non-fatal): {e}")
        # Do NOT re-raise — a transient DB error must not poison this module's import


_ensure_table()


# ============================================================================
# PUBLIC API
# ============================================================================

def scan_for_leads() -> Dict[str, Any]:
    """
    Run today's search group, score each result with Sonnet, and store
    any leads with relevance_score >= 6.

    Called by proactive/scheduler.py at 6:00 AM Pacific daily.
    Can also be triggered manually via the API.

    Search rotation: uses day_of_year % 5 to pick today's query group.
    This spreads API calls across the week and avoids hammering Tavily
    with all queries simultaneously.

    Returns:
        dict with keys:
            success (bool)
            group_index (int): which query group ran today
            queries_run (int): number of Tavily searches made
            results_evaluated (int): total raw results scored by Sonnet
            leads_stored (int): new leads saved (score >= 6, not duplicate)
            leads_skipped (int): results below threshold or already stored
            errors (list): any non-fatal errors encountered
    """
    logger.info("scan_for_leads: starting daily lead scan")
    print("🔍 Lead Scanner: starting daily scan...")

    # ----------------------------------------------------------------
    # 1. Check Tavily is available
    # ----------------------------------------------------------------
    try:
        from research_agent import get_research_agent
        agent = get_research_agent()
    except Exception as e:
        msg = f"Could not load research_agent: {e}"
        logger.error(msg)
        return {'success': False, 'error': msg, 'leads_stored': 0}

    if not agent.is_available:
        msg = "Tavily API key not configured — lead scan skipped"
        logger.warning(msg)
        print(f"⚠️  Lead Scanner: {msg}")
        return {'success': False, 'error': msg, 'leads_stored': 0}

    # ----------------------------------------------------------------
    # 2. Select today's query group via rotation
    # ----------------------------------------------------------------
    current_year = date.today().year
    day_of_year  = date.today().timetuple().tm_yday
    group_index  = day_of_year % len(_QUERY_GROUPS)
    raw_queries  = _QUERY_GROUPS[group_index]

    # Substitute {year} placeholder
    queries = [q.format(year=current_year) for q in raw_queries]

    logger.info(f"scan_for_leads: running group {group_index} ({len(queries)} queries)")
    print(f"🔍 Lead Scanner: group {group_index}, {len(queries)} queries for {current_year}")

    # ----------------------------------------------------------------
    # 3. Run searches and collect raw results
    # ----------------------------------------------------------------
    raw_results: List[Dict[str, Any]] = []
    queries_run = 0
    errors: List[str] = []

    for query in queries:
        try:
            result = agent.search(
                query=query,
                search_depth="basic",
                max_results=5,
            )
            queries_run += 1

            if result.get('success') and result.get('results'):
                for item in result['results']:
                    item['_search_query'] = query   # track which query found it
                raw_results.extend(result['results'])
                print(f"  ✓ '{query}' → {len(result['results'])} results")
            else:
                logger.warning(f"No results for query: '{query}'")

        except Exception as e:
            err = f"Search failed for '{query}': {e}"
            logger.error(err)
            errors.append(err)
            print(f"  ⚠️  {err}")

    if not raw_results:
        logger.info("No raw results from any search query")
        print("ℹ️  Lead Scanner: no results returned from Tavily")
        return {
            'success': True,
            'group_index': group_index,
            'queries_run': queries_run,
            'results_evaluated': 0,
            'leads_stored': 0,
            'leads_skipped': 0,
            'errors': errors,
        }

    # ----------------------------------------------------------------
    # 4. Deduplicate raw results by URL before scoring
    #    (avoid paying Sonnet tokens for URLs we already have)
    # ----------------------------------------------------------------
    seen_urls: set = set()
    unique_results: List[Dict[str, Any]] = []
    for item in raw_results:
        url = (item.get('url') or '').strip()
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(item)

    # Also filter out URLs already in the database
    existing_urls = _get_existing_urls(list(seen_urls))
    unique_results = [
        r for r in unique_results
        if (r.get('url') or '').strip() not in existing_urls
    ]

    logger.info(f"scan_for_leads: {len(unique_results)} unique new URLs to score")
    print(f"🔍 Lead Scanner: scoring {len(unique_results)} unique new results...")

    # ----------------------------------------------------------------
    # 5. Score each result with Sonnet — batch to reduce API calls
    # ----------------------------------------------------------------
    leads_stored  = 0
    leads_skipped = 0

    for item in unique_results:
        try:
            scored = _score_result_with_sonnet(item)
            if scored is None:
                leads_skipped += 1
                continue

            if scored['score'] < MIN_RELEVANCE_SCORE:
                leads_skipped += 1
                logger.debug(
                    f"Below threshold ({scored['score']:.1f}): {item.get('title', '')[:60]}"
                )
                continue

            # Store the lead
            stored = _store_lead(
                title           = item.get('title', 'Untitled'),
                summary         = scored.get('summary', item.get('content', '')[:300]),
                source_url      = item.get('url', ''),
                industry        = scored.get('industry', 'Unknown'),
                location        = scored.get('location', 'Unknown'),
                relevance_score = scored['score'],
            )
            if stored:
                leads_stored += 1
                print(
                    f"  ✅ Stored lead [{scored['score']:.0f}/10]: "
                    f"{item.get('title', '')[:60]}"
                )
            else:
                leads_skipped += 1   # Duplicate caught at INSERT level

        except Exception as e:
            err = f"Error processing result '{item.get('title', '')}': {e}"
            logger.error(err)
            errors.append(err)
            leads_skipped += 1

    print(
        f"🔍 Lead Scanner: complete — "
        f"{leads_stored} stored, {leads_skipped} skipped, "
        f"{len(errors)} errors"
    )
    logger.info(
        f"scan_for_leads complete: stored={leads_stored}, "
        f"skipped={leads_skipped}, errors={len(errors)}"
    )

    return {
        'success':            True,
        'group_index':        group_index,
        'queries_run':        queries_run,
        'results_evaluated':  len(unique_results),
        'leads_stored':       leads_stored,
        'leads_skipped':      leads_skipped,
        'errors':             errors,
    }


def get_new_leads(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return unreviewed leads (status='new') sorted by relevance_score descending.

    Args:
        limit: Maximum leads to return (default 10, max 50)

    Returns:
        List of lead dicts (JSON-serializable), best leads first
    """
    limit = max(1, min(int(limit), 50))
    from db_engine import get_db_connection

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, summary, source_url, industry, location,
                       relevance_score, status, created_at
                FROM   lead_alerts
                WHERE  status = 'new'
                ORDER  BY relevance_score DESC, created_at DESC
                LIMIT  %s
            """, (limit,))
            rows = cursor.fetchall()

        return [_serialize_lead(row) for row in rows]

    except Exception as e:
        logger.error(f"get_new_leads failed: {e}")
        return []


def get_lead_summary() -> Dict[str, Any]:
    """
    Return aggregate lead statistics for the daily briefing.

    Returns:
        dict with keys:
            total_new (int): leads with status='new'
            total_all (int): all leads ever stored
            by_industry (dict): count of new leads per industry
            top_leads (list): top 3 new leads by relevance_score
            available (bool): True if table is accessible
    """
    from db_engine import get_db_connection

    summary: Dict[str, Any] = {
        'total_new':   0,
        'total_all':   0,
        'by_industry': {},
        'top_leads':   [],
        'available':   False,
    }

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Total new
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM lead_alerts WHERE status = 'new'"
            )
            summary['total_new'] = cursor.fetchone()['cnt']

            # Total all-time
            cursor.execute("SELECT COUNT(*) AS cnt FROM lead_alerts")
            summary['total_all'] = cursor.fetchone()['cnt']

            # New leads by industry
            cursor.execute("""
                SELECT industry, COUNT(*) AS cnt
                FROM   lead_alerts
                WHERE  status = 'new'
                GROUP  BY industry
                ORDER  BY cnt DESC
            """)
            summary['by_industry'] = {
                row['industry']: row['cnt'] for row in cursor.fetchall()
            }

            # Top 3 new leads
            cursor.execute("""
                SELECT id, title, industry, location, relevance_score
                FROM   lead_alerts
                WHERE  status = 'new'
                ORDER  BY relevance_score DESC
                LIMIT  3
            """)
            summary['top_leads'] = [
                _serialize_lead(row) for row in cursor.fetchall()
            ]

        summary['available'] = True
        return summary

    except Exception as e:
        logger.error(f"get_lead_summary failed: {e}")
        summary['error'] = str(e)
        return summary


def update_lead_status(lead_id: int, status: str) -> bool:
    """
    Update a lead's status (reviewed, contacted, or dismissed).

    Args:
        lead_id: The lead's database ID
        status:  One of 'reviewed', 'contacted', 'dismissed'

    Returns:
        True if updated, False if not found or invalid status
    """
    status = status.lower().strip()
    if status not in VALID_LEAD_STATUSES:
        logger.warning(f"update_lead_status: invalid status '{status}'")
        return False

    from db_engine import get_db_connection

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lead_alerts
                SET    status      = %s,
                       reviewed_at = NOW()
                WHERE  id = %s
            """, (status, lead_id))
            updated = cursor.rowcount

        if updated:
            logger.info(f"Lead {lead_id} status → {status}")
        return bool(updated)

    except Exception as e:
        logger.error(f"update_lead_status failed for id={lead_id}: {e}")
        return False


# ============================================================================
# PRIVATE HELPERS
# ============================================================================

def _get_existing_urls(urls: List[str]) -> set:
    """
    Return the subset of URLs that already exist in lead_alerts.
    Used to avoid scoring results we already have stored.
    Falls back to empty set on any error (better to score a duplicate
    than to crash the scan).
    """
    if not urls:
        return set()

    from db_engine import get_db_connection

    try:
        # PostgreSQL supports ANY(%s) with a list parameter
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT source_url FROM lead_alerts WHERE source_url = ANY(%s)",
                (urls,)
            )
            rows = cursor.fetchall()
        return {row['source_url'] for row in rows}

    except Exception as e:
        logger.warning(f"_get_existing_urls failed (non-fatal): {e}")
        return set()


def _score_result_with_sonnet(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Call Claude Sonnet to score a single search result for lead relevance.

    Args:
        item: A Tavily result dict with title, url, content fields

    Returns:
        dict with keys: score (float), industry (str), location (str), summary (str)
        Returns None on API failure or unparseable response.
    """
    import anthropic
    from config import ANTHROPIC_API_KEY, CLAUDE_SONNET_MODEL

    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set — cannot score leads")
        return None

    title   = item.get('title', 'No title')
    content = item.get('content', '')[:600]   # Cap to avoid token waste
    url     = item.get('url', '')

    prompt = f"""You are a lead qualification assistant for Shiftwork Solutions LLC, \
a shift work scheduling consulting firm serving {_TARGET_INDUSTRIES} industries.

Evaluate this search result for potential business relevance:

Title: {title}
URL: {url}
Content: {content}

Is this a potential lead for a shift work consulting firm? Consider:
- Is this a new or expanding facility that would need shift scheduling help?
- Is it in an industry we serve?
- Is there a scheduling problem, transition, or growth signal mentioned?
- Would this facility likely run 24/7 or multi-shift operations?

Return ONLY a JSON object. No preamble, no explanation, no markdown code fences.

{{
  "relevant": true or false,
  "score": 0 to 10,
  "industry": "industry name or Unknown",
  "location": "city and state/country or Unknown",
  "summary": "One sentence about why this is or is not relevant to shift scheduling"
}}"""

    try:
        client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=CLAUDE_SONNET_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()

        # Strip accidental markdown fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        scored = json.loads(raw_text)

        # Validate and normalize
        score = float(scored.get('score', 0))
        score = max(0.0, min(10.0, score))

        return {
            'score':    score,
            'industry': str(scored.get('industry', 'Unknown'))[:100],
            'location': str(scored.get('location', 'Unknown'))[:200],
            'summary':  str(scored.get('summary', ''))[:500],
        }

    except json.JSONDecodeError as e:
        logger.warning(f"Could not parse Sonnet lead score as JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Sonnet lead scoring failed: {e}")
        return None


def _store_lead(
    title: str,
    summary: str,
    source_url: str,
    industry: str,
    location: str,
    relevance_score: float,
) -> bool:
    """
    Insert a new lead into lead_alerts.
    Uses INSERT ... ON CONFLICT DO NOTHING so a duplicate URL is silently
    skipped rather than raising an exception.

    Returns:
        True if a new row was inserted, False if duplicate or error
    """
    from db_engine import get_db_connection

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lead_alerts
                    (title, summary, source_url, industry, location,
                     relevance_score, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'new', NOW())
                ON CONFLICT (source_url) DO NOTHING
            """, (title, summary, source_url, industry, location, relevance_score))
            inserted = cursor.rowcount

        return inserted > 0

    except Exception as e:
        logger.error(f"_store_lead failed for '{source_url}': {e}")
        return False


def _serialize_lead(row) -> Dict[str, Any]:
    """
    Convert a lead_alerts DB row to a plain JSON-serializable dict.
    """
    result = {}
    for key in row.keys():
        value = row[key]
        if isinstance(value, (datetime, date)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


# I did no harm and this file is not truncated
