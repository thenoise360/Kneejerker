import sys
import os

# Get the directory of the current file
current_dir = os.path.dirname(__file__)

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)

# Add the FPL_site directory to sys.path
fpl_site_dir = current_dir
sys.path.insert(0, fpl_site_dir)

# Import necessary modules
import genericMethods
import mysql.connector
import pymysql
import sqlite3
import pandas
import json
import requests
from datetime import datetime
import pytz
from dataModels import get_players
from dotenv import load_dotenv
from config import current_config

# Access configuration variables
host = current_config.HOST
user = current_config.USER
password = current_config.PASSWORD
db = current_config.DATABASE

season_start = "2024"

conversions = {
    'int': 'INT',
    'bool': 'INT',
    'str': 'TEXT',
    'float': 'FLOAT'
    }

# TODO: DELETE ONCE CURRENT IMPORT ERROR IS SORTED (SEE LINE 1)
def generateCurrentGameweek():
    JSON = requests.get("https://fantasy.premierleague.com/api/entry/1/")
    bootstrapStaticData = JSON.json()
    DumpsPre = json.dumps(bootstrapStaticData)
    dumps = json.loads(DumpsPre)
    for keys in dumps:
        if keys == 'current_event':
            return dumps[keys]

def get_column_names(cursor, table_name):
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    return [column[0] for column in cursor.fetchall()]

