import streamlit as st
import pandas as pd
import time
import json
from collections import defaultdict
from celery.result import AsyncResult
from celery_config import app as celery_app

# Import the new Celery tasks
from utils.simulation_tasks import run_single_table_sim_task, run_group_sim_task

# Import the original utility functions
from utils.simulation import (
    get_series_outcome_options, build_standings_table, build_week_blocks,
    load_bracket_config, save_bracket_config,
    load_group_config, save_group_config,
    load_tournament_format, save_tournament_format,
    delete_tournament_configs
)
from utils.sidebar import build_sidebar

st.set_page_config(layout="wide", page_title="Playoff Qualification Odds")
build_sidebar()

# --- Page State and Data Prep (Unchanged) ---
if 'page_view' not in st.session_state:
    st.session_state.page_view = 'format_selection'

if 'parsed_matches' not in st.session_state or not st.session_state['parsed_matches']:
    st.warning("Please select and load tournament data on the homepage first.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.subheader("⚠️ Danger Zone")
if st.sidebar.button("Force Reset Tournament Config"):
    if st.session_state.get('selected_tournaments'):
        tournament_to_reset = st.session_state.selected_tournaments[0]
        deleted = delete_tournament_configs(tournament_to_reset)
        if deleted: st.sidebar.success(f"Reset successful! Deleted: {', '.join(deleted)}")
        else: st.sidebar.info("No saved config found to reset.")
        st.session_state.page_view = 'format_selection'
        st.rerun()
    else:
        st.sidebar.warning("No tournament selected.")

tournament_name = st.session_state.selected_tournaments[0]
all_matches_for_tournament = st.session_state['parsed_matches']

unique_stages = sorted(
    list(set(m['stage_type'] for m in all_matches_for_tournament if 'stage_type' in m)),
    key=lambda s: min(m['stage_priority'] for m in all_matches_for_tournament if m['stage_type'] == s)
)

selected_stage = None
if len(st.session_state.get('selected_tournaments', [])) == 1 and len(unique_stages) > 1:
    st.sidebar.subheader("Simulator Stage Selection")
    selected_stage = st.sidebar.selectbox(f"Select Stage to Simulate for {tournament_name}:", unique_stages, index=0)

if selected_stage:
    simulation_matches = [m for m in all_matches_for_tournament if m.get("stage_type") == selected_stage]
else:
    simulation_matches = [m for m in all_matches_for_tournament if m.get("stage_priority", 99) < 40]

if not simulation_matches:
    st.error(f"No simulation-eligible matches found for the selected tournament/stage.")
    st.stop()

teams = sorted(list(set(
    opp.get('name', '').strip() for m in simulation_matches for opp in m.get("match2opponents", []) if opp.get('name')
)))

# --- NEW: Helper function for displaying results ---
def display_simulation_results(task_id):
    result = AsyncResult(task_id, app=celery_app)
    if result.ready():
        st.success("✅ Simulation complete!")
        if result.successful():
            sim_results_data = result.get()
            sim_results_df = pd.read_json(sim_results_data['probs_df'], orient='split')
            best_rank = sim_results_data.get('best_rank')
            worst_rank = sim_results_data.get('worst_rank')
            
            st.subheader("Simulation Results")
            cols = st.columns(2)
            cols[0].metric(label="🏆 Best Possible Rank", value=f"#{best_rank}" if best_rank else "N/A")
            cols[1].metric(label="💔 Worst Possible Rank", value=f"#{worst_rank}" if worst_rank else "N/A")
            st.dataframe(sim_results_df, use_container_width=True, hide_index=True)
        else:
            st.error(f"Task failed: {result.state}")
            st.json(result.info)
        st.session_state['monitoring_task_id'] = None
    else:
        with st.spinner(f"Simulation task {task_id} is {result.state}... Auto-refreshing in 10 seconds."):
            time.sleep(10)
        st.rerun()

# --- Main UI Rendering Functions (Phase 1) ---
def get_teams_from_match(match):
    opps = match.get("match2opponents", [])
    teamA = opps[0].get('name', 'Team A') if opps else 'Team A'
    teamB = opps[1].get('name', 'Team B') if len(opps) > 1 else 'Team B'
    return teamA, teamB

def single_table_dashboard():
    st.header(f"Simulation for {tournament_name} (Single Table)")
    st.button("← Change Tournament Format", on_click=lambda: st.session_state.update(page_view='format_selection'))
    
    st.markdown("---"); st.subheader("Simulation Controls")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in simulation_matches if "date" in m))))
    with col1:
        if week_blocks:
            week_options = {"Pre-Season (Week 0)": -1, **{f"Week {i+1} ({wk[0]} to {wk[-1]})": i for i, wk in enumerate(week_blocks)}}
            sorted_week_options = sorted(week_options.items(), key=lambda item: item[1])
            cutoff_week_label = st.select_slider("Select Cutoff Week:", options=[opt[0] for opt in sorted_week_options], value=sorted_week_options[-1][0])
            cutoff_week_idx = week_options[cutoff_week_label]
        else:
            cutoff_week_idx = -1
    
    with col2:
        n_sim = st.number_input("Number of Simulations:", 1000, 100000, 10000, 1000, key="single_sim_count")
    
    with col3:
        if 'current_brackets' not in st.session_state or st.session_state.get('bracket_tournament') != tournament_name:
            st.session_state.current_brackets = load_bracket_config(tournament_name)['brackets']
            st.session_state.bracket_tournament = tournament_name
        with st.expander("Configure Brackets"):
            editable_brackets = [b.copy() for b in st.session_state.current_brackets]
            for i, bracket in enumerate(editable_brackets):
                b_cols = st.columns([4, 2, 2, 1])
                bracket['name'] = b_cols[0].text_input(f"Name {i+1}", value=bracket.get('name', ''), key=f"s_name_{i}")
                bracket['start'] = b_cols[1].number_input(f"Start {i+1}", value=bracket.get('start', 1), min_value=1, key=f"s_start_{i}")
                bracket['end'] = b_cols[2].number_input(f"End {i+1}", value=bracket.get('end') or len(teams), min_value=bracket.get('start', 1), key=f"s_end_{i}")
                if b_cols[3].button("🗑️", key=f"s_del_{i}"):
                    editable_brackets.pop(i)
                    st.session_state.current_brackets = editable_brackets
                    st.rerun()
            st.session_state.current_brackets = editable_brackets
            if st.button("Add Bracket", key="s_add_bracket"):
                st.session_state.current_brackets.append({"name": "New Bracket", "start": 1, "end": len(teams)})
                st.rerun()
            if st.button("Save Brackets", type="primary", key="s_save_brackets"):
                save_bracket_config(tournament_name, {"brackets": st.session_state.current_brackets})
                st.success("Brackets saved!")

    played, unplayed = [], []
    cutoff_date = week_blocks[cutoff_week_idx][-1] if cutoff_week_idx != -1 and week_blocks else pd.to_datetime("2100-01-01").date()
    for m in simulation_matches:
        match_date = pd.to_datetime(m.get("date")).date() if m.get("date") else None
        if m.get("winner") in ("1", "2") and match_date and match_date <= cutoff_date:
            played.append(m)
        else:
            unplayed.append(m)
    
    forced_outcomes = {}
    st.markdown("---"); st.subheader("Upcoming Matches (What-If Scenarios)")
    if not unplayed:
        st.info("No matches left to simulate.")
    else:
        matches_by_week = defaultdict(list)
        for match in unplayed:
            if "date" in match and match['date']:
                for week_idx, week_dates in enumerate(week_blocks):
                    if pd.to_datetime(match['date']).date() in week_dates:
                        matches_by_week[week_idx].append(match)
                        break
        if not matches_by_week and unplayed:
            st.info("Upcoming matches have no date information and cannot be displayed by week.")
        for week_idx in sorted(matches_by_week.keys()):
            with st.expander(f"📅 Week {week_idx + 1}", expanded=False):
                matches_by_date = defaultdict(list)
                for m in matches_by_week[week_idx]:
                    matches_by_date[pd.to_datetime(m['date']).strftime('%Y-%m-%d')].append(m)
                for date_key in sorted(matches_by_date.keys()):
                    st.markdown(f"#### 📅 {date_key}")
                    date_matches = matches_by_date[date_key]
                    for idx in range(0, len(date_matches), 3):
                        cols = st.columns(3)
                        for col_idx, col in enumerate(cols):
                            if idx + col_idx < len(date_matches):
                                m = date_matches[idx + col_idx]
                                teamA, teamB = get_teams_from_match(m)
                                bo = m.get("bestof", 3)
                                match_key = (teamA, teamB, m.get('date'))
                                with col:
                                    st.markdown(f"<div style='text-align: center; font-weight: bold;'>{teamA} vs {teamB}</div>", unsafe_allow_html=True)
                                    options = get_series_outcome_options(teamA, teamB, bo)
                                    selected = st.radio("",[opt[0] for opt in options], key=f"s_radio_{m.get('date')}_{teamA}_{teamB}", label_visibility="collapsed", horizontal=False)
                                    for opt_label, opt_code in options:
                                        if opt_label == selected:
                                            forced_outcomes[match_key] = opt_code
                                            break
    
    current_wins, current_diff = defaultdict(int), defaultdict(int)
    for m in played:
        teamA, teamB = get_teams_from_match(m)
        winner, loser = (teamA, teamB) if m["winner"] == "1" else (teamB, teamA)
        current_wins[winner] += 1
        s_w = sum(1 for g in m.get("match2games", []) if str(g.get('winner')) == m['winner'])
        s_l = sum(1 for g in m.get("match2games", []) if g.get('winner') and str(g.get('winner')) != m['winner'])
        current_diff[winner] += s_w - s_l
        current_diff[loser] += s_l - s_w
    
    unplayed_tuples = [(get_teams_from_match(m)[0], get_teams_from_match(m)[1], m.get("date"), m.get("bestof", 3)) for m in unplayed]
    
    st.markdown("---"); st.subheader(f"🔍 Key Scenario Analysis")
    selected_team_analysis = st.selectbox("Select a team to analyze:", options=teams, key='analyzer_team')
    
    if st.button(f"Run Deeper Analysis for {selected_team_analysis}"):
        played_json = tuple(json.dumps(m, sort_keys=True) for m in played)
        try:
            with st.spinner("Sending simulation job..."):
                task = run_single_table_sim_task.delay(
                    teams=list(teams),
                    played_matches_json=played_json,
                    current_wins=tuple(sorted(current_wins.items())),
                    current_diff=tuple(sorted(current_diff.items())),
                    unplayed_matches=tuple(unplayed_tuples),
                    forced_outcomes=tuple(sorted(forced_outcomes.items())),
                    brackets=tuple(frozenset(b.items()) for b in st.session_state.get('current_brackets', [])),
                    n_sim=n_sim,
                    team_to_track=selected_team_analysis
                )
                st.session_state['monitoring_task_id'] = task.id
                st.rerun()
        except Exception as e:
            st.error("❌ Failed to send simulation task.")
            st.exception(e)

    if 'monitoring_task_id' in st.session_state and st.session_state['monitoring_task_id']:
        display_simulation_results(st.session_state['monitoring_task_id'])
    else:
        st.subheader("Current Standings")
        display_matches = played + [m for m in unplayed if forced_outcomes.get((get_teams_from_match(m)[0], get_teams_from_match(m)[1], m.get("date")))]
        standings_df = build_standings_table(teams, display_matches)
        st.dataframe(standings_df, use_container_width=True, hide_index=True)
        st.info("Run a deeper analysis to see live simulation results.")

