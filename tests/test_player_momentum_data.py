import json
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest
from mysql.connector.errors import ProgrammingError

import FPL_site.playerMomentum as pm
import FPL_site.matchPredictionEngine as engine


def player(pid, team=1, position=3, xg=0.0, xa=0.0, status='a', chance=None, name=None):
    return {'id': pid, 'web_name': name or 'P%d' % pid, 'team': team, 'element_type': position,
            'status': status, 'chance_of_playing_next_round': chance,
            'expected_goals': xg, 'expected_assists': xa}


def fixture(team, own, opp, gw=1):
    return {'team_id': team, 'gameweek': gw, 'own_mean': own, 'opp_mean': opp}


# ---- build_all_momentum ----

def test_status_u_is_skipped_and_excluded_from_shares():
    players = [player(1, xg=1.0), player(2, xg=1.0, status='u'), player(3, xg=1.0)]
    result = pm.build_all_momentum(players, {1: 90, 3: 90}, [], {})
    assert set(result) == {1, 3}


def test_missing_baselines_fall_back_to_league_mean_for_attackers():
    # Team 1 attackers face 2.0 expected goals; league mean of own_mean is 1.5, so 33% kinder.
    upcoming = [fixture(1, 2.0, 1.0), fixture(2, 1.0, 2.0)]
    players = [player(1, team=1, position=4), player(2, team=2, position=4)]
    result = pm.build_all_momentum(players, {1: 90, 2: 90}, upcoming, {})
    by_key = lambda pid: {s['key']: s for s in result[pid]['signals']}
    assert by_key(1)['fixtures']['direction'] == 'up'
    assert by_key(2)['fixtures']['direction'] == 'down'


def test_missing_baselines_fall_back_to_opp_mean_for_defenders():
    # Team 1 defenders face opponents scoring 1.0; league mean opp_mean is 1.5, so easier.
    upcoming = [fixture(1, 2.0, 1.0), fixture(2, 1.0, 2.0)]
    players = [player(1, team=1, position=2), player(2, team=2, position=2)]
    result = pm.build_all_momentum(players, {1: 90, 2: 90}, upcoming, {})
    assert result[1]['signals'][0]['direction'] == 'up'
    assert result[2]['signals'][0]['direction'] == 'down'


def test_team_strength_baselines_used_when_present():
    upcoming = [fixture(1, 1.0, 1.0)]
    baselines = {1: {'scored': 2.0, 'conceded': 1.0}}
    result = pm.build_all_momentum([player(1, position=4)], {1: 90}, upcoming, baselines)
    assert result[1]['signals'][0]['direction'] == 'down'   # 1.0 against a 2.0 baseline


def test_teammate_back_after_missing_last_gameweek_lifts_everyone_else():
    players = [player(1, xg=1.0, name='Me'), player(2, xg=3.0, name='Saka', chance=100)]
    # Saka has no minutes last gameweek, so he is "back".
    result = pm.build_all_momentum(players, {1: 90}, [], {})
    teammates = result[1]['signals'][1]
    assert teammates['direction'] == 'up'
    assert teammates['reason'] == 'Saka is back in the team'
    # He does not count himself.
    assert result[2]['signals'][1]['direction'] == 'same'


def test_double_gameweek_minutes_sum_counts_as_played():
    # fetch_last_gameweek_minutes sums; here a total above zero means played.
    cursor = FakeCursor([{'element': 2, 'minutes': 45}, {'element': 3, 'minutes': None}])
    assert pm.fetch_last_gameweek_minutes(cursor, 2026, 7) == {2: 45.0, 3: 0.0}
    assert 'SUM(minutes)' in cursor.calls[0][0] and 'GROUP BY element' in cursor.calls[0][0]
    assert cursor.calls[0][1] == (2026, 7)


def test_no_minutes_data_does_not_make_everyone_back():
    players = [player(1, xg=1.0), player(2, xg=3.0, chance=100)]
    result = pm.build_all_momentum(players, {}, [], {})
    assert result[1]['signals'][1]['direction'] == 'same'


def test_team_with_no_minutes_gets_no_false_back():
    # Team 1 has played; team 2 has not kicked off yet (or has a blank gameweek).
    players = [player(1, team=1, xg=1.0), player(2, team=1, xg=3.0, chance=100, name='A'),
               player(3, team=2, xg=1.0), player(4, team=2, xg=3.0, chance=100, name='B')]
    result = pm.build_all_momentum(players, {1: 90}, [], {})
    assert result[1]['signals'][1]['direction'] == 'up'
    assert result[3]['signals'][1]['direction'] == 'same'
    assert 'back' not in (result[3]['signals'][1]['reason'] or '')


def test_ruled_out_teammate_who_played_is_out():
    players = [player(1, xg=1.0), player(2, xg=3.0, chance=0, name='Saka')]
    result = pm.build_all_momentum(players, {1: 90, 2: 90}, [], {})
    assert result[1]['signals'][1]['direction'] == 'down'


# ---- fakes ----

