import streamlit as st
import pandas as pd
from collections import defaultdict
import random
from utils.simulation import (
    get_series_outcome_options, build_standings_table, run_monte_carlo_simulation,
    load_bracket_config, save_bracket_config, build_week_blocks,
    load_group_config, save_group_config, run_monte_carlo_simulation_groups,
    load_tournament_format, save_tournament_format, delete_tournament_configs
)
from utils.sidebar import build_sidebar

st.set_page_config(layout="wide", page_title="Playoff Qualification Odds")
build_sidebar()

# --- Page State Initialization ---
if 'page_view' not in st.session_state:
    st.session_state.page_view = 'format_selection'

# --- Check for loaded data ---
if 'parsed_matches' not in st.session_state or not st.session_state['parsed_matches']:
    st.warning("Please select and load tournament data on the homepage first.")
    st.stop()

# --- ADD THE RESET BUTTON TO THE SIDEBAR ---
st.sidebar.markdown("---")
st.sidebar.subheader("⚠️ Danger Zone")
if st.sidebar.button("Force Reset Tournament Config"):
    tournament_to_reset = st.session_state.selected_tournaments[0]
    deleted = delete_tournament_configs(tournament_to_reset)
    if deleted:
        st.sidebar.success(f"Reset successful! Deleted: {', '.join(deleted)}")
    else:
        st.sidebar.info("No saved config found to reset.")
    
    # IMPORTANT: Reset the page view state to force a fresh start
    st.session_state.page_view = 'format_selection'
    st.rerun()
# --- END OF BUTTON CODE ---
# --- Global Data Prep ---
tournament_name = st.session_state.selected_tournaments[0]
all_matches_for_tournament = st.session_state['parsed_matches']

# Determine unique stages for the selected tournament
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


# --- Cached Simulation Functions ---
@st.cache_data(show_spinner="Running single-table simulation...")
def cached_single_table_sim(teams, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim, team_to_track=None):
    return run_monte_carlo_simulation(
        list(teams), 
        dict(current_wins), 
        dict(current_diff), 
        list(unplayed_matches), 
        dict(forced_outcomes), 
        [dict(b) for b in brackets], 
        n_sim,
        team_to_track=team_to_track  # Pass the new argument through
    )

@st.cache_data(show_spinner="Running group stage simulation...")
def cached_group_sim(groups, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim, team_to_track=None):
    return run_monte_carlo_simulation_groups(
        groups, 
        dict(current_wins), 
        dict(current_diff), 
        list(unplayed_matches), 
        dict(forced_outcomes), 
        [dict(b) for b in brackets], 
        n_sim,
        team_to_track=team_to_track  # Pass the new argument through
    )

# --- UI Functions ---
def get_teams_from_match(match):
    opps = match.get("match2opponents", [])
    teamA = opps[0].get('name', 'Team A') if len(opps) > 0 else 'Team A'
    teamB = opps[1].get('name', 'Team B') if len(opps) > 1 else 'Team B'
    return teamA, teamB

# In pages/5_Playoff_Qualification_Odds.py

