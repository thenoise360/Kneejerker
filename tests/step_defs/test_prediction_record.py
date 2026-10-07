import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.recordCopy import record_summary

scenarios('team/prediction_record.feature')


def _games(count, better_by):
    # Predicted 1-1 every time; the actual scoreline is shifted by the average.
    return [{'predicted_for': 1.0, 'predicted_against': 1.0,
             'actual_for': 1.0 + better_by, 'actual_against': 1.0}
            for _ in range(count)]


@given(parsers.parse('{count:d} finished games averaging {better:f} better than predicted'),
       target_fixture='ctx')
def finished_games(count, better):
    return {'games': _games(count, better), 'started_on': '2026-10-01'}


@given(parsers.parse('no finished games, with scoring started on "{date}"'),
       target_fixture='ctx')
def no_games(date):
    return {'games': [], 'started_on': date}


@when(parsers.parse('the record summary is written for "{team}"'))
def write_summary(ctx, team):
    ctx['result'] = record_summary(team, ctx['games'], ctx['started_on'])


@then(parsers.parse('the headline is "{text}"'))
def headline(ctx, text):
    assert ctx['result']['headline'] == text


@then(parsers.parse('the reason mentions "{text}"'))
def reason_mentions(ctx, text):
    assert text in ctx['result']['reason']


@then('early days is false')
def early_false(ctx):
    assert ctx['result']['early_days'] is False


@then('early days is true')
def early_true(ctx):
    assert ctx['result']['early_days'] is True
