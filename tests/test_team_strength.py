import os
import math
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site.teamStrength import (
    missing_fraction, team_absences, adjust, goals_vs_average,
    build_team_strengths, fetch_squad_rows,
)


def player(pid, team=1, position=3, xg=0.0, xa=0.0, minutes=0, chance=None, status='a', name=None):
    return {'id': pid, 'web_name': name or f'P{pid}', 'team': team, 'element_type': position,
            'expected_goals': xg, 'expected_assists': xa, 'minutes': minutes,
            'chance_of_playing_next_round': chance, 'status': status}


def test_missing_fraction():
    assert missing_fraction(None) == 0
    assert missing_fraction(100) == 0
    assert missing_fraction(25) == 0.75
    assert missing_fraction(0) == 1
    assert missing_fraction(150) == 0
    assert missing_fraction(-5) == 1


def test_shares_with_zero_team_totals():
    result = team_absences([player(1, chance=0), player(2)])
    assert result['attack_share'] == 0
    assert result['defence_share'] == 0


def test_departed_players_are_excluded_from_totals_and_missing():
    players = [player(1, xg=3.0, chance=0), player(2, xg=1.0, status='u', chance=0), player(3, xg=0.0)]
    result = team_absences(players)
    assert result['attack_share'] == pytest.approx(1.0)
    assert [m['name'] for m in result['missing']] == ['P1']


def test_attack_share_of_missing_player():
    players = [player(1, xg=3.0, xa=1.0, chance=0), player(2, xg=5.0, xa=1.0)]
    assert team_absences(players)['attack_share'] == pytest.approx(0.4)
    players[0]['chance_of_playing_next_round'] = 50
    result = team_absences(players)
    assert result['attack_share'] == pytest.approx(0.2)
    # the listed share is the raw share, not weighted by chance
    assert result['missing'][0]['share'] == pytest.approx(0.4)
    assert result['missing'][0]['chance'] == 50


def test_fit_players_are_not_missing():
    result = team_absences([player(1, xg=2.0, chance=100), player(2, xg=2.0)])
    assert result['missing'] == []
    assert result['attack_share'] == 0


def test_defence_share_uses_goalkeeper_and_defender_minutes_only():
    players = [
        player(1, position=1, minutes=900),
        player(2, position=2, minutes=900, chance=0),
        player(3, position=3, minutes=2000, chance=0),
        player(4, position=4, minutes=2000),
    ]
    result = team_absences(players)
    assert result['defence_share'] == pytest.approx(0.5)
    mid = [m for m in result['missing'] if m['name'] == 'P3'][0]
    assert mid['share'] == 0 and mid['role'] == 'attack'


def test_adjust_attack():
    attack, defence = adjust(0.2, -0.1, 0.4, 0.0)
    assert attack == pytest.approx(0.2 + math.log(0.8))
    assert defence == pytest.approx(-0.1)


def test_adjust_defence_concedes_more():
    attack, defence = adjust(0, 0, 0, 0.4)
    assert attack == 0
    assert defence == pytest.approx(-math.log(0.8))
    assert defence > 0


def test_adjust_caps_extreme_share():
    attack, _ = adjust(0, 0, 5.0, 0)
    assert attack == pytest.approx(math.log(0.6))


def test_goals_vs_average():
    scored, conceded = goals_vs_average(0.3, 0.1, 0.0, 0.2, 0.4)
    assert scored == pytest.approx(math.exp(0.3 + 0.2 + 0.2))
    assert conceded == pytest.approx(math.exp(0.0 + 0.1 + 0.2))


def test_build_team_strengths():
    teams = {1: {'id': 1, 'code': 10, 'name': 'Arsenal'}, 2: {'id': 2, 'code': 20, 'name': 'Chelsea'}}
    ratings = {10: {'attack': 0.3, 'defence': -0.2}, 20: {'attack': -0.1, 'defence': 0.2}}
    squad = [
        player(1, team=1, position=4, xg=6.0, xa=0.0, chance=0, name='Striker'),
        player(2, team=1, position=3, xg=2.0, xa=2.0, chance=50, name='Winger'),
        player(3, team=1, position=2, xg=0.0, minutes=1000, chance=0, name='Back'),
        player(4, team=1, position=1, xg=0.0, minutes=1000, name='Keeper'),
        player(5, team=2, position=4, xg=1.0),
    ]
    result = build_team_strengths(teams, ratings, 0.3, squad)
    arsenal, chelsea = result[1], result[2]
    assert arsenal['team_id'] == 1 and arsenal['name'] == 'Arsenal'
    assert result[2]['missing'] == []
    assert chelsea['scored'] == pytest.approx(chelsea['scored_adjusted'])
    assert arsenal['scored_adjusted'] < arsenal['scored']
    assert arsenal['conceded_adjusted'] > arsenal['conceded']
    mean_scored = (arsenal['scored'] + chelsea['scored']) / 2
    assert arsenal['league_scored'] == pytest.approx(mean_scored)
    assert chelsea['league_scored'] == pytest.approx(mean_scored)
    shares = [m['share'] for m in arsenal['missing']]
    assert shares == sorted(shares, reverse=True)
    by_name = {m['name']: m for m in arsenal['missing']}
    assert by_name['Striker']['role'] == 'attack' and by_name['Striker']['position'] == 4
    assert by_name['Back']['role'] == 'defence' and by_name['Back']['position'] == 2
    assert 'Keeper' not in by_name


