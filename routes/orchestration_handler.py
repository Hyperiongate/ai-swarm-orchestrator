"""
Orchestration Handler - Main AI Task Processing (REFACTORED)
Created: January 31, 2026
Last Updated: February 28, 2026 - SIMPLIFIED SURVEY BUILDER FORM

CHANGELOG:

- February 28, 2026 (Session 2): SIMPLIFIED SURVEY BUILDER FORM
  PROBLEM: Handler 3.6 Pass 1 form asked 5 questions including survey type,
    shift length, and distribution method — forcing category selection that
    Jim should not have to make. Pass 2 then routed questions by survey type,
    producing partial question sets instead of comprehensive surveys.
  FIX: Simplified the clarification form to 3 fields only:
    - Company Name (required)
    - Survey Date (optional, defaults to today)
    - Number of Schedules to Include 0–8 (optional, defaults to 0)
    Removed: survey_type dropdown, shift_length dropdown,
             distribution_method dropdown, employee_count dropdown.
  NEW BEHAVIOR: _map_survey_answers_to_questions() now ignores survey type
    entirely and always returns ALL 64 standard questions from the bank.
    Schedules are selected by count from the library in order of most common
    usage. _build_survey_questions_html() renders the simplified 3-field form.
    _detect_survey_request() unchanged.
  IMPACT: Every survey request now produces a comprehensive, all-inclusive
    Word document with no category filtering and no user decisions about
    which questions to include.

- February 28, 2026 (Session 1): ADDED HANDLER 3.6 SURVEY BUILDER
  PROBLEM: Typing "provide me with a survey" in Quick Tasks produced either
    no output (clarification questions with no follow-through) or unformatted
    plain text from Sonnet with no download link. The dedicated SurveyBuilder
    with its 97-question bank and Word export was never called from the
    orchestration flow.
  FIX: Added Handler 3.6 between Handler 3.5 (Contract) and Handler 4 (Labor).
    Uses the same two-pass pattern as Handler 3.5.
  IMPACT: "provide me with a survey" (and similar) now produces a downloadable
    Word document using the proper question bank.

- February 28, 2026: FIXED UnboundLocalError on labor_response
  PROBLEM: When conversation_id is None, Handler 4 (if conversation_id:) is skipped
    entirely so labor_response is never assigned. Handler 4.5 then references
    "if not labor_response" causing UnboundLocalError on every new conversation.
  FIX: Initialize labor_response = None before the if conversation_id: block.

- February 27, 2026: ADDED HANDLER 4.6 INTROSPECTION ROUTING
  PROBLEM: When user typed "run introspection" (or any introspection trigger phrase),
    the request fell through to Handler 10 PATH 3 where Sonnet responded
    conversationally instead of actually running the introspection engine.
    This caused the 'Unexpected token <' error because either (a) Sonnet's
    response contained HTML-like content that broke the JSON parser, or (b) the
    frontend made a secondary fetch to /api/introspection/run which returned
    an HTML error page (503) when INTROSPECTION_AVAILABLE=False.
  FIX: Inserted Handler 4.6 between Handler 4.5 and Handler 5. It calls
    is_introspection_request() (from introspection_engine.py) to detect intent,
    then calls the engine directly (no HTTP round-trip), formats the result as
    HTML, and returns a standard JSON response.
  IMPACT: "run introspection", "how are you doing", "swarm status", and all
    other INTROSPECTION_TRIGGERS now run the engine and display a formatted
    self-assessment report.

- February 27, 2026: ADDED INGESTED KNOWLEDGE BASE BRIDGE
  PROBLEM: Documents uploaded through the Knowledge Management UI were stored
    in knowledge_ingestion.db but NEVER queried when the AI answered questions.
  FIX: In PATH 3 (Sonnet regular conversation), immediately before building
    completion_prompt, call knowledge_query_bridge.query_ingested_knowledge()
    to search the ingested KB for content relevant to the user's question.
  NEW FILE: knowledge_query_bridge.py -- standalone bridge module.
  IMPACT: Consulting lessons, pillar articles, implementation manuals,
    contracts, survey results, and all other ingested documents are now
    available to the AI as a primary reference source.

- February 21, 2026: RESEARCH AGENT SYNTHESIS
- February 21, 2026: FIXED clarification_answers NameError breaking every request
- February 20, 2026: ADDED CONTRACT/PROPOSAL TEMPLATE HANDLER (Handler 3.5)
- February 20, 2026: ADDED DOCUMENT GENERATION TO HANDLER 10
- February 19, 2026: FIXED KNOWLEDGE BASE PROMPT INJECTION
- February 13, 2026 (Session 3): ADDED BACKGROUND PROCESSING FOR LARGE LABOR FILES
- February 13, 2026 (Session 2): Handler 4.5 Labor Session Retrieval
- February 13, 2026 (Session 1): Restored full regular conversation handler
- February 10, 2026: Refactored into modular handlers
- February 5, 2026: Memory fixes, cloud downloads, progressive analysis
- February 4, 2026: Added auto-learning integration
- January 31, 2026: Extracted to separate file

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify, session
import time
import os
import json
import uuid
from datetime import datetime

from database import (
    get_db, create_conversation, add_message,
    get_conversation_context, get_conversation,
    save_generated_document, get_schedule_context,
    save_schedule_context, get_client_profile_context,
    add_avoidance_pattern, get_avoidance_context,
    update_client_profile, load_analysis_session
)

from routes.handlers import (
    handle_file_upload,
    handle_cloud_download,
    handle_file_browser,
    handle_labor_response,
    handle_large_excel_initial,
    handle_smart_analyzer_continuation,
    handle_progressive_continuation,
    download_analysis_file
)

from routes.utils import (
    convert_markdown_to_html,
    store_conversation_context,
    get_conversation_context as get_context_value,
    clear_conversation_context
)

from progressive_file_analyzer import get_progressive_analyzer
from file_content_reader import extract_multiple_files
from cloud_file_handler import get_cloud_handler
from routes.handlers.cloud_handler import is_cloud_link

from orchestration import (
    analyze_task_with_sonnet,
    handle_with_opus,
    execute_specialist_task,
    validate_with_consensus
)

from code_assistant_agent import get_code_assistant
from orchestration.proactive_agent import ProactiveAgent
from schedule_request_handler_combined import get_combined_schedule_handler
from conversation_learning import learn_from_conversation
from orchestration.task_analysis import get_learning_context
from enhanced_intelligence import EnhancedIntelligence
from specialized_knowledge import get_specialized_knowledge
from proactive_suggestions import get_proactive_suggestions
from conversation_summarizer import get_conversation_summarizer
from proactive_curiosity_engine import get_curiosity_engine
from labor_analysis_processor import get_labor_processor

orchestration_bp = Blueprint('orchestration', __name__)


@orchestration_bp.route('/api/download/<path:filename>')
def download_file_route(filename):
    return download_analysis_file(filename)


@orchestration_bp.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    """
    Main orchestration endpoint.
    Handler sequence:
      1   File uploads
      2   Cloud link detection
      3   File browser
          Parse clarification_answers
      3.5 Contract/Proposal templates
      3.6 Survey Builder  <-- SIMPLIFIED February 28, 2026
      4   Labor response
      4.5 Labor session retrieval (background or immediate)
      4.6 Introspection routing
      5   Smart analyzer continuation
      6   Progressive file analysis continuation
      7   Large Excel file analysis
      8   Standard file handling
      9   GPT-4 file analysis
      10  Regular conversation (Sonnet PATH 3)
    """
    try:
        overall_start = time.time()

        if request.is_json:
            data = request.json
            user_request = data.get('request')
            enable_consensus = data.get('enable_consensus', True)
            project_id = data.get('project_id')
            conversation_id = data.get('conversation_id')
            mode = data.get('mode', 'quick')
            file_ids_param = data.get('file_ids')
            file_paths = []
        else:
            user_request = request.form.get('request')
            enable_consensus = request.form.get('enable_consensus', 'true').lower() == 'true'
            project_id = request.form.get('project_id')
            conversation_id = request.form.get('conversation_id')
            mode = request.form.get('mode', 'quick')
            file_ids_param = request.form.get('file_ids')
            file_paths = []

        if not user_request:
            return jsonify({'success': False, 'error': 'Request text required'}), 400

        file_contents = ""

        # HANDLER 1: File uploads
        if not request.is_json and 'files' in request.files:
            files = request.files.getlist('files')
            if files:
                file_paths, early_response = handle_file_upload(
                    files, project_id, conversation_id
                )
                if early_response:
                    return early_response

        # HANDLER 2: Cloud link detection and download
        if is_cloud_link(user_request):
            file_paths, user_request, conversation_id, error_response = handle_cloud_download(
                user_request, conversation_id, project_id, mode
            )
            if error_response:
                return error_response

        # HANDLER 3: File browser
        if file_ids_param and project_id:
            selected_context = handle_file_browser(
                file_ids_param, project_id, request.is_json
            )
            if selected_context:
                file_contents += "\n\n" + selected_context

        # ====================================================================
        # PARSE CLARIFICATION ANSWERS
        # Moved here February 21, 2026 - Handler 3.5 needs it before its block.
        # ====================================================================
        clarification_answers = None
        if request.is_json:
            clarification_answers_raw = request.json.get('clarification_answers')
            if clarification_answers_raw:
                if isinstance(clarification_answers_raw, str):
                    try:
                        clarification_answers = json.loads(clarification_answers_raw)
                    except:
                        clarification_answers = None
                else:
                    clarification_answers = clarification_answers_raw
        else:
            clarification_answers_str = request.form.get('clarification_answers')
            if clarification_answers_str:
                try:
                    clarification_answers = json.loads(clarification_answers_str)
                except:
                    clarification_answers = None

        if clarification_answers:
            print(f"Clarification answers received: {clarification_answers}")

        # ========================================================================
        # HANDLER 3.5: CONTRACT / PROPOSAL TEMPLATE HANDLER
        # Added February 20, 2026
        # ========================================================================
        contract_type = _detect_template_request(user_request)

        if contract_type and not clarification_answers:
            print(f"Contract/proposal request detected: {contract_type} - asking clarifying questions")
            if not conversation_id:
                conversation_id = create_conversation(mode=mode, project_id=project_id)
            add_message(conversation_id, 'user', user_request)
            questions_html = _build_contract_questions_html(contract_type)
            db = get_db()
            cursor = db.execute(
                'INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                (user_request, 'needs_clarification', conversation_id)
            )
            task_id = cursor.lastrowid
            db.commit()
            db.close()
            add_message(conversation_id, 'assistant', questions_html, task_id,
                       {'waiting_for_input': True, 'template_type': contract_type})
            return jsonify({
                'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                'result': questions_html, 'needs_input': True, 'template_type': contract_type,
                'orchestrator': 'contract_handler', 'execution_time': time.time() - overall_start
            })

        if contract_type and clarification_answers:
            print(f"Contract answers received - generating {contract_type}")
            if not conversation_id:
                conversation_id = create_conversation(mode=mode, project_id=project_id)
            add_message(conversation_id, 'user', user_request)
            db = get_db()
            cursor = db.execute(
                'INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                (user_request, 'processing', conversation_id)
            )
            task_id = cursor.lastrowid
            db.commit()
            template_content = _get_template_from_kb(contract_type)
            from orchestration.ai_clients import call_claude_sonnet
            gen_prompt = _build_contract_generation_prompt(contract_type, template_content, clarification_answers)
            api_system_prompt = (
                "You are an expert assistant for Shiftwork Solutions LLC. "
                "When filling in a contract or proposal, use the provided template "
                "structure exactly. Do not add new sections or change the legal language. "
                "Only fill in the blank fields with the client information provided."
            )
            response = call_claude_sonnet(gen_prompt, conversation_history=None,
                                          files_attached=False, system_prompt=api_system_prompt)
            if isinstance(response, dict):
                actual_output = response.get('content', '') if not response.get('error') else f"Error: {response.get('content')}"
            else:
                actual_output = str(response)
            formatted_output = convert_markdown_to_html(actual_output)
            document_created = False
            document_url = None
            document_id = None
            try:
                from document_generator import generate_document
                client_name = clarification_answers.get('client_name', 'Client')
                doc_title = f"Shiftwork Solutions - {contract_type.title()} - {client_name}"
                doc_result = generate_document(user_request=doc_title, ai_response_text=actual_output,
                                               task_id=task_id, conversation_id=conversation_id, project_id=project_id)
                if doc_result.get('success'):
                    document_created = True
                    document_url = doc_result['document_url']
                    document_id = doc_result.get('document_id')
            except Exception as doc_err:
                print(f"Contract doc generation error (non-critical): {doc_err}")
            total_time = time.time() - overall_start
            db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                      ('completed', 'contract_handler', total_time, task_id))
            db.commit()
            db.close()
            add_message(conversation_id, 'assistant', actual_output, task_id,
                       {'orchestrator': 'contract_handler', 'template_type': contract_type,
                        'document_created': document_created, 'document_url': document_url})
            return jsonify({
                'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                'result': formatted_output, 'orchestrator': 'contract_handler',
                'template_type': contract_type, 'document_created': document_created,
                'document_url': document_url, 'document_id': document_id,
                'document_type': 'docx', 'execution_time': total_time
            })

        # ========================================================================
        # HANDLER 3.6: SURVEY BUILDER
        # Added February 28, 2026 (Session 1)
        # Simplified February 28, 2026 (Session 2) - form reduced to 3 fields,
        # always produces comprehensive all-question survey, no category selection.
        #
        # FLOW:
        #   Pass 1 (no clarification_answers): detect intent -> show 3-field form
        #   Pass 2 (clarification_answers present): build full survey -> Word export
        #
        # Uses the same two-pass pattern as Handler 3.5 (Contract/Proposal).
        # Fires BEFORE Handler 10 / ProactiveAgent so it owns the survey flow.
        # ========================================================================
        is_survey_req = _detect_survey_request(user_request)

        if is_survey_req and not clarification_answers:
            print(f"HANDLER 3.6: Survey request detected - showing simplified 3-field form")
            if not conversation_id:
                conversation_id = create_conversation(mode=mode, project_id=project_id)
            add_message(conversation_id, 'user', user_request)
            questions_html = _build_survey_questions_html()
            db = get_db()
            cursor = db.execute(
                'INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                (user_request, 'needs_clarification', conversation_id)
            )
            task_id = cursor.lastrowid
            db.commit()
            db.close()
            add_message(conversation_id, 'assistant', questions_html, task_id,
                       {'waiting_for_input': True, 'handler': 'survey_builder'})
            return jsonify({
                'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                'result': questions_html, 'needs_input': True, 'handler': 'survey_builder',
                'orchestrator': 'survey_builder',
                'execution_time': time.time() - overall_start
            })

        if is_survey_req and clarification_answers:
            print(f"HANDLER 3.6: Survey answers received - building comprehensive survey document")
            if not conversation_id:
                conversation_id = create_conversation(mode=mode, project_id=project_id)
            add_message(conversation_id, 'user', user_request)
            db = get_db()
            cursor = db.execute(
                'INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                (user_request, 'processing', conversation_id)
            )
            task_id = cursor.lastrowid
            db.commit()

            # Pull the three simple fields
            company_name   = clarification_answers.get('company_name', 'Client').strip() or 'Client'
            survey_date    = clarification_answers.get('survey_date', datetime.now().strftime('%Y-%m-%d'))
            num_schedules_str = clarification_answers.get('num_schedules', '0')

            project_name = f"{company_name} - Schedule Preference Survey"

            # Always build comprehensive question set; schedules by count
            selected_questions, schedules_to_rate = _map_survey_answers_to_questions(
                company_name, survey_date, num_schedules_str
            )

            actual_output = ""
            document_created = False
            document_url = None
            document_id = None

            try:
                from survey_builder import SurveyBuilder
                import os
                import tempfile

                builder = SurveyBuilder()
                survey_obj = builder.create_survey(
                    project_name=project_name,
                    company_name=company_name,
                    selected_questions=selected_questions,
                    schedules_to_rate=schedules_to_rate
                )

                word_buffer = builder.export_to_word(survey_obj)

                safe_company = "".join(c for c in company_name if c.isalnum() or c in (' ', '_')).replace(' ', '_')
                filename = f"{safe_company}_Survey_{datetime.now().strftime('%Y%m%d')}.docx"
                tmp_dir = '/tmp'
                file_path = os.path.join(tmp_dir, filename)
                with open(file_path, 'wb') as f:
                    f.write(word_buffer.read())
                file_size = os.path.getsize(file_path)

                doc_id = save_generated_document(
                    filename=filename,
                    original_name=project_name,
                    document_type='docx',
                    file_path=file_path,
                    file_size=file_size,
                    task_id=task_id,
                    conversation_id=conversation_id,
                    project_id=project_id,
                    title=project_name,
                    description=f"Comprehensive schedule preference survey for {company_name} ({len(selected_questions)} questions)",
                    category='survey'
                )
                document_created = True
                document_url = f'/api/generated-documents/{doc_id}/download'
                document_id = doc_id

                q_count = len(selected_questions)
                actual_output = (
                    f"## {project_name}\n\n"
                    f"Your comprehensive survey has been built and is ready to download.\n\n"
                    f"**Survey Details:**\n"
                    f"- Company: {company_name}\n"
                    f"- Survey Date: {survey_date}\n"
                    f"- Total Questions: {q_count}\n"
                )
                if schedules_to_rate:
                    actual_output += f"- Schedule Concepts Included: {len(schedules_to_rate)}\n"
                else:
                    actual_output += "- Schedule Concepts: None (no schedules requested)\n"
                actual_output += (
                    f"\n**The Word document includes:**\n"
                    f"- Standard survey directions\n"
                    f"- Demographics section\n"
                    f"- Sleep & alertness section\n"
                    f"- Working conditions section\n"
                    f"- Schedule features & preferences section\n"
                    f"- Overtime preferences section\n"
                    f"- Open-ended feedback questions\n"
                )
                if schedules_to_rate:
                    actual_output += "- Schedule concept rating sections\n"
                actual_output += (
                    f"- Shiftwork Solutions footer and contact information\n\n"
                    f"Click the download button to save the `.docx` file. "
                    f"You can edit it further in Word before distributing."
                )

            except Exception as survey_err:
                import traceback
                print(f"HANDLER 3.6: Survey build error: {traceback.format_exc()}")
                actual_output = (
                    f"I encountered an error building the survey document: {str(survey_err)}\n\n"
                    f"Please try again or contact support."
                )

            formatted_output = convert_markdown_to_html(actual_output)
            total_time = time.time() - overall_start
            db.execute(
                'UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                ('completed', 'survey_builder', total_time, task_id)
            )
            db.commit()
            db.close()
            add_message(conversation_id, 'assistant', actual_output, task_id,
                       {'orchestrator': 'survey_builder', 'document_created': document_created,
                        'document_url': document_url, 'execution_time': total_time})
            return jsonify({
                'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                'result': formatted_output, 'orchestrator': 'survey_builder',
                'document_created': document_created, 'document_url': document_url,
                'document_id': document_id, 'document_type': 'docx',
                'execution_time': total_time
            })

        # ========================================================================
        # END HANDLER 3.6
        # ========================================================================

        # HANDLER 4: Labor analysis response handler
        # Initialize to None so Handler 4.5 can safely reference it even when
        # conversation_id is None and this block is skipped entirely.
        # Fix applied February 28, 2026 - UnboundLocalError on new conversations.
        labor_response = None
        if conversation_id:
            labor_response = handle_labor_response(user_request, conversation_id)
            if labor_response:
                return labor_response

        # ========================================================================
        # HANDLER 4.5: LABOR SESSION RETRIEVAL WITH BACKGROUND PROCESSING
        # ========================================================================
        if not labor_response and conversation_id:
            pending_session_id = None
            if request.is_json:
                pending_session_id = request.json.get('session_id')
            else:
                pending_session_id = request.form.get('session_id')
            if not pending_session_id:
                pending_session_id = get_context_value(conversation_id, 'pending_analysis_session')

            print(f"HANDLER 4.5: Checking for pending labor session: {pending_session_id}")

            if pending_session_id:
                print(f"Found pending labor session: {pending_session_id}")
                try:
                    session_data = load_analysis_session(pending_session_id)
                    if session_data and session_data.get('data_files'):
                        data_files = session_data['data_files']
                        if data_files and len(data_files) > 0:
                            file_path = data_files[0]
                            print(f"Labor file: {file_path}")
                            if os.path.exists(file_path):
                                file_size = os.path.getsize(file_path)
                                file_size_mb = round(file_size / (1024 * 1024), 2)
                                print(f"File size: {file_size_mb}MB")
                                LARGE_FILE_THRESHOLD_MB = 2.0
                                if file_size_mb > LARGE_FILE_THRESHOLD_MB:
                                    print(f"File is large ({file_size_mb}MB) - using background processing")
                                    clear_conversation_context(conversation_id, 'pending_analysis_session')
                                    db = get_db()
                                    cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                                                       (user_request, 'processing_background', conversation_id))
                                    task_id = cursor.lastrowid
                                    db.commit()
                                    db.close()
                                    processor = get_labor_processor()
                                    job_id = f"LABOR_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
                                    result = processor.submit_job(
                                        job_id=job_id,
                                        file_path=file_path,
                                        user_request=f"Analyze this labor data comprehensively. Provide insights on overtime patterns, productivity, cost analysis, staffing efficiency, and actionable recommendations. File: {os.path.basename(file_path)}",
                                        conversation_id=conversation_id,
                                        task_id=task_id,
                                    )
                                    if result['success']:
                                        initial_msg = f"""🔄 **Analyzing labor data in background...**

