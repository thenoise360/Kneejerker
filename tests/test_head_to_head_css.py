import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import re

CSS = open(os.path.join(os.path.dirname(__file__), '..', 'FPL_site', 'static', 'content', 'home.css'),
           encoding='utf-8').read()


def test_expanded_row_with_meetings_has_room_and_text_wraps():
    # The shared row caps its height at 500px; the meetings block adds about 190px at 375px wide,
    # so a row that holds it must be allowed more room or the caveat line is clipped.
    rule = re.search(r'\.outlook-row\.expanded \.outlook-detail:has\(\.h2h-block\)\s*\{([^}]*)\}', CSS)
    assert rule, 'missing room rule for rows with the meetings block'
    assert int(re.search(r'max-height:\s*(\d+)px', rule.group(1)).group(1)) >= 800
    # Long lines must wrap rather than push the page sideways.
    assert re.search(r'\.h2h-list li\s*\{[^}]*overflow-wrap:\s*anywhere', CSS)
    assert re.search(r'\.h2h-block\s*\{[^}]*min-width:\s*0', CSS)
