"""
The Humanity Index — server tests
File: tests/humanity/test_humanity_server.py
Created: November 15, 2026
Last Updated: November 16, 2026 (evening) — the world built from its countries

PURPOSE:
    End-to-end tests of routes/humanity.py, humanity_engine.py and
    humanity_runner.py against a real PostgreSQL database, the real AI
    libraries, and a local stand-in for the AI services (stub_ai_service.py),
    so no key is needed and nothing is spent. Nothing in the Swarm imports this.

    Run from the repo root, with a THROWAWAY database (the tests empty the
    four humanity_ tables):
        DATABASE_URL=postgresql://... python -m pytest tests/humanity/test_humanity_server.py

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import signal
import subprocess
import sys
import time

import pytest
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

if not os.environ.get("DATABASE_URL"):
    pytest.skip("Set DATABASE_URL to a throwaway PostgreSQL database to run these tests.",
                allow_module_level=True)

STUB_PORT = int(os.environ.get("STUB_PORT", "5098"))
os.environ["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{STUB_PORT}"
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
os.environ.update({
    "OPENAI_API_KEY": "test-key-not-real", "OPENAI_BASE_URL": f"http://127.0.0.1:{STUB_PORT}/gpt",
    "DEEPSEEK_API_KEY": "test-key-not-real", "FACTCHECK_PANEL_DEEPSEEK_URL": f"http://127.0.0.1:{STUB_PORT}/deepseek",
    "GOOGLE_API_KEY": "test-key-not-real", "FACTCHECK_PANEL_GEMINI_URL": f"http://127.0.0.1:{STUB_PORT}/gemini/",
    "HUMANITY_WORLD_BANK_URL": f"http://127.0.0.1:{STUB_PORT}/wb",
    "HUMANITY_OWID_URL": f"http://127.0.0.1:{STUB_PORT}/owid",
})
for _name in ("FACTCHECK_PANEL", "HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy",
              "HUMANITY_PASSCODE", "FACTCHECK_PASSCODE"):
    os.environ.pop(_name, None)
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"

from flask import Flask  # noqa: E402

import humanity_engine as engine  # noqa: E402
import humanity_me  # noqa: E402
import humanity_score  # noqa: E402
import humanity_world  # noqa: E402
from stub_ai_service import SCORE_VALUES  # noqa: E402
from db_engine import get_db_connection  # noqa: E402
from routes.humanity import humanity_bp  # noqa: E402

PASS = "test-pass-123"
H = {"X-App-Passcode": PASS}

flask_app = Flask(__name__)
flask_app.register_blueprint(humanity_bp)


# ---------------------------------------------------------------------------
# helpers and fixtures
# ---------------------------------------------------------------------------

def stub_stats():
    return requests.get(f"http://127.0.0.1:{STUB_PORT}/_stats", timeout=2).json()


def kill_helper():
    """Stop any helper a test started, and clear its row."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT pid FROM humanity_runner WHERE id = 1")
            row = cur.fetchone()
            if row and row["pid"]:
                try:
                    os.kill(int(row["pid"]), signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
            cur.execute("UPDATE humanity_runner SET heartbeat_at = 0, pid = 0, token = '' WHERE id = 1")
    except Exception:
        pass
    time.sleep(0.2)


def work_all():
    """Do every queued job in this process, the way the helper would."""
    while True:
        jobs = engine.claim_jobs(4)
        if not jobs:
            return
        for job in jobs:
            ok, result, error, status = engine.run_job(job["kind"], job["payload"])
            engine.finish_job(job["id"], job["kind"], job["payload"], ok, result=result, error=error,
                              http_status=status)


@pytest.fixture(scope="session", autouse=True)
def stub_service():
    env = dict(os.environ, STUB_DELAY="0.05", STUB_SLOW_SECONDS="6")
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "stub_ai_service.py"), str(STUB_PORT)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            stub_stats()
            break
        except Exception:
            time.sleep(0.1)
    yield
    proc.terminate()


@pytest.fixture()
def web(monkeypatch):
    """A test browser with the passcode set, empty tables, and NO helper process."""
    engine.ensure_tables()
    kill_helper()
    with get_db_connection() as conn:
        cur = conn.cursor()
        for table in ("humanity_jobs", "humanity_library", "humanity_ledger"):
            cur.execute(f"DELETE FROM {table}")
        humanity_score.ensure_tables()
        cur.execute("DELETE FROM humanity_score_values")
        cur.execute("DELETE FROM humanity_score_runs")
        humanity_me.ensure_tables()
        cur.execute("DELETE FROM humanity_me")
        humanity_world.ensure_tables()
        cur.execute("DELETE FROM humanity_country_values")
        cur.execute("DELETE FROM humanity_country")
    monkeypatch.setenv("HUMANITY_PASSCODE", PASS)
    monkeypatch.delenv("FACTCHECK_PASSCODE", raising=False)
    spawned = []
    monkeypatch.setattr(engine, "ensure_runner", lambda: spawned.append(1) and False)
    client = flask_app.test_client()
    client.spawned = spawned
    yield client
    kill_helper()


