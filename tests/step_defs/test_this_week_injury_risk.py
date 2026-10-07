import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.hubSignals import assess_risk, player_signals

scenarios('this_week/injury_risk.feature')


def history(minutes, yellows=None):
    yellows = yellows or [0] * len(minutes)
    return [{'element': 1, 'fixture': i, 'kickoff_time': f'2026-09-{10 + i:02d}T15:00:00Z',
             'minutes': m, 'yellow_cards': y} for i, (m, y) in enumerate(zip(minutes, yellows))]


@given(parsers.parse('a player with a {chance:d} percent chance of playing because "{news}"'),
       target_fixture='ctx')
def doubt(chance, news):
    return {'player': {'chance': chance, 'status': 'd' if chance else 'i', 'news': news}, 'rows': []}


@given(parsers.parse('a fit player whose last five games were {a:d}, {b:d}, {c:d}, {d:d} and {e:d} minutes'),
       target_fixture='ctx')
def recent_minutes(a, b, c, d, e):
    return {'player': {'chance': None, 'status': 'a', 'news': ''}, 'rows': history([a, b, c, d, e])}


@given(parsers.parse('a fit player with {cards:d} yellow cards this season'), target_fixture='ctx')
def bookings(cards):
    games = 8
    yellows = [1] * cards + [0] * (games - cards)
    # Spread the cards across the season so the "booked more often" rule stays quiet.
    yellows = yellows[::2] + yellows[1::2]
    return {'player': {'chance': None, 'status': 'a', 'news': ''}, 'rows': history([90] * games, yellows)}


@when(parsers.parse('we assess the risk for gameweek {gw:d}'))
def assess(ctx, gw):
    ctx['risk'] = assess_risk(ctx['player'], player_signals(ctx['rows']).get(1), gw)


@then(parsers.parse('the risk tier is "{tier}"'))
def tier_is(ctx, tier):
    assert ctx['risk']['tier'] == tier, ctx['risk']


@then(parsers.parse('the risk is {pct:d} percent'))
def pct_is(ctx, pct):
    assert ctx['risk']['pct'] == pct


@then(parsers.parse('a reason is "{key}"'))
def reason_is(ctx, key):
    assert key in [r['key'] for r in ctx['risk']['reasons']], ctx['risk']
