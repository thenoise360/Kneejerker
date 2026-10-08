# Our own expected points model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Predict every player's points for the next gameweek with a model we own, keep every
week's forecasts with an honest accuracy record, and prove (by backtest) whether it beats the
official game's number before it is ever shown to managers.

**Architecture:** Pure functions for features, training, prediction, records and the backtest
maths, with thin `mysql.connector` fetchers around them (the same split as `weekDecision.py` and
`matchPredictionEngine.py`). A daily job trains and predicts once a day and appends to an
append-only log; nothing is fitted in a request. The backtest is an offline script that writes a
Markdown report.

**Tech Stack:** Python 3.11, `mysql.connector` via `dataModels.connect_db()`, numpy, pandas,
scikit-learn 1.6.1 (`HistGradientBoostingRegressor`, already installed), pytest + pytest-bdd.

**Spec:** `docs/superpowers/specs/2026-10-08-expected-points-model-design.md`

## Global Constraints

- Branch `expected-points-model` (from `main`). Run tests with `vs-env/Scripts/python.exe -m pytest -q`; in a worktree use the main checkout's interpreter `C:/Users/jackb/Repos/Kneejerker/vs-env/Scripts/python.exe`.
- Tests set `KJ_SKIP_DB_INIT=1` (put `os.environ.setdefault('KJ_SKIP_DB_INIT', '1')` at the top of each test module) and never touch MySQL or the live API: monkeypatch fetchers, use fake cursors.
- Never hard-code a season: read it with `dataModels.current_season_start()` at call time and call `refresh_season_start()` at the top of the daily job (`tests/test_no_hardcoded_season.py` guards this).
- Players are matched across seasons by `code`; teams by team `code`. Map a season's team **id → code with `matchPredictionEngine.fetch_team_code_map(cursor, year_start)`**, never with `bootstrapstatic_teams` (its past-season ids are unreliable).
- `fixtures_fixtures` can hold another season's matches under the wrong `year_start` (2025 has every id twice). Every fixture read keeps only rows passing `matchPredictionEngine.kickoff_in_season_window(kickoff_time, year_start)`, and history rows join fixtures on `id`, `year_start` **and** `kickoff_time`, with `SELECT DISTINCT` (2024 also has exact duplicate rows).
- Every feature for gameweek G uses only data from before G's deadline. No imputation to zero: missing feature values are `float('nan')`.
- No new dependencies. No fitting inside a Flask request. No user-facing change in this plan.
- `MODEL_VERSION = 'hgb-poisson-2026-10'`.
- Do not commit `FPL_site/__pycache__` changes (`git checkout -- FPL_site/__pycache__` before each commit). Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Chain shell steps with `&&`.

## Review Focus

1. **Negative points** (own goal, red card: a gameweek of −1 or −2). Poisson loss rejects negative targets; expected: training clips the target at 0, prediction never fails. Owner: Task 3.
2. **A player who changed club mid-history** (same `code`, new team). Expected: rolling form follows the player; fixture features follow the club he is at in G. Owner: Task 1.
3. **Season boundary**: gameweek 1 of 2026 uses the player's last 2025 matches for rolling form, but season-to-date features are empty. Owner: Task 1.
4. **Daily job run after the deadline** (the cron runs late). Expected: today's predictions still persist to `player_expected_points`, but nothing is appended to the log for that gameweek. Owner: Task 4.
5. **Gameweek finished but bonus not confirmed** (`finished` true, `data_checked` false). Expected: no accuracy row yet. Owner: Task 4.

---

## File map

| File | Responsibility |
|---|---|
| `FPL_site/expectedPointsFeatures.py` (new) | Pure: per-player gameweek totals, snapshot lookups, rolling features, training and prediction rows |
| `FPL_site/fixtureXgHistory.py` (new) | Each team's expected goals for and against per gameweek, from the match engine fitted as of the gameweek before; table `fixture_xg_history` |
| `FPL_site/expectedPointsModel.py` (new) | `FEATURES`, `train`, `predict`, fetchers, `persist_expected_points`, `run_daily_expected_points` |
| `FPL_site/expectedPointsRecord.py` (new) | Weekly record: pre-deadline log, forecast of record, template squad, captain comparison, accuracy |
| `FPL_site/expectedPointsBacktest.py` (new) | Offline walk-forward backtest and report |
| `FPL_site/run_update.py` | Swap `run_daily_predictions` for `run_daily_expected_points` |
| `features/expected_points/*.feature`, `tests/step_defs/test_expected_points_*.py`, `tests/test_expected_points_*.py` | Tests |

## Shared data shapes (used across tasks)

```python
# One player-gameweek from elementsummary_history, already joined to the player's code and the
# club code for that season (Task 5's fetcher produces these):
HistoryRow = {'code': 1234, 'year_start': 2025, 'gameweek': 7, 'team_code': 3,
              'opponent_code': 14, 'was_home': True, 'minutes': 90, 'goals_scored': 1,
              'assists': 0, 'clean_sheets': 0, 'bonus': 2, 'total_points': 9}

# One snapshot row from bootstrapstatic_elements (snapshot `gameweek` = taken after that gameweek;
# its ep_next is the official forecast for gameweek + 1):
SnapshotRow = {'code': 1234, 'player_id': 351, 'year_start': 2025, 'gameweek': 6,
               'element_type': 4, 'team_code': 3, 'now_cost': 145,
               'chance_of_playing_next_round': None, 'ep_next': 7.5,
               'expected_goals': 4.31, 'expected_assists': 1.02}   # season-to-date totals

# Team expected goals for one gameweek (Task 2), summed over a double gameweek:
FixtureXg = {(year_start, gameweek, team_code): {'team_xg': 1.9, 'opp_xg': 0.8,
                                                  'matches': 1, 'home_share': 1.0}}
```

---

### Task 1: Feature building (pure)

**Files:**
- Create: `FPL_site/expectedPointsFeatures.py`
- Create: `features/expected_points/features.feature`, `tests/step_defs/test_expected_points_features.py`
- Create: `tests/test_expected_points_features.py`

**Interfaces:**
- Produces:
  - `MODEL_VERSION = 'hgb-poisson-2026-10'` (lives here, not in the model module, so the model and record modules can both import it without an import cycle)
  - `FEATURES: tuple[str, ...]` (column order used by the model)
  - `player_gameweeks(history_rows) -> dict[int, list[dict]]` — per `code`, one entry per (season, gameweek) with summed `total_points`, `minutes`, `goals_scored`, `assists`, `clean_sheets`, `bonus`, `starts` (matches with ≥60 minutes), `matches`, `team_code`; sorted by `(year_start, gameweek)`.
  - `per_gameweek_xg(snapshots) -> dict[(code, year_start, gameweek), (xg, xa)]` — difference between consecutive snapshots of the same season; the first snapshot of a season gives its own totals.
  - `feature_row(code, year_start, gameweek, history, snapshot_before, xg_by_gw, fixture) -> dict` — keys `FEATURES` (floats or nan).
  - `training_rows(history_rows, snapshots, fixture_xg) -> list[dict]` — one per player-gameweek played by the team; each has `FEATURES` keys plus `code`, `year_start`, `gameweek`, `position`, `target` (summed points).
  - `prediction_rows(history_rows, snapshots, fixture_xg, year_start, gameweek, players) -> list[dict]` — `players` is the latest snapshot rows of the current season; one row per player; players whose club has no match get `matches_in_gameweek = 0`.

- [ ] **Step 1: Write the behaviour scenarios**

`features/expected_points/features.feature`:

```gherkin
Feature: Expected points features only use what was known before the deadline

  Scenario: A feature never reads the gameweek it predicts
    Given a player who scored 2 points in gameweeks 1 to 4 and 20 points in gameweek 5
    When I build the features for gameweek 5
    Then the average points over the last 3 matches is 2.0

  Scenario: Form carries across seasons by player code
    Given a player with id 300 in 2025 who scored 6 points in each of his last 3 matches
    And the same player with id 41 in 2026
    When I build the features for 2026 gameweek 1
    Then the average points over the last 3 matches is 6.0
    And points per match this season is missing

  Scenario: A double gameweek adds both matches together
    Given a player who played twice in gameweek 7, scoring 5 and 8 points
    When I build the training rows
    Then gameweek 7 has a target of 13 points and 2 matches

  Scenario: A blank gameweek gives no training row
    Given a player whose club had no match in gameweek 8
    When I build the training rows
    Then there is no row for gameweek 8

  Scenario: A new player has empty form, not zeros
    Given a player with no earlier matches
    When I build the features for gameweek 3
    Then the average points over the last 3 matches is missing
```

- [ ] **Step 2: Write the step definitions**

`tests/step_defs/test_expected_points_features.py`:

```python
import math
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from FPL_site import expectedPointsFeatures as ef

scenarios('expected_points/features.feature')


def hist(code, year, gw, points, minutes=90, team_code=3):
    return {'code': code, 'year_start': year, 'gameweek': gw, 'team_code': team_code,
            'opponent_code': 14, 'was_home': True, 'minutes': minutes, 'goals_scored': 0,
            'assists': 0, 'clean_sheets': 0, 'bonus': 0, 'total_points': points}


def fixture_xg(year, gws, team_code=3):
    return {(year, gw, team_code): {'team_xg': 1.5, 'opp_xg': 1.0, 'matches': 1, 'home_share': 1.0}
            for gw in gws}


@pytest.fixture
def ctx():
    return {'history': [], 'fixtures': {}, 'year': 2026, 'row': None, 'rows': None}


@given('a player who scored 2 points in gameweeks 1 to 4 and 20 points in gameweek 5')
def _leak(ctx):
    ctx['history'] = [hist(1, 2026, gw, 2) for gw in range(1, 5)] + [hist(1, 2026, 5, 20)]
    ctx['fixtures'] = fixture_xg(2026, range(1, 6))


@given('a player with id 300 in 2025 who scored 6 points in each of his last 3 matches')
def _last_season(ctx):
    ctx['history'] = [hist(1, 2025, gw, 6) for gw in (36, 37, 38)]
    ctx['fixtures'] = fixture_xg(2026, [1])


@given('the same player with id 41 in 2026')
def _same_code(ctx):
    pass   # history rows carry the code, so the new id changes nothing


@given('a player who played twice in gameweek 7, scoring 5 and 8 points')
def _double(ctx):
    ctx['history'] = [hist(1, 2026, 7, 5), hist(1, 2026, 7, 8)]
    ctx['fixtures'] = {(2026, 7, 3): {'team_xg': 3.0, 'opp_xg': 2.0, 'matches': 2, 'home_share': 0.5}}


@given('a player whose club had no match in gameweek 8')
def _blank(ctx):
    ctx['history'] = [hist(1, 2026, 7, 5), hist(1, 2026, 9, 3)]
    ctx['fixtures'] = fixture_xg(2026, [7, 9])


@given('a player with no earlier matches')
def _new(ctx):
    ctx['history'] = []
    ctx['fixtures'] = fixture_xg(2026, [3])


@when(parsers.parse('I build the features for gameweek {gw:d}'))
def _features(ctx, gw):
    games = ef.player_gameweeks(ctx['history']).get(1, [])
    ctx['row'] = ef.feature_row(1, ctx['year'], gw, games, None, {}, ctx['fixtures'].get((ctx['year'], gw, 3)))


@when(parsers.parse('I build the features for {year:d} gameweek {gw:d}'))
def _features_year(ctx, year, gw):
    games = ef.player_gameweeks(ctx['history']).get(1, [])
    ctx['row'] = ef.feature_row(1, year, gw, games, None, {}, ctx['fixtures'].get((year, gw, 3)))


@when('I build the training rows')
def _training(ctx):
    snaps = [{'code': 1, 'player_id': 1, 'year_start': 2026, 'gameweek': g, 'element_type': 3,
              'team_code': 3, 'now_cost': 60, 'chance_of_playing_next_round': None,
              'ep_next': 3.0, 'expected_goals': 0.0, 'expected_assists': 0.0} for g in range(0, 10)]
    ctx['rows'] = ef.training_rows(ctx['history'], snaps, ctx['fixtures'])


@then(parsers.parse('the average points over the last 3 matches is {value:f}'))
def _avg(ctx, value):
    assert ctx['row']['points_last_3'] == pytest.approx(value)


@then('the average points over the last 3 matches is missing')
def _avg_missing(ctx):
    assert math.isnan(ctx['row']['points_last_3'])


@then('points per match this season is missing')
def _season_missing(ctx):
    assert math.isnan(ctx['row']['season_points_per_match'])


@then(parsers.parse('gameweek {gw:d} has a target of {points:d} points and {matches:d} matches'))
def _target(ctx, gw, points, matches):
    row = next(r for r in ctx['rows'] if r['gameweek'] == gw)
    assert row['target'] == points
    assert row['matches_in_gameweek'] == matches


@then(parsers.parse('there is no row for gameweek {gw:d}'))
def _no_row(ctx, gw):
    assert all(r['gameweek'] != gw for r in ctx['rows'])
```

- [ ] **Step 3: Add the Review Focus unit tests**

`tests/test_expected_points_features.py`:

