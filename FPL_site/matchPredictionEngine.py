#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Match outcome prediction engine (Kneejerker Tasks/07 Team page, Ticket 01).

Fits a time-decayed Dixon-Coles Poisson model - joint attack/defence ratings
per team plus a low-scoring correlation adjustment - and outputs a goal
distribution (mean/low/high) per team per fixture, not a single scalar score.

Architecture mirrors futurePerformanceModel.py's daily-job/live-route split:
run_daily_match_predictions() does the expensive fitting once a day and
persists the result; load_team_fixture_outlook() is the cheap read a live
Flask route calls, so no model fitting ever happens inside a web request.

Team ids in bootstrapstatic_teams / fixtures_fixtures are re-issued every
season, so a team's rating is tracked by its stable `code` (pulse id)
instead, pooled with time-decay across HISTORY_SEASONS_BACK completed
seasons plus the current one. A team with few or no fixtures under its code
this season (newly promoted, or not yet started) is treated as low-data and
gets a deliberately wider range rather than a false-precision one.
"""

import logging
from datetime import datetime

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson, nbinom

from FPL_site.dataModels import connect_db, generateCurrentGameweek, db, season_start
from FPL_site.teamStrength import build_team_strengths, fetch_squad_rows, persist_team_strengths

logger = logging.getLogger(__name__)

PREDICTIONS_TABLE = 'team_fixture_predictions'
LOG_TABLE = 'fixture_prediction_log'
# Bump whenever the model changes, so the record can tell versions apart.
MODEL_VERSION = 'dixon-coles-2026-10'
KICKOFF_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

GAMEWEEKS_PER_SEASON = 38
HISTORY_SEASONS_BACK = 3          # completed seasons pooled alongside the current one
DECAY_RATE = 0.02                 # per-gameweek exponential decay across the pooled timeline
STABLE_GAMES_THIS_SEASON = 5      # games played this season before a team's range stops widening
MAX_DISPERSION = 1.0 + STABLE_GAMES_THIS_SEASON * 0.3
# Gameweek 0 (true preseason) hits every team with the full low-data penalty
# at once, since nobody has a game this season yet - halve it rather than
# applying the same widening reserved for an individual team with a genuine
# data gap mid-season.
PRESEASON_DISPERSION_CAP = 1.0 + (MAX_DISPERSION - 1.0) * 0.5
CONFIDENCE = 0.50                 # width of the reported low/high range (0.50 = 25th-75th percentile)
HOME_ADV_INIT = 0.25

NEXT_N_GAMEWEEKS = 5

#################################################
#               Data fetching                  #
#################################################

def fetch_teams_for_season(cursor, year_start):
    """id -> row for one season's team roster (id is only valid within that year_start)."""
    cursor.execute(
        f"SELECT id, code, name, short_name FROM {db}.bootstrapstatic_teams WHERE year_start = %s",
        (year_start,)
    )
    return {row['id']: row for row in cursor.fetchall()}


def fetch_finished_fixtures(cursor, year_start):
    cursor.execute(
        f"""SELECT event, team_h, team_a, team_h_score, team_a_score
            FROM {db}.fixtures_fixtures
            WHERE year_start = %s AND finished = 1
              AND team_h_score IS NOT NULL AND team_a_score IS NOT NULL""",
        (year_start,)
    )
    return cursor.fetchall()


def fetch_upcoming_fixtures(cursor, year_start, from_gw, to_gw):
    cursor.execute(
        f"""SELECT code, event, team_h, team_a, kickoff_time
            FROM {db}.fixtures_fixtures
            WHERE year_start = %s AND finished = 0
              AND event BETWEEN %s AND %s""",
        (year_start, from_gw, to_gw)
    )
    return cursor.fetchall()


#################################################
#      Pooled, time-decayed rating dataset      #
#################################################

