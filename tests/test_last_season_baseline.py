import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import playerHistory as ph


def rows(points_list, minutes=90, kickoff='2025-09-01T14:00:00Z'):
    """One history row per match, in separate gameweeks."""
    return [{'round': i + 1, 'fixture': i + 1, 'kickoff_time': kickoff,
             'opponent_team': 5, 'was_home': 1, 'total_points': p,
             'minutes': minutes if p is not None else 0} for i, p in enumerate(points_list)]


# ---- tier words: both sides of each boundary -------------------------------

@pytest.mark.parametrize('ppa, word', [
    (6.1, 'a regular points-scorer'),
    (5.0, 'a regular points-scorer'),
    (4.9, 'a steady contributor'),
    (3.0, 'a steady contributor'),
    (2.9, 'a quiet season'),
    (0.0, 'a quiet season'),
])
def test_tier_words(ppa, word):
    assert ph.last_season_tier(ppa) == word


def test_baseline_counts_only_matches_with_minutes_and_rounds_to_one_place():
    data = rows([10, 2, 3] + [6] * 7) + [{'round': 39, 'opponent_team': 5, 'was_home': 0, 'total_points': 0, 'minutes': 0}]
    result = ph.last_season_baseline(data, 'Brighton')
    assert result['appearances'] == 10
    assert result['points_per_appearance'] == 5.7
    assert result['tier'] == 'a regular points-scorer'
    assert result['club'] == 'Brighton'


def test_tier_uses_the_rounded_number_shown_on_screen():
    # 4.96 is shown as 5.0, so it must also read as a regular points-scorer.
    data = rows([5] * 24 + [4])  # 124/25 = 4.96
    result = ph.last_season_baseline(data, 'Brighton')
    assert result['points_per_appearance'] == 5.0
    assert result['tier'] == 'a regular points-scorer'


def test_no_appearances_gives_none():
    assert ph.last_season_baseline([], 'Brighton') is None
    benched = [{'round': 1, 'opponent_team': 5, 'was_home': 1, 'total_points': 0, 'minutes': 0}]
    assert ph.last_season_baseline(benched, 'Brighton') is None


def test_duplicate_rows_for_one_match_count_once():
    data = rows([6]) + rows([6])  # same fixture twice
    assert ph.last_season_baseline(data, 'Brighton')['appearances'] == 1


# ---- the fetcher, against a fake cursor ------------------------------------

class FakeCursor:
    """Answers by what the query asks for. Seasons: this = 2026, last = 2025."""
    def __init__(self, this_el=None, last_el=None, history=None, teams=None, snapshots=None):
        self.snapshots = snapshots or []
        self.this_el, self.last_el = this_el, last_el
        self.history = history or {}
        self.teams = teams or {}
        self.sql, self.params = '', ()

    def execute(self, sql, params=None):
        self.sql, self.params = sql, params or ()

    def fetchone(self):
        if 'bootstrapstatic_elements' in self.sql:
            return self.this_el if 'WHERE id' in self.sql else self.last_el
        if 'bootstrapstatic_teams' in self.sql:
            name = self.teams.get((self.params[0], self.params[1]))
            return {'name': name} if name else None
        return None

    def fetchall(self):
        if 'SELECT gameweek, team_code' in self.sql:
            return self.snapshots
        if 'elementsummary_history' in self.sql:
            return self.history.get((self.params[0], self.params[1]), [])
        return []


def cursor_for(**kw):
    return FakeCursor(**kw)


def test_fetch_matches_the_player_by_code_and_uses_last_seasons_club():
    cur = cursor_for(
        this_el={'code': 223340, 'team_code': 3},
        last_el={'id': 16, 'team_code': 3},
        history={(16, 2025): rows([8] * 34), (12, 2026): rows([6, 6], kickoff='2026-09-01T14:00:00Z')},
        teams={(3, 2025): 'Arsenal'})
    out = ph.fetch_last_season_baseline(cur, 12, this_year=2026)
    assert out['played'] is True
    assert out['club'] == 'Arsenal'
    assert out['appearances'] == 34
    assert out['this_season_appearances'] == 2
    assert out['headline'] == 'Last season: a regular points-scorer (Arsenal)'
    assert out['detail'] == 'about 8.0 points a game across 34 games'


def test_fetch_unknown_player_is_none():
    assert ph.fetch_last_season_baseline(cursor_for(), 999, this_year=2026) is None


def test_not_in_the_league_last_season_is_new():
    cur = cursor_for(this_el={'code': 1, 'team_code': 3}, last_el=None)
    out = ph.fetch_last_season_baseline(cur, 12, this_year=2026)
    assert out['played'] is False
    assert out['headline'] == 'Not in the Premier League last season'


