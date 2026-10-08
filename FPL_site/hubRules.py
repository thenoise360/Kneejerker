"""Rules for the This Week hub: a state per decision and the headline (release 1).

Pure: plain dicts in, plain dicts of states, keys and facts out. No prose and
no randomness, so the same week always gives the same answer.
"""

NEEDS_LOOK = 'needs_look'
NOTHING_TO_DO = 'nothing_to_do'
NEEDS_TEAM = 'needs_team'      # a guest: we need their team number first
NOT_READY = 'not_ready'        # this decision isn't built yet

WORTH_A_LOOK = ('confirmed', 'high', 'medium')
DOUBT_BELOW = 75               # same line as weekDecision: under 75% is a doubt
GUEST_SHORTLIST = 3

# Only these reasons mean "might not play". Bookings and early substitutions
# deserve a look in the injuries row, but a fit player isn't "a doubt" because of them.
AVAILABILITY_REASONS = ('ruled_out', 'official_doubt', 'missed_last_game')

# The headline is the first of these rules that fires. Reorder here and nowhere else.
HEADLINE_RULES = ('starter_doubt', 'starter_blank', 'unused_free_transfers', 'captain_choice')


def _availability_reason(risk):
    for reason in (risk or {}).get('reasons', []):
        if reason['key'] in AVAILABILITY_REASONS:
            return reason
    return None


#################################################
#                  Injuries                     #
#################################################

def resolve_injuries(squad, availability, risks):
    if not squad:
        return {'state': NEEDS_TEAM, 'players': []}
    players = [{'id': p['id'], 'name': availability[p['id']]['name'], 'starter': p['starter'],
                'is_captain': p['is_captain'], 'risk_pct': risks[p['id']]['pct'],
                'tier': risks[p['id']]['tier'], 'reasons': risks[p['id']]['reasons']}
               for p in squad
               if p['id'] in availability and risks.get(p['id'], {}).get('tier') in WORTH_A_LOOK]
    # Starters first, then the biggest risk; the captain wins a tie, then name, so the order never wobbles.
    players.sort(key=lambda x: (not x['starter'], -x['risk_pct'], not x['is_captain'], x['name']))
    for player in players:
        del player['is_captain']
    return {'state': NEEDS_LOOK if players else NOTHING_TO_DO, 'players': players}


#################################################
#                  Captaincy                    #
#################################################

def _is_worry(pid, availability, risks):
    chance = availability[pid]['chance']
    risk = risks.get(pid, {})
    return ((chance is not None and chance < DOUBT_BELOW)
            or (risk.get('tier') in WORTH_A_LOOK and _availability_reason(risk) is not None))


def _rank_key(pid, availability, predictions):
    # Highest expected points first; no stored value goes after everyone who has one.
    predicted = predictions.get(pid)
    return (predicted is None, -(predicted or 0.0), availability[pid]['name'])


def _option(pid, availability, predictions, info):
    facts = (info or {}).get(pid, {})
    predicted = predictions.get(pid)
    return {'id': pid, 'name': availability[pid]['name'],
            'team_short': facts.get('team_short'), 'position': facts.get('position'),
            'price': facts.get('price'),
            'expected_points': round(predicted, 1) if predicted is not None else None,
            'this_week': facts.get('this_week'),
            'recent_points': facts.get('recent_points', [])}


def _ranked_options(player_ids, availability, predictions, fixtures, risks, info=None):
    options = [pid for pid in player_ids
               if pid in availability and availability[pid]['team'] in fixtures
               and not _is_worry(pid, availability, risks)]
    options.sort(key=lambda pid: _rank_key(pid, availability, predictions))
    return [_option(pid, availability, predictions, info) for pid in options]


def _leaning(option):
    # We only lean on someone we have a number for.
    return option if option and option['expected_points'] is not None else None


def resolve_captaincy(squad, availability, predictions, fixtures, risks, info=None):
    """Captaincy applies every week, so it always needs a look.

    predictions: {player_id: expected points}. info: optional per-player summary
    facts (team_short, position, price, this_week, recent_points) from playerContext.

    With a team: their fit starters with a match, plus the rest of the squad as `others`.
    As a guest: the top three across everyone with a stored value, and no others.
    """
    others = []
    if squad:
        starters = [p['id'] for p in squad if p['starter']]
        shortlist = _ranked_options(starters, availability, predictions, fixtures, risks, info)
        listed = {o['id'] for o in shortlist}
        rest = [p['id'] for p in squad if p['id'] not in listed]
        rest.sort(key=lambda pid: _rank_key(pid, availability, predictions) if pid in availability else (True, 0, ''))
        others = [_option(pid, availability, predictions, info) for pid in rest if pid in availability]
    else:
        shortlist = _ranked_options(list(predictions), availability, predictions,
                                    fixtures, risks, info)[:GUEST_SHORTLIST]
    return {'state': NEEDS_LOOK,
            'suggested': _leaning(shortlist[0] if shortlist else None),
            'vice': _leaning(shortlist[1] if len(shortlist) > 1 else None),
            'shortlist': shortlist,
            'others': others}


#################################################
#                  Headline                     #
#################################################

def _starter_doubt(ctx):
    # Only a doubt about playing counts; the list is already in the order we want.
    for p in ctx['injuries'].get('players', []):
        reason = _availability_reason(p) if p['starter'] else None
        if reason:
            return {'decision': 'injuries', 'reason_key': 'starter_doubt', 'player': p['name'],
                    'reason': reason['key'], 'tier': p['tier'], 'risk_pct': p['risk_pct']}
    return None


def _starter_blank(ctx):
    if not ctx['fixtures']:
        return None   # no fixture data at all says nothing about blanks
    availability = ctx['availability']
    names = sorted(availability[p['id']]['name'] for p in ctx['squad']
                   if p['starter'] and p['id'] in availability
                   and availability[p['id']]['team'] not in ctx['fixtures'])
    if not names:
        return None
    return {'decision': 'transfers', 'reason_key': 'starter_blank', 'player': names[0], 'players': names}


def _unused_free_transfers(ctx):
    # Release 4 supplies free_transfers; until then this rule never fires.
    count = ctx.get('free_transfers')
    if not count:
        return None
    return {'decision': 'transfers', 'reason_key': 'unused_free_transfers', 'player': None, 'count': count}


def _captain_choice(ctx):
    suggested = ctx['captaincy'].get('suggested')
    if suggested is None:
        return {'decision': 'captaincy', 'reason_key': 'captain_no_prediction', 'player': None}
    return {'decision': 'captaincy', 'reason_key': 'captain_choice', 'player': suggested['name']}


RULE_CHECKS = {
    'starter_doubt': _starter_doubt,
    'starter_blank': _starter_blank,
    'unused_free_transfers': _unused_free_transfers,
    'captain_choice': _captain_choice,
}


def select_headline(ctx, rules=HEADLINE_RULES):
    for name in rules:
        headline = RULE_CHECKS[name](ctx)
        if headline:
            return headline
    return None