def _season_pool(current_season):
    """Oldest -> newest: HISTORY_SEASONS_BACK completed seasons, then the current one."""
    return [current_season - offset for offset in range(HISTORY_SEASONS_BACK, -1, -1)]


def build_rating_dataset(cursor, current_season, current_gw, current_season_max_event=None):
    """
    Pools finished fixtures across the season window, keyed by each team's
    stable `code` rather than its season-local `id`. `current_season_max_event`
    lets backtest_model() simulate "as of gameweek N" by dropping later
    fixtures from the current/target season only - prior seasons stay whole.
    """
    seasons = _season_pool(current_season)
    rows = []
    codes_seen = set()
    games_this_season = {}

    for season_index, year_start in enumerate(seasons):
        teams = fetch_teams_for_season(cursor, year_start)
        if not teams:
            continue
        id_to_code = {tid: t['code'] for tid, t in teams.items()}
        season_offset = season_index * GAMEWEEKS_PER_SEASON

        for fx in fetch_finished_fixtures(cursor, year_start):
            if (year_start == current_season and current_season_max_event is not None
                    and fx['event'] >= current_season_max_event):
                continue

            code_h = id_to_code.get(fx['team_h'])
            code_a = id_to_code.get(fx['team_a'])
            if code_h is None or code_a is None:
                continue

            rows.append({
                'code_h': code_h, 'code_a': code_a,
                'goals_h': int(fx['team_h_score']), 'goals_a': int(fx['team_a_score']),
                'unified_gw': season_offset + fx['event'],
            })
            codes_seen.add(code_h)
            codes_seen.add(code_a)

            if year_start == current_season:
                games_this_season[code_h] = games_this_season.get(code_h, 0) + 1
                games_this_season[code_a] = games_this_season.get(code_a, 0) + 1

    reference_gw = (len(seasons) - 1) * GAMEWEEKS_PER_SEASON + max(current_gw, 1)
    return rows, sorted(codes_seen), games_this_season, reference_gw


#################################################
#   Dixon-Coles fit: joint attack/defence +     #
#   low-scoring correlation, time-decayed       #
#################################################

def _unpack_theta(theta, n):
    """theta = [attack_1..attack_{n-1} (attack_0 fixed at 0), defence_0..defence_{n-1}, home_adv, rho]."""
    attack = np.zeros(n)
    attack[1:] = theta[0:n - 1]
    defence = theta[n - 1:2 * n - 1]
    home_adv = theta[2 * n - 1]
    rho = theta[2 * n]
    return attack, defence, home_adv, rho


def _dc_tau(x, y, lam, mu, rho):
    """Dixon-Coles low-score correction so 0-0/1-0/0-1/1-1 aren't systematically underpredicted."""
    tau = np.ones_like(lam)
    tau = np.where((x == 0) & (y == 0), 1 - lam * mu * rho, tau)
    tau = np.where((x == 0) & (y == 1), 1 + lam * rho, tau)
    tau = np.where((x == 1) & (y == 0), 1 + mu * rho, tau)
    tau = np.where((x == 1) & (y == 1), 1 - rho, tau)
    return tau


def _dixon_coles_nll(theta, n, idx_h, idx_a, goals_h, goals_a, weights):
    attack, defence, home_adv, rho = _unpack_theta(theta, n)
    lam = np.clip(np.exp(attack[idx_h] + defence[idx_a] + home_adv), 1e-6, 15.0)
    mu = np.clip(np.exp(attack[idx_a] + defence[idx_h]), 1e-6, 15.0)
    tau = np.clip(_dc_tau(goals_h, goals_a, lam, mu, rho), 1e-10, None)
    log_lik = weights * (np.log(tau) + poisson.logpmf(goals_h, lam) + poisson.logpmf(goals_a, mu))
    return -np.sum(log_lik)


