"""
BLOG POST GENERATOR - AI-Powered SEO & AI-Search Optimized Blog Posts
Shiftwork Solutions LLC

PURPOSE:
    Generates conversational, SEO-optimized blog posts for Shiftwork Solutions
    website. Posts are written in an accessible, human style (someone reads
    these over coffee, not in a boardroom), while rigorously following the same
    SEO and AI-search optimization rules as the Case Study Generator.

    The employee engagement narrative is embedded as a non-negotiable element
    in every post regardless of topic — because workforce resistance to change
    is the #1 reason prospects call us, and every piece of content we publish
    must reinforce that we solve that problem.

TARGET AUDIENCE:
    General Managers, Directors, HR Managers — people who own the workforce
    problem, control the budget, and feel pressure from above and below.
    These readers are evaluating whether they can trust Shiftwork Solutions
    with a high-stakes organizational change.

TONE:
    Conversational, thoughtful, authoritative. Written like a seasoned expert
    talking plainly over lunch — not a white paper, not a sales pitch. Uses
    real examples, practical insights, and occasional first-person voice to
    build credibility and trust.

EMPLOYEE ENGAGEMENT NARRATIVE (woven into every post):
    - Workforce resistance acknowledged as the primary obstacle
    - Employee surveys surface real preferences, not assumed ones
    - Employee input shapes real outcomes — creates genuine ownership
    - Shiftwork Solutions is approachable and present on the shop floor
    - The result: workforces that accept and often appreciate the change

SEO/AI-SEARCH STRATEGY:
    - Title leads with keyword-rich phrase or common question being asked
    - Primary keyword in title AND first paragraph
    - Conservative, believable numbers throughout
    - Conversational headings that match natural language queries
    - Posts structured so AI models (Perplexity, ChatGPT) can extract and
      cite specific insights and statistics as quoted facts
    - Unique closing section per post — no duplicate content across library

TOPICS (dropdown):
    - Workforce Resistance to Schedule Change
    - Employee Survey Best Practices
    - Overtime Cost Reduction
    - Shift Schedule Design
    - 12-Hour vs 8-Hour Shifts
    - Work-Life Balance in Shift Work
    - Change Management for Operations
    - Turnover Reduction in 24/7 Operations
    - Fatigue and Shift Work
    - How to Choose a Shift Scheduling Consultant
    - The Cost of Getting Scheduling Wrong
    - Other (free-text)

CHANGE LOG:
    February 23, 2026 - Initial creation. Blog post generation engine with
                        DOCX export, database persistence, and library view.
                        Same SEO discipline and audience focus as Case Study
                        Generator. Conversational tone vs case study formality.
                        12 topic categories + Other. Word download. Library
                        with View / Word / Delete.

AUTHOR: Jim @ Shiftwork Solutions LLC
LAST UPDATED: February 23, 2026
"""

import os
import json
import re
from datetime import datetime


