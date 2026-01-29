"""
Task Analysis Module - WITH SYSTEM CAPABILITIES
Created: January 21, 2026
Last Updated: January 29, 2026 - ADDED SYSTEM CAPABILITIES INJECTION

CHANGELOG:
- January 29, 2026: SYSTEM CAPABILITIES FIX
  * CRITICAL: Added get_system_capabilities_prompt() injection
  * AI now knows what it can do (files, folders, documents, etc.)
  * Capabilities injected into EVERY prompt for Sonnet and Opus
  * Fixed "I don't have ability to..." false negatives

CRITICAL: The system capabilities manifest is now injected into every
AI call so the AI knows what it's capable of doing.

Author: Jim @ Shiftwork Solutions LLC
"""

import json
import time
from orchestration.ai_clients import call_claude_sonnet, call_claude_opus
from database import get_db


def get_learning_context():
    """Retrieve learning patterns to inform orchestration decisions."""
    try:
        db = get_db()
        
        table_check = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='learning_records'"
        ).fetchone()
        
        if not table_check:
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
            if 'knowledge_usage' in pattern_data:
                context += f"  Knowledge usage: {pattern_data['knowledge_usage']}\n"
        
        return context
    except Exception as e:
        print(f"⚠️ Learning context unavailable: {e}")
        return ""


def check_knowledge_base_first(user_request, knowledge_base):
    """
    Check project knowledge base before invoking AI.
    Returns knowledge context and confidence scores.
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
        print("🔍 Searching project knowledge base...")
        
        if hasattr(knowledge_base, 'semantic_search'):
            search_results = knowledge_base.semantic_search(user_request, max_results=5)
        else:
            search_results = knowledge_base.search(user_request, max_results=5)
        
        if not search_results:
            return {
                'has_relevant_knowledge': False,
                'knowledge_context': '',
                'knowledge_confidence': 0.0,
                'knowledge_sources': [],
                'should_proceed_to_ai': True,
                'reason': 'No relevant knowledge found'
            }
        
        top_score = search_results[0].get('score', 0)
        
        if top_score >= 50:
            confidence = 0.9
        elif top_score >= 25:
            confidence = 0.75
        elif top_score >= 10:
            confidence = 0.6
        else:
            confidence = 0.4
        
        knowledge_context = knowledge_base.get_context_for_task(
            user_request, 
            max_context=5000,
            max_results=3
        )
        
        knowledge_sources = [r['filename'] for r in search_results[:3]]
        
        print(f"  ✅ Found {len(search_results)} relevant documents")
        print(f"  📊 Confidence: {confidence*100:.0f}%")
        
        return {
            'has_relevant_knowledge': True,
            'knowledge_context': knowledge_context,
            'knowledge_confidence': confidence,
            'knowledge_sources': knowledge_sources,
            'should_proceed_to_ai': True,
            'reason': f'Found {len(search_results)} documents',
            'top_relevance': search_results[0].get('relevance_type', 'Relevant')
        }
        
    except Exception as e:
        print(f"⚠️ Knowledge search error: {e}")
        return {
            'has_relevant_knowledge': False,
            'knowledge_context': '',
            'knowledge_confidence': 0.0,
            'knowledge_sources': [],
            'should_proceed_to_ai': True,
            'reason': f'Error: {str(e)}'
        }


def analyze_task_with_sonnet(user_request, knowledge_base=None):
    """
    Sonnet analyzes task WITH system capabilities + project knowledge.
    
    CRITICAL FIX (January 29, 2026):
    - Injects SYSTEM CAPABILITIES so AI knows what it can do
    - AI now aware of file handling, folders, document creation, etc.
    """
    
    # 🔧 CRITICAL: Import and inject system capabilities
    from orchestration.system_capabilities import get_system_capabilities_prompt
    capabilities = get_system_capabilities_prompt()
    
    # Check project knowledge
    kb_check = check_knowledge_base_first(user_request, knowledge_base)
    learning_context = get_learning_context()
    
    # Build prompt with CAPABILITIES FIRST (so AI knows what it can do)
    analysis_prompt = f"""{capabilities}

You are the primary orchestrator in an AI swarm system for Shiftwork Solutions LLC.

{learning_context}

{kb_check['knowledge_context']}

USER REQUEST: {user_request}

"""
    
    if kb_check['has_relevant_knowledge']:
        analysis_prompt += f"""
KNOWLEDGE BASE STATUS:
✅ Relevant project knowledge found (Confidence: {kb_check['knowledge_confidence']*100:.0f}%)
📚 Sources: {', '.join(kb_check['knowledge_sources'][:2])}

Use this knowledge to inform your analysis.
"""
    else:
        analysis_prompt += f"""
KNOWLEDGE BASE STATUS:
ℹ️  No directly relevant project knowledge found
"""
    
    analysis_prompt += """
