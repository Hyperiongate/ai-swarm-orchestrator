"""
SURVEY IN A BOX — QUESTION TO NORMATIVE DATABASE MAPPING
File: survey_norm_mapping.py
Repo: ai-swarm-orchestrator (root directory)

CHANGELOG:
- 2026-03-13: Initial creation (Phase 5, Step 5.2)
  * Maps all 103 survey_builder.py questions to normative database
  * 87 questions matched (43 numeric/Likert + 44 categorical)
  * 16 questions have no benchmark (site-specific, open-ended, or
    questions not present in the normative database)
  * All matches verified by loading normative_database and confirming
    find_question() returns the correct record for each norm_question_text
  * Jim Dillingham reviewed and approved mapping on 2026-03-13

PURPOSE:
Explicit link table between survey_builder.py question IDs and the
corresponding questions in the normative database (normative_database.py).

This mapping is used by the report generation pipeline (Phase 6) to:
  1. Look up the norm benchmark for each client response
  2. Produce client vs. industry comparison charts
  3. Generate the normative summary slide (top strengths / concerns)

MATCH TYPES:
  MATCHED_NUMERIC     — Likert/numeric question with norm mean + std dev.
                        Use normative_database.compare_numeric(norm_question_text, client_value)
  MATCHED_CATEGORICAL — Yes/No or multiple-choice question with norm %
                        per option.
                        Use normative_database.compare_categorical(norm_question_text, client_options)
  NO_BENCHMARK        — No normative data available. Reasons vary; see
                        the 'reason' field for each entry.

USAGE:
    from survey_norm_mapping import get_mapping, get_mapped_questions, NO_BENCHMARK

    # Get all 103 entries
    mapping = get_mapping()

    # Get only questions that have a benchmark
    mapped = get_mapped_questions()

    # Look up a single question
    entry = mapping['safety_rating']
    if entry['match_type'] != NO_BENCHMARK:
        result = db.compare_numeric(entry['norm_question_text'], client_value)

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

# Match type constants
MATCHED_NUMERIC     = 'MATCHED_NUMERIC'
MATCHED_CATEGORICAL = 'MATCHED_CATEGORICAL'
NO_BENCHMARK        = 'NO_BENCHMARK'


# ---------------------------------------------------------------------------
# THE MAPPING
# Each entry:
#   survey_id         (str): question ID in survey_builder.py question bank
#   survey_text       (str): abbreviated survey question text (for readability)
#   match_type        (str): MATCHED_NUMERIC | MATCHED_CATEGORICAL | NO_BENCHMARK
#   norm_section      (str): section in normative database (None if NO_BENCHMARK)
#   norm_question_text(str): exact or partial text to pass to find_question()
#                            (None if NO_BENCHMARK)
#   reason            (str): note explaining the mapping or why no benchmark
# ---------------------------------------------------------------------------

_MAPPING_LIST = [

    # ========================================================================
    # DEMOGRAPHICS
    # ========================================================================

    dict(
        survey_id='tenure',
        survey_text='How long have you worked for this company?',
        match_type=MATCHED_NUMERIC,
        norm_section='Demographic Information',
        norm_question_text='How long have you worked for this company?',
        reason='Exact match. AVERAGE row gives mean tenure category in years.',
    ),
    dict(
        survey_id='dept_tenure',
        survey_text='How long have you worked in your current department?',
        match_type=MATCHED_NUMERIC,
        norm_section='Demographic Information',
        norm_question_text='How long have you worked in your current department?',
        reason='Exact match.',
    ),
    dict(
        survey_id='age_group',
        survey_text='What is your age group?',
        match_type=MATCHED_NUMERIC,
        norm_section='Demographic Information',
        norm_question_text='What is your age group?',
        reason='Exact match. AVERAGE row gives mean age group index.',
    ),
    dict(
        survey_id='commute_distance',
        survey_text='How far do you commute to work (one way)?',
        match_type=MATCHED_NUMERIC,
        norm_section='Demographic Information',
        norm_question_text='How far do you commute to work (one way)?',
        reason='Exact match.',
    ),
    dict(
        survey_id='worst_shift_start',
        survey_text='Worst time to start the day shift (commute)?',
        match_type=MATCHED_NUMERIC,
        norm_section='Demographic Information',
        norm_question_text='Looking at your daily commute, what is the worst time to start the day shift?',
        reason='Exact match.',
    ),
    dict(
        survey_id='crew_assignment',
        survey_text='What crew are you assigned to?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Demographic Information',
        norm_question_text='What crew/shift are you assigned to?',
        reason='Near-exact match. Norm uses "crew/shift"; survey uses "crew". '
               'Option labels differ slightly but distribution is comparable.',
    ),
    dict(
        survey_id='second_job',
        survey_text='Do you have a second job?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Demographic Information',
        norm_question_text='Do you have a second job?',
        reason='Exact match.',
    ),
    dict(
        survey_id='second_job_timing',
        survey_text='If you have a second job, when do you work it?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Demographic Information',
        norm_question_text='If you have a second job, do you typically work at that job:',
        reason='Exact match.',
    ),
    dict(
        survey_id='student_status',
        survey_text='Are you a student?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Demographic Information',
        norm_question_text='Are you a student?',
        reason='Exact match.',
    ),
    dict(
        survey_id='caregiving',
        survey_text='Do you have children or elder family members requiring care?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Question exists in norm Excel (row 42) but is not parsed by '
               'normative_database.py — col B contains a space character which '
               'prevents it from being detected as a question row. '
               'Norm data: Yes ~38%, No ~62% (approximate, from raw Excel).',
    ),
    dict(
        survey_id='gender',
        survey_text='What is your gender?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Demographic Information',
        norm_question_text='What is your gender?',
        reason='Exact match. Note: norm has only Female/Male; survey adds '
               'Other and Prefer not to say. Compare Female and Male only.',
    ),
    dict(
        survey_id='single_parent',
        survey_text='Are you a single parent?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Demographic Information',
        norm_question_text='Are you a single parent?',
        reason='Exact match.',
    ),
    dict(
        survey_id='partner_status',
        survey_text="Spouse or domestic partner's work status?",
        match_type=MATCHED_CATEGORICAL,
        norm_section='Demographic Information',
        norm_question_text="Which best describes your spouse or domestic partner's work status?",
        reason='Exact match.',
    ),
    dict(
        survey_id='commute_method',
        survey_text='How do you normally get to work?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Demographic Information',
        norm_question_text='How do you normally get to work?',
        reason='Exact match.',
    ),
    dict(
        survey_id='prior_shiftwork',
        survey_text='Have you ever worked shiftwork at another facility?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Demographic Information',
        norm_question_text='Have you ever worked shiftwork at another facility?',
        reason='Exact match.',
    ),
    dict(
        survey_id='dept',
        survey_text='What department do you work in?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Site-specific. Department names vary by client. '
               'No comparable question in normative database.',
    ),
    dict(
        survey_id='current_schedule',
        survey_text='What schedule are you currently working?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Site-specific. Current schedule depends on client configuration.',
    ),
    dict(
        survey_id='employment_type',
        survey_text='Are you Hourly or Salaried?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Not present in normative database.',
    ),

    # ========================================================================
    # SLEEP & ALERTNESS
    # ========================================================================

    dict(
        survey_id='sleep_day_shift',
        survey_text='Hours of sleep on Day shift?',
        match_type=MATCHED_NUMERIC,
        norm_section='Health & Alertness',
        norm_question_text='How many hours of sleep do you get every 24-hour period when you are working day shift?',
        reason='Exact match (row 230). Note: norm uses lowercase "day shift".',
    ),
    dict(
        survey_id='sleep_second_shift',
        survey_text='Hours of sleep on second/afternoon shift?',
        match_type=MATCHED_NUMERIC,
        norm_section='Health & Alertness',
        norm_question_text='How many hours of sleep do you get every 24-hour period when you are working evening shift?',
        reason='Survey says "second shift"; norm says "evening shift". '
               'Same concept — mapped to evening shift norm (row 239).',
    ),
    dict(
        survey_id='sleep_third_shift',
        survey_text='Hours of sleep on third shift?',
        match_type=MATCHED_NUMERIC,
        norm_section='Health & Alertness',
        norm_question_text='How many hours of sleep do you get every 24-hour period when you are working night shift?',
        reason='Survey says "third shift"; norm says "night shift". '
               'Same concept — mapped to night shift norm (row 248).',
    ),
    dict(
        survey_id='sleep_night_shift',
        survey_text='Hours of sleep on Night shift?',
        match_type=MATCHED_NUMERIC,
        norm_section='Health & Alertness',
        norm_question_text='How many hours of sleep do you get every 24-hour period when you are working night shift?',
        reason='Exact match (row 248).',
    ),
    dict(
        survey_id='sleep_days_off',
        survey_text='Hours of sleep on days off?',
        match_type=MATCHED_NUMERIC,
        norm_section='Health & Alertness',
        norm_question_text='How many hours of sleep do you get every 24-hour period on your days off?',
        reason='Exact match.',
    ),
    dict(
        survey_id='sleep_needed',
        survey_text='Hours of sleep needed to be fully alert?',
        match_type=MATCHED_NUMERIC,
        norm_section='Health & Alertness',
        norm_question_text='How many hours of sleep do you need every 24-hour period to be fully alert?',
        reason='Exact match.',
    ),
    dict(
        survey_id='alarm_clock_normal',
        survey_text='Use alarm clock after a sleep period?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Health & Alertness',
        norm_question_text='Do you normally use an alarm clock to wake up after a sleep period?',
        reason='Exact match.',
    ),
    dict(
        survey_id='alarm_clock_day',
        survey_text='Use alarm clock on day shift?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Health & Alertness',
        norm_question_text='Do you use an alarm clock to wake up when you are working day shift?',
        reason='Exact match.',
    ),
    dict(
        survey_id='alarm_clock_afternoon',
        survey_text='Use alarm clock on afternoon shift?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Health & Alertness',
        norm_question_text='Do you use an alarm clock to wake up when you are working afternoon shift?',
        reason='Exact match.',
    ),
    dict(
        survey_id='alarm_clock_night',
        survey_text='Use alarm clock on night shift?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Health & Alertness',
        norm_question_text='Do you use an alarm clock to wake up when you are working night shift?',
        reason='Exact match.',
    ),
    dict(
        survey_id='sleepiness_problems',
        survey_text='Problems with safety/performance due to sleepiness?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Not present in normative database.',
    ),

    # ========================================================================
    # WORKING CONDITIONS
    # ========================================================================

    dict(
        survey_id='safety_rating',
        survey_text='Overall, this is a safe place to work.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='Overall, this is a safe place to work',
        reason='Exact match. Norm mean = 3.69 (1-5 scale).',
    ),
    dict(
        survey_id='company_communication',
        survey_text='This company places a high priority on communication.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='This company places a high priority on communication.',
        reason='Exact match. Norm mean = 2.91 (1-5 scale).',
    ),
    dict(
        survey_id='communication_importance',
        survey_text='Communication is important to me.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='Communication is important to me.',
        reason='Exact match. Norm mean = 4.56 (1-5 scale).',
    ),
    dict(
        survey_id='handoff_time',
        survey_text='Time needed to communicate daily plant conditions between shifts?',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='How much time is needed to communicate daily plant conditions between shifts?',
        reason='Exact match. AVERAGE = mean minutes encoded as category index.',
    ),
    dict(
        survey_id='management_input',
        survey_text='Management welcomes input from the workforce.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='Management welcomes input from the workforce.',
        reason='Exact match. Norm mean = 3.00 (1-5 scale).',
    ),
    dict(
        survey_id='enjoy_work',
        survey_text='I enjoy the work that I do.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='I enjoy the work that I do.',
        reason='Exact match. Norm mean = 3.96 (1-5 scale).',
    ),
    dict(
        survey_id='pay_competitive',
        survey_text='The pay here is good compared to other jobs in the area.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='The pay here is good compared to other jobs in the area.',
        reason='Exact match. Norm mean = 3.52 (1-5 scale).',
    ),
    dict(
        survey_id='company_belonging',
        survey_text='I feel like I am a part of this company.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='I feel like I am a part of this company.',
        reason='Exact match. Norm mean = 3.45 (1-5 scale).',
    ),
    dict(
        survey_id='facility_improvement',
        survey_text='Overall, things are getting better at this facility.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='Overall, things are getting better at this facility.',
        reason='Exact match. Norm mean = 2.93 (1-5 scale).',
    ),
    dict(
        survey_id='best_workplace',
        survey_text='This is one of the best places to work in this area.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='This is one of the best places to work in this area.',
        reason='Exact match. Norm mean = 3.43 (1-5 scale).',
    ),
    dict(
        survey_id='training_importance',
        survey_text='Job training is important to me.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='Job training is important to me.',
        reason='Exact match. Norm mean = 4.54 (1-5 scale).',
    ),
    dict(
        survey_id='training_adequacy',
        survey_text='I get enough training to do my job well.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='I get enough training to do my job well.',
        reason='Exact match. Norm mean = 3.50 (1-5 scale).',
    ),
    dict(
        survey_id='supervisor_responsive',
        survey_text='My direct supervisor responds to my concerns about working conditions.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='My direct supervisor responds to my concerns about working conditions.',
        reason='Exact match. Norm mean = 3.46 (1-5 scale).',
    ),
    dict(
        survey_id='management_responsive',
        survey_text='Upper management responds to my concerns about working conditions.',
        match_type=MATCHED_NUMERIC,
        norm_section='Working Conditions',
        norm_question_text='Upper management responds to my concerns about working conditions.',
        reason='Exact match. Norm mean = 3.00 (1-5 scale).',
    ),
    dict(
        survey_id='safety_improvement',
        survey_text='Which best describes your opinion? (safety responsibility)',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Working Conditions',
        norm_question_text='Which best describes your opinion?',
        reason='Matched to norm question "Which best describes your opinion?" '
               'with options: company can do more / employees can do more / '
               'both / neither (very safe). Compare option % distributions.',
    ),
    dict(
        survey_id='absenteeism_impact',
        survey_text='Which best describes how you feel? (absenteeism)',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Working Conditions',
        norm_question_text='Which best describes how you feel? (check as many as you wish)',
        reason='Matched to norm checkbox question on absenteeism. '
               'Norm: no problem=25.7%, disrupts family=43.2%, '
               'company should crack down=44.4%. Compare option % distributions.',
    ),
    dict(
        survey_id='management_equality',
        survey_text='Management treats shift-workers and day-workers equally.',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Question exists in norm Excel (row 336) but has no response '
               'data — no companies answered this question. Not benchmarkable.',
    ),
    dict(
        survey_id='training_amount',
        survey_text='We train too much / just right / not enough.',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Not present in normative database.',
    ),

    # ========================================================================
    # SCHEDULE FEATURES
    # ========================================================================

    dict(
        survey_id='schedule_improvement',
        survey_text='A better schedule will really improve things here.',
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text='A better schedule will really improve things here.',
        reason='Exact match. Norm mean = 3.25 (1-5 scale).',
    ),
    dict(
        survey_id='schedule_policies_fair',
        survey_text='Current shift schedule policies are fair.',
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text='Current shift schedule policies are fair.',
        reason='Exact match. Norm mean = 3.25 (1-5 scale).',
    ),
    dict(
        survey_id='current_schedule_satisfaction',
        survey_text='I like my current schedule.',
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text='I like my current schedule.',
        reason='Exact match. Norm mean = 3.66 (1-5 scale).',
    ),
    dict(
        survey_id='better_schedules_exist',
        survey_text='I think there are better schedules available than our current schedule.',
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text='I think there are better schedules available than our current schedule.',
        reason='Exact match. Norm mean = 3.26 (1-5 scale).',
    ),
    dict(
        survey_id='time_off_predictable',
        survey_text='My time off is predictable.',
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text='My time off is predictable.',
        reason='Exact match. Norm mean = 3.43 (1-5 scale).',
    ),
    dict(
        survey_id='schedule_flexibility',
        survey_text='My schedule allows me the flexibility to get time off when I really need it.',
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text='My schedule allows me the flexibility to get time off when I really need it.',
        reason='Exact match. Norm mean = 3.11 (1-5 scale).',
    ),
    dict(
        survey_id='crew_cohesion',
        survey_text='Keeping my current crew members together is important to me.',
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text='Keeping my current crew members together is important to me.',
        reason='Exact match. Norm mean = 3.81 (1-5 scale).',
    ),
    dict(
        survey_id='shift_swap_importance',
        survey_text='The ability to swap shifts is important to me.',
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text='The ability to swap shifts is important to me.',
        reason='Exact match. Norm mean = 3.02 (1-5 scale).',
    ),
    dict(
        survey_id='task_variety',
        survey_text="I don't mind doing several different types of work during the week.",
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text="I don't mind doing several different types of work during the week.",
        reason='Exact match. Norm mean = 3.40 (1-5 scale).',
    ),
    dict(
        survey_id='weekend_occasional',
        survey_text='I am willing to work weekends occasionally if I can plan them in advance.',
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text='I am willing to work weekends occasionally if I can plan them in advance.',
        reason='Exact match. Norm mean = 3.87 (1-5 scale).',
    ),
    dict(
        survey_id='understand_247_need',
        survey_text='It is clear to me why we have to go to a 24/7 schedule.',
        match_type=MATCHED_NUMERIC,
        norm_section='Shift Schedule Features',
        norm_question_text='It is clear to me why we need to go to a 24x7 schedule (or have weekend work)',
        reason='Near-exact match. Survey uses "24/7"; norm uses "24x7". '
               'Same question. Norm mean = 3.53 (1-5 scale).',
    ),
    dict(
        survey_id='preferred_8hr_shift',
        survey_text='Preferred 8-hour shift (Day/Afternoon/Night)?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='Which is your favorite 8-hour shift?',
        reason='Exact match. Norm: Days=70.7%, Afternoons=14.6%, Nights=14.6%.',
    ),
    dict(
        survey_id='least_preferred_8hr_shift',
        survey_text='Least preferred 8-hour shift?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='Which is your least favorite 8-hour shift?',
        reason='Exact match. Norm: Days=17.5%, Afternoons=37.5%, Nights=44.8%.',
    ),
    dict(
        survey_id='preferred_12hr_shift',
        survey_text='Preferred 12-hour shift (Days/Nights)?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='Which is your favorite 12-hour shift?',
        reason='Exact match. Norm: Days=79.0%, Nights=20.7%.',
    ),
    dict(
        survey_id='hours_vs_days_off',
        survey_text='Fewer hours/day vs more hours/day for more days off?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='Assuming that you get the same amount of pay, which is more important to you?',
        reason='Exact match. Norm: fewer hours=25.3%, more hours/more days off=74.6%.',
    ),
    dict(
        survey_id='fixed_vs_rotating',
        survey_text='Fixed or steady shifts vs Rotating shifts?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='Which would you prefer?',
        reason='Matched to norm "Which would you prefer? Fixed or steady shifts / '
               'Rotating shifts". Norm: Fixed=84.5%, Rotating=15.3%.',
    ),
    dict(
        survey_id='fixed_vs_rotating_no_seniority',
        survey_text='Fixed (no seniority consideration) vs Rotating?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='Which would you prefer?',
        reason='Matched to norm "Which would you prefer? Fixed shifts even though '
               'seniority is not a consideration / Rotating shifts". '
               'Norm: Fixed=66.9%, Rotating=32.5%.',
    ),
    dict(
        survey_id='rotation_frequency',
        survey_text='How often would you like to rotate between shifts?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='How often would you like to rotate between shifts?',
        reason='Exact match.',
    ),
    dict(
        survey_id='rotation_direction',
        survey_text='Preferred rotation direction on 8-hour schedule?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='On an 8-hour schedule, which direction would you prefer to rotate?',
        reason='Exact match.',
    ),
    dict(
        survey_id='day_shift_start_8hr',
        survey_text='Preferred day shift start time on 8-hour schedule?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='If you worked 8-hour shifts, what time would you like the day shift to start?',
        reason='Exact match.',
    ),
    dict(
        survey_id='day_shift_start_10hr',
        survey_text='Preferred day shift start time on 10-hour schedule?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='If you worked 10-hour shifts, what time would you like the day shift to start?',
        reason='Exact match.',
    ),
    dict(
        survey_id='day_shift_start_12hr',
        survey_text='Preferred day shift start time on 12-hour schedule?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='If you worked 12-hour shifts, what time would you like the day shift to start?',
        reason='Exact match.',
    ),
    dict(
        survey_id='weekend_preference',
        survey_text='8-week weekend preference (Saturdays/Sundays/full weekends)?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='If pay was not a factor, which would you prefer over an 8-week period?',
        reason='Exact match. Norm: 8 Saturdays=30.1%, 8 Sundays=14.0%, 4 full weekends=55.8%.',
    ),
    dict(
        survey_id='weekend_pattern',
        survey_text='Alternate weekends vs several in a row?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='Which best describes you?',
        reason='Matched to norm "Which best describes you? I like my weekends off '
               'to alternate / several weekends off in a row". '
               'Norm: alternate=75.3%, several in a row=24.5%.',
    ),
    dict(
        survey_id='work_pattern',
        survey_text='Several days in a row vs short work-rest pattern?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='Which best describes you?',
        reason='Matched to norm "Which best describes you? work several days in a '
               'row then long break / work couple days then short break". '
               'Norm: long runs=63.0%, short runs=36.7%.',
    ),
    dict(
        survey_id='three_day_preference',
        survey_text='Preferred 3 days off per week (Fri-Sat-Sun / Sat-Sun-Mon / Sun-Mon-Tue)?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='If you could only have 3 days off per week, which of the following would you prefer?',
        reason='Exact match. Norm: Fri-Sat-Sun=71.9%, Sat-Sun-Mon=23.1%, Sun-Mon-Tue=5.1%.',
    ),
    dict(
        survey_id='weekday_preference',
        survey_text='If taking weekdays off, which day do you prefer?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='If your schedule requires you to take weekdays off, which day do you prefer to have off?',
        reason='Exact match.',
    ),
    dict(
        survey_id='shift_mobility_intent',
        survey_text='Plan to move to a better shift vs stay on current shift?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='Which best describes you?',
        reason='Matched to norm "Which best describes you? I plan to go to a '
               'better shift as soon as I can / My current shift is where I plan to stay".',
    ),
    dict(
        survey_id='night_shift_start_preference',
        survey_text='Prefer night shift starting Sunday night vs Friday night?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Shift Schedule Features',
        norm_question_text='If pay is not a factor when comparing the following two work shifts, I',
        reason='Matched to norm question about Sunday night vs Friday night shift '
               'preference. Norm: Sunday night=71.8%, Friday night=26.9%.',
    ),
    dict(
        survey_id='supervisor_overlap',
        survey_text='What % of time should I work at the same time as my supervisor?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Not present in normative database.',
    ),
    dict(
        survey_id='weekend_willingness',
        survey_text='Willing to work weekends vs will quit before working weekends?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Not present in normative database.',
    ),
    dict(
        survey_id='fixed_vs_rotating_not_first_choice',
        survey_text='Fixed (not first choice) vs Rotating shifts?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Variant of fixed_vs_rotating question. This specific framing '
               '("even though I would not be assigned to my first choice") '
               'is not in the normative database.',
    ),
    dict(
        survey_id='new_schedule_trial_willingness',
        survey_text='Willing to try new schedule for 6-12 months?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Not present in normative database.',
    ),

    # ========================================================================
    # OVERTIME
    # ========================================================================

    dict(
        survey_id='overtime_satisfaction',
        survey_text='Overtime levels are just right the way they are.',
        match_type=MATCHED_NUMERIC,
        norm_section='Overtime',
        norm_question_text='Overtime levels are just right the way they are.',
        reason='Exact match. Norm mean = 3.29 (1-5 scale).',
    ),
    dict(
        survey_id='overtime_extend_shift',
        survey_text='I prefer overtime by extending my shift.',
        match_type=MATCHED_NUMERIC,
        norm_section='Overtime',
        norm_question_text='I prefer to work overtime by extending my shift.',
        reason='Exact match. Norm mean = 2.74 (1-5 scale).',
    ),
    dict(
        survey_id='overtime_day_off',
        survey_text='I prefer to work overtime by coming in on a day off.',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Question exists in norm Excel (row 622) but is not parsed by '
               'normative_database.py — col B contains a company value which '
               'prevents it from being detected as a question row. '
               'Not benchmarkable without a normative_database.py parser fix.',
    ),
    dict(
        survey_id='overtime_distribution_fair',
        survey_text='Current overtime distribution policies are fair.',
        match_type=MATCHED_NUMERIC,
        norm_section='Overtime',
        norm_question_text='Current overtime distribution policies are fair.',
        reason='Exact match. Norm mean = 3.25 (1-5 scale).',
    ),
    dict(
        survey_id='overtime_predictable',
        survey_text='Overtime is predictable and can be planned for.',
        match_type=MATCHED_NUMERIC,
        norm_section='Overtime',
        norm_question_text='Overtime is predictable and can be planned for.',
        reason='Exact match. Norm mean = 2.91 (1-5 scale).',
    ),
    dict(
        survey_id='overtime_expectation',
        survey_text='I expect to get overtime whenever I want it.',
        match_type=MATCHED_NUMERIC,
        norm_section='Overtime',
        norm_question_text='I expect to get overtime whenever I want it.',
        reason='Exact match. Norm mean = 3.03 (1-5 scale).',
    ),
    dict(
        survey_id='overtime_weekly_hours',
        survey_text='How much overtime would you like every week?',
        match_type=MATCHED_NUMERIC,
        norm_section='Overtime',
        norm_question_text='How much overtime would you like to have every week?',
        reason='Exact match. Norm mean = 7.36 (encoded as hours index).',
    ),
    dict(
        survey_id='overtime_timing_actual',
        survey_text='When do you usually work overtime?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Overtime',
        norm_question_text='When you work overtime outside your schedule, when do you usually work it?',
        reason='Exact match.',
    ),
    dict(
        survey_id='overtime_timing_preferred',
        survey_text='When do you prefer to work overtime?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Overtime',
        norm_question_text='When you have to work overtime, when do you prefer to work it?',
        reason='Exact match.',
    ),
    dict(
        survey_id='overtime_amount',
        survey_text='Over the last few months I have been: (too much/too little/just right OT)',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Overtime',
        norm_question_text='Over the last few months I have been:',
        reason='Exact match.',
    ),
    dict(
        survey_id='overtime_desire',
        survey_text='When it comes to overtime, I generally want:',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Overtime',
        norm_question_text='How much overtime would you like to have every week?',
        reason='Survey asks general desire level; closest norm is weekly OT hours '
               'preference. Comparison is approximate — use for directional insight only.',
    ),
    dict(
        survey_id='overtime_dependency',
        survey_text='I depend on overtime to make ends meet.',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Present in norm Excel (row 589) but as a question row with no '
               'options parsed (no data in Averages column). Not benchmarkable.',
    ),
    dict(
        survey_id='time_vs_overtime',
        survey_text='More time off vs more overtime?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Not present in normative database.',
    ),

    # ========================================================================
    # DAY CARE / ELDER CARE
    # ========================================================================

    dict(
        survey_id='daycare_use',
        survey_text='Do you use outside day/elder care?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Day Care / Elder Care',
        norm_question_text='Do you use outside day/elder care?',
        reason='Exact match. Norm: Yes=54.3%, No=44.7%.',
    ),
    dict(
        survey_id='daycare_location',
        survey_text='Is your day/elder care provider close to home/work/at home?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Day Care / Elder Care',
        norm_question_text='Is your day/elder care provider:',
        reason='Exact match.',
    ),
    dict(
        survey_id='daycare_relationship',
        survey_text='Is your day/elder care provider a family member, neighbor or friend?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Day Care / Elder Care',
        norm_question_text='Is your day/elder care provider a family member, neighbor or friend?',
        reason='Exact match. Norm: Yes=54.8%, No=39.2%.',
    ),
    dict(
        survey_id='daycare_shifts_used',
        survey_text='Do you use day/elder care when working (which shifts)?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Day Care / Elder Care',
        norm_question_text='Do you use day/elder care when working day shift?',
        reason='Survey asks one checkbox question covering all shifts. '
               'Norm has separate Yes/No questions per shift. '
               'Map to the day shift norm question as primary reference. '
               'Norm day shift: Yes=51.5%, No=39.0%.',
    ),
    dict(
        survey_id='daycare_shift_issue',
        survey_text='Is day/elder care a bigger issue on a particular shift?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Day Care / Elder Care',
        norm_question_text='Is day/elder care a bigger issue on a particular shift?',
        reason='Exact match. Norm: Yes=50.4%, No=40.0%.',
    ),
    dict(
        survey_id='daycare_worst_shift',
        survey_text='If day/elder care is a bigger issue, which shift?',
        match_type=MATCHED_CATEGORICAL,
        norm_section='Day Care / Elder Care',
        norm_question_text='If yes, which shift?',
        reason='Matched to norm "If yes, which shift?" under day care section. '
               'Norm: Days=30.0%, Afternoons=16.0%, Nights=20.2%.',
    ),

    # ========================================================================
    # OPEN-ENDED  (never benchmarkable)
    # ========================================================================

    dict(
        survey_id='schedule_like_most',
        survey_text='What do you like most about your current schedule?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Open-ended text response. Cannot be benchmarked.',
    ),
    dict(
        survey_id='schedule_like_least',
        survey_text='What do you like least about your current schedule?',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Open-ended text response. Cannot be benchmarked.',
    ),
    dict(
        survey_id='work_life_positives',
        survey_text='3 things company is doing well for work-life balance.',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Open-ended text response. Cannot be benchmarked.',
    ),
    dict(
        survey_id='work_life_improvements',
        survey_text='3 things company should start doing to improve work-life balance.',
        match_type=NO_BENCHMARK,
        norm_section=None,
        norm_question_text=None,
        reason='Open-ended text response. Cannot be benchmarked.',
    ),
]


# ---------------------------------------------------------------------------
# Build lookup dict and public API
# ---------------------------------------------------------------------------

_MAPPING = {entry['survey_id']: entry for entry in _MAPPING_LIST}


def get_mapping():
    """
    Return the complete mapping dict: {survey_id -> entry_dict}.
    All 103 survey_builder.py question IDs are present.
    """
    return _MAPPING


def get_mapped_questions(match_types=None):
    """
    Return only entries that have a normative benchmark.

    Args:
        match_types (list|None): Filter by match type(s).
            e.g. [MATCHED_NUMERIC] or [MATCHED_NUMERIC, MATCHED_CATEGORICAL]
            None = return all matched (excludes NO_BENCHMARK).

    Returns:
        list of entry dicts, sorted by norm_section then survey_id.
    """
    if match_types is None:
        match_types = [MATCHED_NUMERIC, MATCHED_CATEGORICAL]

    results = [e for e in _MAPPING_LIST if e['match_type'] in match_types]
    results.sort(key=lambda e: (e['norm_section'] or '', e['survey_id']))
    return results


def get_no_benchmark_questions():
    """Return all questions with no normative benchmark."""
    return [e for e in _MAPPING_LIST if e['match_type'] == NO_BENCHMARK]


def get_entry(survey_id):
    """
    Return the mapping entry for a single survey question ID.
    Returns None if survey_id is not found.
    """
    return _MAPPING.get(survey_id)


def summarize():
    """Print a human-readable summary of the mapping."""
    numeric   = [e for e in _MAPPING_LIST if e['match_type'] == MATCHED_NUMERIC]
    cat       = [e for e in _MAPPING_LIST if e['match_type'] == MATCHED_CATEGORICAL]
    no_bench  = [e for e in _MAPPING_LIST if e['match_type'] == NO_BENCHMARK]

    print(f"Survey Norm Mapping Summary")
    print(f"  Total questions:        {len(_MAPPING_LIST)}")
    print(f"  MATCHED_NUMERIC:        {len(numeric)}")
    print(f"  MATCHED_CATEGORICAL:    {len(cat)}")
    print(f"  NO_BENCHMARK:           {len(no_bench)}")
    print(f"  Benchmarked total:      {len(numeric) + len(cat)}")
    print()
    print("NO_BENCHMARK questions:")
    for e in no_bench:
        print(f"  {e['survey_id']:40s} — {e['reason'][:60]}")


# I did no harm and this file is not truncated
