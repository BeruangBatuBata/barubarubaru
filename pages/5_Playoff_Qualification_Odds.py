import streamlit as st
import pandas as pd
from collections import defaultdict
from datetime import datetime # MODIFICATION: Import datetime
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
parsed_matches_full = st.session_state['parsed_matches']
selected_stage = "All Stages"
matches_to_analyze = []

# Conditional Stage Filter
if len(st.session_state.get('selected_tournaments', [])) == 1:
    tournament_name = st.session_state.selected_tournaments[0]
    unique_stages = sorted(
        list(set(m['stage_type'] for m in parsed_matches_full if 'stage_type' in m)),
        key=lambda s: min(m['stage_priority'] for m in parsed_matches_full if m['stage_type'] == s)
    )
    
    if unique_stages:
        st.header("Stage Selection")
        selected_stage = st.selectbox(
            "Select which stage to simulate:",
            unique_stages,
            help="Select the specific league stage for the simulation."
        )
        matches_to_analyze = [m for m in parsed_matches_full if m.get('stage_type') == selected_stage]
    else:
        st.warning("No distinct stages found in the data for this tournament.")
        st.stop()
else:
    tournament_name = "Multiple Tournaments"
    st.warning("Playoff simulation is only available when a single tournament is selected.")
    st.stop()

if not matches_to_analyze:
    st.warning(f"No matches found for the selected stage: '{selected_stage}'.")
    st.stop()

# --- MODIFICATION START: Convert date strings to datetime objects ---
structured_matches = []
for m in matches_to_analyze:
    if len(m.get("match2opponents", [])) >= 2:
        teamA_data = m["match2opponents"][0]
        teamB_data = m["match2opponents"][1]
        
        # Safely parse the date string
        match_date = None
        date_str = m.get('date')
        if date_str:
            try:
                # Assuming date format is YYYY-MM-DD
                match_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                # If parsing fails, leave it as None. The app will handle it.
                pass

        structured_matches.append({
            "teamA": teamA_data.get('name', '').strip(),
            "teamB": teamB_data.get('name', '').strip(),
            "scoreA": int(teamA_data.get('score', 0)),
            "scoreB": int(teamB_data.get('score', 0)),
            "winner": m.get('winner'),
            "date": match_date, # Now a datetime object or None
            "bestof": m.get('bestof', 3)
        })
# --- MODIFICATION END ---


teams = sorted(list(set(m["teamA"] for m in structured_matches) | set(m["teamB"] for m in structured_matches)))
if not teams:
    st.error("Could not determine teams for the selected stage.")
    st.stop()

# --- Cached Simulation Functions ---
@st.cache_data(show_spinner="Running single-table simulation...")
def cached_single_table_sim(teams, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim):
    return run_monte_carlo_simulation(list(teams), dict(current_wins), dict(current_diff), list(unplayed_matches), dict(forced_outcomes), [dict(b) for b in brackets], n_sim)

@st.cache_data(show_spinner="Running group stage simulation...")
def cached_group_sim(groups, current_wins, current_diff, unplayed_matches, forced_outcomes, brackets, n_sim):
    return run_monte_carlo_simulation_groups(groups, dict(current_wins), dict(current_diff), list(unplayed_matches), dict(forced_outcomes), [dict(b) for b in brackets], n_sim)

# --- UI Functions ---
def group_setup_ui():
    st.header(f"Group Configuration for {tournament_name} - {selected_stage}")
    st.write("Assign the teams into their respective groups.")
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
        save_group_config(f"{tournament_name}_{selected_stage}", st.session_state.group_config); st.success("Group configuration saved!")
        st.session_state.page_view = 'group_sim'; st.rerun()

