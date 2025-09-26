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

# Cache the expensive data processing step
@st.cache_data
def get_drilldown_data(_pooled_matches):
    return process_hero_drilldown_data(_pooled_matches)

# Load data from cache
all_heroes, hero_stats_map = get_drilldown_data(tuple(st.session_state['pooled_matches']))

# --- MODIFICATION START ---
# 1. Hero selection moved from sidebar to main page
selected_hero = st.selectbox(
    "Select a Hero to Analyze:",
    options=all_heroes,
    index=0
)
# --- MODIFICATION END ---

if selected_hero and selected_hero in hero_stats_map:
    st.header(f"Performance for {selected_hero}")
    
    hero_data = hero_stats_map[selected_hero]
    df_team = hero_data["per_team_df"]
    df_matchups = hero_data["matchups_df"]

    # --- Performance by Team ---
    st.subheader("Performance by Team")
    if not df_team.empty:
        # --- MODIFICATION START ---
        # 2. Reset and increment the index to start from 1
        df_team_display = df_team.reset_index(drop=True)
        df_team_display.index += 1
        st.dataframe(df_team_display, use_container_width=True)
        # --- MODIFICATION END ---
    else:
        st.info(f"No data available for {selected_hero} being played by any specific team.")

    # --- Performance vs Opposing Heroes ---
    st.subheader("Performance Against Opposing Heroes")
    if not df_matchups.empty:
        # --- MODIFICATION START ---
        # 2. Reset and increment the index to start from 1
        df_matchups_display = df_matchups.reset_index(drop=True)
        df_matchups_display.index += 1
        st.dataframe(df_matchups_display, use_container_width=True)
        # --- MODIFICATION END ---
    else:
        st.info(f"No specific matchup data found for {selected_hero}.")
else:
    st.error("Selected hero not found in the data.")
