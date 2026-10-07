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


@pytest.mark.parametrize('flag', [True, False])
def test_radar_feature_flag_marker(client, monkeypatch, flag):
    monkeypatch.setattr(views.current_config, 'FEATURE_MOMENTUM', flag, raising=False)
    html = client.get('/radar').get_data(as_text=True)
    assert 'id="feature-flags"' in html
    assert ('data-momentum="true"' in html) == flag
    assert 'data-momentum=""' in html or flag


def test_feature_momentum_defaults_off():
    from FPL_site.config import Config
    assert Config.FEATURE_MOMENTUM is False


def test_radar_leaves_out_the_slide_for_a_missing_momentum_payload():
    # fetchJsonSafe turns a 404 into null, and buildMiniCards only adds the slide when it has a payload.
    source = open(os.path.join(os.path.dirname(__file__), '..', 'FPL_site', 'static', 'scripts', 'radar.js'),
                  encoding='utf-8').read()
    assert 'if (!res.ok) return null;' in source
    assert 'if (momentum) {' in source


STRIP = {'heating_up': [{'id': 2, 'name': 'B', 'team': 'Chelsea', 'reason': 'Rising: kinder fixtures coming up.'}],
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


@pytest.mark.parametrize('flag', [True, False])
def test_discovery_feature_flag_marker(client, monkeypatch, flag):
    monkeypatch.setattr(views.current_config, 'FEATURE_MOMENTUM', flag, raising=False)
    html = client.get('/discovery').get_data(as_text=True)
    assert 'id="feature-flags"' in html
    assert ('data-momentum="true"' in html) == flag