def fit_dixon_coles(rows, codes, reference_gw, decay_rate=DECAY_RATE):
    """Returns ({code: {'attack', 'defence'}}, home_adv, rho)."""
    n = len(codes)
    if n < 2 or not rows:
        logger.warning("fit_dixon_coles: not enough data to fit (n=%s teams, %s fixtures) - "
                        "falling back to league-average ratings for everyone.", n, len(rows))
        return {c: {'attack': 0.0, 'defence': 0.0} for c in codes}, HOME_ADV_INIT, 0.0

    code_index = {c: i for i, c in enumerate(codes)}
    idx_h = np.array([code_index[r['code_h']] for r in rows])
    idx_a = np.array([code_index[r['code_a']] for r in rows])
    goals_h = np.array([r['goals_h'] for r in rows], dtype=float)
    goals_a = np.array([r['goals_a'] for r in rows], dtype=float)
    gw = np.array([r['unified_gw'] for r in rows], dtype=float)
    weights = np.exp(-decay_rate * np.clip(reference_gw - gw, 0, None))

    theta0 = np.zeros(2 * n + 1)
    theta0[2 * n - 1] = HOME_ADV_INIT
    bounds = [(-3.0, 3.0)] * (n - 1) + [(-3.0, 3.0)] * n + [(-1.0, 1.0), (-0.3, 0.3)]

    result = minimize(
        _dixon_coles_nll, theta0,
        args=(n, idx_h, idx_a, goals_h, goals_a, weights),
        method='L-BFGS-B', bounds=bounds,
    )
    if not result.success:
        logger.warning("fit_dixon_coles: optimizer did not converge cleanly (%s) - using best iterate anyway.",
                        result.message)

    attack, defence, home_adv, rho = _unpack_theta(result.x, n)
    ratings = {codes[i]: {'attack': float(attack[i]), 'defence': float(defence[i])} for i in range(n)}
    return ratings, float(home_adv), float(rho)


#################################################
#   Per-team goal distribution from a rate      #
#################################################

def _interpolated_quantile(dist, p, *params):
    """
    Continuous approximation of a quantile for a discrete (integer-goals)
    distribution, via linear interpolation across the CDF step that contains
    p. A plain integer ppf() jumps straight from e.g. 0 to 1 goals with
    nothing in between, discarding information the underlying distribution
    actually has about where within that step p falls; interpolating spreads
    that step's probability mass evenly across the interval so a value like
    0.6 can be reported instead of always flooring to 0 or ceiling-ing to 1.
    """
    k = int(dist.ppf(p, *params))
    cdf_k = dist.cdf(k, *params)
    cdf_km1 = dist.cdf(k - 1, *params) if k > 0 else 0.0
    pmf_k = cdf_k - cdf_km1
    if pmf_k <= 0:
        return float(k)
    frac = (p - cdf_km1) / pmf_k
    return max(0.0, k - 1 + frac)


def expected_goals_range(lam, games_played_this_season, confidence=CONFIDENCE, is_preseason=False):
    """
    mean/low/high for one team's expected goals in a fixture. A team with
    fewer than STABLE_GAMES_THIS_SEASON games under its belt this season
    (newly promoted, or the season hasn't started) gets extra variance on
    top of the Poisson rate, via a negative-binomial with inflated variance,
    so the range widens instead of quietly reusing a Poisson width the data
    doesn't actually support. `is_preseason` softens that widening for
    gameweek 0 specifically, where it would otherwise hit every team at once.
    """
    lam = max(float(lam), 0.05)
    shortfall = max(0, STABLE_GAMES_THIS_SEASON - games_played_this_season)
    cap = PRESEASON_DISPERSION_CAP if is_preseason else MAX_DISPERSION
    dispersion = min(1.0 + shortfall * 0.3, cap)

    alpha = (1 - confidence) / 2
    if dispersion <= 1.0 + 1e-9:
        low = _interpolated_quantile(poisson, alpha, lam)
        high = _interpolated_quantile(poisson, 1 - alpha, lam)
    else:
        variance = lam * dispersion
        p = lam / variance  # = 1 / dispersion
        r = lam * p / (1 - p)
        low = _interpolated_quantile(nbinom, alpha, r, p)
        high = _interpolated_quantile(nbinom, 1 - alpha, r, p)

    return {'mean': round(lam, 2), 'low': float(max(0.0, low)), 'high': float(high)}


