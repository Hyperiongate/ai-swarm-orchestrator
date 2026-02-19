"""
Orchestration Handler - Main AI Task Processing (REFACTORED)
Created: January 31, 2026
Last Updated: February 13, 2026 - ADDED BACKGROUND PROCESSING FOR LARGE LABOR FILES

CRITICAL FIX (February 13, 2026 - Session 3):
- Handler 4.5 now routes large labor files (>2MB) to background processing
- Prevents worker timeouts on large datasets
- Small files still processed immediately
- User gets instant "Processing in background..." response
- Results posted to conversation when complete

PREVIOUS FIXES:
- Handler 4.5: Labor Session Retrieval (loads file when user clicks "Yes")
- Restored full regular conversation handler
- Labor workflow: detection → offer → user clicks yes → analysis

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify, session
import time
import os
import json
import uuid
from datetime import datetime

# Import database functions
from database import (
    get_db, create_conversation, add_message,
    get_conversation_context, get_conversation,
    save_generated_document, get_schedule_context,
    save_schedule_context, get_client_profile_context,
    add_avoidance_pattern, get_avoidance_context,
    update_client_profile, load_analysis_session
)

# Import handlers
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

# Import utilities
from routes.utils import (
    convert_markdown_to_html,
    store_conversation_context,
    get_conversation_context as get_context_value,
    clear_conversation_context
)

# Import analyzers
from progressive_file_analyzer import get_progressive_analyzer
from file_content_reader import extract_multiple_files

# Import cloud handler
from cloud_file_handler import get_cloud_handler
from routes.handlers.cloud_handler import is_cloud_link

# Import orchestration components
from orchestration import (
    analyze_task_with_sonnet,
    handle_with_opus,
    execute_specialist_task,
    validate_with_consensus
)

# Import specialized handlers
from code_assistant_agent import get_code_assistant
from orchestration.proactive_agent import ProactiveAgent
from schedule_request_handler_combined import get_combined_schedule_handler

# Import learning systems
from conversation_learning import learn_from_conversation
from orchestration.task_analysis import get_learning_context
from enhanced_intelligence import EnhancedIntelligence
from specialized_knowledge import get_specialized_knowledge
from proactive_suggestions import get_proactive_suggestions
from conversation_summarizer import get_conversation_summarizer
from proactive_curiosity_engine import get_curiosity_engine

# Import labor analysis processor
from labor_analysis_processor import get_labor_processor

# Create blueprint
orchestration_bp = Blueprint('orchestration', __name__)


@orchestration_bp.route('/api/download/<path:filename>')
def download_file_route(filename):
    """Download route - delegates to handler"""
    return download_analysis_file(filename)


@orchestration_bp.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    """
    Main orchestration endpoint - routes requests to appropriate handlers.
    
    UPDATED February 13, 2026 (Session 3): Added background processing for large labor files
    UPDATED February 13, 2026 (Session 2): Added Handler 4.5 for labor session retrieval
    UPDATED February 13, 2026 (Session 1): Restored regular conversation handler
    UPDATED February 10, 2026: Refactored into modular handlers
    UPDATED February 5, 2026: Memory fixes, cloud downloads, progressive analysis
    UPDATED February 4, 2026: Added auto-learning integration
    UPDATED January 31, 2026: Extracted to separate file
    """
    try:
        overall_start = time.time()
        
        # Parse request data
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
        
        # Initialize file_contents early
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
        
        # HANDLER 3: File browser (project file selection)
        if file_ids_param and project_id:
            selected_context = handle_file_browser(
                file_ids_param, project_id, request.is_json
            )
            if selected_context:
                file_contents += "\n\n" + selected_context
        
        # HANDLER 4: Labor analysis response handler
        if conversation_id:
            labor_response = handle_labor_response(user_request, conversation_id)
            if labor_response:
                return labor_response
        
        # ========================================================================
        # HANDLER 4.5: LABOR SESSION RETRIEVAL WITH BACKGROUND PROCESSING
        # Updated February 13, 2026 - Session 3
        # ========================================================================
        # If labor_handler returned None, check if there's a pending labor session
        # Large files (>2MB) go to background processing, small files process immediately
        if not labor_response and conversation_id:
            # Try to get session_id from request or conversation context
            pending_session_id = None
            
            # Check if session_id was passed in request
            if request.is_json:
                pending_session_id = request.json.get('session_id')
            else:
                pending_session_id = request.form.get('session_id')
            
            # If not in request, check conversation context
            if not pending_session_id:
                pending_session_id = get_context_value(conversation_id, 'pending_analysis_session')
            
            print(f"🔍 HANDLER 4.5: Checking for pending labor session: {pending_session_id}")
            
            # If we have a session_id, load it and decide on processing approach
            if pending_session_id:
                print(f"✅ Found pending labor session: {pending_session_id}")
                
                try:
                    session_data = load_analysis_session(pending_session_id)
                    
                    if session_data and session_data.get('data_files'):
                        print(f"📊 Loading labor data for analysis...")
                        
                        # Get the file paths from session
                        data_files = session_data['data_files']
                        
                        if data_files and len(data_files) > 0:
                            file_path = data_files[0]  # Get first file
                            
                            print(f"📂 Labor file: {file_path}")
                            
                            # Check if file exists
                            if os.path.exists(file_path):
                                # Get file size to decide on processing approach
                                file_size = os.path.getsize(file_path)
                                file_size_mb = round(file_size / (1024 * 1024), 2)
                                
                                print(f"📏 File size: {file_size_mb}MB")
                                
                                # DECISION POINT: Large file = background, small file = immediate
                                LARGE_FILE_THRESHOLD_MB = 2.0  # Files >2MB go to background
                                
                                if file_size_mb > LARGE_FILE_THRESHOLD_MB:
                                    # ===== LARGE FILE: BACKGROUND PROCESSING =====
                                    print(f"🔄 File is large ({file_size_mb}MB) - using background processing")
                                    
                                    # Clear the pending session
                                    clear_conversation_context(conversation_id, 'pending_analysis_session')
                                    
                                    # Create task
                                    db = get_db()
                                    cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                                                       (user_request, 'processing_background', conversation_id))
                                    task_id = cursor.lastrowid
                                    db.commit()
                                    db.close()
                                    
                                    # Submit to labor analysis processor
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
                                        # Post initial "processing in background" message
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
                                            'success': True,
                                            'task_id': task_id,
                                            'conversation_id': conversation_id,
                                            'result': convert_markdown_to_html(initial_msg),
                                            'orchestrator': 'background_labor_processor',
                                            'job_id': job_id,
                                            'background_processing': True,
                                            'estimated_minutes': result['estimated_minutes'],
                                            'execution_time': time.time() - overall_start
                                        })
                                    else:
                                        # Background submission failed - fall back to immediate processing
                                        print(f"⚠️ Background processing failed: {result.get('error')}, falling back to immediate")
                                        # Continue to immediate processing below
                                
                                # ===== SMALL FILE OR FALLBACK: IMMEDIATE PROCESSING =====
                                print(f"✅ File is small ({file_size_mb}MB) or fallback - processing immediately")
                                
                                # Extract file contents for AI analysis
                                try:
                                    extracted = extract_multiple_files([file_path])
                                    
                                    if extracted['success'] and extracted.get('combined_text'):
                                        file_contents = extracted['combined_text']
                                        
                                        # Truncate if very large
                                        if len(file_contents) > 200000:
                                            print(f"⚠️ File content very large ({len(file_contents)} chars) - truncating")
                                            file_contents = file_contents[:200000] + f"\n\n... (truncated {len(file_contents) - 200000} characters)"
                                        
                                        print(f"✅ Loaded {len(file_contents)} chars from labor file")
                                        
                                        # Clear the pending session
                                        clear_conversation_context(conversation_id, 'pending_analysis_session')
                                        
                                        # Override user_request to make it analysis-focused
                                        user_request = f"Analyze this labor data comprehensively. Provide insights on overtime patterns, productivity, cost analysis, staffing efficiency, and actionable recommendations. File: {os.path.basename(file_path)}"
                                        
                                        print(f"✅ Proceeding to Handler 9 (GPT-4 File Analysis) with labor data...")
                                        
                                        # Set file_paths so Handler 9 knows we have files
                                        file_paths = [file_path]
                                        
                                        # Continue to Handler 9 with file_contents set
                                        # No early return - let it fall through
                                        
                                    else:
                                        print(f"❌ Could not extract labor file contents")
                                        return jsonify({
                                            'success': False,
                                            'error': 'Could not read labor data file'
                                        }), 500
                                        
                                except Exception as extract_error:
                                    print(f"❌ Error extracting labor file: {extract_error}")
                                    return jsonify({
                                        'success': False,
                                        'error': f'Error reading labor data: {str(extract_error)}'
                                    }), 500
                            else:
                                print(f"❌ Labor file not found: {file_path}")
                                return jsonify({
                                    'success': False,
                                    'error': 'Labor data file no longer exists'
                                }), 404
                        else:
                            print(f"⚠️ No files in session")
                    else:
                        print(f"⚠️ Session not found or has no files")
                        
                except Exception as session_error:
                    print(f"❌ Error loading labor session: {session_error}")
                    # Don't fail - just continue without session data
        
        # ========================================================================
        # END HANDLER 4.5
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
                
                # Reject files that are too large
                if file_info.get('is_too_large'):
                    file_size_mb = file_info.get('file_size_mb', 0)
                    return jsonify({
                        'success': False,
                        'error': f'File too large ({file_size_mb:.1f}MB). Maximum file size is 25MB.'
                    }), 413
                
                # Handle large files with progressive or smart analysis
                if file_info.get('is_large') and file_info.get('file_type') in ['.xlsx', '.xls']:
                    print(f"TRIGGERING ANALYSIS for {os.path.basename(file_path)}")
                    return handle_large_excel_initial(
                        file_path=file_path,
                        user_request=user_request,
                        conversation_id=conversation_id,
                        project_id=project_id,
                        mode=mode,
                        file_info=file_info,
                        overall_start=overall_start
                    )
        
        # HANDLER 8: Standard file handling (small files under 5MB)
        if file_paths:
            try:
                extracted = extract_multiple_files(file_paths)
                if extracted['success'] and extracted.get('combined_text'):
                    extracted_text = extracted['combined_text']
                    
                    # Truncate if very large
                    if len(extracted_text) > 200000:
                        print(f"File content very large ({len(extracted_text)} chars) - truncating")
                        extracted_text = extracted_text[:200000] + f"\n\n... (truncated {len(extracted_text) - 200000} characters)"
                    
                    # Append to file_contents
                    if file_contents:
                        file_contents += "\n\n" + extracted_text
                    else:
                        file_contents = extracted_text
            except Exception as extract_error:
                print(f"Could not extract file contents: {extract_error}")
        
        # HANDLER 9: GPT-4 file analysis (if file_contents exist)
        if file_contents:
            print(f"File content detected ({len(file_contents)} chars) - routing to GPT-4")
            
            # Create conversation if needed
            if not conversation_id:
                conversation_id = create_conversation(mode=mode, project_id=project_id)
                print(f"Created new conversation: {conversation_id}")
            
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
                        'success': True,
                        'task_id': task_id,
                        'conversation_id': conversation_id,
                        'result': formatted_output,
                        'orchestrator': 'gpt4_file_handler',
                        'execution_time': total_time,
                        'message': 'File analyzed by GPT-4'
                    })
                else:
                    db.close()
            except Exception as gpt_error:
                print(f"GPT-4 file analysis error: {gpt_error}")
                db.close()
        
        # ========================================================================
        # HANDLER 10: REGULAR CONVERSATION (NO FILES) - RESTORED Feb 13, 2026
        # This is the FULL orchestration handler that was stubbed out on Feb 10
        # ========================================================================
        
        # Check for file contents in conversation history
        if not file_contents and conversation_id:
            from database import get_conversation_file_contents
            file_contents = get_conversation_file_contents(conversation_id)
            if file_contents:
                print(f"Retrieved file contents from conversation history")
        
        # Parse clarification answers
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
            context_additions = []
            for field, value in clarification_answers.items():
                context_additions.append(f"{field}: {value}")
            if context_additions:
                user_request = f"{user_request}\n\nAdditional context:\n" + "\n".join(context_additions)
        
        # Create conversation if needed
        if not conversation_id:
            conversation_id = create_conversation(mode=mode, project_id=project_id)
            print(f"Created new conversation: {conversation_id}")
        
        add_message(conversation_id, 'user', user_request)
        
        # Initialize proactive agent
        proactive = None
        try:
            proactive = ProactiveAgent()
        except Exception as proactive_init_error:
            print(f"Proactive agent init failed: {proactive_init_error}")
        
        # Proactive pre-check
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
        
        # Get knowledge base
        import sys
        app_module = sys.modules.get('app')
        knowledge_base = getattr(app_module, 'knowledge_base', None) if app_module else None
        conversation_context = get_conversation_context(conversation_id, max_messages=10)
        
        # Get project file context
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
                                document_type='py',
                                file_path=code_result['output_path'],
                                file_size=file_size,
                                task_id=task_id,
                                conversation_id=conversation_id,
                                project_id=project_id,
                                title=f"Code Fix: {code_result['target_file']}",
                                description=deployment_pkg['change_summary'],
                                category='code'
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
                        'success': True,
                        'task_id': task_id,
                        'conversation_id': conversation_id,
                        'result': response_html,
                        'document_url': document_url,
                        'document_id': doc_id,
                        'document_created': True,
                        'document_type': 'py',
                        'execution_time': time.time() - overall_start,
                        'orchestrator': 'code_assistant',
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
                    filename=filename,
                    original_name=doc_title,
                    document_type='xlsx',
                    file_path=file_path,
                    file_size=file_size,
                    task_id=task_id,
                    conversation_id=conversation_id,
                    project_id=project_id,
                    title=doc_title,
                    description=f"Visual {shift_length}-hour {pattern_key} schedule pattern",
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
                
                session.pop('schedule_context', None)
                
                suggestions = []
                if proactive:
                    try:
                        suggestions = proactive.post_process_result(task_id, user_request, schedule_result['message'])
                    except:
                        pass
                
                db.close()
                
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'conversation_id': conversation_id,
                    'result': response_html,
                    'document_url': f'/api/generated-documents/{doc_id}/download',
                    'document_id': doc_id,
                    'document_created': True,
                    'document_type': 'xlsx',
                    'execution_time': time.time() - overall_start,
                    'orchestrator': 'pattern_schedule_generator',
                    'knowledge_applied': False,
                    'formatting_applied': True,
                    'specialists_used': [],
                    'consensus': None,
                    'suggestions': suggestions,
                    'shift_length': shift_length,
                    'pattern': pattern_key
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
                    'success': True,
                    'task_id': task_id,
                    'conversation_id': conversation_id,
                    'result': response_html,
                    'needs_input': True,
                    'waiting_for': schedule_result.get('waiting_for'),
                    'orchestrator': 'pattern_schedule_generator',
                    'execution_time': time.time() - overall_start
                })
        
        # Regular AI orchestration
        try:
            print(f"Analyzing task: {user_request[:100]}...")
            analysis = analyze_task_with_sonnet(user_request, knowledge_base=knowledge_base, file_paths=file_paths, file_contents=file_contents)
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
                    opus_result = handle_with_opus(user_request, analysis, knowledge_base=knowledge_base, file_paths=file_paths, file_contents=file_contents)
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
            if specialists_needed:
                for specialist_info in specialists_needed:
                    if isinstance(specialist_info, dict):
                        specialist = specialist_info.get('specialist') or specialist_info.get('ai')
                        specialist_task = specialist_info.get('task', user_request)
                    else:
                        specialist = specialist_info
                        specialist_task = user_request
                    if specialist and specialist.lower() != 'none':
                        result = execute_specialist_task(specialist, specialist_task, file_paths=file_paths, file_contents=file_contents)
                        specialist_results.append(result)
                        if result.get('success') and result.get('output'):
                            specialist_output = result.get('output')
            
            from orchestration.ai_clients import call_claude_opus, call_claude_sonnet
            
            def get_knowledge_context_for_prompt(kb, request, max_context=3000):
                """Get knowledge context to include in completion prompts"""
                if not kb:
                    return ""
                try:
                    context = kb.get_context_for_task(request, max_context=max_context)
                    if context:
                        return f"\n\n=== SHIFTWORK SOLUTIONS KNOWLEDGE BASE ===\nUse this information from our Hundreds of years of expertise:\n\n{context}\n\n=== END KNOWLEDGE BASE ===\n\n"
                    return ""
                except Exception as e:
                    print(f"Knowledge context retrieval failed: {e}")
                    return ""
            
            knowledge_context = get_knowledge_context_for_prompt(knowledge_base, user_request)
            
            # Learning context
            learning_context = ""
            try:
                learning_context = get_learning_context()
                if learning_context:
                    print(f"Retrieved learning context ({len(learning_context)} chars)")
            except Exception as learn_ctx_error:
                print(f"Could not get learning context (non-critical): {learn_ctx_error}")
            
            # Client profile context
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
            
            # Avoidance patterns context
            avoidance_context = ""
            try:
                avoidance_context = get_avoidance_context(days=30, limit=5)
                if avoidance_context:
                    print(f"Retrieved avoidance patterns")
            except Exception as avoid_error:
                print(f"Could not get avoidance context (non-critical): {avoid_error}")
            
            # Specialized knowledge
            specialized_context = ""
            try:
                specialist = get_specialized_knowledge()
                
                industry = None
                if project_id:
                    db_temp = get_db()
                    proj = db_temp.execute('SELECT industry FROM projects WHERE project_id = ?', (project_id,)).fetchone()
                    db_temp.close()
                    if proj:
                        industry = proj['industry']
                
                specialized_context = specialist.build_expertise_context(user_request, industry)
                if specialized_context:
                    print(f"Injected specialized knowledge for {industry or 'general'}")
            except Exception as spec_error:
                print(f"Could not get specialized knowledge: {spec_error}")
            
            # Conversation summary
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
            
            # Initialize intelligence
            intelligence = None
            try:
                intelligence = EnhancedIntelligence()
                print("EnhancedIntelligence initialized")
            except Exception as intel_error:
                print(f"EnhancedIntelligence init failed (non-critical): {intel_error}")
                intelligence = None
            
            # Build project context
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
            
            # Build conversation history
            conversation_history = ""
            if conversation_context and len(conversation_context) > 1:
                conversation_history = "\n\n=== CONVERSATION HISTORY ===\n"
                for msg in conversation_context[:-1]:
                    role_label = "User" if msg['role'] == 'user' else "Assistant"
                    content_preview = msg['content'][:500] + '...' if len(msg['content']) > 500 else msg['content']
                    conversation_history += f"{role_label}: {content_preview}\n"
                conversation_history += "=== END CONVERSATION HISTORY ===\n\n"
            
            if specialist_output:
                actual_output = specialist_output
            else:
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
                
                completion_prompt = f"""{knowledge_context}{project_context}{file_context}{conversation_history}{learning_context}{client_profile_context}{avoidance_context}{specialized_context}{summary_context}{file_section}