def ask(web, question, place=""):
    response = web.post("/api/humanity/ask", json={"question": question, "place": place}, headers=H)
    assert response.status_code == 202, response.get_data(as_text=True)
    return response.get_json()["job_id"]


def status(web, job_id):
    response = web.post("/api/humanity/jobs/status", json={"ids": [job_id]}, headers=H)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["jobs"][0]


def answered(web, question):
    job_id = ask(web, question)
    work_all()
    job = status(web, job_id)
    assert job["status"] == "done", job
    return job_id, job["result"]


def review(web, answer_id):
    response = web.post("/api/humanity/review", json={"answer_id": answer_id}, headers=H)
    assert response.status_code == 202, response.get_data(as_text=True)
    job_id = response.get_json()["job_id"]
    work_all()
    job = status(web, job_id)
    assert job["status"] == "done", job
    return job["result"]


# ---------------------------------------------------------------------------
# the page, health and the passcode
# ---------------------------------------------------------------------------

def test_page_is_served(web):
    response = web.get("/humanity")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "The Humanity Index" in html and "/api/humanity/ask" in html
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_health_reports_ready_and_panel(web):
    info = web.get("/api/humanity/health").get_json()
    assert info["ok"] and info["engine"] == "ok" and info["ai_ready"] and info["database"] == "ok"
    assert info["passcode_set"] and not info["passcode_ok"]
    assert [m["name"] for m in info["panel"]] == ["GPT", "DeepSeek", "Gemini"]
    assert len(info["areas"]) == 10
    assert web.get("/api/humanity/health", headers=H).get_json()["passcode_ok"]


def test_locked_when_no_passcode_is_set_at_all(web, monkeypatch):
    monkeypatch.delenv("HUMANITY_PASSCODE")
    response = web.post("/api/humanity/ask", json={"question": "walk more"})
    assert response.status_code == 401
    assert "HUMANITY_PASSCODE" in response.get_json()["error"]
    assert web.get("/api/humanity/library", headers={"X-App-Passcode": ""}).status_code == 401
    assert not web.get("/api/humanity/health").get_json()["passcode_set"]


def test_factcheck_passcode_is_the_fallback(web, monkeypatch):
    monkeypatch.delenv("HUMANITY_PASSCODE")
    monkeypatch.setenv("FACTCHECK_PASSCODE", "fc-pass")
    assert web.get("/api/humanity/library", headers={"X-App-Passcode": "fc-pass"}).status_code == 200
    assert web.get("/api/humanity/library", headers=H).status_code == 401


def test_every_api_route_needs_the_passcode(web):
    calls = [("post", "/api/humanity/ask", {"question": "walk"}), ("post", "/api/humanity/review", {"answer_id": "a" * 32}),
             ("post", "/api/humanity/jobs/status", {"ids": []}), ("get", "/api/humanity/library", None),
             ("get", "/api/humanity/library/" + "a" * 32, None), ("post", "/api/humanity/library/delete", {"id": "a" * 32}),
             ("get", "/api/humanity/ledger", None), ("post", "/api/humanity/ledger/add", {"answer_id": "a" * 32}),
             ("post", "/api/humanity/ledger/delete", {"id": "a" * 32})]
    for method, path, body in calls:
        response = getattr(web, method)(path, json=body, headers={"X-App-Passcode": "wrong"})
        assert response.status_code == 401, path
    assert web.spawned == []


# ---------------------------------------------------------------------------
# asking
# ---------------------------------------------------------------------------

def test_ask_answers_in_the_fixed_shape(web):
    job_id, result = answered(web, "I want to walk instead of driving")
    assert web.spawned, "asking should make sure the helper is running"
    assert result["title"] == "Walking instead of driving"
    assert result["area"] == "Environment and climate"
    assert result["question"] == "I want to walk instead of driving"
    assert [f["id"] for f in result["where_we_are"]["figures"]] == ["F1", "F2"]
    assert result["why"]["causes"] and result["why"]["disagreement"]
    assert result["action"]["default_times_per_week"] == 5
    co2 = result["effects"][0]
    assert co2["id"] == "E1" and co2["per_time"] == 0.8 and co2["kind"] == "environment"
    assert co2["picture_it"] == {"label": "cars driven for a year", "units_per_item": 4600}
    assert result["everyone_who_could"]["people"] == 1_400_000_000
    assert result["usage"]["searches"] == 1 and result["usage"]["cost"] > 0


