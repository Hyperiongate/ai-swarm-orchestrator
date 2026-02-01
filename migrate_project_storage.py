"""
PROJECT STORAGE PATH MIGRATION SCRIPT
Created: February 1, 2026

This script migrates existing projects from /tmp storage to persistent storage.
Run this ONCE after deploying the persistent storage fix.

WHAT IT DOES:
1. Finds all projects with /tmp storage paths
2. Updates database to use /mnt/project/swarm_projects
3. Moves any existing files to new location (if they exist)

Author: Jim @ Shiftwork Solutions LLC
"""

import sqlite3
import os
import shutil
from config import DATABASE

def migrate_project_storage():
    """Migrate all projects from /tmp to persistent storage"""
    
    # Connect to database
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    
    # New storage root
    new_storage_root = os.environ.get('STORAGE_ROOT', '/mnt/project/swarm_projects')
    
    print("=" * 80)
    print("🔄 PROJECT STORAGE MIGRATION")
    print("=" * 80)
    print(f"Target storage: {new_storage_root}")
    print()
    
    # Find all projects with /tmp storage
    projects = cursor.execute('''
        SELECT project_id, storage_path 
        FROM projects 
        WHERE storage_path LIKE '/tmp/%'
    ''').fetchall()
    
    if not projects:
        print("✅ No projects need migration - all using persistent storage!")
        db.close()
        return
    
    print(f"Found {len(projects)} project(s) to migrate:")
    print()
    
    migrated = 0
    errors = []
    
    for project in projects:
        project_id = project['project_id']
        old_path = project['storage_path']
        
        # Calculate new path
        new_path = os.path.join(new_storage_root, project_id)
        
        print(f"📦 Migrating {project_id}")
        print(f"   Old: {old_path}")
        print(f"   New: {new_path}")
        
        try:
            # Create new directory
            os.makedirs(new_path, exist_ok=True)
            
            # Move files if old directory exists
            if os.path.exists(old_path):
                files_moved = 0
                for filename in os.listdir(old_path):
                    old_file = os.path.join(old_path, filename)
                    new_file = os.path.join(new_path, filename)
                    shutil.move(old_file, new_file)
                    files_moved += 1
                print(f"   ✅ Moved {files_moved} file(s)")
            else:
                print(f"   ℹ️  No files to move (directory didn't exist)")
            
            # Update database
            cursor.execute('''
                UPDATE projects 
                SET storage_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE project_id = ?
            ''', (new_path, project_id))
            
            # Update file paths in database
            cursor.execute('''
                UPDATE project_files
                SET file_path = REPLACE(file_path, ?, ?)
                WHERE project_id = ?
            ''', (old_path, new_path, project_id))
            
            db.commit()
            migrated += 1
            print(f"   ✅ Migration complete!")
            
        except Exception as e:
            error_msg = f"{project_id}: {str(e)}"
            errors.append(error_msg)
            print(f"   ❌ ERROR: {e}")
        
        print()
    
    db.close()
    
    # Summary
    print("=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully migrated: {migrated}/{len(projects)} projects")
    
    if errors:
        print(f"❌ Errors: {len(errors)}")
        for error in errors:
            print(f"   - {error}")
    else:
        print("🎉 All projects migrated successfully!")
    
    print("=" * 80)


if __name__ == '__main__':
    print("\n🚀 Starting project storage migration...")
    print()
    migrate_project_storage()
    print("\n✅ Migration script complete!")

# I did no harm and this file is not truncated
