"""
Core Routes
Created: January 21, 2026
Last Updated: January 22, 2026 - ADDED PERSISTENT CONVERSATION MEMORY

CHANGES IN THIS VERSION:
- January 22, 2026: PERSISTENT CONVERSATION MEMORY
  * Added GET /api/conversations - List recent conversations
  * Added POST /api/conversations - Create new conversation
  * Added GET /api/conversations/<id> - Get conversation with messages
  * Added PUT /api/conversations/<id> - Update conversation metadata
  * Added DELETE /api/conversations/<id> - Delete conversation
  * Added POST /api/conversations/<id>/messages - Add message
  * Updated /api/orchestrate to track conversation_id
  * Messages auto-saved to conversation history

- January 22, 2026: CRITICAL BUG FIX
  * Fixed orchestration logic - AI now actually completes tasks
  * Previously: Opus meta-commentary was displayed instead of actual work
  * Now: When analysis succeeds, AI is called to complete the actual request

- January 22, 2026: Added proactive intelligence (smart questioning + suggestions)
- January 21, 2026: Added feedback endpoint and learning stats

ARCHITECTURE:
- Sonnet analyzes the task and decides routing
- If escalate_to_opus=false and confidence is high, Sonnet completes the task
- If escalate_to_opus=true, Opus provides strategy, then AI completes the task
- Specialists are called only when specifically needed
- Knowledge base context is included in task completion prompts
- All messages are saved to conversation history for persistence

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify, send_file, current_app
import time
import json
import os
import markdown
from datetime import datetime
from database import (
    get_db, 
    create_conversation, 
    get_conversation, 
    get_conversations,
    update_conversation,
    delete_conversation as db_delete_conversation,
    add_message,
    get_messages,
    get_conversation_context
)
from orchestration import (
    analyze_task_with_sonnet,
    handle_with_opus,
    execute_specialist_task,
    validate_with_consensus
)
from orchestration.proactive_agent import ProactiveAgent

core_bp = Blueprint('core', __name__)


def convert_markdown_to_html(text):
    """Convert markdown text to styled HTML"""
    if not text:
        return text
    
    # Convert markdown to HTML
    html = markdown.markdown(text, extensions=['extra', 'nl2br'])
    
    # Add styling to the HTML
    styled_html = f"""
<div style="line-height: 1.8; color: #333;">
    {html}
</div>
"""
    return styled_html


def should_create_document(user_request):
    """Determine if we should create a downloadable document"""
    doc_keywords = [
        'create', 'generate', 'make', 'write', 'draft', 'prepare',
        'document', 'report', 'proposal', 'presentation', 'schedule',
        'contract', 'agreement', 'summary', 'analysis'
    ]
    
    request_lower = user_request.lower()
    
    # Check for document creation intent
    for keyword in doc_keywords:
        if keyword in request_lower:
            # Determine document type
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
            return f"""

=== SHIFTWORK SOLUTIONS KNOWLEDGE BASE ===
Use this information from our 30+ years of expertise to inform your response:

{context}

=== END KNOWLEDGE BASE ===

