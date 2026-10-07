import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.squadContext import (
    squad_from_picks, base_picks_gameweek, apply_transfers, bank_after, get_squad_context,
)
import FPL_site.squadContext as squad_context


def _pick(element, position, captain=False, vice=False, multiplier=1):
    return {'element': element, 'position': position, 'multiplier': multiplier,
            'is_captain': captain, 'is_vice_captain': vice}


def test_starters_are_positions_one_to_eleven_even_with_bench_boost():
    # Bench Boost gives bench players multiplier 1, so position is the only safe signal.
    squad = squad_from_picks({'picks': [_pick(1, 11), _pick(2, 12, multiplier=1)]})
    assert [p['starter'] for p in squad] == [True, False]


def test_armbands_are_read():
    squad = squad_from_picks({'picks': [_pick(1, 1, captain=True), _pick(2, 2, vice=True)]})
    assert squad[0]['is_captain'] and squad[1]['is_vice']


def test_free_hit_goes_back_one_gameweek():
    assert base_picks_gameweek(5, {'active_chip': 'freehit'}) == 4
    assert base_picks_gameweek(5, {'active_chip': 'wildcard'}) == 5
    assert base_picks_gameweek(5, {'active_chip': None}) == 5


def test_transfers_apply_in_time_order_and_drop_armbands():
    squad = [{'id': 1, 'slot': 1, 'starter': True, 'is_captain': True, 'is_vice': False}]
    transfers = [
        {'element_out': 9, 'element_in': 7, 'event': 6, 'time': '2026-10-08T10:00:00Z',
         'element_in_cost': 50, 'element_out_cost': 50},
        {'element_out': 1, 'element_in': 9, 'event': 6, 'time': '2026-10-07T10:00:00Z',
         'element_in_cost': 50, 'element_out_cost': 50},
    ]
    result, applied = apply_transfers(squad, transfers, after_gameweek=5)
    assert result == [{'id': 7, 'slot': 1, 'starter': True, 'is_captain': False, 'is_vice': False}]
    assert len(applied) == 2


def test_older_and_skipped_transfers_are_ignored():
    squad = [{'id': 1, 'slot': 1, 'starter': True, 'is_captain': False, 'is_vice': False}]
    transfers = [{'element_out': 1, 'element_in': 2, 'event': 5, 'time': 't',
                  'element_in_cost': 50, 'element_out_cost': 50}]
    assert apply_transfers(squad, transfers, after_gameweek=5)[0][0]['id'] == 1
    assert apply_transfers(squad, transfers, after_gameweek=4, skip_events=(5,))[0][0]['id'] == 1


def test_transfer_of_unknown_player_is_skipped_not_crashed():
    squad = [{'id': 1, 'slot': 1, 'starter': True, 'is_captain': False, 'is_vice': False}]
    transfers = [{'element_out': 99, 'element_in': 2, 'event': 6, 'time': 't',
                  'element_in_cost': 50, 'element_out_cost': 50}]
    result, applied = apply_transfers(squad, transfers, after_gameweek=5)
    assert result[0]['id'] == 1 and applied == []


def test_bank_moves_with_transfers_and_never_goes_negative():
    applied = [{'element_in_cost': 60, 'element_out_cost': 55}]
    assert bank_after(13, applied) == 8
    assert bank_after(3, applied) == 0


def test_picks_failure_status_is_passed_through(monkeypatch):
    monkeypatch.setattr(squad_context, 'fetch_entry_picks', lambda e, g: ('not_found', None))
    monkeypatch.setattr(squad_context, 'fetch_entry_transfers', lambda e: ('ok', []))
    assert get_squad_context(1, 5) == {'status': 'not_found'}


def test_transfers_outage_means_unavailable(monkeypatch):
    monkeypatch.setattr(squad_context, 'fetch_entry_picks',
                        lambda e, g: ('ok', {'picks': [], 'entry_history': {'bank': 0}}))
    monkeypatch.setattr(squad_context, 'fetch_entry_transfers', lambda e: ('unavailable', None))
    assert get_squad_context(1, 5) == {'status': 'unavailable'}


def test_no_last_gameweek_means_no_squad():
    assert get_squad_context(1, None) == {'status': 'unavailable'}
