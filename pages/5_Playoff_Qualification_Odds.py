# beruangbatubata/barubarubaru/barubarubaru-c62b52c86038cecedd2dda40e096dca331cad981/pages/5_Playoff_Qualification_Odds.py

import streamlit as st
import pandas as pd
from collections import defaultdict
import time
import json
from celery.result import AsyncResult

# --- Local Utility Imports ---
from celery_config import app
from utils.simulation import (
    get_series_outcome_options, build_standings_table,
    load_bracket_config, save_bracket_config, build_week_blocks,
    load_group_config, save_group_config,
    load_tournament_format, save_tournament_format, delete_tournament_configs
)
from utils.sidebar import build_sidebar

# --- Celery Task Imports ---
from utils.simulation_tasks import (
    run_single_table_simulation_task,
    run_group_simulation_task,
    run_deeper_analysis_task
)

st.set_page_config(layout="wide", page_title="Playoff Qualification Odds")
build_sidebar()

# --- Page State Initialization ---
if 'page_view' not in st.session_state:
    st.session_state.page_view = 'format_selection'
# Task IDs for tracking background jobs
if 'main_sim_task_id' not in st.session_state:
    st.session_state.main_sim_task_id = None
if 'analysis_task_id' not in st.session_state:
    st.session_state.analysis_task_id = None
# To store results from completed tasks
if 'main_sim_results' not in st.session_state:
    st.session_state.main_sim_results = None
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None


# --- Check for loaded data ---
if 'parsed_matches' not in st.session_state or not st.session_state['parsed_matches']:
    st.warning("Please select and load tournament data on the homepage first.")
    st.stop()

# --- Reset Button ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚠️ Danger Zone")
if st.sidebar.button("Force Reset Tournament Config"):
    tournament_to_reset = st.session_state.selected_tournaments[0]
    deleted = delete_tournament_configs(tournament_to_reset)
    if deleted:
        st.sidebar.success(f"Reset successful! Deleted: {', '.join(deleted)}")
    else:
        st.sidebar.info("No saved config found to reset.")
    
    # Reset all relevant session state variables
    st.session_state.page_view = 'format_selection'
    st.session_state.main_sim_task_id = None
    st.session_state.analysis_task_id = None
    st.session_state.main_sim_results = None
    st.session_state.analysis_results = None
    st.rerun()

# --- Global Data Prep ---
tournament_name = st.session_state.selected_tournaments[0]
all_matches_for_tournament = st.session_state['parsed_matches']

unique_stages = sorted(
    list(set(m['stage_type'] for m in all_matches_for_tournament if 'stage_type' in m)),
    key=lambda s: min(m['stage_priority'] for m in all_matches_for_tournament if m['stage_type'] == s)
)

selected_stage = None
if len(st.session_state.get('selected_tournaments', [])) == 1 and len(unique_stages) > 1:
    st.sidebar.subheader("Simulator Stage Selection")
    selected_stage = st.sidebar.selectbox(
        f"Select Stage to Simulate for {tournament_name}:",
        unique_stages, index=0, help="Choose which part of the tournament to run the simulation for."
    )
    st.sidebar.info(f"Simulating for the '{selected_stage}' stage.")

if selected_stage:
    simulation_matches = [m for m in all_matches_for_tournament if m.get("stage_type") == selected_stage]
else:
    simulation_matches = [m for m in all_matches_for_tournament if m.get("stage_priority", 99) < 40]

if not simulation_matches:
    st.error(f"No simulation-eligible matches found for the selected tournament/stage. The simulator only runs on group or regular season stages.")
    st.stop()

teams = sorted(list(set(
    opp.get('name', '').strip()
    for m in simulation_matches
    for opp in m.get("match2opponents", [])
    if opp.get('name')
)))

# --- Helper UI Functions ---
def get_teams_from_match(match):
    opps = match.get("match2opponents", [])
    teamA = opps[0].get('name', 'Team A') if len(opps) > 0 else 'Team A'
    teamB = opps[1].get('name', 'Team B') if len(opps) > 1 else 'Team B'
    return teamA, teamB

