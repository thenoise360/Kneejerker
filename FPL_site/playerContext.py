"""Supporting player information for the This Week decision screens.

Pure functions shape rows into facts (never sentences). The fetchers are thin:
a cursor in, rows out. Nothing here fits a model: expected points (the official game's), momentum and
fixture expectations are all read from what the daily jobs stored.
"""
import json
import logging
from collections import defaultdict

from FPL_site.dataModels import connect_db, season_start, get_week_view_state
from FPL_site.playerMomentum import (
    fixture_change, fixture_direction, fetch_upcoming_predictions, fetch_team_baselines,
)

logger = logging.getLogger(__name__)

RECENT_GAMES = 5
NEXT_FIXTURES = 3
POSITION_NAMES = {1: 'Goalkeeper', 2: 'Defender', 3: 'Midfielder', 4: 'Forward'}
DIFFICULTY_WORDS = {'up': 'easier', 'same': 'average', 'down': 'tougher'}


#################################################
#                  Fetchers                     #
#################################################

def fetch_expected_points(cursor, year_start):
    """Rows {player_id, expected_points, element_type} from the latest stored snapshot.

    The official game's own expected points for the next gameweek (ep_next), stored daily in
    bootstrapstatic_elements. Our own model will replace this source later, so keep it behind
    this one fetcher and expected_points_map.
    """
    try:
        cursor.execute("""
            SELECT id AS player_id, ep_next AS expected_points, element_type
            FROM bootstrapstatic_elements
            WHERE year_start = %s
              AND gameweek = (SELECT MAX(gameweek) FROM bootstrapstatic_elements WHERE year_start = %s)
        """, (year_start, year_start))
        return cursor.fetchall()
    except Exception as e:
        logger.warning("fetch_expected_points: %s", e)
        return []


def fetch_team_rows(cursor, years):
    """Every club in the given seasons: year_start, id, code, short_name."""
    placeholders = ', '.join(['%s'] * len(years))
    cursor.execute(f"""
        SELECT year_start, id, code, short_name FROM bootstrapstatic_teams
        WHERE year_start IN ({placeholders})
    """, tuple(years))
    return cursor.fetchall()


def fetch_player_rows(cursor, year_start, ids):
    """The latest snapshot of each requested player this season."""
    if not ids:
        return []
    placeholders = ', '.join(['%s'] * len(ids))
    cursor.execute(f"""
        SELECT id, code, web_name, team, element_type, now_cost
        FROM bootstrapstatic_elements
        WHERE year_start = %s AND id IN ({placeholders})
          AND gameweek = (SELECT MAX(gameweek) FROM bootstrapstatic_elements WHERE year_start = %s)
    """, (year_start, *ids, year_start))
    return cursor.fetchall()


def fetch_element_ids_by_code(cursor, years, codes):
    """Which id a player had in each season: rows of year_start, id, code."""
    if not codes:
        return []
    years_in = ', '.join(['%s'] * len(years))
    codes_in = ', '.join(['%s'] * len(codes))
    cursor.execute(f"""
        SELECT DISTINCT year_start, id, code FROM bootstrapstatic_elements
        WHERE year_start IN ({years_in}) AND code IN ({codes_in})
    """, (*years, *codes))
    return cursor.fetchall()


def fetch_history_rows(cursor, season_elements):
    """Every game for the given {year_start: element id} pairs, oldest first."""
    pairs = [(y, e) for y, e in season_elements if e is not None]
    if not pairs:
        return []
    clause = ' OR '.join(['(year_start = %s AND element = %s)'] * len(pairs))
    params = [v for pair in pairs for v in pair]
    cursor.execute(f"""
        SELECT year_start, element, fixture, round, kickoff_time, opponent_team, was_home,
               minutes, goals_scored, assists, total_points
        FROM elementsummary_history
        WHERE {clause}
        ORDER BY year_start, kickoff_time
    """, params)
    return cursor.fetchall()


def fetch_recent_point_rows(cursor, year_start, element_ids, before_gameweek):
    """Points per game this season before the coming gameweek, for the given players."""
    if not element_ids:
        return []
    placeholders = ', '.join(['%s'] * len(element_ids))
    cursor.execute(f"""
        SELECT element, fixture, round, kickoff_time, total_points
        FROM elementsummary_history
        WHERE year_start = %s AND round < %s AND element IN ({placeholders})
        ORDER BY kickoff_time
    """, (year_start, before_gameweek, *element_ids))
    return cursor.fetchall()


def fetch_momentum_row(cursor, player_id):
    """The stored momentum for one player, or None (also when the table doesn't exist yet)."""
    try:
        cursor.execute("SELECT label, reason, signals_json FROM player_momentum WHERE player_id = %s",
                       (player_id,))
        return cursor.fetchone()
    except Exception as e:
        logger.warning("fetch_momentum_row: %s", e)
        return None


#################################################
#                 Pure shaping                  #
#################################################