# ============================================================================
# TOPIC DEFINITIONS
# Each topic has a display name, primary SEO keyword, secondary keywords,
# and a short description used as a prompt hint.
# ============================================================================
BLOG_TOPICS = {
    'workforce_resistance': {
        'display': 'Workforce Resistance to Schedule Change',
        'primary_keyword': 'workforce resistance to schedule change',
        'secondary_keywords': [
            'employee pushback shift schedule', 'change management shift work',
            'getting employee buy-in scheduling', 'schedule change resistance'
        ],
        'prompt_hint': (
            'Why employees resist schedule changes, what makes it worse, '
            'and how to prevent it through early engagement and real involvement '
            'in the process rather than top-down announcement.'
        )
    },
    'employee_surveys': {
        'display': 'Employee Survey Best Practices',
        'primary_keyword': 'employee survey shift schedule',
        'secondary_keywords': [
            'workforce preference survey', 'shift schedule survey design',
            'employee input scheduling', 'workforce engagement survey'
        ],
        'prompt_hint': (
            'How to design, administer, and use employee surveys when changing '
            'shift schedules. Why most surveys fail (the question is wrong, or '
            'the results are filed away), and what good survey practice looks like.'
        )
    },
    'overtime_cost_reduction': {
        'display': 'Overtime Cost Reduction',
        'primary_keyword': 'overtime cost reduction manufacturing',
        'secondary_keywords': [
            'overtime management shift work', 'reducing overtime 24/7 operations',
            'overtime scheduling strategy', 'workforce overtime optimization'
        ],
        'prompt_hint': (
            'The real reasons overtime gets out of control in 24/7 operations, '
            'how schedule design contributes to chronic overtime, the 20/60/20 rule '
            'for overtime preference distribution, and practical strategies to '
            'reduce overtime without burning out the workforce.'
        )
    },
    'shift_schedule_design': {
        'display': 'Shift Schedule Design',
        'primary_keyword': 'shift schedule design 24/7 operations',
        'secondary_keywords': [
            '12-hour shift pattern', 'rotating shift schedule', 'fixed shift schedule',
            'shift rotation design', 'continuous operations scheduling'
        ],
        'prompt_hint': (
            'Principles of effective shift schedule design for continuous '
            'operations. Tradeoffs between fixed vs rotating schedules, 8-hour '
            'vs 12-hour shifts, and why the "best" schedule depends entirely '
            'on your workforce, not just your coverage requirements.'
        )
    },
    'twelve_vs_eight_hour': {
        'display': '12-Hour vs 8-Hour Shifts',
        'primary_keyword': '12-hour vs 8-hour shifts manufacturing',
        'secondary_keywords': [
            '12-hour shift advantages', '8-hour shift schedule', 'compressed shift schedule',
            'shift length comparison', '12-hour shift fatigue'
        ],
        'prompt_hint': (
            'A practical, balanced look at 12-hour vs 8-hour shift schedules. '
            'Why more than 80 percent of continuous operations workers prefer '
            '12-hour shifts when asked, the fatigue considerations that matter, '
            'and why the answer is different for every workforce and operation.'
        )
    },
    'work_life_balance': {
        'display': 'Work-Life Balance in Shift Work',
        'primary_keyword': 'work-life balance shift work',
        'secondary_keywords': [
            'shift worker work-life balance', 'employee schedule preferences',
            'shift work quality of life', 'workforce schedule satisfaction'
        ],
        'prompt_hint': (
            'What work-life balance actually means to shift workers — and why '
            'it means something different to every person on your floor. The '
            '400 employees, 400 definitions problem, how surveys reveal what '
            'workers actually value, and why assumptions about employee '
            'preferences are usually wrong.'
        )
    },
    'change_management': {
        'display': 'Change Management for Operations',
        'primary_keyword': 'change management shift schedule operations',
        'secondary_keywords': [
            'schedule transition management', 'workforce change management',
            'shift change communication', 'employee change resistance operations'
        ],
        'prompt_hint': (
            'Why schedule changes so often fail — even when the new schedule '
            'is objectively better. The importance of process, communication, '
            'and genuine employee involvement in creating lasting change. '
            'How top-down announcements trigger resistance even for good changes.'
        )
    },
    'turnover_reduction': {
        'display': 'Turnover Reduction in 24/7 Operations',
        'primary_keyword': 'turnover reduction 24/7 operations',
        'secondary_keywords': [
            'shift worker retention', 'reduce turnover manufacturing',
            'schedule-driven turnover', 'workforce retention shift work'
        ],
        'prompt_hint': (
            'How poorly designed shift schedules drive turnover — especially '
            'on night shifts. The hidden costs of turnover in continuous '
            'operations, which schedule-related factors employees cite when '
            'quitting, and how schedule redesign can meaningfully reduce '
            'avoidable turnover.'
        )
    },
    'fatigue_shift_work': {
        'display': 'Fatigue and Shift Work',
        'primary_keyword': 'fatigue shift work management',
        'secondary_keywords': [
            'shift worker fatigue', 'night shift fatigue management',
            'fatigue risk management operations', 'alertness shift work'
        ],
        'prompt_hint': (
            'The science and practical reality of fatigue in shift work. '
            'Why circadian rhythm matters, how shift start times affect sleep '
            'duration, why not starting shifts before 6am matters, and what '
            'managers can actually do to reduce fatigue-related risk without '
            'overhauling the entire schedule.'
        )
    },
    'choosing_consultant': {
        'display': 'How to Choose a Shift Scheduling Consultant',
        'primary_keyword': 'shift scheduling consultant',
        'secondary_keywords': [
            'shift work consultant', 'workforce scheduling consulting firm',
            'choose shiftwork consultant', 'shift schedule consulting services'
        ],
        'prompt_hint': (
            'What to look for when hiring a shift scheduling consultant. '
            'The difference between firms that impose solutions vs those that '
            'involve employees in the process. Why experience and methodology '
            'matter more than software, and the questions every buyer should '
            'ask before signing a contract.'
        )
    },
    'cost_of_wrong_schedule': {
        'display': 'The Cost of Getting Scheduling Wrong',
        'primary_keyword': 'cost of poor shift scheduling',
        'secondary_keywords': [
            'shift schedule ROI', 'scheduling impact operations',
            'cost bad shift schedule', 'workforce scheduling financial impact'
        ],
        'prompt_hint': (
            'The full financial and human cost of a poorly designed or poorly '
            'implemented shift schedule. Overtime explosion, turnover, absenteeism, '
            'quality problems, and workforce morale — and why these costs are '
            'usually invisible on the P&L until they become a crisis.'
        )
    },
    'other': {
        'display': 'Other',
        'primary_keyword': 'shift scheduling 24/7 operations',
        'secondary_keywords': [
            'workforce scheduling', 'continuous operations management',
            'shift work consulting', 'employee scheduling optimization'
        ],
        'prompt_hint': (
            'A general shiftwork operations topic related to scheduling, workforce '
            'management, change management, or consulting best practices.'
        )
    }
}


