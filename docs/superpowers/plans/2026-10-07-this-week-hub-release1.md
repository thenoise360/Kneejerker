# This Week hub — Release 1: "See what this week needs" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Behind `THIS_WEEK_HUB`, replace the single "biggest decision" card with a read-only hub. It shows one headline decision and the injuries and captain rows, each in a clear state. It works without JavaScript, and JavaScript upgrades it to conversational wording.

**Architecture:**
- Three pure Python modules each do one job:
  - `squadContext.py`: works out the squad as it stands now, from the official API.
  - `hubSignals.py`: turns database rows into player risk tiers.
  - `hubRules.py`: decides each row's state and picks the headline.
- `thisWeekHub.py` fetches the data and composes the result for one JSON route and for the server-rendered page.
- Jinja renders factual lines. `hubView.js` and `hubCopy.js` redraw the same markup from JSON, with the conversational phrase bank.

**Tech Stack:** Python 3.11, Flask, `mysql.connector` through `connect_db()`, `requests`, Jinja2, pytest + pytest-bdd, vanilla ES modules, `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-07-this-week-hub-brief.md`. Roadmap: `docs/superpowers/plans/2026-10-07-this-week-hub-roadmap.md` (Release 1).

## Global Constraints

- Feature flag `THIS_WEEK_HUB` (env `THIS_WEEK_HUB=1`). When it's off, `/this-week` must be unchanged and `/api/week/this-week` returns 404.
- No acronyms in user-facing copy: "Gameweek 6", "the official game", "Captain"/"Vice", never `GW`, `FPL`, `C`, `VC`, `pts`, `EO`, `xG`.
- Tone: a suggestion, never a command ("Our lean …, your call").
- Never imply we change their team: "make the changes in the official app before the deadline".
- Tokens come from `style.css` (`--plum`, `--teal`, `--pink`, `--charcoal`, `--offwhite`, `--grey`, `--font`). Cards have a 12px radius and buttons are pills. Every state is shown as **icon plus text**, never colour alone. Usable at 375px.
- The rules engine is deterministic, with no randomness. The JSON carries keys and facts, not prose.
- Tests: `vs-env/Scripts/python.exe -m pytest -q` and `npm test`. They never touch MySQL or the live API (`KJ_SKIP_DB_INIT=1`, fetchers monkeypatched). Every new route goes into `tests/test_regression_routes.py`.
- JavaScript is learning material: comment the *why* in plain English.
- Do not touch the Live Gameweek panel, Discover, Radar, the player sheet, the Team page, the match engine or the prediction scripts. Leave the existing `weekDecision.py`, `/api/week/this-week-decision` and `decisionView.js` unchanged: they are what users see while the flag is off.
- Work on branch `this-week-hub-r1`, created from `main`.

## Review Focus

1. **A free hit last week.** The official API shows the free hit squad and lists the free hit transfers. Expected: we use the squad from the gameweek before, and ignore the free hit week's transfers. Pinned in Task 2.
2. **Transfers already made for the upcoming gameweek.** Expected: they are applied in the order made, the incoming player takes the outgoing player's starting slot (and loses any armband), and a transfer whose outgoing player isn't in the squad is skipped, not crashed on. Pinned in Task 2.
3. **Bench Boost last week.** Bench players have multiplier 1, so a check based on multiplier would call them starters. Expected: starters are positions 1–11. Pinned in Task 2.
4. **A player who never plays has 0 minutes last game.** Expected: no "missed last game" warning unless they're a regular (usual minutes ≥ 45). Pinned in Task 3.
5. **The official API or the database is down on a cold start.** Expected: the API down gives a guest hub with `team_status: "unavailable"` and status 200. The database down gives `status: "unavailable"` and the page shows a calm message. Never a 500 page. Pinned in Tasks 5 and 6.

## File structure

| File | Responsibility |
|---|---|
| `FPL_site/config.py` (modify) | `THIS_WEEK_HUB` flag on both configs |
| `FPL_site/squadContext.py` (create) | Fetch transfers; pure squad and bank derivation; `get_squad_context()` |
| `FPL_site/hubSignals.py` (create) | Fetch squad history; pure `player_signals()` and `assess_risk()` |
| `FPL_site/hubRules.py` (create) | Pure per-decision states, `HEADLINE_RULES`, `select_headline()` |
| `FPL_site/thisWeekHub.py` (create) | Pure `build_hub()`; live entry point `get_this_week_hub()` |
| `FPL_site/views.py` (modify) | `GET /api/week/this-week`; `/this-week` adds hub context when the flag is on |
| `FPL_site/templates/partials/week_v2.html` (modify) | Include the hub instead of `#decision-slot` when `hub_enabled` |
| `FPL_site/templates/partials/week_hub.html` (create) | Read-only hub markup |
| `FPL_site/templates/partials/hub_macros.html` (create) | Factual lines per `reason_key` and state badges |
| `FPL_site/static/content/home.css` (modify) | Hub styles |
| `FPL_site/static/scripts/lib/hubCopy.js` (create) | Pure conversational phrase bank |
| `FPL_site/static/scripts/lib/hubView.js` (create) | Pure `renderHub(data)` → HTML matching the Jinja markup |
| `FPL_site/static/scripts/weekV2.js` (modify) | `loadHub()` glue and the team form |
| `features/this_week/*.feature`, `tests/step_defs/test_this_week_*.py` | Behaviour scenarios |
| `tests/test_*.py`, `tests/js/*.test.js` | Unit tests |

**Changes from the roadmap, decided while planning:**
- `minutes_tier`, `consistency_tier` and `fixture_trend` move to Tasks 4.3 and 5.2, where they're first used (no unused code now).
- Task 1.7 grows to 1.5d: a JavaScript renderer that mirrors the template is needed so a saved team number can personalise the hub without a reload. That puts Release 1 at 9d.
- A bad team number follows the existing pattern: guest hub plus `team_status: "invalid"`, not a 400.
- Guests see a fourth display state, `needs_team`, on the injuries row ("Add your team number…").
- The JSON leaves out `deadline` and `bank` for now. The page already has the deadline, and the bank arrives with transfers in Release 4.

---

### Task 1: Flag, branch and regression gate (0.5d)

**Files:**
- Modify: `FPL_site/config.py`
- Modify: `tests/test_regression_routes.py`

**Interfaces:**
- Produces: `current_config.THIS_WEEK_HUB: bool`. Views read it with `getattr(current_config, 'THIS_WEEK_HUB', False)`. Tests flip it with `monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)`.

- [ ] **Step 1: Create the branch and commit the docs**

```bash
git switch -c this-week-hub-r1 main
git add docs/superpowers/specs/2026-10-07-this-week-hub-brief.md docs/superpowers/plans/2026-10-07-this-week-hub-roadmap.md docs/superpowers/plans/2026-10-07-this-week-hub-release1.md docs/prototypes/kneejerker-product-prototype_5.html
git commit -m "Add the This Week hub brief, roadmap, Release 1 plan and prototype"
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_regression_routes.py`:

```python
def test_hub_flag_defaults_off():
    from FPL_site.config import current_config
    assert getattr(current_config, 'THIS_WEEK_HUB', None) is False
```

- [ ] **Step 3: Run it to verify it fails**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_regression_routes.py::test_hub_flag_defaults_off -q`
Expected: FAIL (`None is False`).

- [ ] **Step 4: Add the flag**

In `FPL_site/config.py`, add this line to **both** `DevelopmentConfig` and `ProductionConfig`, after `MIXPANEL_TOKEN`:

```python
    # This Week hub (four weekly decisions). Off unless THIS_WEEK_HUB=1.
    THIS_WEEK_HUB = os.getenv('THIS_WEEK_HUB', '0') == '1'
```

- [ ] **Step 5: Run the full suite**

Run: `vs-env/Scripts/python.exe -m pytest -q && npm test`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add FPL_site/config.py tests/test_regression_routes.py
git commit -m "Add the THIS_WEEK_HUB feature flag, off by default"
```

---

### Task 2: Squad context (1.5d) — can run in parallel with Task 3

**Files:**
- Create: `FPL_site/squadContext.py`
- Create: `features/this_week/squad.feature`
- Create: `tests/step_defs/test_this_week_squad.py`
- Create: `tests/test_squad_context.py`

**Interfaces:**
- Consumes: `lastWeekRecap.fetch_entry_picks(entry_id, gameweek) -> (status, data)`, where status is `'ok'|'not_found'|'unavailable'`; `dataModels.FPL_API`.
- Produces:
  - `fetch_entry_transfers(entry_id) -> (status, list)`
  - `squad_from_picks(picks_data) -> [{'id': int, 'slot': int, 'starter': bool, 'is_captain': bool, 'is_vice': bool}]`
  - `base_picks_gameweek(last_gameweek, last_picks) -> int`
  - `apply_transfers(squad, transfers, after_gameweek, skip_events=()) -> (squad, applied)`
  - `bank_after(base_bank, applied) -> int` (tenths of a million, never negative)
  - `get_squad_context(team_id, last_gameweek) -> {'status': 'ok', 'squad': [...], 'bank': int, 'squad_gameweek': int}`, or `{'status': 'not_found'|'unavailable'}`

- [ ] **Step 1: Write the behaviour scenarios**

`features/this_week/squad.feature`:

```gherkin
Feature: Knowing your squad before the deadline
  Your picks for the coming gameweek stay private until the deadline, so we
  start from your last finished gameweek and add any transfers made since.

  Scenario: No transfers since last gameweek
    Given my gameweek 5 team has "Raya" in goal and "Saka" starting
    When we work out my squad for gameweek 6
    Then my squad includes "Saka" as a starter

  Scenario: I've already made a transfer for this week
    Given my gameweek 5 team has "Raya" in goal and "Saka" starting
    And I transferred "Saka" out for "Palmer" for gameweek 6
    When we work out my squad for gameweek 6
    Then my squad includes "Palmer" as a starter
    And my squad does not include "Saka"

  Scenario: I played my free hit last week
    Given my gameweek 4 team has "Raya" in goal and "Saka" starting
    And I played my free hit in gameweek 5 with "Isak" instead of "Saka"
    When we work out my squad for gameweek 6
    Then my squad includes "Saka" as a starter
    And my squad does not include "Isak"

  Scenario: My bank never shows as negative
    Given my gameweek 5 team has "Raya" in goal and "Saka" starting
    And I have 0.5 million in the bank
    And I transferred "Saka" out for "Palmer" for gameweek 6 paying 1.0 million more
    When we work out my squad for gameweek 6
    Then my bank is 0.0 million
```

- [ ] **Step 2: Write the step definitions**

