import pandas as pd
import json
from utils.hero_data import HERO_PROFILES, HERO_DAMAGE_TYPE

# --- TEAM NORMALIZATION AND PARSING FUNCTIONS ---
TEAM_NORMALIZATION = {
    "AP.Bren": "Falcons AP.Bren",
    "Falcons AP.Bren": "Falcons AP.Bren",
    "ECHO": "Team Liquid PH",
    "Team Liquid PH": "Team Liquid PH",
}
def normalize_team(n):
    return TEAM_NORMALIZATION.get((n or "").strip(), (n or "").strip())

# --- MODIFICATION START: New function to classify stages ---
def get_stage_info(pagename, section):
    """
    Classifies a match and derives a clean stage name from pagename or section.
    Returns: A tuple of (stage_type, stage_priority)
    """
    # Prefer the 'section' field if it's structured like a path
    source_string = section
    if '/' not in source_string:
        source_string = pagename  # Fallback to pagename

    # Extract the last part of the path and clean it up
    if '/' in source_string:
        stage_type = source_string.split('/')[-1].replace('_', ' ').strip()
    else:
        # If no slashes, use the original string but clean it
        stage_type = source_string.replace('_', ' ').strip()

    # Determine priority based on keywords in the derived stage_type
    stage_type_lower = stage_type.lower()
    
    stage_priority = 99 # Default priority
    if "playoffs" in stage_type_lower or "finals" in stage_type_lower or "knockout" in stage_type_lower:
        stage_priority = 40
    elif "rumble" in stage_type_lower or "play-in" in stage_type_lower:
        stage_priority = 30
    elif "stage 2" in stage_type_lower:
        stage_priority = 20
    elif "regular season" in stage_type_lower or "group" in stage_type_lower or "swiss" in stage_type_lower or "week" in stage_type_lower or "stage 1" in stage_type_lower:
        stage_priority = 10
    
    # If stage_type is empty after all that, provide a fallback name
    if not stage_type:
        stage_type = "Uncategorized"

    return stage_type, stage_priority
# --- MODIFICATION END ---

def parse_matches(matches_raw):
    """
    Parses and enriches the raw match data from the API.
    It adds stage information without flattening the data structure.
    """
    enriched_matches = []
    for m in matches_raw:
        if not isinstance(m, dict):
            continue
        
        # Normalize team names directly in the opponents list
        if "match2opponents" in m:
            for opp in m["match2opponents"]:
                opp["name"] = normalize_team(opp.get("name"))

        pagename = m.get("pagename", "")
        section = m.get("section", "")
        
        # Add stage info to the top level of the match dictionary
        stage_type, stage_priority = get_stage_info(pagename, section)
        m['stage_type'] = stage_type
        m['stage_priority'] = stage_priority
        
        enriched_matches.append(m)

    return enriched_matches
