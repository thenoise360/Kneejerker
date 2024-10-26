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
from pulp import LpProblem, LpVariable, LpMaximize, lpSum, LpStatus, LpBinary
import seaborn as sns
import json
import requests
import unicodedata
import logging
import gc  # Garbage Collector
from sklearn.model_selection import GridSearchCV
from FPL_site.config import current_config

# Setup logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Optimize Data Types Function
def optimize_data_types(df):
    """Optimize DataFrame memory usage by changing data types."""
    float_cols = df.select_dtypes(include=['float64']).columns
    int_cols = df.select_dtypes(include=['int64']).columns
    for col in float_cols:
        df[col] = df[col].astype('float32')
    for col in int_cols:
        df[col] = df[col].astype('int32')
    return df

budget = 100

HOST = current_config.HOST
USER = current_config.USER
PASSWORD = current_config.PASSWORD
DB = current_config.DATABASE

season = "2023_2024"
season_start = 2024

NULL = None

# Fetch data from MySQL
def fetch_mysql_data(query, database):
    logging.info(f"Fetching data from {database} with query: {query}")
    engine = create_engine(f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}/{database}')
    df = pd.read_sql(query, engine)
    logging.info(f"Fetched {len(df)} rows from {database}.")
    # Optimize data types to save memory
    df = optimize_data_types(df)
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
    players_query = (
        f"SELECT id, first_name, second_name, web_name, element_type, now_cost, minutes, chance_of_playing_next_round, "
        f"goals_scored, assists, clean_sheets, goals_conceded, own_goals, penalties_saved, "
        f"penalties_missed, yellow_cards, red_cards, saves, bonus, bps, influence, creativity, "
        f"threat, ict_index, starts, expected_goals, expected_assists, expected_goal_involvements, "
        f"expected_goals_conceded, total_points, in_dreamteam, team_code, team "
        f"FROM {DB}.bootstrapstatic_elements "
        f"WHERE Year_start = {season_start} AND gameweek = {current_gw - 1};"
    )

    players_df = fetch_mysql_data(players_query, f'{DB}')

    logging.info(f"Player data contains {players_df.shape[1]} columns and {players_df.shape[0]} rows.")
    logging.info(f"Columns in players_df: {players_df.columns.tolist()}")  # Added line

    # Clean player names
    players_df = clean_player_names(players_df)

    # Calculate average minutes per game and filter players with at least 15-minute average
    players_df['avg_minutes'] = players_df['minutes'] / (current_gw - 1)  # Assuming we want average until the last gameweek
    players_df = players_df[(players_df['avg_minutes'] >= 15) & (players_df['chance_of_playing_next_round'] >= 50)]
    logging.info(f"Filtered players with at least 15-minute average per game and chance of playing >= 50%. Remaining players: {len(players_df)}")

    # Adjust player costs
    players_df['now_cost'] = players_df['now_cost'] / 10

    # Convert relevant columns in players_df to numeric to prevent TypeError
    player_numeric_columns = [
        'goals_scored', 'assists', 'clean_sheets', 'goals_conceded', 'own_goals',
        'penalties_saved', 'penalties_missed', 'yellow_cards', 'red_cards',
        'saves', 'bonus', 'bps', 'influence', 'creativity', 'threat', 'ict_index'
    ]

    for col in player_numeric_columns:
        if col in players_df.columns:
            players_df[col] = pd.to_numeric(players_df[col], errors='coerce').fillna(0).astype('float32')
            logging.info(f"Converted column '{col}' to numeric.")
        else:
            logging.warning(f"Column '{col}' not found in players_df. Setting to 0.")
            players_df[col] = 0.0

    # Convert relevant columns in events_df to numeric to prevent TypeError
    event_numeric_columns = [
        'goals_scored', 'assists', 'clean_sheets', 'goals_conceded', 'own_goals',
        'penalties_saved', 'penalties_missed', 'yellow_cards', 'red_cards',
        'saves', 'bonus', 'bps', 'influence', 'creativity', 'threat', 'ict_index'
    ]

    for col in event_numeric_columns:
        if col in events_df.columns:
            events_df[col] = pd.to_numeric(events_df[col], errors='coerce').fillna(0).astype('float32')
            logging.info(f"Converted column '{col}' in events_df to numeric.")
        else:
            logging.warning(f"Column '{col}' not found in events_df. Setting to 0.")
            events_df[col] = 0.0

    # Compute 'form' as average points over the last 5 gameweeks
    players_df['form'] = players_df['id'].apply(lambda x: compute_player_form(events_df, x, current_gw, num_gameweeks=5))

    logging.info("Computed 'form' for all players.")

    # Ensure 'predicted_performance' exists
    if 'predicted_performance' not in players_df.columns:
        logging.warning("'predicted_performance' column is missing. Computing based on available metrics.")
        # Example: Simple prediction based on total_points and form
        players_df['predicted_performance'] = players_df['total_points'] * 0.6 + players_df['form'] * 0.4
        players_df['predicted_performance'] = pd.to_numeric(players_df['predicted_performance'], errors='coerce').fillna(0).astype('float32')
        logging.info("Computed 'predicted_performance' for all players.")
    else:
        # Ensure it's numeric
        players_df['predicted_performance'] = pd.to_numeric(players_df['predicted_performance'], errors='coerce').fillna(0).astype('float32')
        logging.info("'predicted_performance' column converted to numeric.")

    # Validate players_df
    validate_players_df(players_df)

    logging.info("players_df validation passed.")

    # Free up memory
    del events_df, fixtures_df
    gc.collect()

    return players_df