```python
import math
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import expectedPointsFeatures as ef


def hist(year, gw, points, team_code=3, minutes=90):
    return {'code': 1, 'year_start': year, 'gameweek': gw, 'team_code': team_code,
            'opponent_code': 14, 'was_home': True, 'minutes': minutes, 'goals_scored': 0,
            'assists': 0, 'clean_sheets': 0, 'bonus': 0, 'total_points': points}


def test_a_player_who_moved_club_keeps_his_form_and_takes_his_new_clubs_fixture():
    games = ef.player_gameweeks([hist(2026, 1, 9, team_code=3), hist(2026, 2, 9, team_code=7)])[1]
    new_club_fixture = {'team_xg': 2.2, 'opp_xg': 0.7, 'matches': 1, 'home_share': 1.0}
    row = ef.feature_row(1, 2026, 3, games, None, {}, new_club_fixture)
    assert row['points_last_3'] == 9.0
    assert row['team_xg'] == 2.2


def test_season_to_date_features_reset_at_a_new_season_but_form_does_not():
    games = ef.player_gameweeks([hist(2025, 38, 8)])[1]
    row = ef.feature_row(1, 2026, 1, games, None, {}, None)
    assert row['points_last_3'] == 8.0
    assert math.isnan(row['season_points_per_match'])
    assert row['matches_in_gameweek'] == 0


def test_per_gameweek_expected_goals_are_differences_between_snapshots():
    snaps = [{'code': 1, 'year_start': 2026, 'gameweek': g, 'expected_goals': xg, 'expected_assists': xa}
             for g, xg, xa in ((1, 0.4, 0.1), (2, 1.0, 0.1), (3, 1.5, 0.6))]
    xg = ef.per_gameweek_xg(snaps)
    assert xg[(1, 2026, 1)] == (0.4, 0.1)
    assert xg[(1, 2026, 2)] == (0.6, 0.0)
    assert xg[(1, 2026, 3)] == (0.5, 0.5)


def test_features_come_out_in_the_fixed_order():
    row = ef.feature_row(1, 2026, 2, [], None, {}, None)
    assert tuple(k for k in row if k in ef.FEATURES) == ef.FEATURES
```

- [ ] **Step 4: Run the tests to see them fail**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/step_defs/test_expected_points_features.py tests/test_expected_points_features.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'FPL_site.expectedPointsFeatures'`.

- [ ] **Step 5: Implement**

`FPL_site/expectedPointsFeatures.py`:

```python
"""Pure feature building for our expected points model. No database access here.

A feature for gameweek G may only use what was known before G's deadline: the player's matches
in earlier gameweeks, the snapshot taken after G - 1, and the match engine as fitted after G - 1.
Missing values are nan (the model handles them); they are never filled with zero.
"""
from collections import defaultdict

NAN = float('nan')
STARTED_MINUTES = 60
# The version of the features and model together; logged with every forecast.
MODEL_VERSION = 'hgb-poisson-2026-10'

FEATURES = (
    'points_last_3', 'points_last_5', 'minutes_last_3', 'minutes_last_5',
    'starts_last_5', 'goals_last_5', 'assists_last_5', 'bonus_last_5', 'clean_sheets_last_5',
    'xg_last_5', 'xa_last_5', 'season_points_per_match', 'season_minutes_per_match',
    'price', 'chance_of_playing', 'home_share', 'matches_in_gameweek', 'team_xg', 'opp_xg',
)

_SUMMED = ('total_points', 'minutes', 'goals_scored', 'assists', 'clean_sheets', 'bonus')


def player_gameweeks(history_rows):
    """{code: [one dict per (season, gameweek), oldest first]}, double gameweeks summed."""
    grouped = {}
    for r in history_rows:
        key = (r['code'], r['year_start'], r['gameweek'])
        g = grouped.get(key)
        if g is None:
            g = grouped[key] = {'year_start': r['year_start'], 'gameweek': r['gameweek'],
                                'team_code': r['team_code'], 'matches': 0, 'starts': 0,
                                **{k: 0 for k in _SUMMED}}
        g['matches'] += 1
        g['starts'] += 1 if (r['minutes'] or 0) >= STARTED_MINUTES else 0
        for k in _SUMMED:
            g[k] += r[k] or 0
    by_code = defaultdict(list)
    for (code, _, _), g in grouped.items():
        by_code[code].append(g)
    for games in by_code.values():
        games.sort(key=lambda g: (g['year_start'], g['gameweek']))
    return dict(by_code)


def per_gameweek_xg(snapshots):
    """{(code, year_start, gameweek): (xg, xa)} from season-to-date snapshot totals."""
    out = {}
    series = defaultdict(list)
    for s in snapshots:
        series[(s['code'], s['year_start'])].append(s)
    for (code, year), snaps in series.items():
        snaps.sort(key=lambda s: s['gameweek'])
        prev_xg = prev_xa = 0.0
        for s in snaps:
            xg, xa = float(s['expected_goals'] or 0), float(s['expected_assists'] or 0)
            out[(code, year, s['gameweek'])] = (round(xg - prev_xg, 4), round(xa - prev_xa, 4))
            prev_xg, prev_xa = xg, xa
    return out


def _mean(values):
    return sum(values) / len(values) if values else NAN


def _total(values):
    return float(sum(values)) if values else NAN


def feature_row(code, year_start, gameweek, games, snapshot_before, xg_by_gw, fixture):
    """Features for one player and target gameweek. `games` are that player's gameweek totals."""
    earlier = [g for g in games if (g['year_start'], g['gameweek']) < (year_start, gameweek)]
    last3, last5 = earlier[-3:], earlier[-5:]
    this_season = [g for g in earlier if g['year_start'] == year_start]
    season_matches = sum(g['matches'] for g in this_season)
    xg5 = [xg_by_gw.get((code, g['year_start'], g['gameweek'])) for g in last5]
    xg5 = [x for x in xg5 if x is not None]
    snap = snapshot_before or {}
    chance = snap.get('chance_of_playing_next_round')
    row = {
        'points_last_3': _mean([g['total_points'] for g in last3]),
        'points_last_5': _mean([g['total_points'] for g in last5]),
        'minutes_last_3': _mean([g['minutes'] for g in last3]),
        'minutes_last_5': _mean([g['minutes'] for g in last5]),
        'starts_last_5': _total([g['starts'] for g in last5]),
        'goals_last_5': _total([g['goals_scored'] for g in last5]),
        'assists_last_5': _total([g['assists'] for g in last5]),
        'bonus_last_5': _total([g['bonus'] for g in last5]),
        'clean_sheets_last_5': _total([g['clean_sheets'] for g in last5]),
        'xg_last_5': _total([x[0] for x in xg5]),
        'xa_last_5': _total([x[1] for x in xg5]),
        'season_points_per_match': (sum(g['total_points'] for g in this_season) / season_matches
                                    if season_matches else NAN),
        'season_minutes_per_match': (sum(g['minutes'] for g in this_season) / season_matches
                                     if season_matches else NAN),
        'price': float(snap['now_cost']) / 10 if snap.get('now_cost') is not None else NAN,
        'chance_of_playing': float(chance) if chance is not None else (100.0 if snap else NAN),
        'home_share': fixture['home_share'] if fixture else NAN,
        'matches_in_gameweek': float(fixture['matches']) if fixture else 0.0,
        'team_xg': fixture['team_xg'] if fixture else NAN,
        'opp_xg': fixture['opp_xg'] if fixture else NAN,
    }
    return {k: row[k] for k in FEATURES}


def _snapshot_index(snapshots):
    return {(s['code'], s['year_start'], s['gameweek']): s for s in snapshots}


def training_rows(history_rows, snapshots, fixture_xg):
    """One row per player-gameweek the player's club played, target = summed points."""
    games_by_code = player_gameweeks(history_rows)
    snaps = _snapshot_index(snapshots)
    xg_by_gw = per_gameweek_xg(snapshots)
    rows = []
    for code, games in games_by_code.items():
        for g in games:
            year, gw = g['year_start'], g['gameweek']
            fixture = fixture_xg.get((year, gw, g['team_code']))
            if fixture is None:
                continue   # no stored fixture for that club and gameweek: not a usable row
            before = snaps.get((code, year, gw - 1))
            position = (before or snaps.get((code, year, gw)) or {}).get('element_type')
            if position is None:
                continue
            row = feature_row(code, year, gw, games, before, xg_by_gw, fixture)
            row.update({'code': code, 'year_start': year, 'gameweek': gw,
                        'position': position, 'target': g['total_points'],
                        'matches_in_gameweek': float(g['matches'])})
            rows.append(row)
    return rows


def prediction_rows(history_rows, snapshots, fixture_xg, year_start, gameweek, players):
    """One row per current player for the coming gameweek; players are latest snapshot rows."""
    games_by_code = player_gameweeks(history_rows)
    xg_by_gw = per_gameweek_xg(snapshots)
    rows = []
    for p in players:
        fixture = fixture_xg.get((year_start, gameweek, p['team_code']))
        row = feature_row(p['code'], year_start, gameweek, games_by_code.get(p['code'], []),
                          p, xg_by_gw, fixture)
        row.update({'code': p['code'], 'player_id': p['player_id'], 'year_start': year_start,
                    'gameweek': gameweek, 'position': p['element_type']})
        rows.append(row)
    return rows
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/step_defs/test_expected_points_features.py tests/test_expected_points_features.py`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git checkout -- FPL_site/__pycache__ 2>/dev/null; git add FPL_site/expectedPointsFeatures.py features/expected_points/features.feature tests/step_defs/test_expected_points_features.py tests/test_expected_points_features.py && git commit -m "Build expected points features from what was known before each deadline

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Team expected goals per gameweek, as known the week before

**Files:**
- Create: `FPL_site/fixtureXgHistory.py`
- Test: `tests/test_fixture_xg_history.py`

**Interfaces:**
- Consumes: `matchPredictionEngine.build_rating_dataset(cursor, current_season, current_gw, current_season_max_event=None)`, `fit_dixon_coles(rows, codes, reference_gw) -> (ratings, home_adv, rho)`, `fetch_team_code_map(cursor, year_start) -> {id: code}`, `teamStrength.rating_for(ratings, code)`.
- Produces:
  - `TABLE = 'fixture_xg_history'`
  - `team_gameweek_xg(fixtures, ratings, home_adv, id_to_code) -> {team_code: {'team_xg', 'opp_xg', 'matches', 'home_share'}}` (pure; `fixtures` are `{'team_h', 'team_a'}` rows of one gameweek)
  - `fit_as_of(cursor, year_start, gameweek) -> {team_code: {...}}` (fits the engine with fixtures before `gameweek` only)
  - `load_fixture_xg(cursor) -> FixtureXg` (all stored rows, keyed `(year_start, gameweek, team_code)`)
  - `fill_missing(conn, cursor, wanted) -> int` — `wanted` is a list of `(year_start, gameweek)`; computes and stores those not stored yet; returns how many gameweeks were added.

- [ ] **Step 1: Write the failing tests**

`tests/test_fixture_xg_history.py`:

```python
import math
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import fixtureXgHistory as fx

RATINGS = {10: {'attack': 0.5, 'defence': -0.2}, 20: {'attack': 0.1, 'defence': 0.1},
           30: {'attack': 0.0, 'defence': 0.0}}
ID_TO_CODE = {1: 10, 2: 20, 3: 30}


def test_a_single_match_gives_both_sides_their_expected_goals():
    out = fx.team_gameweek_xg([{'team_h': 1, 'team_a': 2}], RATINGS, 0.2, ID_TO_CODE)
    home = math.exp(0.5 + 0.1 + 0.2)
    away = math.exp(0.1 - 0.2)
    assert out[10] == {'team_xg': round(home, 3), 'opp_xg': round(away, 3), 'matches': 1, 'home_share': 1.0}
    assert out[20] == {'team_xg': round(away, 3), 'opp_xg': round(home, 3), 'matches': 1, 'home_share': 0.0}


def test_a_double_gameweek_adds_both_matches():
    out = fx.team_gameweek_xg([{'team_h': 1, 'team_a': 2}, {'team_h': 3, 'team_a': 1}],
                              RATINGS, 0.0, ID_TO_CODE)
    assert out[10]['matches'] == 2
    assert out[10]['home_share'] == 0.5
    expected = round(math.exp(0.5 + 0.1), 3) + round(math.exp(0.5 + 0.0), 3)
    assert math.isclose(out[10]['team_xg'], expected, abs_tol=0.002)


def test_a_team_missing_from_the_code_map_is_skipped():
    out = fx.team_gameweek_xg([{'team_h': 1, 'team_a': 99}], RATINGS, 0.0, ID_TO_CODE)
    assert out == {}


def test_fit_as_of_only_uses_fixtures_before_the_gameweek(monkeypatch):
    seen = {}

    def dataset(cursor, season, current_gw, current_season_max_event=None):
        seen['args'] = (season, current_gw, current_season_max_event)
        return [], [10, 20], 0, current_gw

    monkeypatch.setattr(fx, 'build_rating_dataset', dataset)
    monkeypatch.setattr(fx, 'fit_dixon_coles', lambda rows, codes, ref: (RATINGS, 0.0, 0.0))
    monkeypatch.setattr(fx, 'fetch_team_code_map', lambda cursor, year: ID_TO_CODE)
    monkeypatch.setattr(fx, 'fetch_gameweek_fixtures', lambda cursor, year, gw: [{'team_h': 1, 'team_a': 2}])
    out = fx.fit_as_of(object(), 2025, 7)
    assert seen['args'] == (2025, 6, 7)
    assert set(out) == {10, 20}


class RowsCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self.rows


def test_another_seasons_matches_stored_under_this_season_are_ignored():
    rows = [{'id': 51, 'team_h': 1, 'team_a': 2, 'kickoff_time': '2025-09-27T14:00:00Z'},
            {'id': 51, 'team_h': 3, 'team_a': 4, 'kickoff_time': '2026-09-26T14:00:00Z'}]
    assert fx.fetch_gameweek_fixtures(RowsCursor(rows), 2025, 6) == [rows[0]]


