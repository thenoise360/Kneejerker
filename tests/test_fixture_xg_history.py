import math
import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import fixtureXgHistory as fx

RATINGS = {10: {'attack': 0.5, 'defence': -0.2}, 20: {'attack': 0.1, 'defence': 0.1},
           30: {'attack': 0.0, 'defence': 0.0}}
ID_TO_CODE = {1: 10, 2: 20, 3: 30}


def test_a_single_match_gives_both_sides_their_expected_goals():
    out = fx.team_gameweek_xg([{'team_h': 1, 'team_a': 2}], RATINGS, 0.2, ID_TO_CODE)
    home = math.exp(0.5 + 0.1 + 0.2)
    away = math.exp(0.1 - 0.2)
    assert out[10] == {'team_xg': round(home, 3), 'opp_xg': round(away, 3), 'matches': 1, 'home_share': 1.0}
    assert out[20] == {'team_xg': round(away, 3), 'opp_xg': round(home, 3), 'matches': 1, 'home_share': 0.0}


def test_a_double_gameweek_adds_both_matches():
    out = fx.team_gameweek_xg([{'team_h': 1, 'team_a': 2}, {'team_h': 3, 'team_a': 1}],
                              RATINGS, 0.0, ID_TO_CODE)
    assert out[10]['matches'] == 2
    assert out[10]['home_share'] == 0.5
    expected = round(math.exp(0.5 + 0.1), 3) + round(math.exp(0.5 + 0.0), 3)
    assert math.isclose(out[10]['team_xg'], expected, abs_tol=0.002)


def test_a_team_missing_from_the_code_map_is_skipped():
    out = fx.team_gameweek_xg([{'team_h': 1, 'team_a': 99}], RATINGS, 0.0, ID_TO_CODE)
    assert out == {}


def test_fit_as_of_only_uses_fixtures_before_the_gameweek(monkeypatch):
    seen = {}

    def dataset(cursor, season, current_gw, current_season_max_event=None):
        seen['args'] = (season, current_gw, current_season_max_event)
        return [], [10, 20], 0, current_gw

    monkeypatch.setattr(fx, 'build_rating_dataset', dataset)
    monkeypatch.setattr(fx, 'fit_dixon_coles', lambda rows, codes, ref: (RATINGS, 0.0, 0.0))
    monkeypatch.setattr(fx, 'fetch_team_code_map', lambda cursor, year: ID_TO_CODE)
    monkeypatch.setattr(fx, 'fetch_gameweek_fixtures', lambda cursor, year, gw: [{'team_h': 1, 'team_a': 2}])
    out = fx.fit_as_of(object(), 2025, 7)
    assert seen['args'] == (2025, 6, 7)
    assert set(out) == {10, 20}


class RowsCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self.rows


def test_another_seasons_matches_stored_under_this_season_are_ignored():
    rows = [{'id': 51, 'team_h': 1, 'team_a': 2, 'kickoff_time': '2025-09-27T14:00:00Z'},
            {'id': 51, 'team_h': 3, 'team_a': 4, 'kickoff_time': '2026-09-26T14:00:00Z'}]
    assert fx.fetch_gameweek_fixtures(RowsCursor(rows), 2025, 6) == [rows[0]]


class FakeCursor:
    def __init__(self, stored):
        self.stored, self.calls = stored, []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, rows):
        self.calls.append((sql, list(rows)))

    def fetchall(self):
        return self.stored


class FakeConn:
    def __init__(self, cursor):
        self.cur, self.commits = cursor, 0

    def cursor(self, **k):
        return self.cur

    def commit(self):
        self.commits += 1


def test_fill_missing_only_fits_gameweeks_not_already_stored(monkeypatch):
    cursor = FakeCursor(stored=[{'year_start': 2025, 'gameweek': 6}])
    fitted = []
    monkeypatch.setattr(fx, 'fit_as_of', lambda c, y, g: fitted.append((y, g)) or
                        {10: {'team_xg': 1.0, 'opp_xg': 1.0, 'matches': 1, 'home_share': 1.0}})
    added = fx.fill_missing(FakeConn(cursor), cursor, [(2025, 6), (2025, 7)])
    assert fitted == [(2025, 7)]
    assert added == 1


def test_one_gameweek_failing_does_not_stop_the_later_ones(monkeypatch):
    cursor = FakeCursor(stored=[])
    conn = FakeConn(cursor)
    conn.rollbacks = 0
    conn.rollback = lambda: setattr(conn, 'rollbacks', conn.rollbacks + 1)

    def fit(c, y, g):
        if g == 1:
            raise RuntimeError('refit failed')
        return {10: {'team_xg': 1.0, 'opp_xg': 1.0, 'matches': 1, 'home_share': 1.0}}

    monkeypatch.setattr(fx, 'fit_as_of', fit)
    assert fx.fill_missing(conn, cursor, [(2025, 1), (2025, 2)]) == 1
    inserts = [c for c in cursor.calls if isinstance(c[1], list) and c[1]]
    assert [rows[0][1] for _, rows in inserts] == [2]
    assert conn.rollbacks == 1


def test_a_gameweek_that_fits_no_teams_is_not_counted_as_added(monkeypatch):
    cursor = FakeCursor(stored=[])
    conn = FakeConn(cursor)
    monkeypatch.setattr(fx, 'fit_as_of', lambda c, y, g: {})
    assert fx.fill_missing(conn, cursor, [(2025, 1)]) == 0
    assert conn.commits == 0