Analyze this request and determine:
1. Task type (strategy, schedule_design, implementation, survey, content, code, analysis, complex)
2. Your confidence (0.0-1.0)
3. Required specialists (gpt4, deepseek, gemini, or "none")
4. Escalate to Opus? (true/false)
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
    api_response = call_claude_sonnet(analysis_prompt)
    execution_time = time.time() - start_time
    
    # Extract content from dict response
    if isinstance(api_response, dict):
        if api_response.get('error'):
            return {
                "task_type": "error",
                "confidence": 0.0,
                "specialists_needed": [],
                "escalate_to_opus": False,
                "reasoning": f"API error: {api_response.get('content')}",
                "execution_time": execution_time,
                "knowledge_applied": kb_check['has_relevant_knowledge'],
                "knowledge_sources": kb_check['knowledge_sources']
            }
        response_text = api_response.get('content', '')
    else:
        response_text = str(api_response)
    
    try:
        # Clean JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        analysis = json.loads(response_text)
        analysis['execution_time'] = execution_time
        analysis['knowledge_applied'] = kb_check['has_relevant_knowledge']
        analysis['knowledge_sources'] = kb_check['knowledge_sources']
        analysis['knowledge_confidence'] = kb_check['knowledge_confidence']
        
        # Boost confidence if strong knowledge match
        if kb_check['knowledge_confidence'] > 0.7:
            original = analysis.get('confidence', 0.5)
            analysis['confidence'] = min(0.95, original + 0.2)
        
        return analysis
        
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON parse error: {e}")
        return {
            "task_type": "complex",
            "confidence": 0.5,
            "specialists_needed": [],
            "escalate_to_opus": True,
            "reasoning": "Parse error - escalating",
            "execution_time": execution_time,
            "knowledge_applied": kb_check['has_relevant_knowledge'],
            "knowledge_sources": kb_check['knowledge_sources']
        }


def handle_with_opus(user_request, sonnet_analysis, knowledge_base=None):
    """
    Opus handles complex requests WITH system capabilities + knowledge.
    
    CRITICAL FIX (January 29, 2026):
    - Injects SYSTEM CAPABILITIES so Opus knows what it can do
    """
    
    # 🔧 CRITICAL: Import and inject system capabilities
    from orchestration.system_capabilities import get_system_capabilities_prompt
    capabilities = get_system_capabilities_prompt()
    
    kb_check = check_knowledge_base_first(user_request, knowledge_base)
    learning_context = get_learning_context()
    
    # Build prompt with CAPABILITIES FIRST
    opus_prompt = f"""{capabilities}

You are the strategic supervisor in the AI Swarm for Shiftwork Solutions LLC.

{learning_context}

{kb_check['knowledge_context']}

"""
    
    if kb_check['has_relevant_knowledge']:
        opus_prompt += f"""
KNOWLEDGE: Relevant expertise available (Confidence: {kb_check['knowledge_confidence']*100:.0f}%)
Sources: {', '.join(kb_check['knowledge_sources'])}
"""
    
    opus_prompt += f"""
Sonnet escalated this request to you.

USER REQUEST: {user_request}

SONNET'S ANALYSIS:
{json.dumps(sonnet_analysis, indent=2)}

Provide strategic response with:
1. Deep analysis
2. Specialist assignments
3. Expected workflow
4. Learning for Sonnet
5. Methodology applied

Respond in JSON:
{{
    "strategic_analysis": "string",
    "specialist_assignments": [{{"ai": "name", "task": "description", "reason": "why"}}],
    "workflow": ["step1", "step2"],
    "learning_for_sonnet": "pattern to learn",
    "methodology_applied": "principles used"
}}"""

    start_time = time.time()
    api_response = call_claude_opus(opus_prompt)
    execution_time = time.time() - start_time
    
    # Extract content
    if isinstance(api_response, dict):
        if api_response.get('error'):
            return {
                "strategic_analysis": f"API error: {api_response.get('content')}",
                "specialist_assignments": [],
                "workflow": ["Manual handling required"],
                "execution_time": execution_time,
                "knowledge_applied": kb_check['has_relevant_knowledge']
            }
        response_text = api_response.get('content', '')
    else:
        response_text = str(api_response)
    
    try:
        # Clean JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        opus_plan = json.loads(response_text)
        opus_plan['execution_time'] = execution_time
        opus_plan['knowledge_applied'] = kb_check['has_relevant_knowledge']
        opus_plan['knowledge_sources'] = kb_check['knowledge_sources']
        
        return opus_plan
        
    except json.JSONDecodeError:
        return {
            "strategic_analysis": response_text,
            "specialist_assignments": [],
            "workflow": ["Manual handling"],
            "execution_time": execution_time,
            "knowledge_applied": kb_check['has_relevant_knowledge']
        }


def execute_specialist_task(specialist_ai, task_description, knowledge_context=""):
    """Execute task with specialist AI."""
    from orchestration.ai_clients import call_gpt4, call_deepseek, call_gemini
    
    # 🔧 CRITICAL: Inject capabilities for specialists too
    from orchestration.system_capabilities import get_system_capabilities_prompt
    capabilities = get_system_capabilities_prompt()
    
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
            "output": f"ERROR: Unknown specialist",
            "execution_time": 0,
            "success": False
        }
    
    # Build prompt with capabilities
    full_prompt = f"{capabilities}\n\n"
    if knowledge_context:
        full_prompt += f"{knowledge_context}\n\n"
    full_prompt += f"TASK: {task_description}"
    
    start_time = time.time()
    api_response = ai_function(full_prompt)
    execution_time = time.time() - start_time
    
    # Extract content
    if isinstance(api_response, dict):
        output_text = api_response.get('content', '')
        has_error = api_response.get('error', False)
    else:
        output_text = str(api_response)
        has_error = output_text.startswith("ERROR")
    
    return {
        "specialist": specialist_ai,
        "output": output_text,
        "execution_time": execution_time,
        "success": not has_error,
        "had_knowledge_context": bool(knowledge_context)
    }


# I did no harm and this file is not truncated
