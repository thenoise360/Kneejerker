import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.strengthCopy import strength_summary

scenarios('team/strength.feature')


def _defaults():
    return {'scored': 1.9, 'scored_adjusted': 1.9, 'conceded': 1.0,
            'conceded_adjusted': 1.0, 'league_scored': 1.4, 'missing': []}


def _missing(name, role, position=3):
    return {'name': name, 'role': role, 'share': 0.2, 'chance': 0, 'position': position}


@given(parsers.parse('a team that scores {raw:f} a game and {adjusted:f} with absences'),
       target_fixture='ctx')
def scoring_team(raw, adjusted):
    strength = _defaults()
    strength['scored'], strength['scored_adjusted'] = raw, adjusted
    return {'strength': strength}


@given(parsers.parse('a team that concedes {raw:f} a game and {adjusted:f} with absences'),
       target_fixture='ctx')
def conceding_team(raw, adjusted):
    strength = _defaults()
    strength['conceded'], strength['conceded_adjusted'] = raw, adjusted
    return {'strength': strength}


@given(parsers.parse('"{first}" and "{second}" are missing chance-creators'))
def missing_creators(ctx, first, second):
    ctx['strength']['missing'] += [_missing(first, 'attack'), _missing(second, 'attack')]


@given(parsers.parse('"{name}" is a missing defender'))
def missing_defender(ctx, name):
    ctx['strength']['missing'].append(_missing(name, 'defence', position=2))


@when(parsers.parse('the strength summary is written for "{team}"'))
def write_summary(ctx, team):
    ctx['result'] = strength_summary(team, ctx['strength'])


@then(parsers.parse('the headline is "{text}"'))
def headline(ctx, text):
    assert ctx['result']['headline'] == text


@then(parsers.parse('the reason is "{text}"'))
def reason(ctx, text):
    assert ctx['result']['reason'] == text
