import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import logging

from FPL_site.matchPredictionEngine import build_rating_dataset


def roster(n_rows, n_ids, code_base):
    return [{'id': (i % n_ids) + 1, 'code': code_base + i, 'name': f'T{i}', 'short_name': f'T{i}'}
            for i in range(n_rows)]


class FakeCursor:
    """Seasons 2023 and 2025 have clean rosters; 2024 has 23 rows for 20 ids."""
    def __init__(self):
        self.year = None
        self.sql = ''

    def execute(self, sql, params=None):
        self.sql, self.year = sql, params[0] if params else None

    def fetchall(self):
        if 'bootstrapstatic_elements' in self.sql:
            return []          # no snapshots: exercises the teams-table fallback
        if 'bootstrapstatic_teams' in self.sql:
            if self.year == 2024:
                return roster(23, 20, 500)
            if self.year in (2023, 2025):
                return roster(20, 20, 100)
            return []
        # one finished fixture per season between team ids 1 and 2
        return [{'event': 1, 'team_h': 1, 'team_a': 2, 'team_h_score': 1, 'team_a_score': 0,
                 'kickoff_time': f'{self.year}-09-01T14:00:00Z'}]


def test_season_with_a_corrupt_roster_is_skipped_and_logged(caplog):
    with caplog.at_level(logging.WARNING):
        rows, codes, _, _ = build_rating_dataset(FakeCursor(), 2025, 5)
    assert len(rows) == 2              # 2023 and 2025 only; 2024 dropped
    assert not any(c >= 500 for c in codes)
    assert any('2024' in m and 'roster' in m for m in caplog.messages)