`tests/step_defs/test_this_week_squad.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

import FPL_site.squadContext as squad_context

scenarios('this_week/squad.feature')

IDS = {'Raya': 1, 'Saka': 2, 'Palmer': 3, 'Isak': 4}


def picks(gameweek, starters, chip=None, bank=0):
    """A minimal picks response: given names in slots 1.., then filler to 15."""
    rows = [{'element': IDS[name], 'position': i + 1, 'multiplier': 1,
             'is_captain': False, 'is_vice_captain': False} for i, name in enumerate(starters)]
    rows += [{'element': 100 + n, 'position': n, 'multiplier': 1 if n <= 11 else 0,
              'is_captain': False, 'is_vice_captain': False} for n in range(len(starters) + 1, 16)]
    return {'active_chip': chip, 'picks': rows, 'entry_history': {'event': gameweek, 'bank': bank}}


@given(parsers.parse('my gameweek {gw:d} team has "{keeper}" in goal and "{starter}" starting'),
       target_fixture='api')
def base_team(gw, keeper, starter):
    return {'picks': {gw: picks(gw, [keeper, starter])}, 'transfers': []}


@given(parsers.parse('I have {amount:f} million in the bank'))
def bank(api, amount):
    for data in api['picks'].values():
        data['entry_history']['bank'] = round(amount * 10)


@given(parsers.parse('I transferred "{out}" out for "{inn}" for gameweek {gw:d}'))
def transfer(api, out, inn, gw):
    api['transfers'].append({'element_out': IDS[out], 'element_in': IDS[inn], 'event': gw,
                             'element_out_cost': 80, 'element_in_cost': 80,
                             'time': f'2026-10-0{gw}T10:00:00Z'})


@given(parsers.parse('I transferred "{out}" out for "{inn}" for gameweek {gw:d} paying {extra:f} million more'))
def dearer_transfer(api, out, inn, gw, extra):
    api['transfers'].append({'element_out': IDS[out], 'element_in': IDS[inn], 'event': gw,
                             'element_out_cost': 80, 'element_in_cost': 80 + round(extra * 10),
                             'time': f'2026-10-0{gw}T10:00:00Z'})


@given(parsers.parse('I played my free hit in gameweek {gw:d} with "{inn}" instead of "{out}"'))
def free_hit(api, gw, inn, out):
    keeper = next(name for name, i in IDS.items() if i == api['picks'][gw - 1]['picks'][0]['element'])
    api['picks'][gw] = picks(gw, [keeper, inn], chip='freehit')
    api['transfers'].append({'element_out': IDS[out], 'element_in': IDS[inn], 'event': gw,
                             'element_out_cost': 80, 'element_in_cost': 80,
                             'time': f'2026-10-0{gw}T09:00:00Z'})


@when(parsers.parse('we work out my squad for gameweek {gw:d}'), target_fixture='context')
def work_out(api, gw, monkeypatch):
    def fake_picks(entry_id, gameweek):
        return ('ok', api['picks'][gameweek]) if gameweek in api['picks'] else ('not_found', None)
    monkeypatch.setattr(squad_context, 'fetch_entry_picks', fake_picks)
    monkeypatch.setattr(squad_context, 'fetch_entry_transfers', lambda entry_id: ('ok', api['transfers']))
    return squad_context.get_squad_context(123, gw - 1)


@then(parsers.parse('my squad includes "{name}" as a starter'))
def includes_starter(context, name):
    player = next(p for p in context['squad'] if p['id'] == IDS[name])
    assert player['starter'] is True


@then(parsers.parse('my squad does not include "{name}"'))
def excludes(context, name):
    assert IDS[name] not in [p['id'] for p in context['squad']]


@then(parsers.parse('my bank is {amount:f} million'))
def bank_is(context, amount):
    assert context['bank'] == round(amount * 10)
```

- [ ] **Step 3: Write the unit tests for the edges**

`tests/test_squad_context.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.squadContext import (
    squad_from_picks, base_picks_gameweek, apply_transfers, bank_after, get_squad_context,
)
import FPL_site.squadContext as squad_context


def _pick(element, position, captain=False, vice=False, multiplier=1):
    return {'element': element, 'position': position, 'multiplier': multiplier,
            'is_captain': captain, 'is_vice_captain': vice}


def test_starters_are_positions_one_to_eleven_even_with_bench_boost():
    # Bench Boost gives bench players multiplier 1, so position is the only safe signal.
    squad = squad_from_picks({'picks': [_pick(1, 11), _pick(2, 12, multiplier=1)]})
    assert [p['starter'] for p in squad] == [True, False]


def test_armbands_are_read():
    squad = squad_from_picks({'picks': [_pick(1, 1, captain=True), _pick(2, 2, vice=True)]})
    assert squad[0]['is_captain'] and squad[1]['is_vice']


def test_free_hit_goes_back_one_gameweek():
    assert base_picks_gameweek(5, {'active_chip': 'freehit'}) == 4
    assert base_picks_gameweek(5, {'active_chip': 'wildcard'}) == 5
    assert base_picks_gameweek(5, {'active_chip': None}) == 5


def test_transfers_apply_in_time_order_and_drop_armbands():
    squad = [{'id': 1, 'slot': 1, 'starter': True, 'is_captain': True, 'is_vice': False}]
    transfers = [
        {'element_out': 9, 'element_in': 7, 'event': 6, 'time': '2026-10-08T10:00:00Z',
         'element_in_cost': 50, 'element_out_cost': 50},
        {'element_out': 1, 'element_in': 9, 'event': 6, 'time': '2026-10-07T10:00:00Z',
         'element_in_cost': 50, 'element_out_cost': 50},
    ]
    result, applied = apply_transfers(squad, transfers, after_gameweek=5)
    assert result == [{'id': 7, 'slot': 1, 'starter': True, 'is_captain': False, 'is_vice': False}]
    assert len(applied) == 2


def test_older_and_skipped_transfers_are_ignored():
    squad = [{'id': 1, 'slot': 1, 'starter': True, 'is_captain': False, 'is_vice': False}]
    transfers = [{'element_out': 1, 'element_in': 2, 'event': 5, 'time': 't',
                  'element_in_cost': 50, 'element_out_cost': 50}]
    assert apply_transfers(squad, transfers, after_gameweek=5)[0][0]['id'] == 1
    assert apply_transfers(squad, transfers, after_gameweek=4, skip_events=(5,))[0][0]['id'] == 1


def test_transfer_of_unknown_player_is_skipped_not_crashed():
    squad = [{'id': 1, 'slot': 1, 'starter': True, 'is_captain': False, 'is_vice': False}]
    transfers = [{'element_out': 99, 'element_in': 2, 'event': 6, 'time': 't',
                  'element_in_cost': 50, 'element_out_cost': 50}]
    result, applied = apply_transfers(squad, transfers, after_gameweek=5)
    assert result[0]['id'] == 1 and applied == []


def test_bank_moves_with_transfers_and_never_goes_negative():
    applied = [{'element_in_cost': 60, 'element_out_cost': 55}]
    assert bank_after(13, applied) == 8
    assert bank_after(3, applied) == 0


def test_picks_failure_status_is_passed_through(monkeypatch):
    monkeypatch.setattr(squad_context, 'fetch_entry_picks', lambda e, g: ('not_found', None))
    monkeypatch.setattr(squad_context, 'fetch_entry_transfers', lambda e: ('ok', []))
    assert get_squad_context(1, 5) == {'status': 'not_found'}


def test_transfers_outage_means_unavailable(monkeypatch):
    monkeypatch.setattr(squad_context, 'fetch_entry_picks',
                        lambda e, g: ('ok', {'picks': [], 'entry_history': {'bank': 0}}))
    monkeypatch.setattr(squad_context, 'fetch_entry_transfers', lambda e: ('unavailable', None))
    assert get_squad_context(1, 5) == {'status': 'unavailable'}


def test_no_last_gameweek_means_no_squad():
    assert get_squad_context(1, None) == {'status': 'unavailable'}
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_squad_context.py tests/step_defs/test_this_week_squad.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'FPL_site.squadContext'`.

- [ ] **Step 5: Implement**

`FPL_site/squadContext.py`:

```python
"""A manager's squad as it stands for the coming gameweek (This Week hub, release 1).

Picks for the coming gameweek stay private until the deadline, so the squad is
the last finished gameweek's picks plus any transfers made since. Fetchers talk
to the official game's public API; everything else is pure and tested with dicts.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

import requests

from FPL_site.dataModels import FPL_API
from FPL_site.lastWeekRecap import fetch_entry_picks

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
STARTING_SLOTS = 11


#################################################
#                  Fetchers                     #
#################################################

def fetch_entry_transfers(entry_id):
    """Every transfer the team has made this season, same status contract as fetch_entry_picks."""
    try:
        response = requests.get(f'{FPL_API}/entry/{entry_id}/transfers/', timeout=TIMEOUT_SECONDS)
        if response.status_code == 200:
            return 'ok', response.json()
        if response.status_code == 404:
            return 'not_found', None
        return 'unavailable', None
    except Exception as exc:
        # Log the kind of failure only: the message can carry the URL, which holds the team number.
        logger.error("Transfers fetch failed: %s", type(exc).__name__)
        return 'unavailable', None


#################################################
#                 Pure shaping                  #
#################################################

def squad_from_picks(picks_data):
    """Slots 1-11 start. Multiplier can't be used: Bench Boost gives the bench a 1 too."""
    return [{'id': p['element'], 'slot': p['position'],
             'starter': p['position'] <= STARTING_SLOTS,
             'is_captain': bool(p.get('is_captain')), 'is_vice': bool(p.get('is_vice_captain'))}
            for p in (picks_data or {}).get('picks', [])]


def base_picks_gameweek(last_gameweek, last_picks):
    """A free hit team lasts one week, then the team from the week before comes back."""
    if (last_picks or {}).get('active_chip') == 'freehit' and last_gameweek > 1:
        return last_gameweek - 1
    return last_gameweek


def apply_transfers(squad, transfers, after_gameweek, skip_events=()):
    """Apply transfers made for gameweeks after the squad's own, oldest first.

    The incoming player takes the outgoing player's slot, so a starter stays a
    starter. Armbands don't move with a transfer. skip_events holds free hit
    weeks, whose transfers were undone when the week ended.
    """
    squad = [dict(p) for p in squad]
    relevant = [t for t in transfers or []
                if (t.get('event') or 0) > after_gameweek and t.get('event') not in skip_events]
    applied = []
    for t in sorted(relevant, key=lambda t: t.get('time') or ''):
        slot = next((p for p in squad if p['id'] == t['element_out']), None)
        if slot is None:
            logger.warning("Transfer out of a player not in the squad was skipped (gameweek %s)", t.get('event'))
            continue
        slot.update(id=t['element_in'], is_captain=False, is_vice=False)
        applied.append(t)
    return squad, applied


def bank_after(base_bank, applied):
    """Money left in tenths of a million. Never below zero, so copy can't show a negative bank."""
    bank = base_bank - sum(t['element_in_cost'] for t in applied) + sum(t['element_out_cost'] for t in applied)
    return max(bank, 0)


#################################################
#          Live-route entry point               #
#################################################

def get_squad_context(team_id, last_gameweek):
    """The squad, bank and which gameweek's picks it is based on, or a failure status."""
    if not last_gameweek:
        return {'status': 'unavailable'}
    # The two calls don't depend on each other, so run them side by side:
    # on a cold start each one can take seconds.
    with ThreadPoolExecutor(max_workers=2) as pool:
        picks_future = pool.submit(fetch_entry_picks, team_id, last_gameweek)
        transfers_future = pool.submit(fetch_entry_transfers, team_id)
        picks_status, last_picks = picks_future.result()
        transfers_status, transfers = transfers_future.result()
    if picks_status != 'ok':
        return {'status': picks_status}
    if transfers_status != 'ok':
        return {'status': 'unavailable'}

    base_gameweek = base_picks_gameweek(last_gameweek, last_picks)
    base_picks, skip_events = last_picks, ()
    if base_gameweek != last_gameweek:
        status, base_picks = fetch_entry_picks(team_id, base_gameweek)
        if status != 'ok':
            return {'status': 'unavailable'}
        skip_events = (last_gameweek,)

    squad, applied = apply_transfers(squad_from_picks(base_picks), transfers, base_gameweek, skip_events)
    bank = bank_after((base_picks.get('entry_history') or {}).get('bank', 0), applied)
    return {'status': 'ok', 'squad': squad, 'bank': bank, 'squad_gameweek': base_gameweek}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_squad_context.py tests/step_defs/test_this_week_squad.py -q`
Expected: PASS (10 unit tests, 4 scenarios).

- [ ] **Step 7: Verify one assumption against a real response (read-only)**

Run (team 1 is a public team that played a free hit in gameweek 5):

```bash
vs-env/Scripts/python.exe -c "from FPL_site.squadContext import get_squad_context as g; c=g(1,5); print(c['status'], c['squad_gameweek'], len(c['squad']), c['bank'])"
```

Expected: `ok 4 15 <bank>`. If `squad_gameweek` isn't 4, stop and report.

- [ ] **Step 8: Commit**

```bash
git add FPL_site/squadContext.py features/this_week/squad.feature tests/step_defs/test_this_week_squad.py tests/test_squad_context.py
git commit -m "Work out a manager's squad and bank for the coming gameweek, including transfers and free hit weeks"
```

---

### Task 3: Player risk signals (1.5d) — can run in parallel with Task 2

**Files:**
- Create: `FPL_site/hubSignals.py`
- Create: `features/this_week/injury_risk.feature`
- Create: `tests/step_defs/test_this_week_injury_risk.py`
- Create: `tests/test_hub_signals.py`

