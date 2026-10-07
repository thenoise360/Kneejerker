"""Pure player momentum: is a player rising, steady or cooling this week?

Built only from the team's upcoming fixtures and what is changing around the
player (teammates back or out). Never from the player's own minutes, the
Influence, Creativity and Threat index, or form. No database access here.
"""

from FPL_site.momentumCopy import momentum_reason

FIXTURE_WINDOW = 3                 # gameweeks ahead
FIXTURE_CHANGE_FROM = 0.20         # 20% easier or harder than an average opponent
KEY_TEAMMATE_SHARE = 0.15          # share of team expected goals + assists
OUT_BELOW_CHANCE = 50              # chance of playing below this = out
ATTACKING = (3, 4)                 # midfielder, forward

SIGNAL_ORDER = ('fixtures', 'teammates', 'position', 'manager')


def _round(value):
    # Rounding stops float noise tipping a boundary the wrong way.
    return round(value, 9)


def _signal(key, direction, reason, magnitude):
    return {'key': key, 'direction': direction, 'reason': reason, 'magnitude': magnitude}


def not_tracked(key):
    return {'key': key, 'direction': 'not_tracked', 'reason': None, 'magnitude': 0}


def fixtures_signal(position, upcoming, baseline_for, baseline_against):
    if not upcoming:
        return _signal('fixtures', 'same', 'no game this week', 0)
    if position in ATTACKING:
        baseline = baseline_for
        average = sum(f['own_mean'] for f in upcoming) / len(upcoming)
        change = (average - baseline) / baseline if baseline else 0.0
    else:
        # Defenders and goalkeepers want opponents who score less than usual.
        baseline = baseline_against
        average = sum(f['opp_mean'] for f in upcoming) / len(upcoming)
        change = (baseline - average) / baseline if baseline else 0.0
    change = _round(change)
    magnitude = abs(change)
    if change >= FIXTURE_CHANGE_FROM:
        return _signal('fixtures', 'up', 'kinder fixtures coming up', magnitude)
    if change <= -FIXTURE_CHANGE_FROM:
        return _signal('fixtures', 'down', 'tougher fixtures coming up', magnitude)
    return _signal('fixtures', 'same', 'fixtures look about average', magnitude)


def _is_key(teammate):
    share = _round(teammate.get('share') or 0)
    return share >= KEY_TEAMMATE_SHARE and teammate.get('status') != 'u'


def _is_back(teammate):
    chance = teammate.get('chance')
    return not teammate.get('played_last') and (chance is None or chance >= OUT_BELOW_CHANCE)


def _is_out(teammate):
    chance = teammate.get('chance')
    return bool(teammate.get('played_last')) and chance is not None and chance < OUT_BELOW_CHANCE


def teammates_signal(player_id, teammates):
    key = [t for t in teammates if t.get('id') != player_id and _is_key(t)]
    back = [t for t in key if _is_back(t)]
    out = [t for t in key if _is_out(t)]
    magnitude = _round(sum(t['share'] for t in back + out))
    if len(back) > len(out):
        reason = '%s is back in the team' % back[0]['name'] if len(back) == 1 else 'key teammates are back'
        return _signal('teammates', 'up', reason, magnitude)
    if len(out) > len(back):
        reason = '%s is out' % out[0]['name'] if len(out) == 1 else 'key teammates are out'
        return _signal('teammates', 'down', reason, magnitude)
    return _signal('teammates', 'same', 'no change around them', magnitude)


def _label(total):
    if total >= 1:
        return 'Rising'
    if total <= -1:
        return 'Cooling'
    return 'Steady'


def player_momentum(fixtures, teammates):
    """fixtures and teammates are already-built signals. Returns label, reason, signals, score."""
    signals = [fixtures, teammates, not_tracked('position'), not_tracked('manager')]
    step = {'up': 1, 'down': -1}
    total = sum(step.get(s['direction'], 0) for s in signals)
    label = _label(total)
    signed = sum(step.get(s['direction'], 0) * s['magnitude'] for s in signals)
    wanted = 'up' if label == 'Rising' else 'down'
    strongest = None
    if label != 'Steady':
        # max() keeps the first of equals, so ties go to the earlier signal.
        strongest = max((s for s in signals if s['direction'] == wanted),
                        key=lambda s: s['magnitude'])
    return {'label': label,
            'reason': momentum_reason(label, strongest),
            'signals': signals,
            'score': total + 0.1 * signed}


# ---------------------------------------------------------------------------
# Daily job and live-route read. The pure functions above do the thinking;
# everything below only moves rows in and out of the database.
# ---------------------------------------------------------------------------
import json
import logging
from datetime import datetime

