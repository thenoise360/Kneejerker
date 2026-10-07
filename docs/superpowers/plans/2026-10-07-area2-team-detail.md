# Area 2: Team page detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Team page (`/club/<team_id>`) two honest, plain-English layers:

- **Strength:** how strong the team is *this week*, after adjusting for who is missing.
- **Prediction record:** how our pre-kickoff predictions compared with what actually happened.

**Architecture:** This follows the engine's existing daily-job / live-route split.

- **Daily job:** `run_daily_match_predictions()` (`FPL_site/matchPredictionEngine.py`) now also:
  1. appends every pre-kickoff prediction to an append-only log table, and
  2. computes absence-adjusted team strength and stores it in its own table.
- **Pure logic:** new modules hold all the calculations, tested with plain dicts:
  - `FPL_site/teamStrength.py` and `FPL_site/strengthCopy.py` (strength)
  - `FPL_site/predictionRecord.py` and `FPL_site/recordCopy.py` (record)
- **Routes:** thin `/api/club/<id>/strength` and `/api/club/<id>/prediction-record` routes read the stored results.
- **Page:** `club.html` and `club.js` render two new cards behind `FEATURE_TEAM_DETAIL`, using pure view modules in `static/scripts/lib/`.

**Tech Stack:**
- Python 3.11, Flask, mysql.connector, numpy
- pytest and pytest-bdd
- vanilla ES modules tested with `node --test`

**Spec:**
- `~/.claude/plans/virtual-dancing-reddy.md`, the "Area 2" section
- `docs/superpowers/plans/2026-10-06-kneejerker-roadmap.md`, covering the release gate and the default of no backfill

## Global Constraints

Everything in `docs/superpowers/plans/2026-10-06-area1-week-page.md` → Global Constraints applies unchanged. That covers:

- copy rules
- `<details>`/"See the numbers"
- `class="recap-verdict"` on card `<h3>` verdicts (the global `.card h3` style is 12px teal and fails contrast)
- the `KJ_SKIP_DB_INIT` test header
- no database or network in tests
- the commit trailer
- restoring `__pycache__`

Plus the following.

**Model rules:**
- **Never use the Influence, Creativity and Threat index.** Weight a missing player by:
  - their share of the team's expected goals plus expected assists, for attacking strength;
  - their share of the team's goalkeeper-and-defender minutes, for defensive strength.
- **No model fitting in a request path.** Routes only read stored rows.
- **Never compute "past predictions" by re-running the current model on finished games.** The record starts when logging starts, and the page says so (roadmap default: no backfill).
- **Below 8 logged games,** label the record "Early days — this gets more reliable as the season goes on."

**Product rules:**
- **No acronyms in copy.** Three-letter team codes count as acronyms, so use the team `name`, never `short_name`.
- **Players who have left the club** (`status == 'u'`) are neither "missing" nor counted in team shares.

**Code organisation:**
- The engine module keeps its existing style. New logic goes in new modules, so `matchPredictionEngine.py` only gains small, wired-in calls.

## Review Focus

1. **A team with no expected goals data yet** (team total of 0) must not divide by zero. It returns a 0 share. *Task 3:* `test_shares_with_zero_team_totals`.
2. **A missing share near 100%** must not produce `log(0)`. The share is capped. *Task 3:* `test_adjust_caps_extreme_share`.
3. **A team whose only logged games are still unfinished** shows the "no games yet" message, not an empty card. *Task 6:* `test_record_with_no_finished_games`.
4. **The daily job running twice in one day** must not duplicate log rows. *Task 1:* `test_log_rows_are_idempotent_per_day`.
5. **Unknown team id or no stored row yet:** the routes return 404 for unknown teams and a calm "not ready" payload for missing rows, never a 500. *Tasks 4 and 7.*

---

# Release 2.0: Start keeping score (backend only, no visible change)

### Task 1: Append-only prediction log

**Files:**
- Modify: `FPL_site/matchPredictionEngine.py`
  - `fetch_upcoming_fixtures`: add `kickoff_time` to the SELECT.
  - `build_fixture_predictions`: carry `kickoff_time` into each row.
  - Add `MODEL_VERSION`, `LOG_TABLE`, `loggable_rows()` and `log_predictions()`.
  - Call `log_predictions` from `run_daily_match_predictions`.