def compute_player_form(events_df, player_id, current_gameweek, num_gameweeks=5):
    """
    Computes the form of a player based on their performance in the last `num_gameweeks`.
    
    Parameters:
        events_df (pd.DataFrame): DataFrame containing match events.
        player_id (int): The ID of the player.
        current_gameweek (int): The current gameweek.
        num_gameweeks (int): Number of recent gameweeks to consider.
    
    Returns:
        float: The computed form of the player.
    """
    # Filter events for the player and the last `num_gameweeks` gameweeks
    recent_events = events_df[
        (events_df['id'] == player_id) & 
        (events_df['gameweek'] > current_gameweek - num_gameweeks) & 
        (events_df['gameweek'] <= current_gameweek)
    ]

    if recent_events.empty:
        logging.info(f"No recent events for player ID {player_id}. Setting form to 0.")
        return 0.0  # No recent data, assume form is 0

    # Assign weights to each gameweek (more recent gameweeks have higher weight)
    recent_events = recent_events.sort_values('gameweek')
    recent_events['weight'] = range(1, len(recent_events) + 1)  # 1, 2, ..., N

    # Define points as a combination of relevant metrics
    recent_events['points'] = (
        recent_events['goals_scored'] * 6 +
        recent_events['assists'] * 3 +
        recent_events['clean_sheets'] * 4 +
        recent_events['goals_conceded'] * (-1) +
        recent_events['own_goals'] * (-2) +
        recent_events['penalties_saved'] * 5 +
        recent_events['penalties_missed'] * (-2) +
        recent_events['yellow_cards'] * (-1) +
        recent_events['red_cards'] * (-3) +
        recent_events['saves'] * 1 +
        recent_events['bonus'] * 1 +
        recent_events['bps'] * 0.1 +
        recent_events['influence'] * 0.01 +
        recent_events['creativity'] * 0.01 +
        recent_events['threat'] * 0.01 +
        recent_events['ict_index'] * 0.01
    )

    # Handle any potential non-numeric 'points' values
    recent_events['points'] = pd.to_numeric(recent_events['points'], errors='coerce').fillna(0).astype('float32')

    # Compute weighted average points
    weighted_sum = (recent_events['points'] * recent_events['weight']).sum()
    total_weights = recent_events['weight'].sum()
    weighted_average = weighted_sum / total_weights if total_weights != 0 else 0.0

    logging.debug(f"Player ID {player_id} - Weighted Sum: {weighted_sum}, Total Weights: {total_weights}, Form: {weighted_average}")

    return weighted_average

def validate_players_df(players_df):
    required_columns = [
        'id', 'first_name', 'second_name', 'element_type', 'now_cost', 
        'minutes', 'total_points', 'form', 'predicted_performance', 'team'
    ]
    missing_columns = [col for col in required_columns if col not in players_df.columns]
    if missing_columns:
        logging.error(f"Missing required columns in players_df: {missing_columns}")
        raise KeyError(f"Missing required columns: {missing_columns}")

    # Additional checks
    numeric_columns = ['now_cost', 'minutes', 'total_points', 'form', 'predicted_performance']
    for col in numeric_columns:
        if not pd.api.types.is_numeric_dtype(players_df[col]):
            logging.warning(f"Column '{col}' is not numeric. Attempting to convert.")
            players_df[col] = pd.to_numeric(players_df[col], errors='coerce').fillna(0).astype('float32')
            logging.info(f"Converted column '{col}' to numeric.")

