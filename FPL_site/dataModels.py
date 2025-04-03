import mysql.connector
from mysql.connector import Error
from FPL_site.config import current_config
from FPL_site.genericMethods import unicodeReplace
import requests
import json
import time
import httpx
import logging
import random

player_shirts = {
    3: '/static/content/Tshirts/sleeves-red-white-football-shirt-svgrepo-com.svg', # Arsenal
    7: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', # Aston Villa
    91: '/static/content/Tshirts/stripes-red-black-football-shirt-svgrepo-com.svg', # Bournemouth
    94: '/static/content/Tshirts/stripes-white-red-football-shirt-svgrepo-com.svg', # Brentford
    36: '/static/content/Tshirts/stripes-white-blue-football-shirt-svgrepo-com.svg', # Brighton
    90: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', # Burnley
    8: '/static/content/Tshirts/plain-blue-football-shirt-svgrepo-com.svg', # Chelsea
    31: '/static/content/Tshirts/halves-red-blue-football-shirt-svgrepo-com.svg', # Crystal Palace
    11: '/static/content/Tshirts/plain-navy-football-shirt-svgrepo-com.svg', # Everton
    54: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', # Fulham
    40: '/static/content/Tshirts/sleeves-blue-white-football-shirt-svgrepo-com.svg', # Ipswich Town
    2: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', # Leeds
    13: '/static/content/Tshirts/plain-navy-football-shirt-svgrepo-com.svg', # Leicester
    14: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', # Liverpool
    102: '/static/content/Tshirts/vertical-orange-black-football-shirt-svgrepo-com.svg', # Luton
    43: '/static/content/Tshirts/plain-skyblue-football-shirt-svgrepo-com.svg', # Man City
    1: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', # Man Utd
    4: '/static/content/Tshirts/stripes-white-black-football-shirt-svgrepo-com.svg', # Newcastle
    17: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', # Nottingham Forest
    49: '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg', # Sheffield Utd
    20: '/static/content/Tshirts/sash-white-red-football-shirt-svgrepo-com.svg', # Southampton
    6: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', # Spurs
    21: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', # West Ham
    39: '/static/content/Tshirts/plain-orange-football-shirt-svgrepo-com.svg', # Wolves
    'Unknown': '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg', # Default
}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

host = current_config.HOST
user = current_config.USER
password = current_config.PASSWORD
db = current_config.DATABASE

season = "2023_2024"
season_start = 2024

NULL = None

def connect_db():
    try:
        mydb = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=db,
        )
        return mydb
    except Error as e:
        logger.error(f"Error while connecting to MySQL: {e}")
        return None

