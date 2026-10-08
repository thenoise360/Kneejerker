import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime

from FPL_site import expectedPointsRecord as rec
from FPL_site.expectedPointsFeatures import MODEL_VERSION


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, rows):
        self.calls.append((sql, list(rows)))


class FakeConn:
    def __init__(self):
        self.cur, self.commits = FakeCursor(), 0

    def cursor(self, **k):
        return self.cur

    def commit(self):
        self.commits += 1

EVENTS = [{'id': 5, 'deadline_time': '2026-10-03T10:00:00Z', 'finished': True, 'data_checked': True},
          {'id': 6, 'deadline_time': '2026-10-10T10:00:00Z', 'finished': False, 'data_checked': False},
          {'id': 7, 'deadline_time': 'bad', 'finished': False, 'data_checked': False}]


def test_deadlines_and_the_next_gameweek_come_from_the_events():
    assert rec.deadline_for(EVENTS, 6) == datetime(2026, 10, 10, 10, 0)
    assert rec.deadline_for(EVENTS, 7) is None
    assert rec.next_gameweek(EVENTS, datetime(2026, 10, 8)) == 6
    assert rec.next_gameweek(EVENTS, datetime(2026, 10, 11)) is None
    assert rec.is_settled(EVENTS, 5) is True


def test_the_log_is_append_only_and_idempotent_per_day():
    conn = FakeConn()
    rec.log_forecasts(conn, [{'player_id': 1, 'code': 101, 'expected_points': 3.0,
                              'official_expected_points': 2.5}], 2026, 6,
                      datetime(2026, 10, 10, 10), datetime(2026, 10, 8, 6))
    create_sql = conn.cur.calls[0][0]
    insert_sql, records = conn.cur.calls[1]
    assert 'PRIMARY KEY (year_start, player_id, gameweek, model_version, source, log_date)' in create_sql
    assert insert_sql.strip().startswith(f'INSERT IGNORE INTO {rec.LOG_TABLE}')
    assert records[0][-4:] == (MODEL_VERSION, rec.LIVE, datetime(2026, 10, 8, 6), datetime(2026, 10, 8).date())
    assert conn.commits == 1


def test_template_squad_takes_the_most_selected_by_position():
    rows = ([{'player_id': i, 'position': 1, 'selected': 100 - i} for i in range(1, 5)] +
            [{'player_id': 10 + i, 'position': 2, 'selected': 100 - i} for i in range(1, 8)] +
            [{'player_id': 20 + i, 'position': 3, 'selected': 100 - i} for i in range(1, 8)] +
            [{'player_id': 30 + i, 'position': 4, 'selected': 100 - i} for i in range(1, 5)])
    squad = rec.template_squad(rows)
    assert len(squad) == 15
    assert {1, 2} <= set(squad) and 3 not in squad
    assert {31, 32, 33} <= set(squad) and 34 not in squad


def test_captain_pick_ignores_players_without_a_match_and_breaks_ties_by_id():
    assert rec.captain_pick([1, 2, 3], {1: 9.0, 2: 6.0, 3: 6.0}, playing={2, 3}) == 2
    assert rec.captain_pick([1], {1: 9.0}, playing=set()) is None


def test_accuracy_counts_captain_outcomes_and_per_position_errors():
    record = {1: {'player_id': 1, 'position': 4, 'expected_points': 7.0, 'official_expected_points': 4.0},
              2: {'player_id': 2, 'position': 3, 'expected_points': 3.0, 'official_expected_points': 8.0}}
    result = rec.accuracy_for_gameweek(record, {1: 12, 2: 2}, [1, 2], {1, 2})
    assert result['captain_ours'] == 1 and result['captain_official'] == 2
    assert result['captain_ours_points'] == 12 and result['captain_official_points'] == 2
    assert result['mae_by_position'][4] == {'ours': 5.0, 'official': 8.0, 'players': 1}
    assert result['players'] == 2


def test_players_without_an_actual_score_are_left_out_of_the_accuracy():
    record = {1: {'player_id': 1, 'position': 4, 'expected_points': 7.0, 'official_expected_points': 4.0},
              2: {'player_id': 2, 'position': 4, 'expected_points': 3.0, 'official_expected_points': None}}
    result = rec.accuracy_for_gameweek(record, {1: 5}, [1, 2], {1})
    assert result['players'] == 1


def test_mean_absolute_error_is_rounded_and_none_when_empty():
    assert rec.mean_absolute_error([(1.0, 2.0), (3.0, 3.5)]) == 0.75
    assert rec.mean_absolute_error([]) is None


