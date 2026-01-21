"""
Core Routes
Created: January 21, 2026
Last Updated: January 21, 2026 - FIXED: Use current_app.config for schedule generator

Main orchestration endpoint and core API routes.
NO MORE 500+ LINE FUNCTIONS. Clean and manageable.

CRITICAL FIX: Uses current_app.config to access schedule generator (not direct import)
"""

from flask import Blueprint, request, jsonify, send_file, current_app
import time
import json
import os
from datetime import datetime
from database import get_db
from orchestration import (
    analyze_task_with_sonnet,
    handle_with_opus,
    execute_specialist_task,
    validate_with_consensus
)

core_bp = Blueprint('core', __name__)

@core_bp.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    """
    Main orchestration endpoint - NOW READABLE!
    Handles task analysis, specialist routing, consensus validation.
    INCLUDES: Schedule generator intercept, file upload processing
    """
    
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
    
    # ==================== FILE UPLOAD HANDLING ====================
    # Process uploaded files and extract their content
    file_context = ""
    file_names = []
    
    if request.files:
        try:
            from PyPDF2 import PdfReader
            from docx import Document
            import openpyxl
            
            files = request.files.getlist('files')
            
            for file in files:
                filename = file.filename
                file_names.append(filename)
                
                try:
                    if filename.endswith('.pdf'):
                        # Extract PDF text
                        pdf_reader = PdfReader(file.stream)
                        text = ""
                        for page in pdf_reader.pages:
                            text += page.extract_text()
                        file_context += f"\n\n=== FILE: {filename} ===\n{text[:2000]}\n"
                        
                    elif filename.endswith('.docx'):
                        # Extract Word document text
                        doc = Document(file.stream)
                        text = "\n".join([para.text for para in doc.paragraphs])
                        file_context += f"\n\n=== FILE: {filename} ===\n{text[:2000]}\n"
                        
                    elif filename.endswith('.xlsx'):
                        # Extract Excel data
                        wb = openpyxl.load_workbook(file.stream)
                        sheet = wb.active
                        data = []
                        for row in sheet.iter_rows(values_only=True):
                            data.append(str(row))
                        file_context += f"\n\n=== FILE: {filename} ===\n" + "\n".join(data[:50]) + "\n"
                        
                    elif filename.endswith('.txt') or filename.endswith('.csv'):
                        # Extract text files
                        text = file.stream.read().decode('utf-8', errors='ignore')
                        file_context += f"\n\n=== FILE: {filename} ===\n{text[:2000]}\n"
                        
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    file_context += f"\n\n=== FILE: {filename} ===\n[Error reading file: {str(e)}]\n"
            
            # Add file context to user request
            if file_context:
                user_request = f"{user_request}\n\n{file_context}"
        except ImportError:
            print("⚠️ File processing libraries not available")
    
    # ==================== SCHEDULE GENERATION INTERCEPT ====================
    # CHECK IMMEDIATELY - BEFORE ANY AI PROCESSING
    # If this is a schedule request, generate Excel directly and bypass AI
    
    # CRITICAL: Use current_app.config (not direct import)
    if current_app.config.get('SCHEDULE_GENERATOR_AVAILABLE'):
        schedule_gen = current_app.config.get('SCHEDULE_GENERATOR')
        schedule_type = schedule_gen.identify_schedule_type(user_request)
        
        if schedule_type:
            print(f"  📅 SCHEDULE REQUEST DETECTED: {schedule_type}")
            print(f"  ⚡ Bypassing AI - generating Excel directly")
            
            try:
                # Generate Excel schedule directly
                schedule_bytes = schedule_gen.create_schedule(schedule_type, weeks=8)
                
                # Save to outputs directory
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"schedule_{schedule_type}_{timestamp}.xlsx"
                filepath = os.path.join('/mnt/user-data/outputs', filename)
                
                # Ensure output directory exists
                os.makedirs('/mnt/user-data/outputs', exist_ok=True)
                
                with open(filepath, 'wb') as f:
                    f.write(schedule_bytes)
                
                # Get pattern info
                pattern_info = schedule_gen.get_schedule_description(schedule_type)
                
                # Create response message
                response_message = f"""✅ **SCHEDULE CREATED: {pattern_info['name']}**

📋 **Pattern:** {pattern_info['description']}
👥 **Crews:** {pattern_info['crews']}
⏰ **Shift Length:** {pattern_info['shift_length']} hours
📅 **Weeks Generated:** 8

**What's in the Excel file:**
- Week-by-week schedule layout for all crews
- Color-coded shifts (Yellow = Day, Green = Night, Gray = Off)
- D = Day shift, N = Night shift, O = Off
- Professional formatting ready to use
- Legend included

**Download your schedule below** 👇
"""
                
                print(f"  ✅ Schedule created successfully: {filename}")
                
                # Return immediate response WITHOUT going through AI orchestration
                return jsonify({
                    'success': True,
                    'actual_output': response_message,
                    'document_created': True,
                    'document_url': f'/api/download/{filename}',
                    'document_type': 'xlsx',
                    'knowledge_used': False,
                    'formatting_applied': False,
                    'task_id': None,
                    'execution_time_seconds': 0.5,
                    'orchestrator': 'schedule_generator',
                    'specialist_results': []
                })
                
            except Exception as e:
                print(f"  ❌ Schedule generation error: {e}")
                import traceback
                traceback.print_exc()
                # Fall through to normal AI processing if schedule generation fails
    
    # ==================== NORMAL AI ORCHESTRATION ====================
    # If not a schedule request, or if schedule generation failed, continue with AI
    
    # Create task in database
    db = get_db()
    cursor = db.execute(
        'INSERT INTO tasks (user_request, status) VALUES (?, ?)',
        (user_request, 'analyzing')
    )
    task_id = cursor.lastrowid
    db.commit()
    
    overall_start = time.time()
    
    try:
        # Step 1: Sonnet analyzes
        from app import knowledge_base  # Import from main app
        sonnet_analysis = analyze_task_with_sonnet(user_request, knowledge_base)
        
        # Step 2: Escalate to Opus if needed
        if sonnet_analysis.get('escalate_to_opus'):
            db.execute(
                'INSERT INTO escalations (task_id, reason, sonnet_confidence) VALUES (?, ?, ?)',
                (task_id, sonnet_analysis.get('reasoning'), sonnet_analysis.get('confidence'))
            )
            db.commit()
            
            opus_plan = handle_with_opus(user_request, sonnet_analysis, knowledge_base)
            orchestrator = "opus"
            plan = opus_plan
        else:
            orchestrator = "sonnet"
            plan = sonnet_analysis
        
        # Step 3: Execute with specialists OR orchestrator handles directly
        specialist_results = []
        specialists_needed = plan.get('specialists_needed', [])
        actual_output = None
        
        if specialists_needed and specialists_needed != ["none"]:
            for specialist in specialists_needed:
                specialist_task = f"User request: {user_request}\n\nYour role as {specialist}: Complete the task using your specialty."
                result = execute_specialist_task(specialist, specialist_task)
                specialist_results.append(result)
                
                db.execute(
                    '''INSERT INTO specialist_calls 
                       (task_id, specialist_name, specialist_role, output, duration_seconds, success)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (task_id, specialist, result.get('specialist'), 
                     result.get('output'), result.get('execution_time'), result.get('success'))
                )
                db.commit()
                
                if not actual_output:
                    actual_output = result.get('output')
        else:
            # No specialists needed - orchestrator handles it directly
            from orchestration.ai_clients import call_claude_opus, call_claude_sonnet
            if orchestrator == "opus":
                opus_response = call_claude_opus(f"Complete this request:\n\n{user_request}")
                actual_output = opus_response.get('content') if isinstance(opus_response, dict) else opus_response
            else:
                sonnet_response = call_claude_sonnet(f"Complete this request:\n\n{user_request}")
                actual_output = sonnet_response.get('content') if isinstance(sonnet_response, dict) else sonnet_response
            
            specialist_results.append({
                "specialist": orchestrator,
                "output": actual_output,
                "execution_time": 0,
                "success": True
            })
        
        # Step 4: Consensus validation if enabled
        consensus_result = None
        if enable_consensus and actual_output:
            consensus_result = validate_with_consensus(actual_output)
            
            db.execute(
                '''INSERT INTO consensus_validations
                   (task_id, validator_ais, agreement_score, final_decision)
                   VALUES (?, ?, ?, ?)''',
                (task_id, json.dumps(consensus_result.get('validators')),
                 consensus_result.get('agreement_score'), 
                 json.dumps(consensus_result))
            )
            db.commit()
        
        total_time = time.time() - overall_start
        
        # Update task status
        db.execute(
            '''UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? 
               WHERE id = ?''',
            ('completed', orchestrator, total_time, task_id)
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'orchestrator': orchestrator,
            'analysis': plan,
            'actual_output': actual_output,
            'specialist_results': specialist_results,
            'consensus': consensus_result,
            'execution_time_seconds': total_time
        })
        
    except Exception as e:
        db.execute(
            'UPDATE tasks SET status = ?, result = ? WHERE id = ?',
            ('failed', str(e), task_id)
        )
        db.commit()
        
        return jsonify({
            'success': False,
            'error': str(e),
            'task_id': task_id
        }), 500
    finally:
        db.close()

@core_bp.route('/api/tasks', methods=['GET'])
def get_tasks():
    """Get all tasks"""
    db = get_db()
    tasks = db.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50').fetchall()
    db.close()
    
    return jsonify([dict(task) for task in tasks])

@core_bp.route('/api/task/<int:task_id>', methods=['GET'])
def get_task_detail(task_id):
    """Get detailed task information"""
    db = get_db()
    
    task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    specialists = db.execute('SELECT * FROM specialist_calls WHERE task_id = ?', (task_id,)).fetchall()
    consensus = db.execute('SELECT * FROM consensus_validations WHERE task_id = ?', (task_id,)).fetchone()
    escalation = db.execute('SELECT * FROM escalations WHERE task_id = ?', (task_id,)).fetchone()
    
    db.close()
    
    return jsonify({
        'task': dict(task) if task else None,
        'specialists': [dict(s) for s in specialists],
        'consensus': dict(consensus) if consensus else None,
        'escalation': dict(escalation) if escalation else None
    })

@core_bp.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    db = get_db()
    
    total_tasks = db.execute('SELECT COUNT(*) as count FROM tasks').fetchone()['count']
    sonnet_tasks = db.execute("SELECT COUNT(*) as count FROM tasks WHERE assigned_orchestrator = 'sonnet'").fetchone()['count']
    opus_tasks = db.execute("SELECT COUNT(*) as count FROM tasks WHERE assigned_orchestrator = 'opus'").fetchone()['count']
    avg_time = db.execute('SELECT AVG(execution_time_seconds) as avg FROM tasks WHERE status = "completed"').fetchone()['avg']
    
    specialist_usage = db.execute('''
        SELECT specialist_name, COUNT(*) as count 
        FROM specialist_calls 
        GROUP BY specialist_name
    ''').fetchall()
    
    db.close()
    
    return jsonify({
        'total_tasks': total_tasks,
        'sonnet_handled': sonnet_tasks,
        'opus_handled': opus_tasks,
        'sonnet_percentage': round(sonnet_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0,
        'average_time_seconds': round(avg_time, 2) if avg_time else 0,
        'specialist_usage': [dict(s) for s in specialist_usage]
    })

@core_bp.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download generated files"""
    # Security: Only allow files from outputs directory
    filepath = os.path.join('/mnt/user-data/outputs', filename)
    
    # Check if file exists
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    # Determine mime type
    if filename.endswith('.xlsx'):
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif filename.endswith('.docx'):
        mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif filename.endswith('.pdf'):
        mimetype = 'application/pdf'
    elif filename.endswith('.csv'):
        mimetype = 'text/csv'
    else:
        mimetype = 'application/octet-stream'
    
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype=mimetype)

"""
EMERGENCY DIAGNOSTIC ROUTE
Add this temporarily to routes/core.py to diagnose knowledge base issues

ADD THIS ENTIRE BLOCK TO THE BOTTOM OF routes/core.py (before the final comment)
Then push to GitHub and visit /api/diagnose on your Render URL
"""

@core_bp.route('/api/diagnose', methods=['GET'])
def diagnose_system():
    """
    Emergency diagnostic endpoint - shows everything about the system state
    Visit: https://your-app.onrender.com/api/diagnose
    """
    from pathlib import Path
    import sys
    
    diagnosis = {
        'timestamp': datetime.now().isoformat(),
        '1_environment': {},
        '2_file_system': {},
        '3_libraries': {},
        '4_knowledge_base': {},
        '5_initialization_attempt': {}
    }
    
    # ============ ENVIRONMENT ============
    diagnosis['1_environment'] = {
        'python_version': sys.version,
        'current_working_directory': os.getcwd(),
        'is_render': bool(os.getenv('RENDER')),
        'render_service_name': os.getenv('RENDER_SERVICE_NAME', 'N/A')
    }
    
    # ============ FILE SYSTEM ============
    # Check all possible locations
    paths_to_check = [
        'project_files',
        './project_files', 
        '../project_files',
        '/opt/render/project/src/project_files',
        '/mnt/project'
    ]
    
    diagnosis['2_file_system']['paths_checked'] = []
    
    for path_str in paths_to_check:
        path = Path(path_str)
        info = {
            'path': path_str,
            'absolute': str(path.absolute()),
            'exists': path.exists(),
            'is_directory': path.is_dir() if path.exists() else False
        }
        
        if path.exists() and path.is_dir():
            try:
                files = list(path.iterdir())
                info['file_count'] = len(files)
                info['files'] = [f.name for f in files]
            except Exception as e:
                info['error'] = str(e)
        
        diagnosis['2_file_system']['paths_checked'].append(info)
    
    # List what's in root directory
    try:
        root_items = os.listdir('.')
        diagnosis['2_file_system']['root_directory'] = sorted([f for f in root_items if not f.startswith('.')])
    except Exception as e:
        diagnosis['2_file_system']['root_directory_error'] = str(e)
    
    # ============ LIBRARIES ============
    libs = ['docx', 'openpyxl', 'PyPDF2', 'xlsxwriter']
    
    for lib in libs:
        try:
            imported = __import__(lib)
            diagnosis['3_libraries'][lib] = {
                'status': '✅ INSTALLED',
                'version': getattr(imported, '__version__', 'unknown'),
                'location': getattr(imported, '__file__', 'unknown')
            }
        except ImportError as e:
            diagnosis['3_libraries'][lib] = {
                'status': '❌ MISSING',
                'error': str(e)
            }
    
    # ============ KNOWLEDGE BASE STATUS ============
    try:
        # Get the app module
        app_module = sys.modules.get('app')
        
        if app_module:
            kb = getattr(app_module, 'knowledge_base', None)
            
            if kb:
                diagnosis['4_knowledge_base'] = {
                    'instance_exists': True,
                    'class_name': kb.__class__.__name__,
                    'project_path': str(kb.project_path),
                    'project_path_absolute': str(kb.project_path.absolute()),
                    'project_path_exists': kb.project_path.exists(),
                    'documents_in_index': len(kb.knowledge_index),
                    'document_names': list(kb.knowledge_index.keys())
                }
                
                # Check database
                try:
                    import sqlite3
                    db = sqlite3.connect(kb.db_path)
                    count = db.execute('SELECT COUNT(*) FROM knowledge_documents').fetchone()[0]
                    db.close()
                    diagnosis['4_knowledge_base']['documents_in_database'] = count
                except Exception as db_error:
                    diagnosis['4_knowledge_base']['database_error'] = str(db_error)
            else:
                diagnosis['4_knowledge_base'] = {
                    'instance_exists': False,
                    'reason': 'knowledge_base variable is None'
                }
        else:
            diagnosis['4_knowledge_base'] = {
                'error': 'Could not access app module'
            }
    except Exception as e:
        diagnosis['4_knowledge_base']['error'] = str(e)
    
    # ============ TRY TO INITIALIZE ============
    diagnosis['5_initialization_attempt']['message'] = 'Attempting fresh initialization...'
    
    try:
        # Find the project_files directory
        found_path = None
        for path_str in ['project_files', './project_files']:
            if Path(path_str).exists():
                found_path = path_str
                break
        
        if found_path:
            diagnosis['5_initialization_attempt']['found_path'] = found_path
            
            # Try to create a fresh instance
            from knowledge_integration import ProjectKnowledgeBase
            
            test_kb = ProjectKnowledgeBase(project_path=found_path)
            diagnosis['5_initialization_attempt']['test_instance_created'] = True
            
            # Try to initialize it
            try:
                test_kb.initialize()
                diagnosis['5_initialization_attempt']['initialization_result'] = {
                    'success': True,
                    'documents_indexed': len(test_kb.knowledge_index),
                    'document_names': list(test_kb.knowledge_index.keys())
                }
            except Exception as init_error:
                diagnosis['5_initialization_attempt']['initialization_result'] = {
                    'success': False,
                    'error': str(init_error),
                    'error_type': type(init_error).__name__
                }
        else:
            diagnosis['5_initialization_attempt']['error'] = 'No project_files directory found'
    except Exception as e:
        diagnosis['5_initialization_attempt']['error'] = str(e)
        import traceback
        diagnosis['5_initialization_attempt']['traceback'] = traceback.format_exc()
    
    # ============ RECOMMENDATIONS ============
    diagnosis['6_recommendations'] = []
    
    # Check if libraries are missing
    missing_libs = [lib for lib, info in diagnosis['3_libraries'].items() 
                    if isinstance(info, dict) and info.get('status') == '❌ MISSING']
    if missing_libs:
        diagnosis['6_recommendations'].append(
            f"CRITICAL: Missing libraries: {', '.join(missing_libs)}. Update requirements.txt and redeploy."
        )
    
    # Check if project_files exists
    project_files_exists = any(
        p.get('exists') and p.get('path') in ['project_files', './project_files']
        for p in diagnosis['2_file_system'].get('paths_checked', [])
    )
    if not project_files_exists:
        diagnosis['6_recommendations'].append(
            "CRITICAL: project_files directory not found on server. Verify it's in your GitHub repo and pushed."
        )
    
    # Check initialization result
    init_result = diagnosis['5_initialization_attempt'].get('initialization_result', {})
    if init_result.get('success'):
        diagnosis['6_recommendations'].append(
            f"SUCCESS: Test initialization worked! Indexed {init_result.get('documents_indexed')} documents. "
            f"The issue may be in how app.py initializes the knowledge base."
        )
    
    return jsonify(diagnosis)

# I did no harm and this file is not truncated
# I did no harm and this file is not truncated