def display_task_status(task_id, task_name="Task", result_key=None):
    """
    Displays the status of a Celery task.
    When the task is complete, it stores the result in session_state and returns True.
    """
    if not task_id:
        return False

    result = app.AsyncResult(task_id) # <--- CORRECTED LINE
    
    if result.ready():
        if result.successful():
            st.success(f"{task_name} complete!")
            if result_key:
                st.session_state[result_key] = result.get()
            # Clear the task ID now that we have the results
            if st.session_state.main_sim_task_id == task_id:
                st.session_state.main_sim_task_id = None
            if st.session_state.analysis_task_id == task_id:
                st.session_state.analysis_task_id = None
            return True # Indicates completion
        else:
            st.error(f"{task_name} failed. Error: {result.info}")
            # Clear the failed task ID
            if st.session_state.main_sim_task_id == task_id:
                st.session_state.main_sim_task_id = None
            if st.session_state.analysis_task_id == task_id:
                st.session_state.analysis_task_id = None
            return False
    else:
        # For tasks that provide progress updates
        status_info = result.info if isinstance(result.info, dict) else {}
        status_message = status_info.get('status', f'{result.state}...')
        
        if 'total' in status_info and status_info.get('total', 0) > 0:
            current_step = status_info.get('current', 0)
            total_steps = status_info.get('total')
            progress_value = current_step / total_steps
            st.progress(progress_value, text=f"Step {current_step}/{total_steps}: {status_message}")
        else:
            st.info(f"{task_name} is running... Status: {status_message}")

        # Auto-refresh mechanism
        time.sleep(5)
        st.rerun()
    return False

