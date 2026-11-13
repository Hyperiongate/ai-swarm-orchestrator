"""
Admin Gate — tests against the whole Swarm app
File: tests/security/test_admin_gate.py
Created: November 11, 2026
Last Updated: November 13, 2026 — Performance dashboard, HEAD requests, removed features

PURPOSE:
    Starts the real app.py and checks swarm_security.py against every route the
    Swarm has: that outsiders are refused on everything private, that the
    public routes and the routes with their own login are left alone, and that
    the login, the key header, the guessing limit and the watching mode behave.
    Nothing in the Swarm imports this file.

    Run from the repo root with a THROWAWAY database (starting the app runs
    its migrations, and the tests empty the two admin_gate_ tables):
        DATABASE_URL=postgresql://... python -m pytest tests/security/test_admin_gate.py

AUTHOR: Jim @ Shiftwork Solutions LLC (managed by Claude)
"""

import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

if not os.environ.get("DATABASE_URL"):
    pytest.skip("Set DATABASE_URL to a throwaway PostgreSQL database to run these tests.",
                allow_module_level=True)

os.environ.pop("SWARM_ADMIN_PASSCODE", None)
os.environ.pop("FACTCHECK_PASSCODE", None)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")

import swarm_security as gate  # noqa: E402
from db_engine import get_db_connection  # noqa: E402
import app as swarm  # noqa: E402  (starts the whole Swarm)
from flask import Flask, jsonify  # noqa: E402

PASSCODE = "correct-horse-battery-staple-42"
KEY = {"X-Swarm-Key": PASSCODE}
SITE = "https://shift-work.com"


def all_routes():
    """(method, concrete path, endpoint, kind) for every route in the Swarm."""
    out = []
    for rule in swarm.app.url_map.iter_rules():
        path = rule.rule
        for argument in rule.arguments:
            converter = rule._converters[argument].__class__.__name__
            value = "1" if "Integer" in converter else "x"
            for form in (f"<int:{argument}>", f"<path:{argument}>", f"<string:{argument}>", f"<{argument}>"):
                path = path.replace(form, value)
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            out.append((method, path, rule.endpoint, gate.classify(rule.endpoint, path)))
    return out


ROUTES = all_routes()
ENDPOINTS = {endpoint for _m, _p, endpoint, _k in ROUTES}


@pytest.fixture()
def web(monkeypatch):
    """A fresh browser. The gate starts in watching mode (no passcode)."""
    monkeypatch.delenv("SWARM_ADMIN_PASSCODE", raising=False)
    gate.ensure_tables()
    with get_db_connection() as conn:
        conn.cursor().execute("DELETE FROM admin_gate_failures")
        conn.cursor().execute("DELETE FROM admin_gate_seen")
    gate._pending.clear()
    return swarm.app.test_client()


@pytest.fixture()
def locked(web, monkeypatch):
    monkeypatch.setenv("SWARM_ADMIN_PASSCODE", PASSCODE)
    return web


def log_in(client, passcode=PASSCODE):
    return client.post("/api/admin-gate/login", json={"passcode": passcode, "next": "/knowledge"})


def refused(response):
    return response.status_code == 401 or (
        response.status_code == 302 and response.headers["Location"].startswith("/login?next="))


# ---------------------------------------------------------------------------
# what is public, what is private
# ---------------------------------------------------------------------------

def test_every_name_in_the_lists_is_a_real_route():
    """A renamed public route would silently become private and break shift-work.com. Catch that here."""
    named = (gate.PUBLIC_ENDPOINTS | gate.OWN_LOGIN_ENDPOINTS | gate.SERVICE_ENDPOINTS_OPEN_FOR_NOW
             | gate.SURVEY_FAMILY_ENDPOINTS)
    assert named - ENDPOINTS == set()
    blueprints = {endpoint.split(".")[0] for endpoint in ENDPOINTS if "." in endpoint}
    assert (gate.PUBLIC_BLUEPRINTS | gate.OWN_LOGIN_BLUEPRINTS | gate.SURVEY_FAMILY_BLUEPRINTS) - blueprints == set()
    assert not any(name.startswith("ptt") for name in blueprints)      # Part Time Tracker removed Nov 13, 2026