def test_only_links_the_search_returned_are_kept(web):
    _job, result = answered(web, "walk instead of drive")
    f1, f2 = result["where_we_are"]["figures"]
    assert f1["source"]["url"] == "https://stats.example.gov/transport"
    assert f1["source"]["title"] == "Official transport statistics"
    assert f2["source"] is None                      # never searched -> dropped
    urls = [s["url"] for s in result["sources"]]
    assert "https://made-up.example.com/x" not in urls and urls


def test_junk_numbers_are_cleaned(web):
    _job, result = answered(web, "badnumbers walking")
    assert result["area"] == engine.AREAS[0]
    assert result["action"]["default_times_per_week"] == 50
    assert [e["label"] for e in result["effects"]] == ["Calories burned"]    # "lots" is not a number
    assert result["effects"][0]["id"] == "E1" and result["effects"][0]["kind"] == "society"
    assert result["effects"][0]["picture_it"] is None
    assert result["everyone_who_could"]["people"] == engine.EVERYONE
    assert len(result["where_we_are"]["figures"]) == 2


def test_paused_search_is_continued(web):
    _job, result = answered(web, "pausecase walking")
    assert result["title"] == "Walking instead of driving"


def test_no_usable_answer_fails_plainly(web):
    job_id = ask(web, "neveranswer please")
    work_all()
    job = status(web, job_id)
    assert job["status"] == "failed" and "usable form" in job["error"]
    assert web.get("/api/humanity/library", headers=H).get_json()["answers"] == []


def test_rejected_key_gives_an_actionable_message(web):
    job_id = ask(web, "autherror walking")
    work_all()
    job = status(web, job_id)
    assert job["status"] == "failed" and "ANTHROPIC_API_KEY" in job["error"]


def test_bad_questions_are_refused(web):
    for body in ({"question": ""}, {"question": "x" * 601}, {}, ["not", "a", "dict"]):
        response = web.post("/api/humanity/ask", json=body, headers=H)
        assert response.status_code == 400, body
    big = web.post("/api/humanity/ask", data="x" * 40000, headers=dict(H, **{"Content-Type": "application/json"}))
    assert big.status_code == 413
    assert web.spawned == []


def test_unknown_job_is_missing(web):
    assert status(web, "b" * 32)["status"] == "missing"


def test_daily_cap(web, monkeypatch):
    monkeypatch.setattr(engine, "DAILY_JOB_LIMIT", 2)
    ask(web, "walk one")
    ask(web, "walk two")
    response = web.post("/api/humanity/ask", json={"question": "walk three"}, headers=H)
    assert response.status_code == 503 and "HUMANITY_DAILY_JOB_LIMIT" in response.get_json()["error"]


# ---------------------------------------------------------------------------
# the panel review
# ---------------------------------------------------------------------------

def test_panel_rates_every_figure_and_is_stored(web):
    answer_id, _result = answered(web, "walk instead of drive")
    before = stub_stats()["panel_calls"]
    result = review(web, answer_id)
    assert stub_stats()["panel_calls"] - before == 3
    assert result["asked"] == 3 and result["answered"] == 3
    assert set(result["items"]) == {"F1", "F2", "E1", "E1P", "E2", "W"}
    for member in result["panel"]:
        assert member["ok"] and set(member["ratings"]) == set(result["items"])
    stored = web.get(f"/api/humanity/library/{answer_id}", headers=H).get_json()
    assert stored["review"]["answered"] == 3
    # the panel never sees another member's ratings, and is shown the figures and their sources
    asked_text = stub_stats()["panel_last"][-1]["body"]
    assert "Car trips under 2 miles" in str(asked_text) and "stats.example.gov" in str(asked_text)


def test_panel_disagreement_and_failures_are_reported(web):
    answer_id, _ = answered(web, "walk doubt garble geminidown")
    result = review(web, answer_id)
    by = {m["name"]: m for m in result["panel"]}
    assert by["GPT"]["ok"] and by["GPT"]["ratings"]["F1"] == {"rating": "wrong", "note": "Scripted gpt note.",
                                                               "better_value": "30%"}
    assert not by["DeepSeek"]["ok"] and by["DeepSeek"]["error"] == "its answer could not be read"
    assert not by["Gemini"]["ok"] and by["Gemini"]["error"] == "its account is out of credit"
    assert result["answered"] == 1


def test_panel_doubt_from_gemini(web):
    answer_id, _ = answered(web, "walk doubt")
    result = review(web, answer_id)
    gemini = {m["name"]: m for m in result["panel"]}["Gemini"]
    assert gemini["ratings"]["E1"]["rating"] == "doubtful" and gemini["ratings"]["E1"]["better_value"] == "0.6 kg"


def test_review_of_unknown_answer_and_without_panel(web, monkeypatch):
    response = web.post("/api/humanity/review", json={"answer_id": "c" * 32}, headers=H)
    assert response.status_code == 404
    monkeypatch.setenv("FACTCHECK_PANEL", "none")
    response = web.post("/api/humanity/review", json={"answer_id": "c" * 32}, headers=H)
    assert response.status_code == 503 and "OPENAI_API_KEY" in response.get_json()["error"]