def get_random_user_agent():
    """
    Returns a randomly chosen User-Agent string.
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    ]
    return random.choice(user_agents)

def loginToFPL(username, password):
    """
    Logs into FPL using HTTP/2 with randomized headers to bypass bot detection.
    """
    client = httpx.Client(http2=True)

    login_url = 'https://users.premierleague.com/accounts/login/'
    headers = {
        'User-Agent': get_random_user_agent(),  # Rotate user-agents
        'Referer': 'https://fantasy.premierleague.com/',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://fantasy.premierleague.com',
        'DNT': '1',
    }

    payload = {
        'password': password,
        'login': username,
        'redirect_uri': 'https://fantasy.premierleague.com/a/login',
        'app': 'plfpl-web'
    }

    # Perform login
    response = client.post(login_url, data=payload, headers=headers, follow_redirects=True)

    # Extract cookies
    cookies_dict = {c.name: c.value for c in client.cookies.jar}

    # Debugging
    print("🚨 Login Cookies:", cookies_dict)

    return {"status": "Login successful", "cookies": cookies_dict}


def getFPLTeamData(cookies, team_id):
    """
    Fetches the my-team data from FPL using stored session cookies.
    """
    url = f"https://fantasy.premierleague.com/api/my-team/{team_id}"

    # Manually set `pl_profile` if missing
    if "pl_profile" not in cookies:
        cookies["pl_profile"] = "PASTE_YOUR_PL_PROFILE_COOKIE_HERE"  # Manually extracted from browser

    csrf_token = cookies.get("csrftoken", "")
    session_id = cookies.get("sessionid", "")
    pl_profile = cookies.get("pl_profile", "")
    datadome = cookies.get("datadome", "")

    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8,la;q=0.7',
        'Referer': 'https://fantasy.premierleague.com/my-team/',
        'Sec-CH-UA': '"Chromium";v="132", "Google Chrome";v="132", "Not A(Brand";v="8"',
        'Sec-CH-UA-Mobile': '?0',
        'Sec-CH-UA-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=1, i',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
        'X-CSRFToken': csrf_token,
    }

    # Construct Cookie header manually
    cookie_header = f"sessionid={session_id}; csrftoken={csrf_token}; datadome={datadome}; pl_profile={pl_profile}"
    headers["Cookie"] = cookie_header  # ✅ Ensures `pl_profile` is sent

    session = requests.Session()
    session.cookies.update(cookies)

    response = session.get(url, headers=headers)

    print(f"🚨 Team Data Response Status: {response.status_code}")
    print("🚨 Response Headers:", response.headers)
    print("🚨 Response Text:", response.text)  # Debugging

    if response.status_code == 200:
        return response.json()

    return {"error": f"Failed to fetch team data. Status Code: {response.status_code}", "details": response.text}


# Get us the current gameweek number
def generateCurrentGameweek():
    todaysData = json.loads(json.dumps(requests.get('https://fantasy.premierleague.com/api/entry/1/').json()))
    for keys in todaysData:
        if keys == 'current_event':
            return todaysData[keys]


def get_players():
    gw = generateCurrentGameweek() if generateCurrentGameweek() != 0 else 1
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return []

    try:
        cursor = dbConnect.cursor(dictionary=True)
        query = f"SELECT id, team_code as team, CONCAT(first_name, ' ', second_name) AS full_name FROM {db}.bootstrapstatic_elements WHERE year_start = {season_start} AND gameweek = {gw}"
        logger.info(f"Executing query: {query}")
        cursor.execute(query)
        players = cursor.fetchall()
    except Error as e:
        logger.error(f"Error executing query: {e}")
        return []
    finally:
        dbConnect.close()  # Always close the database connection

    return players

def get_players_by_team():
    # Connect to the database
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)

    # Execute SQL query to get players and their respective teams
    cursor.execute(f'SELECT t.name AS "Team", p.team AS "team_id", p.code AS "code", p.first_name AS "First_name", p.second_name AS "Surname",  p.web_name AS "web_name",  p.team_code AS "team_code", p.id AS "ID" FROM {db}.bootstrapstatic_elements p JOIN {db}.bootstrapstatic_teams t ON p.team = t.id WHERE p.year_start = {season_start} AND t.year_start = {season_start}')

    # Fetch all results from the executed query
    players = cursor.fetchall()
    dbConnect.close()  # Close the database connection

    # Initialize the final dictionary
    teams_dict = {}

    # Process the data to create the desired structure
    for entry in players:
        team_name = entry['Team']
        full_name = f"{entry['First_name']} {entry['Surname']}"
        web_name = entry['web_name']
        player_id = entry['ID']
        team_id = entry['team_id']
        team_code = entry['team_code']
    
        if team_name not in teams_dict:
            teams_dict[team_name] = {}
    
        teams_dict[team_name][full_name] = {
            'full_name': full_name, 
            'web_name': web_name, 
            'id': player_id, 
            'team': team_id,
            'team_code': team_code
        }

    # Sort the dictionary by player names within each team
    for team in teams_dict:
        teams_dict[team] = dict(sorted(teams_dict[team].items()))

    return teams_dict

def get_players_by_position():
    # Connect to the database
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)

    positions = {
        1: 'Goalkeeper',
        2: 'Defender',
        3: 'Midfielder',
        4: 'Forward'
    }

    # Execute SQL query to get players and their respective teams
    cursor.execute(f'SELECT p.element_type AS "position_id", p.first_name AS "First_name", p.second_name AS "Surname", p.id AS "ID" FROM {db}.bootstrapstatic_elements p WHERE p.year_start = {season_start}')

    # Fetch all results from the executed query
    players = cursor.fetchall()
    dbConnect.close()  # Close the database connection

    # Initialize the final dictionary
    positions_dict = {}

    # Process the data to create the desired structure
    for entry in players:
        position_name = positions[entry['position_id']]
        full_name = f"{entry['First_name']} {entry['Surname']}"
        player_id = entry['ID']
        position_id = entry['position_id']
    
        if position_name not in positions_dict:
            positions_dict[position_name] = {}
    
        positions_dict[position_name][full_name] = {
            'full_name': full_name, 
            'id': player_id, 
            'position': position_id
        }

    # Sort the dictionary by player names within each position
    for position in positions_dict:
        positions_dict[position] = dict(sorted(positions_dict[position].items()))

    return positions_dict

def get_player_net_transfers(player_id):
    # Assuming you have a database connection utility called connect_db
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    query = f'SELECT id, (transfers_in_event - transfers_out_event) as net_transfers FROM {db}.bootstrapstatic_elements WHERE id = %s and year_start = {season_start};'
    cursor.execute(query, (player_id,))
    net_transfers = cursor.fetchone()
    dbConnect.close()  # Always close the database connection
    return net_transfers


def get_player_index_scores():
    dbConnect = connect_db()
    gameweek = generateCurrentGameweek()
    cursor = dbConnect.cursor(dictionary=True)
    
    query = f'''
    WITH min_max_values AS (
    SELECT 
        MIN((total_points / (now_cost / 10)) * (100 - selected_by_percent)) AS min_points_per_mill_per_perc_not_selected,
        MAX((total_points / (now_cost / 10)) * (100 - selected_by_percent)) AS max_points_per_mill_per_perc_not_selected
    FROM {db}.bootstrapstatic_elements
    WHERE year_start = 2024
      AND gameweek = {gameweek}
      AND element_type IN (1, 2, 3, 4)
      AND total_points > 0
    )

    -- Main query to get the players and the mean row
    SELECT * FROM (
        -- Select player data and normalize the player score
        SELECT CAST(id AS UNSIGNED) AS id, 
            web_name, 
            total_points, 
            (total_points / (now_cost / 10)) AS points_per_mill,  
            (100 - selected_by_percent) AS not_selected_by_perc, 
            ((total_points / (now_cost / 10)) * (100 - selected_by_percent)) AS points_per_mill_per_perc_not_selected,
            -- Normalized player score calculation
            (((total_points / (now_cost / 10)) * (100 - selected_by_percent) - min_max.min_points_per_mill_per_perc_not_selected) /
                (min_max.max_points_per_mill_per_perc_not_selected - min_max.min_points_per_mill_per_perc_not_selected)) * 100 AS player_score
        FROM {db}.bootstrapstatic_elements
        JOIN min_max_values AS min_max
        ON 1=1 -- Cartesian join to make min and max values available for every row
        WHERE year_start = 2024
        AND gameweek = {gameweek}
        AND element_type IN (1, 2, 3, 4)
        
        UNION ALL

        -- Select the mean values
        SELECT AVG(id) AS id,
            CAST('Mean' AS CHAR(255)) AS web_name,  
            AVG(total_points) AS total_points, 
            AVG(total_points / (now_cost / 10)) AS points_per_mill,  
            AVG(100 - selected_by_percent) AS not_selected_by_perc, 
            AVG((total_points / (now_cost / 10)) * (100 - selected_by_percent)) AS points_per_mill_per_perc_not_selected,
            50 AS player_score -- No player score for the mean row
        FROM {db}.bootstrapstatic_elements
        WHERE year_start = 2024
        AND gameweek = {gameweek}
        AND element_type IN (1, 2, 3, 4)
        AND (minutes / {gameweek}) > 45
    ) AS combined_results
    ORDER BY points_per_mill_per_perc_not_selected DESC;
    '''
    
    cursor.execute(query)
    players = cursor.fetchall()

    # Manually cast the 'id' to an integer if it's a Decimal
    for player in players:
        if player['id'] >= 0:
            player['id'] = int(player['id'])
        else:
            player['id'] = 0
            player['player_score'] = int(player['player_score'])

    dbConnect.close()  # Always close the database connection
    return players

def get_comparison_stats(id1, id2):
    gameweek = generateCurrentGameweek()
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    cursor.execute(f"SELECT total_points, bonus, points_per_game, value_season, starts, minutes, now_cost, selected_by_percent, ict_index FROM {db}.bootstrapstatic_elements WHERE id={id1} AND year_start={season_start} AND gameweek = {gameweek};")
    season_player1 = cursor.fetchone()

    cursor.execute(f"SELECT  transfers_in_event, transfers_out_event, chance_of_playing_next_round,  form, bps FROM {db}.bootstrapstatic_elements WHERE id={id1} AND year_start={season_start} AND gameweek = {gameweek};")
    form_player1 = cursor.fetchone()
        
    cursor.execute(f"SELECT  goals_scored, assists, clean_sheets, penalties_saved, yellow_cards, red_cards, saves FROM {db}.bootstrapstatic_elements WHERE id={id1} AND year_start={season_start} AND gameweek = {gameweek};")
    contribution_player1 = cursor.fetchone()

    cursor.execute(f"SELECT expected_goals, expected_assists, expected_goal_involvements FROM {db}.bootstrapstatic_elements WHERE id={id1} AND year_start={season_start} AND gameweek = {gameweek};")
    xG_player1 = cursor.fetchone()

    player1 = {
        'Season': season_player1,
        'Form': form_player1,
        'Contribution': contribution_player1,
        'xG': xG_player1,
            
    }

    cursor.execute(f"SELECT total_points, bonus, points_per_game, value_season, starts, minutes, now_cost, selected_by_percent, ict_index FROM {db}.bootstrapstatic_elements WHERE id={id2} AND year_start={season_start} AND gameweek = {gameweek};")
    season_player2 = cursor.fetchone()

    cursor.execute(f"SELECT  transfers_in_event, transfers_out_event, chance_of_playing_next_round,  form, bps FROM {db}.bootstrapstatic_elements WHERE id={id2} AND year_start={season_start} AND gameweek = {gameweek};")
    form_player2 = cursor.fetchone()
        
    cursor.execute(f"SELECT  goals_scored, assists, clean_sheets, penalties_saved, yellow_cards, red_cards, saves FROM {db}.bootstrapstatic_elements WHERE id={id2} AND year_start={season_start} AND gameweek = {gameweek};")
    contribution_player2 = cursor.fetchone()

    cursor.execute(f"SELECT expected_goals, expected_assists, expected_goal_involvements FROM {db}.bootstrapstatic_elements WHERE id={id2} AND year_start={season_start} AND gameweek = {gameweek};")
    xG_player2 = cursor.fetchone()

    player2 = {
        'Season': season_player2,
        'Form': form_player2,
        'Contribution': contribution_player2,
        'xG': xG_player2,
            
    }

    dbConnect.close()  # It's important to close the connection
    return [player1, player2]
   
def get_player_ownership():
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)

    currentGW = generateCurrentGameweek()
    if currentGW == None:
        currentGW = 1

    response = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
    if response.status_code != 200:
       logger.error(f"Failed to fetch data from FPL API. Status Code: {response.status_code}")
       return {"error": "Failed to fetch data from external API."}, 502
        
    playerData = response.json()['elements']
    playersNetTransfers = {}

    currentOwnership = dict()

    for player in playerData:
        currentOwnership[player['id']] = {'web_name': player['web_name'], 'selected': player['selected_by_percent']}

    try:
        query = (f'SELECT web_name, selected_by_percent, id FROM {db}.bootstrapstatic_elements WHERE year_start = {season_start} AND gameweek = {currentGW - 1} AND selected_by_percent >= 3 ORDER BY selected_by_percent DESC')
        cursor.execute(query)

        # Fetch all results from the executed query
        playersNow = cursor.fetchall()
    except:
        print(f"Issue running query on {db}: Query={query}")

    netOwnership = {p['id']: ((float(currentOwnership[p['id']]['selected']) - p['selected_by_percent'])/float(currentOwnership[p['id']]['selected'])) for p in playersNow}
    bottom5Relative = dict(sorted(netOwnership.items(), key=lambda item: item[1])[:5])
    top5Relative = dict(sorted(netOwnership.items(), key=lambda item: item[1], reverse=True)[:5])
    top10difference = {**top5Relative, **bottom5Relative}

    oldOwnership = {p['id']: p['selected_by_percent'] for p in playersNow if p['id'] in list(top10difference.keys())}


    labels = list()
    oldValues = list()
    newValues = list()
    ids = list()

    for player in top10difference:
        labels.append(currentOwnership[player]['web_name'])
        oldValues.append(oldOwnership[player])
        ids.append(player)
        if currentGW >= 1:
            currentPlayer = currentOwnership[player]
            newValues.append(float(currentPlayer['selected']))
        else:
            newValues.append(0)
    
    ownership = {
        'labels': labels,
        'oldValues': oldValues,
        'newValues': newValues,
        'ids': ids
        }

    dbConnect.close()  # Close the database connection

    return ownership

# For Net Transfers In
def get_top_10_net_transfers_in():
    playerData = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/').json()['elements']
    playersNetTransfers = {}
    idToName = dict()

    for player in playerData:
        netTransfersIn = player['transfers_in_event'] - player['transfers_out_event']
        playersNetTransfers[player['id']] = netTransfersIn
        idToName[player['id']] = player['web_name'] 

    sorted_net_transfers_in = sorted(playersNetTransfers.items(), key=lambda item: item[1], reverse=True)[:10]

    data = {
        'labels': [idToName[item[0]] for item in sorted_net_transfers_in],
        'values': [item[1] for item in sorted_net_transfers_in],
        'ids': [item[0] for item in sorted_net_transfers_in]
    }

    return data

def get_top_10_net_transfers_out():
    playerData = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/').json()['elements']
    playersNetTransfersOut = {}
    idToName = dict()

    # Calculate net transfers out for each player
    for player in playerData:
        netTransfersOut = player['transfers_out_event'] - player['transfers_in_event']
        playersNetTransfersOut[player['id']] = netTransfersOut  # Store as negative value
        idToName[player['id']] = player['web_name'] 

    # Sort the dictionary by values in descending order and pick the top 10
    sorted_net_transfers_out = sorted(playersNetTransfersOut.items(), key=lambda item: item[1], reverse=True)[:10]

    # Prepare the data in the required format
    data = {
        'labels': [idToName[item[0]] for item in sorted_net_transfers_out],
        'values': [item[1] for item in sorted_net_transfers_out],
        'ids': [item[0] for item in sorted_net_transfers_out]
    }

    return data


def next_5_gameweeks(player_id):

    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    gw = generateCurrentGameweek()
    
    # Always ensure you fetch all results or close the cursor before executing another query
    query = f'SELECT id, short_name, code FROM {db}.bootstrapstatic_teams where year_start = {season_start};'
    cursor.execute(query)
    teams = cursor.fetchall()  # Fetch all team information

    team_id_to_code = dict()
    
    for team in teams:
        team_id_to_code[team['id']] = team['code']

    query = f'SELECT t.name as "team", t.short_name as "team_short", p.team AS "team_id", CONCAT(p.first_name, " ", p.second_name) AS "Full_name", p.id AS "ID" FROM {db}.bootstrapstatic_elements p JOIN {db}.bootstrapstatic_teams t ON p.team = t.id WHERE p.year_start = {season_start} AND t.year_start = {season_start} and p.id={player_id} and gameweek={gw};'
    cursor.execute(query)
    player_info = cursor.fetchone()

    i = gw + 1

    fixtures = list()

    while i < gw + 6:
        team_id = player_info['team_id']
        query = f'''
            SELECT DISTINCT
                es_f.team_h AS "team_h",
                es_f.team_a AS "team_a",
                f_f.team_h_difficulty AS "team_h_difficulty", 
                f_f.team_a_difficulty AS "team_a_difficulty",
                es_f.event AS "gameweek"
            FROM {db}.elementsummary_fixtures es_f 
            JOIN {db}.fixtures_fixtures f_f ON es_f.code = f_f.code 
            WHERE 
                f_f.year_start = {season_start} 
                AND es_f.year_start = {season_start} 
                AND es_f.event = {i}
                AND (es_f.team_a = {team_id} OR es_f.team_h = {team_id});
        '''

        cursor.execute(query)
        fixtures_in_gw = cursor.fetchall()  # <-- Now fetching all fixtures, not just one

        if not fixtures_in_gw:
            fixtures.append({
                'teamName': '-',
                'difficulty': "None",
                'shirtImage': player_shirts['Unknown'],
                'homeOrAway': 'Blank',
                'gameweek': i
            })
            i += 1
            continue

        for fixture_info in fixtures_in_gw:
            if fixture_info['team_a'] == team_id:
                venue = 'Away'
                opponent_id = fixture_info['team_h']
                opponent = next(t['short_name'] for t in teams if t['id'] == opponent_id)
            else:
                venue = 'Home'
                opponent_id = fixture_info['team_a']
                opponent = next(t['short_name'] for t in teams if t['id'] == opponent_id)

            opponent_code = team_id_to_code[opponent_id]
            difficulty = fixture_info['team_a_difficulty'] if venue == 'Away' else fixture_info['team_h_difficulty']

            fixtures.append({
                'teamName': opponent,
                'difficulty': difficulty,
                'shirtImage': player_shirts[opponent_code],
                'homeOrAway': venue,
                'gameweek': i
            })

        i += 1             

    cursor.close()  # Close the cursor after using it
    dbConnect.close()  # Close the database connection

    return fixtures

def get_teams(player_id):
    # Connect to the database
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)

    # Execute SQL query to get players and their respective teams
    cursor.execute(f'SELECT t.name AS "Team", t.code AS "Team_code" FROM {db}.bootstrapstatic_elements p JOIN {db}.bootstrapstatic_teams t ON p.team = t.id WHERE p.year_start = {season_start} AND t.year_start = {season_start} and p.id = {player_id} and gameweek = {generateCurrentGameweek()}')

    # Fetch all results from the executed query
    teams = cursor.fetchall()
    dbConnect.close()  # Close the database connection

    return teams

def top_5_players_last_5_weeks():
    """
    Returns JSON/dict data for the top 5 players in each position
    over the last 5 weeks, plus weekly average scores per position.
    Includes:
       - 0 points for missing GWs
       - Current team from bootstrapstatic_elements for that year_start
    """
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database in top_5_players_last_5_weeks().")
        return {}

    cursor = dbConnect.cursor(dictionary=True)

    # Example: if the current gameweek is 19, last 5 GWs are 15..19
    current_gw = generateCurrentGameweek()
    start_gw = current_gw - 4  # 15
    end_gw = current_gw        # 19

    # Positions: 1=GK, 2=DEF, 3=MID, 4=FWD
    position_map = {
        1: "goalkeepers",
        2: "defenders",
        3: "midfielders",
        4: "forwards"
    }

    # Prepare the final structure
    result = {
        "goalkeepers":  {"averageScores": [], "players": []},
        "defenders":    {"averageScores": [], "players": []},
        "midfielders":  {"averageScores": [], "players": []},
        "forwards":     {"averageScores": [], "players": []},
    }

    gws_list = list(range(start_gw, end_gw + 1))  # [15,16,17,18,19]

    try:
        # --------------------------------------------------------------------------------------
        # 1) QUERY the last 5 GWs from elementsummary_history (h) joined with:
        #       elementsummary_fixtures (f) for fixture difficulty
        #       bootstrapstatic_elements (e) for the correct year_start/team info
        #       bootstrapstatic_teams (t) for the team name
        #
        #    The important part is ensuring e.year_start = h.year_start and e.gameweek = h.round
        #
        #    Adjust if your schema differs (e.g. if e.gameweek isn’t a column).
        # --------------------------------------------------------------------------------------
        query = f"""
            SELECT 
                h.element        AS player_id,
                h.round          AS gw,
                h.total_points   AS points,
                f.difficulty     AS fixture_difficulty,

                -- subqueries
                (
                SELECT e2.web_name
                FROM {db}.bootstrapstatic_elements e2
                WHERE e2.id = h.element
                    AND e2.year_start = h.year_start
                ORDER BY ABS(e2.gameweek - h.round)
                LIMIT 1
                ) AS player_name,

                (
                SELECT e2.element_type
                FROM {db}.bootstrapstatic_elements e2
                WHERE e2.id = h.element
                    AND e2.year_start = h.year_start
                ORDER BY ABS(e2.gameweek - h.round)
                LIMIT 1
                ) AS position_id,

                (
                SELECT t.name
                FROM {db}.bootstrapstatic_elements e2
                JOIN {db}.bootstrapstatic_teams t 
                    ON t.id = e2.team
                AND t.year_start = e2.year_start
                WHERE e2.id = h.element
                    AND e2.year_start = h.year_start
                ORDER BY ABS(e2.gameweek - h.round)
                LIMIT 1
                ) AS team_name

            FROM {db}.elementsummary_history h
            JOIN {db}.elementsummary_fixtures f
                ON h.fixture = f.id
            AND f.year_start = h.year_start
            WHERE h.year_start = {season_start}
            AND h.round BETWEEN {start_gw} AND {end_gw}
            AND h.minutes > 15
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # We'll store data in nested dictionaries
        from collections import defaultdict

        # data_by_position[pos][pid] = {
        #     'player_name': str,
        #     'team_name': str,
        #     'gw_points': { gw_number: points },
        #     'gw_difficulty': { gw_number: difficulty }
        # }
        data_by_position = {
            1: defaultdict(lambda: {
                "player_name": "",
                "team_name": "",
                "gw_points": defaultdict(int),
                "gw_difficulty": defaultdict(lambda: 3)  # default difficulty = 3
            }),
            2: defaultdict(lambda: {
                "player_name": "",
                "team_name": "",
                "gw_points": defaultdict(int),
                "gw_difficulty": defaultdict(lambda: 3)
            }),
            3: defaultdict(lambda: {
                "player_name": "",
                "team_name": "",
                "gw_points": defaultdict(int),
                "gw_difficulty": defaultdict(lambda: 3)
            }),
            4: defaultdict(lambda: {
                "player_name": "",
                "team_name": "",
                "gw_points": defaultdict(int),
                "gw_difficulty": defaultdict(lambda: 3)
            }),
        }

        # Also track sum of points for top-5 selection
        sum_points_by_position = {
            1: defaultdict(int),
            2: defaultdict(int),
            3: defaultdict(int),
            4: defaultdict(int)
        }

        # Also track weekly sums & counts for averageScores
        weekly_position_sums = {
            1: defaultdict(int),
            2: defaultdict(int),
            3: defaultdict(int),
            4: defaultdict(int)
        }
        weekly_position_count = {
            1: defaultdict(int),
            2: defaultdict(int),
            3: defaultdict(int),
            4: defaultdict(int)
        }

        for row in rows:
            pos_id = row["position_id"]
            pid = row["player_id"]
            gw = row["gw"]
            pts = row["points"]
            difficulty = row["fixture_difficulty"] if row["fixture_difficulty"] else 3

            # Fill the dictionaries
            p_data = data_by_position[pos_id][pid]
            p_data["player_name"] = row["player_name"]
            p_data["team_name"]   = row["team_name"]
            p_data["gw_points"][gw] = pts
            p_data["gw_difficulty"][gw] = difficulty

            # Add to sum (for top 5)
            sum_points_by_position[pos_id][pid] += pts

            # Add to weekly sums for average
            weekly_position_sums[pos_id][gw]   += pts
            weekly_position_count[pos_id][gw]  += 1

        # --------------------------------------------------------------------------------------
        # 2) Compute the average scores (for each position, per GW),
        #    then store them in result[posName]["averageScores"] as an ordered list
        # --------------------------------------------------------------------------------------
        for pos_id, pos_name in position_map.items():
            # Build an array of average scores in the order of gw 15..19
            avg_scores = []
            for gw in gws_list:
                total_pts_this_gw = weekly_position_sums[pos_id][gw]
                num_players_this_gw = weekly_position_count[pos_id][gw]
                if num_players_this_gw > 0:
                    avg_pts = round(total_pts_this_gw / num_players_this_gw, 2)
                else:
                    avg_pts = 0
                avg_scores.append(avg_pts)

            result[pos_name]["averageScores"] = avg_scores

        # --------------------------------------------------------------------------------------
        # 3) Identify top 5 players in each position by total points
        #    Then build the "players" list in the final JSON
        # --------------------------------------------------------------------------------------
        for pos_id, pos_name in position_map.items():
            sorted_by_sum = sorted(
                sum_points_by_position[pos_id].items(),
                key=lambda x: x[1],
                reverse=True
            )
            top_5_ids = [player_id for player_id, _ in sorted_by_sum[:5]]

            players_list = []
            for pid in top_5_ids:
                p_data = data_by_position[pos_id][pid]

                # Weeks array in ascending order
                # We'll “force” a 0 if the player didn’t appear that gw
                # and difficulty default is 3 if none available
                weeks_sorted = []
                scores_sorted = []
                difficulty_sorted = []
                for gw in gws_list:
                    weeks_sorted.append(gw)
                    scores_sorted.append(p_data["gw_points"][gw]) 
                    difficulty_sorted.append(p_data["gw_difficulty"][gw])

                # Add to players list
                players_list.append({
                    "name": p_data["player_name"],
                    "club": p_data["team_name"],
                    "weeks": weeks_sorted,         # e.g. [15, 16, 17, 18, 19]
                    "scores": scores_sorted,       # e.g. [0, 12, 8, 0, 9]
                    "difficulty": difficulty_sorted
                })

            result[pos_name]["players"] = players_list

    except Exception as e:
        logger.exception(f"Error in top_5_players_last_5_weeks: {str(e)}")
        return {}
    finally:
        cursor.close()
        dbConnect.close()

    return result

