"""
Swarm Self-Evaluation Engine
Created: January 25, 2026
Last Updated: January 25, 2026

PURPOSE:
Weekly self-review system for the AI Swarm Orchestrator that:
1. Evaluates internal performance against benchmarks
2. Tracks emerging AI models and capabilities
3. Identifies gaps in current AI stack
4. Generates actionable recommendations
5. Produces "State of the Swarm" reports

COMPONENTS:
- Performance Evaluator: Analyzes swarm metrics from database
- Market Scanner: Searches for new AI developments (requires web search)
- Gap Analyzer: Compares current capabilities to emerging standards
- Recommendation Engine: Prioritizes improvements
- Report Generator: Creates weekly summary reports

INTEGRATION:
- Uses existing database tables (tasks, consensus_validations, specialist_calls, etc.)
- Uses existing AI clients (call_claude_sonnet, call_gpt4, etc.)
- Stores evaluations in new swarm_evaluations table
- Can be triggered manually or scheduled weekly

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Import database functions
from database import get_db

# Import AI clients
from orchestration.ai_clients import call_claude_sonnet, call_gpt4


# ============================================================================
# PERFORMANCE METRICS COLLECTOR
# ============================================================================

class PerformanceCollector:
    """Collects and analyzes swarm performance metrics from the database."""
    
    def __init__(self):
        self.metrics = {}
    
    def collect_weekly_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Collect performance metrics for the past week.
        
        Returns dict with:
        - task_metrics: Total tasks, success rate, avg execution time
        - consensus_metrics: Agreement rates, validation counts
        - specialist_metrics: Which AIs used most, success by specialist
        - escalation_metrics: How often Sonnet escalated to Opus
        - conversation_metrics: Engagement stats
        """
        db = get_db()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        metrics = {
            'period_start': cutoff_date,
            'period_end': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'days_analyzed': days
        }
        
        # Task Metrics
        try:
            total_tasks = db.execute(
                'SELECT COUNT(*) FROM tasks WHERE created_at >= ?', 
                (cutoff_date,)
            ).fetchone()[0]
            
            completed_tasks = db.execute(
                'SELECT COUNT(*) FROM tasks WHERE created_at >= ? AND status = ?',
                (cutoff_date, 'completed')
            ).fetchone()[0]
            
            failed_tasks = db.execute(
                'SELECT COUNT(*) FROM tasks WHERE created_at >= ? AND status = ?',
                (cutoff_date, 'failed')
            ).fetchone()[0]
            
            avg_execution_time = db.execute(
                'SELECT AVG(execution_time_seconds) FROM tasks WHERE created_at >= ? AND execution_time_seconds IS NOT NULL',
                (cutoff_date,)
            ).fetchone()[0]
            
            avg_confidence = db.execute(
                'SELECT AVG(confidence) FROM tasks WHERE created_at >= ? AND confidence IS NOT NULL',
                (cutoff_date,)
            ).fetchone()[0]
            
            metrics['tasks'] = {
                'total': total_tasks or 0,
                'completed': completed_tasks or 0,
                'failed': failed_tasks or 0,
                'success_rate': round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0,
                'avg_execution_time_seconds': round(avg_execution_time, 2) if avg_execution_time else 0,
                'avg_confidence': round(avg_confidence, 3) if avg_confidence else 0
            }
        except Exception as e:
            metrics['tasks'] = {'error': str(e)}
        
        # Consensus Metrics
        try:
            total_consensus = db.execute(
                'SELECT COUNT(*) FROM consensus_validations WHERE created_at >= ?',
                (cutoff_date,)
            ).fetchone()[0]
            
            achieved_consensus = db.execute(
                'SELECT COUNT(*) FROM consensus_validations WHERE created_at >= ? AND consensus_achieved = 1',
                (cutoff_date,)
            ).fetchone()[0]
            
            avg_agreement = db.execute(
                'SELECT AVG(agreement_score) FROM consensus_validations WHERE created_at >= ? AND agreement_score IS NOT NULL',
                (cutoff_date,)
            ).fetchone()[0]
            
            metrics['consensus'] = {
                'total_validations': total_consensus or 0,
                'consensus_achieved': achieved_consensus or 0,
                'consensus_rate': round((achieved_consensus / total_consensus * 100), 2) if total_consensus > 0 else 0,
                'avg_agreement_score': round(avg_agreement, 3) if avg_agreement else 0
            }
        except Exception as e:
            metrics['consensus'] = {'error': str(e)}
        
        # Specialist Usage Metrics
        try:
            specialist_usage = db.execute('''
                SELECT specialist_name, COUNT(*) as usage_count, 
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                       AVG(execution_time_seconds) as avg_time
                FROM specialist_calls 
                WHERE created_at >= ?
                GROUP BY specialist_name
                ORDER BY usage_count DESC
            ''', (cutoff_date,)).fetchall()
            
            specialists = []
            for row in specialist_usage:
                specialists.append({
                    'name': row['specialist_name'],
                    'usage_count': row['usage_count'],
                    'success_count': row['success_count'] or 0,
                    'success_rate': round((row['success_count'] / row['usage_count'] * 100), 2) if row['usage_count'] > 0 else 0,
                    'avg_execution_time': round(row['avg_time'], 2) if row['avg_time'] else 0
                })
            
            metrics['specialists'] = specialists
        except Exception as e:
            metrics['specialists'] = {'error': str(e)}
        
        # Escalation Metrics
        try:
            total_escalations = db.execute(
                'SELECT COUNT(*) FROM escalations WHERE created_at >= ?',
                (cutoff_date,)
            ).fetchone()[0]
            
            avg_sonnet_confidence_at_escalation = db.execute(
                'SELECT AVG(sonnet_confidence) FROM escalations WHERE created_at >= ? AND sonnet_confidence IS NOT NULL',
                (cutoff_date,)
            ).fetchone()[0]
            
            escalation_rate = 0
            if metrics['tasks'].get('total', 0) > 0:
                escalation_rate = round((total_escalations / metrics['tasks']['total'] * 100), 2)
            
            metrics['escalations'] = {
                'total': total_escalations or 0,
                'escalation_rate': escalation_rate,
                'avg_sonnet_confidence_at_escalation': round(avg_sonnet_confidence_at_escalation, 3) if avg_sonnet_confidence_at_escalation else 0
            }
        except Exception as e:
            metrics['escalations'] = {'error': str(e)}
        
        # Orchestrator Distribution
        try:
            orchestrator_usage = db.execute('''
                SELECT assigned_orchestrator, COUNT(*) as count
                FROM tasks 
                WHERE created_at >= ? AND assigned_orchestrator IS NOT NULL
                GROUP BY assigned_orchestrator
            ''', (cutoff_date,)).fetchall()
            
            orchestrators = {}
            for row in orchestrator_usage:
                orchestrators[row['assigned_orchestrator'] or 'unknown'] = row['count']
            
            metrics['orchestrator_distribution'] = orchestrators
        except Exception as e:
            metrics['orchestrator_distribution'] = {'error': str(e)}
        
        # Conversation Metrics
        try:
            total_conversations = db.execute(
                'SELECT COUNT(*) FROM conversations WHERE created_at >= ?',
                (cutoff_date,)
            ).fetchone()[0]
            
            total_messages = db.execute(
                'SELECT COUNT(*) FROM conversation_messages WHERE created_at >= ?',
                (cutoff_date,)
            ).fetchone()[0]
            
            avg_messages_per_conv = 0
            if total_conversations > 0:
                avg_messages_per_conv = round(total_messages / total_conversations, 2)
            
            metrics['conversations'] = {
                'total': total_conversations or 0,
                'total_messages': total_messages or 0,
                'avg_messages_per_conversation': avg_messages_per_conv
            }
        except Exception as e:
            metrics['conversations'] = {'error': str(e)}
        
        # Document Generation Metrics
        try:
            total_documents = db.execute(
                'SELECT COUNT(*) FROM generated_documents WHERE created_at >= ? AND is_deleted = 0',
                (cutoff_date,)
            ).fetchone()[0]
            
            doc_types = db.execute('''
                SELECT document_type, COUNT(*) as count
                FROM generated_documents
                WHERE created_at >= ? AND is_deleted = 0
                GROUP BY document_type
            ''', (cutoff_date,)).fetchall()
            
            by_type = {row['document_type']: row['count'] for row in doc_types}
            
            metrics['documents'] = {
                'total_generated': total_documents or 0,
                'by_type': by_type
            }
        except Exception as e:
            metrics['documents'] = {'error': str(e)}
        
        # User Feedback Metrics
        try:
            feedback_count = db.execute(
                'SELECT COUNT(*) FROM user_feedback WHERE submitted_at >= ?',
                (cutoff_date,)
            ).fetchone()[0]
            
            avg_overall = db.execute(
                'SELECT AVG(overall_rating) FROM user_feedback WHERE submitted_at >= ?',
                (cutoff_date,)
            ).fetchone()[0]
            
            avg_quality = db.execute(
                'SELECT AVG(quality_rating) FROM user_feedback WHERE submitted_at >= ?',
                (cutoff_date,)
            ).fetchone()[0]
            
            avg_accuracy = db.execute(
                'SELECT AVG(accuracy_rating) FROM user_feedback WHERE submitted_at >= ?',
                (cutoff_date,)
            ).fetchone()[0]
            
            avg_usefulness = db.execute(
                'SELECT AVG(usefulness_rating) FROM user_feedback WHERE submitted_at >= ?',
                (cutoff_date,)
            ).fetchone()[0]
            
            metrics['feedback'] = {
                'total_submissions': feedback_count or 0,
                'avg_overall_rating': round(avg_overall, 2) if avg_overall else 0,
                'avg_quality_rating': round(avg_quality, 2) if avg_quality else 0,
                'avg_accuracy_rating': round(avg_accuracy, 2) if avg_accuracy else 0,
                'avg_usefulness_rating': round(avg_usefulness, 2) if avg_usefulness else 0
            }
        except Exception as e:
            metrics['feedback'] = {'error': str(e)}
        
        # Knowledge Base Usage
        try:
            knowledge_used_count = db.execute(
                'SELECT COUNT(*) FROM tasks WHERE created_at >= ? AND knowledge_used = 1',
                (cutoff_date,)
            ).fetchone()[0]
            
            knowledge_usage_rate = 0
            if metrics['tasks'].get('total', 0) > 0:
                knowledge_usage_rate = round((knowledge_used_count / metrics['tasks']['total'] * 100), 2)
            
            metrics['knowledge_base'] = {
                'tasks_using_knowledge': knowledge_used_count or 0,
                'knowledge_usage_rate': knowledge_usage_rate
            }
        except Exception as e:
            metrics['knowledge_base'] = {'error': str(e)}
        
        db.close()
        
        self.metrics = metrics
        return metrics
    
    def identify_top_performer(self) -> Optional[str]:
        """Identify which AI performed best this week."""
        specialists = self.metrics.get('specialists', [])
        if not specialists or isinstance(specialists, dict):
            return None
        
        best = max(specialists, key=lambda x: x.get('success_rate', 0) * x.get('usage_count', 0))
        return best.get('name') if best else None
    
    def identify_problem_areas(self) -> List[str]:
        """Identify areas that need improvement."""
        problems = []
        
        # Low success rate
        tasks = self.metrics.get('tasks', {})
        if tasks.get('success_rate', 100) < 90:
            problems.append(f"Task success rate is {tasks.get('success_rate')}% (target: 90%+)")
        
        # High escalation rate
        escalations = self.metrics.get('escalations', {})
        if escalations.get('escalation_rate', 0) > 15:
            problems.append(f"Escalation rate is {escalations.get('escalation_rate')}% (target: <15%)")
        
        # Low consensus rate
        consensus = self.metrics.get('consensus', {})
        if consensus.get('consensus_rate', 100) < 80:
            problems.append(f"Consensus rate is {consensus.get('consensus_rate')}% (target: 80%+)")
        
        # Low user satisfaction
        feedback = self.metrics.get('feedback', {})
        if feedback.get('avg_overall_rating', 5) < 4.0:
            problems.append(f"Average user rating is {feedback.get('avg_overall_rating')}/5 (target: 4.0+)")
        
        # Slow execution
        if tasks.get('avg_execution_time_seconds', 0) > 30:
            problems.append(f"Average execution time is {tasks.get('avg_execution_time_seconds')}s (target: <30s)")
        
        return problems