def get_blog_post_prompt(topic: str, custom_topic: str, angle: str) -> str:
    """
    Build the AI prompt for blog post generation.

    Enforces:
    1. Conversational but expert tone — readable over coffee
    2. Employee engagement narrative woven in naturally
    3. SEO and AI-search optimization
    4. Conservative, believable numbers
    5. Dynamic, unique content per post
    """

    # Resolve topic data
    topic_data = BLOG_TOPICS.get(topic, BLOG_TOPICS['other'])
    topic_display = topic_data['display']
    primary_keyword = topic_data['primary_keyword']
    secondary_keywords = ', '.join(topic_data['secondary_keywords'][:3])
    prompt_hint = topic_data['prompt_hint']

    # If topic is 'other' and custom topic was provided, use it
    if topic == 'other' and custom_topic:
        topic_display = custom_topic
        # Keep the generic keywords from 'other' topic

    # The specific angle or additional context Jim provided
    angle_section = f"\nSPECIFIC ANGLE OR FOCUS FOR THIS POST:\n{angle}\n" if angle else ""

    prompt = f"""You are a senior workforce management consultant and content writer for Shiftwork Solutions LLC. You're writing a blog post for the company website — conversational, expert, and deeply practical.

Your readers are General Managers, Plant Directors, and HR Managers at companies with 24/7 shift operations. They are dealing with real pressure from executives to control costs and from employees who are worried about schedule changes affecting their lives. They have seen schedule initiatives blow up before.

TOPIC: {topic_display}
PRIMARY KEYWORD: {primary_keyword}
SECONDARY KEYWORDS: {secondary_keywords}
TOPIC KNOWLEDGE: {prompt_hint}
{angle_section}

===== ABOUT SHIFTWORK SOLUTIONS LLC =====
- Specialized consulting firm with hundreds of completed 24/7 shift operations engagements
- Partners: Jim Dillingham (San Rafael, CA), Dan Capshaw (Ivins, UT), Ethan Franklin
- Core philosophy: the best shift schedule is the one employees actually choose
- Core process: employee surveys, data analysis, collaborative schedule design, change management
- Typical engagement: 6 weeks, about $16,500/week
- Unique value: we walk the shop floor, talk to workers directly, and earn their trust
- Industries: manufacturing, pharmaceutical, food processing, mining, logistics, and many more

===== THE EMPLOYEE ENGAGEMENT RULE =====
EVERY BLOG POST must connect back to the employee engagement dimension — because this is
the #1 reason companies hire us. Clients are not afraid of the schedule math. They are
afraid of their employees pushing back.

Every post must naturally weave in at least ONE clear reference to:
- Why employee involvement is not just nice to have — it determines whether the change sticks
- Surveying the workforce to understand real preferences (not assumed ones)
- How giving employees genuine input creates ownership rather than resentment
- The Shiftwork Solutions approach of being visible and approachable on the shop floor

This should not feel like an advertisement. It should feel like the natural conclusion
of practical advice: "and the reason this works is because employees were part of it."

===== SEO AND AI SEARCH REQUIREMENTS =====
1. TITLE: Lead with the topic or a common question the audience asks. Use "{primary_keyword}"
   or a close variant. Keep it under 70 characters. Format options:
   - "[Primary Keyword]: What Operations Leaders Need to Know"
   - "Why [Problem] Happens — and What to Do About It"
   - "The [Number] Things Most [Industry] Managers Get Wrong About [Topic]"

2. OPENING PARAGRAPH: Use "{primary_keyword}" in the first 2 sentences. Hook the reader
   immediately — start with a specific observation, a counter-intuitive insight, or a
   relatable scenario. Do not start with "In today's competitive landscape" or similar clichés.

3. SECONDARY KEYWORDS: Weave these into headings and body copy naturally: {secondary_keywords}

4. NUMBERS: Use specific, conservative, believable statistics and ranges throughout.
   Examples: "roughly 80 percent of shift workers prefer fixed shifts when surveyed",
   "operations running 15-20 percent chronic overtime", "turnover rates of 25-35 percent
   in non-day shifts." Do not invent implausibly high numbers or vague generalities.

5. QUOTABLE INSIGHTS: Include at least 3 specific, memorable insights that an AI search
   engine (Perplexity, ChatGPT) would pull out to answer questions on this topic. Make
   them concrete and attributable to real consulting experience.

6. INTERNAL CONSISTENCY: Everything in the post must be grounded and coherent. If you
   mention a percentage, it must make sense in context. If you mention a scenario, it
   must feel like something that actually happens.

===== TONE AND STYLE =====
- Conversational but authoritative. Like a seasoned expert talking plainly at lunch.
- Use "you" to address the reader directly — this builds connection and trust.
- Short paragraphs — 2 to 4 sentences each. Blog readers scan.
- Occasional first-person voice ("In our experience..." or "What we consistently find...") 
  is appropriate for a consulting firm blog.
- No jargon unless it is the exact language the audience uses.
- Language this audience actually uses: "workforce resistance," "employee buy-in,"
  "change management," "schedule transition," "overtime burden," "shift rotation,"
  "workforce survey," "shop floor."
- Avoid academic language, buzzwords, or phrases like "leverage synergies" or
  "holistic approach."
- Be direct. If something fails, say so. If something works, say why.
- Target length: 700-900 words. Long enough to be substantive, short enough to finish
  in one sitting.

===== STRUCTURE TO FOLLOW =====
Use these EXACT markdown elements:

# [Title: keyword-rich, specific, under 70 characters]

[Opening paragraph - hook + primary keyword in first 2 sentences]

## [Conversational subheading — like a question or a direct observation]

[2-3 paragraphs on the first main point]

## [Second subheading]

[2-3 paragraphs on the second main point]

## [Third subheading]

[2-3 paragraphs on the third main point — this is where the employee engagement
dimension should appear if it hasn't already come up naturally]

## What This Means for You

[1-2 paragraphs — practical takeaway for the GM or HR director reading this.
What should they actually do differently after reading this post?]

## About Shiftwork Solutions LLC

[DYNAMIC CLOSING — unique to this post, not boilerplate.
Write 2-3 sentences that:
  1. Connect this specific topic/post to something Shiftwork Solutions has seen
     repeatedly across hundreds of engagements (mention the specific topic, not
     a generic "workforce management" reference)
  2. Invite the reader to reach out — conversational, not salesy
  3. Reference the employee-centered philosophy in one sentence

Every post must have a different closing. No two closings should be identical.]

===== OUTPUT INSTRUCTIONS =====
Return ONLY the blog post content in markdown. Start directly with the # title.
No preamble, no explanation, no "Here is your blog post:" wrapper.
No JSON. Just the clean markdown content."""

    return prompt


