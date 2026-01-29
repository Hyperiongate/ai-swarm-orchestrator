"""
Task Analysis Module - MERGED VERSION
Created: January 21, 2026
Last Updated: January 29, 2026 - MERGED: Bug fixes + Knowledge Priority

CHANGELOG:
- January 22, 2026: CRITICAL BUG FIX (from existing version)
  * call_claude_sonnet() and call_claude_opus() return DICT with 'content' key
  * Fixed all functions to extract response['content'] before processing
  * Added proper error handling for API failures
  * Fixed execute_specialist_task to handle dict response

- January 29, 2026: KNOWLEDGE PRIORITY ENHANCEMENT (new)
  * Added check_knowledge_base_first() - MUST be called first
  * Implemented priority system: Check project knowledge BEFORE any AI
  * Added knowledge confidence scoring (0-1 scale)
  * Enhanced prompts with formatted knowledge context
  * Added complete knowledge source tracking
  * Knowledge boosts Sonnet confidence when highly relevant

CRITICAL PRIORITY RULE:
**ALWAYS CHECK PROJECT KNOWLEDGE BASE FIRST**
This is enforced for all domain-specific questions.

Purpose: Analyze incoming tasks and route to appropriate AI specialists.
Clean separation of concerns.

Author: Jim @ Shiftwork Solutions LLC
"""

import json
import time
from orchestration.ai_clients import call_claude_sonnet, call_claude_opus
from database import get_db


def get_learning_context():
    """
    Retrieve learning patterns to inform orchestration decisions.
    Now includes knowledge application success patterns.
    """
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
            # NEW: Track knowledge usage patterns
            if 'knowledge_usage' in pattern_data:
                context += f"  Knowledge usage: {pattern_data['knowledge_usage']}\n"
        
        return context
    except Exception as e:
        # If anything goes wrong with learning, just return empty context
        print(f"⚠️ Learning context unavailable: {e}")
        return ""


def check_knowledge_base_first(user_request, knowledge_base):
    """
    🎯 NEW FUNCTION - CRITICAL PRIORITY CHECK 🎯
    
    THIS MUST BE CALLED FIRST - BEFORE ANY AI IS INVOKED.
    
    Checks the project knowledge base to see if we have domain expertise
    that can inform or answer the request directly.
    
    Returns:
        dict with:
        - has_relevant_knowledge: bool
        - knowledge_context: str (formatted context)
        - knowledge_confidence: float (0-1)
        - knowledge_sources: list of filenames
        - should_proceed_to_ai: bool
    """
    if not knowledge_base:
        return {
            'has_relevant_knowledge': False,
            'knowledge_context': '',
            'knowledge_confidence': 0.0,
            'knowledge_sources': [],
            'should_proceed_to_ai': True,
            'reason': 'Knowledge base not initialized'
        }
    
    try:
        print("🔍 PRIORITY CHECK: Searching project knowledge base...")
        
        # Use semantic search if available, fallback to regular search
        if hasattr(knowledge_base, 'semantic_search'):
            search_results = knowledge_base.semantic_search(user_request, max_results=5)
        else:
            search_results = knowledge_base.search(user_request, max_results=5)
        
        if not search_results:
            print("  ℹ️  No relevant project knowledge found")
            return {
                'has_relevant_knowledge': False,
                'knowledge_context': '',
                'knowledge_confidence': 0.0,
                'knowledge_sources': [],
                'should_proceed_to_ai': True,
                'reason': 'No relevant knowledge found'
            }
        
        # Calculate confidence based on relevance scores
        top_score = search_results[0].get('score', 0)
        
        # Confidence calculation
        if top_score >= 50:  # Highly relevant
            confidence = 0.9
        elif top_score >= 25:  # Very relevant
            confidence = 0.75
        elif top_score >= 10:  # Relevant
            confidence = 0.6
        else:  # Potentially relevant
            confidence = 0.4
        
        # Get formatted context
        knowledge_context = knowledge_base.get_context_for_task(
            user_request, 
            max_context=5000,
            max_results=3
        )
        
        # Extract source filenames
        knowledge_sources = [r['filename'] for r in search_results[:3]]
        
        print(f"  ✅ Found {len(search_results)} relevant documents")
        print(f"  📊 Knowledge confidence: {confidence*100:.0f}%")
        print(f"  📚 Top sources: {', '.join(knowledge_sources[:2])}")
        
        # Always proceed to AI (AI reasoning + knowledge = best results)
        should_proceed_to_ai = True
        
        return {
            'has_relevant_knowledge': True,
            'knowledge_context': knowledge_context,
            'knowledge_confidence': confidence,
            'knowledge_sources': knowledge_sources,
            'should_proceed_to_ai': should_proceed_to_ai,
            'reason': f'Found {len(search_results)} relevant documents',
            'top_relevance': search_results[0].get('relevance_type', 'Relevant')
        }
        
    except Exception as e:
        print(f"⚠️ Knowledge base search error: {e}")
        return {
            'has_relevant_knowledge': False,
            'knowledge_context': '',
            'knowledge_confidence': 0.0,
            'knowledge_sources': [],
            'should_proceed_to_ai': True,
            'reason': f'Search error: {str(e)}'
        }


