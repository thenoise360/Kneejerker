import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import app
import FPL_site.views as views


@pytest.fixture
def client():
    return app.test_client()


def test_strength_route_ready(client, monkeypatch):
    monkeypatch.setattr(views, 'load_team_strength', lambda team_id: {'status': 'ready', 'team_name': 'Arsenal'})
    resp = client.get('/api/club/1/strength')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ready'


def test_strength_route_unknown_team(client, monkeypatch):
    monkeypatch.setattr(views, 'load_team_strength', lambda team_id: None)
    resp = client.get('/api/club/99/strength')
    assert resp.status_code == 404
    assert resp.get_json() == {'error': 'unknown_team'}


def test_strength_route_hides_errors(client, monkeypatch):
    def boom(team_id):
        raise RuntimeError('database exploded')
    monkeypatch.setattr(views, 'load_team_strength', boom)
    resp = client.get('/api/club/1/strength')
    assert resp.status_code == 500
    assert resp.get_json() == {'error': 'server_error'}
