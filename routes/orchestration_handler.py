"""
Orchestration Handler - Main AI Task Processing
Created: January 31, 2026
Last Updated: February 1, 2026 - FIXED FILE BROWSER BUG

This file handles the main /api/orchestrate endpoint that processes user requests.
Separated from core.py to make it easier to fix and maintain.

UPDATES:
- February 1, 2026: FIXED file_contents UnboundLocalError in file browser
  * Initialize file_contents early to prevent crashes
  * Added complete file_ids handling for project file selection
  * File browser now fully functional!
- January 31, 2026: File upload contents now properly passed to Claude
- January 31, 2026: Added progressive analysis for large Excel files (hybrid approach)
  * Files under 5MB: Full analysis
  * Files 5-25MB: Analyze first 100 rows, ask user if they want more
  * Files over 25MB: Rejected with helpful message
  * User can request: "next 500", "next 1000", "analyze all"

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify, session
import time
import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename

# Import all the utilities we need
from database import (
    get_db, create_conversation, get_conversation, add_message,
    get_conversation_context, save_generated_document,
    get_schedule_context, save_schedule_context
)
from orchestration import (
    analyze_task_with_sonnet,
    handle_with_opus,
    execute_specialist_task,
    validate_with_consensus
)
from database_file_management import get_files_for_ai_context, get_file_stats_by_project
from file_content_reader import extract_multiple_files
from code_assistant_agent import get_code_assistant
from orchestration.proactive_agent import ProactiveAgent
from schedule_request_handler_combined import get_combined_schedule_handler
from progressive_file_analyzer import get_progressive_analyzer
from conversation_learning import learn_from_conversation  # Auto-learning from conversations

# Create blueprint
orchestration_bp = Blueprint('orchestration', __name__)


def convert_markdown_to_html(text):
    """Convert markdown text to styled HTML"""
    if not text:
        return text
    import markdown
    html = markdown.markdown(text, extensions=['extra', 'nl2br'])
    return f'<div style="line-height: 1.8; color: #333;">{html}</div>'


def should_create_document(user_request):
    """Determine if we should create a downloadable document"""
    doc_keywords = ['create', 'generate', 'make', 'write', 'draft', 'prepare',
                    'document', 'report', 'proposal', 'presentation', 'schedule',
                    'contract', 'agreement', 'summary', 'analysis']
    request_lower = user_request.lower()
    for keyword in doc_keywords:
        if keyword in request_lower:
            if 'presentation' in request_lower or 'powerpoint' in request_lower or 'slides' in request_lower:
                return True, 'pptx'
            elif 'spreadsheet' in request_lower or 'excel' in request_lower:
                return True, 'xlsx'
            elif 'pdf' in request_lower:
                return True, 'pdf'
            else:
                return True, 'docx'
    return False, None


def get_knowledge_context_for_prompt(knowledge_base, user_request, max_context=3000):
    """Get knowledge context to include in completion prompts"""
    if not knowledge_base:
        return ""
    try:
        context = knowledge_base.get_context_for_task(user_request, max_context=max_context)
        if context:
            return f"\n\n=== SHIFTWORK SOLUTIONS KNOWLEDGE BASE ===\nUse this information from our 30+ years of expertise:\n\n{context}\n\n=== END KNOWLEDGE BASE ===\n\n"
        return ""
    except Exception as e:
        print(f"Knowledge context retrieval failed: {e}")
        return ""


def generate_document_title(user_request, doc_type):
    """Generate a human-readable title from the user request"""
    title = user_request.strip()
    if title:
        title = title[0].upper() + title[1:]
    if len(title) > 60:
        title = title[:57] + '...'
    return title


def categorize_document(user_request, doc_type):
    """Determine document category based on request content"""
    request_lower = user_request.lower()
    if any(word in request_lower for word in ['schedule', 'dupont', 'panama', 'pitman', '2-2-3']):
        return 'schedule'
    elif any(word in request_lower for word in ['proposal', 'bid', 'quote']):
        return 'proposal'
    elif any(word in request_lower for word in ['report', 'analysis', 'summary']):
        return 'report'
    elif any(word in request_lower for word in ['contract', 'agreement', 'legal']):
        return 'contract'
    elif any(word in request_lower for word in ['checklist', 'list', 'todo']):
        return 'checklist'
    elif any(word in request_lower for word in ['email', 'letter', 'memo']):
        return 'communication'
    elif any(word in request_lower for word in ['presentation', 'slides', 'deck']):
        return 'presentation'
    else:
        return 'general'


@orchestration_bp.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    """
    Main orchestration endpoint with proactive intelligence and conversation memory.
    
    UPDATED January 31, 2026: Extracted to separate file for better maintainability
    FIXED January 31, 2026: File contents now properly passed to Claude AI
    """
    try:
        # Parse request data (JSON or FormData)
        if request.is_json:
            data = request.json
            user_request = data.get('request')
            enable_consensus = data.get('enable_consensus', True)
            project_id = data.get('project_id')
            conversation_id = data.get('conversation_id')
            mode = data.get('mode', 'quick')
            file_paths = []
        else:
            user_request = request.form.get('request')
            enable_consensus = request.form.get('enable_consensus', 'true').lower() == 'true'
            project_id = request.form.get('project_id')
            conversation_id = request.form.get('conversation_id')
            mode = request.form.get('mode', 'quick')
            
            # Handle file uploads
            file_paths = []
            if 'files' in request.files:
                files = request.files.getlist('files')
                
                if project_id:
                    upload_dir = f'/tmp/projects/{project_id}'
                else:
                    upload_dir = f'/tmp/uploads'
                os.makedirs(upload_dir, exist_ok=True)
                
                for file in files:
                    if file and file.filename:
                        filename = secure_filename(file.filename)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        name, ext = os.path.splitext(filename)
                        filename = f"{name}_{timestamp}{ext}"
                        file_path = os.path.join(upload_dir, filename)
                        file.save(file_path)
                        file_paths.append(file_path)
                        print(f"📎 Saved uploaded file: {filename}")
        
        # ====================================================================
        # CRITICAL FIX February 1, 2026: Initialize file_contents early
        # This prevents UnboundLocalError when file_ids are used
        # ====================================================================
        file_contents = ""
        
        # ====================================================================
        # FILE BROWSER SUPPORT - Handle file_ids from project file selection
        # Added: January 31, 2026
        # Fixed: February 1, 2026 - file_contents initialized above
        # ====================================================================
        
        # Check if user selected files from project (file_ids parameter)
        file_ids_param = None
        if request.is_json:
            file_ids_param = data.get('file_ids')
        else:
            file_ids_param = request.form.get('file_ids')
        
        # 🔍 DIAGNOSTIC STEP 1: Log initial file_ids detection
        print(f"🔍 DIAGNOSTIC STEP 1: file_ids_param = {file_ids_param}")
        print(f"🔍 DIAGNOSTIC STEP 1: file_ids_param type = {type(file_ids_param)}")
        print(f"🔍 DIAGNOSTIC STEP 1: project_id = {project_id}")
        print(f"🔍 DIAGNOSTIC STEP 1: request.is_json = {request.is_json}")
        
        if file_ids_param and project_id:
            try:
                # Parse file_ids (comes as JSON string)
                if isinstance(file_ids_param, str):
                    import json
                    file_ids = json.loads(file_ids_param)
                else:
                    file_ids = file_ids_param
                
                # 🔍 DIAGNOSTIC STEP 2: Log parsed file_ids
                print(f"🔍 DIAGNOSTIC STEP 2: Parsed file_ids = {file_ids}")
                print(f"🔍 DIAGNOSTIC STEP 2: Number of files = {len(file_ids) if file_ids else 0}")
                
                if file_ids and len(file_ids) > 0:
                    print(f"📎 User selected {len(file_ids)} file(s) from project {project_id}")
                    
                    # Fetch file context from database
                    from database_file_management import get_files_for_ai_context
                    
                    # Get detailed file info with actual file contents
                    selected_file_context = get_files_for_ai_context(
                        project_id=project_id, 
                        file_ids=file_ids,  # Pass specific file IDs
                        max_files=len(file_ids),  # Get all selected files
                        max_chars_per_file=10000  # Allow up to 10k chars per file
                    )
                    
                    # 🔍 DIAGNOSTIC STEP 3: Log retrieved context
                    print(f"🔍 DIAGNOSTIC STEP 3: selected_file_context returned")
                    print(f"🔍 DIAGNOSTIC STEP 3: Context length = {len(selected_file_context) if selected_file_context else 0}")
                    if selected_file_context:
                        print(f"🔍 DIAGNOSTIC STEP 3: Context preview (first 200 chars):")
                        print(f"{selected_file_context[:200]}")
                    else:
                        print(f"🔍 DIAGNOSTIC STEP 3: Context is EMPTY/NONE")
                    
                    if selected_file_context:
                        print(f"✅ Retrieved context for {len(file_ids)} selected file(s)")
                        
                        # Add to file_contents for AI processing
                        file_contents += "\n\n" + selected_file_context
                        
                        # 🔍 DIAGNOSTIC STEP 3 (continued): Log file_contents after adding
                        print(f"🔍 DIAGNOSTIC STEP 3: file_contents now has {len(file_contents)} chars")
                        print(f"🔍 DIAGNOSTIC STEP 3: file_contents preview (first 200 chars):")
                        print(f"{file_contents[:200]}")
                    else:
                        print(f"⚠️ No file context retrieved for file_ids: {file_ids}")
                        
            except Exception as file_ids_error:
                print(f"⚠️ Error processing file_ids: {file_ids_error}")
                import traceback
                traceback.print_exc()
        
        # ====================================================================
        # END FILE BROWSER SUPPORT
        # ====================================================================
        
        if not user_request:
            return jsonify({'success': False, 'error': 'Request text required'}), 400
        
        if file_paths:
            print(f"📎 {len(file_paths)} file(s) attached to request")
        
        overall_start = time.time()
        
        # ====================================================================
        # PROGRESSIVE FILE ANALYSIS - New Feature (January 31, 2026)
        # ====================================================================
        
        # Check if this is a continuation request (user asking for more rows)
        analyzer = get_progressive_analyzer()
        continuation_request = analyzer.parse_user_continuation_request(user_request)
        
        if continuation_request and conversation_id:
            # User is requesting more data from a previous file upload
            # Retrieve file path from session
            file_analysis_state = session.get(f'file_analysis_{conversation_id}')
            
            if file_analysis_state:
                return handle_progressive_continuation(
                    conversation_id=conversation_id,
                    user_request=user_request,
                    continuation_request=continuation_request,
                    file_analysis_state=file_analysis_state,
                    overall_start=overall_start
                )
        
        # Check for large Excel files that need progressive analysis
        if file_paths:
            for file_path in file_paths:
                file_info = analyzer.get_file_info(file_path)
                
                # Reject files that are too large
                if file_info.get('is_too_large'):
                    file_size_mb = file_info.get('file_size_mb', 0)
                    return jsonify({
                        'success': False,
                        'error': f'File too large ({file_size_mb}MB). Maximum file size is 25MB.',
                        'suggestion': 'Please reduce file size by:\n- Filtering to specific date range\n- Removing unnecessary columns\n- Splitting into multiple smaller files\n- Exporting only relevant sheets'
                    }), 413
                
                # Handle large files with progressive analysis
                if file_info.get('is_large') and file_info.get('file_type') in ['.xlsx', '.xls']:
                    return handle_large_excel_initial(
                        file_path=file_path,
                        user_request=user_request,
                        conversation_id=conversation_id,
                        project_id=project_id,
                        mode=mode,
                        file_info=file_info,
                        overall_start=overall_start
                    )
        
        # ====================================================================
        # STANDARD FILE HANDLING (Small files - under 5MB)
        # ====================================================================
        
        # Extract file contents from uploaded files (APPEND to file_contents)
        # NOTE: file_contents already initialized above and may contain file_ids context
        if file_paths:
            try:
                extracted = extract_multiple_files(file_paths)
                if extracted['success'] and extracted.get('combined_text'):
                    extracted_text = extracted['combined_text']
                    
                    # Check if extracted content is too long (over 50,000 chars)
                    if len(extracted_text) > 50000:
                        print(f"⚠️ File content very large ({len(extracted_text)} chars) - truncating")
                        extracted_text = extracted_text[:50000] + f"\n\n... (truncated {len(extracted_text) - 50000} characters for performance)"
                    
                    # APPEND to file_contents (don't overwrite file_ids context!)
                    if file_contents:
                        file_contents += "\n\n" + extracted_text
                    else:
                        file_contents = extracted_text
                else:
                    print(f"⚠️ File extraction returned no content")
            except Exception as extract_error:
                print(f"⚠️ Could not extract file contents: {extract_error}")
        
        overall_start = time.time()
        # 🔍 DIAGNOSTIC STEP 4: Check if file_contents will route to GPT-4
        print(f"🔍 DIAGNOSTIC STEP 4: Checking file_contents for GPT-4 routing")
        print(f"🔍 DIAGNOSTIC STEP 4: file_contents is truthy = {bool(file_contents)}")
        print(f"🔍 DIAGNOSTIC STEP 4: file_contents length = {len(file_contents) if file_contents else 0}")
        
        # Route file analysis to GPT-4 (better for file handling)
        if file_contents:
            print(f"🔍 DIAGNOSTIC STEP 4: ROUTING TO GPT-4! file_contents has {len(file_contents)} chars")
            print(f"📎 File content detected ({len(file_contents)} chars) - routing to GPT-4")
        # Route file analysis to GPT-4 (better for file handling)
        if file_contents:
            print(f"📎 File content detected ({len(file_contents)} chars) - routing to GPT-4")
            
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
            
            file_analysis_prompt = f"""The user has uploaded files and asked: {user_request}

