"""Absence-adjusted team strength.

Takes the engine's attack and defence ratings and weakens them for the players who are
missing this week. Pure functions, apart from one read-only fetcher. Never uses the
Influence, Creativity and Threat index: a player's weight is their share of the team's
expected goals plus expected assists (attack) or of its goalkeeper-and-defender minutes (defence).

The engine is imported only inside load_team_strength, because the engine imports this module
at the top and a module-level import back would be circular.
"""
import json
import logging
import math
from datetime import datetime

from mysql.connector import errorcode
from mysql.connector.errors import ProgrammingError

from FPL_site.dataModels import connect_db, season_start
from FPL_site.strengthCopy import strength_summary, gauge_summary

logger = logging.getLogger(__name__)

STRENGTH_TABLE = 'team_strength'

REPLACEMENT_COVER = 0.5  # a missing player's output is half replaced by the next player
MAX_SHARE = 0.8          # no single absence can remove more than this share of a team
GOALKEEPER = 1
DEFENDER = 2
LEFT_CLUB = 'u'


def fetch_squad_rows(cursor, year_start):
    """Every player in the latest bootstrap snapshot for the season."""
    cursor.execute("""
        SELECT id, web_name, team, element_type, expected_goals, expected_assists,
               minutes, chance_of_playing_next_round, status
        FROM bootstrapstatic_elements
        WHERE year_start = %s
          AND gameweek = (SELECT MAX(gameweek) FROM bootstrapstatic_elements WHERE year_start = %s)
    """, (year_start, year_start))
    return cursor.fetchall()


def missing_fraction(chance):
    """How much of a player is missing: 0 when fit (or unknown), 1 when ruled out."""
    if chance is None:
        return 0.0
    return min(1.0, max(0.0, 1 - float(chance) / 100))


def _ratio(part, total):
    return part / total if total > 0 else 0.0


def team_absences(players):
    """Weighted attack and defence shares lost, plus the list of missing players.

    `attack_share` and `defence_share` are weighted by how missing each player is.
    Each entry in `missing` carries the player's raw, unweighted share.
    """
    squad = [p for p in players if p.get('status') != LEFT_CLUB]
    attack_totals = [float(p['expected_goals'] or 0) + float(p['expected_assists'] or 0) for p in squad]
    team_attack = sum(attack_totals)
    team_defence = sum(float(p['minutes'] or 0) for p in squad if p['element_type'] in (GOALKEEPER, DEFENDER))

    # The first-choice goalkeeper is the one with the most minutes among the current squad.
    keeper_minutes = [float(p['minutes'] or 0) for p in squad if p['element_type'] == GOALKEEPER]
    top_keeper_minutes = max(keeper_minutes) if keeper_minutes else 0.0

    attack_share = defence_share = 0.0
    missing = []
    for p, involvement in zip(squad, attack_totals):
        fraction = missing_fraction(p.get('chance_of_playing_next_round'))
        if fraction <= 0:
            continue
        raw_attack = _ratio(involvement, team_attack)
        raw_defence = (_ratio(float(p['minutes'] or 0), team_defence)
                       if p['element_type'] in (GOALKEEPER, DEFENDER) else 0.0)
        attack_share += raw_attack * fraction
        defence_share += raw_defence * fraction
        missing.append({
            'name': p['web_name'],
            'position': p['element_type'],
            'role': 'attack' if raw_attack >= raw_defence else 'defence',
            'share': max(raw_attack, raw_defence),
            'chance': p.get('chance_of_playing_next_round') or 0,
            'first_choice': (p['element_type'] == GOALKEEPER
                             and float(p['minutes'] or 0) >= top_keeper_minutes),
        })
    return {'attack_share': attack_share, 'defence_share': defence_share, 'missing': missing}


def adjust(attack, defence, attack_share, defence_share):
    """Weaken ratings for absences. A higher defence rating means conceding more."""
    attack_adj = attack + math.log(1 - REPLACEMENT_COVER * min(attack_share, MAX_SHARE))
    defence_adj = defence - math.log(1 - REPLACEMENT_COVER * min(defence_share, MAX_SHARE))
    return attack_adj, defence_adj


def goals_vs_average(attack, defence, league_mean_attack, league_mean_defence, home_adv):
    """Goals a game scored and conceded against an average side, with half the home edge."""
    scored = math.exp(attack + league_mean_defence + home_adv / 2)
    conceded = math.exp(league_mean_attack + defence + home_adv / 2)
    return scored, conceded


