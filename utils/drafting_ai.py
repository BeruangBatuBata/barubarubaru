import streamlit as st
import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
from collections import defaultdict
import itertools
import math

@st.cache_resource
def load_prediction_assets(model_path='draft_predictor.joblib'):
    """
    Loads the trained model and associated assets from the .joblib file.
    This function is cached to run only once per session.
    """
    try:
        assets = joblib.load(model_path)
        return assets
    except FileNotFoundError:
        st.error(f"Model file not found at '{model_path}'. Please ensure it is in the project's root directory.")
        return None

def train_and_save_prediction_model(matches, HERO_PROFILES, HERO_DAMAGE_TYPE, model_filename='draft_predictor.joblib'):
    all_heroes = sorted(list(set(p['champion'] for m in matches for g in m.get('match2games', []) for o in g.get('opponents', []) for p in o.get('players', []) if 'champion' in p)))
    all_teams = sorted(list(set(o['name'] for m in matches for o in m.get('match2opponents', []) if 'name' in o)))
    roles = ["EXP", "Jungle", "Mid", "Gold", "Roam"]
    all_tags = sorted(list(set(tag for hero_profiles in HERO_PROFILES.values() for profile in hero_profiles for tag in profile['tags'])))
    feature_list = []
    for hero in all_heroes:
        for role in roles: feature_list.append(f"{hero}_{role}")
    for hero in all_heroes: feature_list.append(f"{hero}_Ban")
    feature_list.extend(all_teams)
    for tag in all_tags: feature_list.append(f"blue_{tag}_count")
    for tag in all_tags: feature_list.append(f"red_{tag}_count")
    feature_to_idx = {feature: i for i, feature in enumerate(feature_list)}
    X, y = [], []
    for match in matches:
        match_teams = [o.get('name') for o in match.get('match2opponents', [])]
        if len(match_teams) != 2 or not all(t in feature_to_idx for t in match_teams): continue
        for game in match.get('match2games', []):
            extradata = game.get('extradata', {})
            if len(game.get('opponents', [])) != 2 or game.get('winner') not in ['1', '2'] or not extradata: continue
            vector = np.zeros(len(feature_list))
            blue_picks_list, red_picks_list = [], []
            for i, role in enumerate(roles, 1):
                blue_hero, red_hero = extradata.get(f'team1champion{i}'), extradata.get(f'team2champion{i}')
                if blue_hero in all_heroes:
                    vector[feature_to_idx[f"{blue_hero}_{role}"]] = 1
                    blue_picks_list.append(blue_hero)
                if red_hero in all_heroes:
                    vector[feature_to_idx[f"{red_hero}_{role}"]] = -1
                    red_picks_list.append(red_hero)
            for i in range(1, 6):
                blue_ban, red_ban = extradata.get(f'team1ban{i}'), extradata.get(f'team2ban{i}')
                if blue_ban in all_heroes: vector[feature_to_idx[f"{blue_ban}_Ban"]] = 1
                if red_ban in all_heroes: vector[feature_to_idx[f"{red_ban}_Ban"]] = -1
            def get_tags_for_team(team_picks):
                team_tags = defaultdict(int)
                team_has_frontline = any('Front-line' in p['tags'] for h in team_picks if h in HERO_PROFILES for p in HERO_PROFILES[h])
                for hero in team_picks:
                    profiles = HERO_PROFILES.get(hero)
                    if profiles:
                        chosen_build = profiles[0]
                        if len(profiles) > 1 and not team_has_frontline and any('Tank' in p['build_name'] for p in profiles):
                            chosen_build = next((p for p in profiles if 'Tank' in p['build_name']), profiles[0])
                        for tag in chosen_build['tags']: team_tags[tag] += 1
                return team_tags
            blue_tags, red_tags = get_tags_for_team(blue_picks_list), get_tags_for_team(red_picks_list)
            for tag, count in blue_tags.items():
                if f"blue_{tag}_count" in feature_to_idx: vector[feature_to_idx[f"blue_{tag}_count"]] = count
            for tag, count in red_tags.items():
                if f"red_{tag}_count" in feature_to_idx: vector[feature_to_idx[f"red_{tag}_count"]] = count
            vector[feature_to_idx[match_teams[0]]] = 1
            vector[feature_to_idx[match_teams[1]]] = -1
            X.append(vector)
            y.append(1 if game['winner'] == '1' else 0)
    if not X:
        raise ValueError("Could not generate any training samples from the provided match data.")
    model = xgb.XGBClassifier(use_label_encoder=False, eval_metric='logloss', n_estimators=200, max_depth=6, learning_rate=0.05, colsample_bytree=0.8)
    model.fit(np.array(X), np.array(y))
    model_assets = {'model': model, 'feature_list': feature_list, 'feature_to_idx': feature_to_idx, 'roles': roles, 'all_heroes': all_heroes, 'all_tags': all_tags, 'all_teams': all_teams}
    joblib.dump(model_assets, model_filename)
    return f"✅ Advanced model training complete. Saved to '{model_filename}'"

