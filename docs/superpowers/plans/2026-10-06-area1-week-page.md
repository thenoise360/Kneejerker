# Area 1: Week page (Releases 1.2–1.4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the Week tab so it always shows what matters now:
- a kind Last Week recap, first general and then personal
- a welcome-back message for returning users
- a This Week view with calm deadline wording and the single biggest decision with its reason

Once that is done, remove the `FEATURE_WEEK_V2` flag.

**Architecture:**
- **Python modules.** Each new Python module has two layers:
  - *Fetchers* take a database cursor and return raw rows.
  - *Pure functions* aggregate those rows and choose copy. They are tested with plain dicts.
- **Routes.** Routes in `views.py` stay thin and return JSON.
- **Browser code.** JavaScript is split the same way:
  - *Pure modules* in `static/scripts/lib/` build HTML strings and copy. They are tested with `node --test`.
  - `weekV2.js` holds the only DOM glue.
- **Server-side states.** The server renders the empty states, so the page never depends on JavaScript to avoid a blank screen.

**Tech Stack:**
- Python 3.11 with Flask, mysql.connector and Jinja2
- pytest 9 and pytest-bdd
- Vanilla ES modules, tested with Node 23 `node --test`

**Spec:**
- `~/.claude/plans/virtual-dancing-reddy.md`: the original brief and the Step 0 findings.
- `docs/superpowers/plans/2026-10-06-kneejerker-roadmap.md`: the releases, the release gate, and the defaults for the open questions.

## Global Constraints

- **Copy:**
  - No acronyms in user-facing copy. Never write FPL, GW, xG, xA, ICT, DGW or BGW; spell everything out, for example "gameweek" and "Fantasy Premier League".
  - Plain language by default, numbers on demand. The default view shows a verdict plus one reason. Numbers go inside a `<details>` element whose `<summary>` reads "See the numbers".
  - Every recommendation carries a reason, framed as a partnership ("here's what we're seeing — your call").
  - No shame and no dead ends. Copy comes from deterministic phrase banks, with no randomness and no language model calls. Every tier boundary is tested.
- **Visual:**
  - Reuse the `.card`, `.eyebrow-sm`, `.title`, `.sub`, `.btn-pill` and `.skeleton` classes, plus the CSS tokens `--plum`, `--teal`, `--pink`, `--charcoal` and `--grey` from `static/content/style.css`.
  - Keep the 12px card radius and 16px or more padding.
  - Mobile first, at 375–430px, with no horizontal scroll.
- **Accessibility:**
  - Never rely on colour alone.
  - Visible focus states: `summary:focus-visible` gets a 2px solid `var(--plum)` outline.
  - Motion is 150–250ms ease-in-out.
- **Python:**
  - Run Python with `vs-env/Scripts/python.exe` from the repo root.
  - Every test module starts with `import os; os.environ.setdefault('KJ_SKIP_DB_INIT', '1')` before any `FPL_site` import. `tests/conftest.py` already sets it too.
  - **Never** call the real Fantasy Premier League API or MySQL in tests. Monkeypatch the fetchers and routes instead.
- **Releases:**
  - The flag `FEATURE_WEEK_V2` hides all new user-facing work until Task 13.
  - The data routes are always registered.
- **Code style:**
  - Comment non-obvious JavaScript in plain English, for a learner.
  - Plain code over clever code, and one function per job.
- **Commits:**
  - Commit after every green step.
  - Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  - Do not push. The controller pushes once the release gate passes.
- **Generated files:** after running tests, restore any tracked `FPL_site/__pycache__/*.pyc` files with `git checkout -- FPL_site/__pycache__`. Never commit them.

## Review Focus

These are the conditions most likely to bite a real user, and the task whose tests pin each one:

1. **Double gameweek.** A player who plays twice in a gameweek must have their points summed, not listed twice or half-counted. *Task 2:* `test_aggregate_sums_double_gameweek`.
2. **Duplicate event rows.** `bootstrapstatic_events` holds duplicate rows per gameweek (49 rows for 38 gameweeks in 2026), so the average must not be taken from a zero-score duplicate. *Task 2:* `test_summarise_event_ignores_duplicate_zero_row`.
3. **Unsafe player names.** A name such as `O'Brien` or `<b>` is rendered inside HTML strings and must be escaped. *Task 4:* `escapes player names`.
4. **Bad or wrong team number.** The team number could be junk text, negative, or a team that didn't exist in that gameweek. Each case gets a friendly message, never an error. *Task 7:* `test_route_rejects_junk_team_id_gracefully` and `test_personal_recap_team_not_found`.
5. **Deadline passing while the page is open,** plus the user's timezone. The deadline is shown in the browser's local time, and "passed" gets its own calm tier. *Task 10:* `deadline already passed` and `formats in the given time zone`.

---

# Release 1.2: "See how last week went" (guest recap)

### Task 1: Regression suite, single gameweek fetch, test docs

**Files:**
- Create: `tests/test_regression_routes.py`
- Modify: `FPL_site/views.py` (the `home()` function)
- Modify: `CLAUDE.md` (the "Running the app" section)

**Interfaces:**
- Consumes: `views.get_week_view_state()`, `views.get_gameweek_state()` and `current_config.FEATURE_WEEK_V2`, all from Release 1.1.
- Produces:
  - `tests/test_regression_routes.py`, with `PAGE_ROUTES` and a `client` fixture that stubs every network or database call made by page routes.
  - Later tasks append their data routes to `DATA_ROUTE_STUBS`.

**Regression this fixes:** with the flag on, `/this-week` makes **two** calls to the Fantasy Premier League API per request: `get_gameweek_state()` and `get_week_view_state()`. On a cold-start dyno that doubles the page latency. With the flag on, only the new state should be fetched.

- [ ] **Step 1: Write the failing tests**

`tests/test_regression_routes.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import app
import FPL_site.views as views

PAGE_ROUTES = ['/this-week', '/radar', '/discovery', '/clubs', '/club/1', '/privacy']

WEEK_STATE = {
    'this_week': {'mode': 'upcoming', 'gameweek': 6, 'deadline': '2026-10-10T10:00:00Z'},
    'last_week': {'status': 'final', 'gameweek': 5, 'deadline': '2026-10-03T10:00:00Z'},
}

# path -> (name of the function in views to stub, the value the stub returns).
# Each release adds its new data routes here so they stay covered forever.
DATA_ROUTE_STUBS = {}


@pytest.fixture
def calls():
    return []


@pytest.fixture
def client(monkeypatch, calls):
    def fake_gameweek_state():
        calls.append('get_gameweek_state')
        return {'state': 'none', 'gameweek': None, 'deadline': None}

    def fake_week_view_state():
        calls.append('get_week_view_state')
        return WEEK_STATE

    monkeypatch.setattr(views, 'get_gameweek_state', fake_gameweek_state)
    monkeypatch.setattr(views, 'get_week_view_state', fake_week_view_state)
    for _, (name, value) in DATA_ROUTE_STUBS.items():
        monkeypatch.setattr(views, name, lambda *a, _v=value, **k: _v)
    return app.test_client()


def set_flag(monkeypatch, on):
    monkeypatch.setattr(views.current_config, 'FEATURE_WEEK_V2', on, raising=False)


@pytest.mark.parametrize('flag', [False, True])
@pytest.mark.parametrize('path', PAGE_ROUTES)
def test_page_routes_render(client, monkeypatch, flag, path):
    set_flag(monkeypatch, flag)
    assert client.get(path).status_code == 200


@pytest.mark.parametrize('flag', [False, True])
def test_data_routes_respond(client, monkeypatch, flag):
    set_flag(monkeypatch, flag)
    for path in DATA_ROUTE_STUBS:
        assert client.get(path).status_code == 200, path


def test_flag_off_week_page_keeps_existing_markers(client, monkeypatch):
    set_flag(monkeypatch, False)
    html = client.get('/this-week').get_data(as_text=True)
    for marker in ['id="gw-panel-live"', 'id="live-team-id-form"', 'Friend activity feed',
                   'Team of the Week', 'scripts/home.js', 'content/home.css']:
        assert marker in html, marker


def test_flag_on_week_page_fetches_state_once(client, monkeypatch, calls):
    set_flag(monkeypatch, True)
    client.get('/this-week')
    assert calls == ['get_week_view_state']


def test_flag_off_week_page_fetches_state_once(client, monkeypatch, calls):
    set_flag(monkeypatch, False)
    client.get('/this-week')
    assert calls == ['get_gameweek_state']
```

- [ ] **Step 2: Run to verify it fails**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_regression_routes.py -q`
Expected: `test_flag_on_week_page_fetches_state_once` FAILS, with calls showing both functions. Everything else passes.

- [ ] **Step 3: Minimal fix in `FPL_site/views.py` `home()`**

Replace the body after `is_ajax = ...` with:
```python
    week_v2 = getattr(current_config, 'FEATURE_WEEK_V2', False)
    # Only fetch the state the page will actually use: each call is a round
    # trip to the Fantasy Premier League API, which hurts on a cold start.
    if week_v2:
        gw_state = None
        week_context = _week_v2_context()
    else:
        gw_state = get_gameweek_state()
        week_context = {}
    return render_template('home.html', is_ajax=is_ajax, title='This Week', year=datetime.now().year, mixpanel_token=current_config.MIXPANEL_TOKEN, gw_state=gw_state, week_v2=week_v2, **week_context)
```
Keep the existing `# Computed server-side (06.0)...` comment above it.

- [ ] **Step 4: Run all tests**

Run: `vs-env/Scripts/python.exe -m pytest -q`
Expected: all pass. If a 1.1 test passed `gw_state` into the flag-on template, it still passes, because the partial never reads `gw_state`.

- [ ] **Step 5: Document testing in `CLAUDE.md`**

In the "Running the app" section, replace the sentence `No test suite, linter, or build step exists in this repo (\`npm test\` is an unconfigured stub).` with:
```markdown
There is no linter or build step. Tests: `vs-env/Scripts/python.exe -m pytest -q` (pytest + pytest-bdd;
Gherkin scenarios live in `features/`, step definitions in `tests/step_defs/`) and `npm test` (Node's
built-in runner over pure modules in `FPL_site/static/scripts/lib/`). Tests set `KJ_SKIP_DB_INIT=1` and
must never touch MySQL or the live FPL API — monkeypatch fetchers instead. `tests/test_regression_routes.py`
is the regression gate: add every new route to it.
```

- [ ] **Step 6: Commit**
```bash
git add tests/test_regression_routes.py FPL_site/views.py CLAUDE.md
git commit -m "Add route regression suite and fetch Week state once per request"
```

---

### Task 2: Recap data fetch and pure aggregation

**Files:**
- Create: `FPL_site/lastWeekRecap.py`
- Test: `tests/test_last_week_recap_data.py`

**Interfaces:**
- Consumes: `FPL_site.dataModels.connect_db` and `season_start`.
- Produces:
  - `fetch_event_rows(cursor, year_start, gameweek) -> list[dict]`
  - `fetch_history_rows(cursor, year_start, gameweek) -> list[dict]`, where each row has the keys `element`, `total_points`, `minutes`, `goals_scored`, `assists`, `clean_sheets`, `saves`, `bonus`, `penalties_saved`, `web_name`, `element_type`, `team_short_name` and `difficulty`.
  - `summarise_event(rows) -> {'average_score': int, 'highest_score': int|None} | None`
  - `aggregate_player_rows(rows) -> dict[int, Player]`, where Player is `{'id', 'name', 'team', 'position', 'points', 'minutes', 'goals', 'assists', 'clean_sheets', 'saves', 'bonus', 'penalties_saved', 'difficulty'}`. Position is 1=goalkeeper, 2=defender, 3=midfielder, 4=forward. Difficulty is an int or None, and is the easiest of the player's fixtures.
  - `top_performers(players, limit=3) -> list[Player]`

- [ ] **Step 1: Write the failing tests**

`tests/test_last_week_recap_data.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.lastWeekRecap import (
    summarise_event, aggregate_player_rows, top_performers, fetch_event_rows, fetch_history_rows,
)


def row(element, points, name='Player', minutes=90, difficulty=3, **stats):
    base = {'element': element, 'total_points': points, 'minutes': minutes, 'goals_scored': 0,
            'assists': 0, 'clean_sheets': 0, 'saves': 0, 'bonus': 0, 'penalties_saved': 0,
            'web_name': name, 'element_type': 3, 'team_short_name': 'ARS', 'difficulty': difficulty}
    base.update(stats)
    return base


class FakeCursor:
    def __init__(self, rows):
        self.rows, self.executed = rows, []

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


def test_summarise_event_happy_path():
    rows = [{'average_entry_score': 48, 'highest_score': 126, 'finished': 1, 'data_checked': 1}]
    assert summarise_event(rows) == {'average_score': 48, 'highest_score': 126}


def test_summarise_event_ignores_duplicate_zero_row():
    rows = [{'average_entry_score': 0, 'highest_score': None, 'finished': 0, 'data_checked': 0},
            {'average_entry_score': 48, 'highest_score': 126, 'finished': 1, 'data_checked': 1}]
    assert summarise_event(rows) == {'average_score': 48, 'highest_score': 126}


def test_summarise_event_missing_or_unfinished_is_none():
    assert summarise_event([]) is None
    assert summarise_event([{'average_entry_score': 0, 'highest_score': None, 'finished': 0}]) is None


def test_aggregate_sums_double_gameweek():
    players = aggregate_player_rows([
        row(7, 6, name='Saka', goals_scored=1, difficulty=4),
        row(7, 9, name='Saka', assists=2, bonus=3, difficulty=2),
    ])
    saka = players[7]
    assert saka['points'] == 15
    assert saka['minutes'] == 180
    assert saka['goals'] == 1 and saka['assists'] == 2 and saka['bonus'] == 3
    assert saka['difficulty'] == 2  # easiest of the two fixtures


def test_aggregate_handles_missing_difficulty():
    players = aggregate_player_rows([row(3, 2, difficulty=None)])
    assert players[3]['difficulty'] is None


def test_top_performers_orders_by_points_then_bonus_then_name_and_skips_non_players():
    players = aggregate_player_rows([
        row(1, 10, name='Bruno', bonus=1), row(2, 10, name='Alexis', bonus=3),
        row(3, 12, name='Haaland'), row(4, 15, name='Bench', minutes=0), row(5, 2, name='Zed'),
    ])
    assert [p['name'] for p in top_performers(players)] == ['Haaland', 'Alexis', 'Bruno']


def test_top_performers_empty():
    assert top_performers({}) == []


def test_fetchers_pass_season_and_gameweek():
    cursor = FakeCursor([{'x': 1}])
    assert fetch_event_rows(cursor, 2026, 5) == [{'x': 1}]
    assert cursor.executed[0][1] == (2026, 5)
    fetch_history_rows(cursor, 2026, 5)
    assert cursor.executed[1][1] == (2026, 2026, 5)
```

- [ ] **Step 2: Run to verify it fails**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_last_week_recap_data.py -q`
Expected: collection error, `ModuleNotFoundError: FPL_site.lastWeekRecap`.

- [ ] **Step 3: Implement `FPL_site/lastWeekRecap.py`**
```python
"""Last Week recap for the Week tab (releases 1.2-1.3).

Fetchers take a database cursor and return raw rows. Everything below them
is pure, so the recap logic is tested without a database.
"""
import logging

logger = logging.getLogger(__name__)

STANDOUT_COUNT = 3


#################################################
#                  Fetchers                     #
#################################################

def fetch_event_rows(cursor, year_start, gameweek):
    # bootstrapstatic_events holds duplicate rows for some gameweeks, so this
    # returns all of them and summarise_event() picks the real one.
    cursor.execute(
        "SELECT average_entry_score, highest_score, finished, data_checked "
        "FROM bootstrapstatic_events WHERE year_start = %s AND id = %s",
        (year_start, gameweek),
    )
    return cursor.fetchall()