def build_team_strengths(teams, ratings, home_adv, squad_rows):
    """{team_id: strength} for every team; an unrated team uses default ratings."""
    # Same default the engine uses for a team it has no rating for.
    default = {'attack': 0.0, 'defence': 0.0}
    rated = dict(teams)
    if not rated:
        return {}
    ratings = {t['code']: ratings.get(t['code'], default) for t in rated.values()}
    mean_attack = sum(ratings[t['code']]['attack'] for t in rated.values()) / len(rated)
    mean_defence = sum(ratings[t['code']]['defence'] for t in rated.values()) / len(rated)

    by_team = {}
    for row in squad_rows:
        by_team.setdefault(row['team'], []).append(row)

    results = {}
    for tid, team in rated.items():
        rating = ratings[team['code']]
        absences = team_absences(by_team.get(tid, []))
        attack_adj, defence_adj = adjust(rating['attack'], rating['defence'],
                                         absences['attack_share'], absences['defence_share'])
        scored, conceded = goals_vs_average(rating['attack'], rating['defence'], mean_attack, mean_defence, home_adv)
        scored_adj, conceded_adj = goals_vs_average(attack_adj, defence_adj, mean_attack, mean_defence, home_adv)
        results[tid] = {
            'team_id': tid,
            'name': team['name'],
            'scored': scored,
            'scored_adjusted': scored_adj,
            'conceded': conceded,
            'conceded_adjusted': conceded_adj,
            'missing': sorted(absences['missing'], key=lambda m: m['share'], reverse=True),
        }
    league_scored = sum(r['scored'] for r in results.values()) / len(results)
    for r in results.values():
        r['league_scored'] = league_scored
    return results


def persist_team_strengths(conn, strengths):
    """Replace the whole table with today's strengths, in one commit."""
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {STRENGTH_TABLE} (
            team_id INT PRIMARY KEY,
            name VARCHAR(60),
            scored FLOAT,
            scored_adjusted FLOAT,
            conceded FLOAT,
            conceded_adjusted FLOAT,
            league_scored FLOAT,
            missing_json TEXT,
            computed_at DATETIME
        )
    """)
    now = datetime.utcnow()
    records = [
        (s['team_id'], s['name'], s['scored'], s['scored_adjusted'], s['conceded'],
         s['conceded_adjusted'], s['league_scored'], json.dumps(s['missing'], default=float), now)
        for s in strengths.values()
    ]
    cursor.execute(f"DELETE FROM {STRENGTH_TABLE}")
    if records:
        cursor.executemany(f"""
            INSERT INTO {STRENGTH_TABLE}
                (team_id, name, scored, scored_adjusted, conceded, conceded_adjusted,
                 league_scored, missing_json, computed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, records)
    conn.commit()


NOT_READY = {
    'status': 'not_ready',
    'message': {'title': 'Team strength is on its way',
                'body': "We're still working this out. Check back a little later."},
}


def load_team_strength(team_id):
    """Live-route read: what the daily job stored. None for an unknown team."""
    # Imported here, not at the top, to avoid a circular import with the engine.
    from FPL_site.matchPredictionEngine import fetch_teams_for_season

    conn = connect_db()
    if conn is None:
        logger.error('load_team_strength: could not connect to the database.')
        return dict(NOT_READY)
    try:
        cursor = conn.cursor(dictionary=True)
        team_id = int(team_id)
        if team_id not in fetch_teams_for_season(cursor, season_start):
            return None
        try:
            cursor.execute(f"SELECT * FROM {STRENGTH_TABLE} WHERE team_id = %s", (team_id,))
            row = cursor.fetchone()
        except ProgrammingError as e:
            # The table only appears after the first daily run; until then it is "not ready".
            # Never create it here: a request path must not change the database.
            if e.errno != errorcode.ER_NO_SUCH_TABLE:
                raise
            return dict(NOT_READY)
        if not row:
            return dict(NOT_READY)
        strength = {
            'scored': float(row['scored']), 'scored_adjusted': float(row['scored_adjusted']),
            'conceded': float(row['conceded']), 'conceded_adjusted': float(row['conceded_adjusted']),
            'league_scored': float(row['league_scored']),
            'missing': json.loads(row['missing_json'] or '[]'),
        }
        summary = strength_summary(row['name'], strength)
        return {
            'status': 'ready',
            'team_name': row['name'],
            'headline': summary['headline'],
            'reason': summary['reason'],
            'scored': round(strength['scored'], 1),
            'scored_adjusted': round(strength['scored_adjusted'], 1),
            'conceded': round(strength['conceded'], 1),
            'conceded_adjusted': round(strength['conceded_adjusted'], 1),
            # The league average goals scored, which the gauges compare each team against.
            'league_scored': round(strength['league_scored'], 2),
            # Unrounded gauge positions and their words; the rounded figures above are for the written numbers.
            'gauge': gauge_summary(strength),
            'missing': strength['missing'],
        }
    finally:
        conn.close()
