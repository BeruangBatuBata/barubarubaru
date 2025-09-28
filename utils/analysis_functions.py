import pandas as pd
from collections import defaultdict, Counter
import itertools
from datetime import datetime, timedelta
import streamlit as st

def calculate_hero_stats_for_team(matches_to_analyze, team_filter="All Teams"):
    """
    Calculates hero statistics for a specific team or all teams from a given pool of matches.
    """
    stats_data = defaultdict(lambda: {
        "games": 0, "wins": 0, "bans": 0, "blue_picks": 0, "blue_wins": 0,
        "red_picks": 0, "red_wins": 0
    })

    # Calculate total games from the provided match list
    total_games = sum(len(m.get("match2games", [])) for m in matches_to_analyze if any(g.get("winner") for g in m.get("match2games", [])))

    if total_games == 0:
        return pd.DataFrame()

    for match in matches_to_analyze:
        match_teams = [opp.get('name', '') for opp in match.get("match2opponents", [])]
        
        # Skip if the match is not relevant to the team filter
        if team_filter != "All Teams" and team_filter not in match_teams:
            continue

        for game in match.get("match2games", []):
            winner = game.get("winner")
            opponents = game.get("opponents")
            if not winner or not opponents or len(opponents) < 2:
                continue

            extradata = game.get("extradata", {})
            sides = [extradata.get("team1side", "").lower(), extradata.get("team2side", "").lower()]
            
            is_team1_in_filter = team_filter == "All Teams" or (len(match_teams) > 0 and match_teams[0] == team_filter)
            is_team2_in_filter = team_filter == "All Teams" or (len(match_teams) > 1 and match_teams[1] == team_filter)
            
            # Process picks for each team
            for idx, opp_game_data in enumerate(opponents):
                is_win = str(idx + 1) == str(winner)
                side = sides[idx] if idx < len(sides) else ""
                
                # Check if this side should be counted
                if (idx == 0 and is_team1_in_filter) or (idx == 1 and is_team2_in_filter):
                    for p in opp_game_data.get("players", []):
                        if isinstance(p, dict) and "champion" in p:
                            hero = p["champion"]
                            stats_data[hero]["games"] += 1
                            if is_win: stats_data[hero]["wins"] += 1
                            if side == "blue":
                                stats_data[hero]["blue_picks"] += 1
                                if is_win: stats_data[hero]["blue_wins"] += 1
                            elif side == "red":
                                stats_data[hero]["red_picks"] += 1
                                if is_win: stats_data[hero]["red_wins"] += 1

            # Process bans
            for i in range(1, 6):
                if is_team1_in_filter:
                    banned_hero_1 = extradata.get(f'team1ban{i}')
                    if banned_hero_1: stats_data[banned_hero_1]["bans"] += 1
                if is_team2_in_filter:
                    banned_hero_2 = extradata.get(f'team2ban{i}')
                    if banned_hero_2: stats_data[banned_hero_2]["bans"] += 1

    df_rows = []
    for hero, stats in stats_data.items():
        games, bans, wins = stats["games"], stats["bans"], stats["wins"]
        blue_picks, red_picks = stats["blue_picks"], stats["red_picks"]
        blue_wins, red_wins = stats["blue_wins"], stats["red_wins"]
        row = {
            "Hero": hero, "Picks": games, "Bans": bans, "Wins": wins,
            "Pick Rate (%)": round((games / total_games) * 100, 2) if total_games > 0 else 0,
            "Ban Rate (%)": round((bans / total_games) * 100, 2) if total_games > 0 else 0,
            "Presence (%)": round(((games + bans) / total_games) * 100, 2) if total_games > 0 else 0,
            "Win Rate (%)": round((wins / games) * 100, 2) if games > 0 else 0,
            "Blue Picks": blue_picks, "Blue Wins": blue_wins,
            "Blue Win Rate (%)": round((blue_wins / blue_picks) * 100, 2) if blue_picks > 0 else 0,
            "Red Picks": red_picks, "Red Wins": red_wins,
            "Red Win Rate (%)": round((red_wins / red_picks) * 100, 2) if red_picks > 0 else 0,
        }
        df_rows.append(row)
    return pd.DataFrame(df_rows)


