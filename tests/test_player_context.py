import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import json

import FPL_site.playerContext as pc
from FPL_site.thisWeekHub import build_hub, candidate_ids
from FPL_site.playerMomentum import fixtures_signal


def fx(team_id, gw, opponent, home, own, opp):
    return {'team_id': team_id, 'gameweek': gw, 'opponent_id': opponent, 'is_home': home,
            'own_mean': own, 'opp_mean': opp}


UPCOMING = [fx(10, 6, 20, 1, 2.6, 0.9), fx(10, 7, 30, 0, 2.0, 1.0), fx(10, 8, 20, 0, 1.0, 2.0)]
BASELINES = {10: {'scored': 2.0, 'conceded': 1.0}}
SHORTS = {10: 'MCI', 20: 'BOU', 30: 'WOL'}


def test_difficulty_agrees_with_the_momentum_signal():
    # Same rule: where momentum says up/down/same, difficulty says easier/tougher/average.
    words = {'up': 'easier', 'down': 'tougher', 'same': 'average'}
    for own, opp in [(2.6, 0.9), (1.0, 2.0), (2.0, 1.0)]:
        for position in (2, 4):
            row = fx(10, 6, 20, 1, own, opp)
            signal = fixtures_signal(position, [row], 2.0, 1.0)['direction']
            assert pc.fixture_difficulty(position, row, BASELINES[10]) == words[signal]


def test_difficulty_is_unknown_without_data():
    assert pc.fixture_difficulty(4, None, BASELINES[10]) is None
    assert pc.fixture_difficulty(4, fx(10, 6, 20, 1, None, 1.0), BASELINES[10]) is None
    assert pc.fixture_difficulty(4, fx(10, 6, 20, 1, 2.0, 1.0), None) is None


def test_league_average_is_the_fallback_baseline():
    fact = pc.this_week_fact(4, 10, 6, UPCOMING, {}, SHORTS)
    assert fact['opponent_short'] == 'BOU' and fact['is_home'] is True
    assert fact['difficulty'] in ('easier', 'average', 'tougher')
    assert pc.this_week_fact(4, 10, 9, UPCOMING, BASELINES, SHORTS) is None


def test_this_week_fact_shape():
    assert pc.this_week_fact(4, 10, 6, UPCOMING, BASELINES, SHORTS) == {
        'opponent_short': 'BOU', 'is_home': True, 'difficulty': 'easier'}


