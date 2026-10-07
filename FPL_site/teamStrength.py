"""Absence-adjusted team strength.

Takes the engine's attack and defence ratings and weakens them for the players who are
missing this week. Pure functions, apart from one read-only fetcher. Never uses the
Influence, Creativity and Threat index: a player's weight is their share of the team's
expected goals plus expected assists (attack) or of its goalkeeper-and-defender minutes (defence).

The engine is deliberately not imported here: a later task wires this module into the engine.
"""
import math

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
