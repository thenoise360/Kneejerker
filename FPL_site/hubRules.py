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

# The headline is the first of these rules that fires. Reorder here and nowhere else.
HEADLINE_RULES = ('starter_doubt', 'starter_blank', 'unused_free_transfers', 'captain_choice')


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
    return (chance is not None and chance < DOUBT_BELOW) or risks.get(pid, {}).get('tier') in WORTH_A_LOOK


def _ranked_options(player_ids, availability, predictions, fixtures, risks):
    options = [pid for pid in player_ids
               if pid in predictions and pid in availability
               and availability[pid]['team'] in fixtures and not _is_worry(pid, availability, risks)]
    options.sort(key=lambda pid: (-predictions[pid], availability[pid]['name']))
    return [{'id': pid, 'name': availability[pid]['name'],
             'expected_involvement': round(predictions[pid], 1),
             'fixture': fixtures[availability[pid]['team']]} for pid in options]


def resolve_captaincy(squad, availability, predictions, fixtures, risks):
    """Captaincy applies every week, so it always needs a look.

    With a team: their fit starters with a match. As a guest: the top three across everyone.
    """
    if squad:
        shortlist = _ranked_options([p['id'] for p in squad if p['starter']],
                                    availability, predictions, fixtures, risks)
    else:
        shortlist = _ranked_options(list(predictions), availability, predictions,
                                    fixtures, risks)[:GUEST_SHORTLIST]
    return {'state': NEEDS_LOOK,
            'suggested': shortlist[0] if shortlist else None,
            'vice': shortlist[1] if len(shortlist) > 1 else None,
            'shortlist': shortlist}


#################################################
#                  Headline                     #
#################################################

def _starter_doubt(ctx):
    starters = [p for p in ctx['injuries'].get('players', []) if p['starter']]
    if not starters:
        return None
    top = starters[0]
    return {'decision': 'injuries', 'reason_key': 'starter_doubt', 'player': top['name'],
            'tier': top['tier'], 'risk_pct': top['risk_pct']}


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
