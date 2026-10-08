import math
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import expectedPointsFeatures as ef


def hist(year, gw, points, team_code=3, minutes=90):
    return {'code': 1, 'year_start': year, 'gameweek': gw, 'team_code': team_code,
            'opponent_code': 14, 'was_home': True, 'minutes': minutes, 'goals_scored': 0,
            'assists': 0, 'clean_sheets': 0, 'bonus': 0, 'total_points': points}


def test_a_player_who_moved_club_keeps_his_form_and_takes_his_new_clubs_fixture():
    games = ef.player_gameweeks([hist(2026, 1, 9, team_code=3), hist(2026, 2, 9, team_code=7)])[1]
    new_club_fixture = {'team_xg': 2.2, 'opp_xg': 0.7, 'matches': 1, 'home_share': 1.0}
    row = ef.feature_row(1, 2026, 3, games, None, {}, new_club_fixture)
    assert row['points_last_3'] == 9.0
    assert row['team_xg'] == 2.2


def test_season_to_date_features_reset_at_a_new_season_but_form_does_not():
    games = ef.player_gameweeks([hist(2025, 38, 8)])[1]
    row = ef.feature_row(1, 2026, 1, games, None, {}, None)
    assert row['points_last_3'] == 8.0
    assert math.isnan(row['season_points_per_match'])
    assert row['matches_in_gameweek'] == 0


def test_per_gameweek_expected_goals_are_differences_between_snapshots():
    snaps = [{'code': 1, 'year_start': 2026, 'gameweek': g, 'expected_goals': xg, 'expected_assists': xa}
             for g, xg, xa in ((1, 0.4, 0.1), (2, 1.0, 0.1), (3, 1.5, 0.6))]
    xg = ef.per_gameweek_xg(snaps)
    assert xg[(1, 2026, 1)] == (0.4, 0.1)
    assert xg[(1, 2026, 2)] == (0.6, 0.0)
    assert xg[(1, 2026, 3)] == (0.5, 0.5)


def test_features_come_out_in_the_fixed_order():
    row = ef.feature_row(1, 2026, 2, [], None, {}, None)
    assert tuple(k for k in row if k in ef.FEATURES) == ef.FEATURES