"""
        return ""
    except Exception as e:
        print(f"⚠️ Knowledge context retrieval failed: {e}")
        return ""


# ============================================================================
# CONVERSATION MEMORY ENDPOINTS (Added January 22, 2026)
# ============================================================================

@core_bp.route('/api/conversations', methods=['GET'])
def list_conversations():
    """Get list of recent conversations"""
    try:
        limit = request.args.get('limit', 20, type=int)
        project_id = request.args.get('project_id')
        include_archived = request.args.get('include_archived', 'false').lower() == 'true'
        
        conversations = get_conversations(
            limit=limit, 
            project_id=project_id,
            include_archived=include_archived
        )
        
        return jsonify({
            'success': True,
            'conversations': conversations,
            'count': len(conversations)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/conversations', methods=['POST'])
def create_new_conversation():
    """Create a new conversation"""
    try:
        data = request.json or {}
        mode = data.get('mode', 'quick')
        project_id = data.get('project_id')
        title = data.get('title')
        
        conversation_id = create_conversation(
            mode=mode,
            project_id=project_id,
            title=title
        )
        
        return jsonify({
            'success': True,
            'conversation_id': conversation_id,
            'message': 'Conversation created successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_single_conversation(conversation_id):
    """Get a specific conversation with its messages"""
    try:
        conversation = get_conversation(conversation_id)
        
        if not conversation:
            return jsonify({'success': False, 'error': 'Conversation not found'}), 404
        
        messages = get_messages(conversation_id, limit=100)
        
        return jsonify({
            'success': True,
            'conversation': conversation,
            'messages': messages
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/conversations/<conversation_id>', methods=['PUT'])
def update_single_conversation(conversation_id):
    """Update conversation metadata"""
    try:
        conversation = get_conversation(conversation_id)
        
        if not conversation:
            return jsonify({'success': False, 'error': 'Conversation not found'}), 404
        
        data = request.json or {}
        
        update_conversation(
            conversation_id,
            title=data.get('title'),
            mode=data.get('mode'),
            project_id=data.get('project_id'),
            is_archived=data.get('is_archived')
        )
        
        return jsonify({
            'success': True,
            'message': 'Conversation updated successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/conversations/<conversation_id>', methods=['DELETE'])
def delete_single_conversation(conversation_id):
    """Delete a conversation and all its messages"""
    try:
        conversation = get_conversation(conversation_id)
        
        if not conversation:
            return jsonify({'success': False, 'error': 'Conversation not found'}), 404
        
        db_delete_conversation(conversation_id)
        
        return jsonify({
            'success': True,
            'message': 'Conversation deleted successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/conversations/<conversation_id>/messages', methods=['POST'])
def add_conversation_message(conversation_id):
    """Add a message to a conversation (manual add, not through orchestrate)"""
    try:
        conversation = get_conversation(conversation_id)
        
        if not conversation:
            return jsonify({'success': False, 'error': 'Conversation not found'}), 404
        
        data = request.json or {}
        role = data.get('role', 'user')
        content = data.get('content')
        task_id = data.get('task_id')
        metadata = data.get('metadata')
        
        if not content:
            return jsonify({'success': False, 'error': 'Content is required'}), 400
        
        add_message(conversation_id, role, content, task_id, metadata)
        
        return jsonify({
            'success': True,
            'message': 'Message added successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# MAIN ORCHESTRATION ENDPOINT
# ============================================================================

@core_bp.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    """
    Main orchestration endpoint with proactive intelligence and conversation memory
    Now includes smart questioning, post-task suggestions, and message persistence
    
    FLOW:
    1. Get or create conversation_id
    2. Save user message to conversation
    3. Proactive pre-check (questions, project detection)
    4. Schedule generator intercept (for specific schedule types)
    5. Sonnet analyzes task and decides routing
    6. AI completes the actual task (Sonnet or Opus based on analysis)
    7. Specialists called only if specifically needed
    8. Document creation if appropriate
    9. Consensus validation
    10. Save assistant response to conversation
    11. Post-task suggestions
    """
    try:
        # Parse request
        if request.is_json:
            data = request.json
            user_request = data.get('request')
            enable_consensus = data.get('enable_consensus', True)
            project_id = data.get('project_id')
            conversation_id = data.get('conversation_id')
            mode = data.get('mode', 'quick')
        else:
            user_request = request.form.get('request')
            enable_consensus = request.form.get('enable_consensus', 'true').lower() == 'true'
            project_id = request.form.get('project_id')
            conversation_id = request.form.get('conversation_id')
            mode = request.form.get('mode', 'quick')
        
        if not user_request:
            return jsonify({'success': False, 'error': 'Request text required'}), 400
        
        overall_start = time.time()
        
        # ============ CONVERSATION MEMORY ============
        # Create conversation if not provided
        if not conversation_id:
            conversation_id = create_conversation(mode=mode, project_id=project_id)
            print(f"📝 Created new conversation: {conversation_id}")
        
        # Save user message to conversation
        add_message(conversation_id, 'user', user_request)
        # ============ END CONVERSATION MEMORY ============
        
        # Initialize proactive agent
        proactive = None
        try:
            proactive = ProactiveAgent()
        except Exception as proactive_init_error:
            print(f"⚠️ Proactive agent init failed: {proactive_init_error}")
        
        # ============ PROACTIVE PRE-CHECK ============
        if proactive:
            try:
                pre_check = proactive.pre_process_request(user_request)
                
                if pre_check['action'] == 'ask_questions':
                    # Create task for tracking
                    db = get_db()
                    cursor = db.execute(
                        'INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                        (user_request, 'needs_clarification', conversation_id)
                    )
                    task_id = cursor.lastrowid
                    db.commit()
                    db.close()
                    
                    return jsonify({
                        'success': True,
                        'needs_clarification': True,
                        'clarification_data': pre_check['data'],
                        'task_id': task_id,
                        'conversation_id': conversation_id
                    })
                
                if pre_check['action'] == 'detect_project':
                    return jsonify({
                        'success': True,
                        'project_detected': True,
                        'project_data': pre_check['data'],
                        'conversation_id': conversation_id
                    })
            except Exception as proactive_error:
                print(f"⚠️ Proactive check failed: {proactive_error}")
        # ============ END PROACTIVE PRE-CHECK ============
        
        # Get knowledge base from app
        import sys
        app_module = sys.modules.get('app')
        knowledge_base = getattr(app_module, 'knowledge_base', None) if app_module else None
        
        # Get conversation context for AI
        conversation_context = get_conversation_context(conversation_id, max_messages=10)
        
        # Create task in database
        db = get_db()
        cursor = db.execute(
            'INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
            (user_request, 'processing', conversation_id)
        )
        task_id = cursor.lastrowid
        db.commit()
        
        # ==================== SCHEDULE GENERATOR INTERCEPT ====================
        schedule_keywords = ['dupont', 'panama', 'pitman', 'southern swing', '2-2-3', '2-3-2', 
                            'create a schedule', 'generate a schedule', 'make a schedule']
        
        is_schedule_request = any(keyword in user_request.lower() for keyword in schedule_keywords)
        
        if is_schedule_request and current_app.config.get('SCHEDULE_GENERATOR_AVAILABLE'):
            try:
                schedule_gen = current_app.config.get('SCHEDULE_GENERATOR')
                schedule_type = schedule_gen.identify_schedule_type(user_request)
                
                if schedule_type:
                    schedule_file = schedule_gen.create_schedule(schedule_type)
                    
                    if schedule_file and os.path.exists(schedule_file):
                        filename = os.path.basename(schedule_file)
                        
                        # Format response with markdown
                        response_text = f"""# {schedule_type.replace('_', ' ').title()} Schedule Created

