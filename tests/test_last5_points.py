import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
from decimal import Decimal

from FPL_site import dataModels


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self, dictionary=False):
        return FakeCursor(self.rows)

    def close(self):
        pass


def test_last_5_points_are_plain_ints_not_decimals(monkeypatch):
    rows = [{'gw': 3, 'points': Decimal('13'), 'minutes': Decimal('90'), 'difficulty': 4},
            {'gw': 4, 'points': Decimal('2'), 'minutes': Decimal('45'), 'difficulty': None}]
    monkeypatch.setattr(dataModels, 'connect_db', lambda: FakeConn(rows))
    monkeypatch.setattr(dataModels, 'generateCurrentGameweek', lambda: 4)
    result = dataModels.get_player_last_5_points(1)
    by_gw = {r['gw']: r for r in result}
    assert by_gw[3]['points'] == 13 and type(by_gw[3]['points']) is int
    assert type(by_gw[3]['minutes']) is int
    assert type(by_gw[3]['difficulty']) is int
    assert by_gw[4]['difficulty'] is None
    assert type(by_gw[4]['points']) is int
    assert by_gw[1]['points'] == 0
