import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import expectedPointsBacktest as bt


def result(gw, pid, ours, official, actual, position=3):
    return {'year_start': 2025, 'gameweek': gw, 'player_id': pid, 'position': position,
            'ours': ours, 'official': official, 'actual': actual}


def test_passes_only_when_both_error_and_captaincy_beat_the_official_number():
    results = [result(1, 1, 8, 4, 9), result(1, 2, 2, 6, 1), result(2, 1, 7, 3, 8), result(2, 2, 3, 5, 2)]
    squads = {(2025, 1): [1, 2], (2025, 2): [1, 2]}
    s = bt.summarise(results, squads)
    assert s['mae_ours'] < s['mae_official']
    assert s['captain_wins_ours'] == 2 and s['captain_wins_official'] == 0
    assert s['passes'] is True


def test_lower_error_but_worse_captains_fails():
    # Player 3 is outside the squad: ours is spot on there, which wins the error test, but inside
    # the squad ours picks player 2 (2 points) while the official number picks player 1 (10).
    results = [result(1, 1, 5, 9, 10), result(1, 2, 6, 0, 2), result(1, 3, 2, 20, 2)]
    s = bt.summarise(results, {(2025, 1): [1, 2]})
    assert s['mae_ours'] < s['mae_official']
    assert s['captain_wins_official'] == 1
    assert s['passes'] is False


def test_walk_forward_never_trains_on_the_gameweek_it_predicts(monkeypatch):
    trained_on = []
    monkeypatch.setattr(bt, 'train', lambda rows: trained_on.append({(r['year_start'], r['gameweek']) for r in rows}) or {})
    monkeypatch.setattr(bt, 'predict', lambda models, rows: [1.0] * len(rows))
    rows = [{'year_start': 2025, 'gameweek': g, 'player_id': 1, 'position': 3, 'target': 2} for g in (1, 2, 3)]
    official = {(2025, g, 1): 2.0 for g in (1, 2, 3)}
    out = bt.walk_forward(rows, official, [(2025, 2), (2025, 3)])
    assert trained_on == [{(2025, 1)}, {(2025, 1), (2025, 2)}]
    assert [r['gameweek'] for r in out] == [2, 3]


def test_the_report_states_the_verdict():
    text = bt.render_report({'mae_ours': 1.9, 'mae_official': 2.1, 'mae_by_position': {},
                             'captain_wins_ours': 20, 'captain_wins_official': 15, 'captain_ties': 3,
                             'gameweeks': 38, 'players': 9000, 'passes': True}, '2026-10-09')
    assert 'Passes: yes' in text and '1.9' in text and '2.1' in text
