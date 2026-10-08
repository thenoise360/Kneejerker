"""Our expected points model: one gameweek ahead, one model per position.

Gradient-boosted trees with Poisson loss (points are non-negative and skewed). Hyperparameters
are fixed here and only changed on the evidence of the backtest (expectedPointsBacktest.py).
The daily job (run_daily_expected_points, added below) is the only place this is fitted.
"""
import logging
import math
from datetime import datetime

import numpy as np
import requests
from sklearn.ensemble import HistGradientBoostingRegressor

from FPL_site.dataModels import connect_db, current_season_start, refresh_season_start, db
from FPL_site.expectedPointsFeatures import FEATURES, MODEL_VERSION, training_rows, prediction_rows
from FPL_site.expectedPointsRecord import (deadline_for, next_gameweek, is_settled, log_forecasts,
                                           forecast_of_record, template_squad, accuracy_for_gameweek,
                                           persist_accuracy, persist_current, LOG_TABLE, ACCURACY_TABLE)
from FPL_site.fixtureXgHistory import load_fixture_xg, fill_missing
from FPL_site.matchPredictionEngine import fetch_team_code_map, kickoff_in_season_window

logger = logging.getLogger(__name__)

HISTORY_SEASONS = 3   # this season and the two before it
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


#################################################
#                  Fetchers                     #
#################################################

def fetch_events():
    try:
        response = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/', timeout=10)
        response.raise_for_status()
        return response.json().get('events', [])
    except Exception as e:
        logger.error("expected points: could not fetch the official events: %s", type(e).__name__)
        return None


def _codes_by_season(cursor, years):
    """{(year_start, player id): code} from the snapshots (a player's id is per season)."""
    placeholders = ', '.join(['%s'] * len(years))
    cursor.execute(f"""SELECT DISTINCT year_start, id, code FROM {db}.bootstrapstatic_elements
                       WHERE year_start IN ({placeholders})""", tuple(years))
    return {(r['year_start'], r['id']): r['code'] for r in cursor.fetchall()}


def fetch_history_rows(cursor, years):
    codes = _codes_by_season(cursor, years)
    team_maps = {y: fetch_team_code_map(cursor, y) for y in years}
    placeholders = ', '.join(['%s'] * len(years))
    cursor.execute(f"""
        SELECT DISTINCT h.year_start, h.element, h.round, h.fixture, h.opponent_team, h.was_home,
               h.minutes, h.goals_scored, h.assists, h.clean_sheets, h.bonus, h.total_points,
               f.kickoff_time AS kickoff_time,
               CASE WHEN h.was_home = 1 THEN f.team_h ELSE f.team_a END AS team_id
        FROM {db}.elementsummary_history h
        JOIN {db}.fixtures_fixtures f
          ON f.id = h.fixture AND f.year_start = h.year_start AND f.kickoff_time = h.kickoff_time
        WHERE h.year_start IN ({placeholders})
    """, tuple(years))
    rows = []
    for r in cursor.fetchall():
        if not kickoff_in_season_window(r['kickoff_time'], r['year_start']):
            continue
        code = codes.get((r['year_start'], r['element']))
        team_map = team_maps.get(r['year_start'], {})
        if code is None or r['team_id'] not in team_map:
            continue
        rows.append({'code': code, 'year_start': r['year_start'], 'gameweek': r['round'],
                     'team_code': team_map[r['team_id']], 'opponent_code': team_map.get(r['opponent_team']),
                     'was_home': bool(r['was_home']), 'minutes': r['minutes'] or 0,
                     'goals_scored': r['goals_scored'] or 0, 'assists': r['assists'] or 0,
                     'clean_sheets': r['clean_sheets'] or 0, 'bonus': r['bonus'] or 0,
                     'total_points': r['total_points'] or 0})
    return rows


def fetch_snapshot_rows(cursor, years):
    team_maps = {y: fetch_team_code_map(cursor, y) for y in years}
    placeholders = ', '.join(['%s'] * len(years))
    cursor.execute(f"""
        SELECT year_start, gameweek, id, code, element_type, team, now_cost,
               chance_of_playing_next_round, ep_next, expected_goals, expected_assists, selected_by_percent
        FROM {db}.bootstrapstatic_elements WHERE year_start IN ({placeholders})
    """, tuple(years))
    out = []
    for r in cursor.fetchall():
        team_code = team_maps.get(r['year_start'], {}).get(r['team'])
        if team_code is None:
            continue
        out.append({'code': r['code'], 'player_id': r['id'], 'year_start': r['year_start'],
                    'gameweek': r['gameweek'], 'element_type': r['element_type'], 'team_code': team_code,
                    'now_cost': r['now_cost'], 'chance_of_playing_next_round': r['chance_of_playing_next_round'],
                    'ep_next': float(r['ep_next']) if r['ep_next'] is not None else None,
                    'expected_goals': float(r['expected_goals'] or 0),
                    'expected_assists': float(r['expected_assists'] or 0),
                    'selected': float(r['selected_by_percent'] or 0)})
    return out


