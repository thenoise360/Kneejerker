"""The prediction record: how a team's finished games compared with what we said beforehand.

The record is only what the append-only fixture_prediction_log holds. The current model is
never re-run on finished games, so the record starts the day logging started.
"""
import logging
from datetime import date, datetime

from mysql.connector import errorcode
from mysql.connector.errors import ProgrammingError

from FPL_site.dataModels import connect_db, season_start
from FPL_site.recordCopy import game_verdict, record_summary

logger = logging.getLogger(__name__)

EARLY_DAYS_LABEL = 'Early days — this gets more reliable as the season goes on.'

NOT_READY = {
    'status': 'not_ready',
    'message': {'title': 'Our prediction record is on its way',
                'body': "We're still pulling this together. Check back a little later."},
}


def fetch_record_rows(cursor, team_id, year_start):
    """Finished games for a team: the last logged prediction for each, with the real score.

    Every logged row is pre-kickoff by construction. Returns [] if the log table does not
    exist yet (it appears after the first daily run).
    """
    try:
        cursor.execute("""
            SELECT mine.gameweek, mine.is_home, mine.opponent_id, mine.kickoff_time,
                   mine.expected_goals_mean AS predicted_for, theirs.expected_goals_mean AS predicted_against,
                   f.team_h_score, f.team_a_score
            FROM fixture_prediction_log mine
            JOIN fixture_prediction_log theirs
              ON theirs.fixture_code = mine.fixture_code AND theirs.team_id = mine.opponent_id
             AND theirs.log_date = mine.log_date AND theirs.model_version = mine.model_version
            JOIN fixtures_fixtures f ON f.code = mine.fixture_code AND f.year_start = %s
            WHERE mine.team_id = %s AND f.finished = 1
              AND mine.logged_at = (SELECT MAX(l.logged_at) FROM fixture_prediction_log l
                                    WHERE l.fixture_code = mine.fixture_code AND l.team_id = mine.team_id)
            ORDER BY mine.gameweek
        """, (year_start, team_id))
        return cursor.fetchall()
    except ProgrammingError as e:
        if e.errno != errorcode.ER_NO_SUCH_TABLE:
            raise
        return []


def fetch_logging_started(cursor):
    """The first day we logged a prediction, or None if we never have."""
    try:
        cursor.execute("SELECT MIN(log_date) AS started FROM fixture_prediction_log")
        row = cursor.fetchone()
    except ProgrammingError as e:
        if e.errno != errorcode.ER_NO_SUCH_TABLE:
            raise
        return None
    return row['started'] if row else None


def shape_games(rows, teams):
    """One entry per real game, with the verdict. Drops duplicate fixture rows."""
    games, seen = [], set()
    for r in rows:
        key = (r['gameweek'], r['kickoff_time'])
        opponent = teams.get(r['opponent_id'])
        if key in seen or opponent is None:
            continue
        seen.add(key)
        is_home = bool(r['is_home'])
        home, away = r['team_h_score'], r['team_a_score']
        actual_for, actual_against = (home, away) if is_home else (away, home)
        predicted_for, predicted_against = float(r['predicted_for']), float(r['predicted_against'])
        games.append({
            'gameweek': r['gameweek'],
            'opponent': opponent['name'],
            'is_home': is_home,
            # Shown on screen, so one decimal; the verdict below used the raw values.
            'predicted_for': round(predicted_for, 1),
            'predicted_against': round(predicted_against, 1),
            'actual_for': actual_for,
            'actual_against': actual_against,
            'verdict': game_verdict(predicted_for, predicted_against, actual_for, actual_against),
        })
    return games


def _iso(day):
    if day is None:
        return None
    if isinstance(day, datetime):
        return day.date().isoformat()
    if isinstance(day, date):
        return day.isoformat()
    return str(day)


def load_prediction_record(team_id):
    """Live-route read. None for an unknown team; never fits or re-runs the model."""
    # Imported here to match teamStrength and avoid a circular import with the engine.
    from FPL_site.matchPredictionEngine import fetch_teams_for_season

    conn = connect_db()
    if conn is None:
        logger.error('load_prediction_record: could not connect to the database.')
        return dict(NOT_READY)
    try:
        cursor = conn.cursor(dictionary=True)
        team_id = int(team_id)
        teams = fetch_teams_for_season(cursor, season_start)
        if team_id not in teams:
            return None
        team_name = teams[team_id]['name']
        games = shape_games(fetch_record_rows(cursor, team_id, season_start), teams)
        started_on = fetch_logging_started(cursor)
        summary = record_summary(team_name, games, started_on)
        return {
            'status': 'ready',
            'team_name': team_name,
            'headline': summary['headline'],
            'reason': summary['reason'],
            'early_days': summary['early_days'],
            'early_days_label': EARLY_DAYS_LABEL if summary['early_days'] else None,
            'started_on': _iso(started_on),
            'games': games,
        }
    finally:
        conn.close()