def process_hero_drilldown_data(pooled_matches):
    hero_stats_map, all_heroes, hero_pick_rows = {}, set(), []
    for match in pooled_matches:
        t1, t2 = "", ""
        opps = match.get('match2opponents', [])
        if len(opps) >= 2:
            t1, t2 = opps[0].get('name','').strip(), opps[1].get('name','').strip()
        for game in match.get("match2games", []):
            opps_game = game.get("opponents", [])
            if len(opps_game) < 2: continue
            winner_raw = str(game.get("winner",""))
            for idx, opp in enumerate(opps_game[:2]):
                team_name = [t1, t2][idx]
                for p in opp.get("players", []):
                    if isinstance(p, dict) and "champion" in p:
                        hero, win = p["champion"], (str(idx+1) == winner_raw)
                        enemy_heroes = [ep["champion"] for ep in opps_game[1-idx].get("players", []) if isinstance(ep, dict) and "champion" in ep]
                        hero_pick_rows.append({"hero": hero, "team": team_name, "win": win, "enemy_heroes": enemy_heroes})
                        all_heroes.add(hero)
    for hero in sorted(list(all_heroes)):
        rows = [r for r in hero_pick_rows if r['hero'] == hero]
        team_stats = defaultdict(lambda: {'games': 0, 'wins': 0})
        for r in rows:
            team_stats[r['team']]['games'] += 1
            if r['win']: team_stats[r['team']]['wins'] += 1
        team_stats_rows = [{"Team": team, "Games": s['games'], "Wins": s['wins'], "Win Rate (%)": f"{(s['wins'] / s['games'] * 100) if s['games'] > 0 else 0:.2f}%"} for team, s in team_stats.items()]
        all_enemy_heroes = [eh for r in rows for eh in r.get("enemy_heroes", [])]
        matchups, win_counter = Counter(all_enemy_heroes), defaultdict(int)
        for r in rows:
            if r['win']:
                for eh in r['enemy_heroes']: win_counter[eh] += 1
        matchup_rows = [{"Opposing Hero": eh, "Times Faced": fc, f"Win Rate vs Them (%)": f"{(win_counter[eh] / fc * 100) if fc > 0 else 0:.2f}%"} for eh, fc in matchups.most_common()]
        hero_stats_map[hero] = {"per_team_df": pd.DataFrame(team_stats_rows).sort_values("Games", ascending=False), "matchups_df": pd.DataFrame(matchup_rows)}
    return sorted(list(all_heroes)), hero_stats_map

# --- MODIFICATION START ---
# This function is now expanded to handle overall stats as well.
def process_head_to_head_teams(t1_norm, t2_norm, pooled_matches):
    # H2H specific stats
    win_counts = {t1_norm: 0, t2_norm: 0}
    t1_h2h_heroes, t2_h2h_heroes = Counter(), Counter()
    t1_h2h_bans, t2_h2h_bans = Counter(), Counter()
    total_games = 0

    # Overall stats for each team
    t1_overall_heroes, t2_overall_heroes = Counter(), Counter()
    t1_overall_bans, t2_overall_bans = Counter(), Counter()

    for match in pooled_matches:
        opps = [x.get("name", "").strip() for x in match.get("match2opponents", [])]
        
        # --- Overall Stats Calculation ---
        if t1_norm in opps or t2_norm in opps:
            try:
                team_idx = opps.index(t1_norm) if t1_norm in opps else opps.index(t2_norm)
                current_team = opps[team_idx]
            except ValueError:
                continue

            for game in match.get("match2games", []):
                if len(game.get("opponents", [])) < 2: continue
                
                hero_set = {p["champion"] for p in game["opponents"][team_idx].get("players", []) if isinstance(p, dict) and "champion" in p}
                (t1_overall_heroes if current_team == t1_norm else t2_overall_heroes).update(hero_set)

                extrad = game.get("extradata", {})
                for ban_n in range(1, 6):
                    ban_hero = extrad.get(f"team{team_idx+1}ban{ban_n}")
                    if ban_hero:
                        (t1_overall_bans if current_team == t1_norm else t2_overall_bans).update([ban_hero])

        # --- H2H Stats Calculation (existing logic) ---
        if {t1_norm, t2_norm}.issubset(set(opps)):
            try:
                idx1 = opps.index(t1_norm)
            except ValueError:
                continue
            for game in match.get("match2games", []):
                winner = str(game.get("winner", ""))
                if winner.isdigit():
                    total_games += 1
                    winner_team = opps[int(winner) - 1]
                    if winner_team in win_counts: win_counts[winner_team] += 1

                extrad = game.get("extradata", {})
                for i, opp_game in enumerate(game.get("opponents", [])):
                    hero_set = {p["champion"] for p in opp_game.get("players", []) if isinstance(p, dict) and "champion" in p}
                    (t1_h2h_heroes if i == idx1 else t2_h2h_heroes).update(hero_set)
                    for ban_n in range(1, 6):
                        ban_hero = extrad.get(f"team{i+1}ban{ban_n}")
                        if ban_hero:
                            (t1_h2h_bans if i == idx1 else t2_h2h_bans).update([ban_hero])
    
    return {
        "win_counts": win_counts, 
        "total_games": total_games, 
        "t1_picks_df": pd.DataFrame(t1_h2h_heroes.most_common(8), columns=['Hero', 'Picks']), 
        "t2_picks_df": pd.DataFrame(t2_h2h_heroes.most_common(8), columns=['Hero', 'Picks']), 
        "t1_bans_df": pd.DataFrame(t1_h2h_bans.most_common(8), columns=['Hero', 'Bans']), 
        "t2_bans_df": pd.DataFrame(t2_h2h_bans.most_common(8), columns=['Hero', 'Bans']),
        "t1_overall_picks_df": pd.DataFrame(t1_overall_heroes.most_common(8), columns=['Hero', 'Picks']),
        "t2_overall_picks_df": pd.DataFrame(t2_overall_heroes.most_common(8), columns=['Hero', 'Picks']),
        "t1_overall_bans_df": pd.DataFrame(t1_overall_bans.most_common(8), columns=['Hero', 'Bans']),
        "t2_overall_bans_df": pd.DataFrame(t2_overall_bans.most_common(8), columns=['Hero', 'Bans'])
    }
