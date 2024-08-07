from datetime import datetime
from flask import render_template, request, jsonify, send_from_directory, abort
from . import app
import os
import logging
from .dataModels import (
    get_players, get_players_by_team, 
    get_players_by_position, get_comparison_stats, 
    get_player_index_scores, get_player_net_transfers
)

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

@app.route('/api/net-transfers')
def net_transfers():
    data = {
        'labels': ['Haaland', 'Salah', 'Pickford', 'Gordon', 'Saka', 'Watkins', 'Burn', 'Gvardiol', 'Palmer', 'Saliba'],
        'values': [1242233, 943631, 872269, 652834, 598723, 554295, 421678, 293029, 182592, 163206]
    }
    return jsonify(data)

@app.route('/api/relative-ownership')
def relative_ownership():
    data = {
        'labels': ['Haaland', 'Salah', 'Pickford', 'Gordon', 'Saka', 'Watkins', 'Burn', 'Gvardiol', 'Palmer', 'Saliba'],
        'oldValues': [32, 72, 16, 38, 21, 86, 11, 22, 32, 9],
        'newValues': [62, 82, 25, 46, 29, 91, 16, 26, 35, 10]
    }
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
