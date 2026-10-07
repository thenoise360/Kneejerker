"""Pure player momentum: is a player rising, steady or cooling this week?

Built only from the team's upcoming fixtures and what is changing around the
player (teammates back or out). Never from the player's own minutes, the
Influence, Creativity and Threat index, or form. No database access here.
"""

from FPL_site.momentumCopy import momentum_reason

FIXTURE_WINDOW = 3                 # gameweeks ahead
FIXTURE_CHANGE_FROM = 0.10         # 10% easier or harder than an average opponent
KEY_TEAMMATE_SHARE = 0.15          # share of team expected goals + assists
OUT_BELOW_CHANCE = 50              # chance of playing below this = out
ATTACKING = (3, 4)                 # midfielder, forward

SIGNAL_ORDER = ('fixtures', 'teammates', 'position', 'manager')


def _round(value):
    # Rounding stops float noise tipping a boundary the wrong way.
    return round(value, 9)


def _signal(key, direction, reason, magnitude):
    return {'key': key, 'direction': direction, 'reason': reason, 'magnitude': magnitude}


def not_tracked(key):
    return {'key': key, 'direction': 'not_tracked', 'reason': None, 'magnitude': 0}


def fixtures_signal(position, upcoming, baseline_for, baseline_against):
    if not upcoming:
        return _signal('fixtures', 'same', 'no game this week', 0)
    if position in ATTACKING:
        baseline = baseline_for
        average = sum(f['own_mean'] for f in upcoming) / len(upcoming)
        change = (average - baseline) / baseline if baseline else 0.0
    else:
        # Defenders and goalkeepers want opponents who score less than usual.
        baseline = baseline_against
        average = sum(f['opp_mean'] for f in upcoming) / len(upcoming)
        change = (baseline - average) / baseline if baseline else 0.0
    change = _round(change)
    magnitude = abs(change)
    if change >= FIXTURE_CHANGE_FROM:
        return _signal('fixtures', 'up', 'kinder fixtures coming up', magnitude)
    if change <= -FIXTURE_CHANGE_FROM:
        return _signal('fixtures', 'down', 'tougher fixtures coming up', magnitude)
    return _signal('fixtures', 'same', 'fixtures look about average', magnitude)


def _is_key(teammate):
    share = _round(teammate.get('share') or 0)
    return share >= KEY_TEAMMATE_SHARE and teammate.get('status') != 'u'


def _is_back(teammate):
    chance = teammate.get('chance')
    return not teammate.get('played_last') and (chance is None or chance >= OUT_BELOW_CHANCE)


def _is_out(teammate):
    chance = teammate.get('chance')
    return bool(teammate.get('played_last')) and chance is not None and chance < OUT_BELOW_CHANCE


def teammates_signal(player_id, teammates):
    key = [t for t in teammates if t.get('id') != player_id and _is_key(t)]
    back = [t for t in key if _is_back(t)]
    out = [t for t in key if _is_out(t)]
    magnitude = _round(sum(t['share'] for t in back + out))
    if len(back) > len(out):
        reason = '%s is back in the team' % back[0]['name'] if len(back) == 1 else 'key teammates are back'
        return _signal('teammates', 'up', reason, magnitude)
    if len(out) > len(back):
        reason = '%s is out' % out[0]['name'] if len(out) == 1 else 'key teammates are out'
        return _signal('teammates', 'down', reason, magnitude)
    return _signal('teammates', 'same', 'no change around them', magnitude)


def _label(total):
    if total >= 1:
        return 'Rising'
    if total <= -1:
        return 'Cooling'
    return 'Steady'


def player_momentum(fixtures, teammates):
    """fixtures and teammates are already-built signals. Returns label, reason, signals, score."""
    signals = [fixtures, teammates, not_tracked('position'), not_tracked('manager')]
    step = {'up': 1, 'down': -1}
    total = sum(step.get(s['direction'], 0) for s in signals)
    label = _label(total)
    signed = sum(step.get(s['direction'], 0) * s['magnitude'] for s in signals)
    wanted = 'up' if label == 'Rising' else 'down'
    strongest = None
    if label != 'Steady':
        # max() keeps the first of equals, so ties go to the earlier signal.
        strongest = max((s for s in signals if s['direction'] == wanted),
                        key=lambda s: s['magnitude'])
    return {'label': label,
            'reason': momentum_reason(label, strongest),
            'signals': signals,
            'score': total + 0.1 * signed}
