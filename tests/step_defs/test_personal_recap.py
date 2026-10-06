import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.lastWeekRecap import build_personal_recap

scenarios('week/personal_recap.feature')


@given(parsers.parse('the average last week was {avg:d}'), target_fixture='ctx')
def average(avg):
    return {'average': avg, 'picks': None}


@given(parsers.parse('my team scored {gross:d} points with {cost:d} points of transfer costs'))
def team_scored(ctx, gross, cost):
    ctx['picks'] = {'picks': [], 'entry_history': {'points': gross, 'event_transfers_cost': cost}}


@given('my team number is not found')
def not_found(ctx):
    ctx['picks'] = None


@when('my personal recap is built')
def build(ctx):
    ctx['result'] = build_personal_recap(ctx['picks'], {}, ctx['average'], 5)


@then(parsers.parse('the verdict tier is "{tier}"'))
def tier(ctx, tier):
    assert ctx['result']['verdict_tier'] == tier


@then(parsers.parse('the verdict does not contain "{word}"'))
def no_word(ctx, word):
    assert word not in ctx['result']['verdict'].lower()


@then(parsers.parse('I see a gentle not-found message for gameweek {gw:d}'))
def gentle(ctx, gw):
    assert ctx['result']['status'] == 'team_not_found'
    assert f'gameweek {gw}' in ctx['result']['message']['body']
