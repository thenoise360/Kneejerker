# Area 3: Player momentum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show whether a player is Rising, Steady or Cooling, with one plain-English reason. It appears in two places:
- the player sheet, where each signal can be expanded separately
- a "Heating up / Cooling off" strip on Discover

**Architecture:** This follows the daily-job/live-route split.
- **Momentum function.** A pure `player_momentum()` in `FPL_site/playerMomentum.py` turns signal inputs into a label, a reason and a signal list. Signals we don't track yet are returned as `not_tracked`.
- **Daily job.** A daily step, called from `run_daily_match_predictions()` after `team_strength` is written (Area 2), computes momentum for every player and replaces the `player_momentum` table.
- **Routes.** `/api/player/<id>/momentum` and `/api/discover/momentum-strip` only read from that table.
- **Front end.** The sheet card in `radar.js` (`buildMiniCards`) and the Discover strip in `discovery.js` render through the pure `lib/momentumView.js`. Both sit behind `FEATURE_MOMENTUM` until Task 5.

**Tech Stack:** Python 3.11, Flask, mysql.connector, pytest and pytest-bdd, and vanilla ES modules tested with `node --test`.

**Spec:**
- `~/.claude/plans/virtual-dancing-reddy.md` (the "Area 3" section)
- `docs/spikes/momentum.md`, which holds the signal decisions

## Global Constraints

All Area 1 Global Constraints apply (`docs/superpowers/plans/2026-10-06-area1-week-page.md`). On top of those:

**Signals**
- Momentum must **never** be built from the player's own minutes, the Influence, Creativity and Threat index, or form.
- Teammates' minutes may be used only to detect *who was missing last gameweek*.

**Display**
- Each signal is shown as an arrow plus a word: `↑ Up`, `→ No change`, `↓ Down`, `– Not tracked yet`. It is never shown by colour alone.
- **The hidden sort score is never sent to the browser.** The strip route sorts on the server and omits the score from its JSON. A test enforces this.
- Labels are exactly `Rising`, `Steady` and `Cooling`.

**Fixed signal keys and order:** `fixtures`, `teammates`, `position`, `manager`. Position and manager are always `not_tracked`, per the spike.

## Review Focus

1. **Player on a team with no fixture in the window.** The fixtures signal is 0 with the reason "No game this week", and there is no crash. *Task 1:* `test_blank_gameweek_fixtures_signal`.
2. **A key teammate who has left the club** (`status 'u'`). They are neither "back" nor "out". *Task 1:* `test_departed_teammate_ignored`.
3. **The hidden score leaking to the browser.** *Task 4:* `test_strip_never_exposes_score`.
4. **Momentum not computed yet** (no table or no row). The sheet card shows a calm "Momentum is on its way" message and the strip is hidden, never an error. *Tasks 3 and 4.*
5. **A goalkeeper or defender.** The fixtures signal uses expected goals *against*. An easier run means fewer goals against, which is Up. *Task 1:* `test_defender_fixture_direction`.

---

# Release 3.1: "Is this player rising or cooling?" (player sheet)

### Task 1: Pure momentum function and phrase bank

**Files:**
- Create: `FPL_site/playerMomentum.py` (pure)
- Create: `FPL_site/momentumCopy.py`
- Create: `features/momentum/player_momentum.feature`
- Create: `tests/step_defs/test_player_momentum.py`
- Create: `tests/test_player_momentum.py`

**Interfaces:**

Constants:
```python
FIXTURE_WINDOW = 3                 # gameweeks ahead
FIXTURE_CHANGE_FROM = 0.10         # ±10% easier or harder than an average opponent
KEY_TEAMMATE_SHARE = 0.15          # share of team expected goals + assists
OUT_BELOW_CHANCE = 50              # chance of playing below this = out
ATTACKING = (3, 4)                 # midfielder, forward
```

Functions:
- `fixtures_signal(position, upcoming, baseline_for, baseline_against) -> Signal`
  - `upcoming` is a list of the team's fixtures in the window, each `{'own_mean', 'opp_mean'}` (expected goals for and against).
  - `baseline_for` and `baseline_against` are goals for and against versus an average side (from `team_strength`).
  - Attacking players compare the mean of `own_mean` with `baseline_for`. Goalkeepers and defenders compare the mean of `opp_mean` with `baseline_against`, inverted.
  - `ratio - 1 >= 0.10` gives `up` with the reason `"kinder fixtures coming up"`. `<= -0.10` gives `down` with `"tougher fixtures coming up"`. Anything in between gives `same` with `"fixtures look about average"`.
  - An empty `upcoming` gives `same` with `"no game this week"`.
  - `magnitude = abs(ratio - 1)`.
- `teammates_signal(player_id, teammates) -> Signal`
  - `teammates` is a list of `{'id', 'name', 'share', 'status', 'played_last', 'chance'}`, excluding the player.
  - Key teammates have `share >= 0.15` and `status != 'u'`.
  - Back: `not played_last` and (`chance is None or chance >= 50`).
  - Out: `played_last` and `chance is not None and chance < 50`.
  - More back than out gives `up`, with the reason `"{name} is back in the team"` (one back) or `"key teammates are back"` (several).
  - More out than back gives `down`, with `"{name} is out"` or `"key teammates are out"`.
  - Otherwise `same`, with `"no change around them"`.
  - `magnitude` is the sum of the key shares involved.
