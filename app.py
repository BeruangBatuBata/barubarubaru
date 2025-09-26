import streamlit as st
from collections import OrderedDict
from utils.data_processing import parse_matches
from utils.api_handler import ALL_TOURNAMENTS, load_tournament_data, clear_cache_for_live_tournaments
from utils.analysis_functions import calculate_hero_stats_for_team
import pandas as pd

# --- Page Configuration ---
st.set_page_config(
    page_title="MLBB Analytics Dashboard",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Initialization ---
if 'selected_tournaments' not in st.session_state:
    st.session_state['selected_tournaments'] = []
if 'pooled_matches' not in st.session_state:
    st.session_state['pooled_matches'] = None
if 'parsed_matches' not in st.session_state:
    st.session_state['parsed_matches'] = None

# --- Sidebar ---
with st.sidebar:
    st.header("Tournament Selection")
    selected_tournaments = st.multiselect(
        "Choose tournaments:",
        options=list(ALL_TOURNAMENTS.keys()),
        default=st.session_state['selected_tournaments'],
        placeholder="Select one or more tournaments"
    )

    if st.button("Load Data", type="primary"):
        st.cache_data.clear()
        if not selected_tournaments:
            st.warning("Please select at least one tournament.")
        else:
            st.session_state['pooled_matches'] = None
            st.session_state['parsed_matches'] = None
            st.session_state['selected_tournaments'] = selected_tournaments
            all_matches_raw = []
            with st.spinner("Loading tournament data..."):
                for name in selected_tournaments:
                    matches = load_tournament_data(name)
                    if matches:
                        all_matches_raw.extend(matches)
            if all_matches_raw:
                st.session_state['pooled_matches'] = all_matches_raw
                st.session_state['parsed_matches'] = parse_matches(all_matches_raw)
                st.success(f"Successfully loaded data for {len(selected_tournaments)} tournament(s).")
            else:
                st.error("Could not load any match data.")
    
    st.markdown("---")
    live_tournaments_selected = [t for t in selected_tournaments if ALL_TOURNAMENTS.get(t, {}).get('live')]
    if st.button("Clear Cache for Live Tournaments", disabled=not live_tournaments_selected):
        if live_tournaments_selected:
            cleared_count = clear_cache_for_live_tournaments(live_tournaments_selected)
            st.success(f"Cleared cache for {cleared_count} live tournament(s). Click 'Load Data' to refresh.")

# --- Main Page Content ---

# Header with personal logo
col1, col2 = st.columns([1, 10])
with col1:
    st.image("beruangbatubata.jpg", width=80) 
with col2:
    st.title("MLBB Pro-Scene Analytics Dashboard")

# --- State 1: Before Data is Loaded ---
if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.info("Please select tournaments in the sidebar and click 'Load Data' to begin.")
    st.header("How to Use This App")
    st.markdown("""
    1.  **Select Tournaments:** Use the multiselect box in the sidebar to choose one or more tournaments you want to analyze.
    2.  **Load Data:** Click the "Load Data" button. The app will fetch all match data for your selection.
    3.  **Explore:** Once the data is loaded, navigate to any of the analysis pages using the sidebar to explore the insights.
    """)
    st.header("Explore the Tools")
    st.markdown("""
    - **📊 Statistics Breakdown:** Analyze hero pick, ban, and win rates across all selected tournaments.
    - **🔎 Hero Detail Drilldown:** Dive deep into a specific hero's performance with different teams and against other heroes.
    - **⚔️ Head-to-Head:** Compare teams or heroes directly to see their historical performance against each other.
    - **🤝 Synergy & Counter Analysis:** Discover the best and worst hero pairings.
    - **🔮 Playoff Qualification Odds:** Run Monte Carlo simulations to predict tournament outcomes.
    - **🎯 Drafting Assistant:** Get live, AI-powered suggestions during a hero draft.
    - **👑 Admin Panel:** Re-train the AI model with the currently loaded tournament data.
    """)

# --- State 2: After Data is Loaded ---
else:
    pooled_matches = st.session_state['pooled_matches']
    
    st.success(f"**Data Loaded:** Analyzing **{len(st.session_state['parsed_matches'])}** matches from **{len(st.session_state['selected_tournaments'])}** tournament(s).")
    
    st.header("Meta Snapshot")

    df_stats = calculate_hero_stats_for_team(pooled_matches, "All Teams")
    
    if not df_stats.empty:
        most_picked = df_stats.loc[df_stats['Picks'].idxmax()]
        most_banned = df_stats.loc[df_stats['Bans'].idxmax()]
        
        min_games = 10
        df_min_games = df_stats[df_stats['Picks'] >= min_games]
        highest_wr = df_min_games.loc[df_min_games['Win Rate (%)'].idxmax()] if not df_min_games.empty else None

        col1, col2, col3 = st.columns(3)
        col1.metric("Most Picked Hero", most_picked['Hero'], f"{most_picked['Picks']} games")
        col2.metric("Most Banned Hero", most_banned['Hero'], f"{most_banned['Bans']} times")
        if highest_wr is not None:
            col3.metric(f"Highest Win Rate (>{min_games} games)", highest_wr['Hero'], f"{highest_wr['Win Rate (%)']:.1f}%")

        st.subheader("Top 10 Most Present Heroes (Pick % + Ban %)")
        df_presence = df_stats.sort_values("Presence (%)", ascending=False).head(10)
        st.bar_chart(df_presence.set_index('Hero')[['Pick Rate (%)', 'Ban Rate (%)']])
    else:
        st.warning("Not enough completed match data to generate a meta snapshot.")

st.markdown("---")
# --- Liquipedia Credit ---
st.image("Liquipedia_logo.png", width=200) 
