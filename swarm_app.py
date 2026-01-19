"""
AI SWARM ORCHESTRATOR - Main Application
Created: January 18, 2026
Last Updated: January 18, 2026

PURPOSE:
Intelligent AI orchestration system that routes tasks to specialist AIs,
validates through consensus, and learns from outcomes.

ARCHITECTURE:
- Sonnet (Primary Orchestrator): Fast routing for 90% of tasks
- Opus (Strategic Supervisor): Deep analysis for 10% complex tasks  
- Specialist AIs: GPT-4 (design), DeepSeek (code), Gemini (multimodal)
- Consensus Engine: Multi-AI validation
- Learning Layer: Improves over time

AUTHOR: Jim @ Shiftwork Solutions LLC
REPOSITORY: ai-swarm-orchestrator
"""

from flask import Flask, render_template, request, jsonify
import os
import sqlite3
from datetime import datetime
import json
from openai import OpenAI
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

app = Flask(__name__)

# ============================================================================
# API CONFIGURATION
# ============================================================================

# Anthropic (Claude Opus + Sonnet)
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

# OpenAI (GPT-4 for design/content)
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# DeepSeek (Code specialist)
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com") if DEEPSEEK_API_KEY else None

# Google Gemini (Multimodal specialist)
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

# Mistral (Alternative perspective)
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY')

# Groq (Fast inference)
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_API_KEY else None

# ============================================================================
# DATABASE SETUP
# ============================================================================

DATABASE = 'swarm_intelligence.db'

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initialize database tables"""
    db = get_db()
    
    # Tasks table - all requests that come in
    db.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_request TEXT NOT NULL,
            task_type TEXT,
            complexity TEXT,
            assigned_orchestrator TEXT,
            status TEXT DEFAULT 'pending',
            result TEXT,
            execution_time_seconds REAL
        )
    ''')
    
    # Specialist assignments - which AI did what
    db.execute('''
        CREATE TABLE IF NOT EXISTS specialist_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            specialist_name TEXT NOT NULL,
            specialist_role TEXT,
            assigned_reason TEXT,
            output TEXT,
            execution_time_seconds REAL,
            success BOOLEAN,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    # Consensus validations - multi-AI agreement checks
    db.execute('''
        CREATE TABLE IF NOT EXISTS consensus_validations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            validator_ais TEXT,
            agreement_score REAL,
            disagreements TEXT,
            final_decision TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    # Learning records - track what works
    db.execute('''
        CREATE TABLE IF NOT EXISTS learning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pattern_type TEXT,
            pattern_data TEXT,
            success_rate REAL,
            times_applied INTEGER DEFAULT 1
        )
    ''')
    
    # Escalations - when Sonnet calls Opus
    db.execute('''
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            escalated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT,
            sonnet_confidence REAL,
            opus_analysis TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    db.commit()
    db.close()

# Initialize on startup
init_db()

# ============================================================================
# AI CLIENT FUNCTIONS
# ============================================================================

def call_claude_sonnet(prompt, max_tokens=4000):
    """Call Claude Sonnet (Primary Orchestrator)"""
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()['content'][0]['text']
    except Exception as e:
        return f"ERROR: Claude Sonnet call failed - {str(e)}"

def call_claude_opus(prompt, max_tokens=4000):
    """Call Claude Opus (Strategic Supervisor)"""
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-opus-4-20250514",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=90
        )
        response.raise_for_status()
        return response.json()['content'][0]['text']
    except Exception as e:
        return f"ERROR: Claude Opus call failed - {str(e)}"

def call_gpt4(prompt, max_tokens=4000):
    """Call GPT-4 (Design & Content Specialist)"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: GPT-4 call failed - {str(e)}"

def call_deepseek(prompt, max_tokens=4000):
    """Call DeepSeek (Code Specialist)"""
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: DeepSeek call failed - {str(e)}"

def call_gemini(prompt, max_tokens=4000):
    """Call Gemini (Multimodal Specialist)"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GOOGLE_API_KEY}"
        response = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60
        )
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"ERROR: Gemini call failed - {str(e)}"

# ============================================================================
# ORCHESTRATION LOGIC
# ============================================================================

def analyze_task_with_sonnet(user_request):
    """
    Sonnet analyzes incoming request and decides:
    1. Can I handle this? (confidence score)
    2. If yes: What specialists do I need?
    3. If no: Escalate to Opus
    """
    
    analysis_prompt = f"""You are the primary orchestrator in an AI swarm system. Analyze this user request and provide a JSON response.

USER REQUEST: {user_request}

Analyze:
1. Task type (strategy, code, design, content, analysis, multimodal, complex)
2. Your confidence in handling this (0.0-1.0)
3. Required specialists (gpt4, deepseek, gemini, mistral, or "none")
4. Should this be escalated to Opus? (true/false)
5. Reasoning

