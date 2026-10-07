import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from datetime import date

import pytest
from mysql.connector.errors import ProgrammingError

import FPL_site.predictionRecord as pr
import FPL_site.matchPredictionEngine as engine
from FPL_site.recordCopy import game_verdict
from FPL_site.predictionRecord import (
    fetch_record_rows, fetch_logging_started, shape_games, load_prediction_record,
)

TEAMS = {1: {'id': 1, 'name': 'Arsenal', 'short_name': 'ARS'},
         2: {'id': 2, 'name': 'Manchester City', 'short_name': 'MCI'}}


def row(gw=1, is_home=1, opp=2, kickoff='2026-08-15T14:00:00Z', pf=1.5, pa=1.0, h=2, a=0):
    return {'gameweek': gw, 'is_home': is_home, 'opponent_id': opp, 'kickoff_time': kickoff,
            'predicted_for': pf, 'predicted_against': pa, 'team_h_score': h, 'team_a_score': a}


def test_home_game_uses_home_score_for():
    game = shape_games([row(is_home=1, h=3, a=1)], TEAMS)[0]
    assert (game['actual_for'], game['actual_against']) == (3, 1)
    assert game['is_home'] is True
    assert game['opponent'] == 'Manchester City'


def test_away_game_uses_away_score_for():
    game = shape_games([row(is_home=0, h=3, a=1)], TEAMS)[0]
    assert (game['actual_for'], game['actual_against']) == (1, 3)
    assert game['is_home'] is False


def test_duplicate_fixture_rows_are_dropped():
    games = shape_games([row(), row(), row(gw=2, kickoff='2026-08-22T14:00:00Z')], TEAMS)
    assert [g['gameweek'] for g in games] == [1, 2]


def test_verdicts():
    games = shape_games([
        row(gw=1, pf=1.0, pa=1.0, h=3, a=0),
        row(gw=2, kickoff='b', pf=1.0, pa=1.0, h=1, a=1),
        row(gw=3, kickoff='c', pf=1.0, pa=1.0, h=0, a=2),
    ], TEAMS)
    assert [g['verdict'] for g in games] == ['better', 'as_expected', 'worse']


def test_predictions_are_floats():
    game = shape_games([row(pf='1.50', pa='0.80')], TEAMS)[0]
    assert game['predicted_for'] == 1.5 and game['predicted_against'] == 0.8


def test_unknown_opponent_is_skipped():
    assert shape_games([row(opp=99)], TEAMS) == []


class RecCursor:
    def __init__(self, rows=None, started=None, error=None):
        self.rows, self.started, self.error = rows or [], started, error
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if self.error and 'fixture_prediction_log' in sql:
            raise self.error

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return {'started': self.started}


class RecConn:
    def __init__(self, cursor):
        self.cur, self.closed = cursor, False

    def cursor(self, **kwargs):
        return self.cur

    def close(self):
        self.closed = True


def test_fetch_record_rows_passes_year_then_team():
    cursor = RecCursor([row()])
    assert fetch_record_rows(cursor, 7, 2026) == [row()]
    assert cursor.calls[0][1] == (2026, 7)


def test_fetch_record_rows_missing_table_gives_no_rows():
    cursor = RecCursor(error=ProgrammingError(msg='gone', errno=1146))
    assert fetch_record_rows(cursor, 7, 2026) == []


def test_fetch_record_rows_other_errors_propagate():
    cursor = RecCursor(error=ProgrammingError(msg='bad', errno=1064))
    with pytest.raises(ProgrammingError):
        fetch_record_rows(cursor, 7, 2026)


def test_fetch_logging_started():
    assert fetch_logging_started(RecCursor(started=date(2026, 8, 1))) == date(2026, 8, 1)
    assert fetch_logging_started(RecCursor(started=None)) is None


def test_fetch_logging_started_missing_table_is_none():
    cursor = RecCursor(error=ProgrammingError(msg='gone', errno=1146))
    assert fetch_logging_started(cursor) is None


def patch(monkeypatch, conn):
    monkeypatch.setattr(pr, 'connect_db', lambda: conn)
    monkeypatch.setattr(engine, 'fetch_teams_for_season', lambda c, y: TEAMS)


def test_record_with_no_finished_games(monkeypatch):
    conn = RecConn(RecCursor([], started=date(2026, 8, 1)))
    patch(monkeypatch, conn)
    payload = load_prediction_record(1)
    assert payload['status'] == 'ready'
    assert payload['games'] == []
    assert payload['team_name'] == 'Arsenal'
    assert payload['headline'] == 'No finished games logged yet'
    assert '1 August 2026' in payload['reason']
    assert payload['early_days'] is True
    assert payload['early_days_label'].startswith('Early days')
    assert conn.closed


def test_record_with_games_below_eight_is_early_days(monkeypatch):
    patch(monkeypatch, RecConn(RecCursor([row(pf=1, pa=1, h=3, a=0)], started=date(2026, 8, 1))))
    payload = load_prediction_record(1)
    assert len(payload['games']) == 1
    assert payload['early_days'] is True
    assert payload['early_days_label'] == 'Early days — this gets more reliable as the season goes on.'
    assert payload['started_on'] == '2026-08-01'
    assert 'beating their chances' in payload['headline']


def test_record_with_eight_games_is_not_early_days(monkeypatch):
    rows = [row(gw=i, kickoff=f'k{i}') for i in range(8)]
    patch(monkeypatch, RecConn(RecCursor(rows, started=date(2026, 8, 1))))
    payload = load_prediction_record(1)
    assert payload['early_days'] is False
    assert payload['early_days_label'] is None


def test_record_missing_table_is_ready_with_no_games(monkeypatch):
    cursor = RecCursor(error=ProgrammingError(msg='gone', errno=1146))
    patch(monkeypatch, RecConn(cursor))
    payload = load_prediction_record(1)
    assert payload['status'] == 'ready'
    assert payload['games'] == [] and payload['started_on'] is None
    assert payload['reason'] == "We'll start keeping score from their next game."


def test_record_unknown_team_is_none(monkeypatch):
    patch(monkeypatch, RecConn(RecCursor()))
    assert load_prediction_record(99) is None


def test_record_not_ready_when_no_connection(monkeypatch):
    monkeypatch.setattr(pr, 'connect_db', lambda: None)
    payload = load_prediction_record(1)
    assert payload['status'] == 'not_ready'
    assert payload['message']['title'] == 'Our prediction record is on its way'
    assert 'games' not in payload


def test_predictions_are_rounded_to_one_decimal_but_verdict_uses_raw():
    # 1.43727 vs 1.0 expected, scoring 2-1: the raw gap is small, so judge on the raw values.
    game = shape_games([row(pf=1.43727, pa=0.98412, h=2, a=1)], TEAMS)[0]
    assert game['predicted_for'] == 1.4 and game['predicted_against'] == 1.0
    raw = game_verdict(1.43727, 0.98412, 2, 1)
    assert game['verdict'] == raw


def test_rows_without_a_score_are_skipped():
    games = shape_games([row(h=None, a=None), row(gw=2, kickoff='b'), row(gw=3, kickoff='c', h=1, a=None)], TEAMS)
    assert [g['gameweek'] for g in games] == [2]


def test_record_sql_orders_by_kickoff_within_gameweek():
    class C:
        def execute(self, sql, params): self.sql = sql
        def fetchall(self): return []
    c = C()
    fetch_record_rows(c, 1, 2026)
    assert 'ORDER BY mine.gameweek, mine.kickoff_time' in c.sql
