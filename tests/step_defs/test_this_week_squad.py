import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

import FPL_site.squadContext as squad_context

scenarios('this_week/squad.feature')

IDS = {'Raya': 1, 'Saka': 2, 'Palmer': 3, 'Isak': 4}


def picks(gameweek, starters, chip=None, bank=0):
    """A minimal picks response: given names in slots 1.., then filler to 15."""
    rows = [{'element': IDS[name], 'position': i + 1, 'multiplier': 1,
             'is_captain': False, 'is_vice_captain': False} for i, name in enumerate(starters)]
    rows += [{'element': 100 + n, 'position': n, 'multiplier': 1 if n <= 11 else 0,
              'is_captain': False, 'is_vice_captain': False} for n in range(len(starters) + 1, 16)]
    return {'active_chip': chip, 'picks': rows, 'entry_history': {'event': gameweek, 'bank': bank}}


@given(parsers.parse('my gameweek {gw:d} team has "{keeper}" in goal and "{starter}" starting'),
       target_fixture='api')
def base_team(gw, keeper, starter):
    return {'picks': {gw: picks(gw, [keeper, starter])}, 'transfers': []}


@given(parsers.parse('I have {amount:f} million in the bank'))
def bank(api, amount):
    for data in api['picks'].values():
        data['entry_history']['bank'] = round(amount * 10)


@given(parsers.parse('I transferred "{out}" out for "{inn}" for gameweek {gw:d}'))
def transfer(api, out, inn, gw):
    api['transfers'].append({'element_out': IDS[out], 'element_in': IDS[inn], 'event': gw,
                             'element_out_cost': 80, 'element_in_cost': 80,
                             'time': f'2026-10-0{gw}T10:00:00Z'})


@given(parsers.parse('I transferred "{out}" out for "{inn}" for gameweek {gw:d} paying {extra:f} million more'))
def dearer_transfer(api, out, inn, gw, extra):
    api['transfers'].append({'element_out': IDS[out], 'element_in': IDS[inn], 'event': gw,
                             'element_out_cost': 80, 'element_in_cost': 80 + round(extra * 10),
                             'time': f'2026-10-0{gw}T10:00:00Z'})


@given(parsers.parse('I played my free hit in gameweek {gw:d} with "{inn}" instead of "{out}"'))
def free_hit(api, gw, inn, out):
    keeper = next(name for name, i in IDS.items() if i == api['picks'][gw - 1]['picks'][0]['element'])
    api['picks'][gw] = picks(gw, [keeper, inn], chip='freehit')
    api['transfers'].append({'element_out': IDS[out], 'element_in': IDS[inn], 'event': gw,
                             'element_out_cost': 80, 'element_in_cost': 80,
                             'time': f'2026-10-0{gw}T09:00:00Z'})


@when(parsers.parse('we work out my squad for gameweek {gw:d}'), target_fixture='context')
def work_out(api, gw, monkeypatch):
    def fake_picks(entry_id, gameweek):
        return ('ok', api['picks'][gameweek]) if gameweek in api['picks'] else ('not_found', None)
    monkeypatch.setattr(squad_context, 'fetch_entry_picks', fake_picks)
    monkeypatch.setattr(squad_context, 'fetch_entry_transfers', lambda entry_id: ('ok', api['transfers']))
    return squad_context.get_squad_context(123, gw - 1)


@then(parsers.parse('my squad includes "{name}" as a starter'))
def includes_starter(context, name):
    player = next(p for p in context['squad'] if p['id'] == IDS[name])
    assert player['starter'] is True


@then(parsers.parse('my squad does not include "{name}"'))
def excludes(context, name):
    assert IDS[name] not in [p['id'] for p in context['squad']]


@then(parsers.parse('my bank is {amount:f} million'))
def bank_is(context, amount):
    assert context['bank'] == round(amount * 10)