class FakeCursor:
    def __init__(self, stored):
        self.stored, self.calls = stored, []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, rows):
        self.calls.append((sql, list(rows)))

    def fetchall(self):
        return self.stored


class FakeConn:
    def __init__(self, cursor):
        self.cur, self.commits = cursor, 0

    def cursor(self, **k):
        return self.cur

    def commit(self):
        self.commits += 1


def test_fill_missing_only_fits_gameweeks_not_already_stored(monkeypatch):
    cursor = FakeCursor(stored=[{'year_start': 2025, 'gameweek': 6}])
    fitted = []
    monkeypatch.setattr(fx, 'fit_as_of', lambda c, y, g: fitted.append((y, g)) or
                        {10: {'team_xg': 1.0, 'opp_xg': 1.0, 'matches': 1, 'home_share': 1.0}})
    added = fx.fill_missing(FakeConn(cursor), cursor, [(2025, 6), (2025, 7)])
    assert fitted == [(2025, 7)]
    assert added == 1
```

- [ ] **Step 2: Run to see them fail**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/test_fixture_xg_history.py`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`FPL_site/fixtureXgHistory.py`:

```python
"""Each team's expected goals for and against in a gameweek, as our match engine would have seen
it before that gameweek: the engine is refitted with only earlier fixtures. Used as features for
past gameweeks (training and the backtest). Stored once per gameweek in fixture_xg_history, since
each refit takes seconds.
"""
import logging
import math

from FPL_site.dataModels import db
from FPL_site.matchPredictionEngine import (build_rating_dataset, fit_dixon_coles, fetch_team_code_map,
                                            kickoff_in_season_window)
from FPL_site.teamStrength import rating_for

logger = logging.getLogger(__name__)

TABLE = 'fixture_xg_history'


def team_gameweek_xg(fixtures, ratings, home_adv, id_to_code):
    out = {}
    for f in fixtures:
        home, away = id_to_code.get(f['team_h']), id_to_code.get(f['team_a'])
        if home is None or away is None:
            continue
        rh, ra = rating_for(ratings, home), rating_for(ratings, away)
        lam_home = round(math.exp(rh['attack'] + ra['defence'] + home_adv), 3)
        lam_away = round(math.exp(ra['attack'] + rh['defence']), 3)
        for code, own, opp, is_home in ((home, lam_home, lam_away, 1.0), (away, lam_away, lam_home, 0.0)):
            t = out.setdefault(code, {'team_xg': 0.0, 'opp_xg': 0.0, 'matches': 0, 'homes': 0.0})
            t['team_xg'] += own
            t['opp_xg'] += opp
            t['matches'] += 1
            t['homes'] += is_home
    return {code: {'team_xg': round(t['team_xg'], 3), 'opp_xg': round(t['opp_xg'], 3),
                   'matches': t['matches'], 'home_share': t['homes'] / t['matches']}
            for code, t in out.items()}


def fetch_gameweek_fixtures(cursor, year_start, gameweek):
    """One gameweek's matches. The table can hold another season's matches under this
    year_start, so only kickoffs inside the season's window count."""
    cursor.execute(f"""SELECT DISTINCT id, team_h, team_a, kickoff_time FROM {db}.fixtures_fixtures
                       WHERE year_start = %s AND event = %s""", (year_start, gameweek))
    return [r for r in cursor.fetchall() if kickoff_in_season_window(r['kickoff_time'], year_start)]


def fit_as_of(cursor, year_start, gameweek):
    """Fit the engine on fixtures before `gameweek` (prior seasons whole), predict `gameweek`."""
    rows, codes, _, reference_gw = build_rating_dataset(
        cursor, year_start, gameweek - 1, current_season_max_event=gameweek)
    ratings, home_adv, _ = fit_dixon_coles(rows, codes, reference_gw)
    return team_gameweek_xg(fetch_gameweek_fixtures(cursor, year_start, gameweek),
                            ratings, home_adv, fetch_team_code_map(cursor, year_start))


def _ensure_table(cursor):
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            year_start INT NOT NULL,
            gameweek INT NOT NULL,
            team_code INT NOT NULL,
            team_xg FLOAT NOT NULL,
            opp_xg FLOAT NOT NULL,
            matches INT NOT NULL,
            home_share FLOAT NOT NULL,
            PRIMARY KEY (year_start, gameweek, team_code)
        )
    """)


def load_fixture_xg(cursor):
    _ensure_table(cursor)
    cursor.execute(f"SELECT year_start, gameweek, team_code, team_xg, opp_xg, matches, home_share FROM {TABLE}")
    return {(r['year_start'], r['gameweek'], r['team_code']):
            {'team_xg': float(r['team_xg']), 'opp_xg': float(r['opp_xg']),
             'matches': int(r['matches']), 'home_share': float(r['home_share'])}
            for r in cursor.fetchall()}


def fill_missing(conn, cursor, wanted):
    _ensure_table(cursor)
    cursor.execute(f"SELECT DISTINCT year_start, gameweek FROM {TABLE}")
    stored = {(r['year_start'], r['gameweek']) for r in cursor.fetchall()}
    added = 0
    for year, gw in wanted:
        if (year, gw) in stored:
            continue
        teams = fit_as_of(cursor, year, gw)
        cursor.executemany(f"""
            INSERT IGNORE INTO {TABLE} (year_start, gameweek, team_code, team_xg, opp_xg, matches, home_share)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, [(year, gw, code, t['team_xg'], t['opp_xg'], t['matches'], t['home_share'])
              for code, t in teams.items()])
        conn.commit()
        added += 1
        logger.info("fixture_xg_history: stored %s gameweek %s (%d teams).", year, gw, len(teams))
    return added
```

- [ ] **Step 4: Run to see them pass**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/test_fixture_xg_history.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git checkout -- FPL_site/__pycache__ 2>/dev/null; git add FPL_site/fixtureXgHistory.py tests/test_fixture_xg_history.py && git commit -m "Store each team's expected goals per gameweek as the engine saw it the week before

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Train and predict

**Files:**
- Create: `FPL_site/expectedPointsModel.py` (model part only; Task 5 adds the daily job)
- Test: `tests/test_expected_points_model.py`

**Interfaces:**
- Consumes: `expectedPointsFeatures.FEATURES`, training/prediction rows from Task 1 (keys `FEATURES` + `position`, `target`).
- Produces:
  - `MODEL_VERSION` re-exported from `expectedPointsFeatures`
  - `MIN_ROWS_PER_POSITION = 50`
  - `train(rows) -> dict[int, HistGradientBoostingRegressor]` — one per position with at least `MIN_ROWS_PER_POSITION` rows; target clipped at 0.
  - `predict(models, rows) -> list[float]` — same order as `rows`; a position with no model gives `nan`; values ≥ 0, rounded to 1 decimal; rows with `matches_in_gameweek == 0` give `0.0`.

- [ ] **Step 1: Write the failing tests**

`tests/test_expected_points_model.py`:

```python
import math
import os
import random
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import expectedPointsModel as em
from FPL_site.expectedPointsFeatures import FEATURES


def synthetic(n, position, seed=0):
    rnd = random.Random(seed)
    rows = []
    for _ in range(n):
        form = rnd.uniform(0, 10)
        row = {f: rnd.uniform(0, 3) for f in FEATURES}
        row.update({'points_last_5': form, 'matches_in_gameweek': 1.0, 'position': position,
                    'target': max(-2, round(form + rnd.gauss(0, 1)))})
        rows.append(row)
    return rows


def test_one_model_per_position_with_enough_rows():
    models = em.train(synthetic(200, 3) + synthetic(200, 4, seed=1) + synthetic(10, 1, seed=2))
    assert set(models) == {3, 4}


def test_negative_points_do_not_break_training_and_predictions_are_never_negative():
    rows = synthetic(300, 2)
    rows[0]['target'] = -2
    models = em.train(rows)
    preds = em.predict(models, rows)
    assert all(p >= 0 for p in preds)


def test_better_form_predicts_more_points():
    models = em.train(synthetic(600, 3))
    low, high = dict(synthetic(1, 3)[0]), dict(synthetic(1, 3)[0])
    low['points_last_5'], high['points_last_5'] = 1.0, 9.0
    p_low, p_high = em.predict(models, [low, high])
    assert p_high > p_low


def test_no_match_means_zero_and_an_unmodelled_position_means_nan():
    models = em.train(synthetic(200, 3))
    blank = dict(synthetic(1, 3)[0], matches_in_gameweek=0.0)
    keeper = dict(synthetic(1, 1)[0])
    assert em.predict(models, [blank, keeper])[0] == 0.0
    assert math.isnan(em.predict(models, [blank, keeper])[1])


def test_missing_feature_values_are_accepted():
    rows = synthetic(200, 3)
    for r in rows[:50]:
        r['xg_last_5'] = float('nan')
    models = em.train(rows)
    assert len(em.predict(models, rows)) == 200
```

- [ ] **Step 2: Run to see them fail**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/test_expected_points_model.py`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`FPL_site/expectedPointsModel.py`:

```python
"""Our expected points model: one gameweek ahead, one model per position.

Gradient-boosted trees with Poisson loss (points are non-negative and skewed). Hyperparameters
are fixed here and only changed on the evidence of the backtest (expectedPointsBacktest.py).
The daily job (run_daily_expected_points, added below) is the only place this is fitted.
"""
import logging
import math

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from FPL_site.expectedPointsFeatures import FEATURES, MODEL_VERSION

logger = logging.getLogger(__name__)

MIN_ROWS_PER_POSITION = 50
PARAMS = dict(loss='poisson', learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
              min_samples_leaf=40, l2_regularization=1.0, random_state=0)


def _matrix(rows):
    return np.array([[float(r[f]) for f in FEATURES] for r in rows], dtype=float)


def train(rows):
    models = {}
    by_position = {}
    for r in rows:
        by_position.setdefault(r['position'], []).append(r)
    for position, group in by_position.items():
        if len(group) < MIN_ROWS_PER_POSITION:
            logger.warning("expected points: only %d rows for position %s, no model.", len(group), position)
            continue
        target = np.array([max(0.0, float(r['target'])) for r in group])
        models[position] = HistGradientBoostingRegressor(**PARAMS).fit(_matrix(group), target)
    return models


def predict(models, rows):
    out = [math.nan] * len(rows)
    by_position = {}
    for i, r in enumerate(rows):
        if float(r.get('matches_in_gameweek') or 0) == 0:
            out[i] = 0.0
        elif r['position'] in models:
            by_position.setdefault(r['position'], []).append(i)
    for position, idx in by_position.items():
        values = models[position].predict(_matrix([rows[i] for i in idx]))
        for i, v in zip(idx, values):
            out[i] = round(max(0.0, float(v)), 1)
    return out
```

- [ ] **Step 4: Run to see them pass**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/test_expected_points_model.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git checkout -- FPL_site/__pycache__ 2>/dev/null; git add FPL_site/expectedPointsModel.py tests/test_expected_points_model.py && git commit -m "Train one gradient-boosted expected points model per position

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The weekly record

**Files:**
- Create: `FPL_site/expectedPointsRecord.py`
- Create: `features/expected_points/weekly_record.feature`, `tests/step_defs/test_expected_points_record.py`
- Test: `tests/test_expected_points_record.py`

**Interfaces:**
- Consumes: `expectedPointsFeatures.MODEL_VERSION`.
- Produces:
  - `LOG_TABLE = 'expected_points_log'`, `ACCURACY_TABLE = 'expected_points_accuracy'`, `CURRENT_TABLE = 'player_expected_points'`
  - `DEADLINE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'`
  - `deadline_for(events, gameweek) -> datetime | None`
  - `next_gameweek(events, now) -> int | None` — first event whose deadline is after `now`
  - `is_settled(events, gameweek) -> bool` — `finished` and `data_checked`
  - `log_forecasts(conn, rows, gameweek, deadline, now) -> int` — rows are `{'player_id', 'code', 'expected_points', 'official_expected_points'}`; returns rows written (0 when `now >= deadline`)
  - `forecast_of_record(log_rows, deadline) -> {player_id: row}` — each player's latest row with `logged_at < deadline`
  - `template_squad(selection_rows) -> list[int]` — the 15 most selected players: 2 goalkeepers, 5 defenders, 5 midfielders, 3 forwards; `selection_rows` are `{'player_id', 'position', 'selected'}`
  - `captain_pick(squad, values, playing) -> int | None` — highest value among squad players in `playing`; ties to lower id
  - `accuracy_for_gameweek(record, actual, squad, playing) -> dict` with `players`, `mae_ours`, `mae_official`, `mae_by_position` (`{position: {'ours', 'official', 'players'}}`), `captain_ours`, `captain_official`, `captain_ours_points`, `captain_official_points`
  - `persist_accuracy(conn, gameweek, year_start, result, now)` — `REPLACE INTO`
  - `persist_current(conn, rows, now)` — `REPLACE INTO player_expected_points`

- [ ] **Step 1: Write the behaviour scenarios**

`features/expected_points/weekly_record.feature`:

```gherkin
Feature: We keep every week's forecasts so we can say how accurate we were

  Scenario: Forecasts made before the deadline are logged
    Given the gameweek 6 deadline is tomorrow
    When the daily job logs 3 forecasts
    Then 3 rows are written to the log

  Scenario: Forecasts made after the deadline are not logged
    Given the gameweek 6 deadline was an hour ago
    When the daily job logs 3 forecasts
    Then nothing is written to the log

  Scenario: The forecast of record is the last one before the deadline
    Given forecasts for a player of 4.0 on Wednesday, 5.0 on Thursday and 9.0 after the Friday deadline
    When I take the forecast of record
    Then it is 5.0

  Scenario: Accuracy waits for bonus to be confirmed
    Given gameweek 6 has finished but its data is not yet checked
    Then gameweek 6 is not settled

  Scenario: Accuracy compares us with the official number on the same players
    Given our forecasts of 6 and 2 and official forecasts of 3 and 3
    And the players actually scored 8 and 1
    When I work out the accuracy
    Then our average error is 1.5 and the official average error is 3.5
```

