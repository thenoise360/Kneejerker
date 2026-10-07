"""Deterministic phrase bank for the Week tab's biggest decision.

Every decision is framed as the user's call, and always carries a reason.
"""

KIND_FIXTURE_UP_TO = 2
TOUGH_FIXTURE_FROM = 4


def fixture_phrase(fixture):
    if not fixture:
        return ''
    where = f"at home to {fixture['opponent']}" if fixture['is_home'] else f"away at {fixture['opponent']}"
    if fixture['difficulty'] <= KIND_FIXTURE_UP_TO:
        return f', with a kind fixture {where}'
    if fixture['difficulty'] >= TOUGH_FIXTURE_FROM:
        return f', even with a tough fixture {where}'
    return f', {where}'


def availability_decision(name, chance, news):
    status = 'is set to miss this week' if chance == 0 else 'is a doubt this week'
    details = [f'Chance of playing: {chance}%']
    if news:
        details.append(f'Latest news: {news}')
    return {'kind': 'availability', 'title': f'Have a look at {name}',
            'reason': f"We're seeing that {name} {status}. Worth deciding whether to bring in "
                      f"cover, or keep faith. It's your call.",
            'details': details}


def captain_decision(best_name, best_prediction, current_name, fixture):
    details = [f'Our prediction for {best_name}: about {best_prediction:.1f} points']
    where = fixture_phrase(fixture)
    if best_name == current_name:
        return {'kind': 'captain', 'title': f'Captain: {best_name} looks right',
                'reason': f"We're seeing {best_name} as your strongest option{where}. Sticking "
                          f"with them looks sound. It's your call.",
                'details': details}
    return {'kind': 'captain', 'title': f'Captain: worth a look at {best_name}',
            'reason': f"We're seeing {best_name} as your strongest option{where}, ahead of "
                      f"{current_name}. It's your call.",
            'details': details}


def guest_captain_decision(best_name, best_prediction, fixture):
    return {'kind': 'captain', 'title': f'Captain: {best_name} stands out',
            'reason': f"Across every team, {best_name} is the strongest option we're "
                      f"seeing{fixture_phrase(fixture)}. If you have them, they're worth a "
                      f"look as captain. It's your call.",
            'details': [f'Our prediction for {best_name}: about {best_prediction:.1f} points']}


def no_decision_copy():
    return {'title': 'Nothing pressing yet',
            'body': "We're still working out this week's picture. Check back closer to the deadline."}