def expected_points_map(rows):
    """{player_id: expected points}; players with no stored value are left out."""
    return {r['player_id']: float(r['expected_points'])
            for r in rows if r['expected_points'] is not None}


def position_averages(rows):
    """{element_type: average expected points} over everyone with a stored value."""
    totals = defaultdict(list)
    for r in rows:
        if r['expected_points'] is not None and r['element_type'] is not None:
            totals[r['element_type']].append(float(r['expected_points']))
    return {k: sum(v) / len(v) for k, v in totals.items()}


def league_baseline(upcoming):
    """League-average scored/conceded across the fixtures given; None when there are none."""
    rows = [r for r in upcoming if r.get('own_mean') is not None and r.get('opp_mean') is not None]
    if not rows:
        return None
    return {'scored': sum(float(r['own_mean']) for r in rows) / len(rows),
            'conceded': sum(float(r['opp_mean']) for r in rows) / len(rows)}


def fixture_difficulty(position, fixture, strength):
    """'easier', 'average' or 'tougher' for one fixture; None when we can't say.

    fixture: {'own_mean', 'opp_mean'} (a team_fixture_predictions row).
    strength: {'scored', 'conceded'}, the team's usual. Same rule and 20% line as the
    momentum fixtures signal: attackers look at their own expected goals, defenders and
    goalkeepers at the opponent's.
    """
    if not fixture or not strength:
        return None
    if fixture.get('own_mean') is None or fixture.get('opp_mean') is None:
        return None
    one = {'own_mean': float(fixture['own_mean']), 'opp_mean': float(fixture['opp_mean'])}
    change = fixture_change(position, [one], strength['scored'], strength['conceded'])
    return DIFFICULTY_WORDS[fixture_direction(change)]


def fixtures_for_team(upcoming, team_id, from_gw=None, to_gw=None):
    rows = [r for r in upcoming if r['team_id'] == team_id
            and (from_gw is None or r['gameweek'] >= from_gw)
            and (to_gw is None or r['gameweek'] <= to_gw)]
    rows.sort(key=lambda r: r['gameweek'])
    return rows


def fixture_view(row, position, strength, team_shorts):
    return {'gameweek': row['gameweek'],
            'opponent_short': team_shorts.get(row['opponent_id']),
            'is_home': bool(row['is_home']),
            'difficulty': fixture_difficulty(position, row, strength)}


def this_week_fact(position, team_id, gameweek, upcoming, baselines, team_shorts):
    """{'opponent_short', 'is_home', 'difficulty'} for the team's first match, or None."""
    rows = fixtures_for_team(upcoming, team_id, gameweek, gameweek)
    if not rows:
        return None
    strength = baselines.get(team_id) or league_baseline(upcoming)
    view = fixture_view(rows[0], position, strength, team_shorts)
    return {'opponent_short': view['opponent_short'], 'is_home': view['is_home'],
            'difficulty': view['difficulty']}


def recent_points(history_rows, before_gameweek=None, count=RECENT_GAMES):
    """{element: [points]} for each player's last games, oldest first.

    A double gameweek counts once: both games' points are added together.
    """
    per_round = defaultdict(lambda: defaultdict(int))
    seen = set()
    for r in history_rows:
        if before_gameweek is not None and r['round'] >= before_gameweek:
            continue
        key = (r['element'], r.get('fixture'), r['round'])
        if r.get('fixture') is not None and key in seen:
            continue   # a row stored twice counts once
        seen.add(key)
        per_round[r['element']][r['round']] += int(r['total_points'] or 0)
    return {element: [rounds[g] for g in sorted(rounds)][-count:]
            for element, rounds in per_round.items()}


def option_facts(player_id, availability, element_types, prices, gameweek, upcoming, baselines,
                 team_shorts, recent):
    """The summary every hub option carries, apart from id, name and expected points."""
    team = availability[player_id]['team']
    position = element_types.get(player_id)
    return {'team_short': team_shorts.get(team),
            'position': POSITION_NAMES.get(position),
            'price': prices.get(player_id),
            'this_week': this_week_fact(position, team, gameweek, upcoming, baselines, team_shorts),
            'recent_points': recent.get(player_id, [])}


def recent_games(history_rows, team_shorts, before_gameweek, count=RECENT_GAMES):
    """This season's last finished games, oldest first, one entry per match."""
    seen = set()
    games = []
    for r in sorted(history_rows, key=lambda r: (str(r['kickoff_time'] or ''), r['round'])):
        if r['round'] >= before_gameweek or (r['year_start'], r['fixture']) in seen:
            continue
        seen.add((r['year_start'], r['fixture']))
        games.append({'gameweek': r['round'],
                      'opponent_short': team_shorts.get(r['opponent_team']),
                      'is_home': bool(r['was_home']),
                      'minutes': int(r['minutes'] or 0),
                      'goals': int(r['goals_scored'] or 0),
                      'assists': int(r['assists'] or 0),
                      'points': int(r['total_points'] or 0)})
    return games[-count:]


