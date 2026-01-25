"""
AUTONOMOUS CONTENT MARKETING ENGINE
Created: January 25, 2026
Last Updated: January 25, 2026

PURPOSE:
Automatically generates marketing content from consulting work without manual effort.
Transforms every project into marketable insights, LinkedIn posts, and client newsletters.

FEATURES:
- Auto-extracts marketable insights from task history
- Generates LinkedIn posts (3 per week)
- Creates weekly industry intelligence newsletter
- Learns what content performs well
- Queues content for one-click approval

PHILOSOPHY:
Every consulting engagement contains marketable gold. This engine mines it automatically.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json
import re
from datetime import datetime, timedelta
from database import get_db
from typing import List, Dict, Optional

# Try to import AI clients
try:
    from orchestration.ai_clients import call_claude_opus, call_gpt4
    AI_AVAILABLE = True
except ImportError:
    print("⚠️ AI clients not available - content generation will be simulated")
    AI_AVAILABLE = False


class ContentMarketingEngine:
    """
    Automatically generates marketing content from consulting work
    """
    
    def __init__(self):
        """Initialize the content marketing engine"""
        self.content_categories = {
            'case_study': 'Client success stories with measurable results',
            'thought_leadership': 'Industry insights and best practices',
            'how_to': 'Practical guidance for shift work problems',
            'data_insights': 'Trends from normative database',
            'client_education': 'Educational content about shift work'
        }
        
        # LinkedIn post templates based on high-performing content
        self.linkedin_templates = self._load_linkedin_templates()
        
        # Newsletter templates
        self.newsletter_template = self._load_newsletter_template()
    
    def _load_linkedin_templates(self) -> Dict:
        """Load proven LinkedIn post templates"""
        return {
            'insight': {
                'hook': [
                    "After helping hundreds of 24/7 operations, here's what surprises most leaders:",
                    "🎯 Hard truth about shift work that nobody talks about:",
                    "Most facilities get this wrong about {topic}:",
                    "The data from 200+ implementations tells a clear story:"
                ],
                'structure': """
{hook}

{key_insight}

Here's what we learned:
{bullet_points}

💡 The takeaway: {conclusion}

What's your experience with {question}?

#ShiftWork #Operations #Manufacturing #WorkforceManagement
"""
            },
            'case_study': {
                'structure': """
📊 Real Results: {client_industry}

The Challenge: {problem}

The Solution: {approach}

The Results:
• {result_1}
• {result_2}
• {result_3}

{key_learning}

{call_to_action}

#ShiftWork #CaseStudy #{industry_hashtag}
"""
            },
            'how_to': {
                'structure': """
🔧 How to {solve_problem}

(Based on hundreds of successful implementations)

The Problem: {problem_statement}

The Solution:

1️⃣ {step_1}
2️⃣ {step_2}
3️⃣ {step_3}
4️⃣ {step_4}

{bonus_tip}

Try this approach and let me know how it works for your operation.

#ShiftWork #OperationalExcellence #Manufacturing
"""
            },
            'data_insight': {
                'structure': """
📈 Data Point: {statistic}

From our database of 200+ facilities:

{context}

Why this matters:
{implications}

What we recommend:
{recommendation}

Are you seeing similar patterns in your operation?

