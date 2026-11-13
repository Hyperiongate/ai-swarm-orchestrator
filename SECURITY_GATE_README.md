# Admin Gate: one passcode for the private parts of the Swarm

Added 11 November 2026.

Until now only Survey admin and the Part Time Tracker had logins. Everything
else answered anyone who knew the address, including the newsletter subscriber
list, the `/api/admin/*` repair routes and the Part Time Tracker's developer
shortcuts. The Admin Gate puts one passcode in front of all of it.

## Nothing changes until you set the passcode

The switch is one setting in Render: `SWARM_ADMIN_PASSCODE`.

- **Not set (how it deploys):** watching mode. Nothing is blocked. The gate only
  records which requests it would have blocked, so a forgotten outside caller
  shows up before it is locked out. See the record at `/api/admin-gate/report`.
- **Set:** locked. Deleting the setting unlocks everything again at once.

## Before you lock: the shift-work.com performance dashboard

The dashboard at shift-work.com/performance reads the subscriber list, contact
submissions and visitor events from the Swarm. Today its only protection is a
4-digit PIN written in the page's own source, which anyone can read.

Once the Swarm is locked, those reads are refused until that page is changed to
ask for the admin passcode and send it. **Update that page first, or expect the
dashboard to show errors from the moment you lock.** The Swarm side is ready for
it (the page sends the passcode in an `X-Swarm-Key` header).

## To lock

1. Choose a long passcode: 16 characters or more. Four words works well.
2. In Render > the Swarm service > Environment, add `SWARM_ADMIN_PASSCODE`.
3. Open the Swarm. You are sent to `/login`. Enter the passcode once; that
   browser stays logged in for 30 days.
4. While you are there, check whether `SECRET_KEY` is set in Render. If it is
   not, add one (any long random text). See "The session secret" below.

To log out, open `/login` and press **Log out**. Changing the passcode signs
every browser out.

## What stays open, and why

| What | Why |
| --- | --- |
| `/health`, `/static`, `/homepage` | Render's health check, page assets, a copy of the public home page |
| Newsletter subscribe, contact form, assessment, visitor event log | Called by shift-work.com from visitors' browsers |
| Survey intake form, and taking a survey by its link | For clients and their employees |
| Survey admin | Has its own password already |
| Part Time Tracker | Has its own logins already. Its `/api/ptt/dev/*` shortcuts now need the admin passcode |
| Speech Fact-Checker | Has its own passcode already |
| `/api/survey/norm/search` | The Thomas diagnostic app calls it and does not send a key yet. Open for now, on purpose |

Everything else needs the admin passcode, including the main screen,
FeynmanLab, downloads, and every `/api/admin/*` route. The survey builder and
normative tools accept either the admin passcode or a Survey admin login.

**A route added in future is private by default.** If outsiders must reach it,
its name has to be added to `PUBLIC_ENDPOINTS` in `swarm_security.py`.

## Other things it does once locked

- **Slows guessing.** After 10 wrong passcodes from one address in 15 minutes
  (or 100 from anywhere), passcode attempts are refused for the rest of that
  window. A browser already logged in is not affected.
- **Keeps error detail private.** About 57 routes return an internal
  "traceback" when they fail. Outsiders no longer receive it; it goes to the
  Render log instead. Logged in, you still see it.

## The session secret (changed regardless of the passcode)

`app.py` used to fall back to a fixed text, printed in this public repository,
whenever `SECRET_KEY` was missing from Render. With that text a "logged in"
Survey admin cookie could be forged. It now falls back to a key derived from
the database address, which is private. If `SECRET_KEY` is set in Render,
nothing changes. If it was not, everyone is signed out once.

## The developer shortcuts were kept, not removed

The four `/api/ptt/dev/*` routes (reset a company, reseed skills, reset a
shift, make a worker login link) still exist. They are locked behind the admin
passcode instead of deleted, so they remain available for testing.

## What has and has not been tested

Tested 11 November 2026, all passing:

- 24 tests against the whole Swarm app and PostgreSQL 16. One of them asks for
  every private route (more than 300) as an outsider and confirms each is
  refused. Another confirms the list of open routes is exactly the intended one.
- The whole Swarm started before and after the change: the same 432 routes plus
  the 6 new ones.
- 12 checks in a real Chrome browser against the Swarm running under its own
  gunicorn settings: sent to login, wrong passcode refused, main screen and
  FeynmanLab open after login with nothing refused, logout, and public pages
  still open to outsiders.

**Not tested:** the live Swarm on Render, and callers I could not see from the
code. I searched nine of your other repositories for calls into the Swarm and
found only shift-work.com, the Thomas diagnostic app and one newsletter
sign-up. Watching mode exists to catch anything else: run it for a few days
and read `/api/admin-gate/report` before locking.

## Files

| File | What it is |
| --- | --- |
| `swarm_security.py` | The gate, the lists of what is public, and its own routes |
| `templates/admin_login.html` | The login page |
| `tests/security/test_admin_gate.py` | The tests. Not used by the running app |
| `app.py` | Two changes: the gate is switched on, and the session secret fallback |

## Running the tests again

From the repo root, with a throwaway PostgreSQL database:

```
DATABASE_URL=postgresql://... python -m pytest tests/security/test_admin_gate.py
```