- `not_tracked(key) -> Signal` returns `{'key', 'direction': 'not_tracked', 'reason': None, 'magnitude': 0}`.
- `player_momentum(fixtures, teammates) -> {'label', 'reason', 'signals': [4 signals in fixed order], 'score': float}`
  - `total = sum(+1 up, -1 down)` over the tracked signals.
  - A total of +1 or more is `Rising`, -1 or less is `Cooling`, otherwise `Steady`.
  - `reason` is `momentum_reason(label, strongest)`. The strongest is the tracked signal pointing the same way as the label with the highest magnitude.
  - `score = total + 0.1 * signed magnitude sum`. It is used for sorting only and is never sent to the browser.

Signal shape: `{'key': str, 'direction': 'up'|'same'|'down'|'not_tracked', 'reason': str|None, 'magnitude': float}`.

`momentumCopy.py`:
- `momentum_reason(label, signal) -> str`
  - Rising: `f"Rising: {signal['reason']}."` with the first letter of the reason capitalised, for example "Rising: kinder fixtures coming up." The reason should read as one sentence.
  - Steady: `"Steady: nothing much has changed for them this week."`
  - Cooling: `f"Cooling: {signal['reason']}."`
- `DIRECTION_WORDS = {'up': 'Up', 'same': 'No change', 'down': 'Down', 'not_tracked': 'Not tracked yet'}`
- `SIGNAL_NAMES = {'fixtures': 'Fixtures', 'teammates': 'Teammates', 'position': 'Position on the pitch', 'manager': 'Manager change'}`

Copy rules: no digits and no acronyms in any reason.

- [ ] **Step 1: Scenarios.** In `player_momentum.feature`:
  - **Happy path:** a forward with kinder fixtures and a key teammate back is `Rising`, with a reason mentioning fixtures, because fixtures has the bigger magnitude in the given data.
  - **Missing data:** a player whose team has no game in the window, and no teammate changes, is `Steady`, and position and manager are "not_tracked".
  - **Returning user:** a defender whose next three are tougher and whose key midfielder is out is `Cooling`.
- [ ] **Step 2: Unit tests.** In `tests/test_player_momentum.py`:
  - Both sides of ±0.10 for attackers and for defenders, including `test_defender_fixture_direction`.
  - `test_blank_gameweek_fixtures_signal`.
  - KEY_TEAMMATE_SHARE at 0.15 versus 0.149.
  - OUT_BELOW_CHANCE at 49 versus 50.
  - `test_departed_teammate_ignored`.
  - One back versus several back wording.
  - The label thresholds.
  - The fixed signal order.
  - A no-digit and acronym check over every reason.
  - Run them and expect an ImportError.
- [ ] **Step 3:** Implement with small pure functions, run the suite, then commit.

### Task 2: Daily computation and persistence

**Files:**
- Modify: `FPL_site/playerMomentum.py` (fetchers, `build_all_momentum`, `persist_momentum`, `load_player_momentum`, `load_momentum_strip`)
- Modify: `FPL_site/matchPredictionEngine.py` (call after `persist_team_strengths`)
- Test: `tests/test_player_momentum_data.py`

**Interfaces:**

Fetchers. Each takes a cursor:
- `fetch_player_rows(cursor, year_start)` reads the latest `bootstrapstatic_elements` snapshot: `id, web_name, team, element_type, status, chance_of_playing_next_round, expected_goals, expected_assists`.
- `fetch_last_gameweek_minutes(cursor, year_start, gameweek)` returns `{element: minutes}`, summed over a double gameweek.
- `fetch_upcoming_predictions(cursor, from_gw, to_gw)` returns `team_fixture_predictions` rows: `team_id, gameweek, expected_goals_mean AS own_mean`, plus the opponent's `expected_goals_mean` via a self-join on `fixture_code` (copy the self-join from `load_team_fixture_outlook`).
- `fetch_team_baselines(cursor)` returns `{team_id: {'scored', 'conceded'}}` from `team_strength`. If the table is missing (error 1146), it returns `{}`. The fixtures signal then falls back to the league mean of `own_mean` across all upcoming rows as the baseline.

`build_all_momentum(players, last_minutes, upcoming, baselines) -> {player_id: momentum}`:
- Pure.
- Shares are computed per team as in Area 2: expected goals plus assists, excluding status `'u'`.
- Skip players with status `'u'`.

`MOMENTUM_TABLE = 'player_momentum'`. Columns: `player_id INT PRIMARY KEY, name VARCHAR(60), team_id INT, position INT, label VARCHAR(10), reason VARCHAR(200), signals_json TEXT, score FLOAT, computed_at DATETIME`. The table is fully replaced each run.

`load_player_momentum(player_id)` returns one of:
- `{'status': 'ready', 'label', 'reason', 'signals': [{key, name, direction, word, arrow, reason}]}`
- `{'status': 'not_ready', 'message': {'title': 'Momentum is on its way', 'body': "We're still working this out. Check back a little later."}}`

