"""
SWARM PROJECT KNOWLEDGE INTEGRATION MODULE - ENHANCED
Created: January 19, 2026
Last Updated: February 25, 2026 - SAFETY GUARD + DIAGNOSTIC IMPROVEMENTS

CHANGELOG:

- February 25, 2026: SAFETY GUARD + DIAGNOSTIC IMPROVEMENTS
  * PROBLEM: After database deletion, _index_all_documents() starts with
    DELETE FROM knowledge_documents. If /mnt/project resolves to 0 files
    for any reason (path issue, Render mount timing, etc.), the DELETE runs
    but nothing gets re-inserted — leaving the KB silently empty with no
    clear error message. The app continues to run appearing healthy.
  * FIX 1: SAFETY GUARD - _index_all_documents() now counts files BEFORE
    deleting. If 0 files are found, it aborts immediately and logs a clear
    CRITICAL error. Existing DB records are preserved. This prevents a bad
    path from silently wiping a populated KB.
  * FIX 2: STARTUP SUMMARY - After indexing, logs a clear summary showing
    exactly how many documents were indexed and from which path. Makes
    post-deploy verification trivial by reading Render logs.
  * FIX 3: get_index_status() method added — returns path, file count,
    document count, ready state. Used by /api/admin/kb-diagnose endpoint
    in app.py to give real-time KB health info without reading Render logs.
  * NOTE: The knowledge_extracts and learned_patterns tables managed by
    document_ingestion_engine.py are SEPARATE from this module's
    knowledge_documents table. If those were lost when the DB was deleted,
    they must be re-uploaded through the Knowledge Management UI. This
    module only manages the auto-indexed project files from GitHub.

- February 19, 2026 (Session 2): ADDED index_single_file() FOR LIVE KB UPDATES
  * Files uploaded through the UI are now indexed into the live KB immediately.
  * Uses INSERT OR REPLACE so re-uploading updates existing records.
  * Called from routes/handlers/file_handler.py after every successful file save.

- February 19, 2026 (Session 1): TOKENIZER AND SEARCH FIXES
  * Fixed _tokenize() to capture numeric shiftwork terms: 20/60/20, 2-2-3, 24/7
  * Increased _wait_for_ready() timeout to 15 seconds
  * Improved _extract_smart_excerpt() to find numeric terms in excerpts
  * Increased max_context default to 8000 characters
  * Added numeric shiftwork terms to _extract_keywords()

- February 18, 2026: BACKGROUND THREADING FIX
  * Added initialize_background() - gunicorn starts instantly, KB indexes in ~30s
  * Added _initialization_complete threading.Event() flag
  * Added _db_lock threading.Lock() for thread-safe SQLite writes
  * search(), semantic_search(), get_context_for_task() degrade gracefully

- January 29, 2026: MAJOR ENHANCEMENT
  * Added semantic search with TF-IDF-like scoring
  * Multi-document context assembly
  * Priority system: PROJECT KNOWLEDGE FIRST
  * Enhanced excerpt extraction with relevance highlighting
  * Comprehensive document metadata tracking
  * Knowledge source citation tracking
  * Category-based search filtering

PURPOSE:
Integrates the entire Shiftwork Solutions project knowledge base into the AI Swarm,
giving it access to hundreds of facilities worth of expertise, templates, frameworks,
and methodologies.

IMPORTANT - TWO SEPARATE KNOWLEDGE SYSTEMS:
1. THIS MODULE (knowledge_documents table): Auto-indexes GitHub project files from
   /mnt/project at startup. Self-healing — rebuilds from GitHub files on every deploy.
2. document_ingestion_engine.py (knowledge_extracts + learned_patterns tables):
   Stores manually uploaded documents. NOT self-healing — data is lost if DB is
   deleted and must be re-uploaded through the Knowledge Management UI.

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
    7. Fixed tokenizer (February 19, 2026) - numeric terms now indexed correctly
    8. Live file indexing (February 19, 2026) - uploaded files join the KB index
    9. Safety guard (February 25, 2026) - zero-file path never wipes populated KB
    """

    def __init__(self, project_path="/mnt/project", db_path="swarm_intelligence.db"):
        self.project_path = Path(project_path)
        self.db_path = db_path
        self.knowledge_index = {}
        self.document_terms = {}       # Term frequency per document
        self.global_term_frequency = Counter()  # Term frequency across all docs
        self.total_documents = 0

        # Background threading support (Added February 18, 2026)
        self._initialization_complete = threading.Event()
        self._db_lock = threading.Lock()
        self._init_thread = None

        # Diagnostic tracking (Added February 25, 2026)
        self._source_path_used = None
        self._files_found_at_init = 0
        self._init_error = None

    # =========================================================================
    # BACKGROUND INITIALIZATION (Added February 18, 2026)
    # =========================================================================

    def initialize_background(self):
        """
        Start knowledge base initialization in a background daemon thread.

        Gunicorn binds to the port and accepts connections immediately.
        The knowledge index becomes available ~30 seconds later.
        Any search called before init completes returns empty results gracefully.
        """
        print("Starting knowledge base initialization in background thread...")
        print("   Gunicorn will accept connections immediately.")
        print("   Knowledge search will be available in ~30 seconds.")

        self._init_thread = threading.Thread(
            target=self._background_init_worker,
            name="KnowledgeBaseInit",
            daemon=True
        )
        self._init_thread.start()

    def _background_init_worker(self):
        """Worker that runs the full initialization in a background thread."""
        try:
            self.initialize()
        except Exception as e:
            self._init_error = str(e)
            print(f"Background knowledge base initialization failed: {e}")
            import traceback
            print(traceback.format_exc())
        finally:
            self._initialization_complete.set()

    @property
    def is_ready(self):
        """True when initialization is fully complete."""
        return self._initialization_complete.is_set()

    def _wait_for_ready(self, timeout=2.0):
        """
        Wait up to timeout seconds for initialization to complete.
        Returns True if ready, False if still initializing after timeout.
        """
        if self._initialization_complete.is_set():
            return True
        return self._initialization_complete.wait(timeout=timeout)

    # =========================================================================
    # END BACKGROUND INITIALIZATION
    # =========================================================================

    def initialize(self):
        """
        Initialize the ENHANCED knowledge base (synchronous):
        1. Create knowledge_documents table
        2. Extract all documents
        3. Build searchable index
        4. Calculate TF-IDF scores for semantic search
        5. Build concept linkage map
        """
        print("Initializing ENHANCED Project Knowledge Base...")

        self._create_knowledge_table()
        self._index_all_documents()
        self._build_semantic_index()

        self._initialization_complete.set()

        doc_count = len(self.knowledge_index)
        term_count = len(self.global_term_frequency)

        # Clear startup summary for post-deploy log verification
        print("=" * 60)
        print("KNOWLEDGE BASE INITIALIZATION COMPLETE")
        print(f"  Source path  : {self._source_path_used or self.project_path}")
        print(f"  Files found  : {self._files_found_at_init}")
        print(f"  Docs indexed : {doc_count}")
        print(f"  Unique terms : {term_count}")
        if self._init_error:
            print(f"  ERROR        : {self._init_error}")
        if doc_count == 0:
            print("  WARNING: Zero documents in index — KB searches will return empty.")
            print("  Check that /mnt/project is mounted and contains your GitHub files.")
        print("=" * 60)

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
        print("  Building semantic search index...")

        self.total_documents = len(self.knowledge_index)

        if self.total_documents == 0:
            return

        for filename, data in self.knowledge_index.items():
            content = data['content'].lower()
            words = self._tokenize(content)

            term_freq = Counter(words)
            self.document_terms[filename] = term_freq

            for term in set(words):
                self.global_term_frequency[term] += 1

        print(f"  Semantic index built: {len(self.global_term_frequency)} terms")

    def _tokenize(self, text):
        """
        Tokenize text for semantic search.

        FIXED February 19, 2026:
        New regex r'[a-z0-9]+(?:[-/][a-z0-9]+)*' captures:
        - Pure alphabetic words: schedule, overtime, employee
        - Hyphenated terms: 12-hour, work-life, 2-2-3, day-on-day-off
        - Slash-separated terms: 20/60/20, 24/7, 24/5
        - Pure numbers: 20, 60, 12, 8
        """
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were', 'been', 'be',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
            'could', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
            'it', 'its', 'as', 'if', 'when', 'where', 'which', 'who', 'whom'
        }

        words = re.findall(r'[a-z0-9]+(?:[-/][a-z0-9]+)*', text.lower())
        meaningful_words = [w for w in words if w not in stopwords and len(w) > 1]

        return meaningful_words

    def _calculate_tf_idf(self, term, document_terms):
        """Calculate TF-IDF score for a term in a document."""
        if term not in document_terms:
            return 0.0

        tf = document_terms[term]
        docs_with_term = self.global_term_frequency.get(term, 0)

        if docs_with_term == 0:
            return 0.0

        idf = math.log(self.total_documents / docs_with_term)
        return tf * idf

    def _index_all_documents(self):
        """
        Extract and index all documents from the project knowledge base.

        SAFETY GUARD (Added February 25, 2026):
        Before deleting existing records, this method counts the files available
        at the source path. If zero files are found, it aborts immediately and
        preserves any existing records in the database. This prevents a bad
        path resolution or timing issue on Render from silently wiping a
        populated knowledge base.
        """
        self._source_path_used = str(self.project_path)

        if not self.project_path.exists():
            self._init_error = f"Project path does not exist: {self.project_path}"
            print(f"  CRITICAL: {self._init_error}")
            print(f"  Existing knowledge_documents records preserved.")
            return

        # Count available files BEFORE touching the database
        available_files = [f for f in self.project_path.iterdir() if f.is_file()]
        self._files_found_at_init = len(available_files)

        if self._files_found_at_init == 0:
            self._init_error = (
                f"SAFETY GUARD TRIGGERED: Zero files found at {self.project_path}. "
                f"Aborting index — existing knowledge_documents records preserved."
            )
            print(f"  CRITICAL: {self._init_error}")
            print(f"  This may indicate a Render mount issue or incorrect path.")
            print(f"  Check /api/admin/kb-diagnose for current KB state.")
            return

        print(f"  Found {self._files_found_at_init} files at {self.project_path} — proceeding with indexing.")

        with self._db_lock:
            db = sqlite3.connect(self.db_path, check_same_thread=False)

            # Safe to delete now — we confirmed files exist to replace them
            db.execute('DELETE FROM knowledge_documents')
            db.commit()

            indexed_count = 0
            error_count = 0

            for file_path in available_files:
                try:
                    content = self._extract_content(file_path)
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

                        indexed_count += 1
                        print(f"  Indexed: {file_path.name} ({metadata['word_count']} words)")

                except Exception as e:
                    error_msg = str(e)
                    if "File is not a zip file" in error_msg or "not a zip file" in error_msg.lower():
                        # Fallback: try reading as plain text
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
                                    indexed_count += 1
                                    print(f"  Indexed: {file_path.name} ({metadata['word_count']} words) [as text]")
                        except Exception:
                            error_count += 1
                    elif "EOF marker not found" in error_msg:
                        error_count += 1
                    else:
                        print(f"  Error indexing {file_path.name}: {e}")
                        error_count += 1

            db.commit()
            db.close()

            print(f"  Indexing complete: {indexed_count} indexed, {error_count} errors")

    # =========================================================================
    # DIAGNOSTIC METHOD (Added February 25, 2026)
    # =========================================================================

    def get_index_status(self):
        """
        Return current knowledge base status for the /api/admin/kb-diagnose endpoint.

        Provides real-time visibility into what the KB actually contains,
        what path it loaded from, and whether initialization succeeded.
        Allows post-deploy verification without reading Render logs.

        Returns:
            dict with full diagnostic information
        """
        # Count records currently in DB
        db_doc_count = 0
        db_error = None
        db_files = []
        try:
            with self._db_lock:
                db = sqlite3.connect(self.db_path, check_same_thread=False)
                row = db.execute(
                    'SELECT COUNT(*) FROM knowledge_documents'
                ).fetchone()
                db_doc_count = row[0] if row else 0

                # List the actual filenames in DB
                rows = db.execute(
                    'SELECT filename, word_count, category FROM knowledge_documents ORDER BY filename'
                ).fetchall()
                db_files = [
                    {'filename': r[0], 'word_count': r[1], 'category': r[2]}
                    for r in rows
                ]
                db.close()
        except Exception as e:
            db_error = str(e)

        return {
            'is_ready': self.is_ready,
            'initialization_complete': self.is_ready,
            'init_error': self._init_error,
            'source_path': self._source_path_used or str(self.project_path),
            'source_path_exists': self.project_path.exists(),
            'files_found_at_init': self._files_found_at_init,
            'documents_in_memory': len(self.knowledge_index),
            'unique_terms_in_memory': len(self.global_term_frequency),
            'documents_in_database': db_doc_count,
            'database_error': db_error,
            'database_files': db_files,
            'memory_filenames': sorted(list(self.knowledge_index.keys())),
            'safety_guard_triggered': (
                self._files_found_at_init == 0 and self._init_error is not None
            ),
            'diagnosis': self._generate_diagnosis(db_doc_count)
        }

    def _generate_diagnosis(self, db_doc_count):
        """Generate a plain-English diagnosis of KB health."""
        if not self.is_ready:
            return "KB is still initializing — wait 30 seconds and retry."
        if self._init_error and 'SAFETY GUARD' in (self._init_error or ''):
            return (
                "SAFETY GUARD TRIGGERED: Zero files found at source path. "
                "KB was NOT wiped. Check Render environment — /mnt/project may not "
                "be mounted correctly. Existing DB records are intact."
            )
        if self._init_error:
            return f"Initialization error: {self._init_error}"
        if len(self.knowledge_index) == 0 and db_doc_count == 0:
            return (
                "KB is empty. Source path was accessible but contained no indexable files. "
                "Verify /mnt/project is populated in Render."
            )
        if len(self.knowledge_index) == 0 and db_doc_count > 0:
            return (
                f"WARNING: Memory index is empty but DB has {db_doc_count} records. "
                "This should not happen — may indicate a threading issue."
            )
        return (
            f"KB is healthy. {len(self.knowledge_index)} documents indexed from "
            f"{self._source_path_used}."
        )

    # =========================================================================
    # LIVE FILE INDEXING (Added February 19, 2026)
    # =========================================================================

    def index_single_file(self, file_path):
        """
        Index a single file into the live knowledge base immediately.

        Called by file_handler.py after every successful file upload so that
        uploaded documents become searchable in all future conversations,
        not just the current one.

        Uses INSERT OR REPLACE so re-uploading the same filename updates the
        existing record rather than creating a duplicate.

        Also updates self.document_terms and self.global_term_frequency in
        memory so TF-IDF scoring stays accurate without requiring a restart.

        Args:
            file_path: Full path string or Path object to the uploaded file

        Returns:
            dict with keys:
                success (bool): True if indexed successfully
                filename (str): Name of the file indexed
                word_count (int): Number of words indexed
                error (str): Error message if success is False
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return {
                'success': False,
                'filename': file_path.name,
                'word_count': 0,
                'error': f'File not found: {file_path}'
            }

        try:
            # Extract content using existing machinery
            content = self._extract_content(file_path)

            if not content or not content.strip():
                return {
                    'success': False,
                    'filename': file_path.name,
                    'word_count': 0,
                    'error': 'No text content could be extracted from file'
                }

            # Build metadata and keywords using existing machinery
            metadata = self._extract_metadata(file_path, content)
            semantic_keywords = self._extract_semantic_keywords(content)

            # ----------------------------------------------------------------
            # 1. Update the database (thread-safe)
            # ----------------------------------------------------------------
            with self._db_lock:
                db = sqlite3.connect(self.db_path, check_same_thread=False)

                # INSERT OR REPLACE handles re-uploads of the same filename
                db.execute('''
                    INSERT OR REPLACE INTO knowledge_documents
                    (filename, file_type, title, content, keywords, category,
                     word_count, metadata, semantic_keywords, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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

                db.commit()
                db.close()

            # ----------------------------------------------------------------
            # 2. Update in-memory knowledge index
            # ----------------------------------------------------------------
            self.knowledge_index[file_path.name] = {
                'content': content,
                'metadata': metadata,
                'semantic_keywords': semantic_keywords
            }

            # ----------------------------------------------------------------
            # 3. Update in-memory TF-IDF structures so scoring stays accurate.
            # If the file already existed, remove its old term counts first.
            # ----------------------------------------------------------------
            if file_path.name in self.document_terms:
                old_terms = self.document_terms[file_path.name]
                for term in old_terms:
                    if self.global_term_frequency[term] > 1:
                        self.global_term_frequency[term] -= 1
                    else:
                        del self.global_term_frequency[term]

            # Add new term counts
            words = self._tokenize(content.lower())
            new_term_freq = Counter(words)
            self.document_terms[file_path.name] = new_term_freq

            for term in set(words):
                self.global_term_frequency[term] += 1

            # Update total document count
            self.total_documents = len(self.knowledge_index)

            print(f"KB: Indexed uploaded file: {file_path.name} ({metadata['word_count']} words)")

            return {
                'success': True,
                'filename': file_path.name,
                'word_count': metadata['word_count'],
                'category': metadata['category'],
                'error': None
            }

        except Exception as e:
            import traceback
            print(f"KB: Failed to index {file_path.name}: {e}")
            print(traceback.format_exc())
            return {
                'success': False,
                'filename': file_path.name,
                'word_count': 0,
                'error': str(e)
            }

    # =========================================================================
    # END LIVE FILE INDEXING
    # =========================================================================

    def _extract_semantic_keywords(self, content):
        """
        Extract semantically important keywords using domain knowledge.
        Uses direct string search so multi-word and numeric terms are found
        regardless of tokenizer behavior.
        """
        domain_terms = {
            # Numeric rules and ratios
            '20/60/20', '70/70', '80/20',

            # Schedule patterns - numeric
            '2-2-3', '3-2-2-3', '2-3-2', '4-3', '4-4', '5-2', '6-2', '6-3',

            # Schedule types - text
            'continental', 'dupont', 'pitman', 'panama', 'southern swing',
            'fixed', 'rotating', 'compressed', 'extended',

            # Shift lengths
            '12-hour', '8-hour', '10-hour', '12 hour', '8 hour', '10 hour',

            # Coverage patterns
            '24/7', '24/5',

            # Operational concepts
            'coverage', 'staffing', 'overtime', 'fatigue', 'turnover', 'retention',
            'work-life balance', 'shift differential', 'premium pay', 'burden rate',
            'adverse cost', 'overstaffing', 'understaffing',

            # Implementation terms
            'change management', 'resistance', 'stakeholder', 'pilot', 'rollout',
            'training', 'communication', 'feedback', 'survey', 'assessment',
            'implementation', 'transition',

            # Industry terms
            'manufacturing', 'pharmaceutical', 'food processing', 'mining',
            'distribution', 'continuous operations', 'facility',

            # Metrics
            'utilization', 'efficiency', 'productivity', 'quality',
            'safety', 'absenteeism', 'overtime ratio',

            # People terms
            'employee', 'supervisor', 'crew', 'team', 'management', 'union',
            'workforce', 'labor', 'shift worker',

            # Shiftwork Solutions methodology
            'employee involvement', 'employee survey', 'schedule preference',
            'economic dependency', 'organizational dynamics'
        }

        content_lower = content.lower()
        found_terms = []

        for term in domain_terms:
            if term in content_lower:
                count = content_lower.count(term)
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
        """
        Extract relevant keywords from content.
        FIXED February 19, 2026: Added numeric shiftwork terms.
        """
        terms = [
            # Numeric ratios and rules
            '20/60/20', '70/70', '24/7', '24/5',
            # Schedule patterns
            '2-2-3', '3-2-2-3', '4-4', '4-3',
            # Shift lengths
            '12-hour', '8-hour', '10-hour',
            # Core concepts
            'schedule', 'shift', 'overtime', 'staffing', 'crew', 'rotation',
            'coverage', 'fatigue', 'turnover', 'work-life balance',
            'continental', 'DuPont', 'pitman', 'panama',
            'fixed', 'rotating', 'survey', 'implementation', 'change management',
            'employee', 'supervisor', 'production', 'manufacturing', 'operations',
            'consultation', 'assessment', 'analysis', 'recommendation', 'cost',
            'adverse cost', 'burden rate', 'shift differential'
        ]

        content_lower = content.lower()
        found = [term for term in terms if term.lower() in content_lower]

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
        ENHANCED SEMANTIC SEARCH using TF-IDF-like scoring.
        Returns empty list gracefully if called before initialization completes.
        """
        if not self._wait_for_ready(timeout=2.0):
            return []

        query_lower = query.lower()
        query_terms = self._tokenize(query_lower)

        query_phrases = set()
        query_phrases.add(query_lower)
        for term in re.findall(r'[a-z0-9]+(?:[-/][a-z0-9]+)+', query_lower):
            query_phrases.add(term)

        results = []

        for filename, data in self.knowledge_index.items():
            content = data['content'].lower()
            metadata = data['metadata']

            if category_filter and metadata['category'] != category_filter:
                continue

            score = 0

            # 1. Exact phrase match
            if query_lower in content:
                score += 50

            # 2. Numeric/hyphenated term exact matches
            for phrase in query_phrases:
                if phrase != query_lower and phrase in content:
                    score += 30

            # 3. Semantic TF-IDF scoring
            doc_terms = self.document_terms.get(filename, Counter())
            for term in query_terms:
                tf_idf = self._calculate_tf_idf(term, doc_terms)
                score += tf_idf * 10

            # 4. Title matches
            title_lower = metadata['title'].lower()
            title_term_matches = sum(1 for term in query_terms if term in title_lower)
            score += title_term_matches * 15

            # 5. Category matches
            category_lower = metadata['category'].lower()
            category_term_matches = sum(1 for term in query_terms if term in category_lower)
            score += category_term_matches * 10

            # 6. Semantic keyword matches
            semantic_keywords = data.get('semantic_keywords', [])
            semantic_matches = sum(
                1 for term in query_terms
                if any(term in kw.lower() for kw in semantic_keywords)
            )
            score += semantic_matches * 8

            # 7. Direct semantic keyword phrase matches
            for phrase in query_phrases:
                if any(phrase == kw.lower() for kw in semantic_keywords):
                    score += 20

            # 8. Recency bonus
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
                excerpt = self._extract_smart_excerpt(data['content'], query_terms, query_phrases)

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

    def _extract_smart_excerpt(self, content, query_terms, query_phrases=None, context_words=100):
        """
        Extract the most relevant excerpt using query terms.

        FIXED February 19, 2026: Added query_phrases parameter so numeric terms
        like 20/60/20 can be located in content even when tokenizer splits them.
        """
        if query_phrases is None:
            query_phrases = set()

        words = content.split()
        content_lower = content.lower()

        phrase_positions = []
        for phrase in query_phrases:
            if phrase and phrase in content_lower:
                idx = content_lower.find(phrase)
                word_pos = len(content_lower[:idx].split())
                phrase_positions.append(word_pos)

        term_positions = []
        for i, word in enumerate(words):
            word_tokens = re.findall(r'[a-z0-9]+(?:[-/][a-z0-9]+)*', word.lower())
            for token in word_tokens:
                if token in query_terms:
                    term_positions.append(i)
                    break

        all_positions = phrase_positions + term_positions

        if not all_positions:
            return ' '.join(words[:context_words]) + '...'

        best_center = all_positions[0]
        best_density = 1

        for pos in all_positions:
            nearby = sum(1 for p in all_positions if abs(p - pos) <= context_words // 2)
            if nearby > best_density:
                best_density = nearby
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
            print(f"  Access tracking failed: {e}")

    def get_context_for_task(self, task_description, max_context=8000, max_results=3):
        """
        Get relevant context from knowledge base for a specific task.

        THIS IS THE PRIORITY FUNCTION - Always called FIRST before external sources.

        FIXED February 19, 2026:
        - Increased _wait_for_ready timeout to 15 seconds
        - Increased max_context default to 8000
        """
        if not self._wait_for_ready(timeout=15.0):
            print("Knowledge base not ready after 15 seconds - returning empty context")
            return ""

        results = self.semantic_search(task_description, max_results=max_results)

        if not results:
            return ""

        context = "\n\n" + "=" * 70 + "\n"
        context += "SHIFTWORK SOLUTIONS PROJECT KNOWLEDGE\n"
        context += "   (Based on hundreds of facilities across dozens of industries)\n"
        context += "=" * 70 + "\n\n"

        for i, result in enumerate(results, 1):
            context += f"SOURCE {i}: {result['title']}\n"
            context += f"   Category: {result['category']} | "
            context += f"Relevance: {result['relevance_type']} | "
            context += f"Words: {result['word_count']:,}\n"
            context += f"   {result['excerpt']}\n\n"

        context += "KEY PRINCIPLE: The best shift schedules are ones employees actually choose.\n"
        context += "   Focus on employee-centered approaches and change management.\n"
        context += "=" * 70 + "\n"

        if len(context) > max_context:
            context = context[:max_context] + "\n\n[Context truncated for length...]"

        return context

    def search(self, query, max_results=5):
        """Backwards compatible search method."""
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
