import pandas as pd
import mysql.connector
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from scipy.optimize import linprog
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# MySQL connection configuration
config = {
    'user': 'jackbegley',
    'password': 'Athome19369*',
    'host': 'localhost',
}

# Fetch data from MySQL
def fetch_mysql_data(query, database):
    connection = mysql.connector.connect(**config, database=database)
    df = pd.read_sql(query, connection)
    connection.close()
    return df

# Fetch events data
events_query = "SELECT * FROM 2023_2024_events.elements;"
events_df = fetch_mysql_data(events_query, '2023_2024_events')

# Fetch fixtures data
fixtures_query = "SELECT * FROM 2023_2024_elementsummary.fixtures;"
fixtures_df = fetch_mysql_data(fixtures_query, '2023_2024_elementsummary')

# Aggregate fixture difficulty by player
fixture_difficulty = fixtures_df.groupby('id').agg({
    'difficulty': 'mean'  # Use mean difficulty as a feature
}).reset_index()

# Fetch player data with 'element_type' column included
players_query = "SELECT id, second_name, element_type, now_cost FROM 2023_2024_bootstrapstatic.elements;"
players_df = fetch_mysql_data(players_query, '2023_2024_bootstrapstatic')

# Adjust player costs
players_df['now_cost'] = players_df['now_cost'] / 10

# Diagnostic check after fetching data
print("Events DataFrame columns:", events_df.columns)
print("Fixtures DataFrame columns:", fixtures_df.columns)
print("Players DataFrame columns:", players_df.columns)

# Check for missing data
print("\nMissing data after fetching:")
print(players_df.isnull().sum())

# Check data types
print("\nData types after fetching:")
print(players_df.dtypes)

# Ensure unique player IDs
print("\nUnique player IDs after fetching:")
print(players_df['id'].nunique(), len(players_df))

# Check for missing 'gameweek' column
if 'gameweek' not in events_df.columns:
    raise KeyError("The 'gameweek' column is missing from the events dataframe.")

# Fetch historical events data (for training)
historical_events_query_2021 = "SELECT * FROM 2021_2022_events.elements;"
historical_events_df_2021 = fetch_mysql_data(historical_events_query_2021, '2021_2022_events')

historical_events_query_2022 = "SELECT * FROM 2022_2023_events.elements;"
historical_events_df_2022 = fetch_mysql_data(historical_events_query_2022, '2022_2023_events')

historical_events_df = pd.concat([historical_events_df_2021, historical_events_df_2022], ignore_index=True)

# Define a function to predict future performance using a machine learning model
def train_and_predict(df_train, df_predict):
    features = ['minutes', 'goals_scored', 'assists', 'clean_sheets', 'goals_conceded',
                'penalties_saved', 'yellow_cards', 'red_cards', 'saves', 'bonus', 'bps',
                'influence', 'creativity', 'threat', 'ict_index', 'expected_goals',
                'expected_assists', 'expected_goal_involvements', 'expected_goals_conceded']

    # Ensure the necessary columns are present in both dataframes
    missing_features_train = set(features) - set(df_train.columns)
    missing_features_predict = set(features) - set(df_predict.columns)

    if missing_features_train:
        raise KeyError(f"Train DataFrame is missing features: {missing_features_train}")
    if missing_features_predict:
        raise KeyError(f"Predict DataFrame is missing features: {missing_features_predict}")

    # Ensure numeric conversion
    df_train[features] = df_train[features].apply(pd.to_numeric, errors='coerce')
    df_predict[features] = df_predict[features].apply(pd.to_numeric, errors='coerce')

    # Impute missing values
    imputer = SimpleImputer(strategy='mean')
    df_train_imputed = imputer.fit_transform(df_train[features])
    df_predict_imputed = imputer.transform(df_predict[features])

    # Normalize features
    scaler = StandardScaler()
    df_train_imputed = scaler.fit_transform(df_train_imputed)
    df_predict_imputed = scaler.transform(df_predict_imputed)

    # Ensure target does not contain NaN values
    target = df_train['total_points'].fillna(0)

    # Train the model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(df_train_imputed, target)

    # Predict the performance
    df_predict['predicted_performance'] = model.predict(df_predict_imputed)
    return df_predict

