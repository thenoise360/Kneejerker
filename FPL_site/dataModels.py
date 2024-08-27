import mysql.connector
from mysql.connector import Error
from FPL_site.config import current_config
from FPL_site.genericMethods import unicodeReplace
import requests
import json
import logging

player_shirts = {
        1: '/static/content/Tshirts/sleeves-red-white-football-shirt-svgrepo-com.svg', # Arsenal
        2: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', # Aston Villa
        3: '/static/content/Tshirts/stripes-red-black-football-shirt-svgrepo-com.svg', # Bournemouth
        4: '/static/content/Tshirts/stripes-white-red-football-shirt-svgrepo-com.svg', # Brentford
        5: '/static/content/Tshirts/stripes-white-blue-football-shirt-svgrepo-com.svg', # Brighton
        99: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', # Burnley
        6: '/static/content/Tshirts/plain-blue-football-shirt-svgrepo-com.svg', # Chelsea
        7: '/static/content/Tshirts/halves-red-blue-football-shirt-svgrepo-com.svg', # Crystal Palace
        8: '/static/content/Tshirts/plain-navy-football-shirt-svgrepo-com.svg', # Everton
        9: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', # Fulham
        10: '/static/content/Tshirts/sleeves-blue-white-football-shirt-svgrepo-com.svg', # Ipswich Town
        99: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', # Leeds
        11: '/static/content/Tshirts/plain-navy-football-shirt-svgrepo-com.svg', # Leicester
        12: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', # Liverpool
        99: '/static/content/Tshirts/vertical-orange-black-football-shirt-svgrepo-com.svg', # Luton
        13: '/static/content/Tshirts/plain-skyblue-football-shirt-svgrepo-com.svg', # Man City
        14: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', # Man Utd
        15: '/static/content/Tshirts/stripes-white-black-football-shirt-svgrepo-com.svg', # Newcastle
        16: '/static/content/Tshirts/plain-red-football-shirt-svgrepo-com.svg', # Nottingham Forest
        99: '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg', # Sheffield Utd
        17: '/static/content/Tshirts/sash-white-red-football-shirt-svgrepo-com.svg', # Southampton
        18: '/static/content/Tshirts/plain-white-football-shirt-svgrepo-com.svg', # Spurs
        19: '/static/content/Tshirts/sleeves-maroon-skyblue-football-shirt-svgrepo-com.svg', # West Ham
        20: '/static/content/Tshirts/plain-orange-football-shirt-svgrepo-com.svg', # Wolves
        1000: '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg', # Default for unknown teams
};

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

# Get us the current gameweek number
def generateCurrentGameweek():
    todaysData = json.loads(json.dumps(requests.get('https://fantasy.premierleague.com/api/entry/1/').json()))
    for keys in todaysData:
        if keys == 'current_event':
            return todaysData[keys]