def train_and_predict(df_train, df_predict, players_df):
    logging.info("Training models for each position.")

    features = ['minutes', 'goals_scored', 'assists', 'clean_sheets', 'goals_conceded', 
                'own_goals', 'penalties_saved', 'penalties_missed', 'yellow_cards', 
                'red_cards', 'saves', 'bonus', 'bps', 'influence', 'creativity', 
                'threat', 'ict_index', 'starts', 'expected_goals', 'expected_assists', 
                'expected_goal_involvements', 'expected_goals_conceded', 'total_points', 
                'in_dreamteam', 'year_start', 'gameweek']

    # Ensure all required columns are present in both train and predict data
    for col in features:
        if col not in df_train.columns:
            df_train[col] = 0.0
            logging.warning(f"Column '{col}' missing in df_train. Set to 0.")
        if col not in df_predict.columns:
            df_predict[col] = 0.0
            logging.warning(f"Column '{col}' missing in df_predict. Set to 0.")

    # Impute missing values
    imputer = SimpleImputer(strategy='mean')
    df_train_imputed = imputer.fit_transform(df_train[features])
    df_predict_imputed = imputer.transform(df_predict[features])

    # Scale the data
    scaler = StandardScaler()
    df_train_scaled = scaler.fit_transform(df_train_imputed).astype('float32')
    df_predict_scaled = scaler.transform(df_predict_imputed).astype('float32')

    df_train_scaled = pd.DataFrame(df_train_scaled, columns=features)
    df_train_scaled['element_type'] = df_train['element_type'].values.astype('int32')

    df_predict_scaled = pd.DataFrame(df_predict_scaled, columns=features)
    df_predict_scaled['element_type'] = df_predict['element_type'].values.astype('int32')

    # Initialize an empty DataFrame to collect predictions
    df_predictions = pd.DataFrame()

    # Loop over each position (element_type)
    for position in df_train['element_type'].unique():
        logging.info(f"Training model for position: {position}")

        # Filter data for the current position
        X_train_pos = df_train_scaled[df_train_scaled['element_type'] == position][features]
        y_train_pos = df_train[df_train['element_type'] == position]['total_points'].fillna(0).astype('float32')

        X_predict_pos = df_predict_scaled[df_predict_scaled['element_type'] == position][features]
        predict_indices = df_predict_scaled[df_predict_scaled['element_type'] == position].index

        # Check the number of samples
        n_samples = X_train_pos.shape[0]
        logging.info(f"Number of training samples for position {position}: {n_samples}")

        if n_samples == 0:
            logging.warning(f"No training samples for position {position}. Skipping.")
            continue
        elif n_samples == 1:
            logging.warning(f"Only one training sample for position {position}. Training without cross-validation.")
            # Train without cross-validation
            rf = RandomForestRegressor(random_state=42, n_estimators=50)
            rf.fit(X_train_pos, y_train_pos)

            # Predict future performance
            predicted_performance = rf.predict(X_predict_pos)
        else:
            # Adjust cv parameter
            cv_splits = min(3, n_samples)
            logging.info(f"Using cv={cv_splits} for position {position}")

            # Train the model with hyperparameter tuning
            rf = RandomForestRegressor(random_state=42, n_estimators=50)
            param_grid = {
                'max_depth': [None, 10, 20],
                'min_samples_split': [2, 5]
            }
            grid_search = GridSearchCV(
                estimator=rf,
                param_grid=param_grid,
                cv=cv_splits,
                scoring='neg_mean_squared_error',
                n_jobs=1  # Optimized to use single core
            )
            grid_search.fit(X_train_pos, y_train_pos)

            best_model = grid_search.best_estimator_

            # Predict future performance
            predicted_performance = best_model.predict(X_predict_pos)

        # Collect predictions
        position_predictions = pd.DataFrame({
            'id': df_predict.iloc[predict_indices]['id'].values,
            'predicted_performance': predicted_performance.astype('float32'),
            'element_type': position,
            'total_points': df_predict.iloc[predict_indices]['total_points'].values.astype('float32')
        })

        # Add 'form' and 'minutes' by merging with players_df
        position_predictions = pd.merge(position_predictions, players_df[['id', 'form']], on='id', how='left')
        position_predictions = pd.merge(position_predictions, players_df[['id', 'minutes']], on='id', how='left')

        df_predictions = pd.concat([df_predictions, position_predictions], ignore_index=True)

        # Clean up to free memory
        del X_train_pos, y_train_pos, X_predict_pos, grid_search
        gc.collect()

    logging.info("Prediction completed for all positions.")
    return df_predictions, pd.DataFrame()  # Return empty importance_df if not used