- [ ] **Step 2: Write the step definitions**

`tests/step_defs/test_expected_points_record.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from FPL_site import expectedPointsRecord as rec

scenarios('expected_points/weekly_record.feature')

NOW = datetime(2026, 10, 8, 12, 0)


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, rows):
        self.calls.append((sql, list(rows)))


class FakeConn:
    def __init__(self):
        self.cur, self.commits = FakeCursor(), 0

    def cursor(self, **k):
        return self.cur

    def commit(self):
        self.commits += 1


@pytest.fixture
def ctx():
    return {}


@given('the gameweek 6 deadline is tomorrow')
def _tomorrow(ctx):
    ctx['deadline'] = NOW + timedelta(days=1)


@given('the gameweek 6 deadline was an hour ago')
def _passed(ctx):
    ctx['deadline'] = NOW - timedelta(hours=1)


@when(parsers.parse('the daily job logs {n:d} forecasts'))
def _log(ctx, n):
    rows = [{'player_id': i, 'code': 100 + i, 'expected_points': 3.0, 'official_expected_points': 2.5}
            for i in range(n)]
    ctx['written'] = rec.log_forecasts(FakeConn(), rows, 6, ctx['deadline'], NOW)


@then(parsers.parse('{n:d} rows are written to the log'))
def _written(ctx, n):
    assert ctx['written'] == n


@then('nothing is written to the log')
def _nothing(ctx):
    assert ctx['written'] == 0


@given('forecasts for a player of 4.0 on Wednesday, 5.0 on Thursday and 9.0 after the Friday deadline')
def _forecasts(ctx):
    ctx['deadline'] = datetime(2026, 10, 9, 17, 30)
    ctx['log'] = [{'player_id': 1, 'expected_points': 4.0, 'logged_at': datetime(2026, 10, 7, 6)},
                  {'player_id': 1, 'expected_points': 5.0, 'logged_at': datetime(2026, 10, 8, 6)},
                  {'player_id': 1, 'expected_points': 9.0, 'logged_at': datetime(2026, 10, 10, 6)}]


@when('I take the forecast of record')
def _record(ctx):
    ctx['record'] = rec.forecast_of_record(ctx['log'], ctx['deadline'])


@then(parsers.parse('it is {value:f}'))
def _value(ctx, value):
    assert ctx['record'][1]['expected_points'] == value


@given('gameweek 6 has finished but its data is not yet checked')
def _unchecked(ctx):
    ctx['events'] = [{'id': 6, 'deadline_time': '2026-10-03T10:00:00Z', 'finished': True, 'data_checked': False}]


@then('gameweek 6 is not settled')
def _not_settled(ctx):
    assert rec.is_settled(ctx['events'], 6) is False


@given('our forecasts of 6 and 2 and official forecasts of 3 and 3')
def _ours(ctx):
    ctx['record'] = {1: {'player_id': 1, 'position': 3, 'expected_points': 6.0, 'official_expected_points': 3.0},
                     2: {'player_id': 2, 'position': 3, 'expected_points': 2.0, 'official_expected_points': 3.0}}


@given('the players actually scored 8 and 1')
def _actual(ctx):
    ctx['actual'] = {1: 8, 2: 1}


@when('I work out the accuracy')
def _accuracy(ctx):
    ctx['result'] = rec.accuracy_for_gameweek(ctx['record'], ctx['actual'], [1, 2], {1, 2})


@then(parsers.parse('our average error is {ours:f} and the official average error is {official:f}'))
def _maes(ctx, ours, official):
    assert ctx['result']['mae_ours'] == pytest.approx(ours)
    assert ctx['result']['mae_official'] == pytest.approx(official)
```

- [ ] **Step 3: Write the unit tests**

`tests/test_expected_points_record.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime

from FPL_site import expectedPointsRecord as rec
from FPL_site.expectedPointsFeatures import MODEL_VERSION


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, rows):
        self.calls.append((sql, list(rows)))


class FakeConn:
    def __init__(self):
        self.cur, self.commits = FakeCursor(), 0

    def cursor(self, **k):
        return self.cur

    def commit(self):
        self.commits += 1

EVENTS = [{'id': 5, 'deadline_time': '2026-10-03T10:00:00Z', 'finished': True, 'data_checked': True},
          {'id': 6, 'deadline_time': '2026-10-10T10:00:00Z', 'finished': False, 'data_checked': False},
          {'id': 7, 'deadline_time': 'bad', 'finished': False, 'data_checked': False}]


def test_deadlines_and_the_next_gameweek_come_from_the_events():
    assert rec.deadline_for(EVENTS, 6) == datetime(2026, 10, 10, 10, 0)
    assert rec.deadline_for(EVENTS, 7) is None
    assert rec.next_gameweek(EVENTS, datetime(2026, 10, 8)) == 6
    assert rec.next_gameweek(EVENTS, datetime(2026, 10, 11)) is None
    assert rec.is_settled(EVENTS, 5) is True


def test_the_log_is_append_only_and_idempotent_per_day():
    conn = FakeConn()
    rec.log_forecasts(conn, [{'player_id': 1, 'code': 101, 'expected_points': 3.0,
                              'official_expected_points': 2.5}], 6,
                      datetime(2026, 10, 10, 10), datetime(2026, 10, 8, 6))
    create_sql = conn.cur.calls[0][0]
    insert_sql, records = conn.cur.calls[1]
    assert 'PRIMARY KEY (player_id, gameweek, model_version, log_date)' in create_sql
    assert insert_sql.strip().startswith(f'INSERT IGNORE INTO {rec.LOG_TABLE}')
    assert records[0][-3:] == (MODEL_VERSION, datetime(2026, 10, 8, 6), datetime(2026, 10, 8).date())
    assert conn.commits == 1


def test_template_squad_takes_the_most_selected_by_position():
    rows = ([{'player_id': i, 'position': 1, 'selected': 100 - i} for i in range(1, 5)] +
            [{'player_id': 10 + i, 'position': 2, 'selected': 100 - i} for i in range(1, 8)] +
            [{'player_id': 20 + i, 'position': 3, 'selected': 100 - i} for i in range(1, 8)] +
            [{'player_id': 30 + i, 'position': 4, 'selected': 100 - i} for i in range(1, 5)])
    squad = rec.template_squad(rows)
    assert len(squad) == 15
    assert {1, 2} <= set(squad) and 3 not in squad
    assert {31, 32, 33} <= set(squad) and 34 not in squad


def test_captain_pick_ignores_players_without_a_match_and_breaks_ties_by_id():
    assert rec.captain_pick([1, 2, 3], {1: 9.0, 2: 6.0, 3: 6.0}, playing={2, 3}) == 2
    assert rec.captain_pick([1], {1: 9.0}, playing=set()) is None


def test_accuracy_counts_captain_outcomes_and_per_position_errors():
    record = {1: {'player_id': 1, 'position': 4, 'expected_points': 7.0, 'official_expected_points': 4.0},
              2: {'player_id': 2, 'position': 3, 'expected_points': 3.0, 'official_expected_points': 8.0}}
    result = rec.accuracy_for_gameweek(record, {1: 12, 2: 2}, [1, 2], {1, 2})
    assert result['captain_ours'] == 1 and result['captain_official'] == 2
    assert result['captain_ours_points'] == 12 and result['captain_official_points'] == 2
    assert result['mae_by_position'][4] == {'ours': 5.0, 'official': 8.0, 'players': 1}
    assert result['players'] == 2


def test_players_without_an_actual_score_are_left_out_of_the_accuracy():
    record = {1: {'player_id': 1, 'position': 4, 'expected_points': 7.0, 'official_expected_points': 4.0},
              2: {'player_id': 2, 'position': 4, 'expected_points': 3.0, 'official_expected_points': None}}
    result = rec.accuracy_for_gameweek(record, {1: 5}, [1, 2], {1})
    assert result['players'] == 1


def test_accuracy_rows_replace_rather_than_duplicate():
    conn = FakeConn()
    rec.persist_accuracy(conn, 6, 2026, {'players': 1, 'mae_ours': 1.0, 'mae_official': 2.0,
                                         'mae_by_position': {}, 'captain_ours': 1, 'captain_official': 2,
                                         'captain_ours_points': 5, 'captain_official_points': 3},
                         datetime(2026, 10, 12))
    assert conn.cur.calls[1][0].strip().startswith(f'REPLACE INTO {rec.ACCURACY_TABLE}')
```

- [ ] **Step 4: Run to see them fail**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/step_defs/test_expected_points_record.py tests/test_expected_points_record.py`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 5: Implement**

`FPL_site/expectedPointsRecord.py`:

```python
"""The weekly record of our expected points: what we forecast before each deadline, and how
accurate it turned out, next to the official game's number for the same players.

Same honesty rule as matchPredictionEngine's fixture_prediction_log: only forecasts made before
the deadline count, and the log is append-only.
"""
import json
import logging
from datetime import datetime

from FPL_site.expectedPointsFeatures import MODEL_VERSION

logger = logging.getLogger(__name__)

LOG_TABLE = 'expected_points_log'
ACCURACY_TABLE = 'expected_points_accuracy'
CURRENT_TABLE = 'player_expected_points'
DEADLINE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
TEMPLATE_SHAPE = {1: 2, 2: 5, 3: 5, 4: 3}


def _deadline(event):
    try:
        return datetime.strptime(event.get('deadline_time') or '', DEADLINE_FORMAT)
    except (ValueError, TypeError):
        return None


def deadline_for(events, gameweek):
    event = next((e for e in events if e.get('id') == gameweek), None)
    return _deadline(event) if event else None


def next_gameweek(events, now):
    upcoming = sorted((d, e['id']) for e in events for d in [_deadline(e)] if d and d > now)
    return upcoming[0][1] if upcoming else None


def is_settled(events, gameweek):
    event = next((e for e in events if e.get('id') == gameweek), None)
    return bool(event and event.get('finished') and event.get('data_checked'))


def log_forecasts(conn, rows, gameweek, deadline, now):
    if deadline is None or now >= deadline or not rows:
        return 0
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {LOG_TABLE} (
            player_id INT NOT NULL,
            code INT NOT NULL,
            gameweek INT NOT NULL,
            expected_points FLOAT,
            official_expected_points FLOAT,
            model_version VARCHAR(40) NOT NULL,
            logged_at DATETIME NOT NULL,
            log_date DATE NOT NULL,
            PRIMARY KEY (player_id, gameweek, model_version, log_date)
        )
    """)
    cursor.executemany(f"""
        INSERT IGNORE INTO {LOG_TABLE}
            (player_id, code, gameweek, expected_points, official_expected_points,
             model_version, logged_at, log_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, [(r['player_id'], r['code'], gameweek, r['expected_points'], r['official_expected_points'],
           MODEL_VERSION, now, now.date()) for r in rows])
    conn.commit()
    logger.info("Logged %d expected points forecasts for gameweek %s.", len(rows), gameweek)
    return len(rows)


def forecast_of_record(log_rows, deadline):
    record = {}
    for r in sorted(log_rows, key=lambda r: r['logged_at']):
        if r['logged_at'] < deadline:
            record[r['player_id']] = r
    return record


def template_squad(selection_rows):
    squad = []
    for position, count in TEMPLATE_SHAPE.items():
        group = sorted((r for r in selection_rows if r['position'] == position),
                       key=lambda r: (-(r['selected'] or 0), r['player_id']))
        squad.extend(r['player_id'] for r in group[:count])
    return squad


def captain_pick(squad, values, playing):
    options = [(-values[p], p) for p in squad if p in playing and values.get(p) is not None]
    return min(options)[1] if options else None


def _mae(pairs):
    return round(sum(abs(f - a) for f, a in pairs) / len(pairs), 3) if pairs else None


def accuracy_for_gameweek(record, actual, squad, playing):
    """record: {player_id: {'position', 'expected_points', 'official_expected_points'}}."""
    both = [r for pid, r in record.items() if pid in actual
            and r.get('expected_points') is not None and r.get('official_expected_points') is not None]
    by_position = {}
    for r in both:
        by_position.setdefault(r['position'], []).append(r)
    ours = {pid: r['expected_points'] for pid, r in record.items() if r.get('expected_points') is not None}
    official = {pid: r['official_expected_points'] for pid, r in record.items()
                if r.get('official_expected_points') is not None}
    cap_ours, cap_official = captain_pick(squad, ours, playing), captain_pick(squad, official, playing)
    return {
        'players': len(both),
        'mae_ours': _mae([(r['expected_points'], actual[r['player_id']]) for r in both]),
        'mae_official': _mae([(r['official_expected_points'], actual[r['player_id']]) for r in both]),
        'mae_by_position': {pos: {'ours': _mae([(r['expected_points'], actual[r['player_id']]) for r in g]),
                                  'official': _mae([(r['official_expected_points'], actual[r['player_id']]) for r in g]),
                                  'players': len(g)}
                            for pos, g in by_position.items()},
        'captain_ours': cap_ours,
        'captain_official': cap_official,
        'captain_ours_points': actual.get(cap_ours),
        'captain_official_points': actual.get(cap_official),
    }


