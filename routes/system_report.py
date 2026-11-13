"""
System Report — Flask Routes
File: routes/system_report.py
Created: November 13, 2026
Last Updated: November 13, 2026 — Initial implementation

PURPOSE:
    A read-only picture of where the live Swarm actually keeps its data and
    whether its scheduled background jobs are running. It exists so that
    decisions about the database move are made from what is really on the
    server, not from guesses.

    Most of the Swarm stores its data in PostgreSQL (permanent). About forty
    older files still open a local SQLite file instead. Whether that data
    survives a deploy depends on where the file sits: on a mounted disk it
    is kept; inside the app folder it is wiped every time Render deploys.
    This report shows which is which.

WHAT IT REPORTS:
    process     the server process answering (id, parent, how long it has run,
                which background threads are alive in it)
    scheduler   whether ENABLE_SCHEDULED_JOBS is on, and the job list
    disk        whether /mnt/project is a real mounted disk, and free space
    local_files every SQLite file found in the places the code looks, with
                size, last change, and the row count of every table
    postgres    every PostgreSQL table with its row count and the newest
                timestamp in it (which shows what is still being written to)

    It reads counts and timestamps only. It never returns the contents of a
    row, and it changes nothing.

ENDPOINTS:
    GET /system-report              a page with the report as copyable text
    GET /api/admin/system-report    the report as JSON

    Both are private: neither is in swarm_security.py's public list, so the
    Admin Gate requires the admin passcode.

CHANGELOG:
- November 13, 2026: INITIAL IMPLEMENTATION
  * New blueprint system_report_bp. Registered in app.py (see app.py
    changelog). Read-only. Rule 1 (do no harm) preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import glob
import os
import shutil
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, send_from_directory

system_report_bp = Blueprint('system_report', __name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMPLATES_DIR = os.path.join(_ROOT, 'templates')
_LOADED_AT = time.time()

# Folders the Swarm's code looks in for local database files.
LOCAL_FOLDERS = [_ROOT, '/mnt/project', '/opt/render/project/src', '/tmp', '/var/data']

# Column names that usually hold "when this row was written", best first.
TIME_COLUMNS = ['created_at', 'timestamp', 'updated_at', 'run_at', 'checked_at', 'recorded_at',
                'generated_at', 'started_at', 'submitted_at', 'sent_at', 'last_seen', 'date']


def _when(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def _process():
    return {
        'pid': os.getpid(),
        'parent_pid': os.getppid(),
        'python': sys.version.split()[0],
        'folder': os.getcwd(),
        'loaded': _when(_LOADED_AT),
        'minutes_since_loaded': round((time.time() - _LOADED_AT) / 60, 1),
        'threads_alive_here': sorted(thread.name for thread in threading.enumerate()),
    }


def _scheduler():
    info = {'ENABLE_SCHEDULED_JOBS': os.environ.get('ENABLE_SCHEDULED_JOBS', '(not set)')}
    try:
        from proactive.scheduler import get_scheduler_status
        info.update(get_scheduler_status())
    except Exception as error:
        info['error'] = f'{type(error).__name__}: {error}'
    info['note'] = ('The job list comes from this worker process. The jobs themselves run in the '
                    'parent process, so the proof that they run is fresh timestamps in the '
                    'PostgreSQL tables they write to.')
    return info


def _disk():
    folders = []
    for path in ('/mnt/project', '/var/data', _ROOT, '/tmp'):
        entry = {'path': path, 'exists': os.path.isdir(path)}
        if entry['exists']:
            entry['is_mounted_disk'] = os.path.ismount(path)
            try:
                usage = shutil.disk_usage(path)
                entry['free_gb'] = round(usage.free / 1e9, 2)
                entry['total_gb'] = round(usage.total / 1e9, 2)
                entry['files'] = len(os.listdir(path))
            except Exception as error:
                entry['error'] = str(error)
        folders.append(entry)
    return folders


def _sqlite_file(path):
    entry = {'path': path, 'size_kb': round(os.path.getsize(path) / 1024, 1),
             'last_changed': _when(os.path.getmtime(path)), 'tables': {}}
    try:
        connection = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=5)
        try:
            names = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            for name in names:
                try:
                    quoted = '"' + name.replace('"', '""') + '"'
                    entry['tables'][name] = connection.execute(f'SELECT COUNT(*) FROM {quoted}').fetchone()[0]
                except Exception as error:
                    entry['tables'][name] = f'error: {error}'
        finally:
            connection.close()
    except Exception as error:
        entry['error'] = f'{type(error).__name__}: {error}'
    entry['rows_total'] = sum(count for count in entry['tables'].values() if isinstance(count, int))
    return entry


def _local_files():
    seen, files = set(), []
    for folder in LOCAL_FOLDERS:
        if not os.path.isdir(folder):
            continue
        for pattern in ('*.db', '*.sqlite', '*.sqlite3'):
            for path in sorted(glob.glob(os.path.join(folder, pattern))):
                real = os.path.realpath(path)
                if real in seen or not os.path.isfile(real):
                    continue
                seen.add(real)
                files.append(_sqlite_file(path))
    return files


def _postgres():
    from db_engine import get_db_connection, get_db_type
    if get_db_type() != 'postgresql':
        return {'in_use': False, 'note': 'DATABASE_URL is not set, so the Swarm is on its SQLite fallback.'}

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT table_name, column_name FROM information_schema.columns "
                       "WHERE table_schema = 'public' ORDER BY table_name, ordinal_position")
        columns = {}
        for row in cursor.fetchall():
            columns.setdefault(row['table_name'], []).append(row['column_name'])
    finally:
        connection.close()

    tables = []
    for name in sorted(columns):
        entry = {'table': name}
        quoted = '"' + name.replace('"', '""') + '"'
        time_column = next((column for column in TIME_COLUMNS if column in columns[name]), None)
        # One connection per table: an error on one table cannot spoil the next.
        connection = get_db_connection()
        try:
            cursor = connection.cursor()
            if time_column:
                cursor.execute(f'SELECT COUNT(*) AS n, MAX("{time_column}")::text AS newest FROM {quoted}')
            else:
                cursor.execute(f'SELECT COUNT(*) AS n, NULL AS newest FROM {quoted}')
            row = cursor.fetchone()
            entry['rows'] = row['n']
            entry['newest'] = (row['newest'] or '')[:19] or None
            entry['newest_from'] = time_column
        except Exception as error:
            entry['error'] = f'{type(error).__name__}: {str(error)[:120]}'
        finally:
            connection.close()
        tables.append(entry)
    return {'in_use': True, 'table_count': len(tables), 'tables': tables}


def build_report():
    report = {'generated': _when(time.time())}
    for name, function in (('process', _process), ('scheduler', _scheduler), ('disk', _disk),
                           ('local_files', _local_files), ('postgres', _postgres)):
        try:
            report[name] = function()
        except Exception as error:                   # one failed section must not hide the others
            report[name] = {'error': f'{type(error).__name__}: {error}'}
    return report


@system_report_bp.route('/api/admin/system-report', methods=['GET'])
def system_report():
    response = jsonify(build_report())
    response.headers['Cache-Control'] = 'no-store'
    return response


@system_report_bp.route('/system-report', methods=['GET'])
def system_report_page():
    """The page. A plain file: nothing in it is filled in by the server."""
    response = send_from_directory(_TEMPLATES_DIR, 'system_report.html', mimetype='text/html')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Frame-Options'] = 'DENY'
    return response


# I did no harm and this file is not truncated
