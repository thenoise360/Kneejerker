"""Deterministic phrase bank for the Last week recap.

No randomness: every phrase is chosen by an explicit threshold, and each
threshold has a test on both sides of it.
"""

AVERAGE_LOW_BELOW = 45   # an average under this is a tough week for most
AVERAGE_HIGH_FROM = 60   # an average at or over this is a high-scoring week
FULL_BONUS = 3           # the most bonus points one match can give

GOALKEEPER, DEFENDER = 1, 2


def average_headline(average_score):
    if average_score < AVERAGE_LOW_BELOW:
        return 'A tough week for most players'
    if average_score < AVERAGE_HIGH_FROM:
        return 'A fairly typical week'
    return 'A high-scoring week'


def _attacking_phrase(goals, assists):
    if goals >= 3:
        return 'a hat-trick'
    if goals == 2:
        return 'two goals and an assist' if assists else 'two goals'
    if goals == 1 and assists:
        return 'a goal and an assist'
    return None


def _main_phrase(p):
    attacking = _attacking_phrase(p['goals'], p['assists'])
    if attacking:
        return attacking
    if p['penalties_saved']:
        return 'a penalty save'
    if p['goals'] == 1:
        return 'a goal'
    if p['assists'] >= 2:
        return f"{p['assists']} assists"
    if p['assists'] == 1:
        return 'an assist'
    if p['clean_sheets'] and p['position'] in (GOALKEEPER, DEFENDER):
        return f"a clean sheet and {p['saves']} saves" if p['saves'] >= 3 else 'a clean sheet'
    return 'a solid all-round game'


def standout_reason(p):
    """Why a player stood out, as a lowercase phrase that reads after 'with'."""
    phrase = _main_phrase(p)
    if p['bonus'] >= FULL_BONUS:
        phrase += ' and a full haul of bonus points'
    return phrase


def standout_sentence(p):
    return f"{p['name']} led the way with {standout_reason(p)}."


def recap_not_ready_copy(gameweek):
    return {
        'title': f"Gameweek {gameweek}'s recap is nearly ready",
        'body': "We're still pulling the scores together. Check back a little later.",
    }
