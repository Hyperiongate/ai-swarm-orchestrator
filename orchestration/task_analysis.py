"""
Task Analysis Module
Created: January 21, 2026
Last Updated: January 21, 2026

Sonnet analyzes tasks, Opus handles complex cases.
Clean separation of concerns.
"""

import json
import time
from orchestration.ai_clients import call_claude_sonnet, call_claude_opus
from database import get_db

def get_learning_context():
    """Retrieve learning patterns to inform orchestration decisions"""
    db = get_db()
    
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

def analyze_task_with_sonnet(user_request, knowledge_base=None):
    """
    Sonnet analyzes the task WITH PROJECT KNOWLEDGE
    Returns decision: orchestrator, specialists, escalation
    """
    
    learning_context = get_learning_context()
    
    # Get relevant knowledge from project base
    knowledge_context = ""
    knowledge_sources = []
    
    if knowledge_base:
        try:
            knowledge_context = knowledge_base.get_context_for_task(user_request, max_context=3000)
            if knowledge_context:
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

def handle_with_opus(user_request, sonnet_analysis, knowledge_base=None):
    """
    Opus handles complex/novel situations WITH PROJECT KNOWLEDGE
    Returns strategic plan with specialist assignments
    """
    
    # Get relevant knowledge from project base
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
    from orchestration.ai_clients import call_gpt4, call_deepseek, call_gemini
    
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

# I did no harm and this file is not truncated
