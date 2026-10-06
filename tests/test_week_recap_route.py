import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import app
import FPL_site.views as views


@pytest.fixture
def client():
    return app.test_client()


def test_recap_route_returns_payload(client, monkeypatch):
    seen = {}

    def fake(gameweek, team_id=None):
        seen['gameweek'] = gameweek
        return {'gameweek': gameweek, 'status': 'ready', 'guest': {'headline': 'x'},
                'message': None, 'personal': None}

    monkeypatch.setattr(views, 'get_last_week_recap', fake)
    resp = client.get('/api/week/last-week-recap?gameweek=5')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ready'
    assert seen['gameweek'] == 5


@pytest.mark.parametrize('query', ['', '?gameweek=', '?gameweek=abc', '?gameweek=0', '?gameweek=39', '?gameweek=-1', '?gameweek=%C2%B2'])
def test_recap_route_rejects_bad_gameweek(client, query):
    resp = client.get('/api/week/last-week-recap' + query)
    assert resp.status_code == 400
    assert resp.get_json() == {'error': 'invalid_gameweek'}


def test_recap_route_hides_internal_errors(client, monkeypatch):
    def boom(gameweek):
        raise RuntimeError('database exploded')

    monkeypatch.setattr(views, 'get_last_week_recap', boom)
    resp = client.get('/api/week/last-week-recap?gameweek=5')
    assert resp.status_code == 500
    assert resp.get_json() == {'error': 'server_error'}


def test_route_passes_team_id(client, monkeypatch):
    seen = {}

    def fake(gameweek, team_id=None):
        seen['team_id'] = team_id
        return {'gameweek': gameweek, 'status': 'ready', 'guest': {}, 'message': None, 'personal': None}

    monkeypatch.setattr(views, 'get_last_week_recap', fake)
    client.get('/api/week/last-week-recap?gameweek=5&team_id=123')
    assert seen['team_id'] == 123


@pytest.mark.parametrize('junk', ['abc', '-4', '0', '1e5', '99999999999', '%C2%B2'])
def test_route_rejects_junk_team_id_gracefully(client, monkeypatch, junk):
    seen = {}

    def fake(gameweek, team_id=None):
        seen['team_id'] = team_id
        return {'gameweek': gameweek, 'status': 'ready', 'guest': {}, 'message': None,
                'personal': {'status': 'team_not_found'}}

    monkeypatch.setattr(views, 'get_last_week_recap', fake)
    resp = client.get(f'/api/week/last-week-recap?gameweek=5&team_id={junk}')
    assert resp.status_code == 200
    assert seen['team_id'] == 'invalid'
