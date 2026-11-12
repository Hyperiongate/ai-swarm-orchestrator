"""
Speech Fact-Checker — page tests under the Swarm's real server settings
File: tests/factcheck/test_factcheck_page.py
Created: November 11, 2026
Last Updated: November 11, 2026 — Initial version

PURPOSE:
    Drives the listening page in a real Chrome with a pretend microphone, served
    by gunicorn using the Swarm's own gunicorn.conf.py (2 sync workers,
    max_requests=100), with the real helper process and the stand-in AI service.
    Also proves the point of the design: web workers recycling does not lose
    work. Nothing in the Swarm imports this file.

    Run from the repo root with a THROWAWAY database:
        DATABASE_URL=postgresql://... python tests/factcheck/test_factcheck_page.py
    Optional: FACTCHECK_TEST_GUNICORN=/path/to/gunicorn  (default: "gunicorn")
              SHOTS_DIR=/where/to/put/screenshots

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SHOTS = os.environ.get("SHOTS_DIR", os.path.join(tempfile.gettempdir(), "factcheck-screenshots"))
GUNICORN = os.environ.get("FACTCHECK_TEST_GUNICORN", "gunicorn")
SERVER_PYTHON = os.environ.get("FACTCHECK_TEST_PYTHON", sys.executable)
STUB_PORT = 5098

if not os.environ.get("DATABASE_URL"):
    sys.exit("Set DATABASE_URL to a throwaway PostgreSQL database to run these tests.")
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"

sys.path.insert(0, ROOT)
from db_engine import get_db_connection  # noqa: E402

# A pretend speech recogniser: the test calls window.hear("...") to "say" something.
FAKE_MIC = """
window.__recs = [];
class FakeRec {
  start() { window.__recs.push(this); window.__rec = this; }
  stop() { if (this.onend) this.onend(); }
}
window.SpeechRecognition = FakeRec;
window.webkitSpeechRecognition = FakeRec;
window.hear = (text, interim) => {
  const result = [{ transcript: text }];
  result.isFinal = !interim;
  window.__rec.onresult({ resultIndex: 0, results: [result] });
};
"""

SPEECH = [
    "Thank you all for coming tonight it is wonderful to be here.",
    "Crime fell 12 percent last year.",
    "My opponent said taxes rose 40 percent which is wrong.",
    "The half finished bridge cost 3 billion dollars.",
    "We love this country and we always will and nobody can take that away from us ever.",
    "An unknown number of people around 9 thousand moved here.",
    "Wages are up 5 percent since January.",
]


# ---------------------------------------------------------------------------
# starting and stopping the pieces
# ---------------------------------------------------------------------------

def helper_pid():
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT pid, heartbeat_at FROM factcheck_runner WHERE id = 1")
        row = cur.fetchone()
    return int(row["pid"]) if row and time.time() - row["heartbeat_at"] < 15 else 0


def kill_helper():
    try:
        pid = helper_pid()
        if pid:
            os.kill(pid, signal.SIGKILL)
        with get_db_connection() as conn:
            conn.cursor().execute("UPDATE factcheck_runner SET pid = 0, token = '', heartbeat_at = 0 WHERE id = 1")
    except Exception:
        pass


def start_stub():
    env = dict(os.environ, STUB_DELAY="0.25", STUB_SLOW_SECONDS="8")
    return subprocess.Popen([SERVER_PYTHON, os.path.join(HERE, "stub_ai_service.py"), str(STUB_PORT)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_server(port, log_path, extra_env=None, no_key=False):
    """gunicorn with the Swarm's own gunicorn.conf.py, serving only the fact-checker blueprint."""
    env = dict(os.environ)
    env.pop("FACTCHECK_PASSCODE", None)
    env.update({"PORT": str(port), "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{STUB_PORT}",
                "ANTHROPIC_API_KEY": "test-key-not-real"})
    if no_key:
        env.pop("ANTHROPIC_API_KEY")
    env.update(extra_env or {})
    log = open(log_path, "w")
    proc = subprocess.Popen(
        [GUNICORN, "-c", os.path.join(ROOT, "gunicorn.conf.py"),
         "--pythonpath", HERE, "mini_app:app"],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(80):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return proc
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"gunicorn did not start; see {log_path}")