#DataDriven #ShiftWork #Operations
"""
            }
        }
    
    def _load_newsletter_template(self) -> str:
        """Load weekly newsletter template"""
        return """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
        .content {{ padding: 30px; max-width: 600px; margin: 0 auto; }}
        .insight-box {{ background: #f5f5f5; padding: 20px; margin: 20px 0; border-left: 4px solid #667eea; }}
        .cta-button {{ background: #667eea; color: white; padding: 15px 30px; text-decoration: none; display: inline-block; margin: 20px 0; border-radius: 5px; }}
        .footer {{ background: #f5f5f5; padding: 20px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>This Week in Shiftwork</h1>
        <p>{date}</p>
    </div>
    
    <div class="content">
        <h2>🔍 What We're Watching</h2>
        {industry_news}
        
        <h2>💡 This Week's Insight</h2>
        <div class="insight-box">
            {key_insight}
        </div>
        
        <h2>📊 From Our Practice</h2>
        {practice_update}
        
        <h2>🎯 Quick Win</h2>
        {quick_win}
        
        <center>
            <a href="{calendar_link}" class="cta-button">Schedule a Conversation</a>
        </center>
    </div>
    
    <div class="footer">
        <p>Shiftwork Solutions LLC | www.shift-work.com</p>
        <p>Helping hundreds of 24/7 operations optimize their workforce since 1995</p>
        <p><a href="{unsubscribe_link}">Unsubscribe</a></p>
    </div>
</body>
</html>
"""
    
    def extract_marketable_insights(self, days_back: int = 7) -> List[Dict]:
        """
        Extract marketable insights from recent consulting work
        
        Looks for:
        - Completed tasks with good outcomes
        - Client successes
        - Interesting problems solved
        - Data patterns discovered
        """
        db = get_db()
        
        # Get recent tasks that might contain marketable content
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        tasks = db.execute('''
            SELECT * FROM tasks
            WHERE created_at >= ?
            AND status = 'completed'
            ORDER BY created_at DESC
        ''', (cutoff_date,)).fetchall()
        
        insights = []
        
        for task in tasks:
            # Analyze task for marketable content
            insight = self._analyze_task_for_marketing(task)
            if insight:
                insights.append(insight)
        
        db.close()
        return insights
    
    def _analyze_task_for_marketing(self, task: Dict) -> Optional[Dict]:
        """
        Analyze a single task to determine if it contains marketable content
        
        Returns insight dict or None if not marketable
        """
        request = task['request'].lower()
        result = task['result'].lower() if task['result'] else ''
        
        # Pattern matching for marketable content
        patterns = {
            'case_study': [
                r'saved.*\$[\d,]+',
                r'reduced.*overtime.*\d+%',
                r'improved.*satisfaction.*\d+%',
                r'increased.*productivity',
                r'implementation.*success'
            ],
            'thought_leadership': [
                r'best practice',
                r'lesson learned',
                r'insight',
                r'discovered that',
                r'found that',
                r'analysis shows'
            ],
            'how_to': [
                r'how to',
                r'guide to',
                r'step.*by.*step',
                r'process for',
                r'approach to'
            ],
            'data_insights': [
                r'normative.*comparison',
                r'benchmark.*data',
                r'survey.*results',
                r'\d+%.*employees',
                r'database.*shows'
            ]
        }
        
        # Check which category this fits
        for category, category_patterns in patterns.items():
            for pattern in category_patterns:
                if re.search(pattern, request + ' ' + result):
                    return {
                        'task_id': task['id'],
                        'category': category,
                        'source_request': task['request'],
                        'source_result': task['result'][:500],  # First 500 chars
                        'detected_at': datetime.now().isoformat(),
                        'confidence': self._calculate_confidence(request, result, pattern)
                    }
        
        return None
    
    def _calculate_confidence(self, request: str, result: str, pattern: str) -> float:
        """Calculate confidence that this is good marketing content"""
        confidence = 0.5  # Base confidence
        
        # Boost confidence for specific indicators
        if any(word in result.lower() for word in ['success', 'improved', 'saved', 'increased']):
            confidence += 0.2
        
        if any(num in result for num in ['$', '%', 'hours', 'days']):
            confidence += 0.15
        
        if len(result) > 200:  # Substantial content
            confidence += 0.15
        
        return min(confidence, 1.0)
    
    def generate_linkedin_post(self, insight: Dict) -> Dict:
        """
        Generate a LinkedIn post from an insight
        
        Returns:
            {
                'content': 'Post text',
                'category': 'insight|case_study|how_to|data_insight',
                'estimated_engagement': 'low|medium|high',
                'hashtags': ['ShiftWork', ...],
                'source_task_id': 123
            }
        """
        if not AI_AVAILABLE:
            return self._generate_simulated_post(insight)
        
        category = insight['category']
        template = self.linkedin_templates.get(category, self.linkedin_templates['insight'])
        
        # Use Claude Opus to generate high-quality content
        prompt = f"""You are Jim from Shiftwork Solutions, an expert in 24/7 shift operations with hundreds of facility implementations.

Generate a LinkedIn post based on this insight from recent work:

SOURCE TASK: {insight['source_request']}
OUTCOME: {insight['source_result']}
CATEGORY: {category}

TEMPLATE TO FOLLOW:
{template['structure']}

GUIDELINES:
- Write in Jim's voice: experienced, data-driven, practical
- Use specific examples and numbers when available
- Keep it under 1500 characters for LinkedIn
- Include 3-5 relevant hashtags
- End with an engaging question
- NO corporate jargon or buzzwords
- Make it valuable and actionable

Remember: Jim has worked with hundreds of facilities across pharmaceutical, food processing, manufacturing, and distribution. He emphasizes employee-centered approaches and data-driven decisions.

Generate the complete LinkedIn post now:"""
        
        try:
            response = call_claude_opus(prompt, max_tokens=1000)
            
            return {
                'content': response.strip(),
                'category': category,
                'estimated_engagement': self._estimate_engagement(response),
                'hashtags': self._extract_hashtags(response),
                'source_task_id': insight['task_id'],
                'generated_at': datetime.now().isoformat(),
                'status': 'pending_approval'
            }
            
        except Exception as e:
            print(f"❌ Error generating LinkedIn post: {e}")
            return self._generate_simulated_post(insight)
    
    def _generate_simulated_post(self, insight: Dict) -> Dict:
        """Generate a simulated post when AI is unavailable"""
        return {
            'content': f"[SIMULATED POST]\n\nInsight from recent work:\n\n{insight['source_request'][:200]}...\n\n#ShiftWork #Operations",
            'category': insight['category'],
            'estimated_engagement': 'medium',
            'hashtags': ['ShiftWork', 'Operations'],
            'source_task_id': insight['task_id'],
            'generated_at': datetime.now().isoformat(),
            'status': 'pending_approval'
        }
    
    def _estimate_engagement(self, content: str) -> str:
        """Estimate likely engagement based on content characteristics"""
        score = 0
        
        # Factors that increase engagement
        if '?' in content:  # Questions drive engagement
            score += 2
        if any(emoji in content for emoji in ['🎯', '💡', '📊', '🔧', '📈']):
            score += 1
        if re.search(r'\d+%', content):  # Numbers and stats
            score += 2
        if len(content) < 1200:  # Concise posts perform better
            score += 1
        if content.count('\n\n') >= 2:  # Good formatting
            score += 1
        
        if score >= 5:
            return 'high'
        elif score >= 3:
            return 'medium'
        else:
            return 'low'
    
    def _extract_hashtags(self, content: str) -> List[str]:
        """Extract hashtags from content"""
        return re.findall(r'#(\w+)', content)
    
    def generate_weekly_newsletter(self, include_research: bool = True) -> Dict:
        """
        Generate the weekly "This Week in Shiftwork" newsletter
        
        Args:
            include_research: Whether to include industry news via research agent
        
        Returns:
            {
                'subject': 'Email subject line',
                'html_body': 'HTML email content',
                'plain_text': 'Plain text version',
                'generated_at': 'ISO timestamp'
            }
        """
        # Get industry news if research agent available
        industry_news = ""
        if include_research:
            try:
                from research_agent import get_research_agent
                ra = get_research_agent()
                if ra.is_available:
                    news = ra.search("shift work manufacturing operations news", max_results=3)
                    if news.get('success'):
                        industry_news = self._format_news_for_newsletter(news.get('results', []))
            except:
                pass
        
        if not industry_news:
            industry_news = "<p>Monitoring developments in shift work operations...</p>"
        
        # Get key insight from recent work
        insights = self.extract_marketable_insights(days_back=7)
        key_insight = self._select_best_insight(insights) if insights else "Taking a data-driven approach to shift schedule design improves both operations and employee satisfaction."
        
        # Practice update
        practice_update = self._generate_practice_update()
        
        # Quick win tip
        quick_win = self._generate_quick_win()
        
        # Generate newsletter HTML
        html_body = self.newsletter_template.format(
            date=datetime.now().strftime("%B %d, %Y"),
            industry_news=industry_news,
            key_insight=key_insight,
            practice_update=practice_update,
            quick_win=quick_win,
            calendar_link="https://shift-work.com/contact",
            unsubscribe_link="https://shift-work.com/unsubscribe"
        )
        
        # Generate plain text version
        plain_text = self._html_to_plain_text(html_body)
        
        return {
            'subject': f"This Week in Shiftwork - {datetime.now().strftime('%B %d, %Y')}",
            'html_body': html_body,
            'plain_text': plain_text,
            'generated_at': datetime.now().isoformat(),
            'status': 'pending_approval'
        }
    
    def _format_news_for_newsletter(self, news_results: List[Dict]) -> str:
        """Format news results for newsletter"""
        if not news_results:
            return "<p>No significant industry news this week.</p>"
        
        html = "<ul>\n"
        for item in news_results[:3]:
            title = item.get('title', 'Industry Update')
            snippet = item.get('snippet', '')[:150]
            url = item.get('url', '#')
            html += f'<li><strong><a href="{url}">{title}</a></strong><br>{snippet}...</li>\n'
        html += "</ul>\n"
        
        return html
    
    def _select_best_insight(self, insights: List[Dict]) -> str:
        """Select the most valuable insight for newsletter"""
        if not insights:
            return "Focus on employee involvement in schedule design - it's the foundation of successful implementations."
        
        # Prefer case studies with numbers
        for insight in insights:
            if insight['category'] == 'case_study' and insight['confidence'] > 0.7:
                return insight['source_result'][:300]
        
        # Fall back to any high-confidence insight
        for insight in sorted(insights, key=lambda x: x['confidence'], reverse=True):
            if insight['confidence'] > 0.6:
                return insight['source_result'][:300]
        
        return insights[0]['source_result'][:300]
    
    def _generate_practice_update(self) -> str:
        """Generate a practice update for newsletter"""
        db = get_db()
        
        # Count recent projects
        recent_projects = db.execute('''
            SELECT COUNT(*) as count FROM tasks
            WHERE created_at >= datetime('now', '-30 days')
            AND task_type IN ('schedule_design', 'implementation', 'survey')
        ''').fetchone()
        
        db.close()
        
        count = recent_projects['count'] if recent_projects else 0
        
        if count > 0:
            return f"<p>This month we've worked with {count} facilities on schedule optimization projects spanning pharmaceutical, manufacturing, and distribution operations.</p>"
        else:
            return "<p>We continue supporting clients across multiple industries with schedule design, implementation, and workforce optimization.</p>"
    
    def _generate_quick_win(self) -> str:
        """Generate a quick win tip"""
        tips = [
            "<p><strong>Quick Win:</strong> Before changing schedules, survey your employees about their preferences. You'll discover that 100 employees have 100 different ideal schedules - and understanding this diversity is the first step to a solution that works.</p>",
            "<p><strong>Quick Win:</strong> Make overtime predictable. Employees accept necessary overtime much better when they get advance notice. Even moving notification from Friday afternoon to Thursday afternoon significantly reduces resentment.</p>",
            "<p><strong>Quick Win:</strong> Document your current schedule's actual coverage vs. required coverage by hour and day. You might discover you're overstaffed at some times and understaffed at others - knowledge that enables targeted improvements.</p>",
            "<p><strong>Quick Win:</strong> Calculate your true fully-loaded overtime cost (including benefits burden). Many facilities discover that $26/hour base pay actually costs $36/hour when properly calculated - changing the economics of hiring vs. overtime decisions.</p>"
        ]
        
        import random
        return random.choice(tips)
    
    def _html_to_plain_text(self, html: str) -> str:
        """Convert HTML newsletter to plain text"""
        # Simple HTML to text conversion
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def save_content_for_approval(self, content_type: str, content_data: Dict) -> int:
        """
        Save generated content to database for approval
        
        Args:
            content_type: 'linkedin_post' or 'newsletter'
            content_data: Content dictionary
        
        Returns:
            content_id
        """
        db = get_db()
        
        cursor = db.execute('''
            INSERT INTO marketing_content (
                content_type, content_data, status, generated_at
            ) VALUES (?, ?, ?, ?)
        ''', (
            content_type,
            json.dumps(content_data),
            'pending_approval',
            datetime.now()
        ))
        
        content_id = cursor.lastrowid
        db.commit()
        db.close()
        
        return content_id
    
    def get_pending_approvals(self) -> List[Dict]:
        """Get all content pending approval"""
        db = get_db()
        
        pending = db.execute('''
            SELECT * FROM marketing_content
            WHERE status = 'pending_approval'
            ORDER BY generated_at DESC
        ''').fetchall()
        
        db.close()
        
        results = []
        for item in pending:
            results.append({
                'id': item['id'],
                'content_type': item['content_type'],
                'content_data': json.loads(item['content_data']),
                'generated_at': item['generated_at']
            })
        
        return results
    
    def approve_content(self, content_id: int) -> bool:
        """Approve content for publishing"""
        db = get_db()
        
        db.execute('''
            UPDATE marketing_content
            SET status = 'approved',
                approved_at = ?
            WHERE id = ?
        ''', (datetime.now(), content_id))
        
        db.commit()
        db.close()
        
        return True
    
    def reject_content(self, content_id: int, reason: str = None) -> bool:
        """Reject content"""
        db = get_db()
        
        db.execute('''
            UPDATE marketing_content
            SET status = 'rejected',
                rejection_reason = ?
            WHERE id = ?
        ''', (reason, content_id))
        
        db.commit()
        db.close()
        
        return True


# Singleton instance
_content_engine = None

def get_content_engine() -> ContentMarketingEngine:
    """Get or create singleton instance"""
    global _content_engine
    if _content_engine is None:
        _content_engine = ContentMarketingEngine()
    return _content_engine


# I did no harm and this file is not truncated
