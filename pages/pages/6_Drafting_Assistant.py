import streamlit as st
from utils.drafting_ai import load_prediction_assets, predict_draft_outcome, get_ai_suggestions, calculate_series_score_probs
from utils.data_processing import HERO_PROFILES

st.set_page_config(layout="wide", page_title="Drafting Assistant")

# --- Load Model Assets ---
model_assets = load_prediction_assets()

if model_assets is None:
    st.error("Could not load the prediction model. Please ensure 'draft_predictor.joblib' is in the root directory.")
    st.stop()

# --- Initialize Session State for Draft ---
if 'draft' not in st.session_state:
    st.session_state.draft = {
        'blue_team': None, 'red_team': None,
        'blue_bans': [None]*5, 'red_bans': [None]*5,
        'blue_picks': {'EXP': None, 'Jungle': None, 'Mid': None, 'Gold': None, 'Roam': None},
        'red_picks': {'EXP': None, 'Jungle': None, 'Mid': None, 'Gold': None, 'Roam': None}
    }

# --- All Hero and Team Lists ---
ALL_HEROES = model_assets['all_heroes']
ALL_TEAMS = [None] + model_assets['all_teams']
ROLES = ["EXP", "Jungle", "Mid", "Gold", "Roam"]

# --- Main UI ---
st.title("🎯 Professional Drafting Assistant")

# --- Team Selection ---
cols = st.columns(2)
st.session_state.draft['blue_team'] = cols[0].selectbox("Select Blue Team:", ALL_TEAMS, key='blue_team_select')
st.session_state.draft['red_team'] = cols[1].selectbox("Select Red Team:", ALL_TEAMS, key='red_team_select')
series_format = st.selectbox("Series Format:", [1, 2, 3, 5, 7], index=2)

st.markdown("---")

# --- Live Win Probability Display ---
prob_placeholder = st.empty()
analysis_placeholder = st.empty()
turn_placeholder = st.empty()

# --- Draft Area ---
blue_col, red_col = st.columns(2)

with blue_col:
    st.header("🔷 Blue Team")
    st.subheader("Bans")
    ban_cols = st.columns(5)
    for i in range(5):
        st.session_state.draft['blue_bans'][i] = ban_cols[i].selectbox(f"B{i+1}", [None] + ALL_HEROES, key=f"b_ban_{i}")
    st.subheader("Picks")
    for role in ROLES:
        st.session_state.draft['blue_picks'][role] = st.selectbox(role, [None] + ALL_HEROES, key=f"b_pick_{role}")

with red_col:
    st.header("🔶 Red Team")
    st.subheader("Bans")
    ban_cols = st.columns(5)
    for i in range(5):
        st.session_state.draft['red_bans'][i] = ban_cols[i].selectbox(f"R{i+1}", [None] + ALL_HEROES, key=f"r_ban_{i}")
    st.subheader("Picks")
    for role in ROLES:
        st.session_state.draft['red_picks'][role] = st.selectbox(role, [None] + ALL_HEROES, key=f"r_pick_{role}")

# --- Logic for Processing and Displaying ---
draft = st.session_state.draft
blue_p = {k: v for k, v in draft['blue_picks'].items() if v}
red_p = {k: v for k, v in draft['red_picks'].items() if v}
blue_b = [v for v in draft['blue_bans'] if v]
red_b = [v for v in draft['red_bans'] if v]
taken_heroes = set(blue_p.values()) | set(red_p.values()) | set(blue_b) | set(red_b)
available_heroes = [h for h in ALL_HEROES if h not in taken_heroes]

# Predict outcome
win_prob_blue, draft_only_prob = predict_draft_outcome(blue_p, red_p, blue_b, red_b, draft['blue_team'], draft['red_team'], model_assets, HERO_PROFILES)

# Display probabilities
with prob_placeholder.container():
    st.subheader("Win Probability")
    st.write("Overall (Draft + Team History)")
    st.progress(win_prob_blue)
    st.write("Draft Only (Team Neutral)")
    st.progress(draft_only_prob)
    series_probs = calculate_series_score_probs(win_prob_blue, series_format)
    if series_probs:
        st.write(f"**Best-of-{series_format} Score Probabilities:**")
        st.json(series_probs)

# Determine current turn and get suggestions
b_bans, r_bans = len(blue_b), len(red_b)
b_picks, r_picks = len(blue_p), len(red_p)
total_bans, total_picks = b_bans + r_bans, b_picks + r_picks
turn, phase = None, None

if total_bans < 6: phase, turn = "BAN", ['B', 'R', 'B', 'R', 'B', 'R'][total_bans]
elif total_picks < 6: phase, turn = "PICK", ['B', 'R', 'R', 'B', 'B', 'R'][total_picks]
elif total_bans < 10: phase, turn = "BAN", ['R', 'B', 'R', 'B'][total_bans - 6]
elif total_picks < 10: phase, turn = "PICK", ['R', 'B', 'B', 'R'][total_picks - 6]

if turn:
    team_turn = "Blue Team" if turn == 'B' else "Red Team"
    turn_placeholder.info(f"Current Turn: **{team_turn} ({phase})**")
    
    # Get suggestions
    suggestions = get_ai_suggestions(
        available_heroes,
        blue_p if turn == 'B' else red_p,
        red_p if turn == 'B' else blue_p,
        blue_b if turn == 'B' else red_b,
        red_b if turn == 'B' else blue_b,
        draft['blue_team'], draft['red_team'], model_assets, HERO_PROFILES,
        is_blue_turn=(turn == 'B'), phase=phase
    )
    
    with (blue_col if turn == 'B' else red_col):
        st.subheader("AI Suggestions")
        for hero, score in suggestions[:5]:
            st.button(f"{hero} ({'Threat' if phase=='BAN' else 'Win Prob'}: {score:.1%})", key=f"sug_{hero}")

else:
    turn_placeholder.success("Draft Complete!")