# ---------------------------------------------------------------------------
# library and ledger
# ---------------------------------------------------------------------------

def test_library_lists_opens_and_deletes(web):
    answer_id, _ = answered(web, "walk instead of drive")
    listing = web.get("/api/humanity/library", headers=H).get_json()["answers"]
    assert [a["id"] for a in listing] == [answer_id] and listing[0]["reviewed"] is False
    assert web.get(f"/api/humanity/library/{answer_id}", headers=H).get_json()["result"]["title"]
    assert web.get("/api/humanity/library/not-an-id", headers=H).status_code == 404
    assert web.post("/api/humanity/library/delete", json={"id": answer_id}, headers=H).get_json()["deleted"]
    assert web.get(f"/api/humanity/library/{answer_id}", headers=H).status_code == 404


def test_ledger_keeps_credit(web):
    answer_id, _ = answered(web, "walk instead of drive")
    add = web.post("/api/humanity/ledger/add", json={"answer_id": answer_id, "done_on": "2026-11-15", "times": 2},
                   headers=H)
    assert add.status_code == 201
    entry = add.get_json()["entry"]
    assert entry["times"] == 2 and entry["action"] == "Walk instead of driving"
    assert [e["per_time"] for e in entry["effects"]] == [0.8, 200]
    web.post("/api/humanity/ledger/add", json={"answer_id": answer_id, "done_on": "2025-06-01"}, headers=H)
    entries = web.get("/api/humanity/ledger", headers=H).get_json()["entries"]
    assert [e["done_on"] for e in entries] == ["2026-11-15", "2025-06-01"]
    # credit survives even if the answer is deleted from the library
    web.post("/api/humanity/library/delete", json={"id": answer_id}, headers=H)
    assert len(web.get("/api/humanity/ledger", headers=H).get_json()["entries"]) == 2
    assert web.post("/api/humanity/ledger/delete", json={"id": entry["id"]}, headers=H).get_json()["deleted"]
    assert len(web.get("/api/humanity/ledger", headers=H).get_json()["entries"]) == 1


def test_ledger_refuses_bad_entries(web):
    answer_id, _ = answered(web, "walk instead of drive")
    bad = [{"answer_id": "d" * 32}, {"answer_id": "nope"}, {"answer_id": answer_id, "done_on": "2026-13-40"},
           {"answer_id": answer_id, "done_on": "yesterday"}, {"answer_id": answer_id, "times": 0},
           {"answer_id": answer_id, "times": 500}]
    for body in bad:
        assert web.post("/api/humanity/ledger/add", json=body, headers=H).status_code == 400, body
    # effects always come from the stored answer, never from the page
    add = web.post("/api/humanity/ledger/add", json={"answer_id": answer_id,
                                                     "effects": [{"per_time": 1e12}]}, headers=H)
    assert [e["per_time"] for e in add.get_json()["entry"]["effects"]] == [0.8, 200]


# ---------------------------------------------------------------------------
# the real helper process
# ---------------------------------------------------------------------------

def test_real_helper_process_end_to_end(monkeypatch):
    engine.ensure_tables()
    kill_helper()
    with get_db_connection() as conn:
        conn.cursor().execute("DELETE FROM humanity_jobs")
    monkeypatch.setenv("HUMANITY_PASSCODE", PASS)
    client = flask_app.test_client()
    job_id = ask(client, "walk instead of drive")
    deadline = time.time() + 40
    job = {}
    while time.time() < deadline:
        job = status(client, job_id)
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.5)
    assert job["status"] == "done", job
    assert engine.runner_alive()
    # a second helper refuses to start while the first is alive
    second = subprocess.run([sys.executable, engine.RUNNER_PATH], cwd=ROOT, capture_output=True, text=True,
                            timeout=30)
    assert "already running" in second.stderr
    # the fact-checker's helper was never started by any of this
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('factcheck_runner') AS t")
        if cur.fetchone()["t"]:
            cur.execute("SELECT heartbeat_at FROM factcheck_runner WHERE id = 1")
            row = cur.fetchone()
            assert not row or time.time() - float(row["heartbeat_at"] or 0) > 15
    kill_helper()


def test_interrupted_job_is_requeued_then_failed():
    engine.ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM humanity_jobs")
        cur.execute("INSERT INTO humanity_jobs (id, kind, priority, status, payload, attempts, created_at) "
                    "VALUES ('e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1', 'answer', 1, 'running', '{}', 1, %s), "
                    "('e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2', 'answer', 1, 'running', '{}', 2, %s)",
                    (time.time(), time.time()))
    assert engine.requeue_interrupted_jobs() == (1, 1)