def group_setup_ui():
    st.header(f"Group Configuration for {tournament_name}")
    st.write("Assign the teams into their respective groups.")

    # Initialize group_config if it doesn't exist or is invalid
    if 'group_config' not in st.session_state or not isinstance(st.session_state.group_config, dict) or not st.session_state.group_config.get('groups'):
        st.session_state.group_config = {'groups': {'Group A': [], 'Group B': []}}

    current_groups = st.session_state.group_config.get('groups', {})
    default_num_groups = len(current_groups) if len(current_groups) > 0 else 2
    
    num_groups = st.number_input("Number of Groups", min_value=1, max_value=8, value=default_num_groups)

    # Adjust the number of groups in the config if the user changes the number input
    if len(current_groups) != num_groups:
        new_groups = {}
        sorted_keys = sorted(current_groups.keys())
        for i in range(num_groups):
            group_name = sorted_keys[i] if i < len(sorted_keys) else f"Group {chr(65+i)}"
            new_groups[group_name] = current_groups.get(group_name, [])
        st.session_state.group_config['groups'] = new_groups
        st.rerun()

    st.markdown("---")
    
    # --- START: FINAL CORRECTED LOGIC ---

    # Flag to check if a rerun is needed after the full UI is drawn.
    rerun_needed = False

    cols = st.columns(num_groups)
    
    # Get a set of all teams that have been assigned to any group
    all_assigned_teams = {team for group_list in current_groups.values() for team in group_list}

    # Loop and draw ALL group selection boxes first.
    for i, (group_name, group_teams) in enumerate(current_groups.items()):
        with cols[i]:
            st.subheader(group_name)

            # Store the current state of the group before rendering the widget
            teams_before_change = list(group_teams)

            # Determine which teams are assigned to OTHER groups
            teams_in_other_groups = all_assigned_teams - set(teams_before_change)

            # The options for this multiselect are any team not in another group
            available_options = [team for team in teams if team not in teams_in_other_groups]
            
            # Render the multiselect widget
            selected_teams = st.multiselect(
                f"Teams in {group_name}",
                options=available_options,
                default=teams_before_change,
                key=f"group_{group_name}"
            )

            # Update the state with the potentially new selection
            current_groups[group_name] = selected_teams

            # If a change was made, set the flag to True.
            if set(teams_before_change) != set(selected_teams):
                rerun_needed = True

    # After the loop is finished and the entire UI is drawn, check the flag.
    if rerun_needed:
        st.rerun()

    # --- END: FINAL CORRECTED LOGIC ---

    # Display unassigned teams
    assigned_teams_final = {team for group in current_groups.values() for team in group}
    unassigned_teams = [team for team in teams if team not in assigned_teams_final]
    if unassigned_teams:
        st.warning(f"Unassigned Teams: {', '.join(unassigned_teams)}")

    # Save button
    if st.button("Save & Continue", type="primary"):
        save_group_config(tournament_name, st.session_state.group_config)
        st.success("Group configuration saved!")
        st.session_state.page_view = 'group_sim'
        st.rerun()
        
