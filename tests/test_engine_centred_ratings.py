import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import numpy as np

from FPL_site.matchPredictionEngine import build_fixture_predictions


class FakeCursor:
    def __init__(self, teams, fixtures):
        self.teams, self.fixtures, self._result = teams, fixtures, []

    def execute(self, sql, params=None):
        self._result = self.teams if 'bootstrapstatic_teams' in sql else self.fixtures

    def fetchall(self):
        return self._result


TEAMS = [{'id': i, 'code': 100 + i, 'name': f'T{i}', 'short_name': f'T{i}'} for i in (1, 2, 3, 4)]
RATINGS = {101: {'attack': 0.50, 'defence': 0.30}, 102: {'attack': 0.40, 'defence': 0.10},
           103: {'attack': 0.20, 'defence': 0.20}, 104: {'attack': 0.10, 'defence': 0.40}}
FIXTURES = [{'code': 1, 'event': 6, 'team_h': 1, 'team_a': 2, 'kickoff_time': None},
            {'code': 2, 'event': 6, 'team_h': 3, 'team_a': 4, 'kickoff_time': None}]


def build():
    return build_fixture_predictions(FakeCursor(TEAMS, FIXTURES), 2026, 5, RATINGS, 0.2, {})


def test_persisted_ratings_are_centred_on_the_league_average():
    rows = build()
    per_team = {r['team_id']: r for r in rows}
    assert len(per_team) == 4
    assert abs(np.mean([r['attack_rating'] for r in per_team.values()])) < 1e-9
    assert abs(np.mean([r['defence_rating'] for r in per_team.values()])) < 1e-9


def test_centring_does_not_change_expected_goals():
    first = build()[0]
    assert first['expected_goals_mean'] > 0
    # (home) team 1 vs team 2: exp(0.50 + 0.10 + 0.2) = 2.23 before any range adjustment
    assert abs(first['expected_goals_mean'] - np.exp(0.80)) < 0.5