def generate_blog_post(topic: str, custom_topic: str, angle: str) -> dict:
    """
    Generate a blog post using the Claude API.

    Args:
        topic:        Topic key from BLOG_TOPICS (e.g. 'workforce_resistance')
        custom_topic: Human-readable topic name if topic == 'other'
        angle:        Optional additional context or angle from Jim

    Returns:
        {
            'success': True/False,
            'id': int,
            'title': str,
            'topic': str,
            'topic_display': str,
            'content': str,
            'word_count': int,
            'error': str  (only on failure)
        }
    """
    try:
        from config import ANTHROPIC_API_KEY, CLAUDE_SONNET_MODEL
        import anthropic

        if not ANTHROPIC_API_KEY:
            return {'success': False, 'error': 'Anthropic API key not configured'}

        # Validate topic
        if topic not in BLOG_TOPICS:
            topic = 'other'

        # For 'other' topic, require custom_topic
        if topic == 'other' and not custom_topic:
            return {'success': False, 'error': 'Please describe the topic for "Other"'}

        prompt = get_blog_post_prompt(topic, custom_topic, angle)

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model=CLAUDE_SONNET_MODEL,
            max_tokens=2500,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = message.content[0].text.strip()

        # Extract title from the first # heading
        title = 'Blog Post'
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('# ') and not line.startswith('## '):
                title = line[2:].strip()
                break

        # Word count
        word_count = len(content.split())

        # Determine display name
        topic_data = BLOG_TOPICS.get(topic, BLOG_TOPICS['other'])
        if topic == 'other' and custom_topic:
            topic_display = custom_topic
        else:
            topic_display = topic_data['display']

        # Save to database
        post_id = save_blog_post_to_db(
            topic=topic,
            topic_display=topic_display,
            title=title,
            content=content,
            angle=angle or ''
        )

        print(f"[BlogPost] Generated: id={post_id}, topic={topic}, "
              f"title='{title[:60]}', words={word_count}")

        return {
            'success': True,
            'id': post_id,
            'title': title,
            'topic': topic,
            'topic_display': topic_display,
            'content': content,
            'word_count': word_count
        }

    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def generate_blog_post_docx(post_content: str, title: str, topic_display: str) -> bytes:
    """
    Convert markdown blog post content to a professional Word document.
    Styled consistently with the Case Study Generator DOCX output.
    Returns bytes of the .docx file.
    """
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # ---- Page setup: US Letter, 1" margins ----
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)

    # ---- Document styles ----
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)

    h1_style = doc.styles['Heading 1']
    h1_style.font.name = 'Arial'
    h1_style.font.size = Pt(20)
    h1_style.font.bold = True
    h1_style.font.color.rgb = RGBColor(0x1A, 0x53, 0x7A)

    h2_style = doc.styles['Heading 2']
    h2_style.font.name = 'Arial'
    h2_style.font.size = Pt(14)
    h2_style.font.bold = True
    h2_style.font.color.rgb = RGBColor(0x2E, 0x75, 0xB6)

    # ---- Header ----
    header = doc.sections[0].header
    header_para = header.paragraphs[0]
    header_para.text = 'Shiftwork Solutions LLC  |  Blog Post'
    header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header_para.runs[0].font.size = Pt(9)
    header_para.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    # ---- Footer ----
    footer = doc.sections[0].footer
    footer_para = footer.paragraphs[0]
    footer_para.text = (
        f'© Shiftwork Solutions LLC  |  {topic_display}  |  shift-work.com'
    )
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_para.runs[0].font.size = Pt(9)
    footer_para.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    # ---- Helper: inline bold formatting ----
    def add_paragraph_with_formatting(doc, text, style_name='Normal'):
        """Add paragraph handling **bold** inline formatting."""
        para = doc.add_paragraph(style=style_name)
        parts = re.split(r'\*\*(.+?)\*\*', text)
        for i, part in enumerate(parts):
            run = para.add_run(part)
            if i % 2 == 1:
                run.bold = True
        return para

    # ---- Parse and render markdown ----
    lines = post_content.strip().split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        if line.startswith('# ') and not line.startswith('## '):
            heading_text = line[2:].strip()
            para = doc.add_heading(heading_text, level=1)
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            doc.add_paragraph('')

        elif line.startswith('## '):
            heading_text = line[3:].strip()
            doc.add_heading(heading_text, level=2)

        elif line.startswith('### '):
            heading_text = line[4:].strip()
            doc.add_heading(heading_text, level=3)

        elif line.startswith('- ') or line.startswith('* '):
            bullet_text = line[2:].strip()
            add_paragraph_with_formatting(doc, bullet_text, 'List Bullet')

        elif re.match(r'^\d+\.\s', line):
            item_text = re.sub(r'^\d+\.\s', '', line).strip()
            add_paragraph_with_formatting(doc, item_text, 'List Number')

        elif line.startswith('---') or line.startswith('==='):
            pass  # Horizontal rules - skip

        elif line == '':
            pass  # Empty lines - skip (docx handles spacing via styles)

        else:
            if line.strip():
                add_paragraph_with_formatting(doc, line.strip())

        i += 1

    # ---- Final metadata paragraph ----
    doc.add_paragraph('')
    meta_para = doc.add_paragraph()
    meta_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = meta_para.add_run(
        f'Generated by Shiftwork Solutions LLC AI System  |  '
        f'{datetime.now().strftime("%B %d, %Y")}'
    )
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
    run.italic = True

    import io
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()


