import streamlit as st
from utils.sidebar import build_sidebar
from utils.analysis_functions import calculate_hero_stats_for_team
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

# --- HOW TO USE SECTION (DETAILED) ---
with st.expander("ℹ️ How to Use This Dashboard", expanded=True):
    st.markdown("""
        Welcome to the MLBB Pro-Scene Analytics Dashboard! Here’s a detailed guide to help you unlock its full potential.

        ### **Step 1: Load Your Data**
        This is the most important step! No analysis can be done without data.
        - **1. Use the Sidebar:** On the left, find the **"Tournament Selection"** section.
        - **2. Choose Tournaments:** Click to expand the tabs and select the tournaments you wish to analyze. You can mix and match from different regions, splits, or leagues.
        - **3. Load Data:** Scroll to the bottom of the sidebar and click the big **"Load Data"** button.
        - **4. Wait for Confirmation:** A success message will appear on this page, confirming how many matches have been loaded. You are now ready to explore!

        ---

        ### **Feature Breakdown**
        Once your data is loaded, navigate through the pages in the sidebar to access these powerful tools:

        - **`📊 Statistics Breakdown`**
          - **What it is:** The main statistics page for all heroes.
          - **How to use it:**
            - View a table with key metrics: **Picks, Bans, Win Rate (WR%), and Presence %** (Pick% + Ban%).
            - Use the **"Filter by Team"** dropdown to see stats for a single team.
            - If you loaded only one tournament, you can also **"Filter by Stage"** (e.g., Group Stage vs. Playoffs).
            - Click the column headers or use the "Sort by" dropdown to rank heroes and identify the meta.

        - **`🔎 Hero Detail Drilldown`**
          - **What it is:** A deep-dive analysis page for a single hero.
          - **How to use it:**
            - Select a hero from the dropdown menu.
            - **Performance by Team Table:** See which teams play this hero the most and which have the highest win rate with it.
            - **Performance Against Opposing Heroes Table:** Discover which enemy heroes your selected hero statistically wins or loses against.

        - **`⚔️ Head-to-Head`**
          - **What it is:** A direct comparison tool.
          - **How to use it:**
            - **Team vs. Team:** Select two teams to see their direct match history, including the series score. You can also view their most common picks and bans specifically in matches against each other.
            - **Hero vs. Hero:** Select two heroes to find out how many times they have played on opposing teams and which one has a higher win rate in that matchup.

        - **`🤝 Synergy & Counter Analysis`**
          - **What it is:** A tool to find powerful hero combinations and matchups.
          - **How to use it:**
            - **Synergy/Anti-Synergy Mode:** Find hero pairs that have the highest (or lowest) win rates when played on the same team.
            - **Counters Mode:** Select a hero to see which heroes they perform best against (`Counters`) and worst against (`Countered By`).
            - **Filters:** You can refine your analysis by team, minimum number of games played together, and number of results to show.
            - **Trending Tabs:** Check the "Trending Up" and "Trending Down" tabs to see which hero duos have improved or declined in performance recently.

        - **`🔮 Playoff Qualification Odds`**
          - **What it is:** A powerful Monte Carlo simulator for tournament outcomes.
          - **How to use it:**
            - This page works best when you load a single, ongoing tournament.
            - **Standings:** View the current tournament standings based on completed matches.
            - **What-If Scenarios:** For upcoming matches, you can manually set a winner (e.g., Team A wins 2-0).
            - **Run Simulation:** The tool runs thousands of simulations of the remaining games to calculate the final probability for each team to land in a specific bracket (e.g., Upper Bracket, Playoffs, Eliminated).

        - **`🎯 Drafting Assistant`**
          - **What it is:** An AI tool that analyzes drafts in real-time.
          - **How to use it:**
            - **Live Draft:** Select the Blue and Red teams. As a draft happens live, fill in the picks and bans for each team using the dropdowns.
            - **Live Analysis:** The AI will continuously update the win probability for each side based on the heroes drafted and the historical performance of the teams.
            - **AI Suggestions:** Toggle "Show AI Suggestions" to get recommendations for the next best hero to pick or ban.
            - **Review Past Games:** You can also load any previously played game from your dataset to analyze its draft with the AI.

        - **`👑 Admin Panel`**
          - **What it is:** The control panel for the AI model.
          - **How to use it:** After loading a large and recent dataset, you can click **"Train New AI Model"** to update the AI with the latest meta. This ensures its predictions remain accurate.
    """)
# --- END SECTION ---


# --- State 1: Before Data is Loaded ---
if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.info("Please select tournaments in the sidebar and click 'Load Data' to begin.")

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

        # --- MODIFICATION START: Use st.bar_chart with explicit x and y to preserve sort order ---
        st.subheader("Top 10 Most Present Heroes (Pick % + Ban %)")
        df_presence = df_stats.sort_values(by="Presence (%)", ascending=False).head(10)
        # By setting 'x' and 'y' explicitly, st.bar_chart will respect the DataFrame's sort order
        st.bar_chart(df_presence, x='Hero', y=['Pick Rate (%)', 'Ban Rate (%)'],sort=False)
        # --- MODIFICATION END ---
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
