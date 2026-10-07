import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import re
from pathlib import Path

import FPL_site.dataModels as dm


class Conn:
    def __init__(self):
        self.queries = []

    def cursor(self, **k):
        return self

    def execute(self, sql, params=None):
        self.queries.append(sql)

    def fetchall(self):
        return []

    def close(self):
        pass


def test_preseason_consistency_query_looks_one_season_back_from_the_current_one(monkeypatch):
    conn = Conn()
    monkeypatch.setattr(dm, 'connect_db', lambda **k: conn)
    monkeypatch.setattr(dm, 'generateCurrentGameweek', lambda: 0)
    monkeypatch.setattr(dm, 'season_start', 2027)
    dm.get_most_consistent_players()
    sql = ' '.join(conn.queries)
    assert 'year_start = 2026' in sql and 'year_start = 2027' in sql
    assert '2025' not in sql


def test_no_stale_season_label_or_literal_year_assignments_remain():
    for name in ('dataModels.py', 'futurePerformanceModel.py', 'genericMethods.py', 'sqlFunction.py'):
        src = (Path(dm.__file__).parent / name).read_text(encoding='utf-8-sig')
        assert not re.search(r'^season\s*=\s*"\d{4}_\d{4}"', src, re.M), name
        assert not re.search(r'^\s*(last_year|season_start)\s*=\s*"?\d{4}"?\s*$', src, re.M), name
