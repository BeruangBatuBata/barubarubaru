import streamlit as st
import pandas as pd
from utils.analysis_functions import process_head_to_head_teams, process_head_to_head_heroes
from utils.sidebar import build_sidebar

st.set_page_config(layout="wide", page_title="Head-to-Head")
build_sidebar()

st.title("⚔️ Head-to-Head Comparison")

if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.warning("Please select and load tournament data from the sidebar on the Overview page.")
    st.stop()

pooled_matches = st.session_state['pooled_matches']
played_matches = [match for match in pooled_matches if any(game.get("winner") for game in match.get("match2games", []))]
all_teams = sorted(list(set(opp.get('name','').strip() for match in played_matches for opp in match.get("match2opponents", []) if opp.get('name'))))
all_heroes = sorted(list(set(p["champion"] for m in pooled_matches for g in m.get("match2games", []) for o in g.get("opponents", []) for p in o.get("players", []) if isinstance(p, dict) and "champion" in p)))

st.subheader("Comparison Setup")
mode = st.radio("Select Comparison Mode:", ["Team vs. Team", "Hero vs. Hero"], horizontal=True)
st.markdown("---")

if mode == "Team vs. Team":
    col1, col2 = st.columns(2)
    with col1:
        team1 = st.selectbox("Select Team 1:", options=all_teams, index=0)
    with col2:
        team2 = st.selectbox("Select Team 2:", options=all_teams, index=1 if len(all_teams) > 1 else 0)

    if not all_teams:
        st.warning("No teams with completed matches found in the selected data.")
    elif team1 == team2:
        st.error("Please select two different teams for comparison.")
    else:
        st.header(f"{team1} vs {team2}")
        h2h_data = process_head_to_head_teams(team1, team2, pooled_matches)
        
        # --- MODIFICATION START: Create Tabs ---
        h2h_tab, overall_tab = st.tabs(["Head-to-Head Stats", "Overall Stats (vs Everyone)"])
        
        with h2h_tab:
            if h2h_data["total_games"] == 0:
                st.warning(f"No direct matches found between {team1} and {team2}.")
            else:
                col1, col2, col3 = st.columns(3)
                col1.metric(f"{team1} Wins", h2h_data["win_counts"][team1])
                col2.metric(f"{team2} Wins", h2h_data["win_counts"][team2])
                col3.metric("Total Games", h2h_data["total_games"])
                
                st.subheader("Picks & Bans in Head-to-Head Matches")
                c1, c2 = st.columns(2)

                def format_df_for_display(df):
                    """Helper function to reset index and start it from 1."""
                    display_df = df.reset_index(drop=True)
                    display_df.index += 1
                    return display_df

                with c1:
                    st.write(f"**{team1} Top Picks (vs {team2})**")
                    st.dataframe(format_df_for_display(h2h_data["t1_picks_df"]), use_container_width=True)
                    st.write(f"**{team2} Top Picks (vs {team1})**")
                    st.dataframe(format_df_for_display(h2h_data["t2_picks_df"]), use_container_width=True)
                with c2:
                    st.write(f"**{team1} Top Bans (vs {team2})**")
                    st.dataframe(format_df_for_display(h2h_data["t1_bans_df"]), use_container_width=True)
                    st.write(f"**{team2} Top Bans (vs {team1})**")
                    st.dataframe(format_df_for_display(h2h_data["t2_bans_df"]), use_container_width=True)

        with overall_tab:
            st.subheader("Overall Tournament Performance")
            st.info("This shows each team's general pick/ban patterns against all opponents in the selected tournaments.")
            c1_overall, c2_overall = st.columns(2)

            with c1_overall:
                st.write(f"**{team1} Top Picks (Overall)**")
                st.dataframe(format_df_for_display(h2h_data["t1_overall_picks_df"]), use_container_width=True)
                st.write(f"**{team2} Top Picks (Overall)**")
                st.dataframe(format_df_for_display(h2h_data["t2_overall_picks_df"]), use_container_width=True)
            with c2_overall:
                st.write(f"**{team1} Top Bans (Overall)**")
                st.dataframe(format_df_for_display(h2h_data["t1_overall_bans_df"]), use_container_width=True)
                st.write(f"**{team2} Top Bans (Overall)**")
                st.dataframe(format_df_for_display(h2h_data["t2_overall_bans_df"]), use_container_width=True)
        # --- MODIFICATION END ---

else: # Hero vs. Hero mode
    col1, col2 = st.columns(2)
    with col1:
        hero1 = st.selectbox("Select Hero 1:", options=all_heroes, index=0)
    with col2:
        hero2 = st.selectbox("Select Hero 2:", options=all_heroes, index=1 if len(all_heroes) > 1 else 0)
    
    if hero1 == hero2:
        st.error("Please select two different heroes.")
    else:
        st.header(f"{hero1} vs {hero2}")
        h2h_data = process_head_to_head_heroes(hero1, hero2, pooled_matches)
        if h2h_data["total_games"] == 0:
            st.warning("No matches found where these heroes played on opposing teams.")
        else:
            h1_wr = (h2h_data["h1_wins"] / h2h_data["total_games"]) * 100
            col1, col2, col3 = st.columns(3)
            col1.metric(f"{hero1} Wins", h2h_data["h1_wins"], f"{h1_wr:.1f}% Win Rate")
            col2.metric(f"{hero2} Wins", h2h_data["h2_wins"])
            col3.metric("Total Games Against", h2h_data["total_games"])