def persist_accuracy(conn, gameweek, year_start, result, now):
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {ACCURACY_TABLE} (
            year_start INT NOT NULL,
            gameweek INT NOT NULL,
            model_version VARCHAR(40) NOT NULL,
            players INT NOT NULL,
            mae_ours FLOAT,
            mae_official FLOAT,
            mae_by_position TEXT,
            captain_ours INT,
            captain_official INT,
            captain_ours_points INT,
            captain_official_points INT,
            computed_at DATETIME NOT NULL,
            PRIMARY KEY (year_start, gameweek, model_version)
        )
    """)
    cursor.execute(f"""
        REPLACE INTO {ACCURACY_TABLE}
            (year_start, gameweek, model_version, players, mae_ours, mae_official, mae_by_position,
             captain_ours, captain_official, captain_ours_points, captain_official_points, computed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (year_start, gameweek, MODEL_VERSION, result['players'], result['mae_ours'],
          result['mae_official'], json.dumps(result['mae_by_position']), result['captain_ours'],
          result['captain_official'], result['captain_ours_points'], result['captain_official_points'], now))
    conn.commit()


def persist_current(conn, rows, now):
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {CURRENT_TABLE} (
            player_id INT NOT NULL,
            code INT NOT NULL,
            gameweek INT NOT NULL,
            expected_points FLOAT,
            model_version VARCHAR(40) NOT NULL,
            computed_at DATETIME NOT NULL,
            PRIMARY KEY (player_id, gameweek)
        )
    """)
    cursor.executemany(f"""
        REPLACE INTO {CURRENT_TABLE} (player_id, code, gameweek, expected_points, model_version, computed_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, [(r['player_id'], r['code'], r['gameweek'], r['expected_points'], MODEL_VERSION, now) for r in rows])
    conn.commit()
```

Note: the accuracy JSON keys become strings (`"4"`) once stored; that is fine because only the report reads them.

- [ ] **Step 6: Run to see them pass**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/step_defs/test_expected_points_record.py tests/test_expected_points_record.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git checkout -- FPL_site/__pycache__ 2>/dev/null; git add FPL_site/expectedPointsRecord.py features/expected_points/weekly_record.feature tests/step_defs/test_expected_points_record.py tests/test_expected_points_record.py && git commit -m "Keep a pre-deadline log of every week's forecasts and their accuracy

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Fetchers, the daily job and run_update wiring

**Files:**
- Modify: `FPL_site/expectedPointsModel.py` (append fetchers and `run_daily_expected_points`)
- Modify: `FPL_site/run_update.py`
- Test: `tests/test_expected_points_daily.py`; update `tests/test_daily_jobs_season.py` only if it asserts the run_update job list (the existing `run_daily_predictions` test stays: the function still exists).

**Interfaces:**
- Consumes: Tasks 1–4; `dataModels.connect_db`, `current_season_start`, `refresh_season_start`, `db`; `fixtureXgHistory.load_fixture_xg`, `fill_missing`; `matchPredictionEngine.fetch_team_code_map`.
- Produces:
  - `fetch_events() -> list | None` (official `bootstrap-static` events, timeout 10s; `None` on failure)
  - `fetch_history_rows(cursor, years) -> list[HistoryRow]`
  - `fetch_snapshot_rows(cursor, years) -> list[SnapshotRow]`
  - `fetch_live_fixture_xg(cursor, year_start, gameweek, id_to_code) -> FixtureXg` (from `team_fixture_predictions` for the coming gameweek)
  - `fetch_actual_points(cursor, year_start, gameweek) -> {player_id: points}`
  - `fetch_log_rows(cursor, gameweek) -> list` (this model version, joined to position via the latest snapshot)
  - `run_daily_expected_points(now=None)`

- [ ] **Step 1: Write the failing tests**

`tests/test_expected_points_daily.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime

from FPL_site import expectedPointsModel as em
from FPL_site import expectedPointsRecord as rec


class Conn:
    def __init__(self):
        self.closed = False

    def cursor(self, **k):
        return object()

    def commit(self):
        pass

    def close(self):
        self.closed = True


EVENTS = [{'id': 5, 'deadline_time': '2026-10-03T10:00:00Z', 'finished': True, 'data_checked': True},
          {'id': 6, 'deadline_time': '2026-10-10T10:00:00Z', 'finished': False, 'data_checked': False}]


def patch_job(monkeypatch, calls, now_events=EVENTS):
    monkeypatch.setattr(em, 'refresh_season_start', lambda: 2026)
    monkeypatch.setattr(em, 'current_season_start', lambda: 2026)
    monkeypatch.setattr(em, 'connect_db', lambda: Conn())
    monkeypatch.setattr(em, 'fetch_events', lambda: now_events)
    monkeypatch.setattr(em, 'fetch_history_rows', lambda c, y: [])
    monkeypatch.setattr(em, 'fetch_snapshot_rows', lambda c, y: [
        {'code': 1, 'player_id': 7, 'year_start': 2026, 'gameweek': 5, 'element_type': 3, 'team_code': 3,
         'now_cost': 60, 'chance_of_playing_next_round': None, 'ep_next': 4.5,
         'expected_goals': 0.0, 'expected_assists': 0.0}])
    monkeypatch.setattr(em, 'fill_missing', lambda conn, cur, wanted: calls.setdefault('wanted', wanted) and 0)
    monkeypatch.setattr(em, 'load_fixture_xg', lambda cur: {})
    monkeypatch.setattr(em, 'fetch_team_code_map', lambda cur, y: {})
    monkeypatch.setattr(em, 'fetch_live_fixture_xg', lambda cur, y, gw, m: {})
    monkeypatch.setattr(em, 'train', lambda rows: {})
    monkeypatch.setattr(em, 'predict', lambda models, rows: [3.2 for _ in rows])
    monkeypatch.setattr(em, 'persist_current', lambda conn, rows, now: calls.setdefault('current', rows))
    monkeypatch.setattr(em, 'log_forecasts', lambda conn, rows, gw, deadline, now:
                        calls.setdefault('log', (rows, gw, deadline)) and len(rows))
    monkeypatch.setattr(em, 'record_settled_gameweeks', lambda conn, cur, events, year, now:
                        calls.setdefault('settled', True))


def test_the_daily_job_forecasts_the_next_gameweek_and_logs_it_with_the_official_number(monkeypatch):
    calls = {}
    patch_job(monkeypatch, calls)
    em.run_daily_expected_points(now=datetime(2026, 10, 8, 6))
    rows, gw, deadline = calls['log']
    assert gw == 6 and deadline == datetime(2026, 10, 10, 10)
    assert rows[0] == {'player_id': 7, 'code': 1, 'gameweek': 6, 'expected_points': 3.2,
                       'official_expected_points': 4.5}
    assert calls['current'][0]['expected_points'] == 3.2
    assert calls['settled'] is True


def test_no_upcoming_gameweek_means_no_forecasts(monkeypatch):
    calls = {}
    patch_job(monkeypatch, calls)
    em.run_daily_expected_points(now=datetime(2026, 10, 11, 6))
    assert 'log' not in calls and 'current' not in calls


def test_the_official_api_being_down_stops_the_job_quietly(monkeypatch):
    calls = {}
    patch_job(monkeypatch, calls, now_events=None)
    em.run_daily_expected_points(now=datetime(2026, 10, 8, 6))
    assert calls == {}


def test_run_update_runs_our_model_instead_of_the_old_one():
    src = open(os.path.join(os.path.dirname(em.__file__), 'run_update.py'), encoding='utf-8').read()
    assert 'run_daily_expected_points' in src
    assert 'run_daily_predictions,' not in src and 'import run_daily_predictions' not in src
```

- [ ] **Step 2: Run to see them fail**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/test_expected_points_daily.py`
Expected: FAIL with `AttributeError: module 'FPL_site.expectedPointsModel' has no attribute 'refresh_season_start'` (or similar).

- [ ] **Step 3: Implement the fetchers and the job**

Append to `FPL_site/expectedPointsModel.py` (and add these imports at the top of the file):

```python
from datetime import datetime

import requests

from FPL_site.dataModels import connect_db, current_season_start, refresh_season_start, db
from FPL_site.expectedPointsFeatures import training_rows, prediction_rows
from FPL_site.expectedPointsRecord import (deadline_for, next_gameweek, is_settled, log_forecasts,
                                           forecast_of_record, template_squad, accuracy_for_gameweek,
                                           persist_accuracy, persist_current, LOG_TABLE, ACCURACY_TABLE)
from FPL_site.fixtureXgHistory import load_fixture_xg, fill_missing
from FPL_site.matchPredictionEngine import fetch_team_code_map

HISTORY_SEASONS = 3   # this season and the two before it
```

```python
#################################################
#                  Fetchers                     #
#################################################

def fetch_events():
    try:
        response = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/', timeout=10)
        response.raise_for_status()
        return response.json().get('events', [])
    except Exception as e:
        logger.error("expected points: could not fetch the official events: %s", type(e).__name__)
        return None


def _codes_by_season(cursor, years):
    """{(year_start, player id): code} from the snapshots (a player's id is per season)."""
    placeholders = ', '.join(['%s'] * len(years))
    cursor.execute(f"""SELECT DISTINCT year_start, id, code FROM {db}.bootstrapstatic_elements
                       WHERE year_start IN ({placeholders})""", tuple(years))
    return {(r['year_start'], r['id']): r['code'] for r in cursor.fetchall()}


def fetch_history_rows(cursor, years):
    codes = _codes_by_season(cursor, years)
    team_maps = {y: fetch_team_code_map(cursor, y) for y in years}
    placeholders = ', '.join(['%s'] * len(years))
    cursor.execute(f"""
        SELECT DISTINCT h.year_start, h.element, h.round, h.fixture, h.opponent_team, h.was_home,
               h.minutes, h.goals_scored, h.assists, h.clean_sheets, h.bonus, h.total_points,
               CASE WHEN h.was_home = 1 THEN f.team_h ELSE f.team_a END AS team_id
        FROM {db}.elementsummary_history h
        JOIN {db}.fixtures_fixtures f
          ON f.id = h.fixture AND f.year_start = h.year_start AND f.kickoff_time = h.kickoff_time
        WHERE h.year_start IN ({placeholders})
    """, tuple(years))
    rows = []
    for r in cursor.fetchall():
        code = codes.get((r['year_start'], r['element']))
        team_map = team_maps.get(r['year_start'], {})
        if code is None or r['team_id'] not in team_map:
            continue
        rows.append({'code': code, 'year_start': r['year_start'], 'gameweek': r['round'],
                     'team_code': team_map[r['team_id']], 'opponent_code': team_map.get(r['opponent_team']),
                     'was_home': bool(r['was_home']), 'minutes': r['minutes'] or 0,
                     'goals_scored': r['goals_scored'] or 0, 'assists': r['assists'] or 0,
                     'clean_sheets': r['clean_sheets'] or 0, 'bonus': r['bonus'] or 0,
                     'total_points': r['total_points'] or 0})
    return rows


def fetch_snapshot_rows(cursor, years):
    team_maps = {y: fetch_team_code_map(cursor, y) for y in years}
    placeholders = ', '.join(['%s'] * len(years))
    cursor.execute(f"""
        SELECT year_start, gameweek, id, code, element_type, team, now_cost,
               chance_of_playing_next_round, ep_next, expected_goals, expected_assists, selected_by_percent
        FROM {db}.bootstrapstatic_elements WHERE year_start IN ({placeholders})
    """, tuple(years))
    out = []
    for r in cursor.fetchall():
        team_code = team_maps.get(r['year_start'], {}).get(r['team'])
        if team_code is None:
            continue
        out.append({'code': r['code'], 'player_id': r['id'], 'year_start': r['year_start'],
                    'gameweek': r['gameweek'], 'element_type': r['element_type'], 'team_code': team_code,
                    'now_cost': r['now_cost'], 'chance_of_playing_next_round': r['chance_of_playing_next_round'],
                    'ep_next': float(r['ep_next']) if r['ep_next'] is not None else None,
                    'expected_goals': float(r['expected_goals'] or 0),
                    'expected_assists': float(r['expected_assists'] or 0),
                    'selected': float(r['selected_by_percent'] or 0)})
    return out


def fetch_live_fixture_xg(cursor, year_start, gameweek, id_to_code):
    """The coming gameweek from the live engine's stored predictions (team ids are this season's)."""
    cursor.execute(f"""
        SELECT mine.team_id, mine.is_home, mine.expected_goals_mean AS own_mean,
               theirs.expected_goals_mean AS opp_mean
        FROM {db}.team_fixture_predictions mine
        JOIN {db}.team_fixture_predictions theirs
          ON theirs.fixture_code = mine.fixture_code AND theirs.team_id = mine.opponent_id
        WHERE mine.gameweek = %s
    """, (gameweek,))
    out = {}
    for r in cursor.fetchall():
        code = id_to_code.get(r['team_id'])
        if code is None:
            continue
        t = out.setdefault((year_start, gameweek, code),
                           {'team_xg': 0.0, 'opp_xg': 0.0, 'matches': 0, 'home_share': 0.0})
        t['team_xg'] += float(r['own_mean'])
        t['opp_xg'] += float(r['opp_mean'])
        t['home_share'] = (t['home_share'] * t['matches'] + (1.0 if r['is_home'] else 0.0)) / (t['matches'] + 1)
        t['matches'] += 1
    return out


def fetch_actual_points(cursor, year_start, gameweek):
    cursor.execute(f"""SELECT element, SUM(total_points) AS points FROM {db}.elementsummary_history
                       WHERE year_start = %s AND round = %s GROUP BY element""", (year_start, gameweek))
    return {r['element']: int(r['points']) for r in cursor.fetchall()}


def fetch_log_rows(cursor, gameweek):
    cursor.execute(f"""SELECT player_id, code, expected_points, official_expected_points, logged_at
                       FROM {LOG_TABLE} WHERE gameweek = %s AND model_version = %s""",
                   (gameweek, MODEL_VERSION))
    return cursor.fetchall()


def fetch_recorded_gameweeks(cursor, year_start):
    try:
        cursor.execute(f"SELECT gameweek FROM {ACCURACY_TABLE} WHERE year_start = %s AND model_version = %s",
                       (year_start, MODEL_VERSION))
        return {r['gameweek'] for r in cursor.fetchall()}
    except Exception:
        return set()   # the table is created on the first accuracy write


#################################################
#                  Daily job                    #
#################################################

def record_settled_gameweeks(conn, cursor, events, year_start, now):
    """Write accuracy for every settled gameweek we logged forecasts for and haven't recorded."""
    done = fetch_recorded_gameweeks(cursor, year_start)
    snapshots = [s for s in fetch_snapshot_rows(cursor, [year_start])]
    for e in events:
        gw = e['id']
        if gw in done or not is_settled(events, gw):
            continue
        try:
            log_rows = fetch_log_rows(cursor, gw)
        except Exception:
            continue   # no log table yet
        if not log_rows:
            continue
        record = forecast_of_record(log_rows, deadline_for(events, gw))
        before = [s for s in snapshots if s['gameweek'] == gw - 1]
        position = {s['player_id']: s['element_type'] for s in before}
        for pid, r in record.items():
            r['position'] = position.get(pid)
        actual = fetch_actual_points(cursor, year_start, gw)
        squad = template_squad([{'player_id': s['player_id'], 'position': s['element_type'],
                                 'selected': s['selected']} for s in before])
        result = accuracy_for_gameweek(record, actual, squad, set(actual))
        persist_accuracy(conn, gw, year_start, result, now)
        logger.info("Expected points accuracy for gameweek %s: ours %s, official %s.",
                    gw, result['mae_ours'], result['mae_official'])


def run_daily_expected_points(now=None):
    """Train on every finished gameweek, forecast the next one, log it, record settled weeks."""
    now = now or datetime.utcnow()
    refresh_season_start()
    year = current_season_start()
    events = fetch_events()
    if events is None:
        return
    gameweek = next_gameweek(events, now)
    conn = connect_db()
    if conn is None:
        logger.error("run_daily_expected_points: could not connect to the database.")
        return
    try:
        cursor = conn.cursor(dictionary=True)
        years = [year - i for i in range(HISTORY_SEASONS)]
        history = fetch_history_rows(cursor, years)
        snapshots = fetch_snapshot_rows(cursor, years)
        wanted = sorted({(h['year_start'], h['gameweek']) for h in history})
        fill_missing(conn, cursor, wanted)
        fixture_xg = load_fixture_xg(cursor)
        if gameweek is not None:
            models = train(training_rows(history, snapshots, fixture_xg))
            fixture_xg.update(fetch_live_fixture_xg(cursor, year, gameweek, fetch_team_code_map(cursor, year)))
            latest_gw = max((s['gameweek'] for s in snapshots if s['year_start'] == year), default=None)
            players = [s for s in snapshots if s['year_start'] == year and s['gameweek'] == latest_gw]
            rows = prediction_rows(history, snapshots, fixture_xg, year, gameweek, players)
            values = predict(models, rows)
            official = {p['player_id']: p['ep_next'] for p in players}
            forecasts = [{'player_id': r['player_id'], 'code': r['code'], 'gameweek': gameweek,
                          'expected_points': v, 'official_expected_points': official.get(r['player_id'])}
                         for r, v in zip(rows, values) if not math.isnan(v)]
            persist_current(conn, forecasts, now)
            log_forecasts(conn, forecasts, gameweek, deadline_for(events, gameweek), now)
        record_settled_gameweeks(conn, cursor, events, year, now)
    finally:
        conn.close()
```

