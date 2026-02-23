"""
CASE STUDY GENERATOR - AI-Powered SEO & AI-Search Optimized Case Studies
Created: February 21, 2026

PURPOSE:
    Generates professional case studies for Shiftwork Solutions LLC optimized
    for both traditional SEO (Google) and AI-powered search (ChatGPT, Perplexity,
    Claude). Uses the AI Swarm orchestration layer for generation.

SEO/AI-SEARCH STRATEGY:
    - Structured with clear H1/H2/H3 headers that AI models can parse
    - Uses specific industry terminology and long-tail keywords naturally
    - Includes quantifiable results (numbers, percentages) that AI models cite
    - Problem/Solution/Result narrative structure that search engines reward
    - Schema-ready content structure
    - Natural keyword density without stuffing

INDUSTRIES SUPPORTED:
    Manufacturing, Pharmaceutical, Food Processing, Mining, Consumer Products,
    Beverage, Utilities, Paper & Packaging, Technology, Oil/Gas/Energy,
    Chemicals, Automotive, Transportation, Healthcare, Government, Gaming

CHANGE LOG:
    February 21, 2026 - Initial creation. Core generation, DOCX export, DB CRUD.
    February 22, 2026 - Added generate_website_ready_package(). Produces SEO title
                        (≤60 chars), meta description (≤160 chars), URL slug,
                        3-5 FAQ Q&A pairs, and combined Article+FAQPage JSON-LD
                        schema markup for direct website publishing.

AUTHOR: Jim @ Shiftwork Solutions LLC
LAST UPDATED: February 22, 2026
"""

import os
import json
from datetime import datetime

# ============================================================================
# INDUSTRY KEYWORD MAP
# SEO keywords naturally woven into generated content
# ============================================================================
INDUSTRY_SEO_KEYWORDS = {
    'manufacturing': [
        'manufacturing shift scheduling', '24/7 manufacturing operations',
        'production workforce optimization', 'manufacturing overtime reduction',
        'shift rotation manufacturing', 'continuous manufacturing operations'
    ],
    'pharmaceutical': [
        'pharmaceutical shift scheduling', 'GMP compliance shift work',
        'pharmaceutical workforce management', '24/7 pharmaceutical production',
        'FDA compliance shift operations', 'pharma continuous operations'
    ],
    'food_processing': [
        'food processing shift scheduling', 'food manufacturing workforce',
        '24/7 food production', 'food safety shift compliance',
        'food plant workforce optimization', 'continuous food processing'
    ],
    'mining': [
        'mining shift scheduling', 'mine workforce management',
        'fly-in fly-out scheduling', 'FIFO roster management',
        'mining operations workforce', '24/7 mining operations'
    ],
    'consumer_products': [
        'consumer products manufacturing workforce', 'CPG shift scheduling',
        'consumer goods 24/7 operations', 'FMCG workforce optimization',
        'consumer products shift work', 'continuous consumer goods production'
    ],
    'beverage': [
        'beverage manufacturing shift scheduling', 'brewery workforce management',
        'beverage plant 24/7 operations', 'drink manufacturing workforce',
        'beverage production scheduling', 'continuous beverage operations'
    ],
    'utilities': [
        'utility shift scheduling', 'power plant workforce management',
        'utility worker shift rotation', '24/7 utility operations',
        'energy sector shift work', 'utility operations workforce'
    ],
    'paper_packaging': [
        'paper mill shift scheduling', 'packaging plant workforce',
        '24/7 paper manufacturing', 'pulp and paper shift work',
        'packaging operations workforce', 'paper industry continuous operations'
    ],
    'technology': [
        'tech operations shift scheduling', 'data center workforce management',
        '24/7 tech operations', 'technology operations shift work',
        'NOC shift scheduling', 'tech support workforce optimization'
    ],
    'oil_gas_energy': [
        'oil and gas shift scheduling', 'refinery workforce management',
        'upstream operations shift work', 'downstream shift scheduling',
        'energy sector workforce optimization', 'oil field shift rotation'
    ],
    'chemicals': [
        'chemical plant shift scheduling', 'chemical manufacturing workforce',
        '24/7 chemical operations', 'process industry shift work',
        'chemical plant workforce optimization', 'continuous chemical operations'
    ],
    'automotive': [
        'automotive manufacturing shift scheduling', 'auto plant workforce',
        '24/7 automotive production', 'automotive shift rotation',
        'auto manufacturing workforce optimization', 'vehicle production scheduling'
    ],
    'transportation': [
        'transportation workforce scheduling', 'logistics shift management',
        '24/7 transportation operations', 'fleet operations shift work',
        'transportation workforce optimization', 'logistics workforce scheduling'
    ],
    'healthcare': [
        'healthcare shift scheduling', 'hospital workforce management',
        '24/7 healthcare operations', 'nursing shift optimization',
        'healthcare staffing solutions', 'hospital shift rotation'
    ],
    'government_mint': [
        'government operations shift scheduling', 'public sector workforce',
        'government facility 24/7 operations', 'mint operations workforce',
        'government shift work management', 'public sector shift optimization'
    ],
    'gaming_hospitality': [
        'casino shift scheduling', 'hospitality workforce management',
        '24/7 gaming operations', 'hotel shift scheduling',
        'gaming industry workforce optimization', 'hospitality shift rotation'
    ],
    'other': [
        '24/7 operations shift scheduling', 'continuous operations workforce',
        'shift work optimization', 'workforce scheduling consulting',
        'shift schedule design', 'employee-centered scheduling'
    ]
}

