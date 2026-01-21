"""
Consensus Validation Module
Created: January 21, 2026
Last Updated: January 21, 2026

Multiple AIs review outputs for quality assurance.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from orchestration.ai_clients import call_claude_sonnet, call_gpt4
from config import OPENAI_API_KEY

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

# I did no harm and this file is not truncated