- [ ] **Step 4: Wire run_update.py**

In `FPL_site/run_update.py` replace

```python
from FPL_site.futurePerformanceModel import run_daily_predictions
```
with
```python
from FPL_site.expectedPointsModel import run_daily_expected_points
```
and the job tuple with
```python
for job in (update_all_tables, run_daily_match_predictions, run_daily_expected_points):
```
(`run_daily_match_predictions` runs first so `team_fixture_predictions` is fresh for the coming gameweek.) Update the comment above the loop: replace the `run_daily_predictions()` example with `run_daily_expected_points()`.

- [ ] **Step 5: Run the whole suite**

Run: `vs-env/Scripts/python.exe -m pytest -q`
Expected: all PASS (the existing `test_player_job_refreshes_the_season_before_preparing_data` still targets `futurePerformanceModel.run_daily_predictions`, which still exists).

- [ ] **Step 6: Commit**

```bash
git checkout -- FPL_site/__pycache__ 2>/dev/null; git add FPL_site/expectedPointsModel.py FPL_site/run_update.py tests/test_expected_points_daily.py && git commit -m "Run our expected points model in the daily job and record settled gameweeks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The backtest

**Files:**
- Create: `FPL_site/expectedPointsBacktest.py`
- Test: `tests/test_expected_points_backtest.py`
- Output (when run by hand, not in tests): `docs/superpowers/reports/expected-points-backtest-<YYYY-MM-DD>.md`

**Interfaces:**
- Consumes: Tasks 1–5 (`training_rows`, `train`, `predict`, `template_squad`, `captain_pick`, fetchers, `fill_missing`, `load_fixture_xg`).
- Produces:
  - `walk_forward(rows, official, targets) -> list[dict]` — pure; `rows` are training rows (with `player_id`); `targets` is a list of `(year_start, gameweek)`; for each, trains on rows strictly before it and predicts its rows; returns `{'year_start', 'gameweek', 'player_id', 'position', 'ours', 'official', 'actual'}` for rows where `official` (`{(year, gw, player_id): value}`) has a value.
  - `summarise(results, squads_by_gw) -> dict` — `mae_ours`, `mae_official`, `mae_by_position`, `captain_wins_ours`, `captain_wins_official`, `captain_ties`, `passes` (both conditions from the spec).
  - `render_report(summary, run_date) -> str` (Markdown)
  - `main()` — fetches, fills fixture xg, runs, writes the report.

- [ ] **Step 1: Write the failing tests**

`tests/test_expected_points_backtest.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import expectedPointsBacktest as bt


def result(gw, pid, ours, official, actual, position=3):
    return {'year_start': 2025, 'gameweek': gw, 'player_id': pid, 'position': position,
            'ours': ours, 'official': official, 'actual': actual}


def test_passes_only_when_both_error_and_captaincy_beat_the_official_number():
    results = [result(1, 1, 8, 4, 9), result(1, 2, 2, 6, 1), result(2, 1, 7, 3, 8), result(2, 2, 3, 5, 2)]
    squads = {(2025, 1): [1, 2], (2025, 2): [1, 2]}
    s = bt.summarise(results, squads)
    assert s['mae_ours'] < s['mae_official']
    assert s['captain_wins_ours'] == 2 and s['captain_wins_official'] == 0
    assert s['passes'] is True


def test_lower_error_but_worse_captains_fails():
    # Player 3 is outside the squad: ours is spot on there, which wins the error test, but inside
    # the squad ours picks player 2 (2 points) while the official number picks player 1 (10).
    results = [result(1, 1, 5, 9, 10), result(1, 2, 6, 0, 2), result(1, 3, 2, 20, 2)]
    s = bt.summarise(results, {(2025, 1): [1, 2]})
    assert s['mae_ours'] < s['mae_official']
    assert s['captain_wins_official'] == 1
    assert s['passes'] is False


def test_walk_forward_never_trains_on_the_gameweek_it_predicts(monkeypatch):
    trained_on = []
    monkeypatch.setattr(bt, 'train', lambda rows: trained_on.append({(r['year_start'], r['gameweek']) for r in rows}) or {})
    monkeypatch.setattr(bt, 'predict', lambda models, rows: [1.0] * len(rows))
    rows = [{'year_start': 2025, 'gameweek': g, 'player_id': 1, 'position': 3, 'target': 2} for g in (1, 2, 3)]
    official = {(2025, g, 1): 2.0 for g in (1, 2, 3)}
    out = bt.walk_forward(rows, official, [(2025, 2), (2025, 3)])
    assert trained_on == [{(2025, 1)}, {(2025, 1), (2025, 2)}]
    assert [r['gameweek'] for r in out] == [2, 3]


def test_the_report_states_the_verdict():
    text = bt.render_report({'mae_ours': 1.9, 'mae_official': 2.1, 'mae_by_position': {},
                             'captain_wins_ours': 20, 'captain_wins_official': 15, 'captain_ties': 3,
                             'gameweeks': 38, 'players': 9000, 'passes': True}, '2026-10-09')
    assert 'Passes: yes' in text and '1.9' in text and '2.1' in text
```

- [ ] **Step 2: Run to see them fail**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/test_expected_points_backtest.py`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`FPL_site/expectedPointsBacktest.py`:

```python
"""Offline walk-forward backtest: would our expected points have beaten the official number?

Run by hand: python -m FPL_site.expectedPointsBacktest
For each target gameweek, train only on earlier gameweeks and predict that one, then compare with
the official ep_next from the snapshot taken just before it, on the same players. Writes a report
to docs/superpowers/reports/. Never run from a request or the daily job.
"""
import logging
import os
from datetime import date

from FPL_site.dataModels import connect_db, current_season_start, refresh_season_start
from FPL_site.expectedPointsFeatures import training_rows
from FPL_site.expectedPointsModel import (train, predict, fetch_history_rows, fetch_snapshot_rows,
                                          MODEL_VERSION)
from FPL_site.expectedPointsRecord import template_squad, captain_pick
from FPL_site.fixtureXgHistory import fill_missing, load_fixture_xg

logger = logging.getLogger(__name__)

FIRST_TARGET_GAMEWEEK = 6   # leave the first five gameweeks of the earliest backtest season to train on
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs', 'superpowers', 'reports')


def walk_forward(rows, official, targets):
    out = []
    for year, gw in targets:
        past = [r for r in rows if (r['year_start'], r['gameweek']) < (year, gw)]
        now = [r for r in rows if (r['year_start'], r['gameweek']) == (year, gw)
               and official.get((year, gw, r['player_id'])) is not None]
        if not past or not now:
            continue
        values = predict(train(past), now)
        for r, v in zip(now, values):
            if v != v:   # nan: no model for that position yet
                continue
            out.append({'year_start': year, 'gameweek': gw, 'player_id': r['player_id'],
                        'position': r['position'], 'ours': v,
                        'official': official[(year, gw, r['player_id'])], 'actual': r['target']})
    return out


def _mae(pairs):
    return round(sum(abs(a - b) for a, b in pairs) / len(pairs), 3) if pairs else None


def summarise(results, squads_by_gw):
    by_position, by_gw = {}, {}
    for r in results:
        by_position.setdefault(r['position'], []).append(r)
        by_gw.setdefault((r['year_start'], r['gameweek']), []).append(r)
    wins_ours = wins_official = ties = 0
    for key, group in by_gw.items():
        squad = squads_by_gw.get(key, [])
        actual = {r['player_id']: r['actual'] for r in group}
        ours = captain_pick(squad, {r['player_id']: r['ours'] for r in group}, set(actual))
        official = captain_pick(squad, {r['player_id']: r['official'] for r in group}, set(actual))
        if ours is None or official is None:
            continue
        if actual[ours] > actual[official]:
            wins_ours += 1
        elif actual[official] > actual[ours]:
            wins_official += 1
        else:
            ties += 1
    mae_ours = _mae([(r['ours'], r['actual']) for r in results])
    mae_official = _mae([(r['official'], r['actual']) for r in results])
    return {
        'players': len(results), 'gameweeks': len(by_gw),
        'mae_ours': mae_ours, 'mae_official': mae_official,
        'mae_by_position': {p: {'ours': _mae([(r['ours'], r['actual']) for r in g]),
                                'official': _mae([(r['official'], r['actual']) for r in g]),
                                'players': len(g)} for p, g in sorted(by_position.items())},
        'captain_wins_ours': wins_ours, 'captain_wins_official': wins_official, 'captain_ties': ties,
        'passes': (mae_ours is not None and mae_official is not None
                   and mae_ours < mae_official and wins_ours > wins_official),
    }


POSITION_NAMES = {1: 'Goalkeepers', 2: 'Defenders', 3: 'Midfielders', 4: 'Forwards'}


def render_report(summary, run_date):
    lines = [
        f'# Expected points backtest ({run_date})', '',
        f'Model version: `{MODEL_VERSION}`. Walk-forward: each gameweek predicted by a model trained '
        f'only on earlier gameweeks, compared with the official number from the snapshot just before it.', '',
        f'- Gameweeks: {summary["gameweeks"]}, player-gameweeks: {summary["players"]}',
        f'- Average error, ours: {summary["mae_ours"]}',
        f'- Average error, official: {summary["mae_official"]}',
        f'- Captain (most-selected squad each week): ours better {summary["captain_wins_ours"]}, '
        f'official better {summary["captain_wins_official"]}, same {summary["captain_ties"]}',
        f'- Passes: {"yes" if summary["passes"] else "no"}', '',
        '| Position | Ours | Official | Players |', '|---|---|---|---|',
    ]
    for p, m in summary['mae_by_position'].items():
        lines.append(f'| {POSITION_NAMES.get(int(p), p)} | {m["ours"]} | {m["official"]} | {m["players"]} |')
    return '\n'.join(lines) + '\n'


def main():
    logging.basicConfig(level=logging.INFO)
    refresh_season_start()
    year = current_season_start()
    conn = connect_db()
    try:
        cursor = conn.cursor(dictionary=True)
        years = [year - 2, year - 1, year]
        history = fetch_history_rows(cursor, years)
        snapshots = fetch_snapshot_rows(cursor, years)
        fill_missing(conn, cursor, sorted({(h['year_start'], h['gameweek']) for h in history}))
        rows = training_rows(history, snapshots, load_fixture_xg(cursor))
        ids = {(s['code'], s['year_start']): s['player_id'] for s in snapshots}
        for r in rows:
            r['player_id'] = ids.get((r['code'], r['year_start']))
        rows = [r for r in rows if r['player_id'] is not None]
        official = {(s['year_start'], s['gameweek'] + 1, s['player_id']): s['ep_next']
                    for s in snapshots if s['ep_next'] is not None}
        squads = {}
        for (y, gw) in {(s['year_start'], s['gameweek']) for s in snapshots}:
            before = [s for s in snapshots if s['year_start'] == y and s['gameweek'] == gw]
            squads[(y, gw + 1)] = template_squad([{'player_id': s['player_id'], 'position': s['element_type'],
                                                   'selected': s['selected']} for s in before])
        targets = sorted({(r['year_start'], r['gameweek']) for r in rows
                          if r['year_start'] >= year - 1
                          and (r['year_start'], r['gameweek']) >= (year - 1, FIRST_TARGET_GAMEWEEK)})
        summary = summarise(walk_forward(rows, official, targets), squads)
    finally:
        conn.close()
    os.makedirs(REPORT_DIR, exist_ok=True)
    run_date = date.today().isoformat()
    path = os.path.join(REPORT_DIR, f'expected-points-backtest-{run_date}.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(render_report(summary, run_date))
    print(f'Wrote {path}: passes={summary["passes"]}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run to see them pass**

Run: `vs-env/Scripts/python.exe -m pytest -q tests/test_expected_points_backtest.py`
Expected: PASS.

- [ ] **Step 5: Run the whole suite and commit**

Run: `vs-env/Scripts/python.exe -m pytest -q`
Expected: all PASS.

```bash
git checkout -- FPL_site/__pycache__ 2>/dev/null; git add FPL_site/expectedPointsBacktest.py tests/test_expected_points_backtest.py && git commit -m "Add the walk-forward backtest against the official expected points

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6 (controller, not the implementer): run the backtest for real**

