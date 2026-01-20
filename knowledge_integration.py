"""
PROJECT WORKFLOW ORCHESTRATOR 
Created: January 19, 2026
Last Updated: January 19, 2026

PURPOSE:
Conversational interface for managing complete consulting projects from
initial data collection through final deliverables. Handles:
- Data collection document creation
- File analysis (payroll, surveys, etc.)
- Email thread review and context extraction  
- LinkedIn post generation
- Full project lifecycle management

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import json
from datetime import datetime


class ProjectWorkflow:
    """
    Manages state and context for a consulting project
    Enables conversational interaction across multiple project phases
    """
    
    def __init__(self):
        self.project_id = None
        self.client_name = None
        self.industry = None
        self.facility_type = None
        self.project_phase = "initial"  # initial, data_collection, analysis, implementation, followup
        self.uploaded_files = []
        self.email_context = []
        self.key_findings = []
        self.schedules_proposed = []
        self.project_history = []
        
    def add_context(self, context_type, content):
        """Add contextual information to the project"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'type': context_type,
            'content': content
        }
        self.project_history.append(entry)
        
    def get_context_summary(self):
        """Get a summary of all project context for AI consumption"""
        summary = f"""
PROJECT CONTEXT FOR AI:

Client: {self.client_name or 'Not set'}
Industry: {self.industry or 'Not set'}  
Facility: {self.facility_type or 'Not set'}
Current Phase: {self.project_phase}

Files Uploaded: {len(self.uploaded_files)}
{self._format_files()}

Email Threads: {len(self.email_context)}
{self._format_emails()}

Key Findings So Far:
{self._format_findings()}

Proposed Schedules:
{self._format_schedules()}

Recent Activity:
{self._format_recent_history()}
"""
        return summary
        
    def _format_files(self):
        if not self.uploaded_files:
            return "  None yet"
        return "\n".join([f"  - {f['name']} ({f['type']})" for f in self.uploaded_files[-5:]])
    
    def _format_emails(self):
        if not self.email_context:
            return "  None yet"
        return "\n".join([f"  - {e['subject']}" for e in self.email_context[-3:]])
    
    def _format_findings(self):
        if not self.key_findings:
            return "  None yet"
        return "\n".join([f"  - {f}" for f in self.key_findings[-5:]])
    
    def _format_schedules(self):
        if not self.schedules_proposed:
            return "  None yet"
        return "\n".join([f"  - {s}" for s in self.schedules_proposed])
    
    def _format_recent_history(self):
        recent = self.project_history[-5:]
        if not recent:
            return "  No activity yet"
        return "\n".join([f"  - [{h['timestamp'][:10]}] {h['type']}: {str(h['content'])[:60]}..." for h in recent])


def detect_project_intent(user_message, current_workflow=None):
    """
    Analyzes user message to determine what project action they want
    Returns: (intent, parameters)
    
    Intents:
    - create_data_collection: User wants data collection document
    - analyze_files: User has files to analyze
    - review_emails: User wants email context reviewed
    - generate_linkedin: User wants LinkedIn content
    - create_proposal: User wants scope of work / proposal
    - create_presentation: User wants PowerPoint
    - next_phase: User wants to move to next project phase
    - general_question: General consulting question
    """
    
    message_lower = user_message.lower()
    
    # Data collection intent
    if any(phrase in message_lower for phrase in [
        'data collection', 'collect data', 'data request',
        'need data from client', 'initial data', 'data gathering'
    ]):
        return 'create_data_collection', {
            'document_type': 'data_collection',
            'phase': 'initial'
        }
    
    # File analysis intent  
    if any(phrase in message_lower for phrase in [
        'analyze file', 'process file', 'look at file',
        'review file', 'uploaded file', 'have data',
        'payroll data', 'survey data', 'cost data'
    ]):
        return 'analyze_files', {
            'awaiting_files': True
        }
    
    # Email review intent
    if any(phrase in message_lower for phrase in [
        'review email', 'read email', 'email thread',
        'email with client', 'correspondence', 'email exchange'
    ]):
        return 'review_emails', {
            'awaiting_emails': True
        }
    
    # LinkedIn content intent
    if any(phrase in message_lower for phrase in [
        'linkedin post', 'linkedin content', 'social media',
        'post about', 'share on linkedin'
    ]):
        return 'generate_linkedin', {
            'content_type': 'linkedin_post'
        }
    
    # Proposal/SOW intent
    if any(phrase in message_lower for phrase in [
        'proposal', 'scope of work', 'sow', 'contract',
        'engagement letter', 'quote'
    ]):
        return 'create_proposal', {
            'document_type': 'proposal'
        }
    
    # Presentation intent
    if any(phrase in message_lower for phrase in [
        'powerpoint', 'presentation', 'slides', 'deck',
        'client presentation'
    ]):
        return 'create_presentation', {
            'document_type': 'presentation'
        }
    
    # Phase transition intent
    if any(phrase in message_lower for phrase in [
        'next phase', 'move forward', 'next step',
        'ready to', 'proceed to'
    ]):
        return 'next_phase', {
            'current_phase': current_workflow.project_phase if current_workflow else 'unknown'
        }
    
    # General question
    return 'general_question', {}


