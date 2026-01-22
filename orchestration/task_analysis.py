"""
Task Analysis Module
Created: January 21, 2026
Last Updated: January 22, 2026 - CRITICAL FIX: AI client returns dict, not string

CHANGES IN THIS VERSION:
- January 22, 2026: CRITICAL BUG FIX
  * call_claude_sonnet() and call_claude_opus() return DICT with 'content' key
  * Previous code treated response as string, causing "Error: undefined"
  * Fixed all functions to extract response['content'] before processing
  * Added proper error handling for API failures
  * Fixed execute_specialist_task to handle dict response

Sonnet analyzes tasks, Opus handles complex cases.
Clean separation of concerns.

Author: Jim @ Shiftwork Solutions LLC
"""

import json
import time
from orchestration.ai_clients import call_claude_sonnet, call_claude_opus
from database import get_db


def get_learning_context():
    """Retrieve learning patterns to inform orchestration decisions"""
    try:
        db = get_db()
        
        # Check if table exists first
        table_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='learning_records'"
        ).fetchone()
        
        if not table_check:
            # Table doesn't exist yet - return empty context
            db.close()
            return ""
        
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
    except Exception as e:
        # If anything goes wrong with learning, just return empty context
        print(f"⚠️ Learning context unavailable: {e}")
        return ""


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
    
    # CRITICAL FIX: call_claude_sonnet returns a DICT, not a string!
    api_response = call_claude_sonnet(analysis_prompt)
    execution_time = time.time() - start_time
    
    # Extract the content from the response dict
    if isinstance(api_response, dict):
        # Check for API error
        if api_response.get('error'):
            print(f"⚠️ Sonnet API error: {api_response.get('content')}")
            return {
                "task_type": "unknown",
                "confidence": 0.5,
                "specialists_needed": [],
                "escalate_to_opus": True,
                "reasoning": f"API error: {api_response.get('content')}",
                "execution_time": execution_time,
                "knowledge_sources": knowledge_sources,
                "knowledge_applied": bool(knowledge_context)
            }
        response_text = api_response.get('content', '')
    else:
        # Fallback if somehow it's a string
        response_text = str(api_response)
    
    # Parse JSON response
    try:
        # Clean up the response text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        analysis = json.loads(response_text)
        analysis['execution_time'] = execution_time
        analysis['knowledge_sources'] = knowledge_sources
        
        # Ensure knowledge_applied is set
        if 'knowledge_applied' not in analysis:
            analysis['knowledge_applied'] = bool(knowledge_context)
            
        return analysis
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parse error: {e}")
        print(f"⚠️ Raw response: {response_text[:500]}...")
        return {
            "task_type": "unknown",
            "confidence": 0.5,
            "specialists_needed": [],
            "escalate_to_opus": True,
            "reasoning": "Failed to parse Sonnet response, escalating to Opus",
            "raw_response": response_text,
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
    
    # CRITICAL FIX: call_claude_opus returns a DICT, not a string!
    api_response = call_claude_opus(opus_prompt)
    execution_time = time.time() - start_time
    
    # Extract the content from the response dict
    if isinstance(api_response, dict):
        # Check for API error
        if api_response.get('error'):
            print(f"⚠️ Opus API error: {api_response.get('content')}")
            return {
                "strategic_analysis": f"API error: {api_response.get('content')}",
                "specialist_assignments": [],
                "workflow": ["Manual handling required due to API error"],
                "learning_for_sonnet": "API error occurred",
                "execution_time": execution_time,
                "knowledge_applied": bool(knowledge_context)
            }
        response_text = api_response.get('content', '')
    else:
        # Fallback if somehow it's a string
        response_text = str(api_response)
    
    try:
        # Clean up the response text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        opus_plan = json.loads(response_text)
        opus_plan['execution_time'] = execution_time
        opus_plan['knowledge_applied'] = bool(knowledge_context)
        return opus_plan
    except json.JSONDecodeError as e:
        print(f"⚠️ Opus JSON parse error: {e}")
        return {
            "strategic_analysis": response_text,
            "specialist_assignments": [],
            "workflow": ["Manual handling required"],
            "learning_for_sonnet": "Complex case - needs human review",
            "raw_response": response_text,
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
        return {
            "specialist": specialist_ai,
            "output": f"ERROR: Unknown specialist: {specialist_ai}",
            "execution_time": 0,
            "success": False,
            "error": f"Unknown specialist: {specialist_ai}"
        }
    
    start_time = time.time()
    
    # CRITICAL FIX: All AI functions return a DICT with 'content' key!
    api_response = ai_function(task_description)
    execution_time = time.time() - start_time
    
    # Extract the content from the response dict
    if isinstance(api_response, dict):
        output_text = api_response.get('content', '')
        has_error = api_response.get('error', False)
    else:
        # Fallback if somehow it's a string
        output_text = str(api_response)
        has_error = output_text.startswith("ERROR")
    
    return {
        "specialist": specialist_ai,
        "output": output_text,
        "execution_time": execution_time,
        "success": not has_error,
        "usage": api_response.get('usage', {}) if isinstance(api_response, dict) else {}
    }


# I did no harm and this file is not truncated
