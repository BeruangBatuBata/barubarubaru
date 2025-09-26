import streamlit as st
import pandas as pd
from utils.analysis_functions import analyze_synergy_combos, analyze_counter_combos
from utils.plotting import plot_synergy_bar_chart, plot_counter_heatmap
from utils.sidebar import build_sidebar

st.set_page_config(layout="wide", page_title="Synergy & Counter Analysis")
build_sidebar()

st.title("🤝 Synergy & Counter Analysis")

if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.warning("Please select and load tournament data from the sidebar on the Overview page.")
    st.stop()

pooled_matches = st.session_state['pooled_matches']
played_matches = [match for match in pooled_matches if any(game.get("winner") for game in match.get("match2games", []))]
all_teams = sorted(list(set(opp.get('name','').strip() for m in played_matches for opp in m.get("match2opponents", []) if opp.get('name'))))
all_heroes = sorted(list(set(p["champion"] for m in pooled_matches for g in m.get("match2games", []) for o in g.get("opponents", []) for p in o.get("players", []) if isinstance(p, dict) and "champion" in p)))

# --- MODIFICATION START ---
# 1. Controls moved from sidebar to main page using columns.
st.subheader("Analysis Controls")
col1, col2, col3, col4 = st.columns(4)

with col1:
    analysis_mode = st.radio("Select Analysis Mode:", ["Synergy (Best Pairs)", "Anti-Synergy (Worst Pairs)", "Counters"])
with col2:
    team_filter = st.selectbox("Filter by Team:", ["All Teams"] + all_teams)
with col3:
    min_games = st.slider("Minimum Games Played Together:", 1, 20, 5)
with col4:
    top_n = st.slider("Number of Results to Show:", 5, 50, 15)

st.markdown("---")
# --- MODIFICATION END ---

if analysis_mode in ["Synergy (Best Pairs)", "Anti-Synergy (Worst Pairs)"]:
    find_anti = (analysis_mode == "Anti-Synergy (Worst Pairs)")
    
    # --- MODIFICATION START ---
    # Moved the hero filter into the main column layout
    with col2:
        focus_hero = st.selectbox("Focus on a specific Hero (optional):", ["All Heroes"] + all_heroes)
        focus_hero = None if focus_hero == "All Heroes" else focus_hero
    # --- MODIFICATION END ---
        
    df_results = analyze_synergy_combos(pooled_matches, team_filter, min_games, top_n, find_anti, focus_hero)
    st.header(f"Top {top_n} {analysis_mode}")
    if df_results.empty:
        st.warning("No hero pairs found matching the selected criteria.")
    else:
        df_display = df_results.reset_index(drop=True); df_display.index += 1
        st.dataframe(df_display, use_container_width=True)
        title = f"Win Rate of {'Worst' if find_anti else 'Best'} Hero Duos"
        if focus_hero: title += f" with {focus_hero}"
        if team_filter != "All Teams": title += f" for {team_filter}"
        plot_synergy_bar_chart(df_results.sort_values("Win Rate (%)", ascending=find_anti), title, focus_hero=focus_hero)

elif analysis_mode == "Counters":
    focus_on_team_picks = True
    # --- MODIFICATION START ---
    # Moved the conditional radio button into the main column layout
    with col2:
        if team_filter != "All Teams":
            focus_on_team_picks = st.radio(f"Perspective:", [f"{team_filter} picks the hero", f"{team_filter} plays against"], horizontal=True, label_visibility="collapsed") == f"{team_filter} picks the hero"
    # --- MODIFICATION END ---

    df_results = analyze_counter_combos(pooled_matches, min_games, top_n, team_filter, focus_on_team_picks)
    st.header(f"Top {top_n} Counter Matchups")
    if df_results.empty:
        st.warning("No counter matchups found matching the selected criteria.")
    else:
        df_display = df_results.reset_index(drop=True); df_display.index += 1
        st.dataframe(df_display, use_container_width=True)
        title = f"Win Rate: Ally Hero vs. Enemy Hero"
        if team_filter != "All Teams": title += f" (Perspective: {team_filter})"
        plot_counter_heatmap(df_results, title)
