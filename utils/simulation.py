import pandas as pd
import numpy as np
import random
import json
import os
from collections import defaultdict, Counter
import math
from math import comb
from itertools import groupby

# --- [UNCHANGED CODE FROM get_permanent_config_path to build_week_blocks] ---
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
        
def get_series_outcome_options(teamA, teamB, bestof):
    """
    Generates a list of possible outcomes for a series given the format.
    """
    options = [("Random", "random")]
    try:
        bo = int(bestof)
        if bo == 1:
            options.extend([(f"{teamA} Wins 1-0", "A10"), (f"{teamB} Wins 1-0", "B10")])
        elif bo == 2:
            options.extend([(f"{teamA} Wins 2-0", "A20"), ("Series is a 1-1 Draw", "DRAW"), (f"{teamB} Wins 2-0", "B20")])
        elif bo == 3:
            options.extend([(f"{teamA} Wins 2-0", "A20"), (f"{teamA} Wins 2-1", "A21"), (f"{teamB} Wins 2-0", "B20"), (f"{teamB} Wins 2-1", "B21")])
        elif bo == 5:
            options.extend([(f"{teamA} Wins 3-0", "A30"), (f"{teamA} Wins 3-1", "A31"), (f"{teamA} Wins 3-2", "A32"), (f"{teamB} Wins 3-0", "B30"), (f"{teamB} Wins 3-1", "B31"), (f"{teamB} Wins 3-2", "B32")])
        elif bo == 7:
            options.extend([(f"{teamA} Wins 4-0", "A40"), (f"{teamA} Wins 4-1", "A41"), (f"{teamA} Wins 4-2", "A42"), (f"{teamA} Wins 4-3", "A43"), (f"{teamB} Wins 4-0", "B40"), (f"{teamB} Wins 4-1", "B41"), (f"{teamB} Wins 4-2", "B42"), (f"{teamB} Wins 4-3", "B43")])
    except (ValueError, TypeError):
        return [("Random", "random")]
    return options

