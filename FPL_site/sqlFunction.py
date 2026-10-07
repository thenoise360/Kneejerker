import sys
import logging
import os
from tqdm import tqdm
import mysql.connector
import requests
from datetime import datetime
import pytz
from dataModels import get_players
from config import current_config

# Access configuration variables
host = current_config.HOST
user = current_config.USER
password = current_config.PASSWORD
db = current_config.DATABASE

# There is deliberately no fallback year: the update job derives year_start from bootstrap-static's
# gameweek 1 deadline (see season_start_from_events). If it cannot, it writes nothing, because data
# filed under a guessed year is what corrupted the 2024 season.
logger = logging.getLogger(__name__)
BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"


def season_start_from_events(events):
    """Calendar year (int) of the earliest event deadline, i.e. gameweek 1; None if unusable."""
    if not isinstance(events, (list, tuple)):
        return None
    deadlines = []
    for event in events:
        raw = event.get('deadline_time') if isinstance(event, dict) else None
        if not isinstance(raw, str):
            continue
        try:
            moment = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError:
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=pytz.utc)
        deadlines.append(moment)
    if not deadlines:
        return None
    return min(deadlines).year


def resolve_year_start(bootstrap):
    """year_start for this run as the string the tables have always been written with, or None."""
    year = season_start_from_events((bootstrap or {}).get('events') if isinstance(bootstrap, dict) else None)
    return str(year) if year is not None else None


def fetch_bootstrap_static():
    """One bootstrap-static fetch, shared by every step of an update run. None on failure."""
    try:
        response = requests.get(BOOTSTRAP_URL)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException as err:
        print(f"Error fetching bootstrap-static: {err}")
    return None

# Database connection
def connect_to_db(user, password, database, host):
    try:
        return mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# Get column names of a table
def get_column_names(cursor, table_name):
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    return [column[0] for column in cursor.fetchall()]

# Function to generate the current gameweek.
# api/entry/1/'s current_event is None for the entire close season, which
# previously made update_bootstrap_static_tables() below abort completely -
# silently skipping every daily update from the moment a season ends until
# gameweek 1 of the next one kicks off. Mirrors dataModels.py's more robust
# version, which reads bootstrap-static's own events list and explicitly
# returns 0 for pre-season instead of None.
def current_gameweek_from_events(events):
    current_gw = next((event['id'] for event in events if event.get('is_current')), None)
    if current_gw:
        return current_gw

    next_gw = next((event['id'] for event in events if event.get('is_next')), None)
    if next_gw == 1:
        return 0  # Gameweek 0 represents pre-season
    elif next_gw:
        return next_gw - 1
    return None


def generateCurrentGameweek(bootstrap=None):
    if bootstrap is None:
        bootstrap = fetch_bootstrap_static()
    if bootstrap is None:
        return None
    return current_gameweek_from_events(bootstrap.get('events', []))


# Update bootstrap static tables with gameweek handling
def update_bootstrap_static_tables(user, password, database, host, bootstrap=None, year_start=None):
    print("Updating Bootstrap Static Tables...")
    db_connect = connect_to_db(user, password, database, host)
    if not db_connect:
        print("Failed to connect to the database.")
        return
    cursor = db_connect.cursor()

    if bootstrap is None:
        bootstrap = fetch_bootstrap_static()
    if bootstrap is None:
        print("Unable to fetch bootstrap-static.")
        return
    if year_start is None:
        year_start = resolve_year_start(bootstrap)
    if year_start is None:
        logger.error("Cannot work out the season year from bootstrap-static; writing nothing.")
        return

    current_gameweek = generateCurrentGameweek(bootstrap)
    if current_gameweek is None:
        print("Unable to determine current gameweek.")
        return

    response = bootstrap
    for table_name, data in response.items():
        if table_name not in ["events", "elements", "teams"]:
            continue

        table = f"bootstrapstatic_{table_name}"
        existing_columns = get_column_names(cursor, table)
        batch = []
        current_batch_size = 0
        batch_size_limit = 16 * 1024 * 1024  # 16 MB
        row_count = 0

        for record in tqdm(data, desc=f"Updating {table}"):
            record = {k: v for k, v in record.items() if k in existing_columns}

            # Add year_start and gameweek if they exist in the table
            if 'year_start' in existing_columns:
                record['year_start'] = year_start
            if 'gameweek' in existing_columns:
                record['gameweek'] = current_gameweek

            columns = ', '.join(f"`{col}`" for col in record.keys())
            values = ', '.join(f"%({col})s" for col in record.keys())
            update = ', '.join(f"`{col}`=VALUES(`{col}`)" for col in record.keys())
            record_size = sum(len(str(value)) for value in record.values())

            sql = f"""
                INSERT INTO {table} ({columns})
                VALUES ({values})
                ON DUPLICATE KEY UPDATE {update};
            """

            if current_batch_size + record_size > batch_size_limit:
                cursor.executemany(sql, batch)
                db_connect.commit()
                batch = []
                current_batch_size = 0

            batch.append(record)
            current_batch_size += record_size
            row_count += 1

        if batch:
            cursor.executemany(sql, batch)
            db_connect.commit()

        print(f"{table} updated with {row_count} rows.")

    cursor.close()
    db_connect.close()