def single_table_dashboard():
    st.header(f"Simulation for {tournament_name} (Single Table)")
    st.button(
        "← Change Tournament Format", 
        on_click=lambda: st.session_state.update(
            page_view='format_selection', 
            main_sim_task_id=None, 
            analysis_task_id=None,
            main_sim_results=None,
            analysis_results=None
        )
    )
    
    st.markdown("---"); st.subheader("Simulation Controls")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in simulation_matches if "date" in m))))
        if week_blocks:
            week_options = {"Pre-Season (Week 0)": -1}
            week_options.update({f"Week {i+1} ({wk[0]} to {wk[-1]})": i for i, wk in enumerate(week_blocks)})
            sorted_week_options = sorted(week_options.items(), key=lambda item: item[1])
            cutoff_week_label = st.select_slider("Select Cutoff Week:", options=[opt[0] for opt in sorted_week_options], value=sorted_week_options[-1][0])
            cutoff_week_idx = week_options[cutoff_week_label]
        else:
            cutoff_week_idx = -1
            st.warning("No date information available to create weekly filters.")

    with col2:
        n_sim = st.number_input("Number of Simulations:", 1000, 100000, 10000, 1000, key="single_sim_count")
    
    with col3:
        if 'current_brackets' not in st.session_state or st.session_state.get('bracket_tournament') != tournament_name:
            st.session_state.current_brackets = load_bracket_config(tournament_name)['brackets']
            st.session_state.bracket_tournament = tournament_name
        with st.expander("Configure Brackets"):
            editable_brackets = [b.copy() for b in st.session_state.current_brackets]
            for i, bracket in enumerate(editable_brackets):
                st.markdown(f"**Bracket {i+1}**"); b_cols = st.columns([4, 2, 2, 1])
                bracket['name'] = b_cols[0].text_input("Name", value=bracket.get('name', ''), key=f"s_name_{i}", label_visibility="collapsed")
                bracket['start'] = b_cols[1].number_input("Start", value=bracket.get('start', 1), min_value=1, key=f"s_start_{i}", label_visibility="collapsed")
                bracket['end'] = b_cols[2].number_input("End", value=bracket.get('end') or len(teams), min_value=bracket.get('start', 1), key=f"s_end_{i}", label_visibility="collapsed")
                if b_cols[3].button("🗑️", key=f"s_del_{i}"): st.session_state.current_brackets.pop(i); st.rerun()
            st.session_state.current_brackets = editable_brackets
            if st.button("Add Bracket", key="s_add_bracket"): st.session_state.current_brackets.append({"name": "New Bracket", "start": 1, "end": len(teams)}); st.rerun()
            if st.button("Save Brackets", type="primary", key="s_save_brackets"): save_bracket_config(tournament_name, {"brackets": st.session_state.current_brackets}); st.success("Brackets saved!")

    # --- Data Preparation for Simulation ---
    played = []
    unplayed = []
    cutoff_date = week_blocks[cutoff_week_idx][-1] if cutoff_week_idx != -1 and week_blocks else None
    
    for m in simulation_matches:
        is_played = False
        if cutoff_date:
            match_date = pd.to_datetime(m.get("date")).date() if m.get("date") else None
            has_winner = m.get("winner") in ("1", "2")
            is_bo2_complete = str(m.get("bestof")) == "2" and len(m.get("match2games", [])) == 2
        
            if (has_winner or is_bo2_complete) and match_date and match_date <= cutoff_date:
                is_played = True
        if is_played: played.append(m)
        else: unplayed.append(m)

    st.markdown("---"); st.subheader("Upcoming Matches (What-If Scenarios)")
    forced_outcomes = {}
    if not unplayed:
        st.info("No matches left to simulate.")
    else:
        # (This entire section for displaying what-if scenarios is unchanged from your original code)
        matches_by_week = defaultdict(list)
        for match in unplayed:
            if "date" not in match: continue
            for week_idx, week_dates in enumerate(week_blocks):
                try:
                    if pd.to_datetime(match['date']).date() in week_dates: 
                        matches_by_week[week_idx].append(match)
                        break
                except (ValueError, TypeError): continue
        if not matches_by_week and unplayed:
            st.info("Upcoming matches have no date information and cannot be displayed by week.")
        for week_idx in sorted(matches_by_week.keys()):
            week_label = f"Week {week_idx + 1}: {week_blocks[week_idx][0]} — {week_blocks[week_idx][-1]}"
            with st.expander(f"📅 {week_label}", expanded=False):
                matches_by_date = defaultdict(list)
                for m in matches_by_week[week_idx]:
                    try:
                        date_key = pd.to_datetime(m['date']).strftime('%Y-%m-%d')
                        matches_by_date[date_key].append(m)
                    except (ValueError, TypeError): continue
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
                                with col, st.container():
                                    st.markdown(f"<div style='text-align: center; font-weight: bold; padding: 10px; background-color: #262730; border-radius: 10px; margin-bottom: 10px;'>{teamA} vs {teamB}</div>", unsafe_allow_html=True)
                                    options = get_series_outcome_options(teamA, teamB, bo)
                                    selected = st.radio("",[opt[0] for opt in options], key=f"s_radio_{m.get('date')}_{teamA}_{teamB}", label_visibility="collapsed", horizontal=False)
                                    for opt_label, opt_code in options:
                                        if opt_label == selected: forced_outcomes[match_key] = opt_code; break

    current_wins, current_diff = defaultdict(int), defaultdict(int)
    for m in played:
        teamA, teamB = get_teams_from_match(m)
        if m.get("winner") not in ("1", "2"): continue
        winner_idx = int(m["winner"]) - 1
        winner, loser = (teamA, teamB) if winner_idx == 0 else (teamB, teamA)
        current_wins[winner] += 1
        score_winner, score_loser = 0, 0
        for game in m.get("match2games", []):
            if str(game.get('winner')) == str(winner_idx + 1): score_winner += 1
            elif game.get('winner') is not None: score_loser += 1
        current_diff[winner] += score_winner - score_loser
        current_diff[loser] += score_loser - score_winner
    
    unplayed_tuples = [(get_teams_from_match(m)[0], get_teams_from_match(m)[1], m.get("date"), m.get("bestof", 3)) for m in unplayed]
    played_json = tuple(json.dumps(m, sort_keys=True) for m in played)
    
    # --- Action Buttons & Status Display ---
    st.markdown("---")
    if st.button("Run Base Simulation", type="primary", disabled=(st.session_state.main_sim_task_id is not None)):
        with st.spinner("Dispatching simulation task..."):
            task = run_single_table_simulation_task.delay(
                teams=tuple(teams), 
                played_matches_json=played_json,
                current_wins=tuple(sorted(current_wins.items())), 
                current_diff=tuple(sorted(current_diff.items())), 
                unplayed_matches_tuples=tuple(unplayed_tuples), 
                forced_outcomes=tuple(sorted(forced_outcomes.items())), 
                brackets=tuple(tuple(sorted(b.items())) for b in st.session_state.current_brackets), # <--- CORRECTED LINE
                n_sim=n_sim
            )
            st.session_state.main_sim_task_id = task.id
            st.session_state.main_sim_results = None # Clear old results
            st.rerun()

    # If a task is running, display its status
    if st.session_state.main_sim_task_id:
        if display_task_status(st.session_state.main_sim_task_id, "Base Simulation", 'main_sim_results'):
            st.rerun() # Rerun once on completion to display results

    # --- Display Results ---
    if st.session_state.main_sim_results:
        sim_results_data = st.session_state.main_sim_results
        sim_results_df = pd.DataFrame.from_dict(sim_results_data['probs_df'])
        
        st.subheader("Results")
        res_col1, res_col2 = st.columns(2)
        with res_col1:
             # (Code to build and display standings table is unchanged)
            display_matches = played.copy()
            # ... (your original logic for adding predicted matches to display_matches)
            has_predictions = any(v != "random" for v in forced_outcomes.values())
            st.write("**Current Standings (including predictions)**" if has_predictions else "**Current Standings**")
            standings_df = build_standings_table(teams, display_matches)
            st.dataframe(standings_df, use_container_width=True, hide_index=True)
        with res_col2:
            st.write("**Playoff Probabilities**")
            # (Code to sort and display probabilities dataframe is unchanged)
            if not standings_df.empty:
                team_order = standings_df['Team'].tolist()
                sorted_probs_df = sim_results_df.set_index('Team').reindex(team_order).reset_index()
            else:
                sorted_probs_df = sim_results_df
            st.dataframe(sorted_probs_df, use_container_width=True, hide_index=True)

        # --- Deeper Analysis Section ---
        st.markdown("---"); st.subheader(f"🔍 Key Scenario Analysis")
        all_teams_sorted = sorted(teams)
        selected_team_analysis = st.selectbox("Select a team to analyze:", options=all_teams_sorted, key='analyzer_team')
        
        analysis_cols = st.columns(2)
        analysis_cols[0].metric(label="🏆 Best Possible Rank", value=f"#{sim_results_data.get('best_rank', 'N/A')}")
        analysis_cols[1].metric(label="💔 Worst Possible Rank", value=f"#{sim_results_data.get('worst_rank', 'N/A')}")
        
        if st.button(f"Run Deeper Analysis for {selected_team_analysis}", disabled=(st.session_state.analysis_task_id is not None)):
            with st.spinner("Dispatching deeper analysis task..."):
                task = run_deeper_analysis_task.delay(
                    simulation_type='single',
                    teams=tuple(teams),
                    played_json=played_json,
                    current_wins=tuple(sorted(current_wins.items())),
                    current_diff=tuple(sorted(current_diff.items())),
                    unplayed_tuples=tuple(unplayed_tuples),
                    unplayed_matches_full=unplayed, # Send the full match dicts
                    forced_outcomes=tuple(sorted(forced_outcomes.items())),
                    brackets=tuple(tuple(sorted(b.items())) for b in st.session_state.current_brackets), # <--- CORRECTED LINE
                    n_sim=n_sim,
                    selected_team_analysis=selected_team_analysis,
                    base_results_df_dict=sim_results_df.to_dict() # Pass base results
                )
                st.session_state.analysis_task_id = task.id
                st.session_state.analysis_results = None # Clear old results
                st.rerun()

    # Display status or results of the Deeper Analysis task
    if st.session_state.analysis_task_id:
        if display_task_status(st.session_state.analysis_task_id, "Deeper Analysis", 'analysis_results'):
            st.rerun()

    if st.session_state.analysis_results:
        analysis_results = st.session_state.analysis_results
        selected_team_analysis = st.session_state.analyzer_team # retrieve the selected team
        sim_results_df = pd.DataFrame.from_dict(st.session_state.main_sim_results['probs_df']) # Use main results for comparison

        # --- Display "Win and In" Results ---
        st.markdown("---")
        st.write(f"**Results if {selected_team_analysis} Wins All Remaining Matches:**")
        win_out_df = pd.DataFrame.from_dict(analysis_results['win_and_in_df'])
        all_bracket_names = [b['name'] for b in st.session_state.current_brackets]
        metric_cols = st.columns(len(all_bracket_names))
        for i, bracket_name in enumerate(all_bracket_names):
            target_col = f"{bracket_name} (%)"
            if target_col in win_out_df.columns:
                win_out_prob = win_out_df.loc[win_out_df['Team'] == selected_team_analysis, target_col].iloc[0]
                with metric_cols[i]:
                    st.metric(label=f"Chance for '{bracket_name}'", value=f"{win_out_prob:.2f}%")
        
        # --- Display "Most Important Match" Results ---
        st.markdown("---"); st.write(f"**Most Important Match**")
        most_important_match_info = analysis_results.get('most_important_match')
        if most_important_match_info:
            opponent = most_important_match_info['opponent']
            win_df = pd.DataFrame.from_dict(most_important_match_info['win_df'])
            loss_df = pd.DataFrame.from_dict(most_important_match_info['loss_df'])
            st.info(f"The game against **{opponent}** is your most critical. Here's how a win vs. a loss changes your fate:")
            
            result_cols = st.columns(len(all_bracket_names))
            for i, bracket_name in enumerate(all_bracket_names):
                with result_cols[i]:
                    st.markdown(f"**For '{bracket_name}'**")
                    col_name = f"{bracket_name} (%)"
                    base_prob = sim_results_df.loc[sim_results_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    win_prob = win_df.loc[win_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    loss_prob = loss_df.loc[loss_df['Team'] == selected_team_analysis, col_name].iloc[0]

                    st.metric(label="If you WIN 🔼", value=f"{win_prob:.2f}%", delta=f"{win_prob - base_prob:.2f}%")
                    st.metric(label="If you LOSE 🔽", value=f"{loss_prob:.2f}%", delta=f"{loss_prob - base_prob:.2f}%")
        else:
            st.info("No upcoming matches to analyze for this team.")
            
        # --- Display "Who to Root For" Results ---
        st.markdown("---"); st.write(f"**Who to Root For**")
        best_external_match_info = analysis_results.get('best_external_match')
        if best_external_match_info:
            teams_involved = best_external_match_info['teams']
            outcome = best_external_match_info['outcome']
            scenario_df = pd.DataFrame.from_dict(best_external_match_info['scenario_df'])
            st.info(f"The most helpful external result is **{outcome}** in the {teams_involved} game. Here's how it impacts your chances:")
            
            metric_cols = st.columns(len(all_bracket_names))
            for i, bracket_name in enumerate(all_bracket_names):
                col_name = f"{bracket_name} (%)"
                base_prob = sim_results_df.loc[sim_results_df['Team'] == selected_team_analysis, col_name].iloc[0]
                scenario_prob = scenario_df.loc[scenario_df['Team'] == selected_team_analysis, col_name].iloc[0]
                with metric_cols[i]:
                    st.metric(label=f"For '{bracket_name}'", value=f"{scenario_prob:.2f}%", delta=f"{scenario_prob - base_prob:.2f}%")
        else:
            st.info("No single external match significantly helps this team's chances.")

def group_setup_ui():
    st.header(f"Group Configuration for {tournament_name}")
    st.write("Assign the teams into their respective groups.")

    if 'group_config' not in st.session_state or not isinstance(st.session_state.group_config, dict) or not st.session_state.group_config.get('groups'):
        st.session_state.group_config = {'groups': {'Group A': [], 'Group B': []}}

    current_groups = st.session_state.group_config.get('groups', {})
    default_num_groups = len(current_groups) if len(current_groups) > 0 else 2
    
    num_groups = st.number_input("Number of Groups", min_value=1, max_value=8, value=default_num_groups)

    if len(current_groups) != num_groups:
        new_groups = {}
        sorted_keys = sorted(current_groups.keys())
        for i in range(num_groups):
            group_name = sorted_keys[i] if i < len(sorted_keys) else f"Group {chr(65+i)}"
            new_groups[group_name] = current_groups.get(group_name, [])
        st.session_state.group_config['groups'] = new_groups
        st.rerun()

    st.markdown("---")
    
    rerun_needed = False
    cols = st.columns(num_groups)
    all_assigned_teams = {team for group_list in current_groups.values() for team in group_list}

    for i, (group_name, group_teams) in enumerate(current_groups.items()):
        with cols[i]:
            st.subheader(group_name)
            teams_before_change = list(group_teams)
            teams_in_other_groups = all_assigned_teams - set(teams_before_change)
            available_options = [team for team in teams if team not in teams_in_other_groups]
            
            selected_teams = st.multiselect(
                f"Teams in {group_name}",
                options=available_options,
                default=teams_before_change,
                key=f"group_{group_name}"
            )
            current_groups[group_name] = selected_teams
            if set(teams_before_change) != set(selected_teams):
                rerun_needed = True
    if rerun_needed:
        st.rerun()

    assigned_teams_final = {team for group in current_groups.values() for team in group}
    unassigned_teams = [team for team in teams if team not in assigned_teams_final]
    if unassigned_teams:
        st.warning(f"Unassigned Teams: {', '.join(unassigned_teams)}")

    if st.button("Save & Continue", type="primary"):
        save_group_config(tournament_name, st.session_state.group_config)
        st.success("Group configuration saved!")
        st.session_state.page_view = 'group_sim'
        st.rerun()
        
def group_dashboard():
    st.header(f"Simulation for {tournament_name} (Group Stage)")
    st.button(
        "← Change Tournament Format", 
        on_click=lambda: st.session_state.update(
            page_view='format_selection', 
            main_sim_task_id=None, 
            analysis_task_id=None,
            main_sim_results=None,
            analysis_results=None
        )
    )
    
    group_config = st.session_state.group_config
    groups = group_config.get('groups', {})
    all_group_teams = sorted([team for group_teams in groups.values() for team in group_teams])

    st.markdown("---"); st.subheader("Simulation Controls")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in simulation_matches if "date" in m))))
        if week_blocks:
            week_options = {"Pre-Season (Week 0)": -1}
            week_options.update({f"Week {i+1} ({wk[0]} to {wk[-1]})": i for i, wk in enumerate(week_blocks)})
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
        
        config_tabs = st.tabs(["Brackets", "Groups"])
        with config_tabs[0]:
            with st.expander("Configure Brackets", expanded=False):
                editable_brackets = [b.copy() for b in st.session_state.current_brackets]
                for i, bracket in enumerate(editable_brackets):
                    st.markdown(f"**Bracket {i+1}**"); b_cols = st.columns([4, 2, 2, 1])
                    bracket['name'] = b_cols[0].text_input("Name", bracket.get('name', ''), key=f"g_name_{i}", label_visibility="collapsed")
                    bracket['start'] = b_cols[1].number_input("Start", value=bracket.get('start', 1), min_value=1, key=f"g_start_{i}", label_visibility="collapsed")
                    bracket['end'] = b_cols[2].number_input("End", value=bracket.get('end') or len(teams), min_value=bracket.get('start', 1), key=f"g_end_{i}", label_visibility="collapsed")
                    if b_cols[3].button("🗑️", key=f"g_del_{i}"): st.session_state.current_brackets.pop(i); st.rerun()
                st.session_state.current_brackets = editable_brackets
                if st.button("Add Bracket", key="g_add_bracket"): st.session_state.current_brackets.append({"name": "New Bracket", "start": 1, "end": len(teams)}); st.rerun()
                if st.button("Save Brackets", type="primary", key="g_save_brackets"): save_bracket_config(tournament_name, {"brackets": st.session_state.current_brackets}); st.success("Brackets saved!")
        with config_tabs[1]:
            with st.expander("Configure Groups", expanded=False):
                editable_groups = st.session_state.group_config.get('groups', {})
                for group_name, group_teams in editable_groups.items():
                    new_teams = st.multiselect(f"Teams in {group_name}", options=all_group_teams, default=group_teams, key=f"edit_group_{group_name}")
                    editable_groups[group_name] = new_teams
                if st.button("Save Group Changes"): st.session_state.group_config['groups'] = editable_groups; save_group_config(tournament_name, st.session_state.group_config); st.success("Group configuration updated!"); st.rerun()

    if 'analyzer_team_groups' not in st.session_state and all_group_teams:
        st.session_state.analyzer_team_groups = all_group_teams[0]

    played = []
    unplayed = []
    cutoff_date = week_blocks[cutoff_week_idx][-1] if cutoff_week_idx != -1 and week_blocks else None
    
    for m in simulation_matches:
        is_played = False
        if cutoff_date:
            match_date = pd.to_datetime(m.get("date")).date() if m.get("date") else None
            has_winner = m.get("winner") in ("1", "2")
            is_bo2_complete = str(m.get("bestof")) == "2" and len(m.get("match2games", [])) == 2
        
            if (has_winner or is_bo2_complete) and match_date and match_date <= cutoff_date:
                is_played = True

        if is_played:
            played.append(m)
        else:
            unplayed.append(m)

    st.markdown("---"); st.subheader("Upcoming Matches (What-If Scenarios)")
    forced_outcomes = {}
    if not unplayed:
        st.info("No matches left to simulate.")
    else:
        matches_by_week = defaultdict(list)
        for match in unplayed:
            if "date" not in match: continue
            for week_idx, week_dates in enumerate(week_blocks):
                try:
                    if pd.to_datetime(match['date']).date() in week_dates: 
                        matches_by_week[week_idx].append(match)
                        break
                except (ValueError, TypeError): continue
        if not matches_by_week and unplayed:
            st.info("Upcoming matches have no date information and cannot be displayed by week.")
        for week_idx in sorted(matches_by_week.keys()):
            week_label = f"Week {week_idx + 1}: {week_blocks[week_idx][0]} — {week_blocks[week_idx][-1]}"
            with st.expander(f"📅 {week_label}", expanded=False):
                matches_by_date = defaultdict(list)
                for m in matches_by_week[week_idx]:
                    try:
                        date_key = pd.to_datetime(m['date']).strftime('%Y-%m-%d')
                        matches_by_date[date_key].append(m)
                    except (ValueError, TypeError): continue
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
                                with col, st.container():
                                    st.markdown(f"<div style='text-align: center; font-weight: bold; padding: 10px; background-color: #262730; border-radius: 10px; margin-bottom: 10px;'>{teamA} vs {teamB}</div>", unsafe_allow_html=True)
                                    options = get_series_outcome_options(teamA, teamB, bo)
                                    selected = st.radio("",[opt[0] for opt in options], key=f"g_radio_{m.get('date')}_{teamA}_{teamB}", label_visibility="collapsed", horizontal=False)
                                    for opt_label, opt_code in options:
                                        if opt_label == selected: forced_outcomes[match_key] = opt_code; break

    current_wins, current_diff = defaultdict(int), defaultdict(int)
    for m in played:
        teamA, teamB = get_teams_from_match(m)
        if m.get("winner") not in ("1", "2"): continue
        winner_idx = int(m["winner"]) - 1
        winner, loser = (teamA, teamB) if winner_idx == 0 else (teamB, teamA)
        current_wins[winner] += 1
        s_w, s_l = 0,0
        for game in m.get("match2games", []):
            if str(game.get('winner')) == str(winner_idx + 1): s_w += 1
            elif game.get('winner') is not None: s_l += 1
        current_diff[winner] += s_w - s_l; current_diff[loser] += s_l - s_w
    
    unplayed_tuples = [(get_teams_from_match(m)[0], get_teams_from_match(m)[1], m.get("date"), m.get("bestof", 3)) for m in unplayed]
    played_json = tuple(json.dumps(m, sort_keys=True) for m in played)

    st.markdown("---")
    if st.button("Run Base Simulation", type="primary", disabled=(st.session_state.main_sim_task_id is not None)):
        with st.spinner("Dispatching simulation task..."):
            task = run_group_simulation_task.delay(
                groups=groups,
                played_matches_json=played_json,
                current_wins=tuple(sorted(current_wins.items())),
                current_diff=tuple(sorted(current_diff.items())),
                unplayed_matches_tuples=tuple(unplayed_tuples),
                forced_outcomes=tuple(sorted(forced_outcomes.items())),
                brackets=tuple(tuple(sorted(b.items())) for b in st.session_state.current_brackets), # <--- CORRECTED LINE
                n_sim=n_sim
            )
            st.session_state.main_sim_task_id = task.id
            st.session_state.main_sim_results = None
            st.rerun()

    if st.session_state.main_sim_task_id:
        if display_task_status(st.session_state.main_sim_task_id, "Base Simulation", 'main_sim_results'):
            st.rerun()
            
    if st.session_state.main_sim_results:
        sim_results_data = st.session_state.main_sim_results
        sim_results_df = pd.DataFrame.from_dict(sim_results_data['probs_df'])
        
        st.subheader("Results")
        display_matches = played.copy()
        for m in unplayed:
            teamA, teamB = get_teams_from_match(m)
            match_key = (teamA, teamB, m.get("date"))
            if match_key in forced_outcomes and forced_outcomes[match_key] != "random":
                outcome_code = forced_outcomes[match_key]
                predicted_match = m.copy()
                if outcome_code.startswith("A"): predicted_match["winner"] = "1"; score = outcome_code[1:]; predicted_match["scoreA"], predicted_match["scoreB"] = int(score[0]), int(score[1])
                elif outcome_code.startswith("B"): predicted_match["winner"] = "2"; score = outcome_code[1:]; predicted_match["scoreB"], predicted_match["scoreA"] = int(score[0]), int(score[1])
                display_matches.append(predicted_match)
        
        result_tabs = st.tabs(["Overall"] + sorted(groups.keys()))
        with result_tabs[0]:
            st.write("**Standings & Probabilities by Group**")
            for group_name in sorted(groups.keys()):
                st.write(f"**{group_name}**")
                g_col1, g_col2 = st.columns(2)
                group_teams = groups[group_name]
                
                with g_col1:
                    standings_df = build_standings_table(group_teams, display_matches)
                    st.dataframe(standings_df, use_container_width=True, hide_index=True)
                with g_col2:
                    group_probs = sim_results_df[sim_results_df['Group'] == group_name].drop(columns=['Group'])
                    if not standings_df.empty:
                        team_order = standings_df['Team'].tolist()
                        sorted_group_probs = group_probs.set_index('Team').reindex(team_order).reset_index()
                    else:
                        sorted_group_probs = group_probs
                    st.dataframe(sorted_group_probs, use_container_width=True, hide_index=True)

        for i, group_name in enumerate(sorted(groups.keys())):
            with result_tabs[i+1]:
                col1, col2 = st.columns(2)
                group_teams = groups[group_name]
                with col1:
                    st.write(f"**Current Standings**")
                    standings_df = build_standings_table(group_teams, display_matches)
                    st.dataframe(standings_df, use_container_width=True)
                with col2:
                    st.write(f"**Playoff Probabilities**")
                    group_probs = sim_results_df[sim_results_df['Group'] == group_name].drop(columns=['Group'])
                    if not standings_df.empty:
                        team_order = standings_df['Team'].tolist()
                        sorted_group_probs = group_probs.set_index('Team').reindex(team_order).reset_index()
                    else:
                        sorted_group_probs = group_probs
                    st.dataframe(sorted_group_probs, use_container_width=True, hide_index=True)

        st.markdown("---"); st.subheader(f"🔍 Key Scenario Analysis")
        selected_team_analysis = st.selectbox(
            "Select a team to analyze:", 
            options=all_group_teams, 
            key='analyzer_team_groups'
        )
        
        analysis_cols = st.columns(2)
        analysis_cols[0].metric(label="🏆 Best Possible Rank (in Group)", value=f"#{sim_results_data.get('best_rank', 'N/A')}")
        analysis_cols[1].metric(label="💔 Worst Possible Rank (in Group)", value=f"#{sim_results_data.get('worst_rank', 'N/A')}")
        
        if st.button(f"Run Deeper Analysis for {selected_team_analysis}", disabled=(st.session_state.analysis_task_id is not None)):
            with st.spinner("Dispatching deeper analysis task..."):
                task = run_deeper_analysis_task.delay(
                    simulation_type='group',
                    teams=tuple(teams),
                    played_json=played_json,
                    current_wins=tuple(sorted(current_wins.items())),
                    current_diff=tuple(sorted(current_diff.items())),
                    unplayed_tuples=tuple(unplayed_tuples),
                    unplayed_matches_full=unplayed,
                    forced_outcomes=tuple(sorted(forced_outcomes.items())),
                    brackets=tuple(tuple(sorted(b.items())) for b in st.session_state.current_brackets), # <--- CORRECTED LINE
                    n_sim=n_sim,
                    selected_team_analysis=selected_team_analysis,
                    base_results_df_dict=sim_results_df.to_dict(),
                    groups=groups
                )
                st.session_state.analysis_task_id = task.id
                st.session_state.analysis_results = None
                st.rerun()

    if st.session_state.analysis_task_id:
        if display_task_status(st.session_state.analysis_task_id, "Deeper Analysis", 'analysis_results'):
            st.rerun()

    if st.session_state.analysis_results:
        analysis_results = st.session_state.analysis_results
        selected_team_analysis = st.session_state.analyzer_team_groups
        sim_results_df = pd.DataFrame.from_dict(st.session_state.main_sim_results['probs_df'])

        # --- Display "Win and In" Results ---
        st.markdown("---")
        st.write(f"**Results if {selected_team_analysis} Wins All Remaining Matches:**")
        win_out_df = pd.DataFrame.from_dict(analysis_results['win_and_in_df'])
        all_bracket_names = [b['name'] for b in st.session_state.current_brackets]
        metric_cols = st.columns(len(all_bracket_names))
        for i, bracket_name in enumerate(all_bracket_names):
            target_col = f"{bracket_name} (%)"
            if target_col in win_out_df.columns:
                win_out_prob = win_out_df.loc[win_out_df['Team'] == selected_team_analysis, target_col].iloc[0]
                with metric_cols[i]:
                    st.metric(label=f"Chance for '{bracket_name}'", value=f"{win_out_prob:.2f}%")

        # --- Display "Most Important Match" Results ---
        st.markdown("---"); st.write(f"**Most Important Match**")
        most_important_match_info = analysis_results.get('most_important_match')
        if most_important_match_info:
            opponent = most_important_match_info['opponent']
            win_df = pd.DataFrame.from_dict(most_important_match_info['win_df'])
            loss_df = pd.DataFrame.from_dict(most_important_match_info['loss_df'])
            st.info(f"The game against **{opponent}** is your most critical. Here's how a win vs. a loss changes your fate:")
            
            result_cols = st.columns(len(all_bracket_names))
            for i, bracket_name in enumerate(all_bracket_names):
                with result_cols[i]:
                    st.markdown(f"**For '{bracket_name}'**")
                    col_name = f"{bracket_name} (%)"
                    base_prob = sim_results_df.loc[sim_results_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    win_prob = win_df.loc[win_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    loss_prob = loss_df.loc[loss_df['Team'] == selected_team_analysis, col_name].iloc[0]

                    st.metric(label="If you WIN 🔼", value=f"{win_prob:.2f}%", delta=f"{win_prob - base_prob:.2f}%")
                    st.metric(label="If you LOSE 🔽", value=f"{loss_prob:.2f}%", delta=f"{loss_prob - base_prob:.2f}%")
        else:
            st.info("No upcoming matches to analyze for this team.")
            
        # --- Display "Who to Root For" Results ---
        st.markdown("---"); st.write(f"**Who to Root For**")
        best_external_match_info = analysis_results.get('best_external_match')
        if best_external_match_info:
            teams_involved = best_external_match_info['teams']
            outcome = best_external_match_info['outcome']
            scenario_df = pd.DataFrame.from_dict(best_external_match_info['scenario_df'])
            st.info(f"The most helpful external result is **{outcome}** in the {teams_involved} game. Here's how it impacts your chances:")
            
            metric_cols = st.columns(len(all_bracket_names))
            for i, bracket_name in enumerate(all_bracket_names):
                col_name = f"{bracket_name} (%)"
                base_prob = sim_results_df.loc[sim_results_df['Team'] == selected_team_analysis, col_name].iloc[0]
                scenario_prob = scenario_df.loc[scenario_df['Team'] == selected_team_analysis, col_name].iloc[0]
                with metric_cols[i]:
                    st.metric(label=f"For '{bracket_name}'", value=f"{scenario_prob:.2f}%", delta=f"{scenario_prob - base_prob:.2f}%")
        else:
            st.info("No single external match significantly helps this team's chances.")

# --- Page Router ---
if 'active_tournament' not in st.session_state or st.session_state.active_tournament != tournament_name:
    st.session_state.active_tournament = tournament_name
    # Clear state when tournament changes
    st.session_state.main_sim_task_id = None
    st.session_state.analysis_task_id = None
    st.session_state.main_sim_results = None
    st.session_sate.analysis_results = None
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