class FakeCursor:
    def __init__(self, rows=None, error=None):
        self.calls = []
        self.rows = rows or []
        self.error = error

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if self.error and 'FROM ' in sql and (pm.MOMENTUM_TABLE in sql or 'team_strength' in sql):
            raise self.error

    def executemany(self, sql, params):
        self.calls.append((sql, list(params)))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, cursor=None):
        self.cur = cursor or FakeCursor()
        self.committed = 0
        self.closed = False

    def cursor(self, **kwargs):
        return self.cur

    def commit(self):
        self.committed += 1

    def close(self):
        self.closed = True


# ---- fetchers ----

def test_fetch_team_baselines():
    cursor = FakeCursor([{'team_id': 1, 'scored': 1.5, 'conceded': 1.1}])
    assert pm.fetch_team_baselines(cursor) == {1: {'scored': 1.5, 'conceded': 1.1}}


def test_fetch_team_baselines_missing_table_is_empty():
    cursor = FakeCursor(error=ProgrammingError(msg='no table', errno=1146))
    assert pm.fetch_team_baselines(cursor) == {}


def test_fetch_team_baselines_other_errors_propagate():
    cursor = FakeCursor(error=ProgrammingError(msg='bad', errno=1064))
    with pytest.raises(ProgrammingError):
        pm.fetch_team_baselines(cursor)


def test_fetch_upcoming_uses_self_join_and_range():
    cursor = FakeCursor([])
    pm.fetch_upcoming_predictions(cursor, 8, 10)
    sql, params = cursor.calls[0]
    assert 'mine.fixture_code = theirs.fixture_code' in sql and 'theirs.team_id = mine.opponent_id' in sql
    assert params == (8, 10)


def test_fetch_player_rows_passes_year_twice():
    cursor = FakeCursor([{'id': 1}])
    assert pm.fetch_player_rows(cursor, 2026) == [{'id': 1}]
    assert cursor.calls[0][1] == (2026, 2026)


# ---- persistence ----

def test_persist_replaces_table_in_one_commit():
    players = [player(1, name='Saka'), player(2, name='Odegaard')]
    momentum = pm.build_all_momentum(players, {1: 90, 2: 90}, [], {})
    conn = FakeConn()
    pm.persist_momentum(conn, momentum, players)
    sqls = [c[0] for c in conn.cur.calls]
    assert 'CREATE TABLE IF NOT EXISTS player_momentum' in sqls[0]
    assert sqls[1].strip().startswith('DELETE FROM player_momentum')
    insert_sql, records = conn.cur.calls[2]
    assert insert_sql.strip().startswith('INSERT INTO player_momentum')
    assert [r[0] for r in records] == [1, 2]
    assert records[0][1] == 'Saka' and records[0][4] == 'Steady'
    assert json.loads(records[0][6])[0]['key'] == 'fixtures'
    assert conn.committed == 1


# ---- loaders ----

def stored(label='Rising', score=1.2, pid=1, team_id=1, name='Saka', reason='Rising: kinder fixtures coming up.',
           position=3):
    signals = [
        {'key': 'fixtures', 'direction': 'up', 'reason': 'kinder fixtures coming up', 'magnitude': 0.3},
        {'key': 'teammates', 'direction': 'same', 'reason': 'no change around them', 'magnitude': 0},
        {'key': 'position', 'direction': 'not_tracked', 'reason': None, 'magnitude': 0},
        {'key': 'manager', 'direction': 'not_tracked', 'reason': None, 'magnitude': 0},
    ]
    return {'player_id': pid, 'name': name, 'team_id': team_id, 'position': position, 'label': label, 'reason': reason,
            'signals_json': json.dumps(signals), 'score': score}


def test_load_player_momentum_ready_has_no_score(monkeypatch):
    conn = FakeConn(FakeCursor([stored()]))
    monkeypatch.setattr(pm, 'connect_db', lambda: conn)
    payload = pm.load_player_momentum(1)
    assert payload['status'] == 'ready'
    assert payload['label'] == 'Rising'
    first = payload['signals'][0]
    assert first == {'key': 'fixtures', 'name': 'Fixtures', 'direction': 'up', 'word': 'Up',
                     'arrow': '↑', 'reason': 'kinder fixtures coming up'}
    assert [s['arrow'] for s in payload['signals']] == ['↑', '→', '–', '–']
    assert payload['signals'][3]['word'] == 'Not tracked yet'
    assert 'score' not in json.dumps(payload) and 'magnitude' not in json.dumps(payload)
    assert conn.closed


def test_load_player_momentum_unknown_player_is_none_and_not_ready_cases(monkeypatch):
    monkeypatch.setattr(pm, 'connect_db', lambda: FakeConn(FakeCursor([])))
    assert pm.load_player_momentum(1) is None
    monkeypatch.setattr(pm, 'connect_db', lambda: None)
    payload = pm.load_player_momentum(1)
    assert payload['message']['title'] == 'Momentum is on its way'
    missing = FakeConn(FakeCursor(error=ProgrammingError(msg='x', errno=1146)))
    monkeypatch.setattr(pm, 'connect_db', lambda: missing)
    assert pm.load_player_momentum(1)['status'] == 'not_ready'
    assert missing.closed


