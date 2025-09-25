import streamlit as st
from utils.drafting_ai import load_prediction_assets, prepare_draft_data, get_ai_suggestions
from utils.data_processing import HERO_PROFILES

st.set_page_config(layout="wide", page_title="Drafting Assistant")

# --- Load Data ---
if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.warning("Please select and load tournament data on the homepage first.")
    st.stop()
pooled_matches = st.session_state['pooled_matches']
ALL_HEROES = sorted(list(HERO_PROFILES.keys()))

# --- UI ---
st.title("🎯 Professional Drafting Assistant (Hybrid AI)")

# --- Sidebar for Team Selection ---
st.sidebar.header("Draft Focus")
all_teams = sorted(list(set(opp.get('name','').strip() for m in pooled_matches for opp in m.get("match2opponents", []) if opp.get('name'))))
selected_team = st.sidebar.selectbox("Focus on Team (for weighted stats):", [None] + all_teams)
your_team_side = st.sidebar.radio("Your Team is:", ["Blue Team", "Red Team"])

# --- Initialize Session State for Draft ---
if 'draft' not in st.session_state:
    st.session_state.draft = {'blue_picks': [None]*5, 'red_picks': [None]*5, 'blue_bans': [None]*5, 'red_bans': [None]*5}

# --- Prepare Data (cached) ---
with st.spinner("Analyzing historical data for suggestions..."):
    global_synergy, global_counter, team_synergy, team_counter = prepare_draft_data(pooled_matches, selected_team)

# --- Draft Board UI ---
draft = st.session_state.draft
taken_heroes = {p for p in draft['blue_picks']+draft['red_picks']+draft['blue_bans']+draft['red_bans'] if p}
available_heroes = [h for h in ALL_HEROES if h not in taken_heroes]

col1, col2 = st.columns(2)
with col1:
    st.header("🔷 Blue Team")
    st.subheader("Bans")
    for i in range(5): draft['blue_bans'][i] = st.selectbox(f"B{i+1}", [None] + available_heroes, key=f"b_ban_{i}")
    st.subheader("Picks")
    for i in range(5): draft['blue_picks'][i] = st.selectbox(f"P{i+1}", [None] + available_heroes, key=f"b_pick_{i}")

with col2:
    st.header("🔶 Red Team")
    st.subheader("Bans")
    for i in range(5): draft['red_bans'][i] = st.selectbox(f"R{i+1}", [None] + available_heroes, key=f"r_ban_{i}")
    st.subheader("Picks")
    for i in range(5): draft['red_picks'][i] = st.selectbox(f"R{i+1}", [None] + available_heroes, key=f"r_pick_{i}")

# --- Suggestions Logic ---
your_picks = draft['blue_picks'] if your_team_side == "Blue Team" else draft['red_picks']
enemy_picks = draft['red_picks'] if your_team_side == "Blue Team" else draft['blue_picks']

your_picks_clean = [p for p in your_picks if p]
enemy_picks_clean = [p for p in enemy_picks if p]

if len(your_picks_clean) < 5:
    st.sidebar.markdown("---")
    st.sidebar.header("AI Suggestions")
    with st.sidebar:
        with st.spinner("Calculating suggestions..."):
            suggestions = get_ai_suggestions(
                available_heroes, your_picks_clean, enemy_picks_clean,
                global_synergy, global_counter, team_synergy, team_counter,
                selected_team
            )
        st.write(f"Top 5 Picks for **{your_team_side}**:")
        for hero, score, justification in suggestions[:5]:
            st.info(f"**{hero}** (Score: {score:.1f})")
            st.caption(justification)
