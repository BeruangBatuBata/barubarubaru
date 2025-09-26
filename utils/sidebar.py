import streamlit as st
from utils.api_handler import ALL_TOURNAMENTS, load_tournament_data, clear_cache_for_live_tournaments
from utils.data_processing import parse_matches
import os
import base64

def get_image_as_base64(path):
    """Encodes a local image file to a Base64 string for embedding in HTML."""
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return None

def build_sidebar():
    """
    Creates the persistent sidebar with the logo and tournament selection tools.
    """
    # --- NEW: Stable Sidebar Header ---
    logo_base64 = get_image_as_base64("beruangbatubata.png")
    if logo_base64:
        st.sidebar.markdown(
            f"""
            <div style="display: flex;align-items: center; gap: 0px; margin-bottom: 20px;">
                <img src="data:image/png;base64,{logo_base64}" style="width: 40px; height: 60px;margin-right: 0px;">
                <div style="font-size: 1.5em; font-weight: bold; color: #fafafa; line-height: 1.3;">
                    MLBB Pro-scene<br>
                    Analytics Dashboard
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # --- Tournament Selection ---
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
