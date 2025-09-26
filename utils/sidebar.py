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
    # 1. Absolutely positioned logo, placed at the top of the sidebar
    logo_base64 = get_image_as_base64("beruangbatubata.jpg")
    if logo_base64:
        st.sidebar.markdown(f"""
            <div style="
                position: absolute;
                top: 20px;
                left: 20px;
                z-index: 1000;
            ">
                <img src="data:image/jpeg;base64,{logo_base64}" style="width: 250px; border-radius: 10px;">
            </div>
        """, unsafe_allow_html=True)

    # 2. A spacer element to push the content down.
    # Adjust the height (e.g., 8rem) to be a little more than your logo's height.
    st.sidebar.markdown('<div style="height: 8rem;"></div>', unsafe_allow_html=True)


    # 3. The rest of your sidebar content, which will now start below the spacer.
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
