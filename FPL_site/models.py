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
        cursor.execute(f"SELECT  first_name, second_name, transfers_in_event, transfers_out_event, chance_of_playing_next_round, chance_of_playing_this_round, ep_this,  form, id, now_cost, points_per_game,  selected_by_percent, team,  goals_scored, assists, clean_sheets, penalties_saved, yellow_cards, red_cards, saves, bonus, bps, ict_index, expected_goals, expected_assists, expected_goal_involvements FROM 2023_2024_bootstrapstatic.elements where id={id1};")
        player1 = cursor.fetchone()
    
        cursor.execute(f"SELECT  first_name, second_name, transfers_in_event, transfers_out_event, chance_of_playing_next_round, chance_of_playing_this_round, ep_this,  form, id, now_cost, points_per_game,  selected_by_percent, team,  goals_scored, assists, clean_sheets, penalties_saved, yellow_cards, red_cards, saves, bonus, bps, ict_index, expected_goals, expected_assists, expected_goal_involvements FROM 2023_2024_bootstrapstatic.elements where id={id2};")
        player2 = cursor.fetchone()

        dbConnect.close()  # It's important to close the connection
        return [player1, player2]
    