from datetime import datetime
from flask import render_template, request, jsonify
from FPL_site import app
from . import gameweekSummary
from models import get_player_points, get_comparison_stats, get_players

@app.route('/')
def home():
    return render_template('home.html', title='Home Page', year=datetime.now().year)

@app.route('/players')
def players():
    player_data = get_player_points()
    sorted_data = sorted(player_data.items(), key=lambda x: x[1], reverse=True)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('player.html', players=sorted_data)
    return render_template('player.html', players=sorted_data, title='Player Points', year=datetime.now().year)

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
    return render_template('team.html', title='Team', year=datetime.now().year)


@app.route('/compare')
def compare():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('compare.html', is_ajax=is_ajax, title='Player Comparison')

@app.route('/get_players')
def get_players_route():
    players = get_players()
    return jsonify(players)

@app.route('/compare_players')
def compare_players_route():
    id1 = request.args.get('id1', type=int)
    id2 = request.args.get('id2', type=int)
    players_data = get_comparison_stats(id1, id2)
    return jsonify(players_data)
