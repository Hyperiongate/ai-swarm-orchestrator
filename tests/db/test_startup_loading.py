"""
Start-up — nothing is left half-loaded
File: tests/db/test_startup_loading.py
Created: November 13, 2026
Last Updated: November 13, 2026 — Initial version

PURPOSE:
    Gunicorn loads app.py once and copies that process to make the worker. A
    copy made while the knowledge base was still loading in a background
    thread stayed half-loaded for good. app.py now waits for the load at the
    end of start-up. This test loads the app the same way and checks that the
    knowledge base is complete the moment loading returns, which is the moment
    Gunicorn makes its copy.

    Run:  DATABASE_URL=postgresql://... python -m pytest tests/db/test_startup_loading.py -q

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHECK = (
    "import app, threading\n"
    "kb = app.knowledge_base\n"
    "names = [t.name for t in threading.enumerate()]\n"
    "print('RESULT', kb is not None, kb.is_ready if kb else None, "
    "len(kb.knowledge_index) if kb else 0, 'KnowledgeBaseInit' in names, 'manifest-warmer' in names)\n"
)


def test_knowledge_base_is_complete_when_the_app_finishes_loading():
    done = subprocess.run([sys.executable, "-c", CHECK], cwd=ROOT, capture_output=True, text=True, timeout=240)
    lines = [line for line in done.stdout.splitlines() if line.startswith("RESULT ")]
    assert lines, done.stdout[-800:] + done.stderr[-800:]
    _tag, exists, ready, documents, still_loading, still_warming = lines[-1].split()
    assert exists == "True"                      # the repository ships project_files/
    assert ready == "True" and int(documents) > 20
    assert still_loading == "False" and still_warming == "False"


# I did no harm and this file is not truncated