# Check if there are enough players to meet team formation constraints
def check_sufficient_players(players_df):
    """
    Checks if there are sufficient players in each position to meet team constraints.

    Parameters:
    - players_df (pd.DataFrame): DataFrame containing player information.

    Returns:
    - bool: True if sufficient players exist, False otherwise.
    """
    position_counts = players_df['element_type'].value_counts()
    required_positions = {1: 2, 2: 5, 3: 5, 4: 3}  # Squad positions
    for pos, count in required_positions.items():
        if position_counts.get(pos, 0) < count:
            logging.error(f"Not enough players for position {pos}. Required: {count}, Available: {position_counts.get(pos, 0)}")
            return False
    return True

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
    }).reset_index().astype({'id': 'int32', 'gameweek': 'int32', 'year_start': 'int32'})

    next_five_weeks_agg = next_five_weeks_events.groupby('id').agg({
        'minutes': 'sum', 'goals_scored': 'sum', 'assists': 'sum', 'clean_sheets': 'sum',
        'goals_conceded': 'sum', 'own_goals': 'sum', 'penalties_saved': 'sum', 'penalties_missed': 'sum',
        'yellow_cards': 'sum', 'red_cards': 'sum', 'saves': 'sum', 'bonus': 'sum', 'bps': 'sum',
        'influence': 'sum', 'creativity': 'sum', 'threat': 'sum', 'ict_index': 'sum',
        'expected_goals': 'sum', 'expected_assists': 'sum', 'expected_goal_involvements': 'sum',
        'expected_goals_conceded': 'sum', 'total_points': 'sum', 'in_dreamteam': 'sum',
        'gameweek': 'max', 'year_start': 'max'
    }).reset_index().astype({'id': 'int32', 'gameweek': 'int32', 'year_start': 'int32'})

    return current_agg, next_five_weeks_agg

