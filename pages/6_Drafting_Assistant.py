import streamlit as st
from collections import defaultdict
from utils.drafting_ai import load_prediction_assets, predict_draft_outcome, get_ai_suggestions, generate_prediction_explanation
from utils.simulation import calculate_series_score_probs
from utils.data_processing import HERO_PROFILES, HERO_DAMAGE_TYPE
from utils.sidebar import build_sidebar
import pandas as pd

st.set_page_config(layout="wide", page_title="Drafting Assistant")
build_sidebar()

def handle_suggestion_click(hero, phase, is_blue_turn, roles, hero_profiles):
    """
    Callback function to update the draft state when a suggestion button is clicked.
    This modifies BOTH the central 'draft' state and the specific widget's key state.
    """
    if phase == 'BAN':
        # Determine which team's bans to update
        bans_list = st.session_state.draft['blue_bans'] if is_blue_turn else st.session_state.draft['red_bans']
        widget_key_prefix = "b_ban" if is_blue_turn else "r_ban"
        
        # Find the first empty slot and update it
        for i in range(5):
            if bans_list[i] is None:
                bans_list[i] = hero
                st.session_state[f"{widget_key_prefix}_{i}"] = hero # Directly update the widget's key
                break

    elif phase == 'PICK':
        # Determine which team's picks to update
        picks_dict = st.session_state.draft['blue_picks'] if is_blue_turn else st.session_state.draft['red_picks']
        widget_key_prefix = "b_pick" if is_blue_turn else "r_pick"
        
        open_roles = [role for role in roles if picks_dict[role] is None]
        if open_roles:
            # Find the best role for the hero, or default to the first open one
            chosen_role = open_roles[0] 
            profiles = hero_profiles.get(hero, [])
            if profiles:
                primary_role = profiles[0].get('primary_role')
                if primary_role in open_roles:
                    chosen_role = primary_role
            
            # Update the state
            picks_dict[chosen_role] = hero
            st.session_state[f"{widget_key_prefix}_{chosen_role}"] = hero

# --- Helper function for the custom probability bar ---
def generate_win_prob_bar(probability, title):
    """Generates a custom HTML two-sided probability bar."""
    if probability is None:
        probability = 0.5 # Default to 50/50 if no prediction
    blue_pct = probability * 100
    red_pct = 100 - blue_pct
    bar_html = f"""
    <div style="margin-bottom: 1rem;">
        <p style="margin-bottom: 0.25rem; font-size: 0.9em; color: #555; font-weight:bold;">{title}</p>
        <div style="display: flex; width: 100%; height: 28px; font-weight: bold; font-size: 14px; border-radius: 5px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);">
            <div style="width: {blue_pct:.1f}%; background-color: #3b82f6; color: white; display: flex; align-items: center; justify-content: center;">{blue_pct:.1f}%</div>
            <div style="width: {red_pct:.1f}%; background-color: #ef4444; color: white; display: flex; align-items: center; justify-content: center;">{red_pct:.1f}%</div>
        </div>
    </div>
    """
    st.markdown(bar_html, unsafe_allow_html=True)

# --- Load Model & Data ---
model_assets = load_prediction_assets()
if model_assets is None:
    st.error("Could not load the prediction model. Please train a model in the 'Admin Panel' and ensure 'draft_predictor.json' and 'draft_assets.json' are in your repository's root directory.")
    st.stop()

if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.warning("Please select and load tournament data from the sidebar on the Overview page.")
    st.stop()
    
ALL_HEROES = model_assets['all_heroes']
ROLES = ["EXP", "Jungle", "Mid", "Gold", "Roam"]
pooled_matches = st.session_state['pooled_matches']

# Extract teams that have played matches
def get_teams_with_played_matches(pooled_matches):
    """Extract unique teams that have played at least one game"""
    teams_with_games = set()
    
    for match in pooled_matches:
        opps = match.get('match2opponents', [])
        if len(opps) < 2:
            continue
            
        # Check if this match has any played games
        has_played_games = False
        for game in match.get('match2games', []):
            if game.get('extradata') and game.get('winner') in ['1', '2']:
                has_played_games = True
                break
        
        # Only add teams if they've played
        if has_played_games:
            for opp in opps:
                team_name = opp.get('name', '').strip()
                if team_name:
                    teams_with_games.add(team_name)
    
    return sorted(list(teams_with_games))

TOURNAMENT_TEAMS = [None] + get_teams_with_played_matches(pooled_matches)
ALL_TEAMS_FROM_MODEL = model_assets['all_teams']  # Keep this for model compatibility

