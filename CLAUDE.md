# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Kneejerker (FPL_site) is a Flask web app that re-renders Fantasy Premier League data — player
comparisons, transfer trends, fixture/match predictions, a live gameweek view — with a mobile-first
UI (target viewport 375–430px). It reads from a MySQL database that a set of daily offline jobs
populate from the official FPL API; there is no client-side database, and no number shown on screen
should be invented client-side — everything traces back to a backend function.

## Running the app

No test suite, linter, or build step exists in this repo (`npm test` is an unconfigured stub).
Verification is done by starting the dev server and exercising routes directly.

```bash
# Activate the local venv first if not already active (vs-env/Scripts/... on Windows)
python runserver.py                       # or: python -m flask --app FPL_site run --port 5000
SERVER_PORT=5050 python runserver.py      # override the port, e.g. to avoid a port already in use

curl -sS http://127.0.0.1:5000/get_player_index_scores
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/radar
```

Syntax-check changed files without running the whole app:
```bash
python -m py_compile FPL_site/views.py FPL_site/dataModels.py
node --check FPL_site/static/scripts/radar.js
```

Run the offline data-refresh jobs (hit the live FPL API and write to MySQL — only do this
intentionally, not as a side effect of testing a route):
```bash
python FPL_site/run_update.py
```

Config comes from a gitignored `.env` in the repo root (`FLASK_ENV`, `HOST`, `USER`, `PASSWORD`,
`DATABASE`, `MIXPANEL_TOKEN`), loaded via `FPL_site/config.py`. `FLASK_ENV=production` switches to
`ProductionConfig`; anything else defaults to `DevelopmentConfig`, which also loads `.env` itself.

## Architecture

**App wiring (`FPL_site/__init__.py`)**: creates the single global `app` and `db`
(`Flask-SQLAlchemy`) instances, wraps the WSGI app in `WhiteNoise` for static file serving, and
imports `views.py` at the bottom to register routes (routes are registered as a side effect of
import, not via an app factory or blueprints).

**Routes are thin (`FPL_site/views.py`)**: every route logs the request, delegates to a function in
`dataModels.py` / `matchPredictionEngine.py`, and either renders a template or returns `jsonify(...)`.
Page routes (`/this-week`, `/radar`, `/discovery`, `/clubs`, `/club/<id>`) render a template; the
matching `/api/...` or `/get_*` routes are what the page's own JS calls after load to fill in data.
When adding a page, add both a page route and its data route(s), following that existing pairing.

**Data layer bypasses the initialized ORM.** `db = SQLAlchemy(app)` exists in `__init__.py` only to
call `db.create_all()` once at startup — it is *not* how queries are made. Every actual query goes
through raw `mysql.connector` connections, hand-rolled per module:
- `FPL_site/dataModels.py` — the main query layer backing `views.py`; also defines
  `connect_db()`, `generateCurrentGameweek()`, `get_gameweek_state()` (live vs closed gameweek logic)
  used by other modules.
- `FPL_site/matchPredictionEngine.py` — Dixon-Coles-style match outcome model (team fixture outlook).
- `FPL_site/futurePerformanceModel.py` — per-player future performance predictions.
- `FPL_site/sqlFunction.py` — bulk upserts from the FPL API into `bootstrapstatic_*`,
  `fixtures_fixtures`, `elementsummary_*` tables.

Both `matchPredictionEngine.py` and `futurePerformanceModel.py` follow a **daily-job / live-route
split**: an expensive `run_daily_*` function fits/recomputes and persists results to a table once a
day; a cheap `load_*`/`get_*` function is what the Flask route actually calls per-request. Never do
model fitting or heavy computation inside a request path — extend the daily job and read the
persisted result instead. `FPL_site/run_update.py` is the entrypoint that chains all three daily
jobs (`update_all_tables`, `run_daily_predictions`, `run_daily_match_predictions`) for cron/manual
invocation.

Team and player IDs from the FPL API are re-issued each season — code that needs to track an entity
*across* seasons keys off its stable `code` (pulse id), not `id`.

**Templates (`FPL_site/templates/`)**: Jinja, extending `layout.html`, which defines the header,
bottom tab bar (Week / Discover / Radar / Clubs), cookie-consent banner, and a global bottom-sheet
container that page JS populates. Child templates override the `content` and `scripts` blocks.
**Gotcha**: any `<link>`/`<script>` placed outside a `{% block %}` in a child template is silently
dropped at render — this has recurred across templates, so when a page's stylesheet doesn't seem to
apply, check block placement first.

**Static assets are served twice**: once by the `WhiteNoise` middleware (`__init__.py`) and once by
an explicit `/static/<path:filename>` route in `views.py`. No bundler — `layout.html` pulls
Bootstrap 5, Popper, jQuery, Select2, and ECharts from CDNs, plus local `static/scripts/*.js`.
JS files generally pair 1:1 with a template (`radar.html` ↔ `radar.js`, `club.html` ↔ `club.js`, etc.).

`kneejerker-product-prototype.html` in the repo root is a **throwaway design mockup only** — it has
no real backend and hardcoded fake data, including a "demo controls" panel. When copying a pattern
from it, take only CSS tokens/components, markup structure, and client-side math/logic (e.g. bar
scaling, sparkline axis calculations) — never port its fake data or demo controls.

## Feature work / ticket workflow

Feature work is driven by a gitignored `Kneejerker Tasks/` folder of numbered "lists" (e.g. `07 Team
page`, `08 Discovery Page`), each a finite set of ticket `.md` files with the same shape: user story,
objective, in/out of scope, BDD (Given/When/Then) scenarios, definition of done, and technical notes
pointing at real function/file names. Lists are meant to be worked in order where dependencies exist.
Hard product requirements that apply across all tickets: no acronyms in user-facing copy, mobile-first
(375–430px primary target), and every on-screen number must trace back to a real backend function.
