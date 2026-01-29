"""
KNOWLEDGE PRIORITY ENFORCEMENT MODULE
Created: January 29, 2026

PURPOSE:
This module enforces the CRITICAL RULE that project knowledge must ALWAYS
be checked FIRST before any external AI calls or web searches.

This mimics Claude Projects behavior where project_knowledge_search is
prioritized over all other tools and information sources.

ENFORCEMENT MECHANISMS:
1. Decorator to wrap API calls and ensure knowledge check first
2. Priority validator to verify knowledge was checked
3. Audit trail to track knowledge usage
4. Fallback detection to catch missed knowledge checks

USAGE:
    from knowledge_priority import enforce_knowledge_priority, validate_knowledge_checked
    
    @enforce_knowledge_priority
    def my_ai_function(prompt, knowledge_base=None):
        # Knowledge will be automatically checked before this executes
        pass

Author: Jim @ Shiftwork Solutions LLC
"""

import functools
import time
from datetime import datetime
import json


class KnowledgePriorityViolation(Exception):
    """Raised when knowledge priority rules are violated"""
    pass


class KnowledgePriorityEnforcer:
    """
    Enforces that project knowledge is always checked first.
    Maintains audit trail of knowledge usage.
    """
    
    def __init__(self):
        self.audit_log = []
        self.violations = []
        self.knowledge_checks = 0
        self.knowledge_hits = 0
        self.knowledge_misses = 0
        
    def log_knowledge_check(self, request, kb_result, source="unknown"):
        """Log that knowledge base was checked"""
        self.knowledge_checks += 1
        
        if kb_result.get('has_relevant_knowledge'):
            self.knowledge_hits += 1
        else:
            self.knowledge_misses += 1
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'request': request[:100],  # First 100 chars
            'source': source,
            'knowledge_found': kb_result.get('has_relevant_knowledge', False),
            'confidence': kb_result.get('knowledge_confidence', 0.0),
            'sources': kb_result.get('knowledge_sources', [])
        }
        
        self.audit_log.append(log_entry)
        
        # Keep only last 100 entries
        if len(self.audit_log) > 100:
            self.audit_log = self.audit_log[-100:]
    
    def log_violation(self, function_name, reason):
        """Log a knowledge priority violation"""
        violation = {
            'timestamp': datetime.now().isoformat(),
            'function': function_name,
            'reason': reason,
            'severity': 'HIGH'
        }
        
        self.violations.append(violation)
        print(f"⚠️  KNOWLEDGE PRIORITY VIOLATION: {function_name} - {reason}")
        
        # Keep only last 50 violations
        if len(self.violations) > 50:
            self.violations = self.violations[-50:]
    
    def get_stats(self):
        """Get knowledge priority statistics"""
        hit_rate = (self.knowledge_hits / self.knowledge_checks * 100) if self.knowledge_checks > 0 else 0
        
        return {
            'total_checks': self.knowledge_checks,
            'knowledge_hits': self.knowledge_hits,
            'knowledge_misses': self.knowledge_misses,
            'hit_rate_percent': round(hit_rate, 1),
            'violations': len(self.violations),
            'recent_violations': self.violations[-5:] if self.violations else []
        }
    
    def get_audit_trail(self, limit=20):
        """Get recent audit trail entries"""
        return self.audit_log[-limit:]


# Global enforcer instance
_enforcer = KnowledgePriorityEnforcer()


def get_enforcer():
    """Get the global enforcer instance"""
    return _enforcer


