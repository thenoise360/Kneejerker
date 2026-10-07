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
