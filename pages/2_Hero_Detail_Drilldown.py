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

@st.cache_data
def get_drilldown_data(_pooled_matches):
    return process_hero_drilldown_data(_pooled_matches)

pooled_matches = st.session_state['pooled_matches']
all_heroes, hero_stats_map = get_drilldown_data(tuple(pooled_matches))

st.sidebar.header("Hero Selection")
selected_hero = st.sidebar.selectbox("Select a Hero:", all_heroes)

if selected_hero:
    st.header(f"Analysis for {selected_hero}")
    hero_data = hero_stats_map.get(selected_hero)
    if hero_data:
        st.subheader("Performance by Team")
        st.dataframe(hero_data["per_team_df"], use_container_width=True)
        
        st.subheader("Matchup Analysis (Most Faced Opponents)")
        st.dataframe(hero_data["matchups_df"], use_container_width=True)
    else:
        st.warning(f"No data available for {selected_hero}.")
