import streamlit as st
import pandas as pd
import numpy as np
import xgboost as xgb
import json
from collections import defaultdict
import math

@st.cache_resource
def load_prediction_assets(model_path='draft_predictor.json', assets_path='draft_assets.json'):
    """
    Loads the trained model from its native JSON format and the assets from their JSON file.
    """
    try:
        # Load the assets first
        with open(assets_path, 'r') as f:
            assets = json.load(f)
        
        # Create a new model instance and load the saved state into it
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        
        assets['model'] = model
        return assets
    except FileNotFoundError:
        st.error(f"Model or assets file not found. Please ensure '{model_path}' and '{assets_path}' are in the project's root directory.")
        return None

# The rest of the functions (predict_draft_outcome, get_ai_suggestions, etc.)
# remain exactly the same as they were. They will now receive the correctly
# loaded assets and work as intended.
# ... (rest of the functions from previous correct version) ...
def predict_draft_outcome(blue_picks, red_picks, blue_bans, red_bans, blue_team, red_team, model_assets, HERO_PROFILES):
    """Predicts win probability for Blue Team, returning both overall and draft-only scores."""
    model, feature_to_idx = model_assets['model'], model_assets['feature_to_idx']
    all_heroes, all_teams, all_tags = model_assets['all_heroes'], model_assets['all_teams'], model_assets['all_tags']
    vector = np.zeros(len(feature_to_idx))
    for role, hero in blue_picks.items():
        if hero in all_heroes and f"{hero}_{role}" in feature_to_idx: vector[feature_to_idx[f"{hero}_{role}"]] = 1
    for role, hero in red_picks.items():
        if hero in all_heroes and f"{hero}_{role}" in feature_to_idx: vector[feature_to_idx[f"{hero}_{role}"]] = -1
    for hero in blue_bans:
        if hero in all_heroes and f"{hero}_Ban" in feature_to_idx: vector[feature_to_idx[f"{hero}_Ban"]] = 1
    for hero in red_bans:
        if hero in all_heroes and f"{hero}_Ban" in feature_to_idx: vector[feature_to_idx[f"{hero}_Ban"]] = -1
    def get_tags_for_team(team_picks_dict):
        team_tags, team_picks_list = defaultdict(int), list(team_picks_dict.values())
        team_has_frontline = any('Front-line' in p['tags'] for h in team_picks_list if h in HERO_PROFILES for p in HERO_PROFILES[h])
        for hero in team_picks_list:
            profiles = HERO_PROFILES.get(hero)
            if profiles:
                chosen_build = profiles[0]
                if len(profiles) > 1 and not team_has_frontline and any('Tank' in p['build_name'] for p in profiles):
                    chosen_build = next((p for p in profiles if 'Tank' in p['build_name']), profiles[0])
                for tag in chosen_build['tags']:
                    if tag in all_tags: team_tags[tag] += 1
        return team_tags
    blue_tags, red_tags = get_tags_for_team(blue_picks), get_tags_for_team(red_picks)
    for tag, count in blue_tags.items():
        if f"blue_{tag}_count" in feature_to_idx: vector[feature_to_idx[f"blue_{tag}_count"]] = count
    for tag, count in red_tags.items():
        if f"red_{tag}_count" in feature_to_idx: vector[feature_to_idx[f"red_{tag}_count"]] = count
    if blue_team in all_teams and blue_team in feature_to_idx: vector[feature_to_idx[blue_team]] = 1
    if red_team in all_teams and red_team in feature_to_idx: vector[feature_to_idx[red_team]] = -1
    vector_draft_only = vector.copy()
    if blue_team in all_teams and blue_team in feature_to_idx: vector_draft_only[feature_to_idx[blue_team]] = 0
    if red_team in all_teams and red_team in feature_to_idx: vector_draft_only[feature_to_idx[red_team]] = 0
    prob_overall = model.predict_proba(vector.reshape(1, -1))[0][1]
    prob_draft_only = model.predict_proba(vector_draft_only.reshape(1, -1))[0][1]
    return prob_overall, prob_draft_only

