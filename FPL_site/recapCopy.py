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


NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']


def _number_word(n):
    """'three' for 3, up to ten; digits above that."""
    return NUMBER_WORDS[n] if n <= 10 else str(n)


def _count_phrase(n, singular, plural):
    """'a goal' for 1, 'two goals' for 2. The article is 'an' before a vowel."""
    if n == 1:
        article = 'an' if singular[0] in 'aeiou' else 'a'
        return f'{article} {singular}'
    return f'{_number_word(n)} {plural}'


def _attacking_phrase(goals, assists):
    if goals == 3:
        goal_part = 'a hat-trick'
    elif goals:
        goal_part = _count_phrase(goals, 'goal', 'goals')
    else:
        goal_part = None
    assist_part = _count_phrase(assists, 'assist', 'assists') if assists else None
    if goal_part and assist_part:
        return f'{goal_part} and {assist_part}'
    return goal_part or assist_part


def _main_phrase(p):
    attacking = _attacking_phrase(p['goals'], p['assists'])
    if attacking:
        return attacking
    if p['penalties_saved']:
        return _count_phrase(p['penalties_saved'], 'penalty save', 'penalty saves')
    if p['clean_sheets'] and p['position'] in (GOALKEEPER, DEFENDER):
        if p['saves'] >= 3:
            return f"a clean sheet and {_number_word(p['saves'])} saves"
        return 'a clean sheet'
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
