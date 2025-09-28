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

@st.cache_data
def get_stats_df(_matches_to_analyze, team_filter):
    # The function now expects the filtered list of matches
    return calculate_hero_stats_for_team(_matches_to_analyze, team_filter)

# Use the correct 'parsed_matches' session state as the source of truth
parsed_matches = st.session_state['parsed_matches']
selected_stage = "All Stages"

# --- MODIFICATION START: Conditional Stage Filter ---
# Only show the stage filter if a single tournament is selected
if len(st.session_state.get('selected_tournaments', [])) == 1:
    # Create a sorted list of unique stages from the data, using the priority number
    unique_stages = sorted(
        list(set(m['stage_type'] for m in parsed_matches if 'stage_type' in m)),
        key=lambda s: min(m['stage_priority'] for m in parsed_matches if m['stage_type'] == s)
    )
    
    # If there are stages, create the selectbox
    if unique_stages:
        selected_stage = st.selectbox("Filter by Stage:", ["All Stages"] + unique_stages)

# Filter the matches if a specific stage has been selected
if selected_stage != "All Stages":
    filtered_matches = [m for m in parsed_matches if m.get('stage_type') == selected_stage]
else:
    # Otherwise, use all matches
    filtered_matches = parsed_matches
# --- MODIFICATION END ---


# Now, derive the list of teams from the potentially filtered matches
played_matches = [match for match in filtered_matches if any(game.get("winner") for game in match.get("match2games", []))]
all_teams = sorted(list(set(opp.get('name','').strip() for match in played_matches for opp in match.get("match2opponents", []) if opp.get('name'))))


col1_filter, col2_sort, col3_order, col4_download = st.columns([2, 2, 2, 1])

with col1_filter:
    selected_team = st.selectbox("Filter by Team:", ["All Teams"] + all_teams, index=0)

st.info(f"Displaying hero statistics for **{selected_team}** in the selected tournaments: **{', '.join(st.session_state['selected_tournaments'])}**")

with st.spinner(f"Calculating stats for {selected_team}..."):
    # Pass the correctly filtered list of matches to the analysis function
    df_stats = get_stats_df(tuple(filtered_matches), selected_team)
st.info(f"Displaying hero statistics for **{selected_team}** during stage: **{selected_stage}**.")
st.write(f"Number of matches being analyzed: **{len(filtered_matches)}**")
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