def group_dashboard():
    st.header(f"Simulation for {tournament_name} (Group Stage)")
    st.button("← Change Tournament Format", on_click=lambda: st.session_state.update(page_view='format_selection'))
    
    group_config = st.session_state.get('group_config', load_group_config(tournament_name))
    groups = group_config.get('groups', {})
    all_group_teams = sorted([team for group_teams in groups.values() for team in group_teams])
    
    st.markdown("---"); st.subheader("Simulation Controls")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in simulation_matches if "date" in m))))

    with col1:
        if week_blocks:
            week_options = {"Pre-Season (Week 0)": -1, **{f"Week {i+1} ({wk[0]} to {wk[-1]})": i for i, wk in enumerate(week_blocks)}}
            sorted_week_options = sorted(week_options.items(), key=lambda item: item[1])
            cutoff_week_label = st.select_slider("Select Cutoff Week:", options=[opt[0] for opt in sorted_week_options], value=sorted_week_options[-1][0], key="group_week_slider")
            cutoff_week_idx = week_options[cutoff_week_label]
        else:
            cutoff_week_idx = -1
            st.warning("No date information available to create weekly filters.")

    with col2:
        n_sim = st.number_input("Number of Simulations:", 1000, 100000, 10000, 1000, key="group_sim_count")
    
    with col3:
        if 'current_brackets' not in st.session_state or st.session_state.get('bracket_tournament') != tournament_name:
            st.session_state.current_brackets = load_bracket_config(tournament_name)['brackets']
            st.session_state.bracket_tournament = tournament_name
        
        with st.expander("Configure Brackets & Groups", expanded=False):
            editable_brackets = [b.copy() for b in st.session_state.current_brackets]
            for i, bracket in enumerate(editable_brackets):
                b_cols = st.columns([4, 2, 2, 1])
                bracket['name'] = b_cols[0].text_input("Name", bracket.get('name', ''), key=f"g_name_{i}")
                bracket['start'] = b_cols[1].number_input("Start", value=bracket.get('start', 1), min_value=1, key=f"g_start_{i}")
                bracket['end'] = b_cols[2].number_input("End", value=bracket.get('end') or len(teams), min_value=bracket.get('start', 1), key=f"g_end_{i}")
                if b_cols[3].button("🗑️", key=f"g_del_{i}"): 
                    editable_brackets.pop(i); st.session_state.current_brackets = editable_brackets; st.rerun()
            st.session_state.current_brackets = editable_brackets
            if st.button("Add Bracket", key="g_add_bracket"): 
                st.session_state.current_brackets.append({"name": "New Bracket", "start": 1, "end": len(teams)}); st.rerun()
            if st.button("Save Brackets", type="primary", key="g_save_brackets"): 
                save_bracket_config(tournament_name, {"brackets": st.session_state.current_brackets}); st.success("Brackets saved!")

    played, unplayed = [], []
    cutoff_date = week_blocks[cutoff_week_idx][-1] if cutoff_week_idx != -1 and week_blocks else pd.to_datetime("2100-01-01").date()
    
    for m in simulation_matches:
        match_date = pd.to_datetime(m.get("date")).date() if m.get("date") else None
        if m.get("winner") in ("1", "2") and match_date and match_date <= cutoff_date:
            played.append(m)
        else:
            unplayed.append(m)

    forced_outcomes = {}
    st.markdown("---"); st.subheader("Upcoming Matches (What-If Scenarios)")
    if not unplayed:
        st.info("All matches for this stage have been played.")
    else:
        matches_by_week = defaultdict(list)
        for match in unplayed:
            if "date" in match and match['date']:
                for week_idx, week_dates in enumerate(week_blocks):
                    if pd.to_datetime(match['date']).date() in week_dates: matches_by_week[week_idx].append(match); break
        if not matches_by_week and unplayed:
            st.info("Upcoming matches have no date information and cannot be displayed by week.")
        for week_idx in sorted(matches_by_week.keys()):
            with st.expander(f"📅 Week {week_idx + 1}", expanded=False):
                matches_by_date = defaultdict(list)
                for m in matches_by_week[week_idx]: matches_by_date[pd.to_datetime(m['date']).strftime('%Y-%m-%d')].append(m)
                for date_key in sorted(matches_by_date.keys()):
                    st.markdown(f"#### 📅 {date_key}")
                    date_matches = matches_by_date[date_key]
                    for idx in range(0, len(date_matches), 3):
                        cols = st.columns(3)
                        for col_idx, col in enumerate(cols):
                            if idx + col_idx < len(date_matches):
                                m = date_matches[idx + col_idx]
                                teamA, teamB = get_teams_from_match(m); bo = m.get("bestof", 3)
                                match_key = (teamA, teamB, m.get('date'))
                                with col:
                                    st.markdown(f"<div style='text-align: center; font-weight: bold;'>{teamA} vs {teamB}</div>", unsafe_allow_html=True)
                                    options = get_series_outcome_options(teamA, teamB, bo)
                                    selected = st.radio("",[opt[0] for opt in options], key=f"g_radio_{m.get('date')}_{teamA}_{teamB}", label_visibility="collapsed", horizontal=False)
                                    for opt_label, opt_code in options:
                                        if opt_label == selected: forced_outcomes[match_key] = opt_code; break
    
    current_wins, current_diff = defaultdict(int), defaultdict(int)
    for m in played:
        teamA, teamB = get_teams_from_match(m)
        winner, loser = (teamA, teamB) if m["winner"] == "1" else (teamB, teamA)
        current_wins[winner] += 1
        s_w = sum(1 for g in m.get("match2games", []) if str(g.get('winner')) == m['winner'])
        s_l = sum(1 for g in m.get("match2games", []) if g.get('winner') and str(g.get('winner')) != m['winner'])
        current_diff[winner] += s_w - s_l
        current_diff[loser] += s_l - s_w

    unplayed_tuples = [(get_teams_from_match(m)[0], get_teams_from_match(m)[1], m.get("date"), m.get("bestof", 3)) for m in unplayed]

    st.markdown("---"); st.subheader(f"🔍 Key Scenario Analysis")
    selected_team_analysis = st.selectbox(
        "Select a team to analyze:", 
        options=all_group_teams, 
        key='analyzer_team_groups'
    )
    
    if st.button(f"Run Deeper Analysis for {selected_team_analysis}"):
        played_json = tuple(json.dumps(m, sort_keys=True) for m in played)
        try:
            with st.spinner("Sending group simulation job..."):
                task = run_group_sim_task.delay(
                    groups=groups,
                    played_matches_json=played_json,
                    current_wins=tuple(sorted(current_wins.items())),
                    current_diff=tuple(sorted(current_diff.items())),
                    unplayed_matches=tuple(unplayed_tuples),
                    forced_outcomes=tuple(sorted(forced_outcomes.items())),
                    brackets=tuple(frozenset(b.items()) for b in st.session_state.get('current_brackets', [])),
                    n_sim=n_sim,
                    team_to_track=selected_team_analysis
                )
                st.session_state['monitoring_task_id'] = task.id
                st.rerun()
        except Exception as e:
            st.error("❌ Failed to send group simulation task.")
            st.exception(e)
            
    if 'monitoring_task_id' in st.session_state and st.session_state['monitoring_task_id']:
        display_simulation_results(st.session_state['monitoring_task_id'])
    else:
        st.subheader("Current Standings by Group")
        display_matches = played + [m for m in unplayed if forced_outcomes.get((get_teams_from_match(m)[0], get_teams_from_match(m)[1], m.get("date")))]
        for group_name, group_teams in groups.items():
            st.write(f"**{group_name}**")
            standings_df = build_standings_table(group_teams, display_matches)
            st.dataframe(standings_df, use_container_width=True, hide_index=True)
        st.info("Run a deeper analysis for a team to see live simulation results.")

