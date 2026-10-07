"""Deterministic phrase bank for the player momentum label ("Rising, Steady or Cooling").

No randomness, no digits and no acronyms in any output.
"""

STEADY_REASON = 'Steady: nothing much has changed for them this week.'

DIRECTION_WORDS = {'up': 'Up', 'same': 'No change', 'down': 'Down', 'not_tracked': 'Not tracked yet'}

SIGNAL_NAMES = {'fixtures': 'Fixtures', 'teammates': 'Teammates',
                'position': 'Position on the pitch', 'manager': 'Manager change'}



def momentum_reason(label, signal):
    """One sentence for the label. `signal` is the strongest signal pointing the same way."""
    if label == 'Rising':
        return 'Rising: %s.' % signal['reason']
    if label == 'Cooling':
        return 'Cooling: %s.' % signal['reason']
    return STEADY_REASON
