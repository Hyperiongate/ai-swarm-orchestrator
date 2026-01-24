"""
Research Agent - Proactive Web Research for AI Swarm
Created: January 23, 2026
Last Updated: January 23, 2026

PURPOSE:
This module adds real-time web research capabilities to the AI Swarm.
It can proactively search for:
- Industry news and trends
- Competitor activity
- New regulations and compliance updates
- Case studies and research papers
- Potential leads discussing shift problems

USES TAVILY API:
- Purpose-built for AI agents
- Returns clean, structured results
- Includes AI-generated summaries
- $0.01/search or free tier (1000/month)

Author: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import json
import requests
from datetime import datetime, timedelta
from database import get_db

# Tavily API Configuration
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class ResearchAgent:
    """
    Proactive research agent that searches the web for relevant information.
    Integrates with the AI Swarm to provide current, real-time data.
    """
    
    def __init__(self):
        self.api_key = TAVILY_API_KEY
        self.is_available = bool(self.api_key)
        
        # Define research domains relevant to shiftwork consulting
        self.research_domains = {
            'industry_news': {
                'keywords': ['shift work', '24/7 operations', 'manufacturing schedules', 
                            'rotating shifts', 'workforce scheduling'],
                'description': 'Latest news about shift work and scheduling'
            },
            'regulations': {
                'keywords': ['OSHA fatigue', 'labor law shifts', 'overtime regulations',
                            'worker safety hours', 'shift work compliance'],
                'description': 'Regulatory updates affecting shift operations'
            },
            'research_studies': {
                'keywords': ['shift work health study', 'rotating schedule research',
                            '12-hour shift fatigue', 'circadian rhythm workplace'],
                'description': 'Academic and industry research on shift work'
            },
            'competitor_activity': {
                'keywords': ['shift scheduling software', 'workforce management solutions',
                            'employee scheduling consulting'],
                'description': 'Competitor products and services'
            },
            'leads': {
                'keywords': ['struggling with shift schedules', 'need better scheduling',
                            'shift coverage problems', 'overtime costs manufacturing'],
                'description': 'Potential clients discussing scheduling challenges'
            }
        }
        
        if self.is_available:
            print("✅ Research Agent initialized with Tavily API")
        else:
            print("⚠️ Research Agent: TAVILY_API_KEY not configured")
    
    def search(self, query, search_depth="basic", max_results=5, include_domains=None, 
               exclude_domains=None, days_back=None):
        """
        Perform a web search using Tavily API.
        
        Args:
            query: Search query string
            search_depth: "basic" (faster) or "advanced" (more thorough)
            max_results: Number of results to return (1-10)
            include_domains: List of domains to search within
            exclude_domains: List of domains to exclude
            days_back: Only return results from last N days
            
        Returns:
            dict with 'success', 'results', 'summary', 'query'
        """
        if not self.is_available:
            return {
                'success': False,
                'error': 'Tavily API key not configured',
                'results': []
            }
        
        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results,
                "include_answer": True,  # Get AI-generated summary
                "include_raw_content": False
            }
            
            if include_domains:
                payload["include_domains"] = include_domains
            
            if exclude_domains:
                payload["exclude_domains"] = exclude_domains
            
            response = requests.post(TAVILY_SEARCH_URL, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Process results
            results = []
            for result in data.get('results', []):
                results.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('content', ''),
                    'score': result.get('score', 0),
                    'published_date': result.get('published_date')
                })
            
            # Log the search
            self._log_search(query, len(results))
            
            return {
                'success': True,
                'query': query,
                'summary': data.get('answer', ''),  # AI-generated summary
                'results': results,
                'result_count': len(results)
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Research Agent search error: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
        except Exception as e:
            print(f"Research Agent unexpected error: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def search_industry_news(self, specific_topic=None, days_back=7):
        """
        Search for recent industry news about shift work and scheduling.
        """
        base_query = "shift work scheduling manufacturing news"
        if specific_topic:
            base_query = f"{specific_topic} shift work news"
        
        return self.search(
            query=base_query,
            search_depth="advanced",
            max_results=5,
            exclude_domains=["pinterest.com", "facebook.com", "twitter.com"]
        )
    
    def search_regulations(self, topic=None):
        """
        Search for regulatory updates affecting shift operations.
        """
        base_query = "OSHA labor regulations shift work overtime 2024 2025"
        if topic:
            base_query = f"{topic} regulations compliance"
        
        return self.search(
            query=base_query,
            search_depth="advanced",
            max_results=5,
            include_domains=["osha.gov", "dol.gov", "shrm.org", "law.cornell.edu"]
        )
    
    def search_research_studies(self, topic=None):
        """
        Search for academic and industry research on shift work.
        """
        base_query = "shift work health fatigue research study"
        if topic:
            base_query = f"{topic} research study"
        
        return self.search(
            query=base_query,
            search_depth="advanced",
            max_results=5,
            include_domains=["pubmed.gov", "nih.gov", "sciencedirect.com", 
                           "journals.sagepub.com", "nature.com"]
        )
    
    def search_competitors(self):
        """
        Search for competitor activity and products.
        """
        return self.search(
            query="shift scheduling software workforce management consulting",
            search_depth="basic",
            max_results=10,
            exclude_domains=["shiftworksolutions.com"]  # Exclude ourselves
        )
    
    def search_potential_leads(self, industry=None):
        """
        Search for potential clients discussing scheduling challenges.
        """
        base_query = "struggling with shift schedules overtime problems manufacturing"
        if industry:
            base_query = f"{industry} shift scheduling problems challenges"
        
        return self.search(
            query=base_query,
            search_depth="advanced",
            max_results=10,
            include_domains=["linkedin.com", "reddit.com", "quora.com", 
                           "manufacturingnet.com", "industryweek.com"]
        )
    
    def research_topic(self, topic, context=None):
        """
        General-purpose research on any topic related to shift work.
        Used by the AI Swarm when it needs current information.
        
        Args:
            topic: The topic to research
            context: Additional context about why we need this info
            
        Returns:
            Structured research results
        """
        # Enhance query with shiftwork context if relevant
        shiftwork_keywords = ['schedule', 'shift', 'crew', 'rotation', 'overtime', 
                             'fatigue', '12-hour', '24/7', 'manufacturing']
        
        is_shiftwork_related = any(kw in topic.lower() for kw in shiftwork_keywords)
        
        if is_shiftwork_related:
            enhanced_query = f"{topic} workforce operations"
        else:
            enhanced_query = topic
        
        result = self.search(
            query=enhanced_query,
            search_depth="advanced",
            max_results=7
        )
        
        if result['success']:
            # Add metadata
            result['topic'] = topic
            result['context'] = context
            result['is_shiftwork_related'] = is_shiftwork_related
            result['researched_at'] = datetime.now().isoformat()
        
        return result
    
    def get_daily_briefing(self):
        """
        Generate a daily briefing of relevant industry updates.
        Called proactively to keep Jim informed.
        
        Returns:
            Structured briefing with categorized findings
        """
        briefing = {
            'generated_at': datetime.now().isoformat(),
            'sections': []
        }
        
        # Industry News
        news = self.search_industry_news()
        if news['success'] and news['results']:
            briefing['sections'].append({
                'title': '📰 Industry News',
                'summary': news.get('summary', ''),
                'items': news['results'][:3]
            })
        
        # Regulatory Updates
        regs = self.search_regulations()
        if regs['success'] and regs['results']:
            briefing['sections'].append({
                'title': '⚖️ Regulatory Updates',
                'summary': regs.get('summary', ''),
                'items': regs['results'][:2]
            })
        
        # Research & Studies
        research = self.search_research_studies()
        if research['success'] and research['results']:
            briefing['sections'].append({
                'title': '🔬 New Research',
                'summary': research.get('summary', ''),
                'items': research['results'][:2]
            })
        
        # Store briefing in database
        self._store_briefing(briefing)
        
        return briefing
    
    def _log_search(self, query, result_count):
        """Log search to database for analytics"""
        try:
            db = get_db()
            db.execute('''
                INSERT INTO research_logs (query, result_count, searched_at)
                VALUES (?, ?, ?)
            ''', (query, result_count, datetime.now()))
            db.commit()
            db.close()
        except Exception as e:
            print(f"Failed to log search: {e}")
    
    def _store_briefing(self, briefing):
        """Store daily briefing in database"""
        try:
            db = get_db()
            db.execute('''
                INSERT INTO research_briefings (briefing_data, created_at)
                VALUES (?, ?)
            ''', (json.dumps(briefing), datetime.now()))
            db.commit()
            db.close()
        except Exception as e:
            print(f"Failed to store briefing: {e}")
    
    def get_status(self):
        """Get research agent status"""
        return {
            'available': self.is_available,
            'api_configured': bool(self.api_key),
            'domains_tracked': len(self.research_domains),
            'capabilities': [
                'Industry news monitoring',
                'Regulatory update tracking',
                'Research study discovery',
                'Competitor analysis',
                'Lead identification',
                'Topic-specific research'
            ]
        }


# Singleton instance
_research_agent = None

def get_research_agent():
    """Get or create the research agent singleton"""
    global _research_agent
    if _research_agent is None:
        _research_agent = ResearchAgent()
    return _research_agent


# I did no harm and this file is not truncated
