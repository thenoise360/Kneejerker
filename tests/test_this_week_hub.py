import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import json
import pytest

from FPL_site import app
import FPL_site.views as views
import FPL_site.thisWeekHub as hub
from FPL_site.thisWeekHub import build_hub

ROWS = [{'id': 1, 'web_name': 'Saka', 'team': 10, 'chance_of_playing_next_round': 25,
         'news': 'Hamstring', 'element_type': 3, 'status': 'd',
         'expected_goals': 3.0, 'expected_assists': 2.0},
        {'id': 2, 'web_name': 'Haaland', 'team': 20, 'chance_of_playing_next_round': None,
         'news': '', 'element_type': 4, 'status': 'a', 'expected_goals': 6.0, 'expected_assists': 1.0}]
FIXTURES = {10: {'opponent': 'Everton', 'is_home': True, 'difficulty': 2},
            20: {'opponent': 'Burnley', 'is_home': False, 'difficulty': 2}}
SQUAD = {'status': 'ok', 'bank': 5, 'squad_gameweek': 5, 'squad': [
    {'id': 1, 'slot': 1, 'starter': True, 'is_captain': False, 'is_vice': False},
    {'id': 2, 'slot': 2, 'starter': True, 'is_captain': True, 'is_vice': False}]}


def test_personal_hub_shape():
    result = build_hub(6, SQUAD, ROWS, {1: 0.5, 2: 1.4}, FIXTURES, [])
    assert result['status'] == 'ready' and result['based_on'] == 'your_team'
    assert result['headline']['reason_key'] == 'starter_doubt'
    assert result['decisions']['transfers'] == {'state': 'not_ready'}
    assert result['decisions']['captaincy']['suggested']['name'] == 'Haaland'


def test_guest_hub_when_team_unknown():
    result = build_hub(6, {'status': 'not_found'}, ROWS, {2: 1.4}, FIXTURES, [])
    assert result['based_on'] == 'everyone' and result['team_status'] == 'not_found'
    assert result['decisions']['injuries']['state'] == 'needs_team'
    assert result['headline']['reason_key'] == 'captain_choice'


def test_json_has_no_sentences():
    # Facts and keys only: the longest free text allowed is the official news line.
    text = json.dumps(build_hub(6, SQUAD, ROWS, {1: 0.5, 2: 1.4}, FIXTURES, []))
    assert 'your call' not in text.lower() and 'worth' not in text.lower()


def test_database_down_is_unavailable(monkeypatch):
    monkeypatch.setattr(hub, 'connect_db', lambda: None)
    monkeypatch.setattr(hub, 'get_squad_context', lambda t, g: {'status': 'ok', 'squad': []})
    assert hub.get_this_week_hub(6, 5, team_id=1) == {'status': 'unavailable', 'gameweek': 6}


def test_api_down_still_gives_a_guest_hub(monkeypatch):
    monkeypatch.setattr(hub, 'get_squad_context', lambda t, g: {'status': 'unavailable'})
    monkeypatch.setattr(hub, '_load_week_data', lambda gw, ids: (ROWS, {2: 1.4}, FIXTURES, [], None))
    result = hub.get_this_week_hub(6, 5, team_id=1)
    assert result['based_on'] == 'everyone' and result['team_status'] == 'unavailable'


def test_invalid_and_missing_team_skip_the_api(monkeypatch):
    def boom(*a):
        raise AssertionError('should not call the official API')
    monkeypatch.setattr(hub, 'get_squad_context', boom)
    monkeypatch.setattr(hub, '_load_week_data', lambda gw, ids: (ROWS, {}, FIXTURES, [], None))
    assert hub.get_this_week_hub(6, 5, team_id='invalid')['team_status'] == 'invalid'
    assert hub.get_this_week_hub(6, 5, team_id=None)['team_status'] == 'none'


@pytest.fixture
def client():
    return app.test_client()


def test_route_is_hidden_when_flag_off(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', False, raising=False)
    assert client.get('/api/week/this-week?gameweek=6').status_code == 404


def test_route_validates_gameweek(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    assert client.get('/api/week/this-week?gameweek=99').status_code == 400


def test_route_passes_parsed_arguments(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    seen = {}
    def fake(gameweek, last_gameweek, team_id=None):
        seen.update(gameweek=gameweek, last=last_gameweek, team=team_id)
        return {'status': 'ready'}
    monkeypatch.setattr(views, 'get_this_week_hub', fake)
    assert client.get('/api/week/this-week?gameweek=6&last_gameweek=5&team_id=12x').status_code == 200
    assert seen == {'gameweek': 6, 'last': 5, 'team': 'invalid'}


def test_route_error_is_json_500(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'THIS_WEEK_HUB', True, raising=False)
    def broken(*a, **k):
        raise RuntimeError('x')
    monkeypatch.setattr(views, 'get_this_week_hub', broken)
    resp = client.get('/api/week/this-week?gameweek=6')
    assert resp.status_code == 500 and resp.get_json() == {'error': 'server_error'}
