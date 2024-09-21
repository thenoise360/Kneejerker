import pandas as pd
import os
import mysql.connector
from sqlalchemy import create_engine
import pymysql
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from scipy.optimize import linprog
import numpy as np
import matplotlib
matplotlib.use('Agg')
from pulp import LpProblem, LpVariable, LpMaximize, LpInteger, lpSum, LpStatus
import seaborn as sns
import json
import requests
import unicodedata
import logging

# Setup logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Database configuration
FLASK_ENV = 'development'
HOST = 'localhost'
USER = 'jackbegley'
PASSWORD = 'Athome19369*'
DB = 'fpl'

season_start = 2024

# Fetch data from MySQL
def fetch_mysql_data(query, database):
    logging.info(f"Fetching data from {database} with query: {query}")
    engine = create_engine(f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}/{database}')
    df = pd.read_sql(query, engine)
    logging.info(f"Fetched {len(df)} rows from {database}.")
    return df

# Get current gameweek from API
def get_current_gameweek():
    """Fetch current gameweek using the Fantasy Premier League API."""
    logging.info("Fetching current gameweek from the API.")
    response = requests.get('https://fantasy.premierleague.com/api/entry/1/')
    if response.status_code == 200:
        todays_data = response.json()
        current_gameweek = todays_data.get('current_event', None)
        logging.info(f"Current gameweek is: {current_gameweek}")
        return current_gameweek
    else:
        logging.error(f"Failed to fetch gameweek, status code: {response.status_code}")
        raise Exception(f"Failed to fetch gameweek, status code: {response.status_code}")

# Clean player names (remove unicode characters)
def clean_player_names(players_df):
    """Normalize player names by removing special characters."""
    logging.info("Cleaning player names.")
    players_df['second_name'] = players_df['second_name'].apply(
        lambda x: unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode('utf-8')
    )
    return players_df

# Prepare data
def prepare_data():
    """Fetch and prepare data for the model."""
    logging.info("Preparing data by fetching events, fixtures, and player data.")
    current_gw = get_current_gameweek()

    # Fetch events, fixtures, and player data
    events_query = f"SELECT * FROM {DB}.events_elements;"
    events_df = fetch_mysql_data(events_query, DB)

    fixtures_query = f"SELECT * FROM {DB}.elementsummary_fixtures;"
    fixtures_df = fetch_mysql_data(fixtures_query, DB)

    # Fetch player data including element_type
    players_query = (f"SELECT id, first_name, second_name, web_name, element_type, now_cost, minutes, chance_of_playing_next_round,"
                 f"goals_scored, assists, clean_sheets, goals_conceded, own_goals, penalties_saved, "
                 f"penalties_missed, yellow_cards, red_cards, saves, bonus, bps, influence, creativity, "
                 f"threat, ict_index, starts, expected_goals, expected_assists, expected_goal_involvements, "
                 f"expected_goals_conceded, total_points, in_dreamteam "
                 f"FROM {DB}.bootstrapstatic_elements "
                 f"WHERE Year_start = {season_start} AND gameweek = {current_gw - 1};")
    
    players_df = fetch_mysql_data(players_query, f'{DB}')
    
    logging.info(f"Player data contains {players_df.shape[1]} columns and {players_df.shape[0]} rows.")
    
    # Calculate average minutes per game and filter players with at least 15-minute average
    players_df['avg_minutes'] = players_df['minutes'] / (current_gw - 1)  # Assuming we want average until the last gameweek
    players_df = players_df[(players_df['avg_minutes'] >= 15) & (players_df['chance_of_playing_next_round'] >= 50)]
    logging.info(f"Filtered players with at least 15-minute average per game and chance of playing >= 50%. Remaining players: {len(players_df)}")

    # Adjust player costs
    players_df['now_cost'] = players_df['now_cost'] / 10

    return events_df, fixtures_df, players_df

