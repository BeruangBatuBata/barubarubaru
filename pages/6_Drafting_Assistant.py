import streamlit as st
from collections import defaultdict
### --- MODIFIED --- ###
from utils.drafting_ai import load_prediction_assets, predict_draft_outcome, get_ai_suggestions, generate_prediction_explanation, calculate_series_score_probs
### --- END MODIFIED --- ###
from utils.data_processing import HERO_PROFILES, HERO_DAMAGE_TYPE

st.set_page_config(layout="wide", page_title="Drafting Assistant")

# --- Helper function for the custom probability bar ---
def generate_win_prob_bar(probability, title):
    """Generates a custom HTML two-sided probability bar."""
    blue_pct = probability * 100
    red_pct = 100 - blue_pct
    bar_html = f"""
    <div style="margin-bottom: 1rem;">
        <p style="margin-bottom: 0.25rem; font-size: 0.9em; color: #555; font-weight:bold;">{title}</p>
        <div style="display: flex; width: 100%; height: 28px; font-weight: bold; font-size: 14px; border-radius: 5px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);">
            <div style="width: {blue_pct:.1f}%; background-color: #3b82f6; color: white; display: flex; align-items: center; justify-content: center;">{blue_pct:.1f}%</div>
            <div style="width: {red_pct:.1f}%; background-color: #ef4444; color: white; display: flex; align-items: center; justify-content: center;">{red_pct:.1f}%</div>
        </div>
    </div>
    """
    st.markdown(bar_html, unsafe_allow_html=True)

# --- Load Model & Data ---
model_assets = load_prediction_assets()
if model_assets is None:
    st.error("Could not load the prediction model. Please train a model in the 'Admin Panel' and ensure 'draft_predictor.json' and 'draft_assets.json' are in your repository's root directory.")
    st.stop()

if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.warning("Please load tournament data on the homepage first.")
    st.stop()
    
ALL_HEROES = model_assets['all_heroes']
ALL_TEAMS = [None] + model_assets['all_teams']
ROLES = ["EXP", "Jungle", "Mid", "Gold", "Roam"]
pooled_matches = st.session_state['pooled_matches']

# --- Session State Initialization ---
if 'draft' not in st.session_state:
    st.session_state.draft = {
        'blue_team': None, 'red_team': None,
        'blue_bans': [None]*5, 'red_bans': [None]*5,
        'blue_picks': {role: None for role in ROLES},
        'red_picks': {role: None for role in ROLES}
    }

# --- UI & Logic ---
st.title("🎯 Professional Drafting Assistant")

with st.expander("Review a Past Game"):
    playable_games = []
    for match_idx, match in enumerate(pooled_matches):
        opps = match.get('match2opponents', [])
        if len(opps) < 2: continue
        for game_idx, game in enumerate(match.get('match2games', [])):
            if game.get('extradata'):
                label = f"{opps[0].get('name')} vs {opps[1].get('name')} (Game {game_idx + 1})"
                playable_games.append((label, match_idx, game_idx))
    
    selected_game = st.selectbox("Select a past game to analyze:", [None] + playable_games, format_func=lambda x: x[0] if x else "None", key="game_selector")

    if st.button("Load Selected Game"):
        if selected_game:
            _, match_idx, game_idx = selected_game
            match_data = pooled_matches[match_idx]
            game_data = match_data['match2games'][game_idx]
            extradata = game_data['extradata']
            
            st.session_state.draft['blue_team'] = match_data['match2opponents'][0].get('name')
            st.session_state.draft['red_team'] = match_data['match2opponents'][1].get('name')
            for i in range(5):
                st.session_state.draft['blue_bans'][i] = extradata.get(f'team1ban{i+1}')
                st.session_state.draft['red_bans'][i] = extradata.get(f'team2ban{i+1}')
                st.session_state.draft['blue_picks'][ROLES[i]] = extradata.get(f'team1champion{i+1}')
                st.session_state.draft['red_picks'][ROLES[i]] = extradata.get(f'team2champion{i+1}')
            
            winner = "Blue Team" if str(game_data.get('winner')) == '1' else "Red Team"
            st.success(f"**Actual Winner:** {winner}")
            st.rerun()

st.markdown("---")

# --- Main Draft Interface ---
draft = st.session_state.draft
prob_placeholder = st.empty()
turn_placeholder = st.empty()
analysis_placeholder = st.empty()
suggestion_placeholder = st.empty()

c1, c2, c3 = st.columns([2, 2, 1])
draft['blue_team'] = c1.selectbox("Blue Team:", ALL_TEAMS, key='blue_team_select', index=ALL_TEAMS.index(draft['blue_team']) if draft['blue_team'] in ALL_TEAMS else 0)
draft['red_team'] = c2.selectbox("Red Team:", ALL_TEAMS, key='red_team_select', index=ALL_TEAMS.index(draft['red_team']) if draft['red_team'] in ALL_TEAMS else 0)
series_format = c3.selectbox("Series Format:", [1, 3, 5, 7], index=1)

