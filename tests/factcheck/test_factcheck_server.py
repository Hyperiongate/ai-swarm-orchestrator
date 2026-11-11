"""
Speech Fact-Checker — server tests
File: tests/factcheck/test_factcheck_server.py
Created: November 11, 2026
Last Updated: November 11, 2026 — Initial version

PURPOSE:
    Tests for factcheck_engine.py, factcheck_runner.py and routes/factcheck.py
    against a real database, with the stand-in AI service
    (stub_ai_service.py) in place of Anthropic. Nothing in the Swarm imports
    this file.

    Run from the repo root, with a THROWAWAY database (the tests empty the two
    factcheck_ tables):
        DATABASE_URL=postgresql://... python -m pytest tests/factcheck/test_factcheck_server.py

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

if not os.environ.get("DATABASE_URL"):
    pytest.skip("Set DATABASE_URL to a throwaway PostgreSQL database to run these tests.",
                allow_module_level=True)

STUB_PORT = int(os.environ.get("STUB_PORT", "5099"))
os.environ["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{STUB_PORT}"
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"
os.environ.pop("FACTCHECK_PASSCODE", None)

import factcheck_engine as engine  # noqa: E402
from db_engine import get_db_connection  # noqa: E402
from mini_app import app as flask_app  # noqa: E402


# ---------------------------------------------------------------------------
# helpers and fixtures
# ---------------------------------------------------------------------------

def stub_stats():
    with urllib.request.urlopen(f"http://127.0.0.1:{STUB_PORT}/_stats", timeout=5) as response:
        return json.loads(response.read())


def runner_row():
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT pid, token, heartbeat_at FROM factcheck_runner WHERE id = 1")
        return dict(cur.fetchone())


def job_row(job_id):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM factcheck_jobs WHERE id = %s", (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def set_job(job_id, **fields):
    sets = ", ".join(f"{name} = %s" for name in fields)
    with get_db_connection() as conn:
        conn.cursor().execute(f"UPDATE factcheck_jobs SET {sets} WHERE id = %s",
                              tuple(fields.values()) + (job_id,))


def kill_helper():
    """Stop any helper process left by a previous test and mark the row free."""
    row = runner_row()
    if row["pid"] and time.time() - row["heartbeat_at"] < 60:
        try:
            os.kill(int(row["pid"]), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    with get_db_connection() as conn:
        conn.cursor().execute("UPDATE factcheck_runner SET pid = 0, token = '', heartbeat_at = 0 WHERE id = 1")
    for child in list(engine._children):
        try:
            child.wait(timeout=5)
        except Exception:
            pass
    engine._last_spawn = 0.0


def work_all():
    """Do every waiting job right here, the way the helper would."""
    done = 0
    while True:
        jobs = engine.claim_jobs(8, 3)
        if not jobs:
            return done
        for job in jobs:
            ok, result, error, http_status = engine.run_job(job["kind"], job["payload"])
            engine.finish_job(job["id"], ok, result=result, error=error, http_status=http_status)
            done += 1


@pytest.fixture(scope="session", autouse=True)
def stub_service():
    env = dict(os.environ, STUB_DELAY="0.05", STUB_SLOW_SECONDS="8")
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "stub_ai_service.py"), str(STUB_PORT)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            stub_stats()
            break
        except Exception:
            time.sleep(0.1)
    yield
    proc.terminate()


@pytest.fixture()
def web(monkeypatch):
    """A test browser, a clean queue, and NO helper process (jobs are worked with work_all)."""
    engine.ensure_tables()
    kill_helper()
    with get_db_connection() as conn:
        conn.cursor().execute("DELETE FROM factcheck_jobs")
    monkeypatch.delenv("FACTCHECK_PASSCODE", raising=False)
    spawned = []
    monkeypatch.setattr(engine, "ensure_runner", lambda: spawned.append(1) and False)
    client = flask_app.test_client()
    client.spawned = spawned
    yield client
    kill_helper()


def queue(web, kind, body, **kwargs):
    response = web.post(f"/api/factcheck/{kind}", json=body, **kwargs)
    assert response.status_code == 202, response.get_data(as_text=True)
    return response.get_json()["job_id"]


def status(web, ids, **kwargs):
    response = web.post("/api/factcheck/jobs/status", json={"ids": ids}, **kwargs)
    assert response.status_code == 200, response.get_data(as_text=True)
    return {job["id"]: job for job in response.get_json()["jobs"]}


def result_of(web, kind, body):
    job_id = queue(web, kind, body)
    work_all()
    job = status(web, [job_id])[job_id]
    assert job["status"] == "done", job
    return job["result"]


# ---------------------------------------------------------------------------
# the page and the health check
# ---------------------------------------------------------------------------

def test_page_is_served_exactly_as_the_file(web):
    response = web.get("/factcheck")
    assert response.status_code == 200
    with open(os.path.join(ROOT, "templates", "factcheck.html"), "rb") as handle:
        assert response.data == handle.read()          # no template engine touched it
    assert response.mimetype == "text/html"
    assert response.headers["Permissions-Policy"] == "microphone=(self)"
    assert b"I did no harm and this file is not truncated" in response.data


def test_health_reports_what_the_page_needs(web, monkeypatch):
    data = web.get("/api/factcheck/health").get_json()
    assert data["ok"] and data["engine"] == "ok" and data["ai_ready"] is True
    assert data["database"] == "ok" and data["helper"] == "idle"
    assert data["passcode_required"] is False
    assert data["models"] == {"claims": "claude-haiku-5-5", "check": "claude-haiku-5-5",
                              "deep": "claude-sonnet-5-5"}
    monkeypatch.setenv("FACTCHECK_PASSCODE", "open-sesame")
    data = web.get("/api/factcheck/health").get_json()
    assert data["passcode_required"] is True and data["passcode_ok"] is False
    data = web.get("/api/factcheck/health", headers={"X-App-Passcode": "open-sesame"}).get_json()
    assert data["passcode_ok"] is True


def test_passcode_guards_queueing_and_results(web, monkeypatch):
    monkeypatch.setenv("FACTCHECK_PASSCODE", "open-sesame")
    body = {"new_text": "Crime fell 12 percent last year."}
    assert web.post("/api/factcheck/claims", json=body).status_code == 401
    assert web.post("/api/factcheck/claims", json=body, headers={"X-App-Passcode": "wrong"}).status_code == 401
    assert web.post("/api/factcheck/jobs/status", json={"ids": []}).status_code == 401
    good = {"X-App-Passcode": "open-sesame"}
    job_id = queue(web, "claims", body, headers=good)
    assert status(web, [job_id], headers=good)[job_id]["status"] == "queued"


# ---------------------------------------------------------------------------
# queueing
# ---------------------------------------------------------------------------

def test_queueing_is_instant_and_makes_no_ai_call(web):
    before = stub_stats()["calls"]
    job_id = queue(web, "check", {"claim": "Crime fell 12 percent.", "speaker": "S" * 500,
                                  "context": "x" * 9000, "junk": "ignored"})
    assert stub_stats()["calls"] == before
    row = job_row(job_id)
    assert row["status"] == "queued" and row["kind"] == "check" and row["priority"] == 1
    payload = json.loads(row["payload"])
    assert len(payload["speaker"]) == 120 and len(payload["context"]) == 3000 and "junk" not in payload
    assert web.spawned, "queueing should ask for the helper to be started"


def test_bad_requests_are_refused_plainly(web):
    assert web.post("/api/factcheck/claims", json={"new_text": "   "}).status_code == 400
    assert web.post("/api/factcheck/check", json={"claim": ""}).status_code == 400
    assert web.post("/api/factcheck/deep", json={}).status_code == 400
    assert web.post("/api/factcheck/check", data="not json", content_type="text/plain").status_code == 400
    big = web.post("/api/factcheck/claims", json={"new_text": "x" * 300_000})
    assert big.status_code == 413
    assert web.post("/api/factcheck/jobs/status", json={"ids": "nope"}).status_code == 400
    assert web.get("/api/factcheck/claims").status_code == 405


def test_missing_key_is_reported_before_anything_is_queued(web, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    response = web.post("/api/factcheck/check", json={"claim": "Anything 5."})
    assert response.status_code == 503 and "ANTHROPIC_API_KEY" in response.get_json()["error"]
    assert web.get("/api/factcheck/health").get_json()["ai_ready"] is False


def test_daily_cap_holds_in_the_database(web, monkeypatch):
    monkeypatch.setattr(engine, "DAILY_JOB_LIMIT", 2)
    queue(web, "check", {"claim": "First 5."})
    queue(web, "check", {"claim": "Second 5."})
    response = web.post("/api/factcheck/check", json={"claim": "Third 5."})
    assert response.status_code == 503 and "safety cap" in response.get_json()["error"]


# ---------------------------------------------------------------------------
# the three jobs (worked in-process through the real Anthropic library)
# ---------------------------------------------------------------------------

def test_claims_found_and_unfinished_sentence_carried(web):
    data = result_of(web, "claims", {
        "new_text": "Thank you all. Crime fell 12 percent last year. We built 300 miles of"})
    assert [c["quote"] for c in data["claims"]] == ["Crime fell 12 percent last year."]
    assert data["incomplete_tail"] == "We built 300 miles of"
    assert data["usage"]["input_tokens"] == 1000
    sent = stub_stats()["last"][-1]
    assert [t.get("name") for t in sent["tools"]] == ["record_claims"]     # no web search for this job
    assert sent["output_config"] == {"effort": "low"}
    assert sent["model"] == "claude-haiku-5-5"
    assert "same standards to every speaker" in sent["system"]
    assert "never guess at motive" in sent["system"]


def test_final_passage_has_no_carry(web):
    data = result_of(web, "claims", {"new_text": "We built 300 miles of", "final": True})
    assert data["incomplete_tail"] == ""


def test_check_gives_verdict_and_only_real_sources(web):
    data = result_of(web, "check", {"claim": "This is wrong 5.", "speaker": "Senator Example",
                                    "event": "Town hall"})
    assert data["verdict"] == "false"
    assert [s["url"] for s in data["sources"]] == ["https://stats.example.gov/report"]   # made-up link dropped
    assert data["sources"][0]["cited"] is True
    assert data["usage"]["searches"] == 1 and data["searched"] is True
    sent = stub_stats()["last"][-1]
    assert sent["tools"][0] == {"type": "web_search_20250305", "name": "web_search", "max_uses": 2}
    assert "<speaker>Senator Example</speaker>" in sent["messages"][0]["content"]


def test_check_continues_after_a_paused_search(web):
    before = stub_stats()["calls"]
    data = result_of(web, "check", {"claim": "A half truth pausecase 5."})
    assert data["verdict"] == "misleading"
    assert stub_stats()["calls"] == before + 2
    second = stub_stats()["last"][-1]
    assert second["messages"][1]["role"] == "assistant"
    kinds = [block["type"] for block in second["messages"][1]["content"]]
    assert kinds == ["server_tool_use", "web_search_tool_result"]          # the search work is handed back intact
    assert data["sources"][0]["url"] == "https://stats.example.gov/report"


def test_check_nudges_when_the_answer_is_not_recorded(web):
    data = result_of(web, "check", {"claim": "An unknown thing nudgecase 5."})
    assert data["verdict"] == "unverified"
    assert "record_verdict" in stub_stats()["last"][-1]["messages"][-1]["content"]


def test_check_with_no_answer_is_reported_honestly(web):
    data = result_of(web, "check", {"claim": "Something neveranswer 5."})
    assert data["verdict"] == "unverified" and data["no_answer"] is True and data["sources"] == []


def test_deep_returns_five_layers(web):
    data = result_of(web, "deep", {"claim": "A flip claim 5.", "live_verdict": "true", "live_reason": "x"})
    assert data["final_verdict"] == "misleading"
    for key in ("literal_verdict", "literal_explanation", "implied_claim", "implied_verdict",
                "implied_explanation", "track_record", "techniques", "context", "sources"):
        assert key in data
    assert data["techniques"][0]["name"] == "Missing context"
    assert data["sources"][0]["url"] == "https://news.example.org/story/"
    sent = stub_stats()["last"][-1]
    assert "<quick_live_verdict>\ntrue: x" in sent["messages"][0]["content"]
    assert sent["model"] == "claude-sonnet-5-5" and sent["tools"][0]["max_uses"] == 5


def test_ai_service_error_becomes_a_plain_message(web):
    job_id = queue(web, "check", {"claim": "Something autherror 5."})
    work_all()
    job = status(web, [job_id])[job_id]
    assert job["status"] == "failed" and job["http_status"] == 502
    assert job["error"] == "The AI service rejected the key. Check ANTHROPIC_API_KEY in Render."


# ---------------------------------------------------------------------------
# job status and stuck work
# ---------------------------------------------------------------------------

def test_status_handles_unknown_and_malformed_ids(web):
    job_id = queue(web, "check", {"claim": "X 5."})
    unknown = "0" * 32
    response = web.post("/api/factcheck/jobs/status",
                        json={"ids": [job_id, unknown, "'; DROP TABLE factcheck_jobs; --", 7]})
    jobs = response.get_json()["jobs"]
    assert [j["id"] for j in jobs] == [job_id, unknown]
    assert jobs[0]["status"] == "queued" and jobs[1]["status"] == "missing"
    assert status(web, []) == {}


def test_queued_job_fails_when_the_helper_never_starts(web):
    job_id = queue(web, "check", {"claim": "X 5."})
    assert status(web, [job_id])[job_id]["status"] == "queued"
    set_job(job_id, created_at=time.time() - engine.QUEUE_GIVE_UP_SECONDS - 5)
    job = status(web, [job_id])[job_id]
    assert job["status"] == "failed" and "did not start" in job["error"]
    assert job_row(job_id)["status"] == "failed"


def test_job_running_far_too_long_is_failed(web):
    job_id = queue(web, "check", {"claim": "X 5."})
    assert engine.claim_jobs(1, 1)[0]["id"] == job_id
    set_job(job_id, started_at=time.time() - engine.JOB_HARD_LIMIT_SECONDS["check"] - 5)
    job = status(web, [job_id])[job_id]
    assert job["status"] == "failed" and "too long" in job["error"]
    engine.finish_job(job_id, True, result={"verdict": "true"})           # a late answer must not undo it
    assert job_row(job_id)["status"] == "failed"


def test_live_work_is_taken_before_report_work(web):
    deep_ids = [queue(web, "deep", {"claim": f"Deep {n} 5."}) for n in range(5)]
    check_id = queue(web, "check", {"claim": "Live 5."})
    claims_id = queue(web, "claims", {"new_text": "Live text 5."})
    taken = engine.claim_jobs(8, 3)
    assert [job["id"] for job in taken[:2]] == [claims_id, check_id]
    assert sum(1 for job in taken if job["kind"] == "deep") == 3           # report work is capped
    assert len(taken) == 5
    assert [job_row(i)["status"] for i in deep_ids].count("queued") == 2


# ---------------------------------------------------------------------------
# the helper's identity (one at a time) and recovery
# ---------------------------------------------------------------------------

def test_only_one_helper_can_hold_the_row(web):
    assert engine.claim_runner("aaa", 111) is True
    assert engine.runner_alive() is True
    assert engine.claim_runner("bbb", 222) is False                        # the first is still fresh
    assert engine.runner_heartbeat("aaa") is True
    with get_db_connection() as conn:                                      # the first goes quiet...
        conn.cursor().execute("UPDATE factcheck_runner SET heartbeat_at = %s WHERE id = 1",
                              (time.time() - engine.RUNNER_STALE_SECONDS - 1,))
    assert engine.runner_alive() is False
    assert engine.claim_runner("bbb", 222) is True                         # ...so the second takes over
    assert engine.runner_heartbeat("aaa") is False                         # and the first learns it lost
    engine.release_runner("bbb")
    assert engine.runner_alive() is False


def test_interrupted_jobs_get_one_more_try_then_fail(web):
    first = queue(web, "check", {"claim": "A 5."})
    second = queue(web, "check", {"claim": "B 5."})
    assert len(engine.claim_jobs(8, 3)) == 2                               # both now 'running', attempts 1
    set_job(second, attempts=2)
    assert engine.requeue_interrupted_jobs() == (1, 1)
    assert job_row(first)["status"] == "queued" and job_row(first)["attempts"] == 1
    assert job_row(second)["status"] == "failed" and "interrupted twice" in job_row(second)["error"]


def test_old_jobs_are_deleted(web):
    old = queue(web, "check", {"claim": "Old 5."})
    new = queue(web, "check", {"claim": "New 5."})
    set_job(old, created_at=time.time() - engine.JOB_KEEP_SECONDS - 60)
    assert engine.delete_old_jobs() == 1
    assert job_row(old) is None and job_row(new) is not None


# ---------------------------------------------------------------------------
# end to end with the REAL helper process
# ---------------------------------------------------------------------------

@pytest.fixture()
def live(web, monkeypatch):
    """Like `web`, but with the real ensure_runner, so a real helper process is started."""
    monkeypatch.undo()
    monkeypatch.delenv("FACTCHECK_PASSCODE", raising=False)
    return web


def wait_for(web, ids, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        jobs = status(web, ids)
        if all(job["status"] in ("done", "failed", "missing") for job in jobs.values()):
            return jobs
        time.sleep(0.5)
    raise AssertionError(f"jobs not finished after {seconds}s: {status(web, ids)}")


def test_real_helper_does_the_work_and_is_a_singleton(live):
    ids = [queue(live, "claims", {"new_text": "Crime fell 12 percent last year."}),
           queue(live, "check", {"claim": "This is wrong 5."}),
           queue(live, "deep", {"claim": "A flip claim 5."})]
    jobs = wait_for(live, ids, 30)
    assert [jobs[i]["status"] for i in ids] == ["done", "done", "done"]
    assert jobs[ids[1]]["result"]["verdict"] == "false"
    assert jobs[ids[2]]["result"]["final_verdict"] == "misleading"
    assert live.get("/api/factcheck/health").get_json()["helper"] == "running"

    first_pid = runner_row()["pid"]
    second = subprocess.run([sys.executable, os.path.join(ROOT, "factcheck_runner.py")],
                            capture_output=True, text=True, timeout=30)
    assert second.returncode == 0 and "already running" in (second.stdout + second.stderr)
    assert runner_row()["pid"] == first_pid


def test_helper_killed_mid_job_is_replaced_and_the_job_finishes(live):
    job_id = queue(live, "check", {"claim": "A half truth slowcase 5."})   # the stub takes 8 seconds
    deadline = time.time() + 20
    while job_row(job_id)["status"] != "running":
        assert time.time() < deadline, "the helper never picked the job up"
        time.sleep(0.2)
    first_pid = runner_row()["pid"]
    os.kill(first_pid, signal.SIGKILL)

    jobs = wait_for(live, [job_id], 75)        # heartbeat goes stale, a poll starts a new helper, job reruns
    assert jobs[job_id]["status"] == "done" and jobs[job_id]["result"]["verdict"] == "misleading"
    assert job_row(job_id)["attempts"] == 2
    assert runner_row()["pid"] != first_pid

# I did no harm and this file is not truncated
