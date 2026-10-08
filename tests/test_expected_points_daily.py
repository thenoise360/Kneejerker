import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime

from FPL_site import expectedPointsModel as em


class Conn:
    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def cursor(self, **k):
        return object()

    def commit(self):
        pass

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


EVENTS = [{'id': 5, 'deadline_time': '2026-10-03T10:00:00Z', 'finished': True, 'data_checked': True},
          {'id': 6, 'deadline_time': '2026-10-10T10:00:00Z', 'finished': False, 'data_checked': False}]


def patch_job(monkeypatch, calls, now_events=EVENTS):
    monkeypatch.setattr(em, 'refresh_season_start', lambda: 2026)
    monkeypatch.setattr(em, 'current_season_start', lambda: 2026)
    monkeypatch.setattr(em, 'connect_db', lambda: Conn())
    monkeypatch.setattr(em, 'fetch_events', lambda: now_events)
    monkeypatch.setattr(em, 'fetch_history_rows', lambda c, y: [])
    monkeypatch.setattr(em, 'fetch_snapshot_rows', lambda c, y: [
        {'code': 1, 'player_id': 7, 'year_start': 2026, 'gameweek': 5, 'element_type': 3, 'team_code': 3,
         'now_cost': 60, 'chance_of_playing_next_round': None, 'ep_next': 4.5,
         'expected_goals': 0.0, 'expected_assists': 0.0}])
    monkeypatch.setattr(em, 'fill_missing', lambda conn, cur, wanted: calls.setdefault('wanted', wanted) and 0)
    monkeypatch.setattr(em, 'load_fixture_xg', lambda cur: {})
    monkeypatch.setattr(em, 'fetch_team_code_map', lambda cur, y: {})
    monkeypatch.setattr(em, 'fetch_live_fixture_xg', lambda cur, y, gw, m: {
        (2026, 6, 3): {'team_xg': 1.5, 'opp_xg': 1.0, 'matches': 1, 'home_share': 1.0}})
    monkeypatch.setattr(em, 'fetch_clubs_with_fixture', lambda cur, y, gw, m: {3})
    monkeypatch.setattr(em, 'train', lambda rows: {})
    monkeypatch.setattr(em, 'predict', lambda models, rows: [3.2 for _ in rows])
    monkeypatch.setattr(em, 'persist_current', lambda conn, rows, year, now: calls.setdefault('current', rows))
    monkeypatch.setattr(em, 'log_forecasts', lambda conn, rows, year, gw, deadline, now:
                        calls.setdefault('log', (rows, gw, deadline)) and len(rows))
    monkeypatch.setattr(em, 'record_settled_gameweeks', lambda conn, cur, events, year, now:
                        calls.setdefault('settled', True))


def test_the_daily_job_forecasts_the_next_gameweek_and_logs_it_with_the_official_number(monkeypatch):
    calls = {}
    patch_job(monkeypatch, calls)
    em.run_daily_expected_points(now=datetime(2026, 10, 8, 6))
    rows, gw, deadline = calls['log']
    assert gw == 6 and deadline == datetime(2026, 10, 10, 10)
    assert rows[0] == {'player_id': 7, 'code': 1, 'gameweek': 6, 'expected_points': 3.2,
                       'official_expected_points': 4.5}
    assert calls['current'][0]['expected_points'] == 3.2
    assert calls['settled'] is True


def test_no_upcoming_gameweek_means_no_forecasts(monkeypatch):
    calls = {}
    patch_job(monkeypatch, calls)
    em.run_daily_expected_points(now=datetime(2026, 10, 11, 6))
    assert 'log' not in calls and 'current' not in calls


def test_the_official_api_being_down_stops_the_job_quietly(monkeypatch):
    calls = {}
    patch_job(monkeypatch, calls, now_events=None)
    em.run_daily_expected_points(now=datetime(2026, 10, 8, 6))
    assert calls == {}


