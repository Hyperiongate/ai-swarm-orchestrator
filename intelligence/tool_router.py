"""
intelligence/tool_router.py
AI Swarm Orchestrator — Phase 4: Tool Router
Created: March 08, 2026
Last Updated: March 08, 2026 — Initial build (Phase 4)

CHANGELOG:
- March 08, 2026: Phase 4 initial build
  NEW FILE. Routes USE_TOOL decisions from reasoning_engine.py to the
  correct internal tool.

- March 08, 2026: AI-DRIVEN SCHEDULE GENERATOR
  PROBLEM: _run_schedule_generator() previously went straight to
  PatternScheduleGenerator.create_schedule() (hardcoded arrays). The
  knowledge base context gathered by orchestration_handler.py was passed
  to reason_about_request() but dropped before execute_tool() was called.
  The AI was used only as a dispatcher, never as the expert who generates
  the schedule.

  FIX: Three-layer generation pipeline:
    Layer 1 — AI-driven: Query KB for pattern context, call Claude Sonnet
      to generate the correct day-by-day crew pattern as structured JSON,
      validate 24/7 coverage, pass to PatternScheduleGenerator for Excel.
    Layer 2 — Hardcoded fallback: If AI output fails validation, fall back
      to verified hardcoded arrays with a warning log.
    Layer 3 — Clarification: If pattern/shift_length missing, ask user.

  execute_tool() now accepts kb_context (str, default "") so
  orchestration_handler.py can pass _re_kb_context through to the tools.

  VALIDATION: _validate_schedule_pattern() checks:
    - Correct cycle length per pattern
    - Values are D/N/O only
    - Each day has exactly 1 Day crew and 1 Night crew across all crews
    - No crew works more than 5 consecutive days

  SUPPORTED TOOLS:
    schedule_generator — AI-driven pattern generation → Excel via
      PatternScheduleGenerator. Falls back to hardcoded on validation fail.
    research_agent — calls call_research_agent() from task_analysis.py.
    manual_generator — stub pending implementation_manual_generator.py.

  RETURN FORMAT (all tools):
    'success'              (bool)
    'message'              (str)
    'file_path'            (str|None)
    'file_type'            (str|None)
    'needs_clarification'  (bool)
    'clarification_message' (str|None)
    'error'                (str|None)
    Plus tool-specific keys (shift_length, pattern_key, ai_generated).

  DO NO HARM: All imports are inside functions, wrapped in try/except.
  Never raises. Returns success=False with helpful message on any error.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json
import time

# =============================================================================
# PATTERN METADATA REGISTRY
# Defines expected cycle lengths and crew counts for each supported pattern.
# Used for validation and for building the AI generation prompt.
# =============================================================================

_PATTERN_REGISTRY = {
    # 12-hour patterns
    'dupont':   {'cycle_days': 28, 'crews': 4, 'shift_hours': 12,
                 'description': 'DuPont 12-hour rotating — 4 days, 3 off, 3 days, 1 off, '
                                '3 nights, 3 off, 4 nights, 7 off. Pay-week aligned Mon–Sun.'},
    '2-2-3':    {'cycle_days': 14, 'crews': 4, 'shift_hours': 12,
                 'description': '2-2-3 pattern: 2 on, 2 off, 3 on then mirror for 4 crews. '
                                'Alternates day/night. Every other weekend off.'},
    '2-3-2':    {'cycle_days': 14, 'crews': 4, 'shift_hours': 12,
                 'description': '2-3-2 pattern variant of the 2-2-3 family.'},
    '3-2-2-3':  {'cycle_days': 14, 'crews': 4, 'shift_hours': 12,
                 'description': '3-2-2-3 (Panama) pattern: 3 on, 2 off, 2 on, 3 off.'},
    '4-4':      {'cycle_days': 8,  'crews': 4, 'shift_hours': 12,
                 'description': '4 on / 4 off: 4 consecutive 12-hour shifts, 4 off, repeat.'},
    '4-3':      {'cycle_days': 7,  'crews': 4, 'shift_hours': 12,
                 'description': '4 on / 3 off: 4 days on, 3 days off, repeating.'},
    # 8-hour patterns
    '5-2-fixed':      {'cycle_days': 7,  'crews': 3, 'shift_hours': 8,
                       'description': '5 days on / 2 off — fixed shifts Mon–Fri with Sat/Sun off.'},
    '6-3-fixed':      {'cycle_days': 9,  'crews': 3, 'shift_hours': 8,
                       'description': '6 days on / 3 off — fixed shift pattern.'},
    'southern_swing': {'cycle_days': 28, 'crews': 4, 'shift_hours': 8,
                       'description': 'Southern Swing 8-hour rotating: days, evenings, nights '
                                      'rotating weekly over a 28-day cycle.'},
    '6-2-rotating':   {'cycle_days': 8,  'crews': 4, 'shift_hours': 8,
                       'description': '6 on / 2 off rotating 8-hour pattern.'},
}

# =============================================================================
# PATTERN KEY NORMALIZER
# =============================================================================

_VALID_12HR_PATTERNS = {'2-2-3', '2-3-2', '3-2-2-3', '4-3', '4-4', 'dupont'}
_VALID_8HR_PATTERNS  = {'5-2-fixed', '6-3-fixed', 'southern_swing', '6-2-rotating'}


def _normalize_pattern_key(raw):
    if not raw:
        return None
    key = str(raw).lower().strip().replace(' ', '_').replace('/', '-')
    if key in _VALID_12HR_PATTERNS or key in _VALID_8HR_PATTERNS:
        return key
    if 'dupont' in key or 'du-pont' in key:
        return 'dupont'
    if 'southern' in key:
        return 'southern_swing'
    if '223' in key or '2_2_3' in key:
        return '2-2-3'
    if '232' in key or '2_3_2' in key:
        return '2-3-2'
    if '3223' in key or '3_2_2_3' in key:
        return '3-2-2-3'
    return key


# =============================================================================
# SCHEDULE PATTERN VALIDATOR
# Checks AI-generated patterns before they reach the Excel formatter.
# =============================================================================

def _validate_schedule_pattern(crew_patterns, pattern_key):
    """
    Validate an AI-generated crew pattern dict.

    Args:
        crew_patterns (dict): {'Crew A': ['D','N','O',...], ...}
        pattern_key (str): normalized pattern key

    Returns:
        (is_valid: bool, error_message: str)
    """
    meta = _PATTERN_REGISTRY.get(pattern_key)
    if not meta:
        return False, f"Unknown pattern '{pattern_key}' — cannot validate."

    cycle_days = meta['cycle_days']
    expected_crews = meta['crews']
    valid_values = {'D', 'N', 'O'}

    # Check crew count
    if len(crew_patterns) != expected_crews:
        return False, (
            f"Expected {expected_crews} crews for {pattern_key}, "
            f"got {len(crew_patterns)}."
        )

    # Check array length and values
    for crew, pattern in crew_patterns.items():
        if len(pattern) != cycle_days:
            return False, (
                f"Crew {crew}: expected {cycle_days} days, got {len(pattern)}."
            )
        for i, v in enumerate(pattern):
            if str(v).upper() not in valid_values:
                return False, (
                    f"Crew {crew} day {i+1}: invalid value '{v}' "
                    f"(must be D, N, or O)."
                )

    # For 24/7 patterns (12-hour), check day and night coverage
    shift_hours = meta.get('shift_hours', 12)
    if shift_hours == 12:
        crew_names = list(crew_patterns.keys())
        coverage_errors = []
        for day_idx in range(cycle_days):
            day_count = sum(
                1 for c in crew_names
                if str(crew_patterns[c][day_idx]).upper() == 'D'
            )
            night_count = sum(
                1 for c in crew_names
                if str(crew_patterns[c][day_idx]).upper() == 'N'
            )
            if day_count != 1:
                coverage_errors.append(
                    f"Day {day_idx+1}: {day_count} Day crews (need 1)"
                )
            if night_count != 1:
                coverage_errors.append(
                    f"Day {day_idx+1}: {night_count} Night crews (need 1)"
                )
        if coverage_errors:
            return False, (
                f"24/7 coverage failure in {len(coverage_errors)} day(s): "
                + "; ".join(coverage_errors[:4])
            )

    # Check max consecutive days (safety: no crew should work more than 5 in a row)
    for crew, pattern in crew_patterns.items():
        consecutive = 0
        for v in pattern:
            if str(v).upper() in ('D', 'N'):
                consecutive += 1
                if consecutive > 5:
                    return False, (
                        f"Crew {crew} has more than 5 consecutive working days — "
                        f"unsafe schedule."
                    )
            else:
                consecutive = 0

    return True, ""


# =============================================================================
# AI PATTERN GENERATION
# Calls Claude Sonnet with KB context to generate the crew pattern as JSON.
# =============================================================================

_PATTERN_GENERATION_SYSTEM_PROMPT = """You are an expert shift schedule designer for Shiftwork Solutions LLC, 
with 30+ years of experience designing 24/7 rotating schedules. You generate precise, validated 
schedule patterns as structured JSON. Every pattern you generate must provide exactly 1 Day crew 
and 1 Night crew for every day of the cycle — no exceptions. You never guess. You reason from 
the pattern's documented structure and your deep knowledge of shift scheduling."""


