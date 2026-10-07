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
from FPL_site.teamStrength import DEFAULT_RATING_KEY, rating_for, build_team_strengths, fetch_squad_rows, persist_team_strengths

logger = logging.getLogger(__name__)

PREDICTIONS_TABLE = 'team_fixture_predictions'
LOG_TABLE = 'fixture_prediction_log'
# Bump whenever the model changes, so the record can tell versions apart.
MODEL_VERSION = 'dixon-coles-2026-10'
KICKOFF_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

GAMEWEEKS_PER_SEASON = 38
TEAMS_PER_SEASON = 20
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
# Low-data shrinkage (Release P3, Task 7). Newly promoted sides have ~5 pooled games, which
# gave extreme maximum-likelihood ratings (Coventry attack -1.75, ~0.26 goals a game).
# An L2 penalty SHRINKAGE * sum((rating - prior)^2) pulls every team towards its prior:
# (0, 0) for teams with >= ESTABLISHED_GAMES pooled fixtures, PROMOTED_PRIOR otherwise.
# SHRINKAGE = 8 chosen by backtest_model-style holdouts (6, 15, 25; targets 2022, 2023, 2025):
# overall mean absolute error fell (0.996 -> 0.978 for 2022/23, 0.878 -> 0.869 for 2025) and
# error on fixtures involving promoted teams fell 1.010 -> 0.954; it is the smallest value
# that also keeps today's weakest attack at ~0.73 goals a game against an average side.
# Note: time decay leaves only ~46 effective games per team, so the penalty is not negligible
# for established sides either: top teams shrink by roughly 10-15% (Man City scores 1.80 -> 1.68).
# The established/promoted prior switch counts raw (undecayed) pooled games, while the penalty
# acts against decay-weighted information; the two are deliberately not the same measure.
SHRINKAGE = 8.0
ESTABLISHED_GAMES = 38
# PROMOTED_PRIOR = (attack, defence), derived from data: the mean unshrunk fitted rating of
# teams in their first pooled season (fit through that season's gameweek 38, centred on the
# established teams' average): Bournemouth, Fulham, Nott'm Forest (2022); Luton, Sheffield Utd
# (2023). Attack -0.137, defence +0.281 -> rounded. Only 5 team-seasons: treat as approximate.
# (2024/2025 team-seasons were excluded: the 2024 teams table is corrupt, see task report.)
PROMOTED_PRIOR = (-0.14, 0.28)

NEXT_N_GAMEWEEKS = 5

#################################################
#               Data fetching                  #
#################################################

def fetch_team_rows(cursor, year_start):
    cursor.execute(
        f"SELECT id, code, name, short_name FROM {db}.bootstrapstatic_teams WHERE year_start = %s",
        (year_start,)
    )
    return cursor.fetchall()


def fetch_teams_for_season(cursor, year_start):
    """id -> row for one season's team roster (id is only valid within that year_start)."""
    return {row['id']: row for row in fetch_team_rows(cursor, year_start)}


def fetch_team_code_map(cursor, year_start):
    """
    {team id: team code} for one season, read from the player snapshots.

    bootstrapstatic_teams is overwritten in place by every bootstrap run, so a season's
    rows can end up carrying a later season's id numbering (2024 did). Each player row in
    bootstrapstatic_elements records its own `team` id and `team_code` per gameweek, so a
    stray snapshot is outvoted: for each id we take the code seen in the most gameweeks,
    breaking ties by the latest gameweek. Empty dict when the season has no snapshots.
    """
    cursor.execute(
        f"""SELECT team, team_code,
                   COUNT(DISTINCT gameweek) AS gws, MAX(gameweek) AS last_gw
            FROM {db}.bootstrapstatic_elements
            WHERE year_start = %s AND team IS NOT NULL AND team_code IS NOT NULL
            GROUP BY team, team_code""",
        (year_start,)
    )
    best = {}
    for row in cursor.fetchall():
        rank = (row['gws'], row['last_gw'])
        if row['team'] not in best or rank > best[row['team']][0]:
            best[row['team']] = (rank, row['team_code'])
    return {tid: code for tid, (_, code) in best.items()}


