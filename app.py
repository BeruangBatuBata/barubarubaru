import streamlit as st
from collections import OrderedDict
from utils.data_processing import parse_matches
from utils.api_handler import ALL_TOURNAMENTS, load_tournament_data, clear_cache_for_live_tournaments

st.set_page_config(page_title="MLBB Analytics Dashboard", page_icon="🎮", layout="wide")

st.title("MLBB Pro-Scene Analytics Dashboard")
st.markdown("Welcome! Select tournaments in the sidebar, then click 'Load Data'.")

if 'selected_tournaments' not in st.session_state:
    st.session_state['selected_tournaments'] = []
if 'pooled_matches' not in st.session_state:
    st.session_state['pooled_matches'] = None
if 'parsed_matches' not in st.session_state:
    st.session_state['parsed_matches'] = None

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

if st.session_state.get('parsed_matches'):
    st.success(f"**Data Loaded:** {len(st.session_state['parsed_matches'])} matches from {len(st.session_state['selected_tournaments'])} tournament(s).")
    st.info("Navigate to a page in the sidebar to view the analysis.")
