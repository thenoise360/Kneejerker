import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import playerHistory as ph
from FPL_site import dataModels


# ---- wording ----------------------------------------------------------------

@pytest.mark.parametrize('points, word', [
    (12, 'Big return last time'),
    (8, 'Big return last time'),
    (7, 'Steady return last time'),
    (3, 'Steady return last time'),
    (2, 'Quiet game last time'),
    (0, 'Quiet game last time'),
    (-1, 'Quiet game last time'),
])
def test_return_tier_boundaries(points, word):
    assert ph.last_time_tier(points) == word


@pytest.mark.parametrize('was_home, h, a, text', [
    (True, 3, 1, 'won 3–1'),     # at home: own score is the home score
    (True, 1, 1, 'drew 1–1'),
    (True, 0, 2, 'lost 0–2'),
    (False, 0, 2, 'won 2–0'),    # away: own score is the away score, written first
    (False, 2, 2, 'drew 2–2'),
    (False, 3, 1, 'lost 1–3'),
])
def test_result_is_from_the_players_club_perspective(was_home, h, a, text):
    assert ph.result_wording(was_home, h, a) == text


def match(round_, opp, was_home, points=5, minutes=90, h=1, a=0):
    return {'round': round_, 'opponent_team': opp, 'was_home': 1 if was_home else 0,
            'total_points': points, 'minutes': minutes, 'team_h_score': h, 'team_a_score': a}


# ---- choosing the meeting ---------------------------------------------------

def test_two_meetings_prefer_the_same_venue():
    home_game = match(4, 9, True, points=9)
    away_game = match(20, 9, False, points=2, h=0, a=0)
    assert ph.pick_meeting([home_game, away_game], is_home=True) is home_game
    assert ph.pick_meeting([home_game, away_game], is_home=False) is away_game


def test_one_meeting_is_used_whatever_the_venue():
    only = match(4, 9, True)
    assert ph.pick_meeting([only], is_home=False) is only


def test_no_meetings_is_none():
    assert ph.pick_meeting([], is_home=True) is None


# ---- the fetcher, against a fake cursor ---------------------------------------

class FakeCursor:
    """Seasons: this = 2026, last = 2025."""
    def __init__(self, this_el, last_el, history, code_maps, teams):
        self.this_el, self.last_el = this_el, last_el
        self.history, self.code_maps, self.teams = history, code_maps, teams
        self.sql, self.params = '', ()

    def execute(self, sql, params=None):
        self.sql, self.params = sql, params or ()

    def fetchone(self):
        if 'bootstrapstatic_elements' in self.sql:
            return self.this_el if 'WHERE id' in self.sql else self.last_el
        if 'bootstrapstatic_teams' in self.sql:
            name = self.teams.get((self.params[0], self.params[1]))
            return {'name': name} if name else None

    def fetchall(self):
        if 'GROUP BY team, team_code' in self.sql:
            mapping = self.code_maps[self.params[0]]
            return [{'team': t, 'team_code': c, 'gws': 10, 'last_gw': 10, 'n_rows': 100}
                    for t, c in mapping.items()]
        if 'elementsummary_history' in self.sql:
            return self.history.get((self.params[0], self.params[1]), [])
        return []


BRIGHTON = 40
THIS_MAP = {1: 3, 7: BRIGHTON}      # this season: Arsenal is team 1, Brighton team 7
LAST_MAP = {2: 3, 9: BRIGHTON}      # last season the ids were different


def make(history, this_el=None, last_el='default', teams=None):
    return FakeCursor(
        this_el=this_el or {'code': 223340, 'team_code': 3},
        last_el={'id': 16, 'team_code': 3} if last_el == 'default' else last_el,
        history={(16, 2025): history},
        code_maps={2026: THIS_MAP, 2025: LAST_MAP},
        teams=teams or {(3, 2025): 'Arsenal', (BRIGHTON, 2025): 'Brighton'})


def lookup(cursor, opponent_id=7, is_home=True):
    ctx = ph.fetch_last_time_context(cursor, 12, this_year=2026)
    return ph.last_time_for(ctx, opponent_id, is_home)


def test_matches_across_seasons_by_codes_not_ids():
    # Last season's opponent id was 9, this season's is 7; both are Brighton (code 40).
    out = lookup(make([match(4, 9, True, points=9, h=3, a=1)]))
    assert out == {'kind': 'played', 'points': 9, 'minutes': 90, 'result': 'won 3–1',
                   'is_home': True, 'club': None}


def test_a_different_team_with_the_same_old_id_is_not_a_meeting():
    # An id-based match would wrongly pair this-season team 7 with last-season team 7.
    out = lookup(make([match(4, 7, True)]))
    assert out == {'kind': 'no_meeting'}