def fetch_player_summary(player_id):
    try:
        logger.info(f"Request for player_summary with player_id: {player_id}")
        
        # Validate player_id
        try:
            player_id = int(player_id)
        except ValueError:
            logger.error(f"Invalid player_id provided: {player_id}")
            return {"error": "Invalid player ID provided."}, 400

        # Fetch data from FPL API
        response = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
        if response.status_code != 200:
            logger.error(f"Failed to fetch data from FPL API. Status Code: {response.status_code}")
            return {"error": "Failed to fetch data from external API."}, 502

        data = response.json()
        elements = data.get('elements', [])
        teams = data.get('teams', [])

        # Find the player in elements
        player = next((p for p in elements if p['id'] == player_id), None)
        if not player:
            logger.warning(f"Player with ID {player_id} not found in FPL data.")
            return {"error": "Player not found."}, 404

        position = player['element_type']

        element_types = {
            1: 'Goalkeeper',
            2: 'Defender',
            3: 'Midfielder',
            4: 'Forward'
        }

        # Fetch suspension data for the player
        suspensions = fetch_suspension_data()
        suspension_data = next((s for s in suspensions if s['player_id'] == player_id), None)

        # Process suspension data
        if suspension_data:
            yellow_cards = suspension_data['total_yellow_cards']
            yellows_left = suspension_data['yellow_cards_needed']
            suspension_length = suspension_data['suspension_length']
            suspension_end = suspension_data['suspension_end_gameweek']
            card_image_path = f'/static/content/referee-cards/{min(yellow_cards, 5)}-yellow.png' if yellow_cards < 5 else '/static/content/referee-cards/5-plus-yellow.png'
        else:
            yellow_cards = 0
            yellows_left = 0
            suspension_length = 0
            suspension_end = None
            card_image_path = '/static/content/referee-cards/0-yellow.png'

        # Calculate averages
        valid_players = [p for p in elements if p['minutes'] > 0 and p['element_type'] == position]
        if not valid_players:
            logger.warning(f"No valid players with minutes found.")
            return {"error": "No valid player data found."}, 500

        average_goals = round(sum(p['goals_scored'] for p in valid_players) / len(valid_players), 2)
        average_assists = round(sum(p['assists'] for p in valid_players) / len(valid_players), 2)
        average_form = round(sum(float(p['form']) for p in valid_players) / len(valid_players), 2)
        average_points = round(sum(float(p['total_points']) for p in valid_players) / len(valid_players), 2)
        average_influence = round(sum(float(p['influence']) for p in valid_players) / len(valid_players), 2)
        average_creativity = round(sum(float(p['creativity']) for p in valid_players) / len(valid_players), 2)
        average_threat = round(sum(float(p['threat']) for p in valid_players) / len(valid_players), 2)
        average_ep_next = round(sum(float(p['ep_next']) for p in valid_players) / len(valid_players), 2)
        average_minutes = round(sum(float(p['minutes']) for p in valid_players) / len(valid_players)/generateCurrentGameweek(), 0)

        # Get team info
        team = next((t for t in teams if t['code'] == player['team_code']), None)
        if not team:
            logger.warning(f"Team for player ID {player_id} not found.")
            team_name = "Unknown"
            shirt_image = '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg'
        else:
            team_name = team['name']
            shirt_image = player_shirts[team['code']]

        # Create player summary
        player_summary = {
            'id': player_id,
            'name': player['web_name'],
            'value': float(player['now_cost'] / 10),
            'minutes': round(player['minutes']/generateCurrentGameweek(), 2),
            'chance_of_playing': player['chance_of_playing_next_round'],
            'news': player['news'],
            'position': position,
            'position_name': element_types[position],
            'team_name': team_name,
            'shirtImage': shirt_image,
            'metrics': [
                {'title': 'Goals', 'value': player['goals_scored'], 'averageValue': average_goals},
                {'title': 'Assists', 'value': player['assists'], 'averageValue': average_assists},
                {'title': 'Form', 'value': float(player['form']), 'averageValue': average_form},

                {'title': 'Influence', 'value': player['influence'], 'averageValue': average_influence},
                {'title': 'Creativity', 'value': player['creativity'], 'averageValue': average_creativity},
                {'title': 'Threat', 'value': player['threat'], 'averageValue': average_threat},
                
                {'title': 'Est. points next game', 'value': player['ep_next'], 'averageValue': average_ep_next},
                {'title': 'Points', 'value': player['total_points'], 'averageValue': average_points},
                {'title': 'Avg. mins', 'value': round(player['minutes']/generateCurrentGameweek(), 0), 'averageValue': average_minutes},
            ],
            'suspension': {
                'total_yellow_cards': yellow_cards,
                'yellow_cards_needed': yellows_left,
                'card_image': card_image_path,
                'suspension_length': suspension_length,
                'suspension_end_gameweek': suspension_end
            }
        }

        logger.info(f"Successfully retrieved summary for player ID {player_id}")
        return player_summary, 200

    except Exception as e:
        logger.exception(f"An unexpected error occurred while processing player ID {player_id}: {str(e)}")
        return {"error": "An unexpected error occurred."}, 500


