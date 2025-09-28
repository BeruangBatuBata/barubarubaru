import streamlit as st
import pandas as pd
from utils.analysis_functions import process_hero_drilldown_data
from utils.sidebar import build_sidebar

st.set_page_config(layout="wide", page_title="Hero Detail Drilldown")
build_sidebar()

st.title("🔎 Hero Detail Drilldown")

if 'parsed_matches' not in st.session_state or not st.session_state['parsed_matches']:
    st.warning("Please select and load tournament data from the sidebar on the Overview page.")
    st.stop()

# --- Main Page Logic ---
parsed_matches = st.session_state['parsed_matches']
selected_stage = "All Stages"

# Conditional Stage Filter UI (remains the same)
if len(st.session_state.get('selected_tournaments', [])) == 1:
    unique_stages = sorted(
        list(set(m['stage_type'] for m in parsed_matches if 'stage_type' in m)),
        key=lambda s: min(m['stage_priority'] for m in parsed_matches if m['stage_type'] == s)
    )
    
    if unique_stages:
        selected_stage = st.selectbox("Filter by Stage:", ["All Stages"] + unique_stages)

# --- MODIFICATION START: Apply the successful caching pattern from Page 1 ---
@st.cache_data
def get_drilldown_data(_all_matches, stage_filter):
    """
    This cached function now takes the stage filter as a simple argument
    and performs the filtering inside, making the cache reliable.
    """
    # 1. Filter the matches based on the stage selection
    if stage_filter != "All Stages":
        matches_to_analyze = [m for m in _all_matches if m.get('stage_type') == stage_filter]
    else:
        matches_to_analyze = _all_matches
    
    # 2. Process the correctly filtered list of matches
    return process_hero_drilldown_data(matches_to_analyze)

# Load data by passing the full dataset and the filter string to the cached function
all_heroes, hero_stats_map = get_drilldown_data(
    _all_matches=tuple(parsed_matches),
    stage_filter=selected_stage
)
# --- MODIFICATION END ---

selected_hero = st.selectbox(
    "Select a Hero to Analyze:",
    options=all_heroes,
    index=0
)

st.info(f"Displaying hero details for stage: **{selected_stage}**")

if selected_hero and selected_hero in hero_stats_map:
    st.header(f"Performance for {selected_hero}")
    
    hero_data = hero_stats_map[selected_hero]
    df_team = hero_data["per_team_df"]
    df_matchups = hero_data["matchups_df"]

    st.subheader("Performance by Team")
    if not df_team.empty:
        df_team_display = df_team.reset_index(drop=True)
        df_team_display.index += 1
        st.dataframe(df_team_display, use_container_width=True)
    else:
        st.info(f"No data available for {selected_hero} being played by any specific team in this stage.")

    st.subheader("Performance Against Opposing Heroes")
    if not df_matchups.empty:
        df_matchups_display = df_matchups.reset_index(drop=True)
        df_matchups_display.index += 1
        st.dataframe(df_matchups_display, use_container_width=True)
    else:
        st.info(f"No specific matchup data found for {selected_hero} in this stage.")
else:
    st.error("Selected hero not found in the data for this stage.")
