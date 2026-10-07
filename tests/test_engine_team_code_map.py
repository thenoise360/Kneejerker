import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import logging

from FPL_site.matchPredictionEngine import build_rating_dataset, fetch_team_code_map

# Real 2024-25 numbering (id -> code), as read from the player snapshots.
TRUE_2024 = {1: 3, 2: 7, 3: 91, 4: 94, 5: 36, 6: 8, 7: 31, 8: 11, 9: 54, 10: 40,
             11: 13, 12: 14, 13: 43, 14: 1, 15: 4, 16: 17, 17: 20, 18: 6, 19: 21, 20: 39}
# The 2025-26 numbering that overwrote the 2024 gameweek-1 snapshot.
BAD_GW1 = dict(TRUE_2024)
BAD_GW1[3], BAD_GW1[4] = 90, 91


def snapshot_rows(per_gw):
    """per_gw: {gameweek: {team_id: code}} -> grouped rows as the SQL would return them."""
    seen = {}
    for gw, mapping in per_gw.items():
        for tid, code in mapping.items():
            entry = seen.setdefault((tid, code), {'team': tid, 'team_code': code,
                                                  'gws': 0, 'last_gw': 0})
            entry['gws'] += 1
            entry['last_gw'] = max(entry['last_gw'], gw)
    return list(seen.values())


class SnapshotCursor:
    """Serves grouped bootstrapstatic_elements rows and, optionally, a teams table."""
    def __init__(self, snapshots=None, teams=None, fixtures=None):
        self.snapshots = snapshots or {}
        self.teams = teams or {}
        self.fixtures = fixtures or {}
        self.year, self.sql = None, ''

    def execute(self, sql, params=None):
        self.sql, self.year = sql, params[0] if params else None

    def fetchall(self):
        if 'bootstrapstatic_elements' in self.sql:
            return self.snapshots.get(self.year, [])
        if 'bootstrapstatic_teams' in self.sql:
            return self.teams.get(self.year, [])
        return self.fixtures.get(self.year, [])


def test_one_bad_gameweek_among_many_good_ones_gives_the_true_map():
    per_gw = {gw: TRUE_2024 for gw in range(2, 39)}
    per_gw[1] = BAD_GW1
    cur = SnapshotCursor(snapshots={2024: snapshot_rows(per_gw)})
    assert fetch_team_code_map(cur, 2024) == TRUE_2024


def test_a_tie_goes_to_the_code_seen_in_the_latest_gameweek():
    per_gw = {1: {1: 10}, 2: {1: 10}, 3: {1: 20}, 4: {1: 20}}
    cur = SnapshotCursor(snapshots={2024: snapshot_rows(per_gw)})
    assert fetch_team_code_map(cur, 2024) == {1: 20}


def test_no_snapshot_rows_gives_an_empty_map():
    assert fetch_team_code_map(SnapshotCursor(), 2024) == {}


def roster(code_base=100, n=20):
    return [{'id': i + 1, 'code': code_base + i, 'name': f'T{i}', 'short_name': f'T{i}'}
            for i in range(n)]


def one_fixture():
    return [{'event': 1, 'team_h': 1, 'team_a': 3, 'team_h_score': 2, 'team_a_score': 1,
             'kickoff_time': '2024-09-01T14:00:00Z'}]


def test_build_rating_dataset_credits_fixtures_via_the_snapshot_map():
    per_gw = {gw: TRUE_2024 for gw in range(2, 39)}
    per_gw[1] = BAD_GW1
    cur = SnapshotCursor(
        snapshots={2024: snapshot_rows(per_gw)},
        teams={2024: [{'id': i, 'code': 900 + i, 'name': 'x', 'short_name': 'x'}
                      for i in range(1, 24)]},   # corrupt table must be ignored
        fixtures={2024: one_fixture()})
    rows, codes, _, _ = build_rating_dataset(cur, 2024, 5)
    assert [(r['code_h'], r['code_a']) for r in rows] == [(3, 91)]   # Arsenal v Bournemouth


def test_falls_back_to_the_teams_table_only_when_there_are_no_snapshots():
    cur = SnapshotCursor(teams={2024: roster()}, fixtures={2024: one_fixture()})
    rows, _, _, _ = build_rating_dataset(cur, 2024, 5)
    assert [(r['code_h'], r['code_a']) for r in rows] == [(100, 102)]


def test_guard_skips_a_map_with_fewer_than_twenty_ids(caplog):
    per_gw = {gw: {i: 100 + i for i in range(1, 20)} for gw in range(1, 5)}   # 19 ids
    cur = SnapshotCursor(snapshots={2024: snapshot_rows(per_gw)},
                         fixtures={2024: one_fixture()})
    with caplog.at_level(logging.WARNING):
        rows, _, _, _ = build_rating_dataset(cur, 2024, 5)
    assert rows == []
    assert any('2024' in m and 'roster' in m for m in caplog.messages)


def test_guard_skips_a_map_where_two_ids_share_a_code(caplog):
    mapping = {i: 100 + i for i in range(1, 21)}
    mapping[20] = 101                                   # duplicate code
    cur = SnapshotCursor(snapshots={2024: snapshot_rows({1: mapping, 2: mapping})},
                         fixtures={2024: one_fixture()})
    with caplog.at_level(logging.WARNING):
        rows, _, _, _ = build_rating_dataset(cur, 2024, 5)
    assert rows == []
    assert any('2024' in m and 'roster' in m for m in caplog.messages)


def test_a_full_tie_is_broken_deterministically_by_the_larger_code():
    for rows in ([{'team': 1, 'team_code': 10, 'gws': 2, 'last_gw': 5},
                  {'team': 1, 'team_code': 20, 'gws': 2, 'last_gw': 5}],
                 [{'team': 1, 'team_code': 20, 'gws': 2, 'last_gw': 5},
                  {'team': 1, 'team_code': 10, 'gws': 2, 'last_gw': 5}]):
        class C(SnapshotCursor):
            def fetchall(self):
                return rows
        assert fetch_team_code_map(C(), 2024) == {1: 20}