def fetch_live_fixture_xg(cursor, year_start, gameweek, id_to_code):
    """The coming gameweek from the live engine's stored predictions (team ids are this season's)."""
    cursor.execute(f"""
        SELECT mine.team_id, mine.is_home, mine.expected_goals_mean AS own_mean,
               theirs.expected_goals_mean AS opp_mean
        FROM {db}.team_fixture_predictions mine
        JOIN {db}.team_fixture_predictions theirs
          ON theirs.fixture_code = mine.fixture_code AND theirs.team_id = mine.opponent_id
        WHERE mine.gameweek = %s
    """, (gameweek,))
    out = {}
    for r in cursor.fetchall():
        code = id_to_code.get(r['team_id'])
        if code is None:
            continue
        t = out.setdefault((year_start, gameweek, code),
                           {'team_xg': 0.0, 'opp_xg': 0.0, 'matches': 0, 'home_share': 0.0})
        t['team_xg'] += float(r['own_mean'])
        t['opp_xg'] += float(r['opp_mean'])
        t['home_share'] = (t['home_share'] * t['matches'] + (1.0 if r['is_home'] else 0.0)) / (t['matches'] + 1)
        t['matches'] += 1
    return out


def fetch_actual_points(cursor, year_start, gameweek):
    """{player id: points} for a gameweek; duplicate rows and other seasons' matches are ignored."""
    cursor.execute(f"""SELECT DISTINCT element, fixture, round, kickoff_time, total_points
                       FROM {db}.elementsummary_history WHERE year_start = %s AND round = %s""",
                   (year_start, gameweek))
    points = {}
    for r in cursor.fetchall():
        if kickoff_in_season_window(r['kickoff_time'], year_start):
            points[r['element']] = points.get(r['element'], 0) + int(r['total_points'] or 0)
    return points


def fetch_log_rows(cursor, gameweek):
    cursor.execute(f"""SELECT player_id, code, expected_points, official_expected_points, logged_at
                       FROM {LOG_TABLE} WHERE gameweek = %s AND model_version = %s""",
                   (gameweek, MODEL_VERSION))
    return cursor.fetchall()


def fetch_recorded_gameweeks(cursor, year_start):
    try:
        cursor.execute(f"SELECT gameweek FROM {ACCURACY_TABLE} WHERE year_start = %s AND model_version = %s",
                       (year_start, MODEL_VERSION))
        return {r['gameweek'] for r in cursor.fetchall()}
    except Exception:
        return set()   # the table is created on the first accuracy write


#################################################
#                  Daily job                    #
#################################################

def record_settled_gameweeks(conn, cursor, events, year_start, now):
    """Write accuracy for every settled gameweek we logged forecasts for and haven't recorded."""
    done = fetch_recorded_gameweeks(cursor, year_start)
    snapshots = [s for s in fetch_snapshot_rows(cursor, [year_start])]
    for e in events:
        gw = e['id']
        if gw in done or not is_settled(events, gw):
            continue
        try:
            log_rows = fetch_log_rows(cursor, gw)
        except Exception:
            continue   # no log table yet
        if not log_rows:
            continue
        record = forecast_of_record(log_rows, deadline_for(events, gw))
        before = [s for s in snapshots if s['gameweek'] == gw - 1]
        position = {s['player_id']: s['element_type'] for s in before}
        for pid, r in record.items():
            r['position'] = position.get(pid)
        actual = fetch_actual_points(cursor, year_start, gw)
        squad = template_squad([{'player_id': s['player_id'], 'position': s['element_type'],
                                 'selected': s['selected']} for s in before])
        result = accuracy_for_gameweek(record, actual, squad, set(actual))
        persist_accuracy(conn, gw, year_start, result, now)
        logger.info("Expected points accuracy for gameweek %s: ours %s, official %s.",
                    gw, result['mae_ours'], result['mae_official'])


def run_daily_expected_points(now=None):
    """Train on every finished gameweek, forecast the next one, log it, record settled weeks."""
    now = now or datetime.utcnow()
    refresh_season_start()
    year = current_season_start()
    events = fetch_events()
    if events is None:
        return
    gameweek = next_gameweek(events, now)
    conn = connect_db()
    if conn is None:
        logger.error("run_daily_expected_points: could not connect to the database.")
        return
    try:
        cursor = conn.cursor(dictionary=True)
        years = [year - i for i in range(HISTORY_SEASONS)]
        history = fetch_history_rows(cursor, years)
        snapshots = fetch_snapshot_rows(cursor, years)
        wanted = sorted({(h['year_start'], h['gameweek']) for h in history})
        try:
            fill_missing(conn, cursor, wanted)
        except Exception:
            logger.exception("expected points: filling the historical fixture goals failed, "
                             "carrying on with what is stored.")
            if hasattr(conn, 'rollback'):
                conn.rollback()
        fixture_xg = load_fixture_xg(cursor)
        players = []
        if gameweek is not None:
            players = [s for s in snapshots if s['year_start'] == year and s['gameweek'] == gameweek - 1]
            if not players:
                logger.error("expected points: no snapshot for gameweek %s, so gameweek %s is not forecast "
                             "(did the update job fail today?).", gameweek - 1, gameweek)
        if players:
            models = train(training_rows(history, snapshots, fixture_xg))
            fixture_xg.update(fetch_live_fixture_xg(cursor, year, gameweek, fetch_team_code_map(cursor, year)))
            rows = prediction_rows(history, snapshots, fixture_xg, year, gameweek, players)
            values = predict(models, rows)
            official = {p['player_id']: p['ep_next'] for p in players}
            forecasts = [{'player_id': r['player_id'], 'code': r['code'], 'gameweek': gameweek,
                          'expected_points': v, 'official_expected_points': official.get(r['player_id'])}
                         for r, v in zip(rows, values) if not math.isnan(v)]
            persist_current(conn, forecasts, now)
            log_forecasts(conn, forecasts, gameweek, deadline_for(events, gameweek), now)
        record_settled_gameweeks(conn, cursor, events, year, now)
    finally:
        conn.close()
