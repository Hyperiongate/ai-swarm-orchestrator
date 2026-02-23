"""
KNOWLEDGE INGESTION ROUTES
Created: February 2, 2026
Last Updated: February 22, 2026 - ADDED /export endpoint for direct knowledge download

CHANGELOG:

- February 22, 2026: ADDED /api/ingest/export (GET)
  PROBLEM: The Download Knowledge button called /api/knowledge/export which depends on
           knowledge_backup_system module that does not exist on the server. Flask returned
           an HTML 404 page. JavaScript tried to parse that as JSON, producing:
           "Unexpected token '<', '<!doctype'... is not valid JSON"
  FIX: Added /api/ingest/export directly to this blueprint. Queries the existing
       knowledge_extracts and learned_patterns tables (both confirmed working) and
       streams a .json file directly to the browser using send_file() + BytesIO.
       Zero new dependencies. knowledge_management.html updated to call this endpoint
       via window.location.href (native browser download — no JSON parsing involved).

- February 4, 2026: FIXED PowerPoint temp file handling
  Must close temp file before python-pptx can open it. Added proper cleanup in finally block.

Flask API endpoints for document ingestion system.
Allows uploading documents, viewing knowledge base stats, browsing patterns.

Part of "Shoulders of Giants" cumulative learning system.

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
    # Attempt 1: Direct import
    from document_ingestion_engine import get_document_ingestor
    print("✅ Knowledge Ingestion: Direct import succeeded")
except ImportError as e1:
    print(f"⚠️  Direct import failed: {e1}")
    try:
        # Attempt 2: Add parent to path
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from document_ingestion_engine import get_document_ingestor
        print("✅ Knowledge Ingestion: Path-adjusted import succeeded")
    except ImportError as e2:
        print(f"⚠️  Path-adjusted import failed: {e2}")
        try:
            # Attempt 3: Add root directory explicitly
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

# Allowed file extensions - UPDATED with PowerPoint support
ALLOWED_EXTENSIONS = {
    'txt', 'md', 'pdf', 'docx', 'doc', 
    'xlsx', 'xls', 'csv', 'json', 'pptx', 'ppt'
}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@ingest_bp.route('/document', methods=['POST'])
def ingest_document():
    """
    Upload and ingest a document into the knowledge base.
    
    Expects:
        - file: Document file (multipart/form-data)
        - document_type: Type of document (implementation_manual, lessons_learned, etc.)
        - client: Optional client name
        - industry: Optional industry
        - project_type: Optional project type
        
    Returns:
        JSON with ingestion results
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded'
            }), 400
        
        file = request.files['file']
        
        # Check if file was selected
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Validate file type
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Get document type
        document_type = request.form.get('document_type', 'generic')
        
        # Get metadata
        metadata = {
            'document_name': secure_filename(file.filename),
            'client': request.form.get('client'),
            'industry': request.form.get('industry'),
            'project_type': request.form.get('project_type'),
            'uploaded_by': request.form.get('uploaded_by', 'user'),
            'upload_date': datetime.now().isoformat()
        }
        
        # Read file content - FIXED PowerPoint support (February 4, 2026)
        if file.filename.lower().endswith(('.pptx', '.ppt')):
            # Extract text from PowerPoint
            try:
                from pptx import Presentation
                
                # Save to temporary file - FIXED: Must close before reading
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pptx')
                tmp_path = tmp.name
                file.save(tmp_path)
                tmp.close()  # CRITICAL: Close the file so python-pptx can open it
                
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
                            slide_texts.append(f"[Slide {slide_num}]\n" + '\n'.join(slide_content))
                    
                    content = '\n\n'.join(slide_texts)
                    
                    if not content:
                        content = "[PowerPoint file with no extractable text]"
                    
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
                    
            except ImportError:
                return jsonify({
                    'success': False,
                    'error': 'PowerPoint support not installed. Contact administrator.'
                }), 500
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Failed to extract PowerPoint content: {str(e)}'
                }), 500
        else:
            # Regular text extraction for other file types
            content = file.read().decode('utf-8', errors='ignore')
        
        # Ingest document
        ingestor = get_document_ingestor()
        result = ingest_document_content(ingestor, content, document_type, metadata)
        
        return jsonify(result), 200 if result['success'] else 400
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ingestion failed: {str(e)}'
        }), 500


