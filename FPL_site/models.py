import sqlFunction
import genericMethods
import requests
import json

season = "2023_2024"
db = f'{season}_bootstrapstatic'


# Get us the current gameweek number
def generateCurrentGameweek():
    todaysData = json.loads(json.dumps(requests.get('https://fantasy.premierleague.com/api/entry/1/').json()))
    for keys in todaysData:
        if keys == 'current_event':
            return todaysData[keys]

def connect_db():
    return sqlFunction.connectToDB("jackbegley", "Athome19369*", db)

def get_players():
    # Assuming you have a database connection utility called connect_db
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    query = f"SELECT id, CONCAT(first_name, ' ', second_name) AS full_name FROM {db}.elements;"
    cursor.execute(query)
    players = cursor.fetchall()
    dbConnect.close()  # Always close the database connection
    return players

def get_players_by_team():
    # Assuming you have a database connection utility called connect_db
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    cursor.execute(f'SELECT t.name AS "Team", p.first_name AS "First_name", p.second_name AS "Surname", p.id AS "ID" FROM `{db}`.`elements` p JOIN `{db}`.`teams` t on p.team = t.id;')
    players = cursor.fetchall()
    dbConnect.close()  # Always close the database connection

    # Initialize the final dictionary
    teams_dict = {}

    # Process the data to create the desired structure
    for entry in players:
        team_name = entry['Team']
        full_name = f"{entry['First_name']} {entry['Surname']}"
        player_id = entry['ID']
    
        if team_name not in teams_dict:
            teams_dict[team_name] = {}
    
        teams_dict[team_name][full_name] = player_id

    # Sort the dictionary by player names within each team
    for team in teams_dict:
        teams_dict[team] = dict(sorted(teams_dict[team].items()))

    return teams_dict

def get_players_by_position():
    # Assuming you have a database connection utility called connect_db
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    cursor.execute(f'SELECT t.name AS "Team", p.first_name AS "First_name", p.second_name AS "Surname", p.id AS "ID" FROM `{db}`.`elements` p JOIN `{db}`.`teams` t on p.team = t.id;')
    players = cursor.fetchall()
    dbConnect.close()  # Always close the database connection
    return players



def get_player_points():
    points = {}
    db = f'{season}_bootstrapstatic'
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    cursor.execute(f"SELECT second_name, total_points FROM `{db}`.`elements`")
    
    for row in cursor:
        secondName = row['second_name']
        cleanedSurname = str.lower(genericMethods.unicodeReplace(secondName))
        points[cleanedSurname] = row['total_points']

    return points

def get_comparison_stats(id1, id2):
    gameweek = generateCurrentGameweek()
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    cursor.execute(f"SELECT total_points, bonus, points_per_game, value_season, starts, minutes, now_cost, selected_by_percent, ict_index FROM 2023_2024_bootstrapstatic.elements where id={id1};")
    season_player1 = cursor.fetchone()

    cursor.execute(f"SELECT  transfers_in_event, transfers_out_event, chance_of_playing_next_round,  form, bps FROM 2023_2024_bootstrapstatic.elements where id={id1};")
    form_player1 = cursor.fetchone()
        
    cursor.execute(f"SELECT  goals_scored, assists, clean_sheets, penalties_saved, yellow_cards, red_cards, saves FROM 2023_2024_bootstrapstatic.elements where id={id1};")
    contribution_player1 = cursor.fetchone()

    cursor.execute(f"SELECT expected_goals, expected_assists, expected_goal_involvements FROM 2023_2024_bootstrapstatic.elements where id={id1};")
    xG_player1 = cursor.fetchone()

    player1 = {
        'Season': season_player1,
        'Form': form_player1,
        'Contribution': contribution_player1,
        'xG': xG_player1,
            
    }

    cursor.execute(f"SELECT total_points, bonus, points_per_game, value_season, starts, minutes, now_cost, selected_by_percent, ict_index FROM 2023_2024_bootstrapstatic.elements where id={id2};")
    season_player2 = cursor.fetchone()

    cursor.execute(f"SELECT  transfers_in_event, transfers_out_event, chance_of_playing_next_round,  form, bps FROM 2023_2024_bootstrapstatic.elements where id={id2};")
    form_player2 = cursor.fetchone()
        
    cursor.execute(f"SELECT  goals_scored, assists, clean_sheets, penalties_saved, yellow_cards, red_cards, saves FROM 2023_2024_bootstrapstatic.elements where id={id2};")
    contribution_player2 = cursor.fetchone()

    cursor.execute(f"SELECT expected_goals, expected_assists, expected_goal_involvements FROM 2023_2024_bootstrapstatic.elements where id={id2};")
    xG_player2 = cursor.fetchone()

    player2 = {
        'Season': season_player2,
        'Form': form_player2,
        'Contribution': contribution_player2,
        'xG': xG_player2,
            
    }

    dbConnect.close()  # It's important to close the connection
    return [player1, player2]
   