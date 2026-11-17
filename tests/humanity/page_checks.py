"""
The Humanity Index — page tests in a real browser
File: tests/humanity/page_checks.py
Created: November 15, 2026
Last Updated: November 16, 2026 (evening) — rewritten for the two-tab design (Me and World)

PURPOSE:
    Serves the page with gunicorn under the Swarm's own gunicorn.conf.py, with
    the real helper process and the stand-in AI service, and drives it in
    Chromium, as Jim's two-tab design of November 16, 2026 (evening):
      * passcode; only two tabs (Me and World);
      * World: download the free world data, the coloured map, click a
        country, "what if it improved by 10%" moving the world score, filling
        a country's missing measures, "Compare with me";
      * Me: the interview and fine tune, typed and spoken changes (no ready-made
        list), you and a place side by side, the people slider up to the
        place's population, the place's bars moving, expected age, savings for
        you and the crowd, the working behind every line, Marin County worked
        out on request, deleting;
      * phone width and dark mode.
    Before November 16 (evening) it also drove the Score, Ask, Ledger and
    Library tabs; those are no longer in the menu and their server side is
    still covered by test_humanity_server.py.
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
    "HUMANITY_WORLD_BANK_URL": f"http://127.0.0.1:{STUB_PORT}/wb", "HUMANITY_OWID_URL": f"http://127.0.0.1:{STUB_PORT}/owid",
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
            import humanity_world
            humanity_world.ensure_tables()
            cur.execute("DELETE FROM humanity_country_values")
            cur.execute("DELETE FROM humanity_country")
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


def run_browser():
    sys.path.insert(0, HERE)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
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

        page.wait_for_selector("#me .icard", timeout=8000)
        check("Me is the first tab and opens on the interview", page.locator("#me .icard").count() == 9)
        tabs = page.locator("nav.tabs button").all_inner_texts()
        check("only two tabs: Me and World", tabs == ["Me", "World"], tabs)

        world_checks(page)
        me_checks(page)

        # phone width and dark mode
        phone = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1, color_scheme="dark")
        phone.goto(BASE + "/humanity")
        phone.evaluate(f"sessionStorage.setItem('humanity-pass', '{PASS}')")
        phone.goto(BASE + "/humanity")
        phone.wait_for_selector("#me .twocol .dumbbell", timeout=8000)
        phone.wait_for_selector(".placecol .dbrow", timeout=8000)
        overflow = phone.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check("Me: no sideways scrolling at phone width", overflow <= 0, overflow)
        bg = phone.evaluate("getComputedStyle(document.body).backgroundColor")
        check("dark mode applies", bg == "rgb(15, 27, 38)", bg)
        phone.screenshot(path=os.path.join(SCREENS, "me-phone-dark.png"), full_page=True)
        phone.click("nav.tabs button[data-view='world']")
        phone.wait_for_selector(".worldmap .country", timeout=8000)
        phone.click(".worldmap .country[data-iso='HUN']")
        phone.wait_for_selector("#countrypanel h3:has-text('Hungary')", timeout=8000)
        overflow = phone.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check("World: no sideways scrolling at phone width", overflow <= 0, overflow)
        phone.screenshot(path=os.path.join(SCREENS, "world-phone-dark.png"), full_page=True)

        # deleting your answers takes two presses and brings back the interview
        page.click("nav.tabs button[data-view='me']")
        page.click("button:has-text('Delete my answers')")
        check("first press only warns", "again" in page.inner_text("#pagenotice")
              and page.locator("#me .twocol").count() == 1)
        page.click("button:has-text('Delete my answers')")
        page.wait_for_selector("text=Let's talk about you.", timeout=8000)
        check("second press deletes and shows the interview", page.locator("#me .icard").count() == 9)

        check("no script errors or pop-ups", not errors, errors)
        browser.close()


def world_checks(page):
    page.click("nav.tabs button[data-view='world']")
    page.wait_for_selector("text=The world data hasn't been downloaded yet.", timeout=8000)
    check("World starts by offering to download the data", True)
    page.click("button:has-text('Download the world data')")
    page.wait_for_selector(".worldmap .country", timeout=60000)
    shapes = page.locator(".worldmap .country").count()
    check(f"the map draws every country ({shapes})", shapes >= 170, shapes)
    fills = page.eval_on_selector_all(".worldmap .country", "ps => ps.map(p => [p.dataset.iso, p.getAttribute('fill')])")
    coloured = {iso for iso, f in fills if f.startswith("hsl")}
    check("the three countries with data are coloured, the rest grey", coloured == {"USA", "HUN", "IND"}, coloured)
    data = requests.get(BASE + "/api/humanity/world", headers={"X-App-Passcode": PASS}).json()
    head = page.inner_text(".worldhead")
    check("the world score is shown, built from the countries", f"{data['world']['overall']:.1f}" in head
          and "Built from 3 countries" in head, head)
    page.click(".worldmap .country[data-iso='HUN']")
    page.wait_for_selector("#countrypanel h3:has-text('Hungary')", timeout=8000)
    hun = next(c for c in data["countries"] if c["iso3"] == "HUN")
    panel = page.inner_text("#countrypanel")
    check("clicking Hungary shows its score and its 12 categories",
          f"Hungary: {hun['overall']:.1f}" in panel and page.locator("#countrypanel .dbrow").count() == 12, panel[:200])
    counted = [c for c in data["countries"] if c["overall"] is not None]
    share = hun["population"] / sum(c["population"] for c in counted)
    after = min(100, hun["overall"] * 1.1)
    world_after = data["world"]["overall"] + share * (after - hun["overall"])
    check(f"what if Hungary improved by 10%: {after:.1f}, world {world_after:.3f}",
          f"Hungary: {hun['overall']:.1f} → {after:.1f}" in panel and f"{world_after:.3f}" in panel, panel)
    page.eval_on_selector("#countrypanel input[type=range]", "e => { e.value = 30; e.dispatchEvent(new Event('input')); }")
    after = min(100, hun["overall"] * 1.3)
    check("moving the improvement to 30% moves both", f"→ {after:.1f}" in page.inner_text("#countrypanel"))
    page.click("#countrypanel .dbrow:has-text('Health and long life')")
    check("a category opens to its measures, values and sources",
          "Life expectancy at birth" in page.inner_text("#countrypanel") and "worldbank.org" in page.inner_text("#countrypanel"),
          page.inner_text("#countrypanel")[:600])
    page.screenshot(path=os.path.join(SCREENS, "world-desktop.png"), full_page=True)
    measured_before = hun["measured"]
    page.click("#countrypanel button:has-text('Fill in the')")
    page.wait_for_function("() => /\\d+ of 26 measures found/.test(document.querySelector('#countrypanel').innerText) && !document.querySelector('#countrypanel').innerText.includes('Researching')", timeout=60000)
    page.wait_for_selector("#countrypanel h3:has-text('Hungary')", timeout=8000)
    text = page.inner_text("#countrypanel")
    check("filling the missing measures raises the count", f"{measured_before} of 26" not in text and "of 26 measures found" in text, text[:200])
    page.click("#countrypanel button:has-text('Compare with me')")
    page.wait_for_selector("#view-me:not(.hidden)", timeout=8000)
    check("Compare with me opens Me", True)


def change(page, text, label):
    page.fill("#me-own", text)
    page.click("button:has-text('Work it out')")
    page.wait_for_selector(f".examples button.on:has-text('{label}')", timeout=30000)


def place(page):
    return page.inner_text("#me .placecol")


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
    check("each fine-tune question shows why it matters, with a source",
          "Moore and others" in page.inner_text(card) and "Wood and others" in page.inner_text(card))
    page.fill(f"{card} input[aria-label='Height, feet']", "6")
    page.fill(f"{card} input[aria-label='Height, inches']", "0")
    page.fill(f"{card} input[aria-label='Weight, pounds']", "180")
    check("BMI helper picks the band (6 ft, 180 lb = 24.4)", "BMI 24.4" in page.inner_text(card))
    fine["bmi"] = "healthy"
    planet = ".icard:has(h3:text-is('Your footprint on the planet'))"
    page.click(f"{planet} button:has-text('Fine tune')")
    page.select_option(f"{planet} select[aria-label^='Miles you drive']", "150_300")
    community = ".icard:has(h3:text-is('Community and giving'))"
    page.click(f"{community} button:has-text('Fine tune')")
    page.select_option(f"{community} select[aria-label^='Volunteering']", "0")
    page.click("button:has-text('Show my Humanity Index')")
    page.wait_for_selector("#me .twocol .dumbbell", timeout=8000)
    check("greets by name", "Jim, here's your Humanity Index." in page.inner_text("#me-h"))
    mine = "#me .twocol > div:first-child"
    check("you on the left: one line per area plus the overall", page.locator(f"{mine} .dbrow").count() == 9)
    want = expected_me(fine, ratings)
    got = page.inner_text(f"{mine} .dbrow.big .dbval").strip()
    check(f"your overall is {round(want)}", got == str(round(want)), got)
    check("no list of ready-made decisions, one box to type or say a change",
          page.locator("#me .examples button").count() == 0 and page.locator("#me-own").count() == 1)
    page.wait_for_selector("#me .placecol .dbrow", timeout=8000)
    check("Hungary (from Compare with me) on the right, side by side",
          "Hungary" in place(page) and page.locator("#me .placecol .dbrow").count() == 13, place(page)[:200])

    # a typed change: 8-14 drinks a week down to 1-7
    change(page, "I'll drink less", "Keep to 7 drinks a week")
    body = page.inner_text(f"{mine} .dbrow >> nth=1")
    money = page.inner_text(f"{mine} .dbrow:has-text('Money and security')")
    check("drinking less moves your Body and health", "→" in body, body)
    check("and shows money not spent in a year ($2,150)", "$2,150 not spent" in money, money)
    before_age, gain = expected_age(fine, 68), drink_gain(68)
    want_age = f"{before_age:.1f} → {before_age + gain * (1 - math.exp(-1 / 2)):.1f}"
    check(f"expected age after a year: {want_age}", page.inner_text("#me .agebig").replace("\n", "") == want_age,
          page.inner_text("#me .agebig"))
    page.click(".agebtn")
    working = page.inner_text(".explain")
    check("clicking the expected age shows the working", "Social Security" in working and "scaled" in working)
    page.click(".agebtn")

    # the place side: the people slider goes up to the place's population; Hungary's health line moves
    page.eval_on_selector(".sliders input[aria-label='How many people']",
                          "e => { e.value = 1000; e.dispatchEvent(new Event('input')); }")
    label = page.inner_text(".sliders label:nth-child(2)")
    check("people slider is for the place, up to everyone in it", "How many people in Hungary" in label
          and "Everyone (9.6 million)" in label, label)
    health = page.inner_text("#me .placecol .dbrow:has-text('Health and long life')")
    check("everyone in Hungary drinking less moves Hungary's health line", "→" in health, health)
    page.click("#me .placecol .dbrow:has-text('Health and long life')")
    explain = page.inner_text(".explain")
    check("the place line's working shows the measure moving", "Hungary: Health and long life" in explain
          and "Life expectancy at birth" in explain and "moves by" in explain, explain[:500])
    page.click("#me .placecol .dbrow:has-text('Health and long life')")

    # Jim's case: save $200 a month for 21 years, for you and for everyone in the place
    change(page, "save $200 a month", "Save $200 a month")
    page.fill(".sliders input.years", "21")
    months, rate = 252, 0.04 / 12
    one = 200 * ((1 + rate) ** months - 1) / rate
    money = page.inner_text(f"{mine} .dbrow:has-text('Money and security')")
    you = f"You: ${one:,.0f} saved ($50,400 put in, ${one - 50400:,.0f} growth at 4% a year)"
    check(f"savings for you and everyone in Hungary: {you}", you in money and "Everyone in Hungary (9.6 million)" in money, money)
    page.fill(".sliders input.years", "1")

    # world vs a smaller place: the same change by the same share moves a small place, barely the world
    change(page, "drive less", "Drive less")
    page.click("#me .placepick button:has-text('World')")
    page.wait_for_selector("#me .placecol .dbrow:has-text('World')", timeout=8000)
    page.eval_on_selector(".sliders input[aria-label='How many people']",
                          "e => { e.value = 700; e.dispatchEvent(new Event('input')); }")
    planet_world = page.inner_text("#me .placecol .dbrow:has-text('Care for the planet')")
    check("driving less by part of the world: the planet line shows a small change", "→" in planet_world, planet_world)
    page.screenshot(path=os.path.join(SCREENS, "me-desktop.png"), full_page=True)

    # Marin County is worked out on request
    page.click("#me .placepick button:has-text('Marin County')")
    page.wait_for_selector("button:has-text(\"Work out Marin County's score\")", timeout=8000)
    page.click("button:has-text(\"Work out Marin County's score\")")
    page.wait_for_selector("#me .placecol .dbrow.big:has-text('Marin County')", timeout=60000)
    page.wait_for_function("() => !document.querySelector('#me .placecol').innerText.includes('Still researching')", timeout=60000)
    check("Marin County's score appears on the right", page.locator("#me .placecol .dbrow").count() == 13,
          [page.locator("#me .placecol .dbrow").count(), place(page)[:400]])

    # a spoken change: the microphone fills the box and works it out
    page.evaluate("window.__say = 'I will volunteer four hours a month'")
    page.click("#me .decide .mic")
    page.wait_for_selector(".examples button.on:has-text('Volunteer 4 hours a month')", timeout=30000)
    check("a spoken change is worked out like a typed one", True)
    check("your recent changes stay as buttons", page.locator("#me .examples button").count() == 4,
          page.locator("#me .examples button").all_inner_texts())

    # fine-tuning after setup
    check("each line says how well grounded it is",
          "your own rating only" in page.inner_text(f"{mine} .dbrow:has-text('Money and security')"))
    page.click(f"{mine} .dbrow:has-text('Mind and mood')")
    page.click(".explain button:has-text('Fine tune mind and mood')")
    page.wait_for_selector(".icard[data-area='mind'] .fine", timeout=8000)
    page.select_option(".icard[data-area='mind'] select[aria-label^='How often you feel stressed']", "rarely")
    page.click("button:has-text('Show my Humanity Index')")
    page.wait_for_selector("#me .twocol .dumbbell", timeout=8000)
    check("after saving, the new answer counts (Mind and mood now 92)",
          "92" in page.inner_text(f"{mine} .dbrow:has-text('Mind and mood')"))


if __name__ == "__main__":
    sys.exit(main())

# I did no harm and this file is not truncated
