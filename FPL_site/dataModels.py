import mysql.connector
from mysql.connector import Error
from FPL_site.config import current_config
from FPL_site.genericMethods import unicodeReplace
from datetime import datetime
import requests
import json
import time
import logging
import concurrent.futures

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
    9: '/static/content/Tshirts/plain-skyblue-football-shirt-svgrepo-com.svg', # Coventry City
    56: '/static/content/Tshirts/stripes-white-red-football-shirt-svgrepo-com.svg', # Sunderland
    88: '/static/content/Tshirts/vertical-orange-black-football-shirt-svgrepo-com.svg', # Hull City
    'Unknown': '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg', # Default
}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

host = current_config.HOST
user = current_config.USER
password = current_config.PASSWORD
db = current_config.DATABASE

season = "2025_2026"
season_start = 2026

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
    try:
        response = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
        if response.status_code == 200:
            data = response.json()
            # Find the current gameweek
            current_gw = next((event['id'] for event in data.get('events', []) if event.get('is_current')), None)
            if current_gw:
                return current_gw
            
            # If no current gameweek, check if it's pre-season (next event is 1)
            next_gw = next((event['id'] for event in data.get('events', []) if event.get('is_next')), None)
            if next_gw == 1:
                return 0 # Gameweek 0 represents pre-season
            elif next_gw:
                return next_gw - 1
                
    except Exception as e:
        logger.error(f"Failed to fetch the current gameweek: {e}")
    return 1 # Fallback to 1 if anything fails