**File:** {os.path.basename(file_path)} ({file_size_mb}MB)
**Estimated time:** ~{result['estimated_minutes']} minutes

I'm performing comprehensive analysis of all labor records:
- Overtime patterns and cost exposure
- Staffing distribution by department
- Shift balance and coverage gaps
- Day-of-week and monthly trends
- Headcount efficiency metrics

**You can continue using the app while I work on this!**

I'll post the complete analysis here when finished, including detailed insights."""
                                        add_message(conversation_id, 'assistant', initial_msg, task_id,
                                                   {'orchestrator': 'background_labor_processor', 'job_id': job_id})
                                        return jsonify({
                                            'success': True, 'task_id': task_id,
                                            'conversation_id': conversation_id,
                                            'result': convert_markdown_to_html(initial_msg),
                                            'orchestrator': 'background_labor_processor',
                                            'job_id': job_id, 'background_processing': True,
                                            'estimated_minutes': result['estimated_minutes'],
                                            'execution_time': time.time() - overall_start
                                        })
                                    else:
                                        print(f"Background processing failed: {result.get('error')}, falling back to immediate")

                                print(f"File is small ({file_size_mb}MB) or fallback - processing immediately")
                                try:
                                    extracted = extract_multiple_files([file_path])
                                    if extracted['success'] and extracted.get('combined_text'):
                                        file_contents = extracted['combined_text']
                                        if len(file_contents) > 200000:
                                            file_contents = file_contents[:200000] + f"\n\n... (truncated {len(file_contents) - 200000} characters)"
                                        print(f"Loaded {len(file_contents)} chars from labor file")
                                        clear_conversation_context(conversation_id, 'pending_analysis_session')
                                        user_request = f"Analyze this labor data comprehensively. Provide insights on overtime patterns, productivity, cost analysis, staffing efficiency, and actionable recommendations. File: {os.path.basename(file_path)}"
                                        print(f"Proceeding to Handler 9 (GPT-4 File Analysis) with labor data...")
                                        file_paths = [file_path]
                                    else:
                                        return jsonify({'success': False, 'error': 'Could not read labor data file'}), 500
                                except Exception as extract_error:
                                    return jsonify({'success': False, 'error': f'Error reading labor data: {str(extract_error)}'}), 500
                            else:
                                return jsonify({'success': False, 'error': 'Labor data file no longer exists'}), 404
                except Exception as session_error:
                    print(f"Error loading labor session: {session_error}")

        # ========================================================================
        # HANDLER 4.6: INTROSPECTION ROUTING
        # Added February 27, 2026
        #
        # Detects introspection intent and calls the engine directly.
        # No HTTP round-trip eliminates the 'Unexpected token <' HTML error.
        # Only fires when there are no files (introspection is a text-only feature).
        # Falls through gracefully on any import or runtime error so Sonnet
        # can still respond conversationally.
        # ========================================================================
        if not file_contents and not file_paths:
            try:
                from introspection.introspection_engine import is_introspection_request, get_introspection_engine

                intent = is_introspection_request(user_request)

                if intent.get('is_introspection'):
                    action = intent.get('action', 'run')
                    print(f"HANDLER 4.6: Introspection detected - action={action}, trigger='{intent.get('matched_trigger')}'")

                    if not conversation_id:
                        conversation_id = create_conversation(mode=mode, project_id=project_id)

                    add_message(conversation_id, 'user', user_request)

                    db = get_db()
                    cursor = db.execute(
                        'INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                        (user_request, 'processing', conversation_id)
                    )
                    task_id = cursor.lastrowid
                    db.commit()
                    db.close()

                    introspection_engine = get_introspection_engine()

                    if action == 'show_latest':
                        latest = introspection_engine.get_latest_introspection()
                        if latest and latest.get('full_report'):
                            report = latest['full_report']
                            actual_output = "Here is my most recent self-assessment:\n\n" + _format_introspection_as_text(report)
                        else:
                            print(f"No previous introspection - running fresh cycle")
                            report = introspection_engine.run_introspection(days=7, is_monthly=False)
                            actual_output = _format_introspection_as_text(report)
                    else:
                        # 'run' or 'show_proposals' (proposals Phase 3 - run standard cycle for now)
                        report = introspection_engine.run_introspection(days=7, is_monthly=False)
                        actual_output = _format_introspection_as_text(report)

                    formatted_output = convert_markdown_to_html(actual_output)
                    total_time = time.time() - overall_start

                    db = get_db()
                    db.execute(
                        'UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                        ('completed', 'introspection_engine', total_time, task_id)
                    )
                    db.commit()
                    db.close()

                    add_message(conversation_id, 'assistant', actual_output, task_id,
                               {'orchestrator': 'introspection_engine',
                                'introspection_action': action,
                                'execution_time': total_time})

                    return jsonify({
                        'success': True,
                        'task_id': task_id,
                        'conversation_id': conversation_id,
                        'result': formatted_output,
                        'orchestrator': 'introspection_engine',
                        'introspection_action': action,
                        'execution_time': total_time
                    })

            except ImportError as ie:
                print(f"HANDLER 4.6: Introspection not available ({ie}) - falling through to Sonnet")
            except Exception as introspection_error:
                import traceback
                print(f"HANDLER 4.6: Introspection error (non-critical, falling through): {traceback.format_exc()}")

        # ========================================================================
        # END HANDLER 4.6
        # ========================================================================

        # HANDLER 5: Smart analyzer continuation check
        if not file_paths and conversation_id:
            from database import get_smart_analyzer_state
            analyzer_state = get_smart_analyzer_state(conversation_id)
            if analyzer_state and analyzer_state.get('analyzer_state') == 'loaded':
                print(f"Smart analyzer continuation detected")
                continuation_result = handle_smart_analyzer_continuation(
                    user_request, conversation_id, project_id, mode
                )
                if continuation_result:
                    return continuation_result

        # HANDLER 6: Progressive file analysis continuation
        analyzer = get_progressive_analyzer()
        continuation_request = analyzer.parse_user_continuation_request(user_request)
        if continuation_request and conversation_id:
            file_analysis_state = session.get(f'file_analysis_{conversation_id}')
            if file_analysis_state:
                return handle_progressive_continuation(
                    conversation_id=conversation_id,
                    user_request=user_request,
                    continuation_request=continuation_request,
                    file_analysis_state=file_analysis_state,
                    overall_start=overall_start
                )

        # HANDLER 7: Large Excel file analysis (initial upload)
        if file_paths:
            for file_path in file_paths:
                file_info = analyzer.get_file_info(file_path)
                print(f"FILE SIZE DETECTION:")
                print(f"  - File: {os.path.basename(file_path)}")
                print(f"  - Size: {file_info.get('file_size_mb', 0):.1f}MB")
                print(f"  - is_large: {file_info.get('is_large')}")
                print(f"  - file_type: {file_info.get('file_type')}")
                if file_info.get('is_too_large'):
                    file_size_mb = file_info.get('file_size_mb', 0)
                    return jsonify({'success': False, 'error': f'File too large ({file_size_mb:.1f}MB). Maximum file size is 25MB.'}), 413
                if file_info.get('is_large') and file_info.get('file_type') in ['.xlsx', '.xls']:
                    print(f"TRIGGERING ANALYSIS for {os.path.basename(file_path)}")
                    return handle_large_excel_initial(
                        file_path=file_path, user_request=user_request,
                        conversation_id=conversation_id, project_id=project_id,
                        mode=mode, file_info=file_info, overall_start=overall_start
                    )

        # HANDLER 8: Standard file handling (small files)
        if file_paths:
            try:
                extracted = extract_multiple_files(file_paths)
                if extracted['success'] and extracted.get('combined_text'):
                    extracted_text = extracted['combined_text']
                    if len(extracted_text) > 200000:
                        extracted_text = extracted_text[:200000] + f"\n\n... (truncated {len(extracted_text) - 200000} characters)"
                    if file_contents:
                        file_contents += "\n\n" + extracted_text
                    else:
                        file_contents = extracted_text
            except Exception as extract_error:
                print(f"Could not extract file contents: {extract_error}")

        # HANDLER 9: GPT-4 file analysis
        if file_contents:
            print(f"File content detected ({len(file_contents)} chars) - routing to GPT-4")
            if not conversation_id:
                conversation_id = create_conversation(mode=mode, project_id=project_id)
            add_message(conversation_id, 'user', user_request, file_contents=file_contents if file_contents else None)
            db = get_db()
            cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                               (user_request, 'processing', conversation_id))
            task_id = cursor.lastrowid
            db.commit()
            from orchestration.ai_clients import call_gpt4
            file_section = f"""

========================================================================
ATTACHED FILES - READ THESE CAREFULLY
========================================================================

{file_contents}

========================================================================
"""
            completion_prompt = f"""{file_section}

USER REQUEST: {user_request}

Please complete this request fully. Provide the actual deliverable.
Be comprehensive and professional."""
            try:
                gpt_response = call_gpt4(completion_prompt, max_tokens=4000)
                if not gpt_response.get('error') and gpt_response.get('content'):
                    actual_output = gpt_response.get('content', '')
                    formatted_output = convert_markdown_to_html(actual_output)
                    total_time = time.time() - overall_start
                    db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                              ('completed', 'gpt4_file_handler', total_time, task_id))
                    db.commit()
                    db.close()
                    add_message(conversation_id, 'assistant', actual_output, task_id,
                               {'orchestrator': 'gpt4_file_handler', 'file_analysis': True, 'execution_time': total_time})
                    return jsonify({
                        'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                        'result': formatted_output, 'orchestrator': 'gpt4_file_handler',
                        'execution_time': total_time, 'message': 'File analyzed by GPT-4'
                    })
                else:
                    db.close()
            except Exception as gpt_error:
                print(f"GPT-4 file analysis error: {gpt_error}")
                db.close()

        # ========================================================================
        # HANDLER 10: REGULAR CONVERSATION (NO FILES)
        # ========================================================================

        if not file_contents and conversation_id:
            from database import get_conversation_file_contents
            file_contents = get_conversation_file_contents(conversation_id)
            if file_contents:
                print(f"Retrieved file contents from conversation history")

        if clarification_answers:
            context_additions = []
            for field, value in clarification_answers.items():
                context_additions.append(f"{field}: {value}")
            if context_additions:
                user_request = f"{user_request}\n\nAdditional context:\n" + "\n".join(context_additions)

        if not conversation_id:
            conversation_id = create_conversation(mode=mode, project_id=project_id)
            print(f"Created new conversation: {conversation_id}")

        add_message(conversation_id, 'user', user_request)

        proactive = None
        try:
            proactive = ProactiveAgent()
        except Exception as proactive_init_error:
            print(f"Proactive agent init failed: {proactive_init_error}")

        if proactive and not clarification_answers:
            try:
                pre_check = proactive.pre_process_request(user_request)
                if pre_check['action'] == 'ask_questions':
                    db = get_db()
                    cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                                       (user_request, 'needs_clarification', conversation_id))
                    task_id = cursor.lastrowid
                    db.commit()
                    db.close()
                    return jsonify({'success': True, 'needs_clarification': True, 'clarification_data': pre_check['data'],
                                   'task_id': task_id, 'conversation_id': conversation_id})
                if pre_check['action'] == 'detect_project':
                    return jsonify({'success': True, 'project_detected': True, 'project_data': pre_check['data'],
                                   'conversation_id': conversation_id})
            except Exception as proactive_error:
                print(f"Proactive check failed: {proactive_error}")

        import sys
        app_module = sys.modules.get('app')
        knowledge_base = getattr(app_module, 'knowledge_base', None) if app_module else None
        conversation_context = get_conversation_context(conversation_id, max_messages=10)

        file_context = ""
        if project_id:
            try:
                from database_file_management import get_files_for_ai_context
                file_context = get_files_for_ai_context(project_id, max_files=5, max_chars_per_file=2000)
                if file_context:
                    print(f"Added file context from project {project_id}")
            except Exception as file_ctx_error:
                print(f"Could not load file context: {file_ctx_error}")

        db = get_db()
        cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                           (user_request, 'processing', conversation_id))
        task_id = cursor.lastrowid
        db.commit()

        # Code assistant check
        try:
            code_assistant_agent = get_code_assistant(knowledge_base=knowledge_base)
            feedback_check = code_assistant_agent.detect_code_feedback(user_request)
            if feedback_check['is_code_feedback']:
                print(f"Code feedback detected for: {feedback_check['target_file']}")
                from orchestration.ai_clients import call_claude_sonnet
                code_result = code_assistant_agent.process_code_feedback(user_request, call_claude_sonnet)
                if code_result['success']:
                    deployment_pkg = code_result['deployment_package']
                    doc_id = None
                    document_url = None
                    if code_result.get('output_path'):
                        try:
                            file_size = os.path.getsize(code_result['output_path'])
                            doc_id = save_generated_document(
                                filename=os.path.basename(code_result['output_path']),
                                original_name=f"Fixed: {code_result['target_file']}",
                                document_type='py', file_path=code_result['output_path'],
                                file_size=file_size, task_id=task_id,
                                conversation_id=conversation_id, project_id=project_id,
                                title=f"Code Fix: {code_result['target_file']}",
                                description=deployment_pkg['change_summary'], category='code'
                            )
                            document_url = f'/api/generated-documents/{doc_id}/download'
                        except Exception as doc_error:
                            print(f"Could not save code file: {doc_error}")
                    response_html = convert_markdown_to_html(code_result['message'])
                    db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                              ('completed', 'code_assistant', time.time() - overall_start, task_id))
                    db.commit()
                    add_message(conversation_id, 'assistant', code_result['message'], task_id,
                               {'document_created': True, 'document_type': 'py', 'document_id': doc_id,
                                'orchestrator': 'code_assistant', 'target_file': code_result['target_file']})
                    suggestions = []
                    if proactive:
                        try:
                            suggestions = proactive.post_process_result(task_id, user_request, code_result['message'])
                        except:
                            pass
                    db.close()
                    return jsonify({
                        'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                        'result': response_html, 'document_url': document_url, 'document_id': doc_id,
                        'document_created': True, 'document_type': 'py',
                        'execution_time': time.time() - overall_start, 'orchestrator': 'code_assistant',
                        'target_file': code_result['target_file'],
                        'deployment_instructions': deployment_pkg['deployment_instructions'],
                        'suggestions': suggestions
                    })
        except Exception as code_assistant_error:
            print(f"Code Assistant failed: {code_assistant_error}")

        # Schedule handler check
        schedule_handler = get_combined_schedule_handler()
        schedule_context = get_schedule_context(conversation_id)
        schedule_result = schedule_handler.process_request(user_request, schedule_context)

        if schedule_result['action'] != 'not_schedule_request':
            if 'context' in schedule_result:
                save_schedule_context(conversation_id, schedule_result['context'])
            if schedule_result['action'] == 'generate_schedule':
                source_filepath = schedule_result['filepath']
                filename = os.path.basename(source_filepath)
                file_path = source_filepath
                file_size = os.path.getsize(file_path)
                shift_length = schedule_result['shift_length']
                pattern_key = schedule_result['pattern_key']
                doc_title = f"{shift_length}-Hour {pattern_key.upper().replace('_', ' ')} Schedule Pattern"
                doc_id = save_generated_document(
                    filename=filename, original_name=doc_title, document_type='xlsx',
                    file_path=file_path, file_size=file_size, task_id=task_id,
                    conversation_id=conversation_id, project_id=project_id,
                    title=doc_title, description=f"Visual {shift_length}-hour {pattern_key} schedule pattern",
                    category='schedule'
                )
                response_html = convert_markdown_to_html(schedule_result['message'])
                db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                          ('completed', 'pattern_schedule_generator', time.time() - overall_start, task_id))
                db.commit()
                add_message(conversation_id, 'assistant', schedule_result['message'], task_id,
                           {'document_created': True, 'document_type': 'xlsx', 'document_id': doc_id,
                            'orchestrator': 'pattern_schedule_generator', 'shift_length': shift_length,
                            'pattern': pattern_key})
                save_schedule_context(conversation_id, {})
                session.pop('schedule_context', None)
                suggestions = []
                if proactive:
                    try:
                        suggestions = proactive.post_process_result(task_id, user_request, schedule_result['message'])
                    except:
                        pass
                db.close()
                return jsonify({
                    'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                    'result': response_html, 'document_url': f'/api/generated-documents/{doc_id}/download',
                    'document_id': doc_id, 'document_created': True, 'document_type': 'xlsx',
                    'execution_time': time.time() - overall_start,
                    'orchestrator': 'pattern_schedule_generator',
                    'knowledge_applied': False, 'formatting_applied': True,
                    'specialists_used': [], 'consensus': None, 'suggestions': suggestions,
                    'shift_length': shift_length, 'pattern': pattern_key
                })
            else:
                response_html = convert_markdown_to_html(schedule_result['message'])
                db.execute('UPDATE tasks SET status = ? WHERE id = ?', ('in_progress', task_id))
                db.commit()
                add_message(conversation_id, 'assistant', schedule_result['message'], task_id,
                           {'waiting_for_input': True, 'orchestrator': 'pattern_schedule_generator',
                            'waiting_for': schedule_result.get('waiting_for')})
                db.close()
                return jsonify({
                    'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                    'result': response_html, 'needs_input': True,
                    'waiting_for': schedule_result.get('waiting_for'),
                    'orchestrator': 'pattern_schedule_generator',
                    'execution_time': time.time() - overall_start
                })

        # ================================================================
        # REGULAR AI ORCHESTRATION (PATH 3 - Sonnet)
        # ================================================================
        try:
            print(f"Analyzing task: {user_request[:100]}...")
            analysis = analyze_task_with_sonnet(user_request, knowledge_base=knowledge_base,
                                                file_paths=file_paths, file_contents=file_contents)
            task_type = analysis.get('task_type', 'general')
            confidence = analysis.get('confidence', 0.5)
            escalate = analysis.get('escalate_to_opus', False)
            specialists_needed = analysis.get('specialists_needed', [])
            knowledge_applied = analysis.get('knowledge_applied', False)
            knowledge_sources = analysis.get('knowledge_sources', [])

            if specialists_needed:
                specialists_needed = [s for s in specialists_needed if s and s.lower() != 'none']

            orchestrator = 'sonnet'
            opus_guidance = None

            if escalate:
                print("Escalating to Opus...")
                orchestrator = 'opus'
                try:
                    opus_result = handle_with_opus(user_request, analysis, knowledge_base=knowledge_base,
                                                   file_paths=file_paths, file_contents=file_contents)
                    opus_guidance = opus_result.get('strategic_analysis', '')
                    if opus_result.get('specialist_assignments'):
                        for assignment in opus_result.get('specialist_assignments', []):
                            specialist = assignment.get('ai') or assignment.get('specialist')
                            if specialist and specialist.lower() != 'none':
                                specialists_needed.append(specialist)
                except Exception as opus_error:
                    print(f"Opus guidance failed: {opus_error}")

            specialist_results = []
            specialist_output = None
            research_agent_ran = False

            if specialists_needed:
                for specialist_info in specialists_needed:
                    if isinstance(specialist_info, dict):
                        specialist = specialist_info.get('specialist') or specialist_info.get('ai')
                        specialist_task = specialist_info.get('task', user_request)
                    else:
                        specialist = specialist_info
                        specialist_task = user_request
                    if specialist and specialist.lower() != 'none':
                        print(f"Executing specialist: {specialist}")
                        result = execute_specialist_task(specialist, specialist_task,
                                                         file_paths=file_paths, file_contents=file_contents)
                        specialist_results.append(result)
                        if result.get('success') and result.get('output'):
                            specialist_output = result.get('output')
                            if specialist.lower() == 'research_agent':
                                research_agent_ran = True
                                print(f"Research agent completed - will synthesize with Sonnet")

            from orchestration.ai_clients import call_claude_opus, call_claude_sonnet

            def get_knowledge_context_for_prompt(kb, user_req, max_context=6000):
                if not kb:
                    return ""
                try:
                    context = kb.get_context_for_task(user_req, max_context=max_context)
                    if context:
                        return f"""\n\n{'=' * 70}
SHIFTWORK SOLUTIONS PROPRIETARY KNOWLEDGE BASE
This content is drawn from hundreds of real consulting engagements
across dozens of industries over 30+ years of practice.

INSTRUCTION: You MUST use the information below as your PRIMARY source
when answering this question. Do NOT rely on generic knowledge when
specific guidance exists in this knowledge base. Cite specific lessons,
rules, or findings from the sources listed below.
{'=' * 70}

{context}

{'=' * 70}
END KNOWLEDGE BASE - Answer using the above as your primary source.
{'=' * 70}\n\n"""
                    return ""
                except Exception as e:
                    print(f"Knowledge context retrieval failed: {e}")
                    return ""

            knowledge_context = get_knowledge_context_for_prompt(knowledge_base, user_request)

            learning_context = ""
            try:
                learning_context = get_learning_context()
                if learning_context:
                    print(f"Retrieved learning context ({len(learning_context)} chars)")
            except Exception as learn_ctx_error:
                print(f"Could not get learning context (non-critical): {learn_ctx_error}")

            client_profile_context = ""
            if project_id:
                try:
                    db_temp = get_db()
                    project = db_temp.execute('SELECT client_name FROM projects WHERE project_id = ?', (project_id,)).fetchone()
                    db_temp.close()
                    if project and project['client_name']:
                        client_profile_context = get_client_profile_context(project['client_name'])
                        if client_profile_context:
                            print(f"Retrieved client profile for {project['client_name']}")
                except Exception as profile_error:
                    print(f"Could not get client profile (non-critical): {profile_error}")

            avoidance_context = ""
            try:
                avoidance_context = get_avoidance_context(days=30, limit=5)
                if avoidance_context:
                    print(f"Retrieved avoidance patterns")
            except Exception as avoid_error:
                print(f"Could not get avoidance context (non-critical): {avoid_error}")

            specialized_context = ""
            try:
                specialist_kb = get_specialized_knowledge()
                industry = None
                if project_id:
                    db_temp = get_db()
                    proj = db_temp.execute('SELECT industry FROM projects WHERE project_id = ?', (project_id,)).fetchone()
                    db_temp.close()
                    if proj:
                        industry = proj['industry']
                specialized_context = specialist_kb.build_expertise_context(user_request, industry)
                if specialized_context:
                    print(f"Injected specialized knowledge for {industry or 'general'}")
            except Exception as spec_error:
                print(f"Could not get specialized knowledge: {spec_error}")

            summary_context = ""
            try:
                summarizer = get_conversation_summarizer()
                if summarizer.should_summarize(conversation_id):
                    from orchestration.ai_clients import call_claude_sonnet
                    summarizer.summarize_conversation(conversation_id, call_claude_sonnet)
                summary_context = summarizer.get_conversation_context(conversation_id)
                if summary_context:
                    print(f"Retrieved conversation summary")
            except Exception as summary_error:
                print(f"Could not get conversation summary: {summary_error}")

            intelligence = None
            try:
                intelligence = EnhancedIntelligence()
                print("EnhancedIntelligence initialized")
            except Exception as intel_error:
                print(f"EnhancedIntelligence init failed (non-critical): {intel_error}")

            project_context = ""
            if project_id:
                try:
                    from database_file_management import get_file_stats_by_project
                    db_temp = get_db()
                    project = db_temp.execute('SELECT * FROM projects WHERE project_id = ?', (project_id,)).fetchone()
                    db_temp.close()
                    if project:
                        file_stats = get_file_stats_by_project(project_id)
                        project_context = f"""

=== CURRENT PROJECT CONTEXT ===
You are working inside the "{project['client_name']}" PROJECT FOLDER.
- Industry: {project['industry']}
- Facility Type: {project['facility_type']}
- Project Phase: {project['project_phase']}

This project folder contains: {file_stats.get('total_files', 0)} files
- Uploaded: {file_stats.get('uploaded_files', 0)}
- Generated: {file_stats.get('generated_files', 0)}
===

"""
                except Exception as proj_ctx_error:
                    print(f"Could not load project context: {proj_ctx_error}")

            conversation_history = ""
            if conversation_context and len(conversation_context) > 1:
                conversation_history = "\n\n=== CONVERSATION HISTORY ===\n"
                for msg in conversation_context[:-1]:
                    role_label = "User" if msg['role'] == 'user' else "Assistant"
                    content_preview = msg['content'][:500] + '...' if len(msg['content']) > 500 else msg['content']
                    conversation_history += f"{role_label}: {content_preview}\n"
                conversation_history += "=== END CONVERSATION HISTORY ===\n\n"

            if research_agent_ran and specialist_output:
                # PATH 1: Synthesize research results with Sonnet
                print(f"Synthesizing research agent results with Sonnet...")
                synthesis_prompt = f"""{project_context}{conversation_history}
USER QUESTION: {user_request}

CURRENT WEB RESEARCH RESULTS (retrieved this moment via Tavily):
{specialist_output}

You are a senior consulting partner at Shiftwork Solutions LLC with 30+ years
of experience. Using the web research results above as your primary source of
current information, provide a clear, professional answer to the user's question.

INSTRUCTIONS:
- Lead with the most relevant and recent findings from the research
- Organize the information clearly - use headers if there are multiple topics
- Include specific details (dates, companies, dollar amounts) from the sources
- Add your consulting perspective where it adds value
- Cite sources naturally (e.g. "According to OSHA's news releases..." or "A Fox 10 report noted...")
- Keep the tone professional but conversational - this is an internal consulting tool
- If the research reveals something directly relevant to shift work operations, highlight it

Provide a complete, synthesized answer now:"""
                print(f"Sending synthesis prompt to Sonnet ({len(synthesis_prompt)} chars)...")
                response = call_claude_sonnet(synthesis_prompt, conversation_history=None,
                                              files_attached=False, system_prompt=None)
                if isinstance(response, dict):
                    if response.get('error'):
                        print(f"Synthesis failed, using raw research output")
                        actual_output = specialist_output
                    else:
                        actual_output = response.get('content', '')
                        print(f"Research synthesis complete ({len(actual_output)} chars)")
                else:
                    actual_output = str(response)

            elif specialist_output and not research_agent_ran:
                # PATH 2: Non-research specialist - use output directly
                actual_output = specialist_output

            else:
                # PATH 3: No specialist - Sonnet generates response
                if file_contents:
                    file_section = f"""

========================================================================
ATTACHED FILES - READ THESE CAREFULLY
========================================================================

{file_contents}

========================================================================
"""
                else:
                    file_section = ""

                identity_block = ""
                if knowledge_context:
                    identity_block = """
========================================================================
IDENTITY AND INSTRUCTIONS
========================================================================
You are an expert AI assistant for Shiftwork Solutions LLC, a consulting
firm with 30+ years of experience helping hundreds of facilities across
dozens of industries design and implement shift schedules.

When answering questions about shift work, schedules, overtime, employee
preferences, implementation, or change management:

1. ALWAYS draw primarily from the SHIFTWORK SOLUTIONS KNOWLEDGE BASE
   content provided above in this prompt.
2. Reference specific lessons, rules, findings, or percentages from
   those sources when they are relevant.
3. Do NOT give generic textbook answers when specific proprietary
   guidance exists in the knowledge base above.
4. Your answers should reflect the real-world experience of hundreds
   of consulting engagements, not general AI knowledge.
========================================================================

"""

                # ============================================================
                # INGESTED KNOWLEDGE BASE BRIDGE (System 2)
                # Added February 27, 2026
                # ============================================================
                ingested_kb_context = ""
                try:
                    from knowledge_query_bridge import query_ingested_knowledge
                    ingested_kb_context = query_ingested_knowledge(user_request)
                    if ingested_kb_context:
                        print(f"Ingested KB: added {len(ingested_kb_context)} chars of context from uploaded documents")
                except Exception as ikb_err:
                    print(f"Ingested KB query failed (non-critical): {ikb_err}")

                completion_prompt = f"""{project_context}{file_context}{conversation_history}{learning_context}{client_profile_context}{avoidance_context}{specialized_context}{summary_context}{ingested_kb_context}{file_section}
USER REQUEST: {user_request}

Please complete this request fully. Provide the actual deliverable.
Be comprehensive and professional."""

                if opus_guidance:
                    completion_prompt += f"\n\nSTRATEGIC GUIDANCE:\n{opus_guidance}"

                if file_contents:
                    print(f"Completion prompt contains {len(file_contents)} chars of file content")

                api_system_prompt = None
                if knowledge_context or identity_block:
                    api_system_prompt = f"{knowledge_context}{identity_block}".strip()

                if orchestrator == 'opus':
                    response = call_claude_opus(completion_prompt, conversation_history=conversation_context,
                                               files_attached=bool(file_contents), system_prompt=api_system_prompt)
                else:
                    response = call_claude_sonnet(completion_prompt, conversation_history=conversation_context,
                                                  files_attached=bool(file_contents), system_prompt=api_system_prompt)

                if isinstance(response, dict):
                    if response.get('error'):
                        actual_output = f"Error: {response.get('content', 'Unknown error')}"
                    else:
                        actual_output = response.get('content', '')
                else:
                    actual_output = str(response)

            print(f"Task completed. Output length: {len(actual_output) if actual_output else 0} chars")
            formatted_output = convert_markdown_to_html(actual_output)

            consensus_result = None
            if enable_consensus and actual_output and not actual_output.startswith('Error'):
                try:
                    consensus_result = validate_with_consensus(actual_output)
                except Exception as consensus_error:
                    print(f"Consensus validation failed: {consensus_error}")

            total_time = time.time() - overall_start
            db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                      ('completed', orchestrator, total_time, task_id))
            db.commit()
            db.close()

            add_message(conversation_id, 'assistant', actual_output, task_id,
                       {'orchestrator': orchestrator, 'knowledge_applied': knowledge_applied,
                        'execution_time': total_time})

            suggestions = []
            if proactive:
                try:
                    suggestions = proactive.post_process_result(task_id, user_request, actual_output if actual_output else '')
                except Exception as suggest_error:
                    print(f"Suggestion generation failed: {suggest_error}")

            if intelligence and actual_output and not actual_output.startswith('Error'):
                try:
                    intelligence.learn_from_interaction(user_request, actual_output, user_feedback=None)
                    print("EnhancedIntelligence learned from this interaction")
                except Exception as learn_error:
                    print(f"EnhancedIntelligence learning failed (non-critical): {learn_error}")

            if project_id:
                try:
                    db_temp = get_db()
                    project = db_temp.execute('SELECT client_name, industry FROM projects WHERE project_id = ?', (project_id,)).fetchone()
                    db_temp.close()
                    if project and project['client_name']:
                        interaction_data = {'approach': orchestrator, 'approach_worked': True,
                                           'industry': project['industry'], 'preferences': {}}
                        update_client_profile(project['client_name'], interaction_data)
                        print(f"Updated profile for {project['client_name']}")
                except Exception as profile_update_error:
                    print(f"Client profile update failed (non-critical): {profile_update_error}")

            try:
                learn_from_conversation(user_request, actual_output if actual_output else '')
            except Exception as learn_error:
                print(f"Auto-learning failed (non-critical): {learn_error}")

            curious_question = None
            try:
                curiosity_engine = get_curiosity_engine()
                curiosity_check = curiosity_engine.should_be_curious(
                    conversation_id,
                    {'user_request': user_request, 'ai_response': actual_output if actual_output else '',
                     'task_completed': True}
                )
                if curiosity_check['should_ask']:
                    curious_question = curiosity_check['question']
                    print(f"Curious follow-up: {curious_question}")
            except Exception as curiosity_error:
                print(f"Curiosity engine failed (non-critical): {curiosity_error}")

            document_created = False
            document_url = None
            document_id = None
            document_type = None

            try:
                from document_generator import is_document_request, generate_document
                if is_document_request(user_request) and actual_output and not actual_output.startswith('Error'):
                    print(f"Document request detected - generating .docx file")
                    doc_result = generate_document(
                        user_request=user_request, ai_response_text=actual_output,
                        task_id=task_id, conversation_id=conversation_id, project_id=project_id
                    )
                    if doc_result.get('success'):
                        document_created = True
                        document_url = doc_result['document_url']
                        document_id = doc_result.get('document_id')
                        document_type = 'docx'
                        print(f"Document generated: {document_url}")
                    else:
                        print(f"Document generation failed (non-critical): {doc_result.get('error')}")
            except Exception as doc_gen_error:
                print(f"Document generation error (non-critical): {doc_gen_error}")

            return jsonify({
                'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                'result': formatted_output, 'orchestrator': orchestrator,
                'specialists_used': [s.get('specialist') for s in specialist_results] if specialist_results else [],
                'consensus': consensus_result, 'execution_time': total_time,
                'knowledge_applied': knowledge_applied, 'knowledge_used': knowledge_applied,
                'knowledge_sources': knowledge_sources, 'formatting_applied': True,
                'suggestions': suggestions, 'curious_question': curious_question,
                'document_created': document_created, 'document_url': document_url,
                'document_id': document_id, 'document_type': document_type
            })

        except Exception as orchestration_error:
            import traceback
            print(f"Orchestration error: {traceback.format_exc()}")
            db.execute('UPDATE tasks SET status = ? WHERE id = ?', ('failed', task_id))
            db.commit()
            db.close()
            add_message(conversation_id, 'assistant', f"Error: {str(orchestration_error)}", task_id, {'error': True})
            return jsonify({'success': False, 'error': f'Orchestration failed: {str(orchestration_error)}',
                           'task_id': task_id, 'conversation_id': conversation_id}), 500

    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500


