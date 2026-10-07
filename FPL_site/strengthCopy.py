"""Deterministic phrase bank for the Team page's "how strong are they this week" verdict.

No randomness: every phrase is chosen by an explicit threshold, and each
threshold has a test on both sides of it. No digits and no acronyms in any output.
"""

NOTICEABLE_FROM = 0.15    # a change of this size or more is a noticeable weakening
SLIGHT_FROM = 0.05        # a change of this size or more is a slight weakening
KEY_PLAYER_SHARE = 0.10   # a missing player with at least this share of the team is "key"
STRONG_RATIO = 1.15       # at or over this, against the league average, is strong
WEAK_RATIO = 0.87         # at or under this, against the league average, is weak

GOALKEEPER = 1
COUNT_WORDS = {1: 'One', 2: 'Two'}


def _round(value):
    # Rounding stops float noise (0.15000000000000002) tipping a boundary the wrong way.
    return round(value, 9)


def _drop(raw, adjusted):
    """How far goals scored fall once absences are counted, as a share of the raw figure."""
    if raw <= 0:
        return 0.0
    return _round((raw - adjusted) / raw)


def _rise(raw, adjusted):
    """How far goals conceded rise once absences are counted, as a share of the raw figure."""
    if raw <= 0:
        return 0.0
    return _round((adjusted - raw) / raw)


def _tier(change):
    """'noticeable', 'slight' or None."""
    if change >= NOTICEABLE_FROM:
        return 'noticeable'
    if change >= SLIGHT_FROM:
        return 'slight'
    return None


def _key_missing(missing, role):
    return [p for p in missing if p['role'] == role and p['share'] >= KEY_PLAYER_SHARE]


def _missing_reason(key, role):
    if role == 'defence' and any(p.get('position') == GOALKEEPER for p in key):
        return 'Their first-choice goalkeeper is out.'
    if not key:
        return 'A few squad players are missing.'
    count = len(key)
    word = COUNT_WORDS.get(count, 'Several')
    group = 'main chance-creators' if role == 'attack' else 'regular defenders'
    if count == 1:
        return f'{word} of their {group} is out.'
    return f'{word} of their {group} are out.'


def _baseline_reason(strength):
    league = strength['league_scored']
    attack_ratio = _round(strength['scored'] / league) if league > 0 else 1.0
    defence_ratio = _round(strength['conceded'] / league) if league > 0 else 1.0

    if attack_ratio >= STRONG_RATIO:
        attack = 'Strong going forward'
    elif attack_ratio <= WEAK_RATIO:
        attack = 'Short of goals'
    else:
        attack = 'Steady going forward'

    if defence_ratio <= WEAK_RATIO:
        defence = 'solid at the back'
    elif defence_ratio >= STRONG_RATIO:
        defence = 'leaky at the back'
    else:
        defence = 'steady at the back'

    return f'{attack}, {defence}.'


def strength_summary(team_name, strength):
    """One headline and one reason for a team's strength this week."""
    attack_change = _drop(strength['scored'], strength['scored_adjusted'])
    defence_change = _rise(strength['conceded'], strength['conceded_adjusted'])
    attack_tier, defence_tier = _tier(attack_change), _tier(defence_change)

    if attack_tier is None and defence_tier is None:
        return {'headline': f'{team_name} are at full strength',
                'reason': _baseline_reason(strength)}

    # The larger effect wins; an exact tie goes to attack.
    if attack_tier is not None and (defence_tier is None or attack_change >= defence_change):
        role, area, tier = 'attack', 'attack', attack_tier
    else:
        role, area, tier = 'defence', 'defence', defence_tier

    qualifier = 'a little weaker' if tier == 'slight' else 'weaker'
    return {'headline': f"{team_name}'s {area} is {qualifier} this week",
            'reason': _missing_reason(_key_missing(strength['missing'], role), role)}
