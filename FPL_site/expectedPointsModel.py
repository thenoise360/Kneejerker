"""Our expected points model: one gameweek ahead, one model per position.

Gradient-boosted trees with Poisson loss (points are non-negative and skewed). Hyperparameters
are fixed here and only changed on the evidence of the backtest (expectedPointsBacktest.py).
The daily job (run_daily_expected_points, added below) is the only place this is fitted.
"""
import logging
import math

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from FPL_site.expectedPointsFeatures import FEATURES, MODEL_VERSION

logger = logging.getLogger(__name__)

MIN_ROWS_PER_POSITION = 50
PARAMS = dict(loss='poisson', learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
              min_samples_leaf=40, l2_regularization=1.0, random_state=0)


def _matrix(rows):
    return np.array([[float(r[f]) for f in FEATURES] for r in rows], dtype=float)


def train(rows):
    models = {}
    by_position = {}
    for r in rows:
        by_position.setdefault(r['position'], []).append(r)
    for position, group in by_position.items():
        if len(group) < MIN_ROWS_PER_POSITION:
            logger.warning("expected points: only %d rows for position %s, no model.", len(group), position)
            continue
        target = np.array([max(0.0, float(r['target'])) for r in group])
        models[position] = HistGradientBoostingRegressor(**PARAMS).fit(_matrix(group), target)
    return models


def predict(models, rows):
    out = [math.nan] * len(rows)
    by_position = {}
    for i, r in enumerate(rows):
        if float(r.get('matches_in_gameweek') or 0) == 0:
            out[i] = 0.0
        elif r['position'] in models:
            by_position.setdefault(r['position'], []).append(i)
    for position, idx in by_position.items():
        values = models[position].predict(_matrix([rows[i] for i in idx]))
        for i, v in zip(idx, values):
            out[i] = round(max(0.0, float(v)), 1)
    return out