from mysql.connector import errorcode
from mysql.connector.errors import ProgrammingError

from FPL_site.dataModels import connect_db, current_season_start
from FPL_site.momentumCopy import DIRECTION_WORDS, SIGNAL_NAMES

logger = logging.getLogger(__name__)

MOMENTUM_TABLE = 'player_momentum'
LEFT_CLUB = 'u'
ARROWS = {'up': '\u2191', 'same': '\u2192', 'down': '\u2193', 'not_tracked': '\u2013'}

NOT_READY = {
    'status': 'not_ready',
    'message': {'title': 'Momentum is on its way',
                'body': "We're still working this out. Check back a little later."},
}


def fetch_player_rows(cursor, year_start):
    """Every player in the latest bootstrap snapshot for the season."""
    cursor.execute("""
        SELECT id, web_name, team, element_type, status, chance_of_playing_next_round,
               expected_goals, expected_assists
        FROM bootstrapstatic_elements
        WHERE year_start = %s
          AND gameweek = (SELECT MAX(gameweek) FROM bootstrapstatic_elements WHERE year_start = %s)
    """, (year_start, year_start))
    return cursor.fetchall()


def fetch_last_gameweek_minutes(cursor, year_start, gameweek):
    """{element: minutes} for one gameweek, summed over a double gameweek."""
    cursor.execute("""
        SELECT element, SUM(minutes) AS minutes
        FROM elementsummary_history
        WHERE year_start = %s AND round = %s
        GROUP BY element
    """, (year_start, gameweek))
    return {row['element']: float(row['minutes'] or 0) for row in cursor.fetchall()}


def fetch_upcoming_predictions(cursor, from_gw, to_gw):
    """One row per team per upcoming fixture, with the opponent's expected goals alongside."""
    cursor.execute("""
        SELECT mine.team_id, mine.gameweek,
               mine.expected_goals_mean AS own_mean,
               theirs.expected_goals_mean AS opp_mean
        FROM team_fixture_predictions mine
        JOIN team_fixture_predictions theirs
          ON mine.fixture_code = theirs.fixture_code AND theirs.team_id = mine.opponent_id
        WHERE mine.gameweek BETWEEN %s AND %s
        ORDER BY mine.gameweek ASC
    """, (from_gw, to_gw))
    return cursor.fetchall()


def fetch_team_baselines(cursor):
    """{team_id: {'scored', 'conceded'}}; empty when team_strength does not exist yet."""
    try:
        cursor.execute("SELECT team_id, scored, conceded FROM team_strength")
        rows = cursor.fetchall()
    except ProgrammingError as e:
        if e.errno != errorcode.ER_NO_SUCH_TABLE:
            raise
        return {}
    return {r['team_id']: {'scored': float(r['scored']), 'conceded': float(r['conceded'])}
            for r in rows}


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def build_all_momentum(players, last_minutes, upcoming, baselines):
    """{player_id: momentum} for every player still at a club. Pure."""
    squad = [p for p in players if p.get('status') != LEFT_CLUB]
    by_team = {}
    for p in squad:
        by_team.setdefault(p['team'], []).append(p)

    fixtures_by_team = {}
    for row in upcoming:
        fixtures_by_team.setdefault(row['team_id'], []).append(row)

    # Fallback baselines when a team has no stored strength: the league average.
    league_for = _mean(r['own_mean'] for r in upcoming)
    league_against = _mean(r['opp_mean'] for r in upcoming)

    results = {}
    for team_id, members in by_team.items():
        involvement = {p['id']: float(p['expected_goals'] or 0) + float(p['expected_assists'] or 0)
                       for p in members}
        total = sum(involvement.values())
        teammates = []
        # A team has "played" only if one of its own players has minutes. A team
        # that has not kicked off yet, or has a blank gameweek, has none.
        team_played = any(last_minutes.get(p['id'], 0) > 0 for p in members)
        for p in members:
            chance = p.get('chance_of_playing_next_round')
            if team_played:
                played = last_minutes.get(p['id'], 0) > 0
            else:
                # No minutes on record for this team: assume nothing changed rather than call everyone "back".
                played = chance is None or chance >= OUT_BELOW_CHANCE
            teammates.append({'id': p['id'], 'name': p['web_name'],
                              'share': involvement[p['id']] / total if total > 0 else 0.0,
                              'status': p.get('status'), 'chance': chance, 'played_last': played})
        strength = baselines.get(team_id)
        baseline_for = strength['scored'] if strength else league_for
        baseline_against = strength['conceded'] if strength else league_against
        upcoming_rows = fixtures_by_team.get(team_id, [])
        for p in members:
            fixtures = fixtures_signal(p['element_type'], upcoming_rows, baseline_for, baseline_against)
            results[p['id']] = player_momentum(fixtures, teammates_signal(p['id'], teammates))
    return results


