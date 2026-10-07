import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import re
from datetime import date, datetime

import pytest

from FPL_site.recordCopy import (EARLY_DAYS_BELOW, GAME_MARGIN, TREND_FROM,
                                 game_verdict, record_summary)


def games_with_average(count, average):
    """`count` games, each predicted 1-1, whose goal difference beats prediction by `average`."""
    return [{'predicted_for': 1.0, 'predicted_against': 1.0,
             'actual_for': 1.0 + average, 'actual_against': 1.0} for _ in range(count)]


def test_constants():
    assert (EARLY_DAYS_BELOW, TREND_FROM, GAME_MARGIN) == (8, 0.5, 1.0)


@pytest.mark.parametrize('average, expected', [
    (0.5, 'have been beating their chances'),
    (0.49, 'are performing about as expected'),
    (0.0, 'are performing about as expected'),
    (-0.49, 'are performing about as expected'),
    (-0.5, 'have been falling short of their chances'),
])
def test_trend_boundaries(average, expected):
    result = record_summary('Arsenal', games_with_average(8, average), '2026-10-01')
    assert result['headline'] == f'Arsenal {expected}'


def test_float_noise_does_not_tip_boundary():
    # Differences 0.1, 0.2 and 1.2 average exactly 0.5, but the floats do not add up cleanly.
    games = [{'predicted_for': 1.0, 'predicted_against': 1.0,
              'actual_for': 1.0 + d, 'actual_against': 1.0} for d in (0.1, 0.2, 1.2)]
    assert record_summary('Arsenal', games, None)['headline'].endswith('beating their chances')


def test_reasons():
    up = record_summary('Arsenal', games_with_average(8, 1), None)
    down = record_summary('Arsenal', games_with_average(8, -1), None)
    flat = record_summary('Arsenal', games_with_average(8, 0), None)
    assert up['reason'] == "They've been winning by more than their chances suggest. That tends not to last."
    assert down['reason'] == "They've been doing worse than their chances suggest. That tends to turn around."
    assert flat['reason'] == 'Their results have matched their chances so far.'


@pytest.mark.parametrize('count, early', [(7, True), (8, False)])
def test_early_days_boundary(count, early):
    assert record_summary('Arsenal', games_with_average(count, 1), None)['early_days'] is early


def test_early_days_still_gives_a_verdict():
    result = record_summary('Arsenal', games_with_average(3, 1), None)
    assert result['early_days'] is True
    assert 'beating their chances' in result['headline']


@pytest.mark.parametrize('actual_for, actual_against, expected', [
    (2.0, 1.0, 'better'),         # +1.0 exactly
    (1.99, 1.0, 'as_expected'),   # +0.99
    (0.0, 1.0, 'worse'),          # -1.0 exactly
    (0.01, 1.0, 'as_expected'),   # -0.99
    (1.0, 1.0, 'as_expected'),
])
def test_game_verdict_both_sides(actual_for, actual_against, expected):
    assert game_verdict(1.0, 1.0, actual_for, actual_against) == expected


def test_game_verdict_float_noise():
    # Predicted difference 0.3 - 0.2 is 0.09999999999999998; actual 1.1 is exactly +1.0 better.
    assert game_verdict(0.3, 0.2, 2.1, 1.0) == 'better'


def test_no_games_with_date():
    result = record_summary('Arsenal', [], '2026-10-08')
    assert result['headline'] == 'No finished games logged yet'
    assert result['reason'] == ('We started keeping score on 8 October 2026. '
                                'Check back after their next game.')
    assert result['early_days'] is True


def test_no_games_without_date():
    result = record_summary('Arsenal', [], None)
    assert result['reason'] == "We'll start keeping score from their next game."
    assert result['early_days'] is True


def test_no_digits_or_acronyms_outside_date_sentence():
    for average in (1, 0, -1):
        for count in (3, 8):
            result = record_summary('Wolves', games_with_average(count, average), '2026-10-01')
            for text in (result['headline'], result['reason']):
                assert not re.search(r'\d', text)
                assert not re.search(r'\b[A-Z]{2,}\b', text)
    dated = record_summary('Arsenal', [], '2026-10-08')
    undated = record_summary('Arsenal', [], None)
    assert not re.search(r'\d', dated['headline'])
    assert not re.search(r'\d', undated['headline'] + undated['reason'])
    for result in (dated, undated):
        assert not re.search(r'\b[A-Z]{2,}\b', result['headline'] + result['reason'])


@pytest.mark.parametrize('started_on', [date(2026, 10, 8), datetime(2026, 10, 8, 9, 0)])
def test_no_games_accepts_date_objects(started_on):
    # mysql.connector returns DATE columns as datetime.date.
    assert '8 October 2026' in record_summary('Arsenal', [], started_on)['reason']