- Test: `tests/test_prediction_log.py`

**Interfaces:**
- Produces:
  - `MODEL_VERSION = 'dixon-coles-2026-10'`
  - `LOG_TABLE = 'fixture_prediction_log'`, with columns `fixture_code, team_id, opponent_id, gameweek, is_home, kickoff_time (VARCHAR(20)), expected_goals_mean, expected_goals_low, expected_goals_high, model_version, logged_at (DATETIME), log_date (DATE)`, and primary key `(fixture_code, team_id, model_version, log_date)`
  - `loggable_rows(rows, now) -> list[row]`: only rows whose kickoff is strictly after `now`
  - `log_predictions(conn, rows, now)`: `INSERT IGNORE`, so it is idempotent per fixture, team, version and day

- [ ] **Step 1: Write the failing tests.** `tests/test_prediction_log.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime

from FPL_site.matchPredictionEngine import loggable_rows, log_predictions, MODEL_VERSION, LOG_TABLE


def row(fixture_code, team_id, kickoff):
    return {'fixture_code': fixture_code, 'team_id': team_id, 'opponent_id': 99, 'gameweek': 6,
            'is_home': 1, 'kickoff_time': kickoff, 'expected_goals_mean': 1.4,
            'expected_goals_low': 0.8, 'expected_goals_high': 2.0}


NOW = datetime(2026, 10, 10, 12, 0)


def test_only_future_kickoffs_are_logged():
    rows = [row(1, 1, '2026-10-10T11:30:00Z'), row(2, 1, '2026-10-10T12:00:00Z'),
            row(3, 1, '2026-10-10T14:00:00Z'), row(4, 1, None), row(5, 1, 'garbage')]
    assert [r['fixture_code'] for r in loggable_rows(rows, NOW)] == [3]


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, params):
        self.calls.append((sql, list(params)))


class FakeConn:
    def __init__(self):
        self.cur = FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True


def test_log_rows_are_idempotent_per_day():
    conn = FakeConn()
    log_predictions(conn, [row(3, 1, '2026-10-10T14:00:00Z')], NOW)
    create_sql = conn.cur.calls[0][0]
    insert_sql, records = conn.cur.calls[1]
    assert f'CREATE TABLE IF NOT EXISTS {LOG_TABLE}' in create_sql
    assert 'PRIMARY KEY (fixture_code, team_id, model_version, log_date)' in create_sql
    assert insert_sql.strip().startswith(f'INSERT IGNORE INTO {LOG_TABLE}')
    assert records[0][-3:] == (MODEL_VERSION, NOW, NOW.date())
    assert conn.committed


def test_nothing_to_log_writes_nothing():
    conn = FakeConn()
    log_predictions(conn, [row(1, 1, '2026-10-10T11:30:00Z')], NOW)
    assert conn.cur.calls == [] and not conn.committed
```
Run `vs-env/Scripts/python.exe -m pytest tests/test_prediction_log.py -q`. Expected: ImportError.

- [ ] **Step 2: Implement.** In `matchPredictionEngine.py`:
  - Add the constants under `PREDICTIONS_TABLE`:
```python
LOG_TABLE = 'fixture_prediction_log'
# Bump whenever the model changes, so the record can tell versions apart.
MODEL_VERSION = 'dixon-coles-2026-10'
KICKOFF_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
```
  - Add `kickoff_time` to `fetch_upcoming_fixtures`'s SELECT list.
  - In `build_fixture_predictions`, add `'kickoff_time': fx['kickoff_time']` to BOTH appended row dicts.
  - Add, after `persist_match_predictions`:
```python
def _kickoff(row):
    try:
        return datetime.strptime(row.get('kickoff_time') or '', KICKOFF_FORMAT)
    except ValueError:
        return None


def loggable_rows(rows, now):
    """Only predictions made strictly before kickoff count toward the honest record."""
    return [r for r in rows if _kickoff(r) is not None and _kickoff(r) > now]


def log_predictions(conn, rows, now):
    """Append today's pre-kickoff predictions. Re-running the same day changes nothing."""
    to_log = loggable_rows(rows, now)
    if not to_log:
        return
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {LOG_TABLE} (
            fixture_code INT NOT NULL,
            team_id INT NOT NULL,
            opponent_id INT NOT NULL,
            gameweek INT NOT NULL,
            is_home TINYINT NOT NULL,
            kickoff_time VARCHAR(20) NOT NULL,
            expected_goals_mean FLOAT,
            expected_goals_low FLOAT,
            expected_goals_high FLOAT,
            model_version VARCHAR(40) NOT NULL,
            logged_at DATETIME NOT NULL,
            log_date DATE NOT NULL,
            PRIMARY KEY (fixture_code, team_id, model_version, log_date)
        )
    """)
    cursor.executemany(f"""
        INSERT IGNORE INTO {LOG_TABLE}
            (fixture_code, team_id, opponent_id, gameweek, is_home, kickoff_time,
             expected_goals_mean, expected_goals_low, expected_goals_high,
             model_version, logged_at, log_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [(r['fixture_code'], r['team_id'], r['opponent_id'], r['gameweek'], r['is_home'],
           r['kickoff_time'], r['expected_goals_mean'], r['expected_goals_low'],
           r['expected_goals_high'], MODEL_VERSION, now, now.date()) for r in to_log])
    conn.commit()
    logger.info(f"Logged {len(to_log)} pre-kickoff predictions ({MODEL_VERSION}).")
```
  - In `run_daily_match_predictions`, after `persist_match_predictions(conn, rows)`, add:
```python
        # Keep an honest, append-only record of what we predicted before kickoff.
        log_predictions(conn, rows, datetime.utcnow())
```

- [ ] **Step 3:** Run `vs-env/Scripts/python.exe -m pytest -q`; it should be green. Run `python -m py_compile FPL_site/matchPredictionEngine.py`. Commit:
`git commit -am "Log every pre-kickoff match prediction to an append-only table"`

**Release 2.0 gate:**
- Run the full suites.
- **Never run `run_update.py` or the daily job from a test or controller check.** It writes to production tables.
- Ship to main. Logging starts on the next scheduled daily run.

---

# Release 2.1: "How strong are they this week?"

### Task 2: Strength phrase bank

**Files:**
- Create: `FPL_site/strengthCopy.py`
- Create: `tests/test_strength_copy.py`
- Create: `features/team/strength.feature`
- Create: `tests/step_defs/test_strength.py`

**Interfaces:**
- Produces: `strength_summary(team_name, strength) -> {'headline': str, 'reason': str}`. Here `strength` is a dict with these keys:
  - `scored`, `scored_adjusted`, `conceded`, `conceded_adjusted`: goals a game against an average side, all floats
  - `league_scored`: the league-average goals a game, a float
  - `missing`: `[{'name', 'role': 'attack'|'defence', 'share': float, 'chance': int}]`
- Constants:
  - `NOTICEABLE_FROM = 0.15`
  - `SLIGHT_FROM = 0.05`
  - `KEY_PLAYER_SHARE = 0.10`
  - `STRONG_RATIO = 1.15`
  - `WEAK_RATIO = 0.87`
- Copy rules: no digits in `headline` or `reason`; a reason is always present.

- [ ] **Step 1: Scenarios** in `features/team/strength.feature`:
```gherkin
Feature: How strong a team is this week
  So a first-timer knows whether a team is weakened, the Team page gives one verdict and one reason.

  Scenario: Two main chance-creators are out
    Given a team that scores 1.9 a game and 1.5 with absences
    And "Saka" and "Odegaard" are missing chance-creators
    When the strength summary is written for "Arsenal"
    Then the headline is "Arsenal's attack is weaker this week"
    And the reason is "Two of their main chance-creators are out."

  Scenario: Nobody important is missing
    Given a team that scores 1.9 a game and 1.9 with absences
    When the strength summary is written for "Arsenal"
    Then the headline is "Arsenal are at full strength"
    And the reason is "Strong going forward, solid at the back."

  Scenario: A returning user checks a weakened defence
    Given a team that concedes 1.0 a game and 1.25 with absences
    And "Saliba" is a missing defender
    When the strength summary is written for "Arsenal"
    Then the headline is "Arsenal's defence is weaker this week"
    And the reason is "One of their regular defenders is out."
```
Step definitions in `tests/step_defs/test_strength.py`:
- Build `strength` with defaults: `scored` 1.9, `scored_adjusted` 1.9, `conceded` 1.0, `conceded_adjusted` 1.0, `league_scored` 1.4, `missing` [].
- Each missing player gets `share` 0.2 and `chance` 0, with role `attack` for chance-creators and `defence` for defenders.
- Use a `ctx` dict fixture from a Background-free first Given, with `target_fixture='ctx'`. The later Givens mutate `ctx`.

