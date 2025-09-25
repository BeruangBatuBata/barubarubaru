import streamlit as st
import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
from collections import defaultdict, Counter
import itertools
import math

# --- Model Loading ---
@st.cache_resource
def load_prediction_assets(model_path='draft_predictor.joblib'):
    try:
        assets = joblib.load(model_path)
        return assets
    except FileNotFoundError:
        st.error(f"Model file not found at '{model_path}'. Please ensure it is in the project's root directory.")
        return None

# --- Data Preparation (from Notebook) ---
@st.cache_data
def prepare_draft_data(_pooled_matches, selected_team=None):
    """Prepares both global and team-specific dataframes for the draft assistant."""
    global_synergy_df = pd.DataFrame()
    global_counter_df = pd.DataFrame()
    team_synergy_df = pd.DataFrame()
    team_counter_df = pd.DataFrame()

    # Synergy analysis
    duo_counter = defaultdict(lambda: {"games": 0, "wins": 0})
    for match in _pooled_matches:
        teams_names = [opp.get("name", "").strip() for opp in match.get("match2opponents", [])]
        for game in match.get("match2games", []):
            winner = str(game.get("winner", ""))
            for idx, opp in enumerate(game.get("opponents", [])):
                players = [p["champion"] for p in opp.get("players", []) if isinstance(p, dict) and "champion" in p]
                for h1, h2 in itertools.combinations(sorted(players), 2):
                    key = (h1, h2)
                    duo_counter[key]["games"] += 1
                    if str(idx + 1) == winner:
                        duo_counter[key]["wins"] += 1
    
    rows = [{"Hero 1": k[0], "Hero 2": k[1], "Games Together": v["games"], "Wins": v["wins"], "Win Rate (%)": round(v["wins"]/v["games"]*100, 2) if v["games"] > 0 else 0} for k, v in duo_counter.items()]
    global_synergy_df = pd.DataFrame(rows)

    # Counter analysis
    counter_stats = defaultdict(lambda: {"games": 0, "wins": 0})
    for match in _pooled_matches:
        for game in match.get("match2games", []):
            winner = str(game.get("winner", ""))
            opponents = game.get("opponents", [])
            if len(opponents) != 2: continue
            heroes1 = {p["champion"] for p in opponents[0].get("players", []) if isinstance(p, dict) and "champion" in p}
            heroes2 = {p["champion"] for p in opponents[1].get("players", []) if isinstance(p, dict) and "champion" in p}
            for h1 in heroes1:
                for h2 in heroes2:
                    counter_stats[(h1, h2)]["games"] += 1; counter_stats[(h2, h1)]["games"] += 1
                    if winner == "1": counter_stats[(h1, h2)]["wins"] += 1
                    if winner == "2": counter_stats[(h2, h1)]["wins"] += 1

    rows = [{"Ally Hero": k[0], "Enemy Hero": k[1], "Games Against": v["games"], "Wins": v["wins"], "Win Rate (%)": round(v["wins"]/v["games"]*100, 2) if v["games"] > 0 else 0} for k, v in counter_stats.items()]
    global_counter_df = pd.DataFrame(rows)

    # Team-specific data if a team is selected
    if selected_team:
        # Team Synergy
        team_duo_counter = defaultdict(lambda: {"games": 0, "wins": 0})
        for match in _pooled_matches:
            teams_names = [opp.get("name", "").strip() for opp in match.get("match2opponents", [])]
            if selected_team not in teams_names: continue
            for game in match.get("match2games", []):
                winner = str(game.get("winner", ""))
                for idx, opp in enumerate(game.get("opponents", [])):
                    if teams_names[idx] == selected_team:
                        players = [p["champion"] for p in opp.get("players", []) if isinstance(p, dict) and "champion" in p]
                        for h1, h2 in itertools.combinations(sorted(players), 2):
                            key = (h1, h2)
                            team_duo_counter[key]["games"] += 1
                            if str(idx + 1) == winner:
                                team_duo_counter[key]["wins"] += 1
        team_rows = [{"Hero 1": k[0], "Hero 2": k[1], "Games Together": v["games"], "Wins": v["wins"], "Win Rate (%)": round(v["wins"]/v["games"]*100, 2) if v["games"] > 0 else 0} for k, v in team_duo_counter.items()]
        team_synergy_df = pd.DataFrame(team_rows)

    return global_synergy_df, global_counter_df, team_synergy_df, team_counter_df