**Interfaces:**
- Produces:
  - `fetch_squad_history_rows(cursor, year_start, element_ids, before_gameweek) -> [row]` with keys `element, fixture, kickoff_time, minutes, yellow_cards`
  - `player_signals(history_rows) -> {element_id: {'minutes_recent': [int], 'yellows_recent': [int], 'yellows_season': int, 'games_season': int}}`
  - `assess_risk(player, signals, upcoming_gameweek) -> {'pct': int, 'tier': 'confirmed'|'high'|'medium'|'low', 'reasons': [{'key': str, ...facts}]}`, where `player` is `{'chance': int|None, 'status': str, 'news': str}`
  - Reason keys: `ruled_out{news}`, `official_doubt{chance, news}`, `missed_last_game{usual_minutes}`, `subbed_early{minutes, usual_minutes}`, `one_booking_from_ban{cards}`, `booked_more_often{recent_cards, recent_games}`.

- [ ] **Step 1: Write the behaviour scenarios**

`features/this_week/injury_risk.feature`:

```gherkin
Feature: How worried should I be about a player?
  Each risk uses its own signal, scaled to the same tiers. No judgement calls,
  just thresholds on real data.

  Scenario: The official game rules a player out
    Given a player with a 0 percent chance of playing because "Knee injury"
    When we assess the risk for gameweek 6
    Then the risk tier is "confirmed"
    And a reason is "ruled_out"

  Scenario: An official doubt
    Given a player with a 25 percent chance of playing because "Hamstring"
    When we assess the risk for gameweek 6
    Then the risk tier is "high"
    And the risk is 75 percent

  Scenario: A regular starter who didn't feature last game
    Given a fit player whose last five games were 90, 90, 88, 90 and 0 minutes
    When we assess the risk for gameweek 6
    Then the risk tier is "high"
    And a reason is "missed_last_game"

  Scenario: A bench player who rarely plays is not a worry
    Given a fit player whose last five games were 0, 10, 0, 0 and 0 minutes
    When we assess the risk for gameweek 6
    Then the risk tier is "low"

  Scenario: One booking away from a ban
    Given a fit player with 4 yellow cards this season
    When we assess the risk for gameweek 6
    Then the risk tier is "high"
    And a reason is "one_booking_from_ban"

  Scenario: The early-season ban no longer applies after gameweek 19
    Given a fit player with 4 yellow cards this season
    When we assess the risk for gameweek 20
    Then the risk tier is "low"
```

- [ ] **Step 2: Write the step definitions**

`tests/step_defs/test_this_week_injury_risk.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.hubSignals import assess_risk, player_signals

scenarios('this_week/injury_risk.feature')


def history(minutes, yellows=None):
    yellows = yellows or [0] * len(minutes)
    return [{'element': 1, 'fixture': i, 'kickoff_time': f'2026-09-{10 + i:02d}T15:00:00Z',
             'minutes': m, 'yellow_cards': y} for i, (m, y) in enumerate(zip(minutes, yellows))]


@given(parsers.parse('a player with a {chance:d} percent chance of playing because "{news}"'),
       target_fixture='ctx')
def doubt(chance, news):
    return {'player': {'chance': chance, 'status': 'd' if chance else 'i', 'news': news}, 'rows': []}


@given(parsers.parse('a fit player whose last five games were {a:d}, {b:d}, {c:d}, {d:d} and {e:d} minutes'),
       target_fixture='ctx')
def recent_minutes(a, b, c, d, e):
    return {'player': {'chance': None, 'status': 'a', 'news': ''}, 'rows': history([a, b, c, d, e])}


@given(parsers.parse('a fit player with {cards:d} yellow cards this season'), target_fixture='ctx')
def bookings(cards):
    games = 8
    yellows = [1] * cards + [0] * (games - cards)
    # Spread the cards across the season so the "booked more often" rule stays quiet.
    yellows = yellows[::2] + yellows[1::2]
    return {'player': {'chance': None, 'status': 'a', 'news': ''}, 'rows': history([90] * games, yellows)}


@when(parsers.parse('we assess the risk for gameweek {gw:d}'))
def assess(ctx, gw):
    ctx['risk'] = assess_risk(ctx['player'], player_signals(ctx['rows']).get(1), gw)


@then(parsers.parse('the risk tier is "{tier}"'))
def tier_is(ctx, tier):
    assert ctx['risk']['tier'] == tier, ctx['risk']


@then(parsers.parse('the risk is {pct:d} percent'))
def pct_is(ctx, pct):
    assert ctx['risk']['pct'] == pct


@then(parsers.parse('a reason is "{key}"'))
def reason_is(ctx, key):
    assert key in [r['key'] for r in ctx['risk']['reasons']], ctx['risk']
```

- [ ] **Step 3: Write the unit tests for tier edges and data quirks**

`tests/test_hub_signals.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site.hubSignals import assess_risk, player_signals

FIT = {'chance': None, 'status': 'a', 'news': ''}


def _rows(minutes, element=1):
    return [{'element': element, 'fixture': i, 'kickoff_time': f'2026-09-{10 + i:02d}T15:00:00Z',
             'minutes': m, 'yellow_cards': 0} for i, m in enumerate(minutes)]


@pytest.mark.parametrize('chance,tier', [(75, 'low'), (50, 'medium'), (25, 'high'), (0, 'confirmed')])
def test_official_chance_maps_to_tiers(chance, tier):
    assert assess_risk({'chance': chance, 'status': 'd', 'news': ''}, None, 6)['tier'] == tier


@pytest.mark.parametrize('status', ['s', 'u', 'n'])
def test_suspended_or_unavailable_is_confirmed(status):
    assert assess_risk({'chance': None, 'status': status, 'news': ''}, None, 6)['tier'] == 'confirmed'


def test_subbed_early_is_medium():
    risk = assess_risk(FIT, player_signals(_rows([90, 90, 90, 90, 60])).get(1), 6)
    assert risk['tier'] == 'medium'
    assert risk['reasons'] == [{'key': 'subbed_early', 'minutes': 60, 'usual_minutes': 90}]


def test_just_under_threshold_is_not_subbed_early():
    # 70 is not below 0.75 x 90 = 67.5
    assert assess_risk(FIT, player_signals(_rows([90, 90, 90, 90, 70])).get(1), 6)['tier'] == 'low'


def test_only_the_last_five_games_count():
    signals = player_signals(_rows([0, 0, 0, 90, 90, 90, 90, 90]))[1]
    assert signals['minutes_recent'] == [90, 90, 90, 90, 90]
    assert signals['games_season'] == 8


def test_games_are_ordered_by_kickoff_and_deduplicated_by_fixture():
    rows = _rows([90, 0]) + [dict(_rows([90, 0])[1])]  # the same fixture stored twice
    rows.reverse()
    assert player_signals(rows)[1]['minutes_recent'] == [90, 0]


def test_no_history_and_fit_means_low_with_no_reasons():
    assert assess_risk(FIT, None, 6) == {'pct': 0, 'tier': 'low', 'reasons': []}
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_hub_signals.py tests/step_defs/test_this_week_injury_risk.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'FPL_site.hubSignals'`.

- [ ] **Step 5: Implement**

`FPL_site/hubSignals.py`:

```python
"""Player risk signals for the This Week hub (release 1).

Pure functions turn database rows into tiers plus reason keys and facts. They
never write sentences: hubCopy.js and the Jinja macros turn keys into words.
"""

RECENT_GAMES = 5
REGULAR_MINUTES = 45          # below this usual average, one quiet game tells us nothing
SUBBED_EARLY_SHARE = 0.75     # last game under 75% of usual minutes counts as taken off early
BOOKED_MORE_OFTEN = 1.5       # recent card rate this many times the season rate
MIN_GAMES_FOR_RATE = 5
RULED_OUT_STATUSES = ('s', 'u', 'n')   # suspended, left the club, not available
# Yellow-card bans aren't in the official API: (last gameweek the count applies, cards
# that trigger a ban). Matches the 2026/27 rules; check them each summer.
BOOKING_BANS = ((19, 5), (32, 10))


#################################################
#                  Fetchers                     #
#################################################

def fetch_squad_history_rows(cursor, year_start, element_ids, before_gameweek):
    """Every game this season before the coming gameweek, for the given players."""
    if not element_ids:
        return []
    placeholders = ', '.join(['%s'] * len(element_ids))
    cursor.execute(f"""
        SELECT element, fixture, kickoff_time, minutes, yellow_cards
        FROM elementsummary_history
        WHERE year_start = %s AND round < %s AND element IN ({placeholders})
        ORDER BY kickoff_time
    """, (year_start, before_gameweek, *element_ids))
    return cursor.fetchall()


#################################################
#                 Pure shaping                  #
#################################################

def player_signals(history_rows):
    """Group each player's games, oldest first, into what assess_risk needs."""
    games = {}
    for r in history_rows:
        # Keyed by fixture so a row stored twice counts once.
        games.setdefault(r['element'], {})[r['fixture']] = r
    signals = {}
    for element, by_fixture in games.items():
        rows = sorted(by_fixture.values(), key=lambda r: str(r['kickoff_time'] or ''))
        recent = rows[-RECENT_GAMES:]
        signals[element] = {
            'minutes_recent': [int(r['minutes'] or 0) for r in recent],
            'yellows_recent': [int(r['yellow_cards'] or 0) for r in recent],
            'yellows_season': sum(int(r['yellow_cards'] or 0) for r in rows),
            'games_season': len(rows),
        }
    return signals


#################################################
#                Pure choosing                  #
#################################################

def _tier(pct):
    if pct >= 75:
        return 'high'
    if pct >= 50:
        return 'medium'
    return 'low'


def _ban_threshold(gameweek):
    for last_gameweek, cards in BOOKING_BANS:
        if gameweek <= last_gameweek:
            return cards
    return None


def assess_risk(player, signals, upcoming_gameweek):
    """Each kind of risk uses its own signal; the highest one sets the tier."""
    chance, status, news = player.get('chance'), player.get('status'), player.get('news') or ''
    if chance == 0 or status in RULED_OUT_STATUSES or (status == 'i' and chance is None):
        return {'pct': 100, 'tier': 'confirmed', 'reasons': [{'key': 'ruled_out', 'news': news}]}

    pct, reasons = 0, []
    if chance is not None and chance < 100:
        pct = max(pct, 100 - chance)
        reasons.append({'key': 'official_doubt', 'chance': chance, 'news': news})

    s = signals or {}
    minutes = s.get('minutes_recent') or []
    if len(minutes) >= 2:
        last, earlier = minutes[-1], minutes[:-1]
        usual = round(sum(earlier) / len(earlier))
        if usual >= REGULAR_MINUTES:
            if last == 0:
                pct = max(pct, 75)
                reasons.append({'key': 'missed_last_game', 'usual_minutes': usual})
            elif last < usual * SUBBED_EARLY_SHARE:
                pct = max(pct, 50)
                reasons.append({'key': 'subbed_early', 'minutes': last, 'usual_minutes': usual})

    season_cards = s.get('yellows_season', 0)
    ban_at = _ban_threshold(upcoming_gameweek)
    if ban_at is not None and season_cards == ban_at - 1:
        pct = max(pct, 75)
        reasons.append({'key': 'one_booking_from_ban', 'cards': season_cards})

    recent_cards, games = s.get('yellows_recent') or [], s.get('games_season', 0)
    if games >= MIN_GAMES_FOR_RATE and recent_cards and season_cards:
        if sum(recent_cards) / len(recent_cards) > (season_cards / games) * BOOKED_MORE_OFTEN:
            pct = max(pct, 50)
            reasons.append({'key': 'booked_more_often', 'recent_cards': sum(recent_cards),
                            'recent_games': len(recent_cards)})

    return {'pct': pct, 'tier': _tier(pct), 'reasons': reasons}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_hub_signals.py tests/step_defs/test_this_week_injury_risk.py -q`
Expected: PASS. If the "one booking away" scenario also picks up `booked_more_often`, that's fine. The tier is still high.

- [ ] **Step 7: Commit**