#################################################
#        Fitting + building predictions         #
#################################################

def fit_current_ratings(cursor, current_season=season_start, current_gw=None):
    if current_gw is None:
        current_gw = generateCurrentGameweek()
    rows, codes, games_this_season, reference_gw = build_rating_dataset(cursor, current_season, current_gw)
    ratings, home_adv, rho = fit_dixon_coles(rows, codes, reference_gw)
    return ratings, home_adv, rho, games_this_season, current_gw


def _distribution_columns(dist):
    return {
        'expected_goals_mean': dist['mean'],
        'expected_goals_low': dist['low'],
        'expected_goals_high': dist['high'],
    }


def build_fixture_predictions(cursor, current_season, current_gw, ratings, home_adv, games_this_season):
    """One row per team per upcoming fixture (two rows per fixture) for the next NEXT_N_GAMEWEEKS gameweeks."""
    teams = fetch_teams_for_season(cursor, current_season)
    from_gw, to_gw = current_gw + 1, current_gw + NEXT_N_GAMEWEEKS
    fixtures = fetch_upcoming_fixtures(cursor, current_season, from_gw, to_gw)
    computed_at = datetime.utcnow()
    is_preseason = current_gw == 0

    rows = []
    for fx in fixtures:
        team_h_info = teams.get(fx['team_h'])
        team_a_info = teams.get(fx['team_a'])
        if not team_h_info or not team_a_info:
            continue

        code_h, code_a = team_h_info['code'], team_a_info['code']
        rating_h = ratings.get(code_h, {'attack': 0.0, 'defence': 0.0})
        rating_a = ratings.get(code_a, {'attack': 0.0, 'defence': 0.0})

        lam_home = float(np.exp(rating_h['attack'] + rating_a['defence'] + home_adv))
        lam_away = float(np.exp(rating_a['attack'] + rating_h['defence']))

        games_h = games_this_season.get(code_h, 0)
        games_a = games_this_season.get(code_a, 0)

        home_dist = expected_goals_range(lam_home, games_h, is_preseason=is_preseason)
        away_dist = expected_goals_range(lam_away, games_a, is_preseason=is_preseason)

        rows.append({
            'fixture_code': fx['code'], 'gameweek': fx['event'],
            'kickoff_time': fx['kickoff_time'],
            'team_id': fx['team_h'], 'opponent_id': fx['team_a'], 'is_home': 1,
            **_distribution_columns(home_dist), 'computed_at': computed_at,
            'attack_rating': float(rating_h['attack']),
            'defence_rating': float(rating_h['defence']),
            'home_adv': float(home_adv)
        })
        rows.append({
            'fixture_code': fx['code'], 'gameweek': fx['event'],
            'kickoff_time': fx['kickoff_time'],
            'team_id': fx['team_a'], 'opponent_id': fx['team_h'], 'is_home': 0,
            **_distribution_columns(away_dist), 'computed_at': computed_at,
            'attack_rating': float(rating_a['attack']),
            'defence_rating': float(rating_a['defence']),
            'home_adv': 0.0
        })
    return rows


#################################################
#              Persistence (daily job)          #
#################################################

