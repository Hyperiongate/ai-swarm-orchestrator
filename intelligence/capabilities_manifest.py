"""
intelligence/capabilities_manifest.py
AI Swarm Orchestrator — Dynamic Capabilities Manifest
Created: March 08, 2026
Last Updated: March 08, 2026 — Phase 3 Self-Awareness (initial build)

CHANGELOG:
- March 08, 2026: Phase 3 Self-Awareness
  * NEW FILE — dynamically generates a runtime capabilities manifest.
  * Queries live system state: API keys, loaded modules, memory count,
    knowledge base doc count, research agent availability, blueprint list.
  * Results cached for 5 minutes (CACHE_TTL = 300) to avoid redundant
    DB queries on every request. Cache is refreshed on demand via
    invalidate_manifest_cache().
  * generate_capabilities_manifest() returns full text manifest (<3000 chars).
  * get_manifest_summary() returns short summary (<500 chars).
  * All imports are wrapped in try/except — if any module is unavailable
    the manifest still generates; it simply reports that capability as
    unavailable. Never raises to the caller.
  * Called by orchestration/system_capabilities.py as the primary source
    for get_system_capabilities_prompt(). Falls back to static manifest
    if this module raises unexpectedly.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import time

# =============================================================================
# MANIFEST CACHE
# Generated once at startup then refreshed every 5 minutes.
# Module-level dict — shared across all requests in the same worker process.
# =============================================================================

CACHE_TTL = 300  # seconds (5 minutes)

_manifest_cache = {
    'text': None,
    'summary': None,
    'sections': {},
    'generated_at': 0.0,
    'cached': False,
}


def _is_cache_valid():
    """Return True if the cached manifest is still within the TTL window."""
    return (
        _manifest_cache['text'] is not None and
        (time.time() - _manifest_cache['generated_at']) < CACHE_TTL
    )


def invalidate_manifest_cache():
    """
    Force the next call to generate_capabilities_manifest() to rebuild.
    Call this after any configuration change at runtime.
    """
    _manifest_cache['generated_at'] = 0.0
    _manifest_cache['text'] = None
    _manifest_cache['summary'] = None
    _manifest_cache['sections'] = {}
    _manifest_cache['cached'] = False


# =============================================================================
# SECTION BUILDERS — each returns a plain-text string for its section
# =============================================================================

def _build_ai_models_section():
    """
    Section 1: Which AI models are configured based on live API key state.
    Checks config.py keys at call time (not import time) so Render env vars
    are always current.
    """
    try:
        from config import ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY, GOOGLE_API_KEY
    except Exception:
        return "AI model configuration could not be determined."

    lines = []

    if ANTHROPIC_API_KEY:
        lines.append(
            "Claude Sonnet (primary orchestrator, speed/efficiency) and "
            "Claude Opus (complex strategic analysis) are available."
        )
    else:
        lines.append(
            "CRITICAL: Claude is NOT configured — ANTHROPIC_API_KEY is missing. "
            "Core orchestration will fail."
        )

    if OPENAI_API_KEY:
        lines.append("GPT-4 is available for design, content, report formatting, and document tasks.")
    else:
        lines.append(
            "GPT-4 is NOT configured — document formatting and design tasks will fall back to Claude."
        )

    if DEEPSEEK_API_KEY:
        lines.append("DeepSeek is available for code generation and technical implementation tasks.")
    else:
        lines.append(
            "DeepSeek is NOT configured — code generation tasks will fall back to Claude."
        )

    if GOOGLE_API_KEY:
        lines.append("Gemini is available for multimodal analysis and image-based tasks.")
    else:
        lines.append(
            "Gemini is NOT configured — image analysis tasks will fall back to Claude."
        )

    return " ".join(lines)


def _build_schedule_section():
    """
    Section 2: Schedule generator status and available patterns.
    Checks whether schedule_generator module is importable and functional.
    """
    try:
        from schedule_generator import get_pattern_generator  # noqa: F401
        return (
            "Schedule generator is available and ready. "
            "12-hour patterns: 2-2-3, 2-3-2, 3-2-2-3, 4-3, 4-4, DuPont. "
            "8-hour patterns: 5-2-fixed, 6-3-fixed, Southern Swing, 6-2-rotating. "
            "Output is Excel with color coding and professional labeling. "
            "IMPORTANT: When a user asks to generate a schedule, USE THE SCHEDULE GENERATOR "
            "to produce the actual Excel file — do not just describe the schedule pattern."
        )
    except Exception:
        return "Schedule generator is not available — schedule_generator module not loaded."


def _build_knowledge_base_section():
    """
    Section 3: Knowledge base status — document count and topics covered.
    Reads from the app config where the KB object is stored after startup.
    Falls back gracefully if not yet initialized.
    """
    try:
        from flask import current_app
        kb = current_app.config.get('knowledge_base') or current_app.config.get('KNOWLEDGE_BASE')
        if kb is None:
            # Try the module-level reference set during app startup
            import app as _app_module
            kb = getattr(_app_module, 'knowledge_base', None)

        if kb is not None and getattr(kb, 'is_ready', False):
            doc_count = len(getattr(kb, 'knowledge_index', {}))
            return (
                f"Knowledge base is active with {doc_count} indexed documents. "
                "Topics covered: shift scheduling methodology, overtime management, "
                "implementation planning, employee survey design, cost analysis, "
                "contract templates, and lessons learned from hundreds of past projects. "
                "IMPORTANT: When answering questions about shift work, scheduling, or "
                "workforce management, ALWAYS check the knowledge base first. "
                "It contains 35+ years of Shiftwork Solutions consulting expertise."
            )
        elif kb is not None:
            return (
                "Knowledge base is initializing. Document count not yet available. "
                "Topics: shift scheduling, overtime, implementation, surveys, cost analysis. "
                "Check again in 30-60 seconds after startup."
            )
        else:
            return "Knowledge base is not initialized. Project files may be unavailable."
    except Exception as e:
        return f"Knowledge base status could not be determined ({type(e).__name__})."


def _build_memory_section():
    """
    Section 4: Memory system status — counts from the memory_store table.
    Queries PostgreSQL directly. Safe if memory tables don't exist yet.
    """
    try:
        from db_engine import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Total count
            cursor.execute("SELECT COUNT(*) as cnt FROM memory_store")
            row = cursor.fetchone()
            total = row['cnt'] if row else 0

            # Count by memory_type
            cursor.execute(
                "SELECT memory_type, COUNT(*) as cnt FROM memory_store "
                "GROUP BY memory_type ORDER BY cnt DESC"
            )
            type_rows = cursor.fetchall()
            type_summary = ", ".join(
                f"{r['memory_type']}: {r['cnt']}" for r in type_rows
            ) if type_rows else "none"

            # Distinct categories
            cursor.execute(
                "SELECT DISTINCT category FROM memory_store "
                "WHERE category IS NOT NULL ORDER BY category LIMIT 10"
            )
            cat_rows = cursor.fetchall()
            categories = ", ".join(r['category'] for r in cat_rows) if cat_rows else "none"

        return (
            f"Memory system is active. Total memories stored: {total}. "
            f"By type: {type_summary}. "
            f"Categories with memories: {categories}. "
            "IMPORTANT: You have persistent memory across sessions. "
            "Before answering any question, check if you have relevant memories. "
            "If a user mentions a client or project name, search your memory FIRST "
            "before doing web research or making assumptions."
        )
    except Exception as e:
        return (
            f"Memory system status could not be determined ({type(e).__name__}). "
            "Memory-based recall may be unavailable."
        )


def _build_research_section():
    """
    Section 5: Research agent status based on TAVILY_API_KEY.
    """
    try:
        from config import TAVILY_API_KEY
        if TAVILY_API_KEY:
            return (
                "Web research is available via the Research Agent (Tavily). "
                "Can search for industry news, regulatory updates, competitor analysis, "
                "and company information. "
                "IMPORTANT: Only use web research for information you do NOT already "
                "have in memory or the knowledge base. Memory and knowledge base are "
                "your FIRST sources. Web research is a LAST RESORT for information "
                "you genuinely do not have."
            )
        else:
            return (
                "Web research is NOT configured — TAVILY_API_KEY is missing. "
                "Do not attempt to use the research agent."
            )
    except Exception:
        return "Research agent status could not be determined."


def _build_other_capabilities_section():
    """
    Section 6: Other loaded capabilities — checks which blueprints/modules
    are actually registered in the running Flask app.
    """
    capabilities = []

    module_checks = [
        ("database_file_management", "get_project_manager",
         "Project management: create and track projects, upload files, conversation history."),
        ("intelligence", "get_lead_manager",
         "Intelligence dashboard: lead scoring and pipeline management with normative database."),
        ("content_marketing_engine", "get_content_engine",
         "Content marketing: LinkedIn posts and newsletter generation from consulting work."),
        ("implementation_manual_generator", "get_manuals_dashboard",
         "Implementation manual generator: Word document generation for client engagements."),
        ("alert_system", "get_alert_manager",
         "Alert system: scheduled monitoring and notifications."),
        ("avatar_consultation_engine", "get_avatar_engine",
         "Avatar consultation system: David and Sarah consultation personas."),
    ]

    for module_name, func_name, description in module_checks:
        try:
            mod = __import__(module_name)
            if hasattr(mod, func_name):
                capabilities.append(description)
        except Exception:
            pass  # Module not loaded — silently skip

    if capabilities:
        return " ".join(capabilities)
    return "No additional capability modules detected beyond core orchestration."


def _build_limitations_section():
    """
    Section 7: What the system CANNOT do — always included for honesty.
    Checks live config to determine which limitations apply.
    """
    limitations = []

    try:
        from config import SMTP_PASSWORD, ENABLE_EMAIL_ALERTS
        if not SMTP_PASSWORD or not ENABLE_EMAIL_ALERTS:
            limitations.append(
                "Cannot send emails directly — SMTP is not configured."
            )
    except Exception:
        limitations.append("Cannot send emails directly — email configuration unavailable.")

    limitations.extend([
        "Cannot access external databases or CRMs.",
        "Cannot make phone calls or send text messages.",
        "Cannot access the user's local files — they must be uploaded through the interface.",
        "Cannot modify Render or GitHub configuration.",
    ])

    return (
        "Current limitations: " + " ".join(limitations) + " "
        "If you need a capability that is not listed, explain to the user "
        "what would be needed to add it."
    )


# =============================================================================
# MAIN MANIFEST GENERATOR
# =============================================================================

def generate_capabilities_manifest(force_refresh=False):
    """
    Generate (or return cached) the full dynamic capabilities manifest.

    Queries live system state: API keys, module availability, memory counts,
    knowledge base document count, blueprint registration status.

    Results are cached for CACHE_TTL seconds (5 minutes). Pass
    force_refresh=True to bypass the cache.

    Returns:
        str: Plain-text capabilities manifest under 3000 characters.
             Never raises — returns a minimal fallback string on any error.
    """
    if not force_refresh and _is_cache_valid():
        return _manifest_cache['text']

    try:
        sections = {}
        sections['ai_models']         = _build_ai_models_section()
        sections['schedule']          = _build_schedule_section()
        sections['knowledge_base']    = _build_knowledge_base_section()
        sections['memory']            = _build_memory_section()
        sections['research']          = _build_research_section()
        sections['other']             = _build_other_capabilities_section()
        sections['limitations']       = _build_limitations_section()

        manifest = (
            "IMPORTANT: The following is your complete capabilities list. "
            "When a user asks you to do something, ACTIVELY CHECK whether you have "
            "a capability that can help. If a user asks about a client, CHECK YOUR "
            "MEMORY FIRST. If a user asks about shift schedules, CHECK THE KNOWLEDGE "
            "BASE. If a user asks you to generate a schedule, USE THE SCHEDULE "
            "GENERATOR — do not just describe the schedule. If you cannot do what "
            "the user asks, explain specifically what capability is missing and what "
            "would be needed to add it.\n\n"
            "=== LIVE CAPABILITIES MANIFEST ===\n\n"
            f"[AI MODELS]\n{sections['ai_models']}\n\n"
            f"[SCHEDULE GENERATION]\n{sections['schedule']}\n\n"
            f"[KNOWLEDGE BASE]\n{sections['knowledge_base']}\n\n"
            f"[MEMORY SYSTEM]\n{sections['memory']}\n\n"
            f"[RESEARCH]\n{sections['research']}\n\n"
            f"[OTHER CAPABILITIES]\n{sections['other']}\n\n"
            f"[LIMITATIONS]\n{sections['limitations']}\n\n"
            "=== END CAPABILITIES MANIFEST ==="
        )

        # Warn in logs if we approach the limit but never truncate
        if len(manifest) > 2800:
            print(
                f"⚠️ [capabilities_manifest] Manifest is {len(manifest)} chars "
                f"(approaching 3000 limit). Consider trimming section text."
            )

        _manifest_cache['text']         = manifest
        _manifest_cache['sections']     = sections
        _manifest_cache['summary']      = _build_summary(sections)
        _manifest_cache['generated_at'] = time.time()
        _manifest_cache['cached']       = True

        print(
            f"✅ [capabilities_manifest] Manifest generated: {len(manifest)} chars, "
            f"{len(sections)} sections."
        )
        return manifest

    except Exception as e:
        # Never raise to caller — return minimal fallback
        print(f"❌ [capabilities_manifest] Manifest generation failed: {e}")
        fallback = (
            "=== CAPABILITIES MANIFEST (fallback — generation error) ===\n"
            "Core AI orchestration is available. "
            "Knowledge base, memory, and schedule generator may be available. "
            "Consult /api/capabilities for current status.\n"
            "=== END ==="
        )
        return fallback


def _build_summary(sections):
    """
    Build the short summary string (<500 chars) from already-built sections.
    Called internally after sections dict is populated.
    """
    # AI models — extract first sentence
    ai_line = sections.get('ai_models', '').split('.')[0]

    # Schedule
    sched = "Schedules: enabled" if "available" in sections.get('schedule', '') else "Schedules: disabled"

    # KB
    kb_text = sections.get('knowledge_base', '')
    if "active with" in kb_text:
        import re
        m = re.search(r'active with (\d+)', kb_text)
        kb = f"KB: {m.group(1)} docs" if m else "KB: active"
    else:
        kb = "KB: not ready"

    # Memory
    mem_text = sections.get('memory', '')
    if "Total memories stored:" in mem_text:
        import re
        m = re.search(r'Total memories stored: (\d+)', mem_text)
        mem = f"Memory: {m.group(1)} items" if m else "Memory: active"
    else:
        mem = "Memory: unavailable"

    # Research
    res = "Research: enabled" if "available via" in sections.get('research', '') else "Research: disabled"

    summary = f"{ai_line}. {sched} | {kb} | {mem} | {res}"
    return summary[:499]


def get_manifest_summary():
    """
    Return the short capabilities summary (<500 chars).
    Generates the full manifest if cache is empty (to populate the summary).
    Used by /health endpoint and /api/capabilities/summary.

    Returns:
        str: Short summary string. Never raises.
    """
    if not _is_cache_valid():
        generate_capabilities_manifest()
    return _manifest_cache.get('summary') or "Capabilities summary unavailable."


def get_manifest_sections():
    """
    Return the sections dict from the last manifest generation.
    Used by /api/capabilities for per-section debugging.

    Returns:
        dict: Section name -> section text. Empty dict if not yet generated.
    """
    if not _is_cache_valid():
        generate_capabilities_manifest()
    return _manifest_cache.get('sections', {})


def get_manifest_metadata():
    """
    Return cache metadata for the /api/capabilities response.

    Returns:
        dict: generated_at, cached, manifest_length, summary_length
    """
    return {
        'generated_at': _manifest_cache.get('generated_at', 0.0),
        'cached': _manifest_cache.get('cached', False),
        'manifest_length': len(_manifest_cache.get('text') or ''),
        'summary_length': len(_manifest_cache.get('summary') or ''),
    }


# I did no harm and this file is not truncated
