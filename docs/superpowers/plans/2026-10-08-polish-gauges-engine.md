# Polish: Display Fixes, Gauges and Engine Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix the remaining issues from the three-area build, apart from the This Week page, which another session owns:
- Radar summary numbers
- acronyms and low-contrast labels
- the momentum and strength cards matching site styling, with gauge visuals
- low-data team ratings
- prediction rows surviving a season rollover

**Architecture:**
- Pure JavaScript view and helper modules in `static/scripts/lib/` are tested with `node --test`.
- Python fixes have pytest tests.
- The engine change is validated with the existing `backtest_model()`.
- Each release ships to main after an Opus review. The user authorised this on 2026-10-07.

**Out of scope, owned by another session:**
- `templates/home.html`, `templates/partials/week_v2.html`
- `static/scripts/home.js`, `weekV2.js`, `liveGameweek.js`
- the This Week hub and decisions
- any Week-only lib module

Do not touch these.

## Global Constraints

The constraints in `docs/superpowers/plans/2026-10-06-area1-week-page.md` → Global Constraints all apply.

**Copy rules**
- No acronyms in user-facing copy. This includes "GW", position codes ("MID") and three-letter team codes.
- Plain language by default and numbers on demand. Gauges carry **no digits**: numbers live in `<details>`.

**Visual rules**
- Plus Jakarta Sans. Use the existing type scale:
  - player-sheet slides follow `.mini-card` / `.mc-title` (12.5px uppercase, 700) / `.mc-caption` (11.5px grey) in `home.css`
  - Team page cards follow `.card` / `.outlook-row` sizes
  - no new font sizes above 16px in cards
- Colours come from the `:root` tokens in `style.css`.
- Text contrast is at least 4.5:1, and no meaning is carried by colour alone.
- Focus states are visible. Motion is 150–250ms ease-in-out.

**Hidden scores**
- The momentum score never reaches the browser.
- A momentum gauge shows the **label zone** (Cooling / Steady / Rising), never a position derived from the score.

**Engine rule**
- No model fitting in a request path.
- Any change to ratings must be backed by `backtest_model()` evidence in the report.

**Housekeeping**
- Every test module starts with `import os; os.environ.setdefault('KJ_SKIP_DB_INIT', '1')`.
- Never use the database or network in tests. Never run `run_update.py` or the daily job.
- Restore `FPL_site/__pycache__` before committing.

---

# Release P1: "Right numbers, plain words"

### Task 1: Radar summary card numbers

**Files:**
- Modify `FPL_site/dataModels.py`, in `get_player_last_5_points`.
- Modify `FPL_site/static/scripts/radar.js`, in `buildSummaryCard` and any other card that sums the last five games.
- Add pure helpers in a new `FPL_site/static/scripts/lib/numbers.js`.
- Tests: `tests/test_last5_points.py` and `tests/js/numbers.test.js`.

**The bug.** `SUM()` returns MySQL Decimals, which JSON serialises as strings. In JavaScript, `reduce((a, b) => a + b, 0)` then concatenates them, producing "021311714 pts". The position average is never rounded either ("16.240000000000002").

**Fix:**
- In Python, cast `points`, `minutes` and `difficulty` to `int` (or None) in the returned rows. Test this with a FakeCursor returning `Decimal`s.
- In JavaScript, add `sumNumbers(values)`, which coerces with `Number`, ignores non-finite values, and returns a number. Add `formatPoints(value)`, which rounds to one decimal and drops a trailing ".0". Use both wherever radar.js sums or prints last-five values and averages:
  - the Summary card
  - the Form card's caption
  - any "Position average" text

**Node tests:**
- `sumNumbers(['0','2','13'])` returns 15.
- `formatPoints(16.240000000000002)` returns '16.2'.
- `formatPoints(15)` returns '15'.
- `formatPoints(null)` returns '0'.

**Acceptance:** run a manual grep for `reduce((a, b) => a + b` in radar.js. Every remaining use must operate on coerced numbers.

### Task 2: Plain words on Discover

**Files:**
- Modify `FPL_site/static/scripts/discovery.js`, in `createPlayerCard` and the search result rows.
- Modify `FPL_site/dataModels.py`, in `get_new_manager_players`.
- Tests: `tests/js/` for a new pure helper, and pytest for the new-manager copy.

**Fix:**
- Cards and search rows show the position via the existing `POSITION_LABELS` map (`discovery.js:39`), for example "Midfielder" instead of "MID". Keep the raw code in data attributes and in the comparison logic, which still needs the codes.
- Put the label lookup in a pure exported helper `positionLabel(code)` in a new `lib/positions.js`. Re-use it from `discovery.js`, and keep the `POSITION_LABELS` constant as the single source.
- Change the new-manager copy from `"New manager ({name}) since GW{n} - role could change."` to `"New manager ({name}) since gameweek {n}. Their role could change."` Test the exact string.

### Task 3: Header and label contrast

