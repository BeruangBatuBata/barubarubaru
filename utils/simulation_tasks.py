# beruangbatubata/barubarubaru/barubarubaru-c62b52c86038cecedd2dda40e096dca331cad981/utils/simulation_tasks.py
import json
import pandas as pd
from celery_config import app
from utils.simulation import (
    run_monte_carlo_simulation,
    run_monte_carlo_simulation_groups,
    get_series_outcome_options
)

# Helper function to extract team names from a match dictionary.
def get_teams_from_match(match):
    opps = match.get("match2opponents", [])
    teamA = opps[0].get('name', 'Team A') if len(opps) > 0 else 'Team A'
    teamB = opps[1].get('name', 'Team B') if len(opps) > 1 else 'Team B'
    return teamA, teamB

@app.task
def run_single_table_simulation_task(teams, played_matches_json, current_wins, current_diff, unplayed_matches_tuples, forced_outcomes, brackets, n_sim, team_to_track=None):
    """
    Celery task wrapper for the single table Monte Carlo simulation.
    All complex objects are passed as JSON-serializable types.
    """
    played_matches = [json.loads(m) for m in played_matches_json]
    
    # Reconstruct complex objects from tuples/lists
    unhashed_brackets = [dict(b) for b in brackets]

return run_monte_carlo_simulation(
    list(teams),
    played_matches,
    dict(current_wins),
    dict(current_diff),
    list(unplayed_matches_tuples),
    dict(forced_outcomes),
    unhashed_brackets, # <--- CORRECTED LINE
    n_sim,
    team_to_track=team_to_track
)

@app.task
def run_group_simulation_task(groups, played_matches_json, current_wins, current_diff, unplayed_matches_tuples, forced_outcomes, brackets, n_sim, team_to_track=None):
    """
    Celery task wrapper for the group stage Monte Carlo simulation.
    """
    played_matches = [json.loads(m) for m in played_matches_json]

    unhashed_brackets = [dict(b) for b in brackets]

return run_monte_carlo_simulation_groups(
    groups,
    played_matches,
    dict(current_wins),
    dict(current_diff),
    list(unplayed_matches_tuples),
    dict(forced_outcomes),
    unhashed_brackets, # <--- CORRECTED LINE
    n_sim,
    team_to_track=team_to_track
)

