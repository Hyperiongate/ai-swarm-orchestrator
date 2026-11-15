# The Humanity Index (inside the AI Swarm Orchestrator)

Added 15 November 2026, from Jim's concept doc "The Humanity Index — Concept".

## The score (added the afternoon of 15 November 2026)

The **Score** tab (the first tab) gives one number from 0 to 100 for how we are
doing as people, for the **world**, **Marin County**, or any place you type or say.

- **0** is the worst conditions seen in modern times; **100** is an ideal world
  (Jim's choice).
- It is built from **12 categories**: health and long life, basic needs, quality
  of life, freedom of choice, lack of oppression, fair shares, care for the planet,
  ability to aspire, science and discovery, peace and safety, honest government,
  kindness and community. Jim rated all 12 "most important", so **they count
  equally**. "Change what counts" lets a viewer try their own weights (kept in
  that browser only).
- Each category uses **fixed, named measures** (26 in all), each with a stated
  value that scores 0 and a value that scores 100, and the reason. For example,
  life expectancy scores 0 at 25 years and 100 at 90 years. A measure's score
  is where the real value sits between the two; a category is the average of its
  measures; the overall score is the average of the categories. The whole
  scorecard is in `humanity_score.py` (`SCORECARD`), and every end point is
  shown on the page next to its measure.
- **Work out the score** sends the swarm to find the latest value of every
  measure for that place: one research job per category, with web search, at
  the most local level published (county, then state, then country; the page
  says which). It takes a few minutes and roughly $1 to $2. The other AIs then
  check every value, and each measure shows how many agree.
- **Every run is kept.** The score changes only when you refresh it with new
  data, and the page shows the change since the last run and the earlier scores.
- On test data close to real world figures, the world scores about 57.

## Voice

The microphone buttons (Chrome and Edge) let you speak a question on **Ask** or a
place on **Score**. On Ask, a question about the score ("what's the score for
Marin County?") opens the Score tab for that place; anything else is researched
as a question.

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

It uses the Swarm's existing `ANTHROPIC_API_KEY`. Its six database tables
(`humanity_jobs`, `humanity_runner`, `humanity_library`, `humanity_ledger`,
`humanity_score_runs`, `humanity_score_values`) create themselves on first use. No change to `requirements.txt`,
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
| `humanity_score.py` | The scorecard (12 categories, 26 measures and their end points), the research for each category, the scoring, and the saved runs. |
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
| `HUMANITY_DAILY_JOB_LIMIT` | `200` | Safety cap on AI jobs per day (one score run uses 13) |
| `HUMANITY_SCORE_MODEL` | `claude-sonnet-5-5` | Model that looks up the score's measures |
| `HUMANITY_SCORE_MAX_SEARCHES` | `4` | Web searches per category |

## What has and has not been tested

Tested 15 November 2026 (and again that afternoon with the score and voice), all passing:

- 34 server tests against PostgreSQL 16 (11 of them for the score: the scoring
  rule checked independently, both directions of a measure, a failed category,
  nothing found, invented links, history, the real helper process, the AI check) with this repo's `requirements.txt`,
  including the real helper process, the passcode on every route, links that
  the search never returned being dropped, junk numbers being cleaned, panel
  disagreement and panel failures.
- 40 page checks in a real Chromium browser, including the score, the weights,
  history, places and voice (with a simulated microphone), served by gunicorn with this repo's
  `gunicorn.conf.py`, including the dial arithmetic, the ratings, the ledger, the
  library, phone width and dark mode.
- The Swarm's own tests (Admin Gate, fact-checker, database, AI connections) all
  still pass, and the whole `app.py` starts with the same 348 routes plus the 19
  new ones.

**Not yet tested:** real answers from the real AI models (their quality, speed and
cost), and a real microphone, because the test environment has neither. The first
question and the first score on Render are the first real tests.

## Running the tests again

Run each folder on its own; the fact-checker's tests and these each point the AI
libraries at their own stand-in service. From the repo root, with a throwaway database:

```
DATABASE_URL=postgresql://... python -m pytest tests/humanity
DATABASE_URL=postgresql://... python tests/humanity/page_checks.py
```

The page checks also need `playwright` and Chromium.