Run: `vs-env/Scripts/python.exe -m FPL_site.expectedPointsBacktest` (reads MySQL, writes `fixture_xg_history` rows and the report; no live official API calls). Commit the report. The first run refits the match engine once per past gameweek (about 80 fits) and is slow; later runs reuse the stored rows.

---

### Follow-up (blocked until `this-week-player-info` is merged): the source switch

Not executed in this branch. When `this-week-player-info` is on main and the backtest report says
`Passes: yes`, a follow-up adds `EXPECTED_POINTS_SOURCE` (`official` default, `own`) to
`config.py`, makes `playerContext.fetch_expected_points` read `player_expected_points` for the hub
gameweek when it is `own`, adds `expected_points_source` to the hub and player-context JSON, and
gives `lib/playerInfoCopy.js` a "We expect 6.1 points" sentence for `own`. It gets its own short
plan then, because it touches code that only exists on the other branch.

---

## Deviation from the spec (decided while planning)

The spec's captain test uses "the public picks of a fixed sample of team numbers". Past seasons'
picks are not available from the official game, so both the backtest and the weekly record use a
**most-selected template squad** each gameweek (2 goalkeepers, 5 defenders, 5 midfielders,
3 forwards, by ownership in the snapshot before the gameweek). It is the same for both numbers, so
the comparison stays fair, and it needs no live API calls.

---

## Amendment (2026-10-08): seasons on every row, and backfilling past seasons

Spec section "Amendment 2026-10-08". Two tasks, run after Task 6. Nothing has been written to
MySQL by this branch yet, so the table definitions change in place (no migration).

### Task 7: Season and source on every stored forecast

**Files:**
- Modify: `FPL_site/expectedPointsRecord.py`
- Modify: `FPL_site/expectedPointsModel.py` (`fetch_log_rows`, `fetch_recorded_gameweeks`, `record_settled_gameweeks`, `run_daily_expected_points`)
- Modify tests: `tests/test_expected_points_record_rules.py`, `tests/step_defs/test_expected_points_record.py`, `features/expected_points/weekly_record.feature`, `tests/test_expected_points_daily.py`

**Interfaces (new signatures; update every caller and test):**
- `LIVE = 'live'`, `BACKFILL = 'backfill'` (module constants in `expectedPointsRecord`)
- `log_forecasts(conn, rows, year_start, gameweek, deadline, now, source=LIVE) -> int` — for `LIVE`, returns 0 when `deadline is None or now >= deadline`; for `BACKFILL` the deadline is ignored (pass `None`). Rows whose `expected_points` is nan are dropped first; empty `rows` → 0. Table:
  ```sql
  CREATE TABLE IF NOT EXISTS expected_points_log (
      year_start INT NOT NULL,
      player_id INT NOT NULL,
      code INT NOT NULL,
      gameweek INT NOT NULL,
      expected_points FLOAT,
      official_expected_points FLOAT,
      model_version VARCHAR(40) NOT NULL,
      source VARCHAR(10) NOT NULL,
      logged_at DATETIME NOT NULL,
      log_date DATE NOT NULL,
      PRIMARY KEY (year_start, player_id, gameweek, model_version, source, log_date)
  )
  ```
  Insert tuple order: `(year_start, player_id, code, gameweek, expected_points, official_expected_points, model_version, source, logged_at, log_date)`.
- `forecast_of_record(log_rows, deadline, source=LIVE) -> {player_id: row}` — `LIVE`: latest row with `logged_at < deadline` (as now). `BACKFILL`: latest row regardless of deadline (`deadline` may be `None`).
- `persist_accuracy(conn, gameweek, year_start, result, now, source=LIVE)` — table gains `source VARCHAR(10) NOT NULL` after `model_version`; primary key `(year_start, gameweek, model_version, source)`; `REPLACE INTO` includes `source` right after `model_version`.
- `persist_current(conn, rows, year_start, now)` — table gains `year_start INT NOT NULL` as its first column; primary key `(year_start, player_id, gameweek)`; insert tuple starts with `year_start`.
- `expectedPointsModel.fetch_log_rows(cursor, year_start, gameweek, source=LIVE)` — `WHERE year_start = %s AND gameweek = %s AND model_version = %s AND source = %s`, params `(year_start, gameweek, MODEL_VERSION, source)`.
- `expectedPointsModel.fetch_recorded_gameweeks(cursor, year_start, source=LIVE)` — adds `AND source = %s`.
- `record_settled_gameweeks(conn, cursor, events, year_start, now)` — unchanged signature; passes `year_start` and `LIVE` to the readers and writers.
- `run_daily_expected_points` — `persist_current(conn, forecasts, year, now)`; `log_forecasts(conn, forecasts, year, gameweek, deadline_for(events, gameweek), now)`.

- [ ] **Step 1: Write the failing tests** (add to `tests/test_expected_points_record_rules.py`):

```python
def test_every_logged_row_carries_its_season_and_source():
    conn = FakeConn()
    rec.log_forecasts(conn, [{'player_id': 1, 'code': 101, 'expected_points': 3.0,
                              'official_expected_points': 2.5}], 2026, 6,
                      datetime(2026, 10, 10, 10), datetime(2026, 10, 8, 6))
    create_sql = conn.cur.calls[0][0]
    insert_sql, records = conn.cur.calls[1]
    assert 'PRIMARY KEY (year_start, player_id, gameweek, model_version, source, log_date)' in create_sql
    assert records[0][0] == 2026
    assert records[0][7] == rec.LIVE


def test_a_backfill_is_logged_after_the_deadline_but_a_live_forecast_is_not():
    late = datetime(2026, 10, 11)
    row = [{'player_id': 1, 'code': 101, 'expected_points': 3.0, 'official_expected_points': None}]
    assert rec.log_forecasts(FakeConn(), row, 2025, 6, datetime(2026, 10, 10), late) == 0
    conn = FakeConn()
    assert rec.log_forecasts(conn, row, 2025, 6, None, late, source=rec.BACKFILL) == 1
    assert conn.cur.calls[1][1][0][7] == rec.BACKFILL


def test_nan_forecasts_are_never_written():
    conn = FakeConn()
    rows = [{'player_id': 1, 'code': 101, 'expected_points': float('nan'), 'official_expected_points': 2.0},
            {'player_id': 2, 'code': 102, 'expected_points': 4.0, 'official_expected_points': 2.0}]
    assert rec.log_forecasts(conn, rows, 2026, 6, datetime(2026, 10, 10), datetime(2026, 10, 8)) == 1


def test_the_backfill_record_ignores_the_deadline():
    rows = [{'player_id': 1, 'expected_points': 4.0, 'logged_at': datetime(2026, 10, 9)}]
    assert rec.forecast_of_record(rows, None, source=rec.BACKFILL)[1]['expected_points'] == 4.0


def test_current_forecasts_and_accuracy_are_keyed_by_season():
    conn = FakeConn()
    rec.persist_current(conn, [{'player_id': 1, 'code': 101, 'gameweek': 6, 'expected_points': 3.0}],
                        2026, datetime(2026, 10, 8))
    assert 'PRIMARY KEY (year_start, player_id, gameweek)' in conn.cur.calls[0][0]
    assert conn.cur.calls[1][1][0][0] == 2026
    conn = FakeConn()
    rec.persist_accuracy(conn, 6, 2025, {'players': 1, 'mae_ours': 1.0, 'mae_official': 2.0,
                                         'mae_by_position': {}, 'captain_ours': 1, 'captain_official': 2,
                                         'captain_ours_points': 5, 'captain_official_points': 3},
                         datetime(2026, 10, 12), source=rec.BACKFILL)
    assert 'PRIMARY KEY (year_start, gameweek, model_version, source)' in conn.cur.calls[0][0]
    assert rec.BACKFILL in conn.cur.calls[1][1]
```

and to `tests/test_expected_points_daily.py`:

```python
def test_reading_the_log_filters_by_season_and_source():
    seen = []

    class Cur:
        def execute(self, sql, params=None):
            seen.append((sql, params))

        def fetchall(self):
            return []

    em.fetch_log_rows(Cur(), 2026, 6)
    sql, params = seen[0]
    assert 'year_start = %s' in sql and 'source = %s' in sql
    assert params == (2026, 6, em.MODEL_VERSION, 'live')
```

- [ ] **Step 2: Run to see them fail.** `vs-env/Scripts/python.exe -m pytest -q tests/test_expected_points_record_rules.py tests/test_expected_points_daily.py` — expected: FAIL (`AttributeError: ... 'LIVE'` or a signature error).

- [ ] **Step 3: Implement** the signatures above in `expectedPointsRecord.py` and `expectedPointsModel.py`. Update the existing tests and step definitions to the new signatures (pass `2026` as `year_start`; the monkeypatched `persist_current` / `log_forecasts` lambdas in `tests/test_expected_points_daily.py` take the new parameters). In `features/expected_points/weekly_record.feature` add:

```gherkin
  Scenario: Every forecast is stored with its season
    Given the gameweek 6 deadline is tomorrow
    When the daily job logs 3 forecasts for the 2026 season
    Then every logged row is for the 2026 season
```
with step definitions in `tests/step_defs/test_expected_points_record.py` that keep the `FakeConn`, call `rec.log_forecasts(conn, rows, 2026, 6, ctx['deadline'], NOW)` and assert `record[0] == 2026` for every inserted record.

- [ ] **Step 4: Run the whole suite.** `vs-env/Scripts/python.exe -m pytest -q` — expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git checkout -- FPL_site/__pycache__ 2>/dev/null; git add FPL_site/expectedPointsRecord.py FPL_site/expectedPointsModel.py features/expected_points/weekly_record.feature tests/step_defs/test_expected_points_record.py tests/test_expected_points_record_rules.py tests/test_expected_points_daily.py && git commit -m "Store every forecast with its season and whether it was live or replayed

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Backfill past seasons with the data available at the time

**Files:**
- Modify: `FPL_site/expectedPointsBacktest.py` (extract `load_replay_data`; `walk_forward` gains `require_official` and returns `code`)
- Create: `FPL_site/expectedPointsBackfill.py`
- Create: `features/expected_points/backfill.feature`, `tests/step_defs/test_expected_points_backfill_steps.py`
- Test: `tests/test_expected_points_backfill.py`