# --- NEW TASK ADDED BELOW ---
@app.task(bind=True)
def run_deeper_analysis_task(
    self, simulation_type, teams, played_json, current_wins, current_diff, 
    unplayed_tuples, unplayed_matches_full, forced_outcomes, brackets, 
    n_sim, selected_team_analysis, base_results_df_dict, groups=None
):
    """
    A consolidated Celery task to run all parts of the 'Deeper Analysis'.
    This is more efficient than dispatching many small, interdependent tasks.
    """
    results = {}
    total_steps = 3 # Total number of analysis steps
    
    # --- Determine which simulation function to use based on the context ---
    is_group_sim = (simulation_type == 'group')
    
    def run_simulation(forced_scenario_dict):
        """Helper to run the correct simulation type with updated scenarios."""
        # The 'brackets' argument arrives as a tuple of tuples.
        # We must convert it back to a list of dicts for the simulation functions.
        unhashed_brackets = [dict(b) for b in brackets] # <--- CORRECTED LOGIC
        
        if is_group_sim:
            return run_monte_carlo_simulation_groups(
                groups, [json.loads(m) for m in played_json], dict(current_wins), dict(current_diff),
                list(unplayed_tuples), forced_scenario_dict, unhashed_brackets, n_sim
            )
        else:
            return run_monte_carlo_simulation(
                list(teams), [json.loads(m) for m in played_json], dict(current_wins), dict(current_diff),
                list(unplayed_tuples), forced_scenario_dict, unhashed_brackets, n_sim
            )

    # --- 1. "Win and In" Scenario ---
    self.update_state(state='PROGRESS', meta={'current': 1, 'total': total_steps, 'status': 'Calculating "Win and In" scenario...'})
    team_unplayed_matches = [m for m in unplayed_matches_full if selected_team_analysis in get_teams_from_match(m)]
    forced_wins = dict(forced_outcomes).copy()
    for match in team_unplayed_matches:
        teamA, teamB = get_teams_from_match(match)
        match_key = (teamA, teamB, match.get('date'))
        # Assuming BO3 for simplicity; in a real scenario, you might pass the 'bestof' format
        if teamA == selected_team_analysis:
            forced_wins[match_key] = "A20" 
        else:
            forced_wins[match_key] = "B20"
            
    win_out_data = run_simulation(forced_wins)
    # Serialize DataFrame to dict for the final result
    results['win_and_in_df'] = win_out_data['probs_df'].to_dict()

    # --- 2. "Most Important Match" Analysis ---
    self.update_state(state='PROGRESS', meta={'current': 2, 'total': total_steps, 'status': 'Finding most important match...'})
    positive_brackets = [b['name'] for b in brackets if "unqualified" not in b['name'].lower() and "relegation" not in b['name'].lower()]
    max_swing = -1.0
    most_important_match_info = None

    for match in team_unplayed_matches:
        teamA, teamB = get_teams_from_match(match)
        opponent = teamB if teamA == selected_team_analysis else teamA
        match_key = (teamA, teamB, match.get('date'))

        # Scenario where the selected team wins
        forced_win_scenario = dict(forced_outcomes).copy()
        forced_win_scenario[match_key] = "A20" if teamA == selected_team_analysis else "B20"
        
        # Scenario where the selected team loses
        forced_loss_scenario = dict(forced_outcomes).copy()
        forced_loss_scenario[match_key] = "B20" if teamA == selected_team_analysis else "A20"
        
        win_df = run_simulation(forced_win_scenario)['probs_df']
        loss_df = run_simulation(forced_loss_scenario)['probs_df']

        win_prob_cumulative = sum(win_df.loc[win_df['Team'] == selected_team_analysis, f"{b} (%)"].iloc[0] for b in positive_brackets)
        loss_prob_cumulative = sum(loss_df.loc[loss_df['Team'] == selected_team_analysis, f"{b} (%)"].iloc[0] for b in positive_brackets)
        
        swing = abs(win_prob_cumulative - loss_prob_cumulative)

        if swing > max_swing:
            max_swing = swing
            most_important_match_info = {
                "opponent": opponent, 
                "win_df": win_df.to_dict(), 
                "loss_df": loss_df.to_dict()
            }
    
    results['most_important_match'] = most_important_match_info
    
    # --- 3. "Who to Root For" (Critical External Matches) ---
    self.update_state(state='PROGRESS', meta={'current': 3, 'total': total_steps, 'status': 'Finding critical external matches...'})
    external_matches = [m for m in unplayed_matches_full if selected_team_analysis not in get_teams_from_match(m)]
    base_df = pd.DataFrame.from_dict(base_results_df_dict)
    base_cumulative_prob = sum(base_df.loc[base_df['Team'] == selected_team_analysis, f"{b} (%)"].iloc[0] for b in positive_brackets)
    
    best_impact = 0.01  # Minimum threshold for a result to be considered significant
    best_external_match_info = None

    for match in external_matches:
        teamA, teamB = get_teams_from_match(match)
        bo = match.get("bestof", 3)
        outcomes = get_series_outcome_options(teamA, teamB, bo)

        for outcome_label, outcome_code in outcomes:
            if outcome_code == "random": continue
            
            forced_scenario = dict(forced_outcomes).copy()
            match_key = (teamA, teamB, match.get('date'))
            forced_scenario[match_key] = outcome_code
            
            scenario_df = run_simulation(forced_scenario)['probs_df']
            
            scenario_cumulative_prob = sum(scenario_df.loc[scenario_df['Team'] == selected_team_analysis, f"{b} (%)"].iloc[0] for b in positive_brackets)
            impact = scenario_cumulative_prob - base_cumulative_prob

            if impact > best_impact:
                best_impact = impact
                best_external_match_info = {
                    "teams": f"{teamA} vs {teamB}", 
                    "outcome": outcome_label, 
                    "scenario_df": scenario_df.to_dict()
                }

    results['best_external_match'] = best_external_match_info

    return results
