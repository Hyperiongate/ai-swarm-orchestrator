"""
Core Routes
Created: January 21, 2026
Last Updated: January 23, 2026 - ADDED DOCUMENT MANAGEMENT ENDPOINTS

CHANGES IN THIS VERSION:
- January 23, 2026: DOCUMENT MANAGEMENT ENDPOINTS
  * Added GET /api/generated-documents - List all generated documents
  * Added GET /api/generated-documents/<id> - Get single document info
  * Added GET /api/generated-documents/<id>/download - Download document
  * Added GET /api/generated-documents/<id>/print - Get printable version
  * Added DELETE /api/generated-documents/<id> - Delete document
  * Added GET /api/documents/stats - Get document statistics
  * Updated document creation to save to database
  * Documents now tracked with metadata (title, type, size, task_id, etc.)

- January 22, 2026: PERSISTENT CONVERSATION MEMORY
- January 22, 2026: CRITICAL BUG FIX - AI now actually completes tasks
- January 22, 2026: Added proactive intelligence (smart questioning + suggestions)
- January 21, 2026: Added feedback endpoint and learning stats

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify, send_file, current_app, make_response
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
    get_conversation_context,
    save_generated_document,
    get_generated_documents,
    get_generated_document,
    get_generated_document_by_filename,
    update_document_access,
    delete_generated_document,
    get_document_stats
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


# ============================================================================
# GENERATED DOCUMENTS MANAGEMENT ENDPOINTS (Added January 23, 2026)
# ============================================================================

@core_bp.route('/api/generated-documents', methods=['GET'])
def list_generated_documents():
    """Get list of all generated documents for display in sidebar."""
    try:
        limit = request.args.get('limit', 50, type=int)
        document_type = request.args.get('type')
        project_id = request.args.get('project_id')
        conversation_id = request.args.get('conversation_id')
        
        documents = get_generated_documents(
            limit=limit,
            document_type=document_type,
            project_id=project_id,
            conversation_id=conversation_id
        )
        
        formatted_docs = []
        for doc in documents:
            formatted_docs.append({
                'id': doc['id'],
                'filename': doc['filename'],
                'title': doc['title'] or doc['original_name'],
                'type': doc['document_type'],
                'size': doc['file_size'],
                'category': doc['category'],
                'created_at': doc['created_at'],
                'download_count': doc['download_count'],
                'download_url': f"/api/generated-documents/{doc['id']}/download",
                'print_url': f"/api/generated-documents/{doc['id']}/print"
            })
        
        return jsonify({
            'success': True,
            'documents': formatted_docs,
            'count': len(formatted_docs)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/generated-documents/<int:document_id>', methods=['GET'])
def get_document_info(document_id):
    """Get information about a specific document"""
    try:
        doc = get_generated_document(document_id)
        if not doc:
            return jsonify({'success': False, 'error': 'Document not found'}), 404
        
        return jsonify({
            'success': True,
            'document': {
                'id': doc['id'],
                'filename': doc['filename'],
                'title': doc['title'] or doc['original_name'],
                'type': doc['document_type'],
                'size': doc['file_size'],
                'category': doc['category'],
                'description': doc['description'],
                'created_at': doc['created_at'],
                'last_accessed': doc['last_accessed'],
                'download_count': doc['download_count'],
                'task_id': doc['task_id'],
                'conversation_id': doc['conversation_id'],
                'project_id': doc['project_id'],
                'download_url': f"/api/generated-documents/{doc['id']}/download",
                'print_url': f"/api/generated-documents/{doc['id']}/print"
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/generated-documents/<int:document_id>/download', methods=['GET'])
def download_generated_document(document_id):
    """Download a generated document by ID"""
    try:
        doc = get_generated_document(document_id)
        if not doc:
            return jsonify({'error': 'Document not found'}), 404
        
        file_path = doc['file_path']
        if not os.path.exists(file_path):
            alternative_paths = [
                f"/mnt/user-data/outputs/{doc['filename']}",
                f"/tmp/{doc['filename']}",
                f"./{doc['filename']}"
            ]
            file_path = None
            for alt_path in alternative_paths:
                if os.path.exists(alt_path):
                    file_path = alt_path
                    break
            if not file_path:
                return jsonify({'error': 'File not found on server'}), 404
        
        update_document_access(document_id)
        
        mime_types = {
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'pdf': 'application/pdf',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'txt': 'text/plain',
            'csv': 'text/csv'
        }
        mime_type = mime_types.get(doc['document_type'], 'application/octet-stream')
        
        return send_file(file_path, as_attachment=True, download_name=doc['filename'], mimetype=mime_type)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/api/generated-documents/<int:document_id>/print', methods=['GET'])
def print_generated_document(document_id):
    """Get a printable version of the document."""
    try:
        doc = get_generated_document(document_id)
        if not doc:
            return jsonify({'error': 'Document not found'}), 404
        
        file_path = doc['file_path']
        if not os.path.exists(file_path):
            alternative_paths = [
                f"/mnt/user-data/outputs/{doc['filename']}",
                f"/tmp/{doc['filename']}",
                f"./{doc['filename']}"
            ]
            file_path = None
            for alt_path in alternative_paths:
                if os.path.exists(alt_path):
                    file_path = alt_path
                    break
            if not file_path:
                return jsonify({'error': 'File not found on server'}), 404
        
        update_document_access(document_id)
        
        if doc['document_type'] == 'docx':
            try:
                from docx import Document
                docx_doc = Document(file_path)
                content_html = ""
                for para in docx_doc.paragraphs:
                    if para.style.name.startswith('Heading'):
                        level = para.style.name[-1] if para.style.name[-1].isdigit() else '2'
                        content_html += f"<h{level}>{para.text}</h{level}>\n"
                    else:
                        if para.text.strip():
                            content_html += f"<p>{para.text}</p>\n"
                
                print_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{doc['title'] or doc['original_name']} - Print</title>
    <style>
        body {{ font-family: 'Times New Roman', serif; max-width: 800px; margin: 0 auto; padding: 40px; line-height: 1.6; }}
        h1 {{ color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
        h2 {{ color: #667eea; margin-top: 30px; }}
        h3 {{ color: #764ba2; }}
        p {{ margin: 10px 0; text-align: justify; }}
        .header {{ text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px solid #ccc; }}
        .header h1 {{ border-bottom: none; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ccc; text-align: center; font-size: 12px; color: #666; }}
        @media print {{ body {{ padding: 20px; }} .no-print {{ display: none; }} }}
    </style>
</head>
<body>
    <div class="no-print" style="background: #f0f0f0; padding: 15px; margin-bottom: 20px; border-radius: 8px;">
        <button onclick="window.print()" style="padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold;">Print Document</button>
        <button onclick="window.close()" style="padding: 10px 20px; background: #e0e0e0; color: #333; border: none; border-radius: 6px; cursor: pointer; margin-left: 10px;">Close</button>
    </div>
    <div class="header">
        <h1>{doc['title'] or doc['original_name']}</h1>
        <p>Shiftwork Solutions LLC</p>
        <p style="font-size: 12px; color: #666;">Generated: {doc['created_at']}</p>
    </div>
    {content_html}
    <div class="footer">
        <p>Shiftwork Solutions LLC - Hundreds of Facilities Served</p>
        <p>www.shiftworksolutions.com</p>
    </div>
</body>
</html>'''
                response = make_response(print_html)
                response.headers['Content-Type'] = 'text/html'
                return response
            except Exception as docx_error:
                print(f"DOCX parsing failed: {docx_error}")
                return jsonify({
                    'success': False,
                    'error': 'Could not create printable version. Please download the document instead.',
                    'download_url': f"/api/generated-documents/{document_id}/download"
                }), 400
        
        return jsonify({
            'success': False,
            'error': f'{doc["document_type"].upper()} files must be downloaded and printed from the native application.',
            'download_url': f"/api/generated-documents/{document_id}/download"
        }), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/api/generated-documents/<int:document_id>', methods=['DELETE'])
def delete_document(document_id):
    """Delete a generated document"""
    try:
        doc = get_generated_document(document_id)
        if not doc:
            return jsonify({'success': False, 'error': 'Document not found'}), 404
        
        hard_delete = request.args.get('hard', 'false').lower() == 'true'
        success = delete_generated_document(document_id, hard_delete=hard_delete)
        
        if success:
            return jsonify({'success': True, 'message': 'Document deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete document'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/documents/stats', methods=['GET'])
def get_docs_stats():
    """Get document statistics"""
    try:
        stats = get_document_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
        conversations = get_conversations(limit=limit, project_id=project_id, include_archived=include_archived)
        return jsonify({'success': True, 'conversations': conversations, 'count': len(conversations)})
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
        conversation_id = create_conversation(mode=mode, project_id=project_id, title=title)
        return jsonify({'success': True, 'conversation_id': conversation_id, 'message': 'Conversation created successfully'})
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
        return jsonify({'success': True, 'conversation': conversation, 'messages': messages})
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
        update_conversation(conversation_id, title=data.get('title'), mode=data.get('mode'),
                          project_id=data.get('project_id'), is_archived=data.get('is_archived'))
        return jsonify({'success': True, 'message': 'Conversation updated successfully'})
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
        return jsonify({'success': True, 'message': 'Conversation deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@core_bp.route('/api/conversations/<conversation_id>/messages', methods=['POST'])
def add_conversation_message(conversation_id):
    """Add a message to a conversation"""
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
        return jsonify({'success': True, 'message': 'Message added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# MAIN ORCHESTRATION ENDPOINT
# ============================================================================

@core_bp.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    """Main orchestration endpoint with proactive intelligence and conversation memory"""
    try:
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
        
        # Create conversation if not provided
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
        if proactive:
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
        
        db = get_db()
        cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                           (user_request, 'processing', conversation_id))
        task_id = cursor.lastrowid
        db.commit()
        
        # Schedule generator intercept
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
                        file_size = os.path.getsize(schedule_file)
                        doc_title = f"{schedule_type.replace('_', ' ').title()} Schedule"
                        doc_id = save_generated_document(
                            filename=filename, original_name=doc_title, document_type='xlsx',
                            file_path=schedule_file, file_size=file_size, task_id=task_id,
                            conversation_id=conversation_id, project_id=project_id,
                            title=doc_title, description=f"Generated {schedule_type} schedule", category='schedule'
                        )
                        response_text = f"# {schedule_type.replace('_', ' ').title()} Schedule Created\n\n**Status:** Complete\n\nYour professional {schedule_type.replace('_', ' ')} schedule has been generated."
                        response_html = convert_markdown_to_html(response_text)
                        db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                                  ('completed', 'schedule_generator', time.time() - overall_start, task_id))
                        db.commit()
                        add_message(conversation_id, 'assistant', response_text, task_id,
                                   {'document_created': True, 'document_type': 'xlsx', 'document_id': doc_id, 'orchestrator': 'schedule_generator'})
                        suggestions = []
                        if proactive:
                            try:
                                suggestions = proactive.post_process_result(task_id, user_request, response_text)
                            except:
                                pass
                        db.close()
                        return jsonify({'success': True, 'task_id': task_id, 'conversation_id': conversation_id,
                                       'result': response_html, 'document_url': f'/api/generated-documents/{doc_id}/download',
                                       'document_id': doc_id, 'document_created': True, 'document_type': 'xlsx',
                                       'execution_time': time.time() - overall_start, 'orchestrator': 'schedule_generator',
                                       'knowledge_applied': False, 'formatting_applied': True, 'specialists_used': [],
                                       'consensus': None, 'suggestions': suggestions})
            except Exception as schedule_error:
                print(f"Schedule generation failed: {schedule_error}")
        
        # Regular AI orchestration
        try:
            print(f"Analyzing task: {user_request[:100]}...")
            analysis = analyze_task_with_sonnet(user_request, knowledge_base=knowledge_base)
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
                print("Escalating to Opus for strategic guidance...")
                orchestrator = 'opus'
                try:
                    opus_result = handle_with_opus(user_request, analysis, knowledge_base=knowledge_base)
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
                        result = execute_specialist_task(specialist, specialist_task)
                        specialist_results.append(result)
                        if result.get('success') and result.get('output'):
                            specialist_output = result.get('output')
            
            from orchestration.ai_clients import call_claude_opus, call_claude_sonnet
            knowledge_context = get_knowledge_context_for_prompt(knowledge_base, user_request)
            
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
                completion_prompt = f"""{knowledge_context}{conversation_history}