```bash
git add FPL_site/hubSignals.py features/this_week/injury_risk.feature tests/step_defs/test_this_week_injury_risk.py tests/test_hub_signals.py
git commit -m "Assess player risk from official availability, recent minutes and bookings"
```

---

### Task 4: Decision states and headline (1.5d) — after Tasks 2 and 3

**Files:**
- Create: `FPL_site/hubRules.py`
- Create: `features/this_week/headline.feature`
- Create: `tests/step_defs/test_this_week_headline.py`
- Create: `tests/test_hub_rules.py`

**Interfaces:**
- Consumes: the squad shape from Task 2 (`{'id', 'slot', 'starter', 'is_captain', 'is_vice'}`) and the risk shape from Task 3.
- Uses `availability`: `{id: {'name', 'team', 'chance', 'status', 'news'}}`, `predictions`: `{id: float}` (from `weekDecision.involvement_predictions`), and `fixtures`: `{team_id: {'opponent', 'is_home', 'difficulty'}}` (from `weekDecision.fixtures_by_team`).
- Produces:
  - constants `NEEDS_LOOK, NOTHING_TO_DO, NEEDS_TEAM, NOT_READY`, `HEADLINE_RULES`
  - `resolve_injuries(squad, availability, risks) -> {'state', 'players': [{'id', 'name', 'starter', 'risk_pct', 'tier', 'reasons'}]}`
  - `resolve_captaincy(squad, availability, predictions, fixtures, risks) -> {'state': 'needs_look', 'suggested': option|None, 'vice': option|None, 'shortlist': [option]}`, where option is `{'id', 'name', 'expected_involvement', 'fixture'}`
  - `select_headline(ctx, rules=HEADLINE_RULES) -> {'decision', 'reason_key', 'player', ...}`. `ctx` has the keys `squad, availability, fixtures, injuries, captaincy` and optionally `free_transfers`.

- [ ] **Step 1: Write the behaviour scenarios**

`features/this_week/headline.feature`:

```gherkin
Feature: The one decision at the top of This Week
  The headline is the first rule that fires, in a fixed order:
  a doubtful starter, then a starter with no match, then unused free
  transfers, then the captain choice, which always applies.

  Background:
    Given my starters are "Saka", "Haaland" and "Salah"
    And our predictions rank "Haaland" above "Salah" above "Saka"

  Scenario: A doubtful starter comes first
    Given "Saka" has a 25 percent chance of playing
    And "Salah" has no match this gameweek
    When the headline is chosen
    Then the headline decision is "injuries" because "starter_doubt" about "Saka"

  Scenario: A starter with no match comes next
    Given "Salah" has no match this gameweek
    When the headline is chosen
    Then the headline decision is "transfers" because "starter_blank" about "Salah"

  Scenario: Unused free transfers come before the captain
    Given I have 2 free transfers
    When the headline is chosen
    Then the headline decision is "transfers" because "unused_free_transfers"

  Scenario: Otherwise it's the captain choice
    When the headline is chosen
    Then the headline decision is "captaincy" because "captain_choice" about "Haaland"

  Scenario: Changing the order changes the headline
    Given "Saka" has a 25 percent chance of playing
    When the headline is chosen with the captain rule first
    Then the headline decision is "captaincy" because "captain_choice" about "Haaland"

  Scenario: Nothing to do on injuries when everyone is fit
    When the injuries decision is worked out
    Then the injuries decision is "nothing_to_do"

  Scenario: A guest is asked for their team on injuries
    Given I have not given a team number
    When the injuries decision is worked out
    Then the injuries decision is "needs_team"
```

- [ ] **Step 2: Write the step definitions**

`tests/step_defs/test_this_week_headline.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.hubRules import HEADLINE_RULES, resolve_injuries, resolve_captaincy, select_headline
from FPL_site.hubSignals import assess_risk

scenarios('this_week/headline.feature')

IDS = {'Saka': 1, 'Haaland': 2, 'Salah': 3}
TEAMS = {'Saka': 10, 'Haaland': 20, 'Salah': 30}


@given(parsers.parse('my starters are "{a}", "{b}" and "{c}"'), target_fixture='ctx')
def starters(a, b, c):
    names = [a, b, c]
    return {
        'squad': [{'id': IDS[n], 'slot': i + 1, 'starter': True, 'is_captain': False, 'is_vice': False}
                  for i, n in enumerate(names)],
        'availability': {IDS[n]: {'name': n, 'team': TEAMS[n], 'chance': None, 'status': 'a', 'news': ''}
                         for n in names},
        'fixtures': {t: {'opponent': 'Everton', 'is_home': True, 'difficulty': 2} for t in TEAMS.values()},
        'predictions': {},
        'free_transfers': None,
        'rules': HEADLINE_RULES,
    }


@given(parsers.parse('our predictions rank "{first}" above "{second}" above "{third}"'))
def ranking(ctx, first, second, third):
    ctx['predictions'] = {IDS[first]: 1.2, IDS[second]: 0.9, IDS[third]: 0.5}


@given(parsers.parse('"{name}" has a {chance:d} percent chance of playing'))
def doubt(ctx, name, chance):
    ctx['availability'][IDS[name]].update(chance=chance, status='d')


@given(parsers.parse('"{name}" has no match this gameweek'))
def blank(ctx, name):
    del ctx['fixtures'][TEAMS[name]]


@given(parsers.parse('I have {count:d} free transfers'))
def free_transfers(ctx, count):
    ctx['free_transfers'] = count


@given('I have not given a team number')
def guest(ctx):
    ctx['squad'] = []


def _resolve(ctx):
    risks = {p['id']: assess_risk(ctx['availability'][p['id']], None, 6) for p in ctx['squad']}
    injuries = resolve_injuries(ctx['squad'], ctx['availability'], risks)
    captaincy = resolve_captaincy(ctx['squad'], ctx['availability'], ctx['predictions'],
                                  ctx['fixtures'], risks)
    return {'squad': ctx['squad'], 'availability': ctx['availability'], 'fixtures': ctx['fixtures'],
            'injuries': injuries, 'captaincy': captaincy, 'free_transfers': ctx['free_transfers']}


@when('the headline is chosen')
def choose(ctx):
    ctx['headline'] = select_headline(_resolve(ctx), ctx['rules'])


@when('the headline is chosen with the captain rule first')
def choose_reordered(ctx):
    rules = ('captain_choice',) + tuple(r for r in HEADLINE_RULES if r != 'captain_choice')
    ctx['headline'] = select_headline(_resolve(ctx), rules)


@when('the injuries decision is worked out')
def injuries(ctx):
    ctx['injuries'] = _resolve(ctx)['injuries']


@then(parsers.parse('the headline decision is "{decision}" because "{reason}" about "{player}"'))
def headline_about(ctx, decision, reason, player):
    h = ctx['headline']
    assert (h['decision'], h['reason_key'], h['player']) == (decision, reason, player), h


@then(parsers.parse('the headline decision is "{decision}" because "{reason}"'))
def headline_is(ctx, decision, reason):
    assert (ctx['headline']['decision'], ctx['headline']['reason_key']) == (decision, reason)


@then(parsers.parse('the injuries decision is "{state}"'))
def injuries_state(ctx, state):
    assert ctx['injuries']['state'] == state
```

- [ ] **Step 3: Write unit tests for ordering and captaincy**

`tests/test_hub_rules.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.hubRules import resolve_injuries, resolve_captaincy, NEEDS_LOOK

FIX = {'opponent': 'Everton', 'is_home': True, 'difficulty': 2}


def _p(pid, starter=True, captain=False):
    return {'id': pid, 'slot': pid, 'starter': starter, 'is_captain': captain, 'is_vice': False}


def _a(name, team=10, chance=None):
    return {'name': name, 'team': team, 'chance': chance, 'status': 'a', 'news': ''}


def _risk(pct, tier):
    return {'pct': pct, 'tier': tier, 'reasons': []}


def test_injuries_list_starters_first_then_biggest_risk():
    squad = [_p(1, starter=False), _p(2), _p(3)]
    availability = {1: _a('Bench'), 2: _a('Zed'), 3: _a('Abe')}
    risks = {1: _risk(100, 'confirmed'), 2: _risk(50, 'medium'), 3: _risk(75, 'high')}
    players = resolve_injuries(squad, availability, risks)['players']
    assert [p['name'] for p in players] == ['Abe', 'Zed', 'Bench']


def test_low_risk_players_are_not_listed():
    result = resolve_injuries([_p(1)], {1: _a('A')}, {1: _risk(25, 'low')})
    assert result == {'state': 'nothing_to_do', 'players': []}


def test_captaincy_uses_starters_with_a_match_and_no_worries():
    squad = [_p(1), _p(2), _p(3), _p(4, starter=False)]
    availability = {1: _a('Fit', 10), 2: _a('Doubt', 10, chance=50), 3: _a('Blank', 99), 4: _a('Bench', 10)}
    predictions = {1: 0.8, 2: 2.0, 3: 2.0, 4: 3.0}
    result = resolve_captaincy(squad, availability, predictions, {10: FIX}, {})
    assert result['state'] == NEEDS_LOOK
    assert [o['name'] for o in result['shortlist']] == ['Fit']
    assert result['suggested']['name'] == 'Fit' and result['vice'] is None


def test_guest_captaincy_is_top_three_across_everyone():
    availability = {i: _a(f'P{i}') for i in range(1, 6)}
    predictions = {i: float(i) for i in range(1, 6)}
    result = resolve_captaincy([], availability, predictions, {10: FIX}, {})
    assert [o['name'] for o in result['shortlist']] == ['P5', 'P4', 'P3']
    assert result['vice']['name'] == 'P4'


def test_expected_involvement_is_rounded_for_display():
    result = resolve_captaincy([_p(1)], {1: _a('A')}, {1: 1.234}, {10: FIX}, {})
    assert result['suggested']['expected_involvement'] == 1.2


def test_no_predictions_still_needs_a_look_with_no_suggestion():
    result = resolve_captaincy([_p(1)], {1: _a('A')}, {}, {10: FIX}, {})
    assert result == {'state': NEEDS_LOOK, 'suggested': None, 'vice': None, 'shortlist': []}
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_hub_rules.py tests/step_defs/test_this_week_headline.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'FPL_site.hubRules'`.

- [ ] **Step 5: Implement**

`FPL_site/hubRules.py`:

