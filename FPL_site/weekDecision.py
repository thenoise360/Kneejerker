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
        SELECT id, web_name, team, chance_of_playing_next_round, news,
               element_type, status, expected_goals, expected_assists, now_cost
        FROM bootstrapstatic_elements
        WHERE year_start = %s
          AND gameweek = (SELECT MAX(gameweek) FROM bootstrapstatic_elements WHERE year_start = %s)
    """, (year_start, year_start))
    return cursor.fetchall()


def fetch_team_expected_goals_rows(cursor, gameweek):
    cursor.execute("""
        SELECT team_id, expected_goals_mean FROM team_fixture_predictions
        WHERE gameweek = %s
    """, (gameweek,))
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


def involvement_predictions(availability_rows, team_goal_rows):
    """Expected goal involvement this gameweek for each player.

    A player's share of their team's season expected goals plus expected assists,
    times the goals we expect their team to score. A double gameweek adds up and
    a blank gameweek has no entry, so those players are skipped.
    """
    team_goals = {}
    for r in team_goal_rows:
        team_goals[r['team_id']] = team_goals.get(r['team_id'], 0.0) + float(r['expected_goals_mean'] or 0)

    def involvement(r):
        return float(r['expected_goals'] or 0) + float(r['expected_assists'] or 0)

    totals = {}
    for r in availability_rows:
        if r['status'] != 'u':
            totals[r['team']] = totals.get(r['team'], 0.0) + involvement(r)

    predictions = {}
    for r in availability_rows:
        team = r['team']
        if r['status'] == 'u' or team not in team_goals or not totals.get(team):
            continue
        predictions[r['id']] = involvement(r) / totals[team] * team_goals[team]
    return predictions


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
    # An unknown or missing captain gives None, so the copy never claims they look right.
    current_name = availability[captain]['name'] if captain in availability else None
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
        availability_rows = fetch_availability_rows(cursor, season_start)
        availability = availability_from_rows(availability_rows)
        predictions = involvement_predictions(availability_rows,
                                              fetch_team_expected_goals_rows(cursor, gameweek))
        fixtures = fixtures_by_team(fetch_fixture_rows(cursor, season_start, gameweek))
    finally:
        conn.close()

    # Upcoming picks are private until the deadline, so use the most recent
    # finished gameweek's team as the best known version of the squad.
    squad = []
    if isinstance(team_id, int) and last_gameweek:
        status, picks = fetch_entry_picks(team_id, last_gameweek)
        # A Free Hit squad lasts one week only, so it says nothing about next week's team.
        if status == 'ok' and picks.get('active_chip') != 'freehit':
            squad = squad_from_picks(picks)
    if squad:
        decision = biggest_decision(squad, availability, predictions, fixtures)
        based_on, squad_gameweek = 'your_team', last_gameweek
    else:
        decision = guest_biggest_decision(availability, predictions, fixtures)
        based_on, squad_gameweek = 'everyone', None
    return {'gameweek': gameweek, 'based_on': based_on, 'squad_gameweek': squad_gameweek,
            'decision': decision, 'message': None if decision else no_decision_copy()}
