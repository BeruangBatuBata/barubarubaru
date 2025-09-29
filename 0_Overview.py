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

# --- HOW TO USE SECTION (MOST DETAILED) ---
with st.expander("ℹ️ How to Use This Dashboard: A Detailed Guide", expanded=True):
    st.markdown("""
        Welcome to your advanced analytics suite for professional MLBB! This guide will walk you through each feature step-by-step.

        ### **Step 1: Loading Tournament Data (Mandatory First Step)**
        The dashboard is powerless without data. Follow these steps to get started:
        1.  **Navigate the Sidebar:** On the left of your screen is the main sidebar. Find the section titled **"Tournament Selection"**.
        2.  **Select Tournaments:**
            - You can browse tournaments grouped **By Region**, **By Split**, or **By League**.
            - Check the boxes next to the tournaments you want to include in your analysis. You can select a single tournament for a focused view or multiple tournaments to analyze a broader meta.
        3.  **Load the Data:** After selecting your tournaments, click the **"Load Data"** button at the bottom of the sidebar.
        4.  **Confirmation:** The main page will display a success message confirming that the data has been loaded and is ready for analysis. You can now navigate to any page in the sidebar.

        ---

        ### **Feature-by-Feature Guide**

        #### `📊 Statistics Breakdown`
        * **Purpose:** To get a high-level overview of the hero meta based on your selected data.
        * **How to Use:**
            * The main view is a comprehensive table showing every hero's **Pick Rate, Ban Rate, Win Rate, and Presence** (a hero's combined pick and ban rate, indicating their meta relevance).
            * **Filter by Team:** Use this dropdown to isolate stats for a single team, revealing their most picked and most successful heroes.
            * **Filter by Stage:** When analyzing a single tournament, this dropdown appears, allowing you to separate **Group Stage** stats from **Playoffs** stats to see how the meta evolves.
            * **Sort and Download:** You can sort the table by any column to quickly identify top-tier heroes (e.g., sort by "Win Rate (%)" to see who wins the most). Use the "Download as CSV" button to export your current view for offline analysis.

        #### `🔎 Hero Detail Drilldown`
        * **Purpose:** To conduct a granular analysis of a single hero's performance.
        * **How to Use:**
            * **Select a Hero:** Choose any hero from the dropdown menu.
            * **Performance by Team:** This table shows you every team that has played the selected hero. It helps answer questions like, "Which team has the best record on Fanny?" or "Who plays the most Valentina?"
            * **Performance Against Opposing Heroes:** This table details the hero's one-on-one performance against every other hero they've faced. It's perfect for understanding specific matchups, such as "What is Chou's win rate when playing against Arlott?"

        #### `⚔️ Head-to-Head`
        * **Purpose:** For direct comparisons between two entities.
        * **How to Use:**
            * **Team vs. Team:**
                - Select two teams from the dropdowns.
                - The dashboard will immediately show their direct match history (e.g., "Team A has a 3-1 record against Team B").
                - The tables below reveal crucial strategic data: *what did each team prioritize picking and banning when they faced each other?* This is key to understanding their strategic approach to a specific rival.
            * **Hero vs. Hero:**
                - Select two heroes.
                - The dashboard calculates their win rate when they are on opposing teams, directly answering "In a matchup between Hero X and Hero Y, who wins more often?"

        #### `🤝 Synergy & Counter Analysis`
        * **Purpose:** To uncover the most and least effective hero pairings and counters.
        * **How to Use:**
            * **Analysis Mode:**
                - **Synergy (Best Pairs):** Finds duos with the highest win rates when on the same team.
                - **Anti-Synergy (Worst Pairs):** Finds duos with the lowest win rates.
                - **Counters:** Allows you to select a single hero and see which heroes they are statistically strong against (`Counters`) and weak against (`Countered By`).
            * **Filters:** Use the filters for **Team** and **Minimum Games Played** to refine the results and ensure statistical significance.
            * **Trending Tabs:** The **"Trending Up 📈"** and **"Trending Down 📉"** tabs are unique; they compare a duo's performance in the last week versus the week before, highlighting pairs that are rising or falling in the current meta.

        #### `🔮 Playoff Qualification Odds`
        * **Purpose:** A predictive tool to forecast tournament outcomes. **Best used with a single, ongoing tournament loaded.**
        * **How to Use:**
            * **Setup:** First, tell the simulator the tournament format (Single Table or Groups). If it's a group stage, assign the teams to their correct groups. The app will remember these settings for next time.
            * **"What-If" Scenarios:** The tool will display all remaining matches. You can leave them as "Random" or force a specific outcome (e.g., predict that Team A will win 2-0).
            * **Simulate:** The simulator runs thousands of possibilities for the "Random" matches.
            * **Results:** The output is a probability table showing each team's chances of finishing in a specific bracket (e.g., 80% chance for Upper Bracket, 15% for Playoffs, 5% for Elimination). This is perfect for tracking a team's journey through a tournament.

        #### `🎯 Drafting Assistant`
        * **Purpose:** An AI-powered co-pilot for analyzing a live or historical draft.
        * **How to Use:**
            * **Setup:** Select the Blue and Red teams and the series format (e.g., Best of 3).
            * **Drafting:** As a draft unfolds, use the dropdown menus to input the bans and picks for each team in the correct role slots.
            * **Live Probability:** With each pick/ban, the AI updates two win probability bars: one that considers team history and another that is purely based on the draft composition. It also shows the odds for the final series score (e.g., 2-0 vs 2-1).
            * **AI Suggestions:** For a live draft, you can toggle **"Show AI Suggestions"**. The AI will recommend the most statistically advantageous hero to either **PICK** for your team or **BAN** from the enemy team based on the current state of the draft.

        #### `👑 Admin Panel`
        * **Purpose:** To keep the AI model sharp and up-to-date.
        * **How to Use:**
            * After loading a new, large set of tournament data (e.g., from a completed season), navigate to this page.
            * Click **"Train New AI Model"**. The system will use all the loaded match data to retrain the machine learning model.
            * **Download & Deploy:** Once training is complete, download the two new model files (`.json` and `.assets`) and upload them to your GitHub repository to make the updated AI live for all users.
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

# --- Final, Polished Footer ---
st.markdown("---")

# --- SVG Icons (encoded in Base64 for reliability) ---
github_icon_svg = "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ"
mail_icon_svg = "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h"

liquipedia_logo_base_64 = get_image_as_base_64("Liquipedia_logo.png")

if liquipedia_logo_base_64:
    st.markdown(f"""
        <style>
            .footer-wrapper {{
                padding: 2.5rem 1rem 1.5rem 1rem;
                background-color: #262730;
                border-top: 1px solid #3a3b44;
                color: #afb8c1;
                text-align: center;
            }}
            .footer-wrapper a {{
                color: #4A90E2;
                text-decoration: none;
                font-weight: 500;
            }}
            .footer-wrapper a:hover {{
                text-decoration: underline;
            }}
            .footer-credits {{
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 1rem;
                margin-bottom: 1rem;
            }}
            .footer-credits .separator {{
                color: #555;
            }}
            .footer-disclaimer {{
                font-size: 0.8em;
                font-style: italic;
                margin-bottom: 1.5rem;
            }}
            .footer-icon {{
                vertical-align: middle;
                margin-right: 0.3rem;
                opacity: 0.8;
            }}
        </style>
        <div class="footer-wrapper">
            <div class="footer-disclaimer">
                This is a fan-made project and is not affiliated with Moonton or any official MLBB esports league.
            </div>
            <div class="footer-credits">
                <span>
                    <img src="data:image/svg+xml;base64,{github_icon_svg}" width="16" class="footer-icon">
                    Created by <a href="https://github.com/beruangbatubata" target="_blank">Beruang Batu Bata</a>
                </span>
                <span class="separator">|</span>
                <span>
                    <img src="data:image/svg+xml;base64,{bug_icon_svg}" width="16" class="footer-icon">
                    <a href="https://github.com/beruangbatubata/barubaru/issues" target="_blank">Report an Issue</a>
                </span>
                <span class="separator">|</span>
                <span>Version 1.0</span>
            </div>
            <div>
                <p style="margin-bottom: 0.5rem;">Data Sourced From <a href="https://liquipedia.net/mobilelegends" target="_blank">Liquipedia</a> and licensed under <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank">CC BY-SA 3.0</a>.</p>
                <a href="https://liquipedia.net/mobilelegends" target="_blank">
                    <img src="data:image/png;base64,{liquipedia_logo_base_64}" width="140">
                </a>
            </div>
        </div>
    """, unsafe_allow_html=True)
else:
    # Fallback if the logo file is missing
     st.markdown("""
        <div style="text-align: center; margin-top: 2rem; font-size: 0.875em; color: #afb8c1;">
            <p>Data Sourced From <a href="https://liquipedia.net/mobilelegends" target="_blank">Liquipedia</a> and licensed under <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank">CC BY-SA 3.0</a>.</p>
            <p>Created with ❤️ by Beruang Batu Bata | Version 1.0</p>
        </div>
    """, unsafe_allow_html=True)