def test_strip_ordering_limit_and_no_score(monkeypatch):
    rows = [stored('Rising', 1.5, 1, 1, 'A'), stored('Rising', 2.5, 2, 2, 'B'),
            stored('Rising', 1.1, 3, 1, 'C'),
            stored('Cooling', -1.5, 4, 1, 'D'), stored('Cooling', -2.5, 5, 2, 'E'),
            stored('Cooling', -1.1, 6, 1, 'F')]
    conn = FakeConn(FakeCursor(rows))
    monkeypatch.setattr(pm, 'connect_db', lambda: conn)
    monkeypatch.setattr(engine, 'fetch_teams_for_season', lambda c, y: {
        1: {'id': 1, 'name': 'Arsenal', 'short_name': 'ARS'}, 2: {'id': 2, 'name': 'Chelsea', 'short_name': 'CHE'}})
    strip = pm.load_momentum_strip(limit=2)
    assert [i['name'] for i in strip['heating_up']] == ['B', 'A']
    assert [i['name'] for i in strip['cooling_off']] == ['E', 'D']
    assert strip['heating_up'][0] == {'id': 2, 'name': 'B', 'team': 'Chelsea', 'position': 'MID',
                                      'reason': 'Rising: kinder fixtures coming up.'}
    for item in strip['heating_up'] + strip['cooling_off']:
        assert 'score' not in item
    assert 'ARS' not in json.dumps(strip) and 'score' not in json.dumps(strip)
    assert conn.closed


def test_strip_maps_stored_position_numbers_to_short_codes(monkeypatch):
    rows = [stored('Rising', 4.0, 1, 1, 'G', position=1), stored('Rising', 3.0, 2, 1, 'D', position=2),
            stored('Rising', 2.0, 3, 1, 'M', position=3), stored('Rising', 1.0, 4, 1, 'F', position=4),
            stored('Cooling', -1.0, 5, 1, 'X', position=None)]
    monkeypatch.setattr(pm, 'connect_db', lambda: FakeConn(FakeCursor(rows)))
    monkeypatch.setattr(engine, 'fetch_teams_for_season', lambda c, y: {})
    strip = pm.load_momentum_strip()
    assert [i['position'] for i in strip['heating_up']] == ['GKP', 'DEF', 'MID', 'FWD']
    assert strip['cooling_off'][0]['position'] == ''


def test_strip_empty_when_no_table_or_connection(monkeypatch):
    monkeypatch.setattr(pm, 'connect_db', lambda: None)
    assert pm.load_momentum_strip() == {'heating_up': [], 'cooling_off': []}
    conn = FakeConn(FakeCursor(error=ProgrammingError(msg='x', errno=1146)))
    monkeypatch.setattr(pm, 'connect_db', lambda: conn)
    assert pm.load_momentum_strip() == {'heating_up': [], 'cooling_off': []}


def test_strip_empty_when_teams_missing_or_teams_table_missing(monkeypatch):
    rows = [stored('Rising', 1.5, 1, 1, 'A'), stored('Cooling', -1.5, 4, 1, 'D')]
    empty = {'heating_up': [], 'cooling_off': []}
    # No teams result at all (None): never an exception.
    monkeypatch.setattr(pm, 'connect_db', lambda: FakeConn(FakeCursor(rows)))
    monkeypatch.setattr(engine, 'fetch_teams_for_season', lambda c, y: None)
    strip = pm.load_momentum_strip()
    assert [i['team'] for i in strip['heating_up'] + strip['cooling_off']] == ['', '']

    # The teams table itself is missing (error 1146): empty lists.
    def no_table(c, y):
        raise ProgrammingError(msg='x', errno=1146)
    conn = FakeConn(FakeCursor(rows))
    monkeypatch.setattr(pm, 'connect_db', lambda: conn)
    monkeypatch.setattr(engine, 'fetch_teams_for_season', no_table)
    assert pm.load_momentum_strip() == empty
    assert conn.closed


def test_run_daily_momentum_wires_fetchers_and_persists(monkeypatch):
    seen = {}
    monkeypatch.setattr(pm, 'fetch_player_rows', lambda c, y: [player(1)])
    monkeypatch.setattr(pm, 'fetch_last_gameweek_minutes', lambda c, y, gw: seen.setdefault('gw', gw) and {1: 90})
    monkeypatch.setattr(pm, 'fetch_upcoming_predictions', lambda c, a, b: seen.setdefault('range', (a, b)) and [])
    monkeypatch.setattr(pm, 'fetch_team_baselines', lambda c: {})
    conn = FakeConn()
    result = pm.run_daily_momentum(conn.cur, conn, 7)
    assert set(result) == {1}
    assert seen['gw'] == 7 and seen['range'] == (8, 10)
    assert conn.committed == 1