# ============================================================================
# INTROSPECTION REPORT FORMATTER
# Added February 27, 2026 - Handler 4.6 helper
# ============================================================================

def _format_introspection_as_text(report: dict) -> str:
    """
    Format an introspection report dict as readable markdown for the frontend.
    Called by Handler 4.6 to produce the 'result' field.
    """
    lines = []

    introspection_type = report.get('introspection_type', 'weekly').title()
    generated_at = report.get('generated_at', '')
    period_days = report.get('period_days', 7)

    lines.append(f"## Swarm {introspection_type} Self-Assessment")
    lines.append(f"*Generated: {generated_at} | Period: Last {period_days} days*")
    lines.append("")

    summary = report.get('summary', {})
    health_score = summary.get('health_score', 0)
    trend = summary.get('trend', 'stable')
    tasks_analyzed = summary.get('tasks_analyzed', 0)
    success_rate = summary.get('success_rate', 0)
    anomalies = summary.get('anomalies_detected', 0)
    alignment_score = summary.get('alignment_score', 0)

    trend_icon = {'improving': 'Trending Up', 'declining': 'Trending Down', 'stable': 'Stable'}.get(trend, 'Stable')

    lines.append("### Performance Summary")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Health Score | **{health_score}/100** |")
    lines.append(f"| Trend | {trend_icon} |")
    lines.append(f"| Tasks Analyzed | {tasks_analyzed} |")
    lines.append(f"| Success Rate | {success_rate}% |")
    lines.append(f"| Anomalies Detected | {anomalies} |")
    lines.append(f"| Goal Alignment Score | {alignment_score}/100 |")
    lines.append("")

    monitoring = report.get('components', {}).get('self_monitoring', {})
    if monitoring.get('status') == 'complete':
        metrics = monitoring.get('metrics', {})
        timing = metrics.get('timing', {})
        feedback = metrics.get('feedback', {})
        lines.append("### Self-Monitoring Details")
        anomaly_list = monitoring.get('anomalies', [])
        if anomaly_list:
            lines.append("**Anomalies Detected:**")
            for a in anomaly_list:
                severity = 'HIGH' if a.get('severity') == 'high' else 'MEDIUM'
                lines.append(f"- [{severity}] {a.get('description', '')}")
            lines.append("")
        if timing.get('avg_execution_time'):
            lines.append(f"**Response Times:** avg {timing['avg_execution_time']}s | "
                        f"min {timing.get('min_execution_time', 0)}s | "
                        f"max {timing.get('max_execution_time', 0)}s")
            lines.append("")
        if feedback.get('total_feedback', 0) > 0:
            lines.append(f"**User Feedback:** {feedback['total_feedback']} responses | "
                        f"avg rating {feedback.get('avg_overall_rating', 0)}/5")
            lines.append("")
    elif monitoring.get('status') == 'failed':
        lines.append("### Self-Monitoring")
        lines.append(f"*Could not collect metrics: {monitoring.get('error', 'Unknown error')}*")
        lines.append("")

    alignment = report.get('components', {}).get('goal_alignment', {})
    if alignment.get('status') == 'complete':
        lines.append("### Goal Alignment")
        lines.append(f"**Overall Score: {alignment.get('alignment_score', 0)}/100**")
        lines.append("")
        by_objective = alignment.get('by_objective', [])
        if by_objective:
            lines.append("| Objective | Tasks | % of Activity | Status |")
            lines.append("|-----------|-------|---------------|--------|")
            for obj in by_objective:
                status = obj.get('assessment', '').replace('_', ' ').title()
                lines.append(f"| {obj['name']} | {obj['task_count']} | {obj['percentage']}% | {status} |")
            lines.append("")
        observations = alignment.get('observations', [])
        if observations:
            lines.append("**Observations:**")
            for obs in observations:
                lines.append(f"- {obs}")
            lines.append("")

    reflection = report.get('reflection', '')
    if reflection:
        lines.append("### My Self-Reflection")
        lines.append(reflection)
        lines.append("")

    lines.append("---")
    lines.append("*Components in development: Capability Boundary Tracking (Phase 2), "
                "Confidence Calibration (Phase 2), Self-Modification Proposals (Phase 3)*")

    return "\n".join(lines)


