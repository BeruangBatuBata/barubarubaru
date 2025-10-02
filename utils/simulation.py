import pandas as pd
import random
import json
import os
from collections import defaultdict
import math
from math import comb

# --- UNIFIED CONFIGURATION FUNCTIONS ---

def get_permanent_config_path(tournament_name):
    """Generate the standard path for a permanent tournament config file."""
    return os.path.join("configs", f"{tournament_name.replace(' ', '_')}.json")

def load_unified_config(tournament_name):
    """
    Loads a tournament's complete configuration with a clear priority:
    1. Session-specific (cached) file (e.g., .playoff_config_...)
    2. Permanent file in the /configs/ directory
    3. Default values
    """
    session_bracket_file = get_bracket_cache_key(tournament_name)
    session_group_file = get_group_cache_key(tournament_name)
    session_format_file = get_format_cache_key(tournament_name)
    permanent_file = get_permanent_config_path(tournament_name)

    config = {
        "tournament_name": tournament_name,
        "format": None,
        "groups": {},
        "brackets": []
    }

    # 1. Load from permanent file first to establish a base
    if os.path.exists(permanent_file):
        try:
            with open(permanent_file, 'r') as f:
                config.update(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass # Fallback to defaults if file is corrupt

    # 2. Override with session-specific files if they exist
    if os.path.exists(session_format_file):
        try:
            with open(session_format_file, 'r') as f:
                config['format'] = json.load(f).get('format')
        except (json.JSONDecodeError, IOError):
            pass

    if os.path.exists(session_group_file):
        try:
            with open(session_group_file, 'r') as f:
                config['groups'] = json.load(f).get('groups', {})
        except (json.JSONDecodeError, IOError):
            pass

    if os.path.exists(session_bracket_file):
        try:
            with open(session_bracket_file, 'r') as f:
                config['brackets'] = json.load(f).get('brackets', [])
        except (json.JSONDecodeError, IOError):
            pass

    # 3. Apply defaults if any part of the config is still missing
    if not config.get('format'):
        config['format'] = 'single_table' # Default format

    if not config.get('brackets'):
        config['brackets'] = [
            {"start": 1, "end": 2, "name": "Upper Bracket"},
            {"start": 3, "end": 6, "name": "Play-in"},
            {"start": 7, "end": 9, "name": "Eliminated"}
        ]

    return config

# The old individual save/load functions are kept for session-specific operations

def get_bracket_cache_key(tournament_name):
    """Generate a unique filename for a tournament's bracket config."""
    return f".playoff_config_{tournament_name.replace(' ', '_')}.json"

def load_bracket_config(tournament_name):
    """Load a saved bracket configuration."""
    config = load_unified_config(tournament_name)
    return {"brackets": config['brackets']}


def save_bracket_config(tournament_name, config):
    """Save a bracket configuration to a local session file."""
    cache_file = get_bracket_cache_key(tournament_name)
    try:
        with open(cache_file, 'w') as f:
            json.dump(config, f)
        return True
    except Exception:
        return False

def get_format_cache_key(tournament_name):
    """Generate a unique filename for a tournament's format choice."""
    return f".tournament_format_{tournament_name.replace(' ', '_')}.json"


def load_tournament_format(tournament_name):
    """Load a saved format choice."""
    return load_unified_config(tournament_name).get('format')


def save_tournament_format(tournament_name, format_choice):
    """Save a format choice to a local session file."""
    cache_file = get_format_cache_key(tournament_name)
    try:
        with open(cache_file, 'w') as f:
            json.dump({"format": format_choice}, f)
        return True
    except Exception:
        return False

def get_group_cache_key(tournament_name):
    """Generate a unique filename for a tournament's group config."""
    return f".group_config_{tournament_name.replace(' ', '_')}.json"


def load_group_config(tournament_name):
    """Load a saved group configuration."""
    config = load_unified_config(tournament_name)
    return {"groups": config['groups']}


def save_group_config(tournament_name, config):
    """Save a group configuration to a local session file."""
    cache_file = get_group_cache_key(tournament_name)
    try:
        with open(cache_file, 'w') as f:
            json.dump(config, f)
        return True
    except Exception:
        return False

# --- HELPER FUNCTIONS ---
def get_series_outcome_options(teamA, teamB, bo: int):
    opts = [("Random", "random")]
    if bo == 3:
        opts += [(f"{teamA} 2–0", "A20"), (f"{teamA} 2–1", "A21"), (f"{teamB} 2–1", "B21"), (f"{teamB} 2–0", "B20")]
    return opts

def build_standings_table(teams, played_matches):
    stats = {team: {'match_wins': 0, 'match_count': 0, 'game_wins': 0, 'game_losses': 0} for team in teams}
    
    for m in played_matches:
        opps = m.get("match2opponents", [])
        if len(opps) < 2: continue
        
        team_a = opps[0].get('name')
        team_b = opps[1].get('name')
        
        # This check is still useful to prevent errors if a team from a match isn't in the master list
        if team_a not in stats or team_b not in stats:
            continue
            
        score_a = 0
        score_b = 0
        for game in m.get("match2games", []):
            if game.get('winner') == '1':
                score_a += 1
            elif game.get('winner') == '2':
                score_b += 1

        stats[team_a]['match_count'] += 1
        stats[team_b]['match_count'] += 1
        stats[team_a]['game_wins'] += score_a
        stats[team_a]['game_losses'] += score_b
        stats[team_b]['game_wins'] += score_b
        stats[team_b]['game_losses'] += score_a
        
        if m.get("winner") == "1":
            stats[team_a]['match_wins'] += 1
        elif m.get("winner") == "2":
            stats[team_b]['match_wins'] += 1
            
    rows = []
    # --- MODIFICATION START: The incorrect "if" condition is removed ---
    # The loop now processes every team, ensuring the table is always fully populated.
    for team, data in stats.items():
        mw = data['match_wins']
        ml = data['match_count'] - data['match_wins']
        gw = data['game_wins']
        gl = data['game_losses']
        diff = gw - gl
        rows.append({
            "Team": team, 
            "Match W-L": f"{mw}-{ml}", 
            "Game W-L": f"{gw}-{gl}", 
            "Diff": diff, 
            "_MW": mw, 
            "_Diff": diff
        })
    # --- MODIFICATION END ---
            
    if not rows: return pd.DataFrame()
    
    df = pd.DataFrame(rows).sort_values(by=["_MW", "_Diff"], ascending=[False, False]).reset_index(drop=True)
    df = df.drop(columns=["_MW", "_Diff"])
    df.index += 1
    return df

def build_week_blocks(dates_str):
    """Groups dates into week-long blocks."""
    if not dates_str: return []
    
    # Convert string dates to datetime.date objects for comparison
    dates = []
    for d_str in dates_str:
        try:
            # pd.to_datetime is robust and handles various formats
            dates.append(pd.to_datetime(d_str).date())
        except (ValueError, TypeError):
            continue # Skip if a date string is invalid
    
    if not dates: return []

    # Sort the converted dates
    dates = sorted(list(set(dates)))

    blocks = [[dates[0]]]
    for prev, curr in zip(dates, dates[1:]):
        if (curr - prev).days <= 2:
            blocks[-1].append(curr)
        else:
            blocks.append([curr])
    return blocks

### --- MODIFIED --- ###
def calculate_series_score_probs(p_win, n_games):
    """
    Calculates the probabilities of all possible series scores in a best-of-n series.
    p_win: The probability of the 'main' team (e.g., Blue Team) winning a single game.
    n_games: The total number of games in the series (e.g., 3 for a Bo3).
    """
    if p_win is None or not (0 <= p_win <= 1):
        return {}

    p_lose = 1 - p_win
    games_to_win = (n_games // 2) + 1
    probs = {}

    # Calculate probabilities for the Blue team winning the series
    for games_lost in range(games_to_win):
        total_games_played = games_to_win + games_lost
        if total_games_played > n_games:
            continue
        
        combinations = comb(total_games_played - 1, games_to_win - 1)
        probability = combinations * (p_win ** games_to_win) * (p_lose ** games_lost)
        
        score = f"{games_to_win}-{games_lost}"
        probs[score] = probability

    # Calculate probabilities for the Red team winning the series
    for games_won in range(games_to_win):
        total_games_played = games_to_win + games_won
        if total_games_played > n_games:
            continue

        combinations = comb(total_games_played - 1, games_to_win - 1)
        probability = combinations * (p_lose ** games_to_win) * (p_win ** games_won)
        
        score = f"{games_won}-{games_to_win}"
        probs[score] = probability

    return probs
### --- END MODIFIED --- ###

# --- SIMULATION ENGINES ---
def run_monte_carlo_simulation(teams, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim, team_to_track=None):
    """
    Runs the full Monte Carlo simulation and tracks best/worst rank for a specific team.
    """
    finish_counter = {t: {b["name"]: 0 for b in brackets} for t in teams}
    
    # Initialize trackers for the new feature
    best_rank = len(teams)
    worst_rank = 1

    for _ in range(n_sim):
        sim_wins = defaultdict(int, current_wins)
        sim_diff = defaultdict(int, current_diff)
        for a, b, dt, bo in unplayed_matches:
            code = forced_outcomes.get((a, b, dt), "random")
            outcome = random.choice([c for _, c in get_series_outcome_options(a, b, bo) if c != "random"]) if code == "random" else code
            if outcome == "DRAW": continue
            winner, loser = (a, b) if outcome.startswith("A") else (b, a)
            num = outcome[1:]; w, l = (int(num[0]), int(num[1])) if len(num) == 2 else (int(num), 0)
            sim_wins[winner] += 1; sim_diff[winner] += w - l; sim_diff[loser] += l - w
        
        ranked_teams = sorted(teams, key=lambda t: (sim_wins.get(t, 0), sim_diff.get(t, 0), random.random()), reverse=True)
        
        for pos, team in enumerate(ranked_teams):
            rank = pos + 1
            
            for bracket in brackets:
                start, end = bracket["start"], bracket.get("end") or len(teams)
                if start <= rank <= end:
                    finish_counter[team][bracket["name"]] += 1
                    break
            
            if team == team_to_track:
                if rank < best_rank:
                    best_rank = rank
                if rank > worst_rank:
                    worst_rank = rank

    rows = []
    for t in teams:
        row = {"Team": t}
        for bracket in brackets:
            row[f"{bracket['name']} (%)"] = (finish_counter[t].get(bracket["name"], 0) / n_sim) * 100
        rows.append(row)
    
    probs_df = pd.DataFrame(rows).round(2)

    results = {"probs_df": probs_df}
    if team_to_track:
        results["best_rank"] = best_rank
        results["worst_rank"] = worst_rank
        
    return results


def run_monte_carlo_simulation_groups(groups, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim, team_to_track=None):
    """
    Runs a Monte Carlo simulation for a tournament with a group stage format.

    Args:
        groups (dict): A dictionary where keys are group names and values are lists of team names.
        current_wins (tuple): A tuple of (team, wins) tuples representing the current standings.
        current_diff (tuple): A tuple of (team, diff) tuples for game score differential.
        unplayed_matches (tuple): A tuple of (teamA, teamB, date, bestof) tuples for matches to be simulated.
        forced_outcomes (tuple): A tuple of ((teamA, teamB, date), outcome_code) tuples for user-defined results.
        brackets (tuple): A tuple of dictionaries, each defining a playoff bracket (e.g., {"name": "Upper Bracket", "start": 1, "end": 4}).
        n_sim (int): The number of simulation iterations to run.
        team_to_track (str, optional): A specific team to gather detailed analytics for (best/worst rank). Defaults to None.

    Returns:
        dict: A dictionary containing the simulation results, including a DataFrame of probabilities,
              best/worst possible rank for the tracked team, and their rank distribution.
    """
    # Initialize dictionaries to store simulation results
    team_rank_counts = defaultdict(lambda: defaultdict(int))
    bracket_counts = {b['name']: defaultdict(int) for b in brackets}
    best_ranks = defaultdict(lambda: 99) # Initialize best rank to a high number
    worst_ranks = defaultdict(int)      # Initialize worst rank to zero

    # Convert tuples back to dictionaries for efficient lookups inside the loop
    forced_outcomes_dict = dict(forced_outcomes)
    current_wins_dict = dict(current_wins)
    current_diff_dict = dict(current_diff)

    # Main simulation loop
    for _ in range(n_sim):
        # Create a copy of the current standings for this single simulation run
        sim_wins = defaultdict(int, current_wins_dict)
        sim_diff = defaultdict(int, current_diff_dict)

        # Iterate through each match that hasn't been played yet
        for teamA, teamB, match_date, bestof in unplayed_matches:
            
            # --- START: CORRECTED LOGIC ---

            # 1. Check if the user has forced an outcome for this specific match.
            #    If not, the outcome is "random", and we need to simulate it.
            outcome = forced_outcomes_dict.get((teamA, teamB, match_date), "random")

            # 2. If the outcome is "random", we generate a result.
            if outcome == "random":
                # Get all valid, non-random outcomes for the given "best of" format.
                possible_outcomes = [code for _, code in get_series_outcome_options(teamA, teamB, bestof) if code != "random"]
                
                # 3. SAFEGUARD: If no outcomes are possible (due to invalid 'bestof' data),
                #    skip this match to prevent a crash and log a warning.
                if not possible_outcomes:
                    # Optional: print a warning to the console for debugging data issues.
                    # print(f"Warning: No possible outcomes for match {teamA} vs {teamB} (Bo{bestof}). Skipping.")
                    continue
                
                # Select a random outcome from the valid possibilities.
                outcome = random.choice(possible_outcomes)
            
            # --- END: CORRECTED LOGIC ---

            # Process the definitive outcome (either user-forced or randomly simulated).
            if outcome == "DRAW":
                # If the outcome is a draw (e.g., in a Bo2), no team gets a series win.
                # The score differential is handled by the rules of get_series_outcome_options.
                continue

            # Determine the winner and loser from the outcome code (e.g., "A21")
            winner, loser = (teamA, teamB) if outcome.startswith("A") else (teamB, teamA)
            score_part = outcome[1:]
            
            # Update wins and score differential based on the match result
            if len(score_part) == 2:
                score_winner, score_loser = int(score_part[0]), int(score_part[1])
                sim_wins[winner] += 1
                sim_diff[winner] += score_winner - score_loser
                sim_diff[loser] += score_loser - score_winner

        # After simulating all matches for one iteration, calculate the final standings.
        final_standings = {}
        for group_name, group_teams in groups.items():
            # Sort teams within each group based on wins, then score differential.
            group_standings = sorted(
                group_teams,
                key=lambda t: (sim_wins.get(t, 0), sim_diff.get(t, 0)),
                reverse=True
            )
            # Record the final rank for each team in this simulation run.
            for rank, team in enumerate(group_standings, 1):
                final_standings[team] = (rank, group_name)
                # If this is the team we are tracking, update its best/worst rank seen so far.
                if team == team_to_track:
                    best_ranks[team] = min(best_ranks[team], rank)
                    worst_ranks[team] = max(worst_ranks[team], rank)

        # Tally the results for this simulation run.
        for team, (rank, group) in final_standings.items():
            team_rank_counts[team][rank] += 1
            # Check which playoff bracket the team falls into based on their rank.
            for bracket in brackets:
                if bracket['start'] <= rank <= bracket['end']:
                    bracket_counts[bracket['name']][team] += 1

    # After all simulations are complete, compile the final probability data.
    probs_data = []
    all_teams_in_groups = sorted([team for teams in groups.values() for team in teams])
    for team in all_teams_in_groups:
        team_probs = {"Team": team, "Group": next((g for g, t in groups.items() if team in t), "N/A")}
        # Calculate the percentage chance for each team to land in each bracket.
        for bracket_name, counts in bracket_counts.items():
            team_probs[f"{bracket_name} (%)"] = (counts.get(team, 0) / n_sim) * 100
        probs_data.append(team_probs)

    # Return a dictionary containing the results.
    return {
        "probs_df": pd.DataFrame(probs_data),
        "best_rank": best_ranks.get(team_to_track),
        "worst_rank": worst_ranks.get(team_to_track),
        "rank_dist": team_rank_counts.get(team_to_track)
    }

def _run_single_simulation_instance(teams, initial_wins, initial_diff, unplayed_matches, forced_outcomes):
    """
    Simulates one possible future for a single table format and returns the ranked teams.
    """
    sim_wins = defaultdict(int, initial_wins)
    sim_diff = defaultdict(int, initial_diff)

    for a, b, dt, bo in unplayed_matches:
        # Use a specific forced outcome if provided, otherwise pick a random one
        code = forced_outcomes.get((a, b, dt), "random")
        if code == "random":
            # Generate possible outcomes (e.g., "A20", "A21", "B21", "B20")
            options = [c for _, c in get_series_outcome_options(a, b, bo) if c != "random"]
            outcome = random.choice(options)
        else:
            outcome = code
        
        if outcome == "DRAW":
            continue

        winner = a if outcome.startswith("A") else b
        loser = b if outcome.startswith("A") else a
        
        score_str = outcome[1:]
        w_score = int(score_str[0])
        l_score = int(score_str[1])
        
        sim_wins[winner] += 1
        sim_diff[winner] += w_score - l_score
        sim_diff[loser] += l_score - w_score
        
    # Rank teams by wins, then diff, with a random tie-breaker
    ranked = sorted(teams, key=lambda t: (sim_wins.get(t, 0), sim_diff.get(t, 0), random.random()), reverse=True)
    return ranked

CONFIG_DIR = "configs"

def get_config_path(tournament_name, config_type):
    """Generates the file path for a given tournament and config type."""
    safe_filename = "".join(c for c in tournament_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
    return os.path.join(CONFIG_DIR, f"{safe_filename}_{config_type}.json")

def delete_tournament_configs(tournament_name):
    """
    Deletes all configuration files associated with a specific tournament.
    """
    if not os.path.exists(CONFIG_DIR):
        return # No directory, so nothing to delete.

    configs_to_delete = [
        get_config_path(tournament_name, 'format'),
        get_config_path(tournament_name, 'groups'),
        get_config_path(tournament_name, 'brackets')
    ]
    
    deleted_files = []
    for path in configs_to_delete:
        if os.path.exists(path):
            try:
                os.remove(path)
                deleted_files.append(os.path.basename(path))
            except OSError as e:
                # Optional: log an error if a file can't be deleted
                print(f"Error deleting file {path}: {e}")
    
    return deleted_files