def single_table_dashboard():
    st.header(f"Simulation for {tournament_name} ({selected_stage})")
    st.button("← Change Tournament Format", on_click=lambda: st.session_state.update(page_view='format_selection'))
    week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in structured_matches if m.get("date")))))
    st.markdown("---"); st.subheader("Simulation Controls")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        week_options = {f"Week {i+1} ({wk[0]} to {wk[-1]})": i for i, wk in enumerate(week_blocks)}
        week_options["Pre-Season (Week 0)"] = -1
        sorted_week_options = sorted(week_options.items(), key=lambda item: item[1])
        cutoff_week_label = st.select_slider("Select Cutoff Week:", options=[opt[0] for opt in sorted_week_options], value=sorted_week_options[-1][0] if sorted_week_options else "Pre-Season (Week 0)")
        cutoff_week_idx = week_options.get(cutoff_week_label, -1)
    with col2:
        n_sim = st.number_input("Number of Simulations:", 1000, 100000, 10000, 1000, key="single_sim_count")
    bracket_config_key = f"{tournament_name}_{selected_stage}"
    if 'current_brackets' not in st.session_state or st.session_state.get('bracket_tournament') != bracket_config_key:
        st.session_state.current_brackets = load_bracket_config(bracket_config_key)['brackets']
        st.session_state.bracket_tournament = bracket_config_key
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
            if st.button("Save Brackets", type="primary", key="s_save_brackets"):
                save_bracket_config(bracket_config_key, {"brackets": st.session_state.current_brackets}); st.success("Brackets saved!"); st.cache_data.clear()
    cutoff_dates = set(d for i in range(cutoff_week_idx + 1) for d in week_blocks[i]) if cutoff_week_idx >= 0 and week_blocks else set()
    played = [m for m in structured_matches if m.get("date") in cutoff_dates and m.get("winner") in ("1", "2")]
    unplayed = [m for m in structured_matches if m not in played]
    st.markdown("---"); st.subheader("Upcoming Matches (What-If Scenarios)"); forced_outcomes = {}
    matches_by_week = defaultdict(list)
    for match in unplayed:
        if match.get("date"):
            for week_idx, week_dates in enumerate(week_blocks):
                if match['date'] in week_dates: matches_by_week[week_idx].append(match); break
    if not matches_by_week: st.info("No upcoming matches to simulate for the selected cutoff week.")
    else:
        for week_idx in sorted(matches_by_week.keys()):
            week_label = f"Week {week_idx + 1}: {week_blocks[week_idx][0]} — {week_blocks[week_idx][-1]}"
            with st.expander(f"📅 {week_label}", expanded=False):
                matches_by_date = defaultdict(list); [matches_by_date[m['date']].append(m) for m in matches_by_week[week_idx]]
                for date in sorted(matches_by_date.keys()):
                    st.markdown(f"#### 📅 {date}"); date_matches = matches_by_date[date]
                    for idx in range(0, len(date_matches), 3):
                        cols = st.columns(3)
                        for col_idx, col in enumerate(cols):
                            if idx + col_idx < len(date_matches):
                                m = date_matches[idx + col_idx]; teamA, teamB, bo = m["teamA"], m["teamB"], m["bestof"]; match_key = (teamA, teamB, date)
                                with col, st.container():
                                    st.markdown(f"<div style='text-align: center; font-weight: bold; padding: 10px; background-color: #262730; border-radius: 10px; margin-bottom: 10px;'>{teamA} vs {teamB}</div>", unsafe_allow_html=True)
                                    options = get_series_outcome_options(teamA, teamB, bo)
                                    selected = st.radio("",[opt[0] for opt in options], key=f"s_radio_{date}_{teamA}_{teamB}", label_visibility="collapsed")
                                    for opt_label, opt_code in options:
                                        if opt_label == selected: forced_outcomes[match_key] = opt_code; break
                    st.markdown("---")
    current_wins, current_diff = defaultdict(int), defaultdict(int)
    for m in played:
        winner_idx = int(m["winner"]) - 1; teams_in_match = [m["teamA"], m["teamB"]]; winner, loser = teams_in_match[winner_idx], teams_in_match[1-winner_idx]; current_wins[winner] += 1
        s_w, s_l = (m["scoreA"], m["scoreB"]) if winner_idx == 0 else (m["scoreB"], m["scoreA"]); current_diff[winner] += s_w - s_l; current_diff[loser] += s_l - s_w
    sim_results = cached_single_table_sim(tuple(teams), tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), tuple((m["teamA"], m["teamB"], m["date"], m["bestof"]) for m in unplayed), tuple(sorted(forced_outcomes.items())), tuple(frozenset(b.items()) for b in st.session_state.current_brackets), n_sim)
    st.markdown("---"); st.subheader("Results")
    col1, col2 = st.columns(2)
    with col1:
        display_matches = played.copy()
        for m in unplayed:
            match_key = (m["teamA"], m["teamB"], m.get("date")); outcome_code = forced_outcomes.get(match_key)
            if outcome_code and outcome_code != "random":
                pm = m.copy()
                if outcome_code.startswith("A"): pm["winner"] = "1"; pm["scoreA"], pm["scoreB"] = int(outcome_code[1]), int(outcome_code[2])
                elif outcome_code.startswith("B"): pm["winner"] = "2"; pm["scoreB"], pm["scoreA"] = int(outcome_code[1]), int(outcome_code[2])
                display_matches.append(pm)
        has_preds = any(forced_outcomes.get((m["teamA"], m["teamB"], m.get("date")), "random") != "random" for m in unplayed)
        st.write("**Current Standings (including predictions)**" if has_preds else "**Current Standings**")
        standings_df = build_standings_table(teams, display_matches); st.dataframe(standings_df, use_container_width=True)
    with col2:
        st.write("**Playoff Probabilities**")
        if sim_results is not None and not sim_results.empty:
            if 'Team' in standings_df.columns and not standings_df.empty: st.dataframe(sim_results.set_index('Team').loc[standings_df['Team']].reset_index(), use_container_width=True, hide_index=True)
            else: st.dataframe(sim_results, use_container_width=True, hide_index=True)