def _build_pattern_generation_prompt(shift_length, pattern_key, meta, kb_context, user_request):
    """
    Build the prompt that asks Sonnet to generate the correct crew pattern.
    """
    cycle_days = meta['cycle_days']
    num_crews = meta['crews']
    description = meta['description']

    kb_section = ""
    if kb_context and kb_context.strip():
        kb_section = f"""
KNOWLEDGE BASE CONTEXT (from Shiftwork Solutions documents — use as primary reference):
{kb_context.strip()}
END KNOWLEDGE BASE CONTEXT
"""

    prompt = f"""You are generating a {shift_length}-hour {pattern_key.upper().replace('_', ' ')} schedule pattern.

PATTERN DESCRIPTION: {description}

USER REQUEST: {user_request}
{kb_section}
REQUIREMENTS:
- Shift length: {shift_length} hours
- Pattern: {pattern_key}
- Cycle length: EXACTLY {cycle_days} days
- Number of crews: EXACTLY {num_crews} crews (Crew A, Crew B, Crew C{', Crew D' if num_crews == 4 else ''})
- Valid values: "D" (Day shift), "N" (Night shift), "O" (Off)
- CRITICAL: Each day position must have EXACTLY 1 "D" and EXACTLY 1 "N" across all crews (for 12-hour patterns)
- No crew should work more than 4 consecutive days

INSTRUCTIONS:
1. Reason through the {pattern_key} pattern structure step by step
2. Generate the day-by-day pattern for each crew across all {cycle_days} days
3. Verify: for each of the {cycle_days} days, count D's and N's across crews — must be exactly 1 each
4. Return ONLY valid JSON — no explanation, no markdown, no text outside the JSON

Return this exact JSON structure:
{{
  "pattern_key": "{pattern_key}",
  "shift_length": {shift_length},
  "cycle_days": {cycle_days},
  "crews": {num_crews},
  "reasoning": "Brief explanation of how this pattern achieves 24/7 coverage",
  "crew_patterns": {{
    "Crew A": ["D","D","O","N","N","O","O", ... exactly {cycle_days} values],
    "Crew B": ["N","O","D","D","O","N","O", ... exactly {cycle_days} values],
    "Crew C": ["O","N","O","O","D","D","N", ... exactly {cycle_days} values]{',\n    "Crew D": ["O","O","N","O","O","O","D", ... exactly {cycle_days} values]' if num_crews == 4 else ''}
  }}
}}"""
    return prompt


