import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.lastWeekRecap import recap_payload

scenarios('week/last_week_recap.feature')


def make_player(name, points, goals, bonus):
    return {'id': hash(name) % 1000, 'name': name, 'team': 'MCI', 'position': 4, 'points': points,
            'minutes': 90, 'goals': goals, 'assists': 0, 'clean_sheets': 0, 'saves': 0,
            'bonus': bonus, 'penalties_saved': 0, 'difficulty': 3}


@given(parsers.parse('gameweek {gw:d} finished with an average of {avg:d} and a highest score of {high:d}'),
       target_fixture='ctx')
def finished_gameweek(gw, avg, high):
    return {'gameweek': gw, 'summary': {'average_score': avg, 'highest_score': high}, 'players': {}}


@given(parsers.parse('gameweek {gw:d} has no finished scores'), target_fixture='ctx')
def unfinished_gameweek(gw):
    return {'gameweek': gw, 'summary': None, 'players': {}}


@given(parsers.parse('"{name}" scored {points:d} points with {goals:d} goals and {bonus:d} bonus'))
def a_player(ctx, name, points, goals, bonus):
    player = make_player(name, points, goals, bonus)
    ctx['players'][player['id']] = player


@when('the guest recap is built')
def build(ctx):
    ctx['result'] = recap_payload(ctx['gameweek'], ctx['summary'], ctx['players'])


@then(parsers.parse('the headline is "{text}"'))
def headline(ctx, text):
    assert ctx['result']['guest']['headline'] == text


@then(parsers.parse('the reason is "{text}"'))
def reason(ctx, text):
    assert ctx['result']['guest']['reason'] == text


@then(parsers.parse('the numbers include an average of {avg:d}'))
def numbers(ctx, avg):
    assert ctx['result']['guest']['average_score'] == avg


@then('the recap is not ready')
def not_ready(ctx):
    assert ctx['result']['status'] == 'not_ready'
    assert ctx['result']['guest'] is None


@then(parsers.parse('the not-ready message mentions gameweek {gw:d}'))
def not_ready_message(ctx, gw):
    assert f'Gameweek {gw}' in ctx['result']['message']['title']