# Adjust the training and predicting function to return the feature importance
def train_and_predict(df_train, df_predict, players_df):
    logging.info("Training Random Forest model for performance prediction.")
    
    features = ['minutes', 'goals_scored', 'assists', 'clean_sheets', 'goals_conceded', 
                'own_goals', 'penalties_saved', 'penalties_missed', 'yellow_cards', 
                'red_cards', 'saves', 'bonus', 'bps', 'influence', 'creativity', 
                'threat', 'ict_index', 'starts', 'expected_goals', 'expected_assists', 
                'expected_goal_involvements', 'expected_goals_conceded', 'total_points', 
                'in_dreamteam', 'year_start', 'gameweek']

    # Ensure all required columns are present in both train and predict data
    for col in features:
        if col not in df_train.columns:
            df_train[col] = 0
        if col not in df_predict.columns:
            df_predict[col] = 0

    logging.info(f"Missing columns in training data: {set(features) - set(df_train.columns)}")
    logging.info(f"Missing columns in prediction data: {set(features) - set(df_predict.columns)}")

    # Before training, ensure 'element_type', 'now_cost', 'first_name', and 'second_name' exist in df_predict
    df_predict = pd.merge(df_predict, players_df[['id', 'element_type', 'now_cost', 'first_name', 'second_name']], on='id', how='left')

    # Retain non-feature columns before transformation
    non_feature_columns_train = df_train[['id', 'element_type', 'now_cost', 'first_name', 'second_name']].copy()
    non_feature_columns_predict = df_predict[['id', 'element_type', 'now_cost', 'first_name', 'second_name']].copy()

    # Ensure all features are numeric
    df_train[features] = df_train[features].apply(pd.to_numeric, errors='coerce')
    df_predict[features] = df_predict[features].apply(pd.to_numeric, errors='coerce')

    # Impute missing values (mean imputation)
    imputer = SimpleImputer(strategy='mean')
    df_train_imputed = imputer.fit_transform(df_train[features])
    df_predict_imputed = imputer.transform(df_predict[features])

    # Scale the data
    scaler = StandardScaler()
    df_train_scaled = scaler.fit_transform(df_train_imputed)
    df_predict_scaled = scaler.transform(df_predict_imputed)

    # Define the target variable
    target = df_train['total_points'].fillna(0)

    # Train the RandomForestRegressor
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(df_train_scaled, target)

    # Get feature importance
    feature_importance = model.feature_importances_
    importance_df = pd.DataFrame({'Feature': features, 'Importance': feature_importance}).sort_values(by='Importance', ascending=False)

    logging.info("Feature importance:\n%s", importance_df)

    # Predict future performance
    predicted_performance = model.predict(df_predict_scaled)

    # Re-attach non-feature columns
    df_predict_final = pd.concat([non_feature_columns_predict.reset_index(drop=True), 
                                  pd.DataFrame(predicted_performance, columns=['predicted_performance'])], axis=1)

    logging.info("Prediction completed.")

     # Re-attach non-feature columns
    df_predict_final = pd.concat([
        non_feature_columns_predict.reset_index(drop=True),
        pd.DataFrame(predicted_performance, columns=['predicted_performance']),
        df_predict[['total_points']].reset_index(drop=True)  # Include 'total_points' from df_predict
    ], axis=1)

    logging.info("Prediction completed.")
    return df_predict_final, importance_df

# Check if there are enough players to meet team formation constraints
def check_sufficient_players(players_df):
    """Check if there are enough players to meet team formation constraints."""
    logging.info("Checking if there are enough players to meet team formation constraints.")
    position_counts = players_df.groupby('element_type').size()
    sufficient = all([
        position_counts.get(1, 0) >= 2,
        position_counts.get(2, 0) >= 5,
        position_counts.get(3, 0) >= 5,
        position_counts.get(4, 0) >= 3,
    ])
    if sufficient:
        logging.info("Sufficient players found for each position.")
    else:
        logging.warning("Not enough players found to meet team formation constraints.")
    return sufficient

def aggregate_gameweek_data(events_df, current_gameweek):
    """Aggregate player stats for training and next five weeks prediction."""
    current_events = events_df[events_df['gameweek'] <= current_gameweek]
    next_five_weeks_events = events_df[(events_df['gameweek'] > current_gameweek) & (events_df['gameweek'] <= current_gameweek + 5)]

    current_agg = current_events.groupby('id').agg({
        'minutes': 'sum', 'goals_scored': 'sum', 'assists': 'sum', 'clean_sheets': 'sum',
        'goals_conceded': 'sum', 'own_goals': 'sum', 'penalties_saved': 'sum', 'penalties_missed': 'sum',
        'yellow_cards': 'sum', 'red_cards': 'sum', 'saves': 'sum', 'bonus': 'sum', 'bps': 'sum',
        'influence': 'sum', 'creativity': 'sum', 'threat': 'sum', 'ict_index': 'sum',
        'expected_goals': 'sum', 'expected_assists': 'sum', 'expected_goal_involvements': 'sum',
        'expected_goals_conceded': 'sum', 'total_points': 'sum', 'in_dreamteam': 'sum',
        'gameweek': 'max', 'year_start': 'max'
    }).reset_index()

    next_five_weeks_agg = next_five_weeks_events.groupby('id').agg({
        'minutes': 'sum', 'goals_scored': 'sum', 'assists': 'sum', 'clean_sheets': 'sum',
        'goals_conceded': 'sum', 'own_goals': 'sum', 'penalties_saved': 'sum', 'penalties_missed': 'sum',
        'yellow_cards': 'sum', 'red_cards': 'sum', 'saves': 'sum', 'bonus': 'sum', 'bps': 'sum',
        'influence': 'sum', 'creativity': 'sum', 'threat': 'sum', 'ict_index': 'sum',
        'expected_goals': 'sum', 'expected_assists': 'sum', 'expected_goal_involvements': 'sum',
        'expected_goals_conceded': 'sum', 'total_points': 'sum', 'in_dreamteam': 'sum',
        'gameweek': 'max', 'year_start': 'max'
    }).reset_index()

    return current_agg, next_five_weeks_agg

