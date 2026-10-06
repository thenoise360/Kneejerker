import os; os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import re
import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from FPL_site.weekCopy import this_week_empty_copy

scenarios('week/empty_states.feature')

ACRONYMS = ['FPL', 'GW', 'XG', 'XA', 'ICT', 'DGW', 'BGW']
ERROR_WORDS = ['error', 'failed', 'fail', 'invalid', 'oops']


@pytest.fixture
def ctx():
    return {}


@given('I have been away for weeks')
def _away(ctx):
    ctx['away'] = True


@when(parsers.parse('I ask for the this week copy for "{mode}"'))
def _ask(ctx, mode):
    ctx['copy'] = this_week_empty_copy(mode)


@then('I get a title, eyebrow and body')
def _keys(ctx):
    assert all(ctx['copy'][k] for k in ('title', 'eyebrow', 'body'))


@then('the copy contains no acronyms')
def _no_acr(ctx):
    text = ' '.join(ctx['copy'].values())
    assert not any(re.search(r'\b%s\b' % a, text, re.I) for a in ACRONYMS)


@then("the body says nothing is wrong on the user's side")
def _reassure(ctx):
    assert 'nothing' in ctx['copy']['body'].lower() and 'your side' in ctx['copy']['body']


@then('there is no copy')
def _none(ctx):
    assert ctx['copy'] is None


@then('the body mentions a breather')
def _breather(ctx):
    assert 'breather' in ctx['copy']['body']


@then('the copy does not read like an error')
def _not_error(ctx):
    text = ' '.join(ctx['copy'].values()).lower()
    assert not any(w in text for w in ERROR_WORDS)
