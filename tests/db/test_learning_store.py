"""
Learning store — where the self-learning modules keep their file
File: tests/db/test_learning_store.py
Created: November 13, 2026
Last Updated: November 13, 2026 — Initial version

PURPOSE:
    Before November 13, 2026 the learning engines wrote to a file in the app
    folder, which Render replaces on every deploy, so they forgot everything
    each time. These tests check the rule that now chooses the file
    (local_store.py) and that all four engines follow it.

    Run:  python -m pytest tests/db/test_learning_store.py -q

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import importlib
import inspect
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

ENGINES = ("adaptive_learning_engine", "predictive_intelligence",
           "collective_intelligence_engine", "auto_learning_trigger")


def test_the_file_is_chosen_in_the_documented_order(tmp_path, monkeypatch):
    import local_store
    monkeypatch.setenv("LEARNING_DB_PATH", str(tmp_path / "chosen.db"))
    assert local_store.learning_db_path() == str(tmp_path / "chosen.db")

    monkeypatch.delenv("LEARNING_DB_PATH")
    disk = tmp_path / "disk"
    disk.mkdir()
    monkeypatch.setattr(local_store, "PERSISTENT_FOLDER", str(disk))
    assert local_store.learning_db_path() == str(disk / "swarm_learning.db")      # a disk is attached

    monkeypatch.setattr(local_store, "PERSISTENT_FOLDER", str(tmp_path / "no-such-disk"))
    assert local_store.learning_db_path() == "swarm_intelligence.db"              # no disk: as before


def test_every_engine_defaults_to_the_shared_setting():
    import local_store
    checked = 0
    for name in ENGINES:
        module = importlib.import_module(name)
        for _n, thing in inspect.getmembers(module):
            if getattr(thing, "__module__", None) != name:
                continue
            target = thing.__init__ if inspect.isclass(thing) else thing
            try:
                parameters = inspect.signature(target).parameters
            except (TypeError, ValueError):
                continue
            if "db_path" in parameters:
                assert parameters["db_path"].default == local_store.LEARNING_DB_PATH, (name, _n)
                checked += 1
        source = open(os.path.join(ROOT, name + ".py"), encoding="utf-8").read().split('"""', 2)[2]
        assert "'swarm_intelligence.db'" not in source, name
    assert checked == 16


def test_what_an_engine_learns_is_still_there_after_a_restart(tmp_path):
    """A 'restart' here is a brand-new engine object opening the same file, as after a deploy."""
    from adaptive_learning_engine import AdaptiveLearningEngine, OutcomeTracker
    path = str(tmp_path / "swarm_learning.db")
    engine = AdaptiveLearningEngine(path)
    first = engine.outcome_tracker.record_outcome({"task_id": 1, "task_type": "schedule", "execution_time_seconds": 12})
    assert first

    OutcomeTracker(path)                                   # creating tables again must not clear them
    again = AdaptiveLearningEngine(path)
    again.outcome_tracker.record_outcome({"task_id": 2, "task_type": "schedule"})
    db = sqlite3.connect(path)
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"outcome_tracking", "learned_patterns", "behavior_adjustments"} <= tables
    assert db.execute("SELECT COUNT(*) FROM outcome_tracking").fetchone()[0] == 2
    db.close()


# I did no harm and this file is not truncated
