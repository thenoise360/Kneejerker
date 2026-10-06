import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.lastWeekRecap import (
    summarise_event, aggregate_player_rows, top_performers, fetch_event_rows, fetch_history_rows,
)


def row(element, points, name='Player', minutes=90, difficulty=3, **stats):
    base = {'element': element, 'total_points': points, 'minutes': minutes, 'goals_scored': 0,
            'assists': 0, 'clean_sheets': 0, 'saves': 0, 'bonus': 0, 'penalties_saved': 0,
            'web_name': name, 'element_type': 3, 'team_short_name': 'ARS', 'difficulty': difficulty}
    base.update(stats)
    return base


class FakeCursor:
    def __init__(self, rows):
        self.rows, self.executed = rows, []

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


def test_summarise_event_happy_path():
    rows = [{'average_entry_score': 48, 'highest_score': 126, 'finished': 1, 'data_checked': 1}]
    assert summarise_event(rows) == {'average_score': 48, 'highest_score': 126}


def test_summarise_event_ignores_duplicate_zero_row():
    rows = [{'average_entry_score': 0, 'highest_score': None, 'finished': 0, 'data_checked': 0},
            {'average_entry_score': 48, 'highest_score': 126, 'finished': 1, 'data_checked': 1}]
    assert summarise_event(rows) == {'average_score': 48, 'highest_score': 126}


def test_summarise_event_missing_or_unfinished_is_none():
    assert summarise_event([]) is None
    assert summarise_event([{'average_entry_score': 0, 'highest_score': None, 'finished': 0}]) is None


def test_aggregate_sums_double_gameweek():
    players = aggregate_player_rows([
        row(7, 6, name='Saka', goals_scored=1, difficulty=4),
        row(7, 9, name='Saka', assists=2, bonus=3, difficulty=2),
    ])
    saka = players[7]
    assert saka['points'] == 15
    assert saka['minutes'] == 180
    assert saka['goals'] == 1 and saka['assists'] == 2 and saka['bonus'] == 3
    assert saka['difficulty'] == 2  # easiest of the two fixtures


def test_aggregate_handles_missing_difficulty():
    players = aggregate_player_rows([row(3, 2, difficulty=None)])
    assert players[3]['difficulty'] is None


def test_top_performers_orders_by_points_then_bonus_then_name_and_skips_non_players():
    players = aggregate_player_rows([
        row(1, 10, name='Bruno', bonus=1), row(2, 10, name='Alexis', bonus=3),
        row(3, 12, name='Haaland'), row(4, 15, name='Bench', minutes=0), row(5, 2, name='Zed'),
    ])
    assert [p['name'] for p in top_performers(players)] == ['Haaland', 'Alexis', 'Bruno']


def test_top_performers_empty():
    assert top_performers({}) == []


def test_fetchers_pass_season_and_gameweek():
    cursor = FakeCursor([{'x': 1}])
    assert fetch_event_rows(cursor, 2026, 5) == [{'x': 1}]
    assert cursor.executed[0][1] == (2026, 5)
    fetch_history_rows(cursor, 2026, 5)
    assert cursor.executed[1][1] == (2026, 2026, 5)