def test_recent_points_last_five_oldest_first_and_double_gameweeks_add_up():
    rows = [{'element': 1, 'fixture': i, 'round': r, 'total_points': p}
            for i, (r, p) in enumerate([(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (5, 1), (6, 9)])]
    rows.append(dict(rows[0]))   # a row stored twice counts once
    assert pc.recent_points(rows, before_gameweek=7) == {1: [3, 4, 5, 7, 9]}
    assert pc.recent_points(rows, before_gameweek=3) == {1: [2, 3]}


def test_predicted_points_and_position_averages_skip_nulls():
    rows = [{'player_id': 1, 'predicted_performance': 6.0, 'element_type': 3},
            {'player_id': 2, 'predicted_performance': 2.0, 'element_type': 3},
            {'player_id': 3, 'predicted_performance': None, 'element_type': 3}]
    assert pc.predicted_points_map(rows) == {1: 6.0, 2: 2.0}
    assert pc.position_averages(rows) == {3: 4.0}


def test_fetch_predicted_points_survives_a_missing_table():
    class Boom:
        def execute(self, *a):
            raise RuntimeError('no such table')
    assert pc.fetch_predicted_points(Boom(), 6) == []
    assert pc.fetch_latest_prediction_gameweek(Boom()) is None


def test_games_against_dedupes_and_orders_across_seasons():
    teams = [{'year_start': 2025, 'id': 12, 'code': 43}, {'year_start': 2026, 'id': 3, 'code': 43}]
    base = {'element': 7, 'opponent_team': 12, 'was_home': 1, 'minutes': 90, 'total_points': 5}
    rows = [dict(base, year_start=2025, fixture=1, round=4, kickoff_time='2025-09-01'),
            dict(base, year_start=2025, fixture=1, round=4, kickoff_time='2025-09-01'),
            dict(base, year_start=2026, fixture=9, round=2, kickoff_time='2026-08-20', opponent_team=3)]
    assert [(g['season'], g['gameweek']) for g in pc.games_against(rows, teams, 43)] == [(2025, 4), (2026, 2)]


def player_data(**overrides):
    data = {
        'ids': [1, 99],
        'players': [{'id': 1, 'code': 500, 'web_name': 'Haaland', 'team': 10, 'element_type': 4, 'now_cost': 145}],
        'predictions': [{'player_id': 1, 'predicted_performance': 7.44, 'element_type': 4},
                        {'player_id': 2, 'predicted_performance': 2.0, 'element_type': 4}],
        'upcoming': UPCOMING, 'baselines': BASELINES,
        'teams': [{'year_start': 2026, 'id': 10, 'code': 8, 'short_name': 'MCI'},
                  {'year_start': 2026, 'id': 20, 'code': 43, 'short_name': 'BOU'},
                  {'year_start': 2026, 'id': 30, 'code': 39, 'short_name': 'WOL'},
                  {'year_start': 2025, 'id': 14, 'code': 43, 'short_name': 'BOU'}],
        'element_codes': [{'year_start': 2026, 'id': 1, 'code': 500}, {'year_start': 2025, 'id': 77, 'code': 500}],
        'history': [
            {'year_start': 2026, 'element': 1, 'fixture': 1, 'round': 1, 'kickoff_time': '2026-08-15',
             'opponent_team': 30, 'was_home': 0, 'minutes': 90, 'goals_scored': 2, 'assists': 0, 'total_points': 13},
            {'year_start': 2025, 'element': 77, 'fixture': 50, 'round': 12, 'kickoff_time': '2025-11-20',
             'opponent_team': 14, 'was_home': 0, 'minutes': 90, 'goals_scored': 0, 'assists': 1, 'total_points': 8},
            {'year_start': 2025, 'element': 78, 'fixture': 51, 'round': 12, 'kickoff_time': '2025-11-20',
             'opponent_team': 14, 'was_home': 0, 'minutes': 90, 'goals_scored': 0, 'assists': 1, 'total_points': 99}],
        'momentum': {1: {'label': 'Rising', 'signals_json': json.dumps([{'key': 'fixtures', 'direction': 'up'}])}},
    }
    data.update(overrides)
    return data


def test_build_player_context_matches_the_agreed_shape():
    result = pc.build_player_context(6, player_data())
    assert result['status'] == 'ready' and result['gameweek'] == 6
    assert len(result['players']) == 1   # unknown id 99 is omitted
    p = result['players'][0]
    assert (p['id'], p['name'], p['team_short'], p['position'], p['price']) == (1, 'Haaland', 'MCI', 'Forward', 145)
    assert p['predicted_points'] == 7.4 and p['position_average_predicted_points'] == 4.7
    assert p['recent_games'] == [{'gameweek': 1, 'opponent_short': 'WOL', 'is_home': False,
                                  'minutes': 90, 'goals': 2, 'assists': 0, 'points': 13}]
    assert p['momentum'] == {'label': 'Rising', 'signals': [{'key': 'fixtures', 'direction': 'up'}]}
    assert [f['gameweek'] for f in p['next_fixtures']] == [6, 7, 8]
    assert p['next_fixtures'][0] == {'gameweek': 6, 'opponent_short': 'BOU', 'is_home': True, 'difficulty': 'easier'}
    # Last season's club had a different id but the same code; only this player's games count.
    assert p['vs_opponent'] == {'opponent_short': 'BOU', 'games': [
        {'season': 2025, 'gameweek': 12, 'is_home': False, 'minutes': 90, 'points': 8}]}


def test_no_match_this_week_means_no_vs_opponent_and_no_momentum_is_null():
    data = player_data(upcoming=[], momentum={})
    p = pc.build_player_context(6, data)['players'][0]
    assert p['vs_opponent'] is None and p['momentum'] is None and p['next_fixtures'] == []


def test_no_past_meetings_gives_empty_games():
    data = player_data(history=[])
    assert pc.build_player_context(6, data)['players'][0]['vs_opponent']['games'] == []


def test_missing_prediction_is_null():
    data = player_data(predictions=[])
    p = pc.build_player_context(6, data)['players'][0]
    assert p['predicted_points'] is None and p['position_average_predicted_points'] is None


def test_get_player_context_without_a_gameweek_or_database(monkeypatch):
    monkeypatch.setattr(pc, 'connect_db', lambda: None)
    assert pc.get_player_context([1]) == {'status': 'unavailable'}


#################################################
#                  Hub options                  #
#################################################

ROWS = [{'id': 1, 'web_name': 'Haaland', 'team': 10, 'chance_of_playing_next_round': None, 'news': '',
         'element_type': 4, 'status': 'a', 'expected_goals': 1, 'expected_assists': 1, 'now_cost': 145},
        {'id': 2, 'web_name': 'Bench', 'team': 10, 'chance_of_playing_next_round': None, 'news': '',
         'element_type': 2, 'status': 'a', 'expected_goals': 1, 'expected_assists': 1, 'now_cost': 45}]
FACTS = {'team_shorts': SHORTS, 'upcoming': UPCOMING, 'baselines': BASELINES,
         'recent_rows': [{'element': 1, 'fixture': i, 'round': i, 'total_points': 2 * i} for i in range(1, 6)]}
SQUAD = {'status': 'ok', 'squad_gameweek': 5, 'squad': [
    {'id': 1, 'slot': 1, 'starter': True, 'is_captain': False, 'is_vice': False},
    {'id': 2, 'slot': 12, 'starter': False, 'is_captain': False, 'is_vice': False}]}
FIXTURES = {10: {'opponent': 'Bournemouth', 'is_home': True, 'difficulty': 2}}


def test_hub_options_carry_the_summary():
    hub = build_hub(6, SQUAD, ROWS, {1: 7.44, 2: 3.0}, FIXTURES, [], FACTS)
    captaincy = hub['decisions']['captaincy']
    assert captaincy['suggested'] == {
        'id': 1, 'name': 'Haaland', 'team_short': 'MCI', 'position': 'Forward', 'price': 145,
        'predicted_points': 7.4,
        'this_week': {'opponent_short': 'BOU', 'is_home': True, 'difficulty': 'easier'},
        'recent_points': [2, 4, 6, 8, 10]}
    assert [o['name'] for o in captaincy['others']] == ['Bench']
    assert captaincy['others'][0]['position'] == 'Defender' and captaincy['others'][0]['recent_points'] == []
    json.dumps(hub)   # plain JSON, no sentences needed


def test_guest_candidates_are_the_best_predicted():
    assert candidate_ids([], {i: float(i) for i in range(1, 30)}) == list(range(29, 19, -1))
    assert candidate_ids([5, 6], {1: 9.0}) == [5, 6]