# 06.0: live/closed state for the Week tab. `finished` alone isn't a safe
# signal - bonus points and DEFCON can still be revised right up until
# `data_checked` flips, so "closed" requires both.
def get_gameweek_state():
    try:
        response = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
        if response.status_code != 200:
            raise ValueError(f"bootstrap-static returned status {response.status_code}")
        events = response.json().get('events', [])
    except Exception as e:
        logger.error(f"Failed to fetch gameweek state: {e}")
        return {'state': 'none', 'gameweek': None, 'deadline': None}

    now = datetime.utcnow()
    past_deadline = []
    for event in events:
        deadline = event.get('deadline_time')
        if not deadline:
            continue
        try:
            deadline_dt = datetime.strptime(deadline, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            continue
        if deadline_dt <= now:
            past_deadline.append((deadline_dt, event))

    # No gameweek has passed its deadline yet (off-season, pre-Gameweek-1)
    if not past_deadline:
        return {'state': 'none', 'gameweek': None, 'deadline': None}

    # The most recently-passed deadline is the currently-relevant gameweek
    _, current_event = max(past_deadline, key=lambda pair: pair[0])

    state = 'closed' if (current_event.get('finished') and current_event.get('data_checked')) else 'live'

    return {
        'state': state,
        'gameweek': current_event.get('id'),
        'deadline': current_event.get('deadline_time'),
    }


FPL_API = 'https://fantasy.premierleague.com/api'

# A mini-league is realistically a handful to a few dozen friends. Capping
# how many members' live picks get pulled in one poll keeps a large public
# league from turning into hundreds of outbound requests every refresh.
MAX_LEAGUE_MEMBERS_LIVE = 50


# 06.1: per-player live stats for a gameweek, decomposed into base / bonus /
# defensive-contribution points using the live endpoint's own per-fixture
# `explain` breakdown - the same numbers FPL uses to build `total_points`,
# rather than re-deriving the defensive-contribution threshold ourselves.
def get_live_gameweek_stats(gameweek):
    try:
        response = requests.get(f'{FPL_API}/event/{gameweek}/live/', timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch live stats for gameweek {gameweek}: {e}")
        return {}

    stats_by_element = {}
    for element in response.json().get('elements', []):
        stats = element.get('stats', {})
        total_points = stats.get('total_points', 0)
        bonus = stats.get('bonus', 0)

        defensive_contribution_points = 0
        for fixture in element.get('explain', []):
            for stat_line in fixture.get('stats', []):
                if stat_line.get('identifier') == 'defensive_contribution':
                    defensive_contribution_points += stat_line.get('points', 0)

        stats_by_element[element['id']] = {
            'total_points': total_points,
            'bonus': bonus,
            'defensive_contribution_points': defensive_contribution_points,
            # Everything that isn't bonus or the defensive-contribution
            # threshold bonus - goals, assists, cards, clean sheets, minutes, etc.
            'base_points': total_points - bonus - defensive_contribution_points,
        }
    return stats_by_element


# Bonus (and therefore total_points) can still be revised until every
# fixture in the gameweek has finished - this drives the "still settling"
# label on the bonus figure specifically, never on defensive-contribution
# points, which are final for a player as soon as their own match ends.
def get_gameweek_bonus_still_settling(gameweek):
    try:
        response = requests.get(f'{FPL_API}/fixtures/', params={'event': gameweek}, timeout=10)
        response.raise_for_status()
        fixtures = response.json()
    except Exception as e:
        logger.error(f"Failed to fetch fixtures for gameweek {gameweek}: {e}")
        return True  # can't confirm settled - never claim final when unsure

    return any(not fixture.get('finished') for fixture in fixtures)


def get_entry_picks(entry_id, gameweek):
    try:
        response = requests.get(f'{FPL_API}/entry/{entry_id}/event/{gameweek}/picks/', timeout=10)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch picks for entry {entry_id}, gameweek {gameweek}: {e}")
        return None


def compute_live_entry_score(picks_data, live_stats):
    if not picks_data:
        return None

    base_points = bonus_points = defensive_contribution_points = 0
    for pick in picks_data.get('picks', []):
        multiplier = pick.get('multiplier', 0)
        if multiplier <= 0:
            continue
        player_stats = live_stats.get(pick['element'])
        if not player_stats:
            continue
        base_points += player_stats['base_points'] * multiplier
        bonus_points += player_stats['bonus'] * multiplier
        defensive_contribution_points += player_stats['defensive_contribution_points'] * multiplier

    transfer_cost = picks_data.get('entry_history', {}).get('event_transfers_cost', 0)

    return {
        'base_points': base_points,
        'bonus_points': bonus_points,
        'defensive_contribution_points': defensive_contribution_points,
        'transfer_cost': transfer_cost,
        'total': base_points + bonus_points + defensive_contribution_points - transfer_cost,
    }


# The classic leagues this entry has actually joined with other people -
# excludes FPL's system-generated leagues (Overall, country, club,
# gameweek, "Top 1%", etc.), which aren't a "mini-league of friends" and
# are far too large to fetch live standings for.
def get_entry_mini_leagues(entry_id):
    try:
        response = requests.get(f'{FPL_API}/entry/{entry_id}/', timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
    except Exception as e:
        logger.error(f"Failed to fetch entry {entry_id}: {e}")
        return None

    classic_leagues = data.get('leagues', {}).get('classic', [])
    return [
        {'id': league['id'], 'name': league['name']}
        for league in classic_leagues
        if league.get('league_type') == 'x'
    ]


def get_league_standings_entries(league_id, max_entries=MAX_LEAGUE_MEMBERS_LIVE):
    entries = []
    page = 1
    try:
        while len(entries) < max_entries:
            response = requests.get(
                f'{FPL_API}/leagues-classic/{league_id}/standings/',
                params={'page_standings': page},
                timeout=10,
            )
            if response.status_code != 200:
                break
            standings = response.json().get('standings', {})
            entries.extend(standings.get('results', []))
            if not standings.get('has_next'):
                break
            page += 1
    except Exception as e:
        logger.error(f"Failed to fetch standings for league {league_id}: {e}")

    return entries[:max_entries]


# Live rank for one league: standings gives us the member list, then each
# member's current-gameweek picks are combined with the gameweek's live
# stats (fetched once, up front, and passed in) to get a real-time total.
# The live-stats lookup itself is a single shared call, never repeated per
# member - only the inherently-per-entry picks calls run per member, and
# those run concurrently rather than one at a time.
def get_live_league_leaderboard(league_id, league_name, gameweek, live_stats):
    members = get_league_standings_entries(league_id)
    if not members:
        return {'id': league_id, 'name': league_name, 'entries': []}

    def score_member(member):
        picks = get_entry_picks(member['entry'], gameweek)
        score = compute_live_entry_score(picks, live_stats)
        return {
            'entry_id': member['entry'],
            'entry_name': member.get('entry_name'),
            'player_name': member.get('player_name'),
            'live_total': score['total'] if score else None,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        scored = list(executor.map(score_member, members))

    scored = [member for member in scored if member['live_total'] is not None]
    scored.sort(key=lambda member: member['live_total'], reverse=True)
    for rank, member in enumerate(scored, start=1):
        member['rank'] = rank

    return {'id': league_id, 'name': league_name, 'entries': scored}


# 06.1: orchestrates the live score + live leaderboards for one entry.
# Only meaningful while the gameweek is live - callers should have already
# checked get_gameweek_state().
def get_live_gameweek_view(entry_id):
    gw_state = get_gameweek_state()
    if gw_state['state'] != 'live':
        return {'error': 'not_live', 'gw_state': gw_state}

    gameweek = gw_state['gameweek']
    live_stats = get_live_gameweek_stats(gameweek)
    bonus_still_settling = get_gameweek_bonus_still_settling(gameweek)

    my_picks = get_entry_picks(entry_id, gameweek)
    if my_picks is None:
        return {'error': 'invalid_team_id'}

    my_score = compute_live_entry_score(my_picks, live_stats)

    leagues = get_entry_mini_leagues(entry_id) or []
    leaderboards = [
        get_live_league_leaderboard(league['id'], league['name'], gameweek, live_stats)
        for league in leagues
    ]

    return {
        'gameweek': gameweek,
        'bonus_still_settling': bonus_still_settling,
        'my_entry_id': entry_id,
        'my_score': my_score,
        'leaderboards': leaderboards,
    }


def get_players():
    gw = generateCurrentGameweek()
    # 0 is a legitimate, meaningful pre-season value (and also falsy in
    # Python) - only None (a genuine lookup failure) should fall back to 1,
    # otherwise this queries gameweek 1 for data the ingestion job actually
    # wrote under gameweek 0, and get_players() silently returns nothing.
    if gw is None:
        gw = 1
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return []

    try:
        cursor = dbConnect.cursor(dictionary=True)
        # Modified to join with teams table and get element_type (position)
        query = f"""
            SELECT 
                p.id, 
                p.team_code, 
                CONCAT(p.first_name, ' ', p.second_name) AS full_name,
                p.web_name,
                t.name AS team_name,
                p.element_type
            FROM {db}.bootstrapstatic_elements p
            JOIN {db}.bootstrapstatic_teams t ON p.team = t.id
            WHERE p.year_start = {season_start} 
              AND t.year_start = {season_start}
              AND p.gameweek = {gw}
        """
        logger.info(f"Executing query: {query}")
        cursor.execute(query)
        players = cursor.fetchall()
        
        # Map element_type to position string
        positions = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD', 5: 'MGR'}
        for p in players:
            p['position'] = positions.get(p['element_type'], '???')
            # For backward compatibility with script.js (if needed)
            p['team'] = p['team_code']
            
    except Error as e:
        logger.error(f"Error executing query: {e}")
        return []
    finally:
        dbConnect.close()  # Always close the database connection

    return players

def get_players_by_team():
    # Connect to the database
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return {}
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
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return {}
    cursor = dbConnect.cursor(dictionary=True)

    positions = {
        1: 'Goalkeeper',
        2: 'Defender',
        3: 'Midfielder',
        4: 'Forward',
        5: 'Manager'
    }

    cursor.execute(f'''
        SELECT
            MIN(p.id) AS ID,
            p.element_type AS position_id,
            p.first_name AS First_name,
            p.second_name AS Surname
        FROM {db}.bootstrapstatic_elements p
        WHERE p.year_start = {season_start}
        GROUP BY p.first_name, p.second_name, p.element_type
    ''')

    players = cursor.fetchall()
    dbConnect.close()

    positions_dict = {}

    for entry in players:
        position_id = entry.get('position_id')
        position_name = positions.get(position_id, 'Unknown')

        if position_name == 'Unknown':
            logger.warning(f"⚠️ Unknown position_id: {position_id} for {entry['First_name']} {entry['Surname']}")
            continue  # Optional: skip unknowns

        full_name = f"{entry['First_name']} {entry['Surname']}"
        player_id = entry['ID']

        if position_name not in positions_dict:
            positions_dict[position_name] = {}

        if full_name not in positions_dict[position_name]:
            positions_dict[position_name][full_name] = {
                'full_name': full_name,
                'id': player_id,
                'position': position_id
            }

    for position in positions_dict:
        positions_dict[position] = dict(sorted(positions_dict[position].items()))

    return positions_dict

def get_player_net_transfers(player_id):
    # Assuming you have a database connection utility called connect_db
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return None
    cursor = dbConnect.cursor(dictionary=True)
    query = f'SELECT id, (transfers_in_event - transfers_out_event) as net_transfers FROM {db}.bootstrapstatic_elements WHERE id = %s and year_start = {season_start};'
    cursor.execute(query, (player_id,))
    net_transfers = cursor.fetchone()
    dbConnect.close()  # Always close the database connection
    return net_transfers


def get_player_index_scores():
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return []
    cursor = dbConnect.cursor(dictionary=True)

    # generateCurrentGameweek() reflects the live FPL calendar (e.g. 0 during
    # close season), which can be a gameweek this table never stored rows
    # for. Fall back to the latest gameweek actually present so this doesn't
    # silently resolve to zero matching rows (and a NULL/None "Mean" row).
    # 0 is a legitimate, meaningful gameweek (pre-season) and also falsy in
    # Python - `not gameweek` / `x or default` both misfire on it, so this
    # checks explicitly for None instead.
    gameweek = generateCurrentGameweek()
    cursor.execute(f'SELECT COUNT(*) AS c FROM {db}.bootstrapstatic_elements WHERE year_start = {season_start} AND gameweek = {gameweek}')
    has_data_for_gameweek = cursor.fetchone()['c'] > 0
    if gameweek is None or not has_data_for_gameweek:
        cursor.execute(f'SELECT MAX(gameweek) AS max_gw FROM {db}.bootstrapstatic_elements WHERE year_start = {season_start}')
        max_gw = cursor.fetchone()['max_gw']
        gameweek = max_gw if max_gw is not None else 1

    # "Minutes per gameweek so far > 45" identifies regular starters for the
    # Mean row's player pool - meaningless (and a division by zero) at
    # gameweek 0, since nobody has played any minutes yet this pre-season.
    minutes_filter = f"AND (minutes / {gameweek}) > 45" if gameweek > 0 else ""

    query = f'''
    WITH min_max_values AS (
    SELECT 
        MIN((total_points / (now_cost / 10)) * (100 - selected_by_percent)) AS min_points_per_mill_per_perc_not_selected,
        MAX((total_points / (now_cost / 10)) * (100 - selected_by_percent)) AS max_points_per_mill_per_perc_not_selected
    FROM {db}.bootstrapstatic_elements
    WHERE year_start = {season_start}
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
        WHERE year_start = {season_start}
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
        WHERE year_start = {season_start}
        AND gameweek = {gameweek}
        AND element_type IN (1, 2, 3, 4)
        {minutes_filter}
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
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return []
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
    """
    Fetches player ownership data and calculates relative change using the live FPL API.
    """
    try:
        response = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
        if response.status_code != 200:
            logger.error(f"Failed to fetch data from FPL API. Status Code: {response.status_code}")
            return {"error": "Failed to fetch data from external API."}, 502
            
        data = response.json()
        playerData = data['elements']
        total_players = data.get('total_players', 1)
        if total_players == 0:
            total_players = 1
            
        current_gw = generateCurrentGameweek()

        netOwnership = {}
        currentOwnership = {}
        oldOwnership = {}

        # Pre-season, transfers_in/out are genuinely 0 for every player (the
        # API doesn't track them until gameweek 1 locks), which would make
        # every "relative change" below collapse to 0 too - not a bug, just
        # nothing to show yet. Rank by current ownership level instead, the
        # only signal that's actually live before then.
        if current_gw == 0:
            for player in playerData:
                pid = player['id']
                current_selected = float(player['selected_by_percent'])
                netOwnership[pid] = current_selected
                currentOwnership[pid] = {'web_name': player['web_name'], 'selected': current_selected}
                oldOwnership[pid] = current_selected
        else:
            for player in playerData:
                pid = player['id']
                current_selected = float(player['selected_by_percent'])
                transfers_in = player['transfers_in_event']
                transfers_out = player['transfers_out_event']

                net_transfers = transfers_in - transfers_out

                # Estimate percentage change in overall ownership
                net_selected_change = (net_transfers / total_players) * 100

                # Calculate relative change (how much it changed relative to its own size)
                if current_selected > 0.1: # Avoid division by zero or very small numbers
                    relative_change = net_selected_change / current_selected
                else:
                    # For new players or 0 ownership, use the absolute change as a proxy for trend
                    relative_change = net_selected_change

                netOwnership[pid] = relative_change
                currentOwnership[pid] = {'web_name': player['web_name'], 'selected': current_selected}
                oldOwnership[pid] = max(0, current_selected - net_selected_change)

        # Sort to find top/bottom relative changes (filtering for significant ownership)
        # We only care about players with at least some ownership to avoid noise
        relevant_ids = [pid for pid in netOwnership if currentOwnership[pid]['selected'] >= 0.5]

        if not relevant_ids:
            relevant_ids = list(netOwnership.keys())

        sorted_ids = sorted(relevant_ids, key=lambda x: netOwnership[x])

        bottom5RelativeIds = sorted_ids[:5]
        top5RelativeIds = sorted_ids[-5:]
        top5RelativeIds.reverse() # Show highest first

        # Combine them
        top10differenceIds = top5RelativeIds + bottom5RelativeIds

        labels = []
        oldValues = []
        newValues = []
        ids = []

        for pid in top10differenceIds:
            labels.append(currentOwnership[pid]['web_name'])
            oldValues.append(oldOwnership[pid])
            newValues.append(currentOwnership[pid]['selected'])
            ids.append(pid)

        ownership = {
            'labels': labels,
            'oldValues': oldValues,
            'newValues': newValues,
            'ids': ids,
            'metric': 'ownership' if current_gw == 0 else 'ownership_change'
        }

        return ownership
    except Exception as e:
        logger.error(f"Error in get_player_ownership: {e}")
        return {"error": str(e)}, 500

def get_under_the_radar_players():
    """
    Fetches 'Under the radar' players: low ownership but solid performance.
    Thresholds:
    - Ownership < 10% (Differential)
    - Average minutes per gameweek > 45 (Regular starter)
    - Ranked by (Total Points / Cost) * (100 - Ownership)
    """
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database in get_under_the_radar_players().")
        return []
    
    try:
        cursor = dbConnect.cursor(dictionary=True)
        
        # Determine the relevant gameweek for data
        gameweek = generateCurrentGameweek()
        cursor.execute(f'SELECT MAX(gameweek) AS max_gw FROM {db}.bootstrapstatic_elements WHERE year_start = {season_start}')
        max_gw = cursor.fetchone()['max_gw']
        if gameweek is None or gameweek == 0:
            gameweek = max_gw if max_gw is not None else 0

        # Divisor for average minutes calculation
        # If we're at GW0, we treat the data as a full season (38 matches)
        divisor = gameweek if gameweek > 0 else 38

        # Query for differentials with solid performance
        # Using points/cost normalized by non-ownership as the primary ranking signal
        query = f'''
        SELECT 
            e.id, 
            e.web_name, 
            CONCAT(e.first_name, ' ', e.second_name) AS full_name, 
            t.name AS team_name, 
            et.singular_name_short AS position,
            e.now_cost,
            e.total_points,
            e.selected_by_percent
        FROM {db}.bootstrapstatic_elements e
        JOIN {db}.bootstrapstatic_teams t ON e.team = t.id
        JOIN {db}.bootstrapstatic_element_types et ON e.element_type = et.id
        WHERE e.year_start = {season_start} 
          AND t.year_start = {season_start}
          AND e.gameweek = {gameweek}
          AND e.selected_by_percent < 10.0
          AND (e.minutes / {divisor}) > 45
        ORDER BY (e.total_points / (e.now_cost / 10)) * (100 - e.selected_by_percent) DESC
        LIMIT 10;
        '''
        cursor.execute(query)
        players = cursor.fetchall()
        dbConnect.close()
        
        # Enrich with a specific "why" reason based on recent points
        for p in players:
            if divisor == 38:  # Pre-season or start of season, use total_points as a proxy for last season
                p['why'] = f"Delivered {p['total_points']} points last season with only {p['selected_by_percent']}% ownership."
            else:
                # We already closed dbConnect, but get_player_last_5_points opens its own
                last_5 = get_player_last_5_points(p['id'])
                # Sum the last 3 available gameweeks' points
                last_3_sum = sum(item['points'] for item in last_5[-3:]) if last_5 else 0
                p['why'] = f"Produced {last_3_sum} points in the last 3 matches with only {p['selected_by_percent']}% ownership."
            
        return players
    except Exception as e:
        if dbConnect:
            dbConnect.close()
        logger.error(f"Error in get_under_the_radar_players: {e}")
        return []

def get_worth_watching_players():
    """
    Combines top form (from top_5_players_last_5_weeks) and 
    fixture difficulty (from next_5_gameweeks) to find players
    with the best combined signal.
    
    Weighting Logic:
    - Form Score (60%): Based on points delivered in last 5 weeks (or last season if GW0).
    - Fixture Score (40%): Based on average difficulty of next 5 fixtures.
    """
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database in get_worth_watching_players().")
        return []

    try:
        current_gw = generateCurrentGameweek()
        candidates = []
        
        # 1. Gather Candidates
        top_form_data = top_5_players_last_5_weeks()
        
        # If we have real form data (usually GW6+), use those players
        has_real_form = any(top_form_data[pos]['players'] for pos in top_form_data)
        
        if has_real_form:
            for pos_name in top_form_data:
                # Map position names to short versions (GK, DEF, MID, FWD)
                pos_map_short = {
                    "goalkeepers": "GKP",
                    "defenders": "DEF",
                    "midfielders": "MID",
                    "forwards": "FWD"
                }
                pos_short = pos_map_short.get(pos_name, "ALL")

                for p in top_form_data[pos_name]['players']:
                    p_id = p['player_id']
                    # Use the already calculated score sum from the data
                    form_points = sum(p['scores'])
                    candidates.append({
                        'id': p_id,
                        'web_name': p['name'],
                        'team_name': p['club'],
                        'position': pos_short,
                        'form_points': form_points,
                        'scores': p['scores'],
                        'is_gw0': False
                    })
        else:
            # GW0 fallback: Fetch top 30 players by total_points (last season)
            cursor = dbConnect.cursor(dictionary=True)
            cursor.execute(f'''
                SELECT e.id, e.web_name, t.name AS team_name, e.total_points, et.singular_name_short AS position
                FROM {db}.bootstrapstatic_elements e
                JOIN {db}.bootstrapstatic_teams t ON e.team = t.id
                JOIN {db}.bootstrapstatic_element_types et ON e.element_type = et.id
                WHERE e.year_start = {season_start} AND t.year_start = {season_start} AND e.gameweek = 0
                ORDER BY e.total_points DESC
                LIMIT 30
            ''')
            rows = cursor.fetchall()
            for row in rows:
                candidates.append({
                    'id': row['id'],
                    'web_name': row['web_name'],
                    'team_name': row['team_name'],
                    'position': row['position'],
                    'form_points': row['total_points'],
                    'is_gw0': True
                })
        
        # 2. Calculate Combined Score for each candidate
        results = []
        for c in candidates:
            fixtures = next_5_gameweeks(c['id'])
            if not fixtures:
                avg_diff = 3.0
            else:
                diffs = [f['difficulty'] for f in fixtures if isinstance(f['difficulty'], (int, float))]
                avg_diff = sum(diffs) / len(diffs) if diffs else 3.0
            
            # Form Score (0-10)
            if c['is_gw0']:
                # Assume 200 points last season is a good benchmark for pre-season form
                form_score = min((c['form_points'] / 200) * 10, 10)
            else:
                # 30 points in last 5 weeks (6 pts/game) is a good benchmark
                form_score = min((c['form_points'] / 30) * 10, 10)
                
            # Fixture Score (0-10)
            # Difficulty is 1-5. 1 is easiest (Score 10), 5 is hardest (Score 0)
            # (5 - difficulty) / 4 * 10
            fixture_score = ((5 - avg_diff) / 4) * 10
            
            combined_score = (form_score * 0.6) + (fixture_score * 0.4)
            
            # Build "why" note
            if c['is_gw0']:
                reason = f"Delivered {c['form_points']} pts last season; kind fixture run coming up."
            else:
                # Try to find how many returns in last 5
                returns = len([s for s in c.get('scores', []) if s >= 4]) # simple proxy for 'return'
                if returns > 0:
                    reason = f"{returns} returns in last 5, meeting a soft run of fixtures."
                else:
                    reason = f"{c['form_points']} points in last 5 games, and a soft run coming up."

            results.append({
                'id': c['id'],
                'web_name': c['web_name'],
                'team_name': c['team_name'],
                'position': c['position'],
                'score': combined_score,
                'form_points': c['form_points'],
                'avg_diff': round(avg_diff, 1),
                'why': reason
            })
            
        # 3. Sort and Return Top 10
        results.sort(key=lambda x: x['score'], reverse=True)
        top_10 = results[:10]
        
        # Final enrichment (shirts, etc.)
        # Need to re-open cursor if we used it
        cursor = dbConnect.cursor(dictionary=True)
        for p in top_10:
            cursor.execute(f'SELECT team_code FROM {db}.bootstrapstatic_elements WHERE id = {p["id"]} AND year_start = {season_start} LIMIT 1')
            row = cursor.fetchone()
            if row:
                p['shirt'] = player_shirts.get(row['team_code'], player_shirts['Unknown'])
            else:
                p['shirt'] = player_shirts['Unknown']
        
        dbConnect.close()
        return top_10

    except Exception as e:
        if dbConnect:
            dbConnect.close()
        logger.error(f"Error in get_worth_watching_players: {e}")
        return []

def get_most_consistent_players():
    """
    Identifies players who rarely let you down, defined as those
    with the lowest standard deviation in points over the last 5 GWs,
    provided they meet a minimum average and minutes threshold.
    """
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database in get_most_consistent_players().")
        return []
    cursor = dbConnect.cursor(dictionary=True)

    current_gw = generateCurrentGameweek()
    
    try:
        if current_gw == 0:
            # Pre-season logic: Use end of last season (2025)
            # We must use 'code' to bridge between seasons as IDs may have changed
            last_year = 2025
            query = f"""
                SELECT 
                    e2026.id, 
                    e2026.web_name,
                    e2026.now_cost,
                    e2026.team_code,
                    t.short_name as team_short_name,
                    et.singular_name_short as position,
                    stats.std_dev,
                    stats.avg_points
                FROM (
                    SELECT 
                        e2025.code,
                        STDDEV_POP(h.total_points) as std_dev, 
                        AVG(h.total_points) as avg_points,
                        COUNT(CASE WHEN h.minutes >= 60 THEN 1 END) as starts
                    FROM {db}.elementsummary_history h
                    JOIN {db}.bootstrapstatic_elements e2025 ON h.element = e2025.id AND e2025.year_start = {last_year}
                    WHERE h.year_start = {last_year}
                    AND h.round BETWEEN 34 AND 38
                    GROUP BY e2025.code
                    HAVING starts >= 4
                    AND avg_points >= 3.5
                ) stats
                JOIN {db}.bootstrapstatic_elements e2026 ON stats.code = e2026.code AND e2026.year_start = {season_start}
                JOIN {db}.bootstrapstatic_teams t ON e2026.team = t.id AND t.year_start = {season_start}
                JOIN {db}.bootstrapstatic_element_types et ON e2026.element_type = et.id
                ORDER BY stats.std_dev ASC
                LIMIT 10
            """
        else:
            # Active season logic: Use current season history
            start_gw = max(1, current_gw - 4)
            end_gw = current_gw
            # Require starting in at least 80% of games in the window
            min_starts = max(1, (end_gw - start_gw + 1) * 0.8)
            
            query = f"""
                SELECT 
                    e.id, 
                    e.web_name,
                    e.now_cost,
                    e.team_code,
                    t.short_name as team_short_name,
                    et.singular_name_short as position,
                    STDDEV_POP(h.total_points) as std_dev, 
                    AVG(h.total_points) as avg_points,
                    COUNT(CASE WHEN h.minutes >= 60 THEN 1 END) as starts
                FROM {db}.elementsummary_history h
                JOIN {db}.bootstrapstatic_elements e ON h.element = e.id AND e.year_start = {season_start}
                JOIN {db}.bootstrapstatic_teams t ON e.team = t.id AND t.year_start = {season_start}
                JOIN {db}.bootstrapstatic_element_types et ON e.element_type = et.id
                WHERE h.year_start = {season_start}
                AND h.round BETWEEN {start_gw} AND {end_gw}
                GROUP BY h.element
                HAVING starts >= {min_starts}
                AND avg_points >= 3.5
                ORDER BY std_dev ASC
                LIMIT 10
            """
            
        cursor.execute(query)
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            # Generate the "Why" note
            note = f"Averages {row['avg_points']:.1f} pts with very low variance."
            
            result.append({
                'id': row['id'],
                'name': row['web_name'],
                'team': row['team_short_name'],
                'position': row['position'],
                'price': row['now_cost'] / 10.0,
                'why': note,
                'shirt': player_shirts.get(row['team_code'], player_shirts['Unknown'])
            })
            
        return result
    except Exception as e:
        logger.exception(f"Error in get_most_consistent_players: {str(e)}")
        return []
    finally:
        cursor.close()
        dbConnect.close()

def get_momentum_players():
    """
    Identifies players whose ownership is rising fast (momentum),
    defined as the absolute percentage point change over 3 gameweeks.
    Capped at 40% current ownership to surface 'discoveries'.
    """
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database in get_momentum_players().")
        return []
    cursor = dbConnect.cursor(dictionary=True)
    
    current_gw = generateCurrentGameweek()
    
    try:
        current_year = season_start
        
        if current_gw >= 3:
            old_gw = current_gw - 3
            old_year = current_year
        else:
            old_year = current_year - 1
            old_gw = 38 - (3 - current_gw)

        query = f"""
            SELECT 
                curr.id, 
                curr.web_name, 
                t.short_name as team_short_name, 
                t.code as team_code,
                et.singular_name_short as position,
                curr.selected_by_percent as current_ownership,
                COALESCE(old.selected_by_percent, 0) as old_ownership,
                (curr.selected_by_percent - COALESCE(old.selected_by_percent, 0)) as momentum,
                curr.now_cost
            FROM 
                {db}.bootstrapstatic_elements curr
            JOIN
                {db}.bootstrapstatic_teams t ON curr.team = t.id AND t.year_start = curr.year_start
            JOIN 
                {db}.bootstrapstatic_element_types et ON curr.element_type = et.id
            LEFT JOIN 
                {db}.bootstrapstatic_elements old ON curr.code = old.code AND old.year_start = %s AND old.gameweek = %s
            WHERE 
                curr.year_start = %s AND curr.gameweek = %s
                AND curr.selected_by_percent < 40
            ORDER BY 
                momentum DESC
            LIMIT 10
        """
        cursor.execute(query, (old_year, old_gw, current_year, current_gw))
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            # Generate the "Why" note
            note = f"Ownership up {row['momentum']:.1f} points in 3 gameweeks."
            
            result.append({
                'id': row['id'],
                'name': row['web_name'],
                'team': row['team_short_name'],
                'position': row['position'],
                'price': row['now_cost'] / 10.0,
                'why': note,
                'shirt': player_shirts.get(row['team_code'], player_shirts['Unknown'])
            })
            
        return result
    except Exception as e:
        logger.exception(f"Error in get_momentum_players: {str(e)}")
        return []
    finally:
        cursor.close()
        dbConnect.close()

def get_new_manager_players():
    """
    Fetches players from teams with a new manager appointed within the last 4 gameweeks.
    If no teams qualify, returns an empty list (thin-category handling).
    """
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database in get_new_manager_players().")
        return []
    cursor = dbConnect.cursor(dictionary=True)
    
    current_gw = generateCurrentGameweek()
    
    try:
        # 1. Identify teams with new managers (within 4 GWs)
        threshold = 4
        query_teams = f'''
            SELECT team_id, manager_name, appointment_gameweek 
            FROM team_manager_appointments t1
            WHERE year_start = {season_start}
              AND appointment_gameweek = (
                  SELECT MAX(appointment_gameweek) 
                  FROM team_manager_appointments t2 
                  WHERE t2.team_id = t1.team_id 
                    AND t2.year_start = {season_start}
              )
              AND ({current_gw} - appointment_gameweek) <= {threshold}
              AND ({current_gw} - appointment_gameweek) >= 0
        '''
        cursor.execute(query_teams)
        new_manager_teams = cursor.fetchall()
        
        if not new_manager_teams:
            return []
            
        results = []
        for team in new_manager_teams:
            # 2. For each team, fetch top 3 players by performance (total_points)
            gw_for_elements = current_gw if current_gw > 0 else 0
            
            query_players = f'''
                SELECT 
                    e.id, 
                    e.web_name, 
                    t.name AS team_name, 
                    et.singular_name_short AS position,
                    e.team_code
                FROM {db}.bootstrapstatic_elements e
                JOIN {db}.bootstrapstatic_teams t ON e.team = t.id
                JOIN {db}.bootstrapstatic_element_types et ON e.element_type = et.id
                WHERE e.year_start = {season_start}
                  AND t.year_start = {season_start}
                  AND e.gameweek = {gw_for_elements}
                  AND e.team = {team['team_id']}
                ORDER BY e.total_points DESC, e.now_cost DESC
                LIMIT 3
            '''
            cursor.execute(query_players)
            players = cursor.fetchall()
            
            for p in players:
                results.append({
                    'id': p['id'],
                    'name': p['web_name'],
                    'team': p['team_name'],
                    'position': p['position'],
                    'why': f"New manager ({team['manager_name']}) since GW{team['appointment_gameweek']} - role could change.",
                    'shirt': player_shirts.get(p['team_code'], player_shirts['Unknown'])
                })
                
        return results

    except Exception as e:
        logger.exception(f"Error in get_new_manager_players: {str(e)}")
        return []
    finally:
        cursor.close()
        dbConnect.close()

# Every player's transfers_in/out (and transfers_in_event/out_event) sit at a
# genuine, real 0 for everyone until gameweek 1 locks - the FPL API doesn't
# start tracking transfers until initial squad-building ends. That's not a
# bug to work around: it's the real count, so these just report it as 0
# rather than substituting a different metric.

# For Net Transfers In
def get_top_10_net_transfers_in():
    current_gw = generateCurrentGameweek()
    playerData = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/').json()['elements']
    playersNetTransfers = {}
    idToName = dict()

    for player in playerData:
        if current_gw == 0:
            netTransfersIn = player['transfers_in'] - player['transfers_out']
        else:
            netTransfersIn = player['transfers_in_event'] - player['transfers_out_event']
        playersNetTransfers[player['id']] = netTransfersIn
        idToName[player['id']] = player['web_name']

    sorted_net_transfers_in = sorted(playersNetTransfers.items(), key=lambda item: item[1], reverse=True)[:10]

    data = {
        'labels': [idToName[item[0]] for item in sorted_net_transfers_in],
        'values': [item[1] for item in sorted_net_transfers_in],
        'ids': [item[0] for item in sorted_net_transfers_in],
        'metric': 'transfers'
    }

    return data

def get_top_10_net_transfers_out():
    current_gw = generateCurrentGameweek()
    playerData = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/').json()['elements']
    playersNetTransfersOut = {}
    idToName = dict()

    # Calculate net transfers out for each player
    for player in playerData:
        if current_gw == 0:
            netTransfersOut = player['transfers_out'] - player['transfers_in']
        else:
            netTransfersOut = player['transfers_out_event'] - player['transfers_in_event']
        playersNetTransfersOut[player['id']] = netTransfersOut
        idToName[player['id']] = player['web_name']

    # Sort the dictionary by values in descending order and pick the top 10
    sorted_net_transfers_out = sorted(playersNetTransfersOut.items(), key=lambda item: item[1], reverse=True)[:10]

    # Prepare the data in the required format
    data = {
        'labels': [idToName[item[0]] for item in sorted_net_transfers_out],
        'values': [item[1] for item in sorted_net_transfers_out],
        'ids': [item[0] for item in sorted_net_transfers_out],
        'metric': 'transfers'
    }

    return data


def next_5_gameweeks(player_id):

    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return []
    cursor = dbConnect.cursor(dictionary=True)
    gw = generateCurrentGameweek()
    
    # Always ensure you fetch all results or close the cursor before executing another query
    query = f'SELECT id, short_name, code FROM {db}.bootstrapstatic_teams where year_start = {season_start};'
    cursor.execute(query)
    teams = cursor.fetchall()  # Fetch all team information

    team_id_to_code = dict()
    
    for team in teams:
        team_id_to_code[team['id']] = team['code']

    # p and t each store one row per gameweek snapshot, so without ordering
    # + limiting this join returns one row per gameweek (e.g. 38 duplicates),
    # and cursor.fetchone() leaves the rest unread - which breaks the very
    # next cursor.execute() in this function with "Unread result found".
    query = f'SELECT t.name as "team", t.short_name as "team_short", p.team AS "team_id", CONCAT(p.first_name, " ", p.second_name) AS "Full_name", p.id AS "ID" FROM {db}.bootstrapstatic_elements p JOIN {db}.bootstrapstatic_teams t ON p.team = t.id WHERE p.year_start = {season_start} AND t.year_start = {season_start} and p.id={player_id} ORDER BY p.gameweek DESC LIMIT 1;'
    cursor.execute(query)
    player_info = cursor.fetchone()

    # Fallback to API if player info not in DB
    if not player_info:
        try:
            api_resp = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
            if api_resp.status_code == 200:
                api_data = api_resp.json()
                player = next((p for p in api_data['elements'] if p['id'] == int(player_id)), None)
                if player:
                    player_info = {
                        'team_id': player['team'],
                        'Full_name': f"{player['first_name']} {player['second_name']}"
                    }
        except Exception as e:
            logger.error(f"Failed to fetch player info from API: {e}")

    if not player_info:
        dbConnect.close()
        return []

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

        # Average difficulty across every fixture in the gameweek (both sides),
        # used as the "league average" comparison row for this gameweek.
        cursor.execute(f'''
            SELECT AVG(d) AS avg_difficulty FROM (
                SELECT team_h_difficulty AS d FROM {db}.fixtures_fixtures WHERE year_start = {season_start} AND event = {i}
                UNION ALL
                SELECT team_a_difficulty AS d FROM {db}.fixtures_fixtures WHERE year_start = {season_start} AND event = {i}
            ) all_difficulties;
        ''')
        avg_row = cursor.fetchone()
        league_avg_difficulty = round(float(avg_row['avg_difficulty'])) if avg_row and avg_row['avg_difficulty'] is not None else None

        if not fixtures_in_gw:
            fixtures.append({
                'teamName': '-',
                'difficulty': "None",
                'shirtImage': player_shirts['Unknown'],
                'homeOrAway': 'Blank',
                'gameweek': i,
                'leagueAverageDifficulty': league_avg_difficulty
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
                'shirtImage': player_shirts.get(opponent_code, player_shirts['Unknown']),
                'homeOrAway': venue,
                'gameweek': i,
                'leagueAverageDifficulty': league_avg_difficulty
            })

        i += 1             

    cursor.close()  # Close the cursor after using it
    dbConnect.close()  # Close the database connection

    return fixtures

def get_teams(player_id):
    # Connect to the database
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return []
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
                    "player_id": pid,
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

def get_player_ownership_history(player_id):
    """
    Returns a player's ownership percentage history for the last 5 gameweeks.
    """
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database in get_player_ownership_history().")
        return []
    cursor = dbConnect.cursor(dictionary=True)

    current_gw = generateCurrentGameweek()
    start_gw = max(0, current_gw - 4)
    end_gw = current_gw

    try:
        # Get historical ownership from bootstrapstatic_elements
        # We need to map by gameweek and handle missing data
        query = f"""
            SELECT gameweek, selected_by_percent
            FROM {db}.bootstrapstatic_elements
            WHERE code = (SELECT code FROM {db}.bootstrapstatic_elements WHERE id = %s AND year_start = {season_start} LIMIT 1)
            AND year_start = {season_start}
            AND gameweek BETWEEN %s AND %s
            ORDER BY gameweek ASC
        """
        cursor.execute(query, (player_id, start_gw, end_gw))
        rows = cursor.fetchall()
        
        # If no rows (pre-season or new player), fallback to current ownership
        if not rows:
            cursor.execute(f"SELECT selected_by_percent FROM {db}.bootstrapstatic_elements WHERE id = %s AND year_start = {season_start}", (player_id,))
            row = cursor.fetchone()
            current_val = float(row['selected_by_percent']) if row else 0
            return [current_val] * 5

        by_gw = {row['gameweek']: float(row['selected_by_percent']) for row in rows}
        
        result = []
        for gw in range(start_gw, end_gw + 1):
            if gw in by_gw:
                result.append(by_gw[gw])
            else:
                # Fill gaps with the previous available value or 0
                prev = result[-1] if result else 0
                result.append(prev)
        
        # Ensure we have 5 points
        while len(result) < 5:
            result.insert(0, result[0] if result else 0)
            
        return result[-5:]

    except Exception as e:
        logger.exception(f"Error in get_player_ownership_history: {str(e)}")
        return []
    finally:
        cursor.close()
        dbConnect.close()

def get_player_last_5_points(player_id):
    """
    Returns one player's own points, minutes played, and fixture difficulty
    for each of the last 5 gameweeks, filling in 0/None for any gameweek
    they didn't feature in - same window and gap-filling approach as
    top_5_players_last_5_weeks(), but scoped to a single player_id rather
    than a position's top 5 scorers.
    """
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database in get_player_last_5_points().")
        return {}
    cursor = dbConnect.cursor(dictionary=True)

    current_gw = generateCurrentGameweek()
    start_gw = current_gw - 4
    end_gw = current_gw
    gws_list = list(range(start_gw, end_gw + 1))

    try:
        query = f"""
            SELECT h.round AS gw, SUM(h.total_points) AS points,
                   SUM(h.minutes) AS minutes, MAX(f.difficulty) AS difficulty
            FROM {db}.elementsummary_history h
            LEFT JOIN {db}.elementsummary_fixtures f
                ON h.fixture = f.id AND f.year_start = h.year_start
            WHERE h.year_start = {season_start}
            AND h.element = {player_id}
            AND h.round BETWEEN {start_gw} AND {end_gw}
            GROUP BY h.round
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        by_gw = {row['gw']: row for row in rows}
        
        result = []
        for gw in gws_list:
            result.append({
                'gw': gw,
                'points': by_gw[gw]['points'] if gw in by_gw else 0,
                'minutes': by_gw[gw]['minutes'] if gw in by_gw else 0,
                'difficulty': by_gw[gw]['difficulty'] if gw in by_gw else 3
            })
        return result
    except Exception as e:
        logger.exception(f"Error in get_player_last_5_points: {str(e)}")
        return []
    finally:
        cursor.close()
        dbConnect.close()

def get_comparison_averages_last_5(position=None):
    """
    Weekly average points and average ownership over the last 5 gameweeks,
    for the Discovery comparison panel's reference line (04.14 follow-up:
    up to 3-player comparison with a position/overall average overlay).

    position: one of 'GKP'/'DEF'/'MID'/'FWD' to scope both averages to that
    position, or None/anything else (e.g. the 'MGR' position, not covered by
    this positional breakdown) for a leaguewide "overall" average across all
    players.

    Points average uses a `minutes >= 1` threshold - deliberately looser than
    top_5_players_last_5_weeks()'s `> 15`, since this line represents "anyone
    who actually took part that week", not "regular starters" - a different
    purpose, so a different, separately-maintained threshold rather than
    reusing/changing that function's.

    Ownership average has NO minutes filter: an unused/benched player's
    ownership % is still real and meaningful, unlike their points, so
    excluding them would bias the average upward rather than represent it.
    """
    dbConnect = connect_db()
    if dbConnect is None:
        logger.error("Failed to connect to the database in get_comparison_averages_last_5().")
        return {'points': [], 'ownership': []}
    cursor = dbConnect.cursor(dictionary=True)

    current_gw = generateCurrentGameweek()
    start_gw = current_gw - 4
    end_gw = current_gw
    gws_list = list(range(start_gw, end_gw + 1))

    position_to_element_type = {'GKP': 1, 'DEF': 2, 'MID': 3, 'FWD': 4}
    element_type = position_to_element_type.get(position)

    try:
        # Same "nearest gameweek snapshot" position lookup as top_5_players_last_5_weeks(),
        # applied as a correlated-subquery filter rather than a join, so a player's several
        # bootstrapstatic_elements snapshot rows can't multiply their elementsummary_history row.
        element_type_filter = ""
        if element_type:
            element_type_filter = f"""
                AND (
                    SELECT e2.element_type
                    FROM {db}.bootstrapstatic_elements e2
                    WHERE e2.id = h.element AND e2.year_start = h.year_start
                    ORDER BY ABS(e2.gameweek - h.round)
                    LIMIT 1
                ) = {element_type}
            """
        points_query = f"""
            SELECT h.round AS gw, AVG(h.total_points) AS avg_points
            FROM {db}.elementsummary_history h
            WHERE h.year_start = {season_start}
            AND h.round BETWEEN {start_gw} AND {end_gw}
            AND h.minutes >= 1
            {element_type_filter}
            GROUP BY h.round
        """
        cursor.execute(points_query)
        points_rows = cursor.fetchall()
        points_by_gw = {row['gw']: float(row['avg_points']) for row in points_rows if row['avg_points'] is not None}
        points_result = [round(points_by_gw.get(gw, 0), 2) for gw in gws_list]

        ownership_filter = f"AND element_type = {element_type}" if element_type else ""
        ownership_query = f"""
            SELECT gameweek AS gw, AVG(selected_by_percent) AS avg_ownership
            FROM {db}.bootstrapstatic_elements
            WHERE year_start = {season_start}
            AND gameweek BETWEEN {start_gw} AND {end_gw}
            {ownership_filter}
            GROUP BY gameweek
        """
        cursor.execute(ownership_query)
        ownership_rows = cursor.fetchall()
        ownership_by_gw = {row['gw']: float(row['avg_ownership']) for row in ownership_rows if row['avg_ownership'] is not None}
        ownership_result = [round(ownership_by_gw.get(gw, 0), 2) for gw in gws_list]

        return {'points': points_result, 'ownership': ownership_result}
    except Exception as e:
        logger.exception(f"Error in get_comparison_averages_last_5: {str(e)}")
        return {'points': [], 'ownership': []}
    finally:
        cursor.close()
        dbConnect.close()

def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"

# 02.7: set-piece duty order, straight from the same live bootstrap-static
# player record fetch_player_summary already has in scope - no separate
# database lookup, so this can't hit the DB/live-API identity mismatch that
# affects the DB-sourced fixture/rating data during a season rollover.
def _set_piece_duties(player):
    duty_fields = [
        ('penalties_order', 'penalties'),
        ('direct_freekicks_order', 'direct free-kicks'),
        ('corners_and_indirect_freekicks_order', 'corners and indirect free-kicks'),
    ]
    duties = []
    for field, label in duty_fields:
        order = player.get(field)
        if order:
            duties.append({
                'label': label,
                'order': order,
                'text': f"{_ordinal(order)} in line for {label}"
            })
    return duties

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
        
        current_gw = generateCurrentGameweek()
        # Use GW 1 for per-gameweek calculations if in pre-season (GW 0)
        calculation_gw = max(1, current_gw)

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
        
        # If pre-season, everyone has 0 minutes, so relax the filter
        if current_gw == 0 or not valid_players:
             valid_players = [p for p in elements if p['element_type'] == position]

        if not valid_players:
            logger.warning(f"No valid players found for position {position}.")
            return {"error": "No valid player data found."}, 500

        average_goals = round(sum(p['goals_scored'] for p in valid_players) / len(valid_players), 2)
        average_assists = round(sum(p['assists'] for p in valid_players) / len(valid_players), 2)
        average_form = round(sum(float(p['form']) for p in valid_players) / len(valid_players), 2)
        average_points = round(sum(float(p['total_points']) for p in valid_players) / len(valid_players), 2)
        average_influence = round(sum(float(p['influence']) for p in valid_players) / len(valid_players), 2)
        average_creativity = round(sum(float(p['creativity']) for p in valid_players) / len(valid_players), 2)
        average_threat = round(sum(float(p['threat']) for p in valid_players) / len(valid_players), 2)
        average_ep_next = round(sum(float(p['ep_next']) for p in valid_players) / len(valid_players), 2)
        average_minutes = round(sum(float(p['minutes']) for p in valid_players) / len(valid_players) / calculation_gw, 0)
        average_clean_sheets = round(sum(p['clean_sheets'] for p in valid_players) / len(valid_players), 2)
        average_bonus = round(sum(p['bonus'] for p in valid_players) / len(valid_players), 2)
        ppm_values = [float(p['total_points']) / (p['now_cost'] / 10) for p in valid_players if p['now_cost'] > 0]
        average_ppm = round(sum(ppm_values) / len(ppm_values), 2) if ppm_values else 0

        # Get team info
        team = next((t for t in teams if t['code'] == player['team_code']), None)
        if not team:
            logger.warning(f"Team for player ID {player_id} not found.")
            team_name = "Unknown"
            shirt_image = '/static/content/Tshirts/unknown-football-shirt-svgrepo-com.svg'
        else:
            team_name = team['name']
            shirt_image = player_shirts.get(team['code'], player_shirts['Unknown'])

        # Create player summary
        player_summary = {
            'id': player_id,
            'name': player['web_name'],
            'value': float(player['now_cost'] / 10),
            'minutes': round(player['minutes'] / calculation_gw, 2),
            'chance_of_playing': player['chance_of_playing_next_round'],
            'news': player['news'],
            'position': position,
            'position_name': element_types[position],
            'team_name': team_name,
            'shirtImage': shirt_image,
            'selected_by_percent': float(player['selected_by_percent']),
            'transfers_in_event': player['transfers_in'] if current_gw == 0 else player['transfers_in_event'],
            'transfers_out_event': player['transfers_out'] if current_gw == 0 else player['transfers_out_event'],
            'is_pre_season': (current_gw == 0),
            'setPieceDuties': _set_piece_duties(player),
            'metrics': [
                {'title': 'Goals', 'value': player['goals_scored'], 'averageValue': average_goals},
                {'title': 'Assists', 'value': player['assists'], 'averageValue': average_assists},
                {'title': 'Form', 'value': float(player['form']), 'averageValue': average_form},

                {'title': 'Influence', 'value': player['influence'], 'averageValue': average_influence},
                {'title': 'Creativity', 'value': player['creativity'], 'averageValue': average_creativity},
                {'title': 'Threat', 'value': player['threat'], 'averageValue': average_threat},
                
                {'title': 'Est. points next game', 'value': player['ep_next'], 'averageValue': average_ep_next},
                {'title': 'Points', 'value': player['total_points'], 'averageValue': average_points},
                {'title': 'Avg. mins', 'value': round(player['minutes'] / calculation_gw, 0), 'averageValue': average_minutes},
                {'title': 'Clean sheets', 'value': player['clean_sheets'], 'averageValue': average_clean_sheets},
                {'title': 'Bonus points', 'value': player['bonus'], 'averageValue': average_bonus},
                {'title': 'Points per £1m', 'value': round(float(player['total_points']) / (player['now_cost'] / 10), 2) if player['now_cost'] > 0 else 0, 'averageValue': average_ppm},
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
    if dbConnect is None:
        logger.error("Failed to connect to the database.")
        return []
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
        player['shirt'] = player_shirts.get(player['team_code'], player_shirts['Unknown'])
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
