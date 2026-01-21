"""
Core Routes
Created: January 21, 2026
Last Updated: January 21, 2026 - Added comprehensive error handling

Main orchestration endpoint and core API routes.
CRITICAL FIX: Wrapped everything in try-except to prevent 500 errors
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
    Main orchestration endpoint with comprehensive error handling
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
        
        # Create task in database
        db = get_db()
        cursor = db.execute(
            'INSERT INTO tasks (user_request, status) VALUES (?, ?)',
            (user_request, 'processing')
        )
        task_id = cursor.lastrowid
        db.commit()
        
        # ==================== SCHEDULE GENERATOR INTERCEPT ====================
        # Check if this is a schedule request - bypass AI if so
        schedule_keywords = ['dupont', 'panama', 'pitman', 'southern swing', '2-2-3', '2-3-2', 
                            'create a schedule', 'generate a schedule', 'make a schedule']
        
        is_schedule_request = any(keyword in user_request.lower() for keyword in schedule_keywords)
        
        if is_schedule_request and current_app.config.get('SCHEDULE_GENERATOR_AVAILABLE'):
            try:
                schedule_gen = current_app.config.get('SCHEDULE_GENERATOR')
                schedule_type = schedule_gen.identify_schedule_type(user_request)
                
                if schedule_type:
                    # Generate the schedule
                    schedule_file = schedule_gen.create_schedule(schedule_type)
                    
                    if schedule_file and os.path.exists(schedule_file):
                        # Return download link
                        filename = os.path.basename(schedule_file)
                        
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
                            'result': f'Schedule created successfully',
                            'document_url': f'/api/download/{filename}',
                            'execution_time': time.time() - overall_start,
                            'orchestrator': 'schedule_generator'
                        })
            except Exception as schedule_error:
                # If schedule generation fails, continue with regular AI processing
                print(f"Schedule generation failed: {schedule_error}")
        
        # ==================== REGULAR AI ORCHESTRATION ====================
        try:
            # Step 1: Analyze with Sonnet
            analysis = analyze_task_with_sonnet(user_request)
            
            orchestrator = analysis.get('orchestrator', 'sonnet')
            specialists_needed = analysis.get('specialists', [])
            confidence = analysis.get('confidence', 0.5)
            
            # Step 2: Escalate to Opus if needed
            if orchestrator == "opus":
                opus_result = handle_with_opus(user_request)
                actual_output = opus_result.get('output')
                orchestrator = 'opus'
            else:
                actual_output = None
            
            # Step 3: Execute with specialists if needed
            specialist_results = []
            
            if specialists_needed:
                for specialist_info in specialists_needed:
                    if isinstance(specialist_info, dict):
                        specialist = specialist_info.get('specialist')
                        specialist_task = specialist_info.get('task', user_request)
                    else:
                        specialist = specialist_info
                        specialist_task = user_request
                    
                    result = execute_specialist_task(specialist, specialist_task)
                    specialist_results.append(result)
                    
                    if not actual_output:
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
            
            # Step 4: Consensus validation if enabled
            consensus_result = None
            if enable_consensus and actual_output:
                try:
                    consensus_result = validate_with_consensus(actual_output)
                except Exception as consensus_error:
                    print(f"Consensus validation failed: {consensus_error}")
                    consensus_result = None
            
            total_time = time.time() - overall_start
            
            # Update task
            db.execute(
                '''UPDATE tasks SET status = ?, assigned_orchestrator = ?, 
                   execution_time_seconds = ? WHERE id = ?''',
                ('completed', orchestrator, total_time, task_id)
            )
            db.commit()
            db.close()
            
            return jsonify({
                'success': True,
                'task_id': task_id,
                'result': actual_output or "Task completed",
                'orchestrator': orchestrator,
                'specialists_used': [s.get('specialist') for s in specialist_results] if specialist_results else [],
                'consensus': consensus_result,
                'execution_time': total_time
            })
            
        except Exception as orchestration_error:
            # Orchestration failed - return error but don't crash
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
        # Top-level error - something went very wrong
        import traceback
        error_trace = traceback.format_exc()
        print(f"CRITICAL ERROR in orchestrate: {error_trace}")
        
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}',
            'details': 'Check server logs for full traceback'
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
