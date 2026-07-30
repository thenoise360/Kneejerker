from datetime import datetime
from re import M
from flask import render_template, request, jsonify, send_from_directory, abort, redirect, url_for
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
    get_under_the_radar_players, get_worth_watching_players, get_most_consistent_players,
    get_momentum_players, get_new_manager_players, get_player_ownership_history,
    next_5_gameweeks, fetch_player_summary, get_alternative_players, top_5_players_last_5_weeks,
    get_player_last_5_points, generateCurrentGameweek,
    get_gameweek_state, get_live_gameweek_view, get_comparison_averages_last_5
)

from .matchPredictionEngine import load_team_fixture_outlook, list_current_teams

# Remove ==================================================

@app.route('/privacy')
def privacy():
    logger.info("Request for privacy page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('privacy.html', is_ajax=is_ajax, title='Privacy policy', mixpanel_token=current_config.MIXPANEL_TOKEN)

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
def index():
    return redirect(url_for('home'))

@app.route('/this-week')
def home():
    logger.info("Request for home page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    # Computed server-side (06.0) since it's cheap and changes infrequently -
    # no need for the client to poll for it.
    gw_state = get_gameweek_state()
    return render_template('home.html', is_ajax=is_ajax, title='This Week', year=datetime.now().year, mixpanel_token=current_config.MIXPANEL_TOKEN, gw_state=gw_state)

@app.route('/radar')
def radar():
    logger.info("Request for radar page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('radar.html', is_ajax=is_ajax, title='Radar', mixpanel_token=current_config.MIXPANEL_TOKEN)

@app.route('/discovery')
def discovery():
    logger.info("Request for discovery page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('discovery.html', is_ajax=is_ajax, title='Discover', mixpanel_token=current_config.MIXPANEL_TOKEN)

@app.route('/api/net-transfers-in')
def net_transfers_in():
    data = get_top_10_net_transfers_in()
    return jsonify(data)

@app.route('/api/net-transfers-out')
def net_transfers_out():
    data = get_top_10_net_transfers_out()
    return jsonify(data)

@app.route('/api/header-info')
def header_info():
    try:
        current_gw = generateCurrentGameweek()
        response = requests.get('https://fantasy.premierleague.com/api/bootstrap-static/')
        if response.status_code == 200:
            data = response.json()
            next_event = next((e for e in data['events'] if e['is_next']), None)
            return jsonify({
                'current_gw': current_gw,
                'deadline': next_event['deadline_time'] if next_event else None
            })
    except Exception as e:
        logger.error(f"Error fetching header info: {e}")
    return jsonify({'error': 'Failed to fetch data'}), 500

@app.route('/api/live-gameweek')
def live_gameweek():
    team_id = request.args.get('team_id')
    if not team_id or not team_id.isdigit():
        return jsonify({'error': 'invalid_team_id'}), 400

    try:
        data = get_live_gameweek_view(int(team_id))
    except Exception as e:
        logger.error(f"Error building live gameweek view: {e}")
        return jsonify({'error': 'server_error'}), 500

    if data.get('error') == 'invalid_team_id':
        return jsonify(data), 404

    return jsonify(data)

@app.route('/api/relative-ownership')
def relative_ownership():
    data = get_player_ownership()
    return jsonify(data)


@app.route('/api/top-5-players')
def top_5_players():
    data = top_5_players_last_5_weeks()
    return jsonify(data)

@app.route('/clubs')
def clubs():
    logger.info("Request for clubs list page")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template('clubs.html', is_ajax=is_ajax, title='Clubs', mixpanel_token=current_config.MIXPANEL_TOKEN)

@app.route('/api/clubs')
def clubs_list():
    logger.info("Request for clubs list")
    return jsonify(list_current_teams())

@app.route('/club/<int:team_id>')
def club(team_id):
    logger.info(f"Request for club page: team_id={team_id}")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return render_template(
        'club.html', is_ajax=is_ajax, title='Fixture outlook',
        mixpanel_token=current_config.MIXPANEL_TOKEN, team_id=team_id
    )

@app.route('/api/club/<int:team_id>/fixture-outlook')
def club_fixture_outlook(team_id):
    logger.info(f"Request for club fixture outlook: team_id={team_id}")
    try:
        outlook = load_team_fixture_outlook(team_id)
    except Exception as e:
        logger.error(f"Error building club fixture outlook: {e}")
        return jsonify({'error': 'server_error'}), 500

    if outlook is None:
        return jsonify({'error': 'unknown_team'}), 404

    return jsonify(outlook)

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

@app.route('/get_under_the_radar')
def get_under_the_radar():
    logger.info("Request for get_under_the_radar")
    try:
        players = get_under_the_radar_players()
        return jsonify(players)
    except Exception as e:
        logger.error(f"Error in get_under_the_radar: {str(e)}")
        return str(e), 500

@app.route('/get_worth_watching')
def get_worth_watching():
    logger.info("Request for get_worth_watching")
    try:
        players = get_worth_watching_players()
        return jsonify(players)
    except Exception as e:
        logger.error(f"Error in get_worth_watching: {str(e)}")
        return str(e), 500

@app.route('/get_most_consistent')
def get_most_consistent():
    logger.info("Request for get_most_consistent")
    try:
        players = get_most_consistent_players()
        return jsonify(players)
    except Exception as e:
        logger.error(f"Error in get_most_consistent: {str(e)}")
        return str(e), 500

@app.route('/get_momentum')
def get_momentum():
    logger.info("Request for get_momentum")
    try:
        players = get_momentum_players()
        return jsonify(players)
    except Exception as e:
        logger.error(f"Error in get_momentum: {str(e)}")
        return str(e), 500

@app.route('/get_new_manager')
def get_new_manager():
    logger.info("Request for get_new_manager")
    try:
        players = get_new_manager_players()
        return jsonify(players)
    except Exception as e:
        logger.error(f"Error in get_new_manager: {str(e)}")
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

@app.route('/get_player_last_5_points')
def get_player_last_5_points_route():
    logger.info("Request for get_player_last_5_points")
    try:
        player_id = request.args.get('id')
        data = get_player_last_5_points(player_id)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e), 500

@app.route('/get_player_ownership_history')
def get_player_ownership_history_route():
    logger.info("Request for get_player_ownership_history")
    try:
        player_id = request.args.get('id')
        data = get_player_ownership_history(player_id)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return str(e), 500

@app.route('/get_comparison_averages')
def get_comparison_averages_route():
    logger.info("Request for get_comparison_averages")
    try:
        position = request.args.get('position')
        data = get_comparison_averages_last_5(position)
        return jsonify(data)
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

