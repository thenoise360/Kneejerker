"""
Historical context for a player: how last season went (a baseline for early-season form) and
how the player did the last time they faced an upcoming opponent.

Player ids and team ids are re-issued every season, so everything here crosses seasons through
the stable `code` (player code, team code), never through `id`.

The pure functions take plain rows; the fetchers take a database cursor, so tests can pass a
fake one. Nothing here writes to the database.
"""
import logging

logger = logging.getLogger(__name__)

# A player counts as having "appeared" in a match when they were on the pitch for at least a minute.
# Points per appearance at or above these lines pick the wording.
REGULAR_FROM = 5.0
STEADY_FROM = 3.0

# Points scored in one match at or above these lines pick the "last time" wording.
BIG_RETURN_FROM = 8
STEADY_RETURN_FROM = 3

NEW_TO_LEAGUE = 'New to the league last season'
DID_NOT_PLAY = "Didn't play last season"


def last_season_tier(points_per_appearance):
    """A plain-language word for a season's points per appearance."""
    if points_per_appearance >= REGULAR_FROM:
        return 'a regular points-scorer'
    if points_per_appearance >= STEADY_FROM:
        return 'a steady contributor'
    return 'a quiet season'


def _distinct_matches(rows):
    """The history table can hold the same match more than once; keep one per match."""
    seen, unique = set(), []
    for row in rows or []:
        key = (row.get('round'), row.get('opponent_team'), row.get('was_home'))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def count_appearances(rows):
    return sum(1 for r in _distinct_matches(rows) if (r.get('minutes') or 0) > 0)


def last_season_baseline(rows, club_name):
    """
    Appearances and points per appearance from one season's match rows, or None when the
    player never got on the pitch. The tier is read from the rounded figure, so the word
    always agrees with the number a reader can open and see.
    """
    played = [r for r in _distinct_matches(rows) if (r.get('minutes') or 0) > 0]
    if not played:
        return None
    total = sum(r.get('total_points') or 0 for r in played)
    per_game = round(total / len(played), 1)
    return {
        'appearances': len(played),
        'points_per_appearance': per_game,
        'tier': last_season_tier(per_game),
        'club': club_name,
    }


def _season_rows(cursor, element_id, year_start):
    cursor.execute(
        "SELECT round, opponent_team, was_home, total_points, minutes, "
        "team_h_score, team_a_score FROM {db}.elementsummary_history "
        "WHERE element = %s AND year_start = %s".format(db=_db()),
        (element_id, year_start))
    return cursor.fetchall()


def _db():
    from FPL_site.dataModels import db
    return db


def _team_name(cursor, team_code, year_start):
    cursor.execute(
        "SELECT name FROM {db}.bootstrapstatic_teams WHERE code = %s AND year_start = %s "
        "LIMIT 1".format(db=_db()), (team_code, year_start))
    row = cursor.fetchone()
    return row['name'] if row else None


def _this_season_player(cursor, player_id, year_start):
    cursor.execute(
        "SELECT code, team_code FROM {db}.bootstrapstatic_elements WHERE id = %s "
        "AND year_start = %s ORDER BY gameweek DESC LIMIT 1".format(db=_db()),
        (player_id, year_start))
    return cursor.fetchone()


def _last_season_player(cursor, code, year_start):
    cursor.execute(
        "SELECT id, team_code FROM {db}.bootstrapstatic_elements WHERE code = %s "
        "AND year_start = %s ORDER BY gameweek DESC LIMIT 1".format(db=_db()),
        (code, year_start))
    return cursor.fetchone()


def fetch_last_season_baseline(cursor, player_id, this_year=None):
    """
    Payload for /api/player/<id>/last-season, or None for a player we don't know.
    `this_season_appearances` lets the page hide the line once this season has a real sample.
    """
    if this_year is None:
        from FPL_site.dataModels import current_season_start
        this_year = current_season_start()
    last_year = this_year - 1

    mine = _this_season_player(cursor, player_id, this_year)
    if not mine:
        return None

    this_season_appearances = count_appearances(_season_rows(cursor, player_id, this_year))
    out = {'this_season_appearances': this_season_appearances}

    before = _last_season_player(cursor, mine['code'], last_year)
    if not before:
        out.update({'played': False, 'headline': NEW_TO_LEAGUE})
        return out

    club = _team_name(cursor, before.get('team_code'), last_year)
    baseline = last_season_baseline(_season_rows(cursor, before['id'], last_year), club)
    if baseline is None:
        out.update({'played': False, 'headline': DID_NOT_PLAY})
        return out

    headline = 'Last season: ' + baseline['tier']
    if club:
        headline += ' (' + club + ')'
    out.update(baseline)
    out.update({
        'played': True,
        'headline': headline,
        'detail': 'about {} points a game across {} games'.format(
            baseline['points_per_appearance'], baseline['appearances']),
    })
    return out


def load_last_season(player_id):
    """The per-request entry point used by the route. Opens and closes its own connection."""
    from FPL_site.dataModels import connect_db
    connection = connect_db()
    if connection is None:
        raise RuntimeError('database unavailable')
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            return fetch_last_season_baseline(cursor, player_id)
        finally:
            cursor.close()
    finally:
        connection.close()
