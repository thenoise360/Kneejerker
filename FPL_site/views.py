from datetime import datetime
from re import M
from flask import request, jsonify, session as flask_session
from flask import render_template, request, jsonify, send_from_directory, abort
from . import app
from .config import current_config
import os
import requests
import logging
from .dataModels import (
    get_players, get_players_by_team, 
    get_players_by_position, get_comparison_stats, 
    get_player_index_scores, get_player_net_transfers,
    get_player_ownership, get_top_10_net_transfers_in, get_top_10_net_transfers_out,
    next_5_gameweeks, fetch_player_summary, get_alternative_players, top_5_players_last_5_weeks, loginToFPL, getFPLTeamData
)

from .futurePerformanceModel import( team_optimization )

# Remove ==================================================

@app.route('/my-team')
def my_team():
    logger.info("Request for my-team page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('my-team.html', is_ajax=is_ajax, title='My Team',, mixpanel_token=current_config.MIXPANEL_TOKEN)

@app.route('/login-fpl', methods=['POST'])
def login_fpl():
    """
    Logs into FPL and saves real browser session cookies for future requests.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    login_response = loginToFPL(username, password)

    if "error" in login_response:
        return jsonify(login_response), 401  # Unauthorized

    # Debugging: Print the returned cookies
    print("Login Cookies (Stored):", login_response["cookies"])

    # ✅ Check if `pl_profile` is missing
    if "pl_profile" not in login_response["cookies"]:
        print("🚨 WARNING: `pl_profile` is missing from stored cookies!")

    # Save cookies correctly
    flask_session['fpl_cookies'] = login_response["cookies"]

    return jsonify({"message": "Login successful"})


@app.route('/get-my-team', methods=['POST'])
def get_my_team():
    data = request.get_json()
    team_id = data.get('team_id')

    if not team_id:
        return jsonify({"error": "Team ID is required"}), 400

    # Retrieve stored cookies from Flask session
    cookies = flask_session.get('fpl_cookies', {})

    print("Stored Cookies in Flask:", cookies)  # ✅ Debug stored cookies

    if not cookies:
        return jsonify({"error": "No login session found. Please log in first."}), 401  # Unauthorized

    # Get team data using stored cookies
    team_data = getFPLTeamData(cookies, team_id)

    return jsonify(team_data)

# Remove ==================================================

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/static/<path:filename>')
def custom_static(filename):
    app.logger.info(f"Request for static file: {filename}")
    try:
        full_path = os.path.join(app.static_folder, filename)
        app.logger.info(f"Full path resolved to: {full_path}")
        if os.path.exists(full_path):
            return send_from_directory(app.static_folder, filename)
        else:
            app.logger.error(f"Static file not found at path: {full_path}")
            abort(404)
    except FileNotFoundError:
        app.logger.error(f"Static file not found: {filename}")
        abort(404)

@app.route('/')
def home():
    logger.info("Request for home page")
    return render_template('home.html', title='Home Page', year=datetime.now().year, mixpanel_token=current_config.MIXPANEL_TOKEN)

@app.route('/api/net-transfers-in')
def net_transfers_in():
    data = get_top_10_net_transfers_in()
    return jsonify(data)

@app.route('/api/net-transfers-out')
def net_transfers_out():
    data = get_top_10_net_transfers_out()
    return jsonify(data)

@app.route('/api/relative-ownership')
def relative_ownership():
    data = get_player_ownership()
    return jsonify(data)


@app.route('/api/top-5-players')
def top_5_players():
    data = top_5_players_last_5_weeks()
    return jsonify(data)

@app.route('/players')
def players():
    logger.info("Request for players page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('players.html', is_ajax=is_ajax, title='Top layers', mixpanel_token=current_config.MIXPANEL_TOKEN)

@app.route('/team')
def team():
    logger.info("Request for team page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('team.html', is_ajax=is_ajax, title='Team', mixpanel_token=current_config.MIXPANEL_TOKEN)

@app.route('/compare')
def compare():
    logger.info("Request for compare page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('compare.html', is_ajax=is_ajax, title='Player Comparison', mixpanel_token=current_config.MIXPANEL_TOKEN)

@app.route('/get_players')
def get_players_route():
    logger.info("Request for get_players")
    players = get_players()
    return jsonify(players)

@app.route('/get_players_by_team')
def get_players_by_team_route():
    logger.info("Request for get_players_by_team")
    players = get_players_by_team()
    return jsonify(players)

@app.route('/get_players_by_position')
def get_players_by_position_route():
    logger.info("Request for get_players_by_position")
    players = get_players_by_position()
    return jsonify(players)

@app.route('/get_player_index_scores')
def get_player_index_scores_route():
    logger.info("Request for get_player_index_scores")
    try:
        players = get_player_index_scores()
        return jsonify(players)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e), 500

@app.route('/get_player_net_transfers')
def get_player_net_transfers_route():
    logger.info("Request for get_player_net_transfers")
    try:
        player_id = request.args.get('id')
        net_transfers = get_player_net_transfers(player_id)
        return jsonify(net_transfers)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e), 500

@app.route('/compare_players')
def compare_players_route():
    logger.info("Request for compare_players")
    id1 = request.args.get('id1', type=int)
    id2 = request.args.get('id2', type=int)
    players_data = get_comparison_stats(id1, id2)
    return jsonify(players_data)

@app.route('/get_next_5_gameweeks')
def get_player_next_5_gameweeks():
    logger.info("Request for get_next_5_gameweeks")
    try:
        player_id = request.args.get('id')
        gameweeks = next_5_gameweeks(player_id)
        return jsonify(gameweeks)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e), 500

@app.route('/get_player_summary')
def get_player_summary():
    logger.info("Request for get_player_summary")
    try:
        player_id = request.args.get('id')
        player_summary_result = fetch_player_summary(player_id)
        return jsonify(player_summary_result)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e), 500

@app.route('/run-team-optimization', methods=['POST'])
def process_data():
    data = request.get_json()
    slider_values = data.get('sliders', [])

    # Start processing the slider values and get the optimized team
    result, optimized_team = team_optimization(slider_values)  # Assume it returns the team and success flag

    # After the processing is complete, return success or error response with team data
    if result:
        return jsonify(success=True, team=optimized_team)  # Include the optimized team in the response
    else:
        return jsonify(success=False, error="Processing failed")


# Error handling for 500 errors
@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


@app.route('/get_player_alternates')
def get_player_alternates():
    logger.info("Request for get_player_alternates")
    try:
        player_id = request.args.get('id')
        player_summary_result = get_alternative_players(player_id)
        return jsonify(player_summary_result)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e), 500

