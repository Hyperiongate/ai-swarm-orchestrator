"""
Knowledge Backup API Routes
Created: February 4, 2026
Last Updated: February 26, 2026 - FIXED: Use KNOWLEDGE_DB_PATH via updated backup system

CHANGELOG:
- February 26, 2026: FIXED DB Path Reference
  * PROBLEM: get_statistics() was reading SWARM_DB_PATH env var, which pointed to
    swarm_intelligence.db (the operational database). The knowledge extracts live
    in KNOWLEDGE_DB_PATH (a separate persistent database). This meant the statistics
    endpoint was always looking in the wrong database.
  * FIX: Removed explicit db_path arguments from all standalone function calls.
    The updated knowledge_backup_system.py standalone functions now default to
    reading KNOWLEDGE_DB_PATH themselves, matching DocumentIngestor behavior.
    This ensures all three systems (ingestor, backup, routes) always use the same DB.
  * No route signatures changed — API contract with frontend is unchanged.

- February 4, 2026: Original file created
  * GET  /api/knowledge/statistics - Get knowledge base statistics
  * POST /api/knowledge/export - Export knowledge (format: json/markdown/csv/all)
  * GET  /api/knowledge/backup/latest - Get latest backup info
  * POST /api/knowledge/backup/run - Run manual backup now

ENDPOINTS:
- GET  /api/knowledge/statistics - Get knowledge base statistics
- POST /api/knowledge/export - Export knowledge (format: json/markdown/csv/all)
- GET  /api/knowledge/backup/latest - Get latest backup info
- POST /api/knowledge/backup/run - Run manual backup now

Author: Jim @ Shiftwork Solutions LLC
"""

from flask import Blueprint, request, jsonify
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

    FIXED February 26, 2026: No longer passes SWARM_DB_PATH — the backup system
    now reads KNOWLEDGE_DB_PATH automatically, matching the ingestor.

    Returns:
    {
        "success": true,
        "total_documents": 12,
        "total_learned_patterns": 45,
        "by_document_type": { "implementation_manual": 5, "lessons_learned": 3 },
        "by_client": { "Andersen": 2, "unknown": 10 },
        "by_industry": { "Manufacturing": 4, "unknown": 8 },
        "date_range": { "oldest": "...", "newest": "..." },
        "average_pattern_confidence": 0.82,
        "recent_ingestions": [...]
    }
    """
    try:
        # Pass None - backup system reads KNOWLEDGE_DB_PATH env var automatically
        stats = get_knowledge_statistics(None)

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

        # Pass None - backup system reads KNOWLEDGE_DB_PATH env var automatically
        output_dir = '/tmp'

        if export_format == 'all':
            results = backup_knowledge_all_formats(None, output_dir)

            file_ids = []
            for export_result in results['exports']:
                if export_result.get('success'):
                    file_path = export_result['output_path']
                    filename = os.path.basename(file_path)

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
                result = export_knowledge_json(None)
            elif export_format in ('markdown', 'md'):
                result = export_knowledge_markdown(None)
            elif export_format == 'csv':
                result = export_knowledge_csv(None)
            else:
                return jsonify({
                    'success': False,
                    'error': f"Invalid format: {export_format}. Use: json, markdown, csv, or all"
                }), 400

            if result['success']:
                file_path = result['output_path']
                filename = os.path.basename(file_path)

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
        "exports": [...],
        "timestamp": "20260226_143022"
    }
    """
    try:
        results = backup_knowledge_all_formats(None, '/tmp')

        file_ids = []
        for export_result in results['exports']:
            if export_result.get('success'):
                file_path = export_result['output_path']
                filename = os.path.basename(file_path)

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
            'timestamp': results['timestamp'],
            'summary': results.get('summary', {})
        }), 200

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
                "document_id": 42,
                "filename": "knowledge_backup_20260226_143022.json",
                "title": "Knowledge Base Backup (JSON)",
                "created_at": "2026-02-26 14:30:22",
                "file_size_kb": 18.4,
                "download_url": "/api/generated-documents/42/download"
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
                'file_size_kb': round((row['file_size'] or 0) / 1024, 2),
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