def update_fixtures_tables(user, password, database, host, year_start=None):
    if year_start is None:
        logger.error("update_fixtures_tables: no season year given; writing nothing.")
        return
    print("Updating Fixtures Tables...")
    db_connect = connect_to_db(user, password, database, host)
    if not db_connect:
        print("Failed to connect to the database.")
        return
    cursor = db_connect.cursor()

    response = requests.get("https://fantasy.premierleague.com/api/fixtures/").json()
    table = "fixtures_fixtures"
    existing_columns = get_column_names(cursor, table)
    batch = []
    current_batch_size = 0
    batch_size_limit = 16 * 1024 * 1024  # 16 MB
    row_count = 0

    for record in tqdm(response, desc="Updating fixtures"):
        record = {k: v for k, v in record.items() if k in existing_columns}

        # Handle missing event values
        if 'event' in record and record['event'] is None:
            record['event'] = -1  # Replace with a default value (e.g., -1 for unknown)

        # Add year_start to the record if it's not already present
        if 'year_start' in existing_columns:
            record['year_start'] = year_start

        columns = ', '.join(f"`{col}`" for col in record.keys())
        values = ', '.join(f"%({col})s" for col in record.keys())
        update = ', '.join(f"`{col}`=VALUES(`{col}`)" for col in record.keys())
        record_size = sum(len(str(value)) for value in record.values())

        sql = f"""
            INSERT INTO {table} ({columns})
            VALUES ({values})
            ON DUPLICATE KEY UPDATE {update};
        """

        if current_batch_size + record_size > batch_size_limit:
            cursor.executemany(sql, batch)
            db_connect.commit()
            batch = []
            current_batch_size = 0

        batch.append(record)
        current_batch_size += record_size
        row_count += 1

    if batch:
        cursor.executemany(sql, batch)
        db_connect.commit()

    print(f"Fixtures table updated with {row_count} rows.")
    cursor.close()
    db_connect.close()


def update_element_summary_tables(user, password, database, host, year_start=None):
    if year_start is None:
        logger.error("update_element_summary_tables: no season year given; writing nothing.")
        return
    print("Updating Element Summary Tables...")
    db_connect = connect_to_db(user, password, database, host)
    if not db_connect:
        print("Failed to connect to the database.")
        return
    cursor = db_connect.cursor()

    players = get_players()
    table_data = {
        "fixtures": "elementsummary_fixtures",
        "history": "elementsummary_history",
        "history_past": "elementsummary_history_past"
    }

    for player in tqdm(players, desc="Updating element summaries"):
        player_id = player['id']
        try:
            response = requests.get(f"https://fantasy.premierleague.com/api/element-summary/{player_id}/").json()
        except requests.RequestException as err:
            print(f"Error fetching data for player {player_id}: {err}")
            continue

        for key, table in table_data.items():
            if key not in response:
                continue

            existing_columns = get_column_names(cursor, table)
            batch = []
            current_batch_size = 0
            batch_size_limit = 16 * 1024 * 1024  # 16 MB
            row_count = 0

            for record in response[key]:
                record = {k: v for k, v in record.items() if k in existing_columns}

                # Add required fields
                if 'id' in existing_columns and 'id' not in record:
                    record['id'] = player_id  # Ensure the `id` field is present
                if 'year_start' in existing_columns and 'year_start' not in record:
                    record['year_start'] = year_start

                columns = ', '.join(f"`{col}`" for col in record.keys())
                values = ', '.join(f"%({col})s" for col in record.keys())
                update = ', '.join(f"`{col}`=VALUES(`{col}`)" for col in record.keys())
                record_size = sum(len(str(value)) for value in record.values())

                sql = f"""
                    INSERT INTO {table} ({columns})
                    VALUES ({values})
                    ON DUPLICATE KEY UPDATE {update};
                """

                if current_batch_size + record_size > batch_size_limit:
                    cursor.executemany(sql, batch)
                    db_connect.commit()
                    batch = []
                    current_batch_size = 0

                batch.append(record)
                current_batch_size += record_size
                row_count += 1

            if batch:
                cursor.executemany(sql, batch)
                db_connect.commit()

    cursor.close()
    db_connect.close()

# Update all tables
def update_all_tables():
    # Fetch bootstrap-static once and derive the season from it, so the new season's
    # pre-season data is written under the new year without anyone editing a constant.
    bootstrap = fetch_bootstrap_static()
    year_start = resolve_year_start(bootstrap)
    if year_start is None:
        logger.error("update_all_tables: could not work out the season year (bootstrap-static "
                     "failed or had no usable events); skipping the whole run so nothing is "
                     "filed under a guessed year.")
        return
    update_bootstrap_static_tables(user, password, db, host, bootstrap=bootstrap, year_start=year_start)
    update_fixtures_tables(user, password, db, host, year_start=year_start)
    update_element_summary_tables(user, password, db, host, year_start=year_start)

if __name__ == "__main__":
    print("Starting updates...")
    update_all_tables()
    print("Updates completed.")
