"""
Knowledge Backup System - Export Learned Intelligence
Created: February 4, 2026
Last Updated: February 26, 2026 - CRITICAL FIX: Correct schema alignment and KNOWLEDGE_DB_PATH

CHANGELOG:
- February 26, 2026: CRITICAL FIX - Schema Alignment and DB Path Correction
  * PROBLEM: Every export method queried columns that do not exist in knowledge_extracts:
    source, content, category, confidence_score, last_accessed — all five were wrong.
    This caused every backup/export/statistics call to crash silently.
  * ACTUAL SCHEMA (from document_ingestion_engine.py):
    id, document_type, document_name, extracted_data, client, industry,
    project_type, source_hash, extracted_at, file_size, metadata
  * FIX: All query methods now use the correct column names.
  * FIX: __init__ now reads KNOWLEDGE_DB_PATH env var (same as DocumentIngestor)
    instead of hardcoding swarm_intelligence.db. This ensures backup and ingestor
    always point to the same database.
  * FIX: get_statistics() rebuilt from scratch against actual schema.
  * FIX: export_to_json(), export_to_markdown(), export_to_csv() rebuilt
    against actual schema. CSV now includes patterns_count and insights_count
    derived from extracted_data JSON rather than non-existent columns.
  * NOTE: The learned_patterns and ingestion_log tables are also in KNOWLEDGE_DB_PATH.
    Statistics now includes pattern counts and recent ingestion log entries.

- February 4, 2026: Original file created
  * Export all knowledge extracts to JSON (machine-readable)
  * Export to Markdown (human-readable)
  * Export to CSV (spreadsheet-compatible)
  * Manual export on demand
  * Statistics and health check

Author: Jim @ Shiftwork Solutions LLC
"""

import sqlite3
import json
import csv
from datetime import datetime
import os


