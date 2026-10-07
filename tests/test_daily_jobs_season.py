import os
os.environ.setdefault('KJ_SKIP_DB_INIT', '1')
import sys

import pytest

import FPL_site.dataModels as dm
import FPL_site.matchPredictionEngine as engine
import FPL_site.futurePerformanceModel as fpm


@pytest.fixture
def rollover(monkeypatch):
    """The update step has just written 2027; refresh_season_start() picks it up."""
    monkeypatch.setattr(dm, 'season_start', 2026)

    def fake_refresh():
        monkeypatch.setattr(dm, 'season_start', 2027)
        return 2027

    monkeypatch.setattr(engine, 'refresh_season_start', fake_refresh)
    monkeypatch.setattr(fpm, 'refresh_season_start', fake_refresh)
    return fake_refresh


def test_match_job_uses_the_year_the_update_just_wrote(rollover, monkeypatch):
    seen = {}

    class Conn:
        def cursor(self, **k):
            return object()

        def close(self):
            pass

    def fit(cursor, current_season=None, current_gw=None):
        seen['fit'] = current_season if current_season is not None else engine.current_season_start()
        return {}, 0.3, 0.0, {}, 6

    monkeypatch.setattr(engine, 'connect_db', lambda: Conn())
    monkeypatch.setattr(engine, 'fit_current_ratings', fit)
    monkeypatch.setattr(engine, 'build_fixture_predictions',
                        lambda cursor, season, *a: seen.setdefault('predict', season) and [])
    monkeypatch.setattr(engine, 'persist_match_predictions', lambda conn, rows: None)
    monkeypatch.setattr(engine, 'log_predictions', lambda *a: None)
    monkeypatch.setattr(engine, 'fetch_teams_for_season',
                        lambda cursor, season: seen.setdefault('teams', season) and {})
    monkeypatch.setattr(engine, 'fetch_squad_rows',
                        lambda cursor, season: seen.setdefault('squad', season) and [])
    monkeypatch.setattr(engine, 'build_team_strengths', lambda *a: [])
    monkeypatch.setattr(engine, 'persist_team_strengths', lambda *a: None)
    import FPL_site.playerMomentum as pm
    monkeypatch.setattr(pm, 'run_daily_momentum', lambda *a: None)
    engine.run_daily_match_predictions()
    assert seen == {'fit': 2027, 'predict': 2027, 'teams': 2027, 'squad': 2027}


def test_player_job_refreshes_the_season_before_preparing_data(rollover, monkeypatch):
    class Stop(Exception):
        pass

    seen = {}

    def prepare():
        seen['year'] = fpm.current_season_start()
        raise Stop

    monkeypatch.setattr(fpm, 'get_current_gameweek', lambda: 0)
    monkeypatch.setattr(fpm, 'prepare_data', prepare)
    with pytest.raises(Stop):
        fpm.run_daily_predictions()
    assert seen['year'] == 2027


def test_sqlfunction_and_the_package_hold_separate_dataModels_copies():
    """Why a lazy import in run_update would not be robust: two module objects, two season_starts."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'FPL_site'))
    import sqlFunction  # noqa: F401  (imports the top-level 'dataModels')
    assert sys.modules['dataModels'] is not dm
