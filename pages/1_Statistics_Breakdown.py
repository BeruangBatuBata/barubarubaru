import streamlit as st
import pandas as pd
from utils.analysis_functions import calculate_hero_stats_for_team
from utils.sidebar import build_sidebar

st.set_page_config(layout="wide", page_title="Statistics Breakdown")
build_sidebar()

st.title("📊 Statistics Breakdown")

# --- HOW TO USE SECTION ---
with st.expander("ℹ️ How to Use This Dashboard", expanded=False):
    st.markdown("""
        Welcome to the MLBB Pro-Scene Analytics Dashboard! Here’s a quick guide to get you started:

        ### 1. Loading Data (The First Step!)
        - **Go to the "Overview" page** using the navigation on the left.
        - In the sidebar, you'll see a **"Tournament Selection"** area.
        - Click to expand it and choose one or more tournaments you want to analyze. You can select by Region, Split, or League.
        - Once you've made your selections, click the **"Load Data"** button at the bottom of the sidebar.
        - The app will then fetch all the match data for the selected tournaments. You'll see a success message on the Overview page when it's done.

        ### 2. Exploring the Features
        Once data is loaded, you can navigate to any of the pages to explore different insights:

        - **📊 Statistics Breakdown (This Page):**
          - View detailed hero statistics like pick rate, ban rate, win rate, and presence.
          - Use the dropdown menus to filter the stats for a specific team or a particular stage of a tournament (e.g., Playoffs, Group Stage).
          - Sort the data by any column to find top-performing heroes.

        - **🔎 Hero Detail Drilldown:**
          - Select a single hero to see a deep dive into their performance.
          - Analyze which teams play the hero most effectively.
          - See how the hero performs against every other hero in the game.

        - **⚔️ Head-to-Head:**
          - Compare two teams directly to see their historical win/loss record and their most common picks and bans against each other.
          - Switch to "Hero vs. Hero" mode to see which of two heroes wins more often when they are on opposing teams.

        - **🤝 Synergy & Counter Analysis:**
          - Discover the best and worst performing hero duos (Synergy/Anti-Synergy).
          - Use the "Counters" mode to find which heroes are statistically strong or weak against a selected hero.
          - Filter by team to see team-specific strategies.

        - **🔮 Playoff Qualification Odds:**
          - Run simulations for a selected tournament to see the probability of each team qualifying for playoffs.
          - Use the "What-If Scenarios" to force outcomes of upcoming matches and see how it impacts the final standings.

        - **🎯 Drafting Assistant:**
          - An AI-powered tool to help with the drafting phase.
          - Select two teams and fill in the picks and bans as they happen.
          - The AI will provide a live win probability and suggest the best heroes to pick or ban next.

        - **👑 Admin Panel:**
          - Re-train the AI model using the currently loaded tournament data to keep its predictions up-to-date with the latest meta.
    """)
# --- END SECTION ---


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
