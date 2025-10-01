import streamlit as st
import requests
import os
import json
from utils.tournaments import ALL_TOURNAMENTS

# --- CONSTANTS ---
# The hardcoded key is gone. We will access it securely inside the function.
BASE_PARAMS = {"wiki": "mobilelegends", "limit": 500}

# This function is unchanged
def clear_cache_for_live_tournaments(selected_live_keys):
    """Finds and deletes cache files and returns the count of cleared files."""
    cleared_count = 0
    for key in selected_live_keys:
        if key in ALL_TOURNAMENTS and ALL_TOURNAMENTS[key]['live']:
            tournament_path = ALL_TOURNAMENTS[key]['path']
            cache_key = f"matches_{tournament_path.replace('/', '_')}.json"
            cache_dir = "data" 
            filepath = os.path.join(cache_dir, cache_key)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    cleared_count += 1
                except Exception as e:
                    st.warning(f"Could not remove cache for {key}: {e}")
    return cleared_count

# --- MODIFIED FUNCTION ---
@st.cache_data(ttl=3600)
def fetch_from_api(tournament_path):
    """Unified function to fetch data from the Liquipedia API."""
    try:
        # Securely access the API key from st.secrets
        api_key = st.secrets["LIQUIPEDIA_API_KEY"]
        
        # Build headers just before the request is made
        headers = {
            "Authorization": f"Apikey {api_key}", 
            "User-Agent": "HeroStatsCollector/1.0"
        }
        
        params = BASE_PARAMS.copy()
        params['conditions'] = f"[[parent::{tournament_path}]]"
        url = "https://api.liquipedia.net/api/v3/match"
        
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json().get("result", [])
        
    except KeyError:
        # This error is specifically for when the secret isn't set
        st.error("API key not found. Please add 'LIQUIPEDIA_API_KEY' to your Streamlit secrets.")
        return {'error': 'API key not configured.'}
    except Exception as e:
        return {'error': str(e)}

# --- MODIFIED FUNCTION ---
def load_tournament_data(tournament_name):
    """Loads data from local file or fetches from API."""
    tournament_info = ALL_TOURNAMENTS[tournament_name]
    is_live = tournament_info.get('live', False)
    path = tournament_info['path']
    filename = f"{tournament_name.replace(' ', '_').replace('/', '_')}.json"
    data_dir = "data"
    filepath = os.path.join(data_dir, filename)
    os.makedirs(data_dir, exist_ok=True)

    # Always fetch live data from the API
    if is_live:
        data = fetch_from_api(path)
        if isinstance(data, dict) and 'error' in data:
            st.error(f"Failed to fetch live data for {tournament_name}: {data['error']}")
            return []
        st.toast(f"Fetched {len(data)} live matches for {tournament_name} from API.", icon="📡")
        return data

    # For non-live data, try loading from file first
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        st.toast(f"Loaded {len(data)} matches for {tournament_name} from file.", icon="📄")
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        st.toast(f"Local data for {tournament_name} not found or invalid. Fetching from API...", icon="☁️")
        data = fetch_from_api(path)
        
        if isinstance(data, dict) and 'error' in data:
            st.error(f"Failed to fetch {tournament_name}: {data['error']}")
            return []
            
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            st.toast(f"Saved API data for {tournament_name} locally.", icon="💾")
        except Exception as e:
            st.warning(f"Could not save data for {tournament_name}: {e}")
        return data
    except Exception as e:
        st.error(f"Error reading local file for {tournament_name}: {e}")
        return []