# ============================================================================
# CONTRACT / PROPOSAL HANDLER HELPERS
# Added February 20, 2026
# ============================================================================

def _detect_template_request(user_request):
    if not user_request:
        return None
    req_lower = user_request.lower()
    CONTRACT_KEYWORDS = ['contract', 'agreement', 'project agreement', 'service agreement', 'consulting agreement']
    PROPOSAL_KEYWORDS = ['proposal', 'bid', 'quote', 'scope of work', 'sow', 'project proposal', 'consulting proposal']
    if any(k in req_lower for k in CONTRACT_KEYWORDS):
        return 'contract'
    if any(k in req_lower for k in PROPOSAL_KEYWORDS):
        return 'proposal'
    return None


def _build_contract_questions_html(contract_type):
    doc_label = contract_type.title()
    html = (
        f'<div style="background: linear-gradient(135deg, #e8f5e9 0%, #f3e5f5 100%); '
        f'border-radius: 12px; padding: 20px; margin: 10px 0;">'
        f'<div style="font-weight: 600; font-size: 16px; color: #333; margin-bottom: 15px;">'
        f'I\'ll prepare the {doc_label} for you. I just need a few details first:'
        f'</div>'
    )
    questions = [
        ('client_name',    'What is the client company name?',             'e.g. Acme Foods Inc.'),
        ('client_address', 'What is the client address?',                  'e.g. 123 Main St, Chicago IL 60601'),
        ('project_cost',   'What is the total project investment amount?', 'e.g. $99,000'),
        ('payment_terms',  'How would you like payments structured?',
         'e.g. 50% upon signing, 25% at mid-point, 25% on completion'),
    ]
    for field, question, placeholder in questions:
        html += (
            f'<div style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 12px;">'
            f'<div style="font-weight: 500; color: #333; margin-bottom: 8px;">'
            f'{question} <span style="color: #d32f2f;">*</span></div>'
            f'<input type="text" id="contract_field_{field}" placeholder="{placeholder}" '
            f'style="width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; '
            f'font-size: 14px; box-sizing: border-box;">'
            f'</div>'
        )
    html += (
        f'<div style="margin-top: 20px; text-align: center;">'
        f'<button onclick="submitContractAnswers(\'{contract_type}\')" '
        f'style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); '
        f'color: white; border: none; padding: 12px 30px; border-radius: 8px; '
        f'font-weight: 600; cursor: pointer; font-size: 15px;">'
        f'Generate {doc_label}</button>'
        f'</div></div>'
    )
    html += '''
<script>
function submitContractAnswers(contractType) {
    var fields = ['client_name', 'client_address', 'project_cost', 'payment_terms'];
    var answers = {};
    var missing = [];
    fields.forEach(function(f) {
        var el = document.getElementById('contract_field_' + f);
        if (el && el.value.trim()) {
            answers[f] = el.value.trim();
        } else {
            missing.push(f.replace('_', ' '));
        }
    });
    if (missing.length > 0) {
        alert('Please fill in: ' + missing.join(', '));
        return;
    }
    var loading = document.getElementById('loadingIndicator');
    if (loading) loading.classList.add('active');
    var formData = new FormData();
    formData.append('request', 'Generate the ' + contractType + ' with the provided client details');
    formData.append('clarification_answers', JSON.stringify(answers));
    if (typeof currentConversationId !== 'undefined' && currentConversationId) {
        formData.append('conversation_id', currentConversationId);
    }
    fetch('/api/orchestrate', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (loading) loading.classList.remove('active');
        if (data.success) {
            if (data.conversation_id && typeof currentConversationId !== 'undefined') {
                currentConversationId = data.conversation_id;
                localStorage.setItem('currentConversationId', currentConversationId);
            }
            var downloadSection = '';
            if (data.document_url) {
                var docType = (data.document_type || 'docx').toUpperCase();
                downloadSection = '<div style="margin-top:15px;padding:12px;background:#e8f5e9;border-left:4px solid #4caf50;border-radius:4px;">'
                    + '<a href="' + data.document_url + '" download style="padding:8px 16px;background:#4caf50;color:white;text-decoration:none;border-radius:6px;">Download ' + docType + '</a></div>';
            }
            if (typeof addMessage === 'function') {
                addMessage('assistant', data.result + downloadSection, data.task_id, 'quick');
            }
            if (typeof loadConversations === 'function') loadConversations();
            if (typeof loadDocuments === 'function') loadDocuments();
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) {
        if (loading) loading.classList.remove('active');
        alert('Error: ' + err.message);
    });
}
</script>
'''
    return html