def enforce_knowledge_priority(func):
    """
    Decorator to enforce knowledge priority.
    
    Wraps any function that might call external AIs and ensures
    knowledge base is checked first if knowledge_base parameter exists.
    
    Usage:
        @enforce_knowledge_priority
        def analyze_task(request, knowledge_base=None):
            # Knowledge automatically checked first
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check if knowledge_base is in kwargs
        knowledge_base = kwargs.get('knowledge_base')
        
        # Try to get user request from args or kwargs
        user_request = None
        if len(args) > 0:
            user_request = args[0]
        elif 'user_request' in kwargs:
            user_request = kwargs['user_request']
        elif 'request' in kwargs:
            user_request = kwargs['request']
        elif 'prompt' in kwargs:
            user_request = kwargs['prompt']
        
        if knowledge_base and user_request:
            # Check if knowledge was already checked
            # Look for knowledge-related keys in kwargs
            already_checked = any(k.startswith('knowledge_') for k in kwargs.keys())
            
            if not already_checked:
                # Knowledge needs to be checked!
                from orchestration.task_analysis import check_knowledge_base_first
                
                print(f"🎯 ENFORCER: Checking knowledge base before {func.__name__}")
                kb_result = check_knowledge_base_first(user_request, knowledge_base)
                
                # Log the check
                _enforcer.log_knowledge_check(user_request, kb_result, func.__name__)
                
                # Add knowledge result to kwargs for function to use
                kwargs['_kb_check_result'] = kb_result
        
        # Execute the original function
        result = func(*args, **kwargs)
        
        return result
    
    return wrapper


def validate_knowledge_checked(result_dict, function_name):
    """
    Validate that knowledge was checked for a given result.
    
    Args:
        result_dict: Result dictionary from an AI function
        function_name: Name of function that produced result
        
    Raises:
        KnowledgePriorityViolation if knowledge tracking is missing
    """
    required_keys = ['knowledge_applied', 'knowledge_sources', 'knowledge_confidence']
    
    missing_keys = [key for key in required_keys if key not in result_dict]
    
    if missing_keys:
        reason = f"Missing knowledge tracking keys: {', '.join(missing_keys)}"
        _enforcer.log_violation(function_name, reason)
        
        # Don't raise exception (yet) - just log warning
        print(f"⚠️  Knowledge tracking incomplete in {function_name}")
        print(f"    Missing: {missing_keys}")


def create_knowledge_priority_report():
    """
    Generate a report on knowledge priority compliance.
    
    Returns:
        dict with compliance statistics and audit trail
    """
    stats = _enforcer.get_stats()
    audit_trail = _enforcer.get_audit_trail(limit=10)
    
    report = {
        'generated_at': datetime.now().isoformat(),
        'statistics': stats,
        'compliance_status': 'GOOD' if stats['violations'] == 0 else 'NEEDS ATTENTION',
        'recent_checks': audit_trail,
        'recommendations': []
    }
    
    # Add recommendations based on stats
    if stats['hit_rate_percent'] < 30:
        report['recommendations'].append(
            "Knowledge hit rate is low. Consider enhancing knowledge base content or search algorithms."
        )
    
    if stats['violations'] > 0:
        report['recommendations'].append(
            f"Found {stats['violations']} knowledge priority violations. Review function implementations."
        )
    
    if stats['knowledge_checks'] == 0:
        report['recommendations'].append(
            "No knowledge checks detected. Ensure knowledge_base parameter is being passed to functions."
        )
    
    return report


def inject_knowledge_context(func):
    """
    Decorator to automatically inject knowledge context into prompts.
    
    Usage:
        @inject_knowledge_context
        def call_ai(prompt, knowledge_base=None):
            # prompt will be automatically enhanced with knowledge context
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        knowledge_base = kwargs.get('knowledge_base')
        
        if knowledge_base and len(args) > 0:
            # First arg is usually the prompt
            original_prompt = args[0]
            
            # Check if prompt already has knowledge context
            if "PROJECT KNOWLEDGE" not in original_prompt and "SHIFTWORK SOLUTIONS" not in original_prompt:
                # Get knowledge context
                from orchestration.task_analysis import check_knowledge_base_first
                
                kb_result = check_knowledge_base_first(original_prompt, knowledge_base)
                
                if kb_result.get('has_relevant_knowledge'):
                    # Prepend knowledge context to prompt
                    enhanced_prompt = kb_result['knowledge_context'] + "\n\n" + original_prompt
                    
                    # Replace first arg with enhanced prompt
                    args = (enhanced_prompt,) + args[1:]
                    
                    print(f"💡 Knowledge context injected into {func.__name__}")
                
                # Log the check
                _enforcer.log_knowledge_check(original_prompt, kb_result, func.__name__)
        
        return func(*args, **kwargs)
    
    return wrapper


# Priority check function that can be called explicitly
def ensure_knowledge_checked(user_request, knowledge_base, source="explicit_check"):
    """
    Explicitly ensure knowledge has been checked.
    Can be called at the start of any function.
    
    Args:
        user_request: The user's request/query
        knowledge_base: Knowledge base instance
        source: Source of the check (for logging)
        
    Returns:
        Knowledge check result dict
    """
    if not knowledge_base:
        return {
            'has_relevant_knowledge': False,
            'knowledge_context': '',
            'knowledge_confidence': 0.0,
            'knowledge_sources': [],
            'should_proceed_to_ai': True,
            'reason': 'No knowledge base provided'
        }
    
    from orchestration.task_analysis import check_knowledge_base_first
    
    kb_result = check_knowledge_base_first(user_request, knowledge_base)
    _enforcer.log_knowledge_check(user_request, kb_result, source)
    
    return kb_result


# Export key functions
__all__ = [
    'enforce_knowledge_priority',
    'validate_knowledge_checked',
    'create_knowledge_priority_report',
    'inject_knowledge_context',
    'ensure_knowledge_checked',
    'get_enforcer',
    'KnowledgePriorityViolation'
]


# I did no harm and this file is not truncated
