from datetime import datetime
from flask import render_template, request, jsonify, send_from_directory, abort
from . import app
import os
import logging
from .dataModels import (
    get_players, get_players_by_team, 
    get_players_by_position, get_comparison_stats, 
    get_player_index_scores, get_player_net_transfers,
    get_player_ownership, get_top_10_net_transfers
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
    data = get_top_10_net_transfers()
    return jsonify(data)

@app.route('/api/relative-ownership')
def relative_ownership():
    data = get_player_ownership()
    return jsonify(data)

@app.route('/api/top-5-players')
def top_5_players():
    data = {
        "goalkeepers": {
            "averageScores": [8, 7, 9, 8, 7],  # Weekly average scores
            "players": [
            {
                "name": "Alisson Becker",
                "club": "Liverpool",
                "weeks": [1, 2, 3, 4, 5],
                "scores": [6, 9, 7, 8, 10],
                "difficulty": [2, 4, 3, 3, 2]
            },
            {
                "name": "Ederson",
                "club": "Manchester City",
                "weeks": [1, 2, 3, 4, 5],
                "scores": [7, 8, 10, 9, 8],
                "difficulty": [2, 4, 3, 3, 2]
            },
            {
                "name": "David Raya",
                "club": "Arsenal",
                "weeks": [1, 2, 3, 4, 5],
                "scores": [5, 7, 8, 7, 9],
                "difficulty": [2, 4, 3, 3, 2]
            },
            {
                "name": "Aaron Ramsdale",
                "club": "Arsenal",
                "weeks": [1, 2, 3, 4, 5],
                "scores": [8, 6, 9, 10, 7],
                "difficulty": [2, 4, 3, 3, 2]
            },
            {
                "name": "Nick Pope",
                "club": "Newcastle United",
                "weeks": [1, 2, 3, 4, 5],
                "scores": [9, 8, 7, 10, 8],
                "difficulty": [2, 4, 3, 3, 2]
            }
        ]
        },
        "defenders": {
            "averageScores": [7, 8, 7, 8, 7],
            "players": [
                {
                    "name": "Virgil van Dijk",
                    "club": "Liverpool",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [10, 9, 8, 7, 10],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Reece James",
                    "club": "Chelsea",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [8, 9, 7, 8, 9],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Luke Shaw",
                    "club": "Manchester United",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [7, 6, 8, 7, 9],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Trent Alexander-Arnold",
                    "club": "Liverpool",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [9, 7, 8, 7, 8],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "João Cancelo",
                    "club": "Manchester City",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [8, 9, 7, 9, 7],
                    "difficulty": [2, 4, 3, 3, 2]
                }
            ]
        },
        "midfielders": {
            "averageScores": [10, 9, 11, 10, 12],  # Weekly average scores
            "players": [
                {
                    "name": "Kevin De Bruyne",
                    "club": "Manchester City",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [12, 15, 14, 9, 17],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Bruno Fernandes",
                    "club": "Manchester United",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [10, 8, 11, 14, 13],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Bukayo Saka",
                    "club": "Arsenal",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [9, 11, 10, 12, 16],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Son Heung-min",
                    "club": "Tottenham Hotspur",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [8, 13, 9, 14, 12],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Mohamed Salah",
                    "club": "Liverpool",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [14, 10, 12, 11, 18],
                    "difficulty": [2, 4, 3, 3, 2]
                }
            ]
        },
        "forwards": {
            "averageScores": [12, 13, 14, 12, 13],  # Weekly average scores
            "players": [
                {
                    "name": "Erling Haaland",
                    "club": "Manchester City",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [15, 18, 16, 14, 20],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Harry Kane",
                    "club": "Tottenham Hotspur",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [14, 12, 15, 16, 17],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Gabriel Jesus",
                    "club": "Arsenal",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [13, 14, 12, 15, 18],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Darwin Núñez",
                    "club": "Liverpool",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [12, 13, 14, 13, 15],
                    "difficulty": [2, 4, 3, 3, 2]
                },
                {
                    "name": "Ollie Watkins",
                    "club": "Aston Villa",
                    "weeks": [1, 2, 3, 4, 5],
                    "scores": [11, 12, 13, 14, 13],
                    "difficulty": [2, 4, 3, 3, 2]
                }
            ]
        }
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
