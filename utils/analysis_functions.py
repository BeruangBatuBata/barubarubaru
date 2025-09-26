import pandas as pd
from collections import defaultdict, Counter
import itertools

def calculate_hero_stats_for_team(pooled_matches, team_filter="All Teams"):
    """
    Calculates hero statistics for a specific team or all teams from a pool of matches.
    """
    stats_data = defaultdict(lambda: {
        "games": 0, "wins": 0, "bans": 0, "blue_picks": 0, "blue_wins": 0,
        "red_picks": 0, "red_wins": 0
    })

    total_games = 0
    for match in pooled_matches:
        match_teams = [opp.get('name','').strip() for opp in match.get("match2opponents", [])]
        is_relevant_match = (team_filter == "All Teams" or team_filter in match_teams)
        if is_relevant_match:
            for game in match.get("match2games", []):
                if game.get("winner") and game.get("opponents") and len(game.get("opponents")) >= 2:
                    total_games += 1
    if total_games == 0:
        return pd.DataFrame()

    for match in pooled_matches:
        match_teams = [opp.get('name','').strip() for opp in match.get("match2opponents", [])]
        for game in match.get("match2games", []):
            winner = game.get("winner")
            opponents = game.get("opponents")
            if not winner or not opponents or len(opponents) < 2:
                continue

            extradata = game.get("extradata", {})
            sides = [extradata.get("team1side", "").lower(), extradata.get("team2side", "").lower()]
            
            is_team1_in_filter = team_filter == "All Teams" or (len(match_teams) > 0 and match_teams[0] == team_filter)
            is_team2_in_filter = team_filter == "All Teams" or (len(match_teams) > 1 and match_teams[1] == team_filter)
            
            # --- MODIFIED LOGIC ---
            # Process picks for each team individually
            for idx, opp_game_data in enumerate(opponents):
                is_win = str(idx + 1) == str(winner)
                side = sides[idx] if idx < len(sides) else ""
                
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

            # Process bans only once per game to avoid double counting
            if is_team1_in_filter or is_team2_in_filter:
                for i in range(1, 6):
                    if is_team1_in_filter:
                        banned_hero_1 = extradata.get(f'team1ban{i}')
                        if banned_hero_1: stats_data[banned_hero_1]["bans"] += 1
                    if is_team2_in_filter:
                        banned_hero_2 = extradata.get(f'team2ban{i}')
                        if banned_hero_2: stats_data[banned_hero_2]["bans"] += 1
            # --- END MODIFIED LOGIC ---

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
