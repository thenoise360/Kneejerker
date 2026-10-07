import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import app
import FPL_site.views as views


@pytest.fixture
def client():
    return app.test_client()


def test_decision_route_passes_arguments(client, monkeypatch):
    seen = {}

    def fake(gameweek, last_gameweek, team_id=None):
        seen.update(gameweek=gameweek, last_gameweek=last_gameweek, team_id=team_id)
        return {'gameweek': gameweek, 'based_on': 'everyone', 'squad_gameweek': None,
                'decision': None, 'message': {'title': 't', 'body': 'b'}}

    monkeypatch.setattr(views, 'get_this_week_decision', fake)
    resp = client.get('/api/week/this-week-decision?gameweek=6&last_gameweek=5&team_id=42')
    assert resp.status_code == 200
    assert seen == {'gameweek': 6, 'last_gameweek': 5, 'team_id': 42}


def test_decision_route_without_last_gameweek(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(views, 'get_this_week_decision',
                        lambda gameweek, last_gameweek, team_id=None: seen.update(last=last_gameweek) or {})
    client.get('/api/week/this-week-decision?gameweek=1')
    assert seen['last'] is None


@pytest.mark.parametrize('query', ['', '?gameweek=x', '?gameweek=40'])
def test_decision_route_rejects_bad_gameweek(client, query):
    assert client.get('/api/week/this-week-decision' + query).status_code == 400