def group_dashboard():
    st.header(f"Simulation for {tournament_name} (Group Stage - {selected_stage})")
    st.button("← Change Tournament Format", on_click=lambda: st.session_state.update(page_view='format_selection'))
    group_config = st.session_state.group_config; groups = group_config.get('groups', {}); week_blocks = build_week_blocks(sorted(list(set(m["date"] for m in structured_matches if m.get("date")))))
    st.markdown("---"); st.subheader("Simulation Controls")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        cutoff_week_label = st.select_slider("Select Cutoff Week:", options=[f"Week {i+1}" for i in range(len(week_blocks))], value=f"Week {len(week_blocks)}"); cutoff_week_idx = int(cutoff_week_label.split(" ")[1]) - 1
    with col2:
        n_sim = st.number_input("Number of Simulations:", 1000, 100000, 10000, 1000, key="group_sim_count")
    bracket_config_key = f"{tournament_name}_{selected_stage}"
    if 'current_brackets' not in st.session_state or st.session_state.get('bracket_tournament') != bracket_config_key:
        st.session_state.current_brackets = load_bracket_config(bracket_config_key)['brackets']; st.session_state.bracket_tournament = bracket_config_key
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
                if st.button("Save Brackets", type="primary", key="g_save_brackets"): save_bracket_config(bracket_config_key, {"brackets": st.session_state.current_brackets}); st.success("Brackets saved!"); st.cache_data.clear()
        with config_tabs[1]:
            with st.expander("Configure Groups", expanded=False):
                editable_groups = st.session_state.group_config.get('groups', {})
                for group_name, group_teams in editable_groups.items():
                    editable_groups[group_name] = st.multiselect(f"Teams in {group_name}", options=teams, default=group_teams, key=f"edit_group_{group_name}")
                if st.button("Save Group Changes"):
                    st.session_state.group_config['groups'] = editable_groups; save_group_config(bracket_config_key, st.session_state.group_config); st.success("Group configuration updated!"); st.cache_data.clear(); st.rerun()
    brackets = st.session_state.current_brackets; cutoff_dates = set(d for i in range(cutoff_week_idx + 1) for d in week_blocks[i]) if cutoff_week_idx >= 0 and week_blocks else set()
    played = [m for m in structured_matches if m.get("date") in cutoff_dates and m.get("winner") in ("1", "2")]; unplayed = [m for m in structured_matches if m not in played]
    st.markdown("---"); st.subheader("Upcoming Matches (What-If Scenarios)"); forced_outcomes = {}
    if not unplayed: st.info("No matches left to simulate.")
    else:
        matches_by_week = defaultdict(list); [matches_by_week[w_idx].append(m) for m in unplayed if m.get("date") for w_idx, w_dates in enumerate(week_blocks) if m['date'] in w_dates]
        for week_idx in sorted(matches_by_week.keys()):
            week_label = f"Week {week_idx + 1}: {week_blocks[week_idx][0]} — {week_blocks[week_idx][-1]}"
            with st.expander(f"📅 {week_label}", expanded=False):
                matches_by_date = defaultdict(list); [matches_by_date[m['date']].append(m) for m in matches_by_week[week_idx]]
                for date in sorted(matches_by_date.keys()):
                    st.markdown(f"#### 📅 {date}"); date_matches = matches_by_date[date]
                    for idx in range(0, len(date_matches), 3):
                        cols = st.columns(3)
                        for col_idx, col in enumerate(cols):
                            if idx + col_idx < len(date_matches):
                                m = date_matches[idx + col_idx]; teamA, teamB, bo = m["teamA"], m["teamB"], m["bestof"]; match_key = (teamA, teamB, date)
                                with col, st.container():
                                    st.markdown(f"<div style='text-align: center; font-weight: bold; padding: 10px; background-color: #262730; border-radius: 10px; margin-bottom: 10px;'>{teamA} vs {teamB}</div>", unsafe_allow_html=True)
                                    options = get_series_outcome_options(teamA, teamB, bo)
                                    selected = st.radio("", [opt[0] for opt in options], key=f"g_radio_{date}_{teamA}_{teamB}", label_visibility="collapsed")
                                    for opt_label, opt_code in options:
                                        if opt_label == selected: forced_outcomes[match_key] = opt_code; break
                    st.markdown("---")
    current_wins, current_diff = defaultdict(int), defaultdict(int)
    for m in played:
        winner_idx = int(m["winner"]) - 1; teams_in_match = [m["teamA"], m["teamB"]]; winner, loser = teams_in_match[winner_idx], teams_in_match[1-winner_idx]; current_wins[winner] += 1
        s_w, s_l = (m["scoreA"], m["scoreB"]) if winner_idx == 0 else (m["scoreB"], m["scoreA"]); current_diff[winner] += s_w - s_l; current_diff[loser] += s_l - s_w
    sim_results = cached_group_sim(groups, tuple(sorted(current_wins.items())), tuple(sorted(current_diff.items())), tuple((m["teamA"], m["teamB"], m["date"], m["bestof"]) for m in unplayed), tuple(sorted(forced_outcomes.items())), tuple(frozenset(b.items()) for b in brackets), n_sim)
    display_matches = played.copy()
    for m in unplayed:
        match_key = (m["teamA"], m["teamB"], m.get("date")); outcome_code = forced_outcomes.get(match_key)
        if outcome_code and outcome_code != "random":
            pm = m.copy()
            if outcome_code.startswith("A"): pm["winner"] = "1"; pm["scoreA"], pm["scoreB"] = int(outcome_code[1]), int(outcome_code[2])
            elif outcome_code.startswith("B"): pm["winner"] = "2"; pm["scoreB"], pm["scoreA"] = int(outcome_code[1]), int(outcome_code[2])
            display_matches.append(pm)
    has_preds = any(forced_outcomes.get((m["teamA"], m.get("teamB"), m.get("date")), "random") != "random" for m in unplayed)
    standings_label = "**Standings (incl. predictions)**" if has_preds else "**Current Standings**"
    st.markdown("---"); st.subheader("Results")
    result_tabs = st.tabs(["Overall"] + sorted(groups.keys()))
    with result_tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            st.write(standings_label)
            for gn, g_teams in sorted(groups.items()):
                st.write(f"**{gn}**")
                st.dataframe(build_standings_table(g_teams, display_matches), use_container_width=True)
        with col2:
            st.write("**Playoff Probabilities**")
            if sim_results is not None and not sim_results.empty:
                for gn in sorted(groups.keys()):
                    st.write(f"**{gn}**")
                    st.dataframe(sim_results[sim_results['Group'] == gn].drop(columns=['Group']), use_container_width=True, hide_index=True)
    for i, group_name in enumerate(sorted(groups.keys())):
        with result_tabs[i+1]:
            col1, col2 = st.columns(2)
            with col1: st.write(f"{standings_label} ({group_name})"); st.dataframe(build_standings_table(groups[group_name], display_matches), use_container_width=True)
            with col2:
                st.write(f"**Playoff Probabilities ({group_name})**")
                if sim_results is not None and not sim_results.empty: st.dataframe(sim_results[sim_results['Group'] == group_name].drop(columns=['Group']), use_container_width=True, hide_index=True)

