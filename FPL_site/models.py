import sqlFunction
import genericMethods

season = "2023_2024"

def connect_db():
    return sqlFunction.connectToDB("jackbegley", "Athome19369*", season + "_bootstrapstatic")

def get_players():
    # Assuming you have a database connection utility called connect_db
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    query = "SELECT id, CONCAT(first_name, ' ', second_name) AS full_name FROM 2023_2024_bootstrapstatic.elements;"
    cursor.execute(query)
    players = cursor.fetchall()
    dbConnect.close()  # Always close the database connection
    return players


def get_player_points():
    points = {}
    dbConnect = connect_db()
    cursor = dbConnect.cursor(dictionary=True)
    cursor.execute(f"SELECT second_name, total_points FROM `{season}_bootstrapstatic`.`elements`")
    
    for row in cursor:
        secondName = row['second_name']
        cleanedSurname = str.lower(genericMethods.unicodeReplace(secondName))
        points[cleanedSurname] = row['total_points']

    return points

def get_comparison_stats(id1, id2):
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
    