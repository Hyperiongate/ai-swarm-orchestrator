"""
Database File Management Extension
Created: January 28, 2026
Last Updated: January 29, 2026 - Added missing functions for AI file access

CHANGELOG January 29, 2026:
- Added get_files_for_ai_context() - Extract file content for AI prompts
- Added mark_file_as_analyzed() - Track when AI has analyzed a file
- Added search_project_files() - Search files by name/description
- Added update_file_metadata() - Update file metadata

Adds project_files table and related functions for project-based file management.
This allows users to upload files to projects and have the AI access them.

INTEGRATION:
Run this once to add the table: python database_file_management.py
Then the functions are available to import in routes/core.py

Author: Jim @ Shiftwork Solutions LLC
"""

import sqlite3
import os
from datetime import datetime
from config import DATABASE


def add_project_files_table():
    """Add the project_files table to track uploaded and generated files by project"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    # Create project_files table
    db.execute('''
        CREATE TABLE IF NOT EXISTS project_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            file_path TEXT NOT NULL,
            storage_type TEXT DEFAULT 'local',
            uploaded_by TEXT DEFAULT 'user',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_generated BOOLEAN DEFAULT 0,
            task_id INTEGER,
            conversation_id TEXT,
            category TEXT DEFAULT 'general',
            description TEXT,
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at TIMESTAMP,
            metadata TEXT,
            is_analyzed BOOLEAN DEFAULT 0,
            analysis_summary TEXT,
            analyzed_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        )
    ''')
    
    # Create indexes for performance
    db.execute('CREATE INDEX IF NOT EXISTS idx_project_files_project ON project_files(project_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_project_files_uploaded ON project_files(uploaded_at DESC)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_project_files_type ON project_files(file_type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_project_files_deleted ON project_files(is_deleted)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_project_files_task ON project_files(task_id)')
    
    db.commit()
    db.close()
    
    print("✅ project_files table created successfully!")


# ============================================================================
# PROJECT FILE MANAGEMENT FUNCTIONS
# ============================================================================

def save_project_file(project_id, filename, original_filename, file_type, file_path, 
                     file_size=0, uploaded_by='user', is_generated=False, task_id=None,
                     conversation_id=None, category='general', description=None, metadata=None):
    """Save a file record to the database"""
    import json
    
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    cursor = db.execute('''
        INSERT INTO project_files 
        (project_id, filename, original_filename, file_type, file_size, file_path,
         uploaded_by, is_generated, task_id, conversation_id, category, description, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id, filename, original_filename, file_type, file_size, file_path,
        uploaded_by, is_generated, task_id, conversation_id, category, description,
        json.dumps(metadata) if metadata else None
    ))
    
    file_id = cursor.lastrowid
    db.commit()
    db.close()
    
    print(f"📄 File saved to database: {filename} (ID: {file_id})")
    return file_id


def get_project_files(project_id, include_deleted=False, file_type=None):
    """Get all files for a specific project"""
    import json
    
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    query = 'SELECT * FROM project_files WHERE project_id = ?'
    params = [project_id]
    
    if not include_deleted:
        query += ' AND is_deleted = 0'
    
    if file_type:
        query += ' AND file_type = ?'
        params.append(file_type)
    
    query += ' ORDER BY uploaded_at DESC'
    
    rows = db.execute(query, params).fetchall()
    db.close()
    
    files = []
    for row in rows:
        file_dict = dict(row)
        if file_dict.get('metadata'):
            try:
                file_dict['metadata'] = json.loads(file_dict['metadata'])
            except:
                pass
        files.append(file_dict)
    
    return files


def get_all_projects_with_files():
    """Get all projects that have files"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    projects = db.execute('''
        SELECT p.project_id, p.client_name, p.industry, p.project_phase, 
               COUNT(pf.id) as file_count
        FROM projects p
        LEFT JOIN project_files pf ON p.project_id = pf.project_id AND pf.is_deleted = 0
        WHERE p.status = 'active'
        GROUP BY p.project_id
        ORDER BY p.updated_at DESC
    ''').fetchall()
    
    db.close()
    
    return [dict(row) for row in projects]


def get_project_file_by_id(file_id):
    """Get a specific file by ID"""
    import json
    
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    row = db.execute('SELECT * FROM project_files WHERE id = ?', (file_id,)).fetchone()
    db.close()
    
    if row:
        file_dict = dict(row)
        if file_dict.get('metadata'):
            try:
                file_dict['metadata'] = json.loads(file_dict['metadata'])
            except:
                pass
        return file_dict
    return None


def get_project_file_by_name(project_id, filename):
    """Get a file by project_id and filename (for AI to find files)"""
    import json
    
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    # Try exact match first
    row = db.execute('''
        SELECT * FROM project_files 
        WHERE project_id = ? AND (filename = ? OR original_filename = ?) 
        AND is_deleted = 0
        ORDER BY uploaded_at DESC
        LIMIT 1
    ''', (project_id, filename, filename)).fetchone()
    
    # If no exact match, try fuzzy match
    if not row:
        row = db.execute('''
            SELECT * FROM project_files 
            WHERE project_id = ? 
            AND (filename LIKE ? OR original_filename LIKE ?)
            AND is_deleted = 0
            ORDER BY uploaded_at DESC
            LIMIT 1
        ''', (project_id, f'%{filename}%', f'%{filename}%')).fetchone()
    
    db.close()
    
    if row:
        file_dict = dict(row)
        if file_dict.get('metadata'):
            try:
                file_dict['metadata'] = json.loads(file_dict['metadata'])
            except:
                pass
        return file_dict
    return None


def delete_project_file(file_id, hard_delete=False):
    """Delete a project file"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    if hard_delete:
        # Get file path first
        row = db.execute('SELECT file_path FROM project_files WHERE id = ?', (file_id,)).fetchone()
        if row and row['file_path'] and os.path.exists(row['file_path']):
            try:
                os.remove(row['file_path'])
            except Exception as e:
                print(f"⚠️ Could not delete file: {e}")
        
        db.execute('DELETE FROM project_files WHERE id = ?', (file_id,))
    else:
        # Soft delete
        db.execute('''
            UPDATE project_files 
            SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (file_id,))
    
    db.commit()
    db.close()
    return True