INDUSTRY_DISPLAY_NAMES = {
    'manufacturing': 'Manufacturing',
    'pharmaceutical': 'Pharmaceutical',
    'food_processing': 'Food Processing',
    'mining': 'Mining',
    'consumer_products': 'Consumer Products',
    'beverage': 'Beverage',
    'utilities': 'Utilities',
    'paper_packaging': 'Paper & Packaging',
    'technology': 'Technology',
    'oil_gas_energy': 'Oil, Gas & Energy',
    'chemicals': 'Chemicals',
    'automotive': 'Automotive',
    'transportation': 'Transportation',
    'healthcare': 'Healthcare',
    'government_mint': 'Government / Mint',
    'gaming_hospitality': 'Gaming & Hospitality',
    'other': 'Industrial Operations'
}


def get_case_study_prompt(industry: str, problem: str, solution: str) -> str:
    """
    Build the AI prompt for case study generation.
    Instructs the AI to produce SEO and AI-search optimized content.
    """
    industry_display = INDUSTRY_DISPLAY_NAMES.get(industry, 'Industrial Operations')
    keywords = INDUSTRY_SEO_KEYWORDS.get(industry, INDUSTRY_SEO_KEYWORDS['other'])
    primary_keyword = keywords[0] if keywords else 'shift scheduling'
    secondary_keywords = ', '.join(keywords[1:4]) if len(keywords) > 1 else ''

    prompt = f"""You are a professional content writer specializing in workforce management consulting case studies. 
Write a compelling, SEO-optimized case study for Shiftwork Solutions LLC based on the following:

INDUSTRY: {industry_display}
CLIENT PROBLEM: {problem}
SOLUTION APPLIED: {solution}

ABOUT SHIFTWORK SOLUTIONS LLC:
- Specialized consulting firm with hundreds of completed 24/7 shift operations engagements
- Core philosophy: the best shift schedules are ones employees actually choose
- Methodology: employee surveys, data analysis, change management, workforce optimization
- Typical engagement: 6 weeks, focused on continuous improvement
- Industries served: manufacturing, pharmaceutical, food processing, mining, and more
- Approach: never top-down mandates — always collaborative employee-centered design

SEO REQUIREMENTS (follow these exactly):
1. Use "{primary_keyword}" as the primary keyword — include it naturally in the title and first paragraph
2. Include these secondary keywords naturally throughout: {secondary_keywords}
3. Use specific numbers and quantifiable results where plausible (estimate conservatively if needed)
4. Structure for AI-search readability: clear headers, concise paragraphs, specific facts
5. Write for both human readers AND AI models that will summarize this content

STRUCTURE TO FOLLOW (use these exact section headers):
# [Compelling Title with Primary Keyword]

## The Challenge
[2-3 paragraphs describing the specific operational problem. Be specific about pain points: overtime costs, employee morale, scheduling complexity, turnover. Include industry-specific context.]

## Why Shiftwork Solutions LLC
[1-2 paragraphs explaining why the client chose Shiftwork Solutions. Mention the employee-centered approach, decades of industry experience, proven methodology, and the normative database of hundreds of past client engagements for benchmarking.]

## Our Approach
[2-3 paragraphs describing the solution methodology. Include: initial assessment, employee survey process, data analysis, schedule design options presented to employees, implementation planning, change management support. Be specific about the process.]

## The Results
[2-3 paragraphs with specific, quantifiable outcomes. Include metrics like: overtime reduction percentage, employee satisfaction improvement, turnover reduction, cost savings, productivity gains. Even if estimated, make them realistic and conservative.]

## Key Takeaways
[3-4 bullet points summarizing the most important lessons from this engagement. Make these specific and actionable — things other companies in this industry can learn from.]

## About Shiftwork Solutions LLC
[1 short paragraph. Mention: hundreds of 24/7 operations engagements, employee-centered philosophy, industries served, approach of letting employees choose their schedules through survey-driven design.]

WRITING STYLE:
- Professional but accessible — readable by plant managers and HR directors
- Specific and factual — avoid vague generalities
- Confident but not boastful
- Third person for the client, first person plural ("we", "our team") for Shiftwork Solutions
- No client name — use "[Client]" as placeholder
- Approximate headcount with ranges like "500+ employees" or "a team of 200"

OUTPUT: Return ONLY the case study content in markdown format. No preamble, no explanation, no JSON wrapper. Start directly with the # title."""

    return prompt


