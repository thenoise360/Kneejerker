import math
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from FPL_site import expectedPointsFeatures as ef

scenarios('expected_points/features.feature')


def hist(code, year, gw, points, minutes=90, team_code=3):
    return {'code': code, 'year_start': year, 'gameweek': gw, 'team_code': team_code,
            'opponent_code': 14, 'was_home': True, 'minutes': minutes, 'goals_scored': 0,
            'assists': 0, 'clean_sheets': 0, 'bonus': 0, 'total_points': points}


def fixture_xg(year, gws, team_code=3):
    return {(year, gw, team_code): {'team_xg': 1.5, 'opp_xg': 1.0, 'matches': 1, 'home_share': 1.0}
            for gw in gws}


@pytest.fixture
def ctx():
    return {'history': [], 'fixtures': {}, 'year': 2026, 'row': None, 'rows': None}


@given('a player who scored 2 points in gameweeks 1 to 4 and 20 points in gameweek 5')
def _leak(ctx):
    ctx['history'] = [hist(1, 2026, gw, 2) for gw in range(1, 5)] + [hist(1, 2026, 5, 20)]
    ctx['fixtures'] = fixture_xg(2026, range(1, 6))


@given('a player with id 300 in 2025 who scored 6 points in each of his last 3 matches')
def _last_season(ctx):
    ctx['history'] = [hist(1, 2025, gw, 6) for gw in (36, 37, 38)]
    ctx['fixtures'] = fixture_xg(2026, [1])


@given('the same player with id 41 in 2026')
def _same_code(ctx):
    pass   # history rows carry the code, so the new id changes nothing


@given('a player who played twice in gameweek 7, scoring 5 and 8 points')
def _double(ctx):
    ctx['history'] = [hist(1, 2026, 7, 5), hist(1, 2026, 7, 8)]
    ctx['fixtures'] = {(2026, 7, 3): {'team_xg': 3.0, 'opp_xg': 2.0, 'matches': 2, 'home_share': 0.5}}


@given('a player whose club had no match in gameweek 8')
def _blank(ctx):
    ctx['history'] = [hist(1, 2026, 7, 5), hist(1, 2026, 9, 3)]
    ctx['fixtures'] = fixture_xg(2026, [7, 9])


@given('a player with no earlier matches')
def _new(ctx):
    ctx['history'] = []
    ctx['fixtures'] = fixture_xg(2026, [3])


@when(parsers.parse('I build the features for gameweek {gw:d}'))
def _features(ctx, gw):
    games = ef.player_gameweeks(ctx['history']).get(1, [])
    ctx['row'] = ef.feature_row(1, ctx['year'], gw, games, None, {}, ctx['fixtures'].get((ctx['year'], gw, 3)))


@when(parsers.parse('I build the features for {year:d} gameweek {gw:d}'))
def _features_year(ctx, year, gw):
    games = ef.player_gameweeks(ctx['history']).get(1, [])
    ctx['row'] = ef.feature_row(1, year, gw, games, None, {}, ctx['fixtures'].get((year, gw, 3)))


@when('I build the training rows')
def _training(ctx):
    snaps = [{'code': 1, 'player_id': 1, 'year_start': 2026, 'gameweek': g, 'element_type': 3,
              'team_code': 3, 'now_cost': 60, 'chance_of_playing_next_round': None,
              'ep_next': 3.0, 'expected_goals': 0.0, 'expected_assists': 0.0} for g in range(0, 10)]
    ctx['rows'] = ef.training_rows(ctx['history'], snaps, ctx['fixtures'])


@then(parsers.parse('the average points over the last 3 matches is {value:f}'))
def _avg(ctx, value):
    assert ctx['row']['points_last_3'] == pytest.approx(value)


@then('the average points over the last 3 matches is missing')
def _avg_missing(ctx):
    assert math.isnan(ctx['row']['points_last_3'])


@then('points per match this season is missing')
def _season_missing(ctx):
    assert math.isnan(ctx['row']['season_points_per_match'])


@then(parsers.parse('gameweek {gw:d} has a target of {points:d} points and {matches:d} matches'))
def _target(ctx, gw, points, matches):
    row = next(r for r in ctx['rows'] if r['gameweek'] == gw)
    assert row['target'] == points
    assert row['matches_in_gameweek'] == matches


@then(parsers.parse('there is no row for gameweek {gw:d}'))
def _no_row(ctx, gw):
    assert all(r['gameweek'] != gw for r in ctx['rows'])
