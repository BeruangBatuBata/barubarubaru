import streamlit as st
import pandas as pd
from utils.analysis_functions import calculate_hero_stats_for_team
from utils.sidebar import build_sidebar

st.set_page_config(layout="wide", page_title="Statistics Breakdown")
build_sidebar()

st.title("📊 Statistics Breakdown")

if 'parsed_matches' not in st.session_state or not st.session_state['parsed_matches']:
    st.warning("Please select and load tournament data from the sidebar on the Overview page.")
    st.stop()

# --- MODIFICATION START: Updated Caching Strategy ---
@st.cache_data
def get_stats_df(_all_matches, team_filter, stage_filter):
    """
    This cached function now takes the stage filter as a simple argument
    and performs the filtering inside, making the cache more reliable.
    """
    # 1. Filter the matches based on the stage
    if stage_filter != "All Stages":
        matches_to_analyze = [m for m in _all_matches if m.get('stage_type') == stage_filter]
    else:
        matches_to_analyze = _all_matches

    # 2. Pass the correctly filtered list to the calculation function
    return calculate_hero_stats_for_team(matches_to_analyze, team_filter)
# --- MODIFICATION END ---

# --- Main Page Logic ---

# Use the parsed_matches from session state as the base data
parsed_matches = st.session_state['parsed_matches']
selected_stage = "All Stages"

# --- Conditional Stage Filter UI ---
# This part remains the same
if len(st.session_state.get('selected_tournaments', [])) == 1:
    unique_stages = sorted(
        list(set(m['stage_type'] for m in parsed_matches if 'stage_type' in m)),
        key=lambda s: min(m['stage_priority'] for m in parsed_matches if m['stage_type'] == s)
    )
    
    if unique_stages:
        selected_stage = st.selectbox("Filter by Stage:", ["All Stages"] + unique_stages)

# Now, we need to derive the list of teams from the potentially filtered matches
# This is for the team dropdown, so we need to manually filter here as well.
if selected_stage != "All Stages":
    matches_for_team_list = [m for m in parsed_matches if m.get('stage_type') == selected_stage]
else:
    matches_for_team_list = parsed_matches

played_matches = [match for match in matches_for_team_list if any(game.get("winner") for game in match.get("match2games", []))]
all_teams = sorted(list(set(opp.get('name','').strip() for match in played_matches for opp in match.get("match2opponents", []) if opp.get('name'))))


col1_filter, col2_sort, col3_order, col4_download = st.columns([2, 2, 2, 1])

with col1_filter:
    selected_team = st.selectbox("Filter by Team:", ["All Teams"] + all_teams, index=0)

st.info(f"Displaying hero statistics for **{selected_team}** in stage **{selected_stage}** for the selected tournaments.")

with st.spinner(f"Calculating stats for {selected_team}..."):
    # --- MODIFICATION START: Updated function call ---
    # Pass the full dataset and the simple filter strings to the cached function
    df_stats = get_stats_df(
        _all_matches=tuple(parsed_matches), 
        team_filter=selected_team, 
        stage_filter=selected_stage
    )
    # --- MODIFICATION END ---


if df_stats.empty:
    st.warning(f"No match data found for '{selected_team}' in the selected tournaments or stage.")
else:
    with col2_sort:
        sort_column = st.selectbox("Sort by:", options=df_stats.columns, index=list(df_stats.columns).index("Presence (%)"))
    with col3_order:
        sort_order = st.radio("Order:", options=["Descending", "Ascending"], horizontal=True, label_visibility="collapsed")

    df_display = df_stats.sort_values(by=sort_column, ascending=(sort_order == "Ascending")).reset_index(drop=True)
    df_display.index += 1
    
    st.dataframe(df_display, use_container_width=True)
    
    csv = df_display.to_csv(index=False).encode('utf-8')
    with col4_download:
        st.download_button(
           label="📥 Download as CSV",
           data=csv,
           file_name=f'hero_stats_{selected_team}.csv',
           mime='text/csv',
        )