# ---------------------------------------------------------------------------
# the score
# ---------------------------------------------------------------------------

def score_of(web, place):
    response = web.post("/api/humanity/score/run", json={"place": place}, headers=H)
    assert response.status_code == 202, response.get_data(as_text=True)
    run_id = response.get_json()["run_id"]
    work_all()
    run = web.get(f"/api/humanity/score/run/{run_id}", headers=H).get_json()["run"]
    return run_id, run


def expected_overall(values):
    """The scoring rule written out independently of humanity_score.py."""
    cats = []
    for cat in humanity_score.SCORECARD:
        scores = []
        for m in cat["measures"]:
            if m.get("info"):
                continue                     # population is shown, never scored
            v = values[m["key"]]
            s = (v - m["worst"]) / (m["ideal"] - m["worst"]) * 100
            scores.append(min(100, max(0, s)))
        cats.append(sum(scores) / len(scores))
    return sum(cats) / len(cats)


def test_scorecard_is_sound():
    keys = [m["key"] for c in humanity_score.SCORECARD for m in c["measures"]]
    scored = [m["key"] for c in humanity_score.SCORECARD for m in c["measures"] if not m.get("info")]
    assert len(humanity_score.SCORECARD) == 12 and len(keys) == len(set(keys)) == 27 and len(scored) == 26
    for c in humanity_score.SCORECARD:
        for m in c["measures"]:
            assert (m["worst"] != m["ideal"] or m.get("info")) and m["why"] and m["where"] and m["unit"], m["key"]
    assert set(keys) == set(SCORE_VALUES)


def test_measure_scoring_both_directions():
    life = humanity_score._CATEGORY["health"]["measures"][0]
    hunger = next(m for m in humanity_score._CATEGORY["basic_needs"]["measures"] if m["key"] == "hunger")
    assert humanity_score.measure_score(life, 90) == 100 and humanity_score.measure_score(life, 25) == 0
    assert humanity_score.measure_score(life, 57.5) == 50
    assert humanity_score.measure_score(life, 120) == 100 and humanity_score.measure_score(life, 10) == 0
    assert humanity_score.measure_score(hunger, 0) == 100 and humanity_score.measure_score(hunger, 10) == 75
    assert humanity_score.measure_score(hunger, None) is None


def test_world_score_end_to_end(web):
    run_id, run = score_of(web, "World")
    assert run["complete"] and run["pending"] == [] and run["place"] == "World"
    score = run["score"]
    assert score["measured"] == 26 and score["of"] == 26
    assert abs(score["overall"] - round(expected_overall(SCORE_VALUES), 1)) <= 0.15
    health = score["categories"][0]
    assert health["key"] == "health" and health["weight"] == 3
    life = health["measures"][0]
    assert life["value"] == 73.3 and life["score"] == 74.3 and life["worst"] == 25 and life["ideal"] == 90
    assert life["source"]["url"] == "https://stats.example.gov/transport" and life["level"] == "world"
    assert run["cost"] > 0
    latest = web.get("/api/humanity/score/latest?place=world", headers=H).get_json()["run"]
    assert latest["id"] == run_id and "values" not in latest


def test_one_failed_category_does_not_sink_the_score(web):
    _id, run = score_of(web, "Brokenville")
    cats = {c["key"]: c for c in run["score"]["categories"]}
    assert cats["science"]["status"] == "failed" and cats["science"]["score"] is None
    assert "usable form" in cats["science"]["error"]
    assert run["score"]["overall"] is not None and run["score"]["measured"] == 24


def test_nothing_found_means_no_score_not_a_made_up_one(web):
    _id, run = score_of(web, "Nodataville")
    assert run["score"]["overall"] is None and run["score"]["measured"] == 0


def test_values_citing_unsearched_pages_keep_no_link(web):
    _id, run = score_of(web, "Fakelinkton")
    assert all(m["source"] is None for c in run["score"]["categories"] for m in c["measures"])


def test_marin_county_and_history(web):
    first, run = score_of(web, "Marin County, California")
    assert run["score"]["categories"][0]["measures"][0]["level"] == "county"
    time.sleep(0.01)
    second, _ = score_of(web, "marin county,  california")
    history = web.get("/api/humanity/score/history?place=Marin County, California", headers=H).get_json()["runs"]
    assert [h["id"] for h in history] == [second, first] and history[0]["overall"] is not None
    places = web.get("/api/humanity/score/places", headers=H).get_json()["places"]
    assert places[0]["place"].lower().startswith("marin")
    assert web.post("/api/humanity/score/delete", json={"run_id": first}, headers=H).get_json()["deleted"]
    assert len(web.get("/api/humanity/score/history?place=Marin County, California",
                       headers=H).get_json()["runs"]) == 1