# ============================================================================
# AI MARKET LANDSCAPE SCANNER
# ============================================================================

class MarketScanner:
    """
    Scans for new AI developments, models, and capabilities.
    Uses web search when available, or AI knowledge as fallback.
    """
    
    def __init__(self):
        self.findings = []
        self.web_search_available = False
        
        # Check if Research Agent is available for web search
        try:
            from research_agent import get_research_agent
            ra = get_research_agent()
            self.web_search_available = ra.is_available
            self.research_agent = ra if self.web_search_available else None
        except:
            self.research_agent = None
    
    def scan_ai_landscape(self) -> Dict[str, Any]:
        """
        Scan for recent AI developments relevant to the swarm.
        
        Returns:
        - new_models: Recently released AI models
        - capability_updates: Updates to existing models
        - emerging_tools: New AI tools and platforms
        - industry_specific: Developments relevant to shift work consulting
        """
        findings = {
            'scan_date': datetime.now().isoformat(),
            'web_search_used': self.web_search_available,
            'new_models': [],
            'capability_updates': [],
            'emerging_tools': [],
            'industry_specific': [],
            'raw_findings': []
        }
        
        # Define search topics
        search_topics = [
            "new AI language models released 2026",
            "Claude Anthropic updates capabilities",
            "GPT-4 OpenAI improvements",
            "AI orchestration multi-agent systems",
            "enterprise AI automation tools"
        ]
        
        if self.web_search_available and self.research_agent:
            # Use Research Agent for actual web search
            for topic in search_topics:
                try:
                    results = self.research_agent.search(topic, max_results=3)
                    if results and results.get('results'):
                        for result in results['results']:
                            findings['raw_findings'].append({
                                'topic': topic,
                                'title': result.get('title', ''),
                                'url': result.get('url', ''),
                                'snippet': result.get('snippet', '')[:200]
                            })
                except Exception as e:
                    print(f"Web search failed for '{topic}': {e}")
        
        # Use AI to analyze and categorize findings (or generate from knowledge)
        analysis_prompt = f"""
Analyze the current AI landscape for an AI orchestration system used by a shift work consulting firm.

Current System Configuration:
- Primary: Claude Sonnet (orchestration)
- Strategic: Claude Opus (complex tasks)
- Design: GPT-4 (presentations, marketing)
- Code: DeepSeek (programming)
- Multimodal: Gemini (image/video analysis)

{"Web Search Findings:" + json.dumps(findings['raw_findings'], indent=2) if findings['raw_findings'] else "No web search results available - use your knowledge of recent AI developments."}

Provide a structured analysis in this exact JSON format:
{{
    "new_models": [
        {{"name": "Model Name", "provider": "Company", "relevance": "Why it matters for our swarm", "recommendation": "Consider/Monitor/Ignore"}}
    ],
    "capability_updates": [
        {{"model": "Existing Model", "update": "What changed", "impact": "How it affects our system"}}
    ],
    "emerging_tools": [
        {{"name": "Tool Name", "purpose": "What it does", "potential_use": "How we could use it"}}
    ],
    "industry_relevant": [
        {{"development": "What happened", "relevance": "How it applies to shift work consulting AI"}}
    ],
    "overall_assessment": "Brief summary of the AI landscape health for our use case"
}}

Return ONLY the JSON, no other text.
"""
        
        try:
            response = call_claude_sonnet(analysis_prompt, max_tokens=2000)
            if response and not response.get('error'):
                content = response.get('content', '{}')
                # Extract JSON from response
                try:
                    # Try to parse directly
                    analysis = json.loads(content)
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                    import re
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_match:
                        analysis = json.loads(json_match.group(1))
                    else:
                        # Try to find JSON object in response
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            analysis = json.loads(json_match.group(0))
                        else:
                            analysis = {}
                
                findings['new_models'] = analysis.get('new_models', [])
                findings['capability_updates'] = analysis.get('capability_updates', [])
                findings['emerging_tools'] = analysis.get('emerging_tools', [])
                findings['industry_specific'] = analysis.get('industry_relevant', [])
                findings['overall_assessment'] = analysis.get('overall_assessment', '')
        except Exception as e:
            findings['analysis_error'] = str(e)
        
        self.findings = findings
        return findings