def test_a_failed_historical_refit_does_not_stop_the_weeks_forecast(monkeypatch):
    calls = {}
    patch_job(monkeypatch, calls)
    conns = []

    def connect():
        conns.append(Conn())
        return conns[-1]

    def broken_fill(conn, cursor, wanted):
        raise RuntimeError('refit failed')

    monkeypatch.setattr(em, 'connect_db', connect)
    monkeypatch.setattr(em, 'fill_missing', broken_fill)
    em.run_daily_expected_points(now=datetime(2026, 10, 8, 6))
    assert calls['current'][0]['expected_points'] == 3.2
    assert calls['log'][1] == 6
    assert conns[0].rolled_back and conns[0].closed


def test_run_update_runs_our_model_instead_of_the_old_one():
    src = open(os.path.join(os.path.dirname(em.__file__), 'run_update.py'), encoding='utf-8').read()
    assert 'run_daily_expected_points' in src
    assert 'run_daily_predictions,' not in src and 'import run_daily_predictions' not in src


def test_a_stale_snapshot_is_never_logged_as_the_forecast_of_record(monkeypatch):
    calls = {}
    patch_job(monkeypatch, calls)
    monkeypatch.setattr(em, 'fetch_snapshot_rows', lambda c, y: [
        {'code': 1, 'player_id': 7, 'year_start': 2026, 'gameweek': 4, 'element_type': 3, 'team_code': 3,
         'now_cost': 60, 'chance_of_playing_next_round': None, 'ep_next': 4.5,
         'expected_goals': 0.0, 'expected_assists': 0.0}])
    em.run_daily_expected_points(now=datetime(2026, 10, 8, 6))
    assert 'log' not in calls and 'current' not in calls
    assert calls['settled'] is True


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        self.sql = sql

    def fetchall(self):
        return self.rows


def test_actual_points_ignore_duplicates_and_other_seasons_matches():
    rows = [{'element': 7, 'fixture': 1, 'round': 5, 'kickoff_time': '2026-10-03T14:00:00Z', 'total_points': 6},
            {'element': 7, 'fixture': 2, 'round': 5, 'kickoff_time': '2026-10-04T14:00:00Z', 'total_points': 2},
            {'element': 8, 'fixture': 3, 'round': 5, 'kickoff_time': '2025-10-04T14:00:00Z', 'total_points': 9}]
    cur = FakeCursor(rows)
    assert em.fetch_actual_points(cur, 2026, 5) == {7: 8}
    assert 'DISTINCT' in cur.sql


def test_history_rows_outside_the_season_window_are_dropped(monkeypatch):
    monkeypatch.setattr(em, 'fetch_team_code_map', lambda c, y: {1: 10, 2: 20})
    base = {'year_start': 2026, 'element': 7, 'round': 5, 'fixture': 1, 'opponent_team': 2, 'was_home': 1,
            'minutes': 90, 'goals_scored': 0, 'assists': 0, 'clean_sheets': 0, 'bonus': 0,
            'total_points': 2, 'team_id': 1}

    class Cur(FakeCursor):
        def fetchall(self):
            if 'bootstrapstatic_elements' in self.sql:
                return [{'year_start': 2026, 'id': 7, 'code': 70}]
            return [dict(base, kickoff_time='2026-10-03T14:00:00Z'),
                    dict(base, fixture=2, kickoff_time='2025-10-03T14:00:00Z')]

    out = em.fetch_history_rows(Cur([]), [2026])
    assert len(out) == 1 and out[0]['code'] == 70


def test_reading_the_log_filters_by_season_and_source():
    seen = []

    class Cur:
        def execute(self, sql, params=None):
            seen.append((sql, params))

        def fetchall(self):
            return []

    em.fetch_log_rows(Cur(), 2026, 6)
    sql, params = seen[0]
    assert 'year_start = %s' in sql and 'source = %s' in sql
    assert params == (2026, 6, em.MODEL_VERSION, 'live')


