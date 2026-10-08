import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from datetime import datetime

from FPL_site import expectedPointsModel as em

EVENTS = [{'id': g, 'deadline_time': f'2026-09-{10 + g:02d}T10:00:00Z', 'finished': g <= 6,
           'data_checked': g <= 6} for g in range(1, 8)]
NOW = datetime(2026, 10, 20)


class Conn:
    rolled_back = False

    def rollback(self):
        self.rolled_back = True


def log(pid, ep, official, gw):
    return {'player_id': pid, 'code': 100 + pid, 'expected_points': ep, 'official_expected_points': official,
            'logged_at': datetime(2026, 9, 10 + gw - 1)}


def setup(monkeypatch, recorded=()):
    out = {'accuracy': [], 'log_reads': []}
    monkeypatch.setattr(em, 'fetch_recorded_gameweeks', lambda cur, y, source: set(recorded))
    # the snapshot after gameweek 4 says position 3 for both; after gameweek 5 it would say 4
    monkeypatch.setattr(em, 'fetch_snapshot_rows', lambda cur, years: [
        {'gameweek': 4, 'player_id': 1, 'element_type': 3, 'selected': 50.0},
        {'gameweek': 4, 'player_id': 2, 'element_type': 3, 'selected': 20.0},
        {'gameweek': 5, 'player_id': 1, 'element_type': 4, 'selected': 99.0}])

    def log_rows(cur, y, gw, source):
        out['log_reads'].append((y, gw, source))
        return [log(1, 6.0, 5.0, gw), log(2, 2.0, 3.0, gw)]

    monkeypatch.setattr(em, 'fetch_log_rows', log_rows)
    monkeypatch.setattr(em, 'fetch_actual_points', lambda cur, y, gw: {1: 8, 2: 2})
    monkeypatch.setattr(em, 'persist_accuracy', lambda conn, gw, y, result, now, source:
                        out['accuracy'].append((gw, y, source, result)))
    return out


def test_a_settled_gameweek_gets_a_live_accuracy_row_for_its_season(monkeypatch):
    out = setup(monkeypatch, recorded={1, 2, 3, 4, 6})
    em.record_settled_gameweeks(Conn(), object(), EVENTS, 2026, NOW)
    assert len(out['accuracy']) == 1
    gw, year, source, result = out['accuracy'][0]
    assert (gw, year, source) == (5, 2026, 'live')
    assert result['players'] == 2
    assert result['mae_ours'] == 1.0 and result['mae_official'] == 2.0


def test_positions_and_the_template_squad_come_from_the_snapshot_before_the_gameweek(monkeypatch):
    out = setup(monkeypatch, recorded={1, 2, 3, 4, 6})
    em.record_settled_gameweeks(Conn(), object(), EVENTS, 2026, NOW)
    result = out['accuracy'][0][3]
    assert set(result['mae_by_position']) == {3}   # the later snapshot would have said position 4
    assert result['captain_ours'] == 1 and result['captain_ours_points'] == 8


def test_recorded_and_unsettled_gameweeks_are_skipped(monkeypatch):
    out = setup(monkeypatch, recorded={1, 2, 3, 4, 5, 6})
    em.record_settled_gameweeks(Conn(), object(), EVENTS, 2026, NOW)
    assert out['accuracy'] == [] and out['log_reads'] == []   # gameweek 7 is unsettled


def test_one_failing_gameweek_does_not_stop_the_rest(monkeypatch):
    out = setup(monkeypatch, recorded={1, 2, 3, 6})

    def flaky(cur, y, gw):
        if gw == 4:
            raise RuntimeError('boom')
        return {1: 8, 2: 2}

    monkeypatch.setattr(em, 'fetch_actual_points', flaky)
    conn = Conn()
    em.record_settled_gameweeks(conn, object(), EVENTS, 2026, NOW)
    assert [a[0] for a in out['accuracy']] == [5]
    assert conn.rolled_back
