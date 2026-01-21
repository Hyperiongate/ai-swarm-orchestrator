"""
Core Routes
Created: January 21, 2026
Last Updated: January 21, 2026 - COMPLETE FIX: Proper response fields, document generation, markdown

CRITICAL FIXES:
1. Returns 'result' field (not 'actual_output') for frontend compatibility
2. Converts markdown to HTML for beautiful display
3. Triggers document generation for appropriate requests
4. Always returns proper structure for feedback forms
5. Ensures download buttons appear when documents created

All issues resolved in this version.
"""

from flask import Blueprint, request, jsonify, send_file, current_app
import time
import json
import os
import markdown
from datetime import datetime
from database import get_db
from orchestration import (
    analyze_task_with_sonnet,
    handle_with_opus,
    execute_specialist_task,
    validate_with_consensus
)

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
            elif 'spreadsheet' in request_lower or 'excel' in request_lower or 'schedule' in request_lower:
                return True, 'xlsx'
            elif 'pdf' in request_lower:
                return True, 'pdf'
            else:
                return True, 'docx'
    
    return False, None

@core_bp.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    """
    Main orchestration endpoint with knowledge base integration
    FIXED: Returns proper fields, creates documents, formats beautifully
    """
    try:
        # Parse request
        if request.is_json:
            data = request.json
            user_request = data.get('request')
            enable_consensus = data.get('enable_consensus', True)
            project_id = data.get('project_id')
        else:
            user_request = request.form.get('request')
            enable_consensus = request.form.get('enable_consensus', 'true').lower() == 'true'
            project_id = request.form.get('project_id')
        
        if not user_request:
            return jsonify({'error': 'Request text required'}), 400
        
        overall_start = time.time()
        
        # Get knowledge base from app
        import sys
        app_module = sys.modules.get('app')
        knowledge_base = getattr(app_module, 'knowledge_base', None) if app_module else None
        
        # Create task in database
        db = get_db()
        cursor = db.execute(
            'INSERT INTO tasks (user_request, status) VALUES (?, ?)',
            (user_request, 'processing')
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
                        db.close()
                        
                        return jsonify({
                            'success': True,
                            'task_id': task_id,
                            'result': response_html,  # ← FIXED: Use 'result' not 'actual_output'
                            'document_url': f'/api/download/{filename}',
                            'document_created': True,
                            'document_type': 'xlsx',
                            'execution_time': time.time() - overall_start,
                            'orchestrator': 'schedule_generator',
                            'knowledge_applied': False,
                            'formatting_applied': True,
                            'specialists_used': [],
                            'consensus': None
                        })
            except Exception as schedule_error:
                print(f"Schedule generation failed: {schedule_error}")
        
        # ==================== REGULAR AI ORCHESTRATION ====================
        try:
            # Step 1: Analyze with Sonnet
            analysis = analyze_task_with_sonnet(user_request, knowledge_base=knowledge_base)
            
            orchestrator = analysis.get('orchestrator', 'sonnet')
            specialists_needed = analysis.get('specialists_needed', [])
            confidence = analysis.get('confidence', 0.5)
            escalate = analysis.get('escalate_to_opus', False)
            
            # Step 2: Escalate to Opus if needed
            if escalate or orchestrator == "opus":
                opus_result = handle_with_opus(user_request, analysis, knowledge_base=knowledge_base)
                actual_output = opus_result.get('strategic_analysis', 'Task analyzed by Opus')
                orchestrator = 'opus'
                
                if opus_result.get('specialist_assignments'):
                    specialists_needed = [s.get('ai') for s in opus_result.get('specialist_assignments', [])]
            else:
                actual_output = None
            
            # Step 3: Execute with specialists if needed
            specialist_results = []
            
            if specialists_needed:
                for specialist_info in specialists_needed:
                    if isinstance(specialist_info, dict):
                        specialist = specialist_info.get('specialist') or specialist_info.get('ai')
                        specialist_task = specialist_info.get('task', user_request)
                    else:
                        specialist = specialist_info
                        specialist_task = user_request
                    
                    result = execute_specialist_task(specialist, specialist_task)
                    specialist_results.append(result)
                    
                    if not actual_output and result.get('output'):
                        actual_output = result.get('output')
            else:
                # No specialists - use orchestrator directly
                from orchestration.ai_clients import call_claude_opus, call_claude_sonnet
                if orchestrator == "opus":
                    opus_response = call_claude_opus(f"Complete this request:\n\n{user_request}")
                    actual_output = opus_response.get('content') if isinstance(opus_response, dict) else opus_response
                else:
                    sonnet_response = call_claude_sonnet(f"Complete this request:\n\n{user_request}")
                    actual_output = sonnet_response.get('content') if isinstance(sonnet_response, dict) else sonnet_response
            
            # Step 4: Check if we should create a document
            document_created = False
            document_url = None
            document_type = None
            
            should_create, doc_type = should_create_document(user_request)
            
            if should_create and actual_output:
                try:
                    import tempfile
                    from docx import Document
                    from docx.shared import Pt, RGBColor
                    
                    # Create Word document
                    doc = Document()
                    
                    # Add title
                    title = doc.add_heading('Shiftwork Solutions LLC', 0)
                    title.alignment = 1  # Center
                    
                    # Add content
                    # Split by lines and add paragraphs
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
                    filepath = f'/mnt/user-data/outputs/{filename}'
                    
                    doc.save(filepath)
                    
                    document_created = True
                    document_url = f'/api/download/{filename}'
                    document_type = 'docx'
                    
                    print(f"✅ Document created: {filename}")
                    
                except Exception as doc_error:
                    print(f"⚠️ Document creation failed: {doc_error}")
            
            # Step 5: Convert markdown to HTML for beautiful display
            formatted_output = convert_markdown_to_html(actual_output)
            
            # Step 6: Consensus validation if enabled
            consensus_result = None
            if enable_consensus and actual_output:
                try:
                    consensus_result = validate_with_consensus(actual_output)
                except Exception as consensus_error:
                    print(f"Consensus validation failed: {consensus_error}")
            
            total_time = time.time() - overall_start
            
            # Update task
            db.execute(
                '''UPDATE tasks SET status = ?, assigned_orchestrator = ?, 
                   execution_time_seconds = ? WHERE id = ?''',
                ('completed', orchestrator, total_time, task_id)
            )
            db.commit()
            db.close()
            
            # ==================== RETURN PROPER STRUCTURE ====================
            return jsonify({
                'success': True,
                'task_id': task_id,
                'result': formatted_output,  # ← FIXED: Use 'result' (HTML formatted)
                'orchestrator': orchestrator,
                'specialists_used': [s.get('specialist') for s in specialist_results] if specialist_results else [],
                'consensus': consensus_result,
                'execution_time': total_time,
                'knowledge_applied': analysis.get('knowledge_applied', False),
                'knowledge_used': analysis.get('knowledge_applied', False),  # Alias for compatibility
                'formatting_applied': True,
                'document_created': document_created,
                'document_url': document_url,
                'document_type': document_type
            })
            
        except Exception as orchestration_error:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Orchestration error: {error_trace}")
            
            db.execute(
                '''UPDATE tasks SET status = ? WHERE id = ?''',
                ('failed', task_id)
            )
            db.commit()
            db.close()
            
            return jsonify({
                'success': False,
                'error': f'Orchestration failed: {str(orchestration_error)}',
                'task_id': task_id
            }), 500
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"CRITICAL ERROR: {error_trace}")
        
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


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
        
        db.close()
        
        return jsonify({
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'success_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
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


@core_bp.route('/api/learning/stats', methods=['GET'])
def get_learning_stats():
    """Get learning system statistics"""
    try:
        db = get_db()
        
        # Check if learning_records table exists
        table_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='learning_records'"
        ).fetchone()
        
        if not table_check:
            db.close()
            return jsonify({
                'patterns': [],
                'total_patterns': 0,
                'status': 'learning_not_initialized'
            })
        
        # Get learning patterns
        patterns = db.execute('''
            SELECT pattern_type, success_rate, times_applied, pattern_data
            FROM learning_records
            ORDER BY success_rate DESC
            LIMIT 10
        ''').fetchall()
        
        db.close()
        
        pattern_list = []
        for p in patterns:
            pattern_list.append({
                'type': p['pattern_type'],
                'success_rate': p['success_rate'],
                'times_applied': p['times_applied']
            })
        
        return jsonify({
            'patterns': pattern_list,
            'total_patterns': len(pattern_list),
            'status': 'available'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@core_bp.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download generated files"""
    try:
        file_path = f'/mnt/user-data/outputs/{filename}'
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# I did no harm and this file is not truncated
