import streamlit as st
import pandas as pd
from utils.analysis_functions import calculate_hero_stats_for_team
from utils.sidebar import build_sidebar

st.set_page_config(layout="wide", page_title="Statistics Breakdown")
build_sidebar()

st.title("📊 Statistics Breakdown")

if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.warning("Please select and load tournament data from the sidebar on the Overview page.")
    st.stop()

@st.cache_data
def get_stats_df(_pooled_matches, team_filter):
    return calculate_hero_stats_for_team(_pooled_matches, team_filter)

pooled_matches = st.session_state['pooled_matches']
played_matches = [match for match in pooled_matches if any(game.get("winner") for game in match.get("match2games", []))]
all_teams = sorted(list(set(opp.get('name','').strip() for match in played_matches for opp in match.get("match2opponents", []) if opp.get('name'))))

st.sidebar.header("Statistics Filters")
selected_team = st.sidebar.selectbox("Filter by Team:", ["All Teams"] + all_teams, index=0)

st.info(f"Displaying hero statistics for **{selected_team}** in the selected tournaments: **{', '.join(st.session_state['selected_tournaments'])}**")

with st.spinner(f"Calculating stats for {selected_team}..."):
    df_stats = get_stats_df(tuple(pooled_matches), selected_team)

if df_stats.empty:
    st.warning(f"No match data found for '{selected_team}' in the selected tournaments.")
else:
    col1, col2, col3 = st.columns(3)
    sort_column = col1.selectbox("Sort by:", options=df_stats.columns, index=list(df_stats.columns).index("Presence (%)"))
    sort_order = col2.radio("Order:", options=["Descending", "Ascending"], horizontal=True)
    
    df_display = df_stats.sort_values(by=sort_column, ascending=(sort_order == "Ascending")).reset_index(drop=True)
    df_display.index += 1
    
    st.dataframe(df_display, use_container_width=True)
    
    csv = df_display.to_csv(index=False).encode('utf-8')
    with col3:
        st.download_button(
           label="📥 Download as CSV",
           data=csv,
           file_name=f'hero_stats_{selected_team}.csv',
           mime='text/csv',
        )