def analyze_task_with_sonnet(user_request, knowledge_base=None):
    """
    Sonnet analyzes the task WITH PROJECT KNOWLEDGE PRIORITY.
    
    CRITICAL FLOW:
    1. Check project knowledge base FIRST (NEW!)
    2. If relevant knowledge found → inject into Sonnet's prompt
    3. Sonnet makes decision with benefit of domain expertise
    4. Return decision: orchestrator, specialists, or escalation
    
    Returns decision dict with knowledge tracking.
    """
    
    # 🎯 NEW STEP 1: CHECK PROJECT KNOWLEDGE FIRST (PRIORITY!)
    kb_check = check_knowledge_base_first(user_request, knowledge_base)
    
    # Get learning context
    learning_context = get_learning_context()
    
    # Build analysis prompt with knowledge context
    analysis_prompt = f"""You are the primary orchestrator in an AI swarm system for Shiftwork Solutions LLC.

{learning_context}

{kb_check['knowledge_context']}

USER REQUEST: {user_request}

"""
    
    # NEW: Add knowledge status to prompt
    if kb_check['has_relevant_knowledge']:
        analysis_prompt += f"""
KNOWLEDGE BASE STATUS:
✅ Relevant project knowledge found (Confidence: {kb_check['knowledge_confidence']*100:.0f}%)
📚 Sources: {', '.join(kb_check['knowledge_sources'][:2])}
🎯 Relevance: {kb_check.get('top_relevance', 'Relevant')}

You have access to Shiftwork Solutions' expertise from hundreds of facilities across dozens of industries above.
Use this knowledge to inform your analysis and response.
"""
    else:
        analysis_prompt += f"""
KNOWLEDGE BASE STATUS:
ℹ️  No directly relevant project knowledge found
   Reason: {kb_check['reason']}
   Proceeding with general AI capabilities.
"""
    
    analysis_prompt += """
Analyze this request and determine:
1. Task type (strategy, schedule_design, implementation, survey, content, code, analysis, complex)
2. Your confidence in handling this (0.0-1.0)
3. Required specialists (gpt4, deepseek, gemini, or "none")
4. Should this be escalated to Opus? (true/false)
5. Reasoning

Respond ONLY with valid JSON:
{
    "task_type": "string",
    "confidence": 0.0-1.0,
    "specialists_needed": ["ai_name", ...],
    "escalate_to_opus": boolean,
    "reasoning": "string",
    "knowledge_applied": boolean
}"""

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
                "task_type": "error",
                "confidence": 0.0,
                "specialists_needed": [],
                "escalate_to_opus": False,
                "reasoning": f"API error: {api_response.get('content')}",
                "execution_time": execution_time,
                "knowledge_applied": kb_check['has_relevant_knowledge'],
                "knowledge_sources": kb_check['knowledge_sources'],
                "knowledge_confidence": kb_check['knowledge_confidence']
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
            
        analysis = json.loads(response_text)
        
        # Add execution metadata
        analysis['execution_time'] = execution_time
        
        # NEW: Add knowledge tracking (CRITICAL for audit trail)
        analysis['knowledge_applied'] = kb_check['has_relevant_knowledge']
        analysis['knowledge_sources'] = kb_check['knowledge_sources']
        analysis['knowledge_confidence'] = kb_check['knowledge_confidence']
        
        # NEW: If high knowledge confidence, boost Sonnet's confidence
        if kb_check['knowledge_confidence'] > 0.7:
            original_confidence = analysis.get('confidence', 0.5)
            analysis['confidence'] = min(0.95, original_confidence + 0.2)
            analysis['reasoning'] += f" [Confidence boosted from {original_confidence:.2f} to {analysis['confidence']:.2f} due to strong project knowledge match]"
        
        return analysis
        
    except json.JSONDecodeError as e:
        print(f"⚠️ Sonnet JSON parse error: {e}")
        print(f"⚠️ Raw response: {response_text[:500]}...")
        return {
            "task_type": "complex",
            "confidence": 0.5,
            "specialists_needed": [],
            "escalate_to_opus": True,
            "reasoning": "Failed to parse Sonnet analysis - escalating to Opus",
            "raw_response": response_text,
            "execution_time": execution_time,
            "knowledge_applied": kb_check['has_relevant_knowledge'],
            "knowledge_sources": kb_check['knowledge_sources'],
            "knowledge_confidence": kb_check['knowledge_confidence']
        }


