import streamlit as st
import pandas as pd
from utils.analysis_functions import process_head_to_head_teams, process_head_to_head_heroes

st.set_page_config(layout="wide", page_title="Head-to-Head")

st.title("⚔️ Head-to-Head Comparison")

if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.warning("Please select and load tournament data on the homepage first.")
    st.stop()

pooled_matches = st.session_state['pooled_matches']

### --- MODIFIED --- ###
played_matches = [
    match for match in pooled_matches 
    if any(game.get("winner") for game in match.get("match2games", []))
]

all_teams = sorted(list(set(
    opp.get('name','').strip()
    for match in played_matches
    for opp in match.get("match2opponents", [])
    if opp.get('name')
)))
### --- END MODIFIED --- ###

all_heroes = sorted(list(set(
    p["champion"]
    for m in pooled_matches
    for g in m.get("match2games", [])
    for o in g.get("opponents", [])
    for p in o.get("players", [])
    if isinstance(p, dict) and "champion" in p
)))

# --- Sidebar Controls ---
st.sidebar.header("Comparison Setup")
mode = st.sidebar.radio("Select Comparison Mode:", ["Team vs. Team", "Hero vs. Hero"])

if mode == "Team vs. Team":
    team1 = st.sidebar.selectbox("Select Team 1:", options=all_teams, index=0)
    team2 = st.sidebar.selectbox("Select Team 2:", options=all_teams, index=1 if len(all_teams) > 1 else 0)

    if not all_teams:
        st.warning("No teams with completed matches found in the selected data.")
    elif team1 == team2:
        st.error("Please select two different teams for comparison.")
    else:
        st.header(f"{team1} vs {team2}")
        with st.spinner(f"Analyzing matches between {team1} and {team2}..."):
            h2h_data = process_head_to_head_teams(team1, team2, pooled_matches)
        if h2h_data["total_games"] == 0:
            st.warning(f"No direct matches found between {team1} and {team2} in the selected tournaments.")
        else:
            st.subheader("Overall Match Results")
            col1, col2, col3 = st.columns(3)
            col1.metric(label=f"{team1} Wins", value=h2h_data["win_counts"][team1])
            col2.metric(label=f"{team2} Wins", value=h2h_data["win_counts"][team2])
            col3.metric(label="Total Games Played", value=h2h_data["total_games"])
            st.markdown("---")
            st.subheader("Top Picks & Bans (in Head-to-Head Matches)")
            col_picks, col_bans = st.columns(2)
            with col_picks:
                st.write(f"**Most Picked by {team1}**")
                t1_picks_df = h2h_data["t1_picks_df"]; t1_picks_df.index += 1
                st.dataframe(t1_picks_df, use_container_width=True)
                st.write(f"**Most Picked by {team2}**")
                t2_picks_df = h2h_data["t2_picks_df"]; t2_picks_df.index += 1
                st.dataframe(t2_picks_df, use_container_width=True)
            with col_bans:
                st.write(f"**Most Banned by {team1}**")
                t1_bans_df = h2h_data["t1_bans_df"]; t1_bans_df.index += 1
                st.dataframe(t1_bans_df, use_container_width=True)
                st.write(f"**Most Banned by {team2}**")
                t2_bans_df = h2h_data["t2_bans_df"]; t2_bans_df.index += 1
                st.dataframe(t2_bans_df, use_container_width=True)

else: # Hero vs. Hero mode
    hero1 = st.sidebar.selectbox("Select Hero 1:", options=all_heroes, index=0)
    hero2 = st.sidebar.selectbox("Select Hero 2:", options=all_heroes, index=1 if len(all_heroes) > 1 else 0)

    if hero1 == hero2:
        st.error("Please select two different heroes for comparison.")
    else:
        st.header(f"{hero1} vs {hero2}")
        with st.spinner(f"Analyzing matches between {hero1} and {hero2}..."):
            h2h_data = process_head_to_head_heroes(hero1, hero2, pooled_matches)
        
        if h2h_data["total_games"] == 0:
            st.warning(f"No matches found where {hero1} and {hero2} played on opposing teams.")
        else:
            st.subheader("Head-to-Head Results")
            h1_wins, h2_wins, total_games = h2h_data["h1_wins"], h2h_data["h2_wins"], h2h_data["total_games"]
            h1_win_rate = (h1_wins / total_games * 100) if total_games > 0 else 0
            h2_win_rate = (h2_wins / total_games * 100) if total_games > 0 else 0

            col1, col2, col3 = st.columns(3)
            col1.metric(label=f"{hero1} Wins", value=f"{h1_wins} ({h1_win_rate:.1f}%)")
            col2.metric(label=f"{hero2} Wins", value=f"{h2_wins} ({h2_win_rate:.1f}%)")
            col3.metric(label="Total Games Against", value=total_games)