def generate_prediction_explanation(blue_picks, red_picks, HERO_PROFILES, HERO_DAMAGE_TYPE):
    def analyze_team(team_picks, damage_types):
        points = []
        if not team_picks: return ["Waiting for picks..."]
        all_tags = [tag for hero in team_picks if hero in HERO_PROFILES for profile in HERO_PROFILES[hero] for tag in profile['tags']]
        if 'Front-line' not in all_tags and 'Initiator' not in all_tags:
            points.append("⚠️ **Lacks a durable front-line or initiator.**")
        magic_count = sum(1 for hero in team_picks if 'Magic' in damage_types.get(hero, []))
        phys_count = sum(1 for hero in team_picks if 'Physical' in damage_types.get(hero, []))
        if magic_count == 0 and phys_count > 1: points.append("⚠️ **Lacks magic damage.**")
        elif phys_count == 0 and magic_count > 1: points.append("⚠️ **Lacks physical damage.**")
        else: points.append("✅ **Balanced damage profile.**")
        if all_tags.count('High Mobility') >= 2 and all_tags.count('Burst') >= 2:
            points.append("📈 **Strategy: Excellent Pick-off potential.**")
        if all_tags.count('Poke') >= 2 and all_tags.count('Long Range') >= 1:
            points.append("📈 **Strategy: Strong Poke & Siege composition.**")
        if all_tags.count('Initiator') >= 1 and all_tags.count('AoE Damage') >= 2:
            points.append("📈 **Strategy: Strong Team Fighting capabilities.**")
        return points if points else ["No outstanding features to note."]
    blue_analysis = analyze_team(blue_picks, HERO_DAMAGE_TYPE)
    red_analysis = analyze_team(red_picks, HERO_DAMAGE_TYPE)
    return {'blue': blue_analysis, 'red': red_analysis}

def get_ai_suggestions(available_heroes, your_picks, enemy_picks, your_bans, enemy_bans, your_team, enemy_team, model_assets, HERO_PROFILES, is_blue_turn, phase):
    suggestions = []
    blue_p, red_p = (your_picks, enemy_picks) if is_blue_turn else (enemy_picks, your_picks)
    blue_b, red_b = (your_bans, enemy_bans) if is_blue_turn else (enemy_bans, your_bans)
    blue_t, red_t = (your_team, enemy_team) if is_blue_turn else (enemy_team, your_team)
    if phase == "BAN":
        for hero in available_heroes:
            hypothetical_enemy_picks = enemy_picks.copy()
            open_roles = [r for r in ["EXP", "Jungle", "Mid", "Gold", "Roam"] if r not in hypothetical_enemy_picks]
            if not open_roles: continue
            hypothetical_enemy_picks[open_roles[0]] = hero
            win_prob_blue, _ = predict_draft_outcome(blue_p, hypothetical_enemy_picks, blue_b, red_b, blue_t, red_t, model_assets, HERO_PROFILES)
            threat_score = 1 - win_prob_blue if is_blue_turn else win_prob_blue
            suggestions.append((hero, threat_score))
    elif phase == "PICK":
        open_roles = [role for role in ["EXP", "Jungle", "Mid", "Gold", "Roam"] if role not in your_picks]
        if not open_roles: return []
        for hero in available_heroes:
            hypothetical_your_picks = your_picks.copy()
            hypothetical_your_picks[open_roles[0]] = hero
            blue_p_sim, red_p_sim = (hypothetical_your_picks, red_p) if is_blue_turn else (blue_p, hypothetical_your_picks)
            win_prob_blue, _ = predict_draft_outcome(blue_p_sim, red_p_sim, blue_b, red_b, blue_t, red_t, model_assets, HERO_PROFILES)
            pick_score = win_prob_blue if is_blue_turn else (1 - win_prob_blue)
            suggestions.append((hero, pick_score))
    return sorted(suggestions, key=lambda x: x[1], reverse=True)