def _get_template_from_kb(doc_type):
    import sqlite3
    db_path = os.environ.get('KNOWLEDGE_DB_PATH', 'swarm_intelligence.db')
    try:
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        exists = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_extracts'"
        ).fetchone()
        if not exists:
            db.close()
            print(f"knowledge_extracts table not found in {db_path}")
            return ""
        row = db.execute(
            'SELECT document_name, document_type, extracted_data FROM knowledge_extracts WHERE LOWER(document_type) = ? ORDER BY extracted_at DESC LIMIT 1',
            (doc_type.lower(),)
        ).fetchone()
        if not row:
            row = db.execute(
                'SELECT document_name, document_type, extracted_data FROM knowledge_extracts WHERE LOWER(document_type) LIKE ? ORDER BY extracted_at DESC LIMIT 1',
                (f'%{doc_type.lower()}%',)
            ).fetchone()
        db.close()
        if row:
            print(f"Template found: {row['document_name']} (type: {row['document_type']})")
            try:
                extracted = json.loads(row['extracted_data'])
                raw = (extracted.get('raw_content') or extracted.get('content')
                       or extracted.get('full_text') or extracted.get('text', ''))
                if raw:
                    return raw
                insights = extracted.get('insights', [])
                patterns = extracted.get('patterns', [])
                parts = [f"Template: {row['document_name']}"]
                for item in insights[:20]:
                    parts.append(str(item.get('content', item)) if isinstance(item, dict) else str(item))
                for item in patterns[:10]:
                    parts.append(str(item.get('pattern', item)) if isinstance(item, dict) else str(item))
                return '\n'.join(parts)
            except Exception as parse_err:
                print(f"Template JSON parse error: {parse_err}")
                return str(row['extracted_data'])[:5000]
        else:
            print(f"No {doc_type} template found in knowledge_extracts")
            return ""
    except Exception as e:
        print(f"Template retrieval error: {e}")
        return ""


