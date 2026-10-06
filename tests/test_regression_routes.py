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
DATA_ROUTE_STUBS = {}


@pytest.fixture
def calls():
    return []


@pytest.fixture
def client(monkeypatch, calls):
    def fake_gameweek_state():
        calls.append('get_gameweek_state')
        return {'state': 'none', 'gameweek': None, 'deadline': None}

    def fake_week_view_state():
        calls.append('get_week_view_state')
        return WEEK_STATE

    monkeypatch.setattr(views, 'get_gameweek_state', fake_gameweek_state)
    monkeypatch.setattr(views, 'get_week_view_state', fake_week_view_state)
    for _, (name, value) in DATA_ROUTE_STUBS.items():
        monkeypatch.setattr(views, name, lambda *a, _v=value, **k: _v)
    return app.test_client()


def set_flag(monkeypatch, on):
    monkeypatch.setattr(views.current_config, 'FEATURE_WEEK_V2', on, raising=False)


@pytest.mark.parametrize('flag', [False, True])
@pytest.mark.parametrize('path', PAGE_ROUTES)
def test_page_routes_render(client, monkeypatch, flag, path):
    set_flag(monkeypatch, flag)
    assert client.get(path).status_code == 200


@pytest.mark.parametrize('flag', [False, True])
def test_data_routes_respond(client, monkeypatch, flag):
    set_flag(monkeypatch, flag)
    for path in DATA_ROUTE_STUBS:
        assert client.get(path).status_code == 200, path


def test_flag_off_week_page_keeps_existing_markers(client, monkeypatch):
    set_flag(monkeypatch, False)
    html = client.get('/this-week').get_data(as_text=True)
    for marker in ['id="gw-panel-live"', 'id="live-team-id-form"', 'Friend activity feed',
                   'Team of the Week', 'scripts/home.js', 'content/home.css']:
        assert marker in html, marker


def test_flag_on_week_page_fetches_state_once(client, monkeypatch, calls):
    set_flag(monkeypatch, True)
    client.get('/this-week')
    assert calls == ['get_week_view_state']


def test_flag_off_week_page_fetches_state_once(client, monkeypatch, calls):
    set_flag(monkeypatch, False)
    client.get('/this-week')
    assert calls == ['get_gameweek_state']
