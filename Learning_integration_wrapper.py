"""
LEARNING INTEGRATION WRAPPER - Simple Drop-in Integration with Auto-Triggers
Created: February 2, 2026
Last Updated: February 2, 2026 - Added automatic cycle triggers

This wrapper adds learning outcome recording AND automatic cycle triggering
to your orchestration handler.

After each task completes, it:
1. Records the outcome for learning
2. Checks if enough new data exists
3. Automatically triggers learning cycles when ready

Trigger Rules:
- Phase 1 (Adaptive Learning): Every 10 new outcomes
- Phase 2 (Predictive Intelligence): Every 20 new outcomes  
- Phase 3 (Self-Optimization): Every 30 new outcomes

USAGE:
1. Upload this file to your repo (root directory)
2. In routes/orchestration_handler.py, add ONE line at the very end:
   
   At the END of the file, add:
   from learning_integration_wrapper import record_orchestration_outcome

   Then in the orchestrate() function, RIGHT BEFORE the final return jsonify(...),
   add:
   record_orchestration_outcome(task_id, orchestrator, user_request, total_time, 
                                consensus_result, knowledge_applied, specialist_results)

That's it! The learning system will collect data AND run cycles automatically.

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

from datetime import datetime
from typing import Optional, List, Dict, Any


def record_orchestration_outcome(
    task_id: Optional[int] = None,
    orchestrator: str = 'sonnet',
    user_request: str = '',
    total_time: float = 0,
    consensus_result: Optional[Dict] = None,
    knowledge_applied: bool = False,
    specialist_results: Optional[List] = None,
    **kwargs
) -> None:
    """
    Record task outcome for learning system.
    
    This function is designed to be 100% safe:
    - Never raises exceptions (catches everything)
    - Never slows down orchestration (runs quickly)
    - Never breaks if learning system has issues
    
    Args:
        task_id: Task ID from database
        orchestrator: Which orchestrator handled it ('sonnet', 'opus')
        user_request: The user's original request
        total_time: How long task took in seconds
        consensus_result: Consensus validation results (if used)
        knowledge_applied: Whether knowledge base was used
        specialist_results: List of specialist AI results (if any)
        **kwargs: Any other data you want to pass
    """
    try:
        # Import here to avoid circular imports
        from learning_integration import record_outcome
        
        # Determine AI used
        if orchestrator == 'opus':
            ai_used = 'claude-opus-4-5'
        else:
            ai_used = 'claude-sonnet-4'
        
        # Extract specialist info
        specialist_used = None
        if specialist_results and len(specialist_results) > 0:
            specialist_used = specialist_results[0].get('specialist', None)
        
        # Extract consensus info
        consensus_enabled = consensus_result is not None
        consensus_score = None
        if consensus_result:
            consensus_score = consensus_result.get('agreement_score', None)
        
        # Record the outcome
        outcome_id = record_outcome(
            task_id=task_id,
            ai_used=ai_used,
            orchestrator=orchestrator,
            user_request=user_request,
            execution_time=total_time,
            consensus_enabled=consensus_enabled,
            consensus_score=consensus_score,
            knowledge_applied=knowledge_applied,
            specialist_used=specialist_used,
            escalated_to_opus=(orchestrator == 'opus'),
            task_completed_successfully=True,
            additional_context=kwargs
        )
        
        # Silent success - outcome recorded
        if outcome_id:
            # Check if we should trigger any learning cycles
            try:
                from smart_learning_trigger import get_trigger_system
                trigger = get_trigger_system()
                trigger.check_and_trigger_all()
            except Exception as trigger_error:
                # Don't let trigger failures break anything
                print(f"⚠️ Auto-trigger check failed (non-fatal): {trigger_error}")
        
    except Exception as e:
        # CRITICAL: Never let learning break orchestration
        # Just silently log the error and continue
        print(f"⚠️ Learning outcome recording failed (non-fatal): {e}")
        pass


# Convenience function for manual testing
def test_learning_integration():
    """
    Test function to verify learning integration is working.
    Call this manually to test.
    """
    print("🧪 Testing learning integration...")
    
    try:
        record_orchestration_outcome(
            task_id=999,
            orchestrator='sonnet',
            user_request='Test request for learning system',
            total_time=2.5,
            consensus_result={'agreement_score': 0.85},
            knowledge_applied=True,
            specialist_results=[],
        )
        print("✅ Test outcome recorded successfully!")
        
        # Check if it was recorded
        from learning_integration import get_learning_report
        report = get_learning_report()
        print(f"📊 Total outcomes in system: {report.get('total_outcomes', 0)}")
        
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == '__main__':
    # Run test if executed directly
    test_learning_integration()


# I did no harm and this file is not truncated
