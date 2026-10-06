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


from FPL_site.recapCopy import pick_one_thing_right


def squad_player(name, points, captain=False, multiplier=None, minutes=90, difficulty=3):
    if multiplier is None:
        multiplier = 2 if captain else 1
    return {'id': hash(name) % 1000, 'name': name, 'is_captain': captain,
            'multiplier': multiplier,
            'points': points, 'minutes': minutes, 'difficulty': difficulty}


@pytest.mark.parametrize('points,tier', [(5, 'solid_pick'), (6, 'captain')])
def test_captain_threshold(points, tier):
    assert pick_one_thing_right([squad_player('Cap', points, captain=True)])['tier'] == tier


def test_triple_captain_wording():
    result = pick_one_thing_right([squad_player('Cap', 10, captain=True, multiplier=3)])
    assert result['reason'] == 'Captaining Cap paid off, and you got the points triple.'


@pytest.mark.parametrize('points,tier', [(7, 'solid_pick'), (8, 'big_pick')])
def test_big_pick_threshold(points, tier):
    squad = [squad_player('Cap', 1, captain=True, difficulty=5), squad_player('Star', points)]
    assert pick_one_thing_right(squad)['tier'] == tier


def test_bench_player_never_counts():
    squad = [squad_player('Cap', 1, captain=True, difficulty=5), squad_player('Bench', 15, multiplier=0)]
    assert pick_one_thing_right(squad)['tier'] == 'showed_up'


@pytest.mark.parametrize('difficulty,points,tier', [
    (2, 2, 'sound_blank'), (3, 2, 'showed_up'), (2, 3, 'showed_up'), (None, 1, 'showed_up'),
])
def test_sound_blank_boundaries(difficulty, points, tier):
    squad = [squad_player('Cap', 0, captain=True, difficulty=5, minutes=0),
             squad_player('Pick', points, difficulty=difficulty)]
    assert pick_one_thing_right(squad)['tier'] == tier


def test_sound_blank_needs_minutes():
    squad = [squad_player('Cap', 0, captain=True, minutes=0, difficulty=5),
             squad_player('Benched', 0, minutes=0, difficulty=1)]
    assert pick_one_thing_right(squad)['tier'] == 'showed_up'


def test_empty_squad_is_kind():
    result = pick_one_thing_right([])
    assert result['tier'] == 'showed_up' and not ACRONYMS.search(result['reason'])


def test_captain_double_wording():
    result = pick_one_thing_right([squad_player('Cap', 10, captain=True, multiplier=2)])
    assert result['reason'] == 'Captaining Cap paid off, and you got the points double.'


def test_captain_with_unexpected_multiplier_has_no_double_claim():
    result = pick_one_thing_right([squad_player('Cap', 10, captain=True, multiplier=1)])
    assert result['tier'] == 'captain'
    assert 'double' not in result['reason'] and 'triple' not in result['reason']
    assert result['reason'] == 'Captaining Cap paid off.'


@pytest.mark.parametrize('points,tier', [(3, 'showed_up'), (4, 'solid_pick')])
def test_solid_pick_threshold(points, tier):
    squad = [squad_player('Cap', 0, captain=True, minutes=0, difficulty=5),
             squad_player('Pick', points, difficulty=3)]
    assert pick_one_thing_right(squad)['tier'] == tier


from FPL_site.recapCopy import score_verdict, team_not_found_copy


@pytest.mark.parametrize('score,tier', [
    (63, 'well_above'), (62, 'above'), (53, 'above'), (52, 'about'),
    (48, 'about'), (44, 'about'), (43, 'below'), (34, 'below'), (33, 'tough'), (0, 'tough'),
])
def test_score_verdict_boundaries_against_average_48(score, tier):
    assert score_verdict(score, 48)['tier'] == tier


def test_score_verdict_copy_is_kind_and_acronym_free():
    for score in (0, 40, 48, 55, 90):
        text = score_verdict(score, 48)['text']
        assert not ACRONYMS.search(text)
        assert 'bad' not in text.lower() and 'fail' not in text.lower()


def test_team_not_found_copy():
    copy = team_not_found_copy(5)
    assert 'gameweek 5' in copy['body'] and not ACRONYMS.search(copy['title'] + copy['body'])


def test_no_reason_in_any_tier_contains_a_digit():
    squads = [
        [squad_player('Cap', 12, captain=True, multiplier=3)],
        [squad_player('Cap', 12, captain=True, multiplier=2)],
        [squad_player('Cap', 12, captain=True, multiplier=1)],
        [squad_player('Cap', 1, captain=True, difficulty=5), squad_player('Star', 9)],
        [squad_player('Cap', 0, captain=True, difficulty=5, minutes=0), squad_player('Pick', 1, difficulty=2)],
        [squad_player('Cap', 0, captain=True, difficulty=5, minutes=0), squad_player('Pick', 5, difficulty=3)],
        [],
    ]
    seen = set()
    for squad in squads:
        result = pick_one_thing_right(squad)
        seen.add(result['tier'])
        assert not re.search(r'\d', result['reason']), result
    assert seen == {'captain', 'big_pick', 'sound_blank', 'solid_pick', 'showed_up'}


def test_points_and_name_travel_in_their_own_keys():
    captain = pick_one_thing_right([squad_player('Cap', 12, captain=True)])
    assert captain['points'] == 12 and captain['name'] == 'Cap'
    big = pick_one_thing_right([squad_player('Cap', 1, captain=True, difficulty=5), squad_player('Star', 9)])
    assert big['points'] == 9 and big['name'] == 'Star'
    solid = pick_one_thing_right([squad_player('Cap', 0, captain=True, minutes=0, difficulty=5),
                                  squad_player('Pick', 5)])
    assert solid['points'] == 5 and solid['name'] == 'Pick'


def test_tiers_without_a_meaningful_number_have_no_points():
    blank = pick_one_thing_right([squad_player('Cap', 0, captain=True, minutes=0, difficulty=5),
                                  squad_player('Pick', 1, difficulty=2)])
    assert blank['tier'] == 'sound_blank' and blank['points'] is None and blank['name'] == 'Pick'
    assert pick_one_thing_right([])['points'] is None