def call(port, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data,
                                     headers=dict({"Content-Type": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, json.loads(response.read())


def new_page(browser, port, errors, fake_mic=True, **context_args):
    context = browser.new_context(viewport={"width": 1360, "height": 900}, **context_args)
    context.route("**/fonts.googleapis.com/**", lambda route: route.abort())
    context.route("**/fonts.gstatic.com/**", lambda route: route.abort())
    page = context.new_page()
    page.on("pageerror", lambda exc: errors.append("page error: " + str(exc)))
    page.on("console", lambda msg: errors.append("console: " + msg.text)
            if msg.type == "error" and "fonts.g" not in msg.text and "ERR_FAILED" not in msg.text else None)
    if fake_mic:
        page.add_init_script(FAKE_MIC)
    else:
        page.add_init_script("delete window.SpeechRecognition; delete window.webkitSpeechRecognition;"
                             "Object.defineProperty(window, 'webkitSpeechRecognition', {value: undefined});")
    page.goto(f"http://127.0.0.1:{port}/factcheck")
    page.wait_for_load_state("domcontentloaded")
    return page


def check(condition, message, failures):
    print(("  ok    " if condition else "  FAIL  ") + message)
    if not condition:
        failures.append(message)


# ---------------------------------------------------------------------------
# the flows
# ---------------------------------------------------------------------------

def live_flow(browser, port, failures, errors):
    print("Live listening")
    page = new_page(browser, port, errors)
    page.fill("#inSpeaker", "Senator Example")
    page.fill("#inEvent", "Town hall")
    page.click("#btnStart")
    page.wait_for_function("!!window.__rec")
    check(page.inner_text("#bubbleVerdict") == "Listening", "bubble says Listening after Start", failures)
    check(page.is_visible("#btnStop") and not page.is_visible("#btnStart"), "Stop button replaces Start", failures)
    check(page.is_hidden("#progress"), "no progress bar while listening live (the length is unknown)", failures)

    page.evaluate("window.hear('thank you all', true)")
    check("thank you all" in page.inner_text("#transcript"), "words in progress show in the transcript", failures)
    for sentence in SPEECH:
        page.evaluate("text => window.hear(text)", sentence)
        page.wait_for_timeout(150)

    page.wait_for_function("document.querySelectorAll('#claimList li .chip').length >= 5", timeout=40000)
    page.wait_for_function("!document.querySelector('#claimList li.v-checking')", timeout=40000)
    chips = page.eval_on_selector_all("#claimList li .chip", "els => els.map(e => e.textContent)")
    check(sorted(chips) == sorted(["True", "False", "Misleading", "Can’t verify", "True"]),
          f"five claims with the expected verdicts (got {chips})", failures)
    check(page.inner_text("#bubbleVerdict").startswith("True"), "bubble shows the latest verdict", failures)
    check("Wages are up 5 percent" in page.inner_text("#bubbleClaim"), "bubble shows the latest claim", failures)
    check("stats.example.gov" in page.inner_text("#bubbleSources"), "bubble shows the source", failures)
    marks = page.eval_on_selector_all("#transcript mark", "els => els.map(e => e.className + '|' + e.textContent)")
    check(len(marks) == 5 and any(m.startswith("v-false|My opponent said taxes rose 40 percent") for m in marks),
          f"five highlighted passages in the transcript ({len(marks)})", failures)
    check("5 claims checked: 2 true, 1 misleading, 1 false, 1 can’t verify" in page.inner_text("#meterText"),
          "meter sentence counts correctly: " + page.inner_text("#meterText"), failures)
    check("50% of the rated claims are true" in page.inner_text("#meterText"), "meter shows share true", failures)
    page.click("#transcript mark.v-false")
    check(page.is_visible("#claimList li.v-false details[open]"), "clicking a highlight opens its reason", failures)
    check("made-up.example.com" not in page.content(), "a link the search never returned is not shown", failures)
    os.makedirs(SHOTS, exist_ok=True)
    page.screenshot(path=os.path.join(SHOTS, "live.png"), full_page=True)

    before = page.evaluate("window.__recs.length")
    page.evaluate("window.__rec.onend()")
    page.wait_for_timeout(500)
    check(page.evaluate("window.__recs.length") == before + 1,
          "listening restarts itself after the browser stops it", failures)

    page.evaluate("text => window.hear(text)", "And we also flip 7 switches.")
    page.click("#btnStop")
    page.wait_for_selector("#viewReport:not([hidden])", timeout=40000)
    page.wait_for_function("document.getElementById('reportProgress').textContent.includes('complete')",
                           timeout=90000)
    report = page.inner_text("#report")
    check("Senator Example, Town hall" in report, "report is titled with speaker and occasion", failures)
    check("6 claims checked" in report, "report tally counts all six claims", failures)
    check(report.count("1. As stated") == 6 and report.count("5. Context and interests") == 6,
          "every claim card has the five layers", failures)
    check("Changed on recheck" in report, "a verdict changed by the recheck is marked", failures)
    check("whether it was really said or done" in report, "attribution claims are explained", failures)
    check(page.eval_on_selector_all("#report .annotated mark", "els => els.length") == 6,
          "annotated transcript highlights all six claims", failures)
    check("roughly $" in page.inner_text("#usage"), "cost estimate is shown", failures)
    page.screenshot(path=os.path.join(SHOTS, "report.png"), full_page=True)

    with page.expect_download() as info:
        page.click("#btnWord")
    name = info.value.suggested_filename
    check(name.startswith("fact-check-Senator-Example-") and name.endswith(".doc"),
          f"Word download is named sensibly ({name})", failures)

    page.click("#btnNew")
    check(page.is_visible("#viewLive") and page.inner_text("#bubbleVerdict") == "Ready",
          "New speech returns to the start", failures)
    page.click("#btnHistory")
    check("Senator Example, Town hall" in page.inner_text("#historyList"), "the speech is in Saved speeches", failures)
    page.click("#historyList button[data-open]")
    page.wait_for_selector("#viewReport:not([hidden])")
    check("In-depth recheck complete" in page.inner_text("#reportProgress"),
          "a saved speech reopens with its recheck", failures)
    page.context.close()


def paste_flow(browser, port, failures, errors):
    print("Pasted text")
    page = new_page(browser, port, errors, fake_mic=False)
    check("can’t listen" in page.inner_text("#banner"), "a browser without speech recognition is told so", failures)
    page.click("#btnPaste")
    page.fill("#inPaste", " ".join(SPEECH * 6))          # about 390 words: several passages
    # Record every progress message the page shows, so the three steps can be checked afterwards.
    page.evaluate("""() => {
      window.__seen = [];
      setInterval(() => {
        const live = document.getElementById('progress').hidden ? '' : document.getElementById('progressText').textContent;
        const report = document.getElementById('reportProgress').textContent;
        for (const text of [live, report]) if (text && !window.__seen.includes(text)) window.__seen.push(text);
      }, 50);
    }""")
    page.click("#btnPasteGo")
    page.wait_for_selector("#viewReport:not([hidden])", timeout=90000)
    page.wait_for_function("document.getElementById('reportProgress').textContent.includes('complete')",
                           timeout=90000)
    seen = page.evaluate("window.__seen")
    percents = [int(m.group(1)) for text in seen for m in [re.search(r"Step 1 of 3.* (\d+)% read", text)] if m]
    check(len(percents) >= 2 and percents == sorted(percents) and percents[-1] < 100,
          f"step 1 shows the share of the text read, rising ({percents})", failures)
    check(any(text.startswith("Step 2 of 3") for text in seen) or any("Steps 1 and 2 finished" in t for t in seen),
          "step 2 (quick checks) is announced", failures)
    check(any(re.search(r"Step 3 of 3: rechecking each claim in depth\. \d+ of 5 done", t) for t in seen),
          "step 3 shows the in-depth recheck count", failures)
    check(page.is_hidden("#recheckProgress"), "the recheck bar goes away when the recheck is complete", failures)
    report = page.inner_text("#report")
    check("Checked from pasted text" in report, "report says it came from pasted text", failures)
    count = page.eval_on_selector_all("#report .card", "els => els.length")
    check(count == 5, f"repeated claims are counted once ({count} cards)", failures)
    page.context.close()


def narrow_and_dark(browser, port, failures, errors):
    print("Phone width and dark mode")
    page = new_page(browser, port, errors, color_scheme="dark")
    page.set_viewport_size({"width": 390, "height": 800})
    page.click("#btnStart")
    page.wait_for_function("!!window.__rec")
    for sentence in SPEECH:
        page.evaluate("text => window.hear(text)", sentence)
    page.wait_for_function("document.querySelectorAll('#claimList li .chip').length >= 5", timeout=40000)
    page.wait_for_function("!document.querySelector('#claimList li.v-checking')", timeout=40000)
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
    check(not overflow, "no sideways scrolling at phone width", failures)
    page.screenshot(path=os.path.join(SHOTS, "narrow-dark.png"), full_page=True)
    page.context.close()


def failed_check_flow(browser, port, failures, errors):
    print("A check that fails on the server")
    page = new_page(browser, port, [])       # the browser logs nothing here, but keep the list separate
    page.click("#btnStart")
    page.wait_for_function("!!window.__rec")
    page.evaluate("text => window.hear(text)", "The autherror plan cost 4 billion dollars and nobody noticed it at all.")
    page.wait_for_function("document.querySelector('#claimList li.v-error')", timeout=40000)
    text = page.inner_text("#claimList")
    check("Couldn’t check" in text and "rejected the key" in text,
          "a failed check shows the server's plain reason", failures)
    check(page.is_visible("#claimList button[data-retry]"), "a failed check offers Try again", failures)
    page.context.close()


def recycle_flow(port, log_path, failures):
    """The reason for the helper process: web workers recycling must not lose work."""
    print("Web workers recycling (gunicorn max_requests)")
    _, queued = call(port, "/api/factcheck/check", {"claim": "A half truth slowcase 5."})   # stub takes 8s
    job_id = queued["job_id"]
    deadline = time.time() + 20
    while helper_pid() == 0 and time.time() < deadline:
        time.sleep(0.2)
    pid_before = helper_pid()
    bad = 0
    for _ in range(450):                        # far more than max_requests on both workers
        try:
            code, _body = call(port, "/api/factcheck/jobs/status", {"ids": [job_id]})
            bad += code != 200
        except Exception:
            bad += 1
    job = None
    deadline = time.time() + 30
    while time.time() < deadline:
        _, body = call(port, "/api/factcheck/jobs/status", {"ids": [job_id]})
        job = body["jobs"][0]
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.5)
    with open(log_path) as handle:
        restarts = handle.read().count("Autorestarting worker")
    check(restarts >= 2, f"web workers recycled during the job ({restarts} times)", failures)
    check(bad == 0, f"every request during the recycling was answered ({bad} failed)", failures)
    check(job and job["status"] == "done" and job["result"]["verdict"] == "misleading",
          "the job in flight finished normally", failures)
    check(pid_before and helper_pid() == pid_before, "the helper process was not disturbed", failures)
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT attempts FROM factcheck_jobs WHERE id = %s", (job_id,))
        attempts = cur.fetchone()["attempts"]
    check(attempts == 1, f"the job ran once, not twice (attempts = {attempts})", failures)


def passcode_flow(browser, failures, log_dir):
    print("Passcode")
    proc = start_server(5072, os.path.join(log_dir, "gunicorn-passcode.log"),
                        {"FACTCHECK_PASSCODE": "open-sesame"})
    try:
        # The browser logs the expected "401" refusals as console errors; keep them out of the failure list.
        page = new_page(browser, 5072, [])
        page.wait_for_selector("#dlgPass[open]", timeout=5000)
        check(True, "passcode box appears when a passcode is set", failures)
        page.fill("#inPass", "wrong")
        page.click("#passForm button")
        page.click("#btnPaste")
        page.fill("#inPaste", "Crime fell 12 percent last year.")
        page.click("#btnPasteGo")
        page.wait_for_selector("#dlgPass[open]", timeout=5000)
        check(True, "a wrong passcode is asked for again", failures)
        page.fill("#inPass", "open-sesame")
        page.click("#passForm button")
        page.wait_for_selector("#viewReport:not([hidden])", timeout=60000)
        check("1 claim checked" in page.inner_text("#report"), "the right passcode lets the check through", failures)
        page.context.close()
    finally:
        proc.terminate()


def no_key_flow(browser, failures, log_dir):
    print("No AI key")
    proc = start_server(5073, os.path.join(log_dir, "gunicorn-nokey.log"), no_key=True)
    try:
        page = new_page(browser, 5073, [])
        page.wait_for_function("!document.getElementById('banner').hidden", timeout=5000)
        check("ANTHROPIC_API_KEY" in page.inner_text("#banner"), "missing key is explained on the page", failures)
        page.context.close()
    finally:
        proc.terminate()


def main():
    failures, errors = [], []
    log_dir = tempfile.mkdtemp(prefix="factcheck-logs-")
    main_log = os.path.join(log_dir, "gunicorn.log")
    kill_helper()
    stub = start_stub()
    proc = start_server(5071, main_log)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            live_flow(browser, 5071, failures, errors)
            paste_flow(browser, 5071, failures, errors)
            narrow_and_dark(browser, 5071, failures, errors)
            failed_check_flow(browser, 5071, failures, errors)
            recycle_flow(5071, main_log, failures)
            passcode_flow(browser, failures, log_dir)
            no_key_flow(browser, failures, log_dir)
            browser.close()
    finally:
        proc.terminate()
        stub.terminate()
        kill_helper()
    for line in errors:
        print("  FAIL  " + line)
    failures.extend(errors)
    print(f"\nServer logs: {log_dir}")
    print("ALL PAGE CHECKS PASSED" if not failures else f"{len(failures)} PROBLEM(S)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

# I did no harm and this file is not truncated