- [ ] **Step 2: Unit tests** in `tests/test_strength_copy.py`:
  - **Attack tier boundaries,** with `scored` 2.0: `scored_adjusted` 1.80 (10% drop) is the slight tier, so the headline is "...attack is a little weaker this week". 1.71 is a 14.5% drop and still slight. 1.70 is a 15% drop and noticeable, so the headline is "...attack is weaker this week". 1.91 is a 4.5% drop, so full strength.
  - **Defence tier,** symmetric on the rise in conceded.
  - **When both are hit,** the larger effect wins the headline.
  - **Reasons by count of key missing players** (share at least 0.10, with role matching the headline): 1 is "One of their main chance-creators is out.", 2 is "Two of their main chance-creators are out.", 3 or more is "Several of their main chance-creators are out." If none are key, the reason is "A few squad players are missing." For the defence role, use "regular defenders" and singular "is out". A missing goalkeeper (name with `'role': 'defence', 'position': 1`) gives "Their first-choice goalkeeper is out."
  - **Full-strength reasons** come from the ratio to `league_scored`:
    - attack: at least 1.15 is "Strong going forward", at most 0.87 is "Short of goals", otherwise "Steady going forward"
    - defence: `conceded` against `league_scored`, inverted. At most 0.87 is "solid at the back", at least 1.15 is "leaky at the back", otherwise "steady at the back"
    - join them as "<attack>, <defence>."
  - Test both sides of 1.15 and 0.87.
  - **No digit and no acronym** in any output, checked with a regex test over every tier.

  Run them; expect an ImportError.

- [ ] **Step 3: Implement** `FPL_site/strengthCopy.py`. Use small pure functions, one per job: `_drop(raw, adjusted)`, `_rise(raw, adjusted)`, `_tier(change)`, `_key_missing(missing, role)`, `_missing_reason(key, role)`, `_baseline_reason(strength)` and `strength_summary`. Headlines:
  - noticeable attack: `"{team}'s attack is weaker this week"`
  - slight attack: `"{team}'s attack is a little weaker this week"`
  - defence: the same pattern with "defence"
  - full strength: `"{team} are at full strength"`

  Number words for counts come from a local `{1: 'One', 2: 'Two'}` map; three or more is "Several".

- [ ] **Step 4:** Run `vs-env/Scripts/python.exe -m pytest -q`; it should be green. Commit:
`git commit -m "Add team strength phrase bank"` (add the new files explicitly).

### Task 3: Absence-adjusted strength calculation

**Files:**
- Create: `FPL_site/teamStrength.py`, which is pure apart from one fetcher
- Create: `tests/test_team_strength.py`

