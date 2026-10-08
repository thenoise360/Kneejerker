import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.hubRules import resolve_injuries, resolve_captaincy, select_headline, NEEDS_LOOK

FIX = {'opponent': 'Everton', 'is_home': True, 'difficulty': 2}


def _p(pid, starter=True, captain=False):
    return {'id': pid, 'slot': pid, 'starter': starter, 'is_captain': captain, 'is_vice': False}


def _a(name, team=10, chance=None):
    return {'name': name, 'team': team, 'chance': chance, 'status': 'a', 'news': ''}


def _risk(pct, tier):
    return {'pct': pct, 'tier': tier, 'reasons': []}


def test_injuries_list_starters_first_then_biggest_risk():
    squad = [_p(1, starter=False), _p(2), _p(3)]
    availability = {1: _a('Bench'), 2: _a('Zed'), 3: _a('Abe')}
    risks = {1: _risk(100, 'confirmed'), 2: _risk(50, 'medium'), 3: _risk(75, 'high')}
    players = resolve_injuries(squad, availability, risks)['players']
    assert [p['name'] for p in players] == ['Abe', 'Zed', 'Bench']


def test_low_risk_players_are_not_listed():
    result = resolve_injuries([_p(1)], {1: _a('A')}, {1: _risk(25, 'low')})
    assert result == {'state': 'nothing_to_do', 'players': []}


def test_captaincy_uses_starters_with_a_match_and_no_worries():
    squad = [_p(1), _p(2), _p(3), _p(4, starter=False)]
    availability = {1: _a('Fit', 10), 2: _a('Doubt', 10, chance=50), 3: _a('Blank', 99), 4: _a('Bench', 10)}
    predictions = {1: 0.8, 2: 2.0, 3: 2.0, 4: 3.0}
    result = resolve_captaincy(squad, availability, predictions, {10: FIX}, {})
    assert result['state'] == NEEDS_LOOK
    assert [o['name'] for o in result['shortlist']] == ['Fit']
    assert result['suggested']['name'] == 'Fit' and result['vice'] is None


def test_guest_captaincy_is_top_three_across_everyone():
    availability = {i: _a(f'P{i}') for i in range(1, 6)}
    predictions = {i: float(i) for i in range(1, 6)}
    result = resolve_captaincy([], availability, predictions, {10: FIX}, {})
    assert [o['name'] for o in result['shortlist']] == ['P5', 'P4', 'P3']
    assert result['vice']['name'] == 'P4'


def test_expected_points_are_rounded_for_display():
    result = resolve_captaincy([_p(1)], {1: _a('A')}, {1: 7.46}, {10: FIX}, {})
    assert result['suggested']['expected_points'] == 7.5


def test_option_has_the_agreed_summary_shape():
    info = {1: {'team_short': 'MCI', 'position': 'Forward', 'price': 145,
                'this_week': {'opponent_short': 'BOU', 'is_home': True, 'difficulty': 'easier'},
                'recent_points': [2, 13, 6, 2, 9]}}
    option = resolve_captaincy([_p(1)], {1: _a('A')}, {1: 7.4}, {10: FIX}, {}, info)['suggested']
    assert option == {'id': 1, 'name': 'A', 'team_short': 'MCI', 'position': 'Forward', 'price': 145,
                      'expected_points': 7.4,
                      'this_week': {'opponent_short': 'BOU', 'is_home': True, 'difficulty': 'easier'},
                      'recent_points': [2, 13, 6, 2, 9]}


def test_others_are_the_rest_of_the_squad_and_guests_get_none():
    squad = [_p(1), _p(2, starter=False), _p(3, starter=False), _p(4)]
    availability = {1: _a('A'), 2: _a('Bench'), 3: _a('Unpredicted'), 4: _a('Doubt', chance=25)}
    result = resolve_captaincy(squad, availability, {1: 5.0, 2: 6.0, 4: 9.0}, {10: FIX}, {4: _risk(75, 'high')})
    assert [o['name'] for o in result['others']] == ['Doubt', 'Bench', 'Unpredicted']
    guest = resolve_captaincy([], availability, {1: 5.0}, {10: FIX}, {})
    assert guest['others'] == []


def test_a_player_without_a_prediction_is_ranked_last_not_dropped():
    availability = {1: _a('Zed'), 2: _a('Abe')}
    result = resolve_captaincy([_p(1), _p(2)], availability, {1: 3.0}, {10: FIX}, {})
    assert [o['name'] for o in result['shortlist']] == ['Zed', 'Abe']
    assert result['shortlist'][1]['expected_points'] is None
    assert result['suggested']['name'] == 'Zed' and result['vice'] is None


def test_no_predictions_still_needs_a_look_with_no_suggestion():
    result = resolve_captaincy([_p(1)], {1: _a('A')}, {}, {10: FIX}, {})
    # Still listed (ranked by name) but we don't lean on anyone we have no number for.
    assert result['state'] == NEEDS_LOOK and result['suggested'] is None and result['vice'] is None
    assert [o['name'] for o in result['shortlist']] == ['A']
    assert select_headline(_ctx([_p(1)], {1: _a('A')}, {}))['reason_key'] == 'captain_no_prediction'


def _ctx(squad, availability, risks, predictions=None):
    return {'squad': squad, 'availability': availability, 'fixtures': {10: FIX},
            'injuries': resolve_injuries(squad, availability, risks),
            'captaincy': resolve_captaincy(squad, availability, predictions or {}, {10: FIX}, risks)}


def test_bench_doubt_does_not_fire_the_headline():
    risks = {1: {'pct': 75, 'tier': 'high', 'reasons': [{'key': 'official_doubt', 'chance': 25}]}}
    ctx = _ctx([_p(1, starter=False)], {1: _a('Bench', chance=25)}, risks)
    assert select_headline(ctx, ('starter_doubt',)) is None


def test_booked_or_early_subbed_starter_stays_in_the_captain_shortlist():
    squad = [_p(1), _p(2)]
    availability = {1: _a('Subbed'), 2: _a('Booked')}
    risks = {1: {'pct': 50, 'tier': 'medium', 'reasons': [{'key': 'subbed_early'}]},
             2: {'pct': 75, 'tier': 'high', 'reasons': [{'key': 'one_booking_from_ban'}]}}
    result = resolve_captaincy(squad, availability, {1: 1.0, 2: 0.9}, {10: FIX}, risks)
    assert [o['name'] for o in result['shortlist']] == ['Subbed', 'Booked']


def test_official_doubt_with_a_reason_is_still_a_captain_worry():
    risks = {1: {'pct': 50, 'tier': 'medium', 'reasons': [{'key': 'missed_last_game'}]}}
    assert resolve_captaincy([_p(1)], {1: _a('A')}, {1: 1.0}, {10: FIX}, risks)['shortlist'] == []


def test_headline_carries_the_availability_reason():
    risks = {1: {'pct': 75, 'tier': 'high', 'reasons': [{'key': 'subbed_early'}, {'key': 'missed_last_game'}]},
             2: {'pct': 100, 'tier': 'confirmed', 'reasons': [{'key': 'ruled_out'}]}}
    ctx = _ctx([_p(1), _p(2)], {1: _a('A'), 2: _a('B')}, risks)
    headline = select_headline(ctx, ('starter_doubt',))
    assert headline['player'] == 'B' and headline['reason'] == 'ruled_out'
    ctx = _ctx([_p(1)], {1: _a('A')}, {1: risks[1]})
    assert select_headline(ctx, ('starter_doubt',))['reason'] == 'missed_last_game'
