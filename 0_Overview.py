import streamlit as st
from utils.sidebar import build_sidebar
from utils.analysis_functions import calculate_hero_stats_for_team
from utils.plotting import plot_presence_bar_chart 
import pandas as pd
import base64
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="MLBB Analytics Overview",
    page_icon="🎮",
    layout="wide"
)

# --- Build the shared sidebar ---
build_sidebar()

# --- Function to encode image to Base64 ---
def get_image_as_base_64(path):
    """Encodes a local image file to a Base64 string for embedding in HTML."""
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return None

# --- Main Page Content ---

# Custom Branded Header
beruang_logo_base_64 = get_image_as_base_64("beruangbatubata.png")
if beruang_logo_base_64:
    # This HTML block creates the header without the extra gap
    st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 20px; padding: 10px; border-radius: 10px; background-color: #262730;">
            <img src="data:image/png;base64,{beruang_logo_base_64}" style="width: 100px; margin-right: 20px; border-radius: 10px;">
            <div>
                <h1 style="margin-bottom: 10px;">MLBB Pro-Scene Analytics Dashboard</h1>
                <blockquote style="border-left: 4px solid #4A90E2; padding-left: 15px; margin: 10px 0; font-style: italic; color: #d1d9e1;">
                    Every draft holds a lesson, and every stat is a piece of a puzzle.
                </blockquote>
                <p style="margin-top: 10px; color: #afb8c1;">
                    My name is <strong>Beruang Batu Bata</strong>, and as a passionate fan, I've always believed there's a deeper story hidden within the numbers of every pro match. I created this platform to be a place where we could all become data storytellers—to swim deeper and uncover the strategic truths that define competitive play. This tool is my contribution to the community. Let's explore the real meta together.
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)
else:
    # Fallback if the logo is missing
    st.title("MLBB Pro-Scene Analytics Dashboard")


# --- State 1: Before Data is Loaded ---
if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.info("Please select tournaments in the sidebar and click 'Load Data' to begin.")
    st.header("Explore the Tools")
    st.markdown("""
    - **📊 Statistics Breakdown:** Analyze hero pick, ban, and win rates.
    - **🔎 Hero Detail Drilldown:** Deep dive into a specific hero's performance.
    - **⚔️ Head-to-Head:** Compare teams or heroes directly.
    - **🤝 Synergy & Counter Analysis:** Discover the best and worst hero pairings.
    - **🔮 Playoff Qualification Odds:** Run simulations to predict tournament outcomes.
    - **🎯 Drafting Assistant:** Get live, AI-powered draft recommendations.
    - **👑 Admin Panel:** Re-train the AI model with your selected data.
    """)

# --- State 2: After Data is Loaded ---
else:
    pooled_matches = st.session_state['pooled_matches']
    st.success(f"**Data Loaded:** Analyzing **{len(st.session_state['parsed_matches'])}** matches from **{len(st.session_state['selected_tournaments'])}** tournament(s).")
    st.header("Meta Snapshot")

    df_stats = calculate_hero_stats_for_team(pooled_matches, "All Teams")

    if not df_stats.empty:
        # Key Metrics
        most_picked = df_stats.loc[df_stats['Picks'].idxmax()]
        most_banned = df_stats.loc[df_stats['Bans'].idxmax()]
        min_games = 10
        df_min_games = df_stats[df_stats['Picks'] >= min_games]
        highest_wr = df_min_games.loc[df_min_games['Win Rate (%)'].idxmax()] if not df_min_games.empty else None

        c1, c2, c3 = st.columns(3)
        c1.metric("Most Picked Hero", most_picked['Hero'], f"{most_picked['Picks']} games")
        c2.metric("Most Banned Hero", most_banned['Hero'], f"{most_banned['Bans']} times")
        if highest_wr is not None:
            c3.metric(f"Highest Win Rate (>{min_games} games)", highest_wr['Hero'], f"{highest_wr['Win Rate (%)']:.1f}%")

        # --- FINAL FIX: Use the superior Plotly chart for a sorted, zoom-locked, professional look ---
        st.subheader("Top 10 Most Present Heroes (Pick % + Ban %)")
        df_presence = df_stats.sort_values("Presence (%)", ascending=False).head(10)
        
        # Call the custom plotting function from utils/plotting.py
        fig, config = plot_presence_bar_chart(df_presence, "Top 10 Most Present Heroes")
        
        if fig:
            st.plotly_chart(fig, use_container_width=True, config=config)
        # --- END FIX ---
    else:
        st.warning("Not enough completed match data to generate a meta snapshot.")

st.markdown("---")
# --- Liquipedia Credit using Base64 for reliability ---
liquipedia_logo_base_64 = get_image_as_base_64("Liquipedia_logo.png")
if liquipedia_logo_base_64:
    st.markdown(f"""
        <div style="text-align: center; margin-top: 2rem;">
            <p style="margin-bottom: 0.5rem;">Data Sourced From</p>
            <a href="https://liquipedia.net/mobilelegends" target="_blank">
                <img src="data:image/png;base64,{liquipedia_logo_base_64}" width="200">
            </a>
        </div>
    """, unsafe_allow_html=True)
else:
    # Fallback if the logo file is missing
    st.markdown("""
        <div style="text-align: center; margin-top: 2rem;">
            <p>Data Sourced From <a href="https://liquipedia.net/mobilelegends" target="_blank">Liquipedia</a></p>
        </div>
    """, unsafe_allow_html=True)