def check_sufficient_players(players_df):
    gks = players_df[players_df['element_type'] == 1]
    defs = players_df[players_df['element_type'] == 2]
    mids = players_df[players_df['element_type'] == 3]
    fwds = players_df[players_df['element_type'] == 4]
    
    if len(gks) < 2 or len(defs) < 5 or len(mids) < 5 or len(fwds) < 3:
        print(f"Not enough players to meet the constraints: GKs: {len(gks)}, DEFs: {len(defs)}, MIDs: {len(mids)}, FWDs: {len(fwds)}")
        return False
    return True

# Function to get optimal team for a given gameweek
def get_optimal_team(current_gameweek, budget=90):
    current_events = events_df[events_df['gameweek'] <= current_gameweek]
    next_five_weeks_events = events_df[(events_df['gameweek'] > current_gameweek) & (events_df['gameweek'] <= current_gameweek + 5)]

    current_agg = current_events.groupby('id').agg({
        'minutes': 'sum',
        'goals_scored': 'sum',
        'assists': 'sum',
        'clean_sheets': 'sum',
        'goals_conceded': 'sum',
        'penalties_saved': 'sum',
        'yellow_cards': 'sum',
        'red_cards': 'sum',
        'saves': 'sum',
        'bonus': 'sum',
        'bps': 'sum',
        'influence': 'sum',
        'creativity': 'sum',
        'threat': 'sum',
        'ict_index': 'sum',
        'expected_goals': 'sum',
        'expected_assists': 'sum',
        'expected_goal_involvements': 'sum',
        'expected_goals_conceded': 'sum',
        'total_points': 'sum'
    }).reset_index()

    next_five_weeks_agg = next_five_weeks_events.groupby('id').agg({
        'minutes': 'sum',
        'goals_scored': 'sum',
        'assists': 'sum',
        'clean_sheets': 'sum',
        'goals_conceded': 'sum',
        'penalties_saved': 'sum',
        'yellow_cards': 'sum',
        'red_cards': 'sum',
        'saves': 'sum',
        'bonus': 'sum',
        'bps': 'sum',
        'influence': 'sum',
        'creativity': 'sum',
        'threat': 'sum',
        'ict_index': 'sum',
        'expected_goals': 'sum',
        'expected_assists': 'sum',
        'expected_goal_involvements': 'sum',
        'expected_goals_conceded': 'sum',
        'total_points': 'sum'
    }).reset_index()

    current_merged = pd.merge(current_agg, players_df[['id', 'element_type', 'now_cost']], on='id', how='left')
    current_merged = pd.merge(current_merged, fixture_difficulty, on='id', how='left')

    predicted_df = train_and_predict(current_merged, next_five_weeks_agg)
    predicted_df = pd.merge(predicted_df, next_five_weeks_events[['id', 'total_points']], on='id', how='left', suffixes=('', '_actual'))
    predicted_df = pd.merge(predicted_df, players_df[['id', 'second_name', 'element_type', 'now_cost']], on='id', how='left')

    # Filter out players not in the current season
    current_season_players = players_df['id'].unique()
    predicted_df = predicted_df[predicted_df['id'].isin(current_season_players)]

    # Final diagnostic check before optimization
    print("\nMissing data before optimization:")
    print(predicted_df.isnull().sum())

    print("\nData types before optimization:")
    print(predicted_df.dtypes)

    print("\nRange of values before optimization:")
    print(predicted_df.describe())

    print("\nUnique player IDs before optimization:")
    print(predicted_df['id'].nunique(), len(predicted_df))

    # Proceed with optimization
    optimal_team = optimize_team(predicted_df, budget)
    if optimal_team.empty:
        print("No optimal team could be selected due to constraints.")
    else:
        print_optimal_team_layout(optimal_team)
        
    print(optimal_team[['second_name', 'element_type', 'now_cost', 'predicted_performance']])
    return optimal_team