```python
"""Rules for the This Week hub: a state per decision and the headline (release 1).

Pure: plain dicts in, plain dicts of states, keys and facts out. No prose and
no randomness, so the same week always gives the same answer.
"""

NEEDS_LOOK = 'needs_look'
NOTHING_TO_DO = 'nothing_to_do'
NEEDS_TEAM = 'needs_team'      # a guest: we need their team number first
NOT_READY = 'not_ready'        # this decision isn't built yet

WORTH_A_LOOK = ('confirmed', 'high', 'medium')
DOUBT_BELOW = 75               # same line as weekDecision: under 75% is a doubt
GUEST_SHORTLIST = 3

# The headline is the first of these rules that fires. Reorder here and nowhere else.
HEADLINE_RULES = ('starter_doubt', 'starter_blank', 'unused_free_transfers', 'captain_choice')


#################################################
#                  Injuries                     #
#################################################

def resolve_injuries(squad, availability, risks):
    if not squad:
        return {'state': NEEDS_TEAM, 'players': []}
    players = [{'id': p['id'], 'name': availability[p['id']]['name'], 'starter': p['starter'],
                'is_captain': p['is_captain'], 'risk_pct': risks[p['id']]['pct'],
                'tier': risks[p['id']]['tier'], 'reasons': risks[p['id']]['reasons']}
               for p in squad
               if p['id'] in availability and risks.get(p['id'], {}).get('tier') in WORTH_A_LOOK]
    # Starters first, then the biggest risk; the captain wins a tie, then name, so the order never wobbles.
    players.sort(key=lambda x: (not x['starter'], -x['risk_pct'], not x['is_captain'], x['name']))
    for player in players:
        del player['is_captain']
    return {'state': NEEDS_LOOK if players else NOTHING_TO_DO, 'players': players}


#################################################
#                  Captaincy                    #
#################################################

def _is_worry(pid, availability, risks):
    chance = availability[pid]['chance']
    return (chance is not None and chance < DOUBT_BELOW) or risks.get(pid, {}).get('tier') in WORTH_A_LOOK


def _ranked_options(player_ids, availability, predictions, fixtures, risks):
    options = [pid for pid in player_ids
               if pid in predictions and pid in availability
               and availability[pid]['team'] in fixtures and not _is_worry(pid, availability, risks)]
    options.sort(key=lambda pid: (-predictions[pid], availability[pid]['name']))
    return [{'id': pid, 'name': availability[pid]['name'],
             'expected_involvement': round(predictions[pid], 1),
             'fixture': fixtures[availability[pid]['team']]} for pid in options]


def resolve_captaincy(squad, availability, predictions, fixtures, risks):
    """Captaincy applies every week, so it always needs a look.

    With a team: their fit starters with a match. As a guest: the top three across everyone.
    """
    if squad:
        shortlist = _ranked_options([p['id'] for p in squad if p['starter']],
                                    availability, predictions, fixtures, risks)
    else:
        shortlist = _ranked_options(list(predictions), availability, predictions,
                                    fixtures, risks)[:GUEST_SHORTLIST]
    return {'state': NEEDS_LOOK,
            'suggested': shortlist[0] if shortlist else None,
            'vice': shortlist[1] if len(shortlist) > 1 else None,
            'shortlist': shortlist}


#################################################
#                  Headline                     #
#################################################

def _starter_doubt(ctx):
    starters = [p for p in ctx['injuries'].get('players', []) if p['starter']]
    if not starters:
        return None
    top = starters[0]
    return {'decision': 'injuries', 'reason_key': 'starter_doubt', 'player': top['name'],
            'tier': top['tier'], 'risk_pct': top['risk_pct']}


def _starter_blank(ctx):
    if not ctx['fixtures']:
        return None   # no fixture data at all says nothing about blanks
    availability = ctx['availability']
    names = sorted(availability[p['id']]['name'] for p in ctx['squad']
                   if p['starter'] and p['id'] in availability
                   and availability[p['id']]['team'] not in ctx['fixtures'])
    if not names:
        return None
    return {'decision': 'transfers', 'reason_key': 'starter_blank', 'player': names[0], 'players': names}


def _unused_free_transfers(ctx):
    # Release 4 supplies free_transfers; until then this rule never fires.
    count = ctx.get('free_transfers')
    if not count:
        return None
    return {'decision': 'transfers', 'reason_key': 'unused_free_transfers', 'player': None, 'count': count}


def _captain_choice(ctx):
    suggested = ctx['captaincy'].get('suggested')
    if suggested is None:
        return {'decision': 'captaincy', 'reason_key': 'captain_no_prediction', 'player': None}
    return {'decision': 'captaincy', 'reason_key': 'captain_choice', 'player': suggested['name']}


RULE_CHECKS = {
    'starter_doubt': _starter_doubt,
    'starter_blank': _starter_blank,
    'unused_free_transfers': _unused_free_transfers,
    'captain_choice': _captain_choice,
}


def select_headline(ctx, rules=HEADLINE_RULES):
    for name in rules:
        headline = RULE_CHECKS[name](ctx)
        if headline:
            return headline
    return None
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_hub_rules.py tests/step_defs/test_this_week_headline.py -q`
Expected: PASS (6 unit tests, 7 scenarios).

- [ ] **Step 7: Commit**

```bash
git add FPL_site/hubRules.py features/this_week/headline.feature tests/step_defs/test_this_week_headline.py tests/test_hub_rules.py
git commit -m "Choose the headline decision and work out injury and captain states"
```

---

### Task 5: Hub composer and JSON route (1d)

**Files:**
- Create: `FPL_site/thisWeekHub.py`
- Modify: `FPL_site/views.py` (imports, plus a new route after `week_this_week_decision`)
- Modify: `tests/test_regression_routes.py`
- Create: `tests/test_this_week_hub.py`

**Interfaces:**
- Consumes: Tasks 2–4; `weekDecision.fetch_availability_rows`, `fetch_team_expected_goals_rows`, `fetch_fixture_rows`, `involvement_predictions`, `fixtures_by_team`; `dataModels.connect_db`, `season_start`.
- Produces:
  - `build_hub(gameweek, squad_context, availability_rows, predictions, fixtures, history_rows) -> dict`
  - `get_this_week_hub(gameweek, last_gameweek, team_id=None) -> dict`, where `team_id` is an int, `None` or `'invalid'`
  - JSON shape:

```json
{"status": "ready", "gameweek": 6, "based_on": "your_team", "team_status": "ok", "squad_gameweek": 5,
 "headline": {"decision": "injuries", "reason_key": "starter_doubt", "player": "Rice", "tier": "high", "risk_pct": 75},
 "decisions": {"injuries": {"state": "needs_look", "players": [...]},
               "transfers": {"state": "not_ready"}, "chips": {"state": "not_ready"},
               "captaincy": {"state": "needs_look", "suggested": {...}, "vice": {...}, "shortlist": [...]}}}
```

  - `team_status` is one of `'ok'`, `'none'`, `'invalid'`, `'not_found'`, `'unavailable'`. When the database is down, the result is `{"status": "unavailable", "gameweek": 6}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_this_week_hub.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import json
import pytest

from FPL_site import app
import FPL_site.views as views
import FPL_site.thisWeekHub as hub
from FPL_site.thisWeekHub import build_hub

ROWS = [{'id': 1, 'web_name': 'Saka', 'team': 10, 'chance_of_playing_next_round': 25,
         'news': 'Hamstring', 'element_type': 3, 'status': 'd',
         'expected_goals': 3.0, 'expected_assists': 2.0},
        {'id': 2, 'web_name': 'Haaland', 'team': 20, 'chance_of_playing_next_round': None,
         'news': '', 'element_type': 4, 'status': 'a', 'expected_goals': 6.0, 'expected_assists': 1.0}]
FIXTURES = {10: {'opponent': 'Everton', 'is_home': True, 'difficulty': 2},
            20: {'opponent': 'Burnley', 'is_home': False, 'difficulty': 2}}
SQUAD = {'status': 'ok', 'bank': 5, 'squad_gameweek': 5, 'squad': [
    {'id': 1, 'slot': 1, 'starter': True, 'is_captain': False, 'is_vice': False},
    {'id': 2, 'slot': 2, 'starter': True, 'is_captain': True, 'is_vice': False}]}


def test_personal_hub_shape():
    result = build_hub(6, SQUAD, ROWS, {1: 0.5, 2: 1.4}, FIXTURES, [])
    assert result['status'] == 'ready' and result['based_on'] == 'your_team'
    assert result['headline']['reason_key'] == 'starter_doubt'
    assert result['decisions']['transfers'] == {'state': 'not_ready'}
    assert result['decisions']['captaincy']['suggested']['name'] == 'Haaland'


def test_guest_hub_when_team_unknown():
    result = build_hub(6, {'status': 'not_found'}, ROWS, {2: 1.4}, FIXTURES, [])
    assert result['based_on'] == 'everyone' and result['team_status'] == 'not_found'
    assert result['decisions']['injuries']['state'] == 'needs_team'
    assert result['headline']['reason_key'] == 'captain_choice'


def test_json_has_no_sentences():
    # Facts and keys only: the longest free text allowed is the official news line.
    text = json.dumps(build_hub(6, SQUAD, ROWS, {1: 0.5, 2: 1.4}, FIXTURES, []))
    assert 'your call' not in text.lower() and 'worth' not in text.lower()


def test_database_down_is_unavailable(monkeypatch):
    monkeypatch.setattr(hub, 'connect_db', lambda: None)
    monkeypatch.setattr(hub, 'get_squad_context', lambda t, g: {'status': 'ok', 'squad': []})
    assert hub.get_this_week_hub(6, 5, team_id=1) == {'status': 'unavailable', 'gameweek': 6}


def test_api_down_still_gives_a_guest_hub(monkeypatch):
    monkeypatch.setattr(hub, 'get_squad_context', lambda t, g: {'status': 'unavailable'})
    monkeypatch.setattr(hub, '_load_week_data', lambda gw, ids: (ROWS, {2: 1.4}, FIXTURES, []))
    result = hub.get_this_week_hub(6, 5, team_id=1)
    assert result['based_on'] == 'everyone' and result['team_status'] == 'unavailable'


def test_invalid_and_missing_team_skip_the_api(monkeypatch):
    def boom(*a):
        raise AssertionError('should not call the official API')
    monkeypatch.setattr(hub, 'get_squad_context', boom)
    monkeypatch.setattr(hub, '_load_week_data', lambda gw, ids: (ROWS, {}, FIXTURES, []))
    assert hub.get_this_week_hub(6, 5, team_id='invalid')['team_status'] == 'invalid'
    assert hub.get_this_week_hub(6, 5, team_id=None)['team_status'] == 'none'


@pytest.fixture
def client():
    return app.test_client()


def test_route_is_hidden_when_flag_off(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', False, raising=False)
    assert client.get('/api/week/this-week?gameweek=6').status_code == 404


def test_route_validates_gameweek(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    assert client.get('/api/week/this-week?gameweek=99').status_code == 400


def test_route_passes_parsed_arguments(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    seen = {}
    def fake(gameweek, last_gameweek, team_id=None):
        seen.update(gameweek=gameweek, last=last_gameweek, team=team_id)
        return {'status': 'ready'}
    monkeypatch.setattr(views, 'get_this_week_hub', fake)
    assert client.get('/api/week/this-week?gameweek=6&last_gameweek=5&team_id=12x').status_code == 200
    assert seen == {'gameweek': 6, 'last': 5, 'team': 'invalid'}


def test_route_error_is_json_500(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    def broken(*a, **k):
        raise RuntimeError('x')
    monkeypatch.setattr(views, 'get_this_week_hub', broken)
    resp = client.get('/api/week/this-week?gameweek=6')
    assert resp.status_code == 500 and resp.get_json() == {'error': 'server_error'}
```

Add to `tests/test_regression_routes.py`, after `test_data_routes_respond`:

```python
def test_hub_route_responds_with_flag_on(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    monkeypatch.setattr(views, 'get_this_week_hub',
                        lambda *a, **k: {'status': 'unavailable', 'gameweek': 6})
    assert client.get('/api/week/this-week?gameweek=6&last_gameweek=5').status_code == 200
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_this_week_hub.py tests/test_regression_routes.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'FPL_site.thisWeekHub'`.

- [ ] **Step 3: Implement the composer**

`FPL_site/thisWeekHub.py`:

```python
"""The This Week hub: composes squad, signals and rules into one payload (release 1).

build_hub is pure. get_this_week_hub is the live-route entry point: it calls the
official API for the squad, then reads everything else from the database.
"""
import logging

from FPL_site.dataModels import connect_db, season_start
from FPL_site.weekDecision import (
    fetch_availability_rows, fetch_team_expected_goals_rows, fetch_fixture_rows,
    involvement_predictions, fixtures_by_team,
)
from FPL_site.squadContext import get_squad_context
from FPL_site.hubSignals import fetch_squad_history_rows, player_signals, assess_risk
from FPL_site.hubRules import (
    resolve_injuries, resolve_captaincy, select_headline, NOT_READY,
)

logger = logging.getLogger(__name__)


def hub_availability(rows):
    """Like weekDecision.availability_from_rows, plus status, which the risk check needs."""
    return {r['id']: {'name': r['web_name'], 'team': r['team'],
                      'chance': r['chance_of_playing_next_round'],
                      'status': r['status'], 'news': r['news'] or ''}
            for r in rows}


def build_hub(gameweek, squad_context, availability_rows, predictions, fixtures, history_rows):
    squad = squad_context.get('squad', []) if squad_context['status'] == 'ok' else []
    availability = hub_availability(availability_rows)
    signals = player_signals(history_rows)
    risks = {p['id']: assess_risk(availability[p['id']], signals.get(p['id']), gameweek)
             for p in squad if p['id'] in availability}
    injuries = resolve_injuries(squad, availability, risks)
    captaincy = resolve_captaincy(squad, availability, predictions, fixtures, risks)
    headline = select_headline({'squad': squad, 'availability': availability, 'fixtures': fixtures,
                                'injuries': injuries, 'captaincy': captaincy})
    return {
        'status': 'ready', 'gameweek': gameweek,
        'based_on': 'your_team' if squad else 'everyone',
        'team_status': squad_context['status'],
        'squad_gameweek': squad_context.get('squad_gameweek') if squad else None,
        'headline': headline,
        'decisions': {'injuries': injuries,
                      'transfers': {'state': NOT_READY},
                      'chips': {'state': NOT_READY},
                      'captaincy': captaincy},
    }


def _load_week_data(gameweek, squad_ids):
    """Everything the hub reads from the database, or None if it can't connect."""
    conn = connect_db()
    if conn is None:
        logger.error("get_this_week_hub: could not connect to the database.")
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        availability_rows = fetch_availability_rows(cursor, season_start)
        predictions = involvement_predictions(availability_rows,
                                              fetch_team_expected_goals_rows(cursor, gameweek))
        fixtures = fixtures_by_team(fetch_fixture_rows(cursor, season_start, gameweek))
        history_rows = fetch_squad_history_rows(cursor, season_start, squad_ids, gameweek)
    finally:
        conn.close()
    return availability_rows, predictions, fixtures, history_rows


def get_this_week_hub(gameweek, last_gameweek, team_id=None):
    """team_id: an int, None for a guest, or 'invalid'. Only an int calls the official API."""
    if isinstance(team_id, int):
        squad_context = get_squad_context(team_id, last_gameweek)
    else:
        squad_context = {'status': 'invalid' if team_id == 'invalid' else 'none'}
    squad_ids = [p['id'] for p in squad_context.get('squad', [])] if squad_context['status'] == 'ok' else []

    data = _load_week_data(gameweek, squad_ids)
    if data is None:
        return {'status': 'unavailable', 'gameweek': gameweek}
    return build_hub(gameweek, squad_context, *data)
```

- [ ] **Step 4: Add the route**

In `FPL_site/views.py`:
- add `abort` to the flask import if it isn't already there;
- add `from FPL_site.thisWeekHub import get_this_week_hub` next to the existing `weekDecision` import;
- add this route after `week_this_week_decision`:

```python
@app.route('/api/week/this-week')
def week_this_week_hub():
    # Hidden until launch, so nobody can call it while the hub is behind the flag.
    if not getattr(current_config, 'THIS_WEEK_HUB', False):
        abort(404)
    logger.info("Request for the This Week hub")
    gameweek = _parse_gameweek(request.args.get('gameweek', ''))
    if gameweek is None:
        return jsonify({'error': 'invalid_gameweek'}), 400
    last_gameweek = _parse_gameweek(request.args.get('last_gameweek', ''))
    team_id = _parse_team_id(request.args.get('team_id'))
    try:
        return jsonify(get_this_week_hub(gameweek, last_gameweek, team_id=team_id))
    except Exception as e:
        logger.error(f"Error building the This Week hub: {e}")
        return jsonify({'error': 'server_error'}), 500
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `vs-env/Scripts/python.exe -m pytest -q`
Expected: all pass, including the existing suite.

- [ ] **Step 6: Live check (reads the real database and API; writes nothing)**

```bash
THIS_WEEK_HUB=1 SERVER_PORT=5050 vs-env/Scripts/python.exe runserver.py &
curl -sS "http://127.0.0.1:5050/api/week/this-week?gameweek=6&last_gameweek=5" | head -c 600; echo
curl -sS "http://127.0.0.1:5050/api/week/this-week?gameweek=6&last_gameweek=5&team_id=1" | head -c 600; echo
```

Expected: `"based_on":"everyone"`, then `"based_on":"your_team"`. If the history query fails because a column is missing, stop and report it.

- [ ] **Step 7: Commit**

```bash
git add FPL_site/thisWeekHub.py FPL_site/views.py tests/test_this_week_hub.py tests/test_regression_routes.py
git commit -m "Serve the This Week hub as JSON behind THIS_WEEK_HUB"
```

---

### Task 6: Read-only hub in Jinja (1.5d)

**Files:**
- Create: `FPL_site/templates/partials/hub_macros.html`
- Create: `FPL_site/templates/partials/week_hub.html`
- Modify: `FPL_site/templates/partials/week_v2.html` (the `#decision-hub` block)
- Modify: `FPL_site/views.py` (`home()` and `_week_v2_context()`)
- Modify: `FPL_site/static/content/home.css`
- Create: `tests/test_week_hub_template.py`
- Modify: `tests/test_regression_routes.py`

**Interfaces:**
- Consumes: the Task 5 payload.
- Produces:
  - Template context `hub_enabled: bool` and `hub: dict|None`.
  - DOM contract for Task 7: `#this-week-hub[data-gameweek][data-last-gameweek][data-based-on]` > `#hub-body` (headline and rows, replaced by JavaScript) and `#hub-team-slot` > `form#hub-team-form` > `input#hub-team-input[name=team_id]`.
  - Classes `.hub-headline`, `.hub-rows`, `.hub-row[data-key][data-state]`, `.hub-badge`.

- [ ] **Step 1: Write the failing tests**

`tests/test_week_hub_template.py`:

```python
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import re
import pytest
from flask import render_template

from FPL_site import app
import FPL_site.views as views

STATE = {'this_week': {'mode': 'upcoming', 'gameweek': 6, 'deadline': '2026-10-10T10:00:00Z'},
         'last_week': {'status': 'final', 'gameweek': 5, 'deadline': '2026-10-03T10:00:00Z'}}

OPTION = {'id': 2, 'name': 'Haaland', 'expected_involvement': 1.4,
          'fixture': {'opponent': 'Burnley', 'is_home': False, 'difficulty': 2}}
VICE = dict(OPTION, id=3, name='Salah')


def hub(**overrides):
    base = {'status': 'ready', 'gameweek': 6, 'based_on': 'your_team', 'team_status': 'ok',
            'squad_gameweek': 5,
            'headline': {'decision': 'injuries', 'reason_key': 'starter_doubt', 'player': 'Rice',
                         'tier': 'high', 'risk_pct': 75},
            'decisions': {
                'injuries': {'state': 'needs_look', 'players': [
                    {'id': 1, 'name': 'Rice', 'starter': True, 'risk_pct': 75, 'tier': 'high',
                     'reasons': [{'key': 'official_doubt', 'chance': 25, 'news': 'Knock'}]}]},
                'transfers': {'state': 'not_ready'}, 'chips': {'state': 'not_ready'},
                'captaincy': {'state': 'needs_look', 'suggested': OPTION, 'vice': VICE,
                              'shortlist': [OPTION, VICE]}}}
    base.update(overrides)
    return base


def render(hub_payload):
    with app.test_request_context('/this-week'):
        return render_template('partials/week_v2.html', week_state=STATE, this_week_copy=None,
                               last_week_copy=None, hub_enabled=True, hub=hub_payload)


def test_headline_and_rows_render():
    html = render(hub())
    assert 'id="this-week-hub"' in html and 'id="hub-body"' in html
    assert 'Rice is a doubt for this gameweek' in html
    assert 'data-key="injuries" data-state="needs_look"' in html
    assert 'Our lean: Haaland, with Salah as vice' in html
    assert 'data-key="transfers"' not in html   # not built yet, so not shown
    assert 'More decisions are on the way' in html


def test_states_pair_an_icon_with_words():
    html = render(hub())
    assert re.search(r'<span aria-hidden="true">[^<]+</span>\s*Needs a look', html)


def test_nothing_to_do_and_guest_states():
    payload = hub(based_on='everyone', team_status='none')
    payload['decisions']['injuries'] = {'state': 'needs_team', 'players': []}
    html = render(payload)
    assert 'Add your team number below to check your players' in html
    assert 'id="hub-team-form"' in html and 'method="get"' in html
    fit = hub()
    fit['decisions']['injuries'] = {'state': 'nothing_to_do', 'players': []}
    assert 'Nothing to do this week' in render(fit)


def test_team_form_hidden_for_a_known_team():
    assert 'id="hub-team-form"' not in render(hub())


@pytest.mark.parametrize('team_status,phrase', [
    ('not_found', "couldn't find that team number"),
    ('unavailable', "couldn't reach the official game"),
    ('invalid', 'numbers only'),
])
def test_team_problems_are_explained_kindly(team_status, phrase):
    html = render(hub(based_on='everyone', team_status=team_status))
    assert phrase in html


def test_unavailable_hub_is_calm():
    html = render({'status': 'unavailable', 'gameweek': 6})
    assert "We couldn't load this week's decisions" in html


def test_no_acronyms_in_any_state():
    payload = hub()
    payload['headline'] = {'decision': 'transfers', 'reason_key': 'starter_blank', 'player': 'A',
                           'players': ['A', 'B']}
    for html in (render(payload), render(hub(based_on='everyone', team_status='invalid'))):
        text = re.sub(r'<[^>]+>', ' ', html)
        for pattern in [r'\bGW\s?\d', r'\bFPL\b', r'\bVC\b', r'\bpts\b', r'\bEO\b', r'\bxG\b']:
            assert not re.search(pattern, text), pattern


def test_flag_off_keeps_the_old_decision_slot():
    with app.test_request_context('/this-week'):
        html = render_template('partials/week_v2.html', week_state=STATE,
                               this_week_copy=None, last_week_copy=None)
    assert 'id="decision-slot"' in html and 'id="this-week-hub"' not in html


def test_page_route_builds_the_hub_only_when_flag_on(monkeypatch):
    calls = []
    monkeypatch.setattr(views, 'get_week_view_state', lambda: STATE)
    monkeypatch.setattr(views, 'get_this_week_hub',
                        lambda gw, last, team_id=None: calls.append((gw, last, team_id)) or hub())
    client = app.test_client()
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', False, raising=False)
    client.get('/this-week')
    assert calls == []
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    html = client.get('/this-week?team_id=123').get_data(as_text=True)
    assert calls == [(6, 5, 123)] and 'id="this-week-hub"' in html


def test_page_survives_a_hub_error(monkeypatch):
    monkeypatch.setattr(views, 'get_week_view_state', lambda: STATE)
    def broken(*a, **k):
        raise RuntimeError('x')
    monkeypatch.setattr(views, 'get_this_week_hub', broken)
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    resp = app.test_client().get('/this-week')
    assert resp.status_code == 200
    assert "We couldn't load this week's decisions" in resp.get_data(as_text=True)
```

Add to `tests/test_regression_routes.py`:

```python
def test_week_page_with_hub_flag_on(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    monkeypatch.setattr(views, 'get_this_week_hub',
                        lambda *a, **k: {'status': 'unavailable', 'gameweek': 6})
    html = client.get('/this-week').get_data(as_text=True)
    for marker in ['id="this-week-hub"', 'id="gw-panel-live"', 'data-week-v2="true"']:
        assert marker in html, marker
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `vs-env/Scripts/python.exe -m pytest tests/test_week_hub_template.py tests/test_regression_routes.py -q`
Expected: FAIL (`id="this-week-hub"` not in the HTML).

- [ ] **Step 3: Write the macros**

`FPL_site/templates/partials/hub_macros.html`:

```jinja
{# Short factual lines for the read-only hub, one per reason_key. hubCopy.js swaps
   in the conversational wording when JavaScript runs; these are the no-JavaScript words. #}

{% macro name_list(names) -%}
{%- if names|length == 1 %}{{ names[0] }}{% else %}{{ names[:-1]|join(', ') }} and {{ names[-1] }}{% endif -%}
{%- endmacro %}

{% macro headline_line(h) -%}
{%- if h.reason_key == 'starter_doubt' -%}
  {%- if h.tier == 'confirmed' %}{{ h.player }} is set to miss this gameweek{% else %}{{ h.player }} is a doubt for this gameweek{% endif -%}
{%- elif h.reason_key == 'starter_blank' -%}
  {%- if h.players|length == 1 %}{{ h.player }} has no match this gameweek{% else %}{{ name_list(h.players) }} have no match this gameweek{% endif -%}
{%- elif h.reason_key == 'unused_free_transfers' -%}
  You have {{ h.count }} free transfer{{ 's' if h.count != 1 }} to use
{%- elif h.reason_key == 'captain_choice' -%}
  Our lean for captain: {{ h.player }}
{%- else -%}
  Captain numbers aren't in yet this week
{%- endif -%}
{%- endmacro %}

{% macro row_line(key, d) -%}
{%- if d.state == 'needs_team' -%}
  Add your team number below to check your players
{%- elif key == 'injuries' -%}
  {%- if d.players %}To check: {{ name_list(d.players|map(attribute='name')|list) }}{% else %}No injury worries in your team this week{% endif -%}
{%- elif key == 'captaincy' -%}
  {%- if d.suggested and d.vice %}Our lean: {{ d.suggested.name }}, with {{ d.vice.name }} as vice
  {%- elif d.suggested %}Our lean: {{ d.suggested.name }}
  {%- else %}Captain numbers aren't in yet this week{% endif -%}
{%- endif -%}
{%- endmacro %}

{# Every state is an icon AND words, never colour alone. The icon is hidden from
   screen readers because the words already say it. #}
{% macro state_badge(state) -%}
{%- set badges = {'needs_look': ('!', 'Needs a look'), 'nothing_to_do': ('✓', 'Nothing to do this week'),
                  'decided': ('✓', 'Decided'), 'needs_team': ('+', 'Add your team')} -%}
{%- set icon, label = badges.get(state, ('•', 'Coming soon')) -%}
<span class="hub-badge hub-badge--{{ state }}"><span aria-hidden="true">{{ icon }}</span> {{ label }}</span>
{%- endmacro %}
```

- [ ] **Step 4: Write the hub partial**

`FPL_site/templates/partials/week_hub.html`:

```jinja
{# Read-only This Week hub (release 1, behind THIS_WEEK_HUB). Usable with no
   JavaScript; hubView.js redraws #hub-body from /api/week/this-week. Included
   inside home.html's content block, so no link or script tags here. #}
{% from 'partials/hub_macros.html' import headline_line, row_line, state_badge %}
{% set titles = {'injuries': 'Injuries', 'transfers': 'Transfers', 'chips': 'Chips', 'captaincy': 'Captain and vice'} %}
<div id="this-week-hub"
     data-gameweek="{{ this_week.gameweek if this_week.mode == 'upcoming' and this_week.gameweek is not none else '' }}"
     data-last-gameweek="{{ last_week.gameweek if last_week.status == 'final' else '' }}"
     data-based-on="{{ hub.based_on if hub and hub.based_on else '' }}">
    <p class="hub-notice">We can't change your team for you. Decide here, then make the changes in the official app before the deadline.</p>
    <div id="hub-body">
    {% if hub and hub.status == 'ready' %}
        <div class="card hub-headline">
            <div class="eyebrow-sm">The big one this week</div>
            <h3 class="recap-verdict">{{ headline_line(hub.headline) }}</h3>
        </div>
        <h3>This week's decisions</h3>
        <ul class="hub-rows">
        {% for key in ['injuries', 'transfers', 'chips', 'captaincy'] %}
            {% set d = hub.decisions[key] %}
            {% if d.state != 'not_ready' %}
            <li class="card hub-row" data-key="{{ key }}" data-state="{{ d.state }}">
                <div class="hub-row-head"><span class="hub-row-title">{{ titles[key] }}</span>{{ state_badge(d.state) }}</div>
                <p class="sub">{{ row_line(key, d) }}</p>
            </li>
            {% endif %}
        {% endfor %}
        </ul>
        <p class="sub">More decisions are on the way. We'll add them here as they're ready.</p>
    {% else %}
        <div class="card">
            <h3 class="recap-verdict">We couldn't load this week's decisions</h3>
            <p>Nothing is wrong on your side. Try again in a moment.</p>
        </div>
    {% endif %}
    </div>
    <div id="hub-team-slot">
    {% if not hub or hub.based_on != 'your_team' %}
        <form class="card recap-team-form" id="hub-team-form" method="get" action="{{ url_for('home') }}">
            {% if hub and hub.team_status == 'not_found' %}<p class="sub">We couldn't find that team number. Check it and try again.</p>
            {% elif hub and hub.team_status == 'unavailable' %}<p class="sub">We couldn't reach the official game just now, so this is for everyone. Try again in a moment.</p>
            {% elif hub and hub.team_status == 'invalid' %}<p class="sub">Team numbers are numbers only, for example 1234567.</p>{% endif %}
            <label for="hub-team-input">Your team number, to make this about your team</label>
            <div class="recap-team-row">
                <input id="hub-team-input" name="team_id" inputmode="numeric" pattern="[0-9]*" autocomplete="off" placeholder="e.g. 1234567" required>
                <button type="submit" class="btn-pill">Show my team</button>
            </div>
        </form>
    {% endif %}
    </div>
</div>
```

- [ ] **Step 5: Switch on the hub in `week_v2.html`**

Replace the inside of `<div id="decision-hub" …>` (the `<h3>This week's decisions</h3>`, `#decision-slot` and the "More decisions" paragraph) with:

```jinja
                    {% if hub_enabled %}
                    {% include 'partials/week_hub.html' %}
                    {% else %}
                    <h3 style="margin-top:12px;">This week's decisions</h3>
                    <div id="decision-slot">
                        <div class="card" aria-busy="true" aria-label="Loading this week's decision">
                            <div class="skeleton" style="height:18px; width:55%; margin-bottom:10px;"></div>
                            <div class="skeleton" style="height:14px; width:85%;"></div>
                        </div>
                    </div>
                    <p class="sub">More decisions are on the way. We'll add them here as they're ready.</p>
                    {% endif %}
```

`weekV2.js` `loadDecision()` already returns early when `#decision-slot` is missing, so the old card stays quiet with the flag on.

- [ ] **Step 6: Pass the hub from `home()`**

In `FPL_site/views.py`, replace `_week_v2_context()` with:

```python
def _week_v2_context():
    """Template context for the Week tab rebuild, plus the hub when THIS_WEEK_HUB is on."""
    week_state = get_week_view_state()
    this_week = week_state['this_week']
    last_week = week_state['last_week']
    context = {
        'week_state': week_state,
        'this_week_copy': this_week_empty_copy(this_week['mode'], _hours_since(this_week['deadline'])),
        'last_week_copy': last_week_empty_copy(last_week['status'], last_week['gameweek']),
        'hub_enabled': getattr(current_config, 'THIS_WEEK_HUB', False),
        'hub': None,
    }
    if context['hub_enabled'] and this_week['mode'] == 'upcoming' and this_week['gameweek']:
        last_gameweek = last_week['gameweek'] if last_week['status'] == 'final' else None
        try:
            # ?team_id= comes from the hub's plain form, so the page works without JavaScript.
            context['hub'] = get_this_week_hub(this_week['gameweek'], last_gameweek,
                                               team_id=_parse_team_id(request.args.get('team_id')))
        except Exception as e:
            logger.error(f"Error building the This Week hub for the page: {e}")
    return context
```

`_parse_team_id` is defined further down the file. That's fine, because the function is only called at request time.

- [ ] **Step 7: Add the styles**

Append to `FPL_site/static/content/home.css`:

```css
/* This Week hub (release 1). State badges always carry an icon and words, never colour alone. */
.hub-notice { font-size: 13px; color: var(--charcoal); background: var(--offwhite); border: 1px solid var(--grey); border-radius: 12px; padding: 10px 12px; margin: 8px 0 12px; }
.hub-headline { border-left: 4px solid var(--plum); }
.hub-rows { list-style: none; padding: 0; margin: 0 0 12px; }
.hub-row { border-radius: 12px; margin-bottom: 10px; }
.hub-row-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
.hub-row-title { font-weight: 700; color: var(--charcoal); font-size: 15px; }
.hub-row .sub { margin: 6px 0 0; }
.hub-badge { font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 100px; white-space: nowrap; }
/* Text colours chosen for at least 4.5:1 contrast on their backgrounds. */
.hub-badge--needs_look { background: var(--plum); color: #fff; }
.hub-badge--nothing_to_do { background: var(--grey); color: var(--charcoal); }
.hub-badge--decided { background: #1d7a70; color: #fff; }
.hub-badge--needs_team { background: var(--offwhite); color: var(--plum); border: 1.5px solid var(--plum); }
.hub-row[data-state="nothing_to_do"] { background: var(--offwhite); box-shadow: none; }
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `vs-env/Scripts/python.exe -m pytest -q`
Expected: all pass. The existing `test_week_v2_template.py` tests still pass because they don't set `hub_enabled`.

- [ ] **Step 9: Check in the browser with no JavaScript, at 375px**

Start the server with `THIS_WEEK_HUB=1`. Open `/this-week`, then `/this-week?team_id=1`, with JavaScript disabled in DevTools at a 375px width. Confirm all of the following:
- the headline and rows render;
- the team form submits and personalises the page;
- nothing overflows sideways;
- the badges read correctly in greyscale (DevTools → Rendering → emulate achromatopsia).

- [ ] **Step 10: Commit**

```bash
git add FPL_site/templates/partials/hub_macros.html FPL_site/templates/partials/week_hub.html FPL_site/templates/partials/week_v2.html FPL_site/views.py FPL_site/static/content/home.css tests/test_week_hub_template.py tests/test_regression_routes.py
git commit -m "Render a read-only This Week hub that works without JavaScript"
```

---

### Task 7: Phrase bank, JavaScript view and glue (1.5d)

**Files:**
- Create: `FPL_site/static/scripts/lib/hubCopy.js`
- Create: `FPL_site/static/scripts/lib/hubView.js`
- Modify: `FPL_site/static/scripts/weekV2.js`
- Create: `tests/js/hubCopy.test.js`
- Create: `tests/js/hubView.test.js`

**Interfaces:**
- Consumes: the Task 5 JSON and the Task 6 DOM contract; `escapeHtml(value)` from `lib/escapeHtml.js`; `readTeamId`, `saveTeamId` and `parseTeamId` from `lib/teamId.js`; `createLatestGuard()` from `lib/latestOnly.js`.
- Produces:
  - `headlineSentence(headline) -> string`
  - `rowSentence(key, decision) -> string`
  - `joinNames(names) -> string`
  - `renderHubBody(data) -> string` (inner HTML of `#hub-body`)
  - `DECISION_ORDER`
  - `loadHub()` inside `weekV2.js`

- [ ] **Step 1: Write the failing phrase bank tests**

`tests/js/hubCopy.test.js`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { headlineSentence, rowSentence, joinNames } from '../../FPL_site/static/scripts/lib/hubCopy.js';

const ACRONYMS = [/\bGW\s?\d/, /\bFPL\b/, /\bVC\b/, /\bpts\b/, /\bEO\b/, /\bxG\b/];
const HEADLINES = [
    { reason_key: 'starter_doubt', player: 'Rice', tier: 'high' },
    { reason_key: 'starter_doubt', player: 'Rice', tier: 'confirmed' },
    { reason_key: 'starter_blank', player: 'Saka', players: ['Saka', 'Rice'] },
    { reason_key: 'unused_free_transfers', count: 2 },
    { reason_key: 'captain_choice', player: 'Haaland' },
    { reason_key: 'captain_no_prediction', player: null },
];

test('every headline key has a sentence with no acronyms', () => {
    for (const h of HEADLINES) {
        const sentence = headlineSentence(h);
        assert.ok(sentence.length > 10, h.reason_key);
        for (const pattern of ACRONYMS) assert.doesNotMatch(sentence, pattern);
    }
});

test('the same input always gives the same sentence', () => {
    assert.equal(headlineSentence(HEADLINES[0]), headlineSentence({ ...HEADLINES[0] }));
});

test('advice is a suggestion, never an order', () => {
    assert.match(headlineSentence(HEADLINES[4]), /your call/i);
    assert.match(rowSentence('captaincy', { state: 'needs_look', suggested: { name: 'Haaland' }, vice: { name: 'Salah' } }), /your call/i);
});

test('names join naturally', () => {
    assert.equal(joinNames(['A']), 'A');
    assert.equal(joinNames(['A', 'B']), 'A and B');
    assert.equal(joinNames(['A', 'B', 'C']), 'A, B and C');
});

test('injury rows cover all three states', () => {
    assert.match(rowSentence('injuries', { state: 'needs_look', players: [{ name: 'Rice' }] }), /Rice/);
    assert.match(rowSentence('injuries', { state: 'nothing_to_do', players: [] }), /Nothing to do/);
    assert.match(rowSentence('injuries', { state: 'needs_team', players: [] }), /team number/);
});
```

- [ ] **Step 2: Write the failing view tests**

`tests/js/hubView.test.js`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderHubBody } from '../../FPL_site/static/scripts/lib/hubView.js';

const data = {
    status: 'ready', based_on: 'your_team',
    headline: { decision: 'captaincy', reason_key: 'captain_choice', player: '<b>Haaland</b>' },
    decisions: {
        injuries: { state: 'nothing_to_do', players: [] },
        transfers: { state: 'not_ready' }, chips: { state: 'not_ready' },
        captaincy: { state: 'needs_look', suggested: { name: 'Haaland' }, vice: { name: 'Salah' }, shortlist: [] },
    },
};

test('matches the server markup hooks', () => {
    const html = renderHubBody(data);
    assert.match(html, /class="card hub-headline"/);
    assert.match(html, /data-key="captaincy" data-state="needs_look"/);
    assert.doesNotMatch(html, /data-key="transfers"/);
});

test('escapes names so player data can never inject HTML', () => {
    assert.doesNotMatch(renderHubBody(data), /<b>Haaland<\/b>/);
});

test('every state badge has words next to its icon', () => {
    assert.match(renderHubBody(data), /<span aria-hidden="true">✓<\/span> Nothing to do this week/);
});

test('an unavailable hub shows the calm message', () => {
    assert.match(renderHubBody({ status: 'unavailable' }), /We couldn't load this week's decisions/);
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL with `Cannot find module …/hubCopy.js`.

- [ ] **Step 4: Implement the phrase bank**

`FPL_site/static/scripts/lib/hubCopy.js`:

```js
/***** hubCopy.js *****/
// The This Week hub's phrase bank. The server sends *facts and keys*
// ("starter_doubt", "Rice", tier "high"); this file decides the *words*.
//
// Why keep words out of the server? Tone is a product decision that changes
// often, and keeping every sentence in one file makes it easy to review for
// tone and acronyms. It is also pure: no DOM, no fetch, no randomness, so the
// same facts always give the same sentence and Node can test it directly.

// "A", "A and B", "A, B and C": how people actually list names out loud.
export function joinNames(names) {
    if (names.length <= 1) return names.join('');
    return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// One function per reason key, looked up by name. A lookup object like this
// replaces a long chain of if/else, and adding a new key is one new line.
const HEADLINES = {
    starter_doubt: (h) => (h.tier === 'confirmed'
        ? `${h.player} looks set to miss this one. Worth sorting before you do anything else. Your call.`
        : `${h.player} is a doubt this week. Worth a look before you lock anything else in.`),
    starter_blank: (h) => (h.players.length === 1
        ? `${h.player} has no match this gameweek, so they'd score nothing if they start.`
        : `${joinNames(h.players)} have no match this gameweek, so they'd score nothing if they start.`),
    unused_free_transfers: (h) => `You've got ${h.count} free transfer${h.count === 1 ? '' : 's'} sitting there. Worth seeing if one helps.`,
    captain_choice: (h) => `Our lean for captain is ${h.player}. Your call, as always.`,
    captain_no_prediction: () => "Our captain numbers aren't in yet this week, so this one's all yours for now.",
};

export function headlineSentence(headline) {
    const write = HEADLINES[headline.reason_key];
    // An unknown key should never show raw code words to a user.
    return write ? write(headline) : "Here's what we'd look at first this week.";
}

export function rowSentence(key, decision) {
    if (decision.state === 'needs_team') return "Add your team number and we'll check your players.";
    if (key === 'injuries') {
        const names = (decision.players || []).map((p) => p.name);
        if (names.length === 0) return 'Everyone looks fit. Nothing to do here this week.';
        return names.length === 1
            ? `${names[0]} needs a look before the deadline.`
            : `${names.length} players need a look: ${joinNames(names)}.`;
    }
    if (key === 'captaincy') {
        if (!decision.suggested) return "Captain numbers aren't in yet. Check back soon.";
        return decision.vice
            ? `Our lean: ${decision.suggested.name}, with ${decision.vice.name} as vice. Your call.`
            : `Our lean: ${decision.suggested.name}. Your call.`;
    }
    return '';
}
```

- [ ] **Step 5: Implement the view**

`FPL_site/static/scripts/lib/hubView.js`:

```js
/***** hubView.js *****/
// Turns the hub's JSON into HTML. Pure: it returns a string and never touches
// the page, so Node can test it. The markup deliberately mirrors
// templates/partials/week_hub.html: the server draws it first (so the page
// works without JavaScript), then this redraws it with friendlier words.
import { escapeHtml } from './escapeHtml.js';
import { headlineSentence, rowSentence } from './hubCopy.js';

// The order the four decisions appear in, everywhere.
export const DECISION_ORDER = ['injuries', 'transfers', 'chips', 'captaincy'];

const TITLES = { injuries: 'Injuries', transfers: 'Transfers', chips: 'Chips', captaincy: 'Captain and vice' };

// Each state gets an icon AND words. aria-hidden stops screen readers reading
// the icon, because the words already say the same thing.
const BADGES = {
    needs_look: ['!', 'Needs a look'],
    nothing_to_do: ['✓', 'Nothing to do this week'],
    decided: ['✓', 'Decided'],
    needs_team: ['+', 'Add your team'],
};

function badge(state) {
    const [icon, label] = BADGES[state] || ['•', 'Coming soon'];
    return `<span class="hub-badge hub-badge--${escapeHtml(state)}"><span aria-hidden="true">${icon}</span> ${label}</span>`;
}

function row(key, decision) {
    return `
        <li class="card hub-row" data-key="${key}" data-state="${escapeHtml(decision.state)}">
            <div class="hub-row-head"><span class="hub-row-title">${TITLES[key]}</span>${badge(decision.state)}</div>
            <p class="sub">${escapeHtml(rowSentence(key, decision))}</p>
        </li>`;
}

export function renderHubBody(data) {
    if (!data || data.status !== 'ready') {
        return `
            <div class="card">
                <h3 class="recap-verdict">We couldn't load this week's decisions</h3>
                <p>Nothing is wrong on your side. Try again in a moment.</p>
            </div>`;
    }
    // Decisions that aren't built yet are left out rather than shown half-done.
    const rows = DECISION_ORDER
        .filter((key) => data.decisions[key] && data.decisions[key].state !== 'not_ready')
        .map((key) => row(key, data.decisions[key]))
        .join('');
    // escapeHtml runs on the finished sentence, because player names come from outside data.
    return `
        <div class="card hub-headline">
            <div class="eyebrow-sm">The big one this week</div>
            <h3 class="recap-verdict">${escapeHtml(headlineSentence(data.headline))}</h3>
        </div>
        <h3>This week's decisions</h3>
        <ul class="hub-rows">${rows}</ul>
        <p class="sub">More decisions are on the way. We'll add them here as they're ready.</p>`;
}
```

- [ ] **Step 6: Run the JavaScript tests to verify they pass**

Run: `npm test`
Expected: PASS.

- [ ] **Step 7: Wire it into `weekV2.js`**

Add `parseTeamId` to the existing `teamId.js` import, and import the view:

```js
import { readTeamId, saveTeamId, clearTeamId, parseTeamId } from './lib/teamId.js';
import { renderHubBody } from './lib/hubView.js';
```

Add `const hubGuard = createLatestGuard();` next to `decisionGuard`.

In `initializeWeekV2()`, after `loadDecision();`, add:

```js
    adoptTeamFromAddress();
    bindHubTeamForm();
    loadHub();
```

In `bindChangeTeam` and `bindTeamForm`, change each `loadDecision();` call to:

```js
        loadDecision();
        loadHub();  // the hub personalises too
```

Append these functions:

```js
// Without JavaScript, the hub's form reloads the page as /this-week?team_id=123.
// If someone arrives that way, remember the number they typed, the same as the
// other team forms do, so the next visit is personal straight away.
function adoptTeamFromAddress() {
    const fromAddress = parseTeamId(new URLSearchParams(window.location.search).get('team_id'));
    if (fromAddress !== null) saveTeamId(safeLocalStorage(window), fromAddress);
}

// With JavaScript we can do better than a page reload: save the number, then
// fetch just the hub. preventDefault() stops the browser's own form submit.
function bindHubTeamForm() {
    const form = document.getElementById('hub-team-form');
    const input = document.getElementById('hub-team-input');
    if (!form || !input) return;
    form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (saveTeamId(safeLocalStorage(window), input.value) === null) {
            input.setCustomValidity('Please enter the number only, for example 1234567.');
            input.reportValidity();
            return;
        }
        loadHub();
        loadDecision();
    });
    input.addEventListener('input', () => input.setCustomValidity(''));
}

// Fetches the hub as JSON and redraws its body with the conversational wording.
// If anything goes wrong we simply keep what the server already drew: that
// version is plainer, but it's correct, so there's nothing to "fix" on screen.
async function loadHub() {
    const hub = document.getElementById('this-week-hub');
    const body = document.getElementById('hub-body');
    const teamSlot = document.getElementById('hub-team-slot');
    if (!hub || !body || !hub.dataset.gameweek) return;

    const query = new URLSearchParams({ gameweek: hub.dataset.gameweek });
    if (hub.dataset.lastGameweek) query.set('last_gameweek', hub.dataset.lastGameweek);
    const teamId = readTeamId(safeLocalStorage(window));
    if (teamId !== null) query.set('team_id', String(teamId));

    const token = hubGuard.start();  // a newer request makes this one stale
    body.setAttribute('aria-busy', 'true');
    try {
        const res = await fetch(`/api/week/this-week?${query}`);
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();
        if (!hubGuard.isLatest(token)) return;
        if (data.status === 'ready') {
            body.innerHTML = renderHubBody(data);
            hub.dataset.basedOn = data.based_on;
            // A known team doesn't need the "your team number" form any more.
            if (teamSlot) teamSlot.hidden = data.based_on === 'your_team';
        }
    } catch (err) {
        console.error("Failed to load this week's hub", err);
    } finally {
        if (hubGuard.isLatest(token)) body.removeAttribute('aria-busy');
    }
}
```

- [ ] **Step 8: Check syntax and run all tests**

```bash
node --check FPL_site/static/scripts/weekV2.js
node --check FPL_site/static/scripts/lib/hubCopy.js
node --check FPL_site/static/scripts/lib/hubView.js
npm test && vs-env/Scripts/python.exe -m pytest -q
```

Expected: all pass.

- [ ] **Step 9: Browser check at 375px**

With `THIS_WEEK_HUB=1`, check each of these:
1. A guest sees the conversational headline.
2. Entering `1` in the hub form personalises the hub without a reload, and the form hides.
3. With storage blocked (DevTools → Application → block site data) the hub still loads as a guest, and the console shows no errors.
4. Every row reads correctly with JavaScript off (fallback from Task 6).
5. Turning the flag off brings back the old single decision card.

- [ ] **Step 10: Commit**

```bash
git add FPL_site/static/scripts/lib/hubCopy.js FPL_site/static/scripts/lib/hubView.js FPL_site/static/scripts/weekV2.js tests/js/hubCopy.test.js tests/js/hubView.test.js
git commit -m "Upgrade the This Week hub with conversational wording and a no-reload team form"
```

---

## Release 1 gate

Run the roadmap's release gate:
- both test suites;
- `py_compile` and `node --check`;
- the live smoke with the flag on and off;
- the browser pass at 375px with JavaScript off and with storage blocked;
- one whole-branch review;
- the product checklist.

Then write the release summary. Its "worth reading to learn from" pick is the `HEADLINES` lookup object in `hubCopy.js`, which shows how an object of small functions replaces an if/else chain.