# --- Suggestion Logic (from Notebook) ---
def get_dynamic_weight(team_games):
    """Returns (team_weight, global_weight) based on sample size."""
    if team_games >= 10: return 0.65, 0.35
    elif team_games >= 5: return 0.50, 0.50
    else: return 0.20, 0.80

def calculate_weighted_score(global_score, team_score, team_games):
    """Calculates weighted score based on sample size."""
    team_w, global_w = get_dynamic_weight(team_games)
    if team_score is None: return global_score
    return (team_w * team_score) + (global_w * global_score)

def get_ai_suggestions(available_heroes, your_picks, enemy_picks, global_synergy_df, global_counter_df, team_synergy_df, team_counter_df, selected_team=None):
    """Calculates suggestion scores using the hybrid notebook logic."""
    suggestions = []
    weights = {'synergy': 1.0, 'counter': 1.5, 'penalty': 0.5}

    for hero in available_heroes:
        # 1. Synergy Score
        global_synergy_score, team_synergy_score, team_synergy_games = 50.0, None, 0
        if your_picks:
            synergy_rates = [df[((df['Hero 1'] == hero) & (df['Hero 2'] == ally)) | ((df['Hero 1'] == ally) & (df['Hero 2'] == hero))]['Win Rate (%)'].iloc[0] for ally in your_picks for df in [global_synergy_df] if not df[((df['Hero 1'] == hero) & (df['Hero 2'] == ally)) | ((df['Hero 1'] == ally) & (df['Hero 2'] == hero))].empty]
            if synergy_rates: global_synergy_score = sum(synergy_rates) / len(synergy_rates)
            if selected_team and not team_synergy_df.empty:
                team_rates = [df[((df['Hero 1'] == hero) & (df['Hero 2'] == ally)) | ((df['Hero 1'] == ally) & (df['Hero 2'] == hero))]['Win Rate (%)'].iloc[0] for ally in your_picks for df in [team_synergy_df] if not df[((df['Hero 1'] == hero) & (df['Hero 2'] == ally)) | ((df['Hero 1'] == ally) & (df['Hero 2'] == hero))].empty]
                if team_rates: team_synergy_score = sum(team_rates) / len(team_rates)
                team_synergy_games = sum(df[((df['Hero 1'] == hero) & (df['Hero 2'] == ally)) | ((df['Hero 1'] == ally) & (df['Hero 2'] == hero))]['Games Together'].sum() for ally in your_picks for df in [team_synergy_df] if not df[((df['Hero 1'] == hero) & (df['Hero 2'] == ally)) | ((df['Hero 1'] == ally) & (df['Hero 2'] == hero))].empty)
        
        # 2. Counter Score
        global_counter_score, team_counter_score = 50.0, None
        if enemy_picks:
            counter_rates = [df[(df['Ally Hero'] == hero) & (df['Enemy Hero'] == enemy)]['Win Rate (%)'].iloc[0] for enemy in enemy_picks for df in [global_counter_df] if not df[(df['Ally Hero'] == hero) & (df['Enemy Hero'] == enemy)].empty]
            if counter_rates: global_counter_score = sum(counter_rates) / len(counter_rates)

        # 3. Penalty Score
        global_penalty_score, team_penalty_score = 50.0, None
        if enemy_picks:
            penalty_rates = [df[(df['Ally Hero'] == enemy) & (df['Enemy Hero'] == hero)]['Win Rate (%)'].iloc[0] for enemy in enemy_picks for df in [global_counter_df] if not df[(df['Ally Hero'] == enemy) & (df['Enemy Hero'] == hero)].empty]
            if penalty_rates: global_penalty_score = sum(penalty_rates) / len(penalty_rates)
        
        final_synergy = calculate_weighted_score(global_synergy_score, team_synergy_score, team_synergy_games)
        final_counter = global_counter_score # Simplified for now, can add team counter later
        final_penalty = global_penalty_score

        final_score = (weights['synergy'] * final_synergy) + (weights['counter'] * final_counter) - (weights['penalty'] * (final_penalty - 50))
        justification = f"Synergy: {final_synergy:.1f} | Counter: {final_counter:.1f} | Penalty: {final_penalty:.1f}"
        suggestions.append((hero, final_score, justification))

    return sorted(suggestions, key=lambda x: x[1], reverse=True)