# ============================================================================
# GAP ANALYZER
# ============================================================================

class GapAnalyzer:
    """Analyzes gaps between current capabilities and emerging standards."""
    
    def __init__(self, performance_metrics: Dict, market_findings: Dict):
        self.performance = performance_metrics
        self.market = market_findings
        self.gaps = []
    
    def analyze_gaps(self) -> List[Dict[str, Any]]:
        """
        Identify gaps in current AI stack relative to:
        1. Industry best practices
        2. Emerging capabilities
        3. User needs (from feedback)
        4. Performance benchmarks
        """
        gaps = []
        
        # Performance-based gaps
        tasks = self.performance.get('tasks', {})
        if tasks.get('success_rate', 100) < 95:
            gaps.append({
                'category': 'performance',
                'gap': 'Task Success Rate Below Target',
                'current': f"{tasks.get('success_rate', 0)}%",
                'target': '95%+',
                'severity': 'high' if tasks.get('success_rate', 100) < 85 else 'medium',
                'recommendation': 'Review failed tasks for patterns, consider adding fallback AI providers'
            })
        
        if tasks.get('avg_execution_time_seconds', 0) > 20:
            gaps.append({
                'category': 'performance',
                'gap': 'Slow Average Response Time',
                'current': f"{tasks.get('avg_execution_time_seconds', 0):.1f}s",
                'target': '<20s',
                'severity': 'medium',
                'recommendation': 'Consider faster models for simple tasks, optimize prompt lengths'
            })
        
        # Consensus-based gaps
        consensus = self.performance.get('consensus', {})
        if consensus.get('avg_agreement_score', 1) < 0.8:
            gaps.append({
                'category': 'quality',
                'gap': 'Low AI Agreement Scores',
                'current': f"{consensus.get('avg_agreement_score', 0):.2f}",
                'target': '0.80+',
                'severity': 'medium',
                'recommendation': 'Review consensus validation prompts, consider additional validators'
            })
        
        # Specialist coverage gaps
        specialists = self.performance.get('specialists', [])
        if isinstance(specialists, list):
            specialist_names = [s.get('name', '').lower() for s in specialists]
            
            # Check for missing common specialists
            desired_specialists = ['gpt4', 'deepseek', 'gemini']
            for specialist in desired_specialists:
                if specialist not in specialist_names:
                    gaps.append({
                        'category': 'coverage',
                        'gap': f'Missing {specialist.upper()} Specialist',
                        'current': 'Not configured',
                        'target': 'Available',
                        'severity': 'low',
                        'recommendation': f'Consider adding {specialist.upper()} API key for expanded capabilities'
                    })
        
        # Feedback-based gaps
        feedback = self.performance.get('feedback', {})
        if feedback.get('avg_quality_rating', 5) < 4.0:
            gaps.append({
                'category': 'quality',
                'gap': 'Low Quality Ratings',
                'current': f"{feedback.get('avg_quality_rating', 0):.1f}/5",
                'target': '4.0+/5',
                'severity': 'high',
                'recommendation': 'Review low-rated tasks, improve formatting and completeness'
            })
        
        if feedback.get('avg_accuracy_rating', 5) < 4.0:
            gaps.append({
                'category': 'accuracy',
                'gap': 'Low Accuracy Ratings',
                'current': f"{feedback.get('avg_accuracy_rating', 0):.1f}/5",
                'target': '4.0+/5',
                'severity': 'high',
                'recommendation': 'Increase knowledge base usage, add fact-checking consensus'
            })
        
        # Market-based gaps (from new capabilities)
        new_models = self.market.get('new_models', [])
        for model in new_models:
            if model.get('recommendation') == 'Consider':
                gaps.append({
                    'category': 'capability',
                    'gap': f"New Model Available: {model.get('name', 'Unknown')}",
                    'current': 'Not integrated',
                    'target': 'Evaluate for integration',
                    'severity': 'low',
                    'recommendation': model.get('relevance', 'Evaluate this model for potential integration')
                })
        
        # Knowledge base usage gap
        kb = self.performance.get('knowledge_base', {})
        if kb.get('knowledge_usage_rate', 100) < 50:
            gaps.append({
                'category': 'knowledge',
                'gap': 'Low Knowledge Base Utilization',
                'current': f"{kb.get('knowledge_usage_rate', 0)}%",
                'target': '50%+',
                'severity': 'medium',
                'recommendation': 'Improve knowledge base indexing and relevance matching'
            })
        
        self.gaps = gaps
        return gaps
    
    def prioritize_gaps(self) -> List[Dict[str, Any]]:
        """Sort gaps by severity and impact."""
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        return sorted(self.gaps, key=lambda x: severity_order.get(x.get('severity', 'low'), 3))


