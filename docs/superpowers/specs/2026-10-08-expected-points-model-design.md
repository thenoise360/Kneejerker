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
- No fitting in any request path.

## Weekly record: how accurate were we? (user requirement 2026-10-08)

Every gameweek's forecasts are kept forever so we can look back and say how accurate we were.
Same honesty rule as the match engine's `fixture_prediction_log`: only forecasts made **before
the gameweek's deadline** count.

- **`expected_points_log`** (append-only, never updated or deleted): `player_id`, `code`,
  `gameweek` (the gameweek forecast), `expected_points` (ours), `official_expected_points`
  (`ep_next` from the same day's snapshot, so the comparison is like for like), `model_version`,
  `logged_at`, `log_date`. Primary key `player_id, gameweek, model_version, log_date`, written with
  `INSERT IGNORE`, so re-running the job on the same day changes nothing. The daily job only logs
  when `now` is before that gameweek's deadline (`deadline_time` from the official `bootstrap-static` events, read the same way as `dataModels.get_gameweek_state`; the daily job already calls that API).
- **The forecast of record** for a gameweek is each player's latest log row before the deadline
  (pure `forecast_of_record(log_rows, deadline)`).
- **`expected_points_accuracy`**: one row per gameweek per model version, written by the daily job
  once every fixture in that gameweek is finished and bonus is confirmed. Holds the number of
  players, our mean absolute error, the official number's mean absolute error over the same
  players, both per position too (as JSON), and the captain test for that week (the fixed sample
  squads: how often our top pick outscored the official one, and the reverse). Pure
  `accuracy_for_gameweek(record, actual_points, squads)`. Recomputed rows replace the previous
  row for that gameweek and version (actual points can be corrected after the fact).
- The log starts recording from the first daily run, while the app still shows the official
  number, so the real season builds up its own track record alongside the backtest.
- Showing this record to managers (for example in Last week or the prediction-log area) is a later
  piece of work; this spec only stores and computes it.

## Daily job wiring

- `run_update.py` calls `run_daily_expected_points()` and stops calling `run_daily_predictions()`.
  `futurePerformanceModel.py` and `player_predictions` are left in place, unused, and removed in a
  later clean-up once nothing references them.

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
- source switch: `official` vs `own` and the wording key;
- weekly record: a log row written after the deadline is refused; same-day reruns add nothing;
  the forecast of record is the latest pre-deadline row; accuracy is only computed for finished
  gameweeks and is replaced (not duplicated) on recompute.

## Out of scope

Multi-gameweek forecasts, transfer recommendations from this model, removing
`futurePerformanceModel.py`, any user-facing change before the backtest passes, a page showing the weekly record.

## Amendment 2026-10-08: seasons on every row, and backfilling past seasons (user requirement)

**Season on every prediction.** Player ids are re-issued every season, so every stored forecast
carries `year_start`: `expected_points_log` and `player_expected_points` gain a `year_start`
column, and it joins their primary keys (log: `year_start, player_id, gameweek, model_version,
source, log_date`; current: `year_start, player_id, gameweek`). Every reader filters by season.

**Backfill.** Past seasons can be filled in by replaying the model gameweek by gameweek with only
the data available at the time: for target gameweek G, train on gameweeks strictly before G, use
the snapshot taken after G − 1 (price, availability, the official `ep_next`), the match engine
fitted as of G − 1 (`fixture_xg_history`), and history rows from earlier gameweeks only. This is
the backtest's walk-forward, written to the record instead of only summarised.
- Run by hand: `python -m FPL_site.expectedPointsBackfill [--from-season 2024] [--from-gameweek 6]`.
  Default start: the earliest season with history (2024), gameweek 6.
- Backfilled rows are written today, after those deadlines, so they never mix with the honest
  live record: a `source` column on `expected_points_log` and `expected_points_accuracy` is
  `'live'` (the daily job, pre-deadline only) or `'backfill'` (replayed). `forecast_of_record`
  applies the deadline rule to live rows only; for backfill it takes the replay's row.
- Accuracy rows are written for every backfilled settled gameweek with `source = 'backfill'`,
  keyed `year_start, gameweek, model_version, source`.
- Re-running the backfill for the same model version changes nothing (`INSERT IGNORE`; the
  backfill uses one fixed `log_date` per run and skips gameweeks already backfilled).
- Known limit: history rows and snapshots can be corrected by the official game after the fact,
  so a replay is "data as stored now for that point in time", not a byte-for-byte copy of what was
  visible on the day.
