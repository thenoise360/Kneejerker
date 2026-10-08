# Our own expected points model — Design

Date: 2026-10-08. Branch: `expected-points-model` (from `main`).
Design approved in chat by the user 2026-10-08 ("Yeah let's go with that").

## Why

The captain lean and the number on every captain option need "points this player is likely to
score next gameweek". Today that is the official game's `ep_next`, which is almost always equal to
the player's `form` (recent points per game), so a player with two big hauls tops the list.

The existing `futurePerformanceModel` cannot be fixed in place:
- it trains on `events_elements`, which stops at 2024 gameweek 14, with no season filter;
- its "next five gameweeks" window is old-season rows joined to today's players by `id`, which the
  official game re-issues every season;
- its target is season-to-date points from the same games' stats, so it is not a forecast;
- the stored values (`player_predictions`, e.g. 39.2) are a five-gameweek aggregate, not points.

Nothing else in the app reads `player_predictions`.

## Goal and success bar

Predict each player's points for the **next gameweek**. Ours replaces the official number on screen
only when a walk-forward backtest shows **both**:
1. lower mean absolute error against actual points than the official `ep_next` over the same
   player-gameweeks, and
2. its top-ranked captain choice outscores the official number's top-ranked choice more often than
   the reverse, across real squads (see "Captain test").

Until both hold, the app keeps showing the official number. The wording only changes from "The
official game expects…" to "We expect…" after the switch.

## Data (verified against the live database 2026-10-08)

| Source | What we use | Coverage |
|---|---|---|
| `elementsummary_history` | per player per gameweek: `round`, `minutes`, `goals_scored`, `assists`, `clean_sheets`, `bonus`, `total_points`, `was_home`, `opponent_team`, `fixture` | 2024 1–38, 2025 1–38, 2026 1–5 |
| `bootstrapstatic_elements` snapshots | per player per gameweek snapshot: `code`, `element_type`, `now_cost`, `chance_of_playing_next_round`, `ep_next`, season-to-date `expected_goals` and `expected_assists` (differences between snapshots give per-gameweek values) | 2024 and 2025 every gameweek, 2026 0–5 |
| `bootstrapstatic_teams` | `id`, `code` per season | all seasons |
| Match prediction engine | `build_rating_dataset` + `fit_dixon_coles` as of a past gameweek; `team_fixture_predictions` going forward | refit offline for history |

Players are matched across seasons by `code` and teams by team `code`, never by `id`.
`events_elements` is not used.

## Rows, target and features

One training row = one player, one finished gameweek **G**, in which the player's team had a match.
Target = `total_points` in G (a double gameweek sums both matches and is flagged with
`matches_in_gameweek`).

Every feature uses only information available **before G's deadline**:
- Rolling over the player's last 3 and last 5 matches (earlier gameweeks only, crossing a season
  boundary by `code`): mean points, minutes, starts (60+ minutes), goals, assists, bonus,
  clean sheets, and per-gameweek expected goals and assists from snapshot differences.
- Season-to-date points per match and minutes per match before G.
- From the snapshot taken before G: position, price, chance of playing (missing → 100).
- Fixture: home or away, `matches_in_gameweek`, and the team's and opponent's expected goals for
  G from the match engine fitted **as of G − 1**.

Players with no earlier match (new signings, first gameweek) still get a row; rolling features are
empty and the model handles missing values (no imputation to zero).

## Model

`sklearn.ensemble.HistGradientBoostingRegressor` (already installed via scikit-learn 1.6.1; no new
dependency), one model per position (goalkeeper, defender, midfielder, forward), Poisson loss
(points are non-negative counts, skewed). Hyperparameters are fixed in code and chosen once via the
backtest, not searched per run.

## Backtest (offline, the switch gate)

`FPL_site/expectedPointsBacktest.py`, run by hand: `python -m FPL_site.expectedPointsBacktest`.
- Walk forward across 2025 gameweeks 6–38 and 2026 gameweeks 1–current: for each G, train on all
  rows before G (2024 onward), predict G.
- Compare against the official `ep_next` from the snapshot taken just before G, on exactly the same
  player-gameweeks (players with both numbers).
- **Error test:** mean absolute error, ours vs official, overall and per position.
- **Captain test:** for real squads, ours' top pick vs official top pick among the starters with a
  match; count gameweeks where each scores more. Squads: the public picks of a fixed sample of
  team numbers listed in the script (fetched once and cached to a local file; never in tests).
- Writes `docs/superpowers/reports/expected-points-backtest-<date>.md` with both results and a
  pass/fail line. Historical match-engine fits are cached per gameweek so reruns are quick.

## Daily job and storage

- `FPL_site/expectedPointsModel.py`: thin fetchers, pure feature building
  (`build_feature_rows`), `train(rows)`, `predict(models, rows)`, and
  `run_daily_expected_points()` which trains on all finished gameweeks and predicts the next one.
- New table `player_expected_points` (`player_id`, `code`, `gameweek`, `expected_points`,
  `model_version`, `computed_at`; primary key `player_id, gameweek`), keyed by the gameweek the
  forecast is **for** (not the one it was made in).
- `run_update.py` calls `run_daily_expected_points()` and stops calling `run_daily_predictions()`.
  `futurePerformanceModel.py` and `player_predictions` are left in place, unused, and removed in a
  later clean-up once nothing references them.
- No fitting in any request path.

## Switch-over

Depends on `this-week-player-info` being merged. `playerContext.fetch_expected_points` is the one
switch: when `EXPECTED_POINTS_SOURCE=own` (config, default `official`) it reads
`player_expected_points` for the hub gameweek; otherwise `ep_next`. The JSON gains
`expected_points_source: "official" | "own"` so the phrase bank picks the right wording. The
switch is flipped only after a passing backtest report is committed.

## Testing

pytest-bdd `features/expected_points/`, never touching MySQL or the live API:
- no leakage: a feature for gameweek G never reads a row from G or later (scenario with a planted
  future value);
- cross-season matching by `code` when `id` changed;
- double gameweek summing and blank gameweeks (no row);
- missing history gives empty rolling features, not zeros;
- predictions are non-negative; one model per position;
- backtest comparison maths on a tiny hand-made dataset (both tests, pass and fail);
- source switch: `official` vs `own` and the wording key.

## Out of scope

Multi-gameweek forecasts, transfer recommendations from this model, removing
`futurePerformanceModel.py`, any user-facing change before the backtest passes.
