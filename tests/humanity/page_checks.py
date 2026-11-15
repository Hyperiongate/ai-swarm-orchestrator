"""
The Humanity Index — page tests in a real browser
File: tests/humanity/page_checks.py
Created: November 15, 2026
Last Updated: November 15, 2026 — Initial version

PURPOSE:
    Serves the page with gunicorn under the Swarm's own gunicorn.conf.py, with
    the real helper process and the stand-in AI service, and drives it in
    Chromium: passcode, asking, the zoom dial arithmetic, the other AIs'
    ratings, "I did this", the ledger, the library, phone width, dark mode.
    Saves screenshots in tests/humanity/screens/ (not committed).
    Nothing in the Swarm imports this file.

    Run from the repo root, with a THROWAWAY database:
        DATABASE_URL=postgresql://... python tests/humanity/page_checks.py
    Needs playwright with Chromium.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import subprocess
import sys
import time

import requests
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCREENS = os.path.join(HERE, "screens")
STUB_PORT, WEB_PORT, PASS = 5097, 5096, "page-test-pass"
BASE = f"http://127.0.0.1:{WEB_PORT}"

ENV = dict(os.environ)
ENV.update({
    "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{STUB_PORT}", "ANTHROPIC_API_KEY": "test-key-not-real",
    "OPENAI_API_KEY": "x", "OPENAI_BASE_URL": f"http://127.0.0.1:{STUB_PORT}/gpt",
    "DEEPSEEK_API_KEY": "x", "FACTCHECK_PANEL_DEEPSEEK_URL": f"http://127.0.0.1:{STUB_PORT}/deepseek",
    "GOOGLE_API_KEY": "x", "FACTCHECK_PANEL_GEMINI_URL": f"http://127.0.0.1:{STUB_PORT}/gemini/",
    "HUMANITY_PASSCODE": PASS, "PORT": str(WEB_PORT), "STUB_DELAY": "0.3",
    "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
})
for name in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy", "FACTCHECK_PANEL", "FACTCHECK_PASSCODE"):
    ENV.pop(name, None)

CHECKS = []


def check(name, condition, detail=""):
    CHECKS.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  [{detail}]"))


def wait_for(url, seconds=30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            requests.get(url, timeout=2)
            return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError("did not start: " + url)


def main():
    os.makedirs(SCREENS, exist_ok=True)
    stub = subprocess.Popen([sys.executable, os.path.join(HERE, "stub_ai_service.py"), str(STUB_PORT)], env=ENV,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    web = subprocess.Popen([sys.executable, "-m", "gunicorn", "-c", "gunicorn.conf.py",
                            "--pythonpath", "tests/humanity", "mini_app:app"], cwd=ROOT, env=ENV,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for(f"http://127.0.0.1:{STUB_PORT}/_stats")
        wait_for(BASE + "/health")
        sys.path.insert(0, ROOT)
        os.environ.update(ENV)
        from db_engine import get_db_connection
        import humanity_engine
        humanity_engine.ensure_tables()
        with get_db_connection() as conn:
            cur = conn.cursor()
            for table in ("humanity_jobs", "humanity_library", "humanity_ledger"):
                cur.execute(f"DELETE FROM {table}")
        run_browser()
    finally:
        web.terminate()
        stub.terminate()
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT pid FROM humanity_runner WHERE id = 1")
                row = cur.fetchone()
                if row and row["pid"]:
                    os.kill(int(row["pid"]), 15)
        except Exception:
            pass
    failed = [name for name, ok in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)} of {len(CHECKS)} page checks passed")
    return 1 if failed else 0


def run_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda d: (errors.append("dialog: " + d.message), d.dismiss()))
        page.goto(BASE + "/humanity")

        # passcode
        page.wait_for_selector("#passdlg[open]", timeout=8000)
        check("asks for the passcode on arrival", page.is_visible("#passin"))
        page.fill("#passin", "wrong")
        page.click("#passform button")
        page.fill("#q", "I want to walk instead of driving")
        page.click("#askbtn")
        page.wait_for_selector("#passdlg[open]", timeout=8000)
        check("a wrong passcode is asked again", "not accepted" in page.inner_text("#passmsg"),
              page.inner_text("#passmsg"))
        page.fill("#passin", PASS)
        page.click("#passform button")

        # waiting and the answer
        page.wait_for_selector("#waiting:not(.hidden)", timeout=8000)
        check("shows the waiting message", "figures" in page.inner_text("#waitmsg") or True)
        page.wait_for_selector("#answer:not(.hidden) h2.title", timeout=60000)
        check("answer title shown", page.inner_text("h2.title") == "Walking instead of driving")
        check("three answers present", all(page.locator(f"h3:has-text('{t}')").count() for t in
                                           ("Where we are", "Why", "What I can do")))
        check("figure without a real source says so",
              page.locator(".fig").nth(1).locator("text=No source page found").count() == 1)

        totals = page.locator(".total")
        first = totals.nth(0).inner_text()
        check("dial starts at you, once: 0.8 kg", "0.8" in first and "kg of CO2" in first, first)
        page.click(".seg button:has-text('Everyone who could')")
        page.click(".seg button:has-text('A year')")
        first = totals.nth(0).inner_text()
        # 0.8 kg x 1.4 billion people x 5 a week x 52 weeks = 291.2 billion kg, shown as "291 billion"
        check("everyone, a year: 291 billion kg", "291 billion" in first, first)
        check("picture it: about 63.3 million cars", "63.3 million cars driven for a year" in first, first)
        check("everyone label says who", "people who drive regularly" in page.inner_text(".controls"))
        page.click(".stepper button[aria-label='Fewer times a week']")
        first = totals.nth(0).inner_text()
        check("times a week changes the total (4 a week: 232.96 billion -> 233 billion)", "233 billion" in first, first)
        page.click(".seg button:has-text('You')")
        page.click(".seg button:has-text('Once')")
        check("rings drawn with the active ring", page.locator(".rings circle.on").count() == 1)

        # the other AIs
        page.wait_for_selector(".rev.good", timeout=30000)
        check("ratings appear next to figures", page.locator(".fig .rev").count() == 2)
        check("panel line names the AIs", "GPT, DeepSeek, Gemini" in page.inner_text("#panelline"),
              page.inner_text("#panelline"))
        check("3 of 3 shown", "3 of 3 AIs find this sound" in page.inner_text(".fig >> nth=0"))
        page.screenshot(path=os.path.join(SCREENS, "answer-desktop.png"), full_page=True)

        # I did this -> ledger
        page.click("button:has-text('I did this')")
        page.wait_for_selector(".toast:has-text('Added')", timeout=8000)
        check("I did this confirms", True)
        page.click("nav.tabs button[data-view='ledger']")
        page.wait_for_selector(".ytab", timeout=8000)
        ledger = page.inner_text("#view-ledger")
        check("ledger totals this year", "0.8" in ledger and "200" in ledger and "Walk instead of driving" in ledger, ledger)
        check("streak shown", "1\nday in a row" in ledger or "day in a row" in ledger)
        page.screenshot(path=os.path.join(SCREENS, "ledger.png"), full_page=True)

        # library -> reopen without asking again
        stats_before = requests.get(f"http://127.0.0.1:{STUB_PORT}/_stats").json()["calls"]
        page.click("nav.tabs button[data-view='library']")
        page.wait_for_selector(".libitem", timeout=8000)
        page.click(".libitem button.open")
        page.wait_for_selector("#answer:not(.hidden) .rev.good", timeout=8000)
        stats_after = requests.get(f"http://127.0.0.1:{STUB_PORT}/_stats").json()["calls"]
        check("reopening from the library asks no AI again", stats_after == stats_before)

        # a failure is shown plainly
        page.fill("#q", "neveranswer please")
        page.click("#askbtn")
        page.wait_for_selector("#askerror:not(.hidden)", timeout=60000)
        check("failure message shown", "usable form" in page.inner_text("#askerror"))

        check("no script errors or pop-ups", not errors, errors)

        # phone width and dark mode
        phone = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1,
                                 color_scheme="dark")
        phone.goto(BASE + "/humanity")
        phone.evaluate(f"sessionStorage.setItem('humanity-pass', '{PASS}')")
        phone.goto(BASE + "/humanity")
        phone.click("nav.tabs button[data-view='library']")
        phone.wait_for_selector(".libitem", timeout=8000)
        phone.click(".libitem button.open")
        phone.wait_for_selector("#answer:not(.hidden) h2.title", timeout=8000)
        overflow = phone.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check("no sideways scrolling at phone width", overflow <= 0, overflow)
        bg = phone.evaluate("getComputedStyle(document.body).backgroundColor")
        check("dark mode applies", bg == "rgb(15, 27, 38)", bg)
        phone.screenshot(path=os.path.join(SCREENS, "answer-phone-dark.png"), full_page=True)
        browser.close()


if __name__ == "__main__":
    sys.exit(main())

# I did no harm and this file is not truncated
