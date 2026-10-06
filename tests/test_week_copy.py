import os; os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import re
import pytest
from FPL_site.weekCopy import this_week_empty_copy, last_week_empty_copy

ACRONYMS = ['FPL', 'GW', 'XG', 'XA', 'ICT', 'DGW', 'BGW']
KEYS = {'eyebrow', 'title', 'body'}


def _has_acronym(copy):
    text = ' '.join(copy.values())
    return any(re.search(r'\b%s\b' % a, text, re.I) for a in ACRONYMS)


@pytest.mark.parametrize('mode', ['pre_season', 'off_season', 'unavailable', 'confirming'])
def test_this_week_modes_have_copy(mode):
    c = this_week_empty_copy(mode)
    assert set(c) == KEYS and all(c.values())
    assert not _has_acronym(c)


@pytest.mark.parametrize('mode', ['live', 'upcoming', 'nonsense', None])
def test_this_week_other_modes_none(mode):
    assert this_week_empty_copy(mode) is None


def test_pre_season_and_off_season_wording():
    assert 'kicked off' in this_week_empty_copy('pre_season')['body']
    assert 'breather' in this_week_empty_copy('off_season')['body']


def test_unavailable_reassures():
    assert 'check back shortly' in this_week_empty_copy('unavailable')['body']


def test_confirming_tiers():
    assert 'being checked' in this_week_empty_copy('confirming', 95)['body']
    assert 'longer than usual' in this_week_empty_copy('confirming', 96)['body']
    assert 'being checked' in this_week_empty_copy('confirming', None)['body']
    assert 'being checked' in this_week_empty_copy('confirming')['body']
    assert 'longer than usual' in this_week_empty_copy('confirming', 200)['body']


def test_last_week_none():
    c = last_week_empty_copy('none')
    assert 'first recap' in c['body'] and not _has_acronym(c)


def test_last_week_confirming_mentions_gameweek():
    c = last_week_empty_copy('confirming', 7)
    assert 'ameweek 7' in c['body']
    assert 'confirmed' in c['body'] and not _has_acronym(c)


def test_last_week_final_and_unknown_none():
    assert last_week_empty_copy('final', 7) is None
    assert last_week_empty_copy('weird') is None


def test_last_week_confirming_without_gameweek():
    c = last_week_empty_copy('confirming')
    assert c and 'None' not in ' '.join(c.values())