def predict_draft_outcome(blue_picks, red_picks, blue_bans, red_bans, blue_team, red_team, model_assets, HERO_PROFILES):
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
    return model.predict_proba(vector.reshape(1, -1))[0][1], model.predict_proba(vector_draft_only.reshape(1, -1))[0][1]

### --- ADDED --- ###
def get_ai_suggestions(available_heroes, your_picks, enemy_picks, your_bans, enemy_bans, your_team, enemy_team, model_assets, HERO_PROFILES, is_blue_turn, phase):
    """
    Calculates the best hero to pick or ban to maximize win probability.
    """
    suggestions = []
    
    # Define team roles for prediction based on whose turn it is
    blue_p, red_p = (your_picks, enemy_picks) if is_blue_turn else (enemy_picks, your_picks)
    blue_b, red_b = (your_bans, enemy_bans) if is_blue_turn else (enemy_bans, your_bans)
    blue_t, red_t = (your_team, enemy_team) if is_blue_turn else (enemy_team, your_team)

    if phase == "BAN":
        for hero in available_heroes:
            hypothetical_bans = red_b + [hero] if is_blue_turn else blue_b + [hero]
            # Simulate the ENEMY banning a hero, and see how it impacts your win chance
            win_prob_blue, _ = predict_draft_outcome(blue_p, red_p, blue_b if is_blue_turn else hypothetical_bans, red_b if not is_blue_turn else hypothetical_bans, blue_t, red_t, model_assets, HERO_PROFILES)
            # Threat is high if the enemy banning them makes your win prob go down
            threat_score = 1 - win_prob_blue if is_blue_turn else win_prob_blue
            suggestions.append((hero, threat_score))

    elif phase == "PICK":
        open_roles = [role for role in ["EXP", "Jungle", "Mid", "Gold", "Roam"] if role not in your_picks]
        if not open_roles: return []
        for hero in available_heroes:
            hypothetical_your_picks = your_picks.copy()
            hypothetical_your_picks[open_roles[0]] = hero
            blue_p_sim = hypothetical_your_picks if is_blue_turn else blue_p
            red_p_sim = red_p if is_blue_turn else hypothetical_your_picks
            
            win_prob_blue, _ = predict_draft_outcome(blue_p_sim, red_p_sim, blue_b, red_b, blue_t, red_t, model_assets, HERO_PROFILES)
            pick_score = win_prob_blue if is_blue_turn else (1 - win_prob_blue)
            suggestions.append((hero, pick_score))

    return sorted(suggestions, key=lambda x: x[1], reverse=True)

def calculate_series_score_probs(p_win_game, series_format=3):
    """Calculates the probability of each score in a Best-of-X series."""
    if p_win_game is None or not (0 <= p_win_game <= 1): return {}
    p, q = p_win_game, 1 - p
    if series_format == 2: return {"2-0": p**2, "1-1": 2 * p * q, "0-2": q**2}
    wins_needed = math.ceil((series_format + 1) / 2)
    results = {}
    for losses in range(wins_needed):
        games_played = wins_needed + losses
        if games_played > series_format: continue
        combinations = math.comb(games_played - 1, wins_needed - 1)
        # Prob for Team A (blue) winning
        prob_a = combinations * (p ** wins_needed) * (q ** losses)
        results[f"{wins_needed}-{losses}"] = prob_a
        # Prob for Team B (red) winning
        prob_b = combinations * (q ** wins_needed) * (p ** losses)
        results[f"{losses}-{wins_needed}"] = prob_b
    return dict(sorted(results.items(), key=lambda item: item[1], reverse=True))
### --- END ADDED --- ###