def ingest_document_content(ingestor, content, document_type, metadata):
    """Helper function to ingest document content"""
    try:
        result = ingestor.ingest_document(
            content=content,
            document_type=document_type,
            metadata=metadata
        )
        return result
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@ingest_bp.route('/status', methods=['GET'])
def get_status():
    """
    Get knowledge base statistics.
    
    Returns:
        JSON with:
        - total_extracts: Total documents ingested
        - total_patterns: Total learned patterns
        - by_document_type: Breakdown by type
        - recent_ingestions: Last 10 ingestions
    """
    try:
        ingestor = get_document_ingestor()
        stats = ingestor.get_knowledge_base_stats()
        
        return jsonify({
            'success': True,
            'stats': stats,
            'message': f'Knowledge base contains {stats["total_extracts"]} documents and {stats["total_patterns"]} patterns'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get status: {str(e)}'
        }), 500


@ingest_bp.route('/history', methods=['GET'])
def get_history():
    """
    Get ingestion history.
    
    Query params:
        - limit: Number of records (default 50)
        - offset: Pagination offset (default 0)
        
    Returns:
        JSON with ingestion log entries
    """
    try:
        import sqlite3
        
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Get total count
        cursor.execute('SELECT COUNT(*) as count FROM ingestion_log')
        total = cursor.fetchone()['count']
        
        # Get paginated results
        cursor.execute('''
            SELECT 
                id, document_name, document_type, status,
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
        return jsonify({
            'success': False,
            'error': f'Failed to get history: {str(e)}'
        }), 500


@ingest_bp.route('/patterns', methods=['GET'])
def get_patterns():
    """
    Get learned patterns from knowledge base.
    
    Query params:
        - pattern_type: Filter by pattern type (optional)
        - min_confidence: Minimum confidence threshold (default 0.0)
        - limit: Number of records (default 100)
        
    Returns:
        JSON with learned patterns
    """
    try:
        import sqlite3
        
        pattern_type = request.args.get('pattern_type')
        min_confidence = request.args.get('min_confidence', 0.0, type=float)
        limit = request.args.get('limit', 100, type=int)
        
        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Check if table exists
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learned_patterns'")
            if not cursor.fetchone():
                db.close()
                return jsonify({
                    'success': True,
                    'count': 0,
                    'patterns': []
                }), 200
        except:
            pass
        
        # Try to query patterns - handle missing columns gracefully
        try:
            query = '''
                SELECT 
                    id, pattern_type, pattern_name, pattern_data,
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
            
            cursor.execute(query, params)
            patterns = []
            
            for row in cursor.fetchall():
                pattern = dict(row)
                # Parse JSON fields safely
                try:
                    pattern['pattern_data'] = json.loads(pattern['pattern_data']) if pattern.get('pattern_data') else {}
                except:
                    pattern['pattern_data'] = {}
                
                try:
                    pattern['metadata'] = json.loads(pattern['metadata']) if pattern.get('metadata') else {}
                except:
                    pattern['metadata'] = {}
                
                patterns.append(pattern)
            
            db.close()
            
            return jsonify({
                'success': True,
                'count': len(patterns),
                'patterns': patterns
            }), 200
            
        except sqlite3.OperationalError as e:
            # Handle missing columns - return empty patterns instead of crashing
            db.close()
            return jsonify({
                'success': True,
                'count': 0,
                'patterns': []
            }), 200
        
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
        
    Returns:
        JSON with knowledge extracts
    """
    try:
        import sqlite3
        
        document_type = request.args.get('document_type')
        client = request.args.get('client')
        industry = request.args.get('industry')
        limit = request.args.get('limit', 50, type=int)
        
        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        # Build query
        query = '''
            SELECT 
                id, document_type, document_name,
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
        
        return jsonify({
            'success': True,
            'count': len(extracts),
            'extracts': extracts
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get extracts: {str(e)}'
        }), 500


@ingest_bp.route('/extract/<int:extract_id>', methods=['GET'])
def get_extract_detail(extract_id):
    """
    Get detailed information about a specific knowledge extract.
    
    Returns:
        JSON with full extract data including patterns and insights
    """
    try:
        import sqlite3
        
        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        
        cursor.execute('''
            SELECT * FROM knowledge_extracts WHERE id = ?
        ''', (extract_id,))
        
        row = cursor.fetchone()
        db.close()
        
        if not row:
            return jsonify({
                'success': False,
                'error': 'Extract not found'
            }), 404
        
        extract = dict(row)
        
        # Parse JSON fields
        try:
            extract['extracted_data'] = json.loads(extract['extracted_data']) if extract['extracted_data'] else {}
            extract['metadata'] = json.loads(extract['metadata']) if extract['metadata'] else {}
        except:
            pass
        
        return jsonify({
            'success': True,
            'extract': extract
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get extract: {str(e)}'
        }), 500


# ============================================================================
# EXPORT ENDPOINT - Added February 22, 2026
# ============================================================================
# Replaces the broken /api/knowledge/export from knowledge_backup_routes.py
# which depends on knowledge_backup_system — a module that does not exist on
# the server. That missing module caused Flask to return an HTML 404 page,
# which the JS tried to parse as JSON, producing the error:
#   "Unexpected token '<', '<!doctype'... is not valid JSON"
#
# This endpoint uses only the existing SQLite tables already queried above.
# Zero new dependencies. Returns a single .json file as a direct download.
# knowledge_management.html calls this via window.location.href (GET) so the
# browser handles the file download natively — no JSON parsing in JS,
# making the HTML-as-JSON error structurally impossible.
# ============================================================================
@ingest_bp.route('/export', methods=['GET'])
def export_knowledge():
    """
    Export the full knowledge base as a downloadable JSON file.

    Returns a .json file attachment containing:
    - All knowledge extracts (document metadata + extracted content)
    - All learned patterns
    - Recent ingestion log (last 500 entries)
    - Summary statistics

    Called via GET so the browser can trigger a native file download
    using window.location.href — no fetch() or JSON parsing required.
    """
    try:
        import sqlite3

        ingestor = get_document_ingestor()
        db = sqlite3.connect(ingestor.db_path)
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        # ---- Knowledge extracts ----
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
                    extract[field] = json.loads(extract[field]) if extract.get(field) else {}
                except Exception:
                    extract[field] = {}
            extracts.append(extract)

        # ---- Learned patterns ----
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
                        pattern[field] = json.loads(pattern[field]) if pattern.get(field) else {}
                    except Exception:
                        pattern[field] = {}
                patterns.append(pattern)
        except sqlite3.OperationalError:
            # learned_patterns table may not exist yet — export empty list
            pass

        # ---- Ingestion log (last 500) ----
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

        # ---- Build statistics breakdowns ----
        by_doc_type = {}
        by_industry = {}
        for e in extracts:
            dt = e.get('document_type') or 'unknown'
            ind = e.get('industry') or 'unspecified'
            by_doc_type[dt] = by_doc_type.get(dt, 0) + 1
            by_industry[ind] = by_industry.get(ind, 0) + 1

        # ---- Assemble export payload ----
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

        # ---- Stream as downloadable JSON file ----
        json_bytes = json.dumps(export_payload, indent=2, default=str).encode('utf-8')
        buffer = io.BytesIO(json_bytes)
        buffer.seek(0)

        filename = f"shiftwork_knowledge_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        return send_file(
            buffer,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        import traceback
        # Return JSON (not HTML) so any error is parseable by the frontend
        return jsonify({
            'success': False,
            'error': f'Export failed: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500
# ============================================================================

# I did no harm and this file is not truncated