def kickoff_in_season_window(kickoff, year_start):
    """
    True if `kickoff` ('YYYY-MM-DDTHH:MM:SSZ') is on or after 1 July of year_start and before
    1 July of the next year. The update job once wrote a new season's fixtures under the old
    year_start, so a season's table can hold other seasons' matches. Missing or unparseable
    kickoffs are treated as outside the window.
    """
    if not isinstance(kickoff, str):
        return False
    try:
        moment = datetime.strptime(kickoff, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        return False
    return datetime(int(year_start), 7, 1) <= moment < datetime(int(year_start) + 1, 7, 1)


def fetch_finished_fixtures(cursor, year_start):
    cursor.execute(
        f"""SELECT event, team_h, team_a, team_h_score, team_a_score, kickoff_time
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
        id_to_code = fetch_team_code_map(cursor, year_start)
        if not id_to_code:
            # No player snapshots for this season: fall back to the teams table.
            team_rows = fetch_team_rows(cursor, year_start)
            if not team_rows:
                continue
            id_to_code = {row['id']: row['code'] for row in team_rows}
            n_rows = len(team_rows)
        else:
            n_rows = len(id_to_code)
        if (n_rows != TEAMS_PER_SEASON or len(id_to_code) != TEAMS_PER_SEASON
                or len(set(id_to_code.values())) != TEAMS_PER_SEASON):
            # A season must map exactly 20 ids to 20 distinct codes. Anything else means id
            # collisions (seen in 2024, where a later bootstrap run overwrote the teams
            # table), so results would be credited to the wrong clubs. Skip the season
            # rather than poison the fit. Kept as a tripwire.
            logger.warning("build_rating_dataset: season %s has a corrupt team roster "
                           "(%s rows, %s distinct ids, %s distinct codes, expected %s) - skipping it.",
                           year_start, n_rows, len(id_to_code),
                           len(set(id_to_code.values())), TEAMS_PER_SEASON)
            continue
        season_offset = season_index * GAMEWEEKS_PER_SEASON

        out_of_window = 0
        for fx in fetch_finished_fixtures(cursor, year_start):
            if not kickoff_in_season_window(fx.get('kickoff_time'), year_start):
                out_of_window += 1
                continue
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

        if out_of_window:
            logger.warning("build_rating_dataset: season %s skipped %s finished fixtures with a missing "
                           "or out-of-window kickoff.", year_start, out_of_window)

    reference_gw = (len(seasons) - 1) * GAMEWEEKS_PER_SEASON + max(current_gw, 1)
    return rows, sorted(codes_seen), games_this_season, reference_gw


#################################################
#   Dixon-Coles fit: joint attack/defence +     #
#   low-scoring correlation, time-decayed       #
#################################################

def _unpack_theta(theta, n):
    """
    theta = [attack_0..attack_{n-1}, defence_0..defence_{n-1}, home_adv, rho, intercept].

    All attacks are free. The old "attack_0 fixed at 0" constraint is gone: the
    shrinkage penalty already removes the attack+c / defence-c invariance (it
    anchors the ratings to the priors). The league scoring level is an
    unpenalised `intercept` (global mean log-rate) so the penalty cannot drag
    it towards one goal a game.
    """
    attack = theta[0:n]
    defence = theta[n:2 * n]
    home_adv = theta[2 * n]
    rho = theta[2 * n + 1]
    intercept = theta[2 * n + 2]
    return attack, defence, home_adv, rho, intercept


def _dc_tau(x, y, lam, mu, rho):
    """Dixon-Coles low-score correction so 0-0/1-0/0-1/1-1 aren't systematically underpredicted."""
    tau = np.ones_like(lam)
    tau = np.where((x == 0) & (y == 0), 1 - lam * mu * rho, tau)
    tau = np.where((x == 0) & (y == 1), 1 + lam * rho, tau)
    tau = np.where((x == 1) & (y == 0), 1 + mu * rho, tau)
    tau = np.where((x == 1) & (y == 1), 1 - rho, tau)
    return tau


def _dixon_coles_nll(theta, n, idx_h, idx_a, goals_h, goals_a, weights,
                     shrinkage=0.0, prior_att=None, prior_def=None):
    attack, defence, home_adv, rho, intercept = _unpack_theta(theta, n)
    lam = np.clip(np.exp(intercept + attack[idx_h] + defence[idx_a] + home_adv), 1e-6, 15.0)
    mu = np.clip(np.exp(intercept + attack[idx_a] + defence[idx_h]), 1e-6, 15.0)
    tau = np.clip(_dc_tau(goals_h, goals_a, lam, mu, rho), 1e-10, None)
    log_lik = weights * (np.log(tau) + poisson.logpmf(goals_h, lam) + poisson.logpmf(goals_a, mu))
    nll = -np.sum(log_lik)
    if shrinkage:
        nll += shrinkage * (np.sum((attack - prior_att) ** 2) + np.sum((defence - prior_def) ** 2))
    return nll


def team_priors(rows, codes, established_games=ESTABLISHED_GAMES, promoted_prior=None):
    """
    (prior_att, prior_def) arrays: league average (0, 0) for teams with at least
    `ESTABLISHED_GAMES` pooled fixtures, `promoted_prior` for the rest.
    """
    if promoted_prior is None:
        promoted_prior = PROMOTED_PRIOR
    games = {c: 0 for c in codes}
    for r in rows:
        games[r['code_h']] += 1
        games[r['code_a']] += 1
    established = np.array([games[c] >= established_games for c in codes])
    prior_att = np.where(established, 0.0, promoted_prior[0])
    prior_def = np.where(established, 0.0, promoted_prior[1])
    return prior_att, prior_def


def fit_dixon_coles(rows, codes, reference_gw, decay_rate=DECAY_RATE,
                    shrinkage=None, promoted_prior=None, established_games=ESTABLISHED_GAMES):
    """
    Returns ({code: {'attack', 'defence'}}, home_adv, rho).

    An L2 penalty `shrinkage * sum((rating - prior)^2)` pulls low-data teams
    (newly promoted sides with a handful of pooled games) towards a typical
    promoted side instead of an extreme maximum-likelihood rating.
    """
    if shrinkage is None:
        shrinkage = SHRINKAGE
    n = len(codes)
    if n < 2 or not rows:
        logger.warning("fit_dixon_coles: not enough data to fit (n=%s teams, %s fixtures) - "
                        "falling back to league-average ratings for everyone.", n, len(rows))
        fallback = {c: {'attack': 0.0, 'defence': 0.0} for c in codes}
        fallback[DEFAULT_RATING_KEY] = {'attack': PROMOTED_PRIOR[0], 'defence': PROMOTED_PRIOR[1]}
        return fallback, HOME_ADV_INIT, 0.0

    code_index = {c: i for i, c in enumerate(codes)}
    idx_h = np.array([code_index[r['code_h']] for r in rows])
    idx_a = np.array([code_index[r['code_a']] for r in rows])
    goals_h = np.array([r['goals_h'] for r in rows], dtype=float)
    goals_a = np.array([r['goals_a'] for r in rows], dtype=float)
    gw = np.array([r['unified_gw'] for r in rows], dtype=float)
    weights = np.exp(-decay_rate * np.clip(reference_gw - gw, 0, None))

    prior_att, prior_def = team_priors(rows, codes, established_games, promoted_prior)

    theta0 = np.zeros(2 * n + 3)
    theta0[2 * n] = HOME_ADV_INIT
    bounds = [(-3.0, 3.0)] * (2 * n) + [(-1.0, 1.0), (-0.3, 0.3), (-2.0, 2.0)]

    result = minimize(
        _dixon_coles_nll, theta0,
        args=(n, idx_h, idx_a, goals_h, goals_a, weights, shrinkage, prior_att, prior_def),
        method='L-BFGS-B', bounds=bounds,
    )
    if not result.success:
        logger.warning("fit_dixon_coles: optimizer did not converge cleanly (%s) - using best iterate anyway.",
                        result.message)

    attack, defence, home_adv, rho, intercept = _unpack_theta(result.x, n)
    # Fold the league intercept into the ratings (half each) so that
    # exp(attack_h + defence_a + home_adv) is the home rate everywhere downstream.
    attack = attack + intercept / 2.0
    defence = defence + intercept / 2.0
    ratings = {codes[i]: {'attack': float(attack[i]), 'defence': float(defence[i])} for i in range(n)}
    # Reserved key: the rating for any team with no fixtures in the pool (a promoted side at
    # gameweek 0): a typical promoted side with the league level folded in like the others.
    # A reserved key (not a second return value) keeps every fit_dixon_coles caller and the
    # ratings dict handed to teamStrength unchanged; lookups go through rating_for().
    ratings[DEFAULT_RATING_KEY] = {'attack': float(PROMOTED_PRIOR[0] + intercept / 2.0),
                                   'defence': float(PROMOTED_PRIOR[1] + intercept / 2.0)}
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

    # Persisted ratings are centred on the current teams' league average (the fit's
    # level includes the league scoring rate), so "attack above 0.15" on the club page
    # means "better than an average side". Expected goals use the uncentred ratings.
    current = [rating_for(ratings, t['code']) for t in teams.values()]
    mean_attack = float(np.mean([r['attack'] for r in current])) if current else 0.0
    mean_defence = float(np.mean([r['defence'] for r in current])) if current else 0.0

    rows = []
    for fx in fixtures:
        team_h_info = teams.get(fx['team_h'])
        team_a_info = teams.get(fx['team_a'])
        if not team_h_info or not team_a_info:
            continue

        code_h, code_a = team_h_info['code'], team_a_info['code']
        rating_h = rating_for(ratings, code_h)
        rating_a = rating_for(ratings, code_a)

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
            'attack_rating': float(rating_h['attack'] - mean_attack),
            'defence_rating': float(rating_h['defence'] - mean_defence),
            'home_adv': float(home_adv)
        })
        rows.append({
            'fixture_code': fx['code'], 'gameweek': fx['event'],
            'kickoff_time': fx['kickoff_time'],
            'team_id': fx['team_a'], 'opponent_id': fx['team_h'], 'is_home': 0,
            **_distribution_columns(away_dist), 'computed_at': computed_at,
            'attack_rating': float(rating_a['attack'] - mean_attack),
            'defence_rating': float(rating_a['defence'] - mean_defence),
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
    # Relies on autocommit being OFF (the mysql.connector default, which connect_db does not
    # override): DELETE and INSERT stay in one transaction and readers see the old rows until
    # the single commit. With autocommit on, the table would be briefly empty.
    # Full replace (like persist_team_strengths): a season rollover must not leave
    # last season's rows behind. DELETE + INSERT share one transaction and one commit.
    cursor.execute(f"DELETE FROM {PREDICTIONS_TABLE}")
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
            rating_h = rating_for(ratings, code_h)
            rating_a = rating_for(ratings, code_a)
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
