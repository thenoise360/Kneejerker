import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.headToHead import (
    season_label, last_meetings, load_meeting_history, MEETING_LIMIT,
)


def match(season, event, home, away, hg, ag, kickoff=None):
    """One finished fixture already mapped to team codes, as the fetcher returns it."""
    month = '08' if event < 20 else '02'
    year = season if event < 20 else season + 1
    return {'season': season, 'event': event, 'home_code': home, 'away_code': away,
            'home_goals': hg, 'away_goals': ag,
            'kickoff': kickoff or f'{year}-{month}-{event:02d}T15:00:00Z'}


class FakeCursor:
    """Serves the queries the fetcher makes, keyed by season."""
    def __init__(self, snapshots, fixtures):
        self.snapshots, self.fixtures = snapshots, fixtures
        self.sql, self.year, self.queries = '', None, 0

    def execute(self, sql, params=None):
        self.sql, self.year = sql, params[0] if params else None
        self.queries += 1

    def fetchall(self):
        if 'bootstrapstatic_elements' in self.sql:
            return [{'team': t, 'team_code': c, 'gws': 30, 'last_gw': 38, 'n_rows': 900}
                    for t, c in self.snapshots.get(self.year, {}).items()]
        if 'bootstrapstatic_teams' in self.sql:
            return []
        return self.fixtures.get(self.year, [])


def raw(event, h, a, hg, ag, kickoff):
    return {'event': event, 'team_h': h, 'team_a': a, 'team_h_score': hg,
            'team_a_score': ag, 'kickoff_time': kickoff}


# ---- labels -------------------------------------------------------------
def test_season_label_two_digit_end():
    assert season_label(2025) == '2025/26'
    assert season_label(2099) == '2099/00'


# ---- pure function ------------------------------------------------------
def test_perspective_home_and_away():
    history = [match(2025, 5, 1, 2, 3, 1), match(2024, 8, 2, 1, 0, 2)]
    got = last_meetings(history, 1, 2)
    assert got[0] == {'season_label': '2025/26', 'is_home': True, 'result': 'won', 'score': '3–1'}
    # Team 1 was away in the second game and won 2-0: score is from its side.
    assert got[1] == {'season_label': '2024/25', 'is_home': False, 'result': 'won', 'score': '2–0'}


def test_lost_and_drew_results():
    history = [match(2025, 5, 2, 1, 2, 2), match(2024, 8, 1, 2, 0, 1)]
    got = last_meetings(history, 1, 2)
    assert [g['result'] for g in got] == ['drew', 'lost']
    assert got[1]['score'] == '0–1'


def test_ignores_other_pairings_and_newest_first():
    history = [match(2022, 3, 1, 2, 1, 0), match(2025, 3, 2, 1, 1, 0),
               match(2025, 9, 1, 3, 5, 5), match(2023, 3, 2, 1, 2, 2)]
    got = last_meetings(history, 1, 2)
    assert [g['season_label'] for g in got] == ['2025/26', '2023/24', '2022/23']


def test_limit_is_three():
    history = [match(2021 + i, 4, 1, 2, 1, 0) for i in range(5)]
    got = last_meetings(history, 1, 2)
    assert MEETING_LIMIT == 3 and len(got) == 3
    assert got[0]['season_label'] == '2025/26'


def test_duplicates_collapse():
    a = match(2024, 8, 1, 2, 1, 0)
    got = last_meetings([a, dict(a), dict(a)], 1, 2)
    assert len(got) == 1


def test_none_when_never_met():
    assert last_meetings([match(2025, 1, 5, 6, 1, 1)], 1, 2) == []
    assert last_meetings([], 1, 2) == []


# ---- fetcher ------------------------------------------------------------
def test_maps_shifting_ids_to_codes_across_seasons():
    # Team code 10 is id 4 in 2024 but id 9 in 2025; code 20 is id 7 then id 2.
    cur = FakeCursor(
        snapshots={2024: {4: 10, 7: 20}, 2025: {9: 10, 2: 20}},
        fixtures={2024: [raw(8, 4, 7, 2, 0, '2024-10-05T15:00:00Z')],
                  2025: [raw(5, 2, 9, 1, 1, '2025-09-20T15:00:00Z')]})
    history = load_meeting_history(cursor=cur, seasons=[2024, 2025])
    got = last_meetings(history, 10, 20)
    assert got == [
        {'season_label': '2025/26', 'is_home': False, 'result': 'drew', 'score': '1–1'},
        {'season_label': '2024/25', 'is_home': True, 'result': 'won', 'score': '2–0'},
    ]


