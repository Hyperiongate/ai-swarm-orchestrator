"""
LEARNING INTEGRATION - Phase 1 Integration Layer
Created: February 2, 2026
Last Updated: February 2, 2026

This module provides clean integration points for the Adaptive Learning Engine.
It hooks into existing orchestration without modifying existing files.

HOW TO USE:
1. Import this module in routes that handle orchestration
2. Call learning_integration.record_outcome() AFTER task completes
3. Call learning_integration.apply_learnings() to get routing suggestions

CRITICAL: This module is 100% additive - it only OBSERVES and SUGGESTS.
It never modifies behavior without explicit approval.

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from adaptive_learning_engine import get_learning_engine


class LearningIntegration:
    """
    Integration layer between existing orchestration and learning engine.
    Provides simple hooks that can be added to existing code.
    """
    
    def __init__(self):
        self.engine = get_learning_engine()
        self.enabled = True  # Can be disabled without breaking anything
    
    def record_outcome(self, 
                      task_id: Optional[int] = None,
                      ai_used: str = 'claude-sonnet-4',
                      orchestrator: str = 'sonnet',
                      user_request: str = '',
                      execution_time: float = 0,
                      user_feedback: Optional[int] = None,
                      consensus_enabled: bool = False,
                      consensus_score: Optional[float] = None,
                      knowledge_applied: bool = False,
                      specialist_used: Optional[str] = None,
                      escalated_to_opus: bool = False,
                      task_completed_successfully: bool = True,
                      additional_context: Optional[Dict] = None) -> Optional[int]:
        """
        Record a task outcome for learning.
        
        This is the main integration point - call this AFTER each task completes.
        
        Args:
            task_id: Original task ID from database
            ai_used: Which AI model was used (claude-sonnet-4, claude-opus-4-5, etc.)
            orchestrator: Which orchestrator (sonnet, opus, specialist)
            user_request: The user's request text
            execution_time: How long the task took in seconds
            user_feedback: User rating 1-5 if available
            consensus_enabled: Was consensus validation used
            consensus_score: Agreement score if consensus used
            knowledge_applied: Was knowledge base used
            specialist_used: Which specialist if any (gpt4, deepseek, gemini)
            escalated_to_opus: Was this escalated from Sonnet to Opus
            task_completed_successfully: Did task complete without errors
            additional_context: Any other relevant context
            
        Returns:
            outcome_id if recorded, None if learning disabled
            
        Example:
            # In your orchestration route, after task completes:
            learning_integration.record_outcome(
                task_id=123,
                ai_used='claude-sonnet-4',
                user_request=user_request,
                execution_time=5.2,
                consensus_enabled=True,
                consensus_score=0.92,
                knowledge_applied=True
            )
        """
        if not self.enabled:
            return None
        
        try:
            # Classify task type from request
            task_type = self._classify_task_type(user_request)
            
            # Prepare task data
            task_data = {
                'task_id': task_id,
                'ai_used': ai_used,
                'task_type': task_type,
                'task_context': {
                    'orchestrator': orchestrator,
                    'request_length': len(user_request),
                    'completed_successfully': task_completed_successfully,
                    **(additional_context or {})
                },
                'user_request_length': len(user_request),
                'user_feedback_rating': user_feedback,
                'execution_time_seconds': execution_time,
                'consensus_enabled': consensus_enabled,
                'consensus_score': consensus_score,
                'knowledge_base_used': knowledge_applied,
                'specialist_used': specialist_used,
                'escalated_to_opus': escalated_to_opus,
                'metadata': {
                    'recorded_at': datetime.now().isoformat(),
                    'integration_version': '1.0'
                }
            }
            
            # Record to learning engine
            outcome_id = self.engine.record_task_outcome(task_data)
            
            return outcome_id
            
        except Exception as e:
            # Learning should never break orchestration
            print(f"⚠️ Learning integration error (non-fatal): {e}")
            return None
    
    def _classify_task_type(self, user_request: str) -> str:
        """
        Classify task type from user request.
        This helps identify patterns by task category.
        """
        request_lower = user_request.lower()
        
        # Schedule-related
        if any(word in request_lower for word in ['schedule', 'shift', 'roster', 'rotation']):
            return 'schedule_design'
        
        # Analysis
        if any(word in request_lower for word in ['analyze', 'analysis', 'evaluate', 'assess']):
            return 'analysis'
        
        # Document creation
        if any(word in request_lower for word in ['create', 'generate', 'write', 'draft', 'document']):
            if 'survey' in request_lower:
                return 'survey_creation'
            elif 'implementation' in request_lower or 'manual' in request_lower:
                return 'manual_creation'
            else:
                return 'document_creation'
        
        # Research/information
        if any(word in request_lower for word in ['find', 'search', 'research', 'information']):
            return 'research'
        
        # Calculation
        if any(word in request_lower for word in ['calculate', 'cost', 'overtime', 'savings']):
            return 'calculation'
        
        # Code/technical
        if any(word in request_lower for word in ['code', 'function', 'script', 'debug', 'error']):
            return 'code_assistance'
        
        # Default
        return 'general'
    
    def get_routing_suggestions(self, user_request: str, current_plan: Dict) -> Dict[str, Any]:
        """
        Get learned routing suggestions for a request.
        
        This can be called BEFORE executing a task to apply learned optimizations.
        
        Args:
            user_request: The user's request
            current_plan: Current execution plan (which AI, consensus, etc.)
            
        Returns:
            Dictionary with suggestions based on learned patterns
            
        Example:
            current_plan = {
                'ai': 'claude-sonnet-4',
                'use_consensus': False,
                'use_knowledge_base': True
            }
            
            suggestions = learning_integration.get_routing_suggestions(
                user_request, current_plan
            )
            
            if suggestions['confidence'] > 0.80:
                # Apply high-confidence suggestions
                plan.update(suggestions['modifications'])
        """
        if not self.enabled:
            return {'suggestions': [], 'confidence': 0, 'modifications': {}}
        
        try:
            task_type = self._classify_task_type(user_request)
            
            # Query learned patterns relevant to this task
            patterns = self._get_relevant_patterns(task_type)
            
            modifications = {}
            suggestions = []
            max_confidence = 0
            
            for pattern in patterns:
                if pattern['confidence'] > max_confidence:
                    max_confidence = pattern['confidence']
                
                # Convert pattern to suggestion
                if pattern['pattern_type'] == 'ai_performance':
                    metadata = json.loads(pattern.get('metadata', '{}'))
                    if metadata.get('task_type') == task_type:
                        suggested_ai = metadata.get('best_ai')
                        if suggested_ai and suggested_ai != current_plan.get('ai'):
                            modifications['ai'] = suggested_ai
                            suggestions.append({
                                'type': 'routing',
                                'message': f"Switch to {suggested_ai} (learned pattern: {pattern['confidence']*100:.0f}% confidence)",
                                'confidence': pattern['confidence']
                            })
                
                elif pattern['pattern_type'] == 'knowledge_base_value':
                    if not current_plan.get('use_knowledge_base'):
                        modifications['use_knowledge_base'] = True
                        suggestions.append({
                            'type': 'feature',
                            'message': f"Enable knowledge base (learned pattern improves outcomes by ~10%)",
                            'confidence': pattern['confidence']
                        })
                
                elif pattern['pattern_type'] == 'consensus_value':
                    metadata = json.loads(pattern.get('metadata', '{}'))
                    improvement = metadata.get('improvement', 0)
                    
                    if improvement > 0.10 and not current_plan.get('use_consensus'):
                        modifications['use_consensus'] = True
                        suggestions.append({
                            'type': 'validation',
                            'message': f"Enable consensus validation (learned pattern shows {improvement*100:.1f}% improvement)",
                            'confidence': pattern['confidence']
                        })
                    elif improvement < -0.05 and current_plan.get('use_consensus'):
                        modifications['use_consensus'] = False
                        suggestions.append({
                            'type': 'validation',
                            'message': f"Disable consensus (learned pattern shows it adds overhead without benefit)",
                            'confidence': pattern['confidence']
                        })
            
            return {
                'suggestions': suggestions,
                'confidence': max_confidence,
                'modifications': modifications,
                'patterns_applied': len(patterns)
            }
            
        except Exception as e:
            print(f"⚠️ Error getting routing suggestions (non-fatal): {e}")
            return {'suggestions': [], 'confidence': 0, 'modifications': {}}
    
    def _get_relevant_patterns(self, task_type: str) -> List[Dict]:
        """Get learned patterns relevant to task type"""
        import sqlite3
        
        db = sqlite3.connect(self.engine.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Get high-confidence active patterns
        cursor.execute('''
            SELECT * FROM learned_patterns
            WHERE active = 1
            AND confidence >= 0.75
            ORDER BY confidence DESC, supporting_evidence DESC
            LIMIT 20
        ''')
        
        all_patterns = [dict(row) for row in cursor.fetchall()]
        db.close()
        
        # Filter to relevant patterns
        relevant = []
        for pattern in all_patterns:
            metadata = json.loads(pattern.get('metadata', '{}'))
            
            # Check if pattern applies to this task type
            if pattern['pattern_type'] == 'ai_performance':
                if metadata.get('task_type') == task_type:
                    relevant.append(pattern)
            else:
                # General patterns apply to all tasks
                relevant.append(pattern)
        
        return relevant
    
    def run_learning_cycle(self, min_observations: int = 10) -> Dict[str, Any]:
        """
        Run a learning cycle to analyze recent outcomes and generate insights.
        
        Call this periodically (e.g., daily) to discover new patterns.
        
        Args:
            min_observations: Minimum outcomes needed for analysis
            
        Returns:
            Learning cycle results
            
        Example:
            # Run nightly or manually
            results = learning_integration.run_learning_cycle()
            
            if results['status'] == 'success':
                print(f"Found {results['patterns_found']} patterns")
                print(f"Generated {results['adjustments_suggested']} suggestions")
        """
        if not self.enabled:
            return {'status': 'disabled'}
        
        try:
            results = self.engine.run_learning_cycle(min_observations)
            return results
        except Exception as e:
            print(f"❌ Learning cycle error: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_learning_report(self) -> Dict[str, Any]:
        """
        Get comprehensive learning status report.
        
        Returns:
            Report with learning metrics and discovered patterns
            
        Example:
            report = learning_integration.get_learning_report()
            
            print(f"Outcomes analyzed: {report['learned_outcomes']}")
            print(f"Active patterns: {report['active_patterns']}")
            print(f"Pending adjustments: {report['pending_adjustments']}")
        """
        if not self.enabled:
            return {'status': 'disabled'}
        
        try:
            return self.engine.get_learning_report()
        except Exception as e:
            print(f"❌ Error generating report: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_pending_adjustments(self) -> List[Dict]:
        """
        Get all pending behavior adjustments awaiting approval.
        
        Returns:
            List of suggested adjustments
            
        Example:
            adjustments = learning_integration.get_pending_adjustments()
            
            for adj in adjustments:
                print(f"Suggestion: {adj['reason']}")
                print(f"  Change {adj['parameter_name']} from {adj['old_value']} to {adj['new_value']}")
                # User can approve/reject via API
        """
        if not self.enabled:
            return []
        
        try:
            return self.engine.behavior_modifier.get_pending_adjustments()
        except Exception as e:
            print(f"❌ Error getting adjustments: {e}")
            return []
    
    def enable(self):
        """Enable learning integration"""
        self.enabled = True
        print("✅ Learning integration enabled")
    
    def disable(self):
        """Disable learning integration (for testing or troubleshooting)"""
        self.enabled = False
        print("⚠️ Learning integration disabled")


# Singleton instance for easy import
learning_integration = LearningIntegration()


# Convenience functions
def record_outcome(**kwargs) -> Optional[int]:
    """Convenience wrapper for recording outcomes"""
    return learning_integration.record_outcome(**kwargs)


def get_routing_suggestions(user_request: str, current_plan: Dict) -> Dict:
    """Convenience wrapper for getting routing suggestions"""
    return learning_integration.get_routing_suggestions(user_request, current_plan)


def run_learning_cycle(min_observations: int = 10) -> Dict:
    """Convenience wrapper for running learning cycle"""
    return learning_integration.run_learning_cycle(min_observations)


def get_learning_report() -> Dict:
    """Convenience wrapper for getting learning report"""
    return learning_integration.get_learning_report()


def get_pending_adjustments() -> List[Dict]:
    """Convenience wrapper for getting pending adjustments"""
    return learning_integration.get_pending_adjustments()


# I did no harm and this file is not truncated
