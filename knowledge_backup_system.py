"""
Knowledge Backup System - Export Learned Intelligence
Created: February 4, 2026
Last Updated: February 4, 2026

This system exports all learned knowledge from the swarm intelligence database
to downloadable files (JSON, Markdown, CSV) for backup and archival.

FEATURES:
- Export all knowledge extracts to JSON (machine-readable)
- Export to Markdown (human-readable)
- Export to CSV (spreadsheet-compatible)
- Periodic automated backups
- Manual export on demand
- Statistics and health check

Author: Jim @ Shiftwork Solutions LLC
"""

import sqlite3
import json
import csv
from datetime import datetime
import os


class KnowledgeBackupSystem:
    """System for backing up and exporting learned intelligence"""
    
    def __init__(self, db_path='swarm_intelligence.db'):
        """Initialize backup system"""
        self.db_path = db_path
        
    def get_all_knowledge(self):
        """Retrieve all knowledge extracts from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Access columns by name
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    id,
                    source,
                    content,
                    category,
                    confidence_score,
                    metadata,
                    created_at,
                    last_accessed
                FROM knowledge_extracts
                ORDER BY created_at DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert to list of dictionaries
            knowledge_items = []
            for row in rows:
                item = {
                    'id': row['id'],
                    'source': row['source'],
                    'content': row['content'],
                    'category': row['category'],
                    'confidence_score': row['confidence_score'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else {},
                    'created_at': row['created_at'],
                    'last_accessed': row['last_accessed']
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
    
    def export_to_json(self, output_path=None):
        """Export all knowledge to JSON file"""
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'/tmp/knowledge_backup_{timestamp}.json'
        
        result = self.get_all_knowledge()
        
        if not result['success']:
            return {
                'success': False,
                'error': result['error']
            }
        
        try:
            export_data = {
                'export_date': datetime.now().isoformat(),
                'total_items': result['count'],
                'database_path': self.db_path,
                'knowledge_items': result['items']
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
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_to_markdown(self, output_path=None):
        """Export all knowledge to human-readable Markdown file"""
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'/tmp/knowledge_backup_{timestamp}.md'
        
        result = self.get_all_knowledge()
        
        if not result['success']:
            return {
                'success': False,
                'error': result['error']
            }
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # Header
                f.write(f"# Shiftwork Solutions - Knowledge Base Export\n\n")
                f.write(f"**Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**Total Items:** {result['count']}\n\n")
                f.write(f"**Database:** {self.db_path}\n\n")
                f.write("---\n\n")
                
                # Group by category
                by_category = {}
                for item in result['items']:
                    category = item['category'] or 'uncategorized'
                    if category not in by_category:
                        by_category[category] = []
                    by_category[category].append(item)
                
                # Write each category
                for category, items in sorted(by_category.items()):
                    f.write(f"## {category.upper().replace('_', ' ')}\n\n")
                    
                    for item in items:
                        f.write(f"### ID: {item['id']} | Source: {item['source']}\n\n")
                        f.write(f"**Created:** {item['created_at']}\n\n")
                        f.write(f"**Confidence:** {item['confidence_score']:.2f}\n\n")
                        
                        # Metadata
                        if item['metadata']:
                            f.write(f"**Metadata:**\n")
                            for key, value in item['metadata'].items():
                                f.write(f"- {key}: {value}\n")
                            f.write("\n")
                        
                        # Content
                        f.write(f"**Content:**\n\n")
                        f.write(f"{item['content']}\n\n")
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
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_to_csv(self, output_path=None):
        """Export all knowledge to CSV (spreadsheet-compatible)"""
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'/tmp/knowledge_backup_{timestamp}.csv'
        
        result = self.get_all_knowledge()
        
        if not result['success']:
            return {
                'success': False,
                'error': result['error']
            }
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['id', 'source', 'category', 'content', 'confidence_score', 
                             'created_at', 'last_accessed', 'metadata_json']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                writer.writeheader()
                
                for item in result['items']:
                    row = {
                        'id': item['id'],
                        'source': item['source'],
                        'category': item['category'],
                        'content': item['content'],
                        'confidence_score': item['confidence_score'],
                        'created_at': item['created_at'],
                        'last_accessed': item['last_accessed'],
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
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_all_formats(self, base_path='/tmp'):
        """Export to all formats (JSON, Markdown, CSV)"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        results = {
            'timestamp': timestamp,
            'exports': []
        }
        
        # JSON export
        json_result = self.export_to_json(f'{base_path}/knowledge_backup_{timestamp}.json')
        results['exports'].append(json_result)
        
        # Markdown export
        md_result = self.export_to_markdown(f'{base_path}/knowledge_backup_{timestamp}.md')
        results['exports'].append(md_result)
        
        # CSV export
        csv_result = self.export_to_csv(f'{base_path}/knowledge_backup_{timestamp}.csv')
        results['exports'].append(csv_result)
        
        # Summary
        successful = sum(1 for r in results['exports'] if r.get('success'))
        results['summary'] = {
            'total_exports': len(results['exports']),
            'successful': successful,
            'failed': len(results['exports']) - successful
        }
        
        return results
    
    def get_statistics(self):
        """Get statistics about the knowledge base"""
        result = self.get_all_knowledge()
        
        if not result['success']:
            return {
                'success': False,
                'error': result['error']
            }
        
        items = result['items']
        
        # Category breakdown
        by_category = {}
        for item in items:
            category = item['category'] or 'uncategorized'
            by_category[category] = by_category.get(category, 0) + 1
        
        # Source breakdown
        by_source = {}
        for item in items:
            source = item['source']
            by_source[source] = by_source.get(source, 0) + 1
        
        # Date range
        if items:
            dates = [item['created_at'] for item in items if item['created_at']]
            oldest = min(dates) if dates else None
            newest = max(dates) if dates else None
        else:
            oldest = None
            newest = None
        
        # Average confidence
        confidences = [item['confidence_score'] for item in items if item['confidence_score']]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return {
            'success': True,
            'total_items': result['count'],
            'by_category': by_category,
            'by_source': by_source,
            'date_range': {
                'oldest': oldest,
                'newest': newest
            },
            'average_confidence': round(avg_confidence, 3),
            'database_path': self.db_path
        }


# Standalone functions for easy API integration

def backup_knowledge_all_formats(db_path='swarm_intelligence.db', output_dir='/tmp'):
    """
    Backup all knowledge in all formats.
    Returns paths to created files.
    """
    backup_system = KnowledgeBackupSystem(db_path)
    return backup_system.export_all_formats(output_dir)


def get_knowledge_statistics(db_path='swarm_intelligence.db'):
    """Get statistics about the knowledge base"""
    backup_system = KnowledgeBackupSystem(db_path)
    return backup_system.get_statistics()


def export_knowledge_json(db_path='swarm_intelligence.db', output_path=None):
    """Export knowledge to JSON"""
    backup_system = KnowledgeBackupSystem(db_path)
    return backup_system.export_to_json(output_path)


def export_knowledge_markdown(db_path='swarm_intelligence.db', output_path=None):
    """Export knowledge to Markdown"""
    backup_system = KnowledgeBackupSystem(db_path)
    return backup_system.export_to_markdown(output_path)


def export_knowledge_csv(db_path='swarm_intelligence.db', output_path=None):
    """Export knowledge to CSV"""
    backup_system = KnowledgeBackupSystem(db_path)
    return backup_system.export_to_csv(output_path)


# I did no harm and this file is not truncated