class StubModel:
    def predict(self, matrix):
        return [3.24] * len(matrix)


def snapshot(pid, code, team_code):
    return {'code': code, 'player_id': pid, 'year_start': 2026, 'gameweek': 5, 'element_type': 3,
            'team_code': team_code, 'now_cost': 60, 'chance_of_playing_next_round': None, 'ep_next': 4.5,
            'expected_goals': 0.0, 'expected_assists': 0.0}


real_prediction_rows, real_predict = em.prediction_rows, em.predict


def use_real_prediction(monkeypatch, calls, clubs_with_fixture):
    """The real prediction_rows and predict; only the database reads are faked."""
    patch_job(monkeypatch, calls)
    monkeypatch.setattr(em, 'prediction_rows', real_prediction_rows)
    monkeypatch.setattr(em, 'predict', real_predict)
    monkeypatch.setattr(em, 'train', lambda rows: {3: StubModel()})
    monkeypatch.setattr(em, 'fetch_clubs_with_fixture', lambda cur, y, gw, m: clubs_with_fixture)
    monkeypatch.setattr(em, 'fetch_snapshot_rows', lambda c, y: [
        snapshot(7, 1, 3), snapshot(8, 2, 4), snapshot(9, 3, 5)])


def test_no_stored_fixture_predictions_means_nothing_is_forecast_or_logged(monkeypatch):
    calls = {}
    use_real_prediction(monkeypatch, calls, {3, 4, 5})
    monkeypatch.setattr(em, 'fetch_live_fixture_xg', lambda cur, y, gw, m: {})
    em.run_daily_expected_points(now=datetime(2026, 10, 8, 6))
    assert 'log' not in calls and 'current' not in calls
    assert calls['settled'] is True


def test_a_club_with_no_match_is_a_real_blank_but_a_match_without_numbers_is_not_logged(monkeypatch):
    calls = {}
    # club 3 has numbers, club 4 has a match but no numbers, club 5 has no match this gameweek
    use_real_prediction(monkeypatch, calls, {3, 4})
    em.run_daily_expected_points(now=datetime(2026, 10, 8, 6))
    logged = {r['player_id']: r['expected_points'] for r in calls['log'][0]}
    assert logged == {7: 3.2, 9: 0.0}
    assert 8 not in {r['player_id'] for r in calls['current']}


def test_training_ignores_gameweeks_still_being_played(monkeypatch):
    calls = {}
    patch_job(monkeypatch, calls)

    def hist(year, gw):
        return {'code': 1, 'year_start': year, 'gameweek': gw, 'team_code': 3, 'minutes': 90, 'total_points': 2,
                'goals_scored': 0, 'assists': 0, 'clean_sheets': 0, 'bonus': 0}

    monkeypatch.setattr(em, 'fetch_history_rows', lambda c, y: [hist(2025, 38), hist(2026, 5), hist(2026, 6)])
    monkeypatch.setattr(em, 'training_rows', lambda history, snaps, xg: calls.setdefault('trained', history) and [])
    em.run_daily_expected_points(now=datetime(2026, 10, 8, 6))
    assert [(h['year_start'], h['gameweek']) for h in calls['trained']] == [(2025, 38), (2026, 5)]


def test_one_failing_write_does_not_skip_the_other_or_the_accuracy_record(monkeypatch):
    calls = {}
    patch_job(monkeypatch, calls)
    conns = []
    monkeypatch.setattr(em, 'connect_db', lambda: conns.append(Conn()) or conns[-1])

    def broken_log(conn, rows, year, gw, deadline, now):
        raise RuntimeError('log write failed')

    monkeypatch.setattr(em, 'log_forecasts', broken_log)
    em.run_daily_expected_points(now=datetime(2026, 10, 8, 6))
    assert calls['current'][0]['expected_points'] == 3.2
    assert calls['settled'] is True
    assert conns[0].rolled_back