**Status:** ✅ Complete

Your professional {schedule_type.replace('_', ' ')} schedule has been generated and is ready to download.

## Schedule Details
- **Type:** {schedule_type.replace('_', ' ').title()}
- **Format:** Excel Spreadsheet (.xlsx)
- **Features:** Color-coded, printable, ready to use

**Download your schedule using the button below.**
"""
                        
                        response_html = convert_markdown_to_html(response_text)
                        
                        db.execute(
                            '''UPDATE tasks SET status = ?, assigned_orchestrator = ?, 
                               execution_time_seconds = ? WHERE id = ?''',
                            ('completed', 'schedule_generator', time.time() - overall_start, task_id)
                        )
                        db.commit()
                        
                        # Save assistant response to conversation
                        add_message(conversation_id, 'assistant', response_text, task_id, {
                            'document_created': True,
                            'document_type': 'xlsx',
                            'orchestrator': 'schedule_generator'
                        })
                        
                        # Generate suggestions
                        suggestions = []
                        if proactive:
                            try:
                                suggestions = proactive.post_process_result(task_id, user_request, response_text)
                            except Exception as suggest_error:
                                print(f"⚠️ Suggestion generation failed: {suggest_error}")
                        
                        db.close()
                        
                        return jsonify({
                            'success': True,
                            'task_id': task_id,
                            'conversation_id': conversation_id,
                            'result': response_html,
                            'document_url': f'/api/download/{filename}',
                            'document_created': True,
                            'document_type': 'xlsx',
                            'execution_time': time.time() - overall_start,
                            'orchestrator': 'schedule_generator',
                            'knowledge_applied': False,
                            'formatting_applied': True,
                            'specialists_used': [],
                            'consensus': None,
                            'suggestions': suggestions
                        })
            except Exception as schedule_error:
                print(f"⚠️ Schedule generation failed: {schedule_error}")
        
        # ==================== REGULAR AI ORCHESTRATION ====================
        try:
            # Step 1: Analyze with Sonnet (decides routing, NOT the actual work)
            print(f"📊 Analyzing task: {user_request[:100]}...")
            analysis = analyze_task_with_sonnet(user_request, knowledge_base=knowledge_base)
            
            task_type = analysis.get('task_type', 'general')
            confidence = analysis.get('confidence', 0.5)
            escalate = analysis.get('escalate_to_opus', False)
            specialists_needed = analysis.get('specialists_needed', [])
            knowledge_applied = analysis.get('knowledge_applied', False)
            knowledge_sources = analysis.get('knowledge_sources', [])
            
            print(f"📊 Analysis: type={task_type}, confidence={confidence}, escalate={escalate}, specialists={specialists_needed}")
            
            # Clean up specialists_needed - remove "none" entries
            if specialists_needed:
                specialists_needed = [s for s in specialists_needed if s and s.lower() != 'none']
            
            # Step 2: Determine which AI will complete the task
            orchestrator = 'sonnet'
            opus_guidance = None
            
            if escalate:
                print(f"📊 Escalating to Opus for strategic guidance...")
                orchestrator = 'opus'
                try:
                    opus_result = handle_with_opus(user_request, analysis, knowledge_base=knowledge_base)
                    opus_guidance = opus_result.get('strategic_analysis', '')
                    
                    # Check if Opus assigned specialists
                    if opus_result.get('specialist_assignments'):
                        for assignment in opus_result.get('specialist_assignments', []):
                            specialist = assignment.get('ai') or assignment.get('specialist')
                            if specialist and specialist.lower() != 'none':
                                specialists_needed.append(specialist)
                except Exception as opus_error:
                    print(f"⚠️ Opus guidance failed: {opus_error}")
            
            # Step 3: Execute with specialists if specifically needed
            specialist_results = []
            specialist_output = None
            
            if specialists_needed:
                print(f"📊 Calling specialists: {specialists_needed}")
                for specialist_info in specialists_needed:
                    if isinstance(specialist_info, dict):
                        specialist = specialist_info.get('specialist') or specialist_info.get('ai')
                        specialist_task = specialist_info.get('task', user_request)
                    else:
                        specialist = specialist_info
                        specialist_task = user_request
                    
                    if specialist and specialist.lower() != 'none':
                        result = execute_specialist_task(specialist, specialist_task)
                        specialist_results.append(result)
                        
                        # Use specialist output if it succeeded
                        if result.get('success') and result.get('output'):
                            specialist_output = result.get('output')
            
            # Step 4: ACTUALLY COMPLETE THE TASK
            # This is where the real work happens - NOT in the analysis step!
            print(f"📊 Completing task with {orchestrator}...")
            
            from orchestration.ai_clients import call_claude_opus, call_claude_sonnet
            
            # Build the completion prompt with knowledge context
            knowledge_context = get_knowledge_context_for_prompt(knowledge_base, user_request)
            
            # Build conversation history for context
            conversation_history = ""
            if conversation_context and len(conversation_context) > 1:
                conversation_history = "\n\n=== CONVERSATION HISTORY ===\n"
                for msg in conversation_context[:-1]:  # Exclude current message
                    role_label = "User" if msg['role'] == 'user' else "Assistant"
                    conversation_history += f"{role_label}: {msg['content'][:500]}...\n" if len(msg['content']) > 500 else f"{role_label}: {msg['content']}\n"
                conversation_history += "=== END CONVERSATION HISTORY ===\n\n"
            
            # If we have specialist output, use that
            if specialist_output:
                actual_output = specialist_output
            else:
                # Build a proper completion prompt
                completion_prompt = f"""{knowledge_context}{conversation_history}

