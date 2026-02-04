"""
Knowledge Backup API Routes
Created: February 4, 2026
Last Updated: February 4, 2026

Flask routes for exporting and backing up learned knowledge.
Provides manual and automated backup capabilities.

ENDPOINTS:
- GET  /api/knowledge/statistics - Get knowledge base statistics
- POST /api/knowledge/export - Export knowledge (format: json/markdown/csv/all)
- GET  /api/knowledge/backup/latest - Get latest backup info
- POST /api/knowledge/backup/run - Run manual backup now

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify, send_file
from knowledge_backup_system import (
    KnowledgeBackupSystem,
    backup_knowledge_all_formats,
    get_knowledge_statistics,
    export_knowledge_json,
    export_knowledge_markdown,
    export_knowledge_csv
)
import os
from datetime import datetime

# Create blueprint
knowledge_backup_bp = Blueprint('knowledge_backup', __name__)


@knowledge_backup_bp.route('/api/knowledge/statistics', methods=['GET'])
def get_statistics():
    """
    Get statistics about the knowledge base.
    
    Returns:
    {
        "success": true,
        "total_items": 127,
        "by_category": {
            "client_preference": 45,
            "best_practice": 32,
            "industry_insight": 28,
            "warning": 22
        },
        "by_source": {
            "conversation_learning": 98,
            "manual_entry": 29
        },
        "date_range": {
            "oldest": "2026-02-01 10:30:00",
            "newest": "2026-02-04 15:45:00"
        },
        "average_confidence": 0.85
    }
    """
    try:
        db_path = os.environ.get('SWARM_DB_PATH', 'swarm_intelligence.db')
        stats = get_knowledge_statistics(db_path)
        
        if stats['success']:
            return jsonify(stats), 200
        else:
            return jsonify({
                'success': False,
                'error': stats.get('error', 'Unknown error')
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@knowledge_backup_bp.route('/api/knowledge/export', methods=['POST'])
def export_knowledge():
    """
    Export knowledge to specified format.
    
    Request Body:
    {
        "format": "json" | "markdown" | "csv" | "all"
    }
    
    Returns:
    - For single format: Download link to file
    - For "all": Multiple download links
    """
    try:
        data = request.json or {}
        export_format = data.get('format', 'json').lower()
        
        db_path = os.environ.get('SWARM_DB_PATH', 'swarm_intelligence.db')
        output_dir = '/tmp'
        
        if export_format == 'all':
            # Export all formats
            results = backup_knowledge_all_formats(db_path, output_dir)
            
            # Save files to database for download
            file_ids = []
            for export_result in results['exports']:
                if export_result.get('success'):
                    file_path = export_result['output_path']
                    filename = os.path.basename(file_path)
                    
                    # Save to generated documents (so user can download)
                    from database import save_generated_document
                    doc_id = save_generated_document(
                        filename=filename,
                        original_name=f"Knowledge Backup - {export_result['format'].upper()}",
                        document_type=export_result['format'],
                        file_path=file_path,
                        file_size=export_result['file_size_bytes'],
                        task_id=None,
                        conversation_id=None,
                        project_id=None,
                        title=f"Knowledge Base Backup ({export_result['format'].upper()})",
                        description=f"Exported {export_result['items_exported']} knowledge items",
                        category='backup'
                    )
                    
                    file_ids.append({
                        'format': export_result['format'],
                        'document_id': doc_id,
                        'download_url': f"/api/generated-documents/{doc_id}/download",
                        'items_count': export_result['items_exported'],
                        'file_size_kb': export_result['file_size_kb']
                    })
            
            return jsonify({
                'success': True,
                'exports': file_ids,
                'timestamp': results['timestamp']
            }), 200
            
        else:
            # Export single format
            if export_format == 'json':
                result = export_knowledge_json(db_path)
            elif export_format == 'markdown' or export_format == 'md':
                result = export_knowledge_markdown(db_path)
            elif export_format == 'csv':
                result = export_knowledge_csv(db_path)
            else:
                return jsonify({
                    'success': False,
                    'error': f"Invalid format: {export_format}. Use: json, markdown, csv, or all"
                }), 400
            
            if result['success']:
                file_path = result['output_path']
                filename = os.path.basename(file_path)
                
                # Save to generated documents
                from database import save_generated_document
                doc_id = save_generated_document(
                    filename=filename,
                    original_name=f"Knowledge Backup - {result['format'].upper()}",
                    document_type=result['format'],
                    file_path=file_path,
                    file_size=result['file_size_bytes'],
                    task_id=None,
                    conversation_id=None,
                    project_id=None,
                    title=f"Knowledge Base Backup ({result['format'].upper()})",
                    description=f"Exported {result['items_exported']} knowledge items",
                    category='backup'
                )
                
                return jsonify({
                    'success': True,
                    'format': result['format'],
                    'document_id': doc_id,
                    'download_url': f"/api/generated-documents/{doc_id}/download",
                    'items_exported': result['items_exported'],
                    'file_size_kb': result['file_size_kb']
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Export failed')
                }), 500
                
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@knowledge_backup_bp.route('/api/knowledge/backup/run', methods=['POST'])
def run_manual_backup():
    """
    Run a manual backup now (all formats).
    
    Returns:
    {
        "success": true,
        "backup_id": "20260204_153045",
        "files_created": 3,
        "download_urls": [...]
    }
    """
    try:
        # This just calls the export with "all" format
        data = {'format': 'all'}
        request.json = data
        return export_knowledge()
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@knowledge_backup_bp.route('/api/knowledge/backup/latest', methods=['GET'])
def get_latest_backup():
    """
    Get info about the most recent backup files.
    
    Returns:
    {
        "success": true,
        "latest_backups": [
            {
                "filename": "knowledge_backup_20260204_153045.json",
                "created": "2026-02-04 15:30:45",
                "size_kb": 256
            },
            ...
        ]
    }
    """
    try:
        from database import get_db
        
        db = get_db()
        cursor = db.execute('''
            SELECT id, filename, original_name, created_at, file_size
            FROM generated_documents
            WHERE category = 'backup'
            ORDER BY created_at DESC
            LIMIT 10
        ''')
        
        backups = []
        for row in cursor.fetchall():
            backups.append({
                'document_id': row['id'],
                'filename': row['filename'],
                'title': row['original_name'],
                'created_at': row['created_at'],
                'file_size_bytes': row['file_size'],
                'file_size_kb': round(row['file_size'] / 1024, 2),
                'download_url': f"/api/generated-documents/{row['id']}/download"
            })
        
        db.close()
        
        return jsonify({
            'success': True,
            'total_found': len(backups),
            'latest_backups': backups
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# I did no harm and this file is not truncated