def unicodeReplace(string):
    cleanedString = string.replace("Á", "A").replace("á", "a").replace("À", "A").replace("à", "a").replace("Ȧ", "A").replace("ȧ", "a").replace("Â", "A").replace("â", "a").replace("Ä", "A").replace("ä", "a").replace("Ǎ", "A").replace("ǎ", "a").replace("Ă", "A").replace("ă", "a").replace("Ā", "A").replace("ā", "a").replace("Ã", "A").replace("ã", "a").replace("Å", "A").replace("å", "a").replace("Ą", "A").replace("ą", "a").replace("Ⱥ", "A").replace("Ǡ", "A").replace("ǡ", "a").replace("Ǻ", "A").replace("ǻ", "a").replace("Ǟ", "A").replace("ǟ", "a").replace("Ȁ", "A").replace("ȁ", "a").replace("Ȃ", "A").replace("ȃ", "a").replace("Æ", "AE").replace("æ", "ae").replace("Ǽ", "AE").replace("ǽ", "ae").replace("Ǣ", "AE").replace("ǣ", "ae").replace("Ḃ", "B").replace("ḃ", "b").replace("ƀ", "b").replace("Ƀ", "B").replace("Ɓ", "B").replace("Ƃ", "B").replace("ƃ", "b").replace("Ƅ", "b").replace("ƅ", "b").replace("Ć", "C").replace("ć", "c").replace("Ċ", "C").replace("ċ", "c").replace("Ĉ", "C").replace("ĉ", "c").replace("Č", "C").replace("č", "c").replace("Ç", "C").replace("ç", "c").replace("Ȼ", "C").replace("ȼ", "c").replace("Ƈ", "C").replace("ƈ", "c").replace("Ɔ", "C").replace("Ḋ", "D").replace("ḋ", "d").replace("Ď", "D").replace("ď", "d").replace("Đ", "D").replace("đ", "d").replace("Ƌ", "D").replace("ƌ", "d").replace("Ɗ", "D").replace("Ð", "D").replace("ð", "d").replace("ƍ", "d").replace("ȸ", "db").replace("Ǳ", "DZ").replace("ǲ", "Dz").replace("ǳ", "dz").replace("Ǆ", "DZ").replace("ǅ", "Dz").replace("ǆ", "dz").replace("Ɖ", "D").replace("ȡ", "d").replace("É", "E").replace("é", "e").replace("È", "E").replace("è", "e").replace("Ė", "E").replace("ė", "e").replace("Ê", "E").replace("ê", "e").replace("Ë", "E").replace("ë", "e").replace("Ě", "E").replace("ě", "e").replace("Ĕ", "E").replace("ĕ", "e").replace("Ē", "E").replace("ē", "e").replace("Ę", "E").replace("ę", "e").replace("Ȩ", "E").replace("ȩ", "e").replace("Ɇ", "E").replace("ɇ", "e").replace("Ȅ", "E").replace("ȅ", "e").replace("Ȇ", "E").replace("ȇ", "e").replace("Ǝ", "E").replace("ǝ", "e").replace("Ə", "e").replace("Ɛ", "e").replace("Ȝ", "e").replace("ȝ", "e").replace("Ḟ", "F").replace("ḟ", "f").replace("Ƒ", "F").replace("ƒ", "f").replace("Ǵ", "G").replace("ǵ", "g").replace("Ġ", "G").replace("ġ", "g").replace("Ĝ", "G").replace("ĝ", "g").replace("Ǧ", "G").replace("ǧ", "g").replace("Ğ", "G").replace("ğ", "g").replace("Ģ", "G").replace("ģ", "g").replace("Ǥ", "G").replace("ǥ", "g").replace("Ɠ", "G").replace("Ɣ", "g").replace("Ĥ", "H").replace("ĥ", "h").replace("Ȟ", "H").replace("ȟ", "h").replace("Ħ", "H").replace("ħ", "h").replace("ƕ", "h").replace("Ƕ", "H").replace("ı", "i").replace("Í", "I").replace("í", "i").replace("Ì", "I").replace("ì", "i").replace("İ", "I").replace("Î", "i").replace("î", "I").replace("Ï", "i").replace("ï", "I").replace("Ǐ", "i").replace("ǐ", "I").replace("Ĭ", "i").replace("ĭ", "I").replace("Ī", "i").replace("ī", "I").replace("Ĩ", "i").replace("ĩ", "I").replace("Į", "i").replace("į", "I").replace("Ɨ", "i").replace("Ȉ", "I").replace("ȉ", "i").replace("Ȋ", "I").replace("ȋ", "i").replace("Ɩ", "I").replace("Ĳ", "IJ").replace("ĳ", "ij").replace("ȷ", "j").replace("Ĵ", "J").replace("ĵ", "j").replace("ǰ", "j").replace("Ɉ", "j").replace("ɉ", "j").replace("ĸ", "k").replace("Ǩ", "K").replace("ǩ", "k").replace("Ķ", "K").replace("ķ", "k").replace("Ƙ", "K").replace("ƙ", "k").replace("Ĺ", "L").replace("ĺ", "l").replace("Ŀ", "L").replace("ŀ", "l").replace("Ľ", "L").replace("ľ", "l").replace("Ļ", "L").replace("ļ", "l").replace("ƚ", "l").replace("Ƚ", "L").replace("Ł", "L").replace("ł", "l").replace("ƛ", "L").replace("Ǉ", "LJ").replace("ǈ", "Lj").replace("ǉ", "lj").replace("ȴ", "l").replace("Ṁ", "M").replace("ṁ", "m").replace("Ɯ", "M").replace("Ń", "N").replace("ń", "n").replace("Ǹ", "N").replace("ǹ", "n").replace("Ň", "N").replace("ň", "n").replace("Ñ", "N").replace("ñ", "n").replace("Ņ", "N").replace("ņ", "n").replace("Ɲ", "N").replace("ŉ", "n").replace("ƞ", "n").replace("Ƞ", "N").replace("Ǌ", "NJ").replace("ǋ", "Nj").replace("ǌ", "nj").replace("ȵ", "n").replace("Ŋ", "N").replace("ŋ", "n").replace("Ó", "O").replace("ó", "o").replace("Ò", "O").replace("ò", "o").replace("Ȯ", "O").replace("ȯ", "o").replace("Ô", "O").replace("ô", "o").replace("Ö", "O").replace("ö", "o").replace("Ǒ", "O").replace("ǒ", "o").replace("Ŏ", "O").replace("ŏ", "o").replace("Ō", "O").replace("ō", "o").replace("Õ", "O").replace("õ", "o").replace("Ǫ", "O").replace("ǫ", "o").replace("Ő", "O").replace("ő", "o").replace("Ɵ", "O").replace("Ø", "O").replace("ø", "o").replace("Ȱ", "O").replace("ȱ", "o").replace("Ȫ", "O").replace("ȫ", "o").replace("Ǿ", "O").replace("ǿ", "o").replace("Ȭ", "O").replace("ȭ", "o").replace("Ǭ", "O").replace("ǭ", "o").replace("Ȍ", "O").replace("ȍ", "o").replace("Ȏ", "O").replace("ȏ", "o").replace("Ơ", "O").replace("ơ", "o").replace("Ƣ", "O").replace("ƣ", "o").replace("Œ", "OE").replace("œ", "oe").replace("Ȣ", "O").replace("ȣ", "o").replace("Ṗ", "P").replace("ṗ", "p").replace("Ƥ", "P").replace("ƥ", "p").replace("Ɋ", "P").replace("ɋ", "p").replace("ȹ", "qp").replace("Ʀ", "R").replace("Ŕ", "R").replace("ŕ", "r").replace("Ř", "R").replace("ř", "r").replace("Ŗ", "R").replace("ŗ", "r").replace("Ɍ", "R").replace("ɍ", "r").replace("Ȑ", "R").replace("ȑ", "r").replace("Ȓ", "R").replace("ȓ", "r").replace("Ś", "S").replace("ś", "s").replace("Ṡ", "S").replace("ṡ", "s").replace("Ŝ", "S").replace("ŝ", "s").replace("Š", "S").replace("š", "s").replace("Ş", "S").replace("ş", "s").replace("Ș", "S").replace("ș", "s").replace("ȿ", "s").replace("Ʃ", "S").replace("Ƨ", "S").replace("ƨ", "s").replace("ƪ", "S").replace("ß", "ss").replace("ſ", "t").replace("ẛ", "t").replace("Ṫ", "T").replace("ṫ", "t").replace("Ť", "T").replace("ť", "t").replace("Ţ", "T").replace("ţ", "t").replace("Ƭ", "T").replace("ƭ", "t").replace("ƫ", "t").replace("Ʈ", "T").replace("Ț", "T").replace("ț", "t").replace("Ⱦ", "T").replace("ȶ", "t").replace("Þ", "t").replace("þ", "t").replace("Ŧ", "T").replace("ŧ", "t").replace("Ú", "U").replace("ú", "u").replace("Ù", "U").replace("ù", "u").replace("Û", "U").replace("û", "u").replace("Ü", "U").replace("ü", "u").replace("Ǔ", "U").replace("ǔ", "u").replace("Ŭ", "U").replace("ŭ", "u").replace("Ū", "U").replace("ū", "u").replace("Ũ", "U").replace("ũ", "u").replace("Ů", "U").replace("ů", "u").replace("Ų", "U").replace("ų", "u").replace("Ű", "U").replace("ű", "u").replace("Ʉ", "U").replace("Ǘ", "U").replace("ǘ", "u").replace("Ǜ", "U").replace("ǜ", "u").replace("Ǚ", "U").replace("ǚ", "u").replace("Ǖ", "U").replace("ǖ", "u").replace("Ȕ", "U").replace("ȕ", "u").replace("Ȗ", "U").replace("ȗ", "u").replace("Ư", "U").replace("ư", "u").replace("Ʊ", "U").replace("Ʋ", "U").replace("Ʌ", "V").replace("Ẃ", "W").replace("ẃ", "w").replace("Ẁ", "W").replace("ẁ", "w").replace("Ŵ", "W").replace("ŵ", "w").replace("Ẅ", "W").replace("ẅ", "w").replace("ƿ", "x").replace("Ƿ", "X").replace("Ý", "Y").replace("ý", "y").replace("Ỳ", "Y").replace("ỳ", "y").replace("Ŷ", "Y").replace("ŷ", "y").replace("ÿ", "Y").replace("Ÿ", "y").replace("Ȳ", "Y").replace("ȳ", "y").replace("Ɏ", "Y").replace("ɏ", "y").replace("Ƴ", "Y").replace("ƴ", "y").replace("Ź", "Z").replace("ź", "z").replace("Ż", "Z").replace("ż", "z").replace("Ž", "Z").replace("ž", "z").replace("Ƶ", "Z").replace("ƶ", "z").replace("Ȥ", "Z").replace("ȥ", "z").replace("ɀ", "Z").replace("Ʒ", "z").replace("Ǯ", "Z").replace("ǯ", "z").replace("Ƹ", "Z").replace("ƹ", "z").replace("ƺ", "Z").replace("ƾ", "z").replace("Ɂ", "Z").replace("ɂ", "z")
    return cleanedString