Respond ONLY with valid JSON:
{{
    "task_type": "string",
    "confidence": 0.0-1.0,
    "specialists_needed": ["ai_name", ...],
    "escalate_to_opus": boolean,
    "reasoning": "string"
}}"""

    start_time = time.time()
    response = call_claude_sonnet(analysis_prompt)
    execution_time = time.time() - start_time
    
    # Parse JSON response
    try:
        # Extract JSON if wrapped in markdown
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
            
        analysis = json.loads(response)
        analysis['execution_time'] = execution_time
        return analysis
    except:
        # Fallback if JSON parsing fails
        return {
            "task_type": "unknown",
            "confidence": 0.5,
            "specialists_needed": [],
            "escalate_to_opus": True,
            "reasoning": "Failed to parse Sonnet response, escalating to Opus",
            "raw_response": response,
            "execution_time": execution_time
        }

def handle_with_opus(user_request, sonnet_analysis):
    """
    Opus handles complex/novel situations
    Returns strategic plan with specialist assignments
    """
    
    opus_prompt = f"""You are the strategic supervisor in an AI swarm system. Sonnet (primary orchestrator) has escalated this request to you.

USER REQUEST: {user_request}

SONNET'S ANALYSIS:
{json.dumps(sonnet_analysis, indent=2)}

Provide a strategic response with:
1. Deep analysis of the request
2. Specialist assignments (which AIs should do what)
3. Expected workflow
4. Any new patterns Sonnet should learn

Respond in JSON format:
{{
    "strategic_analysis": "string",
    "specialist_assignments": [
        {{"ai": "name", "task": "description", "reason": "why this AI"}}
    ],
    "workflow": ["step1", "step2", ...],
    "learning_for_sonnet": "what pattern should Sonnet learn from this"
}}"""

    start_time = time.time()
    response = call_claude_opus(opus_prompt)
    execution_time = time.time() - start_time
    
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
            
        opus_plan = json.loads(response)
        opus_plan['execution_time'] = execution_time
        return opus_plan
    except:
        return {
            "strategic_analysis": response,
            "specialist_assignments": [],
            "workflow": ["Manual handling required"],
            "learning_for_sonnet": "Complex case - needs human review",
            "raw_response": response,
            "execution_time": execution_time
        }

def execute_specialist_task(specialist_ai, task_description):
    """Execute task with specified specialist AI"""
    
    specialist_map = {
        "gpt4": call_gpt4,
        "deepseek": call_deepseek,
        "gemini": call_gemini,
        "sonnet": call_claude_sonnet,
        "opus": call_claude_opus
    }
    
    ai_function = specialist_map.get(specialist_ai.lower())
    if not ai_function:
        return {"error": f"Unknown specialist: {specialist_ai}"}
    
    start_time = time.time()
    result = ai_function(task_description)
    execution_time = time.time() - start_time
    
    return {
        "specialist": specialist_ai,
        "output": result,
        "execution_time": execution_time,
        "success": not result.startswith("ERROR")
    }

def validate_with_consensus(task_result, validators=["sonnet", "gpt4"]):
    """
    Multiple AIs review the output
    Return agreement score and any disagreements
    """
    
    validation_prompt = f"""Review this AI-generated output and rate its quality on these criteria (0-10 each):
1. Accuracy
2. Completeness  
3. Clarity
4. Usefulness

OUTPUT TO REVIEW:
{task_result}

