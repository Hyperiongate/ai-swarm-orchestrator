"""
Local Store — where the learning modules keep their file
File: local_store.py
Created: November 13, 2026
Last Updated: November 13, 2026 — Initial implementation

PURPOSE:
    One place that decides where the Swarm's self-learning modules keep their
    local database file.

    THE PROBLEM THIS FIXES:
    The four learning engines (adaptive_learning_engine, predictive_intelligence,
    collective_intelligence_engine, auto_learning_trigger) each opened a file
    called 'swarm_intelligence.db' with no folder in front of it. On Render
    that lands in the app folder, which is replaced on every deploy. So
    everything those engines learned (task outcomes, patterns, behaviour
    adjustments, suggestions) was thrown away each time the Swarm was
    deployed. The live system report of November 13, 2026 confirmed it: the
    file in the app folder held only freshly created, empty learning tables.

    THE FIX:
    The engines now take their default file from LEARNING_DB_PATH below,
    which points at the persistent disk when one is attached. Render's disk
    is mounted at /mnt/project (the system report shows it as a real mounted
    disk, and the knowledge ingestion database already lives there safely).

    A NEW file name is used on the disk, swarm_learning.db, rather than the
    old /mnt/project/swarm_intelligence.db. That old file is the Swarm's
    pre-PostgreSQL database, frozen since March 2026, with its own tables of
    the same names; mixing the two would be guessing. It is left untouched.

    NOT CHANGED: the knowledge base's search index (knowledge_integration.py)
    still uses the app-folder file. It is rebuilt from the documents at every
    start, so there is nothing to lose there.

ORDER OF CHOICE:
    1. LEARNING_DB_PATH environment variable, if set.
    2. /mnt/project/swarm_learning.db, if /mnt/project exists and is writable.
    3. 'swarm_intelligence.db' in the current folder (unchanged behaviour for
       a computer with no persistent disk).

CHANGELOG:
- November 13, 2026: INITIAL IMPLEMENTATION

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os

PERSISTENT_FOLDER = '/mnt/project'
PERSISTENT_FILE = 'swarm_learning.db'
FALLBACK_FILE = 'swarm_intelligence.db'


def learning_db_path():
    """Where the learning engines keep their file. See the notes at the top of this file."""
    chosen = os.environ.get('LEARNING_DB_PATH', '').strip()
    if chosen:
        return chosen
    if os.path.isdir(PERSISTENT_FOLDER) and os.access(PERSISTENT_FOLDER, os.W_OK):
        return os.path.join(PERSISTENT_FOLDER, PERSISTENT_FILE)
    return FALLBACK_FILE


LEARNING_DB_PATH = learning_db_path()


# I did no harm and this file is not truncated