# Check if we have any teams with played matches
if len(TOURNAMENT_TEAMS) <= 1:  # Only None in the list
    st.warning("⚠️ No teams have played matches yet in this tournament. Please wait for matches to be completed.")
    st.stop()

# --- Session State Initialization ---
if 'draft' not in st.session_state:
    st.session_state.draft = {
        'blue_team': None, 'red_team': None,
        'blue_bans': [None]*5, 'red_bans': [None]*5,
        'blue_picks': {role: None for role in ROLES},
        'red_picks': {role: None for role in ROLES}
    }
if 'selected_past_game' not in st.session_state:
    st.session_state.selected_past_game = None

# --- UI & Logic ---
st.title("🎯 Professional Drafting Assistant")

with st.expander("Review a Past Game"):
    # First, extract all unique teams and dates from PLAYED matches
    all_teams = set()
    all_dates = set()
    
    for match in pooled_matches:
        opps = match.get('match2opponents', [])
        if len(opps) >= 2:
            # Check if match has been played by looking for games with extradata
            has_played_games = any(
                game.get('extradata') and game.get('winner') in ['1', '2']
                for game in match.get('match2games', [])
            )
            
            if has_played_games:
                all_teams.add(opps[0].get('name', ''))
                all_teams.add(opps[1].get('name', ''))
                
                # Extract date from the match
                match_date = match.get('date') or match.get('datetime') or match.get('timestamp')
                if match_date:
                    try:
                        date_obj = pd.to_datetime(match_date)
                        all_dates.add(date_obj.strftime('%Y-%m-%d'))
                    except:
                        pass
    
    # Sort teams and dates
    sorted_teams = ['Any Team'] + sorted([t for t in all_teams if t])
    sorted_dates = ['Any Date'] + sorted([d for d in all_dates if d], reverse=True)  # Most recent first
    
    # Filter controls
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        filter_team1 = st.selectbox("Team 1:", sorted_teams, key="filter_team1")
    
    with col2:
        filter_team2 = st.selectbox("Team 2:", sorted_teams, key="filter_team2")
    
    with col3:
        filter_date = st.selectbox("Date:", sorted_dates, key="filter_date")
    
    # Build filtered games list
    filtered_games = []
    
    for match_idx, match in enumerate(pooled_matches):
        opps = match.get('match2opponents', [])
        if len(opps) < 2:
            continue
        
        team1_name = opps[0].get('name', '')
        team2_name = opps[1].get('name', '')
        
        # Apply team filters
        if filter_team1 != 'Any Team' and filter_team2 != 'Any Team':
            # Both teams specified - check exact match (order doesn't matter)
            if not ((team1_name == filter_team1 and team2_name == filter_team2) or 
                    (team1_name == filter_team2 and team2_name == filter_team1)):
                continue
        elif filter_team1 != 'Any Team':
            # Only team 1 specified
            if filter_team1 not in [team1_name, team2_name]:
                continue
        elif filter_team2 != 'Any Team':
            # Only team 2 specified
            if filter_team2 not in [team1_name, team2_name]:
                continue
        
        # Apply date filter
        if filter_date != 'Any Date':
            match_date = match.get('date') or match.get('datetime') or match.get('timestamp')
            if match_date:
                try:
                    date_obj = pd.to_datetime(match_date)
                    if date_obj.strftime('%Y-%m-%d') != filter_date:
                        continue
                except:
                    continue
            else:
                continue
        
        # Add ONLY PLAYED games from this match
        for game_idx, game in enumerate(match.get('match2games', [])):
            extradata = game.get('extradata')
            winner = game.get('winner')
            
            # Check if game was actually played
            if extradata and winner in ['1', '2']:
                # Verify it has actual draft data
                has_draft_data = any(
                    extradata.get(f'team1champion{i}') or extradata.get(f'team2champion{i}')
                    for i in range(1, 6)
                )
                
                if has_draft_data:
                    # Format the date for display
                    match_date = match.get('date') or match.get('datetime') or match.get('timestamp')
                    date_str = ""
                    if match_date:
                        try:
                            date_obj = pd.to_datetime(match_date)
                            date_str = date_obj.strftime('%Y-%m-%d')
                        except:
                            pass
                    
                    label = f"{team1_name} vs {team2_name} - Game {game_idx + 1}"
                    if date_str:
                        label += f" ({date_str})"
                    
                    filtered_games.append((label, match_idx, game_idx))
    
    # Game selector
    if filtered_games:
        st.write(f"Found {len(filtered_games)} played game{'s' if len(filtered_games) > 1 else ''}")
        
        # --- MODIFICATION START ---
        # Find the index of the currently loaded game to set the selectbox default
        game_options = [None] + filtered_games
        current_selection_index = 0
        if st.session_state.selected_past_game in game_options:
            current_selection_index = game_options.index(st.session_state.selected_past_game)

        selected_game = st.selectbox(
            "Select a game:", 
            game_options, 
            index=current_selection_index,
            format_func=lambda x: x[0] if x else "Select a game...", 
            key="filtered_game_selector"
        )
        # --- MODIFICATION END ---

    else:
        st.info("No played games found matching the selected filters.")
        selected_game = None
    
    # Load button
    col1, col2 = st.columns([1, 5])
    with col1:
        load_button = st.button("Load & Analyze Game", type="primary", disabled=(selected_game is None))
    
    if load_button and selected_game:
        # --- MODIFICATION START ---
        # Store the selected game in the session state
        st.session_state.selected_past_game = selected_game
        # --- MODIFICATION END ---
        
        _, match_idx, game_idx = selected_game
        match_data = pooled_matches[match_idx]
        game_data = match_data['match2games'][game_idx]
        extradata = game_data['extradata']
        
        # Load the draft data
        st.session_state.draft['blue_team'] = match_data['match2opponents'][0].get('name')
        st.session_state.draft['red_team'] = match_data['match2opponents'][1].get('name')
        
        for i in range(5):
            st.session_state.draft['blue_bans'][i] = extradata.get(f'team1ban{i+1}')
            st.session_state.draft['red_bans'][i] = extradata.get(f'team2ban{i+1}')
            st.session_state.draft['blue_picks'][ROLES[i]] = extradata.get(f'team1champion{i+1}')
            st.session_state.draft['red_picks'][ROLES[i]] = extradata.get(f'team2champion{i+1}')
        
        # Display the actual winner
        winner = "Blue Team" if str(game_data.get('winner')) == '1' else "Red Team"
        st.success(f"✅ **Game Loaded!** Actual Winner: **{winner}**")
        
        # Show a brief summary
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**{st.session_state.draft['blue_team']}** (Blue Side)")
            blue_picks = [h for h in st.session_state.draft['blue_picks'].values() if h]
            st.write("Picks: " + ", ".join(blue_picks[:3]) + "...")
        with col2:
            st.write(f"**{st.session_state.draft['red_team']}** (Red Side)")  
            red_picks = [h for h in st.session_state.draft['red_picks'].values() if h]
            st.write("Picks: " + ", ".join(red_picks[:3]) + "...")
        
        st.rerun()

