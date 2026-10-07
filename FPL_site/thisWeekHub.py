"""The This Week hub: composes squad, signals and rules into one payload (release 1).

build_hub is pure. get_this_week_hub is the live-route entry point: it calls the
official API for the squad, then reads everything else from the database.
"""
import logging

from FPL_site.dataModels import connect_db, season_start
from FPL_site.weekDecision import (
    fetch_availability_rows, fetch_team_expected_goals_rows, fetch_fixture_rows,
    involvement_predictions, fixtures_by_team,
)
from FPL_site.squadContext import get_squad_context
from FPL_site.hubSignals import fetch_squad_history_rows, player_signals, assess_risk
from FPL_site.hubRules import (
    resolve_injuries, resolve_captaincy, select_headline, NOT_READY,
)

logger = logging.getLogger(__name__)


def hub_availability(rows):
    """Like weekDecision.availability_from_rows, plus status, which the risk check needs."""
    return {r['id']: {'name': r['web_name'], 'team': r['team'],
                      'chance': r['chance_of_playing_next_round'],
                      'status': r['status'], 'news': r['news'] or ''}
            for r in rows}


def build_hub(gameweek, squad_context, availability_rows, predictions, fixtures, history_rows):
    squad = squad_context.get('squad', []) if squad_context['status'] == 'ok' else []
    availability = hub_availability(availability_rows)
    signals = player_signals(history_rows)
    risks = {p['id']: assess_risk(availability[p['id']], signals.get(p['id']), gameweek)
             for p in squad if p['id'] in availability}
    injuries = resolve_injuries(squad, availability, risks)
    captaincy = resolve_captaincy(squad, availability, predictions, fixtures, risks)
    headline = select_headline({'squad': squad, 'availability': availability, 'fixtures': fixtures,
                                'injuries': injuries, 'captaincy': captaincy})
    return {
        'status': 'ready', 'gameweek': gameweek,
        'based_on': 'your_team' if squad else 'everyone',
        'team_status': squad_context['status'],
        'squad_gameweek': squad_context.get('squad_gameweek') if squad else None,
        'headline': headline,
        'decisions': {'injuries': injuries,
                      'transfers': {'state': NOT_READY},
                      'chips': {'state': NOT_READY},
                      'captaincy': captaincy},
    }


def _load_week_data(gameweek, squad_ids):
    """Everything the hub reads from the database, or None if it can't connect."""
    conn = connect_db()
    if conn is None:
        logger.error("get_this_week_hub: could not connect to the database.")
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        availability_rows = fetch_availability_rows(cursor, season_start)
        predictions = involvement_predictions(availability_rows,
                                              fetch_team_expected_goals_rows(cursor, gameweek))
        fixtures = fixtures_by_team(fetch_fixture_rows(cursor, season_start, gameweek))
        history_rows = fetch_squad_history_rows(cursor, season_start, squad_ids, gameweek)
    finally:
        conn.close()
    return availability_rows, predictions, fixtures, history_rows


def get_this_week_hub(gameweek, last_gameweek, team_id=None):
    """team_id: an int, None for a guest, or 'invalid'. Only an int calls the official API."""
    if isinstance(team_id, int):
        squad_context = get_squad_context(team_id, last_gameweek)
    else:
        squad_context = {'status': 'invalid' if team_id == 'invalid' else 'none'}
    squad_ids = [p['id'] for p in squad_context.get('squad', [])] if squad_context['status'] == 'ok' else []

    data = _load_week_data(gameweek, squad_ids)
    if data is None:
        return {'status': 'unavailable', 'gameweek': gameweek}
    return build_hub(gameweek, squad_context, *data)