USER REQUEST: {user_request}

Please complete this request fully. Provide the actual deliverable the user is asking for.
Do not describe what you would do - actually do it.
Do not provide meta-commentary about the task - provide the actual content requested.

If the user asks for a checklist, provide the checklist.
If the user asks for a document, write the document.
If the user asks for analysis, provide the analysis.

Be comprehensive and professional in your response."""

                # Add Opus guidance if available
                if opus_guidance:
                    completion_prompt += f"""

STRATEGIC GUIDANCE (from senior AI):
{opus_guidance}

Use this guidance to inform your response, but focus on delivering the actual content requested."""

                # Call the appropriate AI to complete the task
                if orchestrator == 'opus':
                    response = call_claude_opus(completion_prompt)
                else:
                    response = call_claude_sonnet(completion_prompt)
                
                # Extract content from response dict
                if isinstance(response, dict):
                    if response.get('error'):
                        actual_output = f"Error completing task: {response.get('content', 'Unknown error')}"
                    else:
                        actual_output = response.get('content', '')
                else:
                    actual_output = str(response)
            
            print(f"📊 Task completed. Output length: {len(actual_output) if actual_output else 0} chars")
            
            # Step 5: Check if we should create a document
            document_created = False
            document_url = None
            document_type = None
            
            should_create, doc_type = should_create_document(user_request)
            
            if should_create and actual_output and not actual_output.startswith('Error'):
                try:
                    from docx import Document
                    from docx.shared import Pt
                    
                    # Create Word document
                    doc = Document()
                    
                    # Add title
                    title = doc.add_heading('Shiftwork Solutions LLC', 0)
                    title.alignment = 1  # Center
                    
                    # Add content
                    lines = actual_output.split('\n')
                    for line in lines:
                        if line.strip():
                            if line.startswith('#'):
                                # Header
                                level = len(line) - len(line.lstrip('#'))
                                text = line.lstrip('#').strip()
                                doc.add_heading(text, level=min(level, 3))
                            else:
                                # Regular paragraph
                                p = doc.add_paragraph(line)
                                p.style.font.size = Pt(11)
                    
                    # Save document
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f'shiftwork_document_{timestamp}.docx'
                    
                    # Try multiple paths for saving
                    save_paths = [
                        f'/mnt/user-data/outputs/{filename}',
                        f'/tmp/{filename}',
                        f'./{filename}'
                    ]
                    
                    saved = False
                    for filepath in save_paths:
                        try:
                            # Ensure directory exists
                            os.makedirs(os.path.dirname(filepath), exist_ok=True)
                            doc.save(filepath)
                            saved = True
                            print(f"✅ Document created: {filepath}")
                            break
                        except Exception as save_error:
                            print(f"⚠️ Could not save to {filepath}: {save_error}")
                    
                    if saved:
                        document_created = True
                        document_url = f'/api/download/{filename}'
                        document_type = 'docx'
                    
                except Exception as doc_error:
                    print(f"⚠️ Document creation failed: {doc_error}")
            
            # Step 6: Convert markdown to HTML for beautiful display
            formatted_output = convert_markdown_to_html(actual_output)
            
            # Step 7: Consensus validation if enabled
            consensus_result = None
            if enable_consensus and actual_output and not actual_output.startswith('Error'):
                try:
                    consensus_result = validate_with_consensus(actual_output)
                except Exception as consensus_error:
                    print(f"⚠️ Consensus validation failed: {consensus_error}")
            
            total_time = time.time() - overall_start
            
            # Update task in database
            db.execute(
                '''UPDATE tasks SET status = ?, assigned_orchestrator = ?, 
                   execution_time_seconds = ? WHERE id = ?''',
                ('completed', orchestrator, total_time, task_id)
            )
            db.commit()
            db.close()
            
            # ============ SAVE ASSISTANT RESPONSE TO CONVERSATION ============
            add_message(conversation_id, 'assistant', actual_output, task_id, {
                'orchestrator': orchestrator,
                'knowledge_applied': knowledge_applied,
                'document_created': document_created,
                'document_type': document_type,
                'execution_time': total_time
            })
            # ============ END SAVE RESPONSE ============
            
            # Step 8: Generate post-task suggestions
            suggestions = []
            if proactive:
                try:
                    suggestions = proactive.post_process_result(
                        task_id, 
                        user_request, 
                        actual_output if actual_output else ''
                    )
                except Exception as suggest_error:
                    print(f"⚠️ Suggestion generation failed: {suggest_error}")
            
            # ==================== RETURN RESPONSE ====================
            return jsonify({
                'success': True,
                'task_id': task_id,
                'conversation_id': conversation_id,
                'result': formatted_output,
                'orchestrator': orchestrator,
                'specialists_used': [s.get('specialist') for s in specialist_results] if specialist_results else [],
                'consensus': consensus_result,
                'execution_time': total_time,
                'knowledge_applied': knowledge_applied,
                'knowledge_used': knowledge_applied,
                'knowledge_sources': knowledge_sources,
                'formatting_applied': True,
                'document_created': document_created,
                'document_url': document_url,
                'document_type': document_type,
                'suggestions': suggestions
            })
            
        except Exception as orchestration_error:
            import traceback
            error_trace = traceback.format_exc()
            print(f"❌ Orchestration error: {error_trace}")
            
            db.execute(
                '''UPDATE tasks SET status = ? WHERE id = ?''',
                ('failed', task_id)
            )
            db.commit()
            db.close()
            
            # Save error to conversation
            add_message(conversation_id, 'assistant', f"Error: {str(orchestration_error)}", task_id, {
                'error': True
            })
            
            return jsonify({
                'success': False,
                'error': f'Orchestration failed: {str(orchestration_error)}',
                'task_id': task_id,
                'conversation_id': conversation_id
            }), 500
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ CRITICAL ERROR: {error_trace}")
        
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


# ============================================================================
# OTHER EXISTING ENDPOINTS
# ============================================================================

@core_bp.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get recent tasks"""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        db = get_db()
        tasks = db.execute(
            'SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?',
            (limit,)
        ).fetchall()
        db.close()
        
        return jsonify({
            'tasks': [dict(task) for task in tasks]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/api/task/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get specific task details"""
    try:
        db = get_db()
        task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        db.close()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        return jsonify(dict(task))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        db = get_db()
        
        total_tasks = db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
        completed_tasks = db.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('completed',)).fetchone()[0]
        
        # Conversation stats
        total_conversations = db.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]
        total_messages = db.execute('SELECT COUNT(*) FROM conversation_messages').fetchone()[0]
        
        db.close()
        
        return jsonify({
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'success_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            'total_conversations': total_conversations,
            'total_messages': total_messages
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/api/documents', methods=['GET'])
def get_documents():
    """Get knowledge base documents list"""
    try:
        import sys
        app_module = sys.modules.get('app')
        knowledge_base = getattr(app_module, 'knowledge_base', None) if app_module else None
        
        if not knowledge_base:
            return jsonify({
                'documents': [],
                'count': 0,
                'status': 'knowledge_base_not_initialized'
            })
        
        # Get list of documents from knowledge base
        documents = []
        for filename, doc_data in knowledge_base.knowledge_index.items():
            documents.append({
                'filename': filename,
                'title': doc_data.get('title', filename),
                'word_count': doc_data.get('word_count', 0),
                'category': doc_data.get('category', 'general')
            })
        
        return jsonify({
            'documents': documents,
            'count': len(documents),
            'status': 'available'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit feedback on task results"""
    try:
        data = request.json
        task_id = data.get('task_id')
        overall_rating = data.get('overall_rating')
        quality_rating = data.get('quality_rating')
        accuracy_rating = data.get('accuracy_rating')
        usefulness_rating = data.get('usefulness_rating')
        improvement_categories = data.get('improvement_categories', [])
        user_comment = data.get('user_comment', '')
        output_used = data.get('output_used', False)
        
        if not task_id or not overall_rating:
            return jsonify({'error': 'task_id and overall_rating required'}), 400
        
        db = get_db()
        
        try:
            # Check if task exists
            task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
            if not task:
                return jsonify({'error': 'Task not found'}), 404
            
            # Get consensus score if it exists
            consensus = db.execute(
                'SELECT agreement_score FROM consensus_validations WHERE task_id = ?', 
                (task_id,)
            ).fetchone()
            consensus_score = consensus['agreement_score'] if consensus else None
            
            # Determine if consensus was accurate
            consensus_was_accurate = None
            if consensus_score is not None:
                avg_rating = (quality_rating + accuracy_rating + usefulness_rating) / 3
                if consensus_score >= 0.7 and avg_rating >= 3.5:
                    consensus_was_accurate = True
                elif consensus_score < 0.7 and avg_rating < 3.5:
                    consensus_was_accurate = True
                else:
                    consensus_was_accurate = False
            
            # Insert feedback
            db.execute('''
                INSERT INTO user_feedback 
                (task_id, overall_rating, quality_rating, accuracy_rating, usefulness_rating,
                 consensus_was_accurate, improvement_categories, user_comment, output_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_id, overall_rating, quality_rating, accuracy_rating, usefulness_rating,
                consensus_was_accurate, json.dumps(improvement_categories), user_comment, output_used
            ))
            
            # Update learning records
            orchestrator = task['assigned_orchestrator']
            task_type = 'general'
            avg_rating = (quality_rating + accuracy_rating + usefulness_rating) / 3
            
            pattern_key = f"{orchestrator}_{task_type}"
            existing_pattern = db.execute(
                'SELECT * FROM learning_records WHERE pattern_type = ?', 
                (pattern_key,)
            ).fetchone()
            
            if existing_pattern:
                # Update existing pattern
                new_avg = (existing_pattern['success_rate'] * existing_pattern['times_applied'] + avg_rating / 5.0) / (existing_pattern['times_applied'] + 1)
                db.execute('''
                    UPDATE learning_records 
                    SET success_rate = ?, times_applied = times_applied + 1
                    WHERE pattern_type = ?
                ''', (new_avg, pattern_key))
            else:
                # Create new pattern
                db.execute('''
                    INSERT INTO learning_records 
                    (pattern_type, success_rate, times_applied, pattern_data)
                    VALUES (?, ?, ?, ?)
                ''', (
                    pattern_key, avg_rating / 5.0, 1, 
                    json.dumps({
                        'orchestrator': orchestrator,
                        'task_type': task_type,
                        'last_rating': avg_rating,
                        'last_consensus': consensus_score
                    })
                ))
            
            db.commit()
            
            return jsonify({
                'success': True,
                'message': 'Feedback recorded - system is learning!',
                'consensus_was_accurate': consensus_was_accurate,
                'learning_updated': True
            })
            
        except Exception as e:
            db.rollback()
            import traceback
            print(f"Feedback error: {traceback.format_exc()}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/learning/stats', methods=['GET'])
def get_learning_stats():
    """Get learning system statistics"""
    try:
        db = get_db()
        
        # Get feedback stats
        total_feedback = db.execute('SELECT COUNT(*) as count FROM user_feedback').fetchone()
        avg_overall = db.execute('SELECT AVG(overall_rating) as avg FROM user_feedback').fetchone()
        
        consensus_accuracy = db.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN consensus_was_accurate = 1 THEN 1 ELSE 0 END) as accurate
            FROM user_feedback 
            WHERE consensus_was_accurate IS NOT NULL
        ''').fetchone()
        
        consensus_accuracy_rate = None
        if consensus_accuracy and consensus_accuracy['total'] > 0:
            consensus_accuracy_rate = int((consensus_accuracy['accurate'] / consensus_accuracy['total']) * 100)
        
        db.close()
        
        return jsonify({
            'success': True,
            'total_feedback_count': total_feedback['count'] if total_feedback else 0,
            'average_overall_rating': round(avg_overall['avg'], 2) if avg_overall and avg_overall['avg'] else 0,
            'consensus_accuracy_rate': consensus_accuracy_rate
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download generated files"""
    try:
        # Try multiple paths
        possible_paths = [
            f'/mnt/user-data/outputs/{filename}',
            f'/tmp/{filename}',
            f'./{filename}'
        ]
        
        for file_path in possible_paths:
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True, download_name=filename)
        
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# I did no harm and this file is not truncated
