import streamlit as st
from collections import defaultdict
from utils.drafting_ai import load_prediction_assets, predict_draft_outcome, get_ai_suggestions, generate_prediction_explanation
from utils.simulation import calculate_series_score_probs
from utils.data_processing import HERO_PROFILES, HERO_DAMAGE_TYPE
from utils.sidebar import build_sidebar
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide", page_title="Drafting Assistant")
build_sidebar()

# --- Helper Functions ---
def generate_win_prob_bar(probability, title):
    """Generates a custom HTML two-sided probability bar."""
    if probability is None: probability = 0.5
    blue_pct, red_pct = probability * 100, 100 - (probability * 100)
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

def update_draft(key):
    """Generic callback to ensure widget state is saved on change."""
    pass

# --- Load Model & Data ---
model_assets = load_prediction_assets()
if model_assets is None:
    st.error("Could not load the prediction model. Please train a model in the 'Admin Panel'.")
    st.stop()
if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.warning("Please select and load tournament data from the sidebar on the Overview page.")
    st.stop()
    
ALL_HEROES = model_assets['all_heroes']
ALL_TEAMS = [None] + model_assets['all_teams']
ROLES = ["EXP", "Jungle", "Mid", "Gold", "Roam"]
pooled_matches = st.session_state['pooled_matches']

# --- Session State Initialization ---
if 'draft' not in st.session_state:
    st.session_state.draft = {
        'blue_team': None, 'red_team': None,
        'blue_bans': [None]*5, 'red_bans': [None]*5,
        'blue_picks': {role: None for role in ROLES},
        'red_picks': {role: None for role in ROLES}
    }

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
        selected_game = st.selectbox(
            "Select a game:", 
            [None] + filtered_games, 
            format_func=lambda x: x[0] if x else "Select a game...", 
            key="filtered_game_selector"
        )
    else:
        st.info("No played games found matching the selected filters.")
        selected_game = None

    if st.button("Load Selected Game"):
        if selected_game:
            _, match_idx, game_idx = selected_game
            match_data = pooled_matches[match_idx]
            game_data = match_data['match2games'][game_idx]
            extradata = game_data.get('extradata')
            
            if not extradata:
                st.error("No draft data (extradata) available for this game.")
            else:
                game_opps = game_data.get('opponents', [])
                if len(game_opps) >= 2:
                    st.session_state.draft['blue_team'] = game_opps[0].get('name')
                    st.session_state.draft['red_team'] = game_opps[1].get('name')
                
                    for i in range(5):
                        st.session_state.draft['blue_bans'][i] = extradata.get(f'team1ban{i+1}')
                        st.session_state.draft['red_bans'][i] = extradata.get(f'team2ban{i+1}')
                        st.session_state.draft['blue_picks'][ROLES[i]] = extradata.get(f'team1champion{i+1}')
                        st.session_state.draft['red_picks'][ROLES[i]] = extradata.get(f'team2champion{i+1}')

                    winner_val = str(game_data.get('winner'))
                    if winner_val in ['1', '2']:
                        winner = "Blue Team" if winner_val == '1' else "Red Team"
                        st.success(f"**Actual Winner:** {winner}")
                    st.rerun()

st.markdown("---")

# --- Main Draft Interface (Code is unchanged below this line) ---
draft = st.session_state.draft
prob_placeholder, turn_placeholder, analysis_placeholder, suggestion_placeholder = st.empty(), st.empty(), st.empty(), st.empty()
c1, c2, c3, c4 = st.columns([2, 2, 1, 1])

st.session_state.draft['blue_team'] = c1.selectbox("Blue Team:", ALL_TEAMS, key='blue_team_select', index=ALL_TEAMS.index(st.session_state.draft['blue_team']) if st.session_state.draft['blue_team'] in ALL_TEAMS else 0, on_change=update_draft, args=('blue_team_select',))
st.session_state.draft['red_team'] = c2.selectbox("Red Team:", ALL_TEAMS, key='red_team_select', index=ALL_TEAMS.index(st.session_state.draft['red_team']) if st.session_state.draft['red_team'] in ALL_TEAMS else 0, on_change=update_draft, args=('red_team_select',))
series_format = c3.selectbox("Series Format:", [1, 3, 5, 7], index=1)

if c4.button("Clear Draft"):
    blue_team_on_clear, red_team_on_clear = st.session_state.draft['blue_team'], st.session_state.draft['red_team']
    st.session_state.draft = {
        'blue_team': blue_team_on_clear, 'red_team': red_team_on_clear,
        'blue_bans': [None]*5, 'red_bans': [None]*5,
        'blue_picks': {role: None for role in ROLES},
        'red_picks': {role: None for role in ROLES}
    }
    st.rerun()

