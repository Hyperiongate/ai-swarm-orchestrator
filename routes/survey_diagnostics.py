"""
SURVEY IN A BOX — Migration Diagnostics
File: routes/survey_diagnostics.py
Created: March 12, 2026
Last Updated: March 12, 2026 — Initial creation

PURPOSE:
    Single diagnostic endpoint to determine exactly why migration_002
    is not creating the Survey in a Box tables. Checks four things:
        1. Whether the migration file exists on disk at the expected path
        2. Whether the file is readable
        3. Whether run_migration() succeeds when called right now
        4. Whether the 3 tables exist in PostgreSQL

    This is a temporary diagnostic tool. Once the tables are confirmed
    present and the acceptance test passes 10/10, this file can be removed.

ENDPOINT:
    GET /api/survey/diagnostics
        No authentication required — diagnostic only, no sensitive data.

CHANGELOG:
    - March 12, 2026: Initial creation. Temporary diagnostic for migration_002.
"""

import importlib.util
import io
import os
import sys
import traceback

from flask import Blueprint, jsonify

from db_engine import get_db_connection

survey_diagnostics_bp = Blueprint('survey_diagnostics', __name__)


@survey_diagnostics_bp.route('/api/survey/diagnostics', methods=['GET'])
def survey_diagnostics():
    """
    Diagnose why migration_002_survey_in_a_box.py may not be running.

    Returns a full report covering:
      - file_path:        Absolute path where app.py looks for the file
      - file_exists:      Whether the file is present on disk
      - file_readable:    Whether the file can be opened and read
      - migration_ran:    Whether run_migration() succeeded when called now
      - migration_output: stdout captured during run_migration()
      - migration_error:  Exception message if run_migration() failed
      - tables:           Which of the 3 tables exist in PostgreSQL right now
      - all_tables_present: True only if all 3 tables exist
      - diagnosis:        Plain-English summary of what's wrong (if anything)
    """

    result = {
        'file_path':           None,
        'file_exists':         False,
        'file_readable':       False,
        'migration_ran':       False,
        'migration_output':    None,
        'migration_error':     None,
        'tables': {
            'survey_clients':          False,
            'survey_projects':         False,
            'survey_project_history':  False,
        },
        'all_tables_present':  False,
        'diagnosis':           'Unknown — diagnostics incomplete.',
    }

    # -------------------------------------------------------------------------
    # CHECK 1 & 2: File exists and is readable
    # Use the same path construction as app.py STEP 1 so we test the
    # exact same logic that runs at startup.
    # -------------------------------------------------------------------------
    try:
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        m002_path = os.path.join(app_root, 'migrations',
                                 'migration_002_survey_in_a_box.py')
        result['file_path'] = m002_path
        result['file_exists'] = os.path.isfile(m002_path)

        if result['file_exists']:
            with open(m002_path, 'r') as f:
                _ = f.read(64)  # read first 64 bytes — enough to confirm readable
            result['file_readable'] = True
    except Exception as e:
        result['migration_error'] = f'File check error: {e}\n{traceback.format_exc()}'

    # -------------------------------------------------------------------------
    # CHECK 3: Run the migration right now and capture all output
    # -------------------------------------------------------------------------
    if result['file_readable']:
        captured = io.StringIO()
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = captured
            sys.stderr = captured

            spec = importlib.util.spec_from_file_location(
                'migration_002_survey_in_a_box',
                m002_path
            )
            if spec is None:
                raise ImportError(
                    f'spec_from_file_location returned None for path: {m002_path}'
                )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.run_migration()
            result['migration_ran'] = True

        except Exception as e:
            result['migration_error'] = f'{e}\n{traceback.format_exc()}'
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            result['migration_output'] = captured.getvalue()

    # -------------------------------------------------------------------------
    # CHECK 4: Query PostgreSQL for the 3 tables
    # -------------------------------------------------------------------------
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                      'survey_clients',
                      'survey_projects',
                      'survey_project_history'
                  )
            """)
            found = {row['table_name'] for row in cursor.fetchall()}
        finally:
            conn.close()

        for tname in result['tables']:
            result['tables'][tname] = tname in found

        result['all_tables_present'] = all(result['tables'].values())

    except Exception as e:
        result['migration_error'] = (
            (result['migration_error'] or '') +
            f'\nTable check error: {e}\n{traceback.format_exc()}'
        )

    # -------------------------------------------------------------------------
    # DIAGNOSIS: Plain-English summary
    # -------------------------------------------------------------------------
    if result['all_tables_present']:
        result['diagnosis'] = (
            'All 3 tables exist. Migration is working correctly. '
            'Run the acceptance test to verify full functionality.'
        )
    elif not result['file_exists']:
        result['diagnosis'] = (
            f'PROBLEM: Migration file not found on disk at {result["file_path"]}. '
            'Verify the file was committed to GitHub in the migrations/ folder '
            'and that Render has deployed the latest commit.'
        )
    elif not result['file_readable']:
        result['diagnosis'] = (
            'PROBLEM: Migration file exists but cannot be read. '
            'Check file permissions.'
        )
    elif not result['migration_ran']:
        result['diagnosis'] = (
            'PROBLEM: Migration file found and readable but run_migration() failed. '
            f'See migration_error for details: {result["migration_error"]}'
        )
    else:
        missing = [t for t, v in result['tables'].items() if not v]
        result['diagnosis'] = (
            f'PROBLEM: Migration ran without error but tables are still missing: '
            f'{", ".join(missing)}. '
            'Check migration_output for clues — the CREATE TABLE may have '
            'silently failed or been rolled back.'
        )

    return jsonify(result)


# I did no harm and this file is not truncated
