"""
Last meetings between two clubs, for the Team page fixture detail.

A fetcher (load_meeting_history) reads finished league fixtures for every season once
and maps each season's team ids to stable team codes, because ids are re-issued every
season. A pure function (last_meetings) then picks one pairing out of that history.
Nothing here writes to the database.
"""
from FPL_site.dataModels import db, current_season_start
from FPL_site.matchPredictionEngine import (
    fetch_team_code_map, fetch_teams_for_season, fetch_finished_fixtures,
    kickoff_in_season_window,
)

MEETING_LIMIT = 3
FIRST_SEASON = 2021   # the earliest season held in fixtures_fixtures


def season_label(year_start):
    """2025 -> '2025/26'."""
    return f"{int(year_start)}/{(int(year_start) + 1) % 100:02d}"


def seasons_to_load():
    """Every season from the first one in the data up to the current one."""
    return list(range(FIRST_SEASON, int(current_season_start()) + 1))


def code_map_for_season(cursor, year_start):
    """{team id: team code} for one season; falls back to the teams table if no snapshots."""
    mapping = fetch_team_code_map(cursor, year_start)
    if mapping:
        return mapping
    return {tid: t['code'] for tid, t in fetch_teams_for_season(cursor, year_start).items()
            if t.get('code') is not None}


# Finished seasons never change, so their mapped results are kept for the life of the
# process, keyed by season. The live season is always read fresh.
_COMPLETED_SEASONS = {}


def clear_history_cache():
    """Empty the in-process cache (used by tests)."""
    _COMPLETED_SEASONS.clear()


def _load_one_season(cursor, year, codes=None):
    """Mapped, window-checked, de-duplicated results for one season."""
    codes = codes if codes is not None else code_map_for_season(cursor, year)
    games, seen = [], set()
    for row in fetch_finished_fixtures(cursor, year):
        if not kickoff_in_season_window(row.get('kickoff_time'), year):
            continue
        home, away = codes.get(row['team_h']), codes.get(row['team_a'])
        if home is None or away is None:
            continue
        key = (year, row['event'], home, away)
        if key in seen:
            continue
        seen.add(key)
        games.append({
            'season': year, 'event': row['event'], 'home_code': home, 'away_code': away,
            'home_goals': row['team_h_score'], 'away_goals': row['team_a_score'],
            'kickoff': row['kickoff_time'],
        })
    return games


def load_meeting_history(cursor, seasons=None, current=None, current_codes=None):
    """
    Every finished fixture across `seasons` (default: all), as dicts keyed by team code:
    {season, event, home_code, away_code, home_goals, away_goals, kickoff}.
    Rows outside their season's July-to-July window and rows whose teams cannot be mapped
    are dropped; duplicates are kept once. Seasons before `current` are cached in memory;
    `current` (default: the last season listed) is read each call, using `current_codes`
    if the caller already has that season's id-to-code map.
    """
    years = list(seasons) if seasons is not None else seasons_to_load()
    if current is None:
        current = years[-1] if years else None
    history = []
    for year in years:
        if year < current:
            if year not in _COMPLETED_SEASONS:
                _COMPLETED_SEASONS[year] = _load_one_season(cursor, year)
            history.extend(_COMPLETED_SEASONS[year])
        else:
            history.extend(_load_one_season(cursor, year, current_codes if year == current else None))
    return history


def last_meetings(history, team_code, opponent_code, limit=MEETING_LIMIT):
    """
    The last `limit` meetings of two clubs, newest first, from team_code's point of view:
    [{'season_label': '2025/26', 'is_home': bool, 'result': 'won'|'drew'|'lost', 'score': '3–1'}].
    """
    pair = {team_code, opponent_code}
    games, seen = [], set()
    for g in history:
        if {g['home_code'], g['away_code']} != pair or team_code == opponent_code:
            continue
        key = (g['season'], g['event'], g['home_code'], g['away_code'])
        if key in seen:
            continue
        seen.add(key)
        games.append(g)
    # ISO kickoff strings sort in time order; season and event break ties.
    games.sort(key=lambda g: (g['kickoff'] or '', g['season'], g['event']), reverse=True)

    meetings = []
    for g in games[:limit]:
        is_home = g['home_code'] == team_code
        mine, theirs = (g['home_goals'], g['away_goals']) if is_home else (g['away_goals'], g['home_goals'])
        meetings.append({
            'season_label': season_label(g['season']),
            'is_home': is_home,
            'result': 'won' if mine > theirs else 'drew' if mine == theirs else 'lost',
            'score': f"{mine}–{theirs}",
        })
    return meetings
