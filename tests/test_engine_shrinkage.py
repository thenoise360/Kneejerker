import os
os.environ['KJ_SKIP_DB_INIT'] = '1'

import numpy as np

from FPL_site.matchPredictionEngine import (
    fit_dixon_coles, team_priors, ESTABLISHED_GAMES, PROMOTED_PRIOR, SHRINKAGE,
)

GW = 10
LEAGUE = [1, 2, 3, 4, 5, 6]


def league_rows(repeats):
    """A balanced league: every ordered pair meets `repeats` times with deterministic, mild scores."""
    rows, i = [], 0
    for _ in range(repeats):
        for h in LEAGUE:
            for a in LEAGUE:
                if h == a:
                    continue
                rows.append({'code_h': h, 'code_a': a, 'goals_h': i % 3, 'goals_a': (i // 2) % 3, 'unified_gw': GW})
                i += 1
    return rows


def with_newcomer(rows, n_games=3):
    """Team 99 plays `n_games`, always winning big, so its raw rating is extreme."""
    extra = []
    for k in range(n_games):
        opp = LEAGUE[k % len(LEAGUE)]
        if k % 2 == 0:
            extra.append({'code_h': 99, 'code_a': opp, 'goals_h': 6, 'goals_a': 0, 'unified_gw': GW})
        else:
            extra.append({'code_h': opp, 'code_a': 99, 'goals_h': 0, 'goals_a': 6, 'unified_gw': GW})
    return rows + extra, LEAGUE + [99]


def test_low_data_team_is_pulled_towards_its_prior():
    rows, codes = with_newcomer(league_rows(4), n_games=3)
    # a near-zero (not zero) penalty still anchors the league level, which the raw fit leaves free
    raw, _, _ = fit_dixon_coles(rows, codes, GW, shrinkage=0.01, promoted_prior=(0.0, 0.0))
    shrunk, _, _ = fit_dixon_coles(rows, codes, GW, shrinkage=8.0, promoted_prior=(0.0, 0.0))
    assert raw[99]['attack'] > 0.5
    assert abs(shrunk[99]['attack']) < abs(raw[99]['attack']) * 0.6


def test_team_with_plenty_of_data_barely_moves():
    rows = league_rows(20)  # 200 games each, plenty
    codes = LEAGUE
    raw, _, _ = fit_dixon_coles(rows, codes, GW, shrinkage=0.01)
    shrunk, _, _ = fit_dixon_coles(rows, codes, GW, shrinkage=8.0)
    for c in codes:
        assert abs(raw[c]['attack'] - shrunk[c]['attack']) < 0.02
        assert abs(raw[c]['defence'] - shrunk[c]['defence']) < 0.02


def test_prior_switches_at_established_games():
    def rows_for(n_games_team_99):
        rows = []
        for k in range(n_games_team_99):
            rows.append({'code_h': 99, 'code_a': 1, 'goals_h': 1, 'goals_a': 1, 'unified_gw': GW})
        return rows
    for n, expect_promoted in ((ESTABLISHED_GAMES - 1, True), (ESTABLISHED_GAMES, False)):
        rows = rows_for(n)
        att, dfn = team_priors(rows, [1, 99], promoted_prior=(-0.3, 0.4))
        # code 1 plays the same number of games as 99, so both flip together
        want = (-0.3, 0.4) if expect_promoted else (0.0, 0.0)
        assert (att[1], dfn[1]) == want


def test_shipped_constants_are_sane():
    assert SHRINKAGE > 0
    assert ESTABLISHED_GAMES == 38
    assert PROMOTED_PRIOR[0] < 0 < PROMOTED_PRIOR[1]


def test_penalty_does_not_drag_league_scoring_level_towards_one_goal():
    # A high-scoring league (2 goals a side on average) must still be predicted at ~2 a side
    # under heavy shrinkage: the league level belongs to an unpenalised intercept.
    rows = league_rows(4)
    for r in rows:
        r['goals_h'] += 1
        r['goals_a'] += 1
    ratings, home_adv, _ = fit_dixon_coles(rows, LEAGUE, GW, shrinkage=8.0)
    away_pred = np.mean([np.exp(ratings[r['code_a']]['attack'] + ratings[r['code_h']]['defence']) for r in rows])
    away_obs = np.mean([r['goals_a'] for r in rows])
    assert abs(away_pred - away_obs) / away_obs < 0.03