def group_setup_ui():
    st.header(f"Group Configuration for {tournament_name}")
    st.write("Assign the teams into their respective groups.")
    
    # Load config if not in session state
    if 'group_config' not in st.session_state or not st.session_state.group_config:
        st.session_state.group_config = load_group_config(tournament_name)

    current_groups = st.session_state.group_config.get('groups', {})
    default_num_groups = len(current_groups) if current_groups else 2
    
    num_groups = st.number_input("Number of Groups", min_value=1, max_value=8, value=default_num_groups)
    
    # Adjust number of groups in UI
    if len(current_groups) != num_groups:
        new_groups = {}
        sorted_keys = sorted(current_groups.keys())
        for i in range(num_groups):
            group_name = sorted_keys[i] if i < len(sorted_keys) else f"Group {chr(65+i)}"
            new_groups[group_name] = current_groups.get(group_name, [])
        st.session_state.group_config['groups'] = new_groups
        st.rerun()

    st.markdown("---")
    
    cols = st.columns(num_groups)
    all_assigned_teams = {team for group_list in current_groups.values() for team in group_list}

    for i, (group_name, group_teams) in enumerate(current_groups.items()):
        with cols[i]:
            st.subheader(group_name)
            teams_in_other_groups = all_assigned_teams - set(group_teams)
            available_options = [team for team in teams if team not in teams_in_other_groups]
            
            selected_teams = st.multiselect(
                f"Teams in {group_name}",
                options=available_options,
                default=group_teams,
                key=f"group_{group_name}"
            )
            current_groups[group_name] = selected_teams

    assigned_teams_final = {team for group in current_groups.values() for team in group}
    unassigned_teams = [team for team in teams if team not in assigned_teams_final]
    if unassigned_teams:
        st.warning(f"Unassigned Teams: {', '.join(unassigned_teams)}")

    if st.button("Save & Continue", type="primary"):
        save_group_config(tournament_name, st.session_state.group_config)
        st.success("Group configuration saved!")
        st.session_state.page_view = 'group_sim'
        st.rerun()

