"""
PROACTIVE MARKETING ENGINE
Created: January 20, 2026
Last Updated: January 20, 2026

PURPOSE:
Automatically identify marketing opportunities, generate content, and suggest
promotional actions based on consulting work. Market proactively, not reactively.

FEATURES:
- Detect marketable insights from consulting work
- Auto-generate social media content from project learnings
- Identify case study opportunities
- Suggest content calendar topics
- Track market trends and recommend responses
- Automatically draft marketing materials

PHILOSOPHY:
Every consulting engagement generates marketable content. This module
extracts and packages those insights automatically.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

from datetime import datetime, timedelta
import json
import re


class ProactiveMarketing:
    """
    Automatically identifies and acts on marketing opportunities
    """
    
    def __init__(self):
        # Track marketing opportunities
        self.pending_content = []
        self.posted_content = []
        self.last_post_date = None
        self.content_calendar = []
        
        # Marketing triggers - patterns that create opportunities
        self.triggers = {
            'case_study': [
                'saved.*\\$[0-9,]+',  # Saved money
                'reduced.*overtime',
                'improved.*satisfaction',
                'increased.*productivity',
                'successful.*implementation'
            ],
            'thought_leadership': [
                'insight',
                'best practice',
                'lesson learned',
                'discovered that',
                'found that'
            ],
            'industry_trends': [
                '12-hour',
                '8-hour',
                'rotating shift',
                'fixed shift',
                'compressed work',
                '4-10 schedule'
            ],
            'client_success': [
                'client.*happy',
                'exceeded.*expectations',
                'positive.*feedback',
                'success',
                'achievement'
            ]
        }
        
        # Content templates
        self.templates = self._load_content_templates()
    
    def _load_content_templates(self):
        """Load marketing content templates"""
        
        return {
            'linkedin_insight': """🎯 {topic}

{key_insight}

After {experience_level} years working with hundreds of 24/7 operations, here's what we've learned:

{main_points}

💡 The takeaway: {conclusion}

What's been your experience with {topic_question}?

#ShiftWork #Operations #Manufacturing #ContinuousOperations
""",
            
            'linkedin_case_study': """📊 Real Results: {client_industry}

Challenge: {problem}
Solution: {solution}
Results: {results}

{key_learning}

This is why {broader_principle}

Interested in similar improvements for your operation? Let's talk.

#CaseStudy #OperationsExcellence #ShiftWork
""",
            
            'linkedin_tip': """💡 Quick Win: {tip_title}

{tip_description}

Why this works: {explanation}

Try this and let me know your results!

#ShiftWorkTips #Operations #Leadership
""",
            
            'twitter_insight': """🎯 {insight}

After hundreds of 24/7 ops projects: {key_point}

{cta}

#ShiftWork #Operations
""",
            
            'blog_outline': """Blog Post: {title}

Introduction:
{intro}

Main Points:
{points}

Conclusion:
{conclusion}

Keywords: {keywords}
Target Audience: {audience}
"""
        }
    
    def analyze_for_marketing_opportunities(self, interaction_data):
        """
        Analyze consulting interaction for marketing opportunities
        
        Args:
            interaction_data: dict with user_request, ai_response, context
            
        Returns:
            dict with identified opportunities and suggested content
        """
        
        opportunities = {
            'has_opportunities': False,
            'case_studies': [],
            'content_ideas': [],
            'social_posts': [],
            'blog_topics': [],
            'immediate_actions': []
        }
        
        request = interaction_data.get('user_request', '').lower()
        response = interaction_data.get('ai_response', '').lower()
        combined = f"{request} {response}"
        
        # Detect case study opportunities
        for pattern in self.triggers['case_study']:
            if re.search(pattern, combined, re.IGNORECASE):
                opportunities['case_studies'].append({
                    'trigger': pattern,
                    'context': self._extract_context(combined, pattern),
                    'suggested_action': 'Document this as a case study'
                })
                opportunities['has_opportunities'] = True
        
        # Detect thought leadership opportunities
        for pattern in self.triggers['thought_leadership']:
            if re.search(pattern, combined, re.IGNORECASE):
                insight = self._extract_insight(combined, pattern)
                if insight:
                    opportunities['content_ideas'].append({
                        'type': 'thought_leadership',
                        'insight': insight,
                        'suggested_platform': 'LinkedIn',
                        'urgency': 'medium'
                    })
                    opportunities['has_opportunities'] = True
        
        # Detect trending topics
        for pattern in self.triggers['industry_trends']:
            if re.search(pattern, combined, re.IGNORECASE):
                opportunities['blog_topics'].append({
                    'topic': pattern,
                    'context': 'Discussed in recent consultation',
                    'suggested_action': 'Create educational content about this'
                })
                opportunities['has_opportunities'] = True
        
        # Auto-generate social post if warranted
        if opportunities['has_opportunities']:
            auto_post = self._auto_generate_social_post(interaction_data, opportunities)
            if auto_post:
                opportunities['social_posts'].append(auto_post)
                opportunities['immediate_actions'].append({
                    'action': 'post_to_linkedin',
                    'content': auto_post['content'],
                    'why': auto_post['reasoning']
                })
        
        return opportunities
    
    def _extract_context(self, text, pattern):
        """Extract relevant context around a pattern match"""
        
        # Find the pattern
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return ""
        
        # Get surrounding context (200 chars before and after)
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 200)
        
        context = text[start:end]
        return context.strip()
    
    def _extract_insight(self, text, pattern):
        """Extract a meaningful insight from text"""
        
        # Look for complete sentences containing the pattern
        sentences = text.split('.')
        
        for sentence in sentences:
            if re.search(pattern, sentence, re.IGNORECASE):
                cleaned = sentence.strip()
                if len(cleaned) > 30:  # Meaningful length
                    return cleaned
        
        return None
    
    def _auto_generate_social_post(self, interaction_data, opportunities):
        """
        Automatically generate a social media post from consulting work
        
        Args:
            interaction_data: Original interaction
            opportunities: Detected opportunities
            
        Returns:
            dict with generated post and metadata
        """
        
        # Check if we posted recently (don't spam)
        if self.last_post_date:
            days_since = (datetime.now() - self.last_post_date).days
            if days_since < 2:  # Wait at least 2 days between auto-posts
                return None
        
        # Determine post type
        if opportunities.get('case_studies'):
            post_type = 'case_study'
        elif opportunities.get('content_ideas'):
            post_type = 'insight'
        else:
            post_type = 'tip'
        
        # Generate content based on type
        if post_type == 'insight' and opportunities['content_ideas']:
            insight_data = opportunities['content_ideas'][0]
            
            content = f"""💡 Consulting Insight