Arrows are `↑ → ↓ –`. The score is **not** included.

`load_momentum_strip(limit=5)` returns `{'heating_up': [...], 'cooling_off': [...]}`:
- Each item is `{'id', 'name', 'team' (full team name), 'reason'}`.
- Rising players are sorted by score descending and Cooling players by score ascending.
- Each list is capped at `limit`.
- The score is **not** included.

- [ ] **Steps:**
  1. Write failing tests:
     - `build_all_momentum` with dict fixtures, including a double-gameweek minutes sum, status `'u'` skipped, and the missing-baselines fallback.
     - Persist with a FakeConn.
     - `load_*` with a monkeypatched `connect_db`: ready, not_ready, and the strip ordering. Assert that `'score'` appears in no item of either list.
  2. Implement.
  3. Read-only real-database dry run that computes but does not persist: `build_all_momentum(...)` on real rows. Print the counts per label and three example reasons; they should be plausible.
  4. Run the full suite and commit.

### Task 3: Player sheet card

**Files:**
- Modify: `FPL_site/views.py`: add the route `/api/player/<int:player_id>/momentum` (200 / 404 unknown player / 500). Also pass a `momentum` flag to the radar and discovery templates, from `FEATURE_MOMENTUM`, using the same mechanism as `FEATURE_WEEK_V2`.
- Modify: `FPL_site/config.py` (`FEATURE_MOMENTUM`).
- Create: `FPL_site/static/scripts/lib/momentumView.js`, with `renderMomentumCard(payload)` and `renderStripItem(item)`.
- Modify: `FPL_site/static/scripts/radar.js`:
  - `openPlayerProfile` fetches `/api/player/${playerId}/momentum` alongside the others, using `fetchJsonSafe`.
  - `buildMiniCards` appends a momentum mini-card when `document.body.dataset.momentum === 'true'`.
- Modify: `FPL_site/templates/layout.html`: add `data-momentum="{{ 'true' if momentum else '' }}"` on `<body>` only if the body tag already accepts template context. Otherwise put a hidden `<div id="feature-flags" data-momentum=...>` inside the radar content block. Pick whichever needs fewer changes outside scope, and note the choice in the report.
- Test: `tests/js/momentumView.test.js`, `tests/test_momentum_routes.py`, `tests/test_regression_routes.py` (add the stub).

**What `renderMomentumCard` must do:**
- Show the label and reason as `<h3 class="recap-verdict">` plus a `<p>`.
- Put a `<details><summary>See each signal</summary>` after them, with one row per signal: `<span aria-hidden="true">{arrow}</span> {name}: {word}`, plus the signal's reason in a `.sub` when it has one.
- Use escaped values throughout.
- Render `not_ready` through `renderMessage`.

**Node tests:**
- Default view is the label and reason only.
- All four signals appear inside `<details>`.
- Every arrow is paired with a word, so meaning never rests on colour alone.
- "Not tracked yet" appears for position and manager.
- Values are escaped.
- No digits appear.

- [ ] **Steps:** write failing tests, implement, wire it up, then run the suites, `node --check radar.js` and commit.

**Release 3.1 gate:** run the roadmap gate.
- Live smoke: the route returns `not_ready` until the daily job has run. Do a read-only dry-run compute for a known player and check the card renders that payload in the browser at 375px, by stubbing the fetch in the browser console.
- Ship to main.

---

# Release 3.2: "Heating up / Cooling off" on Discover

### Task 4: Strip route and Discover strip

**Files:**
- Modify: `FPL_site/views.py`: add the route `/api/discover/momentum-strip` and pass the `momentum` flag to `discovery.html`.
- Modify: `FPL_site/templates/discovery.html`: add the flag hook.
- Modify: `FPL_site/static/scripts/discovery.js`:
  - add `heatingUp: 'category-heating-up'` to `CATEGORY_SLOTS`, but only when the flag is on
  - add `loadHeatingUpCategory()`, which renders two groups, "Heating up" and "Cooling off", using the existing `renderCategory`/`createPlayerCard` patterns
  - each player shows one reason (`why: item.reason`)
  - hide the strip (remove the skeleton) when both lists are empty or `not_ready`
- Test: `tests/test_momentum_routes.py` (including `test_strip_never_exposes_score`, which asserts `'score'` is absent from the JSON text), and `tests/test_regression_routes.py`.

**Steps:**
- [ ] Write failing tests.
- [ ] Implement.
- [ ] Do a browser check of Discover at 375px with the flag on, stubbing the route payload via a test request.
- [ ] Commit.

### Task 5: Remove `FEATURE_MOMENTUM`

- [ ] Delete the flag from `config.py`, the templates, views and JS checks, and the flag-off tests.
- [ ] The regression suite asserts that the sheet route and the strip route are registered and that Discover renders.
- [ ] Run `grep -rn "FEATURE_MOMENTUM\|data-momentum" FPL_site tests`. Expect no matches apart from intentional data attributes, if you kept them.
- [ ] Run the full suites and commit.

**Release 3.2 gate:** run the roadmap gate, then ship to main.