def create_project_aware_prompt(user_request, intent, workflow, knowledge_context=""):
    """
    Creates an enhanced prompt that includes full project context
    This makes the AI aware of the entire consulting engagement
    """
    
    project_context = workflow.get_context_summary() if workflow else "No active project context"
    
    prompt_templates = {
        'create_data_collection': f"""You are creating a Week 1 Data Collection document for Shiftwork Solutions LLC.

{knowledge_context}

CURRENT PROJECT CONTEXT:
{project_context}

USER REQUEST: {user_request}

CRITICAL: Create a professional Word document (.docx) using this EXACT structure:

=== DOCUMENT STRUCTURE ===

**TITLE (Title style):**
Kick-off and Data Collection – Week 1

**INTRODUCTION:**
Congratulations on starting your project with Shiftwork Solutions LLC. Your Project Manager, Jim Dillingham, will guide you through this engagement.

This document is your guide through the first week of the project.

**CONTACT INFORMATION:**
James Dillingham
Project Manager and Subject Matter Expert
Shiftwork Solutions LLC
Email: jim@shift-work.com
Phone: 415.265.1621
www.shift-work.com

Let's get this project started!

**SECTION 1: Dates and Activities (Heading 1)**
When: [Insert week/dates]
• [Day]: kick-off day
• Kick-off meeting (30 minutes) with management team
• Site tour
• Data collection and interviews begin
• [Other days]: interviews and data collection
• [Final day]: review meeting (15 minutes) with leadership team

**SECTION 2: Data Collection Needs (Heading 1)**
We need the following information:

1. **Operational Data:**
   • Current shift schedules for all departments
   • Staffing levels and headcount by shift
   • Operating hours and production schedules

2. **Financial Data:**
   • Payroll data (last 12 months if possible)
   • Overtime costs and trends
   • Labor cost structure

3. **People Data:**
   • Demographics (tenure, age ranges)
   • Turnover data
   • Absenteeism patterns

**SECTION 3: Interview Schedule (Heading 1)**
We will conduct interviews with:
• Leadership team members
• Department supervisors
• Front-line employees (sample)

Duration: 30-60 minutes each
Format: One-on-one or small group

**SECTION 4: Deliverables (Heading 1)**
By end of Week 1:
• Complete data collection
• Initial observations
• Schedule for Week 2 analysis

Please provide this data by [date] to keep the project on schedule.

Thank you for your partnership!

=== END STRUCTURE ===

Format this as a clean, professional document ready to send to the client.
Use proper spacing, bullet points, and section headers.
Customize the dates and details based on the client information in the project context.""",

        'analyze_files': f"""You are analyzing client data files for a Shiftwork Solutions consulting project.

{knowledge_context}

CURRENT PROJECT CONTEXT:
{project_context}

USER REQUEST: {user_request}

The user will upload files for analysis. Based on the project context:
1. Identify what type of data this is (payroll, survey, operational, etc.)
2. Perform relevant analysis using Shiftwork Solutions methodologies
3. Extract key findings related to shift schedule optimization
4. Flag any data quality issues
5. Provide recommendations based on the analysis

Use cost analysis principles from the Essential Guide and Implementation Manuals.""",

        'review_emails': f"""You are reviewing email correspondence for a Shiftwork Solutions project.

{knowledge_context}

CURRENT PROJECT CONTEXT:
{project_context}

USER REQUEST: {user_request}

Review the email thread and:
1. Extract key client requirements and concerns
2. Identify decision-makers and their priorities
3. Note any commitments or deadlines
4. Flag potential scope changes
5. Suggest next steps based on the conversation

Provide a concise summary for project planning.""",

        'generate_linkedin': f"""You are creating LinkedIn content for Shiftwork Solutions LLC.

{knowledge_context}

CURRENT PROJECT CONTEXT:
{project_context}

USER REQUEST: {user_request}

Create a LinkedIn post that:
1. Shares insights from this project (without identifying the client)
2. Demonstrates Shiftwork Solutions expertise
3. Provides value to operations managers and HR leaders
4. Includes relevant statistics or findings
5. Uses professional but engaging tone

Length: 150-250 words
Include: 3-5 relevant hashtags""",

        'create_proposal': f"""You are creating a proposal/scope of work for Shiftwork Solutions LLC.

{knowledge_context}

CURRENT PROJECT CONTEXT:
{project_context}

USER REQUEST: {user_request}

Create a professional proposal that includes:
1. Executive Summary
2. Understanding of Client Needs
3. Our Approach (use proven methodology from Scope_of_work_by_AI.docx)
4. Deliverables and Timeline  
5. Investment and Terms
6. Why Shiftwork Solutions

Use the company's contract templates and pricing models as reference.""",

        'create_presentation': f"""You are creating a PowerPoint presentation for Shiftwork Solutions LLC.

{knowledge_context}

CURRENT PROJECT CONTEXT:
{project_context}

USER REQUEST: {user_request}

Outline a presentation with:
1. Title slide
2. Client situation overview
3. Analysis findings (use data from project context)
4. Recommendations
5. Implementation approach
6. Next steps

Format as slide-by-slide outline with bullet points for each slide.""",

        'general_question': f"""You are answering a question about a Shiftwork Solutions consulting project.

{knowledge_context}

CURRENT PROJECT CONTEXT:
{project_context}

USER REQUEST: {user_request}

Provide a helpful response based on:
1. The current project context
2. Shiftwork Solutions' proven methodologies
3. Your 30+ years of expertise in the knowledge base

Be specific and actionable."""
    }
    
    template = prompt_templates.get(intent, prompt_templates['general_question'])
    return template


# I did no harm and this file is not truncated