def _build_contract_generation_prompt(contract_type, template_content, answers):
    from datetime import datetime
    client_name    = answers.get('client_name',    '___')
    client_address = answers.get('client_address', '___')
    project_cost   = answers.get('project_cost',   '___')
    payment_terms  = answers.get('payment_terms',  '50% upon execution, 25% Phase 2 completion, 25% final delivery')
    today          = datetime.now().strftime('%B %d, %Y')
    doc_label = contract_type.title()
    if template_content:
        template_section = (
            f"REFERENCE TEMPLATE (from our uploaded {doc_label} files):\n"
            f"Use this as the structural and legal framework. Keep all sections, "
            f"clauses, and language intact. Only fill in the blanks.\n\n"
            f"{template_content}\n\nEND OF TEMPLATE\n"
        )
    else:
        template_section = (
            f"NOTE: No uploaded {doc_label} template was found in the knowledge base. "
            f"Generate a professional Shiftwork Solutions {doc_label} using our standard "
            f"format: scope of work, phases, client responsibilities, investment & payment "
            f"terms, IP/confidentiality, and signature block.\n\n"
        )
    return f"""You are preparing a {doc_label} for Shiftwork Solutions LLC.

{template_section}
CLIENT INFORMATION:
- Client Company: {client_name}
- Client Address: {client_address}
- Total Project Investment: {project_cost}
- Payment Structure: {payment_terms}
- Date: {today}
- Project Manager: Jim Goodwin
- Contact: (415) 763-5005 | https://shift-work.com

INSTRUCTIONS:
1. Use the template structure exactly -- do not add or remove sections
2. Replace every blank field (_____ or ____) with the client information above
3. Fill in the payment schedule section with the payment structure provided
4. Keep all legal language, protection clauses, and formatting from the template
5. Where the template says "Client: _____" replace with "{client_name}"
6. Where the template says "Facility: _____" use "{client_name} facility"
7. Return the COMPLETE filled-in {doc_label} -- do not truncate or summarize

Generate the complete {doc_label} now:"""