# --- MODIFICATION END ---


def process_head_to_head_heroes(h1, h2, pooled_matches):
    games_with_both, win_h1, win_h2 = 0, 0, 0
    for match in pooled_matches:
        for game in match.get("match2games", []):
            opp_heroes = [ {p["champion"] for p in o.get("players", []) if isinstance(p, dict) and "champion" in p} for o in game.get("opponents", []) ]
            if len(opp_heroes) != 2: continue
            side1, side2 = opp_heroes
            if (h1 in side1 and h2 in side2) or (h2 in side1 and h1 in side2):
                games_with_both += 1
                winner = str(game.get("winner", ""))
                if (h1 in side1 and winner == "1") or (h1 in side2 and winner == "2"): win_h1 += 1
                if (h2 in side1 and winner == "1") or (h2 in side2 and winner == "2"): win_h2 += 1
    return {"total_games": games_with_both, "h1_wins": win_h1, "h2_wins": win_h2}

def analyze_synergy_combos(pooled_matches, team_filter, min_games, top_n, find_anti_synergy=False, focus_hero=None):
    duo_counter = defaultdict(lambda: {"games": 0, "wins": 0})
    for match in pooled_matches:
        teams_names = [opp.get("name", "").strip() for opp in match.get("match2opponents", [])]
        for game in match.get("match2games", []):
            winner = str(game.get("winner", ""))
            for idx, opp in enumerate(game.get("opponents", [])):
                team_name = teams_names[idx] if idx < len(teams_names) else ""
                if team_filter != "All Teams" and team_name != team_filter: continue
                players = [p["champion"] for p in opp.get("players", []) if isinstance(p, dict) and "champion" in p]
                for h1, h2 in itertools.combinations(sorted(players), 2):
                    duo_counter[(h1, h2)]["games"] += 1
                    if str(idx + 1) == winner: duo_counter[(h1, h2)]["wins"] += 1
    rows = []
    for (h1, h2), stats in duo_counter.items():
        if stats["games"] >= min_games:
            if focus_hero and focus_hero not in [h1, h2]: continue
            rows.append({"Hero 1": h1, "Hero 2": h2, "Games Together": stats["games"], "Wins": stats["wins"], "Win Rate (%)": round(stats["wins"] / stats["games"] * 100, 2)})
    df = pd.DataFrame(rows)
    return df if df.empty else df.sort_values("Win Rate (%)", ascending=find_anti_synergy).head(top_n)

