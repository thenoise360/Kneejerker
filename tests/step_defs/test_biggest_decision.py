import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.weekDecision import biggest_decision, guest_biggest_decision

scenarios('week/biggest_decision.feature')

IDS = {'Saka': 1, 'Haaland': 2, 'Salah': 3}
TEAMS = {'Saka': 10, 'Haaland': 20, 'Salah': 30}


@given("this week's fixtures", target_fixture='ctx')
def this_weeks_fixtures():
    return {'squad': [], 'availability': {}, 'predictions': {IDS['Haaland']: 7.0, IDS['Salah']: 6.0},
            'fixtures': {10: {'opponent': 'Everton', 'is_home': True, 'difficulty': 2},
                         20: {'opponent': 'Burnley', 'is_home': False, 'difficulty': 2},
                         30: {'opponent': 'Arsenal', 'is_home': True, 'difficulty': 4}}}


@given(parsers.parse('my starter "{name}" has a {chance:d} percent chance of playing because "{news}"'))
def doubtful_starter(ctx, name, chance, news):
    add_player(ctx, name, chance=chance, news=news)


@given(parsers.parse('my captain is "{name}"'))
def captain(ctx, name):
    add_player(ctx, name, captain=True)


@given(parsers.parse('our prediction ranks "{better}" above "{worse}"'))
def ranking(ctx, better, worse):
    for name in (better, worse):
        add_player(ctx, name)
    ctx['predictions'] = {IDS[better]: 8.0, IDS[worse]: 6.0}


@given('there are no predictions')
def no_predictions(ctx):
    ctx['predictions'] = {}


@given('there is no team')
def no_team(ctx):
    ctx['squad'] = []


@when('the biggest decision is chosen')
def choose(ctx):
    ctx['result'] = biggest_decision(ctx['squad'], ctx['availability'], ctx['predictions'], ctx['fixtures'])


@when('the guest decision is chosen')
def choose_guest(ctx):
    ctx['result'] = guest_biggest_decision(ctx['availability'], ctx['predictions'], ctx['fixtures'])


@then(parsers.parse('the decision kind is "{kind}"'))
def kind(ctx, kind):
    assert ctx['result']['kind'] == kind


@then(parsers.parse('the reason mentions "{text}"'))
def mentions(ctx, text):
    assert text in ctx['result']['reason']


@then(parsers.parse('the reason ends with "{text}"'))
def ends(ctx, text):
    assert ctx['result']['reason'].endswith(text)


@then('there is no decision')
def none(ctx):
    assert ctx['result'] is None


def add_player(ctx, name, chance=None, news='', captain=False):
    """Known to the game (availability) and in my squad as a starter."""
    pid = IDS[name]
    ctx['availability'].setdefault(pid, {'name': name, 'team': TEAMS[name], 'chance': chance, 'news': news})
    if not any(p['id'] == pid for p in ctx['squad']):
        ctx['squad'].append({'id': pid, 'is_captain': captain, 'multiplier': 2 if captain else 1})