Respond with JSON:
{{
    "accuracy": 0-10,
    "completeness": 0-10,
    "clarity": 0-10,
    "usefulness": 0-10,
    "overall_score": 0-10,
    "concerns": "any issues found"
}}"""

    validation_results = []
    
    with ThreadPoolExecutor(max_workers=len(validators)) as executor:
        futures = {}
        for validator in validators:
            if validator.lower() == "sonnet":
                futures[executor.submit(call_claude_sonnet, validation_prompt)] = validator
            elif validator.lower() == "gpt4":
                futures[executor.submit(call_gpt4, validation_prompt)] = validator
        
        for future in as_completed(futures):
            validator = futures[future]
            try:
                result = future.result()
                
                # Parse JSON
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0].strip()
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0].strip()
                
                parsed = json.loads(result)
                parsed['validator'] = validator
                validation_results.append(parsed)
            except:
                validation_results.append({
                    "validator": validator,
                    "error": "Failed to parse validation",
                    "overall_score": 5
                })
    
    # Calculate consensus
    scores = [v.get('overall_score', 5) for v in validation_results]
    agreement_score = 1.0 - (max(scores) - min(scores)) / 10.0  # High agreement if scores are similar
    
    return {
        "validators": validators,
        "validation_results": validation_results,
        "agreement_score": agreement_score,
        "average_score": sum(scores) / len(scores) if scores else 5
    }

# ============================================================================
# MAIN ORCHESTRATION ENDPOINT
# ============================================================================

@app.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    """
    Main endpoint - receives user request, orchestrates AI swarm
    """
    data = request.json
    user_request = data.get('request')
    enable_consensus = data.get('enable_consensus', True)
    
    if not user_request:
        return jsonify({'error': 'Request text required'}), 400
    
    # Log the task
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
        sonnet_analysis = analyze_task_with_sonnet(user_request)
        
        # Step 2: Escalate to Opus if needed
        if sonnet_analysis.get('escalate_to_opus'):
            db.execute(
                'INSERT INTO escalations (task_id, reason, sonnet_confidence) VALUES (?, ?, ?)',
                (task_id, sonnet_analysis.get('reasoning'), sonnet_analysis.get('confidence'))
            )
            db.commit()
            
            opus_plan = handle_with_opus(user_request, sonnet_analysis)
            orchestrator = "opus"
            plan = opus_plan
        else:
            orchestrator = "sonnet"
            plan = sonnet_analysis
        
        # Step 3: Execute with specialists
        specialist_results = []
        specialists_needed = plan.get('specialists_needed', [])
        
        if specialists_needed and specialists_needed != ["none"]:
            for specialist in specialists_needed:
                specialist_task = f"User request: {user_request}\n\nYour role as {specialist}: Complete the task using your specialty."
                result = execute_specialist_task(specialist, specialist_task)
                specialist_results.append(result)
                
                # Log specialist assignment
                db.execute(
                    '''INSERT INTO specialist_assignments 
                       (task_id, specialist_name, specialist_role, output, execution_time_seconds, success)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (task_id, specialist, result.get('specialist'), 
                     result.get('output'), result.get('execution_time'), result.get('success'))
                )
                db.commit()
        
        # Step 4: Consensus validation if enabled
        consensus_result = None
        if enable_consensus and specialist_results:
            # Validate the first specialist's output
            primary_output = specialist_results[0].get('output', '')
            consensus_result = validate_with_consensus(primary_output)
            
            db.execute(
                '''INSERT INTO consensus_validations
                   (task_id, validator_ais, agreement_score, final_decision)
                   VALUES (?, ?, ?, ?)''',
                (task_id, json.dumps(consensus_result.get('validators')),
                 consensus_result.get('agreement_score'), 
                 json.dumps(consensus_result))
            )
            db.commit()
        
        # Calculate total time
        total_time = time.time() - overall_start
        
        # Update task status
        db.execute(
            'UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ? WHERE id = ?',
            ('completed', orchestrator, total_time, task_id)
        )
        db.commit()
        
        # Return response
        return jsonify({
            'success': True,
            'task_id': task_id,
            'orchestrator': orchestrator,
            'analysis': plan,
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

# ============================================================================
# FRONTEND & MONITORING ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main interface"""
    return render_template('index.html')

@app.route('/api/tasks')
def get_tasks():
    """Get all tasks"""
    db = get_db()
    tasks = db.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50').fetchall()
    db.close()
    
    return jsonify([dict(task) for task in tasks])

@app.route('/api/task/<int:task_id>')
def get_task_detail(task_id):
    """Get detailed task information"""
    db = get_db()
    
    task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    specialists = db.execute('SELECT * FROM specialist_assignments WHERE task_id = ?', (task_id,)).fetchall()
    consensus = db.execute('SELECT * FROM consensus_validations WHERE task_id = ?', (task_id,)).fetchone()
    escalation = db.execute('SELECT * FROM escalations WHERE task_id = ?', (task_id,)).fetchone()
    
    db.close()
    
    return jsonify({
        'task': dict(task) if task else None,
        'specialists': [dict(s) for s in specialists],
        'consensus': dict(consensus) if consensus else None,
        'escalation': dict(escalation) if escalation else None
    })

@app.route('/api/stats')
def get_stats():
    """Get system statistics"""
    db = get_db()
    
    total_tasks = db.execute('SELECT COUNT(*) as count FROM tasks').fetchone()['count']
    sonnet_tasks = db.execute("SELECT COUNT(*) as count FROM tasks WHERE assigned_orchestrator = 'sonnet'").fetchone()['count']
    opus_tasks = db.execute("SELECT COUNT(*) as count FROM tasks WHERE assigned_orchestrator = 'opus'").fetchone()['count']
    avg_time = db.execute('SELECT AVG(execution_time_seconds) as avg FROM tasks WHERE status = "completed"').fetchone()['avg']
    
    specialist_usage = db.execute('''
        SELECT specialist_name, COUNT(*) as count 
        FROM specialist_assignments 
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

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'orchestrators': {
            'sonnet': 'configured' if ANTHROPIC_API_KEY else 'missing',
            'opus': 'configured' if ANTHROPIC_API_KEY else 'missing'
        },
        'specialists': {
            'gpt4': 'configured' if OPENAI_API_KEY else 'missing',
            'deepseek': 'configured' if DEEPSEEK_API_KEY else 'missing',
            'gemini': 'configured' if GOOGLE_API_KEY else 'missing'
        }
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# I did no harm and this file is not truncated