def optimize_team(players_df, budget):
    logging.info(f"Optimizing team selection within a budget of {budget}.")

    # Ensure sufficient players for each position
    if not check_sufficient_players(players_df):
        logging.warning("Not enough players to meet team constraints.")
        return pd.DataFrame(columns=players_df.columns)

    # Clean NaN or infinity values in 'now_cost'
    if players_df['now_cost'].isnull().any() or np.isinf(players_df['now_cost']).any():
        logging.warning("Found NaN or inf values in now_cost. Replacing with median value.")
        players_df['now_cost'] = players_df['now_cost'].replace([np.inf, -np.inf], np.nan)
        players_df['now_cost'].fillna(players_df['now_cost'].median(), inplace=True)

    # Initialize the optimization problem
    prob = LpProblem("FPL_Team_Selection", LpMaximize)

    # Create decision variables
    player_vars = LpVariable.dicts("player", players_df.index, cat=LpInteger, lowBound=0, upBound=1)

    # Objective function: maximize total predicted points while minimizing unused budget
    # You can use a weighted combination of points and unused budget to penalize leaving money on the table.
    total_predicted_points = lpSum(players_df.loc[i, 'predicted_performance'] * player_vars[i] for i in players_df.index)
    total_cost = lpSum(players_df.loc[i, 'now_cost'] * player_vars[i] for i in players_df.index)
    unused_budget_penalty = (budget - total_cost) * 18  # IMPORTANT!! Do not adjust weight as this has been optimized.

    # Adjust the objective to maximize points and minimize unused budget
    prob += total_predicted_points - unused_budget_penalty

    # Budget constraint
    prob += total_cost <= budget

    # Positional constraints
    prob += lpSum(player_vars[i] for i in players_df.index if players_df.loc[i, 'element_type'] == 1) == 2  # GK
    prob += lpSum(player_vars[i] for i in players_df.index if players_df.loc[i, 'element_type'] == 2) == 5  # DEF
    prob += lpSum(player_vars[i] for i in players_df.index if players_df.loc[i, 'element_type'] == 3) == 5  # MID
    prob += lpSum(player_vars[i] for i in players_df.index if players_df.loc[i, 'element_type'] == 4) == 3  # FWD

    # Total squad size constraint (15 players in total)
    prob += lpSum(player_vars[i] for i in players_df.index) == 15

    # Solve the problem
    prob.solve()

    # Check if the solution is optimal
    if LpStatus[prob.status] == 'Optimal':
        logging.info("Optimization successful.")
        selected_indices = [i for i in players_df.index if player_vars[i].varValue == 1]
        return players_df.loc[selected_indices]
    else:
        logging.error(f"Optimization failed: {LpStatus[prob.status]}")
        return pd.DataFrame(columns=players_df.columns)


