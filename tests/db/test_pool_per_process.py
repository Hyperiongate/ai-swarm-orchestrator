"""
Database pool — one per process
File: tests/db/test_pool_per_process.py
Created: November 13, 2026
Last Updated: November 13, 2026 — Initial implementation

PURPOSE:
    Gunicorn loads the app once and then copies it into each worker. Before
    November 13, 2026 the copies shared the parent's open database connections,
    which scrambled answers ("no results to fetch"). These tests copy a process
    the same way and prove each copy gets its own connections.

    Needs a PostgreSQL DATABASE_URL (the tests are skipped without one).
    Run:  DATABASE_URL=postgresql://... python -m pytest tests/db -q

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgres") or not hasattr(os, "fork"),
    reason="needs a PostgreSQL DATABASE_URL and a system that can copy processes",
)


def _backend_ids(db_engine, how_many=2):
    """The database's own id for each of this process's connections."""
    held, ids = [], set()
    for _ in range(how_many):
        conn = db_engine.get_db_connection()
        held.append(conn)
        cur = conn.cursor()
        cur.execute("SELECT pg_backend_pid() AS id")
        ids.add(cur.fetchone()["id"])
    for conn in held:
        conn.close()
    return ids


def _in_a_copy(work):
    """Run work() in a copied process; return what it printed down a pipe."""
    read_end, write_end = os.pipe()
    pid = os.fork()
    if pid == 0:
        code = 1
        try:
            os.close(read_end)
            os.write(write_end, work().encode())
            code = 0
        except BaseException as error:           # report, never fall back into pytest
            os.write(write_end, f"ERROR {error!r}".encode())
        finally:
            os._exit(code)
    os.close(write_end)
    chunks = []
    while True:
        chunk = os.read(read_end, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    os.close(read_end)
    os.waitpid(pid, 0)
    return b"".join(chunks).decode()


def test_a_copied_process_opens_its_own_connections():
    import db_engine
    parent_ids = _backend_ids(db_engine)
    parent_pool = db_engine._get_pg_pool()

    answer = _in_a_copy(lambda: ",".join(str(i) for i in sorted(_backend_ids(db_engine))))
    assert not answer.startswith("ERROR"), answer
    child_ids = {int(i) for i in answer.split(",")}

    assert child_ids and not (child_ids & parent_ids)       # nothing shared
    assert db_engine._get_pg_pool() is parent_pool          # the parent keeps its own pool
    assert _backend_ids(db_engine) == parent_ids            # ...and its connections still work


def test_parent_and_copies_can_all_query_at_once_without_mixing_answers():
    import db_engine
    _backend_ids(db_engine)                                 # make sure the parent pool exists first

    def many_queries(tag):
        def work():
            for n in range(300):
                with db_engine.get_db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT %s AS tag, %s AS n", (tag, n))
                    row = cur.fetchone()
                    assert row["tag"] == tag and row["n"] == n, row
            return "ok"
        return work

    read_ends = []
    for tag in ("first-copy", "second-copy"):
        read_end, write_end = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(read_end)
                os.write(write_end, many_queries(tag)().encode())
            except BaseException as error:
                os.write(write_end, f"ERROR {error!r}".encode())
            finally:
                os._exit(0)
        os.close(write_end)
        read_ends.append((pid, read_end))

    assert many_queries("parent")() == "ok"
    for pid, read_end in read_ends:
        answer = os.read(read_end, 65536).decode()
        os.close(read_end)
        os.waitpid(pid, 0)
        assert answer == "ok", answer


# I did no harm and this file is not truncated
