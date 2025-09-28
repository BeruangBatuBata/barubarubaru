import streamlit as st
import pandas as pd
from collections import defaultdict
import random
from utils.simulation import (
    get_series_outcome_options, build_standings_table, run_monte_carlo_simulation,
    load_bracket_config, save_bracket_config, build_week_blocks,
    load_group_config, save_group_config, run_monte_carlo_simulation_groups,
    load_tournament_format, save_tournament_format
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
def cached_single_table_sim(teams, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim):
    return run_monte_carlo_simulation(list(teams), dict(current_wins), dict(current_diff), list(unplayed_matches), dict(forced_outcomes), [dict(b) for b in brackets], n_sim)

@st.cache_data(show_spinner="Running group stage simulation...")
def cached_group_sim(groups, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim):
    return run_monte_carlo_simulation_groups(groups, dict(current_wins), dict(current_diff), list(unplayed_matches), dict(forced_outcomes), [dict(b) for b in brackets], n_sim)

# --- UI Functions ---
def get_teams_from_match(match):
    opps = match.get("match2opponents", [])
    teamA = opps[0].get('name', 'Team A') if len(opps) > 0 else 'Team A'
    teamB = opps[1].get('name', 'Team B') if len(opps) > 1 else 'Team B'
    return teamA, teamB

def group_setup_ui():
    st.header(f"Group Configuration for {tournament_name}"); st.write("Assign the teams into their respective groups.")
    if 'group_config' not in st.session_state or not isinstance(st.session_state.group_config, dict):
        st.session_state.group_config = {'groups': {'Group A': [], 'Group B': []}}
    num_groups = st.number_input("Number of Groups", 1, 8, len(st.session_state.group_config.get('groups', {})))
    current_groups = st.session_state.group_config.get('groups', {})
    if len(current_groups) != num_groups:
        new_groups = {}; sorted_keys = sorted(current_groups.keys())
        for i in range(num_groups):
            group_name = sorted_keys[i] if i < len(sorted_keys) else f"Group {chr(65+i)}"; new_groups[group_name] = current_groups.get(group_name, [])
        st.session_state.group_config['groups'] = new_groups; st.rerun()
    st.markdown("---")
    assigned_teams = {team for group in current_groups.values() for team in group}
    unassigned_teams = [team for team in teams if team not in assigned_teams]
    if unassigned_teams: st.warning(f"Unassigned Teams: {', '.join(unassigned_teams)}")
    cols = st.columns(num_groups)
    for i, (group_name, group_teams) in enumerate(current_groups.items()):
        with cols[i]:
            st.subheader(group_name); new_teams = st.multiselect(f"Teams in {group_name}", teams, default=group_teams, key=f"group_{group_name}")
            current_groups[group_name] = new_teams
    if st.button("Save & Continue", type="primary"):
        save_group_config(tournament_name, st.session_state.group_config); st.success("Group configuration saved!")
        st.session_state.page_view = 'group_sim'; st.rerun()

def single_table_dashboard():
    st.header(f"Simulation for {tournament_name} (Single Table)")
    st.button("← Change Tournament Format", on_click=lambda: st.session_state.update(page_view='format_selection'))
    
    week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in simulation_matches if "date" in m))))
    st.markdown("---"); st.subheader("Simulation Controls")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
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
    
    if 'current_brackets' not in st.session_state or st.session_state.get('bracket_tournament') != tournament_name:
        st.session_state.current_brackets = load_bracket_config(tournament_name)['brackets']
        st.session_state.bracket_tournament = tournament_name
    
    with col3:
        with st.expander("Configure Brackets"):
            editable_brackets = [b.copy() for b in st.session_state.current_brackets]
            for i, bracket in enumerate(editable_brackets):
                st.markdown(f"**Bracket {i+1}**"); cols = st.columns([4, 2, 2, 1])
                bracket['name'] = cols[0].text_input("Name", value=bracket.get('name', ''), key=f"s_name_{i}", label_visibility="collapsed")
                bracket['start'] = cols[1].number_input("Start", value=bracket.get('start', 1), min_value=1, key=f"s_start_{i}", label_visibility="collapsed")
                bracket['end'] = cols[2].number_input("End", value=bracket.get('end') or len(teams), min_value=bracket.get('start', 1), key=f"s_end_{i}", label_visibility="collapsed")
                if cols[3].button("🗑️", key=f"s_del_{i}"): st.session_state.current_brackets.pop(i); st.rerun()
            st.session_state.current_brackets = editable_brackets
            if st.button("Add Bracket", key="s_add_bracket"): st.session_state.current_brackets.append({"name": "New Bracket", "start": 1, "end": len(teams)}); st.rerun()
            if st.button("Save Brackets", type="primary", key="s_save_brackets"): save_bracket_config(tournament_name, {"brackets": st.session_state.current_brackets}); st.success("Brackets saved!"); st.cache_data.clear()
                
    cutoff_dates = set(pd.to_datetime(m.get("date")).date() for m in simulation_matches if m.get("date"))
    if week_blocks and cutoff_week_idx >= 0:
        cutoff_dates = set(d for i in range(cutoff_week_idx + 1) for d in week_blocks[i])

    played = [m for m in simulation_matches if m.get("winner") in ("1", "2") and m.get("date") and pd.to_datetime(m.get("date")).date() in cutoff_dates]
    unplayed = [m for m in simulation_matches if m not in played]

    st.markdown("---"); st.subheader("Upcoming Matches (What-If Scenarios)")
    forced_outcomes = {}
    
    matches_by_week = defaultdict(list)
    for match in unplayed:
        if "date" not in match: continue
        for week_idx, week_dates in enumerate(week_blocks):
            if pd.to_datetime(match['date']).date() in week_dates: matches_by_week[week_idx].append(match); break

    if not unplayed:
        st.info("No matches left to simulate.")
    elif not matches_by_week:
        st.info("No upcoming matches to display for the selected cutoff week.")
    else:
        for week_idx in sorted(matches_by_week.keys()):
            week_label = f"Week {week_idx + 1}: {week_blocks[week_idx][0]} — {week_blocks[week_idx][-1]}"
            with st.expander(f"📅 {week_label}", expanded=False):
                matches_by_date = defaultdict(list)
                for m in matches_by_week[week_idx]: matches_by_date[m['date']].append(m)
                for date in sorted(matches_by_date.keys()):
                    st.markdown(f"#### 📅 {date}")
                    date_matches = matches_by_date[date]
                    for idx in range(0, len(date_matches), 3):
                        cols = st.columns(3)
                        for col_idx, col in enumerate(cols):
                            if idx + col_idx < len(date_matches):
                                m = date_matches[idx + col_idx]
                                teamA, teamB = get_teams_from_match(m); bo = m.get("bestof", 3)
                                match_key = (teamA, teamB, date)
                                with col, st.container():
                                    st.markdown(f"<div style='text-align: center; font-weight: bold; padding: 10px; background-color: #262730; border-radius: 10px; margin-bottom: 10px;'>{teamA} vs {teamB}</div>", unsafe_allow_html=True)
                                    options = get_series_outcome_options(teamA, teamB, bo)
                                    selected = st.radio("",[opt[0] for opt in options], key=f"s_radio_{date}_{teamA}_{teamB}", label_visibility="collapsed", horizontal=False)
                                    for opt_label, opt_code in options:
                                        if opt_label == selected: forced_outcomes[match_key] = opt_code; break
                    st.markdown("---")

    ### LOGIC HIGHLIGHT ###
    # This is the section that processes the results of completed matches.
    # It initializes empty counters for wins and score differences.
    current_wins, current_diff = defaultdict(int), defaultdict(int)

    # It then loops through only the 'played' matches.
    for m in played:
        # It gets the team names and determines the winner and loser.
        teamA, teamB = get_teams_from_match(m)
        winner_idx = int(m["winner"]) - 1
        winner, loser = (teamA, teamB) if winner_idx == 0 else (teamB, teamA)

        # It adds 1 to the winner's match win count.
        current_wins[winner] += 1
        
        # It calculates the game score differential (e.g., 2-1 = +1) and updates both teams.
        score_winner = 0
        score_loser = 0
        for game in m.get("match2games", []):
            # If the overall winner is team 1 (winner_idx=0), then a game winner '1' adds to their score.
            # If the overall winner is team 2 (winner_idx=1), then a game winner '2' adds to their score.
            if str(game.get('winner')) == str(winner_idx + 1):
                score_winner += 1
            else:
                score_loser += 1
        
        current_diff[winner] += score_winner - score_loser
        current_diff[loser] += score_loser - score_winner

    unplayed_tuples = []
    for m in unplayed:
        teamA, teamB = get_teams_from_match(m)
        unplayed_tuples.append((teamA, teamB, m.get("date"), m.get("bestof", 3)))

    sim_results = cached_single_table_sim(tuple(teams), tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), tuple(unplayed_tuples), tuple(sorted(forced_outcomes.items())), tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim)
    
    st.markdown("---"); st.subheader("Results")
    col1, col2 = st.columns(2)
    with col1:
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
        
        has_predictions = any(forced_outcomes.get((get_teams_from_match(m)[0], get_teams_from_match(m)[1], m.get("date")), "random") != "random" for m in unplayed)
        st.write("**Current Standings (including predictions)**" if has_predictions else "**Current Standings**")
        standings_df = build_standings_table(teams, display_matches)
        st.dataframe(standings_df, use_container_width=True)
    with col2:
        st.write("**Playoff Probabilities**")
        if sim_results is not None and not sim_results.empty:
            if 'Team' in standings_df.columns and not standings_df.empty and len(standings_df['Team']) > 0:
                sim_teams = sim_results.set_index('Team')
                standings_teams = standings_df['Team']
                teams_to_show = [t for t in standings_teams if t in sim_teams.index]
                if teams_to_show:
                    st.dataframe(sim_teams.loc[teams_to_show].reset_index(), use_container_width=True, hide_index=True)
                else:
                    st.dataframe(sim_results, use_container_width=True, hide_index=True)
            else:
                st.dataframe(sim_results, use_container_width=True, hide_index=True)

