from datetime import datetime
from re import M
from flask import render_template, request, jsonify, send_from_directory, abort
from . import app
import os
import logging
from .dataModels import (
    get_players, get_players_by_team, 
    get_players_by_position, get_comparison_stats, 
    get_player_index_scores, get_player_net_transfers,
    get_player_ownership, get_top_10_net_transfers_in, get_top_10_net_transfers_out,
    next_5_fixtures, fetch_player_summary, get_alternative_players, top_5_players_last_5_weeks
)

from .futurePerformanceModel import( team_optimization )

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
    return render_template('home.html', title='Home Page', year=datetime.now().year)

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
    return render_template('players.html', is_ajax=is_ajax, title='Team')

@app.route('/team')
def team():
    logger.info("Request for team page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('team.html', is_ajax=is_ajax, title='Team')

@app.route('/compare')
def compare():
    logger.info("Request for compare page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('compare.html', is_ajax=is_ajax, title='Player Comparison')

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

@app.route('/get_next_5_fixtures')
def get_player_next_5_fixtures():
    logger.info("Request for get_next_5_fixtures")
    try:
        player_id = request.args.get('id')
        fixtures = next_5_fixtures(player_id)
        return jsonify(fixtures)
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