def get_players():
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return []

    try:
        cursor = dbConnect.cursor(dictionary=True)
        query = f"SELECT id, team, CONCAT(first_name, ' ', second_name) AS full_name FROM {db}.bootstrapstatic_elements WHERE year_start = {season_start}"
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
    cursor.execute(f'SELECT t.name AS "Team", p.team AS "team_id", p.first_name AS "First_name", p.second_name AS "Surname", p.id AS "ID" FROM {db}.bootstrapstatic_elements p JOIN {db}.bootstrapstatic_teams t ON p.team = t.id WHERE p.year_start = {season_start} AND t.year_start = {season_start}')

    # Fetch all results from the executed query
    players = cursor.fetchall()
    dbConnect.close()  # Close the database connection

    # Initialize the final dictionary
    teams_dict = {}

    # Process the data to create the desired structure
    for entry in players:
        team_name = entry['Team']
        full_name = f"{entry['First_name']} {entry['Surname']}"
        player_id = entry['ID']
        team_id = entry['team_id']
    
        if team_name not in teams_dict:
            teams_dict[team_name] = {}
    
        teams_dict[team_name][full_name] = {
            'full_name': full_name, 
            'id': player_id, 
            'team': team_id
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
    cursor = dbConnect.cursor(dictionary=True)
    query = f'''
    WITH PlayerTeam AS (SELECT id, team_code FROM {db}.bootstrapstatic_elements), 
    FixtureDifficulties AS (
        SELECT f.event, f.team_h, f.team_a, f.team_h_difficulty, f.team_a_difficulty, f.team_h AS team_code, f.team_h_difficulty AS team_difficulty 
        FROM {db}.fixtures_fixtures f WHERE f.year_start = {season_start}
        UNION ALL 
        SELECT f.event, f.team_h, f.team_a, f.team_h_difficulty, f.team_a_difficulty, f.team_a AS team_code, f.team_a_difficulty AS team_difficulty 
        FROM {db}.fixtures_fixtures f WHERE f.year_start = {season_start}
    ), 
    TeamIctIndexSum AS (
        SELECT bs.team_code, SUM(e.ict_index) AS team_ict_index_sum 
        FROM {db}.events_elements e 
        JOIN {db}.bootstrapstatic_elements bs ON e.id = bs.id 
        WHERE e.Gameweek IN (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30) AND e.year_start = {season_start}
        GROUP BY bs.team_code
    ), 
    PlayerIctIndexSum AS (
        SELECT e.id, SUM(e.ict_index) AS player_ict_index_sum 
        FROM {db}.events_elements e 
        WHERE e.Gameweek IN (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30) AND e.year_start = {season_start}
        GROUP BY e.id
    ), 
    RawIndexes AS (
        SELECT e.id, bs.team_code, 
            ((e.goals_scored + e.assists - e.expected_goal_involvements + 1) * 
            (SUM(e.expected_goals_conceded - e.goals_conceded + 1)) * 
            SUM(e.total_points) * 
            COALESCE(SUM(fd.team_difficulty), 0) * 
            (pis.player_ict_index_sum / tis.team_ict_index_sum) * 100) AS debug_score, 
            ((e.goals_scored + e.assists) - e.expected_goal_involvements + 1) AS sum_expected_involvement_achieved_during_period, 
            SUM(e.expected_goals_conceded - e.goals_conceded + 1) AS sum_expected_goals_conceded_achieved_during_period, 
            SUM(e.total_points) AS total_points, 
            COALESCE(SUM(fd.team_difficulty), 0) AS total_team_difficulty, 
            (pis.player_ict_index_sum / tis.team_ict_index_sum) * 100 AS player_contribution_percentage 
        FROM {db}.events_elements e 
        JOIN {db}.bootstrapstatic_elements bs ON e.id = bs.id 
        LEFT JOIN FixtureDifficulties fd ON e.Gameweek = fd.event AND bs.team_code = fd.team_code 
        JOIN TeamIctIndexSum tis ON bs.team_code = tis.team_code 
        JOIN PlayerIctIndexSum pis ON e.id = pis.id 
        WHERE e.Gameweek IN (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30) 
        GROUP BY e.id, bs.team_code, pis.player_ict_index_sum, tis.team_ict_index_sum 
        HAVING player_contribution_percentage IS NOT NULL
    ), 
    MinMaxScore AS (
        SELECT MIN(ri.debug_score) AS min_debug_score, MAX(ri.debug_score) AS max_debug_score 
        FROM RawIndexes ri
    ) 
    SELECT ri.id, 
        CASE WHEN mm.max_debug_score = mm.min_debug_score THEN 0 
        ELSE ((ri.debug_score - mm.min_debug_score) / (mm.max_debug_score - mm.min_debug_score)) * 100 END AS "index", 
        ri.sum_expected_involvement_achieved_during_period, 
        ri.sum_expected_goals_conceded_achieved_during_period, 
        ri.total_points, 
        ri.total_team_difficulty, 
        ri.player_contribution_percentage, 
        ri.debug_score 
    FROM RawIndexes ri, MinMaxScore mm 
    WHERE ri.player_contribution_percentage IS NOT NULL 
    UNION ALL 
    SELECT e.id, 0 AS "index", 
        NULL AS sum_expected_involvement_achieved_during_period, 
        NULL AS sum_expected_goals_conceded_achieved_during_period, 
        NULL AS total_points, 
        NULL AS total_team_difficulty, 
        NULL AS player_contribution_percentage, 
        NULL AS debug_score 
    FROM {db}.events_elements e 
    WHERE e.id NOT IN (SELECT ri.id FROM RawIndexes ri);
    '''

    cursor.execute(query)
    players = cursor.fetchall()
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

    print(f"Current Ownership: {currentOwnership}")

    # Execute SQL query to get players and their respective teams
    try:
        query = f'''
        SELECT web_name, selected_by_percent, id
        FROM {db}.bootstrapstatic_elements 
        WHERE year_start = {season_start} AND gameweek = {currentGW - 1} AND selected_by_percent >= 3
        ORDER BY 
	        selected_by_percent 
        DESC 
        '''
        cursor.execute(query)

        # Fetch all results from the executed query
        playersNow = cursor.fetchall()
    except:
        print(f"Issue running query on {db}: Query={query}")

    print(f"PlayersNow: {playersNow}")


    netOwnership = {p['id']: ((float(currentOwnership[p['id']]['selected']) - p['selected_by_percent'])/float(currentOwnership[p['id']]['selected'])) for p in playersNow}
    print(f"Net Ownership: {netOwnership}")
    
    bottom5Relative = dict(sorted(netOwnership.items(), key=lambda item: item[1])[:5])
    print(f"Bottom 5 Ownership: {bottom5Relative}")
    
    top5Relative = dict(sorted(netOwnership.items(), key=lambda item: item[1], reverse=True)[:5])
    print(f"Top 5 Ownership: {top5Relative}")

    top10difference = {**top5Relative, **bottom5Relative}
    print(f"Top 10 Difference: {top10difference}")

    oldOwnership = {p['id']: p['selected_by_percent'] for p in playersNow if p['id'] in list(top10difference.keys())}
    print(f"Old Ownership: {oldOwnership}")


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


def next_5_fixtures(player_id):

    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)

    query = f'SELECT t.name as "team", t.short_name as "team_short", p.team AS "team_id", CONCAT(p.first_name, " ", p.second_name) AS "Full_name", p.id AS "ID" FROM {db}.bootstrapstatic_elements p JOIN {db}.bootstrapstatic_teams t ON p.team = t.id WHERE p.year_start = {season_start} AND t.year_start = {season_start} and p.id={player_id};'
    cursor.execute(query)
    player_info = cursor.fetchone()

    # Always ensure you fetch all results or close the cursor before executing another query
    query = f'SELECT id, short_name FROM {db}.bootstrapstatic_teams where year_start = {season_start};'
    cursor.execute(query)
    teams = cursor.fetchall()  # Fetch all team information

    gw = generateCurrentGameweek()
    i = gw + 1

    fixtures = list()

    while i < gw + 6:
        fixture = dict()
        team_id = player_info['team_id']
        query = f'SELECT team_a, team_h, team_a_difficulty, team_h_difficulty FROM {db}.fixtures_fixtures WHERE year_start = {season_start} AND (team_h={team_id} OR team_a={team_id}) AND event = {i};'
        cursor.execute(query)
        difficulty_info = cursor.fetchone()  # Fetch the difficulty info for the current fixture

        # Process the result
        if difficulty_info['team_a'] == player_info['team_id']:
            venue = 'Away'
            opponent = next(team['short_name'] for team in teams if team['id'] == difficulty_info['team_h'])
            opponent_id = difficulty_info['team_h']
        elif difficulty_info['team_h'] == player_info['team_id']:
            venue = 'Home'
            opponent = next(team['short_name'] for team in teams if team['id'] == difficulty_info['team_a'])
            opponent_id = difficulty_info['team_a']
        else:
            venue = 'blank'
            opponent = '-'
            opponent_id = 1000


        if venue == 'Away':
            difficulty = difficulty_info['team_a_difficulty']
        elif venue == 'Home':
            difficulty = difficulty_info['team_h_difficulty']
        else: 
            difficulty = "None"

        fixture = {
            'teamName': opponent, 
            'difficulty': difficulty, 
            'shirtImage': player_shirts[opponent_id], 
            'homeOrAway': venue}
        fixtures.append(fixture)
        i += 1                 

    cursor.close()  # Close the cursor after using it
    dbConnect.close()  # Close the database connection

    return fixtures