def analyze_counter_combos(pooled_matches, min_games, top_n, team_filter, focus_on_team_picks):
    counter_stats = defaultdict(lambda: {"games": 0, "wins": 0})
    for match in pooled_matches:
        teams_names = [opp.get("name", "").strip() for opp in match.get("match2opponents", [])]
        for game in match.get("match2games", []):
            winner = str(game.get("winner", ""))
            opponents = game.get("opponents", [])
            if len(opponents) != 2: continue
            heroes1 = {p["champion"] for p in opponents[0].get("players", []) if isinstance(p, dict) and "champion" in p}
            heroes2 = {p["champion"] for p in opponents[1].get("players", []) if isinstance(p, dict) and "champion" in p}
            team1_name = teams_names[0] if len(teams_names) > 0 else ""
            team2_name = teams_names[1] if len(teams_names) > 1 else ""
            is_team1_focus, is_team2_focus = (team_filter == team1_name), (team_filter == team2_name)
            if team_filter != "All Teams" and not (is_team1_focus or is_team2_focus): continue
            if (team_filter == "All Teams") or (is_team1_focus and focus_on_team_picks) or (is_team2_focus and not focus_on_team_picks):
                for a in heroes1:
                    for e in heroes2:
                        counter_stats[(a, e)]["games"] += 1
                        if winner == "1": counter_stats[(a, e)]["wins"] += 1
            if (team_filter == "All Teams") or (is_team2_focus and focus_on_team_picks) or (is_team1_focus and not focus_on_team_picks):
                for a in heroes2:
                    for e in heroes1:
                        counter_stats[(a, e)]["games"] += 1
                        if winner == "2": counter_stats[(a, e)]["wins"] += 1
    rows = []
    for (ally, enemy), stats in counter_stats.items():
        if stats["games"] >= min_games:
            rows.append({"Ally Hero": ally, "Enemy Hero": enemy, "Games Against": stats["games"], "Wins": stats["wins"], "Win Rate (%)": round(stats["wins"] / stats["games"] * 100, 2)})
    df = pd.DataFrame(rows)
    return df if df.empty else df.sort_values("Win Rate (%)", ascending=False).head(top_n)

# --- NEW FUNCTION ---
def calculate_standings(played_matches):
    """Calculates wins, losses, and score differentials for each team."""
    wins = defaultdict(int)
    losses = defaultdict(int)
    diffs = defaultdict(int)
    for m in played_matches:
        winner = m.get('winner')
        teamA = m.get('teamA')
        teamB = m.get('teamB')
        scoreA = m.get('scoreA', 0)
        scoreB = m.get('scoreB', 0)

        if winner == '1':
            wins[teamA] += 1
            losses[teamB] += 1
            diffs[teamA] += scoreA - scoreB
            diffs[teamB] += scoreB - scoreA
        elif winner == '2':
            wins[teamB] += 1
            losses[teamA] += 1
            diffs[teamB] += scoreB - scoreA
            diffs[teamA] += scoreA - scoreB
    return wins, losses, diffs

