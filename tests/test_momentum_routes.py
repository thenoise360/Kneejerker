import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import app
import FPL_site.views as views


@pytest.fixture
def client():
    return app.test_client()


def test_momentum_route_ready(client, monkeypatch):
    monkeypatch.setattr(views, 'load_player_momentum', lambda pid: {'status': 'ready', 'label': 'Steady'})
    resp = client.get('/api/player/5/momentum')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ready'


def test_momentum_route_unknown_player(client, monkeypatch):
    monkeypatch.setattr(views, 'load_player_momentum', lambda pid: None)
    resp = client.get('/api/player/99/momentum')
    assert resp.status_code == 404
    assert resp.get_json() == {'error': 'unknown_player'}


def test_momentum_route_hides_errors(client, monkeypatch):
    def boom(pid):
        raise RuntimeError('database exploded')
    monkeypatch.setattr(views, 'load_player_momentum', boom)
    resp = client.get('/api/player/1/momentum')
    assert resp.status_code == 500
    assert resp.get_json() == {'error': 'server_error'}


def test_radar_leaves_out_the_slide_for_a_missing_momentum_payload():
    # fetchJsonSafe turns a 404 into null, and buildMiniCards only adds the slide when it has a payload.
    source = open(os.path.join(os.path.dirname(__file__), '..', 'FPL_site', 'static', 'scripts', 'radar.js'),
                  encoding='utf-8').read()
    assert 'if (!res.ok) return null;' in source
    assert 'if (momentum) {' in source
    assert 'fetchJsonSafe(`/api/player/${playerId}/momentum`)' in source


STRIP = {'heating_up': [{'id': 2, 'name': 'B', 'team': 'Chelsea', 'position': 'MID', 'reason': 'Rising: kinder fixtures coming up.'}],
         'cooling_off': [{'id': 4, 'name': 'D', 'team': 'Arsenal', 'reason': 'Cooling: tougher fixtures coming up.'}]}


def test_strip_route_returns_both_lists(client, monkeypatch):
    monkeypatch.setattr(views, 'load_momentum_strip', lambda: STRIP)
    resp = client.get('/api/discover/momentum-strip')
    assert resp.status_code == 200
    assert resp.get_json() == STRIP


def test_strip_never_exposes_score(client, monkeypatch):
    monkeypatch.setattr(views, 'load_momentum_strip', lambda: STRIP)
    text = client.get('/api/discover/momentum-strip').get_data(as_text=True)
    assert 'score' not in text


def test_strip_route_hides_errors(client, monkeypatch):
    def boom():
        raise RuntimeError('database exploded')
    monkeypatch.setattr(views, 'load_momentum_strip', boom)
    resp = client.get('/api/discover/momentum-strip')
    assert resp.status_code == 500
    assert resp.get_json() == {'error': 'server_error'}


def test_discover_renders_and_loads_the_strip_without_any_flag(client):
    assert client.get('/discovery').status_code == 200
    root = os.path.join(os.path.dirname(__file__), '..', 'FPL_site')
    discovery_js = open(os.path.join(root, 'static', 'scripts', 'discovery.js'), encoding='utf-8').read()
    assert "heatingUp: 'category-heating-up'" in discovery_js
    assert 'loadHeatingUpCategory()' in discovery_js


def test_sheet_and_strip_routes_are_registered():
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert '/api/player/<int:player_id>/momentum' in rules
    assert '/api/discover/momentum-strip' in rules
