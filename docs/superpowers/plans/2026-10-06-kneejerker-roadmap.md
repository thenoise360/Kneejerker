# Kneejerker three-area build: roadmap

Each release is one pull request that ships one piece of user-facing value end to end. Each task is at most two developer days and carries its own behaviour scenarios and tests. Detailed step-by-step plans are written just in time, one per area:

- Area 1: [`2026-10-06-area1-week-page.md`](2026-10-06-area1-week-page.md), written now.
- Area 2: `…-area2-team-detail.md`, written when Area 1 ships.
- Area 3: `…-area3-momentum.md`, written when Area 2 ships.

The original brief and the Step 0 findings are in `~/.claude/plans/virtual-dancing-reddy.md`.

## Release gate (applies to every release)

A release does not open a PR until all of these pass:

1. `vs-env/Scripts/python.exe -m pytest -q`: green, and the count is no lower than the previous release.
2. `npm test`: green.
3. **Regression suite** (`tests/test_regression_routes.py`, added in 1.2):
   - every page route and every Week data route returns 200 with the flag on and off, using no network and no database
   - the flag-off Week page still contains its pre-release markers
4. `python -m py_compile` on changed Python files, and `node --check` on changed JavaScript files.
5. **Live smoke:** start the dev server against the real database with the flag on, then with it off. `curl` every page route plus the new data routes, and check for 200 and the expected copy. Then do a browser pass at 375px over each state the release touches.
6. **Independent review:** one review of the whole branch (superpowers:requesting-code-review). Every finding is fixed or explicitly answered before the PR.
7. **Product checklist** per screen:
   - no acronyms
   - the default view is a verdict plus one reason, with numbers behind an expander
   - a reason always comes with any recommendation
   - partnership framing
   - nothing shames the user
   - it makes sense to someone who has been away

Releases are stacked branches until the GitHub CLI is authenticated: each branches from the previous release's branch.

## Defaults for the open questions

These keep the work moving. Each is easy to change later.

| Question | Default used |
|---|---|
| What is "the biggest decision"? | **Known team:** a starter flagged as doubtful or out comes first. Otherwise the captain choice, using the stored `player_predictions`. **Guest:** the strongest captain option across all players. |
| The other four "decisions" | Not invented. The hub shows the real decisions only, plus one honest "more on the way" line. They become their own ticket list. |
| Area 2b backfill | **No backfill.** The record starts when logging starts, and the page says so. Reason: the absence adjustment can't be replayed honestly. |
| The Discover "Momentum" category (ownership-based) | Renamed to "Rising in popularity", because that is what it measures. The new strip is "Heating up / Cooling off". |
| Range bar (ticket 07/04) | Stays your learning exercise. The Area 2 expandable layer shows numbers as plain text. |

## Area 1: Week page

| Release | User value | Tasks (estimate) |
|---|---|---|
| **1.1** ✅ shipped | Gameweek-aware shell with friendly empty states | Resolver, phrase bank, shell, flag |
| **1.2** | "See how last week went": the guest recap with average score, standout players and why | T1 regression suite and docs (0.5d) · T2 recap data fetch (1d) · T3 standout and average phrase bank plus builder (1d) · T4 recap route, JavaScript view and wiring (1.5d) |
| **1.3** | "How did *I* do?": the personal recap and the welcome-back message | T5 add the last week's deadline to the resolver (0.25d) · T6 squad results fetch plus "one thing you got right" (1.5d) · T7 score verdict plus route extension (1d) · T8 team-number storage plus welcome-back message (1d) · T9 personal recap rendering (1d) |
| **1.4** | "What matters this week": calm deadline wording, the biggest decision with its reason, then the flag removed | T10 calm deadline wording (0.5d) · T11 biggest-decision data plus chooser (2d) · T12 decision route plus hub card (1d) · T13 remove the flag and the old Week code (1d) |

## Area 2: Team page detail

| Release | User value | Tasks (estimate) |
|---|---|---|
| **2.0** (backend only, can ship any time) | Starts the honest prediction record. Every day without it is history lost. | A1 append-only `fixture_prediction_log` table, written by `run_daily_match_predictions()` only for fixtures not yet kicked off, with `model_version` and `logged_at`; idempotent per fixture, model version and day (1d) |
| **2.1** | "How strong are they *this week*?" | A2 pure `absence_adjusted_strength()`, weighting by expected goals plus assists share for attackers and minutes share for defenders and goalkeepers (1.5d) · A3 daily job computes it from player availability and persists it per team (1d) · A4 route plus Team page strength card, with a verdict and reason by default and before/after plus who's missing in the expander (1.5d) |
| **2.2** | "Do they beat their chances?" | A5 pure `prediction_record()` verdicts, including the "early days" tier under 8 games (1d) · A6 route plus a gameweek-by-gameweek list from the log against `fixtures_fixtures` results (1.5d) · A7 copy pass, then remove `FEATURE_TEAM_DETAIL` (0.5d) |

**Data notes, verified:**
- Expected goals and assists exist only as season-to-date totals on the `bootstrapstatic_elements` gameweek snapshots, not per match. Player shares are therefore season-to-date.
- `elementsummary_history.minutes` gives the minutes share.
- `bootstrapstatic_events` holds duplicate rows per gameweek, so every query must deduplicate on `id`.

## Area 3: Player momentum

| Release | User value | Tasks (estimate) |
|---|---|---|
| **3.0** | Decision record only | M0 spike in `docs/spikes/momentum.md` (0.5d) |
| **3.1** | "Is this player rising or cooling?" on the player sheet | M1 pure `player_momentum()` covering fixtures and teammates, with signals not yet tracked marked as such (1.5d) · M2 daily job persists momentum per player (1d) · M3 player sheet label, reason, and a signal-by-signal expander using arrow plus word (1d) |
| **3.2** | The "Heating up / Cooling off" strip on Discover | M4 strip route sorted on a hidden score that is never displayed (1d) · M5 strip UI plus renaming the old category, then remove `FEATURE_MOMENTUM` (1d) |