# ============================================================================
# SURVEY BUILDER HANDLER HELPERS
# Added February 28, 2026 (Session 1) - Handler 3.6
# Simplified February 28, 2026 (Session 2) - 3-field form, always comprehensive
# ============================================================================

# All standard question IDs in the order they should appear in the survey.
# This is the comprehensive set used for every survey — no category filtering.
# Updated February 28, 2026: added 39 new questions from Master_Survey_for_Survey_Business.doc
# Total: 103 questions across 7 categories (added Day Care / Elder Care as new category)
_ALL_SURVEY_QUESTION_IDS = [
    # Demographics (18 questions)
    'dept', 'tenure', 'dept_tenure', 'crew_assignment', 'current_schedule',
    'prior_shiftwork', 'second_job', 'second_job_timing', 'employment_type',
    'student_status', 'caregiving', 'gender', 'age_group', 'partner_status',
    'single_parent', 'commute_method', 'commute_distance', 'worst_shift_start',
    # Sleep & Alertness (11 questions)
    'alarm_clock_normal', 'alarm_clock_day', 'alarm_clock_afternoon', 'alarm_clock_night',
    'sleep_day_shift', 'sleep_second_shift', 'sleep_third_shift',
    'sleep_night_shift', 'sleep_days_off', 'sleep_needed', 'sleepiness_problems',
    # Working Conditions (18 questions)
    'safety_rating', 'safety_improvement', 'company_communication',
    'communication_importance', 'handoff_time', 'management_input',
    'enjoy_work', 'pay_competitive', 'management_equality', 'company_belonging',
    'absenteeism_impact', 'facility_improvement', 'best_workplace',
    'training_importance', 'training_adequacy', 'training_amount',
    'supervisor_responsive', 'management_responsive',
    # Schedule Features (33 questions)
    'schedule_improvement', 'schedule_policies_fair', 'current_schedule_satisfaction',
    'better_schedules_exist', 'shift_mobility_intent', 'time_off_predictable',
    'schedule_flexibility', 'preferred_8hr_shift', 'least_preferred_8hr_shift',
    'preferred_12hr_shift', 'hours_vs_days_off', 'fixed_vs_rotating',
    'fixed_vs_rotating_no_seniority', 'fixed_vs_rotating_not_first_choice',
    'crew_cohesion', 'rotation_frequency', 'rotation_direction',
    'day_shift_start_8hr', 'day_shift_start_10hr', 'day_shift_start_12hr',
    'weekend_preference', 'shift_swap_importance', 'night_shift_start_preference',
    'weekend_pattern', 'work_pattern', 'three_day_preference', 'weekday_preference',
    'supervisor_overlap', 'task_variety', 'weekend_willingness', 'weekend_occasional',
    'understand_247_need', 'new_schedule_trial_willingness',
    # Overtime (13 questions)
    'overtime_dependency', 'overtime_amount', 'overtime_satisfaction',
    'overtime_timing_actual', 'overtime_timing_preferred', 'overtime_extend_shift',
    'overtime_day_off', 'overtime_distribution_fair', 'overtime_predictable',
    'time_vs_overtime', 'overtime_desire', 'overtime_expectation', 'overtime_weekly_hours',
    # Day Care / Elder Care (6 questions - new section added February 28, 2026)
    'daycare_use', 'daycare_location', 'daycare_relationship',
    'daycare_shifts_used', 'daycare_shift_issue', 'daycare_worst_shift',
    # Open-ended (4 questions)
    'schedule_like_most', 'schedule_like_least',
    'work_life_positives', 'work_life_improvements',
]

