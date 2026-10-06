from unittest.mock import MagicMock, patch

from FPL_site import dataModels


def _response(status, payload=None):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload or {}
    return response


def test_fetch_uses_timeout_and_resolves_events():
    events = [{'id': 1, 'deadline_time': '2020-01-01T10:00:00Z',
               'finished': True, 'data_checked': True}]
    with patch.object(dataModels.requests, 'get', return_value=_response(200, {'events': events})) as get:
        result = dataModels.get_week_view_state()
    assert get.call_args.kwargs['timeout'] == 5
    assert result['this_week']['mode'] == 'off_season'
    assert result['last_week'] == {'status': 'final', 'gameweek': 1,
                                   'deadline': '2020-01-01T10:00:00Z'}


def test_non_200_is_unavailable():
    with patch.object(dataModels.requests, 'get', return_value=_response(500)):
        assert dataModels.get_week_view_state()['this_week']['mode'] == 'unavailable'


def test_exception_is_unavailable():
    with patch.object(dataModels.requests, 'get', side_effect=RuntimeError('boom')):
        assert dataModels.get_week_view_state()['this_week']['mode'] == 'unavailable'
