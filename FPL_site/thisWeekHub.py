"""The This Week hub: composes squad, signals and rules into one payload (release 1).

build_hub is pure. get_this_week_hub is the live-route entry point: it calls the
official API for the squad, then reads everything else from the database.
"""
import logging

from FPL_site.dataModels import connect_db, season_start
from FPL_site.weekDecision import (
    fetch_availability_rows, fetch_fixture_rows, fixtures_by_team,
)
from FPL_site.playerContext import (
    fetch_expected_points, expected_points_map, fetch_team_rows, fetch_recent_point_rows,
    recent_points, option_facts,
)
from FPL_site.playerMomentum import fetch_upcoming_predictions, fetch_team_baselines
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


GUEST_CANDIDATES = 10   # guests see the top three; a few extra keep the list steady if one is a worry


def candidate_ids(squad_ids, predictions):
    """Whose summary facts the hub needs: the squad, or for a guest the highest expected points."""
    if squad_ids:
        return list(squad_ids)
    ranked = sorted(predictions, key=lambda pid: (-predictions[pid], pid))
    return ranked[:GUEST_CANDIDATES]


def _option_info(gameweek, ids, availability_rows, availability, facts):
    element_types = {r['id']: r['element_type'] for r in availability_rows}
    prices = {r['id']: r.get('now_cost') for r in availability_rows}
    recent = recent_points(facts['recent_rows'], gameweek)
    return {pid: option_facts(pid, availability, element_types, prices, gameweek, facts['upcoming'],
                              facts['baselines'], facts['team_shorts'], recent)
            for pid in ids if pid in availability}


def build_hub(gameweek, squad_context, availability_rows, predictions, fixtures, history_rows,
              facts=None):
    """predictions: {player_id: the official game's expected points}. facts: rows for the option summaries
    (team_shorts, upcoming, baselines, recent_rows); without them options carry no summary."""
    squad = squad_context.get('squad', []) if squad_context['status'] == 'ok' else []
    availability = hub_availability(availability_rows)
    signals = player_signals(history_rows)
    risks = {p['id']: assess_risk(availability[p['id']], signals.get(p['id']), gameweek)
             for p in squad if p['id'] in availability}
    injuries = resolve_injuries(squad, availability, risks)
    info = None
    if facts:
        ids = candidate_ids([p['id'] for p in squad], predictions)
        info = _option_info(gameweek, ids, availability_rows, availability, facts)
    captaincy = resolve_captaincy(squad, availability, predictions, fixtures, risks, info)
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
        predictions = expected_points_map(fetch_expected_points(cursor, season_start))
        fixtures = fixtures_by_team(fetch_fixture_rows(cursor, season_start, gameweek))
        history_rows = fetch_squad_history_rows(cursor, season_start, squad_ids, gameweek)
        facts = {
            'team_shorts': {t['id']: t['short_name'] for t in fetch_team_rows(cursor, [season_start])},
            'upcoming': fetch_upcoming_predictions(cursor, gameweek, gameweek),
            'baselines': fetch_team_baselines(cursor),
            'recent_rows': fetch_recent_point_rows(cursor, season_start,
                                                   candidate_ids(squad_ids, predictions), gameweek),
        }
    finally:
        conn.close()
    return availability_rows, predictions, fixtures, history_rows, facts


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