st.markdown("---")

# --- Main Draft Interface ---
draft = st.session_state.draft
prob_placeholder = st.empty()
turn_placeholder = st.empty()
analysis_placeholder = st.empty()
suggestion_placeholder = st.empty()

c1, c2, c3 = st.columns([2, 2, 1])

# Team selection with callbacks

c1.selectbox(
    "Blue Team:", 
    TOURNAMENT_TEAMS, 
    key='blue_team_select', 
    index=TOURNAMENT_TEAMS.index(draft['blue_team']) if draft['blue_team'] in TOURNAMENT_TEAMS else 0,
)

c2.selectbox(
    "Red Team:", 
    TOURNAMENT_TEAMS, 
    key='red_team_select', 
    index=TOURNAMENT_TEAMS.index(draft['red_team']) if draft['red_team'] in TOURNAMENT_TEAMS else 0,
)

series_format = c3.selectbox("Series Format:", [1, 3, 5, 7], index=1)

# Build taken heroes set
taken_heroes = set()
for role, hero in draft['blue_picks'].items():
    if hero and hero != 'None':
        taken_heroes.add(hero)
for role, hero in draft['red_picks'].items():
    if hero and hero != 'None':
        taken_heroes.add(hero)
for hero in draft['blue_bans']:
    if hero and hero != 'None':
        taken_heroes.add(hero)
for hero in draft['red_bans']:
    if hero and hero != 'None':
        taken_heroes.add(hero)

blue_col, red_col = st.columns(2)