USER REQUEST: {user_request}

Please complete this request fully. Provide the actual deliverable the user is asking for.
Do not describe what you would do - actually do it.
Do not provide meta-commentary about the task - provide the actual content requested.

Be comprehensive and professional in your response."""
                if opus_guidance:
                    completion_prompt += f"\n\nSTRATEGIC GUIDANCE (from senior AI):\n{opus_guidance}\n\nUse this guidance to inform your response."
                
                if orchestrator == 'opus':
                    response = call_claude_opus(completion_prompt)
                else:
                    response = call_claude_sonnet(completion_prompt)
                
                if isinstance(response, dict):
                    if response.get('error'):
                        actual_output = f"Error completing task: {response.get('content', 'Unknown error')}"
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
                    save_paths = [f'/mnt/user-data/outputs/{filename}', f'/tmp/{filename}', f'./{filename}']
                    
                    saved = False
                    saved_path = None
                    for filepath in save_paths:
                        try:
                            os.makedirs(os.path.dirname(filepath), exist_ok=True)
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
                            title=doc_title, description=f"Generated from request: {user_request[:100]}",
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


# ============================================================================
# OTHER EXISTING ENDPOINTS
# ============================================================================

@core_bp.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get recent tasks"""
    try:
        limit = request.args.get('limit', 20, type=int)
        db = get_db()
        tasks = db.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        db.close()
        return jsonify({'tasks': [dict(task) for task in tasks]})
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
        total_conversations = db.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]
        total_messages = db.execute('SELECT COUNT(*) FROM conversation_messages').fetchone()[0]
        total_documents = db.execute('SELECT COUNT(*) FROM generated_documents WHERE is_deleted = 0').fetchone()[0]
        db.close()
        return jsonify({
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'success_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'total_documents': total_documents
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/api/documents', methods=['GET'])
def get_documents():
    """Get documents list - returns BOTH knowledge base docs AND generated documents."""
    try:
        import sys
        app_module = sys.modules.get('app')
        knowledge_base = getattr(app_module, 'knowledge_base', None) if app_module else None
        
        kb_documents = []
        if knowledge_base:
            for filename, doc_data in knowledge_base.knowledge_index.items():
                kb_documents.append({
                    'id': f'kb_{filename}',
                    'filename': filename,
                    'title': doc_data.get('title', filename),
                    'type': 'knowledge',
                    'word_count': doc_data.get('word_count', 0),
                    'category': doc_data.get('category', 'reference'),
                    'source': 'knowledge_base'
                })
        
        generated_docs = get_generated_documents(limit=50)
        gen_documents = []
        for doc in generated_docs:
            gen_documents.append({
                'id': doc['id'],
                'filename': doc['filename'],
                'title': doc['title'] or doc['original_name'],
                'type': doc['document_type'],
                'size': doc['file_size'],
                'category': doc['category'],
                'created_at': doc['created_at'],
                'download_url': f"/api/generated-documents/{doc['id']}/download",
                'print_url': f"/api/generated-documents/{doc['id']}/print",
                'source': 'generated'
            })
        
        return jsonify({
            'success': True,
            'knowledge_base_documents': kb_documents,
            'generated_documents': gen_documents,
            'knowledge_base_count': len(kb_documents),
            'generated_count': len(gen_documents),
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
            task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
            if not task:
                return jsonify({'error': 'Task not found'}), 404
            
            consensus = db.execute('SELECT agreement_score FROM consensus_validations WHERE task_id = ?', (task_id,)).fetchone()
            consensus_score = consensus['agreement_score'] if consensus else None
            
            consensus_was_accurate = None
            if consensus_score is not None:
                avg_rating = (quality_rating + accuracy_rating + usefulness_rating) / 3
                if consensus_score >= 0.7 and avg_rating >= 3.5:
                    consensus_was_accurate = True
                elif consensus_score < 0.7 and avg_rating < 3.5:
                    consensus_was_accurate = True
                else:
                    consensus_was_accurate = False
            
            db.execute('''INSERT INTO user_feedback 
                (task_id, overall_rating, quality_rating, accuracy_rating, usefulness_rating,
                 consensus_was_accurate, improvement_categories, user_comment, output_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (task_id, overall_rating, quality_rating, accuracy_rating, usefulness_rating,
                 consensus_was_accurate, json.dumps(improvement_categories), user_comment, output_used))
            
            orchestrator = task['assigned_orchestrator']
            task_type = 'general'
            avg_rating = (quality_rating + accuracy_rating + usefulness_rating) / 3
            pattern_key = f"{orchestrator}_{task_type}"
            
            existing_pattern = db.execute('SELECT * FROM learning_records WHERE pattern_type = ?', (pattern_key,)).fetchone()
            if existing_pattern:
                new_avg = (existing_pattern['success_rate'] * existing_pattern['times_applied'] + avg_rating / 5.0) / (existing_pattern['times_applied'] + 1)
                db.execute('UPDATE learning_records SET success_rate = ?, times_applied = times_applied + 1 WHERE pattern_type = ?',
                          (new_avg, pattern_key))
            else:
                db.execute('INSERT INTO learning_records (pattern_type, success_rate, times_applied, pattern_data) VALUES (?, ?, ?, ?)',
                          (pattern_key, avg_rating / 5.0, 1, json.dumps({'orchestrator': orchestrator, 'task_type': task_type,
                                                                        'last_rating': avg_rating, 'last_consensus': consensus_score})))
            
            db.commit()
            return jsonify({'success': True, 'message': 'Feedback recorded - system is learning!',
                           'consensus_was_accurate': consensus_was_accurate, 'learning_updated': True})
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
        total_feedback = db.execute('SELECT COUNT(*) as count FROM user_feedback').fetchone()
        avg_overall = db.execute('SELECT AVG(overall_rating) as avg FROM user_feedback').fetchone()
        consensus_accuracy = db.execute('''SELECT COUNT(*) as total,
            SUM(CASE WHEN consensus_was_accurate = 1 THEN 1 ELSE 0 END) as accurate
            FROM user_feedback WHERE consensus_was_accurate IS NOT NULL''').fetchone()
        
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
    """Download generated files (legacy endpoint)"""
    try:
        possible_paths = [f'/mnt/user-data/outputs/{filename}', f'/tmp/{filename}', f'./{filename}']
        for file_path in possible_paths:
            if os.path.exists(file_path):
                return send_file(file_path, as_attachment=True, download_name=filename)
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# I did no harm and this file is not truncated