def test_misfiled_row_outside_season_window_is_dropped():
    cur = FakeCursor(
        snapshots={2024: {1: 10, 2: 20}},
        fixtures={2024: [raw(8, 1, 2, 9, 0, '2025-10-05T15:00:00Z'),   # belongs to 2025
                         raw(9, 1, 2, 1, 0, '2024-10-05T15:00:00Z')]})
    history = load_meeting_history(cursor=cur, seasons=[2024])
    got = last_meetings(history, 10, 20)
    assert len(got) == 1 and got[0]['score'] == '1–0'


def test_duplicate_rows_in_the_table_collapse():
    row = raw(8, 1, 2, 1, 0, '2024-10-05T15:00:00Z')
    cur = FakeCursor(snapshots={2024: {1: 10, 2: 20}}, fixtures={2024: [row, dict(row)]})
    assert len(last_meetings(load_meeting_history(cursor=cur, seasons=[2024]), 10, 20)) == 1


def test_one_fetch_per_season_not_per_fixture():
    cur = FakeCursor(snapshots={2024: {1: 10, 2: 20}}, fixtures={2024: []})
    load_meeting_history(cursor=cur, seasons=[2024])
    assert cur.queries <= 3   # code map + (teams fallback) + fixtures


# ---- outlook payload ----------------------------------------------------
def test_outlook_payload_carries_last_meetings(monkeypatch):
    import FPL_site.matchPredictionEngine as engine
    import FPL_site.headToHead as h2h

    class Conn:
        def cursor(self, dictionary=True):
            return OutlookCursor()
        def close(self):
            pass

    class OutlookCursor:
        def execute(self, sql, params=None):
            pass
        def fetchall(self):
            return [{'gameweek': 6, 'is_home': 1, 'opponent_id': 2,
                     'own_mean': 1.5, 'own_low': 1, 'own_high': 2, 'own_attack': 0, 'own_defence': 0,
                     'own_home_adv': 0.2, 'opp_mean': 1.0, 'opp_low': 0, 'opp_high': 2,
                     'opp_attack': 0, 'opp_defence': 0}]

    monkeypatch.setattr(engine, 'connect_db', lambda: Conn())
    monkeypatch.setattr(engine, 'current_season_start', lambda: 2025)
    monkeypatch.setattr(engine, 'fetch_teams_for_season', lambda c, y: {
        1: {'id': 1, 'name': 'Alpha', 'short_name': 'ALP'},
        2: {'id': 2, 'name': 'Beta', 'short_name': 'BET'}})
    monkeypatch.setattr(h2h, 'current_season_start', lambda: 2025)
    monkeypatch.setattr(h2h, 'code_map_for_season', lambda c, y: {1: 10, 2: 20})
    monkeypatch.setattr(h2h, 'load_meeting_history',
                        lambda c, seasons=None, **kw: [match(2024, 8, 20, 10, 0, 2)])
    out = engine.load_team_fixture_outlook(1)
    assert out['fixtures'][0]['last_meetings'] == [
        {'season_label': '2024/25', 'is_home': False, 'result': 'won', 'score': '2–0'}]


# ---- caching ------------------------------------------------------------
import pytest
import FPL_site.headToHead as _h2h


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Each test starts with an empty in-process cache so fakes cannot leak between tests."""
    _h2h.clear_history_cache()
    yield
    _h2h.clear_history_cache()


def test_second_call_makes_no_queries_for_completed_seasons():
    cur = FakeCursor(
        snapshots={2024: {1: 10, 2: 20}, 2025: {1: 10, 2: 20}},
        fixtures={2024: [raw(8, 1, 2, 1, 0, '2024-10-05T15:00:00Z')],
                  2025: [raw(5, 1, 2, 2, 2, '2025-09-20T15:00:00Z')]})
    first = load_meeting_history(cursor=cur, seasons=[2024, 2025], current=2025)
    after_first = cur.queries
    second = load_meeting_history(cursor=cur, seasons=[2024, 2025], current=2025)
    assert second == first
    # Only the live season (2025) is read again: its fixtures, and its code map.
    assert cur.queries - after_first == 2


def test_second_call_reuses_a_supplied_current_code_map():
    cur = FakeCursor(snapshots={2025: {1: 10, 2: 20}},
                     fixtures={2025: [raw(5, 1, 2, 2, 2, '2025-09-20T15:00:00Z')]})
    load_meeting_history(cursor=cur, seasons=[2025], current=2025, current_codes={1: 10, 2: 20})
    assert cur.queries == 1   # fixtures only; no code map query


def test_the_live_season_is_never_cached():
    cur = FakeCursor(snapshots={2025: {1: 10, 2: 20}},
                     fixtures={2025: [raw(5, 1, 2, 2, 2, '2025-09-20T15:00:00Z')]})
    load_meeting_history(cursor=cur, seasons=[2025], current=2025)
    cur.fixtures[2025].append(raw(9, 2, 1, 1, 0, '2025-12-01T15:00:00Z'))
    again = load_meeting_history(cursor=cur, seasons=[2025], current=2025)
    assert len(again) == 2