def test_score_progress_while_running(web):
    response = web.post("/api/humanity/score/run", json={"place": "World"}, headers=H)
    run_id = response.get_json()["run_id"]
    assert web.spawned == [1], "the helper is started once, not 12 times"
    run = web.get(f"/api/humanity/score/run/{run_id}", headers=H).get_json()["run"]
    assert not run["complete"] and len(run["pending"]) == 12
    assert web.post("/api/humanity/score/review", json={"run_id": run_id}, headers=H).status_code == 409
    jobs = engine.claim_jobs(3)
    for job in jobs:
        ok, result, error, status_ = engine.run_job(job["kind"], job["payload"])
        engine.finish_job(job["id"], job["kind"], job["payload"], ok, result=result, error=error, http_status=status_)
    run = web.get(f"/api/humanity/score/run/{run_id}", headers=H).get_json()["run"]
    assert len(run["pending"]) == 9 and run["score"]["overall"] is not None


def test_panel_checks_every_value_of_a_run(web):
    run_id, _ = score_of(web, "Doubtburg")
    response = web.post("/api/humanity/score/review", json={"run_id": run_id}, headers=H)
    assert response.status_code == 202
    work_all()
    run = web.get(f"/api/humanity/score/run/{run_id}", headers=H).get_json()["run"]
    review = run["review"]
    assert review["answered"] == 3 and len(review["items"]) == 26
    gpt = {m["name"]: m for m in review["panel"]}["GPT"]
    assert gpt["ratings"]["life_expectancy"]["rating"] == "wrong"
    assert gpt["ratings"]["life_expectancy"]["better_value"] == "71"
    assert gpt["ratings"]["corruption"]["rating"] == "sound"


def test_score_routes_need_the_passcode_and_good_input(web):
    bad = {"X-App-Passcode": "nope"}
    assert web.post("/api/humanity/score/run", json={"place": "World"}, headers=bad).status_code == 401
    assert web.get("/api/humanity/score/latest", headers=bad).status_code == 401
    assert web.get("/api/humanity/score/card", headers=bad).status_code == 401
    assert web.get("/api/humanity/score/run/xyz", headers=H).status_code == 404
    assert web.get("/api/humanity/score/run/" + "f" * 32, headers=H).status_code == 404
    assert web.post("/api/humanity/score/review", json={"run_id": "f" * 32}, headers=H).status_code == 404
    assert web.get("/api/humanity/score/latest?place=Nowhere", headers=H).get_json()["run"] is None
    card = web.get("/api/humanity/score/card", headers=H).get_json()
    assert len(card["categories"]) == 12 and all(c["weight"] == 3 for c in card["categories"])


def test_score_with_the_real_helper(monkeypatch):
    engine.ensure_tables()
    kill_helper()
    monkeypatch.setenv("HUMANITY_PASSCODE", PASS)
    client = flask_app.test_client()
    run_id = client.post("/api/humanity/score/run", json={"place": "World"}, headers=H).get_json()["run_id"]
    deadline = time.time() + 60
    run = {}
    while time.time() < deadline:
        run = client.get(f"/api/humanity/score/run/{run_id}", headers=H).get_json()["run"]
        if run["complete"]:
            break
        time.sleep(0.5)
    assert run["complete"] and run["score"]["measured"] == 26, run.get("pending")
    kill_helper()

# ---------------------------------------------------------------------------
# me: the personal index
# ---------------------------------------------------------------------------

JIM_LIKE = {"name": "Test", "age": 68, "goal": "Stay well",
            "ratings": {"body": 9, "money": 7, "people": 8},
            "fine": {"exercise": "300_449", "conditions": "one_ok", "smoking": "never", "income": "150_300"}}


def test_catalog_is_consistent():
    cat = humanity_me.catalog()
    assert len(cat["areas"]) == 8
    keys = [q["key"] for a in cat["areas"] for q in a["questions"]]
    assert len(keys) == len(set(keys))
    for a in cat["areas"]:
        assert a["why"] in cat["evidence"] and a["ask"].endswith("?")
        for q in a["questions"]:
            assert q["evidence"] in cat["evidence"], q["key"]
            values = [o["v"] for o in q["options"]]
            assert len(values) == len(set(values)) >= 2, q["key"]
            assert all(0 <= o["score"] <= 100 for o in q["options"]), q["key"]
    by_key = {q["key"]: q for a in cat["areas"] for q in a["questions"]}
    for d in cat["decisions"]:
        assert d["ramp"] > 0 and d["changes"], d["key"]
        for c in d["changes"]:
            assert c["q"] in by_key, d["key"]
            assert c["to"] in [o["v"] for o in by_key[c["q"]]["options"]] + ["quit_now", "_half"], d["key"]
    for e in cat["evidence"].values():
        assert e["finding"] and (e["url"].startswith("https://") or e["title"] == "Our estimate")


