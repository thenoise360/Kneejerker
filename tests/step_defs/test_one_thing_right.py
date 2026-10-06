import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from pytest_bdd import scenarios, given, when, then, parsers

from FPL_site.recapCopy import pick_one_thing_right

scenarios('week/one_thing_right.feature')


def sp(pid, name, points, captain=False, multiplier=1, minutes=90, difficulty=3):
    return {'id': pid, 'name': name, 'is_captain': captain,
            'multiplier': 2 if captain else multiplier, 'points': points,
            'minutes': minutes, 'difficulty': difficulty}


@given(parsers.parse('a squad where captain "{name}" scored {points:d} points'), target_fixture='squad')
def captain_scored(name, points):
    return [sp(1, name, points, captain=True), sp(2, 'Other', 2)]


@given(parsers.parse('a squad where nobody scored more than {points:d} points'), target_fixture='squad')
def low_scoring(points):
    return [sp(1, 'Cap', min(points, 1), captain=True, difficulty=4), sp(2, 'Mid', points, difficulty=4)]


@given(parsers.parse('a squad where nobody scored more than {points:d} point'), target_fixture='squad')
def very_low_scoring(points):
    return [sp(1, 'Cap', points, captain=True, difficulty=4), sp(2, 'Mid', points, difficulty=4)]


@given(parsers.parse('starter "{name}" blanked with {points:d} point in a kind fixture'))
def kind_blank(squad, name, points):
    squad.append(sp(3, name, points, difficulty=2))


@given('a squad with no player results', target_fixture='squad')
def no_results():
    return [sp(1, 'Unknown', 0, captain=True, minutes=0, difficulty=None)]


@when('we look for one thing they got right', target_fixture='result')
def look(squad):
    return pick_one_thing_right(squad)


@then(parsers.parse('the tier is "{tier}"'))
def tier_is(result, tier):
    assert result['tier'] == tier


@then(parsers.parse('the reason mentions "{text}"'))
def reason_mentions(result, text):
    assert text in result['reason']
