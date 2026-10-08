"""Replay past gameweeks into the weekly record, with only the data available at the time.

Run by hand: python -m FPL_site.expectedPointsBackfill [--from-season 2024] [--from-gameweek 6]
Each gameweek is forecast by a model trained only on earlier gameweeks, from the snapshot taken
after the gameweek before and the match engine fitted as of then (expectedPointsBacktest.walk_forward).
Rows are stored with source 'backfill' so they never mix with the live, pre-deadline record.
Re-running adds nothing for gameweeks already backfilled by this model version.
"""
import argparse
import logging
from datetime import datetime

from FPL_site import expectedPointsBacktest
from FPL_site.dataModels import connect_db, current_season_start, refresh_season_start
from FPL_site.expectedPointsFeatures import MODEL_VERSION
from FPL_site.expectedPointsModel import fetch_events
from FPL_site.expectedPointsRecord import (BACKFILL, LOG_TABLE, accuracy_for_gameweek, forecast_of_record,
                                           is_settled, log_forecasts, persist_accuracy)

logger = logging.getLogger(__name__)

DEFAULT_FROM_GAMEWEEK = 6
SEASONS_BACK = 2


def replay_targets(rows, from_season, from_gameweek, settled):
    return sorted({(r['year_start'], r['gameweek']) for r in rows
                   if (r['year_start'], r['gameweek']) >= (from_season, from_gameweek)
                   and settled(r['year_start'], r['gameweek'])})


def fetch_backfilled(cursor):
    try:
        cursor.execute(f"SELECT DISTINCT year_start, gameweek FROM {LOG_TABLE} "
                       f"WHERE source = %s AND model_version = %s", (BACKFILL, MODEL_VERSION))
        return {(r['year_start'], r['gameweek']) for r in cursor.fetchall()}
    except Exception:
        return set()   # the log table is created on the first write


def backfill(conn, data, targets, done, now):
    written = 0
    for year, gw in targets:
        if (year, gw) in done:
            continue
        results = expectedPointsBacktest.walk_forward(data['rows'], data['official'], [(year, gw)],
                                                      require_official=False)
        if not results:
            continue
        forecasts = [{'player_id': r['player_id'], 'code': r['code'], 'expected_points': r['ours'],
                      'official_expected_points': r['official']} for r in results]
        log_forecasts(conn, forecasts, year, gw, None, now, source=BACKFILL)
        record = forecast_of_record([dict(f, logged_at=now) for f in forecasts], None, source=BACKFILL)
        position = {r['player_id']: r['position'] for r in results}
        for pid, row in record.items():
            row['position'] = position.get(pid)
        actual = {r['player_id']: r['actual'] for r in results}
        result = accuracy_for_gameweek(record, actual, data['squads'].get((year, gw), []), set(actual))
        persist_accuracy(conn, gw, year, result, now, source=BACKFILL)
        written += 1
        logger.info("Backfilled %s gameweek %s: ours %s, official %s.",
                    year, gw, result['mae_ours'], result['mae_official'])
    return written


def main(argv=None):
    logging.basicConfig(level=logging.INFO)
    refresh_season_start()
    year = current_season_start()
    parser = argparse.ArgumentParser(description='Replay past gameweeks into the expected points record.')
    parser.add_argument('--from-season', type=int, default=year - SEASONS_BACK)
    parser.add_argument('--from-gameweek', type=int, default=DEFAULT_FROM_GAMEWEEK)
    args = parser.parse_args(argv)
    events = fetch_events()

    def settled(y, gw):
        if y < year:
            return True
        return events is not None and is_settled(events, gw)

    conn = connect_db()
    try:
        cursor = conn.cursor(dictionary=True)
        data = expectedPointsBacktest.load_replay_data(
            conn, cursor, [year - i for i in range(SEASONS_BACK, -1, -1)])
        targets = replay_targets(data['rows'], args.from_season, args.from_gameweek, settled)
        written = backfill(conn, data, targets, fetch_backfilled(cursor), datetime.utcnow())
    finally:
        conn.close()
    print(f'Backfilled {written} gameweeks with model {MODEL_VERSION}.')


if __name__ == '__main__':
    main()