def check_feasibility(players_df, budget):
    # Check if players_df is not empty
    if players_df.empty:
        return "The players dataframe is empty."

    # Check if there are enough players in each position
    positions = [1, 2, 3, 4]
    position_counts = {pos: players_df[players_df['element_type'] == pos].shape[0] for pos in positions}
    
    required_counts = {1: 2, 2: 5, 3: 5, 4: 3}
    
    for pos, count in required_counts.items():
        if position_counts[pos] < count:
            return f"Not enough players in position {pos}: Required {count}, Found {position_counts[pos]}"
    
    # Check if there are players with costs within the budget
    if (players_df['now_cost'] > budget).all():
        return "No players are within the budget."
    
    # Group players by position and sort by cost
    gk_players = players_df[players_df['element_type'] == 1].sort_values(by='now_cost')
    def_players = players_df[players_df['element_type'] == 2].sort_values(by='now_cost')
    mid_players = players_df[players_df['element_type'] == 3].sort_values(by='now_cost')
    fwd_players = players_df[players_df['element_type'] == 4].sort_values(by='now_cost')

    # Select the minimum cost players for each position
    min_cost_gk = gk_players.head(2)
    min_cost_def = def_players.head(5)
    min_cost_mid = mid_players.head(5)
    min_cost_fwd = fwd_players.head(3)

    min_cost_gk_sum = min_cost_gk['now_cost'].sum()
    min_cost_def_sum = min_cost_def['now_cost'].sum()
    min_cost_mid_sum = min_cost_mid['now_cost'].sum()
    min_cost_fwd_sum = min_cost_fwd['now_cost'].sum()

    # Calculate the total minimum cost
    total_min_cost = min_cost_gk_sum + min_cost_def_sum + min_cost_mid_sum + min_cost_fwd_sum

    # Check if the total minimum cost is within the budget
    feasible = total_min_cost <= budget

    min_cost_players = pd.concat([min_cost_gk, min_cost_def, min_cost_mid, min_cost_fwd])

    return {
        'position_counts': position_counts,
        'min_cost_gk': min_cost_gk_sum,
        'min_cost_def': min_cost_def_sum,
        'min_cost_mid': min_cost_mid_sum,
        'min_cost_fwd': min_cost_fwd_sum,
        'total_min_cost': total_min_cost,
        'feasible': feasible,
        'min_cost_players': min_cost_players[['second_name', 'element_type', 'now_cost']]
    }

def optimize_team(players_df, budget):
    if not check_sufficient_players(players_df):
        return pd.DataFrame(columns=players_df.columns)

    # Temporarily increase budget to see if it resolves the infeasibility
    budget += 10  # Increase budget by 10 units as an example

    # Remove duplicates
    players_df = players_df.drop_duplicates(subset=['id'])

    # Objective function: maximize predicted performance
    c = -players_df['predicted_performance'].values

    # Positional constraints
    GK_constraint = (players_df['element_type'] == 1).astype(int).values
    DEF_constraint = (players_df['element_type'] == 2).astype(int).values
    MID_constraint = (players_df['element_type'] == 3).astype(int).values
    FWD_constraint = (players_df['element_type'] == 4).astype(int).values

    # Bounds: Each player can be either selected (1) or not selected (0)
    bounds = [(0, 1) for _ in range(len(players_df))]

    # Constraints: total cost must be less than or equal to budget and positional constraints
    A_eq = np.array([
        players_df['now_cost'].values, 
        GK_constraint, 
        DEF_constraint, 
        MID_constraint, 
        FWD_constraint
    ])
    b_eq = np.array([budget, 2, 5, 5, 3])

    print("Objective function coefficients (c):", c)
    print("Cost constraints (A_eq[0]):", A_eq[0])
    print("Goalkeeper constraints (A_eq[1]):", A_eq[1])
    print("Defender constraints (A_eq[2]):", A_eq[2])
    print("Midfielder constraints (A_eq[3]):", A_eq[3])
    print("Forward constraints (A_eq[4]):", A_eq[4])
    print("Bounds:", bounds)
    print("b_eq:", b_eq)

    # Solve the linear programming problem
    result = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')

    if result.success:
        # Get the selected players
        selected_indices = [i for i, x in enumerate(result.x) if x > 0.5]
        selected_players = players_df.iloc[selected_indices]
    else:
        print("Optimization did not find a solution. Reason:", result.message)
        selected_players = pd.DataFrame(columns=players_df.columns)

    return selected_players