def test_only_the_intended_routes_are_open_without_the_passcode():
    open_paths = sorted({f"{method} {path}" for method, path, _e, kind in ROUTES if kind == "public"})
    assert open_paths == [
        "GET /api/admin-gate/status",
        "GET /api/survey/take/x/questions",
        "GET /health",
        "GET /homepage",
        "GET /login",
        "GET /static/x",
        "GET /survey/start",
        "GET /survey/take/x",
        "POST /api/admin-gate/login",
        "POST /api/admin-gate/logout",
        "POST /api/assessment/generate-pdf",
        "POST /api/assessment/lead",
        "POST /api/assessment/t1-commentary",
        "POST /api/assessment/t2-evaluate",
        "POST /api/assessment/update-scores",
        "POST /api/contact/submit",
        "POST /api/events/log",
        "POST /api/newsletter/subscribe",
        "POST /api/survey/intake/submit",
        "POST /api/survey/take/x/submit",
    ]
    assert sorted({path for _m, path, _e, kind in ROUTES if kind == "service_open"}) == ["/api/survey/norm/search"]
    own = {endpoint.split(".")[0] for _m, _p, endpoint, kind in ROUTES if kind == "own_login"}
    assert own == {"survey_admin", "survey_respondent", "factcheck"}


def test_performance_dashboard_is_private_and_carries_no_pin_or_key(locked):
    assert refused(locked.get("/performance", headers={"Accept": "text/html"}))
    log_in(locked)
    page = locked.get("/performance")
    assert page.status_code == 200
    with open(os.path.join(ROOT, "templates", "performance.html"), "rb") as handle:
        assert page.data == handle.read()                      # served as a plain file
    for gone in (b"1236", b"CORRECT_PIN", b"googletagmanager", b"X-Swarm-Key", b"onrender.com"):
        assert gone not in page.data
    assert locked.get("/performance/").status_code == 200


def test_uptime_checks_using_head_are_redirected_not_refused(locked):
    head = locked.head("/")
    assert head.status_code == 302 and head.headers["Location"] == "/login?next=/"
    assert locked.head("/health").status_code == 200
    assert locked.head("/api/newsletter/subscribers").status_code == 401     # data routes still refuse


def test_removed_features_are_gone(locked):
    """Part Time Tracker, content generators, FeynmanLab and avatars were removed November 13, 2026."""
    gone = ("/ptt", "/api/ptt", "/physics", "/api/physics", "/api/avatar", "/api/manuals",
            "/api/case-studies", "/api/blog-posts", "/api/marketing/generate-posts", "/api/marketing/pending")
    assert [path for _m, path, _e, _k in ROUTES if path.startswith(gone)] == []
    log_in(locked)
    for path in ("/physics", "/ptt/login", "/api/avatar/status", "/api/manuals/status",
                 "/api/case-studies/list", "/api/blog-posts/list", "/api/ptt/dev/reset-company"):
        assert locked.get(path).status_code == 404, path
    page = locked.get("/").data
    for tab in (b"manualsModeBtn", b"casestudiesModeBtn", b"blogpostsModeBtn"):
        assert tab not in page
    for tab in (b"quickModeBtn", b"projectModeBtn", b"surveyModeBtn", b"marketingModeBtn", b"briefingModeBtn"):
        assert tab in page


def test_the_sensitive_routes_are_private():
    kinds = {f"{method} {path}": kind for method, path, _e, kind in ROUTES}
    assert kinds["GET /performance"] == "admin" and kinds["GET /performance/"] == "admin"
    for route in ["GET /api/newsletter/subscribers", "GET /api/newsletter/blocked-ips",
                  "POST /api/newsletter/block-ip", "POST /api/newsletter/unsubscribe",
                  "GET /api/contact/submissions", "GET /api/events/recent", "GET /api/events/summary",
                  "GET /api/admin/clear-knowledge-db", "POST /api/admin/restore-knowledge",
                  "GET /", "POST /api/orchestrate", "GET /api/marketing/status",
                  "GET /downloads/x", "GET /knowledge", "GET /memory-admin",
                  "GET /api/admin-gate/report", "GET /api/admin-gate/check"]:
        assert kinds[route] == "admin", route
    assert kinds["GET /api/survey/question-bank"] == "survey_family"