def analyze_trending_synergies(pooled_matches, team_filter, min_games, top_n, direction='up'):
    """
    Analyzes hero duo performance trends comparing current week vs previous week.
    """
    
    # First, we need to separate matches by time period
    current_date = datetime.now()
    one_week_ago = current_date - timedelta(days=7)
    two_weeks_ago = current_date - timedelta(days=14)
    
    # Separate matches into two periods
    current_week_matches = []
    previous_week_matches = []
    
    for match in pooled_matches:
        # Get match date - this assumes matches have a timestamp field
        match_date = None
        
        # Try different possible date fields and formats
        if 'timestamp' in match:
            try:
                match_date = datetime.fromtimestamp(match['timestamp'])
            except:
                pass
        elif 'date' in match:
            # Try multiple date formats
            date_formats = [
                '%Y-%m-%d %H:%M:%S',  # Full datetime
                '%Y-%m-%d %H:%M',     # Date time without seconds
                '%Y-%m-%d',           # Just date
                '%Y-%m-%dT%H:%M:%S',  # ISO format
                '%Y-%m-%dT%H:%M:%SZ', # ISO format with Z
            ]
            
            for fmt in date_formats:
                try:
                    match_date = datetime.strptime(match['date'], fmt)
                    break
                except ValueError:
                    continue
                    
        elif 'datetime' in match:
            try:
                match_date = datetime.strptime(match['datetime'], '%Y-%m-%dT%H:%M:%S')
            except:
                try:
                    match_date = datetime.strptime(match['datetime'], '%Y-%m-%d %H:%M:%S')
                except:
                    pass
        
        if match_date:
            if match_date >= one_week_ago:
                current_week_matches.append(match)
            elif two_weeks_ago <= match_date < one_week_ago:
                previous_week_matches.append(match)
    
    # If no date field found or all parsing failed, fall back to using match index
    if not current_week_matches and not previous_week_matches:
        st.warning("No date information found in matches. Using match order instead (assuming newer matches are later in the list).")
        total_matches = len(pooled_matches)
        split_point = total_matches // 2
        previous_week_matches = pooled_matches[:split_point]
        current_week_matches = pooled_matches[split_point:]
    
    # Rest of the function remains the same...
    def calculate_period_stats(matches):
        duo_counter = defaultdict(lambda: {"games": 0, "wins": 0})
        
        for match in matches:
            teams_names = [opp.get("name", "").strip() for opp in match.get("match2opponents", [])]
            for game in match.get("match2games", []):
                winner = str(game.get("winner", ""))
                for idx, opp in enumerate(game.get("opponents", [])):
                    team_name = teams_names[idx] if idx < len(teams_names) else ""
                    if team_filter != "All Teams" and team_name != team_filter:
                        continue
                    
                    players = [p["champion"] for p in opp.get("players", []) 
                              if isinstance(p, dict) and "champion" in p]
                    
                    for h1, h2 in itertools.combinations(sorted(players), 2):
                        duo_counter[(h1, h2)]["games"] += 1
                        if str(idx + 1) == winner:
                            duo_counter[(h1, h2)]["wins"] += 1
        
        return duo_counter
    
    current_stats = calculate_period_stats(current_week_matches)
    previous_stats = calculate_period_stats(previous_week_matches)
    
    # Calculate trends
    trend_rows = []
    
    for duo, current_data in current_stats.items():
        if duo in previous_stats:
            prev_games = previous_stats[duo]["games"]
            curr_games = current_data["games"]
            
            # Only include if minimum games met in BOTH periods
            if prev_games >= min_games and curr_games >= min_games:
                prev_wins = previous_stats[duo]["wins"]
                curr_wins = current_data["wins"]
                
                prev_win_rate = (prev_wins / prev_games * 100) if prev_games > 0 else 0
                curr_win_rate = (curr_wins / curr_games * 100) if curr_games > 0 else 0
                change = curr_win_rate - prev_win_rate
                
                # Calculate which team uses this duo most (for current period)
                team_usage = defaultdict(int)
                for match in current_week_matches:
                    teams_names = [opp.get("name", "").strip() for opp in match.get("match2opponents", [])]
                    for game in match.get("match2games", []):
                        for idx, opp in enumerate(game.get("opponents", [])):
                            team_name = teams_names[idx] if idx < len(teams_names) else ""
                            players = [p["champion"] for p in opp.get("players", []) 
                                     if isinstance(p, dict) and "champion" in p]
                            if duo[0] in players and duo[1] in players:
                                team_usage[team_name] += 1
                
                most_used_by = max(team_usage.items(), key=lambda x: x[1])[0] if team_usage else "N/A"
                most_used_count = max(team_usage.values()) if team_usage else 0
                
                trend_rows.append({
                    "Hero 1": duo[0],
                    "Hero 2": duo[1],
                    "Current Win Rate (%)": round(curr_win_rate, 2),
                    "Previous Win Rate (%)": round(prev_win_rate, 2),
                    "Change (%)": round(change, 2),
                    "Current Games": curr_games,
                    "Previous Games": prev_games,
                    "Most Used By": f"{most_used_by} ({most_used_count}g)"
                })
    
    # Create DataFrame and sort
    df = pd.DataFrame(trend_rows)
    
    if df.empty:
        return df
    
    # Sort by change (descending for 'up', ascending for 'down')
    df = df.sort_values("Change (%)", ascending=(direction == 'down'))
    
    # Filter based on direction
    if direction == 'up':
        df = df[df["Change (%)"] > 0]
    else:  # direction == 'down'
        df = df[df["Change (%)"] < 0]
    
    return df.head(top_n)


