"""
OUTPUT FORMATTER - ENFORCEMENT MODULE
Created: January 19, 2026
Last Updated: January 19, 2026

PURPOSE:
This module ENFORCES professional output formatting by detecting unacceptable
text dumps and automatically converting them into clean, structured formats.

CRITICAL RULES:
1. NO walls of text with asterisks
2. NO markdown symbols in final output
3. NO unreadable schedule dumps
4. ALL schedule outputs must be formatted tables or documents

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import re
from datetime import datetime


class OutputFormatter:
    """
    Enforces professional output standards and auto-fixes terrible formatting
    """
    
    def __init__(self):
        self.unacceptable_patterns = [
            r'\*\*[^*]+\*\*',  # Bold markdown
            r'\*[^*]+\*',      # Italic markdown
            r'#{2,}',          # Multiple hashes
            r'\n{3,}',         # Multiple blank lines
        ]
    
    def is_unacceptable(self, text):
        """
        Detect if output is an unacceptable text dump
        
        Returns: (is_bad: bool, reasons: list)
        """
        reasons = []
        
        # Check for excessive markdown
        asterisk_count = text.count('**')
        if asterisk_count > 10:
            reasons.append(f"Excessive markdown symbols ({asterisk_count} instances of **)")
        
        # Check for wall of text (long lines without breaks)
        lines = text.split('\n')
        long_lines = [l for l in lines if len(l) > 200]
        if len(long_lines) > 3:
            reasons.append(f"Wall of text detected ({len(long_lines)} lines over 200 chars)")
        
        # Check for schedule dumps (W = Work, O = Off patterns)
        if re.search(r'[WO\s]{50,}', text):
            reasons.append("Schedule dump detected - needs table format")
        
        # Check for excessive consecutive capitals
        if re.search(r'[A-Z\s]{30,}', text):
            reasons.append("EXCESSIVE CAPS DETECTED")
        
        # Check for pattern: "**Week N:** Work X days"
        if re.search(r'\*\*Week \d+:\*\*', text):
            reasons.append("Raw schedule pattern with markdown - needs formatting")
        
        return (len(reasons) > 0, reasons)
    
    def detect_content_type(self, text):
        """
        Detect what type of content this is
        
        Returns: content_type string
        """
        text_lower = text.lower()
        
        # Schedule patterns
        if any(word in text_lower for word in ['schedule', 'rotation', 'shift', 'dupont', '2-2-3', 'days off', 'week 1', 'week 2']):
            if re.search(r'week \d+', text_lower):
                return 'schedule'
        
        # Analysis/report patterns
        if any(word in text_lower for word in ['analysis', 'findings', 'recommendations', 'summary']):
            return 'report'
        
        # Comparison patterns
        if 'vs' in text_lower or 'versus' in text_lower or 'comparison' in text_lower:
            return 'comparison'
        
        # Proposal patterns
        if any(word in text_lower for word in ['proposal', 'scope of work', 'deliverables']):
            return 'proposal'
        
        return 'general'
    
    def clean_schedule_output(self, text):
        """
        Convert terrible schedule dump into clean formatted output
        """
        lines = text.split('\n')
        
        # Build clean structure
        output = []
        output.append("=" * 80)
        output.append("SCHEDULE SUMMARY")
        output.append("=" * 80)
        output.append("")
        
        # Extract schedule name/type
        for line in lines[:5]:
            if 'schedule' in line.lower() or 'rotation' in line.lower():
                clean_line = line.replace('**', '').replace('##', '').replace('*', '').strip()
                if clean_line:
                    output.append(f"Schedule Type: {clean_line}")
                    output.append("")
                    break
        
        # Extract rotation pattern
        output.append("ROTATION PATTERN:")
        output.append("-" * 80)
        
        # Find weeks
        week_pattern = r'[*#\s]*Week (\d+)[*:#\s]*(.*?)(?=Week \d+|$)'
        weeks = re.findall(week_pattern, text, re.IGNORECASE | re.DOTALL)
        
        for week_num, week_content in weeks:
            clean_content = week_content.replace('**', '').replace('*', '').strip()
            
            # Extract work/off pattern
            if 'work' in clean_content.lower():
                work_match = re.search(r'work\s+(\d+)\s+days?', clean_content, re.IGNORECASE)
                if work_match:
                    work_days = work_match.group(1)
                    output.append(f"  Week {week_num}: Work {work_days} days")
        
        output.append("")
        output.append("-" * 80)
        
        # Extract time off pattern
        output.append("")
        output.append("TIME OFF PATTERN:")
        output.append("-" * 80)
        
        # Find days off mentions
        days_off_pattern = r'(\d+)\s*consecutive days?\s*off'
        days_off = re.findall(days_off_pattern, text, re.IGNORECASE)
        if days_off:
            max_days_off = max([int(d) for d in days_off])
            output.append(f"  Maximum consecutive days off: {max_days_off} days")
        
        # Find frequency
        if 'every 4 weeks' in text.lower():
            output.append(f"  Rotation cycle: Every 4 weeks")
        elif 'every 28 days' in text.lower():
            output.append(f"  Rotation cycle: 28 days")
        
        output.append("")
        output.append("-" * 80)
        
        # Extract key features
        output.append("")
        output.append("KEY FEATURES:")
        output.append("-" * 80)
        
        if 'work time' in text.lower():
            work_time_match = re.search(r'(\d+)%\s*work time', text, re.IGNORECASE)
            if work_time_match:
                output.append(f"  • Work time percentage: {work_time_match.group(1)}%")
        
        if 'off time' in text.lower():
            off_time_match = re.search(r'(\d+)%\s*(?:time )?off', text, re.IGNORECASE)
            if off_time_match:
                output.append(f"  • Time off percentage: {off_time_match.group(1)}%")
        
        # Find alternative distributions if mentioned
        if 'alternative distribution' in text.lower():
            output.append("")
            output.append("ALTERNATIVE PATTERNS AVAILABLE:")
            output.append("-" * 80)
            output.append("  • Variations can be designed based on employee preferences")
            output.append("  • Survey your workforce to determine optimal distribution")
        
        output.append("")
        output.append("=" * 80)
        output.append(f"Generated by Shiftwork Solutions LLC | {datetime.now().strftime('%B %d, %Y')}")
        output.append("=" * 80)
        
        return '\n'.join(output)
    
    def clean_general_output(self, text):
        """
        Clean up general text by removing markdown and improving structure
        """
        # Remove markdown
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Remove bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Remove italic
        text = re.sub(r'#{1,6}\s+', '', text)           # Remove headers
        
        # Fix spacing
        text = re.sub(r'\n{3,}', '\n\n', text)          # Max 2 line breaks
        
        # Add section breaks where appropriate
        lines = text.split('\n')
        output = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                output.append('')
                continue
            
            # Detect section headers (lines ending with :)
            if line.endswith(':') and len(line) < 60:
                if i > 0:
                    output.append('')
                output.append('=' * len(line))
                output.append(line)
                output.append('=' * len(line))
                output.append('')
            else:
                output.append(line)
        
        return '\n'.join(output)
    
    def format_output(self, text, content_type=None):
        """
        Main formatting function - converts bad output to good output
        
        Args:
            text: The raw output text
            content_type: Optional override of detected type
            
        Returns:
            Cleaned, professional output
        """
        # Detect issues
        is_bad, reasons = self.is_unacceptable(text)
        
        if not is_bad:
            return text  # Already acceptable
        
        # Detect content type if not provided
        if not content_type:
            content_type = self.detect_content_type(text)
        
        # Apply appropriate formatting
        if content_type == 'schedule':
            return self.clean_schedule_output(text)
        else:
            return self.clean_general_output(text)
    
    def should_create_document(self, text, user_request):
        """
        Determine if this output should be converted to a document file
        
        Returns: (should_create: bool, doc_type: str)
        """
        request_lower = user_request.lower()
        
        # Always create documents for these requests
        if any(word in request_lower for word in [
            'create schedule', 'schedule design', 'rotation schedule',
            'proposal', 'report', 'analysis', 'document'
        ]):
            # Determine document type
            if 'schedule' in request_lower:
                return True, 'docx'  # Schedule should be Word doc with table
            elif 'proposal' in request_lower:
                return True, 'docx'
            elif 'analysis' in request_lower:
                return True, 'docx'
        
        # Check if output is long/complex enough to warrant a document
        if len(text) > 1000:
            content_type = self.detect_content_type(text)
            if content_type in ['schedule', 'report', 'proposal']:
                return True, 'docx'
        
        return False, None


# Singleton instance
_output_formatter = None

def get_output_formatter():
    """Get or create the output formatter singleton"""
    global _output_formatter
    if _output_formatter is None:
        _output_formatter = OutputFormatter()
    return _output_formatter


# I did no harm and this file is not truncated