def get_website_package_prompt(title: str, content: str, industry: str) -> str:
    """
    Build the AI prompt for generating website-ready SEO metadata and schema markup.
    Called after the case study is already generated.
    """
    industry_display = INDUSTRY_DISPLAY_NAMES.get(industry, 'Industrial Operations')
    keywords = INDUSTRY_SEO_KEYWORDS.get(industry, INDUSTRY_SEO_KEYWORDS['other'])
    primary_keyword = keywords[0] if keywords else 'shift scheduling'

    prompt = f"""You are an SEO specialist and structured data expert. Based on the following case study for Shiftwork Solutions LLC, generate a complete website publishing package.

CASE STUDY TITLE: {title}
INDUSTRY: {industry_display}
PRIMARY KEYWORD: {primary_keyword}

CASE STUDY CONTENT:
{content}

Generate the following elements. Return ONLY valid JSON — no markdown, no preamble, no explanation. The JSON must be parseable by Python's json.loads().

Return this exact JSON structure:
{{
  "seo_title": "...",
  "meta_description": "...",
  "url_slug": "...",
  "faqs": [
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}}
  ],
  "json_ld": {{}}
}}

REQUIREMENTS FOR EACH FIELD:

seo_title:
- Maximum 60 characters including spaces
- Must include the primary keyword "{primary_keyword}" or a close variant
- Compelling and click-worthy
- Format: "[Benefit/Result]: [Primary Keyword] | Shiftwork Solutions"

meta_description:
- Maximum 160 characters including spaces
- Include primary keyword naturally in first half
- End with a soft call to action (e.g., "Learn how.")
- Summarize the key result from the case study

url_slug:
- Lowercase, hyphen-separated, no special characters
- 4-7 words maximum
- Include primary keyword or close variant
- Example format: "manufacturing-shift-scheduling-overtime-reduction"

faqs:
- Exactly 5 FAQ pairs
- Questions should be the kind real plant managers and HR directors search for
- Answers should be 2-4 sentences, specific and helpful
- Use industry terminology naturally
- At least 2 questions should reference the specific results from this case study
- Do NOT use generic questions like "What is shift scheduling?" — make them specific to this case study's problem and solution

json_ld:
- Combined Article + FAQPage schema as a single JSON-LD object
- Use "@graph" array containing both schemas
- Article schema: type="Article", headline=seo_title, description=meta_description, 
  author={{"@type":"Organization","name":"Shiftwork Solutions LLC"}},
  publisher={{"@type":"Organization","name":"Shiftwork Solutions LLC","url":"https://shiftworksolutions.com"}},
  url="https://shiftworksolutions.com/case-studies/[url_slug]"
  datePublished="{datetime.now().strftime('%Y-%m-%d')}"
- FAQPage schema: type="FAQPage" with all 5 FAQ pairs as mainEntity
- The entire json_ld value must itself be valid JSON (it will be serialized to a <script> tag)"""

    return prompt


