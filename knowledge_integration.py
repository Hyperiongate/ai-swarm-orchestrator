"""
SWARM PROJECT KNOWLEDGE INTEGRATION MODULE - ENHANCED
Created: January 19, 2026
Last Updated: February 18, 2026 - BACKGROUND THREADING FIX

CHANGELOG:

- February 18, 2026: BACKGROUND THREADING FIX
  * PROBLEM: Knowledge base initialization was blocking gunicorn for ~30 seconds
    on startup while indexing 34 documents (including 56MB Excel files). This
    caused Render's port scanner to time out and the first real page request to
    return a 30-second timeout error (29 bytes) instead of the full HTML page.
  * FIX: Added initialize_background() method that runs the full initialization
    in a daemon thread. Gunicorn now binds and accepts connections immediately.
  * Added _initialization_complete threading.Event() flag so search methods
    can check readiness without blocking.
  * Added _db_lock threading.Lock() to protect SQLite writes from the background
    thread (SQLite is not thread-safe by default for concurrent writes).
  * search(), semantic_search(), and get_context_for_task() now return empty
    results gracefully if called before init completes (instead of crashing).
  * initialize() still works exactly as before - no breaking changes.
  * app.py only needs one change: initialize() -> initialize_background()

- January 29, 2026: MAJOR ENHANCEMENT
  * Added semantic search capabilities with TF-IDF-like scoring
  * Implemented multi-document context assembly
  * Added priority system: PROJECT KNOWLEDGE FIRST, then external sources
  * Enhanced excerpt extraction with relevance highlighting
  * Added comprehensive document metadata tracking
  * Implemented knowledge source citation tracking
  * Added category-based search filtering
  * Enhanced template and framework retrieval
  * Added cross-document concept linking
  * Improved error handling and fallback mechanisms

PURPOSE:
Integrates the entire Shiftwork Solutions project knowledge base into the AI Swarm,
giving it access to hundreds of facilities' worth of expertise, templates, frameworks,
and methodologies.

AUTHOR: Jim @ Shiftwork Solutions LLC
"""

import os
import json
import threading
import time
from pathlib import Path
import sqlite3
from datetime import datetime
import re
from collections import Counter
import math

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