def get_teams(player_id):
    # Connect to the database
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)

    # Execute SQL query to get players and their respective teams
    cursor.execute(f'SELECT t.name AS "Team" FROM {db}.bootstrapstatic_elements p JOIN {db}.bootstrapstatic_teams t ON p.team = t.id WHERE p.year_start = {season_start} AND t.year_start = {season_start} and p.id = {player_id}')

    # Fetch all results from the executed query
    teams = cursor.fetchall()
    dbConnect.close()  # Close the database connection

    return teams

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

        # Calculate averages
        valid_players = [p for p in elements if p['minutes'] > 0 and p['element_type'] == position]
        if not valid_players:
            logger.warning(f"No valid players with minutes found.")
            return {"error": "No valid player data found."}, 500

        average_goals = round(sum(p['goals_scored'] for p in valid_players) / len(valid_players), 2)
        average_assists = round(sum(p['assists'] for p in valid_players) / len(valid_players), 2)
        average_form = round(sum(float(p['form']) for p in valid_players) / len(valid_players), 2)
        average_influence = round(sum(float(p['influence']) for p in valid_players) / len(valid_players), 2)
        average_creativity = round(sum(float(p['creativity']) for p in valid_players) / len(valid_players), 2)
        average_threat = round(sum(float(p['threat']) for p in valid_players) / len(valid_players), 2)
        average_ep_next = round(sum(float(p['ep_next']) for p in valid_players) / len(valid_players), 2)

        # Get team info
        team = next((t for t in teams if t['id'] == player['team']), None)
        if not team:
            logger.warning(f"Team for player ID {player_id} not found.")
            team_name = "Unknown"
            shirt_image = '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg'
        else:
            team_name = team['name']
            shirt_image = player_shirts[team['id']]

        # Create player summary
        player_summary = {
            'id': player_id,
            'name': player['web_name'],
            'minutes': player['minutes']/generateCurrentGameweek(),
            'value': float(player['now_cost']/10),
            'name': player['web_name'],
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
            ]
        }

        logger.info(f"Successfully retrieved summary for player ID {player_id}")
        return player_summary, 200

    except Exception as e:
        logger.exception(f"An unexpected error occurred while processing player ID {player_id}: {str(e)}")
        return {"error": "An unexpected error occurred."}, 500