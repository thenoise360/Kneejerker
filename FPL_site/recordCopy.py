"""Deterministic phrase bank for the Team page's "do they beat their chances" record.

No randomness: every phrase is chosen by an explicit threshold, and each
threshold has a test on both sides of it. No digits and no acronyms in any
output, apart from the date in the "no games yet" sentence (a label, not a statistic).
"""
from datetime import date

EARLY_DAYS_BELOW = 8   # fewer logged games than this and the record is "early days"
TREND_FROM = 0.5       # average goal difference per game, actual minus predicted
GAME_MARGIN = 1.0      # one game counts as better or worse at this size of gap


def _round(value):
    # Rounding stops float noise tipping a boundary the wrong way.
    return round(value, 9)


def _difference(game):
    """Actual goal difference minus predicted goal difference for one game."""
    actual = game['actual_for'] - game['actual_against']
    predicted = game['predicted_for'] - game['predicted_against']
    return _round(actual - predicted)


def game_verdict(predicted_for, predicted_against, actual_for, actual_against):
    """'better', 'as_expected' or 'worse' for a single finished game."""
    gap = _difference({'predicted_for': predicted_for, 'predicted_against': predicted_against,
                       'actual_for': actual_for, 'actual_against': actual_against})
    if gap >= GAME_MARGIN:
        return 'better'
    if gap <= -GAME_MARGIN:
        return 'worse'
    return 'as_expected'


def _average_difference(games):
    return _round(sum(_difference(g) for g in games) / len(games))


def _format_date(started_on):
    d = date.fromisoformat(started_on)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def _no_games(started_on):
    if started_on:
        reason = (f'We started keeping score on {_format_date(started_on)}. '
                  'Check back after their next game.')
    else:
        reason = "We'll start keeping score from their next game."
    return {'headline': 'No finished games logged yet', 'reason': reason, 'early_days': True}


def record_summary(team_name, games, started_on):
    """One headline and one reason for how a team's results compare with their chances."""
    if not games:
        return _no_games(started_on)

    average = _average_difference(games)
    early_days = len(games) < EARLY_DAYS_BELOW

    if average >= TREND_FROM:
        headline = f'{team_name} have been beating their chances'
        reason = ("They've been winning by more than their chances suggest. "
                  'That tends not to last.')
    elif average <= -TREND_FROM:
        headline = f'{team_name} have been falling short of their chances'
        reason = ("They've been doing worse than their chances suggest. "
                  'That tends to turn around.')
    else:
        headline = f'{team_name} are performing about as expected'
        reason = 'Their results have matched their chances so far.'
    return {'headline': headline, 'reason': reason, 'early_days': early_days}