def test_in_the_league_but_no_minutes_is_didnt_play():
    cur = cursor_for(this_el={'code': 1, 'team_code': 3}, last_el={'id': 4, 'team_code': 3},
                     history={(4, 2025): rows([0], minutes=0)})
    out = ph.fetch_last_season_baseline(cur, 12, this_year=2026)
    assert out['played'] is False
    assert out['headline'] == "Didn't play last season"


def test_club_name_falls_back_to_none_headline_without_it():
    cur = cursor_for(this_el={'code': 1, 'team_code': 3}, last_el={'id': 4, 'team_code': 3},
                     history={(4, 2025): rows([2] * 10)})
    out = ph.fetch_last_season_baseline(cur, 12, this_year=2026)
    assert out['headline'] == 'Last season: a quiet season'


# ---- the route --------------------------------------------------------------

def test_route_returns_200_404_and_500(monkeypatch):
    from FPL_site import views
    client = views.app.test_client()

    monkeypatch.setattr(views, 'load_last_season', lambda pid: {'played': False, 'headline': 'x'})
    assert client.get('/api/player/1/last-season').status_code == 200

    monkeypatch.setattr(views, 'load_last_season', lambda pid: None)
    assert client.get('/api/player/1/last-season').status_code == 404

    def boom(pid):
        raise RuntimeError('db down')
    monkeypatch.setattr(views, 'load_last_season', boom)
    assert client.get('/api/player/1/last-season').status_code == 500


def test_fewer_than_ten_appearances_is_a_small_sample_with_no_rate_tier():
    nine = ph.last_season_baseline(rows([8] * 9), 'Brentford')
    assert nine['appearances'] == 9
    assert nine['tier'] == 'only a few games'
    ten = ph.last_season_baseline(rows([8] * 10), 'Brentford')
    assert ten['appearances'] == 10
    assert ten['tier'] == 'a regular points-scorer'


def test_small_sample_headline_names_the_club_and_keeps_the_numbers_behind_details():
    cur = cursor_for(this_el={'code': 1, 'team_code': 3}, last_el={'id': 4, 'team_code': 94},
                     history={(4, 2025): rows([6] * 4)}, teams={(94, 2025): 'Brentford'})
    out = ph.fetch_last_season_baseline(cur, 12, this_year=2026)
    assert out['headline'] == 'Only a few games last season (Brentford)'
    assert out['detail'] == 'about 6.0 points a game across 4 games'
    for word in ('regular', 'steady', 'quiet'):
        assert word not in out['headline']


def test_a_row_misfiled_from_another_season_is_ignored():
    # The update job once wrote a new season's gameweek 1 under the old year_start.
    stray = dict(rows([9])[0], fixture=999, round=1, kickoff_time='2026-08-15T14:00:00Z')
    cur = cursor_for(this_el={'code': 1, 'team_code': 3}, last_el={'id': 4, 'team_code': 3},
                     history={(4, 2025): rows([2] * 10) + [stray]}, teams={(3, 2025): 'Arsenal'})
    out = ph.fetch_last_season_baseline(cur, 12, this_year=2026)
    assert out['appearances'] == 10
    assert out['points_per_appearance'] == 2.0


def test_the_same_fixture_twice_counts_once_even_if_the_round_differs():
    first = rows([5])[0]
    again = dict(first, round=2)           # same fixture id, filed twice
    assert ph.last_season_baseline([first, again], 'Arsenal')['appearances'] == 1


# ---- a player who changed club in the middle of last season ---------------------

def snap(first, last, team_code):
    return [{'gameweek': g, 'team_code': team_code} for g in range(first, last + 1)]


def test_nearest_snapshot_is_used_for_a_gameweek_without_one():
    snapshots = ph.snapshot_teams(snap(1, 10, 3) + snap(21, 38, 6))
    assert ph.club_code_at(snapshots, 5, 99) == 3
    assert ph.club_code_at(snapshots, 12, 99) == 3     # nearer to 10 than to 21
    assert ph.club_code_at(snapshots, 19, 99) == 6     # nearer to 21
    assert ph.club_code_at({}, 5, 99) == 99            # no snapshots: fall back


def test_club_is_the_one_with_the_most_appearances_for_a_mid_season_mover():
    first_club = [dict(r, round=g, fixture=g) for g, r in zip(range(1, 6), rows([4] * 5))]
    second_club = [dict(r, round=g, fixture=g) for g, r in zip(range(21, 33), rows([4] * 12))]
    cur = cursor_for(this_el={'code': 1, 'team_code': 6}, last_el={'id': 4, 'team_code': 3},
                     history={(4, 2025): first_club + second_club},
                     snapshots=snap(1, 10, 3) + snap(11, 38, 6),
                     teams={(3, 2025): 'Arsenal', (6, 2025): 'Spurs'})
    out = ph.fetch_last_season_baseline(cur, 12, this_year=2026)
    assert out['appearances'] == 17
    assert out['headline'].endswith('(Spurs)')
