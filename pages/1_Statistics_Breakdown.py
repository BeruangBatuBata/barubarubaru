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

# --- MODIFICATION START: Logic to handle stage filtering ---
pooled_matches = st.session_state['pooled_matches']
selected_stage = "All Stages"
num_selected_tournaments = len(st.session_state.get('selected_tournaments', []))

# --- DEBUGGING START ---
st.write(f"DEBUG: Number of tournaments selected: **{num_selected_tournaments}**")
# --- DEBUGGING END ---

# Only show the stage filter if a single tournament is selected
if num_selected_tournaments == 1:
    # Get unique, sorted stages from the loaded data
    unique_stages = sorted(
        list(set(m['stage_type'] for m in pooled_matches if 'stage_type' in m)),
        key=lambda s: min(m['stage_priority'] for m in pooled_matches if m['stage_type'] == s)
    )
    
    # --- DEBUGGING START ---
    st.write(f"DEBUG: Unique stages found: **{unique_stages}**")
    # --- DEBUGGING END ---

    if unique_stages:
        # Create the filter. It will show one or more stages depending on the tournament.
        selected_stage = st.selectbox("Filter by Stage:", ["All Stages"] + unique_stages)


# Filter the matches if a specific stage has been selected
if selected_stage != "All Stages":
    filtered_matches = [m for m in pooled_matches if m.get('stage_type') == selected_stage]
else:
    filtered_matches = pooled_matches
# --- MODIFICATION END ---

played_matches = [match for match in filtered_matches if any(game.get("winner") for game in match.get("match2games", []))]
all_teams = sorted(list(set(opp.get('name','').strip() for match in played_matches for opp in match.get("match2opponents", []) if opp.get('name'))))


col1_filter, col2_sort, col3_order, col4_download = st.columns([2, 2, 2, 1])

with col1_filter:
    selected_team = st.selectbox("Filter by Team:", ["All Teams"] + all_teams, index=0)

st.info(f"Displaying hero statistics for **{selected_team}** in the selected tournaments: **{', '.join(st.session_state['selected_tournaments'])}**")

with st.spinner(f"Calculating stats for {selected_team}..."):
    # --- MODIFICATION START: Use the potentially filtered match list ---
    df_stats = get_stats_df(tuple(filtered_matches), selected_team)
    # --- MODIFICATION END ---

if df_stats.empty:
    st.warning(f"No match data found for '{selected_team}' in the selected tournaments.")
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
