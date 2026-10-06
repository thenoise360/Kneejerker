import os; os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import re
import pytest
from flask import render_template
from FPL_site import app
from FPL_site.weekCopy import this_week_empty_copy, last_week_empty_copy


def _state(mode, gw=None, last='final', last_gw=None, deadline=None):
    return {'this_week': {'mode': mode, 'gameweek': gw, 'deadline': deadline},
            'last_week': {'status': last, 'gameweek': last_gw}}


def render(state, **extra):
    with app.test_request_context('/this-week'):
        return render_template(
            'partials/week_v2.html', week_state=state,
            this_week_copy=this_week_empty_copy(state['this_week']['mode']),
            last_week_copy=last_week_empty_copy(state['last_week']['status'],
                                                state['last_week']['gameweek']),
            **extra)


@pytest.mark.parametrize('mode,expected', [
    ('live', 'live'), ('upcoming', 'closed'), ('confirming', 'none'),
    ('pre_season', 'none'), ('off_season', 'none'), ('unavailable', 'none'),
])
def test_mode_maps_to_data_gw_state(mode, expected):
    html = render(_state(mode, gw=5))
    assert 'data-gw-state="%s"' % expected in html


def test_gameweek_number_attribute():
    assert 'data-gw-number="12"' in render(_state('live', gw=12))
    assert 'data-gw-number=""' in render(_state('off_season'))


def test_keeps_home_js_hooks():
    html = render(_state('live', gw=3))
    for hook in ['id="this-week-view"', 'id="gw-panel-live"', 'id="gw-panel-closed"',
                 'id="gw-panel-none"', 'id="last-week-view"', 'id="live-gameweek-content"',
                 'id="live-team-id-form"']:
        assert hook in html


def test_pre_season_copy_appears():
    html = render(_state('pre_season'))
    copy = this_week_empty_copy('pre_season')
    assert copy['title'] in html and copy['eyebrow'] in html
    assert "kicked off" in html


def test_closed_panel_content():
    html = render(_state('upcoming', gw=9))
    assert 'Your decisions for gameweek 9' in html
    assert "This week&#39;s 5 decisions" in html or "This week's 5 decisions" in html
    assert 'Coming soon' in html


def test_last_week_final_renders_recap_slot():
    html = render(_state('upcoming', gw=9, last='final', last_gw=5))
    assert 'id="last-week-recap-slot"' in html
    assert 'data-gameweek="5"' in html
    assert 'How gameweek 5 went' in html


def test_last_week_confirming_has_no_gameweek_to_fetch():
    html = render(_state('upcoming', gw=9, last='confirming', last_gw=5))
    assert 'data-gameweek=""' in html


def test_last_week_copy_rendered_when_not_final():
    html = render(_state('upcoming', gw=9, last='none'))
    assert 'first recap' in html
    assert 'recap</h' not in html


def test_old_cards_absent():
    html = render(_state('live', gw=3, last_gw=2))
    assert 'Friend activity feed' not in html and 'Team of the Week' not in html


def test_no_acronyms_in_partial_copy():
    html = render(_state('live', gw=3, last_gw=2))
    visible = re.sub(r'<[^>]+>', ' ', html)
    # the live panel's pre-existing form copy is carried over verbatim
    visible = visible.replace('FPL team', '')
    assert not re.search(r'\b(GW|xG|xA)\b', visible)


def test_flag_off_home_keeps_old_markup():
    with app.test_request_context('/this-week'):
        html = render_template('home.html', is_ajax=True,
                               gw_state={'state': 'none', 'gameweek': None})
    assert 'Friend activity feed' in html
    assert 'Team of the Week' in html


def test_flag_on_home_uses_partial():
    with app.test_request_context('/this-week'):
        html = render_template('home.html', is_ajax=True, week_v2=True,
                               week_state=_state('upcoming', gw=4),
                               this_week_copy=None, last_week_copy=None)
    assert 'Friend activity feed' not in html
    assert 'Your decisions for gameweek 4' in html
    assert 'scripts/home.js' in html and 'content/home.css' in html


def test_v2_has_welcome_banner_and_personal_slot():
    html = render(_state('upcoming', gw=6, last='final', last_gw=5))
    banner = re.search(r'<div id="welcome-back-banner"[^>]*>', html)
    assert banner and 'hidden' in banner.group(0)
    assert 'id="personal-recap-slot"' in html


def test_last_week_view_carries_deadline_and_this_week_gameweek():
    # _state only sets this week's deadline, so build the state by hand here.
    state = {'this_week': {'mode': 'upcoming', 'gameweek': 6, 'deadline': None},
             'last_week': {'status': 'final', 'gameweek': 5,
                           'deadline': '2026-09-20T10:00:00Z'}}
    html = render(state)
    assert 'data-deadline="2026-09-20T10:00:00Z"' in html
    assert 'data-this-week-gameweek="6"' in html