def get_alternative_players(player_id):
    player = fetch_player_summary(player_id)[0]

    # Connect to the database
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)

    currentGW = generateCurrentGameweek() - 1

    costLow = (player['value'] - 1) * 10
    costHigh = (player['value'] + 1) * 10
    position = player['position']

    query = f'SELECT id, team, team_code, web_name, total_points, now_cost, form FROM {db}.bootstrapstatic_elements where element_type = {position} and now_cost BETWEEN {costLow} and {costHigh} and year_start = {season_start} and gameweek = {currentGW}  and id <> {player_id} ORDER BY form DESC LIMIT 6'

    cursor.execute(query)

    players = cursor.fetchall()

    if len(players) == 0:
        
            currentGWAlternate = currentGW - 1

            query = f'SELECT id, team, team_code, web_name, total_points, now_cost, form FROM {db}.bootstrapstatic_elements where element_type = {position} and now_cost BETWEEN {costLow} and {costHigh} and year_start = {season_start} and gameweek = {currentGWAlternate}  and id <> {player_id} ORDER BY form DESC LIMIT 6'

            cursor.execute(query)

            players = cursor.fetchall()


    for player in players:
        player['shirt'] = player_shirts[player['team_code']]
        player['team_name'] = get_teams(player['id'])[0]['Team']

    if not players:
        return "No players within 1m of this player"

    else:
        return players
    