# Blue team section with callbacks
with blue_col:
    st.header("🔷 Blue Team")
    st.subheader("Bans")
    ban_cols = st.columns(5)
    for i in range(5):
        current_ban = st.session_state.draft['blue_bans'][i]
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == current_ban])
        if current_ban and current_ban not in available:
            available.append(current_ban)
            available = [None] + sorted(available[1:])
        
        ban_cols[i].selectbox(
            f"B{i+1}", 
            available, 
            key=f"b_ban_{i}", 
            index=available.index(current_ban) if current_ban in available else 0,
        )
    
    st.subheader("Picks")
    for role in ROLES:
        current_pick = st.session_state.draft['blue_picks'][role]
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == current_pick])
        if current_pick and current_pick not in available:
            available.append(current_pick)
            available = [None] + sorted(available[1:])
        
        st.selectbox(
            role, 
            available, 
            key=f"b_pick_{role}", 
            index=available.index(current_pick) if current_pick in available else 0,
        )

# Red team section with callbacks
with red_col:
    st.header("🔶 Red Team")
    st.subheader("Bans")
    ban_cols = st.columns(5)
    for i in range(5):
        current_ban = st.session_state.draft['red_bans'][i]
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == current_ban])
        if current_ban and current_ban not in available:
            available.append(current_ban)
            available = [None] + sorted(available[1:])
        
        ban_cols[i].selectbox(
            f"R{i+1}", 
            available, 
            key=f"r_ban_{i}", 
            index=available.index(current_ban) if current_ban in available else 0,
        )
    
    st.subheader("Picks")
    for role in ROLES:
        current_pick = st.session_state.draft['red_picks'][role]
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == current_pick])
        if current_pick and current_pick not in available:
            available.append(current_pick)
            available = [None] + sorted(available[1:])
        
        st.selectbox(
            role, 
            available, 
            key=f"r_pick_{role}", 
            index=available.index(current_pick) if current_pick in available else 0,
        )

# Add a reset draft button
if st.button("🔄 Reset Draft", help="Clear all picks and bans"):
    st.session_state.draft = {
        'blue_team': draft['blue_team'], 
        'red_team': draft['red_team'],
        'blue_bans': [None]*5, 
        'red_bans': [None]*5,
        'blue_picks': {role: None for role in ROLES},
        'red_picks': {role: None for role in ROLES}
    }
    # --- MODIFICATION START ---
    # Also reset the selected past game
    st.session_state.selected_past_game = None
    # --- MODIFICATION END ---
    st.rerun()
    
# --- Calculations ---
blue_p = {k: v for k, v in draft['blue_picks'].items() if v}
red_p = {k: v for k, v in draft['red_picks'].items() if v}
blue_b = [v for v in draft['blue_bans'] if v]
red_b = [v for v in draft['red_bans'] if v]

prob_overall, prob_draft_only = predict_draft_outcome(blue_p, red_p, blue_b, red_b, draft['blue_team'], draft['red_team'], model_assets, HERO_PROFILES)
explanation = generate_prediction_explanation(list(blue_p.values()), list(red_p.values()), HERO_PROFILES, HERO_DAMAGE_TYPE)

with prob_placeholder.container():
    st.subheader("Live Win Probability")
    generate_win_prob_bar(prob_overall, "Overall Prediction (Draft + Team History)")
    generate_win_prob_bar(prob_draft_only, "Draft-Only Prediction (Team Neutral)")
    
    if series_format > 1 and prob_overall is not None:
        series_probs = calculate_series_score_probs(prob_overall, series_format)
        if series_probs:
            st.write(f"**Best-of-{series_format} Series Score Probability**")
            
            # Get team names with fallbacks
            blue_team_name = draft['blue_team'] or "Blue Team"
            red_team_name = draft['red_team'] or "Red Team"
            
            # Create columns for better layout
            col1, col2 = st.columns(2)
            
            # Separate scores by winner
            blue_wins = []
            red_wins = []
            
            for score, probability in series_probs.items():
                wins, losses = map(int, score.split('-'))
                if wins > losses:  # Blue team wins
                    blue_wins.append((score, probability))
                else:  # Red team wins
                    red_wins.append((score, probability))
            
            # Display blue team winning scenarios
            with col1:
                st.markdown(f"**🔷 {blue_team_name} wins:**")
                if blue_wins:
                    for score, prob in sorted(blue_wins, key=lambda x: x[1], reverse=True):
                        st.markdown(f"- **{score}:** {prob:.1%}")
                else:
                    st.markdown("- *No winning scenarios*")
            
            # Display red team winning scenarios  
            with col2:
                st.markdown(f"**🔶 {red_team_name} wins:**")
                if red_wins:
                    for score, prob in sorted(red_wins, key=lambda x: x[1], reverse=True):
                        st.markdown(f"- **{score}:** {prob:.1%}")
                else:
                    st.markdown("- *No winning scenarios*")
            
            # Show total win probability for series
            blue_series_win_prob = sum(prob for _, prob in blue_wins)
            red_series_win_prob = sum(prob for _, prob in red_wins)
            
            st.markdown("---")
            st.markdown(f"**Series Win Probability:** {blue_team_name} **{blue_series_win_prob:.1%}** vs {red_team_name} **{red_series_win_prob:.1%}**")