# Also update the original analyze_synergy_combos to include extra data for enhanced tooltips
def analyze_synergy_combos_enhanced(pooled_matches, team_filter, min_games, top_n, find_anti_synergy=False, focus_hero=None):
    """
    Enhanced version that includes additional data for tooltips.
    """
    from datetime import datetime
    
    # Get base results with enhanced tracking
    duo_counter = defaultdict(lambda: {
        "games": 0, 
        "wins": 0, 
        "teams": defaultdict(int), 
        "last_played": None,
        "match_dates": []  # Track all match dates for better last played info
    })
    
    for match in pooled_matches:
        teams_names = [opp.get("name", "").strip() for opp in match.get("match2opponents", [])]
        
        # Try to get match date
        match_date = None
        if 'timestamp' in match:
            try:
                match_date = datetime.fromtimestamp(match['timestamp'])
            except:
                pass
        elif 'date' in match:
            # Handle the date format we discovered: YYYY-MM-DD HH:MM:SS
            try:
                match_date = datetime.strptime(match['date'], '%Y-%m-%d %H:%M:%S')
            except:
                # Try other formats as fallback
                date_formats = ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']
                for fmt in date_formats:
                    try:
                        match_date = datetime.strptime(match['date'], fmt)
                        break
                    except:
                        continue
        
        for game in match.get("match2games", []):
            winner = str(game.get("winner", ""))
            for idx, opp in enumerate(game.get("opponents", [])):
                team_name = teams_names[idx] if idx < len(teams_names) else ""
                if team_filter != "All Teams" and team_name != team_filter:
                    continue
                
                players = [p["champion"] for p in opp.get("players", []) 
                          if isinstance(p, dict) and "champion" in p]
                
                for h1, h2 in itertools.combinations(sorted(players), 2):
                    if focus_hero and focus_hero not in [h1, h2]:
                        continue
                    
                    duo_key = (h1, h2)
                    duo_counter[duo_key]["games"] += 1
                    
                    if str(idx + 1) == winner:
                        duo_counter[duo_key]["wins"] += 1
                    
                    # Track team usage
                    if team_name:  # Only count if we have a team name
                        duo_counter[duo_key]["teams"][team_name] += 1
                    
                    # Track match dates
                    if match_date:
                        duo_counter[duo_key]["match_dates"].append(match_date)
    
    # Build results
    rows = []
    current_time = datetime.now()
    
    for (h1, h2), stats in duo_counter.items():
        if stats["games"] >= min_games:
            # Find most used by team
            if stats["teams"]:
                most_used_team = max(stats["teams"].items(), key=lambda x: x[1])
                most_used_by = f"{most_used_team[0]} ({most_used_team[1]}g)"
            else:
                most_used_by = "N/A"
            
            # Calculate last played
            last_played = "N/A"
            if stats["match_dates"]:
                # Sort dates and get the most recent
                stats["match_dates"].sort(reverse=True)
                last_match_date = stats["match_dates"][0]
                
                # Calculate days ago
                if isinstance(last_match_date, datetime):
                    # Handle future dates (your data is from 2025)
                    if last_match_date > current_time:
                        last_played = "Future match"
                    else:
                        days_diff = (current_time - last_match_date).days
                        if days_diff == 0:
                            hours_diff = (current_time - last_match_date).total_seconds() / 3600
                            if hours_diff < 1:
                                last_played = "Less than 1 hour ago"
                            elif hours_diff < 24:
                                last_played = f"{int(hours_diff)} hours ago"
                            else:
                                last_played = "Today"
                        elif days_diff == 1:
                            last_played = "Yesterday"
                        elif days_diff < 7:
                            last_played = f"{days_diff} days ago"
                        elif days_diff < 30:
                            weeks = days_diff // 7
                            last_played = f"{weeks} week{'s' if weeks > 1 else ''} ago"
                        else:
                            months = days_diff // 30
                            last_played = f"{months} month{'s' if months > 1 else ''} ago"
            
            rows.append({
                "Hero 1": h1,
                "Hero 2": h2,
                "Games Together": stats["games"],
                "Wins": stats["wins"],
                "Win Rate (%)": round(stats["wins"] / stats["games"] * 100, 2),
                "Most Used By": most_used_by,
                "Last Played": last_played
            })
    
    df = pd.DataFrame(rows)
    
    if df.empty:
        return df
    
    # Sort by win rate
    return df.sort_values("Win Rate (%)", ascending=find_anti_synergy).head(top_n)