# Print teams in console
def print_optimal_team_layout(df):
    if df.empty:
        print("No optimal team could be selected.")
        return

    df = df.drop_duplicates(subset=['id'])
    gks = df[df['element_type'] == 1]['second_name'].tolist()
    defs = df[df['element_type'] == 2]['second_name'].tolist()
    mids = df[df['element_type'] == 3]['second_name'].tolist()
    fwds = df[df['element_type'] == 4]['second_name'].tolist()

    print("\nList of Goalkeepers:", gks)
    print("List of Defenders:", defs)
    print("List of Midfielders:", mids)
    print("List of Forwards:", fwds)

    # Ensure lists have correct number of players
    if len(gks) < 2:
        print(f"Expected 2 goalkeepers, but got {len(gks)}. Adding placeholders.")
        gks.extend(['None'] * (2 - len(gks)))
    if len(defs) < 5:
        print(f"Expected 5 defenders, but got {len(defs)}. Adding placeholders.")
        defs.extend(['None'] * (5 - len(defs)))
    if len(mids) < 5:
        print(f"Expected 5 midfielders, but got {len(mids)}. Adding placeholders.")
        mids.extend(['None'] * (5 - len(mids)))
    if len(fwds) < 3:
        print(f"Expected 3 forwards, but got {len(fwds)}. Adding placeholders.")
        fwds.extend(['None'] * (3 - len(fwds)))

    print("\nGoalkeepers:        {}        {}".format(gks[0], gks[1]))
    print("\nDefenders:    {}    {}    {}    {}    {}".format(defs[0], defs[1], defs[2], defs[3], defs[4]))
    print("\nMidfielders:    {}    {}    {}    {}    {}".format(mids[0], mids[1], mids[2], mids[3], mids[4]))
    print("\nForwards:      {}      {}      {}".format(fwds[0], fwds[1], fwds[2]))

    total_value = df['now_cost'].sum()
    print("\n               Total Value: {:.1f}\n".format(total_value))

def evaluate_model_by_week(events_df, players_df, initial_budget=100):
    gameweeks = sorted(events_df['gameweek'].unique())
    results = []
    predicted_all_weeks = []
    actual_all_weeks = []

    for current_week in gameweeks[:-1]:
        next_week = current_week + 1

        current_events = events_df[events_df['gameweek'] <= current_week]
        next_five_weeks_events = events_df[(events_df['gameweek'] > current_week) & (events_df['gameweek'] <= current_week + 5)]

        current_agg = current_events.groupby('id').agg({
            'minutes': 'sum',
            'goals_scored': 'sum',
            'assists': 'sum',
            'clean_sheets': 'sum',
            'goals_conceded': 'sum',
            'penalties_saved': 'sum',
            'yellow_cards': 'sum',
            'red_cards': 'sum',
            'saves': 'sum',
            'bonus': 'sum',
            'bps': 'sum',
            'influence': 'sum',
            'creativity': 'sum',
            'threat': 'sum',
            'ict_index': 'sum',
            'expected_goals': 'sum',
            'expected_assists': 'sum',
            'expected_goal_involvements': 'sum',
            'expected_goals_conceded': 'sum',
            'total_points': 'sum'
        }).reset_index()

        next_five_weeks_agg = next_five_weeks_events.groupby('id').agg({
            'minutes': 'sum',
            'goals_scored': 'sum',
            'assists': 'sum',
            'clean_sheets': 'sum',
            'goals_conceded': 'sum',
            'penalties_saved': 'sum',
            'yellow_cards': 'sum',
            'red_cards': 'sum',
            'saves': 'sum',
            'bonus': 'sum',
            'bps': 'sum',
            'influence': 'sum',
            'creativity': 'sum',
            'threat': 'sum',
            'ict_index': 'sum',
            'expected_goals': 'sum',
            'expected_assists': 'sum',
            'expected_goal_involvements': 'sum',
            'expected_goals_conceded': 'sum',
            'total_points': 'sum'
        }).reset_index()

        # Merge dataframes for training and prediction
        current_merged = pd.merge(current_agg, players_df[['id', 'element_type', 'now_cost']], on='id', how='left')
        current_merged = pd.merge(current_merged, fixture_difficulty, on='id', how='left')

        predicted_df = train_and_predict(current_merged, next_five_weeks_agg)
        predicted_df = pd.merge(predicted_df, next_five_weeks_events[['id', 'total_points']], on='id', how='left', suffixes=('', '_actual'))
        predicted_df = pd.merge(predicted_df, players_df[['id', 'second_name', 'element_type', 'now_cost']], on='id', how='left')
        print("\nPredicted DataFrame after merging 'element_type' and 'now_cost':")
        print(predicted_df[['id', 'second_name', 'element_type', 'now_cost', 'predicted_performance']].head())

        top_predicted = predicted_df.loc[predicted_df['predicted_performance'].idxmax()]
        bottom_predicted = predicted_df.loc[predicted_df['predicted_performance'].idxmin()]
        top_actual = predicted_df.loc[predicted_df['total_points'].idxmax()]
        bottom_actual = predicted_df.loc[predicted_df['total_points'].idxmin()]

        results.append({
            'Type': 'Top player - predicted',
            'Player Name': top_predicted['second_name'],
            'Week': next_week,
            'Result': top_predicted['predicted_performance'],
            'Other Result': top_predicted['total_points']
        })
        results.append({
            'Type': 'Bottom player - predicted',
            'Player Name': bottom_predicted['second_name'],
            'Week': next_week,
            'Result': bottom_predicted['predicted_performance'],
            'Other Result': bottom_predicted['total_points']
        })
        results.append({
            'Type': 'Top player - Actual',
            'Player Name': top_actual['second_name'],
            'Week': next_week,
            'Result': top_actual['total_points'],
            'Other Result': top_actual['predicted_performance']
        })
        results.append({
            'Type': 'Bottom player - Actual',
            'Player Name': bottom_actual['second_name'],
            'Week': next_week,
            'Result': bottom_actual['total_points'],
            'Other Result': bottom_actual['predicted_performance']
        })

        # Collect predicted and actual points for box plot
        predicted_all_weeks.append(predicted_df['predicted_performance'].tolist())
        actual_all_weeks.append(predicted_df['total_points'].tolist())

    return pd.DataFrame(results), predicted_all_weeks, actual_all_weeks, gameweeks