**Files:**
- Modify `FPL_site/static/scripts/script.js`, in `updateHeaderInfo`.
- Modify `FPL_site/static/content/style.css`, adding a token.
- Modify `FPL_site/static/content/home.css`, in `.eyebrow-sm` and `.mc-title`.
- Modify the deadline text style wherever it is set.
- Tests: `tests/js/contrast.test.js`, plus the pure helper in a new `lib/contrast.js`.

**Fix:**
- **Header pill:** change `GW ${n}` to `Gameweek ${n}`. Make sure the pill doesn't wrap at 375px; reduce the pill's letter-spacing or padding if needed.
- **Contrast token:** add `--pink-ink` to `:root`. It is a darker brand pink for **text** with at least 4.5:1 contrast on `#FFFFFF` and on `--offwhite` `#F9F9F9`. Pick a value and prove it with the test below.
- **Apply the token:** use `--pink-ink` for `.eyebrow-sm`, `.mc-title` and the header deadline text. Leave `--pink` for fills and accents.
- **Contrast helper:** add a pure `contrastRatio(hexA, hexB)` using the WCAG relative-luminance formula.
- **Contrast tests:**
  - the chosen `--pink-ink` against `#FFFFFF` and `#F9F9F9` is at least 4.5
  - charcoal `#333333` against white is at least 4.5
  - a sanity check that black against white is 21

**Release P1 gate:**
- Full suites pass.
- Live smoke of `/radar`: open a player sheet and check the Summary card shows sane totals.
- `/discovery`: cards show "Midfielder".
- Header reads "Gameweek N" on several pages.
- Browser check at 375px.
- Opus review, then ship to main.

---

# Release P2: "Cards that look like the site, with gauges"

### Task 4: Gauge helper

**Files:**
- Create `FPL_site/static/scripts/lib/gauge.js`.
- Create `tests/js/gauge.test.js`.

**Interface:** `renderGauge({ value, min, max, marker = null, leftLabel, rightLabel, centreLabel, ariaLabel, zones = null })` returns an inline SVG string.

**Shape:**
- A semicircle arc, 160×90 viewBox, that scales to its container width with `width:100%; max-width:200px`.
- A track in `--grey`.
- A filled arc from `min` to `value` in `--plum`.
- If `marker` is given, a small tick in `--teal` at that position (the "usual" level).
- A needle dot at `value`.
- `value` and `marker` are clamped to `[min, max]`.

**Zones (optional):** `[{ from, to, label }]` draws the arc in segments with gaps between them.

**Text:**
- Word labels: `leftLabel` at the left end, `rightLabel` at the right end, `centreLabel` under the needle.
- **No digits in any SVG text.**
- `role="img"` with an `aria-label`.
- All label text goes through `escapeHtml`.

**Node tests:**
- the output contains `role="img"` and the escaped aria-label
- there are no digits in any `<text>` content
- out-of-range values are clamped: the needle angle at `value > max` equals the angle at `max`
- the marker is omitted when null
- a zones gauge produces one arc path per zone

The tests check angle maths through an exported pure `valueToAngle(value, min, max)`: 180° at min, 0° at max, 90° in the middle.

### Task 5: Team strength card, restyled with gauges

**Files:**
- Modify `FPL_site/static/scripts/lib/strengthView.js`.
- Modify `FPL_site/static/content/home.css`, adding scoped `.strength-*` classes.
- Test: `tests/js/strengthView.test.js`.

**Layout.** Match the Team page cards (`.card` plus the `outlook-row` type sizes):
- **Eyebrow:** keep the existing "How strong are they this week".
- **Verdict line:** the headline, at the same size and weight as `.outlook-phrase`. Check `home.css` for the actual values; no 17px.
- **Reason:** in `.sub`.
- **Gauges:** two side by side, each 50% width, stacked on very narrow screens.
  - **Attack:**
    - `value = scored_adjusted / league_scored`
    - `marker = scored / league_scored` (usual)
    - `min = 0.5`, `max = 1.5`
    - labels "Weaker", "Stronger", and centre "Attack"
  - **Defence:**
    - `value = league_scored / conceded_adjusted`, so higher means it concedes less
    - `marker = league_scored / conceded`
    - same range
    - labels "Leakier", "Tighter", and centre "Defence"
  - Each gauge has an aria-label such as "Attack: a little weaker than usual, about average for the league", built from words only.
  - Under each gauge, a one-word caption: "Usual" next to a teal tick swatch, and "This week" next to a plum dot swatch, so the legend doesn't rely on colour alone.
- **Details:** keep `<details class="recap-details">`/"See the numbers" with the existing numbers, plus the missing players list.

**Payload.** `league_scored` must be in the strength payload. If `load_team_strength` doesn't include it, add it in `FPL_site/teamStrength.py` with a test. Handle `league_scored` being missing or 0 by leaving out the gauges, so a "not ready" state stays calm.

**Node tests:**
- two gauges render for a ready payload
- no digits appear before `<details`
- the gauge values computed for a sample payload are correct
- the not_ready state is unchanged

### Task 6: Momentum slide, restyled with a zone gauge