def analyze_hero_counters(pooled_matches, selected_hero, min_games, team_filter="All Teams"):
    """
    Analyzes matchup data for a specific hero.
    
    Returns:
        dict with 'counters' (heroes this hero beats) and 'countered_by' (heroes that beat this)
    """
    counters_data = defaultdict(lambda: {"games": 0, "wins": 0, "as_ally": 0, "as_enemy": 0})
    
    for match in pooled_matches:
        teams_names = [opp.get("name", "").strip() for opp in match.get("match2opponents", [])]
        
        for game in match.get("match2games", []):
            winner = str(game.get("winner", ""))
            opponents = game.get("opponents", [])
            
            if len(opponents) != 2 or not winner.isdigit():
                continue
            
            # Get heroes for each team
            team1_heroes = {p["champion"] for p in opponents[0].get("players", []) 
                           if isinstance(p, dict) and "champion" in p}
            team2_heroes = {p["champion"] for p in opponents[1].get("players", []) 
                           if isinstance(p, dict) and "champion" in p}
            
            # Check if selected hero is in either team
            hero_in_team1 = selected_hero in team1_heroes
            hero_in_team2 = selected_hero in team2_heroes
            
            if not (hero_in_team1 or hero_in_team2):
                continue
            
            # Apply team filter
            if team_filter != "All Teams":
                team1_name = teams_names[0] if len(teams_names) > 0 else ""
                team2_name = teams_names[1] if len(teams_names) > 1 else ""
                
                if hero_in_team1 and team1_name != team_filter:
                    continue
                if hero_in_team2 and team2_name != team_filter:
                    continue
            
            # Determine which team has our hero and if they won
            if hero_in_team1:
                hero_team = 1
                enemy_heroes = team2_heroes
                hero_won = (winner == "1")
            else:
                hero_team = 2
                enemy_heroes = team1_heroes
                hero_won = (winner == "2")
            
            # Record matchup data
            for enemy in enemy_heroes:
                counters_data[enemy]["games"] += 1
                if hero_won:
                    counters_data[enemy]["wins"] += 1
                counters_data[enemy]["as_ally"] = 0  # This hero was our ally
                counters_data[enemy]["as_enemy"] = 1  # This hero was enemy
    
    # Build results
    counters_rows = []
    countered_by_rows = []
    
    for enemy_hero, stats in counters_data.items():
        if stats["games"] >= min_games:
            win_rate = round(stats["wins"] / stats["games"] * 100, 2)
            
            row = {
                "Enemy Hero": enemy_hero,
                "Games Against": stats["games"],
                "Wins": stats["wins"],
                "Losses": stats["games"] - stats["wins"],
                "Win Rate (%)": win_rate
            }
            
            # If our hero has >55% win rate, it counters the enemy
            if win_rate > 55:
                counters_rows.append(row)
            # If our hero has <45% win rate, it's countered by the enemy
            elif win_rate < 45:
                # Flip the perspective for "countered by"
                row["Win Rate (%)"] = round(100 - win_rate, 2)  # Show enemy's win rate
                countered_by_rows.append(row)
    
    # Create DataFrames - handle empty cases
    if counters_rows:
        counters_df = pd.DataFrame(counters_rows).sort_values("Win Rate (%)", ascending=False)
    else:
        # Create empty DataFrame with correct columns
        counters_df = pd.DataFrame(columns=["Enemy Hero", "Games Against", "Wins", "Losses", "Win Rate (%)"])
    
    if countered_by_rows:
        countered_by_df = pd.DataFrame(countered_by_rows).sort_values("Win Rate (%)", ascending=False)
    else:
        # Create empty DataFrame with correct columns
        countered_by_df = pd.DataFrame(columns=["Enemy Hero", "Games Against", "Wins", "Losses", "Win Rate (%)"])
    
    return {
        "counters": counters_df,
        "countered_by": countered_by_df
    }

