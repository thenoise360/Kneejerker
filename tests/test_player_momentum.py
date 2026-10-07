import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

import re

from FPL_site.playerMomentum import (fixtures_signal, teammates_signal, not_tracked,
                                     player_momentum)
from FPL_site.momentumCopy import momentum_reason, DIRECTION_WORDS, SIGNAL_NAMES


def _fx(mean_own, mean_opp):
    return [{'own_mean': mean_own, 'opp_mean': mean_opp}] * 3


def _mate(name='Saka', share=0.2, status='a', played_last=False, chance=None, id=9):
    return {'id': id, 'name': name, 'share': share, 'status': status,
            'played_last': played_last, 'chance': chance}


# fixtures ----------------------------------------------------------------

def test_attacker_boundary_up():
    assert fixtures_signal(4, _fx(1.1, 1), 1.0, 1.0)['direction'] == 'up'
    assert fixtures_signal(3, _fx(1.099, 1), 1.0, 1.0)['direction'] == 'same'


def test_attacker_boundary_down():
    assert fixtures_signal(4, _fx(0.9, 1), 1.0, 1.0)['direction'] == 'down'
    assert fixtures_signal(4, _fx(0.901, 1), 1.0, 1.0)['direction'] == 'same'


def test_defender_fixture_direction():
    # Opponents expected to score less than average is kinder for a defender.
    assert fixtures_signal(2, _fx(1, 0.9), 1.0, 1.0)['direction'] == 'up'
    assert fixtures_signal(1, _fx(1, 0.901), 1.0, 1.0)['direction'] == 'same'
    assert fixtures_signal(2, _fx(1, 1.1), 1.0, 1.0)['direction'] == 'down'
    assert fixtures_signal(2, _fx(1, 1.099), 1.0, 1.0)['direction'] == 'same'


def test_fixture_reasons():
    assert fixtures_signal(4, _fx(1.5, 1), 1.0, 1.0)['reason'] == 'kinder fixtures coming up'
    assert fixtures_signal(4, _fx(0.5, 1), 1.0, 1.0)['reason'] == 'tougher fixtures coming up'
    assert fixtures_signal(4, _fx(1.0, 1), 1.0, 1.0)['reason'] == 'fixtures look about average'


def test_fixture_magnitude():
    assert abs(fixtures_signal(4, _fx(1.3, 1), 1.0, 1.0)['magnitude'] - 0.3) < 1e-9


def test_blank_gameweek_fixtures_signal():
    sig = fixtures_signal(4, [], 1.0, 1.0)
    assert (sig['direction'], sig['reason'], sig['magnitude']) == ('same', 'no game this week', 0)


def test_double_gameweek_averages_both_fixtures():
    upcoming = [{'own_mean': 1.4, 'opp_mean': 1}, {'own_mean': 0.8, 'opp_mean': 1}]
    assert fixtures_signal(4, upcoming, 1.0, 1.0)['direction'] == 'up'


# teammates ---------------------------------------------------------------

def test_key_share_boundary():
    assert teammates_signal(1, [_mate(share=0.15)])['direction'] == 'up'
    assert teammates_signal(1, [_mate(share=0.149)])['direction'] == 'same'


def test_out_below_chance_boundary():
    out49 = _mate(played_last=True, chance=49)
    out50 = _mate(played_last=True, chance=50)
    assert teammates_signal(1, [out49])['direction'] == 'down'
    assert teammates_signal(1, [out50])['direction'] == 'same'


def test_back_chance_boundary():
    assert teammates_signal(1, [_mate(chance=50)])['direction'] == 'up'
    assert teammates_signal(1, [_mate(chance=49)])['direction'] == 'same'


def test_departed_teammate_ignored():
    assert teammates_signal(1, [_mate(status='u')])['direction'] == 'same'


def test_player_themselves_ignored():
    assert teammates_signal(9, [_mate(id=9)])['direction'] == 'same'


def test_one_back_versus_several_back_wording():
    assert teammates_signal(1, [_mate('Saka')])['reason'] == 'Saka is back in the team'
    assert teammates_signal(1, [_mate('Saka'), _mate('Rice', id=10)])['reason'] == 'key teammates are back'


def test_one_out_versus_several_out_wording():
    one = _mate('Palmer', played_last=True, chance=0)
    two = _mate('Rice', played_last=True, chance=0, id=10)
    assert teammates_signal(1, [one])['reason'] == 'Palmer is out'
    assert teammates_signal(1, [one, two])['reason'] == 'key teammates are out'