# ============================================================================
# RECOMMENDATION ENGINE
# ============================================================================

class RecommendationEngine:
    """Generates prioritized recommendations based on analysis."""
    
    def __init__(self, performance: Dict, market: Dict, gaps: List[Dict]):
        self.performance = performance
        self.market = market
        self.gaps = gaps
    
    def generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate actionable recommendations with priority levels."""
        recommendations = []
        
        # Priority 1: Address high-severity gaps
        high_severity_gaps = [g for g in self.gaps if g.get('severity') == 'high']
        for gap in high_severity_gaps:
            recommendations.append({
                'priority': 1,
                'action': gap.get('recommendation', 'Address this gap'),
                'reason': f"High severity gap: {gap.get('gap', 'Unknown')}",
                'effort': 'medium',
                'impact': 'high',
                'category': gap.get('category', 'general')
            })
        
        # Priority 2: Performance optimizations
        tasks = self.performance.get('tasks', {})
        if tasks.get('avg_execution_time_seconds', 0) > 15:
            recommendations.append({
                'priority': 2,
                'action': 'Optimize response times by using Sonnet for more tasks and reserving Opus for complex analysis only',
                'reason': f"Average execution time ({tasks.get('avg_execution_time_seconds', 0):.1f}s) impacts user experience",
                'effort': 'low',
                'impact': 'medium',
                'category': 'performance'
            })
        
        # Priority 2: Medium severity gaps
        medium_severity_gaps = [g for g in self.gaps if g.get('severity') == 'medium']
        for gap in medium_severity_gaps:
            recommendations.append({
                'priority': 2,
                'action': gap.get('recommendation', 'Address this gap'),
                'reason': f"Medium severity gap: {gap.get('gap', 'Unknown')}",
                'effort': 'medium',
                'impact': 'medium',
                'category': gap.get('category', 'general')
            })
        
        # Priority 3: Market opportunities
        new_models = self.market.get('new_models', [])
        for model in new_models:
            if model.get('recommendation') == 'Consider':
                recommendations.append({
                    'priority': 3,
                    'action': f"Evaluate {model.get('name', 'new model')} for potential integration",
                    'reason': model.get('relevance', 'New capability available'),
                    'effort': 'high',
                    'impact': 'medium',
                    'category': 'capability'
                })
        
        # Priority 3: Emerging tools
        tools = self.market.get('emerging_tools', [])
        for tool in tools[:3]:  # Limit to top 3
            recommendations.append({
                'priority': 3,
                'action': f"Investigate {tool.get('name', 'new tool')}: {tool.get('purpose', '')}",
                'reason': tool.get('potential_use', 'Could enhance capabilities'),
                'effort': 'medium',
                'impact': 'low',
                'category': 'tools'
            })
        
        # Sort by priority
        recommendations.sort(key=lambda x: x.get('priority', 99))
        
        return recommendations


# ============================================================================
# REPORT GENERATOR
# ============================================================================

class SwarmReportGenerator:
    """Generates the weekly State of the Swarm report."""
    
    def __init__(self, performance: Dict, market: Dict, gaps: List[Dict], recommendations: List[Dict]):
        self.performance = performance
        self.market = market
        self.gaps = gaps
        self.recommendations = recommendations
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate the complete State of the Swarm report."""
        
        # Calculate overall health score (0-100)
        health_score = self._calculate_health_score()
        
        # Determine trend (compared to typical benchmarks)
        trend = self._determine_trend()
        
        # Generate executive summary
        summary = self._generate_executive_summary(health_score, trend)
        
        report = {
            'report_type': 'weekly_swarm_evaluation',
            'generated_at': datetime.now().isoformat(),
            'week_of': datetime.now().strftime('%B %d, %Y'),
            
            'executive_summary': summary,
            
            'health_score': {
                'overall': health_score,
                'trend': trend,
                'components': {
                    'task_success': self._score_task_success(),
                    'response_time': self._score_response_time(),
                    'consensus_quality': self._score_consensus(),
                    'user_satisfaction': self._score_satisfaction(),
                    'knowledge_utilization': self._score_knowledge()
                }
            },
            
            'performance_summary': {
                'tasks_processed': self.performance.get('tasks', {}).get('total', 0),
                'success_rate': f"{self.performance.get('tasks', {}).get('success_rate', 0)}%",
                'avg_response_time': f"{self.performance.get('tasks', {}).get('avg_execution_time_seconds', 0):.1f}s",
                'top_performer': self._identify_top_performer(),
                'lowest_performing_area': self._identify_weakest_area()
            },
            
            'market_developments': {
                'new_models_count': len(self.market.get('new_models', [])),
                'key_updates': self.market.get('capability_updates', [])[:3],
                'assessment': self.market.get('overall_assessment', 'No assessment available')
            },
            
            'gaps_identified': len(self.gaps),
            'high_priority_gaps': [g for g in self.gaps if g.get('severity') == 'high'],
            
            'recommendations': {
                'priority_1': [r for r in self.recommendations if r.get('priority') == 1],
                'priority_2': [r for r in self.recommendations if r.get('priority') == 2],
                'priority_3': [r for r in self.recommendations if r.get('priority') == 3]
            },
            
            'next_week_focus': self._generate_next_week_focus(),
            
            'raw_data': {
                'performance_metrics': self.performance,
                'market_findings': self.market,
                'all_gaps': self.gaps,
                'all_recommendations': self.recommendations
            }
        }
        
        return report
    
    def _calculate_health_score(self) -> int:
        """Calculate overall swarm health score (0-100)."""
        scores = []
        
        # Task success (40% weight)
        task_success = self.performance.get('tasks', {}).get('success_rate', 0)
        scores.append(min(task_success, 100) * 0.4)
        
        # Response time (20% weight) - inverse scale, faster is better
        avg_time = self.performance.get('tasks', {}).get('avg_execution_time_seconds', 60)
        time_score = max(0, 100 - (avg_time * 2))  # 0s = 100, 50s = 0
        scores.append(time_score * 0.2)
        
        # Consensus quality (20% weight)
        consensus_rate = self.performance.get('consensus', {}).get('consensus_rate', 0)
        scores.append(min(consensus_rate, 100) * 0.2)
        
        # User satisfaction (20% weight)
        avg_rating = self.performance.get('feedback', {}).get('avg_overall_rating', 0)
        satisfaction = (avg_rating / 5) * 100 if avg_rating else 50  # Default to 50 if no feedback
        scores.append(satisfaction * 0.2)
        
        return int(sum(scores))
    
    def _determine_trend(self) -> str:
        """Determine if performance is improving, stable, or declining."""
        # Without historical data, use heuristics
        health = self._calculate_health_score()
        gaps_count = len([g for g in self.gaps if g.get('severity') == 'high'])
        
        if health >= 80 and gaps_count == 0:
            return 'improving'
        elif health >= 60 and gaps_count <= 2:
            return 'stable'
        else:
            return 'needs_attention'
    
    def _generate_executive_summary(self, health_score: int, trend: str) -> str:
        """Generate a brief executive summary."""
        tasks = self.performance.get('tasks', {})
        
        trend_text = {
            'improving': 'Performance is trending positively.',
            'stable': 'Performance is stable.',
            'needs_attention': 'Some areas need attention.'
        }.get(trend, 'Performance requires monitoring.')
        
        return f"The AI Swarm processed {tasks.get('total', 0)} tasks this week with a {tasks.get('success_rate', 0)}% success rate. Overall health score: {health_score}/100. {trend_text} {len(self.gaps)} gaps identified with {len([g for g in self.gaps if g.get('severity') == 'high'])} requiring immediate attention."
    
    def _score_task_success(self) -> int:
        """Score task success rate (0-100)."""
        return int(min(self.performance.get('tasks', {}).get('success_rate', 0), 100))
    
    def _score_response_time(self) -> int:
        """Score response time (0-100, faster is better)."""
        avg_time = self.performance.get('tasks', {}).get('avg_execution_time_seconds', 60)
        return int(max(0, 100 - (avg_time * 2)))
    
    def _score_consensus(self) -> int:
        """Score consensus quality (0-100)."""
        return int(min(self.performance.get('consensus', {}).get('consensus_rate', 0), 100))
    
    def _score_satisfaction(self) -> int:
        """Score user satisfaction (0-100)."""
        avg_rating = self.performance.get('feedback', {}).get('avg_overall_rating', 0)
        return int((avg_rating / 5) * 100) if avg_rating else 50
    
    def _score_knowledge(self) -> int:
        """Score knowledge base utilization (0-100)."""
        return int(min(self.performance.get('knowledge_base', {}).get('knowledge_usage_rate', 0) * 2, 100))
    
    def _identify_top_performer(self) -> str:
        """Identify the top performing AI."""
        specialists = self.performance.get('specialists', [])
        if not specialists or isinstance(specialists, dict):
            return 'No specialist data'
        
        best = max(specialists, key=lambda x: x.get('success_rate', 0) * x.get('usage_count', 1))
        return f"{best.get('name', 'Unknown')} ({best.get('success_rate', 0)}% success rate)"
    
    def _identify_weakest_area(self) -> str:
        """Identify the area needing most improvement."""
        if not self.gaps:
            return 'No significant issues'
        
        high_gaps = [g for g in self.gaps if g.get('severity') == 'high']
        if high_gaps:
            return high_gaps[0].get('gap', 'Unknown')
        
        return self.gaps[0].get('gap', 'No significant issues') if self.gaps else 'No issues detected'
    
    def _generate_next_week_focus(self) -> List[str]:
        """Generate focus areas for next week."""
        focus = []
        
        # Priority 1 recommendations
        p1_recs = [r for r in self.recommendations if r.get('priority') == 1]
        for rec in p1_recs[:2]:
            focus.append(f"Monitor: {rec.get('action', 'Priority action')}")
        
        # High severity gaps
        high_gaps = [g for g in self.gaps if g.get('severity') == 'high']
        for gap in high_gaps[:2]:
            focus.append(f"Evaluate: {gap.get('gap', 'Gap area')}")
        
        # Market opportunities
        new_models = self.market.get('new_models', [])
        consider_models = [m for m in new_models if m.get('recommendation') == 'Consider']
        for model in consider_models[:1]:
            focus.append(f"Consider: Evaluate {model.get('name', 'new model')}")
        
        if not focus:
            focus.append("Continue monitoring system performance")
        
        return focus