def calculate_series_score_probs(p_win, n_games):
    if p_win is None or not (0 <= p_win <= 1): return {}
    p_lose = 1 - p_win
    games_to_win = (n_games // 2) + 1
    probs = {}
    for games_lost in range(games_to_win):
        total_games_played = games_to_win + games_lost
        if total_games_played > n_games: continue
        combinations = comb(total_games_played - 1, games_to_win - 1)
        probability = combinations * (p_win ** games_to_win) * (p_lose ** games_lost)
        probs[f"{games_to_win}-{games_lost}"] = probability
    for games_won in range(games_to_win):
        total_games_played = games_to_win + games_won
        if total_games_played > n_games: continue
        combinations = comb(total_games_played - 1, games_to_win - 1)
        probability = combinations * (p_lose ** games_to_win) * (p_win ** games_won)
        probs[f"{games_won}-{games_to_win}"] = probability
    return probs

def build_week_blocks(dates_str):
    if not dates_str: return []
    dates = []
    for d_str in dates_str:
        try:
            dates.append(pd.to_datetime(d_str).date())
        except (ValueError, TypeError):
            continue
    if not dates: return []
    dates = sorted(list(set(dates)))
    blocks = [[dates[0]]]
    for prev, curr in zip(dates, dates[1:]):
        if (curr - prev).days <= 2:
            blocks[-1].append(curr)
        else:
            blocks.append([curr])
    return blocks

# --- MODIFIED: Tie-breaker functions now follow the new 4-step logic ---

def resolve_ties_h2h_gamediff(tied_teams, all_matches_data):
    """
    Resolves ties between a group of teams based on the game difference
    from their head-to-head matches.
    """
    if len(tied_teams) <= 1:
        return tied_teams

    h2h_diff = Counter()
    for match in all_matches_data:
        teamA, teamB, _, sA, sB = match
        if teamA in tied_teams and teamB in tied_teams:
            h2h_diff[teamA] += sA - sB
            h2h_diff[teamB] += sB - sA
    
    # Sort the group by their H2H game difference.
    # A random element is added as a final, definitive tie-breaker if H2H diff is also identical.
    return sorted(tied_teams, key=lambda t: (h2h_diff[t], random.random()), reverse=True)


def build_standings_table(teams, matches):
    standings_data = {t: {"Matches W": 0, "Matches L": 0, "Games W": 0, "Games L": 0} for t in teams}
    all_matches_simple = []

    for m in matches:
        opps = m.get("match2opponents", [])
        if len(opps) < 2 or m.get("winner") not in ("1", "2"): continue
        tA, tB = opps[0].get('name'), opps[1].get('name')
        if not tA or not tB or tA not in teams or tB not in teams: continue

        winner, loser = (tA, tB) if m["winner"] == "1" else (tB, tA)
        standings_data[winner]["Matches W"] += 1
        standings_data[loser]["Matches L"] += 1
        
        sA, sB = 0, 0
        for g in m.get("match2games", []):
            if str(g.get('winner')) == '1': sA += 1
            elif str(g.get('winner')) == '2': sB += 1
        standings_data[tA]["Games W"] += sA; standings_data[tA]["Games L"] += sB
        standings_data[tB]["Games W"] += sB; standings_data[tB]["Games L"] += sA
        all_matches_simple.append((tA, tB, winner, sA, sB))

    # Step 1 & 2: Sort by Series Wins, then Overall Game Diff
    sorted_teams = sorted(teams, key=lambda t: (
        standings_data[t]["Matches W"], 
        standings_data[t]["Games W"] - standings_data[t]["Games L"]
    ), reverse=True)
    
    final_ranked_order = []
    # Group by the first two tie-breakers
    for _, g in groupby(sorted_teams, key=lambda t: (standings_data[t]["Matches W"], standings_data[t]["Games W"] - standings_data[t]["Games L"])):
        group = list(g)
        if len(group) > 1:
            # Step 3: If a tie remains, resolve it with H2H Game Diff
            resolved_group = resolve_ties_h2h_gamediff(group, all_matches_simple)
            final_ranked_order.extend(resolved_group)
        else:
            final_ranked_order.extend(group)

    df = pd.DataFrame.from_dict(standings_data, orient='index')
    df["Diff"] = df["Games W"] - df["Games L"]
    df = df.reindex(final_ranked_order)
    df["Matches (W-L)"] = df.apply(lambda r: f"{r['Matches W']}-{r['Matches L']}", axis=1)
    df["Games (W-L)"] = df.apply(lambda r: f"{r['Games W']}-{r['Games L']}", axis=1)
    df = df[["Matches (W-L)", "Games (W-L)", "Diff"]].reset_index().rename(columns={"index": "Team"})
    df.insert(0, 'Rank', np.arange(1, len(df) + 1))
    return df

def run_monte_carlo_simulation(teams, played_matches, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim, team_to_track=None):
    finish_counter = {t: {b["name"]: 0 for b in brackets} for t in teams}
    best_rank, worst_rank = len(teams), 1

    played_matches_simple = []
    for m in played_matches:
        opps = m.get("match2opponents", [])
        if len(opps) < 2 or m.get("winner") not in ("1", "2"): continue
        tA, tB = opps[0].get('name'), opps[1].get('name')
        winner = tA if m["winner"] == "1" else tB
        sA, sB = 0,0 
        for g in m.get("match2games", []):
            if str(g.get('winner')) == '1': sA += 1
            elif str(g.get('winner')) == '2': sB += 1
        played_matches_simple.append((tA, tB, winner, sA, sB))

    for _ in range(n_sim):
        sim_wins, sim_diff = defaultdict(int, current_wins), defaultdict(int, current_diff)
        simulated_matches = []
        for a, b, dt, bo in unplayed_matches:
            code = forced_outcomes.get((a, b, dt), "random")
            outcome = random.choice([c for _, c in get_series_outcome_options(a, b, bo) if c != "random"]) if code == "random" else code
            if not outcome or outcome == "DRAW": continue
            winner, loser = (a, b) if outcome.startswith("A") else (b, a)
            w, l = int(outcome[1]), int(outcome[2])
            sim_wins[winner] += 1; sim_diff[winner] += w - l; sim_diff[loser] += l - w
            simulated_matches.append((a, b, winner, w, l))
        
        all_sim_matches = played_matches_simple + simulated_matches

        sorted_teams = sorted(teams, key=lambda t: (sim_wins.get(t, 0), sim_diff.get(t, 0)), reverse=True)
        final_ranked_teams = []
        for _, g in groupby(sorted_teams, key=lambda t: (sim_wins.get(t, 0), sim_diff.get(t, 0))):
            group = list(g)
            if len(group) > 1:
                final_ranked_teams.extend(resolve_ties_h2h_gamediff(group, all_sim_matches))
            else:
                final_ranked_teams.extend(group)

        for pos, team in enumerate(final_ranked_teams):
            rank = pos + 1
            for bracket in brackets:
                if bracket["start"] <= rank <= (bracket.get("end") or len(teams)):
                    finish_counter[team][bracket["name"]] += 1; break
            if team == team_to_track:
                best_rank, worst_rank = min(best_rank, rank), max(worst_rank, rank)

    rows = [{"Team": t, **{f"{b['name']} (%)": (finish_counter[t].get(b["name"], 0) / n_sim) * 100 for b in brackets}} for t in teams]
    return {"probs_df": pd.DataFrame(rows).round(2), "best_rank": best_rank, "worst_rank": worst_rank}


def run_monte_carlo_simulation_groups(groups, played_matches, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim, team_to_track=None):
    all_teams = [t for g in groups.values() for t in g]
    finish_counter = {t: {b["name"]: 0 for b in brackets} for t in all_teams}
    best_ranks, worst_ranks = defaultdict(lambda: 99), defaultdict(int)

    played_matches_simple = []
    for m in played_matches:
        opps = m.get("match2opponents", [])
        if len(opps) < 2 or m.get("winner") not in ("1", "2"): continue
        tA, tB = opps[0].get('name'), opps[1].get('name')
        winner = tA if m["winner"] == "1" else tB
        sA, sB = 0,0
        for g in m.get("match2games", []):
            if str(g.get('winner')) == '1': sA += 1
            elif str(g.get('winner')) == '2': sB += 1
        played_matches_simple.append((tA, tB, winner, sA, sB))

    for _ in range(n_sim):
        sim_wins, sim_diff = defaultdict(int, current_wins), defaultdict(int, current_diff)
        simulated_matches = []
        for a, b, dt, bo in unplayed_matches:
            code = forced_outcomes.get((a, b, dt), "random")
            outcome = random.choice([c for _, c in get_series_outcome_options(a, b, bo) if c != "random"]) if code == "random" else code
            if not outcome or outcome == "DRAW": continue
            winner, loser = (a, b) if outcome.startswith("A") else (b, a)
            w, l = int(outcome[1]), int(outcome[2])
            sim_wins[winner] += 1; sim_diff[winner] += w - l; sim_diff[loser] += l - w
            simulated_matches.append((a, b, winner, w, l))
        
        all_sim_matches = played_matches_simple + simulated_matches
        
        final_standings = {}
        for group_name, group_teams in groups.items():
            sorted_teams = sorted(group_teams, key=lambda t: (sim_wins.get(t, 0), sim_diff.get(t, 0)), reverse=True)
            group_standings = []
            for _, g in groupby(sorted_teams, key=lambda t: (sim_wins.get(t, 0), sim_diff.get(t, 0))):
                group = list(g)
                if len(group) > 1:
                    group_standings.extend(resolve_ties_h2h_gamediff(group, all_sim_matches))
                else:
                    group_standings.extend(group)
            
            for rank, team in enumerate(group_standings, 1):
                final_standings[team] = (rank, group_name)
                if team == team_to_track:
                    best_ranks[team], worst_ranks[team] = min(best_ranks[team], rank), max(worst_ranks[team], rank)

        for team, (rank, _) in final_standings.items():
            for bracket in brackets:
                if bracket['start'] <= rank <= (bracket.get('end') or len(all_teams)):
                    finish_counter[team][bracket["name"]] += 1; break
    
    rows = [{"Team": t, "Group": next((g for g, ts in groups.items() if t in ts), "N/A"), **{f"{b['name']} (%)": (finish_counter[t].get(b["name"], 0) / n_sim) * 100 for b in brackets}} for t in all_teams]
    return {"probs_df": pd.DataFrame(rows).round(2), "best_rank": best_ranks.get(team_to_track), "worst_rank": worst_ranks.get(team_to_track)}

# --- [UNCHANGED CODE FROM _run_single_simulation_instance to the end of the file] ---
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
