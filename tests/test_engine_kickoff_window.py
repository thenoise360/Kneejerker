import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import logging

from FPL_site.matchPredictionEngine import build_rating_dataset, kickoff_in_season_window


def test_window_boundaries_are_the_first_of_july():
    assert kickoff_in_season_window('2024-07-01T00:00:00Z', 2024)
    assert not kickoff_in_season_window('2024-06-30T23:59:59Z', 2024)
    assert kickoff_in_season_window('2025-06-30T23:59:59Z', 2024)
    assert not kickoff_in_season_window('2025-07-01T00:00:00Z', 2024)


def test_in_window_and_out_of_window():
    assert kickoff_in_season_window('2024-08-16T19:00:00Z', 2024)
    assert kickoff_in_season_window('2025-05-25T15:00:00Z', 2024)
    assert not kickoff_in_season_window('2025-08-15T19:00:00Z', 2024)


def test_missing_or_unparseable_kickoffs_are_out_of_window():
    for bad in (None, '', '0', 'garbage', 20240816, '2024-13-45T00:00:00Z'):
        assert not kickoff_in_season_window(bad, 2024)


class Cursor:
    def __init__(self, fixtures):
        self.fixtures, self.sql = fixtures, ''

    def execute(self, sql, params=None):
        self.sql = sql

    def fetchall(self):
        if 'bootstrapstatic_elements' in self.sql:
            return [{'team': i, 'team_code': 100 + i, 'gws': 38, 'last_gw': 38}
                    for i in range(1, 21)]
        return self.fixtures


def fx(kickoff, h=1, a=2):
    return {'event': 1, 'team_h': h, 'team_a': a, 'team_h_score': 1, 'team_a_score': 0,
            'kickoff_time': kickoff}


def test_build_rating_dataset_drops_strays_and_logs_the_count(caplog):
    cur = Cursor([fx('2024-08-16T19:00:00Z'), fx('2025-08-15T19:00:00Z'),
                  fx('0'), fx(None)])
    with caplog.at_level(logging.WARNING):
        rows, _, _, _ = build_rating_dataset(cur, 2024, 5)
    assert len(rows) == 1
    assert any('2024' in m and '3' in m and 'kickoff' in m for m in caplog.messages)
