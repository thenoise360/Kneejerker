import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from FPL_site import expectedPointsRecord as rec

scenarios('expected_points/weekly_record.feature')

NOW = datetime(2026, 10, 8, 12, 0)


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, rows):
        self.calls.append((sql, list(rows)))


class FakeConn:
    def __init__(self):
        self.cur, self.commits = FakeCursor(), 0

    def cursor(self, **k):
        return self.cur

    def commit(self):
        self.commits += 1


@pytest.fixture
def ctx():
    return {}


@given('the gameweek 6 deadline is tomorrow')
def _tomorrow(ctx):
    ctx['deadline'] = NOW + timedelta(days=1)


@given('the gameweek 6 deadline was an hour ago')
def _passed(ctx):
    ctx['deadline'] = NOW - timedelta(hours=1)


@when(parsers.parse('the daily job logs {n:d} forecasts'))
def _log(ctx, n):
    rows = [{'player_id': i, 'code': 100 + i, 'expected_points': 3.0, 'official_expected_points': 2.5}
            for i in range(n)]
    ctx['written'] = rec.log_forecasts(FakeConn(), rows, 2026, 6, ctx['deadline'], NOW)


@when(parsers.parse('the daily job logs {n:d} forecasts for the {season:d} season'))
def _log_season(ctx, n, season):
    rows = [{'player_id': i, 'code': 100 + i, 'expected_points': 3.0, 'official_expected_points': 2.5}
            for i in range(n)]
    ctx['conn'] = FakeConn()
    rec.log_forecasts(ctx['conn'], rows, season, 6, ctx['deadline'], NOW)


@then(parsers.parse('every logged row is for the {season:d} season'))
def _season_rows(ctx, season):
    records = ctx['conn'].cur.calls[1][1]
    assert records and all(record[0] == season for record in records)


@then(parsers.parse('{n:d} rows are written to the log'))
def _written(ctx, n):
    assert ctx['written'] == n


@then('nothing is written to the log')
def _nothing(ctx):
    assert ctx['written'] == 0


@given('forecasts for a player of 4.0 on Wednesday, 5.0 on Thursday and 9.0 after the Friday deadline')
def _forecasts(ctx):
    ctx['deadline'] = datetime(2026, 10, 9, 17, 30)
    ctx['log'] = [{'player_id': 1, 'expected_points': 4.0, 'logged_at': datetime(2026, 10, 7, 6)},
                  {'player_id': 1, 'expected_points': 5.0, 'logged_at': datetime(2026, 10, 8, 6)},
                  {'player_id': 1, 'expected_points': 9.0, 'logged_at': datetime(2026, 10, 10, 6)}]


@when('I take the forecast of record')
def _record(ctx):
    ctx['record'] = rec.forecast_of_record(ctx['log'], ctx['deadline'])


@then(parsers.parse('it is {value:f}'))
def _value(ctx, value):
    assert ctx['record'][1]['expected_points'] == value


@given('gameweek 6 has finished but its data is not yet checked')
def _unchecked(ctx):
    ctx['events'] = [{'id': 6, 'deadline_time': '2026-10-03T10:00:00Z', 'finished': True, 'data_checked': False}]


@then('gameweek 6 is not settled')
def _not_settled(ctx):
    assert rec.is_settled(ctx['events'], 6) is False


@given('our forecasts of 6 and 2 and official forecasts of 3 and 3')
def _ours(ctx):
    ctx['record'] = {1: {'player_id': 1, 'position': 3, 'expected_points': 6.0, 'official_expected_points': 3.0},
                     2: {'player_id': 2, 'position': 3, 'expected_points': 2.0, 'official_expected_points': 3.0}}


@given('the players actually scored 8 and 1')
def _actual(ctx):
    ctx['actual'] = {1: 8, 2: 1}


@when('I work out the accuracy')
def _accuracy(ctx):
    ctx['result'] = rec.accuracy_for_gameweek(ctx['record'], ctx['actual'], [1, 2], {1, 2})


@then(parsers.parse('our average error is {ours:f} and the official average error is {official:f}'))
def _maes(ctx, ours, official):
    assert ctx['result']['mae_ours'] == pytest.approx(ours)
    assert ctx['result']['mae_official'] == pytest.approx(official)