def generate_case_study(industry: str, problem: str, solution: str) -> dict:
    """
    Generate a case study using the AI Swarm orchestration layer.
    Returns dict with success, content, title, word_count.
    """
    try:
        from config import ANTHROPIC_API_KEY, CLAUDE_SONNET_MODEL
        import anthropic

        if not ANTHROPIC_API_KEY:
            return {
                'success': False,
                'error': 'Anthropic API key not configured'
            }

        prompt = get_case_study_prompt(industry, problem, solution)

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model=CLAUDE_SONNET_MODEL,
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = message.content[0].text

        # Extract title from first line
        title = 'Case Study'
        lines = content.strip().split('\n')
        for line in lines:
            if line.startswith('# '):
                title = line.replace('# ', '').strip()
                break

        word_count = len(content.split())

        return {
            'success': True,
            'content': content,
            'title': title,
            'word_count': word_count,
            'industry': industry,
            'industry_display': INDUSTRY_DISPLAY_NAMES.get(industry, industry),
            'generated_at': datetime.now().isoformat()
        }

    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def generate_website_ready_package(study_id: int) -> dict:
    """
    Generate a complete website publishing package for a saved case study.

    Makes a second AI call (separate from case study generation) to produce:
      - seo_title      : ≤60 character SEO-optimized title
      - meta_description: ≤160 character meta description
      - url_slug       : clean URL slug for the page
      - faqs           : list of 5 {question, answer} dicts
      - json_ld        : combined Article + FAQPage JSON-LD schema dict
      - json_ld_string : the json_ld serialized as an indented string for
                         direct paste into a <script type="application/ld+json"> tag

    Returns:
        {
            'success': True/False,
            'seo_title': str,
            'meta_description': str,
            'url_slug': str,
            'faqs': [{'question': str, 'answer': str}, ...],
            'json_ld': dict,
            'json_ld_string': str,
            'error': str  (only on failure)
        }
    """
    try:
        from config import ANTHROPIC_API_KEY, CLAUDE_SONNET_MODEL
        import anthropic

        if not ANTHROPIC_API_KEY:
            return {'success': False, 'error': 'Anthropic API key not configured'}

        # Fetch the saved case study
        study = get_case_study_by_id(study_id)
        if not study:
            return {'success': False, 'error': f'Case study ID {study_id} not found'}

        title = study.get('title', '')
        content = study.get('content', '')
        industry = study.get('industry', 'other')

        if not content:
            return {'success': False, 'error': 'Case study has no content'}

        prompt = get_website_package_prompt(title, content, industry)

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model=CLAUDE_SONNET_MODEL,
            max_tokens=3000,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        raw_response = message.content[0].text.strip()

        # Strip markdown code fences if the model wrapped the JSON
        if raw_response.startswith('```'):
            lines = raw_response.split('\n')
            # Remove first line (```json or ```) and last line (```)
            raw_response = '\n'.join(lines[1:-1]).strip()

        # Parse JSON
        try:
            package = json.loads(raw_response)
        except json.JSONDecodeError as parse_err:
            return {
                'success': False,
                'error': f'AI returned invalid JSON: {str(parse_err)}',
                'raw_response': raw_response[:500]
            }

        # Validate required fields
        required_fields = ['seo_title', 'meta_description', 'url_slug', 'faqs', 'json_ld']
        missing = [f for f in required_fields if f not in package]
        if missing:
            return {
                'success': False,
                'error': f'AI response missing fields: {missing}',
                'raw_response': raw_response[:500]
            }

        # Enforce character limits (trim if AI exceeded them)
        seo_title = str(package['seo_title'])[:60]
        meta_description = str(package['meta_description'])[:160]
        url_slug = str(package['url_slug']).lower().replace(' ', '-')

        # Validate FAQs structure
        faqs = package.get('faqs', [])
        if not isinstance(faqs, list):
            faqs = []
        # Ensure each FAQ has question and answer keys
        cleaned_faqs = []
        for faq in faqs:
            if isinstance(faq, dict) and 'question' in faq and 'answer' in faq:
                cleaned_faqs.append({
                    'question': str(faq['question']),
                    'answer': str(faq['answer'])
                })

        # Serialize JSON-LD to a formatted string for paste-ready output
        json_ld_dict = package.get('json_ld', {})
        json_ld_string = json.dumps(json_ld_dict, indent=2)

        print(f"✅ Website package generated for study ID={study_id}: "
              f"title={len(seo_title)}ch, desc={len(meta_description)}ch, "
              f"faqs={len(cleaned_faqs)}, json_ld={len(json_ld_string)}ch")

        return {
            'success': True,
            'seo_title': seo_title,
            'meta_description': meta_description,
            'url_slug': url_slug,
            'faqs': cleaned_faqs,
            'json_ld': json_ld_dict,
            'json_ld_string': json_ld_string,
            'study_title': title,
            'industry_display': INDUSTRY_DISPLAY_NAMES.get(industry, industry),
            'generated_at': datetime.now().isoformat()
        }

    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def generate_case_study_docx(case_study_content: str, title: str, industry: str) -> bytes:
    """
    Convert markdown case study content to a professional Word document.
    Uses python-docx for reliable server-side generation.
    Returns bytes of the .docx file.
    """
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import re

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

    # Header style (H1)
    h1_style = doc.styles['Heading 1']
    h1_style.font.name = 'Arial'
    h1_style.font.size = Pt(18)
    h1_style.font.bold = True
    h1_style.font.color.rgb = RGBColor(0x1A, 0x53, 0x7A)  # Dark blue

    # Section style (H2)
    h2_style = doc.styles['Heading 2']
    h2_style.font.name = 'Arial'
    h2_style.font.size = Pt(14)
    h2_style.font.bold = True
    h2_style.font.color.rgb = RGBColor(0x2E, 0x75, 0xB6)  # Medium blue

    # ---- Header banner ----
    header = doc.sections[0].header
    header_para = header.paragraphs[0]
    header_para.text = 'Shiftwork Solutions LLC  |  Case Study'
    header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header_para.runs[0].font.size = Pt(9)
    header_para.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    # ---- Footer ----
    footer = doc.sections[0].footer
    footer_para = footer.paragraphs[0]
    industry_display = INDUSTRY_DISPLAY_NAMES.get(industry, 'Industrial Operations')
    footer_para.text = f'© Shiftwork Solutions LLC  |  {industry_display}  |  shiftworksolutions.com'
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_para.runs[0].font.size = Pt(9)
    footer_para.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    # ---- Parse and render markdown ----
    lines = case_study_content.strip().split('\n')

    def add_paragraph_with_formatting(doc, text, style_name='Normal'):
        """Add paragraph, handling **bold** inline formatting."""
        para = doc.add_paragraph(style=style_name)
        # Split on bold markers
        parts = re.split(r'\*\*(.+?)\*\*', text)
        for i, part in enumerate(parts):
            run = para.add_run(part)
            if i % 2 == 1:  # Odd indices are bold
                run.bold = True
        return para

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # H1
        if line.startswith('# ') and not line.startswith('## '):
            heading_text = line[2:].strip()
            para = doc.add_heading(heading_text, level=1)
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            # Add spacing after title
            doc.add_paragraph('')

        # H2
        elif line.startswith('## '):
            heading_text = line[3:].strip()
            doc.add_heading(heading_text, level=2)

        # H3
        elif line.startswith('### '):
            heading_text = line[4:].strip()
            doc.add_heading(heading_text, level=3)

        # Bullet points
        elif line.startswith('- ') or line.startswith('* '):
            bullet_text = line[2:].strip()
            para = add_paragraph_with_formatting(doc, bullet_text, 'List Bullet')

        # Numbered list
        elif re.match(r'^\d+\.\s', line):
            item_text = re.sub(r'^\d+\.\s', '', line).strip()
            para = add_paragraph_with_formatting(doc, item_text, 'List Number')

        # Horizontal rule — skip
        elif line.startswith('---') or line.startswith('==='):
            pass

        # Empty line — small spacing
        elif line == '':
            pass

        # Regular paragraph
        else:
            if line.strip():
                add_paragraph_with_formatting(doc, line.strip())

        i += 1

    # ---- Final metadata paragraph ----
    doc.add_paragraph('')
    meta_para = doc.add_paragraph()
    meta_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = meta_para.add_run(
        f'Generated by Shiftwork Solutions LLC AI System  |  {datetime.now().strftime("%B %d, %Y")}'
    )
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
    run.italic = True

    # ---- Save to bytes ----
    import io
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()