def test_club_change_names_the_old_club():
    cursor = make([match(4, 9, False, points=2, h=1, a=2)],
                  this_el={'code': 223340, 'team_code': 11})
    out = lookup(cursor, is_home=False)
    assert out['club'] == 'Arsenal'
    assert out['result'] == 'won 2–1'


def test_clubs_that_did_not_meet_say_no_meeting():
    assert lookup(make([match(4, 2, True)])) == {'kind': 'no_meeting'}


def test_zero_minutes_is_did_not_play():
    assert lookup(make([match(4, 9, True, points=0, minutes=0)])) == {'kind': 'did_not_play'}


def test_player_not_in_league_last_season_is_a_new_player():
    assert lookup(make([], last_el=None)) == {'kind': 'new_player'}


def test_two_meetings_pick_the_venue_of_the_upcoming_fixture():
    games = [match(4, 9, True, points=9, h=3, a=1), match(20, 9, False, points=1, h=2, a=0)]
    assert lookup(make(games), is_home=True)['points'] == 9
    away = lookup(make(games), is_home=False)
    assert away['points'] == 1 and away['result'] == 'lost 0–2' and away['is_home'] is False


# ---- wiring into next_5_gameweeks ---------------------------------------------

class Next5Cursor:
    def __init__(self):
        self.last = ''

    def execute(self, sql, params=None):
        self.last = sql

    def fetchall(self):
        if 'bootstrapstatic_teams where' in self.last:
            return [{'id': 1, 'name': 'Arsenal', 'short_name': 'ARS', 'code': 3},
                    {'id': 7, 'name': 'Brighton', 'short_name': 'BHA', 'code': BRIGHTON}]
        if 'es_f.event = 11' in self.last:
            return [{'team_h': 1, 'team_a': 7, 'team_h_difficulty': 2,
                     'team_a_difficulty': 4, 'gameweek': 11}]
        return []

    def fetchone(self):
        if 'bootstrapstatic_elements' in self.last:
            return {'team_id': 1, 'Full_name': 'A B'}
        return {'avg_difficulty': 3}

    def close(self):
        pass


class Conn:
    def cursor(self, dictionary=False):
        return Next5Cursor()

    def close(self):
        pass


def test_each_fixture_gets_last_time_and_blank_weeks_get_none(monkeypatch):
    monkeypatch.setattr(dataModels, 'connect_db', lambda: Conn())
    monkeypatch.setattr(dataModels, 'generateCurrentGameweek', lambda: 10)
    seen = []
    monkeypatch.setattr(ph, 'fetch_last_time_context', lambda cur, pid, this_year=None: 'CTX')
    monkeypatch.setattr(ph, 'last_time_for',
                        lambda ctx, opp, home: seen.append((ctx, opp, home)) or {'kind': 'no_meeting'})
    fixtures = dataModels.next_5_gameweeks(1, include_history=True)
    assert fixtures[0]['lastTime'] == {'kind': 'no_meeting'}
    assert seen == [('CTX', 7, True)]
    assert fixtures[1]['homeOrAway'] == 'Blank' and fixtures[1]['lastTime'] is None
    assert fixtures[0]['teamFullName'] == 'Brighton'          # existing text unchanged


def test_a_failed_history_lookup_leaves_fixtures_intact(monkeypatch):
    monkeypatch.setattr(dataModels, 'connect_db', lambda: Conn())
    monkeypatch.setattr(dataModels, 'generateCurrentGameweek', lambda: 10)

    def boom(*a, **k):
        raise RuntimeError('no history')
    monkeypatch.setattr(ph, 'fetch_last_time_context', boom)
    fixtures = dataModels.next_5_gameweeks(1, include_history=True)
    assert fixtures[0]['teamFullName'] == 'Brighton'
    assert fixtures[0]['lastTime'] is None


def test_history_is_not_fetched_unless_asked_for(monkeypatch):
    """Worth-watching calls next_5_gameweeks 20 times and never reads lastTime."""
    monkeypatch.setattr(dataModels, 'connect_db', lambda: Conn())
    monkeypatch.setattr(dataModels, 'generateCurrentGameweek', lambda: 10)
    calls = []
    monkeypatch.setattr(ph, 'fetch_last_time_context', lambda *a, **k: calls.append(a))
    fixtures = dataModels.next_5_gameweeks(1)
    assert calls == []
    assert fixtures[0]['teamFullName'] == 'Brighton'
    assert fixtures[0]['lastTime'] is None


def test_the_route_asks_for_history(monkeypatch):
    from FPL_site import views
    seen = {}
    monkeypatch.setattr(views, 'next_5_gameweeks', lambda pid, include_history=False: seen.update(h=include_history) or [])
    assert views.app.test_client().get('/get_next_5_gameweeks?id=1').status_code == 200
    assert seen['h'] is True
