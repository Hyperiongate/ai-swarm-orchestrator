# The Humanity Index (inside the AI Swarm Orchestrator)

Added 15 November 2026, from Jim's concept doc "The Humanity Index — Concept".

Open **/humanity** on the Swarm, type any sentence ("walk instead of driving",
"end global hunger", "eat less beef"), and the Swarm answers in the same three
parts every time:

1. **Where we are** — the present condition, with 2 to 6 key figures, each
   linked to the page it came from.
2. **Why** — the causes, and where serious experts disagree.
3. **What I can do** — one concrete action and its effects for **one** time
   doing it (CO2, calories, money, time...).

## The zoom dial

Pick **how many people** (you, 10 people, 10 million, everyone who could) and
**over how long** (once, a week, a month, a year), and set times a week. The
totals change at once. "Everyone who could" is a realistic number the research
supplies, such as "people who drive regularly", not always 8.2 billion.

All the multiplying is done by the page in plain arithmetic, from the one cited
figure. The AI never makes up a big total. Each total shows its working, for
example "0.8 kg of CO2 each time × 364 million times", and its source.

## Checked by other AIs (the swarm)

After Claude's answer appears, every figure is put to the other AIs the Swarm has
keys for (GPT, Gemini, DeepSeek). Each rates every figure on its own as sound,
doubtful or wrong, without seeing the others. Each figure then shows, for
example, "3 of 3 AIs find this sound", or who doubts it, why, and their own
value. They use the same connections and settings as the fact-checker's panel
(`FACTCHECK_PANEL` limits who is asked).

The limit: the other AIs judge the figures and sources Claude found; they do not
search the web again.

## The ledger and the library

- **I did this** adds an entry to **My ledger** on the server. Nothing resets.
  The ledger shows totals for this year next to last year, all-time totals, and
  how many days in a row you have done something.
- **Asked before** keeps every answer, so reopening one costs nothing and takes
  no time.

## To deploy

1. The code is pushed to GitHub; Render deploys it as usual.
2. The page is locked until a passcode is set. In Render > the Swarm service >
   Environment, add `HUMANITY_PASSCODE`. (If it is not set, the fact-checker's
   `FACTCHECK_PASSCODE` works instead.) The page asks for it once per browser session.
3. Open `https://<the Swarm address>/humanity`. Start with one sentence and look
   for `[Humanity] Research helper started` in the Render log.

It uses the Swarm's existing `ANTHROPIC_API_KEY`. Its four database tables
(`humanity_jobs`, `humanity_runner`, `humanity_library`, `humanity_ledger`)
create themselves on first use. No change to `requirements.txt`,
`gunicorn.conf.py` or the migrations.

## Cost

One answer is one Claude Sonnet call with up to six web searches: roughly 10 to
30 cents. The page shows the estimate under the sources. The review adds one
call per other AI, billed on their own accounts. A daily safety cap of 200 AI
jobs applies (`HUMANITY_DAILY_JOB_LIMIT`).

## Files

| File | What it is |
| --- | --- |
| `templates/humanity.html` | The page. |
| `routes/humanity.py` | The page route, the passcode, and the small API. |
| `humanity_engine.py` | The instructions to the AI, the fixed answer shape, the panel review, the queue, library and ledger. |
| `humanity_runner.py` | The separate helper process that does the AI work. |
| `tests/humanity/` | The dry-run tests. Not used by the running app. |
| `app.py` | One change: the blueprint registration. |
| `swarm_security.py` | One change: the Admin Gate knows this page has its own passcode. |
| `tests/security/test_admin_gate.py` | Its list of own-login pages now includes this one. |

It borrows the fact-checker's tested AI call, its "only real links" rule and its
panel connections by importing them. Nothing in the fact-checker's files changed.
If those files are edited later, run the Humanity Index tests too.

## Optional settings (Render > Environment)

| Name | Default | What it does |
| --- | --- | --- |
| `HUMANITY_PASSCODE` | none (falls back to `FACTCHECK_PASSCODE`) | The page's passcode |
| `HUMANITY_MODEL` | `claude-sonnet-5-5` | Model that researches the answer |
| `HUMANITY_MAX_SEARCHES` | `6` | Web searches per answer |
| `HUMANITY_DAILY_JOB_LIMIT` | `200` | Safety cap on AI jobs per day |

## What has and has not been tested

Tested 15 November 2026, all passing:

- 23 server tests against PostgreSQL 16 with this repo's `requirements.txt`,
  including the real helper process, the passcode on every route, links that
  the search never returned being dropped, junk numbers being cleaned, panel
  disagreement and panel failures.
- 23 page checks in a real Chromium browser served by gunicorn with this repo's
  `gunicorn.conf.py`, including the dial arithmetic, the ratings, the ledger, the
  library, phone width and dark mode.
- The Swarm's own tests (Admin Gate, fact-checker, database, AI connections) all
  still pass, and the whole `app.py` starts with the same 348 routes plus the 11
  new ones.

**Not yet tested:** real answers from the real AI models (their quality, speed and
cost), because the test environment has no AI keys. The first question on Render
is the first real test.

## Running the tests again

Run each folder on its own; the fact-checker's tests and these each point the AI
libraries at their own stand-in service. From the repo root, with a throwaway database:

```
DATABASE_URL=postgresql://... python -m pytest tests/humanity
DATABASE_URL=postgresql://... python tests/humanity/page_checks.py
```

The page checks also need `playwright` and Chromium.