def test_accuracy_rows_replace_rather_than_duplicate():
    conn = FakeConn()
    rec.persist_accuracy(conn, 6, 2026, {'players': 1, 'mae_ours': 1.0, 'mae_official': 2.0,
                                         'mae_by_position': {}, 'captain_ours': 1, 'captain_official': 2,
                                         'captain_ours_points': 5, 'captain_official_points': 3},
                         datetime(2026, 10, 12))
    assert conn.cur.calls[1][0].strip().startswith(f'REPLACE INTO {rec.ACCURACY_TABLE}')


def test_every_logged_row_carries_its_season_and_source():
    conn = FakeConn()
    rec.log_forecasts(conn, [{'player_id': 1, 'code': 101, 'expected_points': 3.0,
                              'official_expected_points': 2.5}], 2026, 6,
                      datetime(2026, 10, 10, 10), datetime(2026, 10, 8, 6))
    create_sql = conn.cur.calls[0][0]
    insert_sql, records = conn.cur.calls[1]
    assert 'PRIMARY KEY (year_start, player_id, gameweek, model_version, source, log_date)' in create_sql
    assert records[0][0] == 2026
    assert records[0][7] == rec.LIVE


def test_a_backfill_is_logged_after_the_deadline_but_a_live_forecast_is_not():
    late = datetime(2026, 10, 11)
    row = [{'player_id': 1, 'code': 101, 'expected_points': 3.0, 'official_expected_points': None}]
    assert rec.log_forecasts(FakeConn(), row, 2025, 6, datetime(2026, 10, 10), late) == 0
    conn = FakeConn()
    assert rec.log_forecasts(conn, row, 2025, 6, None, late, source=rec.BACKFILL) == 1
    assert conn.cur.calls[1][1][0][7] == rec.BACKFILL


def test_nan_forecasts_are_never_written():
    conn = FakeConn()
    rows = [{'player_id': 1, 'code': 101, 'expected_points': float('nan'), 'official_expected_points': 2.0},
            {'player_id': 2, 'code': 102, 'expected_points': 4.0, 'official_expected_points': 2.0}]
    assert rec.log_forecasts(conn, rows, 2026, 6, datetime(2026, 10, 10), datetime(2026, 10, 8)) == 1


def test_the_backfill_record_ignores_the_deadline():
    rows = [{'player_id': 1, 'expected_points': 4.0, 'logged_at': datetime(2026, 10, 9)}]
    assert rec.forecast_of_record(rows, None, source=rec.BACKFILL)[1]['expected_points'] == 4.0


def test_current_forecasts_and_accuracy_are_keyed_by_season():
    conn = FakeConn()
    rec.persist_current(conn, [{'player_id': 1, 'code': 101, 'gameweek': 6, 'expected_points': 3.0}],
                        2026, datetime(2026, 10, 8))
    assert 'PRIMARY KEY (year_start, player_id, gameweek)' in conn.cur.calls[0][0]
    assert conn.cur.calls[1][1][0][0] == 2026
    conn = FakeConn()
    rec.persist_accuracy(conn, 6, 2025, {'players': 1, 'mae_ours': 1.0, 'mae_official': 2.0,
                                         'mae_by_position': {}, 'captain_ours': 1, 'captain_official': 2,
                                         'captain_ours_points': 5, 'captain_official_points': 3},
                         datetime(2026, 10, 12), source=rec.BACKFILL)
    assert 'PRIMARY KEY (year_start, gameweek, model_version, source)' in conn.cur.calls[0][0]
    assert rec.BACKFILL in conn.cur.calls[1][1]


def test_only_a_backfill_is_exempt_from_the_deadline():
    late = datetime(2026, 10, 11)
    row = [{'player_id': 1, 'code': 101, 'expected_points': 3.0, 'official_expected_points': None}]
    assert rec.log_forecasts(FakeConn(), row, 2025, 6, datetime(2026, 10, 10), late, source='replay') == 0
    assert rec.log_forecasts(FakeConn(), row, 2025, 6, None, late, source='replay') == 0


def test_forecasts_with_no_value_are_never_written():
    rows = [{'player_id': 1, 'code': 101, 'expected_points': None, 'official_expected_points': 2.0},
            {'player_id': 2, 'code': 102, 'expected_points': 4.0, 'official_expected_points': 2.0}]
    assert rec.log_forecasts(FakeConn(), rows, 2026, 6, datetime(2026, 10, 10), datetime(2026, 10, 8)) == 1
