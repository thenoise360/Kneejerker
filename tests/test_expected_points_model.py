import math
import os
import random
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')

from FPL_site import expectedPointsModel as em
from FPL_site.expectedPointsFeatures import FEATURES


def synthetic(n, position, seed=0):
    rnd = random.Random(seed)
    rows = []
    for _ in range(n):
        form = rnd.uniform(0, 10)
        row = {f: rnd.uniform(0, 3) for f in FEATURES}
        row.update({'points_last_5': form, 'matches_in_gameweek': 1.0, 'position': position,
                    'target': max(-2, round(form + rnd.gauss(0, 1)))})
        rows.append(row)
    return rows


def test_one_model_per_position_with_enough_rows():
    models = em.train(synthetic(200, 3) + synthetic(200, 4, seed=1) + synthetic(10, 1, seed=2))
    assert set(models) == {3, 4}


def test_negative_points_do_not_break_training_and_predictions_are_never_negative():
    rows = synthetic(300, 2)
    rows[0]['target'] = -2
    models = em.train(rows)
    preds = em.predict(models, rows)
    assert all(p >= 0 for p in preds)


def test_better_form_predicts_more_points():
    models = em.train(synthetic(600, 3))
    low, high = dict(synthetic(1, 3)[0]), dict(synthetic(1, 3)[0])
    low['points_last_5'], high['points_last_5'] = 1.0, 9.0
    p_low, p_high = em.predict(models, [low, high])
    assert p_high > p_low


def test_no_match_means_zero_and_an_unmodelled_position_means_nan():
    models = em.train(synthetic(200, 3))
    blank = dict(synthetic(1, 3)[0], matches_in_gameweek=0.0)
    keeper = dict(synthetic(1, 1)[0])
    assert em.predict(models, [blank, keeper])[0] == 0.0
    assert math.isnan(em.predict(models, [blank, keeper])[1])


def test_missing_feature_values_are_accepted():
    rows = synthetic(200, 3)
    for r in rows[:50]:
        r['xg_last_5'] = float('nan')
    models = em.train(rows)
    assert len(em.predict(models, rows)) == 200