**Interfaces:**
- Consumes: from the engine, `ratings` `{code: {'attack', 'defence'}}`, `home_adv`, and team rows `{id: {'id', 'code', 'name'}}`.
- Produces:
  - `REPLACEMENT_COVER = 0.5` (a missing player's output is half replaced), `MAX_SHARE = 0.8`, `GOALKEEPER = 1`, `DEFENDER = 2`
  - `fetch_squad_rows(cursor, year_start) -> list[dict]`, from the latest `bootstrapstatic_elements` snapshot: `id, web_name, team, element_type, expected_goals, expected_assists, minutes, chance_of_playing_next_round, status`
  - `missing_fraction(chance) -> float`: None gives 0.0; otherwise `1 - chance/100`, clamped to the range 0–1
  - `team_absences(players) -> {'attack_share', 'defence_share', 'missing': [...]}`
  - `adjust(attack, defence, attack_share, defence_share) -> (attack_adj, defence_adj)`, where `attack_adj = attack + ln(1 - REPLACEMENT_COVER * min(share, MAX_SHARE))` and `defence_adj = defence - ln(1 - REPLACEMENT_COVER * min(dshare, MAX_SHARE))`. In this model a higher `defence` means more goals conceded: `lam = exp(attack_own + defence_opp + home)`.
  - `goals_vs_average(attack, defence, league_mean_attack, league_mean_defence, home_adv) -> (scored, conceded)`, where `scored = exp(attack + mean_defence + home_adv/2)` and `conceded = exp(mean_attack + defence + home_adv/2)`
  - `build_team_strengths(teams, ratings, home_adv, squad_rows) -> {team_id: strength}`, using the `strength` dict shape from Task 2 plus `team_id` and `name`

- [ ] **Step 1: Failing tests** in `tests/test_team_strength.py`:
  - `missing_fraction(None) == 0`, `(100) == 0`, `(25) == 0.75`, `(0) == 1`
  - `test_shares_with_zero_team_totals`: a team whose players all have 0 expected goals and assists gets an attack share of 0, with no ZeroDivisionError
  - A player with status `'u'` is excluded from both the totals and `missing`
  - The attack share of a missing player with 40% of the team's expected goals plus assists and chance 0 is 0.4. With chance 50 it is 0.2.
  - The defence share uses only goalkeeper and defender minutes. A missing midfielder adds 0 to the defence share.
  - `adjust(0.2, -0.1, 0.4, 0.0)` gives an attack of `0.2 + ln(0.8)` with the defence unchanged. `adjust(0, 0, 0, 0.4)` gives a defence of `-ln(0.8)`, which is higher, meaning it concedes more.
  - `test_adjust_caps_extreme_share`: a share of 5.0 is capped to 0.8, giving `ln(0.6)`
  - `build_team_strengths` with two teams: `league_scored` equals the mean of the teams' `scored`; `missing` is sorted by share, descending; `role` is 'attack' when a player's attack share is at least their defence share, otherwise 'defence'; `position` is carried through
  - The fetcher passes `(year_start, year_start)` to a FakeCursor

  Run them; expect an ImportError.

- [ ] **Step 2: Implement** `teamStrength.py` with those functions. Each missing entry is:
  `{'name': web_name, 'position': element_type, 'role', 'share': max(attack_share_i, defence_share_i), 'chance': chance or 0}`.
  Expected goals and assists come back from MySQL as strings or floats, so convert with `float(x or 0)`.

- [ ] **Step 3:** Run the suite; it should be green. Then do a read-only check against the real database:
`KJ_SKIP_DB_INIT=1 vs-env/Scripts/python.exe -c "from FPL_site.dataModels import connect_db, season_start; from FPL_site.teamStrength import fetch_squad_rows; c=connect_db(); cur=c.cursor(dictionary=True); r=fetch_squad_rows(cur, season_start); print(len(r), r[0])"`
Commit: `git commit -m "Calculate absence-adjusted team strength"`

### Task 4: Persist strength daily, route, and Team page card

**Files:**
- Modify: `FPL_site/teamStrength.py` (add `persist_team_strengths`, `load_team_strength`)
- Modify: `FPL_site/matchPredictionEngine.py` (call it from `run_daily_match_predictions`)
- Modify: `FPL_site/views.py` (the `club()` render passes `team_detail`; add the route `/api/club/<int:team_id>/strength`)
- Modify: `FPL_site/config.py` (`FEATURE_TEAM_DETAIL` in both configs, mirroring `FEATURE_WEEK_V2`)
- Modify: `FPL_site/templates/club.html` (a strength card slot, behind `{% if team_detail %}`)
- Create: `FPL_site/static/scripts/lib/strengthView.js`
- Modify: `FPL_site/static/scripts/club.js` (if `#team-strength-slot` exists, fetch and render)
- Modify: `FPL_site/static/content/home.css` (only if a new class is needed)
- Test: `tests/test_team_strength.py`, `tests/test_club_routes.py`, `tests/js/strengthView.test.js`, `tests/test_regression_routes.py`

**Interfaces:**
- `STRENGTH_TABLE = 'team_strength'`, with columns `team_id INT PRIMARY KEY, name VARCHAR(60), scored FLOAT, scored_adjusted FLOAT, conceded FLOAT, conceded_adjusted FLOAT, league_scored FLOAT, missing_json TEXT, computed_at DATETIME`. It is replaced in full each daily run: `DELETE` then `INSERT`, in one commit.
- `load_team_strength(team_id) -> payload | None`. It returns None when the team is unknown, which the route turns into a 404. Otherwise it returns one of:
  - `{'status': 'ready', 'team_name', 'headline', 'reason', 'scored', 'scored_adjusted', 'conceded', 'conceded_adjusted', 'missing': [...]}`, with numbers rounded to 1 decimal place
  - `{'status': 'not_ready', 'message': {'title': 'Team strength is on its way', 'body': "We're still working this out. Check back a little later."}}` when the team exists but has no stored row yet. To tell the two cases apart, use `matchPredictionEngine.fetch_teams_for_season`.
- `GET /api/club/<id>/strength` returns:
  - 200 with the payload
  - 404 with `{'error': 'unknown_team'}`
  - 500 with `{'error': 'server_error'}`
- `renderStrength(payload) -> string`:
  - shows `headline` as `<h3 class="recap-verdict">` and `reason` as `<p>`
  - inside `<details class="recap-details"><summary>See the numbers</summary>`: "Goals a game against an average side: X (Y with this week's absences)", "Goals conceded a game against an average side: X (Y with this week's absences)", then one `<li>` per missing player: "<name>: <chance>% chance of playing"
  - every value goes through `escapeHtml`
  - a `not_ready` payload renders through `renderMessage`

- [ ] **Step 1: Failing tests**
  - Persist test with a FakeConn: the CREATE, the DELETE and an `executemany` with one tuple per team, then commit.
  - `load_team_strength` with a monkeypatched `connect_db` and a cursor returning canned rows, covering three cases: ready, not_ready, and an unknown team returning None.
  - Route tests: 200 ready, 404 unknown, 500 on an exception.
  - `test_regression_routes.py`: add `'/api/club/1/strength': ('load_team_strength', {'status': 'not_ready', 'message': {'title': 't', 'body': 'b'}})` to `DATA_ROUTE_STUBS`, and add `FEATURE_TEAM_DETAIL` on/off coverage for `/club/1`.
  - Node tests for `renderStrength`: no digit before `<details`; the numbers appear inside it; escaping; the not_ready message; `class="recap-verdict"`.
- [ ] **Step 2: Implement.**
  - In `run_daily_match_predictions`, after logging:
```python
        teams = fetch_teams_for_season(cursor, season_start)
        strengths = build_team_strengths(teams, ratings, home_adv, fetch_squad_rows(cursor, season_start))
        persist_team_strengths(conn, strengths)
```
    Import these at the top from `FPL_site.teamStrength`.
  - `teamStrength` must not import `matchPredictionEngine` at module level, to avoid a circular import. `load_team_strength` imports `fetch_teams_for_season` inside the function.
  - `club.html`: inside the content block and above `#club-fixture-list`, add:
    `{% if team_detail %}<div id="team-strength-slot"><div class="card" aria-busy="true"><div class="skeleton" style="height:18px;width:60%;"></div></div></div>{% endif %}`
  - `club.js`: after fetching the outlook, `if (document.getElementById('team-strength-slot')) loadStrength(teamId)`. Catch failures with a calm message.
- [ ] **Step 3:** Run the full suites, `py_compile` and `node --check`, then commit.

**Release 2.1 gate:**
- Run the roadmap gate.
- The live smoke can't populate `team_strength` without the daily job, and the controller must not run that. So do a one-off read-only compute instead:
  `vs-env/Scripts/python.exe -c "...fit_current_ratings + build_team_strengths, print a few teams..."`
  Check the numbers are plausible and the copy reads well for real teams. Do not persist.
- Browser check at 375px with the flag on, using a monkeypatched or stubbed route or the not_ready state.

---

# Release 2.2: "Do they beat their chances?"

### Task 5: Record verdict phrase bank

**Files:**
- Create: `FPL_site/recordCopy.py`
- Create: `tests/test_record_copy.py`
- Create: `features/team/prediction_record.feature`
- Create: `tests/step_defs/test_prediction_record.py`

**Interfaces:**
- `EARLY_DAYS_BELOW = 8`, `TREND_FROM = 0.5` (average goal difference per game, actual minus predicted), `GAME_MARGIN = 1.0`
- `game_verdict(predicted_for, predicted_against, actual_for, actual_against) -> 'better'|'as_expected'|'worse'`: the difference is `(actual_for - actual_against) - (predicted_for - predicted_against)`. At least +1.0 is 'better', at most -1.0 is 'worse', anything else 'as_expected'.
- `record_summary(team_name, games, started_on) -> {'headline', 'reason', 'early_days': bool}`. Here `games` is a list of dicts with `predicted_for`, `predicted_against`, `actual_for` and `actual_against`; `started_on` is a `'YYYY-MM-DD'` string or None. The cases:
  - **No games:** headline "No finished games logged yet". Reason: "We started keeping score on <D Month YYYY>. Check back after their next game." If `started_on` is None, the reason is "We'll start keeping score from their next game." Set `early_days` to True.
  - **Average difference at least TREND_FROM:** headline "<team> have been beating their chances". Reason: "They've been winning by more than their chances suggest. That tends not to last."
  - **Average difference at most -TREND_FROM:** headline "<team> have been falling short of their chances". Reason: "They've been doing worse than their chances suggest. That tends to turn around."
  - **Otherwise:** headline "<team> are performing about as expected". Reason: "Their results have matched their chances so far."
  - **`early_days`** is `len(games) < EARLY_DAYS_BELOW`.
  - No digits are allowed in the headline or reason, except in the date sentence of the no-games case. A date is a label, not a statistic.

- [ ] **Step 1: Scenarios** in `features/team/prediction_record.feature`:
  - **Happy path:** eight games averaging +0.75 give the "beating their chances" headline with `early_days` false.
  - **Missing data:** zero games, `started_on` 2026-10-08, give the headline "No finished games logged yet" and the reason mentions "8 October 2026".
  - **Returning user:** three games give the "early days" flag as true, and the verdict still shows.

  Step definitions follow the house style.
- [ ] **Step 2: Unit tests.**
  - Both sides of TREND_FROM: +0.5 and +0.49; -0.5 and -0.49.
  - EARLY_DAYS_BELOW at 7 and 8 games.
  - `game_verdict` at +1.0 and +0.99, and at -1.0 and -0.99.
  - A no-digit check, excluding the date sentence.
  - An acronym regex.

  Expect an ImportError on the first run.
- [ ] **Step 3: Implement** with small pure functions. Format the date as `f"{d.day} {d.strftime('%B')} {d.year}"`. Run the suite, then commit.

### Task 6: Prediction record data and route

**Files:**
- Create: `FPL_site/predictionRecord.py` (a fetcher plus pure shaping and `load_prediction_record`)
- Modify: `FPL_site/views.py` (the `/api/club/<int:team_id>/prediction-record` route)
- Test: `tests/test_prediction_record.py`, `tests/test_club_routes.py`, `tests/test_regression_routes.py`

**Interfaces:**
- `fetch_record_rows(cursor, team_id, year_start)`: for each logged fixture of `team_id` whose fixture is finished, select the latest log row with `kickoff_time` greater than `logged_at` for this team AND the matching opponent row from the same `log_date` and `model_version`, plus the actual scores from `fixtures_fixtures`. SQL:
```sql
SELECT mine.gameweek, mine.is_home, mine.opponent_id, mine.kickoff_time,
       mine.expected_goals_mean AS predicted_for, theirs.expected_goals_mean AS predicted_against,
       f.team_h_score, f.team_a_score
FROM fixture_prediction_log mine
JOIN fixture_prediction_log theirs
  ON theirs.fixture_code = mine.fixture_code AND theirs.team_id = mine.opponent_id
 AND theirs.log_date = mine.log_date AND theirs.model_version = mine.model_version
JOIN fixtures_fixtures f ON f.code = mine.fixture_code AND f.year_start = %s
WHERE mine.team_id = %s AND f.finished = 1
  AND mine.logged_at = (SELECT MAX(l.logged_at) FROM fixture_prediction_log l
                        WHERE l.fixture_code = mine.fixture_code AND l.team_id = mine.team_id)
ORDER BY mine.gameweek
```
  Every logged row is pre-kickoff by construction (Task 1). `fixtures_fixtures` may hold duplicates (Area 1 finding), so the shaping step deduplicates on `(gameweek, kickoff_time)`.
- `fetch_logging_started(cursor) -> 'YYYY-MM-DD' | None`, from `SELECT MIN(log_date) FROM fixture_prediction_log`. If the table doesn't exist yet, mysql raises error 1146; catch it and return None.
- `shape_games(rows, teams) -> list[game]`, where game is `{'gameweek', 'opponent' (full name), 'is_home', 'predicted_for', 'predicted_against', 'actual_for', 'actual_against', 'verdict'}`. Actual for/against come from the home or away score, according to `is_home`.
- `load_prediction_record(team_id) -> payload | None`. It returns None for an unknown team, otherwise `{'status': 'ready', 'team_name', 'headline', 'reason', 'early_days', 'early_days_label': 'Early days — this gets more reliable as the season goes on.' | None, 'started_on', 'games': [...]}`. A missing table must also give a ready payload, with no games and `started_on` None.
- The route returns 200, 404 `unknown_team`, or 500.

- [ ] **Steps:**
  1. Write failing tests:
     - shaping: home and away mapping, duplicate rows, verdicts
     - `test_record_with_no_finished_games`
     - a missing-table fetcher path, with a FakeCursor raising `mysql.connector.errors.ProgrammingError(errno=1146)`
     - routes
     - a regression stub
  2. Implement.
  3. Do a read-only real-database check. The table may not exist yet; confirm the no-games payload comes back.
  4. Run the full suite, then commit.

### Task 7: Record card on the Team page, then remove `FEATURE_TEAM_DETAIL`

**Files:**
- Create: `FPL_site/static/scripts/lib/recordView.js` (`renderRecord(payload)`)
- Modify: `club.html` (`#prediction-record-slot` after the fixture list), `club.js` (load and render), `views.py`, `config.py`, and the tests

**Interfaces:**
- `renderRecord(payload)`:
  - headline as `<h3 class="recap-verdict">`, then the reason
  - if `early_days_label` is set, a `<p class="sub">` with it, prefixed with an "ⓘ" icon marked `aria-hidden` plus the text, so it never relies on colour
  - `<details>`/"See the numbers": one `<li>` per game reading `Gameweek N, <home to|away at> <Opponent>: we expected X–Y, it finished A–B (<Better than expected|As expected|Worse than expected>)`
  - when `started_on` is set, the footer line "We started keeping score on <date>."
- Pure and escaped, with node tests for:
  - no digit before `<details` except in the started-on footer
  - the early-days label
  - per-game wording
  - escaping

- [ ] **Steps:**
  1. Write failing node tests, then implement.
  2. Wire `club.js` and `club.html` behind the flag, then run the suites and commit.
  3. Remove the flag:
     - delete `FEATURE_TEAM_DETAIL` from `config.py`, and the `{% if team_detail %}` wrappers and the `team_detail` render argument
     - update the tests: remove flag-off cases, and make the regression test assert both slots render on `/club/1`
     - run `grep -rn "FEATURE_TEAM_DETAIL\|team_detail" FPL_site tests`; expect no matches
     - commit

**Release 2.2 gate:** run the roadmap gate. The live smoke covers:
- `/club/1` shows both cards
- the strength card renders `not_ready` until the daily job has run
- the record card shows "No finished games logged yet" with the logging start date, or the "next game" fallback

Then do the browser check at 375px and ship to main.