def group_dashboard():
    st.header(f"Simulation for {tournament_name} (Group Stage)")
    st.button("← Change Tournament Format", on_click=lambda: st.session_state.update(page_view='format_selection'))
    
    group_config = st.session_state.group_config; groups = group_config.get('groups', {})
    week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in simulation_matches if "date" in m))))
    st.markdown("---"); st.subheader("Simulation Controls")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if week_blocks:
            week_options = {f"Week {i+1} ({wk[0]} to {wk[-1]})": i for i, wk in enumerate(week_blocks)}
            cutoff_week_label = st.select_slider("Select Cutoff Week:", options=list(week_options.keys()), value=list(week_options.keys())[-1])
            cutoff_week_idx = week_options[cutoff_week_label]
        else:
            cutoff_week_idx = -1
            st.warning("No date information available to create weekly filters.")

    with col2:
        n_sim = st.number_input("Number of Simulations:", 1000, 100000, 10000, 1000, key="group_sim_count")
    
    if 'current_brackets' not in st.session_state or st.session_state.get('bracket_tournament') != tournament_name:
        st.session_state.current_brackets = load_bracket_config(tournament_name)['brackets']; st.session_state.bracket_tournament = tournament_name
    
    with col3:
        config_tabs = st.tabs(["Brackets", "Groups"])
        with config_tabs[0]:
            with st.expander("Configure Brackets", expanded=False):
                editable_brackets = [b.copy() for b in st.session_state.current_brackets]
                for i, bracket in enumerate(editable_brackets):
                    st.markdown(f"**Bracket {i+1}**"); cols = st.columns([4, 2, 2, 1])
                    bracket['name'] = cols[0].text_input("Name", bracket.get('name', ''), key=f"g_name_{i}", label_visibility="collapsed")
                    bracket['start'] = cols[1].number_input("Start", value=bracket.get('start', 1), min_value=1, key=f"g_start_{i}", label_visibility="collapsed")
                    bracket['end'] = cols[2].number_input("End", value=bracket.get('end') or len(teams), min_value=bracket.get('start', 1), key=f"g_end_{i}", label_visibility="collapsed")
                    if cols[3].button("🗑️", key=f"g_del_{i}"): st.session_state.current_brackets.pop(i); st.rerun()
                st.session_state.current_brackets = editable_brackets
                if st.button("Add Bracket", key="g_add_bracket"): st.session_state.current_brackets.append({"name": "New Bracket", "start": 1, "end": len(teams)}); st.rerun()
                if st.button("Save Brackets", type="primary", key="g_save_brackets"): save_bracket_config(tournament_name, {"brackets": st.session_state.current_brackets}); st.success("Brackets saved!"); st.cache_data.clear()
        
        with config_tabs[1]:
            with st.expander("Configure Groups", expanded=False):
                st.write("Edit team assignments for each group.")
                editable_groups = st.session_state.group_config.get('groups', {})
                for group_name, group_teams in editable_groups.items():
                    new_teams = st.multiselect(f"Teams in {group_name}", options=teams, default=group_teams, key=f"edit_group_{group_name}")
                    editable_groups[group_name] = new_teams
                if st.button("Save Group Changes"): st.session_state.group_config['groups'] = editable_groups; save_group_config(tournament_name, st.session_state.group_config); st.success("Group configuration updated!"); st.cache_data.clear(); st.rerun()

    cutoff_dates = set(d for i in range(cutoff_week_idx + 1) for d in week_blocks[i]) if cutoff_week_idx >= 0 and week_blocks else set()
    played = [m for m in simulation_matches if m.get("date") and pd.to_datetime(m.get("date")).date() in cutoff_dates and m.get("winner") in ("1", "2")]
    unplayed = [m for m in simulation_matches if m not in played]
    
    st.markdown("---"); st.subheader("Upcoming Matches (What-If Scenarios)")
    forced_outcomes = {}
    
    if not unplayed: st.info("No matches left to simulate.")
    else:
        matches_by_week = defaultdict(list)
        for match in unplayed:
            if "date" not in match: continue
            for week_idx, week_dates in enumerate(week_blocks):
                if pd.to_datetime(match['date']).date() in week_dates: matches_by_week[week_idx].append(match); break
        for week_idx in sorted(matches_by_week.keys()):
            week_label = f"Week {week_idx + 1}: {week_blocks[week_idx][0]} — {week_blocks[week_idx][-1]}"
            with st.expander(f"📅 {week_label}", expanded=False):
                matches_by_date = defaultdict(list)
                for m in matches_by_week[week_idx]: matches_by_date[m['date']].append(m)
                for date in sorted(matches_by_date.keys()):
                    st.markdown(f"#### 📅 {date}")
                    date_matches = matches_by_date[date]
                    for idx in range(0, len(date_matches), 3):
                        cols = st.columns(3)
                        for col_idx, col in enumerate(cols):
                            if idx + col_idx < len(date_matches):
                                m = date_matches[idx + col_idx]
                                teamA, teamB = get_teams_from_match(m); bo = m.get("bestof", 3)
                                match_key = (teamA, teamB, date)
                                with col, st.container():
                                    st.markdown(f"<div style='text-align: center; font-weight: bold; padding: 10px; background-color: #262730; border-radius: 10px; margin-bottom: 10px;'>{teamA} vs {teamB}</div>", unsafe_allow_html=True)
                                    options = get_series_outcome_options(teamA, teamB, bo)
                                    selected = st.radio("", [opt[0] for opt in options], key=f"g_radio_{date}_{teamA}_{teamB}", label_visibility="collapsed", horizontal=False)
                                    for opt_label, opt_code in options:
                                        if opt_label == selected: forced_outcomes[match_key] = opt_code; break
                    st.markdown("---")
    
    current_wins, current_diff = defaultdict(int), defaultdict(int)
    for m in played:
        teamA, teamB = get_teams_from_match(m)
        winner_idx = int(m["winner"]) - 1
        winner, loser = (teamA, teamB) if winner_idx == 0 else (teamB, teamA)
        current_wins[winner] += 1
        s_w, s_l = (m.get("scoreA",0), m.get("scoreB",0)) if winner_idx == 0 else (m.get("scoreB",0), m.get("scoreA",0))
        current_diff[winner] += s_w - s_l; current_diff[loser] += s_l - s_w

    unplayed_tuples = []
    for m in unplayed:
        teamA, teamB = get_teams_from_match(m)
        unplayed_tuples.append((teamA, teamB, m.get("date"), m.get("bestof", 3)))

    sim_results = cached_group_sim(groups, tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), tuple(unplayed_tuples), tuple(sorted(forced_outcomes.items())), tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim)
    
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
    
    has_predictions = any(forced_outcomes.get((get_teams_from_match(m)[0], get_teams_from_match(m)[1], m.get("date")), "random") != "random" for m in unplayed)
    standings_label = "**Current Standings (including predictions)**" if has_predictions else "**Current Standings**"
    
    st.markdown("---"); st.subheader("Results")
    result_tabs = st.tabs(["Overall"] + sorted(groups.keys()))
    with result_tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Current Standings by Group**" if not has_predictions else "**Current Standings by Group (including predictions)**")
            for group_name in sorted(groups.keys()):
                st.write(f"**{group_name}**"); standings_df = build_standings_table(groups[group_name], display_matches)
                st.dataframe(standings_df, use_container_width=True)
        with col2:
            st.write("**Playoff Probabilities by Group**")
            if sim_results is not None and not sim_results.empty:
                for group_name in sorted(groups.keys()):
                    st.write(f"**{group_name}**"); group_probs = sim_results[sim_results['Group'] == group_name].drop(columns=['Group'])
                    st.dataframe(group_probs, use_container_width=True, hide_index=True)

    for i, group_name in enumerate(sorted(groups.keys())):
        with result_tabs[i+1]:
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"{standings_label} ({group_name})"); standings_df = build_standings_table(groups[group_name], display_matches)
                st.dataframe(standings_df, use_container_width=True)
            with col2:
                st.write(f"**Playoff Probabilities ({group_name})**")
                if sim_results is not None and not sim_results.empty:
                    group_probs = sim_results[sim_results['Group'] == group_name].drop(columns=['Group'])
                    st.dataframe(group_probs, use_container_width=True, hide_index=True)

