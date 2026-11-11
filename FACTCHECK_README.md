# Speech Fact-Checker (inside the AI Swarm Orchestrator)

Added 11 November 2026. First version built 10 November 2026 as a standalone app.

Open **/factcheck** on the Swarm in Chrome or Edge, press **Start listening**, and
the page listens through the computer's microphone to a speech on TV. Each
checkable claim gets a coloured verdict a few seconds after it is said. Press
**Stop and build report** for the annotated transcript, a tally, and a five-layer
recheck of every claim.

## Files

| File | What it is |
| --- | --- |
| `routes/factcheck.py` | The page route and the small job API. |
| `factcheck_engine.py` | The AI instructions, the three jobs, and the job queue. |
| `factcheck_runner.py` | The separate helper process that does the AI work. |
| `templates/factcheck.html` | The page. |
| `tests/factcheck/` | The dry-run tests. Not used by the running app. |
| `app.py` | One change: the blueprint registration (see its changelog). |

No change to `requirements.txt`, `gunicorn.conf.py`, the migrations, or any
other Swarm file.

## To deploy

1. Review with `git status` and `git diff`, then commit and push. Render deploys as usual.
2. In Render > the Swarm service > Environment, add `FACTCHECK_PASSCODE` with a
   passcode of your choosing. The page asks for it once per browser session.
   Without it, anyone who finds the address can spend the Swarm's AI budget.
3. Open `https://<the Swarm address>/factcheck` in Chrome or Edge on the computer.

The checker uses the Swarm's existing `ANTHROPIC_API_KEY`. Its two database
tables (`factcheck_jobs`, `factcheck_runner`) create themselves on first use.

## Why it has a helper process

The Swarm runs on 2 web workers that each handle one request at a time, with a
180-second limit, and each worker restarts after 100 requests. A speech needs up
to six AI calls in flight at once, some lasting minutes. Run inside the web
workers, the checker would freeze every other Swarm page and the shift-work.com
APIs for the length of the speech.

So the page's requests only add a job to a queue or read a result, and each
returns in milliseconds. One separate helper process does the AI work. It starts
by itself when the first job arrives, there is never more than one, and it exits
after ten idle minutes. If it dies mid-job, the next one picks the job up again
(each job gets two tries). Its lines in the Render log start with `[FactCheck]`.

One side effect to know about: while a speech is being checked, the page asks
the Swarm for progress every two seconds. Those requests count toward the
100-request restart, so the web workers restart more often than usual during a
speech. In testing, restarts dropped no requests and lost no work.

## Optional settings (Render > Environment)

| Name | Default | What it does |
| --- | --- | --- |
| `FACTCHECK_PASSCODE` | none | Locks the checker's API behind a passcode |
| `FACTCHECK_CLAIM_MODEL` | `claude-haiku-5-5` | Model that picks out claims |
| `FACTCHECK_CHECK_MODEL` | `claude-haiku-5-5` | Model for the fast live verdict |
| `FACTCHECK_DEEP_MODEL` | `claude-sonnet-5-5` | Model for the in-depth recheck |
| `FACTCHECK_LIVE_MAX_SEARCHES` | `2` | Web searches allowed per live check |
| `FACTCHECK_DEEP_MAX_SEARCHES` | `5` | Web searches allowed per recheck |
| `FACTCHECK_DAILY_JOB_LIMIT` | `3000` | Safety cap on checker jobs per day |

## What has and has not been tested

Tested 11 November 2026, all passing:

- 24 server tests against PostgreSQL 16, in an environment built from this
  repo's `requirements.txt` (Flask 3.0.0, anthropic 2.8.0), and again with
  anthropic 0.40.0, the oldest version `requirements.txt` allows.
- 39 page checks in a real Chrome browser, served by gunicorn with this repo's
  own `gunicorn.conf.py`, including a deliberate burst of 450 requests that
  restarted the web workers four times while a check was in flight.
- The whole Swarm `app.py` started before and after the change: the same 426
  routes plus the 6 new ones, and an identical start-up log apart from the new
  "Speech Fact-Checker API registered" line.

**Not yet tested**, because the test environment had no AI key and no microphone:

- A real speech through a real microphone, heard from across the room.
- Real verdicts from the real AI models: their accuracy, speed and cost.
- The helper process on Render itself.

So the first run on Render is the first real test. Start with **Check pasted
text** and one paragraph, and look for `[FactCheck] Checking helper started` in
the Render log.

## Things to know

- **Listening** uses the speech recognition built into Chrome and Edge. It is
  free, gives little punctuation, and sends the audio to Google or Microsoft to
  be turned into text.
- **Cost.** The page shows a running estimate. A long speech with dozens of
  claims is likely to cost a few dollars, most of it the in-depth recheck, which
  can be stopped from the report.
- **Saved speeches** are kept in the browser on that one computer. The Swarm's
  database holds only the working queue, and deletes jobs after two days.
- **Sources are real.** A link is shown only if the web search returned that
  page during the check.

## Running the tests again

From the repo root, with a throwaway PostgreSQL database (the tests empty the
two `factcheck_` tables):

```
DATABASE_URL=postgresql://... python -m pytest tests/factcheck/test_factcheck_server.py
DATABASE_URL=postgresql://... python tests/factcheck/test_factcheck_page.py
```

The page tests also need `playwright` and Chrome.
