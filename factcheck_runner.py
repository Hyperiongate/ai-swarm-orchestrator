"""
Speech Fact-Checker — Checking Helper (separate process)
File: factcheck_runner.py
Created: November 11, 2026
Last Updated: November 11, 2026 — Initial implementation

PURPOSE:
    The one process that does the fact-checker's AI work, so the Swarm's web
    workers never have to wait on it. It takes jobs from the factcheck_jobs
    table, runs each in a thread, and writes the answers back.

    It is NOT started by hand and is NOT part of the Render start command.
    factcheck_engine.ensure_runner() starts it when a job is queued and no
    helper is alive. It does not import app.py and touches no other Swarm table.

HOW IT BEHAVES:
    * Singleton. On start it tries to claim the single factcheck_runner row; if
      another helper is alive it exits at once.
    * Heartbeat every 3 seconds. If its heartbeat is ever refused (another
      helper took over after a stall) it stops taking new jobs and exits.
    * On start it re-queues jobs a dead helper left 'running' (each job gets
      two tries in all) and deletes jobs older than two days.
    * Up to 8 jobs at once, at most 3 of them report work, so live checks
      always have room.
    * Exits by itself after 10 minutes with nothing to do. On SIGTERM (a
      deploy) it exits immediately; unfinished jobs are picked up by the next
      helper.

CHANGELOG:
- November 11, 2026: INITIAL IMPLEMENTATION. New file. No existing file touched.
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

import factcheck_engine as engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="[FactCheck] %(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("factcheck_runner")
# The HTTP library logs one line per AI call at INFO; keep the Render log readable.
# (Its logger is named "httpx" or "httpx2" depending on the Anthropic library version.)
for _noisy in ("httpx", "httpx2"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

FAST_POLL_SECONDS = 0.4      # while a speech is in progress
SLOW_POLL_SECONDS = 2.0      # after 30 quiet seconds
FAST_WINDOW_SECONDS = 30


def _store(job_id, ok, result, error, http_status):
    """Write a job's outcome, retrying through a brief database hiccup."""
    for attempt in range(4):
        try:
            engine.finish_job(job_id, ok, result=result, error=error, http_status=http_status)
            return
        except Exception as exc:
            log.warning("Could not store the result of job %s (try %s): %s", job_id[:8], attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))
    log.error("Gave up storing the result of job %s", job_id[:8])


def _work(job):
    started = time.time()
    ok, result, error, http_status = engine.run_job(job["kind"], job["payload"])
    _store(job["id"], ok, result, error, http_status)
    log.info("Job %s (%s) %s in %.1fs%s", job["id"][:8], job["kind"],
             "done" if ok else "FAILED", time.time() - started, "" if ok else f": {error}")


def main():
    token = uuid.uuid4().hex
    try:
        engine.ensure_tables()
        if not engine.claim_runner(token, os.getpid()):
            log.info("Another checking helper is already running. Exiting (pid %s).", os.getpid())
            return 0
    except Exception as exc:
        log.error("Could not start: the database is not reachable (%s)", exc)
        return 1

    log.info("Checking helper started (pid %s).", os.getpid())
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

    threading.Thread(target=_heartbeat, daemon=True, name="FactCheckHeartbeat").start()

    try:
        requeued, failed = engine.requeue_interrupted_jobs()
        if requeued or failed:
            log.info("Found interrupted jobs: %s put back in the queue, %s failed.", requeued, failed)
        removed = engine.delete_old_jobs()
        if removed:
            log.info("Deleted %s jobs older than two days.", removed)
    except Exception as exc:
        log.warning("Start-up housekeeping failed (continuing): %s", exc)

    executor = ThreadPoolExecutor(max_workers=engine.RUNNER_MAX_THREADS, thread_name_prefix="FactCheckJob")
    active = {}                       # future -> kind
    last_work = time.time()

    while not stop.is_set():
        for future in [f for f in active if f.done()]:
            active.pop(future, None)
            error = future.exception()
            if error:
                log.error("A job thread crashed: %s", error)

        free = engine.RUNNER_MAX_THREADS - len(active)
        deep_running = sum(1 for kind in active.values() if kind == "deep")
        jobs = []
        if free > 0:
            try:
                jobs = engine.claim_jobs(free, engine.RUNNER_MAX_DEEP - deep_running)
            except Exception as exc:
                log.warning("Could not read the queue: %s", exc)
                stop.wait(2.0)
        for job in jobs:
            active[executor.submit(_work, job)] = job["kind"]

        now = time.time()
        if active or jobs:
            last_work = now
        elif now - last_work > engine.RUNNER_IDLE_EXIT_SECONDS:
            log.info("Nothing to do for %s minutes. Exiting.", engine.RUNNER_IDLE_EXIT_SECONDS // 60)
            break
        stop.wait(FAST_POLL_SECONDS if now - last_work < FAST_WINDOW_SECONDS else SLOW_POLL_SECONDS)

    stop.set()
    if terminated.is_set():
        # A deploy or shutdown: leave at once. The next helper re-queues unfinished jobs.
        log.info("Stop signal received with %s job(s) in flight. Exiting now.", len(active))
        try:
            engine.release_runner(token)
        except Exception:
            pass
        os._exit(0)

    executor.shutdown(wait=True)      # idle exit has nothing in flight; a take-over lets jobs finish
    if not lost.is_set():
        try:
            engine.release_runner(token)
        except Exception as exc:
            log.warning("Could not step down cleanly: %s", exc)
    log.info("Checking helper stopped (pid %s).", os.getpid())
    return 0


if __name__ == "__main__":
    sys.exit(main())

# I did no harm and this file is not truncated
