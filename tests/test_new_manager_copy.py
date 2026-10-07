import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site.dataModels import new_manager_reason


def test_new_manager_reason_is_plain_words():
    assert new_manager_reason('Slot', 7) == "New manager (Slot) since gameweek 7. Their role could change."
