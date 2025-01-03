import sys
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

season_start = "2024"

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

# Function to generate the current gameweek
def generateCurrentGameweek():
    try:
        response = requests.get("https://fantasy.premierleague.com/api/entry/1/")
        bootstrapStaticData = response.json()
        return bootstrapStaticData.get('current_event', None)
    except requests.RequestException as err:
        print(f"Error fetching current gameweek: {err}")
        return None

# Update bootstrap static tables with gameweek handling
def update_bootstrap_static_tables(user, password, database, host):
    print("Updating Bootstrap Static Tables...")
    db_connect = connect_to_db(user, password, database, host)
    if not db_connect:
        print("Failed to connect to the database.")
        return
    cursor = db_connect.cursor()

    current_gameweek = generateCurrentGameweek()
    if current_gameweek is None:
        print("Unable to determine current gameweek.")
        return

    response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static").json()
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
                record['year_start'] = season_start
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

def update_fixtures_tables(user, password, database, host):
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
            record['year_start'] = season_start

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


def update_element_summary_tables(user, password, database, host):
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
                    record['year_start'] = season_start

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
    update_bootstrap_static_tables(user, password, db, host)
    update_fixtures_tables(user, password, db, host)
    update_element_summary_tables(user, password, db, host)

if __name__ == "__main__":
    print("Starting updates...")
    update_all_tables()
    print("Updates completed.")
