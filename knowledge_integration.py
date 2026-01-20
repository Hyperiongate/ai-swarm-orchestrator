"""
SWARM PROJECT KNOWLEDGE INTEGRATION MODULE
Created: January 19, 2026
Last Updated: January 19, 2026

PURPOSE:
Integrates the entire Shiftwork Solutions project knowledge base into the AI Swarm,
giving it access to 30+ years of expertise, templates, frameworks, and methodologies.

FEATURES:
- Document extraction from all project files
- Semantic search across knowledge base
- Template and framework retrieval
- Expertise injection into swarm prompts
- Real-time knowledge access during task execution

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import os
import json
from pathlib import Path
import sqlite3
from datetime import datetime
import re

# For document processing
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import openpyxl
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


class ProjectKnowledgeBase:
    """
    Manages access to the entire Shiftwork Solutions project knowledge base.
    Provides search, retrieval, and integration with the AI Swarm.
    """
    
    def __init__(self, project_path="/mnt/project", db_path="swarm_intelligence.db"):
        self.project_path = Path(project_path)
        self.db_path = db_path
        self.knowledge_index = {}
        
    def initialize(self):
        """
        Initialize the knowledge base:
        1. Create knowledge_documents table
        2. Extract all documents
        3. Build searchable index
        """
        print("🔍 Initializing Project Knowledge Base...")
        
        # Create database table
        self._create_knowledge_table()
        
        # Extract and index all documents
        self._index_all_documents()
        
        print(f"✅ Knowledge Base Ready: {len(self.knowledge_index)} documents indexed")
        
    def _create_knowledge_table(self):
        """Create knowledge_documents table in the swarm database"""
        db = sqlite3.connect(self.db_path)
        db.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_type TEXT,
                title TEXT,
                content TEXT,
                keywords TEXT,
                category TEXT,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                word_count INTEGER,
                metadata TEXT
            )
        ''')
        db.commit()
        db.close()
        
    def _index_all_documents(self):
        """Extract and index all documents from the project knowledge base"""
        if not self.project_path.exists():
            print(f"⚠️ Project path not found: {self.project_path}")
            return
            
        db = sqlite3.connect(self.db_path)
        
        # Clear existing index
        db.execute('DELETE FROM knowledge_documents')
        db.commit()
        
        for file_path in self.project_path.iterdir():
            if file_path.is_file():
                try:
                    content = self._extract_content(file_path)
                    if content:
                        metadata = self._extract_metadata(file_path, content)
                        
                        db.execute('''
                            INSERT INTO knowledge_documents 
                            (filename, file_type, title, content, keywords, category, word_count, metadata)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            file_path.name,
                            file_path.suffix,
                            metadata['title'],
                            content[:50000],  # Store first 50k chars
                            metadata['keywords'],
                            metadata['category'],
                            metadata['word_count'],
                            json.dumps(metadata)
                        ))
                        
                        self.knowledge_index[file_path.name] = {
                            'content': content,
                            'metadata': metadata
                        }
                        
                        print(f"  ✅ Indexed: {file_path.name} ({metadata['word_count']} words)")
                        
                except Exception as e:
                    # Only show errors for unexpected failures, not format mismatches
                    error_msg = str(e)
                    if "File is not a zip file" in error_msg or "not a zip file" in error_msg.lower():
                        # This is a mislabeled file (text saved as .docx) - try as text
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                if content:
                                    metadata = self._extract_metadata(file_path, content)
                                    db.execute('''
                                        INSERT INTO knowledge_documents 
                                        (filename, file_type, title, content, keywords, category, word_count, metadata)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', (
                                        file_path.name,
                                        file_path.suffix,
                                        metadata['title'],
                                        content[:50000],
                                        metadata['keywords'],
                                        metadata['category'],
                                        metadata['word_count'],
                                        json.dumps(metadata)
                                    ))
                                    self.knowledge_index[file_path.name] = {
                                        'content': content,
                                        'metadata': metadata
                                    }
                                    print(f"  ✅ Indexed: {file_path.name} ({metadata['word_count']} words) [as text]")
                        except:
                            pass  # Silently skip if text extraction also fails
                    elif "EOF marker not found" in error_msg:
                        pass  # Silently skip corrupted PDFs
                    else:
                        print(f"  ⚠️ Error indexing {file_path.name}: {e}")
                    
        db.commit()
        db.close()
        
    def _extract_content(self, file_path):
        """Extract text content from various file types"""
        suffix = file_path.suffix.lower()
        
        try:
            # Plain text files
            if suffix in ['.txt', '.md', '']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
                    
            # Word documents
            elif suffix == '.docx' and DOCX_AVAILABLE:
                try:
                    doc = Document(file_path)
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    return '\n\n'.join(paragraphs)
                except Exception as e:
                    # If docx fails, try reading as plain text (mislabeled file)
                    if "not a zip file" in str(e).lower():
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            return f.read()
                    raise  # Re-raise other errors
                
            # Excel files
            elif suffix == '.xlsx' and EXCEL_AVAILABLE:
                wb = openpyxl.load_workbook(file_path, data_only=True)
                content = []
                for sheet in wb.worksheets:
                    content.append(f"=== {sheet.title} ===\n")
                    for row in sheet.iter_rows(values_only=True):
                        row_text = ' | '.join(str(cell) if cell else '' for cell in row)
                        if row_text.strip():
                            content.append(row_text)
                return '\n'.join(content)
                
            # PDF files
            elif suffix == '.pdf' and PDF_AVAILABLE:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    content = []
                    for page in reader.pages:
                        content.append(page.extract_text())
                    return '\n\n'.join(content)
                    
        except Exception as e:
            print(f"    Error extracting {file_path.name}: {e}")
            
        return None
        
    def _extract_metadata(self, file_path, content):
        """Extract metadata from document content"""
        # Count words
        word_count = len(content.split())
        
        # Try to extract title (first non-empty line or filename)
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        title = lines[0] if lines else file_path.stem.replace('_', ' ')
        
        # Extract keywords (common industry terms)
        keywords = self._extract_keywords(content)
        
        # Categorize document
        category = self._categorize_document(file_path.name, content)
        
        return {
            'title': title[:200],
            'keywords': ', '.join(keywords[:20]),
            'category': category,
            'word_count': word_count,
            'file_size': file_path.stat().st_size,
            'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        }
        
    def _extract_keywords(self, content):
        """Extract relevant keywords from content"""
        # Industry-specific terms
        terms = [
            'schedule', 'shift', 'overtime', 'staffing', 'crew', 'rotation',
            'coverage', 'fatigue', 'turnover', 'work-life balance', '12-hour',
            '8-hour', 'continental', 'DuPont', 'pitman', 'panama', '2-2-3',
            'fixed', 'rotating', 'survey', 'implementation', 'change management',
            'employee', 'supervisor', 'production', 'manufacturing', 'operations',
            'consultation', 'assessment', 'analysis', 'recommendation', 'cost'
        ]
        
        content_lower = content.lower()
        found = [term for term in terms if term in content_lower]
        
        return found[:20]  # Return top 20
        
    def _categorize_document(self, filename, content):
        """Categorize document based on filename and content"""
        filename_lower = filename.lower()
        content_lower = content.lower()[:1000]  # First 1000 chars
        
        if 'contract' in filename_lower:
            return 'Contract'
        elif 'implementation' in filename_lower or 'implementation' in content_lower:
            return 'Implementation Guide'
        elif 'survey' in filename_lower or 'survey' in content_lower:
            return 'Survey & Assessment'
        elif 'schedule' in filename_lower and 'definitive' in filename_lower:
            return 'Schedule Library'
        elif 'bio' in filename_lower or 'profile' in filename_lower:
            return 'Company Profile'
        elif 'lesson' in filename_lower:
            return 'Lessons Learned'
        elif 'guide' in filename_lower or 'essential' in filename_lower:
            return 'Best Practices Guide'
        elif 'summary' in filename_lower:
            return 'Executive Summary'
        elif 'scope' in filename_lower:
            return 'Scope of Work'
        else:
            return 'Reference Material'
            
    def search(self, query, max_results=5):
        """
        Search the knowledge base for relevant documents
        Returns list of relevant documents with excerpts
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        results = []
        
        for filename, data in self.knowledge_index.items():
            content = data['content'].lower()
            metadata = data['metadata']
            
            # Calculate relevance score
            score = 0
            
            # Exact phrase match
            if query_lower in content:
                score += 10
                
            # Word matches
            content_words = set(content.split())
            matching_words = query_words.intersection(content_words)
            score += len(matching_words) * 2
            
            # Title/category matches
            if any(word in metadata['title'].lower() for word in query_words):
                score += 5
            if any(word in metadata['category'].lower() for word in query_words):
                score += 3
                
            if score > 0:
                # Extract relevant excerpt
                excerpt = self._extract_excerpt(data['content'], query_lower)
                
                results.append({
                    'filename': filename,
                    'title': metadata['title'],
                    'category': metadata['category'],
                    'score': score,
                    'excerpt': excerpt,
                    'word_count': metadata['word_count']
                })
                
        # Sort by relevance
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return results[:max_results]
        
    def _extract_excerpt(self, content, query, context_words=100):
        """Extract relevant excerpt around the query"""
        content_lower = content.lower()
        query_pos = content_lower.find(query)
        
        if query_pos == -1:
            # No exact match, return first N words
            words = content.split()[:context_words]
            return ' '.join(words) + '...'
            
        # Extract context around query
        words = content.split()
        query_word_pos = len(content[:query_pos].split())
        
        start = max(0, query_word_pos - context_words // 2)
        end = min(len(words), query_word_pos + context_words // 2)
        
        excerpt = ' '.join(words[start:end])
        
        if start > 0:
            excerpt = '...' + excerpt
        if end < len(words):
            excerpt = excerpt + '...'
            
        return excerpt
        
    def get_document(self, filename):
        """Retrieve full document by filename"""
        if filename in self.knowledge_index:
            return self.knowledge_index[filename]
        return None
        
    def get_all_documents(self):
        """Get list of all indexed documents"""
        return [
            {
                'filename': filename,
                'title': data['metadata']['title'],
                'category': data['metadata']['category'],
                'word_count': data['metadata']['word_count']
            }
            for filename, data in self.knowledge_index.items()
        ]
        
    def get_context_for_task(self, task_description, max_context=5000):
        """
        Get relevant context from knowledge base for a specific task
        Returns a formatted context string to inject into prompts
        """
        # Search for relevant documents
        results = self.search(task_description, max_results=3)
        
        if not results:
            return ""
            
        # Build context string
        context = "\n\n=== RELEVANT SHIFTWORK SOLUTIONS EXPERTISE ===\n\n"
        
        for result in results:
            context += f"📄 {result['title']} ({result['category']})\n"
            context += f"{result['excerpt']}\n\n"
            
        # Trim to max length
        if len(context) > max_context:
            context = context[:max_context] + "\n\n[Context truncated...]"
            
        return context
        
    def get_stats(self):
        """Get knowledge base statistics"""
        total_docs = len(self.knowledge_index)
        total_words = sum(d['metadata']['word_count'] for d in self.knowledge_index.values())
        
        categories = {}
        for data in self.knowledge_index.values():
            cat = data['metadata']['category']
            categories[cat] = categories.get(cat, 0) + 1
            
        return {
            'total_documents': total_docs,
            'total_words': total_words,
            'categories': categories,
            'available_templates': self._get_template_list()
        }
        
    def _get_template_list(self):
        """Get list of available templates"""
        templates = []
        for filename, data in self.knowledge_index.items():
            category = data['metadata']['category']
            if category in ['Contract', 'Implementation Guide', 'Scope of Work', 'Executive Summary']:
                templates.append({
                    'name': data['metadata']['title'],
                    'type': category,
                    'filename': filename
                })
        return templates


# Singleton instance
_knowledge_base = None

def get_knowledge_base():
    """Get or create singleton knowledge base instance"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = ProjectKnowledgeBase()
        _knowledge_base.initialize()
    return _knowledge_base


# I did no harm and this file is not truncated