def dataConvertion(value):
    try:
        convert = float(value)
        return convert
    except:
        try:
            convert = int(value)
            return convert
        except:
            convert = str(value)
            return convert


def connectToSQL(user, password):
    mydb = mysql.connector.connect(
        host="localhost",
        user=user,
        password=password
    )
    
    return mydb

def connectToDB(user, password, database, host):
    try:
        mydb = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        return mydb
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def checkDatabases(user, password):
    mydb = connectToSQL(user, password)

    mycursor = mydb.cursor()

    mycursor.execute("SHOW DATABASES")

    for x in mycursor:
      print(x)

def typeConverter(value):
    if isinstance(value, str):
        try:
            return float(value)
        except:
            if isinstance(value, bool):
                return bool(value)
            else:
                return str(value)
    if isinstance(value, int):
        return int(value)



def updateEventTables(user, password, database, host):
    if generateCurrentGameweek() != None:
        currentGameweek = generateCurrentGameweek()
    else:
        currentGameweek = 1

    currentElement = requests.get(f"https://fantasy.premierleague.com/api/event/{currentGameweek}/live").json()
    currentDateTime = datetime.now(pytz.utc)
    
    dbConnect = connectToDB(user, password, database, host)
    cursor = dbConnect.cursor()

    for element in currentElement['elements']:
        true_table = f"events_elements"
                
        elementsKept = dict()
        for item in element:
            if item in ['gameweek','id','minutes','goals_scored','assists','clean_sheets','goals_conceded','own_goals','penalties_saved','penalties_missed','yellow_cards','red_cards','saves','bonus','bps','influence','creativity','threat','ict_index','starts','expected_goals','expected_assists','expected_goal_involvements','expected_goals_conceded','total_points','in_dreamteam','fixture','minutes_points','minutes_value','assists_points','assists_value','goals_scored_points','goals_scored_value','bonus_points','bonus_value','goals_conceded_points','goals_conceded_value','saves_points','saves_value','yellow_cards_points','yellow_cards_value','clean_sheets_points','clean_sheets_value','red_cards_points','red_cards_value','year_start']:
                if not isinstance(element[item], (list, dict)):
                    valueType = str(type(element[item])).replace("<class ","").replace(">","").replace("'","").replace(" ","")
                    if valueType == "NoneType":
                        value = 0
                    elif valueType == "bool":
                        value = 1 if element[item] else 0
                    else:
                        value = element[item]
                        if isinstance(value, str):
                            valueClean = str(unicodeReplace(str(value))).replace("'","")
                            value = valueClean
                    elementsKept[item] = value

        elementsKept['year_start'] = season_start

        columns = ','.join(f"`{str(x).replace('/', '_')}`" for x in elementsKept.keys())
        values = ','.join(f"'{str(x).replace('/', '_')}'" for x in elementsKept.values())

        sql_insert = f"""
            INSERT INTO {true_table} ({columns}) VALUES ({values})
            ON DUPLICATE KEY UPDATE {', '.join([f"{key}=VALUES({key})" for key in elementsKept.keys()])};
        """
        try:
            cursor.execute(sql_insert)
            dbConnect.commit()
        except pymysql.Error as e:
            print(f"Error executing SQL for table {true_table}: {e}")

    print(f"Events tables updated")
    cursor.close()

