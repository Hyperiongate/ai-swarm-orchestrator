"""
KNOWLEDGE INGESTION ROUTES
Created: February 2, 2026
Last Updated: February 2, 2026

Flask API endpoints for document ingestion system.
Allows uploading documents, viewing knowledge base stats, browsing patterns.

Part of "Shoulders of Giants" cumulative learning system.

Author: Jim @ Shiftwork Solutions LLC (managed by Claude Sonnet 4)
"""

from flask import Blueprint, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
from document_ingestion_engine import get_document_ingestor

# Create blueprint
ingest_bp = Blueprint('ingest', __name__, url_prefix='/api/ingest')

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'txt', 'md', 'pdf', 'docx', 'doc', 
    'xlsx', 'xls', 'csv', 'json'
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
        
        # Read file content
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
        
        # Build query
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
            # Parse JSON fields
            try:
                pattern['pattern_data'] = json.loads(pattern['pattern_data']) if pattern['pattern_data'] else {}
                pattern['metadata'] = json.loads(pattern['metadata']) if pattern['metadata'] else {}
            except:
                pass
            patterns.append(pattern)
        
        db.close()
        
        return jsonify({
            'success': True,
            'count': len(patterns),
            'patterns': patterns
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get patterns: {str(e)}'
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


# HTML page route (outside /api prefix)
@ingest_bp.route('/manage', methods=['GET'])
def manage_page():
    """Render knowledge management UI page"""
    return render_template('knowledge_management.html')


# I did no harm and this file is not truncated