def games_against(history_rows, team_rows, opponent_code):
    """Past meetings with a club, matched by the club's code in each season (ids are re-issued).

    history_rows: one player's games across seasons. team_rows: year_start, id, code per club.
    """
    code_by_season_id = {(t['year_start'], t['id']): t['code'] for t in team_rows}
    seen = set()
    games = []
    for r in sorted(history_rows, key=lambda r: (r['year_start'], str(r['kickoff_time'] or ''))):
        if code_by_season_id.get((r['year_start'], r['opponent_team'])) != opponent_code:
            continue
        key = (r['year_start'], r['fixture'])
        if key in seen:
            continue
        seen.add(key)
        games.append({'season': r['year_start'], 'gameweek': r['round'],
                      'is_home': bool(r['was_home']),
                      'minutes': int(r['minutes'] or 0),
                      'points': int(r['total_points'] or 0)})
    return games


def momentum_view(row):
    if not row:
        return None
    return {'label': row['label'], 'reason': row.get('reason'),
            'signals': json.loads(row.get('signals_json') or '[]')}


def build_player_context(gameweek, data):
    """Compose the route payload from already-fetched rows. Unknown ids are omitted.

    data keys: ids (requested order), players, expected_points, upcoming, baselines, teams,
    element_codes, history, momentum ({id: row}).
    """
    team_rows = data['teams']
    team_shorts = {t['id']: t['short_name'] for t in team_rows if t['year_start'] == season_start}
    team_codes = {t['id']: t['code'] for t in team_rows if t['year_start'] == season_start}
    expected = expected_points_map(data['expected_points'])
    averages = position_averages(data['expected_points'])
    by_id = {p['id']: p for p in data['players']}

    players = []
    for pid in data['ids']:
        p = by_id.get(pid)
        if p is None:
            continue
        position = p['element_type']
        team = p['team']
        strength = data['baselines'].get(team) or league_baseline(data['upcoming'])
        own_ids = {r['year_start']: r['id'] for r in data['element_codes'] if r['code'] == p['code']}
        history = [r for r in data['history'] if r['element'] == own_ids.get(r['year_start'])]
        upcoming = fixtures_for_team(data['upcoming'], team, gameweek, gameweek + NEXT_FIXTURES - 1)
        this_week = upcoming[0] if upcoming and upcoming[0]['gameweek'] == gameweek else None
        if this_week is None:
            vs_opponent = None
        else:
            opponent_code = team_codes.get(this_week['opponent_id'])
            vs_opponent = {'opponent_short': team_shorts.get(this_week['opponent_id']),
                           'games': games_against(history, team_rows, opponent_code)
                           if opponent_code is not None else []}
        expected_points = expected.get(pid)
        average = averages.get(position)
        players.append({
            'id': pid, 'name': p['web_name'], 'team_short': team_shorts.get(team),
            'position': POSITION_NAMES.get(position), 'price': p['now_cost'],
            'expected_points': round(expected_points, 1) if expected_points is not None else None,
            'position_average_expected_points': round(average, 1) if average is not None else None,
            'recent_games': recent_games([r for r in history if r['year_start'] == season_start],
                                         team_shorts, gameweek),
            'momentum': momentum_view(data['momentum'].get(pid)),
            'next_fixtures': [fixture_view(r, position, strength, team_shorts) for r in upcoming],
            'vs_opponent': vs_opponent,
        })
    return {'status': 'ready', 'gameweek': gameweek, 'players': players}


#################################################
#               Live-route entry                #
#################################################

def default_gameweek():
    """The gameweek the This Week page shows as upcoming, or None when there isn't one."""
    this_week = get_week_view_state()['this_week']
    return this_week['gameweek'] if this_week['mode'] == 'upcoming' else None


def get_player_context(ids, gameweek=None):
    """The player-context payload; {'status': 'unavailable'} if the database is down."""
    conn = connect_db()
    if conn is None:
        logger.error("get_player_context: could not connect to the database.")
        return {'status': 'unavailable'}
    years = (season_start, season_start - 1)
    try:
        if gameweek is None:
            gameweek = default_gameweek()
        if gameweek is None:
            return {'status': 'unavailable'}
        cursor = conn.cursor(dictionary=True)
        players = fetch_player_rows(cursor, season_start, ids)
        element_codes = fetch_element_ids_by_code(cursor, years, [p['code'] for p in players])
        pairs = [(r['year_start'], r['id']) for r in element_codes]
        data = {
            'ids': ids,
            'players': players,
            'expected_points': fetch_expected_points(cursor, season_start),
            'upcoming': fetch_upcoming_predictions(cursor, gameweek, gameweek + NEXT_FIXTURES - 1),
            'baselines': fetch_team_baselines(cursor),
            'teams': fetch_team_rows(cursor, years),
            'element_codes': element_codes,
            'history': fetch_history_rows(cursor, pairs),
            'momentum': {pid: fetch_momentum_row(cursor, pid) for pid in ids},
        }
    finally:
        conn.close()
    return build_player_context(gameweek, data)