def fetch_history_rows(cursor, year_start, gameweek):
    """One row per player per fixture in the gameweek (two in a double gameweek)."""
    cursor.execute("""
        SELECT h.element, h.total_points, h.minutes, h.goals_scored, h.assists,
               h.clean_sheets, h.saves, h.bonus, h.penalties_saved,
               e.web_name, e.element_type, t.short_name AS team_short_name,
               CASE WHEN h.was_home THEN f.team_h_difficulty ELSE f.team_a_difficulty END AS difficulty
        FROM elementsummary_history h
        JOIN bootstrapstatic_elements e
          ON e.id = h.element AND e.year_start = h.year_start
         AND e.gameweek = (SELECT MAX(gameweek) FROM bootstrapstatic_elements WHERE year_start = %s)
        JOIN bootstrapstatic_teams t ON t.id = e.team AND t.year_start = e.year_start
        LEFT JOIN fixtures_fixtures f ON f.id = h.fixture AND f.year_start = h.year_start
        WHERE h.year_start = %s AND h.round = %s
    """, (year_start, year_start, gameweek))
    return cursor.fetchall()


#################################################
#              Pure aggregation                 #
#################################################

def summarise_event(rows):
    """The gameweek's average and highest score, or None if it isn't scored yet."""
    scored = [r for r in rows if r.get('finished') and (r.get('average_entry_score') or 0) > 0]
    if not scored:
        return None
    best = max(scored, key=lambda r: r['average_entry_score'])
    highest = best.get('highest_score')
    return {'average_score': int(best['average_entry_score']),
            'highest_score': int(highest) if highest else None}


def _empty_player(row):
    return {'id': row['element'], 'name': row['web_name'], 'team': row['team_short_name'],
            'position': row['element_type'], 'points': 0, 'minutes': 0, 'goals': 0,
            'assists': 0, 'clean_sheets': 0, 'saves': 0, 'bonus': 0, 'penalties_saved': 0,
            'difficulty': None}


def aggregate_player_rows(rows):
    """Sum each player's fixture rows into one record per player."""
    players = {}
    for row in rows:
        player = players.setdefault(row['element'], _empty_player(row))
        player['points'] += row['total_points'] or 0
        player['minutes'] += row['minutes'] or 0
        player['goals'] += row['goals_scored'] or 0
        player['assists'] += row['assists'] or 0
        player['clean_sheets'] += row['clean_sheets'] or 0
        player['saves'] += row['saves'] or 0
        player['bonus'] += row['bonus'] or 0
        player['penalties_saved'] += row['penalties_saved'] or 0
        difficulty = row.get('difficulty')
        if difficulty is not None:
            current = player['difficulty']
            player['difficulty'] = difficulty if current is None else min(current, difficulty)
    return players


def top_performers(players, limit=STANDOUT_COUNT):
    """Highest scorers who actually played; ties broken by bonus, then name."""
    played = [p for p in players.values() if p['minutes'] > 0]
    ranked = sorted(played, key=lambda p: (-p['points'], -p['bonus'], p['name']))
    return ranked[:limit]
```

- [ ] **Step 4: Run to verify it passes**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_last_week_recap_data.py -q`
Expected: 8 passed.

- [ ] **Step 5: Check the SQL once against the real database (read-only)**

Run:
```bash
KJ_SKIP_DB_INIT=1 vs-env/Scripts/python.exe -c "
from FPL_site.dataModels import connect_db, season_start
from FPL_site.lastWeekRecap import *
c=connect_db(); cur=c.cursor(dictionary=True)
print(summarise_event(fetch_event_rows(cur, season_start, 5)))
print([(p['name'], p['points']) for p in top_performers(aggregate_player_rows(fetch_history_rows(cur, season_start, 5)))])"
```
Expected: `{'average_score': 48, 'highest_score': 126}` and three real players with points. If the query errors, fix the SQL and add the fix as a FakeCursor test.

- [ ] **Step 6: Commit**
```bash
git add FPL_site/lastWeekRecap.py tests/test_last_week_recap_data.py
git commit -m "Add last week recap data fetch and pure aggregation"
```

---

### Task 3: Recap phrase bank and guest recap builder

**Files:**
- Create: `FPL_site/recapCopy.py`
- Create: `features/week/last_week_recap.feature`
- Create: `tests/step_defs/test_last_week_recap.py`
- Create: `tests/test_recap_copy.py`
- Modify: `FPL_site/lastWeekRecap.py` (append the pure builder)

**Interfaces:**
- Consumes: the Player dict and `summarise_event` output from Task 2.
- Produces:
  - In `recapCopy.py`:
    - `average_headline(average_score) -> str`
    - `standout_reason(player) -> str`, a lowercase phrase that fits after "with"
    - `standout_sentence(player) -> str`
    - `recap_not_ready_copy(gameweek) -> {'title', 'body'}`
    - `AVERAGE_LOW_BELOW = 45` and `AVERAGE_HIGH_FROM = 60`
  - In `lastWeekRecap.py`:
    - `build_guest_recap(summary, performers) -> Guest | None`, where Guest is `{'headline', 'reason', 'average_score', 'highest_score', 'standouts': [{'id', 'name', 'team', 'points', 'reason'}]}`
    - `recap_payload(gameweek, summary, players) -> {'gameweek', 'status': 'ready'|'not_ready', 'guest': Guest|None, 'message': dict|None, 'personal': None}`

- [ ] **Step 1: Write the scenarios**

`features/week/last_week_recap.feature`:
```gherkin
Feature: Last week recap for everyone
  So a nervous first-timer can see how the week went in plain English,
  the Last week tab gives a verdict on the average score and one standout reason.

  Scenario: A typical week with a clear standout
    Given gameweek 5 finished with an average of 48 and a highest score of 126
    And "Haaland" scored 17 points with 3 goals and 3 bonus
    When the guest recap is built
    Then the headline is "A fairly typical week"
    And the reason is "Haaland led the way with a hat-trick and a full haul of bonus points."
    And the numbers include an average of 48

  Scenario: The gameweek has no scores yet
    Given gameweek 6 has no finished scores
    When the guest recap is built
    Then the recap is not ready
    And the not-ready message mentions gameweek 6

  Scenario: A returning user opens an older finished gameweek
    Given gameweek 2 finished with an average of 81 and a highest score of 161
    And "Palmer" scored 14 points with 2 goals and 0 bonus
    When the guest recap is built
    Then the headline is "A high-scoring week"
    And the reason is "Palmer led the way with two goals."
```

- [ ] **Step 2: Write the step definitions and the unit tests (failing)**

`tests/step_defs/test_last_week_recap.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.lastWeekRecap import recap_payload

scenarios('week/last_week_recap.feature')


def make_player(name, points, goals, bonus):
    return {'id': hash(name) % 1000, 'name': name, 'team': 'MCI', 'position': 4, 'points': points,
            'minutes': 90, 'goals': goals, 'assists': 0, 'clean_sheets': 0, 'saves': 0,
            'bonus': bonus, 'penalties_saved': 0, 'difficulty': 3}


@given(parsers.parse('gameweek {gw:d} finished with an average of {avg:d} and a highest score of {high:d}'),
       target_fixture='ctx')
def finished_gameweek(gw, avg, high):
    return {'gameweek': gw, 'summary': {'average_score': avg, 'highest_score': high}, 'players': {}}


@given(parsers.parse('gameweek {gw:d} has no finished scores'), target_fixture='ctx')
def unfinished_gameweek(gw):
    return {'gameweek': gw, 'summary': None, 'players': {}}


@given(parsers.parse('"{name}" scored {points:d} points with {goals:d} goals and {bonus:d} bonus'))
def a_player(ctx, name, points, goals, bonus):
    player = make_player(name, points, goals, bonus)
    ctx['players'][player['id']] = player


@when('the guest recap is built')
def build(ctx):
    ctx['result'] = recap_payload(ctx['gameweek'], ctx['summary'], ctx['players'])


@then(parsers.parse('the headline is "{text}"'))
def headline(ctx, text):
    assert ctx['result']['guest']['headline'] == text


@then(parsers.parse('the reason is "{text}"'))
def reason(ctx, text):
    assert ctx['result']['guest']['reason'] == text


@then(parsers.parse('the numbers include an average of {avg:d}'))
def numbers(ctx, avg):
    assert ctx['result']['guest']['average_score'] == avg


@then('the recap is not ready')
def not_ready(ctx):
    assert ctx['result']['status'] == 'not_ready'
    assert ctx['result']['guest'] is None


@then(parsers.parse('the not-ready message mentions gameweek {gw:d}'))
def not_ready_message(ctx, gw):
    assert f'Gameweek {gw}' in ctx['result']['message']['title']
```

`tests/test_recap_copy.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import re

import pytest

from FPL_site.recapCopy import (
    average_headline, standout_reason, standout_sentence, recap_not_ready_copy,
)

ACRONYMS = re.compile(r'\b(FPL|GW|XG|XA|ICT|DGW|BGW)\b', re.I)


def player(**overrides):
    base = {'name': 'Player', 'position': 3, 'goals': 0, 'assists': 0, 'clean_sheets': 0,
            'saves': 0, 'bonus': 0, 'penalties_saved': 0}
    base.update(overrides)
    return base


@pytest.mark.parametrize('average,expected', [
    (0, 'A tough week for most players'), (44, 'A tough week for most players'),
    (45, 'A fairly typical week'), (59, 'A fairly typical week'),
    (60, 'A high-scoring week'), (120, 'A high-scoring week'),
])
def test_average_headline_tiers(average, expected):
    assert average_headline(average) == expected


@pytest.mark.parametrize('overrides,expected', [
    ({'goals': 3}, 'a hat-trick'),
    ({'goals': 4, 'assists': 1}, 'a hat-trick'),
    ({'goals': 2, 'assists': 1}, 'two goals and an assist'),
    ({'goals': 2}, 'two goals'),
    ({'goals': 1, 'assists': 2}, 'a goal and an assist'),
    ({'penalties_saved': 1, 'position': 1}, 'a penalty save'),
    ({'goals': 1}, 'a goal'),
    ({'assists': 3}, '3 assists'),
    ({'assists': 2}, '2 assists'),
    ({'assists': 1}, 'an assist'),
    ({'clean_sheets': 1, 'position': 1, 'saves': 3}, 'a clean sheet and 3 saves'),
    ({'clean_sheets': 1, 'position': 2, 'saves': 2}, 'a clean sheet'),
    ({'clean_sheets': 1, 'position': 3}, 'a solid all-round game'),
    ({}, 'a solid all-round game'),
])
def test_standout_reason_tiers(overrides, expected):
    assert standout_reason(player(**overrides)) == expected


@pytest.mark.parametrize('bonus,suffix', [(2, ''), (3, ' and a full haul of bonus points'),
                                          (5, ' and a full haul of bonus points')])
def test_bonus_suffix_boundary(bonus, suffix):
    assert standout_reason(player(goals=1, bonus=bonus)) == 'a goal' + suffix


def test_standout_sentence():
    assert standout_sentence(player(name='Saka', goals=2)) == 'Saka led the way with two goals.'


def test_not_ready_copy_mentions_gameweek_and_is_calm():
    copy = recap_not_ready_copy(6)
    assert 'Gameweek 6' in copy['title']
    assert 'error' not in (copy['title'] + copy['body']).lower()


def test_no_acronyms_anywhere():
    texts = [average_headline(a) for a in (10, 50, 90)]
    texts += [standout_reason(player(**o)) for o in ({'goals': 3}, {'assists': 1}, {})]
    texts += list(recap_not_ready_copy(6).values())
    for text in texts:
        assert not ACRONYMS.search(text), text
```

- [ ] **Step 3: Run to verify they fail**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_recap_copy.py tests/step_defs/test_last_week_recap.py -q`
Expected: collection error, `ModuleNotFoundError: FPL_site.recapCopy` and `ImportError: recap_payload`.

- [ ] **Step 4: Implement `FPL_site/recapCopy.py`**
```python
"""Deterministic phrase bank for the Last week recap.

No randomness: every phrase is chosen by an explicit threshold, and each
threshold has a test on both sides of it.
"""

AVERAGE_LOW_BELOW = 45   # an average under this is a tough week for most
AVERAGE_HIGH_FROM = 60   # an average at or over this is a high-scoring week
FULL_BONUS = 3           # the most bonus points one match can give

GOALKEEPER, DEFENDER = 1, 2


def average_headline(average_score):
    if average_score < AVERAGE_LOW_BELOW:
        return 'A tough week for most players'
    if average_score < AVERAGE_HIGH_FROM:
        return 'A fairly typical week'
    return 'A high-scoring week'


def _attacking_phrase(goals, assists):
    if goals >= 3:
        return 'a hat-trick'
    if goals == 2:
        return 'two goals and an assist' if assists else 'two goals'
    if goals == 1 and assists:
        return 'a goal and an assist'
    return None


def _main_phrase(p):
    attacking = _attacking_phrase(p['goals'], p['assists'])
    if attacking:
        return attacking
    if p['penalties_saved']:
        return 'a penalty save'
    if p['goals'] == 1:
        return 'a goal'
    if p['assists'] >= 2:
        return f"{p['assists']} assists"
    if p['assists'] == 1:
        return 'an assist'
    if p['clean_sheets'] and p['position'] in (GOALKEEPER, DEFENDER):
        return f"a clean sheet and {p['saves']} saves" if p['saves'] >= 3 else 'a clean sheet'
    return 'a solid all-round game'


def standout_reason(p):
    """Why a player stood out, as a lowercase phrase that reads after 'with'."""
    phrase = _main_phrase(p)
    if p['bonus'] >= FULL_BONUS:
        phrase += ' and a full haul of bonus points'
    return phrase


def standout_sentence(p):
    return f"{p['name']} led the way with {standout_reason(p)}."


def recap_not_ready_copy(gameweek):
    return {
        'title': f"Gameweek {gameweek}'s recap is nearly ready",
        'body': "We're still pulling the scores together. Check back a little later.",
    }
```

- [ ] **Step 5: Append the builder to `FPL_site/lastWeekRecap.py`**

Add `from FPL_site.recapCopy import average_headline, standout_reason, standout_sentence, recap_not_ready_copy` to the imports. Then append:
```python
#################################################
#               Pure recap building             #
#################################################

def build_guest_recap(summary, performers):
    """The recap everyone sees: a verdict on the week plus one standout reason."""
    if summary is None or not performers:
        return None
    return {
        'headline': average_headline(summary['average_score']),
        'reason': standout_sentence(performers[0]),
        'average_score': summary['average_score'],
        'highest_score': summary['highest_score'],
        'standouts': [
            {'id': p['id'], 'name': p['name'], 'team': p['team'],
             'points': p['points'], 'reason': standout_reason(p)}
            for p in performers
        ],
    }


def recap_payload(gameweek, summary, players):
    """The JSON the recap route returns. 'personal' is filled in by release 1.3."""
    guest = build_guest_recap(summary, top_performers(players))
    if guest is None:
        return {'gameweek': gameweek, 'status': 'not_ready', 'guest': None,
                'message': recap_not_ready_copy(gameweek), 'personal': None}
    return {'gameweek': gameweek, 'status': 'ready', 'guest': guest,
            'message': None, 'personal': None}
```

- [ ] **Step 6: Run to verify they pass**

Run: `vs-env/Scripts/python.exe -m pytest -q`
Expected: all pass, including 3 new scenarios.

- [ ] **Step 7: Commit**
```bash
git add FPL_site/recapCopy.py FPL_site/lastWeekRecap.py features/week/last_week_recap.feature tests/step_defs/test_last_week_recap.py tests/test_recap_copy.py
git commit -m "Add last week recap phrase bank and guest recap builder"
```

---

### Task 4: Recap route, JavaScript view and wiring

**Files:**
- Modify: `FPL_site/lastWeekRecap.py` (append the orchestrator)
- Modify: `FPL_site/views.py` (import plus a new route)
- Create: `FPL_site/static/scripts/lib/escapeHtml.js`
- Create: `FPL_site/static/scripts/lib/recapView.js`
- Create: `FPL_site/static/scripts/weekV2.js`
- Modify: `FPL_site/static/scripts/home.js` (one import, one call)
- Modify: `FPL_site/templates/partials/week_v2.html` (the `#last-week-view` block)
- Modify: `FPL_site/static/content/home.css` (append the details styles)
- Test: `tests/js/recapView.test.js`, `tests/test_week_recap_route.py`
- Update: `tests/test_week_v2_template.py`, `tests/test_week_route.py`, `tests/test_regression_routes.py`