# --- Page Router ---
config_key = f"{tournament_name}_{selected_stage}"
if 'page_view' not in st.session_state or st.session_state.get('active_tournament') != config_key:
    st.session_state.active_tournament = config_key
    saved_format = load_tournament_format(config_key)
    if saved_format == 'single_table': st.session_state.page_view = 'single_table_sim'
    elif saved_format == 'group':
        st.session_state.page_view = 'group_sim'
        st.session_state.group_config = load_group_config(config_key)
    else: st.session_state.page_view = 'format_selection'

if st.session_state.page_view == 'format_selection':
    st.title("🏆 Playoff Odds: Tournament Format")
    st.write(f"How is the **{selected_stage}** of **{tournament_name}** structured?")
    col1, col2 = st.columns(2)
    if col1.button("Single Table League", use_container_width=True):
        save_tournament_format(config_key, 'single_table'); st.session_state.page_view = 'single_table_sim'; st.rerun()
    if col2.button("Group Stage", use_container_width=True):
        save_tournament_format(config_key, 'group'); saved_config = load_group_config(config_key)
        if saved_config: st.session_state.group_config = saved_config; st.session_state.page_view = 'group_sim'
        else: st.session_state.page_view = 'group_setup'
        st.rerun()
elif st.session_state.page_view == 'group_setup':
    group_setup_ui()
    if st.button("← Back to Format Selection"): st.session_state.page_view = 'format_selection'; st.rerun()
elif st.session_state.page_view == 'single_table_sim': single_table_dashboard()
elif st.session_state.page_view == 'group_sim': group_dashboard()