blue_col, red_col = st.columns(2)
taken_heroes = {v for v in draft['blue_picks'].values() if v} | {v for v in draft['red_picks'].values() if v} | set(draft['blue_bans']) | set(draft['red_bans'])
taken_heroes.discard(None)

with blue_col:
    st.header("🔷 Blue Team")
    st.subheader("Bans")
    ban_cols = st.columns(5)
    for i in range(5):
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == draft['blue_bans'][i]])
        key = f"b_ban_{i}"
        draft['blue_bans'][i] = ban_cols[i].selectbox(f"B{i+1}", available, key=key, index=available.index(draft['blue_bans'][i]) if draft['blue_bans'][i] in available else 0, on_change=update_draft, args=(key,))
    st.subheader("Picks")
    for role in ROLES:
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == draft['blue_picks'][role]])
        key = f"b_pick_{role}"
        draft['blue_picks'][role] = st.selectbox(role, available, key=key, index=available.index(draft['blue_picks'][role]) if draft['blue_picks'][role] in available else 0, on_change=update_draft, args=(key,))

with red_col:
    st.header("🔶 Red Team")
    st.subheader("Bans")
    ban_cols = st.columns(5)
    for i in range(5):
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == draft['red_bans'][i]])
        key = f"r_ban_{i}"
        draft['red_bans'][i] = ban_cols[i].selectbox(f"R{i+1}", available, key=key, index=available.index(draft['red_bans'][i]) if draft['red_bans'][i] in available else 0, on_change=update_draft, args=(key,))
    st.subheader("Picks")
    for role in ROLES:
        available = [None] + sorted([h for h in ALL_HEROES if h not in taken_heroes or h == draft['red_picks'][role]])
        key = f"r_pick_{role}"
        draft['red_picks'][role] = st.selectbox(role, available, key=key, index=available.index(draft['red_picks'][role]) if draft['red_picks'][role] in available else 0, on_change=update_draft, args=(key,))

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
    series_probs = calculate_series_score_probs(prob_overall, series_format, draft['blue_team'], draft['red_team'])
    if series_probs:
        st.write(f"**Best-of-{series_format} Series Score Probability**")
        sorted_probs = sorted(series_probs.items(), key=lambda item: item[1], reverse=True)
        prob_text = ""
        for score, probability in sorted_probs: prob_text += f"- **{score}:** {probability:.1%}\n"
        st.markdown(prob_text)

with analysis_placeholder.container():
    st.subheader("AI Draft Analysis")
    c1, c2 = st.columns(2)
    with c1: st.markdown("".join([f"- {s}\n" for s in explanation['blue']]))
    with c2: st.markdown("".join([f"- {s}\n" for s in explanation['red']]))

total_bans, total_picks = len(blue_b) + len(red_b), len(blue_p) + len(red_p)
turn, phase = None, "DRAFT COMPLETE"
if total_bans < 6: phase, turn = "BAN", ['B', 'R', 'B', 'R', 'B', 'R'][total_bans]
elif total_picks < 6: phase, turn = "PICK", ['B', 'R', 'R', 'B', 'B', 'R'][total_picks]
elif total_bans < 10: phase, turn = "BAN", ['R', 'B', 'R', 'B'][total_bans - 6]
elif total_picks < 10: phase, turn = "PICK", ['R', 'B', 'B', 'R'][total_picks - 6]

if turn == 'B': team_turn = draft.get('blue_team') or "Blue Team"
elif turn == 'R': team_turn = draft.get('red_team') or "Red Team"
else: team_turn = "Draft Complete"
turn_phase_text = phase if phase != "DRAFT COMPLETE" else ""
turn_placeholder.header(f"Turn: {team_turn} ({turn_phase_text})" if team_turn != "Draft Complete" else f"{team_turn}")

with suggestion_placeholder.container():
    if turn:
        st.subheader("AI Suggestions")
        is_blue_turn = (turn == 'B')
        suggestions = get_ai_suggestions([h for h in ALL_HEROES if h not in taken_heroes], blue_p, red_p, blue_b, red_b, draft['blue_team'], draft['red_team'], model_assets, HERO_PROFILES, is_blue_turn, phase)
        for hero, score in suggestions[:5]:
            label = f"{hero} ({'Threat' if phase == 'BAN' else 'Win Prob'}: {score:.1%})"
            st.button(label, key=f"sug_{hero}")