def get_file_stats_by_project(project_id):
    """Get file statistics for a project"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    stats = {}
    
    # Total files
    stats['total_files'] = db.execute(
        'SELECT COUNT(*) FROM project_files WHERE project_id = ? AND is_deleted = 0',
        (project_id,)
    ).fetchone()[0]
    
    # By type
    type_counts = db.execute('''
        SELECT file_type, COUNT(*) as count 
        FROM project_files 
        WHERE project_id = ? AND is_deleted = 0
        GROUP BY file_type
    ''', (project_id,)).fetchall()
    stats['by_type'] = {row['file_type']: row['count'] for row in type_counts}
    
    # Total size
    stats['total_size_bytes'] = db.execute(
        'SELECT SUM(file_size) FROM project_files WHERE project_id = ? AND is_deleted = 0',
        (project_id,)
    ).fetchone()[0] or 0
    
    # Generated vs uploaded
    stats['uploaded_count'] = db.execute(
        'SELECT COUNT(*) FROM project_files WHERE project_id = ? AND is_deleted = 0 AND is_generated = 0',
        (project_id,)
    ).fetchone()[0]
    
    stats['generated_count'] = db.execute(
        'SELECT COUNT(*) FROM project_files WHERE project_id = ? AND is_deleted = 0 AND is_generated = 1',
        (project_id,)
    ).fetchone()[0]
    
    db.close()
    return stats


# ============================================================================
# NEW FUNCTIONS - Added January 29, 2026
# ============================================================================

def get_files_for_ai_context(project_id, max_files=5, max_chars_per_file=2000):
    """
    NEW FUNCTION - Extract file content to provide as context to AI.
    
    This function is called when the AI needs to know what files exist in a project
    and get relevant content from them to inform its responses.
    
    Args:
        project_id: The project to get files from
        max_files: Maximum number of files to include (default 5)
        max_chars_per_file: Maximum characters to extract per file (default 2000)
        
    Returns:
        str: Formatted context string with file information
    """
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    # Get recent files from this project
    files = db.execute('''
        SELECT id, filename, original_filename, file_type, file_path, 
               description, uploaded_at, is_analyzed, analysis_summary
        FROM project_files
        WHERE project_id = ? AND is_deleted = 0
        ORDER BY uploaded_at DESC
        LIMIT ?
    ''', (project_id, max_files)).fetchall()
    
    db.close()
    
    if not files:
        return ""
    
    context = "\n\n=== PROJECT FILES CONTEXT ===\n"
    context += f"This project has {len(files)} file(s) available:\n\n"
    
    for file in files:
        context += f"📄 {file['original_filename']} ({file['file_type']})\n"
        
        # Add description if available
        if file['description']:
            context += f"   Description: {file['description']}\n"
        
        # Add analysis summary if available
        if file['is_analyzed'] and file['analysis_summary']:
            context += f"   Summary: {file['analysis_summary']}\n"
        
        # Try to extract content from file
        try:
            file_content = _extract_file_preview(file['file_path'], file['file_type'], max_chars_per_file)
            if file_content:
                context += f"   Preview: {file_content[:max_chars_per_file]}...\n"
        except Exception as e:
            context += f"   (Content extraction failed: {str(e)})\n"
        
        context += "\n"
    
    context += "=== END PROJECT FILES CONTEXT ===\n\n"
    
    return context


def _extract_file_preview(file_path, file_type, max_chars):
    """
    Helper function to extract a preview of file content.
    Used by get_files_for_ai_context.
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        # Text files
        if file_type in ['txt', 'md', 'csv']:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(max_chars)
                return content
        
        # Word documents
        elif file_type in ['docx', 'doc']:
            try:
                from docx import Document
                doc = Document(file_path)
                text = '\n'.join([p.text for p in doc.paragraphs[:10]])  # First 10 paragraphs
                return text[:max_chars]
            except:
                return None
        
        # PDFs
        elif file_type == 'pdf':
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ''
                    for page_num in range(min(3, len(reader.pages))):  # First 3 pages
                        text += reader.pages[page_num].extract_text()
                    return text[:max_chars]
            except:
                return None
        
        # Excel files
        elif file_type in ['xlsx', 'xls']:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                sheet = wb.active
                text = f"Sheet: {sheet.title}\n"
                for row in list(sheet.iter_rows(values_only=True))[:20]:  # First 20 rows
                    text += ' | '.join([str(cell) if cell else '' for cell in row]) + '\n'
                return text[:max_chars]
            except:
                return None
        
        else:
            return None
            
    except Exception as e:
        print(f"Error extracting preview from {file_path}: {e}")
        return None


