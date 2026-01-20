"""
AI SWARM ORCHESTRATOR - Main Application with OUTPUT FORMATTING ENFORCEMENT
Created: January 18, 2026
Last Updated: January 19, 2026

CHANGES IN THIS VERSION:
- January 19, 2026: ADDED OUTPUT FORMATTING ENFORCEMENT
  * Automatically detects terrible text dumps with asterisks/markdown
  * Forces clean, professional formatting on ALL outputs
  * Converts schedule dumps into proper formatted tables
  * Adds strict formatting requirements to AI prompts
  * Prevents walls of text from reaching users

- January 19, 2026: INTEGRATED ENTIRE PROJECT KNOWLEDGE BASE
  * All Shiftwork Solutions documents now accessible to swarm
  * Automatic context injection from 30+ years of expertise
  * Smart search across Implementation Manuals, templates, guides
  * Real-time knowledge retrieval during task execution
  * New /api/knowledge endpoints for knowledge base management

- January 19, 2026: Fixed Anthropic API timeout issues (extended to 180 seconds)
- January 19, 2026: Added proper timeout configuration for long-running AI operations

PURPOSE:
Intelligent AI orchestration system that routes tasks to specialist AIs,
validates through consensus, learns from outcomes, leverages your
complete Shiftwork Solutions knowledge base, and ENFORCES PROFESSIONAL OUTPUT.

ARCHITECTURE:
- Sonnet (Primary Orchestrator): Fast routing for 90% of tasks + PROJECT KNOWLEDGE ACCESS
- Opus (Strategic Supervisor): Deep analysis for 10% complex tasks + PROJECT KNOWLEDGE ACCESS
- Specialist AIs: GPT-4 (design), DeepSeek (code), Gemini (multimodal)
- Consensus Engine: Multi-AI validation
- Learning Layer: Improves over time
- Knowledge Base: 20+ documents from /mnt/project automatically indexed and searchable
- OUTPUT FORMATTER: Enforces professional standards, NO text dumps allowed

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

# Import our knowledge integration module
from knowledge_integration import get_knowledge_base

# Import formatting enhancement module (optional)
try:
    from formatting_enhancement import format_with_gpt4, detect_output_type, needs_formatting
    FORMATTING_AVAILABLE = True
except ImportError:
    print("⚠️ Warning: formatting_enhancement module not found - formatting features disabled")
    FORMATTING_AVAILABLE = False

# Import project workflow module (optional)
try:
    from project_workflow import ProjectWorkflow, detect_project_intent, create_project_aware_prompt
    WORKFLOW_AVAILABLE = True
except ImportError:
    print("⚠️ Warning: project_workflow module not found - workflow features disabled")
    WORKFLOW_AVAILABLE = False

# Import document generator module (optional)
try:
    from document_generator import get_document_generator
    DOCUMENT_GENERATOR_AVAILABLE = True
except ImportError:
    print("⚠️ Warning: document_generator module not found - will return text only")
    DOCUMENT_GENERATOR_AVAILABLE = False

# Import output formatter module (CRITICAL - ENFORCES PROFESSIONAL OUTPUT)
try:
    from output_formatter import get_output_formatter
    OUTPUT_FORMATTER_AVAILABLE = True
    print("✅ Output formatter loaded - will enforce professional formatting")
except ImportError:
    print("⚠️ Warning: output_formatter module not found - may produce terrible text dumps")
    OUTPUT_FORMATTER_AVAILABLE = False

# Import Microsoft 365 integration (PROFESSIONAL DOCUMENTS)
try:
    from microsoft365_integration import get_ms365
    MS365_AVAILABLE = True
    ms365 = get_ms365()
    if ms365.is_configured:
        print("✅ Microsoft 365 integrated - will create professional Office documents")
    else:
        print("⚠️ Microsoft 365 not configured - set MS365_CLIENT_ID, MS365_CLIENT_SECRET, MS365_TENANT_ID")
        MS365_AVAILABLE = False
except ImportError:
    print("⚠️ Warning: microsoft365_integration module not found")
    MS365_AVAILABLE = False

# Import Marketing Hub (SOCIAL MEDIA & RESEARCH)
try:
    from marketing_hub import get_marketing_hub
    MARKETING_AVAILABLE = True
    marketing = get_marketing_hub()
    print(f"✅ Marketing Hub loaded - {sum(marketing.platforms_configured.values())}/3 platforms configured")
except ImportError:
    print("⚠️ Warning: marketing_hub module not found")
    MARKETING_AVAILABLE = False

# Import Cost Calculator (OVERTIME ANALYSIS)
try:
    from cost_calculator import get_calculator
    CALCULATOR_AVAILABLE = True
    calculator = get_calculator()
    print("✅ Cost Calculator loaded - overtime and schedule cost analysis ready")
except ImportError:
    print("⚠️ Warning: cost_calculator module not found")
    CALCULATOR_AVAILABLE = False

# Import Survey Builder (EMPLOYEE SURVEYS)
try:
    from survey_builder import get_survey_builder
    SURVEY_AVAILABLE = True
    survey_builder = get_survey_builder()
    print(f"✅ Survey Builder loaded - {len(survey_builder.question_bank)} questions available")
except ImportError:
    print("⚠️ Warning: survey_builder module not found")
    SURVEY_AVAILABLE = False

# Import Proactive Intelligence (SHOWS INITIATIVE)
try:
    from proactive_intelligence import get_proactive_intelligence
    PROACTIVE_AVAILABLE = True
    proactive_ai = get_proactive_intelligence()
    print("✅ Proactive Intelligence loaded - AI will show initiative and suggest next steps")
except ImportError:
    print("⚠️ Warning: proactive_intelligence module not found")
    PROACTIVE_AVAILABLE = False

# Import Marketing Initiative (CREATIVE BUSINESS PARTNER)
try:
    from marketing_initiative import get_marketing_initiative
    MARKETING_INITIATIVE_AVAILABLE = True
    marketing_ideas = get_marketing_initiative()
    print("✅ Marketing Initiative loaded - AI will proactively suggest business ideas")
except ImportError:
    print("⚠️ Warning: marketing_initiative module not found")
    MARKETING_INITIATIVE_AVAILABLE = False

app = Flask(__name__)

# Global workflow storage (in production, use database or session storage)
active_workflows = {}

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
# DATABASE SETUP (UNCHANGED)
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
            execution_time_seconds REAL,
            knowledge_used BOOLEAN DEFAULT 0,
            knowledge_sources TEXT
        )
    ''')
    
    # Projects table - persistent project storage (NEW)
    db.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            client_name TEXT,
            industry TEXT,
            facility_type TEXT,
            project_phase TEXT DEFAULT 'initial',
            context_data TEXT,
            uploaded_files TEXT,
            email_context TEXT,
            key_findings TEXT,
            schedules_proposed TEXT,
            status TEXT DEFAULT 'active'
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
    
    # User feedback - capture user ratings and learning data
    db.execute('''
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            overall_rating INTEGER CHECK(overall_rating >= 1 AND overall_rating <= 5),
            quality_rating INTEGER CHECK(quality_rating >= 1 AND quality_rating <= 5),
            accuracy_rating INTEGER CHECK(accuracy_rating >= 1 AND overall_rating <= 5),
            usefulness_rating INTEGER CHECK(usefulness_rating >= 1 AND usefulness_rating <= 5),
            consensus_was_accurate BOOLEAN,
            improvement_categories TEXT,
            user_comment TEXT,
            output_used BOOLEAN,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    ''')
    
    db.commit()
    db.close()

# Initialize database on startup
init_db()

# Helper functions for project persistence
def load_project_from_db(project_id):
    """Load project from database"""
    if not WORKFLOW_AVAILABLE:
        return None
    
    db = get_db()
    project_row = db.execute(
        'SELECT * FROM projects WHERE project_id = ? AND status = "active"',
        (project_id,)
    ).fetchone()
    db.close()
    
    if not project_row:
        return None
    
    workflow = ProjectWorkflow()
    workflow.project_id = project_row['project_id']
    workflow.client_name = project_row['client_name']
    workflow.industry = project_row['industry']
    workflow.facility_type = project_row['facility_type']
    workflow.project_phase = project_row['project_phase']
    
    # Load JSON data
    if project_row['context_data']:
        workflow.context_history = json.loads(project_row['context_data'])
    if project_row['uploaded_files']:
        workflow.uploaded_files = json.loads(project_row['uploaded_files'])
    if project_row['email_context']:
        workflow.email_context = json.loads(project_row['email_context'])
    if project_row['key_findings']:
        workflow.key_findings = json.loads(project_row['key_findings'])
    if project_row['schedules_proposed']:
        workflow.schedules_proposed = json.loads(project_row['schedules_proposed'])
    
    return workflow

def save_project_to_db(workflow):
    """Save project to database"""
    if not workflow:
        return
    
    db = get_db()
    
    # Check if project exists
    existing = db.execute(
        'SELECT id FROM projects WHERE project_id = ?',
        (workflow.project_id,)
    ).fetchone()
    
    if existing:
        # Update existing
        db.execute('''
            UPDATE projects SET
                updated_at = CURRENT_TIMESTAMP,
                client_name = ?,
                industry = ?,
                facility_type = ?,
                project_phase = ?,
                context_data = ?,
                uploaded_files = ?,
                email_context = ?,
                key_findings = ?,
                schedules_proposed = ?
            WHERE project_id = ?
        ''', (
            workflow.client_name,
            workflow.industry,
            workflow.facility_type,
            workflow.project_phase,
            json.dumps(workflow.context_history),
            json.dumps(workflow.uploaded_files),
            json.dumps(workflow.email_context),
            json.dumps(workflow.key_findings),
            json.dumps(workflow.schedules_proposed),
            workflow.project_id
        ))
    else:
        # Insert new
        db.execute('''
            INSERT INTO projects (
                project_id, client_name, industry, facility_type, 
                project_phase, context_data, uploaded_files, email_context,
                key_findings, schedules_proposed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            workflow.project_id,
            workflow.client_name,
            workflow.industry,
            workflow.facility_type,
            workflow.project_phase,
            json.dumps(workflow.context_history),
            json.dumps(workflow.uploaded_files),
            json.dumps(workflow.email_context),
            json.dumps(workflow.key_findings),
            json.dumps(workflow.schedules_proposed)
        ))
    
    db.commit()
    db.close()

# Initialize database on startup
init_db()

# Initialize project knowledge base on startup
print("🔍 Initializing Project Knowledge Base...")
knowledge_base = None
try:
    # Check if path exists first
    import os
    from pathlib import Path
    
    project_paths = ["/mnt/project", "project_files", "./project_files"]
    found_path = None
    
    for path in project_paths:
        if Path(path).exists():
            found_path = path
            file_count = len(list(Path(path).iterdir())) if Path(path).is_dir() else 0
            print(f"  📁 Found directory: {path} ({file_count} files)")
            break
    
    if not found_path:
        print(f"  ⚠️ No project files found. Checked: {project_paths}")
        print(f"  ℹ️  Knowledge base features disabled until files are added")
    else:
        knowledge_base = get_knowledge_base()
        print(f"  ✅ Knowledge Base Ready: {len(knowledge_base.knowledge_index)} documents indexed")
        
except Exception as e:
    print(f"  ⚠️ Warning: Knowledge Base initialization failed: {e}")
    import traceback
    print(f"  📋 Full error: {traceback.format_exc()}")
    knowledge_base = None

# ============================================================================
# AI CLIENT FUNCTIONS WITH FORMATTING REQUIREMENTS
# ============================================================================

# FORMATTING ENFORCEMENT PROMPT (CRITICAL - PREVENTS TEXT DUMPS)
FORMATTING_REQUIREMENTS = """
CRITICAL OUTPUT FORMATTING REQUIREMENTS:
1. NEVER use markdown symbols (**bold**, *italic*, ###headers) in your final output
2. For schedules: Use clean tables or structured lists, NOT walls of text
3. NO consecutive capital letters spanning more than 10 characters
4. Use proper section breaks (blank lines) between topics
5. If creating a schedule, present it in a clear, readable format:
   - Use section headers like "ROTATION PATTERN:" or "TIME OFF SCHEDULE:"
   - List weeks clearly: "Week 1: Work 7 days" (not **Week 1:** Work 7 days)
   - Use dash lines (----) to separate sections
6. Maximum line length: 100 characters (wrap longer content)
7. For professional consulting outputs, use clean prose without formatting symbols

YOUR OUTPUT WILL BE CHECKED. If it contains excessive markdown, walls of text, or
poor formatting, it will be automatically reformatted, which wastes processing time.

Format your response professionally from the start.
"""

def call_claude_sonnet(prompt, max_tokens=4000):
    """Call Claude Sonnet with FORMATTING REQUIREMENTS"""
    if not ANTHROPIC_API_KEY:
        return "ERROR: Anthropic API key not configured"
    
    # Add formatting requirements to prompt
    enhanced_prompt = f"{prompt}\n\n{FORMATTING_REQUIREMENTS}"
    
    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': enhanced_prompt}]
            },
            timeout=180
        )
        
        if response.status_code == 200:
            return response.json()['content'][0]['text']
        else:
            return f"ERROR: Sonnet API returned {response.status_code}: {response.text}"
            
    except requests.exceptions.Timeout:
        return "ERROR: Sonnet API timeout after 180 seconds"
    except Exception as e:
        return f"ERROR: Sonnet API call failed: {str(e)}"

def call_claude_opus(prompt, max_tokens=4000):
    """Call Claude Opus with FORMATTING REQUIREMENTS"""
    if not ANTHROPIC_API_KEY:
        return "ERROR: Anthropic API key not configured"
    
    # Add formatting requirements to prompt
    enhanced_prompt = f"{prompt}\n\n{FORMATTING_REQUIREMENTS}"
    
    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-opus-4-20250514',
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': enhanced_prompt}]
            },
            timeout=180
        )
        
        if response.status_code == 200:
            return response.json()['content'][0]['text']
        else:
            return f"ERROR: Opus API returned {response.status_code}: {response.text}"
            
    except requests.exceptions.Timeout:
        return "ERROR: Opus API timeout after 180 seconds"
    except Exception as e:
        return f"ERROR: Opus API call failed: {str(e)}"

def call_gpt4(prompt, max_tokens=4000):
    """Call GPT-4 (Design & Content Specialist)"""
    if not openai_client:
        return "ERROR: OpenAI API not configured"
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            timeout=120
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: GPT-4 call failed: {str(e)}"

def call_deepseek(prompt, max_tokens=4000):
    """Call DeepSeek (Code Specialist)"""
    if not deepseek_client:
        return "ERROR: DeepSeek API not configured"
    
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            timeout=120
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"ERROR: DeepSeek call failed: {str(e)}"

def call_gemini(prompt, max_tokens=4000):
    """Call Google Gemini (Multimodal Specialist)"""
    if not GOOGLE_API_KEY:
        return "ERROR: Google API not configured"
    
    try:
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GOOGLE_API_KEY}',
            json={
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'maxOutputTokens': max_tokens}
            },
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"ERROR: Gemini API returned {response.status_code}"
            
    except Exception as e:
        return f"ERROR: Gemini call failed: {str(e)}"

# ============================================================================
# ORCHESTRATION LOGIC (KEEPS EXISTING IMPLEMENTATION)
# ============================================================================

def get_learning_context():
    """Retrieve learning patterns to inform orchestration decisions"""
    db = get_db()
    
    # Get recent patterns
    patterns = db.execute('''
        SELECT pattern_type, success_rate, times_applied, pattern_data
        FROM learning_records
        WHERE times_applied >= 2
        ORDER BY success_rate DESC
        LIMIT 10
    ''').fetchall()
    
    db.close()
    
    if not patterns:
        return ""
        
    context = "\n\n=== LEARNING FROM PAST TASKS ===\n"
    context += "Your system has learned these patterns:\n\n"
    
    for p in patterns:
        pattern_data = json.loads(p['pattern_data'])
        context += f"- {p['pattern_type']}: {p['success_rate']*100:.0f}% success rate ({p['times_applied']} times)\n"
        if 'improvement_areas' in pattern_data and pattern_data['improvement_areas']:
            context += f"  Common issues: {', '.join(pattern_data['improvement_areas'])}\n"
    
    return context

def analyze_task_with_sonnet(user_request):
    """
    Sonnet analyzes the task WITH PROJECT KNOWLEDGE
    Returns decision: orchestrator, specialists, escalation
    """
    
    # Get learning context
    learning_context = get_learning_context()
    
    # GET RELEVANT KNOWLEDGE FROM PROJECT BASE
    knowledge_context = ""
    knowledge_sources = []
    
    if knowledge_base:
        try:
            knowledge_context = knowledge_base.get_context_for_task(user_request, max_context=3000)
            if knowledge_context:
                # Extract sources for tracking
                search_results = knowledge_base.search(user_request, max_results=3)
                knowledge_sources = [r['filename'] for r in search_results]
        except Exception as e:
            print(f"⚠️ Knowledge retrieval error: {e}")
    
    analysis_prompt = f"""You are the primary orchestrator in an AI swarm system for Shiftwork Solutions LLC.

{learning_context}

{knowledge_context}

USER REQUEST: {user_request}

Analyze this request with the benefit of Shiftwork Solutions' 30+ years of expertise above.

Determine:
1. Task type (strategy, schedule_design, implementation, survey, content, code, analysis, complex)
2. Your confidence in handling this (0.0-1.0)
3. Required specialists (gpt4, deepseek, gemini, or "none")
4. Should this be escalated to Opus? (true/false)
5. Reasoning

Respond ONLY with valid JSON:
{{
    "task_type": "string",
    "confidence": 0.0-1.0,
    "specialists_needed": ["ai_name", ...],
    "escalate_to_opus": boolean,
    "reasoning": "string",
    "knowledge_applied": boolean
}}"""

    start_time = time.time()
    response = call_claude_sonnet(analysis_prompt)
    execution_time = time.time() - start_time
    
    # Parse JSON response
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
            
        analysis = json.loads(response)
        analysis['execution_time'] = execution_time
        analysis['knowledge_sources'] = knowledge_sources
        return analysis
    except:
        return {
            "task_type": "unknown",
            "confidence": 0.5,
            "specialists_needed": [],
            "escalate_to_opus": True,
            "reasoning": "Failed to parse Sonnet response, escalating to Opus",
            "raw_response": response,
            "execution_time": execution_time,
            "knowledge_sources": knowledge_sources,
            "knowledge_applied": bool(knowledge_context)
        }

def handle_with_opus(user_request, sonnet_analysis):
    """
    Opus handles complex/novel situations WITH PROJECT KNOWLEDGE
    Returns strategic plan with specialist assignments
    """
    
    # GET RELEVANT KNOWLEDGE FROM PROJECT BASE
    knowledge_context = ""
    if knowledge_base:
        try:
            knowledge_context = knowledge_base.get_context_for_task(user_request, max_context=4000)
        except Exception as e:
            print(f"⚠️ Knowledge retrieval error: {e}")
    
    opus_prompt = f"""You are the strategic supervisor in an AI swarm system for Shiftwork Solutions LLC.

{knowledge_context}

Sonnet (primary orchestrator) has escalated this request to you.

USER REQUEST: {user_request}

SONNET'S ANALYSIS:
{json.dumps(sonnet_analysis, indent=2)}

With access to Shiftwork Solutions' expertise above, provide a strategic response with:
1. Deep analysis of the request
2. Specialist assignments (which AIs should do what)
3. Expected workflow
4. Any new patterns Sonnet should learn
5. How to apply the company's methodology

Respond in JSON format:
{{
    "strategic_analysis": "string",
    "specialist_assignments": [
        {{"ai": "name", "task": "description", "reason": "why this AI"}}
    ],
    "workflow": ["step1", "step2", ...],
    "learning_for_sonnet": "what pattern should Sonnet learn from this",
    "methodology_applied": "which Shiftwork Solutions principles apply"
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
        opus_plan['knowledge_applied'] = bool(knowledge_context)
        return opus_plan
    except:
        return {
            "strategic_analysis": response,
            "specialist_assignments": [],
            "workflow": ["Manual handling required"],
            "learning_for_sonnet": "Complex case - needs human review",
            "raw_response": response,
            "execution_time": execution_time,
            "knowledge_applied": bool(knowledge_context)
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

def validate_with_consensus(task_result, validators=None):
    """
    Multiple AIs review the output
    Returns agreement score and any disagreements
    Auto-detects available validators
    """
    
    if validators is None:
        validators = []
        validators.append("sonnet")
        if OPENAI_API_KEY:
            validators.append("gpt4")
        if len(validators) == 1:
            validators = ["sonnet"]
    
    validation_prompt = f"""Review this AI-generated output and rate its quality on these criteria (0-10 each):
1. Accuracy
2. Completeness  
3. Clarity
4. Usefulness

OUTPUT TO REVIEW:
{task_result[:2000]}

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
                futures[executor.submit(call_claude_sonnet, validation_prompt, 1000)] = validator
            elif validator.lower() == "gpt4" and OPENAI_API_KEY:
                futures[executor.submit(call_gpt4, validation_prompt, 1000)] = validator
        
        for future in as_completed(futures):
            validator = futures[future]
            try:
                result = future.result()
                
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0].strip()
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0].strip()
                
                parsed = json.loads(result)
                parsed['validator'] = validator
                validation_results.append(parsed)
            except Exception as e:
                validation_results.append({
                    "validator": validator,
                    "error": f"Failed to parse: {str(e)[:100]}",
                    "overall_score": 5
                })
    
    scores = [v.get('overall_score', 5) for v in validation_results]
    
    if len(scores) == 1:
        agreement_score = 1.0
    else:
        agreement_score = 1.0 - (max(scores) - min(scores)) / 10.0
    
    return {
        "validators": validators,
        "validation_results": validation_results,
        "agreement_score": agreement_score,
        "average_score": sum(scores) / len(scores) if scores else 5,
        "validator_count": len(validation_results)
    }

# ============================================================================
# PROJECT WORKFLOW ENDPOINTS (UNCHANGED - KEEPING EXISTING)
# ============================================================================

@app.route('/api/projects', methods=['GET'])
def list_projects():
    """List all active projects"""
    db = get_db()
    
    projects = db.execute('''
        SELECT project_id, client_name, industry, facility_type, 
               project_phase, created_at, updated_at
        FROM projects 
        WHERE status = 'active'
        ORDER BY updated_at DESC
    ''').fetchall()
    
    db.close()
    
    return jsonify({
        'success': True,
        'projects': [dict(p) for p in projects],
        'total_count': len(projects)
    })


# ==================== MARKETING HUB ENDPOINTS ====================

@app.route('/api/marketing/status', methods=['GET'])
def marketing_status():
    """Get marketing platform configuration status"""
    if not MARKETING_AVAILABLE:
        return jsonify({'error': 'Marketing Hub not available'}), 503
    
    status = marketing.get_status()
    return jsonify(status)

@app.route('/api/marketing/post', methods=['POST'])
def marketing_post():
    """Post to social media platforms"""
    if not MARKETING_AVAILABLE:
        return jsonify({'error': 'Marketing Hub not available'}), 503
    
    data = request.json
    content = data.get('content')
    platform = data.get('platform', 'linkedin')
    
    if not content:
        return jsonify({'error': 'Content required'}), 400
    
    if platform == 'linkedin':
        result = marketing.post_to_linkedin(content)
    else:
        result = {'success': False, 'error': f'Platform {platform} not yet implemented'}
    
    return jsonify(result)

@app.route('/api/marketing/research', methods=['POST'])
def marketing_research():
    """Conduct market research"""
    if not MARKETING_AVAILABLE:
        return jsonify({'error': 'Marketing Hub not available'}), 503
    
    data = request.json
    topic = data.get('topic')
    
    if not topic:
        return jsonify({'error': 'Research topic required'}), 400
    
    # Use Claude Sonnet for research
    result = marketing.conduct_market_research(topic, call_claude_sonnet)
    
    return jsonify(result)

@app.route('/api/marketing/generate', methods=['POST'])
def marketing_generate_content():
    """Generate platform-optimized content"""
    if not MARKETING_AVAILABLE:
        return jsonify({'error': 'Marketing Hub not available'}), 503
    
    data = request.json
    topic = data.get('topic')
    platform = data.get('platform', 'linkedin')
    
    if not topic:
        return jsonify({'error': 'Topic required'}), 400
    
    # Use Claude Sonnet for content generation
    result = marketing.generate_social_content(topic, platform, call_claude_sonnet)
    
    return jsonify(result)

@app.route('/api/marketing/idea', methods=['GET'])
def marketing_generate_idea():
    """Proactively generate a creative marketing idea - "Hey Jim, I have an idea!" """
    if not MARKETING_INITIATIVE_AVAILABLE:
        return jsonify({'error': 'Marketing Initiative not available'}), 503
    
    # Generate proactive marketing message
    message = marketing_ideas.generate_proactive_marketing_message()
    
    if message:
        return jsonify({
            'success': True,
            'has_idea': True,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
    else:
        return jsonify({
            'success': True,
            'has_idea': False,
            'message': '💤 No new ideas right now - I shared one recently. Check back in an hour!'
        })

@app.route('/api/marketing/content-idea', methods=['GET'])
def get_detailed_content_idea():
    """Get a specific content idea with full execution plan"""
    if not MARKETING_INITIATIVE_AVAILABLE:
        return jsonify({'error': 'Marketing Initiative not available'}), 503
    
    idea = marketing_ideas.generate_content_idea()
    
    return jsonify({'success': True, 'idea': idea})


# ==================== CALCULATOR ENDPOINTS ====================

@app.route('/api/calculator/overtime', methods=['POST'])
def calculate_overtime():
    """Calculate overtime costs"""
    if not CALCULATOR_AVAILABLE:
        return jsonify({'error': 'Calculator not available'}), 503
    
    data = request.json
    base_wage = data.get('base_wage')
    ot_hours_weekly = data.get('ot_hours_weekly')
    
    if not base_wage or not ot_hours_weekly:
        return jsonify({'error': 'base_wage and ot_hours_weekly required'}), 400
    
    result = calculator.calculate_overtime_cost(
        float(base_wage),
        float(ot_hours_weekly),
        weeks=data.get('weeks', 52),
        burden_rate=data.get('burden_rate')
    )
    
    return jsonify({'success': True, 'calculation': result})

@app.route('/api/calculator/hire-vs-ot', methods=['POST'])
def compare_hire_vs_ot():
    """Compare hiring vs continuing overtime"""
    if not CALCULATOR_AVAILABLE:
        return jsonify({'error': 'Calculator not available'}), 503
    
    data = request.json
    current_ot_cost = data.get('current_ot_cost')
    new_employee_wage = data.get('new_employee_wage')
    
    if not current_ot_cost or not new_employee_wage:
        return jsonify({'error': 'current_ot_cost and new_employee_wage required'}), 400
    
    result = calculator.compare_overtime_vs_hiring(
        float(current_ot_cost),
        float(new_employee_wage),
        training_cost=data.get('training_cost'),
        burden_rate=data.get('burden_rate')
    )
    
    return jsonify({'success': True, 'comparison': result})

@app.route('/api/calculator/report', methods=['POST'])
def generate_cost_report():
    """Generate cost analysis report"""
    if not CALCULATOR_AVAILABLE:
        return jsonify({'error': 'Calculator not available'}), 503
    
    data = request.json
    analysis_data = data.get('analysis_data')
    client_name = data.get('client_name')
    
    if not analysis_data:
        return jsonify({'error': 'analysis_data required'}), 400
    
    report = calculator.generate_cost_report(analysis_data, client_name)
    
    return jsonify({'success': True, 'report': report})


# ==================== SURVEY ENDPOINTS ====================

@app.route('/api/survey/create', methods=['POST'])
def create_survey():
    """Create a new survey"""
    if not SURVEY_AVAILABLE:
        return jsonify({'error': 'Survey Builder not available'}), 503
    
    data = request.json
    project_name = data.get('project_name')
    selected_questions = data.get('selected_questions')
    custom_questions = data.get('custom_questions')
    
    if not project_name:
        return jsonify({'error': 'project_name required'}), 400
    
    survey = survey_builder.create_survey(
        project_name,
        selected_questions=selected_questions,
        custom_questions=custom_questions
    )
    
    return jsonify({'success': True, 'survey': survey})

@app.route('/api/survey/<survey_id>', methods=['GET'])
def get_survey(survey_id):
    """Get survey by ID"""
    if not SURVEY_AVAILABLE:
        return jsonify({'error': 'Survey Builder not available'}), 503
    
    survey = survey_builder.get_survey(survey_id)
    
    if not survey:
        return jsonify({'error': 'Survey not found'}), 404
    
    return jsonify({'success': True, 'survey': survey})

@app.route('/api/survey/<survey_id>/respond', methods=['POST'])
def submit_survey_response(survey_id):
    """Submit a survey response"""
    if not SURVEY_AVAILABLE:
        return jsonify({'error': 'Survey Builder not available'}), 503
    
    data = request.json
    answers = data.get('answers')
    respondent_id = data.get('respondent_id')
    
    if not answers:
        return jsonify({'error': 'answers required'}), 400
    
    result = survey_builder.submit_response(survey_id, answers, respondent_id)
    
    return jsonify(result)

@app.route('/api/survey/<survey_id>/analyze', methods=['GET'])
def analyze_survey(survey_id):
    """Analyze survey responses"""
    if not SURVEY_AVAILABLE:
        return jsonify({'error': 'Survey Builder not available'}), 503
    
    analysis = survey_builder.analyze_responses(survey_id)
    
    return jsonify(analysis)

@app.route('/api/survey/<survey_id>/export', methods=['GET'])
def export_survey_data(survey_id):
    """Export survey data in Remark format"""
    if not SURVEY_AVAILABLE:
        return jsonify({'error': 'Survey Builder not available'}), 503
    
    csv_data = survey_builder.export_to_remark_format(survey_id)
    
    if not csv_data:
        return jsonify({'error': 'Survey not found'}), 404
    
    return jsonify({'success': True, 'csv_data': csv_data})

@app.route('/api/survey/questions', methods=['GET'])
def get_question_bank():
    """Get available questions from question bank"""
    if not SURVEY_AVAILABLE:
        return jsonify({'error': 'Survey Builder not available'}), 503
    
    questions = survey_builder.question_bank
    
    return jsonify({
        'success': True,
        'questions': questions,
        'total_count': len(questions)
    })


@app.route('/api/project/start', methods=['POST'])
def start_project():
    """Start a new project workflow with DATABASE PERSISTENCE"""
    data = request.json
    project_id = data.get('project_id') or f"proj_{int(time.time())}"
    
    workflow = ProjectWorkflow()
    workflow.project_id = project_id
    workflow.client_name = data.get('client_name', '')
    workflow.industry = data.get('industry', '')
    workflow.facility_type = data.get('facility_type', '')
    
    # Save to database
    save_project_to_db(workflow)
    
    workflow.add_context('project_started', f"New project for {workflow.client_name}")
    save_project_to_db(workflow)  # Save context update
    
    return jsonify({
        'success': True,
        'project_id': project_id,
        'message': f'Project workflow started for {workflow.client_name}',
        'suggested_first_step': 'Create a data collection document'
    })

@app.route('/api/project/<project_id>/context', methods=['GET'])
def get_project_context(project_id):
    """Get current project context from DATABASE"""
    workflow = load_project_from_db(project_id)
    
    if not workflow:
        return jsonify({'error': 'Project not found'}), 404
    
    return jsonify({
        'success': True,
        'project_id': project_id,
        'client_name': workflow.client_name,
        'phase': workflow.project_phase,
        'context_summary': workflow.get_context_summary(),
        'files_count': len(workflow.uploaded_files),
        'findings_count': len(workflow.key_findings)
    })

@app.route('/api/project/<project_id>/add_context', methods=['POST'])
def add_project_context(project_id):
    """Add context to an active project and SAVE TO DATABASE"""
    workflow = load_project_from_db(project_id)
    
    if not workflow:
        return jsonify({'error': 'Project not found'}), 404
    
    data = request.json
    context_type = data.get('type')  # 'file', 'email', 'finding', 'schedule', 'note'
    content = data.get('content')
    
    if context_type == 'file':
        workflow.uploaded_files.append(content)
    elif context_type == 'email':
        workflow.email_context.append(content)
    elif context_type == 'finding':
        workflow.key_findings.append(content)
    elif context_type == 'schedule':
        workflow.schedules_proposed.append(content)
    
    workflow.add_context(context_type, content)
    
    # Save to database
    save_project_to_db(workflow)
    
    return jsonify({
        'success': True,
        'message': f'Added {context_type} to project context'
    })

@app.route('/api/project/<project_id>/phase', methods=['POST'])
def update_project_phase(project_id):
    """Move project to next phase and SAVE TO DATABASE"""
    workflow = load_project_from_db(project_id)
    
    if not workflow:
        return jsonify({'error': 'Project not found'}), 404
    
    data = request.json
    new_phase = data.get('phase')
    
    old_phase = workflow.project_phase
    workflow.project_phase = new_phase
    workflow.add_context('phase_change', f"Moved from {old_phase} to {new_phase}")
    
    # Save to database
    save_project_to_db(workflow)
    
    return jsonify({
        'success': True,
        'old_phase': old_phase,
        'new_phase': new_phase,
        'message': f'Project moved to {new_phase} phase'
    })

# ============================================================================
# MAIN ORCHESTRATION ENDPOINT WITH OUTPUT FORMATTING ENFORCEMENT
# ============================================================================

@app.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    """Main endpoint with OUTPUT FORMATTING ENFORCEMENT and FILE UPLOAD SUPPORT"""
    
    # Handle both JSON and FormData requests
    if request.is_json:
        data = request.json
        user_request = data.get('request')
        enable_consensus = data.get('enable_consensus', True)
        project_id = data.get('project_id')
        uploaded_files = []
    else:
        # FormData (with file uploads)
        user_request = request.form.get('request')
        enable_consensus = request.form.get('enable_consensus', 'true').lower() == 'true'
        project_id = request.form.get('project_id')
        uploaded_files = request.files.getlist('files')
    
    if not user_request:
        return jsonify({'error': 'Request text required'}), 400
    
    # Process uploaded files
    file_context = ""
    file_names = []
    
    if uploaded_files:
        file_context = "\n\n=== UPLOADED FILES ===\n"
        for file in uploaded_files:
            if file.filename:
                file_names.append(file.filename)
                
                # Save file temporarily
                import tempfile
                temp_dir = tempfile.mkdtemp()
                file_path = os.path.join(temp_dir, file.filename)
                file.save(file_path)
                
                # Extract text based on file type
                file_ext = file.filename.split('.')[-1].lower()
                
                if file_ext in ['txt', 'csv']:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()[:5000]  # First 5000 chars
                        file_context += f"\n--- {file.filename} ---\n{content}\n"
                
                elif file_ext in ['pdf']:
                    try:
                        import PyPDF2
                        with open(file_path, 'rb') as f:
                            pdf = PyPDF2.PdfReader(f)
                            text = ""
                            for page in pdf.pages[:5]:  # First 5 pages
                                text += page.extract_text()
                            file_context += f"\n--- {file.filename} ---\n{text[:5000]}\n"
                    except Exception as e:
                        file_context += f"\n--- {file.filename} ---\n[Error reading PDF: {e}]\n"
                
                elif file_ext in ['docx']:
                    try:
                        import docx
                        doc = docx.Document(file_path)
                        text = "\n".join([p.text for p in doc.paragraphs])
                        file_context += f"\n--- {file.filename} ---\n{text[:5000]}\n"
                    except Exception as e:
                        file_context += f"\n--- {file.filename} ---\n[Error reading DOCX: {e}]\n"
                
                elif file_ext in ['xlsx', 'xls']:
                    try:
                        import openpyxl
                        wb = openpyxl.load_workbook(file_path)
                        text = ""
                        for sheet in wb.worksheets[:3]:  # First 3 sheets
                            text += f"\n--- Sheet: {sheet.title} ---\n"
                            for row in list(sheet.rows)[:50]:  # First 50 rows
                                text += " | ".join([str(cell.value) if cell.value else "" for cell in row]) + "\n"
                        file_context += f"\n--- {file.filename} ---\n{text[:5000]}\n"
                    except Exception as e:
                        file_context += f"\n--- {file.filename} ---\n[Error reading Excel: {e}]\n"
                
                else:
                    file_context += f"\n--- {file.filename} ---\n[File type not supported for text extraction]\n"
        
        file_context += "\n=== END OF FILES ===\n"
        
        # Append file context to user request
        user_request = f"{user_request}\n{file_context}"
    
    # Get project workflow if specified - LOAD FROM DATABASE
    workflow = None
    intent = 'general_question'
    intent_params = {}
    
    if project_id and WORKFLOW_AVAILABLE:
        workflow = load_project_from_db(project_id)
        if workflow:
            intent, intent_params = detect_project_intent(user_request, workflow)
    
    # PROACTIVE INTELLIGENCE - Analyze context and show initiative
    proactive_analysis = None
    if PROACTIVE_AVAILABLE:
        project_context = None
        if workflow:
            project_context = {
                'project_phase': workflow.project_phase,
                'uploaded_files': workflow.uploaded_files,
                'key_findings': workflow.key_findings,
                'schedules_proposed': workflow.schedules_proposed
            }
        
        proactive_analysis = proactive_ai.analyze_context(
            user_request,
            project_context=project_context,
            conversation_history=None  # Could add conversation tracking
        )
        
        # If proactive AI has critical suggestions, prepend to response
        if proactive_analysis and proactive_analysis.get('has_suggestions'):
            print(f"  🎯 Proactive Intelligence activated:")
            for suggestion in proactive_analysis.get('suggestions', [])[:2]:
                print(f"     • {suggestion.get('type')}: {suggestion.get('suggestion')[:80]}...")
            
            # Check for phase advancement readiness
            if workflow and proactive_analysis.get('identified_gaps'):
                readiness = proactive_ai.detect_readiness_to_advance(project_context)
                if readiness.get('ready'):
                    print(f"  ✅ Project ready to advance: {readiness.get('recommendation')}")
    
    # Enhance the prompt with proactive context
    proactive_context = ""
    if proactive_analysis and proactive_analysis.get('proactive_message'):
        proactive_context = f"\n\nPROACTIVE INSIGHT: {proactive_analysis['proactive_message']}\n"
    
    db = get_db()
    cursor = db.execute(
        'INSERT INTO tasks (user_request, status) VALUES (?, ?)',
        (user_request, 'analyzing')
    )
    task_id = cursor.lastrowid
    db.commit()
    
    overall_start = time.time()
    knowledge_used = False
    knowledge_sources = []
    
    try:
        # Get relevant knowledge from project base
        knowledge_context = ""
        if knowledge_base:
            try:
                knowledge_context = knowledge_base.get_context_for_task(user_request, max_context=3000)
                if knowledge_context:
                    knowledge_used = True
                    search_results = knowledge_base.search(user_request, max_results=3)
                    knowledge_sources = [r['filename'] for r in search_results]
            except Exception as e:
                print(f"⚠️ Knowledge retrieval error: {e}")
        
        # Create project-aware prompt if workflow exists
        user_request_for_ai = user_request
        
        if workflow and intent != 'general_question' and WORKFLOW_AVAILABLE:
            enhanced_prompt = create_project_aware_prompt(
                user_request, 
                intent, 
                workflow,
                knowledge_context
            )
            workflow.add_context('request', f"{intent}: {user_request}")
            
            # Save workflow updates to database
            save_project_to_db(workflow)
            
            user_request_for_ai = enhanced_prompt
        
        # Step 1: Sonnet analyzes
        sonnet_analysis = analyze_task_with_sonnet(user_request_for_ai)
        knowledge_used = sonnet_analysis.get('knowledge_applied', False) or knowledge_used
        knowledge_sources = knowledge_sources or sonnet_analysis.get('knowledge_sources', [])
        
        # Step 2: Escalate to Opus if needed
        if sonnet_analysis.get('escalate_to_opus'):
            db.execute(
                'INSERT INTO escalations (task_id, reason, sonnet_confidence) VALUES (?, ?, ?)',
                (task_id, sonnet_analysis.get('reasoning'), sonnet_analysis.get('confidence'))
            )
            db.commit()
            
            opus_plan = handle_with_opus(user_request_for_ai, sonnet_analysis)
            orchestrator = "opus"
            plan = opus_plan
            if opus_plan.get('knowledge_applied'):
                knowledge_used = True
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
                    '''INSERT INTO specialist_assignments 
                       (task_id, specialist_name, specialist_role, output, execution_time_seconds, success)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (task_id, specialist, result.get('specialist'), 
                     result.get('output'), result.get('execution_time'), result.get('success'))
                )
                db.commit()
                
                if not actual_output:
                    actual_output = result.get('output')
        else:
            # No specialists needed - orchestrator handles it directly
            if orchestrator == "opus":
                actual_output = call_claude_opus(f"Complete this request:\n\n{user_request}")
            else:
                actual_output = call_claude_sonnet(f"Complete this request:\n\n{user_request}")
            
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
        
        # Step 5: OUTPUT FORMATTING ENFORCEMENT (NEW - CRITICAL)
        formatting_applied = False
        formatting_fixed = False
        
        if actual_output and OUTPUT_FORMATTER_AVAILABLE:
            formatter = get_output_formatter()
            
            # Check if output is terrible
            is_bad, reasons = formatter.is_unacceptable(actual_output)
            
            if is_bad:
                print(f"  ⚠️ UNACCEPTABLE OUTPUT DETECTED: {reasons}")
                print(f"  🔧 Applying automatic formatting fix...")
                
                # Fix the terrible output
                actual_output = formatter.format_output(actual_output)
                formatting_fixed = True
                formatting_applied = True
                
                print(f"  ✅ Output reformatted to professional standard")
        
        # Step 6: Professional Formatting Pass (if not already fixed)
        if actual_output and OPENAI_API_KEY and FORMATTING_AVAILABLE and not formatting_fixed:
            needs_format, format_issues = needs_formatting(actual_output)
            
            if needs_format:
                print(f"  🎨 Applying formatting pass (issues: {format_issues})")
                
                doc_type = detect_output_type(user_request, actual_output)
                
                try:
                    formatted_output = format_with_gpt4(actual_output, doc_type, call_gpt4)
                    
                    if formatted_output and not formatted_output.startswith('[Formatting pass failed'):
                        actual_output = formatted_output
                        formatting_applied = True
                        print(f"  ✅ Formatting applied (type: {doc_type})")
                    else:
                        print(f"  ⚠️ Formatting skipped (failed or no change)")
                        
                except Exception as e:
                    print(f"  ⚠️ Formatting error: {e}")
        
        # Step 7: Document Generation (MICROSOFT 365 PRIORITY)
        document_file = None
        document_url = None
        doc_type = None
        
        if actual_output:
            # Detect if document should be created
            should_create_doc = False
            
            if DOCUMENT_GENERATOR_AVAILABLE:
                doc_gen = get_document_generator()
                should_create_doc, doc_type = doc_gen.should_create_document(user_request)
            
            # Check if user explicitly requests a document
            request_lower = user_request.lower()
            if any(word in request_lower for word in ['create document', 'create schedule', 'create report', 'create proposal', 'word document', 'excel', 'spreadsheet']):
                should_create_doc = True
                if not doc_type:
                    if 'excel' in request_lower or 'spreadsheet' in request_lower:
                        doc_type = 'xlsx'
                    else:
                        doc_type = 'docx'
            
            if should_create_doc and doc_type:
                print(f"  📄 Creating {doc_type.upper()} document...")
                
                # PRIORITIZE MICROSOFT 365
                if MS365_AVAILABLE and ms365.is_configured and doc_type in ['docx', 'xlsx']:
                    try:
                        # Generate descriptive filename
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        base_name = "document"
                        
                        if "schedule" in request_lower:
                            base_name = "schedule"
                        elif "proposal" in request_lower:
                            base_name = "proposal"
                        elif "report" in request_lower:
                            base_name = "report"
                        elif "analysis" in request_lower:
                            base_name = "analysis"
                        
                        filename = f"{base_name}_{timestamp}.{doc_type}"
                        
                        print(f"  ☁️  Using Microsoft 365 for professional document...")
                        
                        if doc_type == 'docx':
                            result = ms365.create_word_document(actual_output, filename)
                        elif doc_type == 'xlsx':
                            # For Excel, convert text to structured data
                            result = ms365.create_excel_workbook({'Sheet1': [[actual_output]]}, filename)
                        
                        if result.get('success'):
                            document_url = result.get('web_url')  # OneDrive web link
                            document_file = filename
                            print(f"  ✅ Microsoft 365 document created: {filename}")
                            print(f"  🔗 OneDrive link: {document_url}")
                        else:
                            print(f"  ⚠️ Microsoft 365 failed: {result.get('error')}, falling back to local generation")
                            # Fall back to local generation
                            MS365_AVAILABLE_FALLBACK = False
                    
                    except Exception as e:
                        print(f"  ⚠️ Microsoft 365 error: {e}, falling back to local generation")
                        MS365_AVAILABLE_FALLBACK = False
                
                # FALLBACK: Use local document generator
                if not document_file and DOCUMENT_GENERATOR_AVAILABLE:
                    try:
                        doc_gen = get_document_generator()
                        
                        if doc_type == 'docx':
                            document_file = doc_gen.create_word_document(actual_output)
                        elif doc_type == 'pdf':
                            document_file = doc_gen.create_pdf(actual_output)
                        elif doc_type == 'pptx':
                            document_file = doc_gen.create_powerpoint(actual_output)
                        
                        if document_file:
                            filename = os.path.basename(document_file)
                            document_url = f"/api/download/{filename}"
                            print(f"  ✅ Local document created: {filename}")
                        else:
                            print(f"  ⚠️ Document generation failed, returning text")
                    
                    except Exception as e:
                        print(f"  ⚠️ Document generation error: {e}")
        
        total_time = time.time() - overall_start
        
        # ==================== PROACTIVE INTELLIGENCE ====================
        # Generate proactive suggestions based on context
        proactive_suggestions = None
        proactive_message = None
        
        if PROACTIVE_AVAILABLE and proactive_ai.should_show_initiative():
            suggestions = proactive_ai.analyze_context_and_suggest(
                user_request,
                project_phase=workflow.project_phase if workflow else None,
                project_context={
                    'uploaded_files': workflow.uploaded_files if workflow else [],
                    'email_context': workflow.email_context if workflow else [],
                    'key_findings': workflow.key_findings if workflow else []
                } if workflow else None
            )
            
            if suggestions.get('has_suggestions'):
                proactive_message = proactive_ai.generate_proactive_message(suggestions)
                proactive_suggestions = suggestions
                proactive_ai.last_suggestion_time = datetime.now()
                
                # Append proactive message to output
                if proactive_message:
                    actual_output += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🧠 **PROACTIVE SUGGESTIONS**\n{proactive_message}"
        
        # Update task status
        db.execute(
            '''UPDATE tasks SET status = ?, assigned_orchestrator = ?, execution_time_seconds = ?,
               knowledge_used = ?, knowledge_sources = ? WHERE id = ?''',
            ('completed', orchestrator, total_time, knowledge_used, 
             json.dumps(knowledge_sources), task_id)
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
            'execution_time_seconds': total_time,
            'knowledge_used': knowledge_used,
            'knowledge_sources': knowledge_sources,
            'formatting_applied': formatting_applied,
            'formatting_fixed': formatting_fixed,
            'document_created': document_file is not None,
            'document_url': document_url,
            'document_type': doc_type if document_file else None,
            'files_processed': file_names,
            'proactive_suggestions': proactive_suggestions,  # NEW - Shows initiative!
            'project_workflow': {
                'active': workflow is not None,
                'project_id': project_id if workflow else None,
                'intent_detected': intent,
                'phase': workflow.project_phase if workflow else None
            }
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
# REST OF THE ENDPOINTS (UNCHANGED - KEEPING ALL EXISTING FUNCTIONALITY)
# ============================================================================

@app.route('/api/knowledge/search', methods=['POST'])
def knowledge_search():
    """Search the project knowledge base"""
    if not knowledge_base:
        return jsonify({'error': 'Knowledge base not initialized'}), 503
    
    data = request.json
    query = data.get('query', '')
    max_results = data.get('max_results', 5)
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    try:
        results = knowledge_base.search(query, max_results=max_results)
        return jsonify({
            'success': True,
            'query': query,
            'results': results,
            'total_found': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/document/<filename>')
def get_knowledge_document(filename):
    """Retrieve a specific document from the knowledge base"""
    if not knowledge_base:
        return jsonify({'error': 'Knowledge base not initialized'}), 503
    
    try:
        doc = knowledge_base.get_document(filename)
        if doc:
            return jsonify({
                'success': True,
                'filename': filename,
                'content': doc['content'][:10000],
                'metadata': doc['metadata'],
                'full_content_length': len(doc['content'])
            })
        else:
            return jsonify({'error': 'Document not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/stats')
def knowledge_stats():
    """Get knowledge base statistics"""
    if not knowledge_base:
        return jsonify({'error': 'Knowledge base not initialized'}), 503
    
    try:
        stats = knowledge_base.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/knowledge/documents')
def list_knowledge_documents():
    """List all documents in the knowledge base"""
    if not knowledge_base:
        return jsonify({'error': 'Knowledge base not initialized'}), 503
    
    try:
        docs = knowledge_base.get_all_documents()
        return jsonify({
            'success': True,
            'documents': docs,
            'total_count': len(docs)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit feedback on task results"""
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
        
        db.execute('''
            INSERT INTO user_feedback 
            (task_id, overall_rating, quality_rating, accuracy_rating, usefulness_rating,
             consensus_was_accurate, improvement_categories, user_comment, output_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, overall_rating, quality_rating, accuracy_rating, usefulness_rating,
              consensus_was_accurate, json.dumps(improvement_categories), user_comment, output_used))
        
        orchestrator = task['assigned_orchestrator']
        task_type = task['task_type']
        avg_rating = (quality_rating + accuracy_rating + usefulness_rating) / 3
        
        pattern_key = f"{orchestrator}_{task_type}"
        existing_pattern = db.execute(
            'SELECT * FROM learning_records WHERE pattern_type = ?', (pattern_key,)
        ).fetchone()
        
        if existing_pattern:
            old_success = existing_pattern['success_rate']
            old_times = existing_pattern['times_applied']
            new_success = (old_success * old_times + (avg_rating / 5.0)) / (old_times + 1)
            
            db.execute('''
                UPDATE learning_records 
                SET success_rate = ?, times_applied = ?, pattern_data = ?
                WHERE pattern_type = ?
            ''', (new_success, old_times + 1, json.dumps({
                'last_rating': avg_rating,
                'last_consensus': consensus_score,
                'improvement_areas': improvement_categories
            }), pattern_key))
        else:
            db.execute('''
                INSERT INTO learning_records (pattern_type, success_rate, times_applied, pattern_data)
                VALUES (?, ?, ?, ?)
            ''', (pattern_key, avg_rating / 5.0, 1, json.dumps({
                'orchestrator': orchestrator,
                'task_type': task_type,
                'last_rating': avg_rating,
                'last_consensus': consensus_score
            })))
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Feedback recorded - system is learning!',
            'consensus_was_accurate': consensus_was_accurate,
            'learning_updated': True
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()

@app.route('/api/learning/stats')
def learning_stats():
    """Get learning system statistics"""
    db = get_db()
    
    total_feedback = db.execute('SELECT COUNT(*) as count FROM user_feedback').fetchone()['count']
    avg_overall = db.execute('SELECT AVG(overall_rating) as avg FROM user_feedback').fetchone()['avg']
    
    consensus_accuracy = db.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN consensus_was_accurate = 1 THEN 1 ELSE 0 END) as accurate
        FROM user_feedback 
        WHERE consensus_was_accurate IS NOT NULL
    ''').fetchone()
    
    orchestrator_performance = db.execute('''
        SELECT 
            t.assigned_orchestrator as orchestrator,
            AVG(f.overall_rating) as avg_rating,
            COUNT(*) as tasks_rated
        FROM user_feedback f
        JOIN tasks t ON f.task_id = t.id
        GROUP BY t.assigned_orchestrator
    ''').fetchall()
    
    all_improvements = db.execute('SELECT improvement_categories FROM user_feedback').fetchall()
    improvement_counts = {}
    for row in all_improvements:
        if row['improvement_categories']:
            categories = json.loads(row['improvement_categories'])
            for cat in categories:
                improvement_counts[cat] = improvement_counts.get(cat, 0) + 1
    
    knowledge_usage = db.execute('''
        SELECT 
            COUNT(*) as total_tasks,
            SUM(CASE WHEN knowledge_used = 1 THEN 1 ELSE 0 END) as tasks_with_knowledge
        FROM tasks
        WHERE status = 'completed'
    ''').fetchone()
    
    db.close()
    
    return jsonify({
        'total_feedback_submissions': total_feedback,
        'average_overall_rating': round(avg_overall, 2) if avg_overall else 0,
        'consensus_accuracy_rate': round(
            (consensus_accuracy['accurate'] / consensus_accuracy['total'] * 100) 
            if consensus_accuracy['total'] > 0 else 0, 1
        ),
        'orchestrator_performance': [dict(row) for row in orchestrator_performance],
        'common_improvement_areas': improvement_counts,
        'knowledge_usage': {
            'total_tasks': knowledge_usage['total_tasks'],
            'tasks_using_knowledge': knowledge_usage['tasks_with_knowledge'],
            'usage_percentage': round(
                (knowledge_usage['tasks_with_knowledge'] / knowledge_usage['total_tasks'] * 100)
                if knowledge_usage['total_tasks'] > 0 else 0, 1
            )
        }
    })

@app.route('/')
def index():
    """Main interface"""
    return render_template('index.html')

@app.route('/workflow')
def workflow():
    """New conversational workflow interface"""
    return render_template('index_workflow.html')

@app.route('/api/download/<filename>')
def download_file(filename):
    """Download generated documents"""
    from flask import send_file
    import os
    
    file_path = os.path.join('/mnt/user-data/outputs', filename)
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    if filename.endswith('.docx'):
        mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif filename.endswith('.pdf'):
        mimetype = 'application/pdf'
    elif filename.endswith('.pptx'):
        mimetype = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    elif filename.endswith('.xlsx'):
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        mimetype = 'application/octet-stream'
    
    return send_file(file_path, mimetype=mimetype, as_attachment=True, download_name=filename)

@app.route('/api/documents')
def list_documents():
    """List all generated documents available for download"""
    import os
    from pathlib import Path
    
    output_dir = '/mnt/user-data/outputs'
    
    if not os.path.exists(output_dir):
        return jsonify({'documents': []})
    
    documents = []
    for file in os.listdir(output_dir):
        file_path = os.path.join(output_dir, file)
        if os.path.isfile(file_path):
            # Get file stats
            stat = os.stat(file_path)
            
            # Determine file type
            ext = file.split('.')[-1].lower()
            if ext in ['docx', 'pdf', 'xlsx', 'pptx', 'csv', 'txt']:
                documents.append({
                    'filename': file,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'type': ext,
                    'download_url': f'/api/download/{file}'
                })
    
    # Sort by modified time (newest first)
    documents.sort(key=lambda x: x['modified'], reverse=True)
    
    return jsonify({
        'success': True,
        'documents': documents,
        'total_count': len(documents)
    })

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
    kb_status = 'initialized' if knowledge_base and len(knowledge_base.knowledge_index) > 0 else 'not_initialized'
    kb_doc_count = len(knowledge_base.knowledge_index) if knowledge_base else 0
    
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
        },
        'knowledge_base': {
            'status': kb_status,
            'documents_indexed': kb_doc_count
        },
        'output_formatter': {
            'status': 'enabled' if OUTPUT_FORMATTER_AVAILABLE else 'disabled'
        }
    })

@app.route('/api/debug/knowledge')
def debug_knowledge():
    """Debug endpoint to diagnose knowledge base issues"""
    import os
    from pathlib import Path
    
    debug_info = {
        'knowledge_base_object': knowledge_base is not None,
        'paths_checked': [],
        'libraries': {
            'python-docx': 'unknown',
            'openpyxl': 'unknown', 
            'PyPDF2': 'unknown'
        },
        'current_directory': os.getcwd(),
        'files_in_current_dir': []
    }
    
    for path in ["/mnt/project", "project_files", "./project_files"]:
        path_obj = Path(path)
        debug_info['paths_checked'].append({
            'path': path,
            'exists': path_obj.exists(),
            'is_dir': path_obj.is_dir() if path_obj.exists() else False,
            'files': list(path_obj.iterdir()) if path_obj.exists() and path_obj.is_dir() else []
        })
    
    try:
        import docx
        debug_info['libraries']['python-docx'] = 'installed'
    except:
        debug_info['libraries']['python-docx'] = 'MISSING'
    
    try:
        import openpyxl
        debug_info['libraries']['openpyxl'] = 'installed'
    except:
        debug_info['libraries']['openpyxl'] = 'MISSING'
    
    try:
        import PyPDF2
        debug_info['libraries']['PyPDF2'] = 'installed'
    except:
        debug_info['libraries']['PyPDF2'] = 'MISSING'
    
    try:
        debug_info['files_in_current_dir'] = os.listdir('.')
    except:
        pass
    
    if knowledge_base:
        debug_info['knowledge_base_details'] = {
            'project_path': str(knowledge_base.project_path),
            'project_path_exists': knowledge_base.project_path.exists(),
            'documents_indexed': len(knowledge_base.knowledge_index),
            'index_keys': list(knowledge_base.knowledge_index.keys())
        }
    
    return jsonify(debug_info)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# I did no harm and this file is not truncated