def persist_match_predictions(conn, rows):
    if not rows:
        logger.warning("persist_match_predictions called with no rows to write.")
        return

    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {PREDICTIONS_TABLE} (
            fixture_code INT NOT NULL,
            team_id INT NOT NULL,
            gameweek INT NOT NULL,
            opponent_id INT NOT NULL,
            is_home TINYINT NOT NULL,
            expected_goals_mean FLOAT,
            expected_goals_low FLOAT,
            expected_goals_high FLOAT,
            attack_rating FLOAT,
            defence_rating FLOAT,
            home_adv FLOAT,
            computed_at DATETIME,
            PRIMARY KEY (fixture_code, team_id)
        )
    """)

    records = [
        (r['fixture_code'], r['team_id'], r['gameweek'], r['opponent_id'], r['is_home'],
         r['expected_goals_mean'], r['expected_goals_low'], r['expected_goals_high'],
         r['attack_rating'], r['defence_rating'], r['home_adv'], r['computed_at'])
        for r in rows
    ]
    cursor.execute(f"DELETE FROM {PREDICTIONS_TABLE} WHERE gameweek < %s", (min(r['gameweek'] for r in rows),))
    cursor.executemany(f"""
        INSERT INTO {PREDICTIONS_TABLE}
            (fixture_code, team_id, gameweek, opponent_id, is_home,
             expected_goals_mean, expected_goals_low, expected_goals_high,
             attack_rating, defence_rating, home_adv, computed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            gameweek = VALUES(gameweek),
            opponent_id = VALUES(opponent_id),
            is_home = VALUES(is_home),
            expected_goals_mean = VALUES(expected_goals_mean),
            expected_goals_low = VALUES(expected_goals_low),
            expected_goals_high = VALUES(expected_goals_high),
            attack_rating = VALUES(attack_rating),
            defence_rating = VALUES(defence_rating),
            home_adv = VALUES(home_adv),
            computed_at = VALUES(computed_at)
    """, records)
    conn.commit()
    logger.info(f"Persisted {len(records)} team-fixture predictions.")


def _kickoff(row):
    try:
        return datetime.strptime(row.get('kickoff_time') or '', KICKOFF_FORMAT)
    except (ValueError, TypeError):
        return None


def loggable_rows(rows, now):
    """Only predictions made strictly before kickoff count toward the honest record."""
    return [r for r in rows if _kickoff(r) is not None and _kickoff(r) > now]


def log_predictions(conn, rows, now):
    """Append today's pre-kickoff predictions. Re-running the same day changes nothing."""
    to_log = loggable_rows(rows, now)
    if not to_log:
        return
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {LOG_TABLE} (
            fixture_code INT NOT NULL,
            team_id INT NOT NULL,
            opponent_id INT NOT NULL,
            gameweek INT NOT NULL,
            is_home TINYINT NOT NULL,
            kickoff_time VARCHAR(20) NOT NULL,
            expected_goals_mean FLOAT,
            expected_goals_low FLOAT,
            expected_goals_high FLOAT,
            model_version VARCHAR(40) NOT NULL,
            logged_at DATETIME NOT NULL,
            log_date DATE NOT NULL,
            PRIMARY KEY (fixture_code, team_id, model_version, log_date)
        )
    """)
    cursor.executemany(f"""
        INSERT IGNORE INTO {LOG_TABLE}
            (fixture_code, team_id, opponent_id, gameweek, is_home, kickoff_time,
             expected_goals_mean, expected_goals_low, expected_goals_high,
             model_version, logged_at, log_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [(r['fixture_code'], r['team_id'], r['opponent_id'], r['gameweek'], r['is_home'],
           r['kickoff_time'], r['expected_goals_mean'], r['expected_goals_low'],
           r['expected_goals_high'], MODEL_VERSION, now, now.date()) for r in to_log])
    conn.commit()
    logger.info(f"Logged {len(to_log)} pre-kickoff predictions ({MODEL_VERSION}).")


def _safe_rollback(conn):
    """Undo any half-finished write so the next step cannot commit it by accident."""
    try:
        conn.rollback()
    except Exception:
        logger.exception("Rollback failed.")


def run_daily_match_predictions():
    """
    Daily job entry point (called from run_update.py, alongside
    run_daily_predictions()). Fits the Dixon-Coles ratings and computes
    fixture distributions once, then persists them so the live Team page
    route never re-fits inside a web request.
    """
    logger.info("Starting daily match-outcome prediction run.")
    conn = connect_db()
    if conn is None:
        logger.error("run_daily_match_predictions: could not connect to the database.")
        return
    try:
        cursor = conn.cursor(dictionary=True)
        ratings, home_adv, rho, games_this_season, current_gw = fit_current_ratings(cursor)
        rows = build_fixture_predictions(cursor, season_start, current_gw, ratings, home_adv, games_this_season)
        persist_match_predictions(conn, rows)
        # Keep an honest, append-only record of what we predicted before kickoff.
        try:
            log_predictions(conn, rows, datetime.utcnow())
        except Exception:
            logger.exception("Prediction logging failed; predictions were still saved.")
            _safe_rollback(conn)
        # Team strength has its own guard: a failure here must never undo the predictions.
        try:
            teams = fetch_teams_for_season(cursor, season_start)
            strengths = build_team_strengths(teams, ratings, home_adv, fetch_squad_rows(cursor, season_start))
            persist_team_strengths(conn, strengths)
        except Exception:
            logger.exception("Team strength failed; predictions were still saved.")
            _safe_rollback(conn)
        # Player momentum has its own guard too: it can never break predictions or strength.
        try:
            from FPL_site.playerMomentum import run_daily_momentum
            run_daily_momentum(cursor, conn, current_gw)
        except Exception:
            logger.exception("Player momentum failed; predictions were still saved.")
            _safe_rollback(conn)
        logger.info(
            f"Daily match-outcome prediction run complete for gameweek {current_gw}. "
            f"home_adv={home_adv:.3f}, rho={rho:.3f}, {len(rows)} rows written."
        )
    finally:
        conn.close()


#################################################
#        Live-route read (Ticket 02 needs)      #
#################################################

def load_team_fixture_outlook(team_id, num_gameweeks=NEXT_N_GAMEWEEKS):
    """
    Live-route entry point for the Team page. Reads back what
    run_daily_match_predictions() persisted - no fitting happens here.
    Returns None if the team id isn't recognised for the current season.
    """
    conn = connect_db()
    if conn is None:
        logger.error("load_team_fixture_outlook: could not connect to the database.")
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        team_id = int(team_id)
        teams = fetch_teams_for_season(cursor, season_start)
        team_info = teams.get(team_id)
        if not team_info:
            return None

        cursor.execute(f"""
            SELECT mine.gameweek, mine.is_home, mine.opponent_id,
                   mine.expected_goals_mean AS own_mean,
                   mine.expected_goals_low AS own_low,
                   mine.expected_goals_high AS own_high,
                   mine.attack_rating AS own_attack,
                   mine.defence_rating AS own_defence,
                   mine.home_adv AS own_home_adv,
                   theirs.expected_goals_mean AS opp_mean,
                   theirs.expected_goals_low AS opp_low,
                   theirs.expected_goals_high AS opp_high,
                   theirs.attack_rating AS opp_attack,
                   theirs.defence_rating AS opp_defence
            FROM {PREDICTIONS_TABLE} mine
            JOIN {PREDICTIONS_TABLE} theirs
              ON mine.fixture_code = theirs.fixture_code AND theirs.team_id = mine.opponent_id
            WHERE mine.team_id = %s
            ORDER BY mine.gameweek ASC
            LIMIT %s
        """, (team_id, num_gameweeks))
        rows = cursor.fetchall()

        fixtures = []
        for row in rows:
            opponent = teams.get(row['opponent_id'], {})
            fixtures.append({
                'gameweek': row['gameweek'],
                'is_home': bool(row['is_home']),
                'opponent_name': opponent.get('name', 'Unknown'),
                'opponent_short_name': opponent.get('short_name', '???'),
                'own': {
                    'mean': row['own_mean'], 'low': row['own_low'], 'high': row['own_high'],
                    'attack': row['own_attack'], 'defence': row['own_defence'], 'home_adv': row['own_home_adv']
                },
                'opponent': {
                    'mean': row['opp_mean'], 'low': row['opp_low'], 'high': row['opp_high'],
                    'attack': row['opp_attack'], 'defence': row['opp_defence']
                },
            })

        return {
            'team_id': team_id,
            'team_name': team_info['name'],
            'team_short_name': team_info['short_name'],
            'fixtures': fixtures,
        }
    finally:
        conn.close()


#################################################
#        Club picker (nav entry point)          #
#################################################

def list_current_teams():
    """All teams for the current season, name-sorted - powers the club picker list."""
    conn = connect_db()
    if conn is None:
        logger.error("list_current_teams: could not connect to the database.")
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        teams = fetch_teams_for_season(cursor, season_start)
        return sorted(
            [{'id': t['id'], 'name': t['name'], 'short_name': t['short_name']} for t in teams.values()],
            key=lambda t: t['name']
        )
    finally:
        conn.close()


#################################################
#     Backtest (validation, not wired in)       #
#################################################

def backtest_model(target_season, holdout_gw=25, gw_window=13):
    """
    Fits ratings using only fixtures before `holdout_gw` of `target_season`
    (plus the usual pooled prior seasons), predicts the held-out gameweeks,
    and compares mean absolute error against a naive league-average
    baseline. A standalone validation helper for Ticket 01's DoD - not part
    of the daily job or any live route.
    """
    conn = connect_db()
    if conn is None:
        raise RuntimeError("backtest_model: could not connect to the database.")
    try:
        cursor = conn.cursor(dictionary=True)
        rows, codes, games_this_season, reference_gw = build_rating_dataset(
            cursor, target_season, holdout_gw - 1, current_season_max_event=holdout_gw
        )
        ratings, home_adv, rho = fit_dixon_coles(rows, codes, reference_gw)

        baseline_mean = float(np.mean([r['goals_h'] for r in rows] + [r['goals_a'] for r in rows]))

        teams = fetch_teams_for_season(cursor, target_season)
        id_to_code = {tid: t['code'] for tid, t in teams.items()}

        cursor.execute(f"""
            SELECT event, team_h, team_a, team_h_score, team_a_score
            FROM {db}.fixtures_fixtures
            WHERE year_start = %s AND finished = 1 AND event >= %s AND event < %s
              AND team_h_score IS NOT NULL AND team_a_score IS NOT NULL
        """, (target_season, holdout_gw, holdout_gw + gw_window))
        held_out = cursor.fetchall()

        model_errors, baseline_errors = [], []
        for fx in held_out:
            code_h, code_a = id_to_code.get(fx['team_h']), id_to_code.get(fx['team_a'])
            rating_h = ratings.get(code_h, {'attack': 0.0, 'defence': 0.0})
            rating_a = ratings.get(code_a, {'attack': 0.0, 'defence': 0.0})
            lam_home = float(np.exp(rating_h['attack'] + rating_a['defence'] + home_adv))
            lam_away = float(np.exp(rating_a['attack'] + rating_h['defence']))

            model_errors.append(abs(lam_home - fx['team_h_score']))
            model_errors.append(abs(lam_away - fx['team_a_score']))
            baseline_errors.append(abs(baseline_mean - fx['team_h_score']))
            baseline_errors.append(abs(baseline_mean - fx['team_a_score']))

        return {
            'target_season': target_season,
            'holdout_gw': holdout_gw,
            'n_fixtures': len(held_out),
            'model_mae': float(np.mean(model_errors)) if model_errors else None,
            'baseline_mae': float(np.mean(baseline_errors)) if baseline_errors else None,
            'baseline_mean_goals': baseline_mean,
            'home_adv': home_adv,
            'rho': rho,
        }
    finally:
        conn.close()
