"""Each team's expected goals for and against in a gameweek, as our match engine would have seen
it before that gameweek: the engine is refitted with only earlier fixtures. Used as features for
past gameweeks (training and the backtest). Stored once per gameweek in fixture_xg_history, since
each refit takes seconds.
"""
import logging
import math

from FPL_site.dataModels import db
from FPL_site.matchPredictionEngine import (build_rating_dataset, fit_dixon_coles, fetch_team_code_map,
                                            kickoff_in_season_window)
from FPL_site.teamStrength import rating_for

logger = logging.getLogger(__name__)

TABLE = 'fixture_xg_history'


def team_gameweek_xg(fixtures, ratings, home_adv, id_to_code):
    out = {}
    for f in fixtures:
        home, away = id_to_code.get(f['team_h']), id_to_code.get(f['team_a'])
        if home is None or away is None:
            continue
        rh, ra = rating_for(ratings, home), rating_for(ratings, away)
        lam_home = round(math.exp(rh['attack'] + ra['defence'] + home_adv), 3)
        lam_away = round(math.exp(ra['attack'] + rh['defence']), 3)
        for code, own, opp, is_home in ((home, lam_home, lam_away, 1.0), (away, lam_away, lam_home, 0.0)):
            t = out.setdefault(code, {'team_xg': 0.0, 'opp_xg': 0.0, 'matches': 0, 'homes': 0.0})
            t['team_xg'] += own
            t['opp_xg'] += opp
            t['matches'] += 1
            t['homes'] += is_home
    return {code: {'team_xg': round(t['team_xg'], 3), 'opp_xg': round(t['opp_xg'], 3),
                   'matches': t['matches'], 'home_share': t['homes'] / t['matches']}
            for code, t in out.items()}


def fetch_gameweek_fixtures(cursor, year_start, gameweek):
    """One gameweek's matches. The table can hold another season's matches under this
    year_start, so only kickoffs inside the season's window count."""
    cursor.execute(f"""SELECT DISTINCT id, team_h, team_a, kickoff_time FROM {db}.fixtures_fixtures
                       WHERE year_start = %s AND event = %s""", (year_start, gameweek))
    return [r for r in cursor.fetchall() if kickoff_in_season_window(r['kickoff_time'], year_start)]


def fit_as_of(cursor, year_start, gameweek):
    """Fit the engine on fixtures before `gameweek` (prior seasons whole), predict `gameweek`."""
    rows, codes, _, reference_gw = build_rating_dataset(
        cursor, year_start, gameweek - 1, current_season_max_event=gameweek)
    ratings, home_adv, _ = fit_dixon_coles(rows, codes, reference_gw)
    return team_gameweek_xg(fetch_gameweek_fixtures(cursor, year_start, gameweek),
                            ratings, home_adv, fetch_team_code_map(cursor, year_start))


def _ensure_table(cursor):
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            year_start INT NOT NULL,
            gameweek INT NOT NULL,
            team_code INT NOT NULL,
            team_xg FLOAT NOT NULL,
            opp_xg FLOAT NOT NULL,
            matches INT NOT NULL,
            home_share FLOAT NOT NULL,
            PRIMARY KEY (year_start, gameweek, team_code)
        )
    """)


def load_fixture_xg(cursor):
    _ensure_table(cursor)
    cursor.execute(f"SELECT year_start, gameweek, team_code, team_xg, opp_xg, matches, home_share FROM {TABLE}")
    return {(r['year_start'], r['gameweek'], r['team_code']):
            {'team_xg': float(r['team_xg']), 'opp_xg': float(r['opp_xg']),
             'matches': int(r['matches']), 'home_share': float(r['home_share'])}
            for r in cursor.fetchall()}


def fill_missing(conn, cursor, wanted):
    _ensure_table(cursor)
    cursor.execute(f"SELECT DISTINCT year_start, gameweek FROM {TABLE}")
    stored = {(r['year_start'], r['gameweek']) for r in cursor.fetchall()}
    added = 0
    for year, gw in wanted:
        if (year, gw) in stored:
            continue
        teams = fit_as_of(cursor, year, gw)
        cursor.executemany(f"""
            INSERT IGNORE INTO {TABLE} (year_start, gameweek, team_code, team_xg, opp_xg, matches, home_share)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, [(year, gw, code, t['team_xg'], t['opp_xg'], t['matches'], t['home_share'])
              for code, t in teams.items()])
        conn.commit()
        added += 1
        logger.info("fixture_xg_history: stored %s gameweek %s (%d teams).", year, gw, len(teams))
    return added