def get_optimal_team(current_gameweek, budget=100):
    """Get optimal team for the specified gameweek."""
    logging.info(f"Fetching data and optimizing team for gameweek {current_gameweek}.")
    events_df, fixtures_df, players_df = prepare_data()

    # Use the helper function to aggregate data
    current_agg, next_five_weeks_agg = aggregate_gameweek_data(events_df, current_gameweek)

    # Merge current_agg with players_df to retain critical columns
    current_merged = pd.merge(current_agg, players_df[['id', 'element_type', 'now_cost', 'second_name', 'first_name']], on='id', how='left')

    # Perform predictions and get feature importance
    predicted_df, feature_importance_df = train_and_predict(current_merged, next_five_weeks_agg, players_df)

    # Verify that 'element_type' and 'second_name' are present in predicted_df
    if 'element_type' not in predicted_df.columns or 'second_name' not in predicted_df.columns:
        logging.error("'element_type' or 'second_name' column is missing in predicted_df.")
        raise KeyError("'element_type' or 'second_name' column is required but missing in predicted_df.")
    else:
        logging.info("'element_type' and 'second_name' are present in predicted_df after merging.")

    # Proceed with optimization
    optimal_team = optimize_team(predicted_df, budget)
    if optimal_team.empty:
        logging.warning("No optimal team could be selected due to constraints.")
    else:
        print_optimal_team_layout(optimal_team)
        
    return optimal_team

# Print optimal team layout
def print_optimal_team_layout(df):
    logging.info("Printing the optimal team layout.")
    df = df.drop_duplicates(subset=['id'])
    gks = df[df['element_type'] == 1][['first_name', 'second_name']].apply(lambda x: ' '.join(x), axis=1).tolist()
    defs = df[df['element_type'] == 2][['first_name', 'second_name']].apply(lambda x: ' '.join(x), axis=1).tolist()
    mids = df[df['element_type'] == 3][['first_name', 'second_name']].apply(lambda x: ' '.join(x), axis=1).tolist()
    fwds = df[df['element_type'] == 4][['first_name', 'second_name']].apply(lambda x: ' '.join(x), axis=1).tolist()

    # Print formatted output
    print("\nGoalkeepers:        {}        {}".format(gks[0], gks[1] if len(gks) > 1 else 'None'))
    print("\nDefenders:    {}    {}    {}    {}    {}".format(*defs[:5], *['None']*(5-len(defs))))
    print("\nMidfielders:    {}    {}    {}    {}    {}".format(*mids[:5], *['None']*(5-len(mids))))
    print("\nForwards:      {}      {}      {}".format(*fwds[:3], *['None']*(3-len(fwds))))

    total_value = df['now_cost'].sum()
    print("\nTotal Value: {:.1f}".format(total_value))

    logging.info(f"Total team value: {total_value}")

def export_all_players_to_csv(players_df, file_name="all_players.csv"):
    logging.info(f"Exporting all players to {file_name}.")
    
    # Calculate points per million if not already done
    if 'points_per_million' not in players_df.columns:
        players_df['points_per_million'] = players_df['predicted_performance'] / players_df['now_cost']

    # Select relevant columns
    columns_to_export = ['first_name', 'second_name', 'now_cost', 'total_points','points_per_million']

    # Check if the required columns exist in the DataFrame
    missing_columns = [col for col in columns_to_export if col not in players_df.columns]
    if missing_columns:
        logging.error(f"Missing columns for export: {missing_columns}")
        raise KeyError(f"Missing columns for export: {missing_columns}")

    # Sort players by points_per_million in descending order
    sorted_players_df = players_df[columns_to_export].sort_values(by='points_per_million', ascending=False)

    # Export the sorted DataFrame to CSV
    sorted_players_df.to_csv(file_name, index=False)
    logging.info(f"All players exported to {file_name} in descending order by points_per_million.")

def main():
    """Main workflow for fetching data, training the model, and optimizing team."""
    logging.info("Starting the FPL optimization process.")
    current_gameweek = get_current_gameweek()

    # Fetch data and aggregate
    events_df, fixtures_df, players_df = prepare_data()
    current_agg, next_five_weeks_agg = aggregate_gameweek_data(events_df, current_gameweek)

    # Merge the data for predictions
    current_merged = pd.merge(current_agg, players_df[['id', 'element_type', 'now_cost', 'second_name', 'first_name']], on='id', how='left')

    # Get optimal team for the current gameweek
    optimal_team = get_optimal_team(current_gameweek, budget=100)

    # Save and display results
    if not optimal_team.empty:
        optimal_team.to_csv('optimal_team.csv', index=False)
        logging.info("Optimal team saved to 'optimal_team.csv'.")
        print_optimal_team_layout(optimal_team)
    else:
        logging.warning("No optimal team was selected.")

    # Run predictions and export all players after predicted performance has been calculated
    predicted_df, _ = train_and_predict(current_merged, next_five_weeks_agg, players_df)

    # Export all players to CSV sorted by points_per_million
    export_all_players_to_csv(predicted_df, file_name="all_players.csv")

if __name__ == "__main__":
    main()
    logging.info("Process completed.")
    print("")
