import streamlit as st
import pandas as pd
from collections import defaultdict
from utils.simulation import *
from utils.sidebar import build_sidebar

st.set_page_config(layout="wide", page_title="Playoff Qualification Odds")
build_sidebar()

if 'page_view' not in st.session_state:
    st.session_state.page_view = 'format_selection'
if 'parsed_matches' not in st.session_state or not st.session_state['parsed_matches']:
    st.warning("Please select and load tournament data from the sidebar on the Overview page.")
    st.stop()

tournament_name = st.session_state.selected_tournaments[0]
regular_season_matches = [m for m in st.session_state.parsed_matches if m.get("is_regular_season", False)]
if not regular_season_matches:
    st.error("No regular season matches found for this feature."); st.stop()
teams = sorted(list(set(m["teamA"] for m in regular_season_matches) | set(m["teamB"] for m in regular_season_matches)))

@st.cache_data(show_spinner=False)
def cached_single_table_sim(teams_tuple, wins_tuple, diff_tuple, unplayed_tuple, forced_tuple, brackets_tuple, n_sim):
    return run_monte_carlo_simulation(list(teams_tuple), dict(wins_tuple), dict(diff_tuple), list(unplayed_tuple), dict(forced_tuple), [dict(b) for b in brackets_tuple], n_sim)
@st.cache_data(show_spinner=False)
def cached_group_sim(groups_tuple, wins_tuple, diff_tuple, unplayed_tuple, forced_tuple, brackets_tuple, n_sim):
    groups = {k: list(v) for k, v in groups_tuple}
    return run_monte_carlo_simulation_groups(groups, dict(wins_tuple), dict(diff_tuple), list(unplayed_tuple), dict(forced_tuple), [dict(b) for b in brackets_tuple], n_sim)

def group_setup_ui():
    st.header(f"Group Configuration for {tournament_name}")
    if 'group_config' not in st.session_state: st.session_state.group_config = {'groups': {'Group A': [], 'Group B': []}}
    num_groups = st.number_input("Number of Groups", 1, 8, len(st.session_state.group_config.get('groups', {})))
    current_groups = st.session_state.group_config.get('groups', {})
    if len(current_groups) != num_groups:
        new_groups = {}; sorted_keys = sorted(current_groups.keys())
        for i in range(num_groups):
            group_name = sorted_keys[i] if i < len(sorted_keys) else f"Group {chr(65+i)}"; new_groups[group_name] = current_groups.get(group_name, [])
        st.session_state.group_config['groups'] = new_groups; st.rerun()
    assigned_teams = {team for group in current_groups.values() for team in group}
    unassigned_teams = [team for team in teams if team not in assigned_teams]
    if unassigned_teams: st.warning(f"Unassigned Teams: {', '.join(unassigned_teams)}")
    cols = st.columns(num_groups)
    for i, (group_name, group_teams) in enumerate(current_groups.items()):
        with cols[i]:
            new_teams = st.multiselect(f"Teams in {group_name}", teams, default=group_teams, key=f"group_{group_name}")
            current_groups[group_name] = new_teams
    if st.button("Save & Continue", type="primary"):
        save_group_config(tournament_name, st.session_state.group_config)
        st.session_state.page_view = 'group_sim'; st.rerun()

def dashboard(is_group_mode):
    st.header(f"Simulation for {tournament_name} ({'Group Stage' if is_group_mode else 'Single Table'})")
    week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in regular_season_matches))))
    st.sidebar.header("Simulation Controls")
    week_options = {f"Week {i+1}": i for i in range(len(week_blocks))}; week_options["Pre-Season"] = -1
    cutoff_week_idx = st.sidebar.select_slider("Cutoff Week:", options=list(week_options.values()), format_func=lambda x: [k for k, v in week_options.items() if v == x][0], value=len(week_blocks)-1)
    n_sim = st.sidebar.number_input("Simulations:", 1000, 100000, 10000, 1000)
    if 'current_brackets' not in st.session_state or st.session_state.get('bracket_tournament') != tournament_name:
        st.session_state.current_brackets = load_bracket_config(tournament_name)['brackets']
        st.session_state.bracket_tournament = tournament_name
    # (Bracket config UI and the rest of dashboard logic follows...)

if st.session_state.page_view == 'format_selection':
    st.title("🏆 Playoff Odds: Tournament Format")
    # (Format selection logic)
elif st.session_state.page_view == 'group_setup':
    group_setup_ui()
else:
    dashboard(is_group_mode=(st.session_state.page_view == 'group_sim'))
