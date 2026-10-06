import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import re

import pytest

from FPL_site.recapCopy import (
    average_headline, standout_reason, standout_sentence, recap_not_ready_copy,
)

ACRONYMS = re.compile(r'\b(FPL|GW|XG|XA|ICT|DGW|BGW)\b', re.I)


def player(**overrides):
    base = {'name': 'Player', 'position': 3, 'goals': 0, 'assists': 0, 'clean_sheets': 0,
            'saves': 0, 'bonus': 0, 'penalties_saved': 0}
    base.update(overrides)
    return base


@pytest.mark.parametrize('average,expected', [
    (0, 'A tough week for most players'), (44, 'A tough week for most players'),
    (45, 'A fairly typical week'), (59, 'A fairly typical week'),
    (60, 'A high-scoring week'), (120, 'A high-scoring week'),
])
def test_average_headline_tiers(average, expected):
    assert average_headline(average) == expected


@pytest.mark.parametrize('overrides,expected', [
    ({'goals': 3}, 'a hat-trick'),
    ({'goals': 3, 'assists': 1}, 'a hat-trick and an assist'),
    ({'goals': 4}, 'four goals'),
    ({'goals': 2}, 'two goals'),
    ({'goals': 2, 'assists': 1}, 'two goals and an assist'),
    ({'goals': 2, 'assists': 2}, 'two goals and two assists'),
    ({'goals': 1, 'assists': 1}, 'a goal and an assist'),
    ({'goals': 1, 'assists': 3}, 'a goal and three assists'),
    ({'goals': 1}, 'a goal'),
    ({'assists': 1}, 'an assist'),
    ({'assists': 2}, 'two assists'),
    ({'assists': 3}, 'three assists'),
    ({'assists': 11}, '11 assists'),
    ({'penalties_saved': 1, 'position': 1}, 'a penalty save'),
    ({'penalties_saved': 2, 'position': 1}, 'two penalty saves'),
    ({'clean_sheets': 1, 'position': 1, 'saves': 3}, 'a clean sheet and three saves'),
    ({'clean_sheets': 1, 'position': 1, 'saves': 5}, 'a clean sheet and five saves'),
    ({'clean_sheets': 1, 'position': 2, 'saves': 2}, 'a clean sheet'),
    ({'clean_sheets': 1, 'position': 3}, 'a solid all-round game'),
    ({}, 'a solid all-round game'),
])
def test_standout_reason_tiers(overrides, expected):
    assert standout_reason(player(**overrides)) == expected


@pytest.mark.parametrize('bonus,suffix', [(2, ''), (3, ' and a full haul of bonus points'),
                                          (5, ' and a full haul of bonus points')])
def test_bonus_suffix_boundary(bonus, suffix):
    assert standout_reason(player(goals=1, bonus=bonus)) == 'a goal' + suffix


def test_standout_sentence():
    assert standout_sentence(player(name='Saka', goals=2)) == 'Saka led the way with two goals.'


def test_not_ready_copy_mentions_gameweek_and_is_calm():
    copy = recap_not_ready_copy(6)
    assert 'Gameweek 6' in copy['title']
    assert 'error' not in (copy['title'] + copy['body']).lower()


def test_no_acronyms_anywhere():
    texts = [average_headline(a) for a in (10, 50, 90)]
    texts += [standout_reason(player(**o)) for o in ({'goals': 3}, {'assists': 1}, {})]
    texts += list(recap_not_ready_copy(6).values())
    for text in texts:
        assert not ACRONYMS.search(text), text
