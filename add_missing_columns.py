"""
ADD MISSING COLUMNS - Schema Migration
Created: March 03, 2026
Last Updated: March 03, 2026

PURPOSE:
    Adds columns to existing PostgreSQL tables that were added to the
    CREATE TABLE definitions over time but never applied to the already-
    existing tables on Render (because CREATE TABLE IF NOT EXISTS skips
    re-creation and does not add new columns).

    All ALTER TABLE statements use IF NOT EXISTS (PostgreSQL 9.6+) so
    this migration is fully idempotent — safe to run on every startup
    with no side effects after the first run.

    Existing data is never modified.

TABLES AND COLUMNS ADDED:
    case_studies:
        - problem_summary TEXT   (was missing, caused UndefinedColumn error)
        - solution_summary TEXT  (was missing, caused UndefinedColumn error)

    blog_posts:
        - topic_display    TEXT    (was missing, caused UndefinedColumn error)
        - url_slug         TEXT    (was missing, caused UndefinedColumn error)
        - meta_description TEXT    (was missing, caused UndefinedColumn error)
        - word_count       INTEGER (added proactively — referenced in generator)
        - seo_title        TEXT    (added proactively — referenced in generator)
        - author_name      TEXT    (added proactively — referenced in generator)
        - tags             TEXT    (added proactively — referenced in generator)

    projects:
        - project_id TEXT  (was missing, caused "column project_id does not exist" error)

ERRORS FIXED:
    psycopg2.errors.UndefinedColumn: column "problem_summary" does not exist
    psycopg2.errors.UndefinedColumn: column "topic_display" does not exist
    Error listing projects: column "project_id" does not exist

HOW TO WIRE INTO app.py (STEP 3 legacy migrations section):
    try:
        from add_missing_columns import add_missing_columns
        add_missing_columns()
    except Exception as e:
        print(f"Missing columns migration: {e}")

CHANGELOG:
    March 03, 2026 - Created. Fixes three schema mismatch errors from
                     deployment logs after PostgreSQL pool fix.

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
        # case_studies
        ('case_studies', 'problem_summary',
         'ALTER TABLE case_studies ADD COLUMN IF NOT EXISTS problem_summary TEXT'),
        ('case_studies', 'solution_summary',
         'ALTER TABLE case_studies ADD COLUMN IF NOT EXISTS solution_summary TEXT'),

        # blog_posts
        ('blog_posts', 'topic_display',
         'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS topic_display TEXT'),
        ('blog_posts', 'url_slug',
         'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS url_slug TEXT'),
        ('blog_posts', 'meta_description',
         'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS meta_description TEXT'),
        ('blog_posts', 'word_count',
         'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS word_count INTEGER DEFAULT 0'),
        ('blog_posts', 'seo_title',
         'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS seo_title TEXT'),
        ('blog_posts', 'author_name',
         "ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS author_name TEXT DEFAULT 'Shiftwork Solutions LLC'"),
        ('blog_posts', 'tags',
         'ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS tags TEXT'),

        # projects
        ('projects', 'project_id',
         'ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_id TEXT'),
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
        ('case_studies', 'problem_summary',
         'ALTER TABLE case_studies ADD COLUMN problem_summary TEXT'),
        ('case_studies', 'solution_summary',
         'ALTER TABLE case_studies ADD COLUMN solution_summary TEXT'),
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
        ('projects', 'project_id',
         'ALTER TABLE projects ADD COLUMN project_id TEXT'),
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