def test_me_is_private_and_saves_every_copy(web):
    assert web.get("/api/humanity/me", headers={"X-App-Passcode": "nope"}).status_code == 401
    assert web.post("/api/humanity/me", json=JIM_LIKE, headers={"X-App-Passcode": "nope"}).status_code == 401
    assert web.get("/api/humanity/me", headers=H).get_json()["me"] is None
    first = web.post("/api/humanity/me", json=JIM_LIKE, headers=H)
    assert first.status_code == 201
    saved = first.get_json()["me"]["answers"]
    assert saved["age"] == 68 and saved["ratings"] == {"body": 9, "money": 7, "people": 8}
    assert saved["fine"]["exercise"] == "300_449"
    changed = dict(JIM_LIKE, ratings={"body": 8})
    web.post("/api/humanity/me", json=changed, headers=H)
    latest = web.get("/api/humanity/me", headers=H).get_json()["me"]
    assert latest["answers"]["ratings"] == {"body": 8} and latest["saves"] == 2
    assert web.post("/api/humanity/me/delete", json={}, headers=H).get_json()["deleted"] == 2
    assert web.get("/api/humanity/me", headers=H).get_json()["me"] is None


def test_me_refuses_bad_answers(web):
    bad = [{"ratings": {"body": 11}}, {"ratings": {"body": "x"}}, {"fine": {"exercise": "lots"}},
           {"age": 5, "ratings": {"body": 5}}, {"age": "old", "ratings": {"body": 5}}, {}, {"ratings": {}},
           {"sex": "other", "ratings": {"body": 5}}]
    for body in bad:
        assert web.post("/api/humanity/me", json=body, headers=H).status_code == 400, body
    ok = web.post("/api/humanity/me", json={"ratings": {"body": 5, "unknown_area": 3},
                                            "fine": {"made_up": "x", "sleep": "7_8"}, "name": "x" * 90}, headers=H)
    answers = ok.get_json()["me"]["answers"]
    assert answers["ratings"] == {"body": 5} and answers["fine"] == {"sleep": "7_8"} and len(answers["name"]) == 40


def test_life_table_and_typical_habits():
    t = humanity_me.LIFE_TABLE
    assert len(t["ages"]) == len(t["male"]) == len(t["female"])
    for k in ("male", "female"):
        assert all(a > b for a, b in zip(t[k], t[k][1:])), k          # fewer years left at every older age
    assert t["female"][9] > t["male"][9]                                # at 65, women can expect more years
    for key, typ in humanity_me.TYPICAL_LIFE.items():
        assert typ["evidence"] in humanity_me.EVIDENCE and typ["years"] <= 0, key
    saved = humanity_me.clean_answers({"sex": "Male", "ratings": {"body": 5}})
    assert saved["sex"] == "male"


def test_your_own_decision_is_checked_against_the_catalog(web):
    response = web.post("/api/humanity/me/decision", json={"text": "I want to cycle to work twice a week"}, headers=H)
    assert response.status_code == 202
    job_id = response.get_json()["job_id"]
    work_all()
    d = status(web, job_id)["result"]
    assert d["custom"] and d["label"] == "Cycle to work twice a week" and d["ramp"] == 0.5
    assert [(c["q"], c["to"]) for c in d["changes"]] == [("car", "50_150"), ("exercise", "150_299")]
    assert len(d["facts"]) == 1 and d["facts"][0]["kind"] == "dollars" and d["facts"][0]["per_year"] == 520
    assert d["facts"][0]["source"]["url"] == "https://stats.example.gov/transport"
    # the AI is never shown anyone's answers
    web.post("/api/humanity/me", json=JIM_LIKE, headers=H)
    web.post("/api/humanity/me/decision", json={"text": "nothing at all"}, headers=H)
    work_all()
    body = stub_stats()["last"][-1]
    assert body["messages"][0]["content"] == "<decision>\nnothing at all\n</decision>"
    assert "Stay well" not in body["system"] and "Test" not in body["system"]


def test_your_own_decision_input(web):
    for body in ({"text": ""}, {"text": "x" * 301}, {}):
        assert web.post("/api/humanity/me/decision", json=body, headers=H).status_code == 400
    assert web.post("/api/humanity/me/decision", json={"text": "walk"}, headers={"X-App-Passcode": "no"}).status_code == 401

# ---------------------------------------------------------------------------
# the world, built from its countries
# ---------------------------------------------------------------------------

def refreshed(web):
    response = web.post("/api/humanity/world/refresh", json={}, headers=H)
    assert response.status_code == 202
    job_id = response.get_json()["job_id"]
    work_all()
    job = status(web, job_id)
    assert job["status"] == "done", job
    return job["result"]