{insight_data['insight']}

Based on working with hundreds of 24/7 operations across manufacturing, healthcare, and distribution.

The key takeaway: Small schedule changes can have massive impact on employee satisfaction AND operational costs.

What's been your experience?

#ShiftWork #Operations #Manufacturing #Leadership"""
            
            return {
                'type': 'linkedin_post',
                'content': content,
                'reasoning': 'Valuable insight from recent consulting work',
                'platform': 'linkedin',
                'auto_generated': True,
                'requires_approval': True
            }
        
        return None
    
    def suggest_content_calendar(self, weeks_ahead=4):
        """
        Suggest content calendar based on past work and trends
        
        Args:
            weeks_ahead: Number of weeks to plan
            
        Returns:
            list of content suggestions with dates
        """
        
        calendar = []
        today = datetime.now()
        
        # Core topics to cycle through
        topics = [
            {
                'topic': '12-Hour Schedules',
                'angle': 'Pros, cons, and best practices',
                'format': 'LinkedIn post',
                'cta': 'Share your 12-hour schedule experience'
            },
            {
                'topic': 'Overtime Management',
                'angle': 'When to hire vs continue OT',
                'format': 'Blog post + LinkedIn snippet',
                'cta': 'Download our OT calculator'
            },
            {
                'topic': 'Employee Surveys',
                'angle': 'Why surveys matter for schedule success',
                'format': 'Case study',
                'cta': 'Request our survey template'
            },
            {
                'topic': 'Implementation Success',
                'angle': 'How to get employee buy-in',
                'format': 'Tips thread',
                'cta': 'Book a consultation'
            },
            {
                'topic': 'Cost Analysis',
                'angle': 'Hidden costs of bad schedules',
                'format': 'Educational post',
                'cta': 'Try our cost calculator'
            },
            {
                'topic': '20/60/20 Rule',
                'angle': 'Understanding OT preferences',
                'format': 'Insight post',
                'cta': 'Ask about your workforce'
            }
        ]
        
        # Plan posts for each week
        for week in range(weeks_ahead):
            post_date = today + timedelta(weeks=week)
            topic = topics[week % len(topics)]
            
            calendar.append({
                'week': week + 1,
                'date': post_date.strftime('%Y-%m-%d'),
                'topic': topic['topic'],
                'angle': topic['angle'],
                'format': topic['format'],
                'cta': topic['cta'],
                'status': 'planned'
            })
        
        return calendar
    
    def generate_proactive_marketing_message(self, opportunities):
        """
        Format marketing opportunities into actionable message
        
        Args:
            opportunities: dict from analyze_for_marketing_opportunities
            
        Returns:
            Formatted message string
        """
        
        if not opportunities.get('has_opportunities'):
            return None
        
        message = "\n📢 **MARKETING OPPORTUNITIES DETECTED**\n\n"
        
        # Case studies
        if opportunities.get('case_studies'):
            message += "📊 **CASE STUDY POTENTIAL:**\n"
            for cs in opportunities['case_studies'][:2]:
                message += f"• {cs.get('suggested_action', 'Document this success')}\n"
            message += "\n"
        
        # Content ideas
        if opportunities.get('content_ideas'):
            message += "💡 **CONTENT IDEAS:**\n"
            for idea in opportunities['content_ideas'][:2]:
                message += f"• {idea.get('type', 'content')}: {idea.get('insight', 'Valuable insight')[:100]}...\n"
            message += "\n"
        
        # Auto-generated posts
        if opportunities.get('social_posts'):
            message += "🤖 **READY TO POST:**\n"
            for post in opportunities['social_posts']:
                message += f"• {post.get('type', 'post')} auto-generated (review & approve)\n"
            message += "\n"
        
        # Immediate actions
        if opportunities.get('immediate_actions'):
            message += "⚡ **SUGGESTED ACTIONS:**\n"
            for action in opportunities['immediate_actions']:
                message += f"• {action.get('why', 'Marketing opportunity')}\n"
            message += "  → Should I post this to LinkedIn now?\n"
        
        return message.strip()
    
    def should_market_now(self):
        """
        Determine if it's a good time to suggest marketing
        
        Returns:
            Boolean
        """
        
        # Don't suggest too frequently
        if self.last_post_date:
            days_since = (datetime.now() - self.last_post_date).days
            if days_since < 2:
                return False
        
        # Check if we have pending content
        if len(self.pending_content) >= 3:
            return True  # Have enough content, should post
        
        return True


# Singleton instance
_proactive_marketing = None

def get_proactive_marketing():
    """Get or create the proactive marketing singleton"""
    global _proactive_marketing
    if _proactive_marketing is None:
        _proactive_marketing = ProactiveMarketing()
    return _proactive_marketing


# I did no harm and this file is not truncated