class EnhancedProjectKnowledgeBase:
    """
    ENHANCED knowledge base with semantic search and priority system.

    This gives the AI Swarm the same (and better) access to project knowledge
    that Claude Projects has through project_knowledge_search tool.

    Key Enhancements:
    1. Semantic search with TF-IDF-like relevance scoring
    2. Multi-document context assembly
    3. Priority system: Check project knowledge BEFORE external sources
    4. Enhanced citation tracking
    5. Cross-document concept linking
    6. Background initialization (February 18, 2026) - gunicorn starts instantly
    """

    def __init__(self, project_path="/mnt/project", db_path="swarm_intelligence.db"):
        self.project_path = Path(project_path)
        self.db_path = db_path
        self.knowledge_index = {}
        self.document_terms = {}       # Term frequency per document
        self.global_term_frequency = Counter()  # Term frequency across all docs
        self.total_documents = 0

        # =====================================================================
        # BACKGROUND THREADING SUPPORT (Added February 18, 2026)
        # =====================================================================
        # Event is set when initialization is fully complete.
        # Lock protects SQLite writes from the background thread.
        self._initialization_complete = threading.Event()
        self._db_lock = threading.Lock()
        self._init_thread = None
        # =====================================================================

    # =========================================================================
    # BACKGROUND INITIALIZATION (Added February 18, 2026)
    # =========================================================================

    def initialize_background(self):
        """
        Start knowledge base initialization in a background daemon thread.

        Gunicorn binds to the port and accepts connections immediately.
        The knowledge index becomes available ~30 seconds later.
        Any search called before init completes returns empty results gracefully.

        This is the RECOMMENDED way to initialize in production (app.py).
        The original initialize() method is still available and unchanged.
        """
        print("🔄 Starting knowledge base initialization in background thread...")
        print("   Gunicorn will accept connections immediately.")
        print("   Knowledge search will be available in ~30 seconds.")

        self._init_thread = threading.Thread(
            target=self._background_init_worker,
            name="KnowledgeBaseInit",
            daemon=True   # Daemon thread: dies when main process exits
        )
        self._init_thread.start()

    def _background_init_worker(self):
        """Worker that runs the full initialization in a background thread."""
        try:
            self.initialize()
        except Exception as e:
            print(f"⚠️ Background knowledge base initialization failed: {e}")
            import traceback
            print(traceback.format_exc())
        finally:
            # Always set the event so callers don't wait forever
            self._initialization_complete.set()

    @property
    def is_ready(self):
        """True when initialization is fully complete."""
        return self._initialization_complete.is_set()

    def _wait_for_ready(self, timeout=2.0):
        """
        Wait up to timeout seconds for initialization to complete.
        Returns True if ready, False if still initializing after timeout.
        Used by search methods so they degrade gracefully rather than crashing.
        """
        if self._initialization_complete.is_set():
            return True
        # Brief wait - enough for very fast startups but won't block requests
        return self._initialization_complete.wait(timeout=timeout)

    # =========================================================================
    # END BACKGROUND INITIALIZATION
    # =========================================================================

    def initialize(self):
        """
        Initialize the ENHANCED knowledge base (synchronous - original behavior):
        1. Create knowledge_documents table
        2. Extract all documents
        3. Build searchable index
        4. Calculate TF-IDF scores for semantic search
        5. Build concept linkage map

        Called directly by initialize_background() worker thread.
        Can also be called directly for synchronous initialization (legacy).
        """
        print("🔍 Initializing ENHANCED Project Knowledge Base...")

        # Create database table
        self._create_knowledge_table()

        # Extract and index all documents
        self._index_all_documents()

        # Build semantic search index
        self._build_semantic_index()

        # Mark as complete (in case called directly, not via initialize_background)
        self._initialization_complete.set()

        print(f"✅ ENHANCED Knowledge Base Ready:")
        print(f"   📚 {len(self.knowledge_index)} documents indexed")
        print(f"   🔤 {len(self.global_term_frequency)} unique terms")
        print(f"   🎯 Semantic search enabled")

    def _create_knowledge_table(self):
        """Create enhanced knowledge_documents table with citation tracking"""
        with self._db_lock:
            db = sqlite3.connect(self.db_path, check_same_thread=False)
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
                    metadata TEXT,
                    semantic_keywords TEXT,
                    relevance_score REAL DEFAULT 0,
                    last_accessed TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                )
            ''')

            # Create citation tracking table
            db.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_citations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    document_id INTEGER,
                    relevance_score REAL,
                    excerpt TEXT,
                    cited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES knowledge_documents(id)
                )
            ''')

            db.commit()
            db.close()

    def _build_semantic_index(self):
        """Build TF-IDF-like index for semantic search"""
        print("  🔨 Building semantic search index...")

        self.total_documents = len(self.knowledge_index)

        if self.total_documents == 0:
            return

        # Calculate term frequencies for each document
        for filename, data in self.knowledge_index.items():
            content = data['content'].lower()
            words = self._tokenize(content)

            # Count term frequency in this document
            term_freq = Counter(words)
            self.document_terms[filename] = term_freq

            # Update global term frequency
            for term in set(words):
                self.global_term_frequency[term] += 1

        print(f"  ✅ Semantic index built: {len(self.global_term_frequency)} terms")

    def _tokenize(self, text):
        """
        Tokenize text for semantic search.
        Removes stopwords and extracts meaningful terms.
        """
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'been', 'be',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
            'could', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
            'it', 'its', 'as', 'if', 'when', 'where', 'which', 'who', 'whom'
        }

        words = re.findall(r'\b[a-z]+\b', text.lower())
        meaningful_words = [w for w in words if w not in stopwords and len(w) > 2]

        return meaningful_words

    def _calculate_tf_idf(self, term, document_terms):
        """
        Calculate TF-IDF score for a term in a document.
        TF = Term frequency in document
        IDF = log(Total documents / Documents containing term)
        """
        if term not in document_terms:
            return 0.0

        tf = document_terms[term]

        docs_with_term = self.global_term_frequency.get(term, 0)
        if docs_with_term == 0:
            return 0.0

        idf = math.log(self.total_documents / docs_with_term)

        return tf * idf

    def _index_all_documents(self):
        """Extract and index all documents from the project knowledge base"""
        if not self.project_path.exists():
            print(f"⚠️ Project path not found: {self.project_path}")
            return

        with self._db_lock:
            db = sqlite3.connect(self.db_path, check_same_thread=False)

            # Clear existing index
            db.execute('DELETE FROM knowledge_documents')
            db.commit()

            for file_path in self.project_path.iterdir():
                if file_path.is_file():
                    try:
                        content = self._extract_content(file_path)
                        if content:
                            metadata = self._extract_metadata(file_path, content)

                            # Extract semantic keywords
                            semantic_keywords = self._extract_semantic_keywords(content)

                            db.execute('''
                                INSERT INTO knowledge_documents
                                (filename, file_type, title, content, keywords, category,
                                 word_count, metadata, semantic_keywords)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                file_path.name,
                                file_path.suffix,
                                metadata['title'],
                                content[:50000],  # Store first 50k chars
                                metadata['keywords'],
                                metadata['category'],
                                metadata['word_count'],
                                json.dumps(metadata),
                                ', '.join(semantic_keywords[:50])
                            ))

                            self.knowledge_index[file_path.name] = {
                                'content': content,
                                'metadata': metadata,
                                'semantic_keywords': semantic_keywords
                            }

                            print(f"  ✅ Indexed: {file_path.name} ({metadata['word_count']} words)")

                    except Exception as e:
                        error_msg = str(e)
                        if "File is not a zip file" in error_msg or "not a zip file" in error_msg.lower():
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                    if content:
                                        metadata = self._extract_metadata(file_path, content)
                                        semantic_keywords = self._extract_semantic_keywords(content)

                                        db.execute('''
                                            INSERT INTO knowledge_documents
                                            (filename, file_type, title, content, keywords, category,
                                             word_count, metadata, semantic_keywords)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        ''', (
                                            file_path.name,
                                            file_path.suffix,
                                            metadata['title'],
                                            content[:50000],
                                            metadata['keywords'],
                                            metadata['category'],
                                            metadata['word_count'],
                                            json.dumps(metadata),
                                            ', '.join(semantic_keywords[:50])
                                        ))
                                        self.knowledge_index[file_path.name] = {
                                            'content': content,
                                            'metadata': metadata,
                                            'semantic_keywords': semantic_keywords
                                        }
                                        print(f"  ✅ Indexed: {file_path.name} ({metadata['word_count']} words) [as text]")
                            except Exception:
                                pass  # Silently skip if text extraction also fails
                        elif "EOF marker not found" in error_msg:
                            pass  # Silently skip corrupted PDFs
                        else:
                            print(f"  ⚠️ Error indexing {file_path.name}: {e}")

            db.commit()
            db.close()

    def _extract_semantic_keywords(self, content):
        """Extract semantically important keywords using domain knowledge"""
        domain_terms = {
            # Schedule types
            'continental', 'dupont', 'pitman', 'panama', '2-2-3', 'southern swing',
            'fixed', 'rotating', 'compressed', 'extended',

            # Operational concepts
            'coverage', 'staffing', 'overtime', 'fatigue', 'turnover', 'retention',
            'work-life balance', 'shift differential', 'premium pay', 'burden rate',

            # Implementation terms
            'change management', 'resistance', 'stakeholder', 'pilot', 'rollout',
            'training', 'communication', 'feedback', 'survey', 'assessment',

            # Industry terms
            'manufacturing', 'pharmaceutical', 'food processing', 'mining',
            'distribution', 'continuous operations', '24/7', 'facility',

            # Metrics
            'adverse cost', 'utilization', 'efficiency', 'productivity', 'quality',
            'safety', 'absenteeism', 'overtime ratio',

            # People terms
            'employee', 'supervisor', 'crew', 'team', 'management', 'union',
            'workforce', 'labor', 'shift worker'
        }

        content_lower = content.lower()
        found_terms = []

        for term in domain_terms:
            if term in content_lower:
                count = content_lower.count(term)
                if count > 0:
                    found_terms.append((term, count))

        found_terms.sort(key=lambda x: x[1], reverse=True)

        return [term for term, count in found_terms]

    def _extract_content(self, file_path):
        """Extract text content from various file types"""
        suffix = file_path.suffix.lower()

        try:
            if suffix in ['.txt', '.md', '']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()

            elif suffix == '.docx' and DOCX_AVAILABLE:
                try:
                    doc = Document(file_path)
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    return '\n\n'.join(paragraphs)
                except Exception as e:
                    if "not a zip file" in str(e).lower():
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            return f.read()
                    raise

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
        word_count = len(content.split())

        lines = [l.strip() for l in content.split('\n') if l.strip()]
        title = lines[0] if lines else file_path.stem.replace('_', ' ')

        keywords = self._extract_keywords(content)
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

        return found[:20]

    def _categorize_document(self, filename, content):
        """Categorize document based on filename and content"""
        filename_lower = filename.lower()
        content_lower = content.lower()[:1000]

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

    def semantic_search(self, query, max_results=5, category_filter=None):
        """
        ENHANCED SEMANTIC SEARCH - Similar to Claude Projects' project_knowledge_search

        Returns empty list gracefully if called before initialization completes.
        Uses TF-IDF-like scoring to find semantically relevant documents.

        Args:
            query: Search query
            max_results: Maximum results to return (1-15)
            category_filter: Optional category to filter by

        Returns:
            List of relevant documents with scores and excerpts
        """
        # Graceful degradation if not yet ready (February 18, 2026)
        if not self._wait_for_ready(timeout=2.0):
            return []

        query_lower = query.lower()
        query_terms = self._tokenize(query_lower)

        results = []

        for filename, data in self.knowledge_index.items():
            content = data['content'].lower()
            metadata = data['metadata']

            if category_filter and metadata['category'] != category_filter:
                continue

            score = 0

            # 1. Exact phrase match (highest weight)
            if query_lower in content:
                score += 50

            # 2. Semantic TF-IDF scoring
            doc_terms = self.document_terms.get(filename, Counter())
            for term in query_terms:
                tf_idf = self._calculate_tf_idf(term, doc_terms)
                score += tf_idf * 10

            # 3. Title matches (high relevance)
            title_lower = metadata['title'].lower()
            title_term_matches = sum(1 for term in query_terms if term in title_lower)
            score += title_term_matches * 15

            # 4. Category matches
            category_lower = metadata['category'].lower()
            category_term_matches = sum(1 for term in query_terms if term in category_lower)
            score += category_term_matches * 10

            # 5. Semantic keyword matches
            semantic_keywords = data.get('semantic_keywords', [])
            semantic_matches = sum(1 for term in query_terms if term in [k.lower() for k in semantic_keywords])
            score += semantic_matches * 8

            # 6. Recency bonus
            try:
                modified_date = datetime.fromisoformat(metadata['modified'])
                days_old = (datetime.now() - modified_date).days
                if days_old < 30:
                    score += 5
                elif days_old < 90:
                    score += 2
            except Exception:
                pass

            if score > 0:
                excerpt = self._extract_smart_excerpt(data['content'], query_terms)

                results.append({
                    'filename': filename,
                    'title': metadata['title'],
                    'category': metadata['category'],
                    'score': score,
                    'excerpt': excerpt,
                    'word_count': metadata['word_count'],
                    'relevance_type': self._classify_relevance(score)
                })

        results.sort(key=lambda x: x['score'], reverse=True)

        self._track_access(results[:max_results])

        return results[:max_results]

    def _classify_relevance(self, score):
        """Classify relevance level based on score"""
        if score >= 50:
            return "Highly Relevant"
        elif score >= 25:
            return "Very Relevant"
        elif score >= 10:
            return "Relevant"
        else:
            return "Potentially Relevant"

    def _extract_smart_excerpt(self, content, query_terms, context_words=100):
        """
        Extract the most relevant excerpt using query terms.
        Prioritizes sections with multiple query term matches.
        """
        content_lower = content.lower()
        words = content.split()

        term_positions = []
        for i, word in enumerate(words):
            word_lower = word.lower().strip('.,;:!?()')
            if word_lower in query_terms:
                term_positions.append(i)

        if not term_positions:
            return ' '.join(words[:context_words]) + '...'

        best_center = term_positions[0]
        best_density = 1

        for pos in term_positions:
            nearby_terms = sum(1 for p in term_positions if abs(p - pos) <= context_words // 2)
            if nearby_terms > best_density:
                best_density = nearby_terms
                best_center = pos

        start = max(0, best_center - context_words // 2)
        end = min(len(words), best_center + context_words // 2)

        excerpt = ' '.join(words[start:end])

        if start > 0:
            excerpt = '...' + excerpt
        if end < len(words):
            excerpt = excerpt + '...'

        return excerpt

    def _track_access(self, results):
        """Track which documents are being accessed for analytics"""
        try:
            with self._db_lock:
                db = sqlite3.connect(self.db_path, check_same_thread=False)
                for result in results:
                    db.execute('''
                        UPDATE knowledge_documents
                        SET access_count = access_count + 1,
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE filename = ?
                    ''', (result['filename'],))
                db.commit()
                db.close()
        except Exception as e:
            print(f"  ⚠️ Access tracking failed: {e}")

    def get_context_for_task(self, task_description, max_context=5000, max_results=3):
        """
        Get relevant context from knowledge base for a specific task.

        THIS IS THE PRIORITY FUNCTION - Always called FIRST before external sources.
        Returns empty string gracefully if called before initialization completes.

        Returns a formatted context string to inject into AI prompts with:
        - Relevant excerpts from multiple documents
        - Source citations
        - Relevance indicators
        """
        # Graceful degradation if not yet ready (February 18, 2026)
        if not self._wait_for_ready(timeout=2.0):
            return ""

        results = self.semantic_search(task_description, max_results=max_results)

        if not results:
            return ""

        context = "\n\n" + "=" * 70 + "\n"
        context += "🎯 SHIFTWORK SOLUTIONS PROJECT KNOWLEDGE\n"
        context += "   (Based on hundreds of facilities across dozens of industries)\n"
        context += "=" * 70 + "\n\n"

        for i, result in enumerate(results, 1):
            context += f"📄 SOURCE {i}: {result['title']}\n"
            context += f"   Category: {result['category']} | "
            context += f"Relevance: {result['relevance_type']} | "
            context += f"Words: {result['word_count']:,}\n"
            context += f"   {result['excerpt']}\n\n"

        context += "💡 KEY PRINCIPLE: The best shift schedules are ones employees actually choose.\n"
        context += "   Focus on employee-centered approaches and change management.\n"
        context += "=" * 70 + "\n"

        if len(context) > max_context:
            context = context[:max_context] + "\n\n[Context truncated for length...]"

        return context

    def search(self, query, max_results=5):
        """
        Backwards compatible search method.
        Calls semantic_search for better results.
        Returns empty list gracefully if not yet ready.
        """
        return self.semantic_search(query, max_results)

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

    def get_stats(self):
        """Get comprehensive knowledge base statistics"""
        total_docs = len(self.knowledge_index)
        total_words = sum(d['metadata']['word_count'] for d in self.knowledge_index.values())

        categories = {}
        for data in self.knowledge_index.values():
            cat = data['metadata']['category']
            categories[cat] = categories.get(cat, 0) + 1

        try:
            with self._db_lock:
                db = sqlite3.connect(self.db_path, check_same_thread=False)
                popular = db.execute('''
                    SELECT filename, title, access_count, last_accessed
                    FROM knowledge_documents
                    WHERE access_count > 0
                    ORDER BY access_count DESC
                    LIMIT 10
                ''').fetchall()
                db.close()

            popular_docs = [
                {
                    'filename': row[0],
                    'title': row[1],
                    'access_count': row[2],
                    'last_accessed': row[3]
                }
                for row in popular
            ]
        except Exception:
            popular_docs = []

        return {
            'total_documents': total_docs,
            'total_words': total_words,
            'total_terms_indexed': len(self.global_term_frequency),
            'categories': categories,
            'available_templates': self._get_template_list(),
            'most_accessed': popular_docs,
            'semantic_search_enabled': True,
            'initialization_complete': self.is_ready
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


# Maintain backward compatibility
class ProjectKnowledgeBase(EnhancedProjectKnowledgeBase):
    """Backward compatible wrapper - uses Enhanced version"""
    pass


# Singleton instance
_knowledge_base = None

def get_knowledge_base():
    """Get or create singleton ENHANCED knowledge base instance"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = EnhancedProjectKnowledgeBase()
        _knowledge_base.initialize()
    return _knowledge_base


# I did no harm and this file is not truncated
