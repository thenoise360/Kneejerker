import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import re

import pytest

from FPL_site.strengthCopy import strength_summary


def make(**over):
    base = {'scored': 2.0, 'scored_adjusted': 2.0, 'conceded': 1.0,
            'conceded_adjusted': 1.0, 'league_scored': 1.4,
            # a minor absentee, so the numbers are allowed to speak; tests override as needed
            'missing': [{'name': 'Minor', 'role': 'attack', 'share': 0.01, 'chance': 0, 'position': 3}]}
    base.update(over)
    return base


def player(role='attack', share=0.2, position=3, name='Someone', chance=0):
    return {'name': name, 'role': role, 'share': share, 'chance': chance, 'position': position}


def headline(strength):
    return strength_summary('Arsenal', strength)['headline']


def reason(strength):
    return strength_summary('Arsenal', strength)['reason']


@pytest.mark.parametrize('adjusted,expected', [
    (1.80, "Arsenal's attack is a little weaker this week"),
    (1.71, "Arsenal's attack is a little weaker this week"),
    (1.70, "Arsenal's attack is weaker this week"),
    (1.91, 'Arsenal are at full strength'),
    (1.90, "Arsenal's attack is a little weaker this week"),
    (2.0, 'Arsenal are at full strength'),
    (2.4, 'Arsenal are at full strength'),
])
def test_attack_tiers(adjusted, expected):
    assert headline(make(scored_adjusted=adjusted)) == expected


@pytest.mark.parametrize('adjusted,expected', [
    (1.10, "Arsenal's defence is a little weaker this week"),
    (1.149, "Arsenal's defence is a little weaker this week"),
    (1.15, "Arsenal's defence is weaker this week"),
    (1.045, 'Arsenal are at full strength'),
    (1.05, "Arsenal's defence is a little weaker this week"),
    (0.8, 'Arsenal are at full strength'),
])
def test_defence_tiers(adjusted, expected):
    assert headline(make(conceded_adjusted=adjusted)) == expected


def test_larger_effect_wins():
    assert headline(make(scored_adjusted=1.7, conceded_adjusted=1.3)) == "Arsenal's defence is weaker this week"
    assert headline(make(scored_adjusted=1.5, conceded_adjusted=1.2)) == "Arsenal's attack is weaker this week"


def test_tie_goes_to_attack():
    assert headline(make(scored_adjusted=1.7, conceded_adjusted=1.15)) == "Arsenal's attack is weaker this week"


def test_zero_raw_does_not_divide_by_zero():
    assert headline(make(scored=0, scored_adjusted=0, conceded=0, conceded_adjusted=0)) == 'Arsenal are at full strength'


@pytest.mark.parametrize('count,text', [
    (1, 'One of their main chance-creators is out.'),
    (2, 'Two of their main chance-creators are out.'),
    (3, 'Several of their main chance-creators are out.'),
    (5, 'Several of their main chance-creators are out.'),
])
def test_attack_reason_counts(count, text):
    s = make(scored_adjusted=1.5, missing=[player() for _ in range(count)])
    assert reason(s) == text


@pytest.mark.parametrize('count,text', [
    (1, 'One of their regular defenders is out.'),
    (2, 'Two of their regular defenders are out.'),
    (3, 'Several of their regular defenders are out.'),
])
def test_defence_reason_counts(count, text):
    s = make(conceded_adjusted=1.3, missing=[player('defence', position=2) for _ in range(count)])
    assert reason(s) == text


def test_key_share_boundary():
    low = make(scored_adjusted=1.5, missing=[player(share=0.0999)])
    at = make(scored_adjusted=1.5, missing=[player(share=0.10)])
    assert reason(low) == 'A few squad players are missing.'
    assert reason(at) == 'One of their main chance-creators is out.'


def test_other_role_does_not_count():
    s = make(scored_adjusted=1.5, missing=[player('defence', position=2)])
    assert reason(s) == 'A few squad players are missing.'


def test_nobody_missing_is_always_full_strength():
    s = make(scored_adjusted=1.0, conceded_adjusted=2.0, missing=[])
    assert headline(s) == 'Arsenal are at full strength'
    assert reason(s) == 'Strong going forward, solid at the back.'


