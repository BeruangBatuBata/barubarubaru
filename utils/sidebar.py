import streamlit as st
from utils.api_handler import ALL_TOURNAMENTS, load_tournament_data, clear_cache_for_live_tournaments
from utils.data_processing import parse_matches
import os
import base64
from collections import defaultdict

def get_image_as_base64(path):
    """Encodes a local image file to a Base64 string for embedding in HTML."""
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return None

def build_sidebar():
    """
    Creates the persistent sidebar with an advanced, tabbed tournament selection UI.
    """
    # --- Sidebar Header ---
    logo_base64 = get_image_as_base64("beruangbatubata.png")
    if logo_base64:
        st.sidebar.markdown(
            f"""
            <div style="display: flex;align-items: center;justify-content: center; gap: 0px; margin-bottom: 20px;">
                <img src="data:image/png;base64,{logo_base64}" style="width: 40px; height: 60px;margin-right: 0px;">
                <div style="font-size: 1.5em; font-weight: bold; color: #fafafa; line-height: 1.3;">
                    MLBB Pro-scene<br>
                    Analytics Dashboard
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # --- Initialize session_state for selections ---
    if 'tournament_selections' not in st.session_state:
        st.session_state.tournament_selections = {name: False for name in ALL_TOURNAMENTS.keys()}

    # --- Tournament Selection Expander ---
    with st.sidebar.expander("Tournament Selection", expanded=True):

        # --- Create Data Structures for Grouping ---
        tournaments_by_region = defaultdict(list)
        tournaments_by_year = defaultdict(list)
        for name, data in ALL_TOURNAMENTS.items():
            tournaments_by_region[data['region']].append(name)
            tournaments_by_year[data['year']].append(name)
        
        sorted_regions = ['International'] + sorted([r for r in tournaments_by_region if r != 'International'])
        sorted_years = sorted(tournaments_by_year.keys(), reverse=True)

        # --- Callback Functions for State Synchronization ---
        def sync_checkbox_state(key):
            # This function is called when a checkbox changes.
            # It updates the central dictionary with the new value from the widget.
            st.session_state.tournament_selections[key] = st.session_state[f"chk_{key}"]

        def select_all(group, value=True):
            for t_name in group:
                st.session_state.tournament_selections[t_name] = value
        
        # --- Tabs for Region and Year ---
        region_tab, year_tab = st.tabs(["By Region", "By Year"])

        with region_tab:
            for region in sorted_regions:
                with st.expander(f"{region} ({len(tournaments_by_region[region])})"):
                    col1, col2 = st.columns(2)
                    region_tournaments = tournaments_by_region[region]
                    col1.button("Select All", key=f"select_all_{region}", on_click=select_all, args=(region_tournaments, True), use_container_width=True)
                    col2.button("Deselect All", key=f"deselect_all_{region}", on_click=select_all, args=(region_tournaments, False), use_container_width=True)
                    st.markdown("---")
                    for t_name in region_tournaments:
                        st.checkbox(
                            t_name, 
                            value=st.session_state.tournament_selections[t_name], 
                            key=f"chk_{t_name}", # Unique key for the widget itself
                            on_change=sync_checkbox_state, 
                            args=(t_name,) # Pass the tournament name to the callback
                        )
        
        with year_tab:
            for year in sorted_years:
                with st.expander(f"Year {year} ({len(tournaments_by_year[year])})"):
                    col1, col2 = st.columns(2)
                    year_tournaments = tournaments_by_year[year]
                    col1.button("Select All", key=f"select_all_{year}", on_click=select_all, args=(year_tournaments, True), use_container_width=True)
                    col2.button("Deselect All", key=f"deselect_all_{year}", on_click=select_all, args=(year_tournaments, False), use_container_width=True)
                    st.markdown("---")
                    for t_name in year_tournaments:
                        # This checkbox will now correctly sync with the one in the other tab
                         st.checkbox(
                            t_name, 
                            value=st.session_state.tournament_selections[t_name], 
                            key=f"chk_{t_name}", 
                            on_change=sync_checkbox_state, 
                            args=(t_name,)
                        )

        # --- Data Loading and Cache Clearing Logic ---
        st.markdown("---")
        selected_tournaments = [name for name, selected in st.session_state.tournament_selections.items() if selected]

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