def mark_file_as_analyzed(file_id, analysis_summary=None):
    """
    NEW FUNCTION - Mark a file as analyzed by AI.
    
    This tracks when the AI has looked at a file and what it found,
    so we don't repeatedly analyze the same files.
    
    Args:
        file_id: ID of the file that was analyzed
        analysis_summary: Optional short summary of the analysis (max 500 chars)
    """
    db = sqlite3.connect(DATABASE)
    
    if analysis_summary and len(analysis_summary) > 500:
        analysis_summary = analysis_summary[:497] + "..."
    
    db.execute('''
        UPDATE project_files
        SET is_analyzed = 1,
            analysis_summary = ?,
            analyzed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (analysis_summary, file_id))
    
    db.commit()
    db.close()
    
    print(f"✅ File {file_id} marked as analyzed")


def search_project_files(project_id, search_term):
    """
    NEW FUNCTION - Search for files by name or description.
    
    This allows the AI (or users) to find files based on keywords.
    
    Args:
        project_id: The project to search in
        search_term: The term to search for
        
    Returns:
        list: Matching files
    """
    import json
    
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    
    search_pattern = f'%{search_term}%'
    
    rows = db.execute('''
        SELECT * FROM project_files
        WHERE project_id = ?
        AND is_deleted = 0
        AND (
            filename LIKE ? OR
            original_filename LIKE ? OR
            description LIKE ? OR
            analysis_summary LIKE ?
        )
        ORDER BY uploaded_at DESC
    ''', (project_id, search_pattern, search_pattern, search_pattern, search_pattern)).fetchall()
    
    db.close()
    
    files = []
    for row in rows:
        file_dict = dict(row)
        if file_dict.get('metadata'):
            try:
                file_dict['metadata'] = json.loads(file_dict['metadata'])
            except:
                pass
        files.append(file_dict)
    
    return files


def update_file_metadata(file_id, **kwargs):
    """
    NEW FUNCTION - Update file metadata.
    
    This allows updating file properties like description, category, etc.
    
    Args:
        file_id: ID of the file to update
        **kwargs: Fields to update (description, category, metadata, etc.)
    """
    import json
    
    db = sqlite3.connect(DATABASE)
    
    # Build update query dynamically based on provided kwargs
    allowed_fields = ['description', 'category', 'metadata']
    updates = []
    values = []
    
    for field, value in kwargs.items():
        if field in allowed_fields:
            if field == 'metadata' and isinstance(value, dict):
                value = json.dumps(value)
            updates.append(f"{field} = ?")
            values.append(value)
    
    if not updates:
        db.close()
        return False
    
    values.append(file_id)
    query = f"UPDATE project_files SET {', '.join(updates)} WHERE id = ?"
    
    db.execute(query, values)
    db.commit()
    db.close()
    
    print(f"✅ File {file_id} metadata updated")
    return True


if __name__ == '__main__':
    print("🔧 Adding project_files table to database...")
    add_project_files_table()
    print("✅ Database migration complete!")
    print("\nYou can now upload files to projects and the AI can access them.")

# I did no harm and this file is not truncated