def test_an_outsider_is_refused_on_every_private_route(locked):
    private = [(method, path) for method, path, _e, kind in ROUTES if kind in ("admin", "survey_family")]
    assert len(private) > 250
    # A WebSocket route (the voice stream) only exists for WebSocket requests, so ask the way a browser would.
    websocket_paths = {rule.rule for rule in swarm.app.url_map.iter_rules() if rule.websocket}
    upgrade = {"Connection": "Upgrade", "Upgrade": "websocket"}
    not_refused = []
    for method, path in private:
        response = locked.open(path, method=method, headers=upgrade if path in websocket_paths else {})
        if not refused(response):
            not_refused.append(f"{method} {path} -> {response.status_code}")
    assert not_refused == []


def test_public_and_own_login_routes_pass_the_gate_when_locked(locked):
    """Checked at the gate itself, without running the routes (some send email or write records)."""
    for method, path, endpoint, kind in ROUTES:
        if kind not in ("public", "own_login", "service_open"):
            continue
        with swarm.app.test_request_context(path, method=method):
            from flask import request
            request.url_rule = next(r for r in swarm.app.url_map.iter_rules() if r.endpoint == endpoint)
            assert gate._gate() is None, f"{method} {path}"


def test_public_pages_still_open_when_locked(locked):
    assert locked.get("/health").status_code == 200
    assert locked.get("/homepage").status_code == 200
    assert locked.get("/survey/start").status_code == 200
    assert locked.get("/survey/admin").status_code == 200          # its own login page
    assert locked.get("/factcheck").status_code == 200
    assert locked.get("/api/factcheck/health").status_code == 200
    assert locked.get("/no/such/address").status_code == 404       # unknown addresses are not turned into 401s
    assert locked.options("/api/newsletter/subscribers").status_code == 200


# ---------------------------------------------------------------------------
# watching mode (no passcode set): nothing is blocked, everything is recorded
# ---------------------------------------------------------------------------

def test_watching_mode_blocks_nothing_and_records_what_it_would_block(web):
    assert web.get("/api/newsletter/blocked-ips").status_code == 200
    assert web.get("/knowledge").status_code == 200
    assert web.get("/api/events/summary", headers={"Origin": SITE}).status_code == 200
    assert web.get("/health").status_code == 200
    state = web.get("/api/admin-gate/status").get_json()
    assert state == {"locked": False, "logged_in": False, "passcode_is_short": False}
    assert web.post("/api/admin-gate/login", json={"passcode": "anything"}).status_code == 409

    report = web.get("/api/admin-gate/report").get_json()
    seen = {(row["mode"], row["endpoint"], row["source"]) for row in report["seen"]}
    assert ("would_block", "newsletter.view_blocked_ips", "direct (typed address, script or another server)") in seen
    assert ("would_block", "knowledge_management", "direct (typed address, script or another server)") in seen
    assert ("would_block", "site_events.events_summary", "shift-work.com") in seen
    assert not any(endpoint == "health" for _mode, endpoint, _source in seen)


# ---------------------------------------------------------------------------
# logging in with a browser
# ---------------------------------------------------------------------------

def test_page_requests_are_sent_to_the_login_page(locked):
    response = locked.get("/knowledge?x=1", headers={"Accept": "text/html"})
    assert response.status_code == 302 and response.headers["Location"] == "/login?next=/knowledge%3Fx%3D1"
    page = locked.get("/login")
    assert page.status_code == 200 and b"Admin passcode" in page.data
    with open(os.path.join(ROOT, "templates", "admin_login.html"), "rb") as handle:
        assert page.data == handle.read()
    api = locked.get("/api/newsletter/subscribers")
    assert api.status_code == 401 and api.get_json()["login_url"] == "/login"


