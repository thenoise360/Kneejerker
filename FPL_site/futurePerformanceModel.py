#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FPL Optimization Code - Full Version with Position-Specific Scoring
-------------------------------------------------------------------
Key Points:
1) We keep columns like 'goals_scored','assists','clean_sheets','goals_conceded',
   'own_goals','penalties_saved','penalties_missed','yellow_cards','red_cards','saves','bonus',
   'bps','influence','creativity','threat','ict_index', etc. for predictions.
2) We use compute_player_points(row) for position-specific scoring, but do not drop columns.
3) compute_player_form uses a 2.0 -> 1.8 -> 1.6 -> 1.4 -> 1.2 weighting for last 5 matches.
4) The code merges everything without discarding crucial numeric columns for the model.
"""

import pandas as pd
import os
from sqlalchemy import create_engine
import pymysql
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from pulp import LpProblem, LpVariable, LpMaximize, lpSum, LpStatus, LpBinary
import requests
import unicodedata
import logging
import gc  # Garbage Collector
from sklearn.model_selection import GridSearchCV
from FPL_site.config import current_config
import numpy as np
from tqdm import tqdm

# Setup logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

#################################################
#           Utility & Data Optimization         #
#################################################

def optimize_data_types(df):
    """Optimize DataFrame memory usage by converting float64/int64 -> float32/int32."""
    float_cols = df.select_dtypes(include=['float64']).columns
    int_cols   = df.select_dtypes(include=['int64']).columns
    for col in float_cols:
        df[col] = df[col].astype('float32')
    for col in int_cols:
        df[col] = df[col].astype('int32')
    return df

def optimize_categories(df, category_columns):
    """Convert repetitive string/object columns to 'category' dtype."""
    for col in category_columns:
        if col in df.columns and df[col].dtype == 'object':
            df[col] = df[col].astype('category')
    return df

#################################################
#        Global Config & Constants              #
#################################################

budget = 100
HOST = current_config.HOST
USER = current_config.USER
PASSWORD = current_config.PASSWORD
DB = current_config.DATABASE

season = "2023_2024"
season_start = 2024

# Weighted array for last 5 GWs: newest=2.0 => older=1.8 => 1.6 => 1.4 => 1.2
form_weights = [2.0, 1.8, 1.6, 1.4, 1.2, 1.0, 0.8, 0.6, 0.4, 0.2]

#################################################
#               Data Fetching                   #
#################################################

def fetch_mysql_data(query, database, chunksize=None):
    """
    Optionally read in chunks with a progress bar (tqdm).
    """
    logging.info(f"Fetching data from {database} with query: {query}")
    engine = create_engine(f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}/{database}')
    
    if chunksize:
        df_list = []
        for chunk in tqdm(pd.read_sql(query, engine, chunksize=chunksize), desc="Reading MySQL in chunks"):
            chunk = optimize_data_types(chunk)
            df_list.append(chunk)
        df = pd.concat(df_list, ignore_index=True)
    else:
        df = pd.read_sql(query, engine)
        df = optimize_data_types(df)

    logging.info(f"Fetched {len(df)} rows from {database}.")
    return df

def get_current_gameweek():
    """Fetch current gameweek from the official FPL API."""
    logging.info("Fetching current gameweek from the bootstrap-static API.")
    try:
        response = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
        response.raise_for_status()
        data = response.json()
        events = data.get('events', [])
        current_gw = None
        for e in events:
            if e.get('is_current', False):
                current_gw = e.get('id', None)
                break
        if current_gw is not None:
            logging.info(f"Current gameweek determined to be: {current_gw}")
            return current_gw
        else:
            logging.error("Current gameweek not found in API response.")
            raise ValueError("Current gameweek not found.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed fetching current gameweek: {e}")
        raise

#################################################
#         Data Cleaning & Preparation           #
#################################################

def clean_player_names(players_df):
    """Normalize player names by removing special characters."""
    logging.info("Cleaning player names.")
    players_df.loc[:, 'second_name'] = players_df['second_name'].apply(
        lambda x: unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode('utf-8')
                  if isinstance(x, str) else x
    )
    return players_df

def compute_player_points(row):
    """
    Position-specific FPL scoring for a single match event row:
      - element_type (1=GK,2=DEF,3=MID,4=FWD)
      - includes columns like goals_scored, assists, clean_sheets, etc.
    """
    pos = row.get('element_type', 0)
    points = 0.0

    # (1) Base appearance:
    minutes_played = row.get('minutes', 0)
    if minutes_played >= 60:
        points += 2
    else:
        points += 1

    # (2) Goals scored:
    goals = row.get('goals_scored', 0)
    if pos in [1, 2]:    # GK or DEF => 6 points
        points += goals * 6
    elif pos == 3:       # MID => 5
        points += goals * 5
    elif pos == 4:       # FWD => 4
        points += goals * 4

    # (3) Assists => +3
    assists = row.get('assists', 0)
    points += assists * 3

    # (4) Clean sheets => GK/DEF=4, MID=1, FWD=0
    cs = row.get('clean_sheets', 0)
    if cs > 0:
        if pos in [1, 2]:
            points += 4
        elif pos == 3:
            points += 1

    # (5) Own goals => -2
    own_goals = row.get('own_goals', 0)
    points += own_goals * (-2)

    # (6) Penalties => saved=+5, missed=-2
    pens_saved = row.get('penalties_saved', 0)
    pens_missed = row.get('penalties_missed', 0)
    points += (pens_saved * 5) + (pens_missed * -2)

    # (7) Cards => yellow=-1, red=-3
    yellows = row.get('yellow_cards', 0)
    reds = row.get('red_cards', 0)
    points += (yellows * -1) + (reds * -3)

    # (8) Bonus => direct from 'bonus' col
    bonus_pts = row.get('bonus', 0)
    points += bonus_pts

    # (9) GK/DEF => every 2 goals_conceded => -1
    if pos in [1, 2]:
        gc = row.get('goals_conceded', 0)
        points -= (gc // 2)

    return float(points)

def compute_player_form(events_df, player_id, current_gameweek, num_gameweeks=10):
    recent_events = events_df[
        (events_df['id'] == player_id)
        & (events_df['gameweek'] > current_gameweek - num_gameweeks)
        & (events_df['gameweek'] <= current_gameweek)
    ]
    if recent_events.empty:
        return 0.0

    # Sort newest first
    recent_events = recent_events.sort_values('gameweek', ascending=False)

    # Keep at most 5 matches
    recent_events = recent_events.head(10)

    num_matches = len(recent_events)
    chosen_weights = form_weights[:num_matches]  # e.g. [2.0,1.8,...] up to the count

    recent_events.loc[:, 'weight'] = chosen_weights

    # Use position-based scoring
    recent_events.loc[:, 'points'] = recent_events.apply(compute_player_points, axis=1)

    weighted_sum = (recent_events['points'] * recent_events['weight']).sum()
    total_weight = recent_events['weight'].sum()
    form_value = weighted_sum / total_weight if total_weight != 0 else 0.0
    return float(form_value)


def validate_players_df(players_df):
    required = [
        'id', 'first_name', 'second_name', 'element_type', 'now_cost',
        'minutes', 'total_points', 'form', 'predicted_performance', 'team',
        'starts'
    ]
    missing = [col for col in required if col not in players_df.columns]
    if missing:
        logging.error(f"Missing required columns in players_df: {missing}")
        raise KeyError(f"Missing columns: {missing}")

    numeric = ['now_cost','minutes','total_points','form','predicted_performance','starts']
    for col in numeric:
        if not pd.api.types.is_numeric_dtype(players_df[col]):
            players_df.loc[:, col] = pd.to_numeric(players_df[col], errors='coerce').fillna(0).astype('float32')
            logging.info(f"Converted '{col}' to numeric in players_df.")

def prepare_data():
    """Fetch data from MySQL, clean, filter, compute form, etc."""
    logging.info("Preparing data by fetching events, fixtures, and player data.")
    current_gw = get_current_gameweek()

    # events
    events_query = f"SELECT * FROM {DB}.events_elements;"
    events_df = fetch_mysql_data(events_query, DB)

    # fixtures
    fixtures_query = f"SELECT * FROM {DB}.elementsummary_fixtures;"
    fixtures_df = fetch_mysql_data(fixtures_query, DB)

    # players
    players_query = (
        f"SELECT id, first_name, second_name, web_name, element_type, now_cost, minutes, "
        f"chance_of_playing_next_round, goals_scored, assists, clean_sheets, goals_conceded, "
        f"own_goals, penalties_saved, penalties_missed, yellow_cards, red_cards, saves, bonus, "
        f"bps, influence, creativity, threat, ict_index, starts, expected_goals, expected_assists, "
        f"expected_goal_involvements, expected_goals_conceded, total_points, in_dreamteam, team_code, team "
        f"FROM {DB}.bootstrapstatic_elements "
        f"WHERE Year_start = {season_start};"
    )
    players_df = fetch_mysql_data(players_query, DB)

    logging.info(f"Player data contains {players_df.shape[1]} columns and {players_df.shape[0]} rows.")
    logging.info(f"Columns in players_df: {players_df.columns.tolist()}")

    players_df = optimize_categories(players_df, ['team'])
    players_df = clean_player_names(players_df)

    # Convert now_cost -> float then /10
    players_df.loc[:, 'now_cost'] = pd.to_numeric(players_df['now_cost'], errors='coerce').astype('float32') / 10
    
    if 'chance_of_playing_next_round' in players_df.columns:
        # Fill nulls with 100%
        players_df['chance_of_playing_next_round'] = (
            players_df['chance_of_playing_next_round']
            .fillna(100)
            .astype('float32')  # match numeric dtype
        )
        logging.info("Set missing 'chance_of_playing_next_round' to 100%.")
    else:
        logging.warning("'chance_of_playing_next_round' column not found. Cannot set missing to 100%.")

    # If gw <= 1 => can't average
    if current_gw <= 1:
        players_df.loc[:, 'avg_minutes'] = players_df['minutes']
    else:
        players_df.loc[:, 'avg_minutes'] = players_df['minutes'] / (current_gw - 1)

    # Filter
    players_df = players_df[
        (players_df['avg_minutes'] >= 15)
        & (players_df['chance_of_playing_next_round'] >= 50)
    ]
    logging.info(f"Filtered players... Remaining players: {len(players_df)}")

    numeric_cols = [
        'goals_scored','assists','clean_sheets','goals_conceded','own_goals',
        'penalties_saved','penalties_missed','yellow_cards','red_cards',
        'saves','bonus','bps','influence','creativity','threat','ict_index',
        'starts'
    ]
    for col in numeric_cols:
        if col in players_df.columns:
            players_df.loc[:, col] = pd.to_numeric(players_df[col], errors='coerce').fillna(0).astype('float32')
            logging.info(f"Converted column '{col}' to numeric.")
        else:
            logging.warning(f"Column '{col}' not found in players_df; setting to 0.")
            players_df.loc[:, col] = 0.0

    event_numeric = [
        'goals_scored','assists','clean_sheets','goals_conceded','own_goals',
        'penalties_saved','penalties_missed','yellow_cards','red_cards',
        'saves','bonus','bps','influence','creativity','threat','ict_index'
    ]
    for col in event_numeric:
        if col in events_df.columns:
            events_df.loc[:, col] = pd.to_numeric(events_df[col], errors='coerce').fillna(0).astype('float32')
            logging.info(f"Converted column '{col}' in events_df to numeric.")
        else:
            logging.warning(f"Column '{col}' not found in events_df; setting to 0.")
            events_df.loc[:, col] = 0.0

    # Compute form:
    players_df.loc[:, 'form'] = players_df['id'].apply(
        lambda x: compute_player_form(events_df, x, current_gw, num_gameweeks=5)
    )
    logging.info("Computed 'form' for all players.")

    # Ensure predicted_performance
    if 'predicted_performance' not in players_df.columns:
        logging.warning("'predicted_performance' column is missing. Using simple formula.")
        players_df.loc[:, 'predicted_performance'] = (
            players_df['total_points']*0.6 + players_df['form']*0.4
        ).astype('float32')
        logging.info("Computed 'predicted_performance' for all players.")
    else:
        players_df.loc[:, 'predicted_performance'] = pd.to_numeric(
            players_df['predicted_performance'], errors='coerce'
        ).fillna(0).astype('float32')
        logging.info("'predicted_performance' column converted to numeric.")

    validate_players_df(players_df)
    logging.info("players_df validation passed.")

    gc.collect()
    return players_df, events_df, fixtures_df

##################################################
#           Aggregation & Training               #
##################################################

def aggregate_gameweek_data(events_df, current_gameweek, players_df):
    """Aggregate stats for training vs. next 5 GWs. Merge in 'element_type'."""
    current_events = events_df[events_df['gameweek'] <= current_gameweek]
    next5_events   = events_df[
        (events_df['gameweek'] > current_gameweek) &
        (events_df['gameweek'] <= current_gameweek+5)
    ]

    agg_dict = {
        'minutes':'sum','goals_scored':'sum','assists':'sum','clean_sheets':'sum','goals_conceded':'sum',
        'own_goals':'sum','penalties_saved':'sum','penalties_missed':'sum','yellow_cards':'sum',
        'red_cards':'sum','saves':'sum','bonus':'sum','bps':'sum','influence':'sum','creativity':'sum',
        'threat':'sum','ict_index':'sum','expected_goals':'sum','expected_assists':'sum',
        'expected_goal_involvements':'sum','expected_goals_conceded':'sum','total_points':'sum',
        'in_dreamteam':'sum','gameweek':'max','year_start':'max','starts':'sum'
    }
    current_agg = current_events.groupby('id').agg(agg_dict).reset_index().astype({
        'id':'int32','gameweek':'int32','year_start':'int32','starts':'int32'
    })
    next5_agg   = next5_events.groupby('id').agg(agg_dict).reset_index().astype({
        'id':'int32','gameweek':'int32','year_start':'int32','starts':'int32'
    })

    # Merge element_type if needed
    if 'element_type' in players_df.columns:
        current_agg = current_agg.merge(players_df[['id','element_type']], on='id', how='left')
        next5_agg   = next5_agg.merge(players_df[['id','element_type']], on='id', how='left')
    else:
        logging.warning("No 'element_type' in players_df to merge.")

    return current_agg, next5_agg

def train_and_predict(df_train, df_predict, players_df):
    logging.info("Training models for each position.")

    # Drop NaN positions
    df_train = df_train.dropna(subset=['element_type']).copy()
    df_predict = df_predict.dropna(subset=['element_type']).copy()

    df_train['element_type']   = df_train['element_type'].astype('int32')
    df_predict['element_type'] = df_predict['element_type'].astype('int32')

    features = [
        'minutes','goals_scored','assists','clean_sheets','goals_conceded','own_goals',
        'penalties_saved','penalties_missed','yellow_cards','red_cards','saves','bonus','bps',
        'influence','creativity','threat','ict_index','starts','expected_goals','expected_assists',
        'expected_goal_involvements','expected_goals_conceded','total_points','in_dreamteam',
        'year_start','gameweek'
    ]
    # Ensure columns
    for col in features:
        if col not in df_train.columns:
            df_train[col] = 0.0
            logging.warning(f"Column '{col}' missing in df_train; set to 0.")
        if col not in df_predict.columns:
            df_predict[col] = 0.0
            logging.warning(f"Column '{col}' missing in df_predict; set to 0.")

        df_train[col]   = pd.to_numeric(df_train[col], errors='coerce').fillna(0).astype('float32')
        df_predict[col] = pd.to_numeric(df_predict[col], errors='coerce').fillna(0).astype('float32')

    # Impute
    imputer = SimpleImputer(strategy='mean')
    X_train_imputed = imputer.fit_transform(df_train[features])
    X_pred_imputed  = imputer.transform(df_predict[features])

    # Scale
    scaler = StandardScaler()
    X_train_scaled_array = scaler.fit_transform(X_train_imputed).astype('float32')
    X_pred_scaled_array  = scaler.transform(X_pred_imputed).astype('float32')

    # Convert to DataFrame with same indexes
    df_train_scaled = pd.DataFrame(X_train_scaled_array, columns=features, index=df_train.index)
    df_predict_scaled = pd.DataFrame(X_pred_scaled_array, columns=features, index=df_predict.index)

    df_train_scaled['element_type']   = df_train['element_type']
    df_predict_scaled['element_type'] = df_predict['element_type']

    df_predictions = pd.DataFrame()

    # Use a tqdm progress bar for each position
    unique_positions = df_train_scaled['element_type'].unique()
    for position in tqdm(unique_positions, desc="Training each position"):
        logging.info(f"Training model for position: {position}")

        X_train_pos = df_train_scaled.loc[df_train_scaled['element_type']==position, features]
        y_train_pos = df_train.loc[df_train_scaled['element_type']==position, 'total_points'].fillna(0).astype('float32')

        X_pred_pos  = df_predict_scaled.loc[df_predict_scaled['element_type']==position, features]
        pred_idx    = X_pred_pos.index

        n_samples = X_train_pos.shape[0]
        logging.info(f"Number of training samples for position {position}: {n_samples}")

        if n_samples == 0:
            logging.warning(f"No training samples for position {position}. Skipping.")
            continue
        elif n_samples == 1:
            logging.warning(f"Only one training sample for position {position}.")
            rf = RandomForestRegressor(random_state=42, n_estimators=50)
            rf.fit(X_train_pos, y_train_pos)
            predicted_perf = rf.predict(X_pred_pos)
        else:
            rf = RandomForestRegressor(random_state=42, n_estimators=50)
            param_grid = {'max_depth':[10], 'min_samples_split':[2]}
            cv_splits  = min(2, n_samples)
            grid_search = GridSearchCV(
                estimator=rf,
                param_grid=param_grid,
                cv=cv_splits,
                scoring='neg_mean_squared_error',
                n_jobs=1
            )
            try:
                grid_search.fit(X_train_pos, y_train_pos)
            except ValueError as ve:
                logging.error(f"GridSearch failed for pos {position}: {ve}")
                continue
            best_model    = grid_search.best_estimator_
            predicted_perf = best_model.predict(X_pred_pos)

        pos_preds = pd.DataFrame({
            'id': df_predict.loc[pred_idx, 'id'].values,
            'predicted_performance': predicted_perf.astype('float32'),
            'element_type': position,
            'total_points': df_predict.loc[pred_idx, 'total_points'].values.astype('float32')
        })
        # Merge 'form', 'minutes' from players_df if needed
        pos_preds = pd.merge(pos_preds, players_df[['id','form']], on='id', how='left')
        pos_preds = pd.merge(pos_preds, players_df[['id','minutes']], on='id', how='left')

        df_predictions = pd.concat([df_predictions, pos_preds], ignore_index=True)

        del X_train_pos, y_train_pos, X_pred_pos
        gc.collect()

    logging.info("Prediction completed for all positions.")
    return df_predictions, pd.DataFrame()  # skip feature importances

##################################################
#             Team Optimization Code             #
##################################################

def check_sufficient_players(players_df):
    pos_counts = players_df['element_type'].value_counts()
    required   = {1:2, 2:5, 3:5, 4:3}
    for pos, needed in required.items():
        if pos_counts.get(pos, 0) < needed:
            logging.error(f"Not enough players for pos {pos}. Have {pos_counts.get(pos,0)}, need {needed}")
            return False
    return True

def optimize_team(players_df, budget, weights):
    logging.info(f"Optimizing team with budget={budget}M, weights={weights}")
    if not isinstance(weights, list) or len(weights)!=3:
        raise ValueError("Weights must be [points_weight, form_weight, minutes_weight].")

    try:
        wt_points = float(weights[0]) / 100
        wt_form   = float(weights[1]) / 100
        wt_mins   = float(weights[2]) / 100
    except (ValueError,TypeError) as e:
        logging.error(f"Converting weights to float failed: {e}")
        raise

    if not check_sufficient_players(players_df):
        logging.warning("Not enough players to meet formation constraints.")
        return pd.DataFrame(columns=players_df.columns)

    logging.info(players_df[players_df['second_name'].str.contains('Salah', na=False)])

    required_cols = ['now_cost','total_points','form','minutes','predicted_performance']
    for col in required_cols:
        if col not in players_df.columns:
            logging.error(f"Required col '{col}' missing in players_df.")
            raise KeyError(f"Required col '{col}' missing.")
        players_df.loc[:, col] = players_df[col].replace([np.inf, -np.inf], np.nan)
        med = players_df[col].median()
        players_df.loc[:, col] = players_df[col].fillna(med).astype('float32')

    total_wt = wt_points + wt_form + wt_mins
    if total_wt == 0:
        raise ValueError("Sum of weights = 0.")

    w_pts = wt_points / total_wt
    w_frm = wt_form   / total_wt
    w_mns = wt_mins   / total_wt

    players_df.loc[:, 'weighted_score'] = (
        players_df['total_points'] * w_pts +
        players_df['form']                  * w_frm +
        players_df['minutes']               * w_mns
    ).astype('float32')

    prob = LpProblem("FPL_Team_Selection", LpMaximize)
    player_vars = LpVariable.dicts("player", players_df.index, cat=LpBinary)

    # Objective
    prob += lpSum(players_df.loc[i,'weighted_score'] * player_vars[i] for i in players_df.index), "Total_Weighted_Score"

    # Budget constraint
    prob += (
        lpSum(players_df.loc[i,'now_cost'] * player_vars[i] for i in players_df.index) <= budget,
        "BudgetConstraint"
    )

    # Squad size
    prob += (
        lpSum(player_vars[i] for i in players_df.index) == 15,
        "SquadSizeConstraint"
    )

    # Positions
    pos_limits = {1:2, 2:5, 3:5, 4:3}
    for pos, limit in pos_limits.items():
        prob += (
            lpSum(player_vars[i] for i in players_df.index if players_df.loc[i,'element_type']==pos) == limit,
            f"Pos_{pos}_limit"
        )

    # Max 3 from same club
    if 'team' in players_df.columns:
        clubs = players_df['team'].unique()
        for club in clubs:
            club_idx = players_df[players_df['team']==club].index
            prob += (
                lpSum(player_vars[i] for i in club_idx) <= 3,
                f"Max_3_{club}"
            )

    prob.solve()

    if LpStatus[prob.status] == 'Optimal':
        logging.info("Optimization successful.")
        chosen_indices = [i for i in players_df.index if player_vars[i].varValue == 1]
        final_team = players_df.loc[chosen_indices].copy()

        # Label bench vs. starters (1 GK, 3 DEF, 5 MID, 2 FWD => 11)
        final_team['is_starter'] = False

        # GK
        gk_players = final_team[final_team['element_type'] == 1]
        if len(gk_players) >= 1:
            gk_idx = gk_players.nlargest(1, 'weighted_score').index
            final_team.loc[gk_idx, 'is_starter'] = True

        # 3 DEF
        def_players = final_team[final_team['element_type'] == 2]
        if len(def_players) >= 3:
            def_idx = def_players.nlargest(3, 'weighted_score').index
            final_team.loc[def_idx, 'is_starter'] = True

        # 5 MID
        mid_players = final_team[final_team['element_type'] == 3]
        if len(mid_players) >= 5:
            mid_idx = mid_players.nlargest(5, 'weighted_score').index
            final_team.loc[mid_idx, 'is_starter'] = True

        # 2 FWD
        fwd_players = final_team[final_team['element_type'] == 4]
        if len(fwd_players) >= 2:
            fwd_idx = fwd_players.nlargest(2, 'weighted_score').index
            final_team.loc[fwd_idx, 'is_starter'] = True

        return final_team
    else:
        logging.error(f"Optimization failed: {LpStatus[prob.status]}")
        return pd.DataFrame(columns=players_df.columns)

###################################################
#       High-Level Orchestration / API            #
###################################################

def print_optimal_team_layout(df):
    logging.info("Printing the optimal team layout.")
    if 'is_starter' not in df.columns:
        df['is_starter'] = True

    starters = df[df['is_starter']]
    bench = df[~df['is_starter']]

    def fmt(sub):
        if sub.empty:
            return []
        sub = sub.fillna({'first_name':'','second_name':'','predicted_performance':0.0})
        return sub.apply(lambda x: f"{x['first_name']} {x['second_name']} (Pred:{x['predicted_performance']:.1f})", axis=1).tolist()

    print("\n--- Optimal Team Layout ---\n")
    gk_starters = fmt(starters[starters['element_type']==1][['first_name','second_name','predicted_performance']])
    df_starters = fmt(starters[starters['element_type']==2][['first_name','second_name','predicted_performance']])
    md_starters = fmt(starters[starters['element_type']==3][['first_name','second_name','predicted_performance']])
    fw_starters = fmt(starters[starters['element_type']==4][['first_name','second_name','predicted_performance']])

    gk_bench = fmt(bench[bench['element_type']==1][['first_name','second_name','predicted_performance']])
    df_bench = fmt(bench[bench['element_type']==2][['first_name','second_name','predicted_performance']])
    md_bench = fmt(bench[bench['element_type']==3][['first_name','second_name','predicted_performance']])
    fw_bench = fmt(bench[bench['element_type']==4][['first_name','second_name','predicted_performance']])

    print("Starters:")
    print(f"Goalkeepers:  {', '.join(gk_starters) if gk_starters else 'None'}")
    print(f"Defenders:    {', '.join(df_starters) if df_starters else 'None'}")
    print(f"Midfielders:  {', '.join(md_starters) if md_starters else 'None'}")
    print(f"Forwards:     {', '.join(fw_starters) if fw_starters else 'None'}")

    print("\nBench:")
    print(f"Goalkeepers:  {', '.join(gk_bench) if gk_bench else 'None'}")
    print(f"Defenders:    {', '.join(df_bench) if df_bench else 'None'}")
    print(f"Midfielders:  {', '.join(md_bench) if md_bench else 'None'}")
    print(f"Forwards:     {', '.join(fw_bench) if fw_bench else 'None'}")

    total_val = df['now_cost'].sum()
    print(f"\nTotal Value: {total_val:.1f}M")
    logging.info(f"Total team value: {total_val:.1f}M")

def export_all_players_to_csv(players_df, fname="all_players.csv"):
    logging.info(f"Exporting all players to {fname}.")
    if 'points_per_million' not in players_df.columns:
        if 'predicted_performance' in players_df.columns and 'now_cost' in players_df.columns:
            players_df.loc[:, 'points_per_million'] = players_df.apply(
                lambda x: x['predicted_performance']/x['now_cost'] if x['now_cost']>0 else 0,
                axis=1
            ).astype('float32')
        else:
            raise KeyError("Cannot create 'points_per_million' without 'predicted_performance' or 'now_cost'.")

    cols_needed = ['first_name','second_name','now_cost','predicted_performance','total_points','points_per_million']
    missing = [c for c in cols_needed if c not in players_df.columns]
    if missing:
        logging.error(f"Missing columns for CSV: {missing}")
        raise KeyError(f"Missing {missing} for CSV.")

    sorted_df = players_df[cols_needed].sort_values('points_per_million', ascending=False)
    sorted_df.to_csv(fname, index=False)
    logging.info(f"All players exported to {fname} sorted by points_per_million desc.")

############################################
#        Final team_optimization()         #
############################################

def team_optimization(weights):
    """
    Main workflow:
    1) prepare_data -> (players_df, events_df, fixtures_df)
    2) aggregate_gameweek_data -> (current_agg, next_five_agg)
    3) train_and_predict -> predicted_df
    4) aggregate predicted_df by id so each player is single-row
    5) merge aggregated preds into players_df
    6) run optimize_team
    7) print/export
    """
    try:
        logging.info("Starting the FPL optimization process.")
        current_gameweek = get_current_gameweek()

        players_df, events_df, fixtures_df = prepare_data()
        current_agg, next_five_weeks_agg = aggregate_gameweek_data(events_df, current_gameweek, players_df)

        # Train/predict
        predicted_df, _ = train_and_predict(current_agg, next_five_weeks_agg, players_df)
        logging.info(f"Predicted df columns: {predicted_df.columns.tolist()}")

        logging.info(predicted_df[predicted_df['id'] == 328])

        # If 'predicted_performance' already in players_df, drop it so we can merge new
        if 'predicted_performance' in players_df.columns:
            players_df.drop(columns=['predicted_performance'], inplace=True)
            logging.info("Dropped old 'predicted_performance' from players_df.")

        # Aggregation to avoid 1.5 million row merges:
        agg_preds = (
            predicted_df
            .groupby('id', as_index=False)
            .agg({'predicted_performance': 'mean'})
            .rename(columns={'predicted_performance': 'pred_perf_agg'})
        )
        logging.info(f"After aggregation, agg_preds shape: {agg_preds.shape}")

        # Merge single-row-per-id
        merged_df = pd.merge(players_df, agg_preds, on='id', how='left')
        merged_df['predicted_performance'] = merged_df['pred_perf_agg'].fillna(0).astype('float32')
        merged_df.drop(columns=['pred_perf_agg'], inplace=True)

        # ensure no duplicates in final
        merged_df = merged_df.drop_duplicates(subset='id', keep='last').reset_index(drop=True)

        logging.info(f"Merged DataFrame shape after combine: {merged_df.shape}")
        logging.info(f"Merged DataFrame columns: {merged_df.columns.tolist()}")

        # Optimize the final 15
        optimal_team = optimize_team(merged_df, budget, weights)
        if not optimal_team.empty:
            optimal_team.to_csv('optimal_team.csv', index=False)
            logging.info("Optimal team saved to 'optimal_team.csv'.")
            print_optimal_team_layout(optimal_team)
        else:
            logging.warning("No optimal team was selected.")

        # Export all players for reference
        export_all_players_to_csv(merged_df)

        return True, optimal_team.to_dict(orient='records')
    except Exception as e:
        logging.error(f"Team optimization failed: {e}")
        return False, {}