**Files:**
- Modify `FPL_site/static/scripts/lib/momentumView.js`.
- Modify `FPL_site/static/content/home.css`, removing `.momentum-verdict` if it becomes unused.
- Test: `tests/js/momentumView.test.js`.

**Layout.** Match the other player-sheet slides exactly:
- `<div class="mini-card mini-slide">`
- `<div class="mc-title">Momentum</div>`
- a zone gauge:
  - `zones = Cooling | Steady | Rising`
  - the needle sits at the centre of the label's zone, never a score-derived position
  - `centreLabel` is the label word
  - `leftLabel` "Cooling", `rightLabel` "Rising"
- the reason as a short line at the existing mini-card body size, with the label prefix stripped as now
- each signal as an existing-style row: arrow, name and word, with the signal reason in `.mc-caption`-sized text
- an `.mc-caption` explaining in plain words what momentum looks at, for example "Looks at upcoming fixtures and key teammates coming in or out."

Remove the `<details>` if the signals now fit on the slide without it. Mini-slides show their numbers directly, and these signals carry no digits.

**Not ready:** the not_ready state also uses the mini-card markup, with the title and a caption-style message.

**Node tests:**
- the slide uses the `mini-card mini-slide` and `mc-title` classes
- the needle zone matches the label for each of Rising, Steady and Cooling
- no score is used: pass a payload with an extra `score` and assert the output is identical without it
- arrows are paired with words
- values are escaped

**Release P2 gate:**
- Full suites pass.
- Live smoke, then a browser check at 375px: open the Team page for three teams, and the Radar player sheet's momentum slide for a Rising, a Steady and a Cooling player.
- Compare type sizes against the neighbouring cards.
- Opus review, then ship to main.

---

# Release P3: "Fairer ratings for promoted teams"

### Task 7: Shrink low-data team ratings

**Files:**
- Modify `FPL_site/matchPredictionEngine.py`, in `_dixon_coles_nll` and `fit_dixon_coles`, plus new constants.
- Test: `tests/test_engine_shrinkage.py`.

**The bug.** Teams with almost no data, such as newly promoted Coventry City with 5 games in the pool, get extreme maximum-likelihood ratings. Coventry's attack is −1.75 against a league range of about −0.4 to +0.25, which is about 0.26 goals a game.

**Fix:** add an L2 penalty that pulls each team's attack and defence towards a prior:
```
penalty = SHRINKAGE * Σ_i [(attack_i − prior_att_i)² + (defence_i − prior_def_i)²]
```
- The prior is the league average (0, 0) for teams with at least `ESTABLISHED_GAMES = 38` pooled fixtures.
- Teams with fewer pooled fixtures get `PROMOTED_PRIOR = (attack, defence)`, a typical promoted side. Derive it from data: the mean fitted rating of teams in their first season in the pool, computed once in the backtest script. Record the values and how they were derived in a code comment.
- Because the penalty works against a fixed number of pooled games, a team with plenty of data barely moves.

**Choosing `SHRINKAGE`:**
- Use `backtest_model(target_season=2025, holdout_gw=…)`. Read it first; it is read-only and fits from the database.
- Compare mean absolute error before and after at holdouts 6, 15 and 25.
- Pick the smallest value that does not worsen overall error by more than 0.01 goals and improves error for promoted teams.
- Put the table of results in the report.

**Tests**, using small synthetic fixture lists with no database:
- a team with 3 games and an extreme result fits closer to its prior than with a shrinkage of 0
- a team with 100 games barely moves, by less than 0.02
- the prior choice switches at `ESTABLISHED_GAMES`

Note that `fit_dixon_coles` fixes `attack_0 = 0` for identifiability. Make sure the penalty doesn't fight that constraint, or switch to a sum-to-zero constraint if needed, and explain the choice.

**Acceptance:** a read-only dry run on today's data shows Coventry City's attack inside the league range, and no team below about 0.7 goals a game against an average side. Put the dry-run table in the report. **Never persist anything.**

### Task 8: Prediction rows survive a season rollover

**Files:**
- Modify `FPL_site/matchPredictionEngine.py`, in `persist_match_predictions`.
- Test: `tests/test_prediction_persist.py`.

**The bug.** `persist_match_predictions` only deletes rows with `gameweek < min(new)`. At a season rollover, last season's rows for gameweek 1 and up survive, and can inflate sums elsewhere.

**Fix:** fully replace the table each run. DELETE all rows, then INSERT the new ones, in the same transaction and with one commit. This matches `persist_team_strengths`. If there are no new rows, do nothing, as today, rather than wiping the table.

**Test:** a FakeConn records the SQL and asserts:
- an unconditional `DELETE FROM team_fixture_predictions` comes before the inserts
- there is one commit
- no-rows means no SQL

**Release P3 gate:**
- Full suites pass.
- The backtest table is in the report.
- Read-only dry run of ratings and team strength copy for all 20 teams.
- Opus review.
- Ship to main. New ratings apply from the next daily run.
