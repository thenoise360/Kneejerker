import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import re

import pytest

from FPL_site.decisionCopy import (
    fixture_phrase, availability_decision, captain_decision, guest_captain_decision, no_decision_copy,
)

ACRONYMS = re.compile(r'\b(FPL|GW|XG|XA|ICT|DGW|BGW)\b', re.I)
FIXTURE = {'opponent': 'Everton', 'is_home': True, 'difficulty': 2}


@pytest.mark.parametrize('fixture,expected', [
    (None, ''),
    ({'opponent': 'Everton', 'is_home': True, 'difficulty': 2}, ', with a kind fixture at home to Everton'),
    ({'opponent': 'Everton', 'is_home': False, 'difficulty': 2}, ', with a kind fixture away at Everton'),
    ({'opponent': 'Villa', 'is_home': True, 'difficulty': 3}, ', at home to Villa'),
    ({'opponent': 'City', 'is_home': False, 'difficulty': 4}, ', even with a tough fixture away at City'),
])
def test_fixture_phrase_tiers(fixture, expected):
    assert fixture_phrase(fixture) == expected


@pytest.mark.parametrize('chance,phrase', [(0, 'is set to miss this week'), (25, 'is a doubt this week'),
                                           (74, 'is a doubt this week')])
def test_availability_wording(chance, phrase):
    d = availability_decision('Saka', chance, 'Hamstring injury')
    assert phrase in d['reason'] and d['reason'].endswith('your call.')
    assert d['details'] == [f'Chance of playing: {chance}%', 'Latest news: Hamstring injury']


def test_availability_without_news():
    d = availability_decision('Saka', 50, '')
    assert '()' not in d['reason'] and d['details'] == ['Chance of playing: 50%']


def test_captain_same_vs_switch():
    fixture = {'opponent': 'Everton', 'is_home': True, 'difficulty': 2}
    same = captain_decision('Haaland', 7.04, 'Haaland', fixture)
    assert same['title'] == 'Captain: Haaland looks right'
    assert same['details'] == ['Our prediction for Haaland: about 7.0 points']
    switch = captain_decision('Salah', 8.0, 'Haaland', fixture)
    assert switch['title'] == 'Captain: worth a look at Salah' and 'ahead of Haaland' in switch['reason']


def test_guest_and_empty_copy():
    g = guest_captain_decision('Salah', 8.0, None)
    assert g['reason'].endswith('your call.')
    for text in [g['title'], g['reason'], *no_decision_copy().values()]:
        assert not ACRONYMS.search(text)


def test_no_title_or_reason_contains_a_digit_in_any_builder():
    """Numbers belong in details only. Player and club names are digit-free here."""
    tough = {'opponent': 'City', 'is_home': False, 'difficulty': 4}
    builders = [
        availability_decision('Saka', 0, 'Out'),
        availability_decision('Saka', 25, ''),
        availability_decision('Saka', 74, 'Knock'),
        captain_decision('Haaland', 7.04, 'Haaland', FIXTURE),
        captain_decision('Salah', 8.0, 'Haaland', tough),
        captain_decision('Salah', 8.0, 'Haaland', None),
        guest_captain_decision('Salah', 8.0, None),
        guest_captain_decision('Salah', 8.0, {'opponent': 'Villa', 'is_home': True, 'difficulty': 3}),
        no_decision_copy(),
    ]
    for d in builders:
        for key in ('title', 'reason', 'body'):
            if key in d:
                assert not re.search(r'\d', d[key]), d[key]
