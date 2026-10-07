import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import re
import pytest
from flask import render_template

from FPL_site import app
import FPL_site.views as views

STATE = {'this_week': {'mode': 'upcoming', 'gameweek': 6, 'deadline': '2026-10-10T10:00:00Z'},
         'last_week': {'status': 'final', 'gameweek': 5, 'deadline': '2026-10-03T10:00:00Z'}}

OPTION = {'id': 2, 'name': 'Haaland', 'expected_involvement': 1.4,
          'fixture': {'opponent': 'Burnley', 'is_home': False, 'difficulty': 2}}
VICE = dict(OPTION, id=3, name='Salah')


def hub(**overrides):
    base = {'status': 'ready', 'gameweek': 6, 'based_on': 'your_team', 'team_status': 'ok',
            'squad_gameweek': 5,
            'headline': {'decision': 'injuries', 'reason_key': 'starter_doubt', 'player': 'Rice',
                         'tier': 'high', 'risk_pct': 75},
            'decisions': {
                'injuries': {'state': 'needs_look', 'players': [
                    {'id': 1, 'name': 'Rice', 'starter': True, 'risk_pct': 75, 'tier': 'high',
                     'reasons': [{'key': 'official_doubt', 'chance': 25, 'news': 'Knock'}]}]},
                'transfers': {'state': 'not_ready'}, 'chips': {'state': 'not_ready'},
                'captaincy': {'state': 'needs_look', 'suggested': OPTION, 'vice': VICE,
                              'shortlist': [OPTION, VICE]}}}
    base.update(overrides)
    return base


def render(hub_payload):
    with app.test_request_context('/this-week'):
        return render_template('partials/week_v2.html', week_state=STATE, this_week_copy=None,
                               last_week_copy=None, hub_enabled=True, hub=hub_payload)


def test_headline_and_rows_render():
    html = render(hub())
    assert 'id="this-week-hub"' in html and 'id="hub-body"' in html
    assert 'Rice is a doubt for this gameweek' in html
    assert 'data-key="injuries" data-state="needs_look"' in html
    assert 'Our lean: Haaland, with Salah as vice' in html
    assert 'data-key="transfers"' not in html   # not built yet, so not shown
    assert 'More decisions are on the way' in html


def test_states_pair_an_icon_with_words():
    html = render(hub())
    assert re.search(r'<span aria-hidden="true">[^<]+</span>\s*Needs a look', html)


def test_nothing_to_do_and_guest_states():
    payload = hub(based_on='everyone', team_status='none')
    payload['decisions']['injuries'] = {'state': 'needs_team', 'players': []}
    html = render(payload)
    assert 'Add your team number below to check your players' in html
    assert 'id="hub-team-form"' in html and 'method="get"' in html
    fit = hub()
    fit['decisions']['injuries'] = {'state': 'nothing_to_do', 'players': []}
    assert 'Nothing to do this week' in render(fit)


def test_team_form_hidden_for_a_known_team():
    assert 'id="hub-team-form"' not in render(hub())


@pytest.mark.parametrize('team_status,phrase', [
    ('not_found', "couldn't find that team number"),
    ('unavailable', "couldn't reach the official game"),
    ('invalid', 'numbers only'),
])
def test_team_problems_are_explained_kindly(team_status, phrase):
    html = render(hub(based_on='everyone', team_status=team_status))
    assert phrase in html


def test_unavailable_hub_is_calm():
    html = render({'status': 'unavailable', 'gameweek': 6})
    assert "We couldn't load this week's decisions" in html


def test_no_acronyms_in_any_state():
    payload = hub()
    payload['headline'] = {'decision': 'transfers', 'reason_key': 'starter_blank', 'player': 'A',
                           'players': ['A', 'B']}
    for html in (render(payload), render(hub(based_on='everyone', team_status='invalid'))):
        text = re.sub(r'<[^>]+>', ' ', html)
        for pattern in [r'\bGW\s?\d', r'\bFPL\b', r'\bVC\b', r'\bpts\b', r'\bEO\b', r'\bxG\b']:
            assert not re.search(pattern, text), pattern


def test_flag_off_keeps_the_old_decision_slot():
    with app.test_request_context('/this-week'):
        html = render_template('partials/week_v2.html', week_state=STATE,
                               this_week_copy=None, last_week_copy=None)
    assert 'id="decision-slot"' in html and 'id="this-week-hub"' not in html


def test_page_route_builds_the_hub_only_when_flag_on(monkeypatch):
    calls = []
    monkeypatch.setattr(views, 'get_week_view_state', lambda: STATE)
    monkeypatch.setattr(views, 'get_this_week_hub',
                        lambda gw, last, team_id=None: calls.append((gw, last, team_id)) or hub())
    client = app.test_client()
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', False, raising=False)
    client.get('/this-week')
    assert calls == []
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    html = client.get('/this-week?team_id=123').get_data(as_text=True)
    assert calls == [(6, 5, 123)] and 'id="this-week-hub"' in html


def test_page_survives_a_hub_error(monkeypatch):
    monkeypatch.setattr(views, 'get_week_view_state', lambda: STATE)
    def broken(*a, **k):
        raise RuntimeError('x')
    monkeypatch.setattr(views, 'get_this_week_hub', broken)
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    resp = app.test_client().get('/this-week')
    assert resp.status_code == 200
    assert "We couldn't load this week's decisions" in resp.get_data(as_text=True)
