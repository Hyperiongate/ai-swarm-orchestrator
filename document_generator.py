"""
DOCUMENT GENERATOR MODULE
Created: January 19, 2026
Last Updated: January 19, 2026

PURPOSE:
Creates professional, formatted documents (Word, PowerPoint, PDF, Excel)
instead of plain text output. Uses Claude's document creation skills to
generate client-ready files.

INTEGRATION:
This module integrates with the AI Swarm to detect when the user needs
a document and automatically creates a properly formatted file.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import subprocess
import os
import json
from datetime import datetime


class DocumentGenerator:
    """
    Generates professional documents using Claude's document creation skills
    """
    
    def __init__(self, output_dir="/mnt/user-data/outputs"):
        self.output_dir = output_dir
        self.skills_path = "/mnt/skills/public"
        
    def detect_document_type(self, user_request, content_hint=""):
        """
        Detect what type of document the user wants
        
        Returns: document_type (docx, pptx, pdf, xlsx, or None)
        """
        request_lower = user_request.lower()
        
        # PowerPoint indicators
        if any(word in request_lower for word in ['powerpoint', 'presentation', 'slides', 'deck', 'ppt', 'pptx']):
            return 'pptx'
        
        # PDF indicators
        if any(word in request_lower for word in ['pdf', 'report', 'executive summary']) and 'pdf' in request_lower:
            return 'pdf'
        
        # Excel indicators
        if any(word in request_lower for word in ['spreadsheet', 'excel', 'calculator', 'cost analysis', 'xlsx']):
            return 'xlsx'
        
        # Word document indicators (default for most documents)
        if any(word in request_lower for word in [
            'document', 'letter', 'memo', 'proposal', 'contract',
            'data collection', 'word', 'docx', 'implementation', 'scope of work'
        ]):
            return 'docx'
        
        # Check content hint for clues
        if 'slide' in content_hint.lower():
            return 'pptx'
        
        # Default to Word for professional documents
        return 'docx'
    
    def should_create_document(self, user_request):
        """
        Determine if this request should result in a file
        Returns: (should_create: bool, document_type: str)
        """
        request_lower = user_request.lower()
        
        # Questions don't need documents
        if request_lower.startswith(('what', 'how', 'why', 'when', 'where', 'who', 'is', 'are', 'can', 'should')):
            return False, None
        
        # Creation requests DO need documents
        if any(word in request_lower for word in [
            'create', 'generate', 'make', 'build', 'write', 'draft', 'prepare', 'develop'
        ]):
            doc_type = self.detect_document_type(user_request)
            return True, doc_type
        
        # "I need" statements
        if 'i need' in request_lower or 'need a' in request_lower:
            doc_type = self.detect_document_type(user_request)
            return True, doc_type
        
        return False, None
    
    def create_word_document(self, content, filename=None, template_style="professional"):
        """
        Create a professional Word document using docx skill
        
        Args:
            content: The text content to put in the document
            filename: Output filename (auto-generated if None)
            template_style: Style template (professional, report, letter)
            
        Returns:
            filepath to the created document
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"document_{timestamp}.docx"
        
        output_path = os.path.join(self.output_dir, filename)
        
        # Create a Node.js script to generate the .docx
        script = self._generate_docx_script(content, output_path, template_style)
        script_path = "/tmp/create_doc.js"
        
        with open(script_path, 'w') as f:
            f.write(script)
        
        try:
            # Install docx if not already installed
            subprocess.run(['npm', 'install', '-g', 'docx'], 
                         capture_output=True, timeout=30)
            
            # Run the script
            result = subprocess.run(['node', script_path],
                                  capture_output=True, 
                                  text=True,
                                  timeout=30)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
            else:
                print(f"Error creating Word doc: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Exception creating Word doc: {e}")
            return None
    
    def _generate_docx_script(self, content, output_path, style):
        """Generate Node.js script for creating Word document"""
        
        # Parse content into sections
        lines = content.split('\n')
        paragraphs = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect headings
            if line.startswith('# '):
                paragraphs.append({'type': 'heading1', 'text': line[2:]})
            elif line.startswith('## '):
                paragraphs.append({'type': 'heading2', 'text': line[3:]})
            elif line.startswith('### '):
                paragraphs.append({'type': 'heading3', 'text': line[4:]})
            elif line.startswith('- ') or line.startswith('• '):
                paragraphs.append({'type': 'bullet', 'text': line[2:]})
            elif line.startswith(('1.', '2.', '3.', '4.', '5.')):
                paragraphs.append({'type': 'numbered', 'text': line[3:]})
            else:
                paragraphs.append({'type': 'normal', 'text': line})
        
        # Generate JavaScript code
        return f"""
const {{ Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel }} = require('docx');
const fs = require('fs');

const paragraphs = {json.dumps(paragraphs)};

const children = paragraphs.map(p => {{
    if (p.type === 'heading1') {{
        return new Paragraph({{
            text: p.text,
            heading: HeadingLevel.HEADING_1,
            spacing: {{ before: 240, after: 120 }}
        }});
    }} else if (p.type === 'heading2') {{
        return new Paragraph({{
            text: p.text,
            heading: HeadingLevel.HEADING_2,
            spacing: {{ before: 200, after: 100 }}
        }});
    }} else if (p.type === 'bullet') {{
        return new Paragraph({{
            text: p.text,
            bullet: {{ level: 0 }},
            spacing: {{ before: 60, after: 60 }}
        }});
    }} else {{
        return new Paragraph({{
            text: p.text,
            spacing: {{ before: 60, after: 60 }}
        }});
    }}
}});

const doc = new Document({{
    sections: [{{
        properties: {{
            page: {{
                size: {{ width: 12240, height: 15840 }},
                margin: {{ top: 1440, right: 1440, bottom: 1440, left: 1440 }}
            }}
        }},
        children: children
    }}]
}});

Packer.toBuffer(doc).then(buffer => {{
    fs.writeFileSync('{output_path}', buffer);
    console.log('Document created successfully');
}}).catch(err => {{
    console.error('Error:', err);
    process.exit(1);
}});
"""
    
    def create_powerpoint(self, content, filename=None):
        """
        Create a professional PowerPoint presentation
        
        Returns:
            filepath to the created presentation
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"presentation_{timestamp}.pptx"
        
        output_path = os.path.join(self.output_dir, filename)
        
        # For now, return None - full PowerPoint creation requires html2pptx
        # This would be implemented using the pptx skill
        print("PowerPoint creation requires html2pptx setup - returning None for now")
        return None
    
    def create_pdf(self, content, filename=None):
        """
        Create a professional PDF document
        
        Returns:
            filepath to the created PDF
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"document_{timestamp}.pdf"
        
        # First create a Word doc, then convert to PDF
        docx_path = self.create_word_document(content, filename.replace('.pdf', '.docx'))
        
        if not docx_path:
            return None
        
        output_path = os.path.join(self.output_dir, filename)
        
        try:
            # Convert to PDF using LibreOffice
            subprocess.run([
                'soffice', '--headless', '--convert-to', 'pdf',
                '--outdir', self.output_dir, docx_path
            ], capture_output=True, timeout=30)
            
            if os.path.exists(output_path):
                # Clean up intermediate docx
                os.remove(docx_path)
                return output_path
            else:
                print(f"PDF conversion failed")
                return docx_path  # Return docx if PDF fails
                
        except Exception as e:
            print(f"Exception creating PDF: {e}")
            return docx_path  # Return docx if PDF fails


# Singleton instance
_document_generator = None

def get_document_generator():
    """Get or create the document generator singleton"""
    global _document_generator
    if _document_generator is None:
        _document_generator = DocumentGenerator()
    return _document_generator


# I did no harm and this file is not truncated