blue_col, red_col = st.columns(2)
taken_heroes = {v for k, v in draft['blue_picks'].items() if v} | {v for k, v in draft['red_picks'].items() if v} | {v for v in draft['blue_bans'] if v} | {v for v in draft['red_bans'] if v}

with blue_col:
    st.header("🔷 Blue Team")
    st.subheader("Bans")
    ban_cols = st.columns(5)
    for i in range(5):
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == draft['blue_bans'][i]])
        draft['blue_bans'][i] = ban_cols[i].selectbox(f"B{i+1}", available, key=f"b_ban_{i}", index=available.index(draft['blue_bans'][i]) if draft['blue_bans'][i] in available else 0)
    st.subheader("Picks")
    for role in ROLES:
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == draft['blue_picks'][role]])
        draft['blue_picks'][role] = st.selectbox(role, available, key=f"b_pick_{role}", index=available.index(draft['blue_picks'][role]) if draft['blue_picks'][role] in available else 0)

with red_col:
    st.header("🔶 Red Team")
    st.subheader("Bans")
    ban_cols = st.columns(5)
    for i in range(5):
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == draft['red_bans'][i]])
        draft['red_bans'][i] = ban_cols[i].selectbox(f"R{i+1}", available, key=f"r_ban_{i}", index=available.index(draft['red_bans'][i]) if draft['red_bans'][i] in available else 0)
    st.subheader("Picks")
    for role in ROLES:
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == draft['red_picks'][role]])
        draft['red_picks'][role] = st.selectbox(role, available, key=f"r_pick_{role}", index=available.index(draft['red_picks'][role]) if draft['red_picks'][role] in available else 0)

# --- Calculations ---
blue_p = {k: v for k, v in draft['blue_picks'].items() if v}
red_p = {k: v for k, v in draft['red_picks'].items() if v}
blue_b = [v for v in draft['blue_bans'] if v]
red_b = [v for v in draft['red_bans'] if v]

prob_overall, prob_draft_only = predict_draft_outcome(blue_p, red_p, blue_b, red_b, draft['blue_team'], draft['red_team'], model_assets, HERO_PROFILES)
explanation = generate_prediction_explanation(list(blue_p.values()), list(red_p.values()), HERO_PROFILES, HERO_DAMAGE_TYPE)

with prob_placeholder.container():
    st.subheader("Live Win Probability")
    generate_win_prob_bar(prob_overall, "Overall Prediction (Draft + Team History)")
    generate_win_prob_bar(prob_draft_only, "Draft-Only Prediction (Team Neutral)")
    
    series_probs = calculate_series_score_probs(prob_overall, series_format)
    if series_probs:
        st.write(f"**Best-of-{series_format} Series Score Probability**")
        prob_text = ""
        for score, probability in series_probs.items():
            prob_text += f"- **{score}:** {probability:.1%}\n"
        st.markdown(prob_text)

with analysis_placeholder.container():
    st.subheader("AI Draft Analysis")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("".join([f"- {s}\n" for s in explanation['blue']]))
    with c2:
        st.markdown("".join([f"- {s}\n" for s in explanation['red']]))

# --- Turn Logic & Suggestions ---
total_bans, total_picks = len(blue_b) + len(red_b), len(blue_p) + len(red_p)
turn, phase = None, "DRAFT COMPLETE"
if total_bans < 6: phase, turn = "BAN", ['B', 'R', 'B', 'R', 'B', 'R'][total_bans]
elif total_picks < 6: phase, turn = "PICK", ['B', 'R', 'R', 'B', 'B', 'R'][total_picks]
elif total_bans < 10: phase, turn = "BAN", ['R', 'B', 'R', 'B'][total_bans - 6]
elif total_picks < 10: phase, turn = "PICK", ['R', 'B', 'B', 'R'][total_picks - 6]

team_turn = "Blue Team" if turn == 'B' else "Red Team"
turn_placeholder.header(f"Turn: {team_turn} ({phase})")

with suggestion_placeholder.container():
    if turn:
        st.subheader("AI Suggestions")
        is_blue_turn = (turn == 'B')
        suggestions = get_ai_suggestions(
            [h for h in ALL_HEROES if h not in taken_heroes],
            blue_p, red_p, blue_b, red_b,
            draft['blue_team'], draft['red_team'],
            model_assets, HERO_PROFILES, is_blue_turn, phase
        )
        for hero, score in suggestions[:5]:
            label = f"{hero} ({'Threat' if phase == 'BAN' else 'Win Prob'}: {score:.1%})"
            st.button(label, key=f"sug_{hero}")
