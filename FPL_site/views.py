from datetime import datetime
from flask import render_template, request, jsonify
from FPL_site import app  # Correct import statement
from .dataModels import (
    get_player_points, get_players, get_players_by_team, 
    get_players_by_position, get_comparison_stats, 
    get_player_index_scores, get_player_net_transfers
)

@app.route('/')
def home():
    return render_template('home.html', title='Home Page', year=datetime.now().year)

@app.route('/players')
def players():
    player_data = get_player_points()
    sorted_data = sorted(player_data.items(), key=lambda x: x[1], reverse=True)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('players.html', is_ajax=is_ajax, players=sorted_data, title='Player Points', year=datetime.now().year)

@app.route('/player_data')
def player_points():
    start = request.args.get('start', default=0, type=int)
    limit = request.args.get('limit', default=30, type=int)
    data = get_player_points()
    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
    segment = sorted_data[start:start + limit]
    return jsonify(segment)

@app.route('/team')
def team():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('team.html', is_ajax=is_ajax, title='Team')

@app.route('/compare')
def compare():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('compare.html', is_ajax=is_ajax, title='Player Comparison')

@app.route('/get_players')
def get_players_route():
    players = get_players()
    return jsonify(players)

@app.route('/get_players_by_team')
def get_players_by_team_route():
    players = get_players_by_team()
    return jsonify(players)

@app.route('/get_players_by_position')
def get_players_by_position_route():
    players = get_players_by_position()
    return jsonify(players)

@app.route('/get_player_index_scores')
def get_player_index_scores_route():
    try:
        players = get_player_index_scores()
        return jsonify(players)
    except Exception as e:
        return str(e), 500

@app.route('/get_player_net_transfers')
def get_player_net_transfers_route():
    try:
        player_id = request.args.get('id')
        net_transfers = get_player_net_transfers(player_id)
        return jsonify(net_transfers)
    except Exception as e:
        return str(e), 500

@app.route('/compare_players')
def compare_players_route():
    id1 = request.args.get('id1', type=int)
    id2 = request.args.get('id2', type=int)
    players_data = get_comparison_stats(id1, id2)
    return jsonify(players_data)