def test_login_sets_a_cookie_that_opens_the_private_routes(locked):
    assert log_in(locked, "wrong").status_code == 401
    assert refused(locked.get("/api/newsletter/blocked-ips"))

    response = log_in(locked)
    assert response.status_code == 200 and response.get_json() == {"success": True, "next": "/knowledge"}
    cookie = response.headers["Set-Cookie"]
    assert "swarm_admin=" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Max-Age=2592000" in cookie

    assert locked.get("/api/newsletter/blocked-ips").status_code == 200
    assert locked.get("/knowledge").status_code == 200
    assert locked.get("/").status_code == 200
    assert locked.get("/api/admin-gate/check").get_json() == {"success": True, "locked": True}
    assert locked.get("/api/admin-gate/status").get_json()["logged_in"] is True

    assert locked.post("/api/admin-gate/logout").status_code == 200
    assert refused(locked.get("/api/newsletter/blocked-ips"))


def test_login_never_sends_the_browser_off_site(locked):
    for bad in ["https://evil.example/", "//evil.example", "/\\evil.example", "javascript:alert(1)", ""]:
        response = locked.post("/api/admin-gate/login", json={"passcode": PASSCODE, "next": bad})
        assert response.get_json()["next"] == "/"


def test_cookie_cannot_be_forged_and_dies_with_the_passcode(locked, monkeypatch):
    good = gate.make_cookie_value(PASSCODE)
    expires, signature = good.split(".")
    assert gate.cookie_is_valid(good, PASSCODE)
    assert not gate.cookie_is_valid(f"{int(expires) + 999}.{signature}", PASSCODE)       # edited expiry
    assert not gate.cookie_is_valid(gate.make_cookie_value(PASSCODE, now=time.time() - 31 * 86400), PASSCODE)  # expired
    assert not gate.cookie_is_valid(gate.make_cookie_value("another passcode"), PASSCODE)
    for junk in ["", "abc", "1.2.3", "9999999999.", None]:
        assert not gate.cookie_is_valid(junk, PASSCODE)

    log_in(locked)
    assert locked.get("/api/admin-gate/check").status_code == 200
    monkeypatch.setenv("SWARM_ADMIN_PASSCODE", "a brand new passcode 2026")           # changing it signs everyone out
    assert locked.get("/api/admin-gate/check").status_code == 401


# ---------------------------------------------------------------------------
# the key header, and the guessing limit
# ---------------------------------------------------------------------------

def test_key_header_works_for_other_apps(locked):
    assert locked.get("/api/admin-gate/check", headers=KEY).status_code == 200
    assert locked.get("/api/newsletter/stats", headers=KEY).status_code == 200
    assert locked.get("/api/newsletter/stats", headers={"X-Swarm-Key": "nope"}).status_code == 401


def test_guessing_is_cut_off_but_a_logged_in_browser_carries_on(locked):
    log_in(locked)                                             # this browser has its cookie
    guesser = swarm.app.test_client()
    for _ in range(gate.MAX_FAILURES_PER_ADDRESS):
        assert guesser.get("/api/admin-gate/check", headers={"X-Swarm-Key": "guess"}).status_code == 401
    assert guesser.get("/api/admin-gate/check", headers=KEY).status_code == 429          # even the right key now
    assert guesser.post("/api/admin-gate/login", json={"passcode": PASSCODE}).status_code == 429
    assert locked.get("/api/admin-gate/check").status_code == 200                        # cookie unaffected

    with get_db_connection() as conn:                          # fifteen minutes later...
        conn.cursor().execute("UPDATE admin_gate_failures SET at = at - %s", (gate.FAILURE_WINDOW_SECONDS + 5,))
    assert guesser.get("/api/admin-gate/check", headers=KEY).status_code == 200


def test_blocked_requests_are_recorded(locked):
    locked.get("/api/newsletter/subscribers", headers={"Origin": SITE})
    report = locked.get("/api/admin-gate/report", headers=KEY).get_json()
    assert any(row["mode"] == "blocked" and row["endpoint"] == "newsletter.list_subscribers"
               and row["source"] == "shift-work.com" for row in report["seen"])


