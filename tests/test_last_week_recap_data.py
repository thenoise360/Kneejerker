import os
import pytest
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.lastWeekRecap import (
    summarise_event, aggregate_player_rows, top_performers, fetch_event_rows, fetch_history_rows,
)


def row(element, points, name='Player', minutes=90, difficulty=3, fixture=None, **stats):
    base = {'element': element, 'fixture': element * 100 if fixture is None else fixture,
            'total_points': points, 'minutes': minutes, 'goals_scored': 0,
            'assists': 0, 'clean_sheets': 0, 'saves': 0, 'bonus': 0, 'penalties_saved': 0,
            'web_name': name, 'element_type': 3, 'team_name': 'Arsenal', 'difficulty': difficulty}
    base.update(stats)
    return base


def test_player_team_is_the_full_team_name():
    players = aggregate_player_rows([row(1, 10, name='Saka')])
    assert players[1]['team'] == 'Arsenal'


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
        row(7, 6, name='Saka', goals_scored=1, difficulty=4, fixture=11),
        row(7, 9, name='Saka', assists=2, bonus=3, difficulty=2, fixture=12),
    ])
    saka = players[7]
    assert saka['points'] == 15
    assert saka['minutes'] == 180
    assert saka['goals'] == 1 and saka['assists'] == 2 and saka['bonus'] == 3
    assert saka['difficulty'] == 2  # easiest of the two fixtures


def test_aggregate_ignores_duplicate_join_rows():
    players = aggregate_player_rows([row(7, 6, name='Saka', goals_scored=1), row(7, 6, name='Saka', goals_scored=1)])
    assert players[7]['points'] == 6
    assert players[7]['minutes'] == 90
    assert players[7]['goals'] == 1


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


from FPL_site.lastWeekRecap import recap_payload, build_personal_recap, get_last_week_recap
import FPL_site.lastWeekRecap as recap_module


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


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, dictionary=False):
        return self._cursor

    def close(self):
        pass


class SequenceCursor:
    """Returns the event rows first, then the history rows, matching the fetch order."""
    def __init__(self, batches):
        self.batches = list(batches)

    def execute(self, sql, params):
        pass

    def fetchall(self):
        return self.batches.pop(0)


def test_get_last_week_recap_fetches_picks_only_for_a_valid_team(monkeypatch):
    calls = []

    def fake_picks(entry_id, gameweek):
        calls.append((entry_id, gameweek))
        return 'not_found', None

    def fresh_conn():
        return FakeConn(SequenceCursor([
            [{'average_entry_score': 48, 'highest_score': 100, 'finished': 1, 'data_checked': 1}],
            [row(7, 9, name='Saka')],
        ]))

    monkeypatch.setattr(recap_module, 'connect_db', fresh_conn)
    monkeypatch.setattr(recap_module, 'fetch_entry_picks', fake_picks)

    result = get_last_week_recap(5, team_id=123)
    assert calls == [(123, 5)]
    assert result['personal']['status'] == 'team_not_found'

    get_last_week_recap(5, team_id='invalid')
    get_last_week_recap(5, team_id=None)
    assert calls == [(123, 5)]


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_fetch_entry_picks_ok(monkeypatch):
    seen = {}

    def fake_get(url, timeout=None, **kwargs):
        seen['timeout'] = timeout
        return FakeResponse(200, {'picks': []})

    monkeypatch.setattr(recap_module.requests, 'get', fake_get)
    assert recap_module.fetch_entry_picks(123, 5) == ('ok', {'picks': []})
    assert seen['timeout'] == 10


def test_fetch_entry_picks_404_is_not_found(monkeypatch):
    monkeypatch.setattr(recap_module.requests, 'get', lambda *a, **k: FakeResponse(404))
    assert recap_module.fetch_entry_picks(123, 5) == ('not_found', None)


@pytest.mark.parametrize('status', [500, 503, 429, 403])
def test_fetch_entry_picks_other_statuses_are_unavailable(monkeypatch, status):
    monkeypatch.setattr(recap_module.requests, 'get', lambda *a, **k: FakeResponse(status))
    assert recap_module.fetch_entry_picks(123, 5) == ('unavailable', None)


def test_fetch_entry_picks_exception_is_unavailable_and_logs_only_the_type(monkeypatch, caplog):
    def boom(*a, **k):
        raise recap_module.requests.Timeout('https://example/entry/987654/ timed out')

    monkeypatch.setattr(recap_module.requests, 'get', boom)
    with caplog.at_level('ERROR'):
        assert recap_module.fetch_entry_picks(987654, 5) == ('unavailable', None)
    assert 'Timeout' in caplog.text
    assert '987654' not in caplog.text and 'example' not in caplog.text


def test_personal_recap_unavailable_is_calm_and_has_no_prompt_to_change_number():
    result = build_personal_recap(None, {}, 48, 5, fetch_status='unavailable')
    assert result['status'] == 'unavailable'
    body = result['message']['body'].lower()
    assert 'nothing is wrong on your side' in body and 'double-check' not in body


def test_get_last_week_recap_reports_unavailable_when_the_api_is_down(monkeypatch):
    monkeypatch.setattr(recap_module, 'connect_db', lambda: FakeConn(SequenceCursor([
        [{'average_entry_score': 48, 'highest_score': 100, 'finished': 1, 'data_checked': 1}],
        [row(7, 9, name='Saka')],
    ])))
    monkeypatch.setattr(recap_module, 'fetch_entry_picks', lambda e, g: ('unavailable', None))
    assert get_last_week_recap(5, team_id=123)['personal']['status'] == 'unavailable'