def analyze_synergy_combos_enhanced_with_duo(pooled_matches, team_filter, min_games, top_n, 
                                            find_anti_synergy=False, focus_hero1=None, focus_hero2=None):
    """
    Enhanced version that can filter for specific hero duos.
    If both focus_hero1 and focus_hero2 are specified, only shows that specific pair.
    If only one is specified, shows all pairs containing that hero.
    """
    from datetime import datetime
    
    duo_counter = defaultdict(lambda: {
        "games": 0, 
        "wins": 0, 
        "teams": defaultdict(int), 
        "last_played": None,
        "match_dates": []
    })
    
    for match in pooled_matches:
        teams_names = [opp.get("name", "").strip() for opp in match.get("match2opponents", [])]
        
        # Try to get match date
        match_date = None
        if 'timestamp' in match:
            try:
                match_date = datetime.fromtimestamp(match['timestamp'])
            except:
                pass
        elif 'date' in match:
            try:
                match_date = datetime.strptime(match['date'], '%Y-%m-%d %H:%M:%S')
            except:
                date_formats = ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']
                for fmt in date_formats:
                    try:
                        match_date = datetime.strptime(match['date'], fmt)
                        break
                    except:
                        continue
        
        for game in match.get("match2games", []):
            winner = str(game.get("winner", ""))
            for idx, opp in enumerate(game.get("opponents", [])):
                team_name = teams_names[idx] if idx < len(teams_names) else ""
                if team_filter != "All Teams" and team_name != team_filter:
                    continue
                
                players = [p["champion"] for p in opp.get("players", []) 
                          if isinstance(p, dict) and "champion" in p]
                
                for h1, h2 in itertools.combinations(sorted(players), 2):
                    # Apply hero filters
                    if focus_hero1 and focus_hero2:
                        # Both heroes specified - only show this exact pair
                        if not ({focus_hero1, focus_hero2} == {h1, h2}):
                            continue
                    elif focus_hero1:
                        # Only hero1 specified - must contain this hero
                        if focus_hero1 not in [h1, h2]:
                            continue
                    elif focus_hero2:
                        # Only hero2 specified - must contain this hero
                        if focus_hero2 not in [h1, h2]:
                            continue
                    
                    duo_key = (h1, h2)
                    duo_counter[duo_key]["games"] += 1
                    
                    if str(idx + 1) == winner:
                        duo_counter[duo_key]["wins"] += 1
                    
                    # Track team usage
                    if team_name:
                        duo_counter[duo_key]["teams"][team_name] += 1
                    
                    # Track match dates
                    if match_date:
                        duo_counter[duo_key]["match_dates"].append(match_date)
    
    # Build results
    rows = []
    current_time = datetime.now()
    
    for (h1, h2), stats in duo_counter.items():
        if stats["games"] >= min_games:
            # Find most used by team
            if stats["teams"]:
                most_used_team = max(stats["teams"].items(), key=lambda x: x[1])
                most_used_by = f"{most_used_team[0]} ({most_used_team[1]}g)"
            else:
                most_used_by = "N/A"
            
            # Calculate last played
            last_played = "N/A"
            if stats["match_dates"]:
                stats["match_dates"].sort(reverse=True)
                last_match_date = stats["match_dates"][0]
                
                if isinstance(last_match_date, datetime):
                    if last_match_date > current_time:
                        last_played = "Future match"
                    else:
                        days_diff = (current_time - last_match_date).days
                        if days_diff == 0:
                            hours_diff = (current_time - last_match_date).total_seconds() / 3600
                            if hours_diff < 1:
                                last_played = "Less than 1 hour ago"
                            elif hours_diff < 24:
                                last_played = f"{int(hours_diff)} hours ago"
                            else:
                                last_played = "Today"
                        elif days_diff == 1:
                            last_played = "Yesterday"
                        elif days_diff < 7:
                            last_played = f"{days_diff} days ago"
                        elif days_diff < 30:
                            weeks = days_diff // 7
                            last_played = f"{weeks} week{'s' if weeks > 1 else ''} ago"
                        else:
                            months = days_diff // 30
                            last_played = f"{months} month{'s' if months > 1 else ''} ago"
            
            rows.append({
                "Hero 1": h1,
                "Hero 2": h2,
                "Games Together": stats["games"],
                "Wins": stats["wins"],
                "Win Rate (%)": round(stats["wins"] / stats["games"] * 100, 2),
                "Most Used By": most_used_by,
                "Last Played": last_played
            })
    
    df = pd.DataFrame(rows)
    
    if df.empty:
        return df
    
    # Sort by win rate
    return df.sort_values("Win Rate (%)", ascending=find_anti_synergy).head(top_n)
