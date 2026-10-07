"""A manager's squad as it stands for the coming gameweek (This Week hub, release 1).

Picks for the coming gameweek stay private until the deadline, so the squad is
the last finished gameweek's picks plus any transfers made since. Fetchers talk
to the official game's public API; everything else is pure and tested with dicts.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

import requests

from FPL_site.dataModels import FPL_API
from FPL_site.lastWeekRecap import fetch_entry_picks

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
STARTING_SLOTS = 11


#################################################
#                  Fetchers                     #
#################################################

def fetch_entry_transfers(entry_id):
    """Every transfer the team has made this season, same status contract as fetch_entry_picks."""
    try:
        response = requests.get(f'{FPL_API}/entry/{entry_id}/transfers/', timeout=TIMEOUT_SECONDS)
        if response.status_code == 200:
            return 'ok', response.json()
        if response.status_code == 404:
            return 'not_found', None
        return 'unavailable', None
    except Exception as exc:
        # Log the kind of failure only: the message can carry the URL, which holds the team number.
        logger.error("Transfers fetch failed: %s", type(exc).__name__)
        return 'unavailable', None


#################################################
#                 Pure shaping                  #
#################################################

def squad_from_picks(picks_data):
    """Slots 1-11 start. Multiplier can't be used: Bench Boost gives the bench a 1 too."""
    return [{'id': p['element'], 'slot': p['position'],
             'starter': p['position'] <= STARTING_SLOTS,
             'is_captain': bool(p.get('is_captain')), 'is_vice': bool(p.get('is_vice_captain'))}
            for p in (picks_data or {}).get('picks', [])]


def base_picks_gameweek(last_gameweek, last_picks):
    """A free hit team lasts one week, then the team from the week before comes back."""
    if (last_picks or {}).get('active_chip') == 'freehit' and last_gameweek > 1:
        return last_gameweek - 1
    return last_gameweek


def apply_transfers(squad, transfers, after_gameweek, skip_events=()):
    """Apply transfers made for gameweeks after the squad's own, oldest first.

    The incoming player takes the outgoing player's slot, so a starter stays a
    starter. Armbands don't move with a transfer. skip_events holds free hit
    weeks, whose transfers were undone when the week ended.
    """
    squad = [dict(p) for p in squad]
    relevant = [t for t in transfers or []
                if (t.get('event') or 0) > after_gameweek and t.get('event') not in skip_events]
    applied = []
    for t in sorted(relevant, key=lambda t: t.get('time') or ''):
        slot = next((p for p in squad if p['id'] == t['element_out']), None)
        if slot is None:
            logger.warning("Transfer out of a player not in the squad was skipped (gameweek %s)", t.get('event'))
            continue
        slot.update(id=t['element_in'], is_captain=False, is_vice=False)
        applied.append(t)
    return squad, applied


def bank_after(base_bank, applied):
    """Money left in tenths of a million. Never below zero, so copy can't show a negative bank."""
    bank = base_bank - sum(t['element_in_cost'] for t in applied) + sum(t['element_out_cost'] for t in applied)
    return max(bank, 0)


#################################################
#          Live-route entry point               #
#################################################

def get_squad_context(team_id, last_gameweek):
    """The squad, bank and which gameweek's picks it is based on, or a failure status."""
    if not last_gameweek:
        return {'status': 'unavailable'}
    # The two calls don't depend on each other, so run them side by side:
    # on a cold start each one can take seconds.
    with ThreadPoolExecutor(max_workers=2) as pool:
        picks_future = pool.submit(fetch_entry_picks, team_id, last_gameweek)
        transfers_future = pool.submit(fetch_entry_transfers, team_id)
        picks_status, last_picks = picks_future.result()
        transfers_status, transfers = transfers_future.result()
    if picks_status != 'ok':
        return {'status': picks_status}
    if transfers_status != 'ok':
        return {'status': 'unavailable'}

    base_gameweek = base_picks_gameweek(last_gameweek, last_picks)
    base_picks, skip_events = last_picks, ()
    if base_gameweek != last_gameweek:
        status, base_picks = fetch_entry_picks(team_id, base_gameweek)
        if status != 'ok':
            return {'status': 'unavailable'}
        skip_events = (last_gameweek,)

    squad, applied = apply_transfers(squad_from_picks(base_picks), transfers, base_gameweek, skip_events)
    bank = bank_after((base_picks.get('entry_history') or {}).get('bank', 0), applied)
    return {'status': 'ok', 'squad': squad, 'bank': bank, 'squad_gameweek': base_gameweek}
