import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import app
import FPL_site.views as views

PAGE_ROUTES = ['/this-week', '/radar', '/discovery', '/clubs', '/club/1', '/privacy']

WEEK_STATE = {
    'this_week': {'mode': 'upcoming', 'gameweek': 6, 'deadline': '2026-10-10T10:00:00Z'},
    'last_week': {'status': 'final', 'gameweek': 5, 'deadline': '2026-10-03T10:00:00Z'},
}

# path -> (name of the function in views to stub, the value the stub returns).
# Each release adds its new data routes here so they stay covered forever.
DATA_ROUTE_STUBS = {
    '/api/week/last-week-recap?gameweek=5': ('get_last_week_recap', {
        'gameweek': 5, 'status': 'ready', 'guest': None, 'message': None, 'personal': None}),
    '/api/week/this-week-decision?gameweek=6&last_gameweek=5': ('get_this_week_decision', {
        'gameweek': 6, 'based_on': 'everyone', 'squad_gameweek': None, 'decision': None,
        'message': {'title': 't', 'body': 'b'}}),
    '/api/club/1/strength': ('load_team_strength', {'status': 'not_ready', 'message': {'title': 't', 'body': 'b'}}),
    '/api/club/1/prediction-record': ('load_prediction_record', {'status': 'ready', 'games': []}),
}


@pytest.fixture
def calls():
    return []


@pytest.fixture
def client(monkeypatch, calls):
    def fake_week_view_state():
        calls.append('get_week_view_state')
        return WEEK_STATE

    monkeypatch.setattr(views, 'get_week_view_state', fake_week_view_state)
    for _, (name, value) in DATA_ROUTE_STUBS.items():
        monkeypatch.setattr(views, name, lambda *a, _v=value, **k: _v)
    return app.test_client()


@pytest.mark.parametrize('path', PAGE_ROUTES)
def test_page_routes_render(client, path):
    assert client.get(path).status_code == 200


def test_data_routes_respond(client):
    for path in DATA_ROUTE_STUBS:
        assert client.get(path).status_code == 200, path


def test_week_page_is_v2_without_any_flag(client, calls):
    html = client.get('/this-week').get_data(as_text=True)
    for marker in ['data-week-v2="true"', 'id="decision-hub"', 'id="gw-panel-live"',
                   'id="live-team-id-form"', 'scripts/home.js', 'content/home.css']:
        assert marker in html, marker
    assert 'Friend activity feed' not in html and 'Team of the Week' not in html
    assert calls == ['get_week_view_state']


def test_club_page_always_has_both_cards(client):
    html = client.get('/club/1').get_data(as_text=True)
    assert 'id="team-strength-slot"' in html
    assert 'id="prediction-record-slot"' in html
