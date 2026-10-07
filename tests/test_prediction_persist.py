import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.matchPredictionEngine import persist_match_predictions, PREDICTIONS_TABLE


class FakeCursor:
    def __init__(self, calls):
        self.calls = calls

    def execute(self, sql, params=None):
        self.calls.append(('execute', ' '.join(sql.split()), params))

    def executemany(self, sql, records):
        self.calls.append(('executemany', ' '.join(sql.split()), records))


class FakeConn:
    def __init__(self):
        self.calls = []
        self.commits = 0

    def cursor(self):
        return FakeCursor(self.calls)

    def commit(self):
        self.calls.append(('commit', '', None))
        self.commits += 1


def make_row(fixture_code, team_id, gameweek):
    return {'fixture_code': fixture_code, 'team_id': team_id, 'gameweek': gameweek,
            'opponent_id': 9, 'is_home': 1, 'expected_goals_mean': 1.4,
            'expected_goals_low': 0.8, 'expected_goals_high': 2.0, 'attack_rating': 0.1,
            'defence_rating': 0.0, 'home_adv': 0.25, 'computed_at': None}


def test_full_replace_deletes_everything_before_inserting_in_one_commit():
    conn = FakeConn()
    persist_match_predictions(conn, [make_row(1, 1, 6), make_row(1, 2, 6)])
    deletes = [i for i, c in enumerate(conn.calls) if c[1].startswith('DELETE')]
    inserts = [i for i, c in enumerate(conn.calls) if c[0] == 'executemany']
    assert len(deletes) == 1 and len(inserts) == 1
    assert conn.calls[deletes[0]][1] == f'DELETE FROM {PREDICTIONS_TABLE}'
    assert conn.calls[deletes[0]][2] is None
    assert deletes[0] < inserts[0]
    assert conn.commits == 1
    assert conn.calls[-1][0] == 'commit'


def test_no_rows_runs_no_sql():
    conn = FakeConn()
    persist_match_predictions(conn, [])
    assert conn.calls == [] and conn.commits == 0
