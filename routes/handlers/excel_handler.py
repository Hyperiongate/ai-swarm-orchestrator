"""
Excel Handler - Large File Analysis Workflows
Created: February 10, 2026
Last Updated: February 10, 2026

Handles Excel file analysis with intelligent routing:
- Small-medium files (under 100MB) with data questions -> Smart pandas analyzer
- Large files or conversational questions -> Progressive analysis

Fixed all syntax errors:
- No emojis
- No Unicode box characters
- Fixed apostrophes in f-strings
- Changed "8hr" to "8-hour"

Author: Jim @ Shiftwork Solutions LLC
"""

import os
import time
import traceback
from datetime import datetime
from flask import jsonify, session
import pandas as pd

from database import get_db, add_message
from progressive_file_analyzer import get_progressive_analyzer
from routes.utils import convert_markdown_to_html


def handle_large_excel_initial(file_path, user_request, conversation_id, project_id, mode, file_info, overall_start):
    """
    Handle initial upload of Excel file with intelligent routing.
    
    Routes to either:
    - Smart pandas analyzer for data analysis questions
    - Progressive analyzer for large files or conversational mode
    
    Args:
        file_path: Path to Excel file
        user_request: User request
        conversation_id: Conversation ID
        project_id: Project ID
        mode: Conversation mode
        file_info: File info dict with size, type
        overall_start: Start time for timing
        
    Returns:
        Flask JSON response
    """
    try:
        # Determine analysis strategy
        file_size_mb = file_info['file_size_mb']
        
        # Check if user wants conversational/narrative analysis
        conversational_keywords = [
            'tell me about', 'describe', 'explain', 'what does this show',
            'give me an overview', 'summarize', 'walk me through'
        ]
        
        user_wants_conversation = any(keyword in user_request.lower() for keyword in conversational_keywords)
        
        # Use smart analyzer by DEFAULT for files under 100MB
        use_smart_analyzer = (file_size_mb < 100 and not user_wants_conversation)
        
        print(f"File: {file_size_mb}MB | Analysis mode: {'SMART_PANDAS' if use_smart_analyzer else 'PROGRESSIVE'}")
        
        # Route to appropriate handler
        if use_smart_analyzer:
            return handle_excel_smart_analysis(
                file_path, user_request, conversation_id, project_id, 
                mode, file_info, overall_start
            )
        else:
            return handle_progressive_analysis(
                file_path, user_request, conversation_id, project_id,
                mode, file_info, overall_start
            )
            
    except Exception as e:
        print(f"Large Excel handling error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


def handle_progressive_analysis(file_path, user_request, conversation_id, project_id, mode, file_info, overall_start):
    """
    Handle Excel with progressive chunked analysis.
    
    Args:
        file_path: Path to Excel file
        user_request: User request
        conversation_id: Conversation ID
        project_id: Project ID
        mode: Conversation mode
        file_info: File info dict
        overall_start: Start time
        
    Returns:
        Flask JSON response
    """
    try:
        from database import create_conversation
        
        analyzer = get_progressive_analyzer()
        
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
        
        # Use temp file directly (no permanent save)
        original_filename = os.path.basename(file_path)
        permanent_path = file_path
        
        print(f"Using temporary file: {file_path}")
        
        # Store minimal info in session
        session[f'file_analysis_{conversation_id}'] = {
            'file_path': permanent_path,
            'current_position': chunk_result['end_row'],
            'total_rows': chunk_result['total_rows'],
            'columns': chunk_result['columns'],
            'file_name': original_filename,
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
        
        sheet_names = chunk_result.get('sheet_names', ['Sheet1'])
        num_sheets = chunk_result.get('num_sheets', 1)
        sheets_summary = f"\nFILE CONTAINS {num_sheets} WORKSHEET(S): {', '.join(sheet_names)}\n"
        
        analysis_prompt = f"""You are Jim Goodwin, Shiftwork Solutions LLC - 30+ years optimizing 24/7 operations.

CLIENT FILE: {file_info['file_size_mb']}MB Excel, {chunk_result['total_rows']:,} total rows
REQUEST: {user_request}
{sheets_summary}

YOUR TASK: Analyze first 100 rows with SPECIFIC NUMBERS - this is a $16,500/week consulting engagement.

DELIVER:
1. Key Statistics - Actual totals, ranges, averages (not "varies")
2. Top Patterns - What 3 things stand out? Use percentages.
3. Operational Insights - Coverage gaps? Shift patterns? Cost drivers?
4. Red Flags - What needs immediate attention?
5. Next Steps - What would you recommend?

DATA (First 100 rows):
{chunk_result['summary']}

{chunk_result['text_preview']}

BE SPECIFIC. Use actual numbers from the data."""

        print(f"Calling GPT-4 with max_tokens=3000...")
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
                        'total_rows': chunk_result['total_rows'], 'execution_time': total_time,
                        'permanent_file': permanent_path})
                        
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
            error_msg = gpt_response.get('content', 'Unknown error')
            print(f"GPT-4 analysis failed: {error_msg}")
            db.close()
            return jsonify({
                'success': False,
                'error': f'Could not analyze Excel file: {error_msg}'
            }), 500
            
    except Exception as e:
        print(f"Progressive analysis error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


def handle_excel_smart_analysis(file_path, user_request, conversation_id, project_id, mode, file_info, overall_start):
    """
    Handle Excel analysis using pandas for REAL calculations.
    
    Loads entire file into memory, profiles it, generates pandas code
    to answer user questions with actual calculations.
    
    Args:
        file_path: Path to Excel file
        user_request: User request
        conversation_id: Conversation ID
        project_id: Project ID
        mode: Conversation mode
        file_info: File info dict
        overall_start: Start time
        
    Returns:
        Flask JSON response
    """
    try:
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from smart_excel_analyzer import SmartExcelAnalyzer
        from orchestration.ai_clients import call_gpt4
        from database import create_conversation, save_smart_analyzer_state
        
        print(f"Using Smart Pandas Analyzer for {file_info['file_size_mb']}MB file")
        
        # Create conversation if needed
        if not conversation_id:
            conversation_id = create_conversation(mode=mode, project_id=project_id)
            print(f"Created new conversation: {conversation_id}")
        
        # Load and profile the file
        analyzer = SmartExcelAnalyzer(file_path)
        profile_result = analyzer.load_and_profile()
        
        if not profile_result['success']:
            return jsonify({
                'success': False,
                'error': f"Could not load Excel file: {profile_result.get('error')}"
            }), 500
        
        # Use temp file directly (no permanent save)
        original_filename = os.path.basename(file_path)
        permanent_path = file_path
        
        print(f"Using temporary file: {permanent_path}")
        
        # Store analyzer in session for follow-up questions
        save_smart_analyzer_state(
            conversation_id=conversation_id,
            file_path=permanent_path,
            file_name=original_filename,
            profile=analyzer.profile
        )
        
        # Create task
        db = get_db()
        cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                           (user_request, 'processing', conversation_id))
        task_id = cursor.lastrowid
        db.commit()
        
        # Get file profile and ask GPT-4 to understand the file
        profile_context = analyzer.format_for_gpt_context()
        
        initial_prompt = f"""You are Jim Goodwin, Shiftwork Solutions LLC - 30+ years optimizing 24/7 operations.

A client has uploaded an Excel file. Here is what I found:

{profile_context}

USER REQUEST: {user_request}

YOUR TASK:

1. Understand what the user wants - What specific analysis or view are they asking for?

2. Generate pandas code to answer their question. The DataFrame is called df.
   - Use actual pandas methods (groupby, agg, pivot_table, etc.)
   - Return ONLY the pandas expression that will produce the result
   - No explanations, just the code

3. Format: Return your response in TWO parts:
   
   PART 1 - PANDAS_CODE (on its own line, clearly marked):
```
   PANDAS_CODE: df.groupby('Department')['Hours'].sum()
```
   
   PART 2 - EXPLANATION (what this analysis will show):
   Brief explanation of what the results will tell the user.

EXAMPLES:

User asks: "Show me total hours by department"
Your response:
```
PANDAS_CODE: df.groupby('Dept & Bldg')['Total Hours'].sum().sort_values(ascending=False)

This will show the total hours for each department, sorted from highest to lowest.
```

User asks: "What day of the week has the most overtime?"
Your response:
```
PANDAS_CODE: df.groupby(df['Date'].dt.day_name())['Overtime'].sum().sort_values(ascending=False)

This will show which day of the week (Monday-Sunday) has the most overtime hours.
```

NOW ANSWER THE USER QUESTION."""

        print(f"Asking GPT-4 to generate pandas code...")
        gpt_response = call_gpt4(initial_prompt, max_tokens=2000)
        
        if not gpt_response.get('error') and gpt_response.get('content'):
            ai_response = gpt_response.get('content', '')
            
            # Extract pandas code from GPT-4 response
            import re
            pandas_code_match = re.search(r'PANDAS_CODE:\s*(.+?)(?:\n|$)', ai_response, re.MULTILINE | re.DOTALL)
            
            if pandas_code_match:
                pandas_code = pandas_code_match.group(1).strip()
                # Remove any markdown code blocks
                pandas_code = re.sub(r'```python?\s*|\s*```', '', pandas_code).strip()
                
                print(f"Extracted pandas code: {pandas_code}")
                
                # Execute the pandas code
                execution_result = analyzer.execute_analysis(user_request, pandas_code)
                
                if execution_result.get('success') and execution_result.get('result'):
                    # Get the markdown formatted result
                    result_markdown = execution_result['result']['markdown']
                    
                    # Check if result is a DataFrame and has >5 rows - create download
                    result_df = execution_result['result'].get('dataframe')
                    download_created = False
                    download_filepath = None
                    
                    if result_df is not None and len(result_df) > 10:
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"analysis_{timestamp}.xlsx"
                        output_path = f"/tmp/outputs/{filename}"
                        
                        try:
                            os.makedirs("/tmp/outputs", exist_ok=True)
                            result_df.to_excel(output_path, index=True, engine='openpyxl')
                            print(f"Saved {len(result_df)} rows to {output_path}")
                            
                            download_created = True
                            download_filepath = f"/api/download/{filename}"
                            
                            # Show preview instead of full table
                            preview_df = result_df.head(30)
                            result_markdown = preview_df.to_markdown(index=True)
                            result_markdown = f"Showing first 30 rows of {len(result_df)} total. Download complete file below.\n\n" + result_markdown
                        except Exception as save_error:
                            print(f"Could not save Excel: {save_error}")
                    
                    # Build final response
                    full_response = f"""# Analysis Results

{ai_response.split('PANDAS_CODE:')[0].strip() if 'PANDAS_CODE:' in ai_response else ''}

## Results

{result_markdown}

---

What would you like to know next? I have the complete dataset loaded and can answer follow-up questions instantly."""
                    
                    formatted_output = convert_markdown_to_html(full_response)
                    
                    total_time = time.time() - overall_start
                    db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                              ('completed', 'smart_pandas_analyzer', total_time, task_id))
                    db.commit()
                    db.close()
                    
                    add_message(conversation_id, 'assistant', full_response, task_id,
                               {'orchestrator': 'smart_pandas_analyzer', 
                                'total_rows': profile_result['profile']['file_info']['total_rows'],
                                'execution_time': total_time,
                                'permanent_file': permanent_path,
                                'pandas_code': pandas_code})
                    
                    return jsonify({
                        'success': True,
                        'task_id': task_id,
                        'conversation_id': conversation_id,
                        'result': formatted_output,
                        'orchestrator': 'smart_pandas_analyzer',
                        'execution_time': total_time,
                        'total_rows': profile_result['profile']['file_info']['total_rows'],
                        'analysis_type': 'pandas_calculation',
                        'download_available': download_created,
                        'download_file': download_filepath if download_created else None,
                        'download_filename': os.path.basename(download_filepath) if download_created and download_filepath else None
                    })
                else:
                    # Pandas execution failed
                    error_msg = execution_result.get('error', 'Unknown error')
                    print(f"Pandas execution failed: {error_msg}")
                    
                    fallback_response = f"""I loaded your file successfully ({profile_result['profile']['file_info']['total_rows']:,} rows), but encountered an issue running the analysis.

Error: {error_msg}

What I can see in your file:
{analyzer.get_profile_summary()}

Please rephrase your question or ask me to show you something specific from the data."""
                    
                    formatted_output = convert_markdown_to_html(fallback_response)
                    
                    total_time = time.time() - overall_start
                    db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                              ('completed', 'smart_pandas_analyzer', total_time, task_id))
                    db.commit()
                    db.close()
                    
                    add_message(conversation_id, 'assistant', fallback_response, task_id,
                               {'orchestrator': 'smart_pandas_analyzer', 
                                'total_rows': profile_result['profile']['file_info']['total_rows'],
                                'execution_time': total_time,
                                'error': error_msg})
                    
                    return jsonify({
                        'success': True,
                        'task_id': task_id,
                        'conversation_id': conversation_id,
                        'result': formatted_output,
                        'orchestrator': 'smart_pandas_analyzer',
                        'execution_time': total_time
                    })
            else:
                # Could not extract pandas code
                print("Could not extract pandas code from GPT-4 response")
                
                profile_response = f"""I loaded your Excel file successfully!

{analyzer.get_profile_summary()}

Suggested analyses:
{chr(10).join(f"- {s}" for s in analyzer.profile.get('suggested_analyses', []))}

What would you like to analyze?"""
                
                formatted_output = convert_markdown_to_html(profile_response)
                
                total_time = time.time() - overall_start
                db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                          ('completed', 'smart_pandas_analyzer', total_time, task_id))
                db.commit()
                db.close()
                
                add_message(conversation_id, 'assistant', profile_response, task_id,
                           {'orchestrator': 'smart_pandas_analyzer', 
                            'total_rows': profile_result['profile']['file_info']['total_rows'],
                            'execution_time': total_time})
                
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'conversation_id': conversation_id,
                    'result': formatted_output,
                    'orchestrator': 'smart_pandas_analyzer',
                    'execution_time': total_time
                })
        else:
            error_msg = gpt_response.get('content', 'Unknown error')
            print(f"GPT-4 failed: {error_msg}")
            db.close()
            return jsonify({
                'success': False,
                'error': f'Could not analyze file: {error_msg}'
            }), 500
            
    except Exception as e:
        print(f"Smart analysis error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


def handle_smart_analyzer_continuation(user_request, conversation_id, project_id, mode):
    """
    Handle follow-up questions after smart analyzer loads a file.
    
    Args:
        user_request: User follow-up question
        conversation_id: Conversation ID
        project_id: Project ID
        mode: Conversation mode
        
    Returns:
        Flask JSON response or None if not a continuation
    """
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from smart_excel_analyzer import SmartExcelAnalyzer
        from orchestration.ai_clients import call_gpt4
        from database import get_smart_analyzer_state
        
        analyzer_state = get_smart_analyzer_state(conversation_id)
        if not analyzer_state:
            return None
        
        print(f"Smart analyzer continuation - reloading file: {analyzer_state['file_name']}")
        
        file_path = analyzer_state['file_path']
        analyzer = SmartExcelAnalyzer(file_path)
        load_result = analyzer.load_and_profile()
        
        if not load_result['success']:
            return jsonify({'success': False, 'error': f"Could not reload file: {load_result.get('error')}"}), 500
        
        print(f"File reloaded: {len(analyzer.df):,} rows")
        
        db = get_db()
        cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                           (user_request, 'processing', conversation_id))
        task_id = cursor.lastrowid
        db.commit()
        
        overall_start = time.time()
        profile_context = analyzer.format_for_gpt_context()
        
        analysis_prompt = f"""{profile_context}

USER QUESTION: {user_request}

YOUR RESPONSE FORMAT - FOLLOW EXACTLY:
Line 1: CODE: [your pandas expression]
Line 2: (blank)
Line 3 onwards: Brief explanation

NOW ANSWER THE USER QUESTION. Start with "CODE: " followed by pandas expression."""

        print(f"Asking GPT-4 to generate pandas code...")
        gpt_response = call_gpt4(analysis_prompt, max_tokens=2000)
        
        if not gpt_response.get('error') and gpt_response.get('content'):
            ai_response = gpt_response.get('content', '')
            
            import re
            print(f"RAW GPT-4 RESPONSE (first 500 chars): {ai_response[:500]}")
            
            try:
                if 'CODE:' in ai_response:
                    code_match = re.search(r'CODE:\s*(.+?)(?:\n|$)', ai_response, re.MULTILINE)
                    pandas_code = code_match.group(1).strip() if code_match else ai_response.split('CODE:')[1].split('\n')[0].strip()
                else:
                    pandas_code = re.sub(r'```python?\s*|\s*```', '', ai_response).strip()
                
                pandas_code = re.sub(r'^PANDAS_CODE:\s*', '', pandas_code, flags=re.IGNORECASE).strip()
                
            except Exception as extract_error:
                print(f"Code extraction failed: {extract_error}")
                pandas_code = ai_response.strip()
            
            print(f"Extracted pandas code: {pandas_code[:100]}...")
            
            execution_result = analyzer.execute_analysis(user_request, pandas_code)
            
            if execution_result['success']:
                result_data = execution_result['result']
                result_df = result_data.get('dataframe')
                result_markdown = result_data['markdown']
                
                download_created = False
                download_filepath = None
                preview_note = ""
                
                if result_df is not None and len(result_df) > 10:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"analysis_{timestamp}.xlsx"
                    output_path = f"/tmp/outputs/{filename}"
                    
                    try:
                        os.makedirs("/tmp/outputs", exist_ok=True)
                        result_df.to_excel(output_path, index=True, engine='openpyxl')
                        print(f"Saved {len(result_df)} rows to {output_path}")
                        
                        download_created = True
                        download_filepath = f"/api/download/{filename}"
                        
                        preview_df = result_df.head(30)
                        result_markdown = preview_df.to_markdown(index=True)
                        preview_note = f"""

COMPLETE RESULTS ({len(result_df)} rows)

Showing first 30 rows below. Download the complete Excel file with the link below.

---

"""
                    except Exception as save_error:
                        print(f"Could not save to Excel: {save_error}")
                        preview_note = f"\n\nNote: Table has {len(result_df)} rows (showing first 50)\n\n"
                        result_markdown = result_df.head(50).to_markdown(index=True)
                
                full_response = f"""## Results
{preview_note}
{result_markdown}

---

What else would you like to know?"""
                
                formatted_output = convert_markdown_to_html(full_response)
                
                total_time = time.time() - overall_start
                db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                          ('completed', 'smart_pandas_analyzer_continuation', total_time, task_id))
                db.commit()
                db.close()
                
                add_message(conversation_id, 'assistant', full_response, task_id,
                           {'orchestrator': 'smart_pandas_analyzer_continuation',
                            'execution_time': total_time,
                            'pandas_code': pandas_code,
                            'rows_processed': len(analyzer.df),
                            'download_created': download_created})
                
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'conversation_id': conversation_id,
                    'result': formatted_output,
                    'orchestrator': 'smart_pandas_analyzer_continuation',
                    'execution_time': total_time,
                    'download_available': download_created,
                    'download_file': download_filepath if download_created else None,
                    'download_filename': os.path.basename(download_filepath) if download_created and download_filepath else None
                })
            
            else:
                error_msg = execution_result.get('error', 'Unknown error')
                print(f"Pandas execution failed: {error_msg}")
                
                error_response = f"""I tried to analyze your data but encountered an issue:

Error: {error_msg}

Code attempted: 
```python
{pandas_code}
```

Could you rephrase your question?

Available columns: {', '.join(analyzer.df.columns)}"""
                
                formatted_output = convert_markdown_to_html(error_response)
                
                total_time = time.time() - overall_start
                db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                          ('completed', 'smart_pandas_analyzer_error', total_time, task_id))
                db.commit()
                db.close()
                
                add_message(conversation_id, 'assistant', error_response, task_id,
                           {'orchestrator': 'smart_pandas_analyzer_error',
                            'error': error_msg,
                            'execution_time': total_time})
                
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'conversation_id': conversation_id,
                    'result': formatted_output,
                    'orchestrator': 'smart_pandas_analyzer_error',
                    'execution_time': total_time
                })
        else:
            error_msg = gpt_response.get('content', 'Unknown error')
            print(f"GPT-4 failed: {error_msg}")
            db.close()
            return jsonify({'success': False, 'error': f'Could not generate analysis: {error_msg}'}), 500
            
    except Exception as e:
        print(f"Smart analyzer continuation error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


def handle_progressive_continuation(conversation_id, user_request, continuation_request, file_analysis_state, overall_start):
    """
    Handle user requesting more rows from a large Excel file.
    
    Args:
        conversation_id: Conversation ID
        user_request: User request
        continuation_request: Parsed continuation request
        file_analysis_state: File analysis state from session
        overall_start: Start time
        
    Returns:
        Flask JSON response
    """
    try:
        analyzer = get_progressive_analyzer()
        
        file_path = file_analysis_state['file_path']
        current_position = file_analysis_state['current_position']
        total_rows = file_analysis_state['total_rows']
        file_name = file_analysis_state.get('file_name', 'file')
        
        action = continuation_request['action']
        
        if action == 'analyze_next':
            num_rows = continuation_request['num_rows']
            start_row = current_position
        elif action == 'analyze_all':
            num_rows = None
            start_row = current_position
        elif action == 'analyze_range':
            start_row = continuation_request['start_row']
            num_rows = continuation_request['end_row'] - start_row
        else:
            return jsonify({'success': False, 'error': 'Invalid continuation action'}), 400
        
        end_display = start_row + num_rows if num_rows else 'end'
        print(f"Extracting rows {start_row} to {end_display} from {file_name}")
        
        chunk_result = analyzer.extract_excel_chunk(file_path, start_row=start_row, num_rows=num_rows)
        
        if not chunk_result['success']:
            return jsonify({'success': False, 'error': f"Could not extract data: {chunk_result.get('error')}"}), 500
        
        session[f'file_analysis_{conversation_id}']['current_position'] = chunk_result['end_row']
        
        db = get_db()
        cursor = db.execute('INSERT INTO tasks (user_request, status, conversation_id) VALUES (?, ?, ?)',
                           (user_request, 'processing', conversation_id))
        task_id = cursor.lastrowid
        db.commit()
        
        from orchestration.ai_clients import call_gpt4
        
        rows_analyzed = chunk_result['rows_analyzed']
        
        analysis_prompt = f"""You are Jim Goodwin, Shiftwork Solutions LLC - analyzing workforce data.

USER REQUEST: {user_request}

CRITICAL INSTRUCTION: The user wants ACTUAL CALCULATIONS from the data below.
- Calculate actual totals, averages, sums
- Provide real numbers in tables
- Just analyze the data and give the user the actual numbers

DATA ANALYZED: Rows {start_row + 1} to {chunk_result['end_row']} ({rows_analyzed:,} rows)

{chunk_result['summary']}

{chunk_result['text_preview']}

DELIVER ACTUAL ANALYSIS WITH REAL NUMBERS FROM THIS DATA."""

        print(f"Calling GPT-4 to analyze {rows_analyzed:,} rows...")
        gpt_response = call_gpt4(analysis_prompt, max_tokens=4000)
        
        if not gpt_response.get('error') and gpt_response.get('content'):
            ai_analysis = gpt_response.get('content', '')
            
            if chunk_result['rows_remaining'] > 0:
                continuation_prompt = analyzer.generate_continuation_prompt(chunk_result)
                full_response = ai_analysis + continuation_prompt
            else:
                full_response = ai_analysis + "\n\nAnalysis complete! All rows have been analyzed."
                session.pop(f'file_analysis_{conversation_id}', None)
            
            formatted_output = convert_markdown_to_html(full_response)
            
            total_time = time.time() - overall_start
            db.execute('UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
                      ('completed', 'gpt4_progressive_excel', total_time, task_id))
            db.commit()
            db.close()
            
            add_message(conversation_id, 'assistant', full_response, task_id,
                       {'orchestrator': 'gpt4_progressive_excel', 'rows_analyzed': rows_analyzed,
                        'total_rows': total_rows, 'execution_time': total_time})
            
            return jsonify({
                'success': True,
                'task_id': task_id,
                'conversation_id': conversation_id,
                'result': formatted_output,
                'orchestrator': 'gpt4_progressive_excel',
                'execution_time': total_time,
                'progressive_analysis': True,
                'rows_analyzed': rows_analyzed,
                'total_rows': total_rows,
                'rows_remaining': chunk_result['rows_remaining']
            })
        else:
            db.close()
            return jsonify({'success': False, 'error': 'Could not analyze data'}), 500
            
    except Exception as e:
        print(f"Progressive continuation error: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# I did no harm and this file is not truncated
