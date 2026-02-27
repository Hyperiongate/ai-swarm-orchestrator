"""
KNOWLEDGE INGESTION ROUTES
Created: February 2, 2026
Last Updated: February 27, 2026 - ADDED /api/ingest/batch endpoint for multi-file upload

CHANGELOG:

- February 27, 2026 (Session 2): ADDED /api/ingest/batch endpoint
  * PROBLEM: The upload UI only handled one file at a time. Users could not
    drag and drop multiple files or select multiple files from the file picker.
    The single /api/ingest/document endpoint accepts one file per POST.
  * SOLUTION: Added /api/ingest/batch endpoint that accepts multiple files via
    request.files.getlist('files'), loops through each file, reuses all existing
    file-type handling (PPTX, Excel, DOCX, PDF/text), and returns a consolidated
    result with per-file success/error detail and aggregate counts.
  * Also extracted shared file processing into _process_file_for_ingest() helper
    so both single and batch paths use identical extraction logic with no duplication.
  * Single-file path /api/ingest/document is completely unchanged in behavior.

- February 27, 2026 (Session 1): FIXED DOCX content extraction
  * PROBLEM: The else branch (all non-PPTX, non-Excel files, including .docx) was
    doing content = file.read().decode('utf-8', errors='ignore') reading the raw
    .docx zip bytes as UTF-8 text. This produces garbled binary output.
  * SOLUTION: Added _extract_docx_structured() helper using python-docx.

- February 26, 2026 (Session 2): UPDATED PPTX and Excel routes to pass file_bytes

- February 26, 2026 (Session 1): ADDED new document types and proposal alias

- February 22, 2026: ADDED /api/ingest/export (GET)

- February 4, 2026: FIXED PowerPoint temp file handling

Flask API endpoints for document ingestion system.
Part of Shoulders of Giants cumulative learning system.
Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
import os
import sys
import json
from datetime import datetime
import tempfile
import io

# Multiple import attempts with debugging
try:
    from document_ingestion_engine import get_document_ingestor
    print("✅ Knowledge Ingestion: Direct import succeeded")
except ImportError as e1:
    print(f"⚠️  Direct import failed: {e1}")
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from document_ingestion_engine import get_document_ingestor
        print("✅ Knowledge Ingestion: Path-adjusted import succeeded")
    except ImportError as e2:
        print(f"⚠️  Path-adjusted import failed: {e2}")
        try:
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            sys.path.insert(0, root_dir)
            from document_ingestion_engine import get_document_ingestor
            print("✅ Knowledge Ingestion: Root directory import succeeded")
        except ImportError as e3:
            print(f"❌ All import attempts failed!")
            print(f"   Error 1: {e1}")
            print(f"   Error 2: {e2}")
            print(f"   Error 3: {e3}")
            print(f"   Current directory: {os.getcwd()}")
            print(f"   Script directory: {os.path.dirname(__file__)}")
            print(f"   Files in root: {os.listdir(root_dir) if 'root_dir' in locals() else 'N/A'}")
            raise

# Create blueprint
ingest_bp = Blueprint('ingest', __name__, url_prefix='/api/ingest')

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'txt', 'md', 'pdf', 'docx', 'doc',
    'xlsx', 'xls', 'csv', 'json', 'pptx', 'ppt'
}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _extract_docx_structured(file_bytes: bytes) -> dict:
    """
    Extract structured paragraph data from a .docx file using python-docx.

    Returns a dict with:
        'paragraphs': list of {style, bold, text} dicts - for engine extractors
        'plain_text': clean newline-joined text - for regex fallbacks
        'error': None or error string if python-docx fails

    Why this matters:
        Raw .docx files are zip archives. Reading the bytes as UTF-8 text produces
        garbled binary. python-docx properly parses the XML inside and returns real
        text with formatting metadata (style name, bold state) that the engine
        extractors need to identify headings, lessons, key principles, and structure.

    Style names in typical Shiftwork Solutions docs:
        'Heading1'       - major section headings
        'Heading2'       - subsection headings
        'BodyText'       - formatted body paragraph
        'FirstParagraph' - first paragraph of section (some Pillar docs)
        'ListParagraph'  - bullet list items
        ''               - default/normal paragraph
    """
    result = {'paragraphs': [], 'plain_text': '', 'error': None}
    try:
        from docx import Document
        import io as _io

        doc = Document(_io.BytesIO(file_bytes))
        paragraphs = []
        plain_lines = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            style_name = ''
            if para.style and para.style.name:
                style_name = para.style.name.replace(' ', '')

            runs_with_text = [r for r in para.runs if r.text.strip()]
            is_bold = False
            if runs_with_text:
                is_bold = all(r.bold for r in runs_with_text)
            if 'heading' in style_name.lower():
                is_bold = True

            paragraphs.append({
                'style': style_name,
                'bold': is_bold,
                'text': text
            })
            plain_lines.append(text)

        result['paragraphs'] = paragraphs
        result['plain_text'] = '\n'.join(plain_lines)

    except ImportError:
        result['error'] = 'python-docx not available'
    except Exception as e:
        result['error'] = str(e)

    return result


def _process_file_for_ingest(file, document_type, metadata):
    """
    Shared file processing logic used by both single-file and batch endpoints.

    Added February 27, 2026 (Session 2):
    Extracted from ingest_document() so that /api/ingest/batch can reuse
    identical PPTX, Excel, DOCX, and plain-text handling without duplication.
    Any future improvements to extraction automatically apply to both paths.

    Args:
        file:          werkzeug FileStorage object (already validated as allowed type)
        document_type: string from form field
        metadata:      dict with document_name, client, industry, etc.

    Returns:
        dict result from ingest_document_content()
    """
    filename_lower = file.filename.lower()

    # ---- PPTX: pass file_bytes to engine for chart XML extraction ----
    if filename_lower.endswith(('.pptx', '.ppt')):
        file_bytes = file.read()

        slide_text_content = None
        try:
            from pptx import Presentation

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pptx')
            tmp_path = tmp.name
            tmp.write(file_bytes)
            tmp.close()  # CRITICAL: Close before python-pptx opens it

            try:
                prs = Presentation(tmp_path)
                slide_texts = []
                for slide_num, slide in enumerate(prs.slides, 1):
                    slide_content = []
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            text = shape.text.strip()
                            if text:
                                slide_content.append(text)
                    if slide_content:
                        slide_texts.append(
                            f"[Slide {slide_num}]\n" + '\n'.join(slide_content)
                        )
                slide_text_content = '\n\n'.join(slide_texts)
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        except ImportError:
            pass  # python-pptx not available; file_bytes path will handle it
        except Exception:
            pass  # Non-fatal; file_bytes path is primary

        if slide_text_content:
            metadata['slide_text_preview'] = slide_text_content[:2000]

        return ingest_document_content(
            ingestor=get_document_ingestor(),
            content=slide_text_content or '',
            document_type=document_type,
            metadata=metadata,
            file_bytes=file_bytes
        )

    # ---- Excel: pass file_bytes to engine for structured extraction ----
    elif filename_lower.endswith(('.xlsx', '.xls')):
        file_bytes = file.read()
        excel_type = document_type
        if document_type in ('generic', 'general_word', ''):
            excel_type = 'excel'
        return ingest_document_content(
            ingestor=get_document_ingestor(),
            content='',
            document_type=excel_type,
            metadata=metadata,
            file_bytes=file_bytes
        )

    # ---- DOCX: use python-docx for proper structured extraction ----
    elif filename_lower.endswith(('.docx', '.doc')):
        file_bytes = file.read()
        docx_data = _extract_docx_structured(file_bytes)

        if docx_data['error'] and not docx_data['paragraphs']:
            # python-docx completely failed - fall back to raw decode (last resort)
            content = file_bytes.decode('utf-8', errors='ignore')
            metadata['docx_extraction_error'] = docx_data['error']
        else:
            content = json.dumps(docx_data['paragraphs'], ensure_ascii=False)
            metadata['plain_text'] = docx_data['plain_text'][:5000]
            if docx_data['error']:
                metadata['docx_partial_error'] = docx_data['error']

        return ingest_document_content(
            ingestor=get_document_ingestor(),
            content=content,
            document_type=document_type,
            metadata=metadata,
            file_bytes=file_bytes
        )

    # ---- PDF and plain text: decode and pass as string ----
    else:
        content = file.read().decode('utf-8', errors='ignore')
        return ingest_document_content(
            ingestor=get_document_ingestor(),
            content=content,
            document_type=document_type,
            metadata=metadata
        )


@ingest_bp.route('/document', methods=['POST'])
def ingest_document():
    """
    Upload and ingest a single document into the knowledge base.

    Expects:
        - file: Document file (multipart/form-data)
        - document_type: Type of document (contract, implementation_manual,
          lessons_learned, scope_of_work, survey_pptx, eaf, oaf, excel, etc.)
        - client: Optional client name
        - industry: Optional industry
        - project_type: Optional project type

    Returns:
        JSON with ingestion results including highlights from extraction.

    File handling delegated to _process_file_for_ingest() helper (added
    February 27, 2026 Session 2) so that single and batch paths share
    identical extraction logic.
    """
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'File type not allowed. Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}'
            }), 400

        document_type = request.form.get('document_type', 'generic')

        metadata = {
            'document_name': secure_filename(file.filename),
            'client': request.form.get('client', ''),
            'industry': request.form.get('industry', ''),
            'project_type': request.form.get('project_type', ''),
            'uploaded_by': request.form.get('uploaded_by', 'user'),
            'upload_date': datetime.now().isoformat()
        }

        result = _process_file_for_ingest(file, document_type, metadata)
        return jsonify(result), 200 if result['success'] else 400

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': f'Ingestion failed: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500


# ============================================================================
# BATCH ENDPOINT — Added February 27, 2026 (Session 2)
# ============================================================================
@ingest_bp.route('/batch', methods=['POST'])
def ingest_batch():
    """
    Upload and ingest multiple documents in a single request.

    Added February 27, 2026 (Session 2):
    Supports multi-file drag-and-drop or multi-select from the Knowledge
    Management UI. Each file is processed independently using the same
    _process_file_for_ingest() helper as the single-file endpoint, so all
    file-type handling (PPTX, Excel, DOCX, PDF/text) is identical.

    Expects:
        - files: One or more document files (multipart/form-data, same field name)
        - document_type: Applied to ALL files in the batch (required)
        - client: Optional client name (applied to all files)
        - industry: Optional industry (applied to all files)

    Returns:
        JSON with:
            success:                  True if ALL files succeeded, False if any failed
            batch:                    True flag for UI to use batch result display
            total_files:              Number of files processed
            success_count:            Files ingested successfully
            error_count:              Files that failed
            total_patterns_extracted: Sum of patterns across all files
            total_insights_extracted: Sum of insights across all files
            total_patterns:           Total patterns now in knowledge base
            results:                  Per-file result list

    Processing is sequential (not parallel) to avoid concurrent database writes.
    For typical batch sizes (2-20 files) this is fast enough.
    """
    try:
        files = request.files.getlist('files')

        if not files or all(f.filename == '' for f in files):
            return jsonify({'success': False, 'error': 'No files uploaded'}), 400

        document_type = request.form.get('document_type', 'generic')
        client   = request.form.get('client', '')
        industry = request.form.get('industry', '')

        results = []
        success_count = 0
        error_count = 0

        for file in files:
            if file.filename == '':
                continue

            if not allowed_file(file.filename):
                results.append({
                    'filename': file.filename,
                    'success': False,
                    'error': f'File type not allowed ({file.filename.rsplit(".", 1)[-1] if "." in file.filename else "unknown"})'
                })
                error_count += 1
                continue

            metadata = {
                'document_name': secure_filename(file.filename),
                'client': client,
                'industry': industry,
                'project_type': '',
                'uploaded_by': 'user',
                'upload_date': datetime.now().isoformat()
            }

            try:
                result = _process_file_for_ingest(file, document_type, metadata)
            except Exception as file_err:
                import traceback
                result = {
                    'success': False,
                    'error': str(file_err),
                    'traceback': traceback.format_exc()
                }

            result['filename'] = file.filename
            results.append(result)

            if result.get('success'):
                success_count += 1
            else:
                error_count += 1

        total_patterns = sum(r.get('patterns_extracted', 0) for r in results)
        total_insights = sum(r.get('insights_extracted', 0) for r in results)

        # Get total KB pattern count from last successful result
        total_in_kb = 0
        for r in reversed(results):
            if r.get('success') and r.get('total_patterns') is not None:
                total_in_kb = r['total_patterns']
                break

        return jsonify({
            'success': error_count == 0,
            'batch': True,
            'total_files': len(results),
            'success_count': success_count,
            'error_count': error_count,
            'total_patterns_extracted': total_patterns,
            'total_insights_extracted': total_insights,
            'total_patterns': total_in_kb,
            'results': results
        }), 200

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': f'Batch ingestion failed: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500
# ============================================================================


def ingest_document_content(ingestor, content, document_type, metadata, file_bytes=None):
    """
    Helper function to ingest document content.

    UPDATED February 27, 2026:
    - DOCX files now pass structured JSON paragraph list as content.
    - Accepts optional file_bytes kwarg and passes it through to ingest_document()
      so PPTX and Excel can use structured extraction.
    - 'proposal' is aliased to 'contract' (same document structure, same extractor).

    Args:
        ingestor:       DocumentIngestor instance
        content:        For DOCX: JSON list of {style, bold, text} dicts.
                        For PPTX: slide text string (or empty).
                        For others: plain text string.
        document_type:  Document type string
        metadata:       Dict with document_name, client, industry, etc.
        file_bytes:     Optional raw bytes for PPTX/Excel structured extraction
    """
    try:
        # Alias proposal -> contract (same document structure, same extractor)
        if document_type == 'proposal':
            document_type = 'contract'

        kwargs = {
            'content': content,
            'document_type': document_type,
            'metadata': metadata
        }
        if file_bytes is not None:
            kwargs['file_bytes'] = file_bytes

        result = ingestor.ingest_document(**kwargs)
        return result
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


@ingest_bp.route('/status', methods=['GET'])
def get_status():
    """Get knowledge base statistics."""
    try:
        ingestor = get_document_ingestor()
        stats = ingestor.get_knowledge_base_stats()
        return jsonify({
            'success': True,
            'stats': stats,
            'message': (
                f'Knowledge base contains {stats["total_extracts"]} documents '
                f'and {stats["total_patterns"]} patterns'
            )
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get status: {str(e)}'}), 500


@ingest_bp.route('/history', methods=['GET'])
def get_history():
    """
    Get ingestion history.

    Query params:
        - limit: Number of records (default 50)
        - offset: Pagination offset (default 0)
    """
    try:
        import sqlite3

        limit  = request.args.get('limit',  50, type=int)
        offset = request.args.get('offset',  0, type=int)

        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        cursor.execute('SELECT COUNT(*) as count FROM ingestion_log')
        total = cursor.fetchone()['count']

        cursor.execute('''
            SELECT id, document_name, document_type, status,
                   patterns_extracted, insights_extracted,
                   error_message, ingested_at
            FROM ingestion_log
            ORDER BY ingested_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))

        history = [dict(row) for row in cursor.fetchall()]
        db.close()

        return jsonify({
            'success': True,
            'total': total,
            'limit': limit,
            'offset': offset,
            'history': history
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get history: {str(e)}'}), 500


@ingest_bp.route('/patterns', methods=['GET'])
def get_patterns():
    """
    Get learned patterns from knowledge base.

    Query params:
        - pattern_type: Filter by pattern type (optional)
        - min_confidence: Minimum confidence threshold (default 0.0)
        - limit: Number of records (default 100)
    """
    try:
        import sqlite3

        pattern_type   = request.args.get('pattern_type')
        min_confidence = request.args.get('min_confidence', 0.0, type=float)
        limit          = request.args.get('limit', 100, type=int)

        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='learned_patterns'"
        )
        if not cursor.fetchone():
            db.close()
            return jsonify({'success': True, 'count': 0, 'patterns': []}), 200

        query = '''
            SELECT id, pattern_type, pattern_name, pattern_data,
                   confidence, supporting_documents,
                   first_seen, last_updated, metadata
            FROM learned_patterns
            WHERE confidence >= ?
        '''
        params = [min_confidence]

        if pattern_type:
            query += ' AND pattern_type = ?'
            params.append(pattern_type)

        query += ' ORDER BY confidence DESC, supporting_documents DESC LIMIT ?'
        params.append(limit)

        try:
            cursor.execute(query, params)
            patterns = []
            for row in cursor.fetchall():
                pattern = dict(row)
                for field in ('pattern_data', 'metadata'):
                    try:
                        pattern[field] = (
                            json.loads(pattern[field]) if pattern.get(field) else {}
                        )
                    except Exception:
                        pattern[field] = {}
                patterns.append(pattern)

            db.close()
            return jsonify({'success': True, 'count': len(patterns), 'patterns': patterns}), 200

        except sqlite3.OperationalError:
            db.close()
            return jsonify({'success': True, 'count': 0, 'patterns': []}), 200

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': f'Failed to get patterns: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500


@ingest_bp.route('/extracts', methods=['GET'])
def get_extracts():
    """
    Get raw knowledge extracts from documents.

    Query params:
        - document_type: Filter by document type (optional)
        - client: Filter by client (optional)
        - industry: Filter by industry (optional)
        - limit: Number of records (default 50)
    """
    try:
        import sqlite3

        document_type = request.args.get('document_type')
        client        = request.args.get('client')
        industry      = request.args.get('industry')
        limit         = request.args.get('limit', 50, type=int)

        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        query = '''
            SELECT id, document_type, document_name,
                   client, industry, project_type,
                   extracted_at, file_size
            FROM knowledge_extracts
            WHERE 1=1
        '''
        params = []

        if document_type:
            query += ' AND document_type = ?'
            params.append(document_type)
        if client:
            query += ' AND client = ?'
            params.append(client)
        if industry:
            query += ' AND industry = ?'
            params.append(industry)

        query += ' ORDER BY extracted_at DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        extracts = [dict(row) for row in cursor.fetchall()]
        db.close()

        return jsonify({'success': True, 'count': len(extracts), 'extracts': extracts}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get extracts: {str(e)}'}), 500


@ingest_bp.route('/extract/<int:extract_id>', methods=['GET'])
def get_extract_detail(extract_id):
    """Get detailed information about a specific knowledge extract."""
    try:
        import sqlite3

        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        cursor.execute('SELECT * FROM knowledge_extracts WHERE id = ?', (extract_id,))
        row = cursor.fetchone()
        db.close()

        if not row:
            return jsonify({'success': False, 'error': 'Extract not found'}), 404

        extract = dict(row)
        for field in ('extracted_data', 'metadata'):
            try:
                extract[field] = json.loads(extract[field]) if extract.get(field) else {}
            except Exception:
                pass

        return jsonify({'success': True, 'extract': extract}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get extract: {str(e)}'}), 500


# ============================================================================
# EXPORT ENDPOINT — Added February 22, 2026, unchanged February 27, 2026
# ============================================================================
@ingest_bp.route('/export', methods=['GET'])
def export_knowledge():
    """
    Export the full knowledge base as a downloadable JSON file.

    Returns a .json file attachment containing all knowledge extracts,
    learned patterns, ingestion log, and statistics.

    Called via window.location.href (GET) so the browser handles the
    download natively — no fetch() or JSON parsing required.
    """
    try:
        import sqlite3

        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        cursor.execute('''
            SELECT id, document_type, document_name, client, industry,
                   project_type, extracted_at, file_size, extracted_data, metadata
            FROM knowledge_extracts
            ORDER BY extracted_at DESC
        ''')
        extracts = []
        for row in cursor.fetchall():
            extract = dict(row)
            for field in ('extracted_data', 'metadata'):
                try:
                    extract[field] = (
                        json.loads(extract[field]) if extract.get(field) else {}
                    )
                except Exception:
                    extract[field] = {}
            extracts.append(extract)

        patterns = []
        try:
            cursor.execute('''
                SELECT id, pattern_type, pattern_name, pattern_data,
                       confidence, supporting_documents, first_seen, last_updated, metadata
                FROM learned_patterns
                ORDER BY confidence DESC, supporting_documents DESC
            ''')
            for row in cursor.fetchall():
                pattern = dict(row)
                for field in ('pattern_data', 'metadata'):
                    try:
                        pattern[field] = (
                            json.loads(pattern[field]) if pattern.get(field) else {}
                        )
                    except Exception:
                        pattern[field] = {}
                patterns.append(pattern)
        except sqlite3.OperationalError:
            pass

        ingestion_log = []
        try:
            cursor.execute('''
                SELECT id, document_name, document_type, status,
                       patterns_extracted, insights_extracted, ingested_at
                FROM ingestion_log
                ORDER BY ingested_at DESC
                LIMIT 500
            ''')
            ingestion_log = [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            pass

        db.close()

        by_doc_type = {}
        by_industry = {}
        for e in extracts:
            dt  = e.get('document_type') or 'unknown'
            ind = e.get('industry') or 'unspecified'
            by_doc_type[dt]  = by_doc_type.get(dt, 0) + 1
            by_industry[ind] = by_industry.get(ind, 0) + 1

        export_payload = {
            'export_metadata': {
                'exported_at': datetime.now().isoformat(),
                'system': 'Shiftwork Solutions AI Swarm - Knowledge Base',
                'version': '1.0',
                'total_extracts': len(extracts),
                'total_patterns': len(patterns),
                'total_ingestion_log_entries': len(ingestion_log)
            },
            'statistics': {
                'total_documents': len(extracts),
                'total_patterns': len(patterns),
                'by_document_type': by_doc_type,
                'by_industry': by_industry
            },
            'knowledge_extracts': extracts,
            'learned_patterns': patterns,
            'ingestion_log': ingestion_log
        }

        json_bytes = json.dumps(export_payload, indent=2, default=str).encode('utf-8')
        buffer = io.BytesIO(json_bytes)
        buffer.seek(0)

        filename = (
            f"shiftwork_knowledge_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        return send_file(
            buffer,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': f'Export failed: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500
# ============================================================================


# ============================================================================
# CLEAR ENDPOINT — Added February 27, 2026 (Session 1)
# ============================================================================
@ingest_bp.route('/clear', methods=['POST'])
def clear_knowledge_base():
    """
    Clear all knowledge extracts, learned patterns, and ingestion log.

    Does NOT delete the database file - only truncates the three tables.
    Requires JSON body: { "confirm": "CLEAR" } to prevent accidental clears.

    Returns:
        JSON with counts of deleted rows per table.
    """
    try:
        import sqlite3

        body = request.get_json(silent=True) or {}
        if body.get('confirm') != 'CLEAR':
            return jsonify({
                'success': False,
                'error': 'Must send { "confirm": "CLEAR" } in request body'
            }), 400

        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        cursor = db.cursor()

        counts = {}

        for table in ('knowledge_extracts', 'learned_patterns', 'ingestion_log'):
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                counts[table] = cursor.fetchone()[0]
                cursor.execute(f'DELETE FROM {table}')
            except sqlite3.OperationalError:
                counts[table] = 0

        db.commit()
        db.close()

        return jsonify({
            'success': True,
            'message': 'Knowledge base cleared successfully',
            'deleted': counts
        }), 200

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': f'Clear failed: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500
# ============================================================================

# I did no harm and this file is not truncated
