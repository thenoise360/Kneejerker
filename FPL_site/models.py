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
    query = f"SELECT id, team, CONCAT(first_name, ' ', second_name) AS full_name FROM {db}.elements;"
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

def get_player_net_transfers(player_id):
    # Assuming you have a database connection utility called connect_db
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    query = f'SELECT id, (transfers_in_event - transfers_out_event) as net_transfers FROM {db}.elements WHERE id = %s;'
    cursor.execute(query, (player_id,))
    net_transfers = cursor.fetchone()
    dbConnect.close()  # Always close the database connection
    return net_transfers


def get_player_index_scores():
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    
    db = f'{season}_bootstrapstatic'
    events_db = f'{season}_events'
    fixtures_db = f'{season}_fixtures'

    query = f'''
    WITH PlayerTeam AS (SELECT id, team_code FROM {db}.elements), 
    FixtureDifficulties AS (
        SELECT event, team_h, team_a, team_h_difficulty, team_a_difficulty, team_h AS team_code, team_h_difficulty AS team_difficulty 
        FROM {fixtures_db}.fixtures 
        UNION ALL 
        SELECT event, team_h, team_a, team_h_difficulty, team_a_difficulty, team_a AS team_code, team_a_difficulty AS team_difficulty 
        FROM {fixtures_db}.fixtures
    ), 
    TeamIctIndexSum AS (
        SELECT bs.team_code, SUM(e.ict_index) AS team_ict_index_sum 
        FROM {events_db}.elements e 
        JOIN {db}.elements bs ON e.id = bs.id 
        WHERE e.Gameweek IN (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30) 
        GROUP BY bs.team_code
    ), 
    PlayerIctIndexSum AS (
        SELECT e.id, SUM(e.ict_index) AS player_ict_index_sum 
        FROM {events_db}.elements e 
        WHERE e.Gameweek IN (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30) 
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
        FROM {events_db}.elements e 
        JOIN {db}.elements bs ON e.id = bs.id 
        LEFT JOIN FixtureDifficulties fd ON e.Gameweek = fd.event AND bs.team_code = fd.team_code 
        JOIN TeamIctIndexSum tis ON bs.team_code = tis.team_code 
        JOIN PlayerIctIndexSum pis ON e.id = pis.id 
        WHERE e.Gameweek IN (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30) 
        GROUP BY e.id, bs.team_code, pis.player_ict_index_sum, tis.team_ict_index_sum 
        HAVING player_contribution_percentage IS NOT NULL
    ), 
    MinMaxScore AS (
        SELECT MIN(debug_score) AS min_debug_score, MAX(debug_score) AS max_debug_score 
        FROM RawIndexes
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
    FROM {events_db}.elements e 
    WHERE e.id NOT IN (SELECT id FROM RawIndexes);
    '''
    
    cursor.execute(query)
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
   