USER REQUEST: {user_request}

Please complete this request fully. Provide the actual deliverable.
Be comprehensive and professional."""
                
                if opus_guidance:
                    completion_prompt += f"\n\nSTRATEGIC GUIDANCE:\n{opus_guidance}"
                
                if file_contents:
                    print(f"Completion prompt contains {len(file_contents)} chars of file content")
                
                if orchestrator == 'opus':
                    response = call_claude_opus(completion_prompt, conversation_history=conversation_context, files_attached=bool(file_contents))
                else:
                    response = call_claude_sonnet(completion_prompt, conversation_history=conversation_context, files_attached=bool(file_contents))
                
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
            
            # Learning
            if intelligence and actual_output and not actual_output.startswith('Error'):
                try:
                    intelligence.learn_from_interaction(user_request, actual_output, user_feedback=None)
                    print("EnhancedIntelligence learned from this interaction")
                except Exception as learn_error:
                    print(f"EnhancedIntelligence learning failed (non-critical): {learn_error}")
            
            # Update client profile
            if project_id:
                try:
                    db_temp = get_db()
                    project = db_temp.execute('SELECT client_name, industry FROM projects WHERE project_id = ?', (project_id,)).fetchone()
                    db_temp.close()
                    
                    if project and project['client_name']:
                        interaction_data = {
                            'approach': orchestrator,
                            'approach_worked': True,
                            'industry': project['industry'],
                            'preferences': {}
                        }
                        
                        update_client_profile(project['client_name'], interaction_data)
                        print(f"Updated profile for {project['client_name']}")
                except Exception as profile_update_error:
                    print(f"Client profile update failed (non-critical): {profile_update_error}")
            
            # Auto-learn from conversation
            try:
                learn_from_conversation(user_request, actual_output if actual_output else '')
            except Exception as learn_error:
                print(f"Auto-learning failed (non-critical): {learn_error}")
            
            # Proactive curiosity
            curious_question = None
            try:
                curiosity_engine = get_curiosity_engine()
                curiosity_check = curiosity_engine.should_be_curious(
                    conversation_id,
                    {
                        'user_request': user_request,
                        'ai_response': actual_output if actual_output else '',
                        'task_completed': True
                    }
                )
                
                if curiosity_check['should_ask']:
                    curious_question = curiosity_check['question']
                    print(f"Curious follow-up: {curious_question}")
            except Exception as curiosity_error:
                print(f"Curiosity engine failed (non-critical): {curiosity_error}")
            
            return jsonify({
                'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                'result': formatted_output, 'orchestrator': orchestrator,
                'specialists_used': [s.get('specialist') for s in specialist_results] if specialist_results else [],
                'consensus': consensus_result, 'execution_time': total_time,
                'knowledge_applied': knowledge_applied, 'knowledge_used': knowledge_applied,
                'knowledge_sources': knowledge_sources, 'formatting_applied': True,
                'suggestions': suggestions,
                'curious_question': curious_question
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


# I did no harm and this file is not truncated