def updateElementsummaryTables(user, password, database, player_id, host):
    currentElement = requests.get(f"https://fantasy.premierleague.com/api/element-summary/{player_id}/").json()
    currentDateTime = datetime.now(pytz.utc)
    
    dbConnect = connectToDB(user, password, database, host)
    cursor = dbConnect.cursor()

    if 'detail' in currentElement:
        return
    else:
        for table in currentElement:
            if table not in ["fixtures", "history", "history_past"]:
                continue
            for element in currentElement[table]:
                true_table = f"elementsummary_{table}"
                
                elementsKept = dict()
                for item in element:
                    if not isinstance(element[item], (list, dict)):
                        valueType = str(type(element[item])).replace("<class ","").replace(">","").replace("'","").replace(" ","")
                        if valueType == "NoneType":
                            value = 0
                        elif valueType == "bool":
                            value = 1 if element[item] else 0
                        else:
                            value = element[item]
                            if isinstance(value, str):
                                valueClean = str(unicodeReplace(str(value))).replace("'","")
                                value = valueClean
                        elementsKept[item] = value

                elementsKept['year_start'] = season_start
                try:
                    elementsKept['id'] = element['id']
                except KeyError:
                    elementsKept['id'] = player_id

                columns = ','.join(f"`{str(x).replace('/', '_')}`" for x in elementsKept.keys())
                values = ','.join(f"'{str(x).replace('/', '_')}'" for x in elementsKept.values())

                sql_insert = f"""
                    INSERT INTO {true_table} ({columns}) VALUES ({values})
                    ON DUPLICATE KEY UPDATE {', '.join([f"{key}=VALUES({key})" for key in elementsKept.keys()])};
                """
                try:
                    cursor.execute(sql_insert)
                    dbConnect.commit()
                except pymysql.Error as e:
                    print(f"Error executing SQL for table {table}: {e}")

        print(f"Element_summary tables - player added: {player_id}")
        cursor.close()