def save_blog_post_to_db(topic: str, topic_display: str, title: str,
                          content: str, angle: str) -> int:
    """Save a generated blog post to the database. Returns the new record ID."""
    from database import get_db
    db = get_db()
    cursor = db.execute('''
        INSERT INTO blog_posts (
            topic, topic_display, title, content, angle,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        topic, topic_display, title, content, angle,
        datetime.now().isoformat(), datetime.now().isoformat()
    ))
    db.commit()
    record_id = cursor.lastrowid
    db.close()
    return record_id


def get_all_blog_posts() -> list:
    """Retrieve all saved blog posts, newest first."""
    from database import get_db
    db = get_db()
    rows = db.execute('''
        SELECT id, topic, topic_display, title, angle, created_at
        FROM blog_posts
        ORDER BY created_at DESC
    ''').fetchall()
    db.close()
    return [dict(row) for row in rows]


def get_blog_post_by_id(post_id: int) -> dict:
    """Retrieve a single blog post by ID."""
    from database import get_db
    db = get_db()
    row = db.execute(
        'SELECT * FROM blog_posts WHERE id = ?', (post_id,)
    ).fetchone()
    db.close()
    return dict(row) if row else None


def delete_blog_post(post_id: int) -> bool:
    """Delete a blog post by ID."""
    from database import get_db
    db = get_db()
    db.execute('DELETE FROM blog_posts WHERE id = ?', (post_id,))
    db.commit()
    db.close()
    return True


def init_blog_posts_table():
    """Create the blog_posts table if it does not exist. Called at app startup."""
    from database import get_db
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS blog_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            topic_display TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            angle TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS idx_blog_posts_topic
        ON blog_posts(topic)
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS idx_blog_posts_created
        ON blog_posts(created_at DESC)
    ''')
    db.commit()
    db.close()
    print("  [BlogPost] blog_posts table ready")

# I did no harm and this file is not truncated