# ============================================================================
# MAIN EVALUATION ORCHESTRATOR
# ============================================================================

class SwarmSelfEvaluator:
    """
    Main orchestrator for the weekly self-evaluation process.
    Coordinates all components and produces the final report.
    """
    
    def __init__(self):
        self.performance_collector = PerformanceCollector()
        self.market_scanner = MarketScanner()
        self.last_evaluation = None
    
    def run_evaluation(self, days: int = 7, save_to_db: bool = True) -> Dict[str, Any]:
        """
        Run the complete weekly evaluation.
        
        Args:
            days: Number of days to analyze (default 7)
            save_to_db: Whether to save the evaluation to database
        
        Returns:
            Complete evaluation report
        """
        print(f"🔍 Starting Swarm Self-Evaluation ({days} day period)...")
        
        # Step 1: Collect performance metrics
        print("  📊 Collecting performance metrics...")
        performance = self.performance_collector.collect_weekly_metrics(days=days)
        
        # Step 2: Scan AI market landscape
        print("  🌐 Scanning AI market landscape...")
        market = self.market_scanner.scan_ai_landscape()
        
        # Step 3: Analyze gaps
        print("  🔎 Analyzing capability gaps...")
        gap_analyzer = GapAnalyzer(performance, market)
        gaps = gap_analyzer.analyze_gaps()
        prioritized_gaps = gap_analyzer.prioritize_gaps()
        
        # Step 4: Generate recommendations
        print("  💡 Generating recommendations...")
        rec_engine = RecommendationEngine(performance, market, prioritized_gaps)
        recommendations = rec_engine.generate_recommendations()
        
        # Step 5: Generate report
        print("  📝 Generating State of the Swarm report...")
        report_gen = SwarmReportGenerator(performance, market, prioritized_gaps, recommendations)
        report = report_gen.generate_report()
        
        # Step 6: Save to database if requested
        if save_to_db:
            print("  💾 Saving evaluation to database...")
            self._save_evaluation(report)
        
        self.last_evaluation = report
        
        print(f"✅ Evaluation complete! Health Score: {report.get('health_score', {}).get('overall', 'N/A')}/100")
        
        return report
    
    def _save_evaluation(self, report: Dict[str, Any]) -> int:
        """Save evaluation report to database."""
        db = get_db()
        
        try:
            cursor = db.execute('''
                INSERT INTO swarm_evaluations (
                    evaluation_date, period_days, health_score, trend,
                    tasks_processed, success_rate, executive_summary,
                    gaps_count, high_priority_gaps_count, recommendations_count,
                    full_report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                report.get('raw_data', {}).get('performance_metrics', {}).get('days_analyzed', 7),
                report.get('health_score', {}).get('overall', 0),
                report.get('health_score', {}).get('trend', 'unknown'),
                report.get('performance_summary', {}).get('tasks_processed', 0),
                report.get('performance_summary', {}).get('success_rate', '0%'),
                report.get('executive_summary', ''),
                report.get('gaps_identified', 0),
                len(report.get('high_priority_gaps', [])),
                len(report.get('recommendations', {}).get('priority_1', [])) +
                len(report.get('recommendations', {}).get('priority_2', [])) +
                len(report.get('recommendations', {}).get('priority_3', [])),
                json.dumps(report)
            ))
            
            evaluation_id = cursor.lastrowid
            db.commit()
            print(f"  📁 Saved evaluation ID: {evaluation_id}")
            return evaluation_id
        except Exception as e:
            print(f"  ⚠️ Failed to save evaluation: {e}")
            return 0
        finally:
            db.close()
    
    def get_latest_evaluation(self) -> Optional[Dict[str, Any]]:
        """Get the most recent evaluation from database."""
        db = get_db()
        
        try:
            row = db.execute('''
                SELECT * FROM swarm_evaluations 
                ORDER BY evaluation_date DESC 
                LIMIT 1
            ''').fetchone()
            
            if row:
                return {
                    'id': row['id'],
                    'evaluation_date': row['evaluation_date'],
                    'health_score': row['health_score'],
                    'trend': row['trend'],
                    'tasks_processed': row['tasks_processed'],
                    'success_rate': row['success_rate'],
                    'executive_summary': row['executive_summary'],
                    'gaps_count': row['gaps_count'],
                    'high_priority_gaps_count': row['high_priority_gaps_count'],
                    'recommendations_count': row['recommendations_count'],
                    'full_report': json.loads(row['full_report_json']) if row['full_report_json'] else None
                }
            return None
        except Exception as e:
            print(f"Error fetching evaluation: {e}")
            return None
        finally:
            db.close()
    
    def get_evaluation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get history of evaluations."""
        db = get_db()
        
        try:
            rows = db.execute('''
                SELECT id, evaluation_date, health_score, trend, tasks_processed,
                       success_rate, gaps_count, high_priority_gaps_count
                FROM swarm_evaluations 
                ORDER BY evaluation_date DESC 
                LIMIT ?
            ''', (limit,)).fetchall()
            
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error fetching evaluation history: {e}")
            return []
        finally:
            db.close()


# ============================================================================
# SINGLETON ACCESSOR
# ============================================================================

_evaluator_instance = None

def get_swarm_evaluator() -> SwarmSelfEvaluator:
    """Get the singleton SwarmSelfEvaluator instance."""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = SwarmSelfEvaluator()
    return _evaluator_instance


# I did no harm and this file is not truncated