def test_only_minor_absentees_still_gives_a_reason():
    assert reason(make(scored_adjusted=1.5)) == 'A few squad players are missing.'


def test_one_doubtful_attacker():
    s = make(scored_adjusted=1.5, missing=[player(chance=50)])
    assert reason(s) == 'One of their main chance-creators is out or doubtful.'


def test_mix_of_out_and_doubtful():
    s = make(conceded_adjusted=1.3, missing=[player('defence', position=2), player('defence', position=2, chance=25)])
    assert reason(s) == 'Two of their regular defenders are out or doubtful.'


def test_all_out_keeps_plain_wording():
    s = make(conceded_adjusted=1.3, missing=[player('defence', position=2, chance=0)] * 2)
    assert reason(s) == 'Two of their regular defenders are out.'


def test_doubtful_goalkeeper():
    s = make(conceded_adjusted=1.3, missing=[player('defence', position=1, chance=75)])
    assert reason(s) == 'Their first-choice goalkeeper is out or doubtful.'


def test_unkeyed_doubtful_player_does_not_change_wording():
    s = make(scored_adjusted=1.5, missing=[player(), player(share=0.05, chance=50)])
    assert reason(s) == 'One of their main chance-creators is out.'


@pytest.mark.parametrize('team,expected', [
    ('Wolves', "Wolves' attack is weaker this week"),
    ('Spurs', "Spurs' attack is weaker this week"),
    ('Arsenal', "Arsenal's attack is weaker this week"),
])
def test_possessive_headline(team, expected):
    out = strength_summary(team, make(scored_adjusted=1.5))
    assert out['headline'] == expected


def test_possessive_defence_headline():
    out = strength_summary('Wolves', make(conceded_adjusted=1.5))
    assert out['headline'] == "Wolves' defence is weaker this week"


def test_goalkeeper_reason():
    s = make(conceded_adjusted=1.3, missing=[player('defence', position=1), player('defence', position=2)])
    assert reason(s) == 'Their first-choice goalkeeper is out.'


def test_unkeyed_goalkeeper_is_not_special():
    s = make(conceded_adjusted=1.3, missing=[player('defence', share=0.05, position=1)])
    assert reason(s) == 'A few squad players are missing.'


@pytest.mark.parametrize('scored,text', [
    (1.61, 'Strong going forward'),     # 1.15 * 1.4 = 1.61, ratio exactly 1.15
    (1.60, 'Steady going forward'),
    (1.218, 'Short of goals'),          # 0.87 * 1.4 = 1.218, ratio exactly 0.87
    (1.22, 'Steady going forward'),
])
def test_full_strength_attack_reason(scored, text):
    s = make(scored=scored, scored_adjusted=scored)
    assert reason(s).startswith(text + ',')


@pytest.mark.parametrize('conceded,text', [
    (1.218, 'solid at the back'),
    (1.22, 'steady at the back'),
    (1.60, 'steady at the back'),
    (1.61, 'leaky at the back'),
])
def test_full_strength_defence_reason(conceded, text):
    s = make(conceded=conceded, conceded_adjusted=conceded)
    assert reason(s).endswith(', ' + text + '.')


def test_full_strength_reason_joined():
    assert reason(make(scored=1.9, scored_adjusted=1.9)) == 'Strong going forward, solid at the back.'


def test_full_strength_even_with_key_players_missing():
    s = make(missing=[player()])
    assert headline(s) == 'Arsenal are at full strength'
    assert reason(s).endswith('.')


def test_no_digits_or_acronyms_anywhere():
    cases = []
    for adj in (2.0, 1.8, 1.5):
        for conc in (1.0, 1.1, 1.3):
            for scored in (1.0, 1.9, 2.5):
                for n in (0, 1, 2, 3):
                    for role, pos in (('attack', 3), ('defence', 2), ('defence', 1)):
                        cases.append(make(scored=scored, scored_adjusted=adj, conceded_adjusted=conc,
                                          missing=[player(role, position=pos) for _ in range(n)]))
    for s in cases:
        out = strength_summary('Arsenal', s)
        for text in out.values():
            assert text
            assert not re.search(r'\d', text)
            assert not re.search(r'\b[A-Z]{2,}\b', text)