def test_unrated_team_gets_a_row_from_default_ratings():
    teams = {1: {'id': 1, 'code': 10, 'name': 'Arsenal'}, 2: {'id': 2, 'code': 99, 'name': 'New'}}
    ratings = {10: {'attack': 0.4, 'defence': 0.0}}
    result = build_team_strengths(teams, ratings, 0.3, [])
    assert set(result) == {1, 2}
    # league means are taken over both teams: attack mean 0.2, defence mean 0.0
    assert result[2]['scored'] == pytest.approx(math.exp(0.0 + 0.0 + 0.15))
    assert result[2]['conceded'] == pytest.approx(math.exp(0.2 + 0.0 + 0.15))


def test_missing_fraction_accepts_decimal_and_numeric_string():
    from decimal import Decimal
    assert missing_fraction(Decimal('25')) == 0.75
    assert missing_fraction('25') == 0.75


class FakeCursor:
    def __init__(self, rows):
        self.rows, self.executed = rows, []

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


def test_fetch_squad_rows_passes_year_twice():
    cursor = FakeCursor([{'id': 1}])
    assert fetch_squad_rows(cursor, 2026) == [{'id': 1}]
    assert cursor.executed[0][1] == (2026, 2026)


# ---- Persistence and loading (Task 4) ----
import json
from datetime import datetime

import FPL_site.teamStrength as ts
import FPL_site.matchPredictionEngine as engine


class StrengthCursor:
    def __init__(self, rows=None):
        self.calls = []
        self.rows = rows or []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, params):
        self.calls.append((sql, list(params)))

    def fetchone(self):
        return self.rows[0] if self.rows else None


class StrengthConn:
    def __init__(self, cursor=None):
        self.cur = cursor or StrengthCursor()
        self.committed = 0
        self.closed = False

    def cursor(self, **kwargs):
        return self.cur

    def commit(self):
        self.committed += 1

    def close(self):
        self.closed = True


def strength(tid, name='Arsenal'):
    return {'team_id': tid, 'name': name, 'scored': 1.5, 'scored_adjusted': 1.2,
            'conceded': 1.0, 'conceded_adjusted': 1.1, 'league_scored': 1.4,
            'missing': [{'name': 'Saka', 'position': 'midfielder', 'role': 'attack', 'share': 0.3, 'chance': 25}]}


def test_persist_replaces_table_in_one_commit():
    conn = StrengthConn()
    ts.persist_team_strengths(conn, {1: strength(1), 2: strength(2, 'Chelsea')})
    sqls = [c[0] for c in conn.cur.calls]
    assert f'CREATE TABLE IF NOT EXISTS {ts.STRENGTH_TABLE}' in sqls[0]
    assert sqls[1].strip().startswith(f'DELETE FROM {ts.STRENGTH_TABLE}')
    insert_sql, records = conn.cur.calls[2]
    assert insert_sql.strip().startswith(f'INSERT INTO {ts.STRENGTH_TABLE}')
    assert [r[0] for r in records] == [1, 2]
    assert json.loads(records[0][7])[0]['name'] == 'Saka'
    assert conn.committed == 1


def test_load_ready(monkeypatch):
    row = {'team_id': 1, 'name': 'Arsenal', 'scored': 1.54, 'scored_adjusted': 1.21,
           'conceded': 1.0, 'conceded_adjusted': 1.06, 'league_scored': 1.4,
           'missing_json': json.dumps(strength(1)['missing'])}
    conn = StrengthConn(StrengthCursor([row]))
    monkeypatch.setattr(ts, 'connect_db', lambda: conn)
    monkeypatch.setattr(engine, 'fetch_teams_for_season', lambda c, y: {1: {'id': 1, 'name': 'Arsenal'}})
    payload = ts.load_team_strength(1)
    assert payload['status'] == 'ready'
    assert payload['team_name'] == 'Arsenal'
    assert payload['scored'] == 1.5 and payload['scored_adjusted'] == 1.2
    assert payload['missing'][0]['name'] == 'Saka'
    assert payload['headline'] and payload['reason']
    assert conn.closed


def test_load_not_ready_when_no_row(monkeypatch):
    conn = StrengthConn(StrengthCursor([]))
    monkeypatch.setattr(ts, 'connect_db', lambda: conn)
    monkeypatch.setattr(engine, 'fetch_teams_for_season', lambda c, y: {1: {'id': 1, 'name': 'Arsenal'}})
    payload = ts.load_team_strength(1)
    assert payload['status'] == 'not_ready'
    assert payload['message']['title'] == 'Team strength is on its way'


def test_load_unknown_team_is_none(monkeypatch):
    conn = StrengthConn(StrengthCursor([]))
    monkeypatch.setattr(ts, 'connect_db', lambda: conn)
    monkeypatch.setattr(engine, 'fetch_teams_for_season', lambda c, y: {1: {'id': 1, 'name': 'Arsenal'}})
    assert ts.load_team_strength(99) is None