Here are the file contents:

{file_contents}

Please analyze these files and respond to the user's request. Be specific and reference actual content from the files."""

            try:
                gpt_response = call_gpt4(file_analysis_prompt, max_tokens=4000)
                
                if not gpt_response.get('error') and gpt_response.get('content'):
                    actual_output = gpt_response.get('content', '')
                    formatted_output = convert_markdown_to_html(actual_output)
                    
                    # ================================================================
                    # CREATE PROFESSIONAL DOCUMENT - February 1, 2026
                    # Use docx-js for professional formatting
                    # ================================================================
                    document_created = False
                    document_url = None
                    document_id = None
                    
                                                                  
                    try:
                        from document_creation_helper import create_analysis_document
                        
                        # Get analyzed file names
                        analyzed_files = []
                        if file_ids_param:
                            # Parse file_ids if needed
                            if isinstance(file_ids_param, str):
                                import json
                                file_ids = json.loads(file_ids_param)
                            else:
                                file_ids = file_ids_param
                            
                            from database_file_management import get_project_manager
                            pm = get_project_manager()
                            for fid in file_ids:
                                file_info = pm.get_file(fid)
                                if file_info:
                                    analyzed_files.append(file_info.get('original_filename', 'Unknown'))
                        
                        file_names_str = ", ".join(analyzed_files) if analyzed_files else "Uploaded Files"
                        
                        # Create document using Python (not Node.js!)
                        print(f"📄 Creating professional analysis document...")
                        doc_result = create_analysis_document(
                            analysis_text=actual_output,
                            file_names_str=file_names_str,
                            output_path='/tmp/file_analysis.docx'
                        )
                        
                        if doc_result['success'] and os.path.exists('/tmp/file_analysis.docx'):
                            # Save to database
                            file_size = os.path.getsize('/tmp/file_analysis.docx')
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f'file_analysis_{timestamp}.docx'
                            
                            # Move to permanent location
                            final_path = f'/tmp/{filename}'
                            os.rename('/tmp/file_analysis.docx', final_path)
                            
                            document_id = save_generated_document(
                                filename=filename,
                                original_name=f"File Analysis - {file_names_str[:50]}",
                                document_type='docx',
                                file_path=final_path,
                                file_size=file_size,
                                task_id=task_id,
                                conversation_id=conversation_id,
                                project_id=project_id,
                                title=f"File Analysis Report",
                                description=f"AI analysis of {file_names_str}",
                                category='report'
                            )
                            
                            document_created = True
                            document_url = f'/api/generated-documents/{document_id}/download'
                            print(f"✅ Created professional analysis document: {filename}")
                        else:
                            print(f"⚠️ Document creation failed: {doc_result.get('error', 'Unknown error')}")
                    
                    except Exception as doc_error:
                        print(f"⚠️ Could not create analysis document: {doc_error}")
                        import traceback
                        traceback.print_exc()  
                    
                    # ================================================================
                    # END DOCUMENT CREATION
                    # ================================================================
                    
                    total_time = time.time() - overall_start
                    db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                              ('completed', 'gpt4_file_handler', total_time, task_id))
                    db.commit()
                    db.close()
                    
                    add_message(conversation_id, 'assistant', actual_output, task_id,
                               {'orchestrator': 'gpt4_file_handler', 'file_analysis': True, 'execution_time': total_time})
                 
                    # Auto-learn from this conversation
                    try:
                        learn_from_conversation(user_request, actual_output)
                    except Exception as learn_error:
                        print(f"⚠️ Auto-learning failed (non-critical): {learn_error}")
                  
                    return jsonify({
                        'success': True,
                        'task_id': task_id,
                        'conversation_id': conversation_id,
                        'result': formatted_output,
                        'orchestrator': 'gpt4_file_handler',
                        'execution_time': total_time,
                        'message': '📎 File analyzed by GPT-4',
                        'document_created': document_created,
                        'document_url': document_url,
                        'document_id': document_id,
                        'document_type': 'docx' if document_created else None
                    })
                   
                else:
                    print(f"⚠️ GPT-4 analysis failed: {gpt_response.get('content', 'Unknown error')}")
                    db.close()
                    
            except Exception as gpt_error:
                print(f"GPT-4 file analysis error: {gpt_error}")
                db.close()

        # Check for file contents in conversation history
        if not file_contents and conversation_id:
            from database import get_conversation_file_contents
            file_contents = get_conversation_file_contents(conversation_id)
            if file_contents:
                print(f"📎 Retrieved file contents from conversation history")
                
                db = get_db()
                cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                               (user_request, 'processing', conversation_id))
                task_id = cursor.lastrowid
                db.commit()
                
                from orchestration.ai_clients import call_gpt4
                
                file_analysis_prompt = f"""The user previously uploaded files and is now asking a follow-up question: {user_request}

Here are the file contents from the previous upload:

{file_contents}

Please respond to the user's follow-up question based on these files."""

                try:
                    gpt_response = call_gpt4(file_analysis_prompt, max_tokens=4000)
                    
                    if not gpt_response.get('error') and gpt_response.get('content'):
                        actual_output = gpt_response.get('content', '')
                        formatted_output = convert_markdown_to_html(actual_output)
                        
                        total_time = time.time() - overall_start
                        db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                                  ('completed', 'gpt4_file_handler', total_time, task_id))
                        db.commit()
                        db.close()
                        
                        add_message(conversation_id, 'assistant', actual_output, task_id,
                               {'orchestrator': 'gpt4_file_handler', 'file_analysis': True, 'execution_time': total_time,
                                'document_created': document_created, 'document_id': document_id})
                        
                        return jsonify({
                            'success': True,
                            'task_id': task_id,
                            'conversation_id': conversation_id,
                            'result': formatted_output,
                            'orchestrator': 'gpt4_file_handler',
                            'execution_time': total_time,
                            'message': '📎 Follow-up answered using uploaded files'
                        })
                    else:
                        db.close()
                        
                except Exception as gpt_error:
                    print(f"GPT-4 follow-up error: {gpt_error}")
                    db.close()
        
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
            print(f"✅ Clarification answers received: {clarification_answers}")
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
                file_context = get_files_for_ai_context(project_id, max_files=5, max_chars_per_file=2000)
                if file_context:
                    print(f"✅ Added file context from project {project_id}")
            except Exception as file_ctx_error:
                print(f"⚠️ Could not load file context: {file_ctx_error}")
        
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
                print(f"🔧 Code feedback detected for: {feedback_check['target_file']}")
                
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

        # Introspection check
        try:
            from introspection import is_introspection_request, get_introspection_engine
            
            introspection_check = is_introspection_request(user_request)
            
            if introspection_check['is_introspection']:
                print(f"🔍 Introspection request detected")
                
                intro_engine = get_introspection_engine()
                action = introspection_check['action']
                
                if action == 'run':
                    days = 7
                    if 'monthly' in user_request.lower() or '30' in user_request:
                        days = 30
                    
                    report = intro_engine.run_introspection(days=days, is_monthly=(days >= 28))
                    response_html = convert_markdown_to_html(report.get('reflection', ''))
                    
                    db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                              ('completed', 'introspection_engine', time.time() - overall_start, task_id))
                    db.commit()
                    
                    add_message(conversation_id, 'assistant', report.get('reflection', ''), task_id,
                               {'orchestrator': 'introspection_engine', 'introspection_id': report.get('insight_id')})
                    
                    db.close()
                    
                    return jsonify({
                        'success': True,
                        'task_id': task_id,
                        'conversation_id': conversation_id,
                        'result': response_html,
                        'orchestrator': 'introspection_engine',
                        'execution_time': time.time() - overall_start,
                        'introspection_report': {
                            'id': report.get('insight_id'),
                            'health_score': report.get('summary', {}).get('health_score', 0),
                            'period_days': report.get('period_days', days),
                            'type': report.get('introspection_type', 'weekly')
                        }
                    })
                
                elif action == 'show_latest':
                    latest = intro_engine.get_latest_introspection()
                    
                    if not latest or not latest.get('full_report'):
                        response_text = "No introspection has been run yet."
                    else:
                        response_text = latest.get('full_report', {}).get('reflection', 'No reflection available.')
                    
                    response_html = convert_markdown_to_html(response_text)
                    
                    db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ? WHERE id = ?',
                              ('completed', 'introspection_engine', task_id))
                    db.commit()
                    
                    add_message(conversation_id, 'assistant', response_text, task_id,
                               {'orchestrator': 'introspection_engine'})
                    
                    db.close()
                    
                    return jsonify({
                        'success': True,
                        'task_id': task_id,
                        'conversation_id': conversation_id,
                        'result': response_html,
                        'orchestrator': 'introspection_engine',
                        'execution_time': time.time() - overall_start
                    })
        
        except ImportError:
            print("ℹ️  Introspection not available")
        except Exception as intro_error:
            print(f"⚠️  Introspection detection failed: {intro_error}")
        
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
            knowledge_context = get_knowledge_context_for_prompt(knowledge_base, user_request)

            # Build project context
            project_context = ""
            if project_id:
                try:
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
                    print(f"⚠️ Could not load project context: {proj_ctx_error}")
            
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
                # 🔧 CRITICAL FIX: Add file contents to completion prompt
                if file_contents:
                    file_section = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📎 ATTACHED FILES - READ THESE CAREFULLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{file_contents}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
                else:
                    file_section = ""

                completion_prompt = f"""{knowledge_context}{project_context}{file_context}{conversation_history}{file_section}

USER REQUEST: {user_request}

Please complete this request fully. Provide the actual deliverable.
Be comprehensive and professional."""

                if opus_guidance:
                    completion_prompt += f"\n\nSTRATEGIC GUIDANCE:\n{opus_guidance}"

                if file_contents:
                    print(f"🔍 Completion prompt contains {len(file_contents)} chars of file content")
                              
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
            
            # Document creation
            document_created = False
            document_url = None
            document_type = None
            document_id = None
            
            should_create, doc_type = should_create_document(user_request)
            if should_create and actual_output and not actual_output.startswith('Error'):
                try:
                    from docx import Document
                    from docx.shared import Pt
                    doc = Document()
                    title = doc.add_heading('Shiftwork Solutions LLC', 0)
                    title.alignment = 1
                    lines = actual_output.split('\n')
                    for line in lines:
                        if line.strip():
                            if line.startswith('#'):
                                level = len(line) - len(line.lstrip('#'))
                                text = line.lstrip('#').strip()
                                doc.add_heading(text, level=min(level, 3))
                            else:
                                p = doc.add_paragraph(line)
                                p.style.font.size = Pt(11)
                    
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f'shiftwork_document_{timestamp}.docx'
                    save_paths = [f'/tmp/{filename}', f'./{filename}']
                    
                    saved = False
                    saved_path = None
                    for filepath in save_paths:
                        try:
                            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
                            doc.save(filepath)
                            saved = True
                            saved_path = filepath
                            print(f"Document created: {filepath}")
                            break
                        except Exception as save_error:
                            print(f"Could not save to {filepath}: {save_error}")
                    
                    if saved and saved_path:
                        file_size = os.path.getsize(saved_path)
                        doc_title = generate_document_title(user_request, 'docx')
                        doc_category = categorize_document(user_request, 'docx')
                        document_id = save_generated_document(
                            filename=filename, original_name=doc_title, document_type='docx',
                            file_path=saved_path, file_size=file_size, task_id=task_id,
                            conversation_id=conversation_id, project_id=project_id,
                            title=doc_title, description=f"Generated from: {user_request[:100]}",
                            category=doc_category
                        )
                        document_created = True
                        document_url = f'/api/generated-documents/{document_id}/download'
                        document_type = 'docx'
                except Exception as doc_error:
                    print(f"Document creation failed: {doc_error}")
            
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
                        'document_created': document_created, 'document_type': document_type,
                        'document_id': document_id, 'execution_time': total_time})
            
            suggestions = []
            if proactive:
                try:
                    suggestions = proactive.post_process_result(task_id, user_request, actual_output if actual_output else '')
                except Exception as suggest_error:
                    print(f"Suggestion generation failed: {suggest_error}")
            
            return jsonify({
                'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                'result': formatted_output, 'orchestrator': orchestrator,
                'specialists_used': [s.get('specialist') for s in specialist_results] if specialist_results else [],
                'consensus': consensus_result, 'execution_time': total_time,
                'knowledge_applied': knowledge_applied, 'knowledge_used': knowledge_applied,
                'knowledge_sources': knowledge_sources, 'formatting_applied': True,
                'document_created': document_created, 'document_url': document_url,
                'document_id': document_id, 'document_type': document_type, 'suggestions': suggestions
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


def handle_large_excel_initial(file_path, user_request, conversation_id, project_id, mode, file_info, overall_start):
    """
    Handle initial upload of a large Excel file - analyze first 100 rows.
    Added: January 31, 2026
    """
    try:
        analyzer = get_progressive_analyzer()
        
        # Extract first 100 rows
        chunk_result = analyzer.extract_excel_chunk(file_path, start_row=0, num_rows=100)
        
        if not chunk_result['success']:
            return jsonify({
                'success': False,
                'error': f"Could not analyze Excel file: {chunk_result.get('error')}"
            }), 500
        
        # Create conversation if needed
        if not conversation_id:
            conversation_id = create_conversation(mode=mode, project_id=project_id)
            print(f"Created new conversation: {conversation_id}")
        
        # Store file analysis state in session
        session[f'file_analysis_{conversation_id}'] = {
            'file_path': file_path,
            'current_position': chunk_result['end_row'],
            'total_rows': chunk_result['total_rows'],
            'columns': chunk_result['columns'],
            'file_name': os.path.basename(file_path),
            'file_size_mb': file_info['file_size_mb']
        }
        
        # Create task
        db = get_db()
        cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                           (user_request, 'processing', conversation_id))
        task_id = cursor.lastrowid
        db.commit()
        
        # Build analysis prompt
        from orchestration.ai_clients import call_gpt4
        
        analysis_prompt = f"""The user uploaded a large Excel file ({file_info['file_size_mb']}MB, {chunk_result['total_rows']:,} rows) and asked: {user_request}

This is a LARGE file, so I'm showing you the FIRST 100 ROWS as a preview.

{chunk_result['summary']}

{chunk_result['text_preview']}

Please analyze this preview and respond to the user's request based on what you can see in these first 100 rows."""

        gpt_response = call_gpt4(analysis_prompt, max_tokens=3000)
        
        if not gpt_response.get('error') and gpt_response.get('content'):
            ai_analysis = gpt_response.get('content', '')
            
            # Add continuation prompt
            continuation_prompt = analyzer.generate_continuation_prompt(chunk_result)
            full_response = ai_analysis + continuation_prompt
            
            formatted_output = convert_markdown_to_html(full_response)
            
            total_time = time.time() - overall_start
            db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                      ('completed', 'gpt4_progressive_excel', total_time, task_id))
            db.commit()
            db.close()
            
            add_message(conversation_id, 'assistant', full_response, task_id,
                       {'orchestrator': 'gpt4_progressive_excel', 'rows_analyzed': 100, 
                        'total_rows': chunk_result['total_rows'], 'execution_time': total_time})
            
            return jsonify({
                'success': True,
                'task_id': task_id,
                'conversation_id': conversation_id,
                'result': formatted_output,
                'orchestrator': 'gpt4_progressive_excel',
                'execution_time': total_time,
                'progressive_analysis': True,
                'rows_analyzed': 100,
                'total_rows': chunk_result['total_rows'],
                'rows_remaining': chunk_result['rows_remaining']
            })
        else:
            db.close()
            return jsonify({
                'success': False,
                'error': 'Could not analyze Excel file'
            }), 500
            
    except Exception as e:
        import traceback
        print(f"Large Excel handling error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


def handle_progressive_continuation(conversation_id, user_request, continuation_request, file_analysis_state, overall_start):
    """
    Handle user requesting more rows from a large Excel file.
    Added: January 31, 2026
    """
    try:
        analyzer = get_progressive_analyzer()
        
        file_path = file_analysis_state['file_path']
        current_position = file_analysis_state['current_position']
        total_rows = file_analysis_state['total_rows']
        
        # Determine how many rows to analyze
        action = continuation_request['action']
        
        if action == 'analyze_next':
            num_rows = continuation_request['num_rows']
            start_row = current_position
        elif action == 'analyze_all':
            num_rows = None  # All remaining
            start_row = current_position
        elif action == 'analyze_range':
            start_row = continuation_request['start_row']
            num_rows = continuation_request['end_row'] - start_row
        else:
            return jsonify({'success': False, 'error': 'Invalid continuation action'}), 400
        
        # Extract the requested chunk
        chunk_result = analyzer.extract_excel_chunk(file_path, start_row=start_row, num_rows=num_rows)
        
        if not chunk_result['success']:
            return jsonify({
                'success': False,
                'error': f"Could not extract data: {chunk_result.get('error')}"
            }), 500
        
        # Update session state
        session[f'file_analysis_{conversation_id}']['current_position'] = chunk_result['end_row']
        
        # Create task
        db = get_db()
        cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                           (user_request, 'processing', conversation_id))
        task_id = cursor.lastrowid
        db.commit()
        
        # Build analysis prompt
        from orchestration.ai_clients import call_gpt4
        
        analysis_prompt = f"""The user requested more data from their Excel file. They said: "{user_request}"

Here is the next chunk of data:

{chunk_result['summary']}

{chunk_result['text_preview']}

Please analyze this data and respond to the user's request."""

        gpt_response = call_gpt4(analysis_prompt, max_tokens=3000)
        
        if not gpt_response.get('error') and gpt_response.get('content'):
            ai_analysis = gpt_response.get('content', '')
            
            # Add continuation prompt if more rows remain
            if chunk_result['rows_remaining'] > 0:
                continuation_prompt = analyzer.generate_continuation_prompt(chunk_result)
                full_response = ai_analysis + continuation_prompt
            else:
                full_response = ai_analysis + "\n\n✅ **Analysis complete!** All rows have been analyzed."
                # Clear session state
                session.pop(f'file_analysis_{conversation_id}', None)
            
            formatted_output = convert_markdown_to_html(full_response)
            
            total_time = time.time() - overall_start
            db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                      ('completed', 'gpt4_progressive_excel', total_time, task_id))
            db.commit()
            db.close()
            
            add_message(conversation_id, 'assistant', full_response, task_id,
                       {'orchestrator': 'gpt4_progressive_excel', 'rows_analyzed': chunk_result['rows_analyzed'],
                        'total_rows': total_rows, 'execution_time': total_time})
            
            return jsonify({
                'success': True,
                'task_id': task_id,
                'conversation_id': conversation_id,
                'result': formatted_output,
                'orchestrator': 'gpt4_progressive_excel',
                'execution_time': total_time,
                'progressive_analysis': True,
                'rows_analyzed': chunk_result['rows_analyzed'],
                'total_rows': total_rows,
                'rows_remaining': chunk_result['rows_remaining']
            })
        else:
            db.close()
            return jsonify({
                'success': False,
                'error': 'Could not analyze data'
            }), 500
            
    except Exception as e:
        import traceback
        print(f"Progressive continuation error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# I did no harm and this file is not truncated