def _generate_pattern_with_ai(shift_length, pattern_key, meta, kb_context, user_request):
    """
    Call Claude Sonnet to generate the schedule pattern from KB context.

    Returns:
        (crew_patterns: dict|None, reasoning: str, error: str|None)
        crew_patterns is None if generation failed.
    """
    try:
        from orchestration.ai_clients import call_claude_sonnet

        prompt = _build_pattern_generation_prompt(
            shift_length, pattern_key, meta, kb_context, user_request
        )

        print(f"🤖 [tool_router] Calling Sonnet for AI pattern generation "
              f"({len(prompt)} char prompt, pattern={pattern_key})...")

        api_response = call_claude_sonnet(
            prompt,
            conversation_history=None,
            files_attached=False,
            system_prompt=_PATTERN_GENERATION_SYSTEM_PROMPT,
        )

        if isinstance(api_response, dict):
            if api_response.get('error'):
                return None, "", f"Sonnet API error: {api_response.get('content', 'unknown')}"
            response_text = api_response.get('content', '')
        else:
            response_text = str(api_response)

        # Extract JSON from response
        json_str = _extract_json_object(response_text)
        if json_str is None:
            return None, "", (
                f"No JSON found in Sonnet response "
                f"(first 200 chars): {response_text[:200]}"
            )

        parsed = json.loads(json_str)
        crew_patterns = parsed.get('crew_patterns')
        reasoning = parsed.get('reasoning', '')

        if not crew_patterns or not isinstance(crew_patterns, dict):
            return None, "", "Sonnet returned JSON but crew_patterns is missing or not a dict."

        # Normalize values to uppercase
        normalized = {}
        for crew, pattern in crew_patterns.items():
            normalized[crew] = [str(v).upper() for v in pattern]

        print(f"🤖 [tool_router] AI generated pattern for {pattern_key}: "
              f"{len(normalized)} crews × {len(list(normalized.values())[0])} days")

        return normalized, reasoning, None

    except Exception as e:
        import traceback
        print(f"⚠️ [tool_router] AI pattern generation failed: {traceback.format_exc()}")
        return None, "", str(e)


