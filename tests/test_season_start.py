import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import logging
import sys
from datetime import datetime

import pytest

import FPL_site.dataModels as dm

# sqlFunction (the offline update job) uses top-level imports, so FPL_site must be on the path.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'FPL_site'))
import sqlFunction as sf


def events(*deadlines):
    return [{'id': i + 1, 'deadline_time': d} for i, d in enumerate(deadlines)]


# ---- season_start_from_events ----------------------------------------------------------

def test_year_is_the_calendar_year_of_the_first_deadline():
    assert sf.season_start_from_events(events('2026-08-15T17:30:00Z', '2026-08-22T10:00:00Z')) == 2026


def test_year_is_the_first_deadline_even_if_the_season_ends_next_year():
    evs = events('2026-08-15T17:30:00Z', '2027-05-24T10:00:00Z')
    assert sf.season_start_from_events(evs) == 2026


def test_earliest_deadline_wins_regardless_of_order():
    evs = events('2027-01-02T10:00:00Z', '2026-08-15T17:30:00Z')
    assert sf.season_start_from_events(evs) == 2026


def test_year_is_an_int():
    assert isinstance(sf.season_start_from_events(events('2026-08-15T17:30:00Z')), int)


@pytest.mark.parametrize('bad', [None, [], {}, 'nope', [None], [{}], [{'deadline_time': None}],
                                 [{'deadline_time': 'garbage'}], [{'deadline_time': 20260815}]])
def test_no_or_garbled_events_give_none(bad):
    assert sf.season_start_from_events(bad) is None


def test_garbled_entries_are_skipped_when_a_good_one_exists():
    evs = events('garbage', '2026-08-15T17:30:00Z')
    assert sf.season_start_from_events(evs) == 2026


# ---- dataModels.season_start resolution ------------------------------------------------

class FakeConn:
    def __init__(self, value=None, boom=False):
        self.value, self.boom, self.closed = value, boom, False

    def cursor(self):
        return self

    def execute(self, sql):
        if self.boom:
            raise RuntimeError('db down')
        self.sql = sql

    def fetchone(self):
        return (self.value,)

    def close(self):
        self.closed = True


def test_module_level_season_start_is_an_int_and_offline_under_skip_flag():
    assert isinstance(dm.season_start, int)
    assert dm.season_start == dm.FALLBACK_SEASON_START


def test_calendar_fallback_rolls_over_in_july():
    assert dm._calendar_season_start(datetime(2026, 10, 8)) == 2026
    assert dm._calendar_season_start(datetime(2027, 2, 1)) == 2026
    assert dm._calendar_season_start(datetime(2027, 6, 30)) == 2026
    assert dm._calendar_season_start(datetime(2027, 7, 1)) == 2027


def test_skip_flag_never_touches_the_database(monkeypatch):
    monkeypatch.setattr(dm, 'connect_db', lambda **k: pytest.fail('connected'))
    assert dm._resolve_season_start(2026) == 2026


@pytest.fixture
def live(monkeypatch):
    monkeypatch.delenv('KJ_SKIP_DB_INIT', raising=False)


def test_reads_the_latest_year_from_the_database_with_a_short_timeout(live, monkeypatch):
    conn, seen = FakeConn(2027), {}
    monkeypatch.setattr(dm, 'connect_db', lambda **k: seen.update(k) or conn)
    assert dm._resolve_season_start(2026) == 2027
    assert 'MAX(year_start)' in conn.sql and conn.closed
    assert 0 < seen['timeout'] <= 5


def test_falls_back_when_the_database_is_unavailable_and_logs_an_error(live, monkeypatch, caplog):
    monkeypatch.setattr(dm, 'connect_db', lambda **k: None)
    with caplog.at_level(logging.ERROR):
        assert dm._resolve_season_start(2026) == 2026
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_falls_back_when_the_query_fails_or_is_empty(live, monkeypatch, caplog):
    monkeypatch.setattr(dm, 'connect_db', lambda **k: FakeConn(boom=True))
    with caplog.at_level(logging.ERROR):
        assert dm._resolve_season_start(2026) == 2026
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    monkeypatch.setattr(dm, 'connect_db', lambda **k: FakeConn(None))
    assert dm._resolve_season_start(2026) == 2026