def plot_box_plots(predicted_all_weeks, actual_all_weeks, gameweeks):
    data = []

    for i, week in enumerate(gameweeks[:-1]):
        predicted = predicted_all_weeks[i]
        actual = actual_all_weeks[i]
        for pred in predicted:
            data.append((week, pred, 'Predicted'))
        for act in actual:
            data.append((week, act, 'Actual'))

    df = pd.DataFrame(data, columns=['Week', 'Points', 'Type'])

    plt.figure(figsize=(14, 8))
    sns.boxplot(x='Week', y='Points', hue='Type', data=df)
    plt.title('Box Plot of Predicted and Actual Points by Week')
    plt.axhline(y=df[df['Type'] == 'Actual']['Points'].median(), color='blue', linestyle='--', label='Actual Median')
    plt.axhline(y=df[df['Type'] == 'Predicted']['Points'].median(), color='red', linestyle='--', label='Predicted Median')
    plt.legend()
    plt.show()

feasibility_report = check_feasibility(players_df, 100)
print(feasibility_report)

# Evaluate the model week by week and generate the results table
results_df, predicted_all_weeks, actual_all_weeks, gameweeks = evaluate_model_by_week(events_df, players_df)

# Display the results in the console
print(results_df.to_string(index=False))

# Optionally, save the results to a CSV file
results_df.to_csv('predicted_vs_actual_results.csv', index=False)

# Plot the box plots
plot_box_plots(predicted_all_weeks, actual_all_weeks, gameweeks)

print("Evaluation completed")

# Get optimal team for a specified gameweek
current_gameweek = 10  # Example: change to desired gameweek
optimal_team = get_optimal_team(current_gameweek)

# Print detailed player performance
print("\nDetailed Player Performance:")
for index, player in optimal_team.iterrows():
    player_id = player['id']
    predicted_points = player['predicted_performance']
    actual_points = player['total_points']
    print(f"Player: {player['second_name']} | Predicted Points: {predicted_points:.2f} | Actual Points: {actual_points}")

# Save the processed data
optimal_team_data = optimal_team[['second_name', 'element_type', 'predicted_performance', 'now_cost']]
optimal_team_data.to_csv('optimal_team.csv', index=False)

print_optimal_team_layout(optimal_team)

