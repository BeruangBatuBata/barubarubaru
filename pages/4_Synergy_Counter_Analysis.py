import streamlit as st
import pandas as pd
from utils.analysis_functions import analyze_synergy_combos, analyze_counter_combos, analyze_trending_synergies, analyze_synergy_combos_enhanced_with_duo, analyze_hero_counters
from utils.plotting import plot_synergy_bar_chart, plot_counter_heatmap, plot_synergy_bar_chart_interactive, create_counter_bars
from utils.sidebar import build_sidebar

# Custom CSS for better styling
st.markdown("""
    <style>
    /* Better tab styling that works with dark mode */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: inherit;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: rgba(255, 255, 255, 0.1);
        border-color: rgba(255, 255, 255, 0.2);
    }
    
    .stTabs [aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.15);
        border-bottom: 2px solid #43a047;
        border-top: none;
        border-left: 1px solid rgba(255, 255, 255, 0.2);
        border-right: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    /* Remove the default Streamlit tab underline */
    .stTabs [data-baseweb="tab-border"] {
        display: none;
    }
    
    /* Improve dataframe appearance */
    .dataframe {
        font-size: 14px;
    }
    
    /* Better styling for info/warning boxes */
    .stAlert {
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Remove any unwanted background colors from tab panel */
    .stTabs [data-baseweb="tab-panel"] {
        background-color: transparent;
    }
    
    /* Make sure tab text is readable */
    .stTabs [data-baseweb="tab"] p {
        color: inherit !important;
    }
    </style>
    """, unsafe_allow_html=True)

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

# Analysis Controls
st.subheader("Analysis Controls")
col1, col2, col3, col4 = st.columns(4)

with col1:
    analysis_mode = st.radio("Select Analysis Mode:", ["Synergy (Best Pairs)", "Anti-Synergy (Worst Pairs)", "Counters"])
with col2:
    team_filter = st.selectbox("Filter by Team:", ["All Teams"] + all_teams)
with col3:
    min_games = st.slider("Minimum Games Played Together:", 1, 20, 5)
with col4:
    top_n = st.slider("Number of Results to Show:", 5, 50, 10)

st.markdown("---")

if analysis_mode in ["Synergy (Best Pairs)", "Anti-Synergy (Worst Pairs)"]:
    find_anti = (analysis_mode == "Anti-Synergy (Worst Pairs)")
    
    # Hero filtering section
    st.subheader("Hero Filters (Optional)")
    col_hero1, col_hero2 = st.columns(2)
    
    with col_hero1:
        focus_hero1 = st.selectbox(
            "Filter for Hero 1:", 
            ["All Heroes"] + all_heroes,
            key="focus_hero1",
            help="Select first hero to filter duos"
        )
        focus_hero1 = None if focus_hero1 == "All Heroes" else focus_hero1
    
    with col_hero2:
        focus_hero2 = st.selectbox(
            "Filter for Hero 2:", 
            ["All Heroes"] + all_heroes,
            key="focus_hero2",
            help="Select second hero. If both are selected, shows only this specific duo."
        )
        focus_hero2 = None if focus_hero2 == "All Heroes" else focus_hero2
    
    # Show filtering status
    if focus_hero1 and focus_hero2:
        st.info(f"🎯 Showing stats for **{focus_hero1} + {focus_hero2}** duo only")
    elif focus_hero1:
        st.info(f"🎯 Showing all duos containing **{focus_hero1}**")
    elif focus_hero2:
        st.info(f"🎯 Showing all duos containing **{focus_hero2}**")
    
    # Get results with hero filtering
    df_results = analyze_synergy_combos_enhanced_with_duo(
        pooled_matches, team_filter, min_games, top_n, find_anti, 
        focus_hero1, focus_hero2
    )
    
    if df_results.empty:
        st.warning("No hero pairs found matching the selected criteria.")
    else:
        # Create tabs
        tab1, tab2, tab3 = st.tabs(["Top Synergies", "Trending Up 📈", "Trending Down 📉"])
        
        with tab1:
            # Display the dataframe
            df_display = df_results.reset_index(drop=True)
            df_display.index += 1
            st.dataframe(df_display, use_container_width=True)
            
            # Create and display the interactive chart
            title = f"Win Rate of {'Worst' if find_anti else 'Best'} Hero Duos"
            if focus_hero1 and focus_hero2:
                title = f"{focus_hero1} + {focus_hero2} Performance"
            elif focus_hero1:
                title += f" with {focus_hero1}"
            elif focus_hero2:
                title += f" with {focus_hero2}"
            if team_filter != "All Teams": 
                title += f" for {team_filter}"
            
            # --- MODIFICATION START ---
            fig, config = plot_synergy_bar_chart_interactive(df_results, title, chart_type='top')
            if fig:
                st.plotly_chart(fig, use_container_width=True, key="synergy_chart", config=config)
            # --- MODIFICATION END ---

        with tab2:
            st.info("📈 Showing hero duos with the biggest win rate improvements compared to last week")
            
            # Trending analysis doesn't use hero filters in this implementation
            df_trending_up = analyze_trending_synergies(pooled_matches, team_filter, min_games, top_n, direction='up')
            
            if df_trending_up.empty:
                st.warning("No improving hero pairs found. This might be because there's not enough historical data yet.")
            else:
                df_display = df_trending_up.reset_index(drop=True)
                df_display.index += 1
                st.dataframe(df_display, use_container_width=True)
                
                title = "Most Improved Hero Duos (vs Last Week)"
                if team_filter != "All Teams":
                    title += f" for {team_filter}"
                
                # --- MODIFICATION START ---
                fig, config = plot_synergy_bar_chart_interactive(df_trending_up, title, chart_type='trending_up')
                if fig:
                    st.plotly_chart(fig, use_container_width=True, key="trending_up_chart", config=config)
                # --- MODIFICATION END ---

        with tab3:
            st.info("📉 Showing hero duos with the biggest win rate declines compared to last week")
            
            df_trending_down = analyze_trending_synergies(pooled_matches, team_filter, min_games, top_n, direction='down')
            
            if df_trending_down.empty:
                st.warning("No declining hero pairs found. This might be because there's not enough historical data yet.")
            else:
                df_display = df_trending_down.reset_index(drop=True)
                df_display.index += 1
                st.dataframe(df_display, use_container_width=True)
                
                title = "Most Declined Hero Duos (vs Last Week)"
                if team_filter != "All Teams":
                    title += f" for {team_filter}"
                
                # --- MODIFICATION START ---
                fig, config = plot_synergy_bar_chart_interactive(df_trending_down, title, chart_type='trending_down')
                if fig:
                    st.plotly_chart(fig, use_container_width=True, key="trending_down_chart", config=config)
                # --- MODIFICATION END ---

