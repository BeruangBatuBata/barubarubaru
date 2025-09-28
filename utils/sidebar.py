import streamlit as st
from utils.api_handler import ALL_TOURNAMENTS, load_tournament_data, clear_cache_for_live_tournaments
from utils.data_processing import parse_matches
import os
import base64
from collections import defaultdict

def get_image_as_base_64(path):
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
    logo_base64 = get_image_as_base_64("beruangbatubata.png")
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

    # --- Initialize session_state for the central truth of selections ---
    if 'tournament_selections' not in st.session_state:
        st.session_state.tournament_selections = {name: False for name in ALL_TOURNAMENTS.keys()}

    # --- Tournament Selection Expander ---
    with st.sidebar.expander("Tournament Selection", expanded=True):

        # --- Create Data Structures for Grouping ---
        tournaments_by_region = defaultdict(list)
        tournaments_by_split = defaultdict(list)
        tournaments_by_league = defaultdict(list)
        all_tournament_names = list(ALL_TOURNAMENTS.keys())

        for name, data in ALL_TOURNAMENTS.items():
            tournaments_by_region[data['region']].append(name)
            tournaments_by_split[data.get('split', 'Uncategorized')].append(name)
            tournaments_by_league[data.get('league', 'Uncategorized')].append(name)
        
        sorted_regions = ['International'] + sorted([r for r in tournaments_by_region if r != 'International'])
        sorted_splits = sorted(tournaments_by_split.keys(), reverse=True)
        sorted_leagues = sorted(tournaments_by_league.keys())


        # --- Callback Functions ---
        # --- MODIFICATION START: Updated sync function ---
        def sync_checkbox_state(t_name, changed_key):
            # 1. Get the new value from the checkbox that was just clicked
            new_value = st.session_state[changed_key]
            
            # 2. Update the central source of truth
            st.session_state.tournament_selections[t_name] = new_value
            
            # 3. Force all other checkboxes for the same tournament to match
            st.session_state[f"region_chk_{t_name}"] = new_value
            st.session_state[f"split_chk_{t_name}"] = new_value
            st.session_state[f"league_chk_{t_name}"] = new_value
        # --- MODIFICATION END ---


        def select_all(group, value=True):
            for t_name in group:
                st.session_state.tournament_selections[t_name] = value
                # Update all three possible widget states to keep them in sync
                st.session_state[f"region_chk_{t_name}"] = value
                st.session_state[f"split_chk_{t_name}"] = value
                st.session_state[f"league_chk_{t_name}"] = value

        # --- Global Select/Deselect All ---
        col1_all, col2_all = st.columns(2)
        col1_all.button("Select All Tournaments", key="select_all_global", on_click=select_all, args=(all_tournament_names, True), use_container_width=True)
        col2_all.button("Deselect All Tournaments", key="deselect_all_global", on_click=select_all, args=(all_tournament_names, False), use_container_width=True)
        st.sidebar.markdown("---")
        
        # --- Tabs for different groupings ---
        region_tab, split_tab, league_tab = st.tabs(["By Region", "By Split", "By League"])

        with region_tab:
            for region in sorted_regions:
                with st.expander(f"{region} ({len(tournaments_by_region[region])})"):
                    col1, col2 = st.columns(2)
                    region_tournaments = tournaments_by_region[region]
                    col1.button("Select All", key=f"select_all_{region}", on_click=select_all, args=(region_tournaments, True), use_container_width=True)
                    col2.button("Deselect All", key=f"deselect_all_{region}", on_click=select_all, args=(region_tournaments, False), use_container_width=True)
                    st.markdown("---")
                    for t_name in region_tournaments:
                        # --- MODIFICATION START: Use the central state for value and pass the key to the callback ---
                        key = f"region_chk_{t_name}"
                        st.checkbox(t_name, value=st.session_state.tournament_selections[t_name], key=key, on_change=sync_checkbox_state, args=(t_name, key))
                        # --- MODIFICATION END ---
        
        with split_tab:
            for split in sorted_splits:
                with st.expander(f"{split} ({len(tournaments_by_split[split])})"):
                    col1, col2 = st.columns(2)
                    split_tournaments = tournaments_by_split[split]
                    col1.button("Select All", key=f"select_all_{split}", on_click=select_all, args=(split_tournaments, True), use_container_width=True)
                    col2.button("Deselect All", key=f"deselect_all_{split}", on_click=select_all, args=(split_tournaments, False), use_container_width=True)
                    st.markdown("---")
                    for t_name in split_tournaments:
                        # --- MODIFICATION START: Use the central state for value and pass the key to the callback ---
                        key = f"split_chk_{t_name}"
                        st.checkbox(t_name, value=st.session_state.tournament_selections[t_name], key=key, on_change=sync_checkbox_state, args=(t_name, key))
                        # --- MODIFICATION END ---
        
        with league_tab:
            for league in sorted_leagues:
                with st.expander(f"{league} ({len(tournaments_by_league[league])})"):
                    col1, col2 = st.columns(2)
                    league_tournaments = tournaments_by_league[league]
                    col1.button("Select All", key=f"select_all_{league}", on_click=select_all, args=(league_tournaments, True), use_container_width=True)
                    col2.button("Deselect All", key=f"deselect_all_{league}", on_click=select_all, args=(league_tournaments, False), use_container_width=True)
                    st.markdown("---")
                    for t_name in league_tournaments:
                        # --- MODIFICATION START: Use the central state for value and pass the key to the callback ---
                        key = f"league_chk_{t_name}"
                        st.checkbox(t_name, value=st.session_state.tournament_selections[t_name], key=key, on_change=sync_checkbox_state, args=(t_name, key))
                        # --- MODIFICATION END ---


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