def updateBootstrapStaticTables(user, password, database, host):
    currentElement = requests.get(f"https://fantasy.premierleague.com/api/bootstrap-static").json()
    
    dbConnect = connectToDB(user, password, database, host)
    cursor = dbConnect.cursor()

    for table in currentElement:
        if table not in ["events", "elements", "teams"]:
            continue
        for element in currentElement[table]:
            true_table = f"bootstrapstatic_{table}"
            elementsKept = dict()
            for item in element:
                if not isinstance(element[item], (list, dict)):
                    valueType = str(type(element[item])).replace("<class ","").replace(">","").replace("'","").replace(" ","")
                    if valueType == "NoneType":
                        value = 0
                    elif valueType == "bool":
                        value = 1 if element[item] else 0
                    else:
                        value = element[item]
                        if isinstance(value, str):
                            valueClean = str(unicodeReplace(str(value))).replace("'","")
                            value = valueClean
                        elementsKept[item] = value

            elementsKept['year_start'] = season_start
            if table == 'elements':
                if generateCurrentGameweek() == None:
                    currentGameweek = 1
                else:
                    currentGameweek = generateCurrentGameweek()
                elementsKept['gameweek'] = currentGameweek

            if table == 'events':
                tempHold = dict()
                for item in elementsKept:
                    if item in ['id','name','deadline_time','average_entry_score','finished','data_checked','highest_scoring_entry','deadline_time_epoch','deadline_time_game_offset','highest_score','is_previous','is_current','is_next','cup_leagues_created','h2h_ko_matches_created','chip_plays_bboost','chip_plays_3xc','most_selected','most_transferred_in','top_element','points','transfers_made','most_captained','most_vice_captained','chip_plays_freehit','chip_plays_wildcard','year_start']:
                        tempHold[item] = elementsKept[item]
                elementsKept = tempHold

            columns = ','.join(f"`{str(x).replace('/', '_')}`" for x in elementsKept.keys())
            values = ','.join(f"'{str(x).replace('/', '_')}'" for x in elementsKept.values())

            sql_insert = f"""
                INSERT INTO {true_table} ({columns}) VALUES ({values})
                ON DUPLICATE KEY UPDATE {', '.join([f"{key}=VALUES({key})" for key in elementsKept.keys()])};
            """
            try:
                cursor.execute(sql_insert)
                dbConnect.commit()
            except pymysql.Error as e:
                print(f"Error executing SQL for table {table}: {e}")

    print(f"Bootstrap static table updated: {true_table}")
    cursor.close()

