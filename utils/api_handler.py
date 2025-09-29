import streamlit as st
import requests
import os
import json

# --- CONSTANTS ---
API_KEY = "pIfcpzOZFhSaLGG5elRsP3s9rnL8NPr1Xt194SxPrryEfvb3cOvvNVj0V83nLAyk0FNuI6HtLCGfNvYpyHLjrKExyvOFYEQMsxyjnrk9H1KDU84ahTW3JnRF9FLIueN2"
HEADERS = {"Authorization": f"Apikey {API_KEY}", "User-Agent": "HeroStatsCollector/1.0"}
BASE_PARAMS = {"wiki": "mobilelegends", "limit": 500}

# --- MODIFICATION START: Added 'league' and 'split' keys ---
ALL_TOURNAMENTS = {
    'MPL ID Season 14': {'path': 'MPL/Indonesia/Season_14', 'region': 'Indonesia', 'year': 2024, 'live': False, 'league': 'MPL Indonesia', 'split': '2024 Split 2'},
    'MPL PH Season 13': {'path': 'MPL/Philippines/Season_13', 'region': 'Philippines', 'year': 2024, 'live': False, 'league': 'MPL Philippines', 'split': '2024 Split 1'},
    'MSC 2024': {'path': 'MSC/2024', 'region': 'International', 'year': 2024, 'live': False, 'league': 'MSC (Mid-Season Cup)', 'split': '2024 Split 2'},
    'MPL ID Season 15': {'path': 'MPL/Indonesia/Season_15', 'region': 'Indonesia', 'year': 2025, 'live': False, 'league': 'MPL Indonesia', 'split': '2025 Split 1'},
    'MPL PH Season 15': {'path': 'MPL/Philippines/Season_15', 'region': 'Philippines', 'year': 2025, 'live': False, 'league': 'MPL Philippines', 'split': '2025 Split 1'},
    'MPL ID Season 16': {'path': 'MPL/Indonesia/Season_16', 'region': 'Indonesia', 'year': 2025, 'live': True, 'league': 'MPL Indonesia', 'split': '2025 Split 2'},
    'MPL PH Season 16': {'path': 'MPL/Philippines/Season_16', 'region': 'Philippines', 'year': 2025, 'live': True, 'league': 'MPL Philippines', 'split': '2025 Split 2'},
    'MPL MY Season 16': {'path': 'MPL/Malaysia/Season_16', 'region': 'Malaysia', 'year': 2025, 'live': True, 'league': 'MPL Malaysia', 'split': '2025 Split 2'},
    'VMC 2025 Winter': {'path': 'Vietnam_MLBB_Championship/2025/Winter', 'region': 'Vietnam', 'year': 2025, 'live': True, 'league': 'VMC (Vietnam)', 'split': '2025 Split 1'},
    'MPL MENA S8': {'path': 'MPL/MENA/Season_8', 'region': 'MENA', 'year': 2025, 'live': True, 'league': 'MPL MENA', 'split': '2025 Split 2'},
    'MCC S6': {'path': 'MLBB_Continental_Championships/Season_6', 'region': 'EECA', 'year': 2025, 'live': True, 'league': 'MCC (EECA)', 'split': '2025 Split 2'},
    'China Masters 2025': {'path': 'MLBB_China_Masters/2025', 'region': 'China', 'year': 2025, 'live': True, 'league': 'China Masters', 'split': '2025 Split 2'},
    'MTC S5': {'path': 'MTC_Turkiye_Championship/Season_5', 'region': 'Turkey', 'year': 2025, 'live': True, 'league': 'MTC (Turkey)', 'split': '2025 Split 1'},
    'MPL KH Season 9': {'path': 'MPL/Cambodia/Season_9', 'region': 'Cambodia', 'year': 2025, 'live': True, 'league': 'MPL Cambodia', 'split': '2025 Split 1'},
    'MSL MM Season 2': {'path': 'MLBB_Super_League/Season_2', 'region': 'Myanmar', 'year': 2025, 'live': True, 'league': 'MSL Myanmar', 'split': '2025 Split 1'},
}
# --- MODIFICATION END ---


def clear_cache_for_live_tournaments(selected_live_keys):
    """Finds and deletes cache files and returns the count of cleared files."""
    cleared_count = 0
    for key in selected_live_keys:
        if key in ALL_TOURNAMENTS and ALL_TOURNAMENTS[key]['live']:
            tournament_path = ALL_TOURNAMENTS[key]['path']
            # Create a filename-safe version for the cache key
            cache_key = f"matches_{tournament_path.replace('/', '_')}.json"
            cache_dir = "data" # Assuming a local data cache directory
            filepath = os.path.join(cache_dir, cache_key)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    cleared_count += 1
                except Exception as e:
                    st.warning(f"Could not remove cache for {key}: {e}")
    return cleared_count

@st.cache_data(ttl=3600)
def fetch_from_api(tournament_path):
    """Unified function to fetch data from the Liquipedia API."""
    try:
        params = BASE_PARAMS.copy()
        params['conditions'] = f"[[parent::{tournament_path}]]"
        url = "https://api.liquipedia.net/api/v3/match"
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        return resp.json().get("result", [])
    except Exception as e:
        return {'error': str(e)}

def load_tournament_data(tournament_name):
    """Loads data from local file or fetches from API."""
    tournament_info = ALL_TOURNAMENTS[tournament_name]
    is_live = tournament_info.get('live', False)
    path = tournament_info['path']
    filename = f"{tournament_name.replace(' ', '_').replace('/', '_')}.json"
    data_dir = "data"
    filepath = os.path.join(data_dir, filename)
    os.makedirs(data_dir, exist_ok=True)

    if not is_live:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                st.toast(f"Loaded {len(data)} matches for {tournament_name} from file.", icon="📄")
                return data
        except FileNotFoundError:
            st.toast(f"Local file for {tournament_name} not found. Fetching from API...", icon="☁️")
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
    else:
        data = fetch_from_api(path)
        if isinstance(data, dict) and 'error' in data:
            st.error(f"Failed to fetch live data for {tournament_name}: {data['error']}")
            return []
        st.toast(f"Fetched {len(data)} live matches for {tournament_name} from API.", icon="📡")
        return data