def single_table_dashboard():
    st.header(f"Simulation for {tournament_name} (Single Table)")
    st.button("← Change Tournament Format", on_click=lambda: st.session_state.update(page_view='format_selection'))
    
    # --- Top Control Layout ---
    st.markdown("---"); st.subheader("Simulation Controls")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in simulation_matches if "date" in m))))
        if week_blocks:
            week_options = {f"Week {i+1} ({wk[0]} to {wk[-1]})": i for i, wk in enumerate(week_blocks)}
            week_options["Pre-Season (Week 0)"] = -1
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
            if st.button("Save Brackets", type="primary", key="s_save_brackets"): save_bracket_config(tournament_name, {"brackets": st.session_state.current_brackets}); st.success("Brackets saved!"); st.cache_data.clear()

    # --- Initialize Session State for Team Selector ---
    all_teams_sorted = sorted(teams)
    if 'analyzer_team' not in st.session_state:
        st.session_state.analyzer_team = all_teams_sorted[0]

    # --- Corrected Data Preparation Logic ---
    played = []
    unplayed = []
    cutoff_date = week_blocks[cutoff_week_idx][-1] if cutoff_week_idx != -1 and week_blocks else None
    
    for m in simulation_matches:
        match_date = pd.to_datetime(m.get("date")).date() if m.get("date") else None
        
        # Determine if the match is considered "played" based on the new rules
        is_played = False
        num_games_played = len(m.get("match2games", []))
        
        # Rule 1: It has a definitive winner (for Bo1, Bo3, Bo5).
        has_winner = m.get("winner") in ("1", "2")
        # Rule 2 (Your suggestion): It's a Bo2 and 2 games have been played.
        is_bo2_complete = str(m.get("bestof")) == "2" and num_games_played == 2
    
        if has_winner or is_bo2_complete:
            if cutoff_date and match_date and match_date <= cutoff_date:
                is_played = True
            elif not cutoff_date: # If no cutoff, any completed match is "played"
                is_played = True
    
        if is_played:
            played.append(m)
        else:
            unplayed.append(m)

    # --- Upcoming Matches (What-If Scenarios) UI ---
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
                                    selected = st.radio("",[opt[0] for opt in options], key=f"s_radio_{m.get('date')}_{teamA}_{teamB}", label_visibility="collapsed", horizontal=False)
                                    for opt_label, opt_code in options:
                                        if opt_label == selected: forced_outcomes[match_key] = opt_code; break

    # --- Data prep for simulation ---
    current_wins, current_diff = defaultdict(int), defaultdict(int)
    for m in played:
        teamA, teamB = get_teams_from_match(m)
        winner_idx = int(m["winner"]) - 1
        winner, loser = (teamA, teamB) if winner_idx == 0 else (teamB, teamA)
        current_wins[winner] += 1
        score_winner, score_loser = 0, 0
        for game in m.get("match2games", []):
            if str(game.get('winner')) == str(winner_idx + 1): score_winner += 1
            elif game.get('winner') is not None: score_loser += 1
        current_diff[winner] += score_winner - score_loser
        current_diff[loser] += score_loser - score_winner
    unplayed_tuples = []
    for m in unplayed:
        teamA, teamB = get_teams_from_match(m)
        unplayed_tuples.append((teamA, teamB, m.get("date"), m.get("bestof", 3)))

    # --- A SINGLE, UNIFIED SIMULATION CALL for base results ---
    with st.spinner(f"Running simulation for {st.session_state.analyzer_team}..."):
        sim_results_data = cached_single_table_sim(
            tuple(teams), tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), 
            tuple(unplayed_tuples), tuple(sorted(forced_outcomes.items())), 
            tuple(frozenset(b.items()) for b in st.session_state.current_brackets), 
            n_sim, team_to_track=st.session_state.analyzer_team
        )
    
    sim_results_df = sim_results_data['probs_df']
    best_rank = sim_results_data.get('best_rank')
    worst_rank = sim_results_data.get('worst_rank')

    # --- DISPLAY RESULTS ---
    st.markdown("---"); st.subheader("Results")
    res_col1, res_col2 = st.columns(2)
    with res_col1:
        display_matches = played.copy()
        for m in unplayed:
            teamA, teamB = get_teams_from_match(m)
            match_key = (teamA, teamB, m.get("date"))
            if match_key in forced_outcomes and forced_outcomes[match_key] != "random":
                outcome_code = forced_outcomes[match_key]
                predicted_match = m.copy()
                if outcome_code.startswith("A"):
                    predicted_match["winner"] = "1"
                    score_part = outcome_code[1:]
                    if len(score_part) == 2:
                        scoreA, scoreB = int(score_part[0]), int(score_part[1])
                        predicted_match["match2games"] = ([{'winner': '1'}] * scoreA) + ([{'winner': '2'}] * scoreB)
                elif outcome_code.startswith("B"):
                    predicted_match["winner"] = "2"
                    score_part = outcome_code[1:]
                    if len(score_part) == 2:
                        scoreA, scoreB = int(score_part[1]), int(score_part[0])
                        predicted_match["match2games"] = ([{'winner': '1'}] * scoreA) + ([{'winner': '2'}] * scoreB)
                display_matches.append(predicted_match)
        has_predictions = any(v != "random" for v in forced_outcomes.values())
        st.write("**Current Standings (including predictions)**" if has_predictions else "**Current Standings**")
        standings_df = build_standings_table(teams, display_matches)
        st.dataframe(standings_df, use_container_width=True, hide_index=True)
    with res_col2:
        st.write("**Playoff Probabilities**")
        if not standings_df.empty:
            team_order = standings_df['Team'].tolist()
            sorted_probs_df = sim_results_df.set_index('Team').reindex(team_order).reset_index()
        else:
            sorted_probs_df = sim_results_df
        st.dataframe(sorted_probs_df, use_container_width=True, hide_index=True)

    # --- DISPLAY ANALYSIS ---
    st.markdown("---"); st.subheader(f"🔍 Key Scenario Analysis")
    selected_team_analysis = st.selectbox("Select a team to analyze:", options=all_teams_sorted, key='analyzer_team')
    
    analysis_cols = st.columns(2)
    analysis_cols[0].metric(label="🏆 Best Possible Rank", value=f"#{best_rank}")
    analysis_cols[1].metric(label="💔 Worst Possible Rank", value=f"#{worst_rank}")
    
    if st.button(f"Run Deeper Analysis for {selected_team_analysis}"):
        
        # --- 'Win and In' Analysis ---
        with st.spinner(f"Calculating 'Win and In' scenario..."):
            all_bracket_names_win_in = [b['name'] for b in st.session_state.current_brackets]
            if not all_bracket_names_win_in:
                st.warning("No brackets have been configured to analyze.")
            else:
                team_unplayed_win_in = [m for m in unplayed if selected_team_analysis in get_teams_from_match(m)]
                forced_wins = forced_outcomes.copy()
                for match in team_unplayed_win_in:
                    teamA, teamB = get_teams_from_match(match)
                    match_key = (teamA, teamB, match.get('date'))
                    if teamA == selected_team_analysis: forced_wins[match_key] = "A20"
                    else: forced_wins[match_key] = "B20"

                win_out_data = cached_single_table_sim(
                    tuple(teams), tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), 
                    tuple(unplayed_tuples), tuple(sorted(forced_wins.items())), 
                    tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim)['probs_df']

                st.markdown("---")
                st.write(f"**Results if {selected_team_analysis} Wins All Remaining Matches:**")
                metric_cols = st.columns(len(all_bracket_names_win_in))
                for i, bracket_name in enumerate(all_bracket_names_win_in):
                    target_bracket_col = f"{bracket_name} (%)"
                    win_out_prob = win_out_data.loc[win_out_data['Team'] == selected_team_analysis, target_bracket_col].iloc[0]
                    with metric_cols[i]:
                        st.metric(label=f"Chance for '{bracket_name}'", value=f"{win_out_prob:.2f}%")

        # --- Most Important Match Analysis ---
        with st.spinner(f"Finding most important match..."):
            team_unplayed_importance = [m for m in unplayed if selected_team_analysis in get_teams_from_match(m)]
            all_brackets_importance = sorted([b for b in st.session_state.current_brackets], key=lambda x: x.get('start', 99))
            positive_brackets_importance = [b['name'] for b in all_brackets_importance if "unqualified" not in b['name'].lower() and "relegation" not in b['name'].lower()]

            max_swing = -1.0
            most_important_match_info = None

            for match in team_unplayed_importance:
                teamA, teamB = get_teams_from_match(match)
                opponent = teamB if teamA == selected_team_analysis else teamA
                match_key = (teamA, teamB, match.get('date'))

                forced_win_scenario = forced_outcomes.copy()
                forced_loss_scenario = forced_outcomes.copy()
                if teamA == selected_team_analysis:
                    forced_win_scenario[match_key], forced_loss_scenario[match_key] = "A20", "B20"
                else:
                    forced_win_scenario[match_key], forced_loss_scenario[match_key] = "B20", "A20"
                
                win_df = cached_single_table_sim(tuple(teams), tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), tuple(unplayed_tuples), tuple(sorted(forced_win_scenario.items())), tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim)['probs_df']
                loss_df = cached_single_table_sim(tuple(teams), tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), tuple(unplayed_tuples), tuple(sorted(forced_loss_scenario.items())), tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim)['probs_df']

                win_prob_cumulative, loss_prob_cumulative = 0, 0
                for bracket_name in positive_brackets_importance:
                    col_name = f"{bracket_name} (%)"
                    win_prob_cumulative += win_df.loc[win_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    loss_prob_cumulative += loss_df.loc[loss_df['Team'] == selected_team_analysis, col_name].iloc[0]
                
                swing = abs(win_prob_cumulative - loss_prob_cumulative)

                if swing > max_swing:
                    max_swing = swing
                    most_important_match_info = {"opponent": opponent, "win_df": win_df, "loss_df": loss_df}

            st.markdown("---")
            st.write(f"**Most Important Match**")

            if most_important_match_info:
                opponent = most_important_match_info['opponent']
                win_df = most_important_match_info['win_df']
                loss_df = most_important_match_info['loss_df']

                st.info(f"The game against **{opponent}** is your most critical. Here's how a win vs. a loss changes your fate:")
                
                brackets_to_show = [b['name'] for b in all_brackets_importance]
                result_cols = st.columns(len(brackets_to_show))
                
                for i, bracket_name in enumerate(brackets_to_show):
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
        
        # --- "Who to Root For" Analysis ---
        with st.spinner(f"Finding critical external matches..."):
            external_matches = [m for m in unplayed if selected_team_analysis not in get_teams_from_match(m)]
            
            all_brackets_root_for = sorted([b for b in st.session_state.current_brackets], key=lambda x: x.get('start', 99))
            positive_brackets_root_for = [b['name'] for b in all_brackets_root_for if "unqualified" not in b['name'].lower() and "relegation" not in b['name'].lower()]

            base_cumulative_prob_overall = 0
            for bracket_name in positive_brackets_root_for:
                col_name = f"{bracket_name} (%)"
                base_cumulative_prob_overall += sim_results_df.loc[sim_results_df['Team'] == selected_team_analysis, col_name].iloc[0]

            best_external_impact = 0.01 
            best_external_match_info = None

            for match in external_matches:
                teamA, teamB = get_teams_from_match(match)
                bo = match.get("bestof", 3)
                outcomes = get_series_outcome_options(teamA, teamB, bo)

                for outcome_label, outcome_code in outcomes:
                    if outcome_code == "random": continue

                    forced_scenario = forced_outcomes.copy()
                    match_key = (teamA, teamB, match.get('date'))
                    forced_scenario[match_key] = outcome_code

                    scenario_df = cached_single_table_sim(
                        tuple(teams), tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())),
                        tuple(unplayed_tuples), tuple(sorted(forced_scenario.items())),
                        tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim
                    )['probs_df']

                    scenario_cumulative_prob = 0
                    for bracket_name in positive_brackets_root_for:
                        col_name = f"{bracket_name} (%)"
                        scenario_cumulative_prob += scenario_df.loc[scenario_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    
                    impact = scenario_cumulative_prob - base_cumulative_prob_overall

                    if impact > best_external_impact:
                        best_external_impact = impact
                        best_external_match_info = {"teams": f"{teamA} vs {teamB}", "outcome": outcome_label, "scenario_df": scenario_df}

            st.markdown("---")
            st.write(f"**Who to Root For**")

            if best_external_match_info:
                teams_involved = best_external_match_info['teams']
                outcome = best_external_match_info['outcome']
                scenario_df = best_external_match_info['scenario_df']

                st.info(f"The most helpful external result is **{outcome}** in the {teams_involved} game. Here's how it impacts your chances:")
                
                brackets_to_show = [b['name'] for b in all_brackets_root_for]
                metric_cols = st.columns(len(brackets_to_show))
                
                for i, bracket_name in enumerate(brackets_to_show):
                    col_name = f"{bracket_name} (%)"
                    
                    base_prob = sim_results_df.loc[sim_results_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    scenario_prob = scenario_df.loc[scenario_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    
                    with metric_cols[i]:
                        st.metric(label=f"For '{bracket_name}'", value=f"{scenario_prob:.2f}%", delta=f"{scenario_prob - base_prob:.2f}%")
            else:
                st.info("No single external match significantly helps this team's chances.")

def group_dashboard():
    st.header(f"Simulation for {tournament_name} (Group Stage)")
    st.button("← Change Tournament Format", on_click=lambda: st.session_state.update(page_view='format_selection'))
    
    group_config = st.session_state.group_config
    groups = group_config.get('groups', {})
    all_group_teams = sorted([team for group_teams in groups.values() for team in group_teams])

    # --- Top Control Layout ---
    st.markdown("---"); st.subheader("Simulation Controls")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in simulation_matches if "date" in m))))
        if week_blocks:
            week_options = {f"Week {i+1} ({wk[0]} to {wk[-1]})": i for i, wk in enumerate(week_blocks)}
            week_options["Pre-Season (Week 0)"] = -1
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
                if st.button("Save Brackets", type="primary", key="g_save_brackets"): save_bracket_config(tournament_name, {"brackets": st.session_state.current_brackets}); st.success("Brackets saved!"); st.cache_data.clear()
        with config_tabs[1]:
            with st.expander("Configure Groups", expanded=False):
                editable_groups = st.session_state.group_config.get('groups', {})
                for group_name, group_teams in editable_groups.items():
                    new_teams = st.multiselect(f"Teams in {group_name}", options=all_group_teams, default=group_teams, key=f"edit_group_{group_name}")
                    editable_groups[group_name] = new_teams
                if st.button("Save Group Changes"): st.session_state.group_config['groups'] = editable_groups; save_group_config(tournament_name, st.session_state.group_config); st.success("Group configuration updated!"); st.cache_data.clear(); st.rerun()

    # --- Initialize Session State for Team Selector ---
    if 'analyzer_team_groups' not in st.session_state and all_group_teams:
        st.session_state.analyzer_team_groups = all_group_teams[0]

    # --- Corrected Data Preparation Logic ---
    played = []
    unplayed = []
    cutoff_date = week_blocks[cutoff_week_idx][-1] if cutoff_week_idx != -1 and week_blocks else None
    
    for m in simulation_matches:
        match_date = pd.to_datetime(m.get("date")).date() if m.get("date") else None
        
        # Determine if the match is considered "played" based on the new rules
        is_played = False
        num_games_played = len(m.get("match2games", []))
        
        # Rule 1: It has a definitive winner (for Bo1, Bo3, Bo5).
        has_winner = m.get("winner") in ("1", "2")
        # Rule 2 (Your suggestion): It's a Bo2 and 2 games have been played.
        is_bo2_complete = str(m.get("bestof")) == "2" and num_games_played == 2
    
        if has_winner or is_bo2_complete:
            if cutoff_date and match_date and match_date <= cutoff_date:
                is_played = True
            elif not cutoff_date: # If no cutoff, any completed match is "played"
                is_played = True
    
        if is_played:
            played.append(m)
        else:
            unplayed.append(m)

    # --- Upcoming Matches (What-If Scenarios) UI ---
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

    # --- Data prep for simulation ---
    current_wins, current_diff = defaultdict(int), defaultdict(int)
    for m in played:
        teamA, teamB = get_teams_from_match(m)
        winner_idx = int(m["winner"]) - 1
        winner, loser = (teamA, teamB) if winner_idx == 0 else (teamB, teamA)
        current_wins[winner] += 1
        s_w, s_l = 0,0
        for game in m.get("match2games", []):
            if str(game.get('winner')) == str(winner_idx + 1): s_w += 1
            elif game.get('winner') is not None: s_l += 1
        current_diff[winner] += s_w - s_l; current_diff[loser] += s_l - s_w
    unplayed_tuples = []
    for m in unplayed:
        teamA, teamB = get_teams_from_match(m)
        unplayed_tuples.append((teamA, teamB, m.get("date"), m.get("bestof", 3)))

    # --- A SINGLE, UNIFIED SIMULATION CALL for base results ---
    with st.spinner(f"Running simulation and analysis for {st.session_state.analyzer_team_groups}..."):
        sim_results_data = cached_group_sim(
            groups, tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())),
            tuple(unplayed_tuples), tuple(sorted(forced_outcomes.items())),
            tuple(frozenset(b.items()) for b in st.session_state.current_brackets),
            n_sim, team_to_track=st.session_state.analyzer_team_groups
        )
    
    sim_results_df = sim_results_data['probs_df']
    best_rank = sim_results_data.get('best_rank')
    worst_rank = sim_results_data.get('worst_rank')
    
    # --- DISPLAY RESULTS ---
    st.markdown("---"); st.subheader("Results")
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

    # --- DISPLAY ANALYSIS ---
    st.markdown("---"); st.subheader(f"🔍 Key Scenario Analysis")
    selected_team_analysis = st.selectbox(
        "Select a team to analyze:", 
        options=all_group_teams, 
        key='analyzer_team_groups'
    )
    
    analysis_cols = st.columns(2)
    analysis_cols[0].metric(label="🏆 Best Possible Rank (in Group)", value=f"#{best_rank}")
    analysis_cols[1].metric(label="💔 Worst Possible Rank (in Group)", value=f"#{worst_rank}")
    
    if st.button(f"Run Deeper Analysis for {selected_team_analysis}"):
        
        # --- 'Win and In' Analysis ---
        with st.spinner(f"Calculating 'Win and In' scenario..."):
            all_bracket_names_win_in = [b['name'] for b in st.session_state.current_brackets]
            if not all_bracket_names_win_in:
                st.warning("No brackets have been configured to analyze.")
            else:
                team_unplayed_win_in = [m for m in unplayed if selected_team_analysis in get_teams_from_match(m)]
                forced_wins = forced_outcomes.copy()
                for match in team_unplayed_win_in:
                    teamA, teamB = get_teams_from_match(match)
                    match_key = (teamA, teamB, match.get('date'))
                    if teamA == selected_team_analysis: forced_wins[match_key] = "A20"
                    else: forced_wins[match_key] = "B20"

                win_out_data = cached_group_sim(
                    groups, tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())),
                    tuple(unplayed_tuples), tuple(sorted(forced_wins.items())),
                    tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim)['probs_df']

                st.markdown("---")
                st.write(f"**Results if {selected_team_analysis} Wins All Remaining Matches:**")
                metric_cols = st.columns(len(all_bracket_names_win_in))
                for i, bracket_name in enumerate(all_bracket_names_win_in):
                    target_bracket_col = f"{bracket_name} (%)"
                    win_out_prob = win_out_data.loc[win_out_data['Team'] == selected_team_analysis, target_bracket_col].iloc[0]
                    with metric_cols[i]:
                        st.metric(label=f"Chance for '{bracket_name}'", value=f"{win_out_prob:.2f}%")

        # --- Most Important Match Analysis ---
        with st.spinner(f"Finding most important match..."):
            team_unplayed_importance = [m for m in unplayed if selected_team_analysis in get_teams_from_match(m)]
            all_brackets_importance = sorted([b for b in st.session_state.current_brackets], key=lambda x: x.get('start', 99))
            positive_brackets_importance = [b['name'] for b in all_brackets_importance if "unqualified" not in b['name'].lower() and "relegation" not in b['name'].lower()]
            max_swing = -1.0
            most_important_match_info = None

            for match in team_unplayed_importance:
                teamA, teamB = get_teams_from_match(match)
                opponent = teamB if teamA == selected_team_analysis else teamA
                match_key = (teamA, teamB, match.get('date'))
                forced_win_scenario, forced_loss_scenario = forced_outcomes.copy(), forced_outcomes.copy()
                if teamA == selected_team_analysis:
                    forced_win_scenario[match_key], forced_loss_scenario[match_key] = "A20", "B20"
                else:
                    forced_win_scenario[match_key], forced_loss_scenario[match_key] = "B20", "A20"
                win_df = cached_group_sim(groups, tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), tuple(unplayed_tuples), tuple(sorted(forced_win_scenario.items())), tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim)['probs_df']
                loss_df = cached_group_sim(groups, tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), tuple(unplayed_tuples), tuple(sorted(forced_loss_scenario.items())), tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim)['probs_df']
                win_prob_cumulative, loss_prob_cumulative = 0, 0
                for bracket_name in positive_brackets_importance:
                    col_name = f"{bracket_name} (%)"
                    win_prob_cumulative += win_df.loc[win_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    loss_prob_cumulative += loss_df.loc[loss_df['Team'] == selected_team_analysis, col_name].iloc[0]
                swing = abs(win_prob_cumulative - loss_prob_cumulative)
                if swing > max_swing:
                    max_swing = swing
                    most_important_match_info = {"opponent": opponent, "win_df": win_df, "loss_df": loss_df}

            st.markdown("---")
            st.write(f"**Most Important Match**")
            if most_important_match_info:
                opponent, win_df, loss_df = most_important_match_info['opponent'], most_important_match_info['win_df'], most_important_match_info['loss_df']
                st.info(f"The game against **{opponent}** is your most critical. Here's how a win vs. a loss changes your fate:")
                brackets_to_show = [b['name'] for b in all_brackets_importance]
                result_cols = st.columns(len(brackets_to_show))
                for i, bracket_name in enumerate(brackets_to_show):
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
        
        # --- "Who to Root For" Analysis ---
        with st.spinner(f"Finding critical external matches..."):
            external_matches = [m for m in unplayed if selected_team_analysis not in get_teams_from_match(m)]
            all_brackets_root_for = sorted([b for b in st.session_state.current_brackets], key=lambda x: x.get('start', 99))
            positive_brackets_root_for = [b['name'] for b in all_brackets_root_for if "unqualified" not in b['name'].lower() and "relegation" not in b['name'].lower()]
            narrative_target_brackets, narrative_target_name = [], "overall playoff"
            base_cumulative_prob_overall = sum(sim_results_df.loc[sim_results_df['Team'] == selected_team_analysis, f"{b} (%)"].iloc[0] for b in positive_brackets_root_for)
            best_external_impact, best_external_match_info = 0.01, None

            for match in external_matches:
                teamA, teamB = get_teams_from_match(match)
                bo, outcomes = match.get("bestof", 3), get_series_outcome_options(teamA, teamB, bo)
                for outcome_label, outcome_code in outcomes:
                    if outcome_code == "random": continue
                    forced_scenario = forced_outcomes.copy()
                    forced_scenario[(teamA, teamB, match.get('date'))] = outcome_code
                    scenario_df = cached_group_sim(groups, tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), tuple(unplayed_tuples), tuple(sorted(forced_scenario.items())), tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim)['probs_df']
                    scenario_cumulative_prob = sum(scenario_df.loc[scenario_df['Team'] == selected_team_analysis, f"{b} (%)"].iloc[0] for b in positive_brackets_root_for)
                    impact = scenario_cumulative_prob - base_cumulative_prob_overall
                    if impact > best_external_impact:
                        best_external_impact = impact
                        best_external_match_info = {"teams": f"{teamA} vs {teamB}", "outcome": outcome_label, "scenario_df": scenario_df}

            st.markdown("---")
            st.write(f"**Who to Root For**")
            if best_external_match_info:
                teams_involved, outcome, scenario_df = best_external_match_info['teams'], best_external_match_info['outcome'], best_external_match_info['scenario_df']
                st.info(f"The most helpful external result is **{outcome}** in the {teams_involved} game. Here's how it impacts your chances:")
                brackets_to_show = [b['name'] for b in all_brackets_root_for]
                metric_cols = st.columns(len(brackets_to_show))
                for i, bracket_name in enumerate(brackets_to_show):
                    col_name = f"{bracket_name} (%)"
                    base_prob = sim_results_df.loc[sim_results_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    scenario_prob = scenario_df.loc[scenario_df['Team'] == selected_team_analysis, col_name].iloc[0]
                    with metric_cols[i]:
                        st.metric(label=f"For '{bracket_name}'", value=f"{scenario_prob:.2f}%", delta=f"{scenario_prob - base_prob:.2f}%")
            else:
                st.info("No single external match significantly helps this team's chances.")

# --- Page Router ---

# This logic now correctly handles new and existing tournament configurations.

# Only check for saved formats when the page loads or the tournament selection changes.
if 'active_tournament' not in st.session_state or st.session_state.active_tournament != tournament_name:
    st.session_state.active_tournament = tournament_name
    saved_format = load_tournament_format(tournament_name)

    # THE CORE FIX: If no format is saved, ALWAYS default to the selection page.
    if not saved_format:
        st.session_state.page_view = 'format_selection'
    # If a format IS saved, determine the correct view.
    elif saved_format == 'single_table':
        st.session_state.page_view = 'single_table_sim'
    elif saved_format == 'group':
        saved_group_config = load_group_config(tournament_name)
        # Check if groups have been configured. If not, go to the setup page.
        if saved_group_config and saved_group_config.get('groups'):
            st.session_state.group_config = saved_group_config
            st.session_state.page_view = 'group_sim'
        else:
            st.session_state.page_view = 'group_setup'

# This section renders the UI based on the page_view state determined above.
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
            # For a new setup, immediately go to the group configuration screen.
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