def updateFixturesTables(user, password, database, host):
    dbConnect = connectToDB(user, password, database, host)
    if dbConnect is None:
        print("Failed to connect to the database.")
        return

    currentElement = requests.get(f"https://fantasy.premierleague.com/api/fixtures/").json()
    currentDateTime = datetime.now(pytz.utc)
    
    cursor = dbConnect.cursor()

    # Retrieve column names for the table
    column_names = get_column_names(cursor, 'fixtures_fixtures')

    for element in currentElement:
        true_table = f"fixtures_fixtures"
        elementsKept = dict()
        for item in element:
            if item in ['code', 'event', 'finished', 'finished_provisional', 'id', 'kickoff_time', 'minutes', 'provisional_start_time', 'started', 'team_a', 'team_a_score', 'team_h', 'team_h_score', 'goals_scored_a', 'goals_scored_h', 'assists_a', 'assists_h', 'own_goals_a', 'own_goals_h', 'penalties_saved_a', 'penalties_saved_h', 'penalties_missed_a', 'penalties_missed_h', 'yellow_cards_a', 'yellow_cards_h', 'red_cards_a', 'red_cards_h', 'saves_a', 'saves_h', 'bonus_a', 'bonus_h', 'bps_a', 'bps_h', 'team_h_difficulty', 'team_a_difficulty', 'pulse_id', 'year_start']:
                if not isinstance(element[item], (list, dict)):
                    valueType = str(type(element[item])).replace("<class ", "").replace(">", "").replace("'", "").replace(" ", "")
                    if valueType == "NoneType":
                        value = 0
                    elif valueType == "bool":
                        value = 1 if element[item] else 0
                    else:
                        value = element[item]
                        if isinstance(value, str):
                            valueClean = str(unicodeReplace(str(value))).replace("'", "")
                            value = valueClean
                    elementsKept[item] = value

        elementsKept['year_start'] = season_start

        columns = ','.join(f"`{str(x).replace('/', '_')}`" for x in elementsKept.keys())
        values = ','.join(f"'{str(x).replace('/', '_')}'" for x in elementsKept.values())

        # Construct the WHERE clause to check for existing records
        where_clause = ' AND '.join([f"{key}='{value}'" for key, value in elementsKept.items() if key in ['year_start', 'id']])

        # Query to check if the record exists
        check_query = f"SELECT * FROM {true_table} WHERE {where_clause}"

        cursor.execute(check_query)
        existing_record = cursor.fetchone()

        if existing_record:
            # Compare the records and update if there are differences
            update_needed = False
            for key, value in elementsKept.items():
                # Map existing record tuple to column names
                if key in column_names:
                    existing_value = existing_record[column_names.index(key)]
                    if str(existing_value) != str(value):
                        update_needed = True
                        break

            if update_needed:
                update_clause = ', '.join([f"`{key}`='{value}'" for key, value in elementsKept.items()])
                sql_update = f"UPDATE {true_table} SET {update_clause} WHERE {where_clause}"
                try:
                    cursor.execute(sql_update)
                    dbConnect.commit()
                except pymysql.Error as e:
                    print(f"Error executing SQL update for table {true_table}: {e}")
        else:
            sql_insert = f"""
                INSERT INTO {true_table} ({columns}) VALUES ({values})
                ON DUPLICATE KEY UPDATE {', '.join([f"{key}=VALUES({key})" for key in elementsKept.keys()])};
            """
            try:
                cursor.execute(sql_insert)
                dbConnect.commit()
            except pymysql.Error as e:
                print(f"Error executing SQL insert for table {true_table}: {e}")

    print(f"Fixtures tables updated")
    cursor.close()
    dbConnect.close()

def updateAllTables():
    players = get_players()
    updateFixturesTables(user, password, db, host)
    updateEventTables(user, password, db, host)
    updateBootstrapStaticTables(user, password, db, host)
    for player in players:
        updateElementsummaryTables(user, password, db, player['id'], host)

print("Project root:", project_root)
print("FPL_site directory:", fpl_site_dir)