def test_refresh_fixes_a_season_that_stuck_on_the_fallback(live, monkeypatch):
    monkeypatch.setattr(dm, 'season_start', 2026)
    monkeypatch.setattr(dm, 'connect_db', lambda **k: FakeConn(2027))
    assert dm.refresh_season_start() == 2027
    assert dm.season_start == 2027 and dm.current_season_start() == 2027


def test_refresh_keeps_the_current_season_when_the_database_blips(live, monkeypatch):
    monkeypatch.setattr(dm, 'season_start', 2027)
    monkeypatch.setattr(dm, 'connect_db', lambda **k: None)
    assert dm.refresh_season_start() == 2027
    assert dm.season_start == 2027


def test_future_performance_model_shares_the_same_season():
    import FPL_site.futurePerformanceModel as fpm
    assert fpm.season_start == dm.season_start


# ---- the update job uses the derived year ----------------------------------------------

BOOTSTRAP = {
    'events': [{'id': 1, 'deadline_time': '2027-08-14T17:30:00Z', 'is_current': False, 'is_next': True}],
    'teams': [{'id': 1, 'code': 3, 'name': 'Arsenal'}],
    'elements': [],
}


class FakeResponse:
    def __init__(self, payload):
        self.payload, self.status_code = payload, 200

    def json(self):
        return self.payload


class FakeDB:
    def __init__(self, log):
        self.log = log

    def cursor(self):
        return self

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return [('id',), ('code',), ('name',), ('year_start',), ('gameweek',), ('event',)]

    def executemany(self, sql, batch):
        self.log.append((sql, batch))

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def job(monkeypatch):
    urls, writes = [], []

    def fake_get(url, *a, **k):
        urls.append(url)
        if 'bootstrap-static' in url:
            return FakeResponse(BOOTSTRAP)
        if 'fixtures' in url:
            return FakeResponse([{'id': 1, 'code': 9, 'event': 1}])
        pytest.fail('unexpected request ' + url)

    monkeypatch.setattr(sf.requests, 'get', fake_get)
    monkeypatch.setattr(sf, 'connect_to_db', lambda *a: FakeDB(writes))
    monkeypatch.setattr(sf, 'get_players', lambda: [])
    return urls, writes


def test_update_job_writes_the_derived_year_and_fetches_bootstrap_once(job):
    urls, writes = job
    sf.update_all_tables()
    assert sum('bootstrap-static' in u for u in urls) == 1
    assert writes, 'nothing was written'
    for _, batch in writes:
        assert all(rec['year_start'] == '2027' for rec in batch)   # string, as before


@pytest.mark.parametrize('payload', ['no_events', 'garbled', 'fetch_failed'])
def test_update_job_writes_nothing_when_the_year_cannot_be_derived(job, monkeypatch, caplog, payload):
    urls, writes = job
    connects = []
    monkeypatch.setattr(sf, 'connect_to_db', lambda *a: connects.append(a) or FakeDB(writes))
    if payload == 'no_events':
        monkeypatch.setitem(BOOTSTRAP, 'events', [])
    elif payload == 'garbled':
        monkeypatch.setitem(BOOTSTRAP, 'events', [{'deadline_time': 'garbage'}])
    else:
        monkeypatch.setattr(sf, 'fetch_bootstrap_static', lambda: None)
    with caplog.at_level(logging.ERROR):
        sf.update_all_tables()
    assert connects == [] and writes == []
    assert any('year' in m.lower() for m in caplog.messages)
    assert not any('fixtures' in u and 'bootstrap' not in u for u in urls)


def test_individual_writers_refuse_to_write_without_a_year(job):
    urls, writes = job
    sf.update_fixtures_tables('u', 'p', 'd', 'h')
    sf.update_element_summary_tables('u', 'p', 'd', 'h')
    assert writes == [] and urls == []
