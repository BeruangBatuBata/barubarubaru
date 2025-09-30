import pandas as pd
import random
import json
import os
from collections import defaultdict
import math
from math import comb

# --- BRACKET CONFIGURATION FUNCTIONS ---
def get_bracket_cache_key(tournament_name):
    """Generate a unique filename for a tournament's bracket config."""
    return f".playoff_config_{tournament_name.replace(' ', '_')}.json"

def load_bracket_config(tournament_name):
    """Load a saved bracket configuration from a local JSON file."""
    cache_file = get_bracket_cache_key(tournament_name)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "brackets": [
            {"start": 1, "end": 2, "name": "Top 2 Seed"},
            {"start": 3, "end": 6, "name": "Playoff (3-6)"},
            {"start": 7, "end": None, "name": "Unqualified"}
        ]
    }

def save_bracket_config(tournament_name, config):
    """Save a bracket configuration to a local JSON file."""
    cache_file = get_bracket_cache_key(tournament_name)
    try:
        with open(cache_file, 'w') as f:
            json.dump(config, f)
        return True
    except Exception:
        return False

# --- TOURNAMENT FORMAT CONFIGURATION FUNCTIONS ---
def get_format_cache_key(tournament_name):
    """Generate a unique filename for a tournament's format choice."""
    return f".tournament_format_{tournament_name.replace(' ', '_')}.json"

def load_tournament_format(tournament_name):
    """Load a saved format choice from a local JSON file."""
    cache_file = get_format_cache_key(tournament_name)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                return data.get("format")
        except Exception:
            pass
    return None

def save_tournament_format(tournament_name, format_choice):
    """Save a format choice to a local JSON file."""
    cache_file = get_format_cache_key(tournament_name)
    try:
        with open(cache_file, 'w') as f:
            json.dump({"format": format_choice}, f)
        return True
    except Exception:
        return False

# --- GROUP CONFIGURATION FUNCTIONS ---
def get_group_cache_key(tournament_name):
    """Generate a unique filename for a tournament's group config."""
    return f".group_config_{tournament_name.replace(' ', '_')}.json"

def load_group_config(tournament_name):
    """Load a saved group configuration from a local JSON file."""
    cache_file = get_group_cache_key(tournament_name)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_group_config(tournament_name, config):
    """Save a group configuration to a local JSON file."""
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
        # Use the new helper to get the result of one simulation
        ranked_teams = _run_single_simulation_instance(list(teams), dict(current_wins), dict(current_diff), list(unplayed_matches), dict(forced_outcomes))
        
        for pos, team in enumerate(ranked_teams):
            rank = pos + 1
            
            # Original logic to calculate bracket probabilities
            for bracket in brackets:
                start, end = bracket["start"], bracket.get("end") or len(teams)
                if start <= rank <= end:
                    finish_counter[team][bracket["name"]] += 1
                    break
            
            # New logic to track best/worst rank for the selected team
            if team == team_to_track:
                if rank < best_rank:
                    best_rank = rank
                if rank > worst_rank:
                    worst_rank = rank

    # --- Create the results DataFrame ---
    rows = []
    for t in teams:
        row = {"Team": t}
        for bracket in brackets:
            row[f"{bracket['name']} (%)"] = (finish_counter[t].get(bracket["name"], 0) / n_sim) * 100
        rows.append(row)
    
    probs_df = pd.DataFrame(rows).round(2)

    # --- Return results in a dictionary ---
    results = {"probs_df": probs_df}
    if team_to_track:
        results["best_rank"] = best_rank
        results["worst_rank"] = worst_rank
        
    return results

def run_monte_carlo_simulation_groups(groups, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim, team_to_track=None):
    """
    Runs the full Monte Carlo simulation for groups and tracks best/worst rank.
    Note: Best/Worst rank is within the group, not overall.
    """
    teams = [t for g_teams in groups.values() for t in g_teams]
    finish_counter = {t: {b["name"]: 0 for b in brackets} for t in teams}

    # Initialize trackers for the new feature
    best_rank_in_group = float('inf')
    worst_rank_in_group = 0
    
    for _ in range(n_sim):
        # This uses the same helper, as match outcomes are independent of groups
        sim_wins = defaultdict(int, current_wins)
        sim_diff = defaultdict(int, current_diff)
        for a, b, dt, bo in unplayed_matches:
            code = forced_outcomes.get((a, b, dt), "random")
            outcome = random.choice([c for _, c in get_series_outcome_options(a, b, bo) if c != "random"]) if code == "random" else code
            if outcome == "DRAW": continue
            winner, loser = (a, b) if outcome.startswith("A") else (b, a)
            num = outcome[1:]; w, l = int(num[0]), int(num[1])
            sim_wins[winner] += 1; sim_diff[winner] += w - l; sim_diff[loser] += l - w

        # Rank within each group
        for group_name, group_teams in groups.items():
            ranked_in_group = sorted(group_teams, key=lambda t: (sim_wins.get(t, 0), sim_diff.get(t, 0), random.random()), reverse=True)
            for pos, team in enumerate(ranked_in_group):
                rank_in_group = pos + 1
                
                # Bracket logic
                for bracket in brackets:
                    start = bracket["start"]; end = bracket.get("end") or len(group_teams)
                    if start <= rank_in_group <= end:
                        finish_counter[team][bracket["name"]] += 1
                        break

                # Best/Worst rank logic
                if team == team_to_track:
                    if rank_in_group < best_rank_in_group:
                        best_rank_in_group = rank_in_group
                    if rank_in_group > worst_rank_in_group:
                        worst_rank_in_group = rank_in_group

    # --- Create the results DataFrame ---
    prob_data = []
    for t in teams:
        row = {"Team": t}
        for g_name, g_teams in groups.items():
            if t in g_teams: row["Group"] = g_name; break
        for bracket in brackets:
            row[f"{bracket['name']} (%)"] = (finish_counter[t][bracket["name"]] / n_sim) * 100
        prob_data.append(row)
    
    probs_df = pd.DataFrame(prob_data).round(2)
    
    # --- Return results in a dictionary ---
    results = {"probs_df": probs_df}
    if team_to_track:
        results["best_rank"] = best_rank_in_group
        results["worst_rank"] = worst_rank_in_group
    
    return results

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
