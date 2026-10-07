import sys
import os
import logging

# Ensure the FPL_site directory is in the sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
if os.path.join(project_root, 'FPL_site') not in sys.path:
    sys.path.append(os.path.join(project_root, 'FPL_site'))

from sqlFunction import update_all_tables
from FPL_site.dataModels import refresh_season_start
from FPL_site.futurePerformanceModel import run_daily_predictions
from FPL_site.matchPredictionEngine import run_daily_match_predictions

logger = logging.getLogger(__name__)

# Each job persists to its own table and is independent of the others - one
# job failing (e.g. run_daily_predictions() on an empty preseason training
# set) must not stop the rest from running and refreshing their own data.
#
# The season is never frozen at import for these jobs: after the update step has (possibly) written
# a new season, refresh_season_start() re-reads it, and the model jobs also re-read it at the top
# of their own run and look it up at call time (dataModels.current_season_start()).
for job in (update_all_tables, run_daily_predictions, run_daily_match_predictions):
    try:
        job()
    except Exception:
        logger.exception(f"run_update.py: {job.__name__} failed, continuing with remaining jobs.")
    if job is update_all_tables:
        refresh_season_start()