**Interfaces:**
- Consumes: `recap_payload` and the Task 2 fetchers.
- Produces:
  - `get_last_week_recap(gameweek) -> payload`, the `recap_payload` shape.
  - `GET /api/week/last-week-recap?gameweek=<1..38>` returns 200 with the payload, 400 with `{'error': 'invalid_gameweek'}`, or 500 with `{'error': 'server_error'}`.
  - In `recapView.js`:
    - `renderGuestRecap(guest, gameweek) -> string`
    - `renderMessage(message) -> string`
    - `RECAP_LOAD_FAILED`
  - `escapeHtml(value) -> string`
  - `initializeWeekV2()` in `weekV2.js`.
  - Template hooks:
    - `#last-week-view[data-week-v2="true"][data-gameweek]`
    - `#last-week-recap-slot`

- [ ] **Step 1: Write the failing JavaScript tests**

`tests/js/recapView.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { escapeHtml } from '../../FPL_site/static/scripts/lib/escapeHtml.js';
import { renderGuestRecap, renderMessage, RECAP_LOAD_FAILED } from '../../FPL_site/static/scripts/lib/recapView.js';

const guest = {
    headline: 'A fairly typical week',
    reason: 'Haaland led the way with a hat-trick.',
    average_score: 48,
    highest_score: 126,
    standouts: [{ id: 1, name: 'Haaland', team: 'MCI', points: 17, reason: 'a hat-trick' }],
};

test('escapes player names', () => {
    assert.equal(escapeHtml(`<b>O'Brien</b> & co`), '&lt;b&gt;O&#39;Brien&lt;/b&gt; &amp; co');
    assert.equal(escapeHtml(null), '');
});

test('guest recap shows verdict and reason by default, numbers inside details', () => {
    const html = renderGuestRecap(guest, 5);
    const [beforeDetails, insideDetails] = html.split('<details');
    assert.match(beforeDetails, /A fairly typical week/);
    assert.match(beforeDetails, /Haaland led the way with a hat-trick\./);
    assert.doesNotMatch(beforeDetails, /48/);
    assert.match(insideDetails, /See the numbers/);
    assert.match(insideDetails, /Average score: 48 points/);
    assert.match(insideDetails, /Highest score: 126 points/);
    assert.match(insideDetails, /A hat-trick/);
});

test('guest recap without a highest score omits it', () => {
    const html = renderGuestRecap({ ...guest, highest_score: null }, 5);
    assert.doesNotMatch(html, /Highest score/);
});

test('guest recap escapes hostile names', () => {
    const hostile = { ...guest, standouts: [{ ...guest.standouts[0], name: '<img src=x>' }] };
    assert.doesNotMatch(renderGuestRecap(hostile, 5), /<img/);
});

test('message card renders title and body', () => {
    const html = renderMessage({ title: 'Nearly ready', body: 'Check back soon.' });
    assert.match(html, /Nearly ready/);
    assert.match(html, /Check back soon\./);
});

