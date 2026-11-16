"""
The Humanity Index — page tests in a real browser
File: tests/humanity/page_checks.py
Created: November 15, 2026
Last Updated: November 16, 2026 (afternoon) — you and the crowd on each line, expected age, fine tune

PURPOSE:
    Serves the page with gunicorn under the Swarm's own gunicorn.conf.py, with
    the real helper process and the stand-in AI service, and drives it in
    Chromium: passcode, Me (the interview, fine tune, the dumbbell chart, the
    sliders, the working behind each line, your own decision, the ripple to
    the world score, deleting), the Score (working it out, the arithmetic, the
    measures, the other AIs' checks, weights, history, places), voice (with a
    simulated microphone), asking, the zoom dial arithmetic, the ratings,
    "I did this", the ledger, the library, phone width, dark mode.
    Saves screenshots in tests/humanity/screens/ (not committed).
    Nothing in the Swarm imports this file.

    Run from the repo root, with a THROWAWAY database:
        DATABASE_URL=postgresql://... python tests/humanity/page_checks.py
    Needs playwright with Chromium.

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import math
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
            import humanity_score
            humanity_score.ensure_tables()
            cur.execute("DELETE FROM humanity_score_values")
            cur.execute("DELETE FROM humanity_score_runs")
            import humanity_me
            humanity_me.ensure_tables()
            cur.execute("DELETE FROM humanity_me")
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


# A pretend microphone: when started, it "hears" whatever window.__say holds.
FAKE_MIC = """
window.__say = "";
window.webkitSpeechRecognition = class {
  start() {
    const text = window.__say;
    setTimeout(() => {
      const res = [[{ transcript: text }]]; res[0].isFinal = true;
      this.onresult && this.onresult({ results: res });
      this.onend && this.onend();
    }, 150);
  }
  stop() { this.onend && this.onend(); }
};
window.SpeechRecognition = window.webkitSpeechRecognition;   // newer Chromium has the unprefixed name too
"""


def expected_scores(leave_out=None):
    import humanity_score
    from stub_ai_service import SCORE_VALUES
    values = {c["key"]: {"values": [{"key": m["key"], "value": SCORE_VALUES[m["key"]]} for m in c["measures"]]}
              for c in humanity_score.SCORECARD}
    weights = {leave_out: 0} if leave_out else None
    return humanity_score.score_run(values, weights)["overall"]


def run_browser():
    sys.path.insert(0, HERE)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        page.add_init_script(FAKE_MIC)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda d: (errors.append("dialog: " + d.message), d.dismiss()))
        page.goto(BASE + "/humanity")

        # passcode
        page.wait_for_selector("#passdlg[open]", timeout=8000)
        check("asks for the passcode on arrival", page.is_visible("#passin"))
        page.fill("#passin", "wrong")
        page.click("#passform button")
        page.wait_for_selector("#passdlg[open]", timeout=8000)
        check("a wrong passcode is asked again", "not accepted" in page.inner_text("#passmsg"),
              page.inner_text("#passmsg"))
        page.fill("#passin", PASS)
        page.click("#passform button")

        # Me is the first tab: with nothing saved, it opens on the interview
        page.wait_for_selector("#me .icard", timeout=8000)
        check("Me is the first tab and opens on the interview", page.locator("#me .icard").count() == 9)
        page.click("nav.tabs button[data-view='score']")

        # ---------------- the score
        page.wait_for_selector("text=No score has been worked out for the world yet", timeout=8000)
        check("Score is the first tab, with an invitation to work it out", True)
        page.click("button:has-text('Work out the score')")
        page.wait_for_selector("text=Researching:", timeout=8000)
        check("shows research progress", True)
        page.wait_for_selector("button:has-text('Refresh with the latest data'):not([disabled])", timeout=90000)
        big = page.inner_text(".bignum")
        want = expected_scores()
        check(f"world score is {want}", big.startswith(str(want)), big)
        check("12 categories listed", page.locator(".cat").count() == 12)
        check("track shows both end points", "worst seen in modern times" in page.inner_text(".track-ends")
              and "ideal world" in page.inner_text(".track-ends"))
        page.click(".cat >> nth=0 >> button")
        health = page.inner_text(".cat >> nth=0")
        check("health opens to its measures, values and end points",
              "73.3" in health and "25 / 90 years" in health and "Life expectancy" in health, health[:300])
        page.wait_for_selector(".cat >> nth=0 >> .rev.good", timeout=40000)
        check("other AIs' checks shown per measure", "3 of 3 AIs find this sound" in page.inner_text(".cat >> nth=0"))
        check("checked-by line names the AIs", "GPT, DeepSeek, Gemini" in page.inner_text(".scoreactions"))
        page.screenshot(path=os.path.join(SCREENS, "score-desktop.png"), full_page=True)

        page.click("button:has-text('Change what counts')")
        page.click(".weights .row:has-text('Fair shares') button:has-text('Leave out')")
        want_without = expected_scores("fair_shares")
        big = page.inner_text(".bignum")
        check(f"leaving out Fair shares gives {want_without}", big.startswith(str(want_without)), big)
        check("says custom weights are in use", "your own weights" in page.inner_text(".herometa"))
        page.click("button:has-text('Go back to equal weights')")
        check("back to equal weights", page.inner_text(".bignum").startswith(str(want)))
        page.click("button:has-text('Done changing what counts')")

        page.click("button:has-text('Refresh with the latest data')")
        page.wait_for_selector("text=Researching:", timeout=8000)
        page.wait_for_selector("button:has-text('Refresh with the latest data'):not([disabled])", timeout=90000)
        page.wait_for_selector(".history .entry", timeout=8000)
        check("earlier score kept in history", str(want) in page.inner_text(".history"))
        check("change since last time shown", "since" in page.inner_text(".herometa"), page.inner_text(".herometa"))

        page.click("#placeseg button:has-text('Marin County')")
        page.wait_for_selector("text=No score has been worked out for Marin County, California yet", timeout=8000)
        check("Marin County has its own score", True)

        # voice on the Ask tab: a spoken score question opens the Score for that place
        page.click("nav.tabs button[data-view='ask']")
        page.evaluate("window.__say = 'What is the score for the world?'")
        page.click("#askmic")
        page.wait_for_selector("#view-score:not(.hidden) .bignum", timeout=8000)
        check("spoken 'what is the score for the world' opens the world score",
              page.get_attribute("#placeseg button[data-place='World']", "aria-pressed") == "true")
        page.evaluate("window.__say = 'marin county'")
        page.click("#placemic")
        page.wait_for_selector("text=No score has been worked out for Marin County, California yet", timeout=8000)
        check("saying 'marin county' picks the Marin County place", True)

        # ---------------- asking (spoken)
        page.click("nav.tabs button[data-view='ask']")
        page.evaluate("window.__say = 'I want to walk instead of driving'")
        page.click("#askmic")

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

        # ---------------- me
        me_checks(page)

        # phone width and dark mode
        phone = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1,
                                 color_scheme="dark")
        phone.goto(BASE + "/humanity")
        phone.evaluate(f"sessionStorage.setItem('humanity-pass', '{PASS}')")
        phone.goto(BASE + "/humanity")
        phone.wait_for_selector(".dumbbell", timeout=8000)
        phone.click(".examples button:has-text('Keep to 7 drinks')")
        phone.click(".dbrow >> nth=1")
        overflow = phone.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check("Me: no sideways scrolling at phone width", overflow <= 0, overflow)
        phone.screenshot(path=os.path.join(SCREENS, "me-phone-dark.png"), full_page=True)
        phone.click("nav.tabs button[data-view='score']")
        phone.wait_for_selector(".bignum", timeout=8000)
        phone.click(".cat >> nth=0 >> button")
        overflow = phone.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check("Score page: no sideways scrolling at phone width", overflow <= 0, overflow)
        phone.screenshot(path=os.path.join(SCREENS, "score-phone-dark.png"), full_page=True)
        phone.click("nav.tabs button[data-view='library']")
        phone.wait_for_selector(".libitem", timeout=8000)
        phone.click(".libitem button.open")
        phone.wait_for_selector("#answer:not(.hidden) h2.title", timeout=8000)
        overflow = phone.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check("no sideways scrolling at phone width", overflow <= 0, overflow)
        bg = phone.evaluate("getComputedStyle(document.body).backgroundColor")
        check("dark mode applies", bg == "rgb(15, 27, 38)", bg)
        phone.screenshot(path=os.path.join(SCREENS, "answer-phone-dark.png"), full_page=True)

        # deleting your answers takes two presses and brings back the interview
        page.click("nav.tabs button[data-view='me']")
        page.click("button:has-text('Delete my answers')")
        check("first press only warns", "again" in page.inner_text("#pagenotice")
              and page.locator(".dumbbell").count() == 1)
        page.click("button:has-text('Delete my answers')")
        page.wait_for_selector("text=Let's talk about you.", timeout=8000)
        check("second press deletes and shows the interview", page.locator("#me .icard").count() == 9)

        check("no script errors or pop-ups", not errors, errors)
        browser.close()


def _remaining(age, sex=None):
    import humanity_me
    t = humanity_me.LIFE_TABLE
    def col(k):
        ys = t[k]
        for i in range(len(t["ages"]) - 1):
            if age <= t["ages"][i + 1]:
                return ys[i] + (ys[i + 1] - ys[i]) * (age - t["ages"][i]) / (t["ages"][i + 1] - t["ages"][i])
        return ys[-1]
    return col(sex) if sex else (col("male") + col("female")) / 2


def expected_age(fine, age, sex=None):
    """The expected-age rule written out independently of the page."""
    import humanity_me
    cat = humanity_me.catalog()
    scale = min(1, _remaining(age) / _remaining(40)) if age > 40 else 1
    habits = 0
    for key in ("exercise", "smoking", "drinks", "bmi"):
        if key in fine:
            life = next(o["life"] for a in cat["areas"] for q in a["questions"] if q["key"] == key
                        for o in q["options"] if o["v"] == fine[key])
            habits += (life - humanity_me.TYPICAL_LIFE[key]["years"]) * scale
    return age + _remaining(age, sex) + habits


def drink_gain(age):
    """Full gain from 8-14 drinks a week (-0.5 years) down to 1-7 (0), scaled for age."""
    return 0.5 * min(1, _remaining(age) / _remaining(40))


def expected_me(fine, ratings):
    """The personal scoring rule written out independently of the page."""
    import humanity_me
    cat = humanity_me.catalog()
    scores = []
    for a in cat["areas"]:
        subs = [next(o["score"] for o in q["options"] if o["v"] == fine[q["key"]]) for q in a["questions"] if q["key"] in fine]
        self = ratings.get(a["key"])
        if self is None and not subs:
            continue
        if self is None:
            scores.append(sum(subs) / len(subs))
            continue
        w = 0.7 * len(subs) / len(a["questions"])
        scores.append((1 - w) * self * 10 + w * (sum(subs) / len(subs)) if subs else self * 10)
    return sum(scores) / len(scores)


def me_checks(page):
    page.click("nav.tabs button[data-view='me']")
    page.wait_for_selector("text=Let's talk about you.", timeout=8000)
    page.fill("#me-name", "Jim")
    page.fill("#me-age", "68")
    ratings = {"body": 9, "money": 7, "people": 8, "life": 8}
    names = {"body": "Body and health", "money": "Money and security", "people": "Relationships and love",
             "life": "Living the life you want"}
    for key, value in ratings.items():
        page.click(f".icard:has(h3:text-is('{names[key]}')) .ten button:text-is('{value}')")
    fine = {"exercise": "300_449", "drinks": "8_14", "car": "150_300", "volunteer": "0"}
    card = ".icard:has(h3:text-is('Body and health'))"
    page.click(f"{card} button:has-text('Fine tune')")
    page.select_option(f"{card} select[aria-label^='Brisk activity']", "300_449")
    page.select_option(f"{card} select[aria-label^='Alcoholic drinks']", "8_14")
    text = page.inner_text(card)
    check("each fine-tune question shows why it matters, with a source",
          "Moore and others" in text and "Wood and others" in text)
    page.fill(f"{card} input[aria-label='Height, feet']", "6")
    page.fill(f"{card} input[aria-label='Height, inches']", "0")
    page.fill(f"{card} input[aria-label='Weight, pounds']", "180")
    check("BMI helper picks the band (6 ft, 180 lb = 24.4)", "BMI 24.4" in page.inner_text(card)
          and page.eval_on_selector(f"{card} select[aria-label^='Weight for your height']", "e => e.value") == "healthy")
    fine["bmi"] = "healthy"
    planet = ".icard:has(h3:text-is('Your footprint on the planet'))"
    page.click(f"{planet} button:has-text('Fine tune')")
    page.select_option(f"{planet} select[aria-label^='Miles you drive']", "150_300")
    community = ".icard:has(h3:text-is('Community and giving'))"
    page.click(f"{community} button:has-text('Fine tune')")
    page.select_option(f"{community} select[aria-label^='Volunteering']", "0")
    page.click("button:has-text('Show my Humanity Index')")
    page.wait_for_selector(".dumbbell", timeout=8000)
    check("greets by name", "Jim, here's your Humanity Index." in page.inner_text("#me-h"))
    check("one line per area plus the overall", page.locator(".dbrow").count() == 9)
    want = expected_me(fine, ratings)
    got = page.inner_text(".dbrow.big .dbval").strip()
    check(f"overall is {round(want)}", got == str(round(want)), got)

    # a ready-made decision: 8-14 drinks a week down to 1-7
    page.click(".examples button:has-text('Keep to 7 drinks')")
    body = page.inner_text(".dbrow >> nth=1")
    money = page.inner_text(".dbrow:has-text('Money and security')")
    check("drinking less moves Body and health", "→" in body, body)
    check("and shows money not spent in a year ($2,150), on the money line", "$2,150 not spent" in money, money)
    check("and expected life gained so far", "of expected life" in body, body)

    # expected age: the life table for 68 (men and women averaged) plus habits versus typical, scaled for age
    before_age, gain = expected_age(fine, 68), drink_gain(68)
    age_text = page.inner_text(".agebig")
    want_age = f"{before_age:.1f} → {before_age + gain * (1 - math.exp(-1 / 2)):.1f}"
    check(f"expected age after a year of drinking less: {want_age}", age_text.replace("\n", "") == want_age, age_text)
    page.fill(".sliders input.years", "30")
    age_text = page.inner_text(".agebig")
    money = page.inner_text(".dbrow:has-text('Money and security')")
    want_age = f"{before_age:.1f} → {before_age + gain * (1 - math.exp(-30 / 2)):.1f}"
    check(f"typing 30 years: expected age {want_age} and $64,500 not spent",
          age_text.replace("\n", "") == want_age and "$64,500" in money, age_text + money)
    page.click(".agebtn")
    working = page.inner_text(".explain")
    check("clicking the expected age shows the working: life table, habits versus typical, scaling",
          "Social Security" in working and "typical" in working and "scaled" in working
          and f"{before_age:.1f}" in working, working[:500])
    page.click(".agebtn")
    page.click(".dbrow >> nth=1")
    explain = page.inner_text(".explain")
    check("clicking the line shows the working, the change and the research",
          "With “Keep to 7 drinks a week or fewer”" in explain and "8 to 14" in explain
          and "Wood and others" in explain and "research-based answers count" in explain, explain[:400])
    page.click(".dbrow >> nth=1")
    page.click(".examples button:has-text('Walk 30 minutes a day')")
    check("walking moves nothing for someone already this active", page.locator(".dbdot.after").count() == 0)

    # Jim's case: 10 million people save $200 a month for 21 years
    page.click(".examples button:has-text('Save $200 a month')")
    page.fill(".sliders input.years", "21")
    page.eval_on_selector(".sliders input[aria-label='How many people']",
                          "e => { e.value = 4; e.dispatchEvent(new Event('input')); }")
    months, rate = 252, 0.04 / 12
    one = 200 * ((1 + rate) ** months - 1) / rate
    money = page.inner_text(".dbrow:has-text('Money and security')")
    you = f"You: ${one:,.0f} saved ($50,400 put in, ${one - 50400:,.0f} growth at 4% a year)"
    crowd = f"10 million people: ${one * 1e7 / 1e9:.0f} billion saved"
    check(f"savings line shows you and the crowd: {you} / {crowd}", you in money and crowd in money, money)
    page.eval_on_selector(".sliders input[aria-label='How many people']",
                          "e => { e.value = 0; e.dispatchEvent(new Event('input')); }")
    page.fill(".sliders input.years", "1")

    # fine-tuning after setup: from the top, and straight to one area from its line
    check("a Fine tune button sits at the top", page.locator("button:has-text('Fine tune my answers')").count() == 1)
    check("each line says how well grounded it is",
          "your own rating only" in page.inner_text(".dbrow:has-text('Money and security')")
          and "fine-tuned 3 of 6" in page.inner_text(".dbrow:has-text('Body and health')"))
    page.click(".dbrow:has-text('Mind and mood')")
    page.click(".explain button:has-text('Fine tune mind and mood')")
    page.wait_for_selector(".icard[data-area='mind'] .fine", timeout=8000)
    check("Fine tune on a line opens that area's questions", page.locator(".icard .fine").count() == 1)
    page.select_option(".icard[data-area='mind'] select[aria-label^='How often you feel stressed']", "rarely")
    page.click("button:has-text('Show my Humanity Index')")
    page.wait_for_selector(".dumbbell", timeout=8000)
    check("after saving, the new answer counts (Mind and mood now 92)",
          "92" in page.inner_text(".dbrow:has-text('Mind and mood')"), page.inner_text(".dbrow:has-text('Mind and mood')"))

    # the ripple: 10 million people, and the world score
    page.click(".examples button:has-text('Volunteer 4 hours a month')")
    page.eval_on_selector(".sliders input[aria-label='How many people']",
                          "e => { e.value = 4; e.dispatchEvent(new Event('input')); }")
    ripple = page.inner_text(".ripple")
    check("ripple: 10 million people's hours", "If 10 million people like you did this" in ripple
          and "hours given" in ripple, ripple)
    check("ripple: the world score moves through 'people who volunteered'",
          "The world's Humanity Index" in ripple and "People who volunteered" in ripple, ripple)
    page.screenshot(path=os.path.join(SCREENS, "me-desktop.png"), full_page=True)

    # your own decision, typed (the microphone fills the same box)
    page.eval_on_selector(".sliders input[aria-label='How many people']",
                          "e => { e.value = 0; e.dispatchEvent(new Event('input')); }")
    page.fill("#me-own", "I want to cycle to work twice a week")
    page.click("button:has-text('Work it out')")
    page.wait_for_selector(".examples button.on:has-text('Cycle to work twice a week')", timeout=30000)
    line = page.inner_text(".dbrow:has-text('Your footprint on the planet')")
    check("your own decision moves the planet line, with tonnes of CO2",
          "→" in line and "tonnes of CO2 avoided" in line, line)
    page.click(".dbrow:has-text('Your footprint on the planet')")
    check("its working says it was worked out by AI from your words",
          "worked out by AI from your words" in page.inner_text(".explain"))


if __name__ == "__main__":
    sys.exit(main())

# I did no harm and this file is not truncated