**Interfaces:**
- Consumes (Task 7): `log_forecasts(..., source=BACKFILL)`, `forecast_of_record(..., source=BACKFILL)`, `persist_accuracy(..., source=BACKFILL)`, `LOG_TABLE`, `BACKFILL`; Task 6: `walk_forward`; Task 4: `template_squad`, `accuracy_for_gameweek`, `is_settled`; Task 5: `fetch_events`.
- Produces:
  - `expectedPointsBacktest.walk_forward(rows, official, targets, require_official=True) -> list` — every output row gains `'code'`; with `require_official=False`, rows without an official number are kept with `'official': None`.
  - `expectedPointsBacktest.load_replay_data(conn, cursor, years) -> dict` with `rows` (training rows with `player_id`), `official` (`{(year, gw, player_id): ep_next}` from snapshot gw − 1), `squads` (`{(year, gw): [player_id]}` from snapshot gw − 1). `main()` uses it.
  - `expectedPointsBackfill.replay_targets(rows, from_season, from_gameweek, settled) -> list[(year, gw)]`.
  - `expectedPointsBackfill.fetch_backfilled(cursor) -> set[(year, gw)]` (empty when the log table doesn't exist yet).
  - `expectedPointsBackfill.backfill(conn, data, targets, done, now) -> int` — gameweeks written.
  - `expectedPointsBackfill.main(argv=None)` — `--from-season` (default current season − 2), `--from-gameweek` (default 6). Past seasons count as settled; a current-season gameweek only if `is_settled(fetch_events(), gw)` (official API down → current season skipped, past seasons still run).

- [ ] **Step 1: Write the behaviour scenarios** — `features/expected_points/backfill.feature`:

```gherkin
Feature: Past seasons can be replayed with only the data available at the time

  Scenario: A replayed gameweek is forecast by a model trained only on earlier gameweeks
    Given stored history for 2025 gameweeks 1 to 8
    When I backfill from 2025 gameweek 6
    Then gameweek 6 was forecast by a model trained on gameweeks 1 to 5
    And gameweek 8 was forecast by a model trained on gameweeks 1 to 7

  Scenario: Replayed forecasts are stored as backfill with their season
    Given stored history for 2025 gameweeks 1 to 8
    When I backfill from 2025 gameweek 6
    Then the log holds 2025 forecasts for gameweeks 6, 7 and 8 marked as backfill
    And an accuracy row marked as backfill exists for each of those gameweeks

  Scenario: Running the backfill again adds nothing new
    Given stored history for 2025 gameweeks 1 to 8
    And gameweeks 6 and 7 of 2025 were already backfilled
    When I backfill from 2025 gameweek 6
    Then only gameweek 8 is written
```

- [ ] **Step 2: Write the step definitions** — `tests/step_defs/test_expected_points_backfill_steps.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from FPL_site import expectedPointsBackfill as bf
from FPL_site import expectedPointsBacktest as bt

scenarios('expected_points/backfill.feature')


@pytest.fixture
def ctx(monkeypatch):
    c = {'trained_on': [], 'logged': [], 'accuracy': [], 'done': set()}
    monkeypatch.setattr(bt, 'train', lambda rows: c['trained_on'].append(
        sorted({r['gameweek'] for r in rows})) or {})
    monkeypatch.setattr(bt, 'predict', lambda models, rows: [3.0] * len(rows))
    monkeypatch.setattr(bf, 'log_forecasts', lambda conn, rows, year, gw, deadline, now, source:
                        c['logged'].append((year, gw, source, len(rows))) or len(rows))
    monkeypatch.setattr(bf, 'persist_accuracy', lambda conn, gw, year, result, now, source:
                        c['accuracy'].append((year, gw, source)))
    return c


@given(parsers.parse('stored history for {year:d} gameweeks 1 to {last:d}'))
def _history(ctx, year, last):
    rows = [{'year_start': year, 'gameweek': gw, 'player_id': pid, 'code': 100 + pid, 'position': 3,
             'target': 2} for gw in range(1, last + 1) for pid in (1, 2)]
    ctx['data'] = {'rows': rows,
                   'official': {(year, gw, pid): 2.5 for gw in range(1, last + 1) for pid in (1, 2)},
                   'squads': {(year, gw): [1, 2] for gw in range(1, last + 1)}}


@given(parsers.parse('gameweeks 6 and 7 of {year:d} were already backfilled'))
def _done(ctx, year):
    ctx['done'] = {(year, 6), (year, 7)}


@when(parsers.parse('I backfill from {year:d} gameweek {gw:d}'))
def _backfill(ctx, year, gw):
    targets = bf.replay_targets(ctx['data']['rows'], year, gw, lambda y, g: True)
    ctx['written'] = bf.backfill(object(), ctx['data'], targets, ctx['done'], datetime(2026, 10, 9))


@then(parsers.parse('gameweek {gw:d} was forecast by a model trained on gameweeks 1 to {last:d}'))
def _trained(ctx, gw, last):
    assert list(range(1, last + 1)) in ctx['trained_on']


@then(parsers.parse('the log holds {year:d} forecasts for gameweeks 6, 7 and 8 marked as backfill'))
def _logged(ctx, year):
    assert [(y, g, s) for y, g, s, _ in ctx['logged']] == [(year, 6, 'backfill'), (year, 7, 'backfill'),
                                                           (year, 8, 'backfill')]


@then('an accuracy row marked as backfill exists for each of those gameweeks')
def _accuracy(ctx):
    assert [g for _, g, s in ctx['accuracy'] if s == 'backfill'] == [6, 7, 8]


@then(parsers.parse('only gameweek {gw:d} is written'))
def _only(ctx, gw):
    assert ctx['written'] == 1
    assert [g for _, g, _, _ in ctx['logged']] == [gw]
```

Note: `expectedPointsBackfill` must call `walk_forward` through the `expectedPointsBacktest` module (which looks up `train`/`predict` as its own module globals), so the monkeypatches on `bt.train` / `bt.predict` take effect. `bf.log_forecasts` and `bf.persist_accuracy` are patched on the backfill module, so import them there by name and call them by that name.

- [ ] **Step 3: Unit tests** — `tests/test_expected_points_backfill.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import expectedPointsBackfill as bf
from FPL_site import expectedPointsBacktest as bt


def test_targets_start_at_the_chosen_gameweek_and_skip_unsettled_ones():
    rows = [{'year_start': y, 'gameweek': g} for y in (2024, 2025) for g in (1, 5, 6, 38)]
    settled = lambda y, g: not (y == 2025 and g == 38)
    assert bf.replay_targets(rows, 2024, 6, settled) == [(2024, 6), (2024, 38), (2025, 1), (2025, 5), (2025, 6)]


def test_walk_forward_can_keep_players_without_an_official_number(monkeypatch):
    monkeypatch.setattr(bt, 'train', lambda rows: {})
    monkeypatch.setattr(bt, 'predict', lambda models, rows: [1.0] * len(rows))
    rows = [{'year_start': 2025, 'gameweek': g, 'player_id': 1, 'code': 9, 'position': 3, 'target': 2}
            for g in (1, 2)]
    kept = bt.walk_forward(rows, {}, [(2025, 2)], require_official=False)
    assert kept == [{'year_start': 2025, 'gameweek': 2, 'player_id': 1, 'code': 9, 'position': 3,
                     'ours': 1.0, 'official': None, 'actual': 2}]
    assert bt.walk_forward(rows, {}, [(2025, 2)]) == []


class Missing:
    def execute(self, sql, params=None):
        raise RuntimeError("Table 'expected_points_log' doesn't exist")


def test_nothing_backfilled_yet_when_the_log_table_is_missing():
    assert bf.fetch_backfilled(Missing()) == set()
```

- [ ] **Step 4: Run to see them fail.** `vs-env/Scripts/python.exe -m pytest -q tests/step_defs/test_expected_points_backfill_steps.py tests/test_expected_points_backfill.py` — expected: FAIL (`ModuleNotFoundError: ... expectedPointsBackfill`).

- [ ] **Step 5: Implement.** In `expectedPointsBacktest.py`: add `require_official=True` to `walk_forward` (filter on the official number only when it is true; each output row gets `'code': r['code']` and `'official': official.get((year, gw, r['player_id']))`), and move the data loading out of `main()` into:

```python
def load_replay_data(conn, cursor, years):
    """Everything a replay needs, as it would have been known before each gameweek."""
    history = fetch_history_rows(cursor, years)
    snapshots = fetch_snapshot_rows(cursor, years)
    fill_missing(conn, cursor, sorted({(h['year_start'], h['gameweek']) for h in history}))
    rows = training_rows(history, snapshots, load_fixture_xg(cursor))
    ids = {(s['code'], s['year_start']): s['player_id'] for s in snapshots}
    for r in rows:
        r['player_id'] = ids.get((r['code'], r['year_start']))
    rows = [r for r in rows if r['player_id'] is not None]
    official = {(s['year_start'], s['gameweek'] + 1, s['player_id']): s['ep_next']
                for s in snapshots if s['ep_next'] is not None}
    by_snapshot = {}
    for s in snapshots:
        by_snapshot.setdefault((s['year_start'], s['gameweek']), []).append(
            {'player_id': s['player_id'], 'position': s['element_type'], 'selected': s['selected']})
    squads = {(y, gw + 1): template_squad(group) for (y, gw), group in by_snapshot.items()}
    return {'rows': rows, 'official': official, 'squads': squads}
```
`main()` then calls `data = load_replay_data(conn, cursor, years)` and uses `data['rows']`, `data['official']`, `data['squads']`.

Create `FPL_site/expectedPointsBackfill.py`:

```python
"""Replay past gameweeks into the weekly record, with only the data available at the time.

Run by hand: python -m FPL_site.expectedPointsBackfill [--from-season 2024] [--from-gameweek 6]
Each gameweek is forecast by a model trained only on earlier gameweeks, from the snapshot taken
after the gameweek before and the match engine fitted as of then (expectedPointsBacktest.walk_forward).
Rows are stored with source 'backfill' so they never mix with the live, pre-deadline record.
Re-running adds nothing for gameweeks already backfilled by this model version.
"""
import argparse
import logging
from datetime import datetime

from FPL_site import expectedPointsBacktest
from FPL_site.dataModels import connect_db, current_season_start, refresh_season_start
from FPL_site.expectedPointsFeatures import MODEL_VERSION
from FPL_site.expectedPointsModel import fetch_events
from FPL_site.expectedPointsRecord import (BACKFILL, LOG_TABLE, accuracy_for_gameweek, forecast_of_record,
                                           is_settled, log_forecasts, persist_accuracy)

logger = logging.getLogger(__name__)

DEFAULT_FROM_GAMEWEEK = 6
SEASONS_BACK = 2


def replay_targets(rows, from_season, from_gameweek, settled):
    return sorted({(r['year_start'], r['gameweek']) for r in rows
                   if (r['year_start'], r['gameweek']) >= (from_season, from_gameweek)
                   and settled(r['year_start'], r['gameweek'])})


def fetch_backfilled(cursor):
    try:
        cursor.execute(f"SELECT DISTINCT year_start, gameweek FROM {LOG_TABLE} "
                       f"WHERE source = %s AND model_version = %s", (BACKFILL, MODEL_VERSION))
        return {(r['year_start'], r['gameweek']) for r in cursor.fetchall()}
    except Exception:
        return set()   # the log table is created on the first write


def backfill(conn, data, targets, done, now):
    written = 0
    for year, gw in targets:
        if (year, gw) in done:
            continue
        results = expectedPointsBacktest.walk_forward(data['rows'], data['official'], [(year, gw)],
                                                      require_official=False)
        if not results:
            continue
        forecasts = [{'player_id': r['player_id'], 'code': r['code'], 'expected_points': r['ours'],
                      'official_expected_points': r['official']} for r in results]
        log_forecasts(conn, forecasts, year, gw, None, now, source=BACKFILL)
        record = forecast_of_record([dict(f, logged_at=now) for f in forecasts], None, source=BACKFILL)
        position = {r['player_id']: r['position'] for r in results}
        for pid, row in record.items():
            row['position'] = position.get(pid)
        actual = {r['player_id']: r['actual'] for r in results}
        result = accuracy_for_gameweek(record, actual, data['squads'].get((year, gw), []), set(actual))
        persist_accuracy(conn, gw, year, result, now, source=BACKFILL)
        written += 1
        logger.info("Backfilled %s gameweek %s: ours %s, official %s.",
                    year, gw, result['mae_ours'], result['mae_official'])
    return written


def main(argv=None):
    logging.basicConfig(level=logging.INFO)
    refresh_season_start()
    year = current_season_start()
    parser = argparse.ArgumentParser(description='Replay past gameweeks into the expected points record.')
    parser.add_argument('--from-season', type=int, default=year - SEASONS_BACK)
    parser.add_argument('--from-gameweek', type=int, default=DEFAULT_FROM_GAMEWEEK)
    args = parser.parse_args(argv)
    events = fetch_events()

    def settled(y, gw):
        if y < year:
            return True
        return events is not None and is_settled(events, gw)

    conn = connect_db()
    try:
        cursor = conn.cursor(dictionary=True)
        data = expectedPointsBacktest.load_replay_data(
            conn, cursor, [year - i for i in range(SEASONS_BACK, -1, -1)])
        targets = replay_targets(data['rows'], args.from_season, args.from_gameweek, settled)
        written = backfill(conn, data, targets, fetch_backfilled(cursor), datetime.utcnow())
    finally:
        conn.close()
    print(f'Backfilled {written} gameweeks with model {MODEL_VERSION}.')


if __name__ == '__main__':
    main()
```

- [ ] **Step 6: Run to see them pass, then the whole suite.** `vs-env/Scripts/python.exe -m pytest -q` — expected: all PASS (the Task 6 backtest tests still pass: `walk_forward`'s default keeps its old filtering; output rows only gain keys).

- [ ] **Step 7: Commit**

```bash
git checkout -- FPL_site/__pycache__ 2>/dev/null; git add FPL_site/expectedPointsBacktest.py FPL_site/expectedPointsBackfill.py features/expected_points/backfill.feature tests/step_defs/test_expected_points_backfill_steps.py tests/test_expected_points_backfill.py && git commit -m "Replay past seasons into the record with only the data available at the time

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 8 (controller): run it for real** after the backtest: `vs-env/Scripts/python.exe -m FPL_site.expectedPointsBackfill` (writes `expected_points_log` and `expected_points_accuracy` rows with `source = 'backfill'`; reads the official events API once).
