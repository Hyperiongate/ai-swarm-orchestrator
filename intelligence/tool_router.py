"""
intelligence/tool_router.py
AI Swarm Orchestrator — Phase 4: Tool Router
Created: March 08, 2026
Last Updated: March 08, 2026 — Initial build (Phase 4)

CHANGELOG:
- March 08, 2026: Phase 4 initial build
  NEW FILE. Handles the USE_TOOL decision from reasoning_engine.py.
  When the reasoning engine decides a request needs a specific tool
  rather than a text response, this module routes to the correct tool
  and returns a standardized result dict.

  SUPPORTED TOOLS:
    schedule_generator — calls PatternScheduleGenerator.create_schedule()
      from schedule_generator.py (already callable, confirmed from file).
      Requires: shift_length (8 or 12) and pattern_key in tool_parameters.
      If parameters are missing, returns NEEDS_CLARIFICATION so the user
      is asked for what's needed before generation runs.

    research_agent — calls call_research_agent() from task_analysis.py.
      Extracts the research query from the user_request.
      Returns the research results as text.

    manual_generator — stub. Returns a message asking for the file.
      Will be wired in when implementation_manual_generator.py is shared.

  RETURN FORMAT:
    All execute_tool() calls return a dict:
      'success'     (bool)
      'message'     (str)   — human-readable description of what happened
      'file_path'   (str|None) — path to generated file, if any
      'file_type'   (str|None) — 'xlsx', 'docx', etc.
      'needs_clarification' (bool) — True if parameters were missing
      'clarification_message' (str|None) — what to ask the user
      'error'       (str|None) — error detail if success is False

  FALLBACK: If the tool fails for any reason, returns success=False with
  a helpful error message. The caller (orchestration_handler.py) falls
  back to a text response using the AI.

  DO NO HARM: This file imports nothing at module level that could break
  the app on startup. All imports are inside the functions that need them,
  wrapped in try/except.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""


# =============================================================================
# PATTERN KEY NORMALIZER
# Handles case/spacing variations so "DuPont", "du pont", "dupont" all work.
# =============================================================================

_VALID_12HR_PATTERNS = {'2-2-3', '2-3-2', '3-2-2-3', '4-3', '4-4', 'dupont'}
_VALID_8HR_PATTERNS  = {'5-2-fixed', '6-3-fixed', 'southern_swing', '6-2-rotating'}


def _normalize_pattern_key(raw):
    """
    Normalize a pattern key string to the canonical form used by
    schedule_generator.py.

    Returns normalized key string, or None if raw is empty/None.
    """
    if not raw:
        return None
    key = str(raw).lower().strip().replace(' ', '_').replace('/', '-')

    # Exact match
    if key in _VALID_12HR_PATTERNS or key in _VALID_8HR_PATTERNS:
        return key

    # Fuzzy matches for common variations
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

    # Pass through — schedule_generator will raise a clear error if invalid
    return key


# =============================================================================
# SCHEDULE GENERATOR TOOL
# =============================================================================

def _run_schedule_generator(tool_parameters, user_request):
    """
    Invoke PatternScheduleGenerator.create_schedule() with parameters
    extracted by the reasoning engine.

    Expected tool_parameters keys:
        shift_length  (int|str): 8 or 12
        pattern_key   (str):     e.g. '2-2-3', 'dupont', '4-4'

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

    # --- Generate the schedule ---
    try:
        from schedule_generator import get_pattern_generator

        generator = get_pattern_generator()
        file_path = generator.create_schedule(
            shift_length=shift_length,
            pattern_key=pattern_key,
            weeks_to_show=8,
        )

        pattern_display = pattern_key.upper().replace('_', ' ')
        message = (
            f"Your {shift_length}-hour {pattern_display} schedule has been generated. "
            f"The Excel file shows 8 weeks of the repeating pattern with color-coded "
            f"shifts (Day = yellow, Night = blue, Off = grey). "
            f"Click the download button to save it."
        )

        print(f"✅ [tool_router] Schedule generated: {file_path}")

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
        }

    except ValueError as ve:
        # Invalid shift_length or pattern_key — ask for clarification
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
                f"I tried to generate the schedule but encountered a technical issue. "
                f"Here is what I know about the {pattern_key} pattern for {shift_length}-hour shifts: "
                f"it is a {shift_length}-hour rotating schedule. I'd recommend trying again, "
                f"or I can describe the pattern in detail if that would help."
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

def _run_research_agent(tool_parameters, user_request):
    """
    Invoke the research agent (Tavily web search) for current information.
    Uses call_research_agent() from orchestration/task_analysis.py.

    Returns standard tool result dict.
    """
    try:
        from orchestration.task_analysis import call_research_agent

        # Use the user_request as the research query directly
        # The reasoning engine will have already determined this needs research
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
# Will be fully wired when implementation_manual_generator.py is shared.
# =============================================================================

def _run_manual_generator(tool_parameters, user_request):
    """
    Stub for implementation manual generator tool.
    Returns a helpful message until the file is shared and integrated.
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

def execute_tool(tool_name, tool_parameters, user_request):
    """
    Route a USE_TOOL decision to the appropriate internal tool.

    Args:
        tool_name (str): 'schedule_generator', 'research_agent',
                         or 'manual_generator'.
        tool_parameters (dict|None): Parameters extracted by the reasoning
                         engine from the user's request.
        user_request (str): The original user message (used as fallback
                         for tool queries).

    Returns:
        dict with keys:
            'success'              (bool)
            'message'              (str)
            'file_path'            (str|None)
            'file_type'            (str|None)
            'needs_clarification'  (bool)
            'clarification_message' (str|None)
            'error'                (str|None)
        Plus any tool-specific keys (e.g. 'shift_length', 'pattern_key').

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
          f"| params: {tool_parameters}")

    if tool_name_lower == 'schedule_generator':
        return _run_schedule_generator(tool_parameters, user_request)

    elif tool_name_lower == 'research_agent':
        return _run_research_agent(tool_parameters, user_request)

    elif tool_name_lower == 'manual_generator':
        return _run_manual_generator(tool_parameters, user_request)

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