def _extract_json_object(text):
    """Extract the first complete JSON object from a response string."""
    if not text:
        return None
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


# =============================================================================
# SCHEDULE GENERATOR TOOL — AI-DRIVEN WITH HARDCODED FALLBACK
# =============================================================================

def _run_schedule_generator(tool_parameters, user_request, kb_context=""):
    """
    Generate a schedule Excel file using a three-layer pipeline:

    Layer 1 — AI-driven: Query KB, call Sonnet to generate correct pattern,
      validate 24/7 coverage, pass validated pattern to Excel formatter.
    Layer 2 — Hardcoded fallback: If AI output fails validation (or AI call
      fails), use the verified hardcoded arrays in schedule_generator.py.
    Layer 3 — Clarification: If shift_length or pattern_key is missing,
      return needs_clarification=True.

    Args:
        tool_parameters (dict|None): shift_length, pattern_key from reasoning engine.
        user_request (str): Original user message.
        kb_context (str): Knowledge base context from query_ingested_knowledge(),
            passed through from orchestration_handler.py.

    Returns standard tool result dict.
    """
    # --- Extract and validate parameters ---
    shift_length_raw = (tool_parameters or {}).get('shift_length')
    pattern_key_raw  = (tool_parameters or {}).get('pattern_key')

    shift_length = None
    if shift_length_raw in (8, 12, '8', '12'):
        shift_length = int(shift_length_raw)

    pattern_key = _normalize_pattern_key(pattern_key_raw)

    # --- Check for missing parameters ---
    missing = []
    if not shift_length:
        missing.append('shift length (8-hour or 12-hour shifts)')
    if not pattern_key:
        missing.append('schedule pattern (e.g. 2-2-3, DuPont, 4-4)')

    if missing:
        clarification = (
            f"To generate the schedule I need a couple of details:\n"
            + "\n".join(f"- {m}" for m in missing)
            + "\n\nFor 12-hour shifts, common patterns are: 2-2-3, DuPont, 4-4, 3-2-2-3.\n"
              "For 8-hour shifts, common patterns are: Southern Swing, 5-2-fixed, 6-2-rotating."
        )
        return {
            'success': False,
            'message': clarification,
            'file_path': None,
            'file_type': None,
            'needs_clarification': True,
            'clarification_message': clarification,
            'error': f"Missing parameters: {', '.join(missing)}",
        }

    meta = _PATTERN_REGISTRY.get(pattern_key)
    if not meta:
        clarification = (
            f"I don't recognize the pattern '{pattern_key}' for {shift_length}-hour shifts.\n\n"
            f"For 12-hour shifts, valid patterns are: 2-2-3, 2-3-2, 3-2-2-3, 4-3, 4-4, DuPont.\n"
            f"For 8-hour shifts, valid patterns are: Southern Swing, 5-2-fixed, "
            f"6-3-fixed, 6-2-rotating.\n\n"
            f"Which pattern would you like?"
        )
        return {
            'success': False,
            'message': clarification,
            'file_path': None,
            'file_type': None,
            'needs_clarification': True,
            'clarification_message': clarification,
            'error': f"Unrecognized pattern: {pattern_key}",
        }

    # Augment kb_context with a focused KB query if it's empty or sparse
    effective_kb = kb_context or ""
    if len(effective_kb.strip()) < 200:
        try:
            from knowledge_query_bridge import query_ingested_knowledge
            focused = query_ingested_knowledge(
                f"{pattern_key} schedule pattern {shift_length} hour shift crew rotation"
            ) or ""
            if focused:
                effective_kb = focused + "\n\n" + effective_kb
                print(f"🔍 [tool_router] Supplemented KB context: "
                      f"{len(focused)} chars for {pattern_key}")
        except Exception as kb_err:
            print(f"⚠️ [tool_router] KB supplementation failed (non-critical): {kb_err}")

    # -------------------------------------------------------------------------
    # LAYER 1: AI-DRIVEN GENERATION
    # -------------------------------------------------------------------------
    ai_crew_patterns = None
    ai_reasoning = ""
    ai_generation_attempted = False

    try:
        print(f"🤖 [tool_router] Layer 1: attempting AI-driven pattern generation "
              f"for {pattern_key} ({shift_length}hr)...")
        ai_generation_attempted = True

        ai_crew_patterns, ai_reasoning, ai_error = _generate_pattern_with_ai(
            shift_length=shift_length,
            pattern_key=pattern_key,
            meta=meta,
            kb_context=effective_kb,
            user_request=user_request,
        )

        if ai_error:
            print(f"⚠️ [tool_router] AI generation error: {ai_error} — falling back to hardcoded")
            ai_crew_patterns = None

        elif ai_crew_patterns:
            # Validate before using
            is_valid, validation_error = _validate_schedule_pattern(ai_crew_patterns, pattern_key)
            if is_valid:
                print(f"✅ [tool_router] AI pattern validated — using AI-generated pattern")
            else:
                print(f"⚠️ [tool_router] AI pattern failed validation: {validation_error} "
                      f"— falling back to hardcoded")
                ai_crew_patterns = None

    except Exception as ai_outer_err:
        import traceback
        print(f"⚠️ [tool_router] AI generation outer error: {traceback.format_exc()} "
              f"— falling back to hardcoded")
        ai_crew_patterns = None

    # -------------------------------------------------------------------------
    # LAYER 2: HARDCODED FALLBACK OR AI PATTERN — PASS TO EXCEL FORMATTER
    # -------------------------------------------------------------------------
    try:
        from schedule_generator import get_pattern_generator

        generator = get_pattern_generator()

        if ai_crew_patterns:
            # AI produced a validated pattern — inject it into the generator
            # PatternScheduleGenerator.create_schedule() accepts optional
            # override_crew_patterns parameter (added alongside this fix).
            # If the generator doesn't support it yet, it falls back gracefully.
            try:
                file_path = generator.create_schedule(
                    shift_length=shift_length,
                    pattern_key=pattern_key,
                    weeks_to_show=8,
                    override_crew_patterns=ai_crew_patterns,
                )
                generation_source = 'ai_generated'
                print(f"✅ [tool_router] Excel generated using AI-validated pattern: {file_path}")
            except TypeError:
                # Generator doesn't yet support override_crew_patterns — use default
                print(f"⚠️ [tool_router] Generator does not support override_crew_patterns "
                      f"— using hardcoded (upgrade schedule_generator.py to unlock)")
                file_path = generator.create_schedule(
                    shift_length=shift_length,
                    pattern_key=pattern_key,
                    weeks_to_show=8,
                )
                generation_source = 'hardcoded_fallback'
        else:
            # Layer 2: use hardcoded arrays
            if ai_generation_attempted:
                print(f"⚙️  [tool_router] Layer 2: using hardcoded pattern for {pattern_key}")
            file_path = generator.create_schedule(
                shift_length=shift_length,
                pattern_key=pattern_key,
                weeks_to_show=8,
            )
            generation_source = 'hardcoded'

        pattern_display = pattern_key.upper().replace('_', ' ')
        source_note = ""
        if generation_source == 'ai_generated':
            source_note = " (AI-generated from knowledge base)"
        elif generation_source == 'hardcoded_fallback':
            source_note = " (using verified pattern library)"
        else:
            source_note = " (using verified pattern library)"

        message = (
            f"Your {shift_length}-hour {pattern_display} schedule has been generated"
            f"{source_note}. "
            f"The Excel file shows 8 weeks of the repeating pattern with color-coded "
            f"shifts (Day = yellow, Night = blue, Off = grey). "
            f"Click the download button to save it."
        )

        if ai_reasoning and generation_source == 'ai_generated':
            message += f"\n\n**Pattern logic:** {ai_reasoning}"

        print(f"✅ [tool_router] Schedule complete: {file_path} (source: {generation_source})")

        return {
            'success': True,
            'message': message,
            'file_path': file_path,
            'file_type': 'xlsx',
            'needs_clarification': False,
            'clarification_message': None,
            'error': None,
            'shift_length': shift_length,
            'pattern_key': pattern_key,
            'ai_generated': generation_source == 'ai_generated',
            'generation_source': generation_source,
        }

    except ValueError as ve:
        clarification = (
            f"I wasn't able to generate that schedule: {str(ve)}\n\n"
            f"For 12-hour shifts, valid patterns are: 2-2-3, 2-3-2, 3-2-2-3, 4-3, 4-4, DuPont.\n"
            f"For 8-hour shifts, valid patterns are: Southern Swing, 5-2-fixed, "
            f"6-3-fixed, 6-2-rotating.\n\n"
            f"Which pattern and shift length would you like?"
        )
        return {
            'success': False,
            'message': clarification,
            'file_path': None,
            'file_type': None,
            'needs_clarification': True,
            'clarification_message': clarification,
            'error': str(ve),
        }

    except Exception as e:
        import traceback
        print(f"⚠️ [tool_router] Schedule generator failed: {traceback.format_exc()}")
        return {
            'success': False,
            'message': (
                f"I tried to generate the {pattern_key} schedule but encountered a "
                f"technical issue. Please try again, or I can describe the pattern "
                f"in detail if that would help."
            ),
            'file_path': None,
            'file_type': None,
            'needs_clarification': False,
            'clarification_message': None,
            'error': str(e),
        }