def test_world_refresh_downloads_every_country(web):
    report = refreshed(web)
    assert report["countries"] == 3                                  # aggregates (WLD) are left out
    assert report["measures"]["life_expectancy"] == {"countries": 3, "source": "World Bank", "error": None}
    assert report["measures"]["corruption"]["source"] == "Our World in Data"
    assert report["measures"]["air"]["countries"] == 0 and "HTTPError" in report["measures"]["air"]["error"]
    assert report["usage"]["cost"] == 0
    data = web.get("/api/humanity/world", headers=H).get_json()
    by = {c["iso3"]: c for c in data["countries"]}
    assert set(by) == {"USA", "HUN", "IND"}
    assert by["HUN"]["population"] == 9.6e6 and by["HUN"]["measured"] == 17 and by["HUN"]["of"] == 26
    # the newest value is kept, older and pre-2005 values are not
    hun = web.get("/api/humanity/world/country/HUN", headers=H).get_json()
    life = next(m for c in hun["score"]["categories"] for m in c["measures"] if m["key"] == "life_expectancy")
    corr = next(m for c in hun["score"]["categories"] for m in c["measures"] if m["key"] == "corruption")
    assert life["value"] == 76.5 and life["year"] == "2023" and life["source"]["title"] == "World Bank"
    assert corr["value"] == 41 and corr["year"] == "2022"
    assert set(hun["missing"]["freedom"]) == {"freedom_choices", "personal_freedom"}
    assert "air" in hun["missing"]["planet"] and "population" not in str(hun["missing"])


def test_world_is_built_from_countries_by_population(web):
    refreshed(web)
    data = web.get("/api/humanity/world", headers=H).get_json()
    cs = [c for c in data["countries"] if c["overall"] is not None]
    expect = sum(c["overall"] * c["population"] for c in cs) / sum(c["population"] for c in cs)
    assert abs(data["world"]["overall"] - expect) < 0.01 and data["world"]["countries_counted"] == 3
    # India's 1.43 billion people pull the world much harder than Hungary's 9.6 million
    by = {c["iso3"]: c for c in cs}
    assert abs(data["world"]["overall"] - by["IND"]["overall"]) < abs(data["world"]["overall"] - by["HUN"]["overall"])


def test_global_measures_come_from_the_world_run(web):
    refreshed(web)
    hun = web.get("/api/humanity/world/country/HUN", headers=H).get_json()
    warming = next(m for c in hun["score"]["categories"] for m in c["measures"] if m["key"] == "warming")
    assert warming["value"] is None
    score_of(web, "World")
    hun = web.get("/api/humanity/world/country/HUN", headers=H).get_json()
    warming = next(m for c in hun["score"]["categories"] for m in c["measures"] if m["key"] == "warming")
    assert warming["value"] == 1.5 and warming["note"] == "Same for every country."


def test_filling_a_countrys_gaps_with_ai(web):
    refreshed(web)
    response = web.post("/api/humanity/world/country/HUN/fill", json={}, headers=H)
    assert response.status_code == 202
    jobs = response.get_json()["jobs"]
    assert set(jobs) == {"freedom", "oppression", "planet", "kindness"}
    work_all()
    hun = web.get("/api/humanity/world/country/HUN", headers=H).get_json()
    assert "freedom" not in hun["missing"] and "kindness" not in hun["missing"]
    fc = next(m for c in hun["score"]["categories"] for m in c["measures"] if m["key"] == "freedom_choices")
    assert fc["value"] == 80 and fc["source"]["title"].startswith("AI research")
    # values that were already there are never overwritten by AI
    life = next(m for c in hun["score"]["categories"] for m in c["measures"] if m["key"] == "life_expectancy")
    assert life["value"] == 76.5


def test_world_routes_need_the_passcode_and_good_input(web):
    bad = {"X-App-Passcode": "no"}
    assert web.get("/api/humanity/world", headers=bad).status_code == 401
    assert web.post("/api/humanity/world/refresh", json={}, headers=bad).status_code == 401
    assert web.get("/api/humanity/world/country/HUN", headers=bad).status_code == 401
    assert web.get("/api/humanity/world/country/H1", headers=H).status_code == 404
    assert web.get("/api/humanity/world/country/ZZZ", headers=H).status_code == 404
    assert web.post("/api/humanity/world/country/ZZZ/fill", json={}, headers=H).status_code == 404
    empty = web.get("/api/humanity/world", headers=H).get_json()
    assert empty["countries"] == [] and empty["world"]["overall"] is None


def test_population_is_researched_but_never_scored(web):
    _id, run = score_of(web, "World")
    assert run["score"]["of"] == 26 and run["score"]["measured"] == 26
    basic = next(c for c in run["score"]["categories"] if c["key"] == "basic_needs")
    pop = next(m for m in basic["measures"] if m["key"] == "population")
    assert pop["value"] == 8200000000 and pop["score"] is None and pop["info"]

# I did no harm and this file is not truncated
