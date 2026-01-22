"""
Resource Finder Module
Created: January 22, 2026
Last Updated: January 22, 2026 - SPRINT 2: Proactive Web Search

This module monitors AI confidence levels and proactively searches
for information when the AI is uncertain or lacks current data.

FEATURES:
- Confidence threshold monitoring (triggers at < 70%)
- Automatic web search initiation
- Search result incorporation into responses
- Knowledge gap tracking in database

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
from datetime import datetime
from database import get_db


class ResourceFinder:
    """Proactively finds resources when AI is uncertain"""
    
    # Confidence threshold that triggers search
    SEARCH_THRESHOLD = 0.70
    
    # Keywords that always trigger search regardless of confidence
    CURRENT_INFO_KEYWORDS = [
        'current', 'latest', 'recent', 'today', 'this week', 'this month',
        'now', 'currently', 'up to date', 'new developments', 'breaking'
    ]
    
    def __init__(self):
        self.searches_performed = 0
        
    def should_search(self, user_request, ai_confidence, ai_response=None):
        """
        Determine if web search is needed
        
        Args:
            user_request: Original user query
            ai_confidence: Confidence score (0.0 - 1.0)
            ai_response: AI's preliminary response (optional)
            
        Returns:
            dict with search decision and reasoning
        """
        # Check for explicit current info requests
        request_lower = user_request.lower()
        wants_current_info = any(
            keyword in request_lower 
            for keyword in self.CURRENT_INFO_KEYWORDS
        )
        
        if wants_current_info:
            return {
                'should_search': True,
                'reason': 'current_information_requested',
                'confidence': ai_confidence,
                'search_query': self._generate_search_query(user_request)
            }
        
        # Check confidence threshold
        if ai_confidence < self.SEARCH_THRESHOLD:
            return {
                'should_search': True,
                'reason': 'low_confidence',
                'confidence': ai_confidence,
                'search_query': self._generate_search_query(user_request)
            }
        
        # Check if response indicates uncertainty
        if ai_response and self._indicates_uncertainty(ai_response):
            return {
                'should_search': True,
                'reason': 'uncertain_response',
                'confidence': ai_confidence,
                'search_query': self._generate_search_query(user_request)
            }
        
        return {
            'should_search': False,
            'reason': 'sufficient_confidence',
            'confidence': ai_confidence
        }
    
    def _generate_search_query(self, user_request):
        """
        Generate effective search query from user request
        
        Extracts key terms and removes question words
        """
        # Remove question words
        query = user_request.lower()
        
        # Remove common question words
        remove_words = [
            'what', 'how', 'when', 'where', 'who', 'why', 'can', 'could',
            'would', 'should', 'is', 'are', 'am', 'tell me', 'explain',
            'describe', 'please', 'help me', 'i need', 'i want'
        ]
        
        for word in remove_words:
            query = query.replace(word + ' ', '')
        
        # Clean up
        query = ' '.join(query.split())  # Remove extra spaces
        query = query.strip('?.,!')
        
        # Limit to reasonable length
        words = query.split()
        if len(words) > 10:
            query = ' '.join(words[:10])
        
        return query
    
    def _indicates_uncertainty(self, response):
        """
        Check if AI response indicates uncertainty
        
        Looks for phrases like "I'm not sure", "I don't know", etc.
        """
        uncertainty_phrases = [
            "i'm not sure", "i don't know", "i'm uncertain", 
            "i cannot confirm", "i lack information", "i don't have",
            "not certain", "unclear", "may be outdated",
            "as of my knowledge cutoff", "i would need to search"
        ]
        
        response_lower = response.lower()
        return any(phrase in response_lower for phrase in uncertainty_phrases)
    
    def incorporate_search_results(self, original_response, search_results, confidence):
        """
        Merge search results with AI response
        
        Args:
            original_response: AI's preliminary answer
            search_results: Results from web_search tool
            confidence: Original confidence level
            
        Returns:
            Enhanced response with search findings
        """
        if not search_results:
            return original_response
        
        # Build enhanced response
        enhanced = f"""Based on my analysis and current research:

{original_response}

**Additional Current Information:**

{self._format_search_results(search_results)}

*Note: This response combines my knowledge base with current web research to provide the most accurate information.*"""
        
        return enhanced
    
    def _format_search_results(self, search_results):
        """Format search results for display"""
        if isinstance(search_results, str):
            return search_results
        
        if isinstance(search_results, dict):
            # Extract relevant parts
            if 'content' in search_results:
                return search_results['content']
            if 'snippets' in search_results:
                return '\n'.join(search_results['snippets'])
        
        return str(search_results)
    
    def track_search(self, task_id, query, results_found, improved_response):
        """
        Track search in database for analytics
        
        Args:
            task_id: ID of the task
            query: Search query used
            results_found: Whether results were found
            improved_response: Whether search improved the response
        """
        db = get_db()
        
        db.execute('''
            INSERT INTO resource_searches 
            (task_id, search_query, results_found, improved_response, searched_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            task_id,
            query,
            results_found,
            improved_response,
            datetime.now()
        ))
        
        db.commit()
        db.close()
        
        self.searches_performed += 1
    
    def get_search_stats(self, days=7):
        """
        Get search statistics for the past N days
        
        Returns:
            dict with search metrics
        """
        db = get_db()
        
        stats = db.execute('''
            SELECT 
                COUNT(*) as total_searches,
                SUM(CASE WHEN results_found = 1 THEN 1 ELSE 0 END) as successful_searches,
                SUM(CASE WHEN improved_response = 1 THEN 1 ELSE 0 END) as improved_responses,
                AVG(CASE WHEN improved_response = 1 THEN 1.0 ELSE 0.0 END) as improvement_rate
            FROM resource_searches
            WHERE searched_at >= datetime('now', '-' || ? || ' days')
        ''', (days,)).fetchone()
        
        db.close()
        
        return {
            'total_searches': stats['total_searches'] or 0,
            'successful_searches': stats['successful_searches'] or 0,
            'improved_responses': stats['improved_responses'] or 0,
            'improvement_rate': round(stats['improvement_rate'] or 0, 2),
            'period_days': days
        }


# I did no harm and this file is not truncated