# --- Page Router ---
if 'page_view' not in st.session_state or st.session_state.get('active_tournament') != tournament_name:
    st.session_state.active_tournament = tournament_name
    saved_format = load_tournament_format(tournament_name)
    if saved_format == 'single_table': st.session_state.page_view = 'single_table_sim'
    elif saved_format == 'group':
        st.session_state.page_view = 'group_sim'
        saved_group_config = load_group_config(tournament_name)
        if saved_group_config: st.session_state.group_config = saved_group_config
    else:
        st.session_state.page_view = 'format_selection'

if st.session_state.page_view == 'format_selection':
    st.title("🏆 Playoff Odds: Tournament Format")
    st.write(f"How is **{tournament_name}** structured?")
    col1, col2 = st.columns(2)
    if col1.button("Single Table League", use_container_width=True):
        save_tournament_format(tournament_name, 'single_table'); st.session_state.page_view = 'single_table_sim'; st.rerun()
    if col2.button("Group Stage", use_container_width=True):
        save_tournament_format(tournament_name, 'group')
        saved_config = load_group_config(tournament_name)
        if saved_config: st.session_state.group_config = saved_config; st.session_state.page_view = 'group_sim'
        else: st.session_state.page_view = 'group_setup'
        st.rerun()

elif st.session_state.page_view == 'group_setup':
    group_setup_ui()
    if st.button("← Back to Format Selection"):
        st.session_state.page_view = 'format_selection'; st.rerun()
elif st.session_state.page_view == 'single_table_sim':
    single_table_dashboard()
elif st.session_state.page_view == 'group_sim':
    group_dashboard()