def test_back_and_out_balance():
    sig = teammates_signal(1, [_mate(), _mate('Rice', played_last=True, chance=0, id=10)])
    assert sig['direction'] == 'same' and sig['reason'] == 'no change around them'


def test_teammate_magnitude_sums_shares():
    sig = teammates_signal(1, [_mate(share=0.2), _mate(share=0.3, id=10)])
    assert abs(sig['magnitude'] - 0.5) < 1e-9


def test_not_tracked_shape():
    assert not_tracked('manager') == {'key': 'manager', 'direction': 'not_tracked',
                                      'reason': None, 'magnitude': 0}


# combining ---------------------------------------------------------------

def _sig(key, direction, magnitude=0.2, reason='kinder fixtures coming up'):
    return {'key': key, 'direction': direction, 'reason': reason, 'magnitude': magnitude}


def test_label_thresholds():
    up, same, down = (_sig('fixtures', d) for d in ('up', 'same', 'down'))
    t_up, t_same, t_down = (_sig('teammates', d) for d in ('up', 'same', 'down'))
    assert player_momentum(up, t_up)['label'] == 'Rising'       # +2
    assert player_momentum(up, t_same)['label'] == 'Rising'     # +1
    assert player_momentum(same, t_same)['label'] == 'Steady'   # 0
    assert player_momentum(up, t_down)['label'] == 'Steady'     # 0
    assert player_momentum(same, t_down)['label'] == 'Cooling'  # -1
    assert player_momentum(down, t_down)['label'] == 'Cooling'  # -2


def test_fixed_signal_order():
    result = player_momentum(_sig('fixtures', 'same'), _sig('teammates', 'same'))
    assert [s['key'] for s in result['signals']] == ['fixtures', 'teammates', 'position', 'manager']
    assert [s['direction'] for s in result['signals'][2:]] == ['not_tracked', 'not_tracked']


def test_strongest_signal_gives_reason():
    fx = _sig('fixtures', 'up', 0.3, 'kinder fixtures coming up')
    tm = _sig('teammates', 'up', 0.2, 'Saka is back in the team')
    assert player_momentum(fx, tm)['reason'] == 'Rising: Kinder fixtures coming up.'
    tm = _sig('teammates', 'up', 0.4, 'Saka is back in the team')
    assert player_momentum(fx, tm)['reason'] == 'Rising: Saka is back in the team.'


def test_cooling_reason_and_steady_reason():
    fx = _sig('fixtures', 'down', 0.3, 'tougher fixtures coming up')
    tm = _sig('teammates', 'same', 0, 'no change around them')
    assert player_momentum(fx, tm)['reason'] == 'Cooling: tougher fixtures coming up.'
    same = _sig('fixtures', 'same', 0)
    assert player_momentum(same, tm)['reason'] == 'Steady: nothing much has changed for them this week.'


def test_score_signed_and_scaled():
    fx = _sig('fixtures', 'up', 0.3)
    tm = _sig('teammates', 'down', 0.1)
    result = player_momentum(fx, tm)
    assert abs(result['score'] - (0 + 0.1 * 0.2)) < 1e-9


def test_labels_and_words():
    assert DIRECTION_WORDS == {'up': 'Up', 'same': 'No change', 'down': 'Down',
                               'not_tracked': 'Not tracked yet'}
    assert SIGNAL_NAMES['position'] == 'Position on the pitch'
    assert SIGNAL_NAMES['manager'] == 'Manager change'


def test_no_digits_or_acronyms_in_any_reason():
    reasons = []
    for pos in (1, 2, 3, 4):
        for own in (0.5, 1.0, 1.5):
            reasons.append(fixtures_signal(pos, _fx(own, own), 1.0, 1.0)['reason'])
    reasons.append(fixtures_signal(4, [], 1.0, 1.0)['reason'])
    out = dict(played_last=True, chance=0)
    for mates in ([_mate()], [_mate(), _mate(id=10)], [_mate(**out)],
                  [_mate(**out), _mate(id=10, **out)], []):
        reasons.append(teammates_signal(1, mates)['reason'])
    texts = list(reasons)
    for label in ('Rising', 'Steady', 'Cooling'):
        texts += [momentum_reason(label, {'reason': r}) for r in reasons]
    texts += list(DIRECTION_WORDS.values()) + list(SIGNAL_NAMES.values())
    for text in texts:
        assert not re.search(r'\d', text), text
        assert not re.search(r'\b[A-Z]{2,}\b', text), text
