import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from FPL_site import expectedPointsBackfill as bf
from FPL_site import expectedPointsBacktest as bt

scenarios('expected_points/backfill.feature')


@pytest.fixture
def ctx(monkeypatch):
    c = {'trained_on': [], 'logged': [], 'accuracy': [], 'done': set()}
    monkeypatch.setattr(bt, 'train', lambda rows: c['trained_on'].append(
        sorted({r['gameweek'] for r in rows})) or {})
    monkeypatch.setattr(bt, 'predict', lambda models, rows: [3.0] * len(rows))
    monkeypatch.setattr(bf, 'log_forecasts', lambda conn, rows, year, gw, deadline, now, source:
                        c['logged'].append((year, gw, source, len(rows))) or len(rows))
    monkeypatch.setattr(bf, 'persist_accuracy', lambda conn, gw, year, result, now, source:
                        c['accuracy'].append((year, gw, source)))
    return c


@given(parsers.parse('stored history for {year:d} gameweeks 1 to {last:d}'))
def _history(ctx, year, last):
    rows = [{'year_start': year, 'gameweek': gw, 'player_id': pid, 'code': 100 + pid, 'position': 3,
             'target': 2} for gw in range(1, last + 1) for pid in (1, 2)]
    ctx['data'] = {'rows': rows,
                   'official': {(year, gw, pid): 2.5 for gw in range(1, last + 1) for pid in (1, 2)},
                   'squads': {(year, gw): [1, 2] for gw in range(1, last + 1)}}


@given(parsers.parse('gameweeks 6 and 7 of {year:d} were already backfilled'))
def _done(ctx, year):
    ctx['done'] = {(year, 6), (year, 7)}


@when(parsers.parse('I backfill from {year:d} gameweek {gw:d}'))
def _backfill(ctx, year, gw):
    targets = bf.replay_targets(ctx['data']['rows'], year, gw, lambda y, g: True)
    ctx['written'] = bf.backfill(object(), ctx['data'], targets, ctx['done'], datetime(2026, 10, 9))


@then(parsers.parse('gameweek {gw:d} was forecast by a model trained on gameweeks 1 to {last:d}'))
def _trained(ctx, gw, last):
    assert list(range(1, last + 1)) in ctx['trained_on']


@then(parsers.parse('the log holds {year:d} forecasts for gameweeks 6, 7 and 8 marked as backfill'))
def _logged(ctx, year):
    assert [(y, g, s) for y, g, s, _ in ctx['logged']] == [(year, 6, 'backfill'), (year, 7, 'backfill'),
                                                           (year, 8, 'backfill')]


@then('an accuracy row marked as backfill exists for each of those gameweeks')
def _accuracy(ctx):
    assert [g for _, g, s in ctx['accuracy'] if s == 'backfill'] == [6, 7, 8]


@then(parsers.parse('only gameweek {gw:d} is written'))
def _only(ctx, gw):
    assert ctx['written'] == 1
    assert [g for _, g, _, _ in ctx['logged']] == [gw]