def optimize_team(players_df, budget, weights):
    """
    Optimize the FPL team selection based on weighted factors.

    Parameters:
    - players_df (pd.DataFrame): DataFrame containing player information and performance metrics.
    - budget (float): Total budget available for team selection (e.g., 100 for £100M).
    - weights (dict): Dictionary containing user-defined weights for factors.
                      Example: {'total_points': 40, 'form': 30, 'minutes': 30}

    Returns:
    - pd.DataFrame: DataFrame of selected players with their roles and weighted scores.
    """
    logging.info(f"Optimizing team selection within a budget of {budget}M.")

    total_points = int(weights[0])/100
    form = int(weights[1])/100
    minutes = int(weights[2])/100

    # Ensure sufficient players for each position
    if not check_sufficient_players(players_df):
        logging.warning("Not enough players to meet team constraints.")
        return pd.DataFrame(columns=players_df.columns)

    # Clean NaN or infinity values in relevant columns
    required_columns = ['now_cost', 'total_points', 'form', 'minutes', 'predicted_performance']
    for col in required_columns:
        if col in players_df.columns:
            players_df[col] = players_df[col].replace([np.inf, -np.inf], np.nan).fillna(players_df[col].median()).astype('float32')
            logging.info(f"Cleaned column '{col}'.")
        else:
            logging.error(f"Required column '{col}' is missing from players_df.")
            raise KeyError(f"Required column '{col}' is missing from players_df.")

    # Calculate weighted_score based on user-defined weights
    # Normalize weights to sum to 1
    total_weight = total_points + form + minutes
    w_total_points = total_points / total_weight
    w_form = form / total_weight
    w_minutes = minutes / total_weight

    # Compute weighted_score
    players_df['weighted_score'] = (
        players_df['predicted_performance'] * w_total_points +
        players_df['form'] * w_form +
        players_df['minutes'] * w_minutes
    ).astype('float32')

    logging.info("Calculated weighted performance for all players based on user-defined weights.")

    # Initialize the optimization problem
    prob = LpProblem("FPL_Team_Selection", LpMaximize)

    # Create binary decision variables for squad selection (x_i)
    player_vars = LpVariable.dicts("player", players_df.index, cat=LpBinary)

    # Objective function: maximize total weighted scores
    prob += lpSum(players_df.loc[i, 'weighted_score'] * player_vars[i] for i in players_df.index), "Total_Weighted_Scores"

    # Budget constraint: total cost <= budget
    prob += (
        lpSum(players_df.loc[i, 'now_cost'] * player_vars[i] for i in players_df.index) <= budget,
        "TotalBudget"
    )

    # Squad size constraint: exactly 15 players
    prob += (
        lpSum(player_vars[i] for i in players_df.index) == 15,
        "TotalSquadSize"
    )

    # Positional constraints for the entire squad
    positions = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}
    squad_position_limits = {1: 2, 2: 5, 3: 5, 4: 3}

    for pos, name in positions.items():
        prob += (
            lpSum(player_vars[i] for i in players_df.index if players_df.loc[i, 'element_type'] == pos) == squad_position_limits[pos],
            f"Squad_Position_{name}_Constraint"
        )

    # Optional: Constraint to limit the number of players from the same club (e.g., max 3 per club)
    if 'team' in players_df.columns:
        clubs = players_df['team'].unique()
        max_players_per_club = 3
        for club in clubs:
            club_players = players_df[players_df['team'] == club].index
            prob += (
                lpSum(player_vars[i] for i in club_players) <= max_players_per_club,
                f"Max_Players_{club}"
            )
    else:
        logging.warning("'team' column not found in players_df. Skipping club diversity constraints.")

    # Solve the problem
    prob.solve()

    # Check if the solution is optimal
    if LpStatus[prob.status] == 'Optimal':
        logging.info("Optimization successful.")
        selected_indices = [i for i in players_df.index if player_vars[i].varValue == 1]

        # Extract selected players
        optimal_team = players_df.loc[selected_indices].copy()
        # Initialize 'is_starter' as False; you can add logic to determine starters if needed
        optimal_team['is_starter'] = False

        # Example: Assign starters based on highest weighted_score within each position
        for pos in positions.keys():
            pos_players = optimal_team[optimal_team['element_type'] == pos]
            if pos == 1:  # Goalkeepers: 1 starter
                starter = pos_players.nlargest(1, 'weighted_score').index
            elif pos == 2:  # Defenders: 3 starters
                starter = pos_players.nlargest(3, 'weighted_score').index
            elif pos == 3:  # Midfielders: 3 starters
                starter = pos_players.nlargest(3, 'weighted_score').index
            elif pos == 4:  # Forwards: 1 starter
                starter = pos_players.nlargest(1, 'weighted_score').index
            optimal_team.loc[starter, 'is_starter'] = True

        return optimal_team
    else:
        logging.error(f"Optimization failed: {LpStatus[prob.status]}")
        return pd.DataFrame(columns=players_df.columns)

def get_optimal_team(current_gameweek, budget, weights):
    """Get optimal team for the specified gameweek."""
    logging.info(f"Fetching data and optimizing team for gameweek {current_gameweek}.")
    players_df = prepare_data()

    # For simplicity, assuming df_train and df_predict are derived from players_df
    # Adjust according to your actual data structure
    df_train = players_df.copy()  # Placeholder; adjust based on actual training data
    df_predict = players_df.copy()  # Placeholder; adjust based on actual prediction data

    # Aggregate gameweek data
    current_agg, next_five_weeks_agg = aggregate_gameweek_data(df_train, current_gameweek)

    # Train and predict
    predicted_df, _ = train_and_predict(current_agg, next_five_weeks_agg, players_df)

    # Proceed with optimization
    optimal_team = optimize_team(predicted_df, budget, weights)

    return optimal_team