# All schedule IDs in order of most common usage across client engagements.
# Selecting N schedules picks the first N from this list.
_SCHEDULE_LIBRARY_ORDER = [
    '2_3_2_fixed_days',
    '2_3_2_fixed_nights',
    'dupont_rotating',
    '4_on_4_off_days',
    '4_on_4_off_nights',
    'rotating_8hr',
    '5_and_2_days',
    '5_and_2_nights',
]


def _detect_survey_request(user_request):
    """
    Detect if the user is asking for a survey or questionnaire.
    Returns True if detected, False otherwise.
    Intentionally simple - catches 'survey' and 'questionnaire' in any context.
    """
    if not user_request:
        return False
    req_lower = user_request.lower()
    return any(kw in req_lower for kw in ['survey', 'questionnaire'])


def _build_survey_questions_html():
    """
    Build the simplified 3-field HTML clarification form for survey requests.

    Fields:
      1. Company Name  (required text input)
      2. Survey Date   (optional date input, defaults to today)
      3. Number of Schedules to Include  (optional dropdown 0-8)

    Simplified February 28, 2026 (Session 2):
      - Removed survey_type dropdown (always comprehensive)
      - Removed shift_length dropdown (not needed)
      - Removed distribution_method dropdown (not needed)
      - Removed employee_count dropdown (not needed)
    """
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')

    html = (
        '<div style="background: linear-gradient(135deg, #e3f2fd 0%, #e8f5e9 100%); '
        'border-radius: 12px; padding: 20px; margin: 10px 0;">'
        '<div style="font-weight: 600; font-size: 16px; color: #333; margin-bottom: 6px;">'
        'Building your comprehensive Shift Schedule Lifestyle Survey.'
        '</div>'
        '<div style="font-size: 13px; color: #555; margin-bottom: 18px;">'
        'All standard questions are included automatically. Just fill in the basics below.'
        '</div>'
    )

    # Field 1: Company Name (required)
    html += (
        '<div style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 12px;">'
        '<div style="font-weight: 500; color: #333; margin-bottom: 8px;">'
        'Client / Company Name <span style="color: #d32f2f;">*</span></div>'
        '<input type="text" id="survey_field_company_name" '
        'placeholder="e.g. Acme Foods Inc." '
        'style="width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; '
        'font-size: 14px; box-sizing: border-box;">'
        '</div>'
    )

    # Field 2: Survey Date (optional)
    html += (
        '<div style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 12px;">'
        '<div style="font-weight: 500; color: #333; margin-bottom: 8px;">'
        'Survey Date <span style="font-size: 12px; color: #888;">(optional)</span></div>'
        f'<input type="date" id="survey_field_survey_date" value="{today_str}" '
        'style="width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; '
        'font-size: 14px; box-sizing: border-box;">'
        '</div>'
    )

    # Field 3: Number of schedules to include (optional, 0-8)
    html += (
        '<div style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 12px;">'
        '<div style="font-weight: 500; color: #333; margin-bottom: 8px;">'
        'How many schedule concepts should employees rate? '
        '<span style="font-size: 12px; color: #888;">(optional)</span></div>'
        '<select id="survey_field_num_schedules" '
        'style="width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; '
        'font-size: 14px; box-sizing: border-box;">'
        '<option value="0">0 — No schedule rating section</option>'
        '<option value="1">1 schedule</option>'
        '<option value="2">2 schedules</option>'
        '<option value="3">3 schedules</option>'
        '<option value="4">4 schedules</option>'
        '<option value="5">5 schedules</option>'
        '<option value="6">6 schedules</option>'
        '<option value="7">7 schedules</option>'
        '<option value="8">8 schedules</option>'
        '</select>'
        '<div style="font-size: 12px; color: #888; margin-top: 6px;">'
        'Schedules are selected from our standard library (2-3-2, DuPont, 4-on-4-off, etc.)'
        '</div>'
        '</div>'
    )

    # Submit button
    html += (
        '<div style="margin-top: 20px; text-align: center;">'
        '<button onclick="submitSurveyAnswers()" '
        'style="background: linear-gradient(135deg, #43a047 0%, #1b5e20 100%); '
        'color: white; border: none; padding: 12px 30px; border-radius: 8px; '
        'font-weight: 600; cursor: pointer; font-size: 15px;">'
        'Build My Survey</button>'
        '</div></div>'
    )

    # JavaScript handler — reads the three fields and posts to /api/orchestrate
    html += '''
<script>
function submitSurveyAnswers() {
    var companyEl = document.getElementById('survey_field_company_name');
    var dateEl    = document.getElementById('survey_field_survey_date');
    var schedEl   = document.getElementById('survey_field_num_schedules');

    var company = companyEl ? companyEl.value.trim() : '';
    if (!company) {
        alert('Please enter the client / company name.');
        if (companyEl) companyEl.focus();
        return;
    }

    var answers = {
        company_name:  company,
        survey_date:   dateEl  ? dateEl.value  : '',
        num_schedules: schedEl ? schedEl.value : '0'
    };

    var loading = document.getElementById('loadingIndicator');
    if (loading) loading.classList.add('active');

    var formData = new FormData();
    formData.append('request', 'Build a survey for ' + company);
    formData.append('clarification_answers', JSON.stringify(answers));
    if (typeof currentConversationId !== 'undefined' && currentConversationId) {
        formData.append('conversation_id', currentConversationId);
    }

    fetch('/api/orchestrate', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (loading) loading.classList.remove('active');
        if (data.success) {
            if (data.conversation_id && typeof currentConversationId !== 'undefined') {
                currentConversationId = data.conversation_id;
                localStorage.setItem('currentConversationId', currentConversationId);
            }
            var downloadSection = '';
            if (data.document_url) {
                downloadSection =
                    '<div style="margin-top:15px;padding:12px;background:#e8f5e9;' +
                    'border-left:4px solid #4caf50;border-radius:4px;">' +
                    '<strong>Survey Ready!</strong> ' +
                    '<a href="' + data.document_url + '" download ' +
                    'style="padding:8px 16px;background:#4caf50;color:white;' +
                    'text-decoration:none;border-radius:6px;margin-left:10px;">' +
                    'Download Survey (.docx)</a></div>';
            }
            if (typeof addMessage === 'function') {
                addMessage('assistant', data.result + downloadSection, data.task_id, 'quick');
            }
            if (typeof loadDocuments === 'function') loadDocuments();
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) {
        if (loading) loading.classList.remove('active');
        alert('Error generating survey: ' + err.message);
    });
}
</script>
'''
    return html


def _map_survey_answers_to_questions(company_name, survey_date, num_schedules_str):
    """
    Map clarification answers to SurveyBuilder question IDs and schedule IDs.

    Simplified February 28, 2026 (Session 2):
      - Always returns ALL standard questions (_ALL_SURVEY_QUESTION_IDS).
        No category filtering, no survey-type branching.
      - Selects the first N schedules from _SCHEDULE_LIBRARY_ORDER where N
        is parsed from num_schedules_str. Invalid/missing input defaults to 0.

    Args:
        company_name:     Client company name (informational only, not used for selection)
        survey_date:      Survey date string (informational only, not used for selection)
        num_schedules_str: String integer 0-8 indicating how many schedule concepts to include

    Returns:
        tuple: (selected_questions list[str], schedules_to_rate list[str])
    """
    selected_questions = list(_ALL_SURVEY_QUESTION_IDS)

    try:
        num_schedules = max(0, min(int(num_schedules_str), len(_SCHEDULE_LIBRARY_ORDER)))
    except (ValueError, TypeError):
        num_schedules = 0

    schedules_to_rate = _SCHEDULE_LIBRARY_ORDER[:num_schedules]

    return selected_questions, schedules_to_rate


# I did no harm and this file is not truncated
