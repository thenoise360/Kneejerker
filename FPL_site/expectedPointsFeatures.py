"""Pure feature building for our expected points model. No database access here.

A feature for gameweek G may only use what was known before G's deadline: the player's matches
in earlier gameweeks, the snapshot taken after G - 1, and the match engine as fitted after G - 1.
Missing values are nan (the model handles them); they are never filled with zero.
"""
from collections import defaultdict

NAN = float('nan')
STARTED_MINUTES = 60
# The version of the features and model together; logged with every forecast.
MODEL_VERSION = 'hgb-poisson-2026-10'

FEATURES = (
    'points_last_3', 'points_last_5', 'minutes_last_3', 'minutes_last_5',
    'starts_last_5', 'goals_last_5', 'assists_last_5', 'bonus_last_5', 'clean_sheets_last_5',
    'xg_last_5', 'xa_last_5', 'season_points_per_match', 'season_minutes_per_match',
    'price', 'chance_of_playing', 'home_share', 'matches_in_gameweek', 'team_xg', 'opp_xg',
)

_SUMMED = ('total_points', 'minutes', 'goals_scored', 'assists', 'clean_sheets', 'bonus')


def player_gameweeks(history_rows):
    """{code: [one dict per (season, gameweek), oldest first]}, double gameweeks summed."""
    grouped = {}
    for r in history_rows:
        key = (r['code'], r['year_start'], r['gameweek'])
        g = grouped.get(key)
        if g is None:
            g = grouped[key] = {'year_start': r['year_start'], 'gameweek': r['gameweek'],
                                'team_code': r['team_code'], 'matches': 0, 'starts': 0,
                                **{k: 0 for k in _SUMMED}}
        g['matches'] += 1
        g['starts'] += 1 if (r['minutes'] or 0) >= STARTED_MINUTES else 0
        for k in _SUMMED:
            g[k] += r[k] or 0
    by_code = defaultdict(list)
    for (code, _, _), g in grouped.items():
        by_code[code].append(g)
    for games in by_code.values():
        games.sort(key=lambda g: (g['year_start'], g['gameweek']))
    return dict(by_code)


def per_gameweek_xg(snapshots):
    """{(code, year_start, gameweek): (xg, xa)} from season-to-date snapshot totals."""
    out = {}
    series = defaultdict(list)
    for s in snapshots:
        series[(s['code'], s['year_start'])].append(s)
    for (code, year), snaps in series.items():
        snaps.sort(key=lambda s: s['gameweek'])
        prev_xg = prev_xa = 0.0
        for s in snaps:
            xg, xa = float(s['expected_goals'] or 0), float(s['expected_assists'] or 0)
            out[(code, year, s['gameweek'])] = (round(xg - prev_xg, 4), round(xa - prev_xa, 4))
            prev_xg, prev_xa = xg, xa
    return out


def _mean(values):
    return sum(values) / len(values) if values else NAN


def _total(values):
    return float(sum(values)) if values else NAN


def feature_row(code, year_start, gameweek, games, snapshot_before, xg_by_gw, fixture):
    """Features for one player and target gameweek. `games` are that player's gameweek totals."""
    earlier = [g for g in games if (g['year_start'], g['gameweek']) < (year_start, gameweek)]
    last3, last5 = earlier[-3:], earlier[-5:]
    this_season = [g for g in earlier if g['year_start'] == year_start]
    season_matches = sum(g['matches'] for g in this_season)
    xg5 = [xg_by_gw.get((code, g['year_start'], g['gameweek'])) for g in last5]
    xg5 = [x for x in xg5 if x is not None]
    snap = snapshot_before or {}
    chance = snap.get('chance_of_playing_next_round')
    row = {
        'points_last_3': _mean([g['total_points'] for g in last3]),
        'points_last_5': _mean([g['total_points'] for g in last5]),
        'minutes_last_3': _mean([g['minutes'] for g in last3]),
        'minutes_last_5': _mean([g['minutes'] for g in last5]),
        'starts_last_5': _total([g['starts'] for g in last5]),
        'goals_last_5': _total([g['goals_scored'] for g in last5]),
        'assists_last_5': _total([g['assists'] for g in last5]),
        'bonus_last_5': _total([g['bonus'] for g in last5]),
        'clean_sheets_last_5': _total([g['clean_sheets'] for g in last5]),
        'xg_last_5': _total([x[0] for x in xg5]),
        'xa_last_5': _total([x[1] for x in xg5]),
        'season_points_per_match': (sum(g['total_points'] for g in this_season) / season_matches
                                    if season_matches else NAN),
        'season_minutes_per_match': (sum(g['minutes'] for g in this_season) / season_matches
                                     if season_matches else NAN),
        'price': float(snap['now_cost']) / 10 if snap.get('now_cost') is not None else NAN,
        'chance_of_playing': float(chance) if chance is not None else (100.0 if snap else NAN),
        'home_share': fixture['home_share'] if fixture else NAN,
        'matches_in_gameweek': float(fixture['matches']) if fixture else 0.0,
        'team_xg': fixture['team_xg'] if fixture else NAN,
        'opp_xg': fixture['opp_xg'] if fixture else NAN,
    }
    return {k: row[k] for k in FEATURES}


def _snapshot_index(snapshots):
    return {(s['code'], s['year_start'], s['gameweek']): s for s in snapshots}


def training_rows(history_rows, snapshots, fixture_xg):
    """One row per player-gameweek the player's club played, target = summed points."""
    games_by_code = player_gameweeks(history_rows)
    snaps = _snapshot_index(snapshots)
    xg_by_gw = per_gameweek_xg(snapshots)
    rows = []
    for code, games in games_by_code.items():
        for g in games:
            year, gw = g['year_start'], g['gameweek']
            fixture = fixture_xg.get((year, gw, g['team_code']))
            if fixture is None:
                continue   # no stored fixture for that club and gameweek: not a usable row
            before = snaps.get((code, year, gw - 1))
            position = (before or snaps.get((code, year, gw)) or {}).get('element_type')
            if position is None:
                continue
            row = feature_row(code, year, gw, games, before, xg_by_gw, fixture)
            row.update({'code': code, 'year_start': year, 'gameweek': gw,
                        'position': position, 'target': g['total_points'],
                        'matches_in_gameweek': float(g['matches'])})
            rows.append(row)
    return rows


def prediction_rows(history_rows, snapshots, fixture_xg, year_start, gameweek, players):
    """One row per current player for the coming gameweek; players are latest snapshot rows."""
    games_by_code = player_gameweeks(history_rows)
    xg_by_gw = per_gameweek_xg(snapshots)
    rows = []
    for p in players:
        fixture = fixture_xg.get((year_start, gameweek, p['team_code']))
        row = feature_row(p['code'], year_start, gameweek, games_by_code.get(p['code'], []),
                          p, xg_by_gw, fixture)
        row.update({'code': p['code'], 'player_id': p['player_id'], 'year_start': year_start,
                    'gameweek': gameweek, 'position': p['element_type']})
        rows.append(row)
    return rows