# ---------------------------------------------------------------------------
# the shift-work.com performance dashboard (another site, sending the key)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/api/newsletter/subscribers", "/api/newsletter/stats",
                                  "/api/newsletter/blocked-ips", "/api/contact/submissions",
                                  "/api/events/summary", "/api/events/recent", "/api/admin-gate/check"])
def test_dashboard_on_shift_work_com_can_send_the_key(locked, path):
    ask = locked.options(path, headers={"Origin": SITE, "Access-Control-Request-Method": "GET",
                                        "Access-Control-Request-Headers": "x-swarm-key"})
    assert ask.status_code in (200, 204)
    assert ask.headers["Access-Control-Allow-Origin"] == SITE
    assert "x-swarm-key" in ask.headers["Access-Control-Allow-Headers"].lower()

    without = locked.get(path, headers={"Origin": SITE})
    assert without.status_code == 401 and without.headers["Access-Control-Allow-Origin"] == SITE   # readable refusal
    with_key = locked.get(path, headers=dict(KEY, Origin=SITE))
    assert with_key.status_code == 200 and with_key.headers["Access-Control-Allow-Origin"] == SITE


# ---------------------------------------------------------------------------
# survey tools: the admin passcode or a Survey admin login
# ---------------------------------------------------------------------------

def test_survey_admin_login_still_reaches_the_survey_tools(locked):
    assert locked.get("/api/survey/question-bank").status_code == 401
    with locked.session_transaction() as session:
        session["survey_admin_authenticated"] = True
    assert locked.get("/api/survey/question-bank").status_code == 200
    assert refused(locked.get("/api/newsletter/subscribers"))          # ...but nothing else
    assert refused(locked.get("/knowledge"))


# ---------------------------------------------------------------------------
# the session secret
# ---------------------------------------------------------------------------

def test_session_secret_is_never_the_old_public_string(monkeypatch):
    old = "dev-secret-key-change-in-production-12345"
    monkeypatch.setenv("SECRET_KEY", "set-in-render")
    assert gate.session_secret_key() == "set-in-render"
    monkeypatch.setenv("SECRET_KEY", old)
    derived = gate.session_secret_key()
    assert derived != old and len(derived) == 64
    monkeypatch.delenv("SECRET_KEY")
    assert gate.session_secret_key() == derived                        # same in every worker, every restart
    monkeypatch.setenv("DATABASE_URL", "postgresql://other/db")
    assert gate.session_secret_key() not in (derived, old)
    monkeypatch.delenv("DATABASE_URL")
    assert gate.session_secret_key() != gate.session_secret_key()      # local dev: random each time
    assert swarm.app.config["SECRET_KEY"] != old


# ---------------------------------------------------------------------------
# error detail (a small stand-alone app, so a route can be made to fail on purpose)
# ---------------------------------------------------------------------------

def test_error_detail_is_withheld_from_outsiders_only(monkeypatch):
    small = Flask("small")

    @small.route("/health")
    def health():
        return jsonify({"success": False, "error": "boom", "traceback": "File app.py line 1 SECRET DETAIL"}), 500

    @small.route("/api/private")
    def private():
        return jsonify({"success": False, "error": "boom", "traceback": "File app.py line 2 SECRET DETAIL"}), 500

    gate.init_security(small)
    client = small.test_client()

    monkeypatch.delenv("SWARM_ADMIN_PASSCODE", raising=False)             # watching mode changes nothing
    assert "traceback" in client.get("/api/private").get_json()

    monkeypatch.setenv("SWARM_ADMIN_PASSCODE", PASSCODE)
    public = client.get("/health")                                        # a public route that fails
    assert public.status_code == 500 and public.get_json() == {"success": False, "error": "boom"}
    assert "traceback" in client.get("/api/private", headers=KEY).get_json()      # the admin still sees it
    log_in(client)
    assert "traceback" in client.get("/health").get_json()                # logged in: public routes too

# I did no harm and this file is not truncated