# =============================================================================
# RESEARCH AGENT TOOL
# =============================================================================

def _run_research_agent(tool_parameters, user_request, kb_context=""):
    """
    Invoke the research agent (Tavily web search) for current information.
    kb_context is accepted for signature compatibility but not used here
    (research agent is for current/external information, not internal KB).
    """
    try:
        from orchestration.task_analysis import call_research_agent

        query = (tool_parameters or {}).get('query') or user_request

        print(f"🔍 [tool_router] Research agent query: {query[:80]}...")

        result = call_research_agent(query)

        if result.get('error'):
            return {
                'success': False,
                'message': (
                    f"Web research is not available right now "
                    f"(TAVILY_API_KEY may not be configured). "
                    f"I'll answer based on my existing knowledge instead."
                ),
                'file_path': None,
                'file_type': None,
                'needs_clarification': False,
                'clarification_message': None,
                'error': result.get('content', 'Research agent unavailable'),
            }

        content = result.get('content', '')
        print(f"✅ [tool_router] Research agent returned {len(content)} chars")

        return {
            'success': True,
            'message': content,
            'file_path': None,
            'file_type': None,
            'needs_clarification': False,
            'clarification_message': None,
            'error': None,
        }

    except Exception as e:
        import traceback
        print(f"⚠️ [tool_router] Research agent failed: {traceback.format_exc()}")
        return {
            'success': False,
            'message': (
                "Web research encountered an error. "
                "I'll answer based on my existing knowledge instead."
            ),
            'file_path': None,
            'file_type': None,
            'needs_clarification': False,
            'clarification_message': None,
            'error': str(e),
        }


