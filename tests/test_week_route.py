import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site import app
import FPL_site.views as views


def _state(mode, gw=None, last_status='none', last_gw=None, deadline=None):
    return {'this_week': {'mode': mode, 'gameweek': gw, 'deadline': deadline},
            'last_week': {'status': last_status, 'gameweek': last_gw}}


@pytest.fixture
def client(monkeypatch):
    # The page must never reach the real FPL API in tests.
    monkeypatch.setattr(views, 'get_gameweek_state',
                        lambda: {'state': 'none', 'gameweek': None, 'deadline': None})
    return app.test_client()


def test_flag_off_renders_existing_page(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'FEATURE_WEEK_V2', False, raising=False)
    html = client.get('/this-week').get_data(as_text=True)
    assert 'Friend activity feed' in html


def test_flag_on_renders_off_season_copy(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'FEATURE_WEEK_V2', True, raising=False)
    monkeypatch.setattr(views, 'get_week_view_state',
                        lambda: _state('off_season', last_status='final', last_gw=38))
    resp = client.get('/this-week')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'taking a breather' in html
    assert 'Gameweek 38 recap' in html
    assert 'Friend activity feed' not in html


def test_flag_on_unavailable_is_friendly_not_an_error(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'FEATURE_WEEK_V2', True, raising=False)
    monkeypatch.setattr(views, 'get_week_view_state', lambda: _state('unavailable'))
    resp = client.get('/this-week')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'Nothing is wrong on your side' in html
    assert 'No recap yet' in html


def test_flag_on_slow_confirming_uses_delayed_tier(client, monkeypatch):
    monkeypatch.setattr(views.current_config, 'FEATURE_WEEK_V2', True, raising=False)
    # Deadline far in the past, so it's well over the 96-hour threshold.
    monkeypatch.setattr(views, 'get_week_view_state', lambda: _state(
        'confirming', gw=5, last_status='final', last_gw=4, deadline='2020-01-01T10:00:00Z'))
    html = client.get('/this-week').get_data(as_text=True)
    assert 'taking a little longer' in html