test('load-failure copy is calm and acronym free', () => {
    const text = RECAP_LOAD_FAILED.title + ' ' + RECAP_LOAD_FAILED.body;
    assert.doesNotMatch(text, /\b(FPL|GW|error)\b/i);
});
```

Run: `npm test`
Expected: FAIL, because the modules can't be found.

- [ ] **Step 2: Implement the JavaScript modules**

`FPL_site/static/scripts/lib/escapeHtml.js`:
```js
/***** escapeHtml.js *****/
// Text from the server (like a player's name) is dropped into HTML strings.
// If that text contained characters such as < or &, the browser would read
// them as markup. This swaps each one for its harmless "entity" version, so
// the text always shows exactly as written.
export function escapeHtml(value) {
    return String(value ?? '')              // ?? turns null/undefined into ''
        .replace(/&/g, '&amp;')             // & first, or we'd double-escape the others
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
```

`FPL_site/static/scripts/lib/recapView.js`:
```js
/***** recapView.js *****/
// Pure functions that turn recap data into HTML strings. No DOM access here,
// so they can be tested in Node. weekV2.js puts the strings on the page.
import { escapeHtml } from './escapeHtml.js';

// Shown if the recap request itself fails (no connection, server down).
export const RECAP_LOAD_FAILED = {
    title: "We couldn't load last week's recap",
    body: 'Nothing is wrong on your side. Try again in a moment.',
};

// "a hat-trick" -> "A hat-trick" (used where a reason starts a line).
function capitalise(text) {
    const s = String(text ?? '');
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function standoutRow(player) {
    return `
        <li class="recap-standout">
            <div class="recap-standout-head">
                <span>${escapeHtml(player.name)} <span class="sub">${escapeHtml(player.team)}</span></span>
                <span class="recap-points">${escapeHtml(player.points)} points</span>
            </div>
            <p class="sub">${escapeHtml(capitalise(player.reason))}</p>
        </li>`;
}

export function renderGuestRecap(guest, gameweek) {
    // Template literal: the backticks let us write HTML across several lines
    // and drop values in with ${...}. Every value goes through escapeHtml.
    const highest = guest.highest_score
        ? ` · Highest score: ${escapeHtml(guest.highest_score)} points`
        : '';
    return `
        <div class="card" id="guest-recap">
            <div class="eyebrow-sm">gameweek ${escapeHtml(gameweek)}, for everyone</div>
            <h3>${escapeHtml(guest.headline)}</h3>
            <p>${escapeHtml(guest.reason)}</p>
            <details class="recap-details">
                <summary>See the numbers</summary>
                <p class="sub">Average score: ${escapeHtml(guest.average_score)} points${highest}</p>
                <ul class="recap-standouts">${guest.standouts.map(standoutRow).join('')}</ul>
            </details>
        </div>`;
}

export function renderMessage(message) {
    return `
        <div class="card">
            <h3>${escapeHtml(message.title)}</h3>
            <p class="sub">${escapeHtml(message.body)}</p>
        </div>`;
}
```

Run: `npm test`
Expected: PASS, with 6 new tests.

- [ ] **Step 3: Write the failing route test**

`tests/test_week_recap_route.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import app
import FPL_site.views as views


@pytest.fixture
def client():
    return app.test_client()


def test_recap_route_returns_payload(client, monkeypatch):
    seen = {}

    def fake(gameweek):
        seen['gameweek'] = gameweek
        return {'gameweek': gameweek, 'status': 'ready', 'guest': {'headline': 'x'},
                'message': None, 'personal': None}

    monkeypatch.setattr(views, 'get_last_week_recap', fake)
    resp = client.get('/api/week/last-week-recap?gameweek=5')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ready'
    assert seen['gameweek'] == 5


@pytest.mark.parametrize('query', ['', '?gameweek=', '?gameweek=abc', '?gameweek=0', '?gameweek=39', '?gameweek=-1'])
def test_recap_route_rejects_bad_gameweek(client, query):
    resp = client.get('/api/week/last-week-recap' + query)
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'invalid_gameweek'}


def test_recap_route_hides_internal_errors(client, monkeypatch):
    def boom(gameweek):
        raise RuntimeError('database exploded')

    monkeypatch.setattr(views, 'get_last_week_recap', boom)
    resp = client.get('/api/week/last-week-recap?gameweek=5')
    assert resp.status_code == 500
    assert resp.get_json() == {'error': 'server_error'}
```

Run: `vs-env/Scripts/python.exe -m pytest tests/test_week_recap_route.py -q`
Expected: FAIL with a 404, or an `AttributeError` on `get_last_week_recap`.

- [ ] **Step 4: Implement the orchestrator and the route**

Append to `FPL_site/lastWeekRecap.py`, and add `from FPL_site.dataModels import connect_db, season_start` to its imports:
```python
#################################################
#          Live-route entry point               #
#################################################

def get_last_week_recap(gameweek):
    """Reads the finished gameweek from the database and builds the recap."""
    conn = connect_db()
    if conn is None:
        logger.error("get_last_week_recap: could not connect to the database.")
        return recap_payload(gameweek, None, {})
    try:
        cursor = conn.cursor(dictionary=True)
        summary = summarise_event(fetch_event_rows(cursor, season_start, gameweek))
        players = aggregate_player_rows(fetch_history_rows(cursor, season_start, gameweek))
    finally:
        conn.close()
    return recap_payload(gameweek, summary, players)
```

In `FPL_site/views.py`, add `from .lastWeekRecap import get_last_week_recap` next to the `weekCopy` import, and add this after the `home()` helpers:
```python
GAMEWEEKS_IN_SEASON = 38


def _parse_gameweek(raw):
    """A gameweek number from a query string, or None if it isn't 1-38."""
    if not raw or not raw.isdigit():
        return None
    gameweek = int(raw)
    return gameweek if 1 <= gameweek <= GAMEWEEKS_IN_SEASON else None


@app.route('/api/week/last-week-recap')
def week_last_week_recap():
    logger.info("Request for last week recap")
    gameweek = _parse_gameweek(request.args.get('gameweek', ''))
    if gameweek is None:
        return jsonify({'error': 'invalid_gameweek'}), 400
    try:
        return jsonify(get_last_week_recap(gameweek))
    except Exception as e:
        logger.error(f"Error building last week recap: {e}")
        return jsonify({'error': 'server_error'}), 500
```

Run: `vs-env/Scripts/python.exe -m pytest tests/test_week_recap_route.py -q`
Expected: 8 passed.

- [ ] **Step 5: Wire the template, the glue and the styles**

In `FPL_site/templates/partials/week_v2.html`, replace the whole `<div class="last-week-view" ...> ... </div>` block with:
```html
        <div class="last-week-view" id="last-week-view" style="display: none;"
             data-week-v2="true"
             data-gameweek="{{ last_week.gameweek if last_week.status == 'final' else '' }}">
            {% if last_week_copy %}
            <div class="eyebrow-sm">{{ last_week_copy.eyebrow }}</div>
            <h2 class="title" style="margin-bottom:4px;">{{ last_week_copy.title }}</h2>
            <p class="sub">{{ last_week_copy.body }}</p>
            {% else %}
            <div class="eyebrow-sm">last week</div>
            <h2 class="title" style="margin-bottom:4px;">How gameweek {{ last_week.gameweek }} went</h2>
            {# Filled by weekV2.js from /api/week/last-week-recap #}
            <div id="last-week-recap-slot">
                <div class="card" aria-busy="true" aria-label="Loading last week's recap">
                    <div class="skeleton" style="height:18px; width:60%; margin-bottom:10px;"></div>
                    <div class="skeleton" style="height:14px; width:90%;"></div>
                </div>
            </div>
            {% endif %}
        </div>
```

`FPL_site/static/scripts/weekV2.js`:
```js
/***** weekV2.js *****/
// DOM glue for the rebuilt Week tab (behind FEATURE_WEEK_V2). All the
// decisions about *what* to show live in the pure modules under lib/; this
// file only fetches data and puts the resulting HTML on the page.
import { renderGuestRecap, renderMessage, RECAP_LOAD_FAILED } from './lib/recapView.js';

export function initializeWeekV2() {
    const lastWeekView = document.getElementById('last-week-view');
    // The flag-off page has no data-week-v2 attribute, so this is a no-op there.
    if (!lastWeekView || lastWeekView.dataset.weekV2 !== 'true') return;
    loadLastWeekRecap(lastWeekView);
}

async function loadLastWeekRecap(lastWeekView) {
    const gameweek = lastWeekView.dataset.gameweek;
    const slot = document.getElementById('last-week-recap-slot');
    // No finished gameweek: the server already rendered a friendly message.
    if (!gameweek || !slot) return;

    try {
        const res = await fetch(`/api/week/last-week-recap?gameweek=${encodeURIComponent(gameweek)}`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();
        slot.innerHTML = data.status === 'ready'
            ? renderGuestRecap(data.guest, data.gameweek)
            : renderMessage(data.message);
    } catch (err) {
        console.error('Failed to load last week recap', err);
        slot.innerHTML = renderMessage(RECAP_LOAD_FAILED);
    }
}
```

In `FPL_site/static/scripts/home.js`:
- Add `import { initializeWeekV2 } from './weekV2.js';` after the `liveGameweek.js` import.
- In `initializeHome()`, add `initializeWeekV2();` on the line directly after `initializeWeekState();`.

Append to `FPL_site/static/content/home.css`:
```css
/* Week v2: numbers-on-demand layer and recap rows */
.recap-details { margin-top: 12px; border-top: 1px solid var(--grey); padding-top: 10px; }
.recap-details summary { cursor: pointer; font-weight: 700; color: var(--plum); font-size: 14px; }
.recap-details summary:focus-visible { outline: 2px solid var(--plum); outline-offset: 2px; border-radius: 4px; }
.recap-details[open] summary { margin-bottom: 8px; }
.recap-standouts { list-style: none; padding: 0; margin: 0; }
.recap-standout { padding: 8px 0; border-bottom: 1px solid var(--grey); }
.recap-standout:last-child { border-bottom: none; }
.recap-standout-head { display: flex; justify-content: space-between; gap: 8px; font-size: 14px; }
.recap-points { font-weight: 700; white-space: nowrap; }
```

- [ ] **Step 6: Update the 1.1 tests and the regression list**

- `tests/test_week_v2_template.py`: replace any assertion on the old fallback text ("Gameweek N recap" or "is on its way") with:
  - `'id="last-week-recap-slot"' in html`
  - `'data-gameweek="5"' in html`
  - for a `confirming` last week, `'data-gameweek=""' in html`
- `tests/test_week_route.py`: replace `assert 'Gameweek 38 recap' in html` with `assert 'How gameweek 38 went' in html`.
- `tests/test_regression_routes.py`: add this entry to `DATA_ROUTE_STUBS`:
```python
    '/api/week/last-week-recap?gameweek=5': ('get_last_week_recap', {
        'gameweek': 5, 'status': 'ready', 'guest': None, 'message': None, 'personal': None}),
```

Run: `vs-env/Scripts/python.exe -m pytest -q && npm test && node --check FPL_site/static/scripts/weekV2.js && node --check FPL_site/static/scripts/home.js`
Expected: all green.

- [ ] **Step 7: Commit**
```bash
git add -A FPL_site tests features
git checkout -- FPL_site/__pycache__ 2>/dev/null
git commit -m "Show the guest last week recap on the Week tab behind FEATURE_WEEK_V2"
```
(Run `git status` first, and make sure no `.pyc` files are staged.)

**Release 1.2 gate:** run the roadmap release gate. The live smoke uses `FEATURE_WEEK_V2=1`:
- `curl /api/week/last-week-recap?gameweek=5` returns a ready payload with real players.
- The browser check at 375px covers the Last week tab: default view, details expanded, and keyboard focus on the summary.

---

# Release 1.3: "How did I do?" (personal recap plus welcome back)

### Task 5: Resolver exposes last week's deadline

**Files:**
- Modify: `FPL_site/weekResolver.py` (`_last_week`, plus the two early returns in `resolve_week`)
- Modify: `FPL_site/templates/partials/week_v2.html` (`#last-week-view` attributes)
- Test: `tests/test_week_resolver.py`, `tests/step_defs/test_gameweek_state.py`

**Interfaces:**
- Produces: `last_week` becomes `{'status', 'gameweek', 'deadline': str|None}`, and the template attribute `data-deadline` on `#last-week-view`.

- [ ] **Step 1: Failing test** — append to `tests/test_week_resolver.py`:
```python
def test_last_week_includes_its_deadline():
    from datetime import datetime
    from FPL_site.weekResolver import resolve_week
    events = [
        {'id': 1, 'deadline_time': '2026-08-15T10:00:00Z', 'finished': True, 'data_checked': True},
        {'id': 2, 'deadline_time': '2026-08-22T10:00:00Z', 'finished': False, 'data_checked': False},
    ]
    state = resolve_week(events, datetime(2026, 8, 20))
    assert state['last_week'] == {'status': 'final', 'gameweek': 1, 'deadline': '2026-08-15T10:00:00Z'}


def test_no_last_week_has_no_deadline():
    from datetime import datetime
    from FPL_site.weekResolver import resolve_week
    assert resolve_week([], datetime(2026, 8, 20))['last_week']['deadline'] is None
```
Run `vs-env/Scripts/python.exe -m pytest tests/test_week_resolver.py -q`. Expected: the 2 new tests FAIL with a KeyError or an inequality.

- [ ] **Step 2: Implement.** In `weekResolver.py`:
  - Add a module constant `NO_LAST_WEEK = {'status': 'none', 'gameweek': None, 'deadline': None}`, and use `dict(NO_LAST_WEEK)` in all three places that currently build `{'status': 'none', 'gameweek': None}`.
  - In `_last_week`, return `{'status': status, 'gameweek': event.get('id'), 'deadline': event.get('deadline_time')}`.

- [ ] **Step 3: Fix the existing expectations.** Run the whole suite. Any existing test comparing a full `last_week` dict now needs a `'deadline'` key. Update those expected dicts with the event's deadline string, or with `None` when the status is 'none'. Don't weaken any assertion.

- [ ] **Step 4: Template.** Add `data-deadline="{{ last_week.deadline or '' }}"` and `data-this-week-gameweek="{{ this_week.gameweek if this_week.gameweek is not none else '' }}"` to the `#last-week-view` div.

- [ ] **Step 5:** Run `vs-env/Scripts/python.exe -m pytest -q`; everything should be green. Then commit: `git commit -am "Expose last week's deadline from the gameweek resolver"`.

---

### Task 6: Squad results and "one thing you got right"

**Files:**
- Modify: `FPL_site/recapCopy.py` (append `pick_one_thing_right`)
- Modify: `FPL_site/lastWeekRecap.py` (append `build_squad`)
- Create: `features/week/one_thing_right.feature`
- Create: `tests/step_defs/test_one_thing_right.py`
- Test: `tests/test_recap_copy.py`, `tests/test_last_week_recap_data.py`

**Interfaces:**
- Consumes:
  - The Player dict (Task 2).
  - The `get_entry_picks(entry_id, gameweek)` shape from `dataModels.py`: `{'picks': [{'element', 'multiplier', 'is_captain'}], 'entry_history': {'points', 'event_transfers_cost'}}`, or None.
- Produces:
  - `build_squad(picks_data, players) -> list[SquadPlayer]`, where SquadPlayer is `{'id', 'name', 'is_captain', 'multiplier', 'points', 'minutes', 'difficulty'}`.
  - `pick_one_thing_right(squad) -> {'tier': 'captain'|'big_pick'|'sound_blank'|'solid_pick'|'showed_up', 'title': str, 'reason': str}`.
  - Thresholds: `CAPTAIN_PAID_OFF_FROM = 6`, `BIG_PICK_FROM = 8`, `SOLID_PICK_FROM = 4`, `KIND_FIXTURE_UP_TO = 2`, `BLANK_UP_TO = 2`.

- [ ] **Step 1: Scenarios** — `features/week/one_thing_right.feature`:
```gherkin
Feature: One thing you got right
  Every personal recap celebrates something, even in a bad week.

  Scenario: The captain delivered
    Given a squad where captain "Salah" scored 12 points
    When we look for one thing they got right
    Then the tier is "captain"
    And the reason mentions "Salah"

  Scenario: Nothing scored well but a pick was sound
    Given a squad where nobody scored more than 3 points
    And starter "Isak" blanked with 1 point in a kind fixture
    When we look for one thing they got right
    Then the tier is "sound_blank"
    And the reason mentions "kind fixture"

  Scenario: Missing data for every player
    Given a squad with no player results
    When we look for one thing they got right
    Then the tier is "showed_up"

  Scenario: A returning user's first week back went badly
    Given a squad where nobody scored more than 1 point
    When we look for one thing they got right
    Then the tier is "showed_up"
    And the reason mentions "fresh start"
```

- [ ] **Step 2: Failing tests.**

`tests/step_defs/test_one_thing_right.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.recapCopy import pick_one_thing_right

scenarios('week/one_thing_right.feature')


def sp(pid, name, points, captain=False, multiplier=1, minutes=90, difficulty=3):
    return {'id': pid, 'name': name, 'is_captain': captain,
            'multiplier': 2 if captain else multiplier, 'points': points,
            'minutes': minutes, 'difficulty': difficulty}


@given(parsers.parse('a squad where captain "{name}" scored {points:d} points'), target_fixture='squad')
def captain_scored(name, points):
    return [sp(1, name, points, captain=True), sp(2, 'Other', 2)]


@given(parsers.parse('a squad where nobody scored more than {points:d} points'), target_fixture='squad')
def low_scoring(points):
    return [sp(1, 'Cap', min(points, 1), captain=True, difficulty=4), sp(2, 'Mid', points, difficulty=4)]


@given(parsers.parse('a squad where nobody scored more than {points:d} point'), target_fixture='squad')
def very_low_scoring(points):
    return [sp(1, 'Cap', points, captain=True, difficulty=4), sp(2, 'Mid', points, difficulty=4)]


@given(parsers.parse('starter "{name}" blanked with {points:d} point in a kind fixture'))
def kind_blank(squad, name, points):
    squad.append(sp(3, name, points, difficulty=2))


@given('a squad with no player results', target_fixture='squad')
def no_results():
    return [sp(1, 'Unknown', 0, captain=True, minutes=0, difficulty=None)]


@when('we look for one thing they got right', target_fixture='result')
def look(squad):
    return pick_one_thing_right(squad)


@then(parsers.parse('the tier is "{tier}"'))
def tier_is(result, tier):
    assert result['tier'] == tier


@then(parsers.parse('the reason mentions "{text}"'))
def reason_mentions(result, text):
    assert text in result['reason']
```

Append to `tests/test_recap_copy.py`:
```python
from FPL_site.recapCopy import pick_one_thing_right


def squad_player(name, points, captain=False, multiplier=1, minutes=90, difficulty=3):
    return {'id': hash(name) % 1000, 'name': name, 'is_captain': captain,
            'multiplier': multiplier if not captain else max(multiplier, 2),
            'points': points, 'minutes': minutes, 'difficulty': difficulty}


@pytest.mark.parametrize('points,tier', [(5, 'solid_pick'), (6, 'captain')])
def test_captain_threshold(points, tier):
    assert pick_one_thing_right([squad_player('Cap', points, captain=True)])['tier'] == tier


def test_triple_captain_wording():
    result = pick_one_thing_right([squad_player('Cap', 10, captain=True, multiplier=3)])
    assert 'triple' in result['reason']


@pytest.mark.parametrize('points,tier', [(7, 'solid_pick'), (8, 'big_pick')])
def test_big_pick_threshold(points, tier):
    squad = [squad_player('Cap', 1, captain=True, difficulty=5), squad_player('Star', points)]
    assert pick_one_thing_right(squad)['tier'] == tier


def test_bench_player_never_counts():
    squad = [squad_player('Cap', 1, captain=True, difficulty=5), squad_player('Bench', 15, multiplier=0)]
    assert pick_one_thing_right(squad)['tier'] == 'showed_up'


@pytest.mark.parametrize('difficulty,points,tier', [
    (2, 2, 'sound_blank'), (3, 2, 'showed_up'), (2, 3, 'showed_up'), (None, 1, 'showed_up'),
])
def test_sound_blank_boundaries(difficulty, points, tier):
    squad = [squad_player('Cap', 0, captain=True, difficulty=5, minutes=0),
             squad_player('Pick', points, difficulty=difficulty)]
    assert pick_one_thing_right(squad)['tier'] == tier


def test_sound_blank_needs_minutes():
    squad = [squad_player('Cap', 0, captain=True, minutes=0, difficulty=5),
             squad_player('Benched', 0, minutes=0, difficulty=1)]
    assert pick_one_thing_right(squad)['tier'] == 'showed_up'


def test_empty_squad_is_kind():
    result = pick_one_thing_right([])
    assert result['tier'] == 'showed_up' and not ACRONYMS.search(result['reason'])
```

Append to `tests/test_last_week_recap_data.py`:
```python
from FPL_site.lastWeekRecap import build_squad


def test_build_squad_joins_picks_to_results_and_tolerates_missing_players():
    players = aggregate_player_rows([row(7, 9, name='Saka', difficulty=2)])
    picks = {'picks': [{'element': 7, 'multiplier': 2, 'is_captain': True},
                       {'element': 99, 'multiplier': 1, 'is_captain': False}]}
    squad = build_squad(picks, players)
    assert squad[0] == {'id': 7, 'name': 'Saka', 'is_captain': True, 'multiplier': 2,
                        'points': 9, 'minutes': 90, 'difficulty': 2}
    assert squad[1]['points'] == 0 and squad[1]['minutes'] == 0 and squad[1]['difficulty'] is None


def test_build_squad_handles_no_picks():
    assert build_squad({}, {}) == []
```

Run `vs-env/Scripts/python.exe -m pytest -q`. Expected: the new tests FAIL with ImportErrors.

- [ ] **Step 3: Implement.** Append to `FPL_site/recapCopy.py`:
```python
CAPTAIN_PAID_OFF_FROM = 6   # captain's own points (before doubling)
BIG_PICK_FROM = 8
SOLID_PICK_FROM = 4
KIND_FIXTURE_UP_TO = 2      # fixture difficulty 1-2 is a kind fixture
BLANK_UP_TO = 2             # 2 points or fewer counts as a blank


def _starters(squad):
    return [p for p in squad if p['multiplier'] > 0]


def _best(players):
    # Highest points; ties broken by name so the choice is always the same.
    return min(players, key=lambda p: (-p['points'], p['name'])) if players else None


def pick_one_thing_right(squad):
    """Something to celebrate in a personal recap, even after a bad week."""
    starters = _starters(squad)
    captain = next((p for p in starters if p['is_captain']), None)
    if captain and captain['points'] >= CAPTAIN_PAID_OFF_FROM:
        times = 'triple' if captain['multiplier'] >= 3 else 'double'
        return {'tier': 'captain', 'title': 'Your captain call',
                'reason': f"Captaining {captain['name']} paid off: {captain['points']} points, "
                          f"and you got them {times}."}

    best = _best(starters)
    if best and best['points'] >= BIG_PICK_FROM:
        return {'tier': 'big_pick', 'title': 'A smart pick',
                'reason': f"Having {best['name']} in your team paid off with {best['points']} points."}

    sound = [p for p in starters if p['minutes'] > 0 and p['difficulty'] is not None
             and p['difficulty'] <= KIND_FIXTURE_UP_TO and p['points'] <= BLANK_UP_TO]
    if sound:
        pick = min(sound, key=lambda p: p['name'])
        return {'tier': 'sound_blank', 'title': 'Sound thinking',
                'reason': f"Backing {pick['name']} for a kind fixture was the right idea, even "
                          f"though it didn't land this time. Keep trusting that logic."}

    if best and best['points'] >= SOLID_PICK_FROM:
        return {'tier': 'solid_pick', 'title': 'A solid pick',
                'reason': f"{best['name']} came through for you with {best['points']} points."}

    return {'tier': 'showed_up', 'title': 'You showed up',
            'reason': "Weeks like this happen to everyone. The next deadline is a fresh start, "
                      "and we'll help you make the most of it."}
```

Append to `FPL_site/lastWeekRecap.py`:
```python
def build_squad(picks_data, players):
    """Join a team's picks to last week's results. Players with no result score 0."""
    squad = []
    for pick in (picks_data or {}).get('picks', []):
        result = players.get(pick['element'], {})
        squad.append({
            'id': pick['element'],
            'name': result.get('name', 'A player'),
            'is_captain': bool(pick.get('is_captain')),
            'multiplier': pick.get('multiplier', 0),
            'points': result.get('points', 0),
            'minutes': result.get('minutes', 0),
            'difficulty': result.get('difficulty'),
        })
    return squad
```

- [ ] **Step 4:** Run `vs-env/Scripts/python.exe -m pytest -q`; everything should be green. Then commit:
```bash
git add FPL_site/recapCopy.py FPL_site/lastWeekRecap.py features/week/one_thing_right.feature tests
git commit -m "Pick one thing the user got right, celebrating sound picks that blanked"
```

---

### Task 7: Score verdict and the personal recap route

**Files:**
- Modify: `FPL_site/recapCopy.py` (append `score_verdict` and `team_not_found_copy`)
- Modify: `FPL_site/lastWeekRecap.py` (`build_personal_recap`; extend `recap_payload` and `get_last_week_recap`)
- Modify: `FPL_site/views.py` (`week_last_week_recap` reads `team_id`)
- Create: `features/week/personal_recap.feature`
- Create: `tests/step_defs/test_personal_recap.py`
- Test: `tests/test_recap_copy.py`, `tests/test_week_recap_route.py`

**Interfaces:**
- Consumes: `build_squad`, `pick_one_thing_right`, and `dataModels.get_entry_picks`.
- Produces:
  - `score_verdict(score, average) -> {'tier': 'well_above'|'above'|'about'|'below'|'tough', 'text': str}`
  - `team_not_found_copy(gameweek) -> {'title', 'body'}`
  - `build_personal_recap(picks_data, players, average_score, gameweek) -> Personal`
  - Personal is one of:
    - `{'status': 'ok', 'score': int, 'average_score': int, 'verdict': str, 'verdict_tier': str, 'right_call': {...}}`
    - `{'status': 'team_not_found', 'message': {...}}`
  - `recap_payload(gameweek, summary, players, picks_data=None, team_requested=False)`
  - `get_last_week_recap(gameweek, team_id=None)`
  - `GET /api/week/last-week-recap?gameweek=5&team_id=123`. A junk `team_id` is treated as not found and still returns 200.

- [ ] **Step 1: Scenarios** — `features/week/personal_recap.feature`:
```gherkin
Feature: Personal last week recap
  A known team sees their score against the average and one thing they got right.

  Scenario: Above average week
    Given the average last week was 48
    And my team scored 61 points with 4 points of transfer costs
    When my personal recap is built
    Then the verdict tier is "above"

  Scenario: The team number can't be found for that gameweek
    Given the average last week was 48
    And my team number is not found
    When my personal recap is built
    Then I see a gentle not-found message for gameweek 5

  Scenario: Returning after weeks away to a tough week
    Given the average last week was 60
    And my team scored 30 points with 0 points of transfer costs
    When my personal recap is built
    Then the verdict tier is "tough"
    And the verdict does not contain "bad"
```

- [ ] **Step 2: Failing tests.**

`tests/step_defs/test_personal_recap.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.lastWeekRecap import build_personal_recap

scenarios('week/personal_recap.feature')


@given(parsers.parse('the average last week was {avg:d}'), target_fixture='ctx')
def average(avg):
    return {'average': avg, 'picks': None}


@given(parsers.parse('my team scored {gross:d} points with {cost:d} points of transfer costs'))
def team_scored(ctx, gross, cost):
    ctx['picks'] = {'picks': [], 'entry_history': {'points': gross, 'event_transfers_cost': cost}}


@given('my team number is not found')
def not_found(ctx):
    ctx['picks'] = None


@when('my personal recap is built')
def build(ctx):
    ctx['result'] = build_personal_recap(ctx['picks'], {}, ctx['average'], 5)


@then(parsers.parse('the verdict tier is "{tier}"'))
def tier(ctx, tier):
    assert ctx['result']['verdict_tier'] == tier


@then(parsers.parse('the verdict does not contain "{word}"'))
def no_word(ctx, word):
    assert word not in ctx['result']['verdict'].lower()


@then(parsers.parse('I see a gentle not-found message for gameweek {gw:d}'))
def gentle(ctx, gw):
    assert ctx['result']['status'] == 'team_not_found'
    assert f'gameweek {gw}' in ctx['result']['message']['body']
```

Append to `tests/test_recap_copy.py`:
```python
from FPL_site.recapCopy import score_verdict, team_not_found_copy


@pytest.mark.parametrize('score,tier', [
    (63, 'well_above'), (62, 'above'), (53, 'above'), (52, 'about'),
    (48, 'about'), (44, 'about'), (43, 'below'), (34, 'below'), (33, 'tough'), (0, 'tough'),
])
def test_score_verdict_boundaries_against_average_48(score, tier):
    assert score_verdict(score, 48)['tier'] == tier


def test_score_verdict_copy_is_kind_and_acronym_free():
    for score in (0, 40, 48, 55, 90):
        text = score_verdict(score, 48)['text']
        assert not ACRONYMS.search(text)
        assert 'bad' not in text.lower() and 'fail' not in text.lower()


def test_team_not_found_copy():
    copy = team_not_found_copy(5)
    assert 'gameweek 5' in copy['body'] and not ACRONYMS.search(copy['title'] + copy['body'])
```

Append to `tests/test_week_recap_route.py`:
```python
def test_route_passes_team_id(client, monkeypatch):
    seen = {}

    def fake(gameweek, team_id=None):
        seen['team_id'] = team_id
        return {'gameweek': gameweek, 'status': 'ready', 'guest': {}, 'message': None, 'personal': None}

    monkeypatch.setattr(views, 'get_last_week_recap', fake)
    client.get('/api/week/last-week-recap?gameweek=5&team_id=123')
    assert seen['team_id'] == 123


@pytest.mark.parametrize('junk', ['abc', '-4', '0', '1e5', '99999999999'])
def test_route_rejects_junk_team_id_gracefully(client, monkeypatch, junk):
    seen = {}

    def fake(gameweek, team_id=None):
        seen['team_id'] = team_id
        return {'gameweek': gameweek, 'status': 'ready', 'guest': {}, 'message': None,
                'personal': {'status': 'team_not_found'}}

    monkeypatch.setattr(views, 'get_last_week_recap', fake)
    resp = client.get(f'/api/week/last-week-recap?gameweek=5&team_id={junk}')
    assert resp.status_code == 200
    assert seen['team_id'] == 'invalid'
```

Add to `tests/test_last_week_recap_data.py`:
```python
from FPL_site.lastWeekRecap import recap_payload, build_personal_recap


def test_personal_recap_team_not_found():
    assert build_personal_recap(None, {}, 48, 5)['status'] == 'team_not_found'


def test_payload_includes_personal_only_when_requested_and_ready():
    players = aggregate_player_rows([row(7, 9, name='Saka')])
    summary = {'average_score': 48, 'highest_score': 100}
    picks = {'picks': [{'element': 7, 'multiplier': 2, 'is_captain': True}],
             'entry_history': {'points': 70, 'event_transfers_cost': 0}}
    assert recap_payload(5, summary, players)['personal'] is None
    personal = recap_payload(5, summary, players, picks_data=picks, team_requested=True)['personal']
    assert personal['status'] == 'ok' and personal['score'] == 70
    not_ready = recap_payload(5, None, {}, picks_data=picks, team_requested=True)
    assert not_ready['personal'] is None
```

Run the suite. Expected: the new tests FAIL.

- [ ] **Step 3: Implement.** Append to `FPL_site/recapCopy.py`:
```python
WELL_ABOVE_FROM = 15   # points above the average
ABOVE_FROM = 5
BELOW_FROM = -5        # 5+ under the average is "below"
TOUGH_FROM = -15       # 15+ under is a tough week


def score_verdict(score, average):
    diff = score - average
    if diff >= WELL_ABOVE_FROM:
        return {'tier': 'well_above', 'text': 'Well above average. A cracking week.'}
    if diff >= ABOVE_FROM:
        return {'tier': 'above', 'text': 'Above average. Nicely done.'}
    if diff > BELOW_FROM:
        return {'tier': 'about', 'text': 'Right around the average. A steady week.'}
    if diff > TOUGH_FROM:
        return {'tier': 'below', 'text': "A little below average. It happens, and one week "
                                         "doesn't define a season."}
    return {'tier': 'tough', 'text': "A tough week. They happen to everyone, and there's "
                                     "plenty of season left."}


def team_not_found_copy(gameweek):
    return {'title': "We couldn't find that team",
            'body': f"There's no team with that number for gameweek {gameweek}. Double-check the "
                    f"number, or if you joined after that, your first recap is on its way."}
```

Boundary check against average 48: 63 is diff 15 (well_above); 62 is 14 (above); 53 is 5 (above); 52 is 4 (about); 44 is -4 (about); 43 is -5 (below); 34 is -14 (below); 33 is -15 (tough). These match the test table.

In `FPL_site/lastWeekRecap.py`, extend the recapCopy import with `pick_one_thing_right, score_verdict, team_not_found_copy` and `from FPL_site.dataModels import get_entry_picks`. Add:
```python
def build_personal_recap(picks_data, players, average_score, gameweek):
    """Score against the average plus one thing the user got right."""
    if not picks_data:
        return {'status': 'team_not_found', 'message': team_not_found_copy(gameweek)}
    history = picks_data.get('entry_history') or {}
    # Match what the official app shows: points minus any transfer costs.
    score = (history.get('points') or 0) - (history.get('event_transfers_cost') or 0)
    verdict = score_verdict(score, average_score)
    return {
        'status': 'ok',
        'score': score,
        'average_score': average_score,
        'verdict': verdict['text'],
        'verdict_tier': verdict['tier'],
        'right_call': pick_one_thing_right(build_squad(picks_data, players)),
    }
```

Replace `recap_payload` with:
```python
def recap_payload(gameweek, summary, players, picks_data=None, team_requested=False):
    """The JSON the recap route returns."""
    guest = build_guest_recap(summary, top_performers(players))
    if guest is None:
        return {'gameweek': gameweek, 'status': 'not_ready', 'guest': None,
                'message': recap_not_ready_copy(gameweek), 'personal': None}
    personal = (build_personal_recap(picks_data, players, summary['average_score'], gameweek)
                if team_requested else None)
    return {'gameweek': gameweek, 'status': 'ready', 'guest': guest,
            'message': None, 'personal': personal}
```

Replace `get_last_week_recap` with:
```python
def get_last_week_recap(gameweek, team_id=None):
    """team_id: an int, None for a guest, or 'invalid' if the user typed junk."""
    conn = connect_db()
    if conn is None:
        logger.error("get_last_week_recap: could not connect to the database.")
        return recap_payload(gameweek, None, {})
    try:
        cursor = conn.cursor(dictionary=True)
        summary = summarise_event(fetch_event_rows(cursor, season_start, gameweek))
        players = aggregate_player_rows(fetch_history_rows(cursor, season_start, gameweek))
    finally:
        conn.close()
    picks_data = get_entry_picks(team_id, gameweek) if isinstance(team_id, int) else None
    return recap_payload(gameweek, summary, players, picks_data=picks_data,
                         team_requested=team_id is not None)
```

In `views.py`, add:
```python
MAX_TEAM_ID_DIGITS = 10


def _parse_team_id(raw):
    """None if absent, an int if valid, or 'invalid' so the page can say so kindly."""
    if raw is None or raw == '':
        return None
    if not raw.isdigit() or len(raw) > MAX_TEAM_ID_DIGITS or int(raw) < 1:
        return 'invalid'
    return int(raw)
```
In `week_last_week_recap`, change the call to `get_last_week_recap(gameweek, team_id=_parse_team_id(request.args.get('team_id')))`.

Update the Task 4 route test fake to accept `team_id=None`, using the signature `def fake(gameweek, team_id=None)`.

- [ ] **Step 4:** Run `vs-env/Scripts/python.exe -m pytest -q`; everything should be green. Commit:
```bash
git add FPL_site tests features
git commit -m "Add personal last week recap: score against average and one thing done right"
```

---

### Task 8: Team-number storage and the welcome-back message

**Files:**
- Create: `FPL_site/static/scripts/lib/teamId.js`
- Create: `FPL_site/static/scripts/lib/returningUser.js`
- Test: `tests/js/teamId.test.js`, `tests/js/returningUser.test.js`

**Interfaces:**
- Produces:
  - In `teamId.js`:
    - `TEAM_ID_KEY = 'kj-fpl-team-id'`, the same key `liveGameweek.js` uses.
    - `parseTeamId(raw) -> number|null`
    - `readTeamId(storage) -> number|null`
    - `saveTeamId(storage, raw) -> number|null`
  - In `returningUser.js`:
    - `LAST_VISIT_KEY = 'kj-last-visit'`
    - `welcomeBackMessage({ lastVisitIso, lastWeekGameweek, lastWeekDeadlineIso, thisWeekGameweek }) -> string|null`
    - `readLastVisit(storage) -> string|null`
    - `recordVisit(storage, now: Date)`

- [ ] **Step 1: Failing tests.**

`tests/js/teamId.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { TEAM_ID_KEY, parseTeamId, readTeamId, saveTeamId } from '../../FPL_site/static/scripts/lib/teamId.js';

function memoryStorage(initial = {}) {
    const data = { ...initial };
    return { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); }, data };
}

test('uses the same key as the live panel', () => {
    assert.equal(TEAM_ID_KEY, 'kj-fpl-team-id');
});

test('parses valid numbers and rejects junk', () => {
    assert.equal(parseTeamId('1234567'), 1234567);
    assert.equal(parseTeamId(' 42 '), 42);
    for (const junk of ['', 'abc', '-4', '0', '1e5', '12345678901', null, undefined]) {
        assert.equal(parseTeamId(junk), null, String(junk));
    }
});

test('read and save round-trip, and junk is never stored', () => {
    const storage = memoryStorage();
    assert.equal(readTeamId(storage), null);
    assert.equal(saveTeamId(storage, 'nope'), null);
    assert.equal(storage.data[TEAM_ID_KEY], undefined);
    assert.equal(saveTeamId(storage, '777'), 777);
    assert.equal(readTeamId(storage), 777);
});

test('blocked storage never throws', () => {
    const blocked = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
    assert.equal(readTeamId(blocked), null);
    assert.equal(saveTeamId(blocked, '5'), 5);
});
```

`tests/js/returningUser.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LAST_VISIT_KEY, welcomeBackMessage, readLastVisit, recordVisit } from '../../FPL_site/static/scripts/lib/returningUser.js';

const base = { lastWeekGameweek: 5, lastWeekDeadlineIso: '2026-10-03T10:00:00Z', thisWeekGameweek: 6 };

test('first ever visit gets no message', () => {
    assert.equal(welcomeBackMessage({ ...base, lastVisitIso: null }), null);
});

test('visited after last week\'s deadline: no message', () => {
    assert.equal(welcomeBackMessage({ ...base, lastVisitIso: '2026-10-04T09:00:00Z' }), null);
});

test('away since before last week\'s deadline: warm welcome pointing at this week', () => {
    const msg = welcomeBackMessage({ ...base, lastVisitIso: '2026-09-01T09:00:00Z' });
    assert.equal(msg, "Welcome back! Gameweek 5 played out while you were away. Here's how it went, and what matters for gameweek 6.");
});

test('no upcoming gameweek (off-season) still welcomes', () => {
    const msg = welcomeBackMessage({ ...base, thisWeekGameweek: null, lastVisitIso: '2026-09-01T09:00:00Z' });
    assert.equal(msg, "Welcome back! Gameweek 5 played out while you were away. Here's how it went.");
});

test('missing or garbled data never shows a message', () => {
    assert.equal(welcomeBackMessage({ ...base, lastVisitIso: 'garbage' }), null);
    assert.equal(welcomeBackMessage({ ...base, lastWeekDeadlineIso: '', lastVisitIso: '2026-09-01T09:00:00Z' }), null);
    assert.equal(welcomeBackMessage({ ...base, lastWeekGameweek: null, lastVisitIso: '2026-09-01T09:00:00Z' }), null);
});

test('records and reads the last visit, surviving blocked storage', () => {
    const data = {};
    const storage = { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; } };
    recordVisit(storage, new Date('2026-10-06T12:00:00Z'));
    assert.equal(readLastVisit(storage), '2026-10-06T12:00:00.000Z');
    assert.equal(LAST_VISIT_KEY in data, true);
    const blocked = { getItem() { throw new Error('x'); }, setItem() { throw new Error('x'); } };
    assert.equal(readLastVisit(blocked), null);
    assert.doesNotThrow(() => recordVisit(blocked, new Date()));
});
```

Run `npm test`. Expected: FAIL, because the modules are missing.

- [ ] **Step 2: Implement.**

`FPL_site/static/scripts/lib/teamId.js`:
```js
/***** teamId.js *****/
// Remembers which Fantasy Premier League team number is the visitor's, in
// the browser only (localStorage) - it is never stored on our server.
// Uses the same key as liveGameweek.js so entering it once works everywhere.
export const TEAM_ID_KEY = 'kj-fpl-team-id';

const MAX_DIGITS = 10;

// Returns a positive whole number, or null for anything else. A regular
// expression (/^\d+$/) checks the text is digits only, which rules out
// things like "1e5" or "-4" that Number() would otherwise accept.
export function parseTeamId(raw) {
    const text = String(raw ?? '').trim();
    if (!/^\d+$/.test(text) || text.length > MAX_DIGITS) return null;
    const id = Number(text);
    return id >= 1 ? id : null;
}

// localStorage can throw (private browsing, blocked cookies), so every
// access is wrapped in try/catch and falls back to "no team known".
export function readTeamId(storage) {
    try {
        return parseTeamId(storage.getItem(TEAM_ID_KEY));
    } catch {
        return null;
    }
}

export function saveTeamId(storage, raw) {
    const id = parseTeamId(raw);
    if (id === null) return null;
    try {
        storage.setItem(TEAM_ID_KEY, String(id));
    } catch {
        // Still return the id so this page view can use it.
    }
    return id;
}
```

`FPL_site/static/scripts/lib/returningUser.js`:
```js
/***** returningUser.js *****/
// Works out whether someone has been away since before last gameweek's
// deadline, so the page can welcome them back warmly instead of assuming
// they know what happened.
export const LAST_VISIT_KEY = 'kj-last-visit';

export function welcomeBackMessage({ lastVisitIso, lastWeekGameweek, lastWeekDeadlineIso, thisWeekGameweek }) {
    if (!lastVisitIso || !lastWeekDeadlineIso || lastWeekGameweek == null) return null;

    // Date.parse turns an ISO date string into milliseconds since 1970,
    // which makes "is this before that?" a simple number comparison.
    // It returns NaN ("not a number") for text it can't read.
    const lastVisit = Date.parse(lastVisitIso);
    const deadline = Date.parse(lastWeekDeadlineIso);
    if (Number.isNaN(lastVisit) || Number.isNaN(deadline)) return null;
    if (lastVisit >= deadline) return null;

    const next = thisWeekGameweek != null ? `, and what matters for gameweek ${thisWeekGameweek}` : '';
    return `Welcome back! Gameweek ${lastWeekGameweek} played out while you were away. Here's how it went${next}.`;
}

export function readLastVisit(storage) {
    try {
        return storage.getItem(LAST_VISIT_KEY);
    } catch {
        return null;
    }
}

export function recordVisit(storage, now) {
    try {
        storage.setItem(LAST_VISIT_KEY, now.toISOString());
    } catch {
        // Not remembering a visit is harmless: they just won't get a welcome back.
    }
}
```

- [ ] **Step 3:** Run `npm test`; it should be green. Commit:
```bash
git add FPL_site/static/scripts/lib tests/js
git commit -m "Add team number storage and welcome-back message modules"
```

---

### Task 9: Personal recap rendering, team form and welcome banner

**Files:**
- Modify: `FPL_site/static/scripts/lib/recapView.js` (add `renderPersonalRecap`, `renderTeamPrompt`)
- Modify: `FPL_site/static/scripts/weekV2.js`
- Modify: `FPL_site/templates/partials/week_v2.html` (banner plus personal slot)
- Test: `tests/js/recapView.test.js`, `tests/test_week_v2_template.py`

**Interfaces:**
- Consumes:
  - The Personal payload (Task 7).
  - `readTeamId` and `saveTeamId` (Task 8).
  - `welcomeBackMessage`, `readLastVisit` and `recordVisit` (Task 8).
  - The `data-deadline` and `data-this-week-gameweek` attributes (Task 5).
- Produces:
  - `renderPersonalRecap(personal, gameweek) -> string`
  - `renderTeamPrompt() -> string`, which contains `<form id="recap-team-form">`
  - The template hooks `#welcome-back-banner` and `#personal-recap-slot`

- [ ] **Step 1: Failing JavaScript tests.** Append to `tests/js/recapView.test.js`:
```js
import { renderPersonalRecap, renderTeamPrompt } from '../../FPL_site/static/scripts/lib/recapView.js';

const personal = {
    status: 'ok', score: 61, average_score: 48, verdict: 'Above average. Nicely done.',
    verdict_tier: 'above',
    right_call: { tier: 'captain', title: 'Your captain call', reason: 'Captaining Salah paid off.' },
};

test('personal recap: verdict and right call by default, numbers in details', () => {
    const html = renderPersonalRecap(personal, 5);
    const [beforeDetails, insideDetails] = html.split('<details');
    assert.match(beforeDetails, /Above average\. Nicely done\./);
    assert.match(beforeDetails, /Your captain call/);
    assert.doesNotMatch(beforeDetails, /61/);
    assert.match(insideDetails, /You scored 61 points\. The average was 48 points\./);
});

test('personal recap: team not found shows the server message', () => {
    const html = renderPersonalRecap({ status: 'team_not_found', message: { title: "We couldn't find that team", body: 'Double-check.' } }, 5);
    assert.match(html, /couldn&#39;t find that team/);
    assert.match(html, /recap-team-form/);  // offers to try another number
});

test('team prompt has an accessible labelled input', () => {
    const html = renderTeamPrompt();
    assert.match(html, /<label for="recap-team-input"/);
    assert.match(html, /inputmode="numeric"/);
    assert.doesNotMatch(html, /\bFPL\b/);
});
```

Run `npm test`. Expected: FAIL, because the exports are missing.

- [ ] **Step 2: Implement** by appending to `recapView.js`:
```js
// Asks for the team number, explained in plain words. Shown to guests and
// after a "not found", so the user is never stuck.
export function renderTeamPrompt() {
    return `
        <div class="card" id="recap-team-card">
            <h3>See how your team did</h3>
            <form id="recap-team-form" class="recap-team-form">
                <label for="recap-team-input" class="sub">
                    Your team number is in the web address of your Fantasy Premier League team page,
                    after "/entry/".
                </label>
                <div class="recap-team-row">
                    <input type="text" inputmode="numeric" pattern="[0-9]*" id="recap-team-input"
                           placeholder="e.g. 1234567" required>
                    <button type="submit" class="btn-pill">Show my recap</button>
                </div>
            </form>
        </div>`;
}

export function renderPersonalRecap(personal, gameweek) {
    if (personal.status !== 'ok') {
        return renderMessage(personal.message) + renderTeamPrompt();
    }
    const call = personal.right_call;
    return `
        <div class="card" id="personal-recap">
            <div class="eyebrow-sm">your gameweek ${escapeHtml(gameweek)}</div>
            <h3>${escapeHtml(personal.verdict)}</h3>
            <p><strong>${escapeHtml(call.title)}:</strong> ${escapeHtml(call.reason)}</p>
            <details class="recap-details">
                <summary>See the numbers</summary>
                <p class="sub">You scored ${escapeHtml(personal.score)} points. The average was ${escapeHtml(personal.average_score)} points.</p>
            </details>
        </div>`;
}
```

Append to `home.css`:
```css
.recap-team-form label { display: block; margin-bottom: 8px; }
.recap-team-row { display: flex; gap: 8px; }
.recap-team-row input { flex: 1; min-width: 0; padding: 10px 12px; border-radius: 8px; border: 1.5px solid var(--black-20); font-family: var(--font); font-size: 16px; }
.recap-team-row input:focus-visible { outline: 2px solid var(--plum); outline-offset: 2px; }
.recap-team-row .btn-pill { width: auto; padding: 10px 18px; }
.welcome-back { border-left: 4px solid var(--teal); transition: opacity 200ms ease-in-out; }
```
The input font size is 16px so iOS doesn't zoom in.

Run `npm test`; it should be green.

- [ ] **Step 3: Template.**
  - In `week_v2.html`, insert `<div id="welcome-back-banner" class="card welcome-back" role="status" hidden></div>` as the first child of `#week-content`.
  - Inside the `{% else %}` branch of `#last-week-view`, insert `<div id="personal-recap-slot"></div>` immediately before `#last-week-recap-slot`.

Add to `tests/test_week_v2_template.py`:
```python
def test_v2_has_welcome_banner_and_personal_slot():
    html = render(_state('upcoming', gw=6, last_status='final', last_gw=5))
    assert 'id="welcome-back-banner"' in html and 'hidden' in html
    assert 'id="personal-recap-slot"' in html
```
Use the `render` and `_state` helpers that file already has. If `_state` doesn't take these keyword names, adapt the call to the helper's real signature; don't add a second helper.

- [ ] **Step 4: Glue.** Replace `weekV2.js` with:
```js
/***** weekV2.js *****/
// DOM glue for the rebuilt Week tab (behind FEATURE_WEEK_V2). All the
// decisions about *what* to show live in the pure modules under lib/; this
// file only reads the page, fetches data, and puts HTML on the page.
import { renderGuestRecap, renderPersonalRecap, renderTeamPrompt, renderMessage, RECAP_LOAD_FAILED } from './lib/recapView.js';
import { readTeamId, saveTeamId } from './lib/teamId.js';
import { welcomeBackMessage, readLastVisit, recordVisit } from './lib/returningUser.js';

export function initializeWeekV2() {
    const lastWeekView = document.getElementById('last-week-view');
    // The flag-off page has no data-week-v2 attribute, so this is a no-op there.
    if (!lastWeekView || lastWeekView.dataset.weekV2 !== 'true') return;
    showWelcomeBack(lastWeekView);
    loadLastWeekRecap(lastWeekView);
}

function showWelcomeBack(lastWeekView) {
    const banner = document.getElementById('welcome-back-banner');
    // Read the previous visit *before* recording this one.
    const message = welcomeBackMessage({
        lastVisitIso: readLastVisit(window.localStorage),
        lastWeekGameweek: lastWeekView.dataset.gameweek ? Number(lastWeekView.dataset.gameweek) : null,
        lastWeekDeadlineIso: lastWeekView.dataset.deadline || null,
        thisWeekGameweek: lastWeekView.dataset.thisWeekGameweek ? Number(lastWeekView.dataset.thisWeekGameweek) : null,
    });
    recordVisit(window.localStorage, new Date());
    if (banner && message) {
        banner.textContent = message;  // textContent never interprets HTML
        banner.hidden = false;
    }
}

async function loadLastWeekRecap(lastWeekView) {
    const gameweek = lastWeekView.dataset.gameweek;
    const guestSlot = document.getElementById('last-week-recap-slot');
    const personalSlot = document.getElementById('personal-recap-slot');
    if (!gameweek || !guestSlot) return;  // server already rendered a friendly message

    const teamId = readTeamId(window.localStorage);
    const query = new URLSearchParams({ gameweek });
    if (teamId !== null) query.set('team_id', String(teamId));

    try {
        const res = await fetch(`/api/week/last-week-recap?${query}`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();
        if (data.status !== 'ready') {
            guestSlot.innerHTML = renderMessage(data.message);
            return;
        }
        guestSlot.innerHTML = renderGuestRecap(data.guest, data.gameweek);
        if (personalSlot) {
            personalSlot.innerHTML = data.personal
                ? renderPersonalRecap(data.personal, data.gameweek)
                : renderTeamPrompt();
            bindTeamForm(lastWeekView);
        }
    } catch (err) {
        console.error('Failed to load last week recap', err);
        guestSlot.innerHTML = renderMessage(RECAP_LOAD_FAILED);
    }
}

// The form is re-created each time the slot is redrawn, so the listener is
// attached fresh every time rather than once on page load.
function bindTeamForm(lastWeekView) {
    const form = document.getElementById('recap-team-form');
    const input = document.getElementById('recap-team-input');
    if (!form || !input) return;
    form.addEventListener('submit', (event) => {
        event.preventDefault();  // stop the browser reloading the page
        if (saveTeamId(window.localStorage, input.value) === null) {
            input.setCustomValidity('Please enter the number only, for example 1234567.');
            input.reportValidity();
            return;
        }
        loadLastWeekRecap(lastWeekView);
    });
    input.addEventListener('input', () => input.setCustomValidity(''));
}
```

- [ ] **Step 5:** Run `vs-env/Scripts/python.exe -m pytest -q && npm test && node --check FPL_site/static/scripts/weekV2.js`; all green. Commit:
```bash
git add FPL_site tests
git commit -m "Show the personal recap, team number prompt and welcome back on the Week tab"
```

**Release 1.3 gate:** run the roadmap gate. The live smoke uses a real public team number:
- `curl '/api/week/last-week-recap?gameweek=5&team_id=<id>'` returns `personal.status == 'ok'`.
- `team_id=1` (very likely not to exist in that gameweek) returns a friendly not-found.
- Browser check at 375px:
  - guest prompt, then entering a number, then the personal card
  - a junk number shows the inline validation message
  - set `localStorage['kj-last-visit']` to a month ago and reload: the welcome banner appears once

---

# Release 1.4: "What matters this week" (then remove the flag)

### Task 10: Calm deadline wording

**Files:**
- Create: `FPL_site/static/scripts/lib/deadlineCopy.js`
- Test: `tests/js/deadlineCopy.test.js`

**Interfaces:**
- Produces: `describeDeadline(deadlineIso, now: Date, timeZone?: string) -> string|null`. It returns null for an unreadable deadline. Without a `timeZone`, it uses the browser's own.

- [ ] **Step 1: Failing tests.** `tests/js/deadlineCopy.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { describeDeadline } from '../../FPL_site/static/scripts/lib/deadlineCopy.js';

const TZ = 'Europe/London';
const at = (iso) => new Date(iso);

test('unreadable deadline gives null', () => {
    assert.equal(describeDeadline('nonsense', at('2026-10-06T09:00:00Z'), TZ), null);
    assert.equal(describeDeadline(null, at('2026-10-06T09:00:00Z'), TZ), null);
});

test('deadline already passed', () => {
    assert.equal(describeDeadline('2026-10-06T09:00:00Z', at('2026-10-06T09:00:00Z'), TZ),
        'The deadline has passed. Your team is locked in for this gameweek.');
});

test('under an hour: calm, not alarming', () => {
    assert.equal(describeDeadline('2026-10-06T10:00:00Z', at('2026-10-06T09:01:00Z'), TZ),
        "Under an hour to go. If you change nothing, your team stays as it is.");
});

test('later today, formats in the given time zone', () => {
    // 17:30 UTC is 18:30 in London during summer time.
    assert.equal(describeDeadline('2026-10-06T17:30:00Z', at('2026-10-06T09:00:00Z'), TZ),
        "Deadline's today at 18:30.");
});

test('tomorrow', () => {
    assert.equal(describeDeadline('2026-10-07T17:30:00Z', at('2026-10-06T09:00:00Z'), TZ),
        "Deadline's tomorrow at 18:30.");
});

test('a few days away', () => {
    assert.equal(describeDeadline('2026-10-09T17:30:00Z', at('2026-10-06T09:00:00Z'), TZ),
        'About 3 days to go. Plenty of time.');
});

test('over a week away', () => {
    assert.equal(describeDeadline('2026-10-20T17:30:00Z', at('2026-10-06T09:00:00Z'), TZ),
        'Over a week to go. Plenty of time.');
});
```

Run `npm test`. Expected: FAIL.

- [ ] **Step 2: Implement** `FPL_site/static/scripts/lib/deadlineCopy.js`:
```js
/***** deadlineCopy.js *****/
// Turns the deadline into calm, human wording ("Deadline's tomorrow at
// 18:30") instead of a ticking countdown. Times are shown in the visitor's
// own time zone unless one is passed in (tests pass one so they're stable).
const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

// "2026-10-06" for a date as seen in a given time zone. Intl.DateTimeFormat
// is the browser's built-in date formatter; 'en-CA' happens to format dates
// as year-month-day, which makes two days easy to compare as text.
function dayKey(date, timeZone) {
    return new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
}

function clockTime(date, timeZone) {
    return new Intl.DateTimeFormat('en-GB', { timeZone, hour: '2-digit', minute: '2-digit' }).format(date);
}

export function describeDeadline(deadlineIso, now, timeZone = undefined) {
    const deadline = new Date(deadlineIso ?? '');
    if (deadlineIso == null || Number.isNaN(deadline.getTime())) return null;

    const remaining = deadline.getTime() - now.getTime();
    if (remaining <= 0) return 'The deadline has passed. Your team is locked in for this gameweek.';
    if (remaining < HOUR_MS) return 'Under an hour to go. If you change nothing, your team stays as it is.';

    const deadlineDay = dayKey(deadline, timeZone);
    if (deadlineDay === dayKey(now, timeZone)) return `Deadline's today at ${clockTime(deadline, timeZone)}.`;
    if (deadlineDay === dayKey(new Date(now.getTime() + DAY_MS), timeZone)) {
        return `Deadline's tomorrow at ${clockTime(deadline, timeZone)}.`;
    }
    if (remaining < 7 * DAY_MS) return `About ${Math.round(remaining / DAY_MS)} days to go. Plenty of time.`;
    return 'Over a week to go. Plenty of time.';
}
```

`Math.round` of 3.35 days is 3, which matches the test.

- [ ] **Step 3:** Run `npm test`; it should be green. Commit: `git add FPL_site/static/scripts/lib/deadlineCopy.js tests/js/deadlineCopy.test.js && git commit -m "Add calm deadline wording module"`.

---

### Task 11: Biggest-decision data and chooser

**Files:**
- Create: `FPL_site/weekDecision.py` (fetchers, pure chooser, orchestrator)
- Create: `FPL_site/decisionCopy.py` (phrase bank)
- Create: `features/week/biggest_decision.feature`
- Create: `tests/step_defs/test_biggest_decision.py`
- Create: `tests/test_decision_copy.py`
- Create: `tests/test_week_decision.py`

**Interfaces:**
- Consumes:
  - `dataModels.connect_db`, `season_start` and `get_entry_picks`.
  - The tables `bootstrapstatic_elements` (latest `gameweek` snapshot: `id`, `web_name`, `team`, `chance_of_playing_next_round`, `news`), `player_predictions` (`player_id`, `predicted_performance`, `gameweek`), `fixtures_fixtures` (`event`, `team_h`, `team_a`, `team_h_difficulty`, `team_a_difficulty`) and `bootstrapstatic_teams` (`id`, `name`).
- Produces:
  - `fixtures_by_team(rows) -> {team_id: {'opponent': str, 'is_home': bool, 'difficulty': int}}`
  - `biggest_decision(squad, availability, predictions, fixtures) -> Decision|None`, where:
    - squad = `[{'id', 'is_captain', 'multiplier'}]`
    - availability = `{id: {'name', 'team', 'chance': int|None, 'news': str}}`
    - predictions = `{id: float}`
  - `guest_biggest_decision(availability, predictions, fixtures) -> Decision|None`
  - Decision = `{'kind': 'availability'|'captain', 'title': str, 'reason': str, 'details': [str, ...]}`
  - `get_this_week_decision(gameweek, last_gameweek, team_id=None) -> {'gameweek', 'based_on': 'your_team'|'everyone', 'squad_gameweek': int|None, 'decision': Decision|None, 'message': {'title', 'body'}|None}`
  - `DOUBT_BELOW = 75`

- [ ] **Step 1: Scenarios** — `features/week/biggest_decision.feature`:
```gherkin
Feature: The single biggest decision this week
  Before the deadline, the Week tab offers one decision with a reason, framed as the user's call.

  Background:
    Given this week's fixtures

  Scenario: A starter is a doubt
    Given my starter "Saka" has a 25 percent chance of playing because "Hamstring injury"
    And my captain is "Haaland"
    When the biggest decision is chosen
    Then the decision kind is "availability"
    And the reason mentions "Saka"
    And the reason ends with "your call."

  Scenario: Everyone is fit, so it's the captain choice
    Given my captain is "Haaland"
    And our prediction ranks "Salah" above "Haaland"
    When the biggest decision is chosen
    Then the decision kind is "captain"
    And the reason mentions "Salah"

  Scenario: No predictions yet
    Given my captain is "Haaland"
    And there are no predictions
    When the biggest decision is chosen
    Then there is no decision

  Scenario: A returning guest with no team number
    Given there is no team
    And our prediction ranks "Salah" above "Haaland"
    When the guest decision is chosen
    Then the decision kind is "captain"
    And the reason mentions "Salah"
```

- [ ] **Step 2: Failing tests.**

`tests/step_defs/test_biggest_decision.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.weekDecision import biggest_decision, guest_biggest_decision

scenarios('week/biggest_decision.feature')

IDS = {'Saka': 1, 'Haaland': 2, 'Salah': 3}
TEAMS = {'Saka': 10, 'Haaland': 20, 'Salah': 30}


@given("this week's fixtures", target_fixture='ctx')
def this_weeks_fixtures():
    return {'squad': [], 'availability': {}, 'predictions': {IDS['Haaland']: 7.0, IDS['Salah']: 6.0},
            'fixtures': {10: {'opponent': 'Everton', 'is_home': True, 'difficulty': 2},
                         20: {'opponent': 'Burnley', 'is_home': False, 'difficulty': 2},
                         30: {'opponent': 'Arsenal', 'is_home': True, 'difficulty': 4}}}


@given(parsers.parse('my starter "{name}" has a {chance:d} percent chance of playing because "{news}"'))
def doubtful_starter(ctx, name, chance, news):
    add_player(ctx, name, chance=chance, news=news)


@given(parsers.parse('my captain is "{name}"'))
def captain(ctx, name):
    add_player(ctx, name, captain=True)


@given(parsers.parse('our prediction ranks "{better}" above "{worse}"'))
def ranking(ctx, better, worse):
    for name in (better, worse):
        add_player(ctx, name)
    ctx['predictions'] = {IDS[better]: 8.0, IDS[worse]: 6.0}


@given('there are no predictions')
def no_predictions(ctx):
    ctx['predictions'] = {}


@given('there is no team')
def no_team(ctx):
    ctx['squad'] = []


@when('the biggest decision is chosen')
def choose(ctx):
    ctx['result'] = biggest_decision(ctx['squad'], ctx['availability'], ctx['predictions'], ctx['fixtures'])


@when('the guest decision is chosen')
def choose_guest(ctx):
    ctx['result'] = guest_biggest_decision(ctx['availability'], ctx['predictions'], ctx['fixtures'])


@then(parsers.parse('the decision kind is "{kind}"'))
def kind(ctx, kind):
    assert ctx['result']['kind'] == kind


@then(parsers.parse('the reason mentions "{text}"'))
def mentions(ctx, text):
    assert text in ctx['result']['reason']


@then(parsers.parse('the reason ends with "{text}"'))
def ends(ctx, text):
    assert ctx['result']['reason'].endswith(text)


@then('there is no decision')
def none(ctx):
    assert ctx['result'] is None


def add_player(ctx, name, chance=None, news='', captain=False):
    """Known to the game (availability) and in my squad as a starter."""
    pid = IDS[name]
    ctx['availability'].setdefault(pid, {'name': name, 'team': TEAMS[name], 'chance': chance, 'news': news})
    if not any(p['id'] == pid for p in ctx['squad']):
        ctx['squad'].append({'id': pid, 'is_captain': captain, 'multiplier': 2 if captain else 1})
```

`tests/test_decision_copy.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import re

import pytest

from FPL_site.decisionCopy import (
    fixture_phrase, availability_decision, captain_decision, guest_captain_decision, no_decision_copy,
)

ACRONYMS = re.compile(r'\b(FPL|GW|XG|XA|ICT|DGW|BGW)\b', re.I)


@pytest.mark.parametrize('fixture,expected', [
    (None, ''),
    ({'opponent': 'Everton', 'is_home': True, 'difficulty': 2}, ', with a kind fixture at home to Everton'),
    ({'opponent': 'Everton', 'is_home': False, 'difficulty': 2}, ', with a kind fixture away at Everton'),
    ({'opponent': 'Villa', 'is_home': True, 'difficulty': 3}, ', at home to Villa'),
    ({'opponent': 'City', 'is_home': False, 'difficulty': 4}, ', even with a tough fixture away at City'),
])
def test_fixture_phrase_tiers(fixture, expected):
    assert fixture_phrase(fixture) == expected


@pytest.mark.parametrize('chance,phrase', [(0, 'is set to miss this week'), (25, 'is a doubt this week'),
                                           (74, 'is a doubt this week')])
def test_availability_wording(chance, phrase):
    d = availability_decision('Saka', chance, 'Hamstring injury')
    assert phrase in d['reason'] and d['reason'].endswith('your call.')
    assert d['details'] == [f'Chance of playing: {chance}%', 'Latest news: Hamstring injury']


def test_availability_without_news():
    d = availability_decision('Saka', 50, '')
    assert '()' not in d['reason'] and d['details'] == ['Chance of playing: 50%']


def test_captain_same_vs_switch():
    fixture = {'opponent': 'Everton', 'is_home': True, 'difficulty': 2}
    same = captain_decision('Haaland', 7.04, 'Haaland', fixture)
    assert same['title'] == 'Captain: Haaland looks right'
    assert same['details'] == ['Our prediction for Haaland: about 7.0 points']
    switch = captain_decision('Salah', 8.0, 'Haaland', fixture)
    assert switch['title'] == 'Captain: worth a look at Salah' and 'ahead of Haaland' in switch['reason']


def test_guest_and_empty_copy():
    g = guest_captain_decision('Salah', 8.0, None)
    assert g['reason'].endswith('your call.')
    for text in [g['title'], g['reason'], *no_decision_copy().values()]:
        assert not ACRONYMS.search(text)
```

`tests/test_week_decision.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.weekDecision import fixtures_by_team, biggest_decision, guest_biggest_decision, DOUBT_BELOW


def test_fixtures_by_team_maps_both_sides_and_keeps_first_of_double():
    rows = [
        {'team_h': 1, 'team_a': 2, 'team_h_difficulty': 2, 'team_a_difficulty': 4, 'home_name': 'Arsenal', 'away_name': 'Chelsea'},
        {'team_h': 3, 'team_a': 1, 'team_h_difficulty': 3, 'team_a_difficulty': 3, 'home_name': 'Spurs', 'away_name': 'Arsenal'},
    ]
    fx = fixtures_by_team(rows)
    assert fx[1] == {'opponent': 'Chelsea', 'is_home': True, 'difficulty': 2}
    assert fx[2] == {'opponent': 'Arsenal', 'is_home': False, 'difficulty': 4}


def availability(*players):
    return {pid: {'name': name, 'team': team, 'chance': chance, 'news': ''} for pid, name, team, chance in players}


def test_doubt_threshold_boundary():
    squad = [{'id': 1, 'is_captain': True, 'multiplier': 2}]
    fixtures = {10: {'opponent': 'X', 'is_home': True, 'difficulty': 3}}
    at_threshold = availability((1, 'A', 10, DOUBT_BELOW))
    below = availability((1, 'A', 10, DOUBT_BELOW - 1))
    assert biggest_decision(squad, at_threshold, {1: 5.0}, fixtures)['kind'] == 'captain'
    assert biggest_decision(squad, below, {1: 5.0}, fixtures)['kind'] == 'availability'


def test_bench_doubts_are_ignored_and_most_doubtful_starter_wins():
    squad = [{'id': 1, 'is_captain': False, 'multiplier': 1},
             {'id': 2, 'is_captain': False, 'multiplier': 1},
             {'id': 3, 'is_captain': False, 'multiplier': 0}]
    avail = availability((1, 'A', 10, 50), (2, 'B', 10, 25), (3, 'C', 10, 0))
    d = biggest_decision(squad, avail, {}, {})
    assert d['kind'] == 'availability' and 'B' in d['reason']


def test_players_without_a_fixture_are_not_captain_options():
    squad = [{'id': 1, 'is_captain': True, 'multiplier': 2}, {'id': 2, 'is_captain': False, 'multiplier': 1}]
    avail = availability((1, 'A', 10, None), (2, 'B', 20, None))
    fixtures = {10: {'opponent': 'X', 'is_home': True, 'difficulty': 3}}  # team 20 has no game
    d = biggest_decision(squad, avail, {1: 5.0, 2: 9.0}, fixtures)
    assert d['title'] == 'Captain: A looks right'


def test_guest_skips_doubtful_players():
    avail = availability((1, 'Hurt', 10, 25), (2, 'Fit', 10, None))
    fixtures = {10: {'opponent': 'X', 'is_home': True, 'difficulty': 3}}
    d = guest_biggest_decision(avail, {1: 9.0, 2: 6.0}, fixtures)
    assert 'Fit' in d['reason']


def test_empty_inputs_give_none():
    assert biggest_decision([], {}, {}, {}) is None
    assert guest_biggest_decision({}, {}, {}) is None
```

Run the suite. Expected: FAIL with ImportErrors.

- [ ] **Step 3: Implement** `FPL_site/decisionCopy.py`:
```python
"""Deterministic phrase bank for the Week tab's biggest decision.

Every decision is framed as the user's call, and always carries a reason.
"""

KIND_FIXTURE_UP_TO = 2
TOUGH_FIXTURE_FROM = 4


def fixture_phrase(fixture):
    if not fixture:
        return ''
    where = f"at home to {fixture['opponent']}" if fixture['is_home'] else f"away at {fixture['opponent']}"
    if fixture['difficulty'] <= KIND_FIXTURE_UP_TO:
        return f', with a kind fixture {where}'
    if fixture['difficulty'] >= TOUGH_FIXTURE_FROM:
        return f', even with a tough fixture {where}'
    return f', {where}'


def availability_decision(name, chance, news):
    status = 'is set to miss this week' if chance == 0 else 'is a doubt this week'
    details = [f'Chance of playing: {chance}%']
    if news:
        details.append(f'Latest news: {news}')
    return {'kind': 'availability', 'title': f'Have a look at {name}',
            'reason': f"We're seeing that {name} {status}. Worth deciding whether to bring in "
                      f"cover, or keep faith. It's your call.",
            'details': details}


def captain_decision(best_name, best_prediction, current_name, fixture):
    details = [f'Our prediction for {best_name}: about {best_prediction:.1f} points']
    where = fixture_phrase(fixture)
    if best_name == current_name:
        return {'kind': 'captain', 'title': f'Captain: {best_name} looks right',
                'reason': f"We're seeing {best_name} as your strongest option{where}. Sticking "
                          f"with them looks sound. It's your call.",
                'details': details}
    return {'kind': 'captain', 'title': f'Captain: worth a look at {best_name}',
            'reason': f"We're seeing {best_name} as your strongest option{where}, ahead of "
                      f"{current_name}. It's your call.",
            'details': details}


def guest_captain_decision(best_name, best_prediction, fixture):
    return {'kind': 'captain', 'title': f'Captain: {best_name} stands out',
            'reason': f"Across every team, {best_name} is the strongest option we're "
                      f"seeing{fixture_phrase(fixture)}. If you have them, they're worth a "
                      f"look as captain. It's your call.",
            'details': [f'Our prediction for {best_name}: about {best_prediction:.1f} points']}


def no_decision_copy():
    return {'title': 'Nothing pressing yet',
            'body': "We're still working out this week's picture. Check back closer to the deadline."}
```

Note on the scenarios: the tests use `.endswith('your call.')`, and every reason ends with "It's your call." Python's `endswith('your call.')` matches that.

`FPL_site/weekDecision.py`:
```python
"""The single biggest decision for the Week tab (release 1.4).

Fetchers read the database; the choosing is pure and tested with dicts.
"""
import logging

from FPL_site.dataModels import connect_db, season_start, get_entry_picks
from FPL_site.decisionCopy import (
    availability_decision, captain_decision, guest_captain_decision, no_decision_copy,
)

logger = logging.getLogger(__name__)

DOUBT_BELOW = 75   # chance of playing under this % makes a starter a doubt


#################################################
#                  Fetchers                     #
#################################################

def fetch_availability_rows(cursor, year_start):
    cursor.execute("""
        SELECT id, web_name, team, chance_of_playing_next_round, news
        FROM bootstrapstatic_elements
        WHERE year_start = %s
          AND gameweek = (SELECT MAX(gameweek) FROM bootstrapstatic_elements WHERE year_start = %s)
    """, (year_start, year_start))
    return cursor.fetchall()


def fetch_prediction_rows(cursor):
    cursor.execute("""
        SELECT player_id, predicted_performance FROM player_predictions
        WHERE gameweek = (SELECT MAX(gameweek) FROM player_predictions)
    """)
    return cursor.fetchall()


def fetch_fixture_rows(cursor, year_start, gameweek):
    cursor.execute("""
        SELECT f.team_h, f.team_a, f.team_h_difficulty, f.team_a_difficulty,
               th.name AS home_name, ta.name AS away_name
        FROM fixtures_fixtures f
        JOIN bootstrapstatic_teams th ON th.id = f.team_h AND th.year_start = f.year_start
        JOIN bootstrapstatic_teams ta ON ta.id = f.team_a AND ta.year_start = f.year_start
        WHERE f.year_start = %s AND f.event = %s
        ORDER BY f.kickoff_time
    """, (year_start, gameweek))
    return cursor.fetchall()


#################################################
#                 Pure shaping                  #
#################################################

def availability_from_rows(rows):
    return {r['id']: {'name': r['web_name'], 'team': r['team'],
                      'chance': r['chance_of_playing_next_round'], 'news': r['news'] or ''}
            for r in rows}


def predictions_from_rows(rows):
    return {r['player_id']: float(r['predicted_performance'])
            for r in rows if r['predicted_performance'] is not None}


def squad_from_picks(picks_data):
    """The official picks list uses 'element' for the player id; we use 'id'."""
    return [{'id': p['element'], 'is_captain': bool(p.get('is_captain')),
             'multiplier': p.get('multiplier', 0)}
            for p in (picks_data or {}).get('picks', [])]


def fixtures_by_team(rows):
    """Each team's first fixture of the gameweek. A team with no game is absent."""
    fixtures = {}
    for r in rows:
        fixtures.setdefault(r['team_h'], {'opponent': r['away_name'], 'is_home': True,
                                          'difficulty': r['team_h_difficulty']})
        fixtures.setdefault(r['team_a'], {'opponent': r['home_name'], 'is_home': False,
                                          'difficulty': r['team_a_difficulty']})
    return fixtures


#################################################
#                Pure choosing                  #
#################################################

def _is_doubt(player):
    return player['chance'] is not None and player['chance'] < DOUBT_BELOW


def _most_doubtful_starter(squad, availability):
    doubts = [(availability[p['id']], p) for p in squad
              if p['multiplier'] > 0 and p['id'] in availability and _is_doubt(availability[p['id']])]
    if not doubts:
        return None
    # Lowest chance first; the captain wins a tie; then name for stability.
    return min(doubts, key=lambda d: (d[0]['chance'], not d[1]['is_captain'], d[0]['name']))[0]


def _best_option(player_ids, availability, predictions, fixtures):
    options = [pid for pid in player_ids
               if pid in predictions and pid in availability
               and availability[pid]['team'] in fixtures and not _is_doubt(availability[pid])]
    if not options:
        return None
    return min(options, key=lambda pid: (-predictions[pid], availability[pid]['name']))


def biggest_decision(squad, availability, predictions, fixtures):
    doubt = _most_doubtful_starter(squad, availability)
    if doubt:
        return availability_decision(doubt['name'], doubt['chance'], doubt['news'])

    starters = [p['id'] for p in squad if p['multiplier'] > 0]
    best = _best_option(starters, availability, predictions, fixtures)
    if best is None:
        return None
    captain = next((p['id'] for p in squad if p['is_captain']), None)
    current_name = availability.get(captain, {}).get('name', availability[best]['name'])
    return captain_decision(availability[best]['name'], predictions[best], current_name,
                            fixtures.get(availability[best]['team']))


def guest_biggest_decision(availability, predictions, fixtures):
    best = _best_option(list(predictions), availability, predictions, fixtures)
    if best is None:
        return None
    return guest_captain_decision(availability[best]['name'], predictions[best],
                                  fixtures.get(availability[best]['team']))


#################################################
#          Live-route entry point               #
#################################################

def get_this_week_decision(gameweek, last_gameweek, team_id=None):
    """team_id: int, None for a guest, or 'invalid' (treated as a guest)."""
    conn = connect_db()
    if conn is None:
        logger.error("get_this_week_decision: could not connect to the database.")
        return {'gameweek': gameweek, 'based_on': 'everyone', 'squad_gameweek': None,
                'decision': None, 'message': no_decision_copy()}
    try:
        cursor = conn.cursor(dictionary=True)
        availability = availability_from_rows(fetch_availability_rows(cursor, season_start))
        predictions = predictions_from_rows(fetch_prediction_rows(cursor))
        fixtures = fixtures_by_team(fetch_fixture_rows(cursor, season_start, gameweek))
    finally:
        conn.close()

    # Upcoming picks are private until the deadline, so use the most recent
    # finished gameweek's team as the best known version of the squad.
    picks = (get_entry_picks(team_id, last_gameweek)
             if isinstance(team_id, int) and last_gameweek else None)
    squad = squad_from_picks(picks)
    if squad:
        decision = biggest_decision(squad, availability, predictions, fixtures)
        based_on, squad_gameweek = 'your_team', last_gameweek
    else:
        decision = guest_biggest_decision(availability, predictions, fixtures)
        based_on, squad_gameweek = 'everyone', None
    return {'gameweek': gameweek, 'based_on': based_on, 'squad_gameweek': squad_gameweek,
            'decision': decision, 'message': None if decision else no_decision_copy()}
```

Add to `tests/test_week_decision.py`, and include it in the Step 2 failing run:
```python
from FPL_site.weekDecision import squad_from_picks


def test_squad_from_picks_maps_official_keys():
    picks = {'picks': [{'element': 9, 'is_captain': True, 'multiplier': 2}]}
    assert squad_from_picks(picks) == [{'id': 9, 'is_captain': True, 'multiplier': 2}]
    assert squad_from_picks(None) == []
```

- [ ] **Step 4: Read-only check against the real database.** Run:
`KJ_SKIP_DB_INIT=1 vs-env/Scripts/python.exe -c "from FPL_site.weekDecision import get_this_week_decision; print(get_this_week_decision(6, 5))"`
Expected: a guest captain decision naming a real player. Fix the SQL if it errors, and add a FakeCursor test for the fix.

- [ ] **Step 5:** Run `vs-env/Scripts/python.exe -m pytest -q`; everything should be green. Commit:
```bash
git add FPL_site/weekDecision.py FPL_site/decisionCopy.py features/week/biggest_decision.feature tests
git commit -m "Choose the single biggest decision for the week, with a reason"
```

---

### Task 12: Decision route and the hub card

**Files:**
- Modify: `FPL_site/views.py` (a new route)
- Create: `FPL_site/static/scripts/lib/decisionView.js`
- Modify: `FPL_site/static/scripts/weekV2.js`
- Modify: `FPL_site/templates/partials/week_v2.html` (`#gw-panel-closed`)
- Test: `tests/test_week_decision_route.py`, `tests/js/decisionView.test.js`, `tests/test_regression_routes.py`

**Interfaces:**
- Consumes: `get_this_week_decision`, `_parse_gameweek` and `_parse_team_id` (Tasks 4 and 7), `describeDeadline` (Task 10), and `readTeamId` (Task 8).
- Produces:
  - `GET /api/week/this-week-decision?gameweek=6&last_gameweek=5[&team_id=]`. It returns 200, or 400 with `{'error': 'invalid_gameweek'}`. `last_gameweek` is optional.
  - `renderDecision(payload) -> string`

- [ ] **Step 1: Failing tests.**

`tests/test_week_decision_route.py`:
```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import app
import FPL_site.views as views


@pytest.fixture
def client():
    return app.test_client()


def test_decision_route_passes_arguments(client, monkeypatch):
    seen = {}

    def fake(gameweek, last_gameweek, team_id=None):
        seen.update(gameweek=gameweek, last_gameweek=last_gameweek, team_id=team_id)
        return {'gameweek': gameweek, 'based_on': 'everyone', 'squad_gameweek': None,
                'decision': None, 'message': {'title': 't', 'body': 'b'}}

    monkeypatch.setattr(views, 'get_this_week_decision', fake)
    resp = client.get('/api/week/this-week-decision?gameweek=6&last_gameweek=5&team_id=42')
    assert resp.status_code == 200
    assert seen == {'gameweek': 6, 'last_gameweek': 5, 'team_id': 42}


def test_decision_route_without_last_gameweek(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(views, 'get_this_week_decision',
                        lambda gameweek, last_gameweek, team_id=None: seen.update(last=last_gameweek) or {})
    client.get('/api/week/this-week-decision?gameweek=1')
    assert seen['last'] is None


@pytest.mark.parametrize('query', ['', '?gameweek=x', '?gameweek=40'])
def test_decision_route_rejects_bad_gameweek(client, query):
    assert client.get('/api/week/this-week-decision' + query).status_code == 400
```

`tests/js/decisionView.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderDecision } from '../../FPL_site/static/scripts/lib/decisionView.js';

const decision = {
    kind: 'captain', title: 'Captain: Salah stands out',
    reason: "Across every team, Salah is the strongest option we're seeing. It's your call.",
    details: ['Our prediction for Salah: about 8.0 points'],
};

test('decision shows title and reason by default, numbers in details', () => {
    const html = renderDecision({ decision, based_on: 'everyone', squad_gameweek: null });
    const [before, inside] = html.split('<details');
    assert.match(before, /Captain: Salah stands out/);
    assert.match(before, /your call/);
    assert.doesNotMatch(before, /8\.0/);
    assert.match(inside, /about 8\.0 points/);
});

test('says which team it is based on', () => {
    const html = renderDecision({ decision, based_on: 'your_team', squad_gameweek: 5 });
    assert.match(html, /Based on your team from gameweek 5/);
});

test('no decision shows the calm message', () => {
    const html = renderDecision({ decision: null, message: { title: 'Nothing pressing yet', body: 'Check back.' } });
    assert.match(html, /Nothing pressing yet/);
});

test('icon is paired with a text label, never colour alone', () => {
    const html = renderDecision({ decision: { ...decision, kind: 'availability' }, based_on: 'everyone' });
    assert.match(html, /aria-hidden="true"/);
    assert.match(html, /Player availability/);
});
```

Run both suites. Expected: FAIL.

- [ ] **Step 2: Route.** Add `from .weekDecision import get_this_week_decision` to `views.py`, then:
```python
@app.route('/api/week/this-week-decision')
def week_this_week_decision():
    logger.info("Request for this week's decision")
    gameweek = _parse_gameweek(request.args.get('gameweek', ''))
    if gameweek is None:
        return jsonify({'error': 'invalid_gameweek'}), 400
    last_gameweek = _parse_gameweek(request.args.get('last_gameweek', ''))
    team_id = _parse_team_id(request.args.get('team_id'))
    try:
        return jsonify(get_this_week_decision(gameweek, last_gameweek, team_id=team_id))
    except Exception as e:
        logger.error(f"Error building this week's decision: {e}")
        return jsonify({'error': 'server_error'}), 500
```

Add to `DATA_ROUTE_STUBS` in `tests/test_regression_routes.py`:
```python
    '/api/week/this-week-decision?gameweek=6&last_gameweek=5': ('get_this_week_decision', {
        'gameweek': 6, 'based_on': 'everyone', 'squad_gameweek': None, 'decision': None,
        'message': {'title': 't', 'body': 'b'}}),
```

- [ ] **Step 3: View module.** `FPL_site/static/scripts/lib/decisionView.js`:
```js
/***** decisionView.js *****/
// Turns the week's biggest decision into HTML. Pure: no DOM access.
import { escapeHtml } from './escapeHtml.js';
import { renderMessage } from './recapView.js';

// Each kind gets an icon AND a word, so meaning never depends on colour alone.
// aria-hidden hides the decorative icon from screen readers; they read the word.
const KIND_LABELS = {
    availability: { icon: '🩹', label: 'Player availability' },
    captain: { icon: '⭐', label: 'Captain choice' },
};

export function renderDecision(payload) {
    if (!payload.decision) return renderMessage(payload.message);
    const d = payload.decision;
    const kind = KIND_LABELS[d.kind] || { icon: '•', label: 'Decision' };
    const basedOn = payload.based_on === 'your_team' && payload.squad_gameweek
        ? `<p class="sub">Based on your team from gameweek ${escapeHtml(payload.squad_gameweek)}.</p>`
        : '';
    const details = (d.details || []).map((line) => `<li>${escapeHtml(line)}</li>`).join('');
    return `
        <div class="card" id="week-decision">
            <div class="eyebrow-sm"><span aria-hidden="true">${kind.icon}</span> ${kind.label}</div>
            <h3>${escapeHtml(d.title)}</h3>
            <p>${escapeHtml(d.reason)}</p>
            ${basedOn}
            <details class="recap-details">
                <summary>See the numbers</summary>
                <ul class="recap-standouts">${details}</ul>
            </details>
        </div>`;
}
```

- [ ] **Step 4: Template.** Replace the inside of `#gw-panel-closed` in `week_v2.html` with:
```html
                <div class="eyebrow-sm">gameweek {{ this_week.gameweek }}</div>
                <h2 class="title" style="margin-bottom:4px;">Your decisions for gameweek {{ this_week.gameweek }}</h2>
                {# Calm deadline wording, written by weekV2.js in the visitor's own time zone #}
                <p class="sub" id="deadline-copy" data-deadline="{{ this_week.deadline or '' }}"></p>

                <div id="decision-hub"
                     data-gameweek="{{ this_week.gameweek if this_week.gameweek is not none else '' }}"
                     data-last-gameweek="{{ last_week.gameweek if last_week.status == 'final' else '' }}">
                    <h3 style="margin-top:12px;">This week's decisions</h3>
                    <div id="decision-slot">
                        <div class="card" aria-busy="true" aria-label="Loading this week's decision">
                            <div class="skeleton" style="height:18px; width:55%; margin-bottom:10px;"></div>
                            <div class="skeleton" style="height:14px; width:85%;"></div>
                        </div>
                    </div>
                    <p class="sub">More decisions are on the way. We'll add them here as they're ready.</p>
                </div>
```
Update `tests/test_week_v2_template.py`:
- Replace assertions on "5 decisions" or "Coming soon" with:
  - `'id="decision-hub"' in html`
  - `'data-gameweek="6"' in html`
  - `'data-last-gameweek="5"' in html`
- Add `assert 'Coming soon' not in html` for the upcoming mode.

- [ ] **Step 5: Glue.** In `weekV2.js`:
  - Add the imports `import { renderDecision } from './lib/decisionView.js';` and `import { describeDeadline } from './lib/deadlineCopy.js';`.
  - Add the calls `showDeadline();` and `loadDecision();` at the end of `initializeWeekV2()`.
  - Add the functions:
```js
function showDeadline() {
    const el = document.getElementById('deadline-copy');
    if (!el || !el.dataset.deadline) return;
    // No time zone passed, so the browser shows the visitor's local time.
    el.textContent = describeDeadline(el.dataset.deadline, new Date()) || '';
}

async function loadDecision() {
    const hub = document.getElementById('decision-hub');
    const slot = document.getElementById('decision-slot');
    if (!hub || !slot || !hub.dataset.gameweek) return;

    const query = new URLSearchParams({ gameweek: hub.dataset.gameweek });
    if (hub.dataset.lastGameweek) query.set('last_gameweek', hub.dataset.lastGameweek);
    const teamId = readTeamId(window.localStorage);
    if (teamId !== null) query.set('team_id', String(teamId));

    try {
        const res = await fetch(`/api/week/this-week-decision?${query}`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        slot.innerHTML = renderDecision(await res.json());
    } catch (err) {
        console.error("Failed to load this week's decision", err);
        slot.innerHTML = renderMessage({
            title: "We couldn't load this week's decision",
            body: 'Nothing is wrong on your side. Try again in a moment.',
        });
    }
}
```
  - In `bindTeamForm`, after a successful save, also call `loadDecision();`, so entering a team number on Last week also personalises This week.

- [ ] **Step 6:** Run `vs-env/Scripts/python.exe -m pytest -q && npm test && node --check FPL_site/static/scripts/weekV2.js`; all green. Commit:
```bash
git add FPL_site tests
git commit -m "Show calm deadline wording and the biggest decision in the Week hub"
```

---

### Task 13: Remove the flag and the old Week code

**Files:**
- Modify: `FPL_site/templates/home.html`
- Modify: `FPL_site/views.py` (`home()`)
- Modify: `FPL_site/config.py`
- Modify: `FPL_site/static/scripts/home.js`
- Modify: `FPL_site/static/scripts/weekV2.js`
- Modify: `FPL_site/templates/partials/week_v2.html`
- Update: `tests/test_regression_routes.py`, `tests/test_week_route.py`, `tests/test_week_v2_template.py`

**Interfaces:**
- Produces: `/this-week` always renders the v2 page, and makes one Fantasy Premier League API call per request (`get_week_view_state`).
- Unchanged: `get_gameweek_state()` stays in `dataModels.py`. It is outside this release's scope; only the call in `home()` is removed.
- Unchanged: the `/api/top-5-players` route stays, because Radar uses it.

- [ ] **Step 1: Turn the regression tests into the post-flag expectation first (failing).** In `tests/test_regression_routes.py`:
  - Delete `test_flag_off_week_page_keeps_existing_markers` and `test_flag_off_week_page_fetches_state_once`.
  - Remove the `flag` parametrisation, and stop calling `set_flag` in the remaining tests.
  - Add:
```python
def test_week_page_is_v2_without_any_flag(client, calls):
    html = client.get('/this-week').get_data(as_text=True)
    for marker in ['data-week-v2="true"', 'id="decision-hub"', 'id="gw-panel-live"',
                   'id="live-team-id-form"', 'scripts/home.js', 'content/home.css']:
        assert marker in html, marker
    assert 'Friend activity feed' not in html and 'Team of the Week' not in html
    assert calls == ['get_week_view_state']
```
In `tests/test_week_route.py`, delete the flag-off test and drop the `FEATURE_WEEK_V2` monkeypatching from the others. In `tests/test_week_v2_template.py`, delete the flag-off `home.html` test.

Run: `vs-env/Scripts/python.exe -m pytest -q`. Expected: `test_week_page_is_v2_without_any_flag` FAILS, because the flag defaults off.

- [ ] **Step 2: Remove the flag.**
  - **`home.html`:** the content block becomes exactly:
```html
{% block content %}
{% include 'partials/week_v2.html' %}

<link rel="stylesheet" href="{{ url_for('static', filename='content/home.css') }}">
<script type="module" src="{{ url_for('static', filename='scripts/home.js') }}"></script>
{% endblock %}
```
  - **`views.py` `home()`:**
```python
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('home.html', is_ajax=is_ajax, title='This Week', year=datetime.now().year,
                           mixpanel_token=current_config.MIXPANEL_TOKEN, **_week_v2_context())
```
    Remove `get_gameweek_state` from the `views.py` import list only if nothing else in `views.py` uses it (`grep -n get_gameweek_state FPL_site/views.py`). Also delete its monkeypatch from the test fixtures.
  - **`config.py`:** delete both `FEATURE_WEEK_V2` lines.
  - **`home.js`:** delete `fetchAlexData`, `renderTotw`, and the `fetchAlexData();` call inside `updateUI`.
  - **`weekV2.js`:** keep the `data-week-v2` guard. It still protects AJAX navigation into other pages.

- [ ] **Step 3:** Run `vs-env/Scripts/python.exe -m pytest -q && npm test && node --check FPL_site/static/scripts/home.js && python -m py_compile FPL_site/views.py FPL_site/config.py`; all green. Then run `grep -rn "FEATURE_WEEK_V2\|week_v2=" FPL_site tests`. Expected: no matches, except the partial's own filename.

- [ ] **Step 4: Commit.**
```bash
git add -A FPL_site tests
git commit -m "Launch the rebuilt Week tab: remove FEATURE_WEEK_V2 and the old Week code"
```

**Release 1.4 gate:** run the roadmap gate with no flag set. In the browser at 375px, walk through:
- upcoming, with deadline wording and the decision as a guest
- entering a team number on Last week, then going back to This week: the decision is now personal
- the live panel, still intact (check `data-gw-state="live"` by monkeypatching or by forcing `week_state` in a template render test)
- off-season and unavailable copy, through the existing template tests
