import streamlit as st
import pandas as pd
from utils.analysis_functions import process_hero_drilldown_data
from utils.sidebar import build_sidebar

st.set_page_config(layout="wide", page_title="Hero Detail Drilldown")
build_sidebar()

st.title("🔎 Hero Detail Drilldown")

if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.warning("Please select and load tournament data from the sidebar on the Overview page.")
    st.stop()

# --- MODIFICATION START: Correctly implement conditional stage filtering ---
matches_to_analyze = st.session_state['parsed_matches']
selected_stage = "All Stages"

# Only show the filter if a single tournament is selected
if len(st.session_state.get('selected_tournaments', [])) == 1:
    unique_stages = sorted(
        list(set(m['stage_type'] for m in matches_to_analyze if 'stage_type' in m)),
        key=lambda s: min(m['stage_priority'] for m in matches_to_analyze if m['stage_type'] == s)
    )
    
    if unique_stages:
        selected_stage = st.selectbox("Filter by Stage:", ["All Stages"] + unique_stages)

# Filter the matches based on the selection BEFORE they are passed to the cached function
if selected_stage != "All Stages":
    matches_to_analyze = [m for m in matches_to_analyze if m.get('stage_type') == selected_stage]
# --- MODIFICATION END ---


# Cache the expensive data processing step
@st.cache_data
def get_drilldown_data(_matches):
    """This function now receives the pre-filtered list of matches."""
    return process_hero_drilldown_data(_matches)

# Load data from cache using the (now correctly filtered) match list
all_heroes, hero_stats_map = get_drilldown_data(tuple(matches_to_analyze))


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
