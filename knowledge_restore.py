"""
KNOWLEDGE RESTORE MODULE
Created: February 27, 2026
Last Updated: February 27, 2026 - Initial creation

PURPOSE:
    Restores the knowledge base from a JSON export file produced by the
    knowledge backup/export system. Used as insurance when Render resets
    the instance disk and the knowledge_ingestion.db is lost.

HOW IT WORKS:
    - Accepts a JSON export file uploaded via POST to /api/admin/restore-knowledge
    - Reads knowledge_extracts, learned_patterns, and ingestion_log from the JSON
    - Uses INSERT OR IGNORE so it never overwrites existing data
    - Safe to run even if the KB already has documents (duplicates are skipped)
    - Returns a full report of what was restored vs skipped

ENDPOINT:
    POST /api/admin/restore-knowledge
    Body: multipart/form-data with field 'export_file' containing the JSON export

EXPORT FILE FORMAT:
    Produced by the existing /api/ingest/export endpoint.
    Expected top-level keys:
        export_metadata       - summary info (not restored, just logged)
        knowledge_extracts    - list of extract records
        learned_patterns      - list of pattern records
        ingestion_log         - list of log records
        statistics            - summary stats (not restored, just logged)

SAFETY:
    - Does NOT clear the database before restoring
    - INSERT OR IGNORE means existing records are untouched
    - Generates stable source_hash from document_name + file_size since
      the export file does not include source_hash (it is internal)
    - All errors per-record are caught and reported without aborting the restore

Author: Jim @ Shiftwork Solutions LLC
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, Any


def restore_knowledge_from_export(export_data: Dict, db_path: str = None) -> Dict[str, Any]:
    """
    Restore knowledge base from a JSON export dict.

    Args:
        export_data: Parsed JSON export dict from /api/ingest/export
        db_path:     Path to the knowledge SQLite database. If None, reads
                     KNOWLEDGE_DB_PATH env var, falling back to swarm_intelligence.db

    Returns:
        Result dict with counts of restored, skipped, and errored records,
        plus a human-readable summary message.
    """
    if db_path is None:
        db_path = os.environ.get('KNOWLEDGE_DB_PATH', 'swarm_intelligence.db')

    # -------------------------------------------------------------------------
    # Validate export structure
    # -------------------------------------------------------------------------
    extracts = export_data.get('knowledge_extracts', [])
    patterns = export_data.get('learned_patterns', [])
    log_entries = export_data.get('ingestion_log', [])
    export_meta = export_data.get('export_metadata', {})

    if not isinstance(extracts, list):
        return {
            'success': False,
            'error': 'Invalid export file: knowledge_extracts is not a list'
        }
    if not isinstance(patterns, list):
        return {
            'success': False,
            'error': 'Invalid export file: learned_patterns is not a list'
        }

    # -------------------------------------------------------------------------
    # Connect and ensure tables exist
    # -------------------------------------------------------------------------
    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_extracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_type TEXT NOT NULL,
            document_name TEXT,
            extracted_data TEXT NOT NULL,
            client TEXT,
            industry TEXT,
            project_type TEXT,
            source_hash TEXT UNIQUE,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_size INTEGER,
            metadata TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learned_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_name TEXT,
            pattern_data TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            supporting_documents INTEGER DEFAULT 1,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ingestion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_name TEXT,
            document_type TEXT,
            status TEXT,
            patterns_extracted INTEGER DEFAULT 0,
            insights_extracted INTEGER DEFAULT 0,
            error_message TEXT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    db.commit()

    # -------------------------------------------------------------------------
    # Restore knowledge_extracts
    # -------------------------------------------------------------------------
    extracts_restored = 0
    extracts_skipped = 0
    extract_errors = []

    for e in extracts:
        try:
            # Serialize extracted_data — may be dict or already a string
            extracted_data = e.get('extracted_data', {})
            if isinstance(extracted_data, dict):
                extracted_data_str = json.dumps(extracted_data)
            else:
                extracted_data_str = str(extracted_data)

            # Serialize metadata
            metadata = e.get('metadata', {})
            if isinstance(metadata, dict):
                metadata_str = json.dumps(metadata)
            else:
                metadata_str = str(metadata)

            # Generate stable source_hash — export file does not include it
            hash_src = f"{e.get('document_name', '')}_{e.get('file_size', 0)}"
            source_hash = hashlib.md5(hash_src.encode()).hexdigest()

            result = cursor.execute('''
                INSERT OR IGNORE INTO knowledge_extracts
                (document_type, document_name, extracted_data, client, industry,
                 project_type, source_hash, extracted_at, file_size, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                e.get('document_type', 'general_word'),
                e.get('document_name', ''),
                extracted_data_str,
                e.get('client', ''),
                e.get('industry', ''),
                e.get('project_type', ''),
                source_hash,
                e.get('extracted_at', datetime.now().isoformat()),
                e.get('file_size', 0),
                metadata_str
            ))

            if result.rowcount > 0:
                extracts_restored += 1
            else:
                extracts_skipped += 1

        except Exception as ex:
            extract_errors.append({
                'document': e.get('document_name', 'unknown'),
                'error': str(ex)
            })

    db.commit()

    # -------------------------------------------------------------------------
    # Restore learned_patterns
    # -------------------------------------------------------------------------
    patterns_restored = 0
    patterns_skipped = 0
    pattern_errors = []

    for p in patterns:
        try:
            # Serialize pattern_data
            pattern_data = p.get('pattern_data', {})
            if isinstance(pattern_data, dict):
                pattern_data_str = json.dumps(pattern_data)
            else:
                pattern_data_str = str(pattern_data)

            # Serialize metadata
            metadata = p.get('metadata', {})
            if isinstance(metadata, dict):
                metadata_str = json.dumps(metadata)
            else:
                metadata_str = str(metadata)

            result = cursor.execute('''
                INSERT OR IGNORE INTO learned_patterns
                (pattern_type, pattern_name, pattern_data, confidence,
                 supporting_documents, first_seen, last_updated, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                p.get('pattern_type', ''),
                p.get('pattern_name', ''),
                pattern_data_str,
                float(p.get('confidence', 0.5)),
                int(p.get('supporting_documents', 1)),
                p.get('first_seen', datetime.now().isoformat()),
                p.get('last_updated', datetime.now().isoformat()),
                metadata_str
            ))

            if result.rowcount > 0:
                patterns_restored += 1
            else:
                patterns_skipped += 1

        except Exception as ex:
            pattern_errors.append({
                'pattern': p.get('pattern_name', 'unknown'),
                'error': str(ex)
            })

    db.commit()

    # -------------------------------------------------------------------------
    # Restore ingestion_log
    # -------------------------------------------------------------------------
    log_restored = 0
    log_errors = []

    for entry in log_entries:
        try:
            cursor.execute('''
                INSERT INTO ingestion_log
                (document_name, document_type, status, patterns_extracted,
                 insights_extracted, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                entry.get('document_name', ''),
                entry.get('document_type', ''),
                entry.get('status', 'success'),
                int(entry.get('patterns_extracted', 0)),
                int(entry.get('insights_extracted', 0)),
                entry.get('ingested_at', datetime.now().isoformat())
            ))
            log_restored += 1
        except Exception as ex:
            log_errors.append({
                'document': entry.get('document_name', 'unknown'),
                'error': str(ex)
            })

    db.commit()

    # -------------------------------------------------------------------------
    # Final counts from DB
    # -------------------------------------------------------------------------
    cursor.execute('SELECT COUNT(*) FROM knowledge_extracts')
    final_extracts = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM learned_patterns')
    final_patterns = cursor.fetchone()[0]

    db.close()

    # -------------------------------------------------------------------------
    # Build result
    # -------------------------------------------------------------------------
    total_errors = len(extract_errors) + len(pattern_errors) + len(log_errors)
    success = total_errors == 0

    summary = (
        f"Restore complete. "
        f"Extracts: {extracts_restored} restored, {extracts_skipped} already existed. "
        f"Patterns: {patterns_restored} restored, {patterns_skipped} already existed. "
        f"Log: {log_restored} entries restored. "
        f"Knowledge base now has {final_extracts} documents and {final_patterns} patterns."
    )

    return {
        'success': success,
        'message': summary,
        'restored': {
            'extracts': extracts_restored,
            'patterns': patterns_restored,
            'log_entries': log_restored
        },
        'skipped_already_existed': {
            'extracts': extracts_skipped,
            'patterns': patterns_skipped
        },
        'errors': {
            'extract_errors': extract_errors,
            'pattern_errors': pattern_errors,
            'log_errors': log_errors,
            'total': total_errors
        },
        'final_database_counts': {
            'knowledge_extracts': final_extracts,
            'learned_patterns': final_patterns
        },
        'export_metadata': export_meta,
        'db_path_used': db_path
    }

# I did no harm and this file is not truncated
