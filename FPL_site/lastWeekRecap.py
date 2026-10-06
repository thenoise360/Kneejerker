"""Last Week recap for the Week tab (releases 1.2-1.3).

Fetchers take a database cursor and return raw rows. Everything below them
is pure, so the recap logic is tested without a database.
"""
import logging

from FPL_site.dataModels import connect_db, season_start
from FPL_site.recapCopy import average_headline, standout_reason, standout_sentence, recap_not_ready_copy

logger = logging.getLogger(__name__)

STANDOUT_COUNT = 3


#################################################
#                  Fetchers                     #
#################################################

def fetch_event_rows(cursor, year_start, gameweek):
    # bootstrapstatic_events holds duplicate rows for some gameweeks, so this
    # returns all of them and summarise_event() picks the real one.
    cursor.execute(
        "SELECT average_entry_score, highest_score, finished, data_checked "
        "FROM bootstrapstatic_events WHERE year_start = %s AND id = %s",
        (year_start, gameweek),
    )
    return cursor.fetchall()


def fetch_history_rows(cursor, year_start, gameweek):
    """One row per player per fixture in the gameweek (two in a double gameweek)."""
    cursor.execute("""
        SELECT h.element, h.fixture, h.total_points, h.minutes, h.goals_scored, h.assists,
               h.clean_sheets, h.saves, h.bonus, h.penalties_saved,
               e.web_name, e.element_type, t.name AS team_name,
               CASE WHEN h.was_home THEN f.team_h_difficulty ELSE f.team_a_difficulty END AS difficulty
        FROM elementsummary_history h
        JOIN bootstrapstatic_elements e
          ON e.id = h.element AND e.year_start = h.year_start
         AND e.gameweek = (SELECT MAX(gameweek) FROM bootstrapstatic_elements WHERE year_start = %s)
        JOIN bootstrapstatic_teams t ON t.id = e.team AND t.year_start = e.year_start
        LEFT JOIN fixtures_fixtures f ON f.id = h.fixture AND f.year_start = h.year_start
        WHERE h.year_start = %s AND h.round = %s
    """, (year_start, year_start, gameweek))
    return cursor.fetchall()


#################################################
#              Pure aggregation                 #
#################################################

def summarise_event(rows):
    """The gameweek's average and highest score, or None if it isn't scored yet."""
    scored = [r for r in rows if r.get('finished') and (r.get('average_entry_score') or 0) > 0]
    if not scored:
        return None
    best = max(scored, key=lambda r: r['average_entry_score'])
    highest = best.get('highest_score')
    return {'average_score': int(best['average_entry_score']),
            'highest_score': int(highest) if highest else None}


def _empty_player(row):
    return {'id': row['element'], 'name': row['web_name'], 'team': row['team_name'],
            'position': row['element_type'], 'points': 0, 'minutes': 0, 'goals': 0,
            'assists': 0, 'clean_sheets': 0, 'saves': 0, 'bonus': 0, 'penalties_saved': 0,
            'difficulty': None}


def aggregate_player_rows(rows):
    """Sum each player's fixture rows into one record per player."""
    players = {}
    seen = set()
    for row in rows:
        # The joined tables can hold duplicate rows, which repeat a fixture row; count each once.
        key = (row['element'], row.get('fixture'))
        if row.get('fixture') is not None:
            if key in seen:
                continue
            seen.add(key)
        player = players.setdefault(row['element'], _empty_player(row))
        player['points'] += row['total_points'] or 0
        player['minutes'] += row['minutes'] or 0
        player['goals'] += row['goals_scored'] or 0
        player['assists'] += row['assists'] or 0
        player['clean_sheets'] += row['clean_sheets'] or 0
        player['saves'] += row['saves'] or 0
        player['bonus'] += row['bonus'] or 0
        player['penalties_saved'] += row['penalties_saved'] or 0
        difficulty = row.get('difficulty')
        if difficulty is not None:
            current = player['difficulty']
            player['difficulty'] = difficulty if current is None else min(current, difficulty)
    return players


def top_performers(players, limit=STANDOUT_COUNT):
    """Highest scorers who actually played; ties broken by bonus, then name."""
    played = [p for p in players.values() if p['minutes'] > 0]
    ranked = sorted(played, key=lambda p: (-p['points'], -p['bonus'], p['name']))
    return ranked[:limit]


#################################################
#               Pure recap building             #
#################################################

def build_guest_recap(summary, performers):
    """The recap everyone sees: a verdict on the week plus one standout reason."""
    if summary is None or not performers:
        return None
    return {
        'headline': average_headline(summary['average_score']),
        'reason': standout_sentence(performers[0]),
        'average_score': summary['average_score'],
        'highest_score': summary['highest_score'],
        'standouts': [
            {'id': p['id'], 'name': p['name'], 'team': p['team'],
             'points': p['points'], 'reason': standout_reason(p)}
            for p in performers
        ],
    }


def recap_payload(gameweek, summary, players):
    """The JSON the recap route returns. 'personal' is filled in by release 1.3."""
    guest = build_guest_recap(summary, top_performers(players))
    if guest is None:
        return {'gameweek': gameweek, 'status': 'not_ready', 'guest': None,
                'message': recap_not_ready_copy(gameweek), 'personal': None}
    return {'gameweek': gameweek, 'status': 'ready', 'guest': guest,
            'message': None, 'personal': None}


#################################################
#          Live-route entry point               #
#################################################

def get_last_week_recap(gameweek):
    """Reads the finished gameweek from the database and builds the recap."""
    conn = connect_db()
    if conn is None:
        logger.error("get_last_week_recap: could not connect to the database.")
        return recap_payload(gameweek, None, {})
    try:
        cursor = conn.cursor(dictionary=True)
        summary = summarise_event(fetch_event_rows(cursor, season_start, gameweek))
        players = aggregate_player_rows(fetch_history_rows(cursor, season_start, gameweek))
    finally:
        conn.close()
    return recap_payload(gameweek, summary, players)
