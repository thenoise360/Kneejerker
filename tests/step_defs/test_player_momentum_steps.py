import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.playerMomentum import fixtures_signal, teammates_signal, player_momentum

scenarios('momentum/player_momentum.feature')

BASE_FOR = 1.4
BASE_AGAINST = 1.4


@given(parsers.parse('a forward whose team expects {own:f} goals a game against a typical {base:f}'),
       target_fixture='ctx')
def forward_kind(own, base):
    upcoming = [{'own_mean': own, 'opp_mean': 1.0}] * 3
    return {'fixtures': fixtures_signal(4, upcoming, base, BASE_AGAINST), 'teammates': []}


@given('a forward whose team has no game in the window', target_fixture='ctx')
def forward_blank():
    return {'fixtures': fixtures_signal(4, [], BASE_FOR, BASE_AGAINST), 'teammates': []}


@given(parsers.parse('a defender whose next three opponents are expected to score {opp:f} against a typical {base:f}'),
       target_fixture='ctx')
def defender_tough(opp, base):
    upcoming = [{'own_mean': 1.0, 'opp_mean': opp}] * 3
    return {'fixtures': fixtures_signal(2, upcoming, BASE_FOR, base), 'teammates': []}


@given(parsers.parse('a key teammate "{name}" with a {share:f} share who is back in the team'))
def teammate_back(ctx, name, share):
    ctx['teammates'].append({'id': 9, 'name': name, 'share': share, 'status': 'a',
                             'played_last': False, 'chance': None})


@given(parsers.parse('a key teammate "{name}" with a {share:f} share who is out'))
def teammate_out(ctx, name, share):
    ctx['teammates'].append({'id': 9, 'name': name, 'share': share, 'status': 'd',
                             'played_last': True, 'chance': 0})


@given('no teammate changes')
def no_changes(ctx):
    pass


@when('the momentum is worked out')
def work_out(ctx):
    ctx['result'] = player_momentum(ctx['fixtures'], teammates_signal(1, ctx['teammates']))


@then(parsers.parse('the label is "{label}"'))
def check_label(ctx, label):
    assert ctx['result']['label'] == label


@then(parsers.parse('the reason mentions "{word}"'))
def check_reason(ctx, word):
    assert word in ctx['result']['reason'].lower()


@then(parsers.parse('position is "{state}"'))
def check_position(ctx, state):
    assert ctx['result']['signals'][2]['direction'] == state


@then(parsers.parse('manager is "{state}"'))
def check_manager(ctx, state):
    assert ctx['result']['signals'][3]['direction'] == state
