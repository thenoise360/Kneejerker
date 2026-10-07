import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import weekDecision
from FPL_site.weekDecision import (
    fixtures_by_team, biggest_decision, guest_biggest_decision, DOUBT_BELOW, squad_from_picks,
    get_this_week_decision,
)


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


def test_squad_from_picks_maps_official_keys():
    picks = {'picks': [{'element': 9, 'is_captain': True, 'multiplier': 2}]}
    assert squad_from_picks(picks) == [{'id': 9, 'is_captain': True, 'multiplier': 2}]
    assert squad_from_picks(None) == []


#################################################
#  get_this_week_decision, with a fake database #
#################################################

ELEMENTS = [
    {'id': 1, 'web_name': 'Saka', 'team': 10, 'chance_of_playing_next_round': 25, 'news': 'Hamstring'},
    {'id': 3, 'web_name': 'Salah', 'team': 30, 'chance_of_playing_next_round': None, 'news': ''},
]
PREDICTIONS = [{'player_id': 1, 'predicted_performance': 5.0}, {'player_id': 3, 'predicted_performance': 8.0}]
FIXTURES = [{'team_h': 30, 'team_a': 40, 'team_h_difficulty': 2, 'team_a_difficulty': 4,
             'home_name': 'Liverpool', 'away_name': 'Everton'},
            {'team_h': 10, 'team_a': 50, 'team_h_difficulty': 3, 'team_a_difficulty': 3,
             'home_name': 'Arsenal', 'away_name': 'Villa'}]


class FakeCursor:
    """Answers each query with canned rows, chosen by the table it reads."""
    def __init__(self):
        self.rows = []

    def execute(self, sql, params=None):
        if 'bootstrapstatic_elements' in sql:
            self.rows = ELEMENTS
        elif 'player_predictions' in sql:
            self.rows = PREDICTIONS
        elif 'fixtures_fixtures' in sql:
            self.rows = FIXTURES
        else:
            raise AssertionError(f'unexpected query: {sql}')

    def fetchall(self):
        return self.rows


class FakeConn:
    def cursor(self, dictionary=False):
        return FakeCursor()

    def close(self):
        pass


def patch(monkeypatch, picks_result):
    monkeypatch.setattr(weekDecision, 'connect_db', lambda: FakeConn())
    monkeypatch.setattr(weekDecision, 'fetch_entry_picks', lambda entry_id, gameweek: picks_result)


def test_ok_picks_give_a_your_team_decision(monkeypatch):
    picks = {'picks': [{'element': 1, 'is_captain': True, 'multiplier': 2}]}
    patch(monkeypatch, ('ok', picks))
    result = get_this_week_decision(6, 5, team_id=123)
    assert result['based_on'] == 'your_team' and result['squad_gameweek'] == 5
    assert result['decision']['kind'] == 'availability' and 'Saka' in result['decision']['reason']
    assert result['message'] is None


def test_not_found_falls_back_to_everyone(monkeypatch):
    patch(monkeypatch, ('not_found', None))
    result = get_this_week_decision(6, 5, team_id=123)
    assert result['based_on'] == 'everyone' and result['squad_gameweek'] is None
    assert result['decision']['kind'] == 'captain' and 'Salah' in result['decision']['reason']


def test_unavailable_falls_back_to_everyone(monkeypatch):
    patch(monkeypatch, ('unavailable', None))
    result = get_this_week_decision(6, 5, team_id=123)
    assert result['based_on'] == 'everyone' and result['decision']['kind'] == 'captain'


def test_ok_but_empty_picks_falls_back_to_everyone(monkeypatch):
    patch(monkeypatch, ('ok', {'picks': []}))
    assert get_this_week_decision(6, 5, team_id=123)['based_on'] == 'everyone'


def test_guest_never_fetches_picks(monkeypatch):
    patch(monkeypatch, ('ok', None))

    def refuse(*args):
        raise AssertionError('should not fetch picks for a guest')
    monkeypatch.setattr(weekDecision, 'fetch_entry_picks', refuse)
    assert get_this_week_decision(6, 5)['based_on'] == 'everyone'
    assert get_this_week_decision(6, 5, team_id='invalid')['based_on'] == 'everyone'


def test_no_database_gives_the_empty_message(monkeypatch):
    monkeypatch.setattr(weekDecision, 'connect_db', lambda: None)
    result = get_this_week_decision(6, 5)
    assert result['decision'] is None and result['message']['title']
