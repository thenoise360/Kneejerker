import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.hubRules import HEADLINE_RULES, resolve_injuries, resolve_captaincy, select_headline
from FPL_site.hubSignals import assess_risk

scenarios('this_week/headline.feature')

IDS = {'Saka': 1, 'Haaland': 2, 'Salah': 3}
TEAMS = {'Saka': 10, 'Haaland': 20, 'Salah': 30}


@given(parsers.parse('my starters are "{a}", "{b}" and "{c}"'), target_fixture='ctx')
def starters(a, b, c):
    names = [a, b, c]
    return {
        'squad': [{'id': IDS[n], 'slot': i + 1, 'starter': True, 'is_captain': False, 'is_vice': False}
                  for i, n in enumerate(names)],
        'availability': {IDS[n]: {'name': n, 'team': TEAMS[n], 'chance': None, 'status': 'a', 'news': ''}
                         for n in names},
        'fixtures': {t: {'opponent': 'Everton', 'is_home': True, 'difficulty': 2} for t in TEAMS.values()},
        'predictions': {},
        'free_transfers': None,
        'signals': {},
        'rules': HEADLINE_RULES,
    }


@given(parsers.parse('our predictions rank "{first}" above "{second}" above "{third}"'))
def ranking(ctx, first, second, third):
    ctx['predictions'] = {IDS[first]: 1.2, IDS[second]: 0.9, IDS[third]: 0.5}


@given(parsers.parse('"{name}" has a {chance:d} percent chance of playing'))
def doubt(ctx, name, chance):
    ctx['availability'][IDS[name]].update(chance=chance, status='d')


@given(parsers.parse('"{name}" was subbed off early last game'))
def subbed_early(ctx, name):
    ctx['signals'][IDS[name]] = {'minutes_recent': [90, 90, 90, 90, 62]}


@given(parsers.parse('"{name}" is one booking from a ban'))
def one_from_ban(ctx, name):
    ctx['signals'][IDS[name]] = {'yellows_season': 4}   # gameweek 6: a ban comes at five


@given(parsers.parse('"{name}" has no match this gameweek'))
def blank(ctx, name):
    del ctx['fixtures'][TEAMS[name]]


@given(parsers.parse('I have {count:d} free transfers'))
def free_transfers(ctx, count):
    ctx['free_transfers'] = count


@given('I have not given a team number')
def guest(ctx):
    ctx['squad'] = []


def _resolve(ctx):
    risks = {p['id']: assess_risk(ctx['availability'][p['id']], ctx['signals'].get(p['id']), 6) for p in ctx['squad']}
    injuries = resolve_injuries(ctx['squad'], ctx['availability'], risks)
    captaincy = resolve_captaincy(ctx['squad'], ctx['availability'], ctx['predictions'],
                                  ctx['fixtures'], risks)
    return {'squad': ctx['squad'], 'availability': ctx['availability'], 'fixtures': ctx['fixtures'],
            'injuries': injuries, 'captaincy': captaincy, 'free_transfers': ctx['free_transfers']}


@when('the headline is chosen')
def choose(ctx):
    ctx['headline'] = select_headline(_resolve(ctx), ctx['rules'])


@when('the headline is chosen with the captain rule first')
def choose_reordered(ctx):
    rules = ('captain_choice',) + tuple(r for r in HEADLINE_RULES if r != 'captain_choice')
    ctx['headline'] = select_headline(_resolve(ctx), rules)


@when('the injuries decision is worked out')
def injuries(ctx):
    ctx['injuries'] = _resolve(ctx)['injuries']


@then(parsers.parse('the headline decision is "{decision}" because "{reason}" about "{player}"'))
def headline_about(ctx, decision, reason, player):
    h = ctx['headline']
    assert (h['decision'], h['reason_key'], h['player']) == (decision, reason, player), h


@then(parsers.parse('the headline decision is "{decision}" because "{reason:w}"'))  # :w so it can't swallow the longer "about" step
def headline_is(ctx, decision, reason):
    assert (ctx['headline']['decision'], ctx['headline']['reason_key']) == (decision, reason)


@then(parsers.parse('the injuries decision is "{state}"'))
def injuries_state(ctx, state):
    assert ctx['injuries']['state'] == state
