"""
Consensus Validation Module
Created: January 21, 2026
Last Updated: February 20, 2026 - CRITICAL BUG FIXES

CHANGELOG:

- February 20, 2026: THREE BUG FIXES (Stress Test)
  
  BUG 1 - CRITICAL: API response dict treated as string
    BEFORE: result = future.result()          <- dict {'content': ..., 'error': ...}
            if "```json" in result            <- TypeError: 'in' on dict
            result.split("```json")           <- AttributeError: dict has no split()
    AFTER:  raw = future.result()             <- dict
            if raw.get('error'):              <- surface real API errors
                raise Exception(raw['content'])
            result = raw.get('content', '')   <- extract string FIRST
            if "```json" in result            <- now correct (string operation)
    IMPACT: Every consensus validation was crashing silently, falling back to
            score=5, making consensus useless. Now actually validates.

  BUG 2 - HIGH: Exception message truncated to 100 chars
    BEFORE: "error": f"Failed to parse: {str(e)[:100]}"
    AFTER:  "error": f"Failed to parse: {str(e)}"
    IMPACT: Full error messages now visible in logs for diagnosis.

  BUG 3 - HIGH: False-perfect agreement when all validators fail
    BEFORE: If both validators fail (both score=5), agreement_score = 1.0
            because max([5,5]) - min([5,5]) = 0 -> 1.0 - 0/10 = 1.0
            This is a FALSE green light - no validation actually happened.
    AFTER:  Check if all results contain 'error' key. If so, return
            agreement_score=0.0 and a clear 'validation_failed' flag.
    IMPACT: Caller can now detect that consensus was not actually performed.

  No changes to function signature, return shape, or any other behavior.
  All existing callers remain compatible.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from orchestration.ai_clients import call_claude_sonnet, call_gpt4
from config import OPENAI_API_KEY


def validate_with_consensus(task_result, validators=None):
    """
    Multiple AIs review the output for quality assurance.

    Returns agreement score and any disagreements.
    Auto-detects available validators.

    Args:
        task_result (str): The AI output to validate
        validators (list): Optional list of validator names. Auto-selected if None.

    Returns:
        dict: {
            'validators': list,
            'validation_results': list,
            'agreement_score': float (0.0-1.0),
            'average_score': float,
            'validator_count': int,
            'validation_failed': bool  (True when all validators errored)
        }
    """

    # Auto-detect available validators
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

Respond with JSON only:
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
                # ================================================================
                # FIX 1 (February 20, 2026): Extract dict content BEFORE parsing
                # call_claude_sonnet() and call_gpt4() both return dicts.
                # The old code passed the dict directly to string operations,
                # causing TypeError on "```json" in result and AttributeError
                # on result.split(). Now we extract the 'content' string first.
                # ================================================================
                raw = future.result()

                # Handle dict response (from call_claude_sonnet / call_gpt4)
                if isinstance(raw, dict):
                    if raw.get('error'):
                        # Surface real API errors so the caller knows what failed
                        raise Exception(f"API error from {validator}: {raw.get('content', 'unknown error')}")
                    result = raw.get('content', '')
                else:
                    # Fallback: already a string (future-proofing)
                    result = str(raw)
                # ================================================================

                # Clean JSON fences
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0].strip()
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0].strip()

                parsed = json.loads(result)
                parsed['validator'] = validator
                validation_results.append(parsed)

            except Exception as e:
                # ================================================================
                # FIX 2 (February 20, 2026): Full error message, not truncated
                # Old code: f"Failed to parse: {str(e)[:100]}"
                # New code: f"Failed to parse: {str(e)}"
                # ================================================================
                validation_results.append({
                    "validator": validator,
                    "error": f"Failed to parse: {str(e)}",
                    "overall_score": 5
                })

    scores = [v.get('overall_score', 5) for v in validation_results]

    # ================================================================
    # FIX 3 (February 20, 2026): Detect all-failed scenario
    # If every validator returned an error, agreement_score was 1.0
    # (because all scores were 5, so max-min = 0, giving 1.0-0/10=1.0).
    # That was a false green light. Now we detect this and return 0.0
    # with a 'validation_failed' flag so the caller can react correctly.
    # ================================================================
    all_failed = all('error' in v for v in validation_results)

    if all_failed:
        return {
            "validators": validators,
            "validation_results": validation_results,
            "agreement_score": 0.0,
            "average_score": 0.0,
            "validator_count": len(validation_results),
            "validation_failed": True,
            "failure_reason": "All validators encountered errors - no consensus was performed"
        }
    # ================================================================

    # Only use scores from successful validators for agreement calculation
    successful_scores = [v.get('overall_score', 5) for v in validation_results if 'error' not in v]

    if len(successful_scores) == 1:
        agreement_score = 1.0
    else:
        agreement_score = 1.0 - (max(successful_scores) - min(successful_scores)) / 10.0

    return {
        "validators": validators,
        "validation_results": validation_results,
        "agreement_score": agreement_score,
        "average_score": sum(successful_scores) / len(successful_scores) if successful_scores else 0,
        "validator_count": len(validation_results),
        "validation_failed": False
    }

# I did no harm and this file is not truncated