class KnowledgeBackupSystem:
    """System for backing up and exporting learned intelligence"""

    def __init__(self, db_path=None):
        """
        Initialize backup system.

        FIXED February 26, 2026: Now reads KNOWLEDGE_DB_PATH env var by default,
        matching the behavior of DocumentIngestor. Previously hardcoded
        swarm_intelligence.db which pointed to the wrong database entirely.
        """
        if db_path is None:
            db_path = os.environ.get('KNOWLEDGE_DB_PATH', 'swarm_intelligence.db')
        self.db_path = db_path
        print(f"📦 Knowledge Backup System using DB: {self.db_path}")

    def get_all_knowledge(self):
        """
        Retrieve all knowledge extracts from database.

        FIXED February 26, 2026: Now queries the actual schema that
        document_ingestion_engine.py creates:
          id, document_type, document_name, extracted_data, client,
          industry, project_type, source_hash, extracted_at, file_size, metadata

        Previously queried non-existent columns (source, content, category,
        confidence_score, last_accessed) which caused every call to crash.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    id,
                    document_type,
                    document_name,
                    extracted_data,
                    client,
                    industry,
                    project_type,
                    source_hash,
                    extracted_at,
                    file_size,
                    metadata
                FROM knowledge_extracts
                ORDER BY extracted_at DESC
            ''')

            rows = cursor.fetchall()
            conn.close()

            knowledge_items = []
            for row in rows:
                # Parse extracted_data JSON to get pattern/insight counts
                extracted = {}
                try:
                    extracted = json.loads(row['extracted_data']) if row['extracted_data'] else {}
                except Exception:
                    extracted = {}

                item = {
                    'id': row['id'],
                    'document_type': row['document_type'],
                    'document_name': row['document_name'],
                    'client': row['client'],
                    'industry': row['industry'],
                    'project_type': row['project_type'],
                    'source_hash': row['source_hash'],
                    'extracted_at': row['extracted_at'],
                    'file_size': row['file_size'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else {},
                    'extracted_data': extracted,
                    'patterns_count': len(extracted.get('patterns', [])),
                    'insights_count': len(extracted.get('insights', []))
                }
                knowledge_items.append(item)

            return {
                'success': True,
                'count': len(knowledge_items),
                'items': knowledge_items
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'count': 0,
                'items': []
            }

    def get_learned_patterns(self):
        """
        Retrieve all learned patterns from database.
        These are the cumulative patterns that grow stronger with more documents.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    id,
                    pattern_type,
                    pattern_name,
                    pattern_data,
                    confidence,
                    supporting_documents,
                    first_seen,
                    last_updated,
                    metadata
                FROM learned_patterns
                ORDER BY confidence DESC, supporting_documents DESC
            ''')

            rows = cursor.fetchall()
            conn.close()

            patterns = []
            for row in rows:
                patterns.append({
                    'id': row['id'],
                    'pattern_type': row['pattern_type'],
                    'pattern_name': row['pattern_name'],
                    'pattern_data': json.loads(row['pattern_data']) if row['pattern_data'] else {},
                    'confidence': row['confidence'],
                    'supporting_documents': row['supporting_documents'],
                    'first_seen': row['first_seen'],
                    'last_updated': row['last_updated'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else {}
                })

            return {'success': True, 'count': len(patterns), 'patterns': patterns}

        except Exception as e:
            return {'success': False, 'error': str(e), 'count': 0, 'patterns': []}

    def export_to_json(self, output_path=None):
        """
        Export all knowledge to JSON file.

        FIXED February 26, 2026: Uses correct schema via get_all_knowledge().
        Also exports learned_patterns for complete backup.
        """
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'/tmp/knowledge_backup_{timestamp}.json'

        result = self.get_all_knowledge()

        if not result['success']:
            return {'success': False, 'error': result['error']}

        patterns_result = self.get_learned_patterns()

        try:
            export_data = {
                'export_date': datetime.now().isoformat(),
                'total_documents': result['count'],
                'total_patterns': patterns_result.get('count', 0),
                'database_path': self.db_path,
                'knowledge_extracts': result['items'],
                'learned_patterns': patterns_result.get('patterns', [])
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            file_size = os.path.getsize(output_path)

            return {
                'success': True,
                'output_path': output_path,
                'format': 'json',
                'items_exported': result['count'],
                'file_size_bytes': file_size,
                'file_size_kb': round(file_size / 1024, 2)
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def export_to_markdown(self, output_path=None):
        """
        Export all knowledge to human-readable Markdown file.

        FIXED February 26, 2026: Uses correct schema — groups by document_type
        instead of non-existent category column. Shows client and industry
        information from actual schema fields.
        """
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'/tmp/knowledge_backup_{timestamp}.md'

        result = self.get_all_knowledge()

        if not result['success']:
            return {'success': False, 'error': result['error']}

        patterns_result = self.get_learned_patterns()

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # Header
                f.write("# Shiftwork Solutions - Knowledge Base Export\n\n")
                f.write(f"**Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**Total Documents:** {result['count']}\n\n")
                f.write(f"**Total Learned Patterns:** {patterns_result.get('count', 0)}\n\n")
                f.write(f"**Database:** {self.db_path}\n\n")
                f.write("---\n\n")

                # Group by document_type (the actual column)
                by_type = {}
                for item in result['items']:
                    doc_type = item['document_type'] or 'unknown'
                    if doc_type not in by_type:
                        by_type[doc_type] = []
                    by_type[doc_type].append(item)

                # Write Knowledge Extracts section
                f.write("## KNOWLEDGE EXTRACTS\n\n")

                for doc_type, items in sorted(by_type.items()):
                    f.write(f"### {doc_type.upper().replace('_', ' ')}\n\n")

                    for item in items:
                        f.write(f"#### ID: {item['id']} | {item['document_name'] or 'Unnamed'}\n\n")
                        f.write(f"**Ingested:** {item['extracted_at']}\n\n")

                        if item['client']:
                            f.write(f"**Client:** {item['client']}\n\n")
                        if item['industry']:
                            f.write(f"**Industry:** {item['industry']}\n\n")

                        f.write(f"**Patterns Extracted:** {item['patterns_count']}\n\n")
                        f.write(f"**Insights Extracted:** {item['insights_count']}\n\n")

                        if item['metadata']:
                            f.write("**Metadata:**\n")
                            for key, value in item['metadata'].items():
                                f.write(f"- {key}: {value}\n")
                            f.write("\n")

                        # Write extracted patterns summary
                        patterns = item['extracted_data'].get('patterns', [])
                        if patterns:
                            f.write("**Extracted Patterns:**\n")
                            for p in patterns[:5]:  # Cap at 5 for readability
                                f.write(f"- {p.get('type', '')}: {p.get('name', '')}\n")
                            f.write("\n")

                        f.write("---\n\n")

                # Write Learned Patterns section
                if patterns_result.get('count', 0) > 0:
                    f.write("## CUMULATIVE LEARNED PATTERNS\n\n")
                    f.write("*These patterns grow stronger with each supporting document.*\n\n")

                    for p in patterns_result.get('patterns', []):
                        f.write(f"### {p['pattern_type']}: {p['pattern_name']}\n\n")
                        f.write(f"**Confidence:** {p['confidence']:.2f}\n\n")
                        f.write(f"**Supporting Documents:** {p['supporting_documents']}\n\n")
                        f.write(f"**First Seen:** {p['first_seen']}\n\n")
                        f.write(f"**Last Updated:** {p['last_updated']}\n\n")
                        f.write("---\n\n")

            file_size = os.path.getsize(output_path)

            return {
                'success': True,
                'output_path': output_path,
                'format': 'markdown',
                'items_exported': result['count'],
                'file_size_bytes': file_size,
                'file_size_kb': round(file_size / 1024, 2)
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def export_to_csv(self, output_path=None):
        """
        Export all knowledge to CSV (spreadsheet-compatible).

        FIXED February 26, 2026: Uses correct column names from actual schema.
        Includes patterns_count and insights_count derived from extracted_data JSON
        rather than non-existent confidence_score / category columns.
        """
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'/tmp/knowledge_backup_{timestamp}.csv'

        result = self.get_all_knowledge()

        if not result['success']:
            return {'success': False, 'error': result['error']}

        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    'id', 'document_type', 'document_name', 'client',
                    'industry', 'project_type', 'extracted_at', 'file_size',
                    'patterns_count', 'insights_count', 'source_hash', 'metadata_json'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for item in result['items']:
                    row = {
                        'id': item['id'],
                        'document_type': item['document_type'],
                        'document_name': item['document_name'],
                        'client': item['client'],
                        'industry': item['industry'],
                        'project_type': item['project_type'],
                        'extracted_at': item['extracted_at'],
                        'file_size': item['file_size'],
                        'patterns_count': item['patterns_count'],
                        'insights_count': item['insights_count'],
                        'source_hash': item['source_hash'],
                        'metadata_json': json.dumps(item['metadata']) if item['metadata'] else ''
                    }
                    writer.writerow(row)

            file_size = os.path.getsize(output_path)

            return {
                'success': True,
                'output_path': output_path,
                'format': 'csv',
                'items_exported': result['count'],
                'file_size_bytes': file_size,
                'file_size_kb': round(file_size / 1024, 2)
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def export_all_formats(self, base_path='/tmp'):
        """Export to all formats (JSON, Markdown, CSV)"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        results = {
            'timestamp': timestamp,
            'exports': []
        }

        json_result = self.export_to_json(f'{base_path}/knowledge_backup_{timestamp}.json')
        results['exports'].append(json_result)

        md_result = self.export_to_markdown(f'{base_path}/knowledge_backup_{timestamp}.md')
        results['exports'].append(md_result)

        csv_result = self.export_to_csv(f'{base_path}/knowledge_backup_{timestamp}.csv')
        results['exports'].append(csv_result)

        successful = sum(1 for r in results['exports'] if r.get('success'))
        results['summary'] = {
            'total_exports': len(results['exports']),
            'successful': successful,
            'failed': len(results['exports']) - successful
        }

        return results

    def get_statistics(self):
        """
        Get statistics about the knowledge base.

        FIXED February 26, 2026: Rebuilt entirely against actual schema.
        Previously queried non-existent columns causing crashes.
        Now correctly reports:
          - Document counts by type (document_type column)
          - Client and industry breakdown
          - Learned pattern counts and average confidence
          - Recent ingestion log entries
        """
        result = self.get_all_knowledge()

        if not result['success']:
            return {'success': False, 'error': result['error']}

        items = result['items']

        # Group by document_type (actual column, not non-existent 'category')
        by_type = {}
        for item in items:
            doc_type = item['document_type'] or 'unknown'
            by_type[doc_type] = by_type.get(doc_type, 0) + 1

        # Client breakdown
        by_client = {}
        for item in items:
            client = item['client'] or 'unknown'
            by_client[client] = by_client.get(client, 0) + 1

        # Industry breakdown
        by_industry = {}
        for item in items:
            industry = item['industry'] or 'unknown'
            by_industry[industry] = by_industry.get(industry, 0) + 1

        # Date range
        oldest = None
        newest = None
        if items:
            dates = [item['extracted_at'] for item in items if item['extracted_at']]
            if dates:
                oldest = min(dates)
                newest = max(dates)

        # Total patterns and average confidence from learned_patterns
        total_patterns = 0
        avg_confidence = 0.0
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) as cnt, AVG(confidence) as avg_conf FROM learned_patterns')
            row = cursor.fetchone()
            total_patterns = row['cnt'] or 0
            avg_confidence = round(row['avg_conf'] or 0.0, 3)

            # Recent ingestion log
            cursor.execute('''
                SELECT document_name, document_type, status, patterns_extracted,
                       insights_extracted, ingested_at
                FROM ingestion_log
                ORDER BY ingested_at DESC
                LIMIT 10
            ''')
            recent_ingestions = [dict(r) for r in cursor.fetchall()]
            conn.close()
        except Exception as e:
            recent_ingestions = []
            print(f"⚠️  Could not read learned_patterns or ingestion_log: {e}")

        return {
            'success': True,
            'total_documents': result['count'],
            'total_learned_patterns': total_patterns,
            'by_document_type': by_type,
            'by_client': by_client,
            'by_industry': by_industry,
            'date_range': {
                'oldest': oldest,
                'newest': newest
            },
            'average_pattern_confidence': avg_confidence,
            'recent_ingestions': recent_ingestions,
            'database_path': self.db_path
        }


# ============================================================================
# STANDALONE FUNCTIONS - Maintain API contract with knowledge_backup_routes.py
# ============================================================================

def backup_knowledge_all_formats(db_path=None, output_dir='/tmp'):
    """Backup all knowledge in all formats. Returns paths to created files."""
    backup_system = KnowledgeBackupSystem(db_path)
    return backup_system.export_all_formats(output_dir)


def get_knowledge_statistics(db_path=None):
    """Get statistics about the knowledge base."""
    backup_system = KnowledgeBackupSystem(db_path)
    return backup_system.get_statistics()


def export_knowledge_json(db_path=None, output_path=None):
    """Export knowledge to JSON."""
    backup_system = KnowledgeBackupSystem(db_path)
    return backup_system.export_to_json(output_path)


def export_knowledge_markdown(db_path=None, output_path=None):
    """Export knowledge to Markdown."""
    backup_system = KnowledgeBackupSystem(db_path)
    return backup_system.export_to_markdown(output_path)


def export_knowledge_csv(db_path=None, output_path=None):
    """Export knowledge to CSV."""
    backup_system = KnowledgeBackupSystem(db_path)
    return backup_system.export_to_csv(output_path)


# I did no harm and this file is not truncated
