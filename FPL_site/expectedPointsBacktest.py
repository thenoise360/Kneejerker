"""Offline walk-forward backtest: would our expected points have beaten the official number?

Run by hand: python -m FPL_site.expectedPointsBacktest
For each target gameweek, train only on earlier gameweeks and predict that one, then compare with
the official ep_next from the snapshot taken just before it, on the same players. Writes a report
to docs/superpowers/reports/. Never run from a request or the daily job.
"""
import logging
import os
from datetime import date

from FPL_site.dataModels import connect_db, current_season_start, refresh_season_start
from FPL_site.expectedPointsFeatures import training_rows
from FPL_site.expectedPointsModel import (train, predict, fetch_history_rows, fetch_snapshot_rows,
                                          MODEL_VERSION)
from FPL_site.expectedPointsRecord import template_squad, captain_pick, mean_absolute_error
from FPL_site.fixtureXgHistory import fill_missing, load_fixture_xg

logger = logging.getLogger(__name__)

FIRST_TARGET_GAMEWEEK = 6   # leave the first five gameweeks of the earliest backtest season to train on
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs', 'superpowers', 'reports')


def walk_forward(rows, official, targets):
    out = []
    for year, gw in targets:
        past = [r for r in rows if (r['year_start'], r['gameweek']) < (year, gw)]
        now = [r for r in rows if (r['year_start'], r['gameweek']) == (year, gw)
               and official.get((year, gw, r['player_id'])) is not None]
        if not past or not now:
            continue
        values = predict(train(past), now)
        for r, v in zip(now, values):
            if v != v:   # nan: no model for that position yet
                continue
            out.append({'year_start': year, 'gameweek': gw, 'player_id': r['player_id'],
                        'position': r['position'], 'ours': v,
                        'official': official[(year, gw, r['player_id'])], 'actual': r['target']})
    return out


def summarise(results, squads_by_gw):
    by_position, by_gw = {}, {}
    for r in results:
        by_position.setdefault(r['position'], []).append(r)
        by_gw.setdefault((r['year_start'], r['gameweek']), []).append(r)
    wins_ours = wins_official = ties = 0
    for key, group in by_gw.items():
        squad = squads_by_gw.get(key, [])
        actual = {r['player_id']: r['actual'] for r in group}
        ours = captain_pick(squad, {r['player_id']: r['ours'] for r in group}, set(actual))
        official = captain_pick(squad, {r['player_id']: r['official'] for r in group}, set(actual))
        if ours is None or official is None:
            continue
        if actual[ours] > actual[official]:
            wins_ours += 1
        elif actual[official] > actual[ours]:
            wins_official += 1
        else:
            ties += 1
    mae_ours = mean_absolute_error([(r['ours'], r['actual']) for r in results])
    mae_official = mean_absolute_error([(r['official'], r['actual']) for r in results])
    return {
        'players': len(results), 'gameweeks': len(by_gw),
        'mae_ours': mae_ours, 'mae_official': mae_official,
        'mae_by_position': {p: {'ours': mean_absolute_error([(r['ours'], r['actual']) for r in g]),
                                'official': mean_absolute_error([(r['official'], r['actual']) for r in g]),
                                'players': len(g)} for p, g in sorted(by_position.items())},
        'captain_wins_ours': wins_ours, 'captain_wins_official': wins_official, 'captain_ties': ties,
        'passes': (mae_ours is not None and mae_official is not None
                   and mae_ours < mae_official and wins_ours > wins_official),
    }


POSITION_NAMES = {1: 'Goalkeepers', 2: 'Defenders', 3: 'Midfielders', 4: 'Forwards'}


def render_report(summary, run_date):
    lines = [
        f'# Expected points backtest ({run_date})', '',
        f'Model version: `{MODEL_VERSION}`. Walk-forward: each gameweek predicted by a model trained '
        f'only on earlier gameweeks, compared with the official number from the snapshot just before it.', '',
        f'- Gameweeks: {summary["gameweeks"]}, player-gameweeks: {summary["players"]}',
        f'- Average error, ours: {summary["mae_ours"]}',
        f'- Average error, official: {summary["mae_official"]}',
        f'- Captain (most-selected squad each week): ours better {summary["captain_wins_ours"]}, '
        f'official better {summary["captain_wins_official"]}, same {summary["captain_ties"]}',
        f'- Passes: {"yes" if summary["passes"] else "no"}', '',
        '| Position | Ours | Official | Players |', '|---|---|---|---|',
    ]
    for p, m in summary['mae_by_position'].items():
        lines.append(f'| {POSITION_NAMES.get(int(p), p)} | {m["ours"]} | {m["official"]} | {m["players"]} |')
    return '\n'.join(lines) + '\n'


def main():
    logging.basicConfig(level=logging.INFO)
    refresh_season_start()
    year = current_season_start()
    conn = connect_db()
    try:
        cursor = conn.cursor(dictionary=True)
        years = [year - 2, year - 1, year]
        history = fetch_history_rows(cursor, years)
        snapshots = fetch_snapshot_rows(cursor, years)
        fill_missing(conn, cursor, sorted({(h['year_start'], h['gameweek']) for h in history}))
        rows = training_rows(history, snapshots, load_fixture_xg(cursor))
        ids = {(s['code'], s['year_start']): s['player_id'] for s in snapshots}
        for r in rows:
            r['player_id'] = ids.get((r['code'], r['year_start']))
        rows = [r for r in rows if r['player_id'] is not None]
        official = {(s['year_start'], s['gameweek'] + 1, s['player_id']): s['ep_next']
                    for s in snapshots if s['ep_next'] is not None}
        squads = {}
        for (y, gw) in {(s['year_start'], s['gameweek']) for s in snapshots}:
            before = [s for s in snapshots if s['year_start'] == y and s['gameweek'] == gw]
            squads[(y, gw + 1)] = template_squad([{'player_id': s['player_id'], 'position': s['element_type'],
                                                   'selected': s['selected']} for s in before])
        targets = sorted({(r['year_start'], r['gameweek']) for r in rows
                          if r['year_start'] >= year - 1
                          and (r['year_start'], r['gameweek']) >= (year - 1, FIRST_TARGET_GAMEWEEK)})
        summary = summarise(walk_forward(rows, official, targets), squads)
    finally:
        conn.close()
    os.makedirs(REPORT_DIR, exist_ok=True)
    run_date = date.today().isoformat()
    path = os.path.join(REPORT_DIR, f'expected-points-backtest-{run_date}.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(render_report(summary, run_date))
    print(f'Wrote {path}: passes={summary["passes"]}')


if __name__ == '__main__':
    main()
