# utils/simulation_tasks.py

from celery_config import app
from utils.simulation import run_monte_carlo_simulation, run_monte_carlo_simulation_groups
import json

# Note: Celery can't pass complex objects like DataFrames, so we pass JSON-serializable data.
# The original functions already accept simple data types, which is perfect.

@app.task(bind=True)
def run_single_table_sim_task(self, teams, played_matches_json, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim, team_to_track=None):
    """Celery task for single-table simulation."""
    try:
        # We need to deserialize the JSON data back into the format the function expects
        played_matches = [json.loads(m) for m in played_matches_json]
        
        results = run_monte_carlo_simulation(
            teams, played_matches, dict(current_wins), dict(current_diff),
            unplayed_matches, dict(forced_outcomes), [dict(b) for b in brackets],
            n_sim, team_to_track
        )
        # Convert the resulting DataFrame to JSON so it can be sent back
        results['probs_df'] = results['probs_df'].to_json(orient='split')
        return results
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        return {'status': 'Failed', 'result': str(e)}


@app.task(bind=True)
def run_group_sim_task(self, groups, played_matches_json, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim, team_to_track=None):
    """Celery task for group stage simulation."""
    try:
        played_matches = [json.loads(m) for m in played_matches_json]

        results = run_monte_carlo_simulation_groups(
            groups, played_matches, dict(current_wins), dict(current_diff),
            unplayed_matches, dict(forced_outcomes), [dict(b) for b in brackets],
            n_sim, team_to_track
        )
        results['probs_df'] = results['probs_df'].to_json(orient='split')
        return results
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        return {'status': 'Failed', 'result': str(e)}
