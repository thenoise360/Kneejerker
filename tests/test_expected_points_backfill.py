import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import expectedPointsBackfill as bf
from FPL_site import expectedPointsBacktest as bt


def test_targets_start_at_the_chosen_gameweek_and_skip_unsettled_ones():
    rows = [{'year_start': y, 'gameweek': g} for y in (2024, 2025) for g in (1, 5, 6, 38)]
    settled = lambda y, g: not (y == 2025 and g == 38)
    assert bf.replay_targets(rows, 2024, 6, settled) == [(2024, 6), (2024, 38), (2025, 1), (2025, 5), (2025, 6)]


def test_walk_forward_can_keep_players_without_an_official_number(monkeypatch):
    monkeypatch.setattr(bt, 'train', lambda rows: {})
    monkeypatch.setattr(bt, 'predict', lambda models, rows: [1.0] * len(rows))
    rows = [{'year_start': 2025, 'gameweek': g, 'player_id': 1, 'code': 9, 'position': 3, 'target': 2}
            for g in (1, 2)]
    kept = bt.walk_forward(rows, {}, [(2025, 2)], require_official=False)
    assert kept == [{'year_start': 2025, 'gameweek': 2, 'player_id': 1, 'code': 9, 'position': 3,
                     'ours': 1.0, 'official': None, 'actual': 2}]
    assert bt.walk_forward(rows, {}, [(2025, 2)]) == []


class Missing:
    def execute(self, sql, params=None):
        raise RuntimeError("Table 'expected_points_log' doesn't exist")


def test_nothing_backfilled_yet_when_the_log_table_is_missing():
    assert bf.fetch_backfilled(Missing()) == set()
