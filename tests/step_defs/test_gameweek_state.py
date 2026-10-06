from datetime import datetime, timedelta

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from FPL_site.weekResolver import resolve_week

scenarios('week/gameweek_state.feature')

NOW = datetime(2025, 10, 1, 12, 0, 0)
FMT = '%Y-%m-%dT%H:%M:%SZ'


def make_event(gw, days_from_now, finished=False, data_checked=False, deadline='auto'):
    if deadline == 'auto':
        deadline = (NOW + timedelta(days=days_from_now)).strftime(FMT)
    return {'id': gw, 'deadline_time': deadline,
            'finished': finished, 'data_checked': data_checked}


def past_done(gw):
    return make_event(gw, -(40 - gw), finished=True, data_checked=True)


@pytest.fixture
def context():
    return {'events': None, 'result': None}


@given('the season has gameweeks 1 to 3 and none has started')
def _pre_season(context):
    context['events'] = [make_event(gw, gw) for gw in (1, 2, 3)]


@given('gameweek 5 deadline has passed and its games are still being played')
def _live(context):
    context['events'] = [past_done(4), make_event(5, -1), make_event(6, 6)]


@given('gameweek 5 has finished but its data is not yet checked')
def _confirming(context):
    context['events'] = [past_done(4), make_event(5, -1, finished=True), make_event(6, 6)]


@given('gameweek 5 is complete and checked and gameweek 6 has not started')
def _between(context):
    context['events'] = [past_done(4), past_done(5), make_event(6, 3)]


@given('the final gameweek 38 is complete and checked')
def _off_season(context):
    context['events'] = [past_done(37), past_done(38)]


@given('the gameweek data could not be fetched')
def _fetch_failed(context):
    context['events'] = None


@given('gameweek 5 is live and gameweek 6 has no deadline')
def _missing_deadline(context):
    context['events'] = [past_done(4), make_event(5, -1), make_event(6, 0, deadline=None)]


@given('someone last looked during gameweek 3')
def _stale_visitor(context):
    context['last_seen_gameweek'] = 3


@given('gameweek 7 is complete and checked and gameweek 8 has not started')
def _returning_user_calendar(context):
    context['events'] = [past_done(g) for g in (3, 4, 5, 6, 7)] + [make_event(8, 2)]


@when('the week view is resolved')
def _resolve(context):
    context['result'] = resolve_week(context['events'], NOW)


@then(parsers.parse('this week is "{mode}" for gameweek {gw:d}'))
def _this_week(context, mode, gw):
    assert context['result']['this_week']['mode'] == mode
    assert context['result']['this_week']['gameweek'] == gw


@then(parsers.parse('this week is "{mode}" with no gameweek'))
def _this_week_none(context, mode):
    assert context['result']['this_week']['mode'] == mode
    assert context['result']['this_week']['gameweek'] is None
    assert context['result']['this_week']['deadline'] is None


@then(parsers.parse('last week is "{status}" for gameweek {gw:d}'))
def _last_week(context, status, gw):
    assert context['result']['last_week'] == {'status': status, 'gameweek': gw}


@then(parsers.parse('last week is "{status}"'))
def _last_week_status(context, status):
    assert context['result']['last_week'] == {'status': status, 'gameweek': None}