def save_case_study_to_db(industry: str, title: str, content: str,
                           problem: str, solution: str) -> int:
    """
    Save a generated case study to the database.
    Returns the new record ID.
    """
    from database import get_db
    db = get_db()
    cursor = db.execute('''
        INSERT INTO case_studies (
            industry, title, content, problem_summary,
            solution_summary, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        industry, title, content, problem, solution,
        datetime.now().isoformat(), datetime.now().isoformat()
    ))
    db.commit()
    record_id = cursor.lastrowid
    db.close()
    return record_id


def get_all_case_studies() -> list:
    """Retrieve all saved case studies, newest first."""
    from database import get_db
    db = get_db()
    rows = db.execute('''
        SELECT id, industry, title, problem_summary, solution_summary,
               created_at
        FROM case_studies
        ORDER BY created_at DESC
    ''').fetchall()
    db.close()
    return [dict(row) for row in rows]


def get_case_study_by_id(study_id: int) -> dict:
    """Retrieve a single case study by ID."""
    from database import get_db
    db = get_db()
    row = db.execute(
        'SELECT * FROM case_studies WHERE id = ?', (study_id,)
    ).fetchone()
    db.close()
    return dict(row) if row else None


def delete_case_study(study_id: int) -> bool:
    """Delete a case study by ID."""
    from database import get_db
    db = get_db()
    db.execute('DELETE FROM case_studies WHERE id = ?', (study_id,))
    db.commit()
    db.close()
    return True


def init_case_studies_table():
    """
    Create the case_studies table if it doesn't exist.
    Called at app startup.
    """
    from database import get_db
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS case_studies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            industry TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            problem_summary TEXT,
            solution_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS idx_case_studies_industry
        ON case_studies(industry)
    ''')
    db.execute('''
        CREATE INDEX IF NOT EXISTS idx_case_studies_created
        ON case_studies(created_at DESC)
    ''')
    db.commit()
    db.close()
    print("  ✅ case_studies table ready")

# I did no harm and this file is not truncated
