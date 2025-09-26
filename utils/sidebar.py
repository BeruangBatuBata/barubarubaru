import streamlit as st
from utils.api_handler import ALL_TOURNAMENTS, load_tournament_data, clear_cache_for_live_tournaments
from utils.data_processing import parse_matches
import os

def build_sidebar():
    """
    Creates the persistent sidebar with tournament selection tools.
    The logo is now handled globally in 0_Overview.py.
    """
    with st.sidebar.expander("Tournament Selection", expanded=True):
        selected_tournaments = st.multiselect(
            "Choose tournaments:",
            options=list(ALL_TOURNAMENTS.keys()),
            default=st.session_state.get('selected_tournaments', []),
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
                    st.success(f"Loaded data for {len(selected_tournaments)} tournament(s).")
                else:
                    st.error("Could not load any match data.")
        
        live_tournaments_selected = [t for t in selected_tournaments if ALL_TOURNAMENTS.get(t, {}).get('live')]
        if st.button("Clear Cache for Live Tournaments", disabled=not live_tournaments_selected):
            if live_tournaments_selected:
                cleared_count = clear_cache_for_live_tournaments(live_tournaments_selected)
                st.success(f"Cleared cache for {cleared_count} live tournament(s).")
