"""The single biggest decision for the Week tab (release 1.4).

Fetchers read the database; the choosing is pure and tested with dicts.
"""
import logging

from FPL_site.dataModels import connect_db, season_start
from FPL_site.lastWeekRecap import fetch_entry_picks
from FPL_site.decisionCopy import (
    availability_decision, captain_decision, guest_captain_decision, no_decision_copy,
)

logger = logging.getLogger(__name__)

DOUBT_BELOW = 75   # chance of playing under this % makes a starter a doubt


#################################################
#                  Fetchers                     #
#################################################

def fetch_availability_rows(cursor, year_start):
    cursor.execute("""
        SELECT id, web_name, team, chance_of_playing_next_round, news
        FROM bootstrapstatic_elements
        WHERE year_start = %s
          AND gameweek = (SELECT MAX(gameweek) FROM bootstrapstatic_elements WHERE year_start = %s)
    """, (year_start, year_start))
    return cursor.fetchall()


def fetch_prediction_rows(cursor):
    cursor.execute("""
        SELECT player_id, predicted_performance FROM player_predictions
        WHERE gameweek = (SELECT MAX(gameweek) FROM player_predictions)
    """)
    return cursor.fetchall()


def fetch_fixture_rows(cursor, year_start, gameweek):
    cursor.execute("""
        SELECT f.team_h, f.team_a, f.team_h_difficulty, f.team_a_difficulty,
               th.name AS home_name, ta.name AS away_name
        FROM fixtures_fixtures f
        JOIN bootstrapstatic_teams th ON th.id = f.team_h AND th.year_start = f.year_start
        JOIN bootstrapstatic_teams ta ON ta.id = f.team_a AND ta.year_start = f.year_start
        WHERE f.year_start = %s AND f.event = %s
        ORDER BY f.kickoff_time
    """, (year_start, gameweek))
    return cursor.fetchall()


#################################################
#                 Pure shaping                  #
#################################################

def availability_from_rows(rows):
    return {r['id']: {'name': r['web_name'], 'team': r['team'],
                      'chance': r['chance_of_playing_next_round'], 'news': r['news'] or ''}
            for r in rows}


def predictions_from_rows(rows):
    return {r['player_id']: float(r['predicted_performance'])
            for r in rows if r['predicted_performance'] is not None}


def squad_from_picks(picks_data):
    """The official picks list uses 'element' for the player id; we use 'id'."""
    return [{'id': p['element'], 'is_captain': bool(p.get('is_captain')),
             'multiplier': p.get('multiplier', 0)}
            for p in (picks_data or {}).get('picks', [])]


def fixtures_by_team(rows):
    """Each team's first fixture of the gameweek. A team with no game is absent."""
    fixtures = {}
    for r in rows:
        fixtures.setdefault(r['team_h'], {'opponent': r['away_name'], 'is_home': True,
                                          'difficulty': r['team_h_difficulty']})
        fixtures.setdefault(r['team_a'], {'opponent': r['home_name'], 'is_home': False,
                                          'difficulty': r['team_a_difficulty']})
    return fixtures


#################################################
#                Pure choosing                  #
#################################################

def _is_doubt(player):
    return player['chance'] is not None and player['chance'] < DOUBT_BELOW


def _most_doubtful_starter(squad, availability):
    doubts = [(availability[p['id']], p) for p in squad
              if p['multiplier'] > 0 and p['id'] in availability and _is_doubt(availability[p['id']])]
    if not doubts:
        return None
    # Lowest chance first; the captain wins a tie; then name for stability.
    return min(doubts, key=lambda d: (d[0]['chance'], not d[1]['is_captain'], d[0]['name']))[0]


def _best_option(player_ids, availability, predictions, fixtures):
    options = [pid for pid in player_ids
               if pid in predictions and pid in availability
               and availability[pid]['team'] in fixtures and not _is_doubt(availability[pid])]
    if not options:
        return None
    return min(options, key=lambda pid: (-predictions[pid], availability[pid]['name']))


def biggest_decision(squad, availability, predictions, fixtures):
    doubt = _most_doubtful_starter(squad, availability)
    if doubt:
        return availability_decision(doubt['name'], doubt['chance'], doubt['news'])

    starters = [p['id'] for p in squad if p['multiplier'] > 0]
    best = _best_option(starters, availability, predictions, fixtures)
    if best is None:
        return None
    captain = next((p['id'] for p in squad if p['is_captain']), None)
    current_name = availability.get(captain, {}).get('name', availability[best]['name'])
    return captain_decision(availability[best]['name'], predictions[best], current_name,
                            fixtures.get(availability[best]['team']))


def guest_biggest_decision(availability, predictions, fixtures):
    best = _best_option(list(predictions), availability, predictions, fixtures)
    if best is None:
        return None
    return guest_captain_decision(availability[best]['name'], predictions[best],
                                  fixtures.get(availability[best]['team']))


#################################################
#          Live-route entry point               #
#################################################

def get_this_week_decision(gameweek, last_gameweek, team_id=None):
    """team_id: int, None for a guest, or 'invalid' (treated as a guest).

    Only a successful picks fetch gives a your-team decision. An unknown team
    and an outage both fall back to the guest decision.
    """
    conn = connect_db()
    if conn is None:
        logger.error("get_this_week_decision: could not connect to the database.")
        return {'gameweek': gameweek, 'based_on': 'everyone', 'squad_gameweek': None,
                'decision': None, 'message': no_decision_copy()}
    try:
        cursor = conn.cursor(dictionary=True)
        availability = availability_from_rows(fetch_availability_rows(cursor, season_start))
        predictions = predictions_from_rows(fetch_prediction_rows(cursor))
        fixtures = fixtures_by_team(fetch_fixture_rows(cursor, season_start, gameweek))
    finally:
        conn.close()

    # Upcoming picks are private until the deadline, so use the most recent
    # finished gameweek's team as the best known version of the squad.
    squad = []
    if isinstance(team_id, int) and last_gameweek:
        status, picks = fetch_entry_picks(team_id, last_gameweek)
        if status == 'ok':
            squad = squad_from_picks(picks)
    if squad:
        decision = biggest_decision(squad, availability, predictions, fixtures)
        based_on, squad_gameweek = 'your_team', last_gameweek
    else:
        decision = guest_biggest_decision(availability, predictions, fixtures)
        based_on, squad_gameweek = 'everyone', None
    return {'gameweek': gameweek, 'based_on': based_on, 'squad_gameweek': squad_gameweek,
            'decision': decision, 'message': None if decision else no_decision_copy()}
