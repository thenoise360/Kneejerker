from datetime import datetime

from FPL_site.weekResolver import resolve_week

NOW = datetime(2025, 10, 1, 12, 0, 0)


def ev(gw, deadline, finished=False, data_checked=False):
    return {'id': gw, 'deadline_time': deadline,
            'finished': finished, 'data_checked': data_checked}


def test_unsorted_events_are_ordered_by_deadline():
    events = [
        ev(6, '2025-10-10T10:00:00Z'),
        ev(4, '2025-09-15T10:00:00Z', True, True),
        ev(5, '2025-09-25T10:00:00Z', True, True),
    ]
    result = resolve_week(events, NOW)
    assert result['this_week'] == {'mode': 'upcoming', 'gameweek': 6,
                                   'deadline': '2025-10-10T10:00:00Z'}
    assert result['last_week'] == {'status': 'final', 'gameweek': 5,
                                   'deadline': '2025-09-25T10:00:00Z'}


def test_all_deadlines_invalid_is_unavailable():
    events = [ev(1, None), ev(2, 'not-a-date'), ev(3, '')]
    result = resolve_week(events, NOW)
    assert result['this_week'] == {'mode': 'unavailable', 'gameweek': None, 'deadline': None}
    assert result['last_week'] == {'status': 'none', 'gameweek': None, 'deadline': None}


def test_deadline_equal_to_now_counts_as_passed():
    result = resolve_week([ev(1, '2025-10-01T12:00:00Z')], NOW)
    assert result['this_week']['mode'] == 'live'
    assert result['this_week']['gameweek'] == 1


def test_empty_and_non_list_events_are_unavailable():
    for bad in (None, [], 'oops', {}):
        assert resolve_week(bad, NOW)['this_week']['mode'] == 'unavailable'


def test_pre_season_uses_earliest_deadline_even_if_unsorted():
    events = [ev(2, '2025-11-01T10:00:00Z'), ev(1, '2025-10-20T10:00:00Z')]
    result = resolve_week(events, NOW)
    assert result['this_week'] == {'mode': 'pre_season', 'gameweek': 1,
                                   'deadline': '2025-10-20T10:00:00Z'}
    assert result['last_week']['status'] == 'none'


def test_confirming_current_gameweek_leaves_previous_as_last_week():
    events = [ev(4, '2025-09-15T10:00:00Z', True, True),
              ev(5, '2025-09-25T10:00:00Z', True, False)]
    result = resolve_week(events, NOW)
    assert result['this_week']['mode'] == 'confirming'
    assert result['last_week'] == {'status': 'final', 'gameweek': 4,
                                   'deadline': '2025-09-15T10:00:00Z'}


def test_last_week_includes_its_deadline():
    from datetime import datetime
    from FPL_site.weekResolver import resolve_week
    events = [
        {'id': 1, 'deadline_time': '2026-08-15T10:00:00Z', 'finished': True, 'data_checked': True},
        {'id': 2, 'deadline_time': '2026-08-22T10:00:00Z', 'finished': False, 'data_checked': False},
    ]
    state = resolve_week(events, datetime(2026, 8, 20))
    assert state['last_week'] == {'status': 'final', 'gameweek': 1, 'deadline': '2026-08-15T10:00:00Z'}


def test_no_last_week_has_no_deadline():
    from datetime import datetime
    from FPL_site.weekResolver import resolve_week
    assert resolve_week([], datetime(2026, 8, 20))['last_week']['deadline'] is None
