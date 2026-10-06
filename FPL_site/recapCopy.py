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


CAPTAIN_PAID_OFF_FROM = 6   # captain's own points (before doubling)
BIG_PICK_FROM = 8
SOLID_PICK_FROM = 4
KIND_FIXTURE_UP_TO = 2      # fixture difficulty 1-2 is a kind fixture
BLANK_UP_TO = 2             # 2 points or fewer counts as a blank


def _starters(squad):
    return [p for p in squad if p['multiplier'] > 0]


def _best(players):
    # Highest points; ties broken by name so the choice is always the same.
    return min(players, key=lambda p: (-p['points'], p['name'])) if players else None


def pick_one_thing_right(squad):
    """Something to celebrate in a personal recap, even after a bad week."""
    starters = _starters(squad)
    captain = next((p for p in starters if p['is_captain']), None)
    if captain and captain['points'] >= CAPTAIN_PAID_OFF_FROM:
        reason = f"Captaining {captain['name']} paid off: {captain['points']} points"
        if captain['multiplier'] == 3:
            reason += ", and you got them triple."
        elif captain['multiplier'] == 2:
            reason += ", and you got them double."
        else:
            reason += "."
        return {'tier': 'captain', 'title': 'Your captain call', 'reason': reason}

    best = _best(starters)
    if best and best['points'] >= BIG_PICK_FROM:
        return {'tier': 'big_pick', 'title': 'A smart pick',
                'reason': f"Having {best['name']} in your team paid off with {best['points']} points."}

    sound = [p for p in starters if p['minutes'] > 0 and p['difficulty'] is not None
             and p['difficulty'] <= KIND_FIXTURE_UP_TO and p['points'] <= BLANK_UP_TO]
    if sound:
        pick = min(sound, key=lambda p: p['name'])
        return {'tier': 'sound_blank', 'title': 'Sound thinking',
                'reason': f"Backing {pick['name']} for a kind fixture was the right idea, even "
                          f"though it didn't land this time. Keep trusting that logic."}

    if best and best['points'] >= SOLID_PICK_FROM:
        return {'tier': 'solid_pick', 'title': 'A solid pick',
                'reason': f"{best['name']} came through for you with {best['points']} points."}

    return {'tier': 'showed_up', 'title': 'You showed up',
            'reason': "Weeks like this happen to everyone. The next deadline is a fresh start, "
                      "and we'll help you make the most of it."}


WELL_ABOVE_FROM = 15   # points above the average
ABOVE_FROM = 5
BELOW_FROM = -5        # 5+ under the average is "below"
TOUGH_FROM = -15       # 15+ under is a tough week


def score_verdict(score, average):
    diff = score - average
    if diff >= WELL_ABOVE_FROM:
        return {'tier': 'well_above', 'text': 'Well above average. A cracking week.'}
    if diff >= ABOVE_FROM:
        return {'tier': 'above', 'text': 'Above average. Nicely done.'}
    if diff > BELOW_FROM:
        return {'tier': 'about', 'text': 'Right around the average. A steady week.'}
    if diff > TOUGH_FROM:
        return {'tier': 'below', 'text': "A little below average. It happens, and one week "
                                         "doesn't define a season."}
    return {'tier': 'tough', 'text': "A tough week. They happen to everyone, and there's "
                                     "plenty of season left."}


def team_not_found_copy(gameweek):
    return {'title': "We couldn't find that team",
            'body': f"There's no team with that number for gameweek {gameweek}. Double-check the "
                    f"number, or if you joined after that, your first recap is on its way."}
