import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import pytest

from FPL_site.hubSignals import assess_risk, player_signals

FIT = {'chance': None, 'status': 'a', 'news': ''}


def _rows(minutes, element=1):
    return [{'element': element, 'fixture': i, 'kickoff_time': f'2026-09-{10 + i:02d}T15:00:00Z',
             'minutes': m, 'yellow_cards': 0} for i, m in enumerate(minutes)]


@pytest.mark.parametrize('chance,tier', [(75, 'low'), (50, 'medium'), (25, 'high'), (0, 'confirmed')])
def test_official_chance_maps_to_tiers(chance, tier):
    assert assess_risk({'chance': chance, 'status': 'd', 'news': ''}, None, 6)['tier'] == tier


@pytest.mark.parametrize('status', ['s', 'u', 'n'])
def test_suspended_or_unavailable_is_confirmed(status):
    assert assess_risk({'chance': None, 'status': status, 'news': ''}, None, 6)['tier'] == 'confirmed'


def test_subbed_early_is_medium():
    risk = assess_risk(FIT, player_signals(_rows([90, 90, 90, 90, 60])).get(1), 6)
    assert risk['tier'] == 'medium'
    assert risk['reasons'] == [{'key': 'subbed_early', 'minutes': 60, 'usual_minutes': 90}]


def test_just_under_threshold_is_not_subbed_early():
    # 70 is not below 0.75 x 90 = 67.5
    assert assess_risk(FIT, player_signals(_rows([90, 90, 90, 90, 70])).get(1), 6)['tier'] == 'low'


def test_only_the_last_five_games_count():
    signals = player_signals(_rows([0, 0, 0, 90, 90, 90, 90, 90]))[1]
    assert signals['minutes_recent'] == [90, 90, 90, 90, 90]
    assert signals['games_season'] == 8


def test_games_are_ordered_by_kickoff_and_deduplicated_by_fixture():
    rows = _rows([90, 0]) + [dict(_rows([90, 0])[1])]  # the same fixture stored twice
    rows.reverse()
    assert player_signals(rows)[1]['minutes_recent'] == [90, 0]


def test_no_history_and_fit_means_low_with_no_reasons():
    assert assess_risk(FIT, None, 6) == {'pct': 0, 'tier': 'low', 'reasons': []}
