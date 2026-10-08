"""The weekly record of our expected points: what we forecast before each deadline, and how
accurate it turned out, next to the official game's number for the same players.

Same honesty rule as matchPredictionEngine's fixture_prediction_log: only forecasts made before
the deadline count, and the log is append-only.
"""
import json
import logging
from datetime import datetime

from FPL_site.expectedPointsFeatures import MODEL_VERSION

logger = logging.getLogger(__name__)

LOG_TABLE = 'expected_points_log'
ACCURACY_TABLE = 'expected_points_accuracy'
CURRENT_TABLE = 'player_expected_points'
DEADLINE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
TEMPLATE_SHAPE = {1: 2, 2: 5, 3: 5, 4: 3}


def _deadline(event):
    try:
        return datetime.strptime(event.get('deadline_time') or '', DEADLINE_FORMAT)
    except (ValueError, TypeError):
        return None


def deadline_for(events, gameweek):
    event = next((e for e in events if e.get('id') == gameweek), None)
    return _deadline(event) if event else None


def next_gameweek(events, now):
    upcoming = sorted((d, e['id']) for e in events for d in [_deadline(e)] if d and d > now)
    return upcoming[0][1] if upcoming else None


def is_settled(events, gameweek):
    event = next((e for e in events if e.get('id') == gameweek), None)
    return bool(event and event.get('finished') and event.get('data_checked'))


def log_forecasts(conn, rows, gameweek, deadline, now):
    if deadline is None or now >= deadline or not rows:
        return 0
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {LOG_TABLE} (
            player_id INT NOT NULL,
            code INT NOT NULL,
            gameweek INT NOT NULL,
            expected_points FLOAT,
            official_expected_points FLOAT,
            model_version VARCHAR(40) NOT NULL,
            logged_at DATETIME NOT NULL,
            log_date DATE NOT NULL,
            PRIMARY KEY (player_id, gameweek, model_version, log_date)
        )
    """)
    cursor.executemany(f"""
        INSERT IGNORE INTO {LOG_TABLE}
            (player_id, code, gameweek, expected_points, official_expected_points,
             model_version, logged_at, log_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, [(r['player_id'], r['code'], gameweek, r['expected_points'], r['official_expected_points'],
           MODEL_VERSION, now, now.date()) for r in rows])
    conn.commit()
    logger.info("Logged %d expected points forecasts for gameweek %s.", len(rows), gameweek)
    return len(rows)


def forecast_of_record(log_rows, deadline):
    record = {}
    for r in sorted(log_rows, key=lambda r: r['logged_at']):
        if r['logged_at'] < deadline:
            record[r['player_id']] = r
    return record


def template_squad(selection_rows):
    squad = []
    for position, count in TEMPLATE_SHAPE.items():
        group = sorted((r for r in selection_rows if r['position'] == position),
                       key=lambda r: (-(r['selected'] or 0), r['player_id']))
        squad.extend(r['player_id'] for r in group[:count])
    return squad


def captain_pick(squad, values, playing):
    options = [(-values[p], p) for p in squad if p in playing and values.get(p) is not None]
    return min(options)[1] if options else None


def mean_absolute_error(pairs):
    return round(sum(abs(f - a) for f, a in pairs) / len(pairs), 3) if pairs else None


def accuracy_for_gameweek(record, actual, squad, playing):
    """record: {player_id: {'position', 'expected_points', 'official_expected_points'}}."""
    both = [r for pid, r in record.items() if pid in actual
            and r.get('expected_points') is not None and r.get('official_expected_points') is not None]
    by_position = {}
    for r in both:
        by_position.setdefault(r['position'], []).append(r)
    ours = {pid: r['expected_points'] for pid, r in record.items() if r.get('expected_points') is not None}
    official = {pid: r['official_expected_points'] for pid, r in record.items()
                if r.get('official_expected_points') is not None}
    cap_ours, cap_official = captain_pick(squad, ours, playing), captain_pick(squad, official, playing)
    return {
        'players': len(both),
        'mae_ours': mean_absolute_error([(r['expected_points'], actual[r['player_id']]) for r in both]),
        'mae_official': mean_absolute_error([(r['official_expected_points'], actual[r['player_id']]) for r in both]),
        'mae_by_position': {pos: {'ours': mean_absolute_error([(r['expected_points'], actual[r['player_id']]) for r in g]),
                                  'official': mean_absolute_error([(r['official_expected_points'], actual[r['player_id']]) for r in g]),
                                  'players': len(g)}
                            for pos, g in by_position.items()},
        'captain_ours': cap_ours,
        'captain_official': cap_official,
        'captain_ours_points': actual.get(cap_ours),
        'captain_official_points': actual.get(cap_official),
    }


def persist_accuracy(conn, gameweek, year_start, result, now):
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {ACCURACY_TABLE} (
            year_start INT NOT NULL,
            gameweek INT NOT NULL,
            model_version VARCHAR(40) NOT NULL,
            players INT NOT NULL,
            mae_ours FLOAT,
            mae_official FLOAT,
            mae_by_position TEXT,
            captain_ours INT,
            captain_official INT,
            captain_ours_points INT,
            captain_official_points INT,
            computed_at DATETIME NOT NULL,
            PRIMARY KEY (year_start, gameweek, model_version)
        )
    """)
    cursor.execute(f"""
        REPLACE INTO {ACCURACY_TABLE}
            (year_start, gameweek, model_version, players, mae_ours, mae_official, mae_by_position,
             captain_ours, captain_official, captain_ours_points, captain_official_points, computed_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (year_start, gameweek, MODEL_VERSION, result['players'], result['mae_ours'],
          result['mae_official'], json.dumps(result['mae_by_position']), result['captain_ours'],
          result['captain_official'], result['captain_ours_points'], result['captain_official_points'], now))
    conn.commit()


def persist_current(conn, rows, now):
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {CURRENT_TABLE} (
            player_id INT NOT NULL,
            code INT NOT NULL,
            gameweek INT NOT NULL,
            expected_points FLOAT,
            model_version VARCHAR(40) NOT NULL,
            computed_at DATETIME NOT NULL,
            PRIMARY KEY (player_id, gameweek)
        )
    """)
    cursor.executemany(f"""
        REPLACE INTO {CURRENT_TABLE} (player_id, code, gameweek, expected_points, model_version, computed_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, [(r['player_id'], r['code'], r['gameweek'], r['expected_points'], MODEL_VERSION, now) for r in rows])
    conn.commit()
