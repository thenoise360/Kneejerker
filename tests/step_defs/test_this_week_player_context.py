import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import re

import pytest
from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site import app
import FPL_site.views as views
from FPL_site.hubRules import resolve_captaincy
from FPL_site.playerContext import fixture_difficulty, games_against

scenarios('this_week/player_context.feature')

IDS = {'Saka': 1, 'Haaland': 2, 'Salah': 3}
TEAM = 10
FIX = {TEAM: {'opponent': 'Everton', 'is_home': True, 'difficulty': 2}}


def _squad(starters, bench):
    squad = [{'id': IDS[n], 'slot': i, 'starter': True, 'is_captain': False, 'is_vice': False}
             for i, n in enumerate(starters)]
    squad += [{'id': IDS[n], 'slot': 12 + i, 'starter': False, 'is_captain': False, 'is_vice': False}
              for i, n in enumerate(bench)]
    return {'squad': squad, 'predictions': {},
            'availability': {IDS[n]: {'name': n, 'team': TEAM, 'chance': None, 'status': 'a', 'news': ''}
                             for n in starters + bench}}


def _words(text):
    return [n.strip('" ') for n in re.split(r',|\band\b', text) if n.strip('" ')]


#################################################
#                 Captain choice                #
#################################################

@given(parsers.re(r'my starters are "(?P<a>[^"]+)", "(?P<b>[^"]+)" and "(?P<c>[^"]+)"'), target_fixture='ctx')
def three_starters(a, b, c):
    return _squad([a, b, c], [])


@given(parsers.re(r'my starters are "(?P<a>[^"]+)" and "(?P<b>[^"]+)"'), target_fixture='ctx')
def two_starters(a, b):
    return _squad([a, b], [])


@given(parsers.parse('"{name}" is on my bench'))
def bench(ctx, name):
    ctx['squad'].append({'id': IDS[name], 'slot': 12, 'starter': False, 'is_captain': False, 'is_vice': False})
    ctx['availability'][IDS[name]] = {'name': name, 'team': TEAM, 'chance': None, 'status': 'a', 'news': ''}


@given(parsers.re(r'their expected points are (?P<pairs>.+)'))
def expected(ctx, pairs):
    for name, value in re.findall(r'"(\w+)" ([\d.]+)', pairs):
        ctx['predictions'][IDS[name]] = float(value)


@when('the captain choice is made', target_fixture='captaincy')
def captain_choice(ctx):
    return resolve_captaincy(ctx['squad'], ctx['availability'], ctx['predictions'], FIX, {})


@then(parsers.parse('the shortlist reads {names}'))
def shortlist(captaincy, names):
    assert [o['name'] for o in captaincy['shortlist']] == _words(names)


@then(parsers.parse('the rest of the squad reads {names}'))
def rest(captaincy, names):
    assert [o['name'] for o in captaincy['others']] == _words(names)


@then(parsers.parse('the vice is "{name}"'))
def vice(captaincy, name):
    assert captaincy['vice']['name'] == name


#################################################
#                  Difficulty                   #
#################################################

@given(parsers.parse('an attacker whose team usually scores {usual:g} expected goals'), target_fixture='diff')
def attacker(usual):
    return {'position': 4, 'strength': {'scored': usual, 'conceded': 1.0}}


@given(parsers.parse('a defender whose team usually concedes {usual:g} expected goals'), target_fixture='diff')
def defender(usual):
    return {'position': 2, 'strength': {'scored': 1.0, 'conceded': usual}}


@when(parsers.parse('their match is expected to bring {own:g} expected goals'))
def own_goals(diff, own):
    diff['fixture'] = {'own_mean': own, 'opp_mean': 1.0}


@when(parsers.parse('the opponent is expected to score {opp:g} expected goals'))
def opp_goals(diff, opp):
    diff['fixture'] = {'own_mean': 1.0, 'opp_mean': opp}


@then(parsers.parse('the difficulty is {word}'))
def difficulty(diff, word):
    assert fixture_difficulty(diff['position'], diff['fixture'], diff['strength']) == word


#################################################
#                 Past meetings                 #
#################################################

@given(parsers.parse('the opponent has club code {code:d}'), target_fixture='meet')
def opponent_code(code):
    return {'code': code, 'teams': [], 'history': [], 'old': None}


@given(parsers.parse('last season that club had id {old:d} and this season it has id {new:d}'))
def club_ids(meet, old, new):
    meet['teams'] += [{'year_start': 2025, 'id': old, 'code': meet['code'], 'short_name': 'BOU'},
                      {'year_start': 2026, 'id': new, 'code': meet['code'], 'short_name': 'BOU'},
                      {'year_start': 2025, 'id': 3, 'code': 99, 'short_name': 'OTH'},
                      {'year_start': 2026, 'id': old, 'code': 98, 'short_name': 'NEW'}]
    meet['old'] = old


@given(parsers.parse('the player met them last season in gameweek {gw:d} away for {mins:d} minutes and {pts:d} points'))
def met(meet, gw, mins, pts):
    meet['history'].append({'year_start': 2025, 'element': 7, 'fixture': 100 + gw, 'round': gw,
                            'kickoff_time': '2025-11-01', 'opponent_team': meet['old'],
                            'was_home': 0, 'minutes': mins, 'total_points': pts})


@given('the player met other clubs too')
def met_others(meet):
    # This season's club with last season's id for the opponent is a different club (code 98),
    # and last season's id 3 was a club with another code.
    meet['history'] += [
        {'year_start': 2026, 'element': 7, 'fixture': 5, 'round': 2, 'kickoff_time': '2026-08-30',
         'opponent_team': meet['old'], 'was_home': 1, 'minutes': 90, 'total_points': 2},
        {'year_start': 2025, 'element': 7, 'fixture': 6, 'round': 3, 'kickoff_time': '2025-09-01',
         'opponent_team': 3, 'was_home': 1, 'minutes': 90, 'total_points': 6}]


@when('past meetings are listed', target_fixture='meetings')
def list_meetings(meet):
    return games_against(meet['history'], meet['teams'], meet['code'])


@then(parsers.parse('there is 1 past meeting, from season {season:d}, in gameweek {gw:d}, away, {mins:d} minutes, {pts:d} points'))
def one_meeting(meetings, season, gw, mins, pts):
    assert meetings == [{'season': season, 'gameweek': gw, 'is_home': False, 'minutes': mins, 'points': pts}]


@then('there are no past meetings')
def no_meetings(meetings):
    assert meetings == []


#################################################
#                     Route                     #
#################################################

@pytest.fixture
def route(monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    monkeypatch.setattr(views, 'get_player_context',
                        lambda ids, gameweek=None: {'status': 'ready', 'gameweek': 6, 'players': []})
    return {}


@given('the database is down')
def db_down(route, monkeypatch):
    import FPL_site.playerContext as pc
    monkeypatch.setattr(views, 'get_player_context', pc.get_player_context)
    monkeypatch.setattr(pc, 'connect_db', lambda: None)


@when(parsers.re(r'I ask for player context with ids "(?P<ids>[^"]*)"'), target_fixture='response')
def ask(route, ids):
    return app.test_client().get('/api/week/player-context?ids=' + ids)


@then(parsers.parse('the response status is {status:d}'))
def status_is(response, status):
    assert response.status_code == status


@then(parsers.parse('the response status field is "{word}"'))
def status_field(response, word):
    assert response.get_json()['status'] == word