elif analysis_mode == "Counters":
    # Hero selection for counter analysis
    st.subheader("Hero Matchup Analysis")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        selected_hero = st.selectbox(
            "Select a Hero to Analyze:",
            all_heroes,
            key="counter_hero_select"
        )
    
    with col2:
        st.info(f"📊 Showing matchup data for **{selected_hero}** with minimum {min_games} games played")
        if team_filter != "All Teams":
            st.caption(f"Filtered for team: {team_filter}")
    
    # Get counter data for selected hero
    counter_data = analyze_hero_counters(
        pooled_matches, 
        selected_hero, 
        min_games, 
        team_filter
    )
    
    counters_df = counter_data['counters']
    countered_by_df = counter_data['countered_by']
    
    if counters_df.empty and countered_by_df.empty:
        st.warning(f"No significant matchup data found for {selected_hero}. Try lowering the minimum games requirement.")
    else:
        # Create two columns for the results
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown(f"### ✅ {selected_hero} Counters")
            st.caption("Heroes that this hero performs well against (>55% win rate)")
            
            if not counters_df.empty:
                # Show mini dataframe
                display_df = counters_df[['Enemy Hero', 'Win Rate (%)', 'Games Against']].head(10)
                display_df = display_df.rename(columns={'Games Against': 'Games'})
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    height=min(350, 35 * len(display_df) + 38)
                )
                
                # Show bar chart
                fig = create_counter_bars(
                    counters_df.head(8),
                    f"{selected_hero} Wins Against",
                    color_scheme='green'
                )
                if fig:
                    st.plotly_chart(fig, use_container_width=True, key="counters_chart")
            else:
                st.info(f"{selected_hero} doesn't have any strong counters (>55% win rate) with {min_games}+ games")
        
        with col_right:
            st.markdown(f"### ❌ Countered By")
            st.caption("Heroes that perform well against this hero (>55% win rate)")
            
            if not countered_by_df.empty:
                # Show mini dataframe
                display_df = countered_by_df[['Enemy Hero', 'Win Rate (%)', 'Games Against']].head(10)
                display_df = display_df.rename(columns={'Games Against': 'Games'})
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    height=min(350, 35 * len(display_df) + 38)
                )
                
                # Show bar chart
                fig = create_counter_bars(
                    countered_by_df.head(8),
                    f"Heroes That Beat {selected_hero}",
                    color_scheme='red'
                )
                if fig:
                    st.plotly_chart(fig, use_container_width=True, key="countered_by_chart")
            else:
                st.info(f"No heroes have a strong advantage (>55% win rate) against {selected_hero} with {min_games}+ games")
