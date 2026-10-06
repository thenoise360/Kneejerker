"""Pure resolver that turns the FPL gameweek calendar into a Week tab view state.

No I/O here: callers pass in the bootstrap-static `events` list and the current
UTC time, and get back what "this week" and "last week" mean right now.
"""
from datetime import datetime

DEADLINE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
NO_LAST_WEEK = {'status': 'none', 'gameweek': None, 'deadline': None}


def _parse_deadline(raw):
    """Return a datetime for a deadline string, or None if missing/unparseable."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, DEADLINE_FORMAT)
    except (ValueError, TypeError):
        return None


def _dated_events(events):
    """Return [(deadline_dt, event)] for usable events, sorted by deadline."""
    if not isinstance(events, list):
        return []
    dated = []
    for event in events:
        if not isinstance(event, dict):
            continue
        deadline_dt = _parse_deadline(event.get('deadline_time'))
        if deadline_dt is not None:
            dated.append((deadline_dt, event))
    return sorted(dated, key=lambda pair: pair[0])


def _this_week(mode, event=None):
    return {
        'mode': mode,
        'gameweek': event.get('id') if event else None,
        'deadline': event.get('deadline_time') if event else None,
    }


def _last_week(passed, this_week_gameweek):
    """Latest passed, finished event that is not this week's gameweek."""
    for _, event in reversed(passed):
        if event.get('finished') and event.get('id') != this_week_gameweek:
            status = 'final' if event.get('data_checked') else 'confirming'
            return {'status': status, 'gameweek': event.get('id'),
                    'deadline': event.get('deadline_time')}
    return dict(NO_LAST_WEEK)


def _resolve_this_week(passed, upcoming):
    current = passed[-1][1]
    if not current.get('finished'):
        return _this_week('live', current)
    if not current.get('data_checked'):
        return _this_week('confirming', current)
    if upcoming:
        return _this_week('upcoming', upcoming[0][1])
    return _this_week('off_season')


def resolve_week(events, now):
    dated = _dated_events(events)
    if not dated:
        return {'this_week': _this_week('unavailable'),
                'last_week': dict(NO_LAST_WEEK)}

    passed = [pair for pair in dated if pair[0] <= now]
    upcoming = [pair for pair in dated if pair[0] > now]

    if not passed:
        return {'this_week': _this_week('pre_season', upcoming[0][1]),
                'last_week': dict(NO_LAST_WEEK)}

    this_week = _resolve_this_week(passed, upcoming)
    return {'this_week': this_week,
            'last_week': _last_week(passed, this_week['gameweek'])}