# --- Page Router (Final Section) ---
if 'active_tournament' not in st.session_state or st.session_state.active_tournament != tournament_name:
    st.session_state.active_tournament = tournament_name
    saved_format = load_tournament_format(tournament_name)
    if not saved_format:
        st.session_state.page_view = 'format_selection'
    elif saved_format == 'single_table':
        st.session_state.page_view = 'single_table_sim'
    elif saved_format == 'group':
        saved_group_config = load_group_config(tournament_name)
        if saved_group_config and saved_group_config.get('groups'):
            st.session_state.group_config = saved_group_config
            st.session_state.page_view = 'group_sim'
        else:
            st.session_state.page_view = 'group_setup'

if st.session_state.page_view == 'format_selection':
    st.title("🏆 Playoff Odds: Tournament Format")
    st.info(f"First time setting up '{tournament_name}'? Please select its format below.")
    st.write(f"How is **{tournament_name}** structured?")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Single Table League", use_container_width=True, type="primary"):
            save_tournament_format(tournament_name, 'single_table')
            st.session_state.page_view = 'single_table_sim'
            st.rerun()
    with col2:
        if st.button("Group Stage", use_container_width=True, type="primary"):
            save_tournament_format(tournament_name, 'group')
            st.session_state.page_view = 'group_setup'
            st.rerun()

elif st.session_state.page_view == 'group_setup':
    group_setup_ui()
    if st.button("← Back to Format Selection"):
        st.session_state.page_view = 'format_selection'
        st.rerun()
        
elif st.session_state.page_view == 'single_table_sim':
    single_table_dashboard()

elif st.session_state.page_view == 'group_sim':
    group_dashboard()
