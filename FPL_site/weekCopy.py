"""Deterministic phrase bank for the Week tab's empty states.

Pure functions: no randomness, no I/O. Tiers are set by explicit thresholds.
"""

# Hours after a deadline at which "being checked" becomes "taking longer".
CONFIRMING_SLOW_AFTER_HOURS = 96

_THIS_WEEK = {
    'pre_season': {
        'eyebrow': 'before kick-off',
        'title': 'The season is almost here',
        'body': "The season hasn't kicked off yet. Your first gameweek will show up "
                "here as soon as it's ready, and we'll go through it together.",
    },
    'off_season': {
        'eyebrow': 'off-season',
        'title': 'The season is taking a breather',
        'body': "The season is taking a breather, so there's nothing to decide right "
                "now. Whenever you come back, we'll pick things up together.",
    },
    'unavailable': {
        'eyebrow': 'just a moment',
        'title': "We can't see the latest gameweek yet",
        'body': "We can't reach the latest gameweek information right now. Nothing is "
                "wrong on your side, so please check back shortly.",
    },
}

_CONFIRMING_FAST = {
    'eyebrow': 'checking the results',
    'title': 'Final scores are being checked',
    'body': "The final scores are being checked. We'll show your next steps "
            "as soon as they're confirmed.",
}
_CONFIRMING_SLOW = {
    'eyebrow': 'checking the results',
    'title': 'Results are taking a little longer',
    'body': "Results are taking a little longer than usual to come through. "
            "Nothing for you to do, and we'll be here when they land.",
}


def this_week_empty_copy(mode, hours_since_deadline=None):
    """Copy for the This week panel, or None when the mode has a real panel."""
    if mode == 'confirming':
        slow = (hours_since_deadline is not None
                and hours_since_deadline >= CONFIRMING_SLOW_AFTER_HOURS)
        return dict(_CONFIRMING_SLOW if slow else _CONFIRMING_FAST)
    copy = _THIS_WEEK.get(mode)
    return dict(copy) if copy else None


def last_week_empty_copy(status, gameweek=None):
    """Copy for the Last week panel, or None for 'final' / unknown statuses."""
    if status == 'none':
        return {
            'eyebrow': 'last week',
            'title': 'No recap yet',
            'body': "There's no finished gameweek yet, so your first recap will "
                    "land after the first gameweek.",
        }
    if status == 'confirming':
        label = 'Gameweek %s' % gameweek if gameweek is not None else 'The latest gameweek'
        return {
            'eyebrow': 'last week',
            'title': 'Your recap is almost ready',
            'body': "%s's scores are still being checked. Your recap appears "
                    "once they're confirmed." % label,
        }
    return None
