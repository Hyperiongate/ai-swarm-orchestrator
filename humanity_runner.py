"""
The Humanity Index — Research Helper (separate process)
File: humanity_runner.py
Created: November 15, 2026
Last Updated: November 15, 2026 — Initial implementation

PURPOSE:
    The one process that does the Humanity Index's AI work, so the Swarm's web
    workers never wait on it. It takes jobs from the humanity_jobs table, runs
    each in a thread, and writes the answers back (and into the library).

    It is NOT started by hand and is NOT part of the Render start command.
    humanity_engine.ensure_runner() starts it when a job is queued and no
    helper is alive. It does not import app.py, and it is separate from the
    fact-checker's helper: each has its own tables and its own singleton row.

HOW IT BEHAVES (the same as factcheck_runner.py, which is tested on Render):
    * Singleton: claims the single humanity_runner row or exits at once.
    * Heartbeat every 3 seconds; if another helper took over, it stops taking
      new jobs and exits.
    * On start it re-queues jobs a dead helper left 'running' (two tries in
      all) and deletes queue entries older than two days. The library and
      the ledger are never touched by this housekeeping.
    * Up to 4 jobs at once. Exits after 10 idle minutes. On SIGTERM (a
      deploy) it exits immediately; unfinished jobs are picked up next time.
    * Its lines in the Render log start with [Humanity].

CHANGELOG:
- November 15, 2026: INITIAL IMPLEMENTATION. New file. No existing file touched.
  Rule 1 (do no harm) preserved.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import logging
import os
import signal
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import humanity_engine as engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="[Humanity] %(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("humanity_runner")
for _noisy in ("httpx", "httpx2"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

FAST_POLL_SECONDS = 0.5
SLOW_POLL_SECONDS = 2.0
FAST_WINDOW_SECONDS = 30


def _store(job, ok, result, error, http_status):
    """Write a job's outcome, retrying through a brief database hiccup."""
    for attempt in range(4):
        try:
            engine.finish_job(job["id"], job["kind"], job["payload"], ok,
                              result=result, error=error, http_status=http_status)
            return
        except Exception as exc:
            log.warning("Could not store the result of job %s (try %s): %s", job["id"][:8], attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))
    log.error("Gave up storing the result of job %s", job["id"][:8])


def _work(job):
    started = time.time()
    ok, result, error, http_status = engine.run_job(job["kind"], job["payload"])
    _store(job, ok, result, error, http_status)
    log.info("Job %s (%s) %s in %.1fs%s", job["id"][:8], job["kind"],
             "done" if ok else "FAILED", time.time() - started, "" if ok else f": {error}")


def main():
    token = uuid.uuid4().hex
    try:
        engine.ensure_tables()
        if not engine.claim_runner(token, os.getpid()):
            log.info("Another research helper is already running. Exiting (pid %s).", os.getpid())
            return 0
    except Exception as exc:
        log.error("Could not start: the database is not reachable (%s)", exc)
        return 1

    log.info("Research helper started (pid %s).", os.getpid())
    stop = threading.Event()
    lost = threading.Event()
    terminated = threading.Event()

    def _on_signal(_signum, _frame):
        terminated.set()
        stop.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    def _heartbeat():
        while not stop.wait(engine.RUNNER_HEARTBEAT_SECONDS):
            try:
                if not engine.runner_heartbeat(token):
                    log.warning("Another helper has taken over. Finishing current jobs, then exiting.")
                    lost.set()
                    stop.set()
            except Exception as exc:
                log.warning("Heartbeat could not be written: %s", exc)

    threading.Thread(target=_heartbeat, daemon=True, name="HumanityHeartbeat").start()

    try:
        requeued, failed = engine.requeue_interrupted_jobs()
        if requeued or failed:
            log.info("Found interrupted jobs: %s put back in the queue, %s failed.", requeued, failed)
        removed = engine.delete_old_jobs()
        if removed:
            log.info("Deleted %s queue entries older than two days.", removed)
    except Exception as exc:
        log.warning("Start-up housekeeping failed (continuing): %s", exc)

    executor = ThreadPoolExecutor(max_workers=engine.RUNNER_MAX_THREADS, thread_name_prefix="HumanityJob")
    active = set()
    last_work = time.time()

    while not stop.is_set():
        for future in [f for f in active if f.done()]:
            active.discard(future)
            error = future.exception()
            if error:
                log.error("A job thread crashed: %s", error)

        jobs = []
        free = engine.RUNNER_MAX_THREADS - len(active)
        if free > 0:
            try:
                jobs = engine.claim_jobs(free)
            except Exception as exc:
                log.warning("Could not read the queue: %s", exc)
                stop.wait(2.0)
        for job in jobs:
            active.add(executor.submit(_work, job))

        now = time.time()
        if active or jobs:
            last_work = now
        elif now - last_work > engine.RUNNER_IDLE_EXIT_SECONDS:
            log.info("Nothing to do for %s minutes. Exiting.", engine.RUNNER_IDLE_EXIT_SECONDS // 60)
            break
        stop.wait(FAST_POLL_SECONDS if now - last_work < FAST_WINDOW_SECONDS else SLOW_POLL_SECONDS)

    stop.set()
    if terminated.is_set():
        log.info("Stop signal received with %s job(s) in flight. Exiting now.", len(active))
        try:
            engine.release_runner(token)
        except Exception:
            pass
        os._exit(0)

    executor.shutdown(wait=True)
    if not lost.is_set():
        try:
            engine.release_runner(token)
        except Exception as exc:
            log.warning("Could not step down cleanly: %s", exc)
    log.info("Research helper stopped (pid %s).", os.getpid())
    return 0


if __name__ == "__main__":
    sys.exit(main())

# I did no harm and this file is not truncated