# =============================================================================
# MANUAL GENERATOR TOOL (STUB)
# =============================================================================

def _run_manual_generator(tool_parameters, user_request, kb_context=""):
    """
    Stub for implementation manual generator tool.
    """
    return {
        'success': False,
        'message': (
            "The implementation manual generator is available but needs to be "
            "wired into the tool router. To complete this integration, please "
            "share implementation_manual_generator.py so I can connect it properly."
        ),
        'file_path': None,
        'file_type': None,
        'needs_clarification': False,
        'clarification_message': None,
        'error': 'manual_generator not yet wired into tool_router',
    }


# =============================================================================
# MAIN DISPATCH FUNCTION
# =============================================================================

def execute_tool(tool_name, tool_parameters, user_request, kb_context=""):
    """
    Route a USE_TOOL decision to the appropriate internal tool.

    Args:
        tool_name (str): 'schedule_generator', 'research_agent', or 'manual_generator'.
        tool_parameters (dict|None): Parameters from the reasoning engine.
        user_request (str): The original user message.
        kb_context (str): Knowledge base context from orchestration_handler.py
            (_re_kb_context). Passed to schedule_generator so the AI has
            proprietary knowledge when generating patterns. Default "".

    Returns:
        dict with keys:
            'success', 'message', 'file_path', 'file_type',
            'needs_clarification', 'clarification_message', 'error'
        Plus tool-specific keys (e.g. 'shift_length', 'pattern_key',
        'ai_generated', 'generation_source').

    Never raises. Returns success=False with helpful message on any error.
    """
    if not tool_name:
        return {
            'success': False,
            'message': "No tool was specified. I'll answer with a text response instead.",
            'file_path': None,
            'file_type': None,
            'needs_clarification': False,
            'clarification_message': None,
            'error': 'tool_name is None or empty',
        }

    tool_name_lower = tool_name.lower().strip()

    print(f"🔧 [tool_router] Routing to tool: {tool_name_lower} "
          f"| params: {tool_parameters} "
          f"| kb_context: {len(kb_context)} chars")

    if tool_name_lower == 'schedule_generator':
        return _run_schedule_generator(tool_parameters, user_request, kb_context)

    elif tool_name_lower == 'research_agent':
        return _run_research_agent(tool_parameters, user_request, kb_context)

    elif tool_name_lower == 'manual_generator':
        return _run_manual_generator(tool_parameters, user_request, kb_context)

    else:
        return {
            'success': False,
            'message': (
                f"I don't recognize the tool '{tool_name}'. "
                f"Available tools are: schedule_generator, research_agent, "
                f"manual_generator. I'll answer with a text response instead."
            ),
            'file_path': None,
            'file_type': None,
            'needs_clarification': False,
            'clarification_message': None,
            'error': f"Unknown tool: {tool_name}",
        }


# I did no harm and this file is not truncated
