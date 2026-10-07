import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import dataModels


class FakeCursor:
    """Answers each query by what it asks for, so no database is needed."""
    def __init__(self):
        self.last = ''

    def execute(self, sql, params=None):
        self.last = sql

    def fetchall(self):
        if 'FROM' in self.last and 'bootstrapstatic_teams where' in self.last:
            return [{'id': 1, 'name': 'Arsenal', 'short_name': 'ARS', 'code': 3},
                    {'id': 2, 'name': 'Crystal Palace', 'short_name': 'CRY', 'code': 31}]
        if 'es_f.event = 11' in self.last:
            return [{'team_h': 1, 'team_a': 2, 'team_h_difficulty': 2,
                     'team_a_difficulty': 4, 'gameweek': 11}]
        return []

    def fetchone(self):
        if 'bootstrapstatic_elements' in self.last:
            return {'team_id': 1, 'Full_name': 'A B'}
        return {'avg_difficulty': 3}

    def close(self):
        pass


class FakeConn:
    def cursor(self, dictionary=False):
        return FakeCursor()

    def close(self):
        pass


def test_fixtures_carry_the_full_opponent_name(monkeypatch):
    monkeypatch.setattr(dataModels, 'connect_db', lambda: FakeConn())
    monkeypatch.setattr(dataModels, 'generateCurrentGameweek', lambda: 10)
    fixtures = dataModels.next_5_gameweeks(1)
    first = fixtures[0]
    assert first['teamFullName'] == 'Crystal Palace'
    assert first['teamName'] == 'CRY'
    assert first['homeOrAway'] == 'Home'
    blank = fixtures[1]
    assert blank['homeOrAway'] == 'Blank'
    assert blank['teamFullName'] == ''