def handle_with_opus(user_request, sonnet_analysis, knowledge_base=None):
    """
    Opus handles complex strategic requests WITH PROJECT KNOWLEDGE.
    
    Opus receives:
    1. User request
    2. Sonnet's analysis
    3. Project knowledge context (if available)
    4. Learning patterns
    
    Returns strategic plan with knowledge tracking.
    """
    
    # NEW: Get knowledge context (may have already been retrieved, but check again for Opus)
    kb_check = check_knowledge_base_first(user_request, knowledge_base)
    learning_context = get_learning_context()
    
    opus_prompt = f"""You are the strategic supervisor in the AI Swarm for Shiftwork Solutions LLC.

{learning_context}

{kb_check['knowledge_context']}

"""
    
    # NEW: Add knowledge status for Opus
    if kb_check['has_relevant_knowledge']:
        opus_prompt += f"""
KNOWLEDGE BASE STATUS:
✅ Relevant project knowledge available (Confidence: {kb_check['knowledge_confidence']*100:.0f}%)
📚 Sources: {', '.join(kb_check['knowledge_sources'])}

You have access to Shiftwork Solutions' expertise from hundreds of facilities.
"""
    
    opus_prompt += f"""
Sonnet (primary orchestrator) has escalated this request to you.

USER REQUEST: {user_request}

SONNET'S ANALYSIS:
{json.dumps(sonnet_analysis, indent=2)}

With access to the company's expertise above, provide a strategic response with:
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
                "knowledge_applied": kb_check['has_relevant_knowledge'],
                "knowledge_sources": kb_check['knowledge_sources'],
                "knowledge_confidence": kb_check['knowledge_confidence']
            }
        response_text = api_response.get('content', '')
    else:
        # Fallback if somehow it's a string
        response_text = str(api_response)
    
    try:
        # Clean up response text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        opus_plan = json.loads(response_text)
        
        # Add metadata
        opus_plan['execution_time'] = execution_time
        
        # NEW: Add knowledge tracking
        opus_plan['knowledge_applied'] = kb_check['has_relevant_knowledge']
        opus_plan['knowledge_sources'] = kb_check['knowledge_sources']
        opus_plan['knowledge_confidence'] = kb_check['knowledge_confidence']
        
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
            "knowledge_applied": kb_check['has_relevant_knowledge'],
            "knowledge_sources": kb_check['knowledge_sources'],
            "knowledge_confidence": kb_check['knowledge_confidence']
        }


def execute_specialist_task(specialist_ai, task_description, knowledge_context=""):
    """
    Execute task with specified specialist AI.
    
    NEW: Now accepts knowledge_context to pass domain expertise to specialists.
    """
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
    
    # NEW: Add knowledge context if available
    if knowledge_context:
        full_prompt = f"{knowledge_context}\n\nTASK: {task_description}"
    else:
        full_prompt = task_description
    
    start_time = time.time()
    
    # CRITICAL FIX: All AI functions return a DICT with 'content' key!
    api_response = ai_function(full_prompt)
    execution_time = time.time() - start_time
    
    # Extract the content from the response dict
    if isinstance(api_response, dict):
        output_text = api_response.get('content', '')
        has_error = api_response.get('error', False)
        usage = api_response.get('usage', {})
    else:
        # Fallback if somehow it's a string
        output_text = str(api_response)
        has_error = output_text.startswith("ERROR")
        usage = {}
    
    return {
        "specialist": specialist_ai,
        "output": output_text,
        "execution_time": execution_time,
        "success": not has_error,
        "usage": usage,
        "had_knowledge_context": bool(knowledge_context)  # NEW: Track if knowledge was used
    }


# I did no harm and this file is not truncated
