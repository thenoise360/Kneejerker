import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime

from FPL_site.matchPredictionEngine import loggable_rows, log_predictions, MODEL_VERSION, LOG_TABLE


def row(fixture_code, team_id, kickoff):
    return {'fixture_code': fixture_code, 'team_id': team_id, 'opponent_id': 99, 'gameweek': 6,
            'is_home': 1, 'kickoff_time': kickoff, 'expected_goals_mean': 1.4,
            'expected_goals_low': 0.8, 'expected_goals_high': 2.0}


NOW = datetime(2026, 10, 10, 12, 0)


def test_only_future_kickoffs_are_logged():
    rows = [row(1, 1, '2026-10-10T11:30:00Z'), row(2, 1, '2026-10-10T12:00:00Z'),
            row(3, 1, '2026-10-10T14:00:00Z'), row(4, 1, None), row(5, 1, 'garbage'),
            row(6, 1, 20261010140000)]
    assert [r['fixture_code'] for r in loggable_rows(rows, NOW)] == [3]


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def executemany(self, sql, params):
        self.calls.append((sql, list(params)))


class FakeConn:
    def __init__(self):
        self.cur = FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True


def test_log_rows_are_idempotent_per_day():
    conn = FakeConn()
    log_predictions(conn, [row(3, 1, '2026-10-10T14:00:00Z')], NOW)
    create_sql = conn.cur.calls[0][0]
    insert_sql, records = conn.cur.calls[1]
    assert f'CREATE TABLE IF NOT EXISTS {LOG_TABLE}' in create_sql
    assert 'PRIMARY KEY (fixture_code, team_id, model_version, log_date)' in create_sql
    assert insert_sql.strip().startswith(f'INSERT IGNORE INTO {LOG_TABLE}')
    assert records[0][-3:] == (MODEL_VERSION, NOW, NOW.date())
    assert conn.committed


def test_nothing_to_log_writes_nothing():
    conn = FakeConn()
    log_predictions(conn, [row(1, 1, '2026-10-10T11:30:00Z')], NOW)
    assert conn.cur.calls == [] and not conn.committed


def test_logging_failure_does_not_fail_the_match_job(monkeypatch):
    import FPL_site.matchPredictionEngine as engine

    class Conn:
        closed = False

        def cursor(self, **kwargs):
            return FakeCursor()

        def close(self):
            self.closed = True

    persisted = []
    monkeypatch.setattr(engine, 'connect_db', lambda: Conn())
    monkeypatch.setattr(engine, 'fit_current_ratings', lambda cursor: ({}, 0.3, 0.0, {}, 6))
    monkeypatch.setattr(engine, 'build_fixture_predictions', lambda *a, **k: [row(3, 1, '2026-10-10T14:00:00Z')])
    monkeypatch.setattr(engine, 'persist_match_predictions', lambda conn, rows: persisted.append(rows))

    def boom(conn, rows, now):
        raise RuntimeError('log table broken')

    monkeypatch.setattr(engine, 'log_predictions', boom)
    engine.run_daily_match_predictions()
    assert len(persisted) == 1


def test_strength_failure_rolls_back_before_momentum_runs(monkeypatch):
    import FPL_site.matchPredictionEngine as engine
    import FPL_site.playerMomentum as pm
    events = []

    class Conn:
        def cursor(self, **kwargs):
            return FakeCursor()

        def rollback(self):
            events.append('rollback')

        def close(self):
            pass

    monkeypatch.setattr(engine, 'connect_db', lambda: Conn())
    monkeypatch.setattr(engine, 'fit_current_ratings', lambda cursor: ({}, 0.3, 0.0, {}, 6))
    monkeypatch.setattr(engine, 'build_fixture_predictions', lambda *a, **k: [])
    monkeypatch.setattr(engine, 'persist_match_predictions', lambda conn, rows: None)
    monkeypatch.setattr(engine, 'log_predictions', lambda conn, rows, now: None)
    monkeypatch.setattr(engine, 'fetch_teams_for_season', lambda cursor, season: {})
    monkeypatch.setattr(engine, 'build_team_strengths', lambda *a, **k: [])
    monkeypatch.setattr(engine, 'fetch_squad_rows', lambda cursor, season: [])

    def broken_persist(conn, strengths):
        raise RuntimeError('insert failed after the delete')

    monkeypatch.setattr(engine, 'persist_team_strengths', broken_persist)
    monkeypatch.setattr(pm, 'run_daily_momentum', lambda cursor, conn, gw: events.append('momentum'))
    engine.run_daily_match_predictions()
    assert events == ['rollback', 'momentum']