with analysis_placeholder.container():
    st.subheader("AI Draft Analysis")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("".join([f"- {s}\n" for s in explanation['blue']]))
    with c2:
        st.markdown("".join([f"- {s}\n" for s in explanation['red']]))

# --- Turn Logic & Suggestions ---
total_bans, total_picks = len(blue_b) + len(red_b), len(blue_p) + len(red_p)
turn, phase = None, "DRAFT COMPLETE"
if total_bans < 6: phase, turn = "BAN", ['B', 'R', 'B', 'R', 'B', 'R'][total_bans]
elif total_picks < 6: phase, turn = "PICK", ['B', 'R', 'R', 'B', 'B', 'R'][total_picks]
elif total_bans < 10: phase, turn = "BAN", ['R', 'B', 'R', 'B'][total_bans - 6]
elif total_picks < 10: phase, turn = "PICK", ['R', 'B', 'B', 'R'][total_picks - 6]

if turn:
    team_turn = "Blue Team" if turn == 'B' else "Red Team"
    turn_placeholder.header(f"Turn: {team_turn} ({phase})")

with suggestion_placeholder.container():
    if turn:
        st.subheader("AI Suggestions")
        is_blue_turn = (turn == 'B')
        suggestions = get_ai_suggestions(
            [h for h in ALL_HEROES if h not in taken_heroes],
            blue_p, red_p, blue_b, red_b,
            draft['blue_team'], draft['red_team'],
            model_assets, HERO_PROFILES, is_blue_turn, phase
        )
        
        # Show which team's turn
        turn_color = "🔷" if is_blue_turn else "🔶"
        team_name = draft['blue_team'] if is_blue_turn else draft['red_team']
        team_name = team_name or ("Blue Team" if is_blue_turn else "Red Team")
        st.markdown(f"{turn_color} **{team_name}'s {phase}**")
        
        # Display suggestions with clickable functionality
        for idx, (hero, score) in enumerate(suggestions[:5]):
            # Get hero role for picks
            hero_role = ""
            if phase == 'PICK' and hero in HERO_PROFILES:
                primary_role = HERO_PROFILES[hero][0].get('primary_role', '')
                hero_role = f" ({primary_role})"
            
            label = f"{hero}{hero_role} - {'Threat' if phase == 'BAN' else 'Win Rate'}: {score:.1%}"
            
            # THIS IS THE KEY CHANGE: Use on_click instead of an 'if' block
            st.button(
                label, 
                key=f"sug_{hero}", 
                use_container_width=True,
                on_click=handle_suggestion_click,
                args=(hero, phase, is_blue_turn, ROLES, HERO_PROFILES) # Pass arguments to the callback
            )
    else:
        # Draft is complete
        st.subheader("📋 Draft Complete")
        st.info("All picks and bans have been completed. Review the AI analysis above to understand the strengths and weaknesses of each draft.")

# Optional: Show team statistics
if st.checkbox("Show team statistics", value=False):
    # Count matches per team
    team_match_count = {}
    for match in pooled_matches:
        opps = match.get('match2opponents', [])
        if len(opps) >= 2:
            # Check if match was played
            for game in match.get('match2games', []):
                if game.get('extradata') and game.get('winner') in ['1', '2']:
                    team1 = opps[0].get('name', '').strip()
                    team2 = opps[1].get('name', '').strip()
                    if team1:
                        team_match_count[team1] = team_match_count.get(team1, 0) + 1
                    if team2:
                        team_match_count[team2] = team_match_count.get(team2, 0) + 1
                    break  # Count match only once
    
    st.info(f"📊 **{len(TOURNAMENT_TEAMS)-1}** teams have played matches in this tournament")
    
    with st.expander("View team statistics"):
        stats_data = []
        for team in TOURNAMENT_TEAMS[1:]:  # Exclude None
            stats_data.append({
                "Team": team,
                "Matches Played": team_match_count.get(team, 0) // 2  # Divide by 2 since we count each match twice
            })
        
        stats_df = pd.DataFrame(stats_data)
        stats_df = stats_df.sort_values("Matches Played", ascending=False)
        st.dataframe(stats_df, hide_index=True)