# Print optimal team layout
def print_optimal_team_layout(df):
    logging.info("Printing the optimal team layout.")

    # Ensure 'is_starter' column exists
    if 'is_starter' not in df.columns:
        logging.warning("'is_starter' column not found. Assuming all are starters.")
        df['is_starter'] = True

    # Separate starters and bench
    starters = df[df['is_starter'] == True]
    bench = df[df['is_starter'] == False]

    # Format player names with predicted performance
    def format_names(sub_df):
        if sub_df.empty:
            return []
        # Fill NaN in 'first_name' and 'second_name' to prevent errors
        sub_df = sub_df[['first_name', 'second_name', 'predicted_performance']].fillna({'first_name': '', 'second_name': '', 'predicted_performance': 0.0})
        return sub_df.apply(lambda x: f"{x['first_name']} {x['second_name']} (Predicted: {x['predicted_performance']:.1f})", axis=1).tolist()

    # Get lists of players per position with predicted scores
    gks_starters = format_names(starters[starters['element_type'] == 1])
    defs_starters = format_names(starters[starters['element_type'] == 2])
    mids_starters = format_names(starters[starters['element_type'] == 3])
    fwds_starters = format_names(starters[starters['element_type'] == 4])

    gks_bench = format_names(bench[bench['element_type'] == 1])
    defs_bench = format_names(bench[bench['element_type'] == 2])
    mids_bench = format_names(bench[bench['element_type'] == 3])
    fwds_bench = format_names(bench[bench['element_type'] == 4])

    # Print formatted output
    print("\n--- Optimal Team Layout ---\n")

    print("Starters:")
    print("Goalkeepers:        {}".format(', '.join(gks_starters) if gks_starters else 'None'))
    print("Defenders:          {}".format(', '.join(defs_starters) if defs_starters else 'None'))
    print("Midfielders:        {}".format(', '.join(mids_starters) if mids_starters else 'None'))
    print("Forwards:           {}".format(', '.join(fwds_starters) if fwds_starters else 'None'))

    print("\nBench:")
    print("Goalkeepers:        {}".format(', '.join(gks_bench) if gks_bench else 'None'))
    print("Defenders:          {}".format(', '.join(defs_bench) if defs_bench else 'None'))
    print("Midfielders:        {}".format(', '.join(mids_bench) if mids_bench else 'None'))
    print("Forwards:           {}".format(', '.join(fwds_bench) if fwds_bench else 'None'))

    total_value = df['now_cost'].sum()
    print("\nTotal Value: {:.1f}M".format(total_value))

    logging.info(f"Total team value: {total_value}M")


def export_all_players_to_csv(players_df, file_name="all_players.csv"):
    logging.info(f"Exporting all players to {file_name}.")

    # Calculate points per million if not already done
    if 'points_per_million' not in players_df.columns:
        if 'predicted_performance' in players_df.columns and 'now_cost' in players_df.columns:
            players_df['points_per_million'] = players_df['predicted_performance'] / players_df['now_cost']
            players_df['points_per_million'] = players_df['points_per_million'].astype('float32')
            logging.info("Calculated 'points_per_million' for all players.")
        else:
            logging.error("Cannot calculate 'points_per_million' as 'predicted_performance' or 'now_cost' is missing.")
            raise KeyError("Missing 'predicted_performance' or 'now_cost' column.")
    else:
        players_df['points_per_million'] = players_df['points_per_million'].astype('float32')

    # Select relevant columns
    columns_to_export = ['first_name', 'second_name', 'now_cost', 'predicted_performance', 'total_points', 'points_per_million']

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

def team_optimization(weights):
    """Main workflow for fetching data, training the model, and optimizing team."""
    logging.info("Starting the FPL optimization process.")
    current_gameweek = get_current_gameweek()

    # Fetch data and prepare
    players_df = prepare_data()

    # Placeholder: Define how df_train and df_predict are derived
    # Adjust according to your actual data structure
    df_train = players_df.copy()  # Placeholder
    df_predict = players_df.copy()  # Placeholder

    # Aggregate gameweek data
    current_agg, next_five_weeks_agg = aggregate_gameweek_data(df_train, current_gameweek)

    # Train and predict
    predicted_df, _ = train_and_predict(current_agg, next_five_weeks_agg, players_df)

    # Proceed with optimization
    optimal_team = optimize_team(predicted_df, budget, weights)

    # Save and display results
    if not optimal_team.empty:
        optimal_team.to_csv('optimal_team.csv', index=False)
        logging.info("Optimal team saved to 'optimal_team.csv'.")
        print_optimal_team_layout(optimal_team)
    else:
        logging.warning("No optimal team was selected.")

    # Export all players to CSV sorted by points_per_million
    export_all_players_to_csv(players_df)

    return True, optimal_team.to_dict(orient='records')

# Example usage:
if __name__ == "__main__":
    # Define user weights as a list: [total_points_weight, form_weight, minutes_weight]
    user_weights = [40, 30, 30]  # Example weights

    # Run team optimization
    success, optimal_team = team_optimization(user_weights)

    if success:
        logging.info("Team optimization completed successfully.")
    else:
        logging.error("Team optimization failed.")