def persist_momentum(conn, momentum, players):
    """Replace the whole table with today's momentum, in one commit."""
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {MOMENTUM_TABLE} (
            player_id INT PRIMARY KEY,
            name VARCHAR(60),
            team_id INT,
            position INT,
            label VARCHAR(10),
            reason VARCHAR(200),
            signals_json TEXT,
            score FLOAT,
            computed_at DATETIME
        )
    """)
    now = datetime.utcnow()
    by_id = {p['id']: p for p in players}
    records = [
        (pid, by_id[pid]['web_name'], by_id[pid]['team'], by_id[pid]['element_type'],
         m['label'], m['reason'], json.dumps(m['signals']), m['score'], now)
        for pid, m in momentum.items() if pid in by_id
    ]
    cursor.execute(f"DELETE FROM {MOMENTUM_TABLE}")
    if records:
        cursor.executemany(f"""
            INSERT INTO {MOMENTUM_TABLE}
                (player_id, name, team_id, position, label, reason, signals_json, score, computed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, records)
    conn.commit()


def run_daily_momentum(cursor, conn, current_gw):
    """Compute and store momentum. Called from the daily match prediction job."""
    players = fetch_player_rows(cursor, current_season_start())
    minutes = fetch_last_gameweek_minutes(cursor, current_season_start(), current_gw)
    upcoming = fetch_upcoming_predictions(cursor, current_gw + 1, current_gw + FIXTURE_WINDOW)
    baselines = fetch_team_baselines(cursor)
    momentum = build_all_momentum(players, minutes, upcoming, baselines)
    persist_momentum(conn, momentum, players)
    return momentum


def _public_signals(signals_json):
    return [{'key': s['key'], 'name': SIGNAL_NAMES[s['key']], 'direction': s['direction'],
             'word': DIRECTION_WORDS[s['direction']], 'arrow': ARROWS[s['direction']],
             'reason': s.get('reason')}
            for s in json.loads(signals_json or '[]')]


def load_player_momentum(player_id):
    """Live-route read: what the daily job stored. The hidden score is never returned."""
    conn = connect_db()
    if conn is None:
        logger.error('load_player_momentum: could not connect to the database.')
        return dict(NOT_READY)
    try:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(f"SELECT * FROM {MOMENTUM_TABLE} WHERE player_id = %s", (int(player_id),))
            row = cursor.fetchone()
        except ProgrammingError as e:
            if e.errno != errorcode.ER_NO_SUCH_TABLE:
                raise
            return dict(NOT_READY)
        if not row:
            # The table exists but this player is not in it (unknown or departed).
            return None
        return {'status': 'ready', 'label': row['label'], 'reason': row['reason'],
                'signals': _public_signals(row['signals_json'])}
    finally:
        conn.close()


# The stored element_type number as the short code the other Discover categories use.
POSITION_CODES = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}


def load_momentum_strip(limit=5):
    """Biggest risers and fallers, sorted on the server. Scores never leave this function."""
    # Imported here, not at the top, to avoid a circular import with the engine.
    from FPL_site.matchPredictionEngine import fetch_teams_for_season

    empty = {'heating_up': [], 'cooling_off': []}
    conn = connect_db()
    if conn is None:
        logger.error('load_momentum_strip: could not connect to the database.')
        return empty
    try:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(f"""
                SELECT player_id, name, team_id, position, label, reason, score FROM {MOMENTUM_TABLE}
                WHERE label IN ('Rising', 'Cooling')
            """)
            rows = cursor.fetchall()
            # Inside the same guard: a missing teams table also means "not ready".
            teams = fetch_teams_for_season(cursor, current_season_start()) or {}
        except ProgrammingError as e:
            if e.errno != errorcode.ER_NO_SUCH_TABLE:
                raise
            return empty

        def item(row):
            return {'id': row['player_id'], 'name': row['name'],
                    'team': teams.get(row['team_id'], {}).get('name', ''),
                    'position': POSITION_CODES.get(row['position'], ''), 'reason': row['reason']}

        rising = sorted((r for r in rows if r['label'] == 'Rising'),
                        key=lambda r: (-float(r['score']), r['player_id']))
        cooling = sorted((r for r in rows if r['label'] == 'Cooling'),
                         key=lambda r: (float(r['score']), r['player_id']))
        return {'heating_up': [item(r) for r in rising[:limit]],
                'cooling_off': [item(r) for r in cooling[:limit]]}
    finally:
        conn.close()
