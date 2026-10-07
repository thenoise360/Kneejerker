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


def _possessive(name):
    return name + "'" if name.endswith('s') else name + "'s"


def _missing_reason(key, role):
    if not key:
        return 'A few squad players are missing.'
    # "out" is only true when nobody counted has any chance of playing.
    status = 'out' if all(p.get('chance', 0) == 0 for p in key) else 'out or doubtful'
    # A back-up goalkeeper is not named as "first-choice"; he counts as a regular defender.
    goalkeepers = [p for p in key if p.get('position') == GOALKEEPER and p.get('first_choice')]
    if role == 'defence' and goalkeepers:
        # The goalkeeper sentence is about the goalkeeper alone, so only their chance counts.
        keeper_status = 'out' if goalkeepers[0].get('chance', 0) == 0 else 'out or doubtful'
        return f'Their first-choice goalkeeper is {keeper_status}.'
    count = len(key)
    word = COUNT_WORDS.get(count, 'Several')
    group = 'main chance-creators' if role == 'attack' else 'regular defenders'
    if count == 1:
        return f'{word} of their {group} is {status}.'
    return f'{word} of their {group} are {status}.'


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

    # Absences are the only thing that moves the adjusted figures, so with
    # nobody missing there is nothing to blame, whatever the numbers say.
    if not strength['missing'] or (attack_tier is None and defence_tier is None):
        return {'headline': f'{team_name} are at full strength',
                'reason': _baseline_reason(strength)}

    # The larger effect wins; an exact tie goes to attack.
    if attack_tier is not None and (defence_tier is None or attack_change >= defence_change):
        role, area, tier = 'attack', 'attack', attack_tier
    else:
        role, area, tier = 'defence', 'defence', defence_tier

    qualifier = 'a little weaker' if tier == 'slight' else 'weaker'
    return {'headline': f"{_possessive(team_name)} {area} is {qualifier} this week",
            'reason': _missing_reason(_key_missing(strength['missing'], role), role)}


def _versus_usual(change, worse):
    """How this week compares with usual, using the same tiers as the headline."""
    tier = _tier(change)
    if tier is None:
        return 'the same as usual'
    return f"{'a little ' if tier == 'slight' else ''}{worse} than usual"


def _versus_league(strong, weak):
    """Where the usual level sits against the league, using the reason's limits."""
    if strong:
        return 'above average for the league'
    if weak:
        return 'below average for the league'
    return 'about average for the league'


def _tone(change):
    """'worse' when this week is noticeably or slightly down on usual, else 'same'.

    Absences only ever weaken a team, so 'better' is never returned today; the
    gauge still knows how to draw it if a future signal can lift a team.
    """
    return 'same' if _tier(change) is None else 'worse'


def gauge_summary(strength):
    """Gauge positions (as a share of the league average) and their spoken words.

    The needle and the words come from the same thresholds as strength_summary,
    so a gauge can never say "the same as usual" next to a "weaker" headline.
    Returns None when there is no league average or no goals conceded to divide by.
    """
    league = strength['league_scored']
    if not (league > 0) or not (strength['conceded'] > 0) or not (strength['conceded_adjusted'] > 0):
        return None
    attack_usual = strength['scored'] / league
    defence_usual = league / strength['conceded']      # higher means it concedes less
    conceded_ratio = _round(strength['conceded'] / league)
    attack_ratio = _round(attack_usual)
    attack_change = _drop(strength['scored'], strength['scored_adjusted'])
    defence_change = _rise(strength['conceded'], strength['conceded_adjusted'])
    attack_versus = _versus_usual(attack_change, 'weaker')
    defence_versus = _versus_usual(defence_change, 'leakier')
    attack_words = 'Attack: ' + ', '.join([
        attack_versus, _versus_league(attack_ratio >= STRONG_RATIO, attack_ratio <= WEAK_RATIO)])
    defence_words = 'Defence: ' + ', '.join([
        defence_versus, _versus_league(conceded_ratio <= WEAK_RATIO, conceded_ratio >= STRONG_RATIO)])
    # 'versus' is the visible label under each gauge, and 'tone' picks its colour.
    # Both come from the same tier as the headline, so they can never disagree with it.
    return {
        'attack': {'now': round(strength['scored_adjusted'] / league, 3), 'usual': round(attack_usual, 3),
                   'words': attack_words, 'versus': attack_versus.capitalize(), 'tone': _tone(attack_change)},
        'defence': {'now': round(league / strength['conceded_adjusted'], 3), 'usual': round(defence_usual, 3),
                    'words': defence_words, 'versus': defence_versus.capitalize(), 'tone': _tone(defence_change)},
    }