def fetch_suspension_data():
    """
    Fetch suspension data for players based on yellow card rules and current gameweek.
    """
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return []

    current_gameweek = generateCurrentGameweek()
    if current_gameweek is None:
        logger.error("Failed to fetch the current gameweek.")
        return []

    try:
        query = f"""
        WITH DeduplicatedHistory AS (
            SELECT 
                esh.element AS player_id,
                esh.round,
                SUM(esh.yellow_cards) AS yellow_cards
            FROM {db}.elementsummary_history esh
            WHERE esh.year_start = {season_start} -- Filter to the current season
            GROUP BY esh.element, esh.round
        ),
        TotalYellowCards AS (
            SELECT 
                dh.player_id,
                SUM(dh.yellow_cards) AS total_yellow_cards
            FROM DeduplicatedHistory dh
            GROUP BY dh.player_id
        ),
        UniquePlayers AS (
            SELECT DISTINCT
                p.id AS player_id,
                CONCAT(p.first_name, ' ', p.second_name) AS player_name
            FROM {db}.bootstrapstatic_elements p
            WHERE p.year_start = {season_start} -- Ensure filtering matches the season
        )
        SELECT 
            tp.player_id,
            up.player_name,
            tp.total_yellow_cards,
            CASE
                WHEN tp.total_yellow_cards < 5 AND {current_gameweek} <= 19 THEN 5 - tp.total_yellow_cards
                WHEN tp.total_yellow_cards < 10 AND {current_gameweek} <= 32 THEN 10 - tp.total_yellow_cards
                WHEN tp.total_yellow_cards < 15 THEN 15 - tp.total_yellow_cards
                ELSE 0
            END AS yellow_cards_needed,
            CASE
                WHEN tp.total_yellow_cards <= 4 AND {current_gameweek} <= 19 THEN 1
                WHEN tp.total_yellow_cards BETWEEN 5 AND 10 AND {current_gameweek} <= 32 THEN 2
                WHEN tp.total_yellow_cards >= 15 THEN 3
                ELSE 0
            END AS suspension_length,
            CASE
                WHEN tp.total_yellow_cards <= 4 AND {current_gameweek} <= 19 THEN {current_gameweek} + 1
                WHEN tp.total_yellow_cards BETWEEN 5 AND 10 AND {current_gameweek} <= 32 THEN {current_gameweek} + 2
                WHEN tp.total_yellow_cards >= 15 THEN {current_gameweek} + 3
                ELSE NULL
            END AS suspension_end_gameweek
        FROM TotalYellowCards tp
        JOIN UniquePlayers up 
            ON tp.player_id = up.player_id
        ORDER BY 
            player_id ASC,
            yellow_cards_needed ASC,
            total_yellow_cards DESC;
        """
        
        cursor = dbConnect.cursor(dictionary=True)
        logger.info(f"Executing query: {query}")
        cursor.execute(query)
        results = cursor.fetchall()
        
        return results

    except Error as e:
        logger.error(f"Error executing query: {e}")
        return []
    finally:
        dbConnect.close()

# Example usage
if __name__ == "__main__":
    suspensions = fetch_suspension_data()
    if suspensions:
        for suspension in suspensions:
            print(suspension)
    else:
        print("No suspension data found.")
