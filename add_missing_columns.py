"""
ADD MISSING COLUMNS - Schema Migration
Created: March 03, 2026
Last Updated: March 03, 2026 - PHASE 8 EXPANSION

CHANGELOG:
- March 03, 2026 (Phase 8): EXPANDED projects table migrations
  * Added project_phase, storage_path, checklist_data, milestone_data,
    folder_data, metadata columns to projects table.
  * These columns are all referenced by database_file_management.py
    (ProjectManager class) but were never created in production because
    migrate_projects_table.py hardcodes SQLite fallback and never ran
    against the PostgreSQL database on Render.
  * project_id was already present from Phase 6 deployment (earlier today).
  * All entries are fully idempotent (IF NOT EXISTS for PG, PRAGMA for SQLite).

- March 03, 2026 (Phase 6): INITIAL VERSION
  * Added project_id to projects table.
  * Added problem_summary, solution_summary to case_studies.
  * Added topic_display, url_slug, meta_description, word_count,
    seo_title, author_name, tags to blog_posts.

PURPOSE:
    Adds columns to existing PostgreSQL tables that were added to
    application code over time but never applied to the production DB.
    All ALTER TABLE statements use IF NOT EXISTS so this migration is
    fully idempotent — safe to run on every startup.
    Existing data is NEVER modified.

TABLES AND COLUMNS ADDED:
    case_studies:
        - problem_summary TEXT
        - solution_summary TEXT

    blog_posts:
        - topic_display TEXT
        - url_slug TEXT
        - meta_description TEXT
        - word_count INTEGER
        - seo_title TEXT
        - author_name TEXT
        - tags TEXT

    projects:
        - project_id TEXT      (referenced by ProjectManager + core routes)
        - project_phase TEXT   (DB was created with 'phase' but all app code
                                uses 'project_phase')
        - storage_path TEXT    (referenced by ProjectManager.create_project)
        - checklist_data TEXT  (referenced by ProjectManager.create_project)
        - milestone_data TEXT  (referenced by ProjectManager.create_project)
        - folder_data TEXT     (referenced by ProjectManager.create_project)
        - metadata TEXT        (referenced by ProjectManager.create_project)

ERRORS FIXED:
    Error listing projects: column "project_phase" does not exist
    Error starting project: column "project_phase" of relation "projects" does not exist
    Error in ProjectManager.create_project: column "storage_path" does not exist
    Error in ProjectManager.create_project: column "checklist_data" does not exist

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

from database import get_db
from db_engine import get_db_type


def add_missing_columns():
    """
    Add missing columns to existing tables.
    Uses ALTER TABLE ADD COLUMN IF NOT EXISTS (PostgreSQL) or
    a PRAGMA-based existence check (SQLite).
    Safe to run on every startup — no-op if columns already exist.
    """
    db_type = get_db_type()

    if db_type == 'postgresql':
        _migrate_postgresql()
    else:
        _migrate_sqlite()


def _migrate_postgresql():
    """
    PostgreSQL: ALTER TABLE ... ADD COLUMN IF NOT EXISTS
    Each column gets its own connection+commit so one failure does not
    block the remaining columns from being added.
    """

    migrations = [

        # -------------------------------------------------------------
        # case_studies table
        # -------------------------------------------------------------
        (
            'case_studies', 'problem_summary',
            'ALTER TABLE case_studies ADD COLUMN IF NOT EXISTS problem_summary TEXT'
        ),
        (
            'case_studies', 'solution_summary',
            'ALTER TABLE case_studies ADD COLUMN IF NOT EXISTS solution_summary TEXT'
        ),

        # -------------------------------------------------------------
        # blog_posts table
        # -------------------------------------------------------------
        (
            'blog_posts', 'topic_display',
            'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS topic_display TEXT'
        ),
        (
            'blog_posts', 'url_slug',
            'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS url_slug TEXT'
        ),
        (
            'blog_posts', 'meta_description',
            'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS meta_description TEXT'
        ),
        (
            'blog_posts', 'word_count',
            'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS word_count INTEGER DEFAULT 0'
        ),
        (
            'blog_posts', 'seo_title',
            'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS seo_title TEXT'
        ),
        (
            'blog_posts', 'author_name',
            "ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS author_name TEXT DEFAULT 'Shiftwork Solutions LLC'"
        ),
        (
            'blog_posts', 'tags',
            'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS tags TEXT'
        ),

        # -------------------------------------------------------------
        # projects table — all columns referenced by application code
        # that were missing from the original CREATE TABLE statement.
        #
        # NOTE: project_id may already exist from a previous deployment.
        # All entries are idempotent (IF NOT EXISTS).
        # -------------------------------------------------------------
        (
            'projects', 'project_id',
            'ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_id TEXT'
        ),
        (
            'projects', 'project_phase',
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_phase TEXT DEFAULT 'discovery'"
        ),
        (
            'projects', 'storage_path',
            'ALTER TABLE projects ADD COLUMN IF NOT EXISTS storage_path TEXT'
        ),
        (
            'projects', 'checklist_data',
            'ALTER TABLE projects ADD COLUMN IF NOT EXISTS checklist_data TEXT'
        ),
        (
            'projects', 'milestone_data',
            'ALTER TABLE projects ADD COLUMN IF NOT EXISTS milestone_data TEXT'
        ),
        (
            'projects', 'folder_data',
            'ALTER TABLE projects ADD COLUMN IF NOT EXISTS folder_data TEXT'
        ),
        (
            'projects', 'metadata',
            'ALTER TABLE projects ADD COLUMN IF NOT EXISTS metadata TEXT'
        ),
    ]

    added = []
    skipped = []
    failed = []

    for table, column, sql in migrations:
        db = get_db()
        try:
            db.execute(sql)
            db.commit()
            added.append(f'{table}.{column}')
        except Exception as e:
            err_lower = str(e).lower()
            if 'already exists' in err_lower or 'duplicate column' in err_lower:
                skipped.append(f'{table}.{column}')
            else:
                failed.append(f'{table}.{column}: {e}')
                try:
                    db.rollback()
                except Exception:
                    pass
        finally:
            db.close()

    if added:
        print(f'  ✅ add_missing_columns: Added {len(added)} columns: {", ".join(added)}')
    if skipped:
        print(f'  ℹ️  add_missing_columns: Already present (skipped): {", ".join(skipped)}')
    if failed:
        print(f'  ⚠️  add_missing_columns: Failed to add: {", ".join(failed)}')
    if not added and not skipped and not failed:
        print('  ℹ️  add_missing_columns: Nothing to do')


def _migrate_sqlite():
    """
    SQLite does not support ADD COLUMN IF NOT EXISTS.
    Use PRAGMA table_info() to check column existence before each ALTER.
    """

    migrations = [
        # case_studies
        ('case_studies', 'problem_summary',
         'ALTER TABLE case_studies ADD COLUMN problem_summary TEXT'),
        ('case_studies', 'solution_summary',
         'ALTER TABLE case_studies ADD COLUMN solution_summary TEXT'),

        # blog_posts
        ('blog_posts', 'topic_display',
         'ALTER TABLE blog_posts ADD COLUMN topic_display TEXT'),
        ('blog_posts', 'url_slug',
         'ALTER TABLE blog_posts ADD COLUMN url_slug TEXT'),
        ('blog_posts', 'meta_description',
         'ALTER TABLE blog_posts ADD COLUMN meta_description TEXT'),
        ('blog_posts', 'word_count',
         'ALTER TABLE blog_posts ADD COLUMN word_count INTEGER DEFAULT 0'),
        ('blog_posts', 'seo_title',
         'ALTER TABLE blog_posts ADD COLUMN seo_title TEXT'),
        ('blog_posts', 'author_name',
         "ALTER TABLE blog_posts ADD COLUMN author_name TEXT DEFAULT 'Shiftwork Solutions LLC'"),
        ('blog_posts', 'tags',
         'ALTER TABLE blog_posts ADD COLUMN tags TEXT'),

        # projects — all columns referenced by application code
        ('projects', 'project_id',
         'ALTER TABLE projects ADD COLUMN project_id TEXT'),
        ('projects', 'project_phase',
         "ALTER TABLE projects ADD COLUMN project_phase TEXT DEFAULT 'discovery'"),
        ('projects', 'storage_path',
         'ALTER TABLE projects ADD COLUMN storage_path TEXT'),
        ('projects', 'checklist_data',
         'ALTER TABLE projects ADD COLUMN checklist_data TEXT'),
        ('projects', 'milestone_data',
         'ALTER TABLE projects ADD COLUMN milestone_data TEXT'),
        ('projects', 'folder_data',
         'ALTER TABLE projects ADD COLUMN folder_data TEXT'),
        ('projects', 'metadata',
         'ALTER TABLE projects ADD COLUMN metadata TEXT'),
    ]

    added = []

    for table, column, sql in migrations:
        db = get_db()
        try:
            rows = db.execute(f'PRAGMA table_info({table})').fetchall()
            existing = [row['name'] for row in rows]
            if column not in existing:
                db.execute(sql)
                db.commit()
                added.append(f'{table}.{column}')
        except Exception as e:
            print(f'  ⚠️  add_missing_columns SQLite [{table}.{column}]: {e}')
        finally:
            db.close()

    if added:
        print(f'  ✅ add_missing_columns (SQLite): Added: {", ".join(added)}')
    else:
        print('  ℹ️  add_missing_columns (SQLite): All columns already present')


if __name__ == '__main__':
    print('Running add_missing_columns migration directly...')
    add_missing_columns()
    print('Done.')

# I did no harm and this file is not truncated
