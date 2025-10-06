import streamlit as st
from utils.drafting_ai_tasks import train_ai_model_task # <-- IMPORT THE NEW TASK
from celery.result import AsyncResult # <-- IMPORT FOR CHECKING RESULTS
from utils.hero_data import HERO_PROFILES
from utils.sidebar import build_sidebar
import os
import json
import zipfile
import io
from utils.tournaments import ALL_TOURNAMENTS
from utils.simulation import load_unified_config

# --- Page Configuration ---
st.set_page_config(layout="wide", page_title="Admin Panel")
build_sidebar()

# --- Authentication Logic ---
def check_password():
    """Returns `True` if the user had a correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if (
            st.session_state["username"] in ["admin", "beruang"]
            and st.session_state["password"] == "batu"
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Username", on_change=password_entered, key="username")
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Username", on_change=password_entered, key="username")
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 User not known or password incorrect")
        return False
    else:
        return True

# --- Main Page Content ---
st.title("👑 Admin Panel")

if check_password():
    st.success("Login successful!")
    
    # --- SECTION 1: AI MODEL TRAINING (MODIFIED) ---
    st.header("AI Model Training")
    st.info("Use this tool to re-train the Drafting Assistant's AI model using the tournament data currently loaded in the application.")
    st.warning("Training a new model can take several minutes. It will run in the background.", icon="⚠️")

    if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
        st.error("No tournament data loaded. Please go to the Overview page, select tournaments, and click 'Load Data' before training.")
    else:
        st.success(f"**{len(st.session_state['pooled_matches'])}** matches are loaded and ready for training.")

        if st.button("Train New AI Model (in Background)", type="primary"):
            with st.spinner("Sending training job to the kitchen..."):
                # Send the training job to the Celery queue
                task = train_ai_model_task.delay(st.session_state['pooled_matches'])
                st.session_state['last_task_id'] = task.id
                st.success(f"✅ Training job sent successfully! Task ID: {task.id}")
                st.info("You can monitor the status below or enter a Task ID to check on a previous job.")

    # --- NEW SECTION: TASK MONITORING ---
    st.markdown("---")
    st.header("Task Monitoring")
    task_id_input = st.text_input("Enter Task ID to check status:", value=st.session_state.get('last_task_id', ''))

    if st.button("Check Status"):
        if task_id_input:
            result = AsyncResult(task_id_input)
            st.write(f"**Status for Task ID:** `{task_id_input}`")
            if result.ready():
                if result.successful():
                    st.success(f"**Status:** {result.state}")
                    st.write("**Result:**")
                    st.json(result.result)
                else:
                    st.error(f"**Status:** {result.state}")
                    st.write("**Error:**")
                    st.json(result.info)
            else:
                st.info(f"**Status:** {result.state} (Running...)")
        else:
            st.warning("Please enter a Task ID to check.")

    # --- SECTION 3: DOWNLOAD AND CONFIG (UNCHANGED) ---
    st.markdown("---")
    st.header("Download Trained Model Files")
    st.info("Once a training task completes, the new model files (`draft_predictor.json`, `draft_assets.json`) are saved on the worker's disk. Future updates could add functionality to retrieve these files from a shared cloud storage location.")
    # For now, this section remains a placeholder.
    
    st.markdown("---")

    st.header("Tournament Configuration Management")
    st.info("Select tournaments, preview their current configurations one-by-one, and download them as a single zip file.")

    all_tournaments = list(ALL_TOURNAMENTS.keys())

    if 'config_selections' not in st.session_state:
        st.session_state.config_selections = {name: False for name in all_tournaments}
    if 'preview_index' not in st.session_state:
        st.session_state.preview_index = 0

    with st.expander("Select Tournaments to Download"):
        col1, col2 = st.columns(2)
        if col1.button("Select All", key="select_all_configs"):
            for t_name in all_tournaments:
                st.session_state.config_selections[t_name] = True
            st.session_state.preview_index = 0
        if col2.button("Deselect All", key="deselect_all_configs"):
            for t_name in all_tournaments:
                st.session_state.config_selections[t_name] = False
            st.session_state.preview_index = 0
        
        st.markdown("---")
        for t_name in all_tournaments:
            if st.checkbox(t_name, value=st.session_state.config_selections.get(t_name, False), key=f"config_chk_{t_name}"):
                if not st.session_state.config_selections[t_name]:
                    st.session_state.config_selections[t_name] = True
                    st.session_state.preview_index = 0
            else:
                if st.session_state.config_selections[t_name]:
                    st.session_state.config_selections[t_name] = False
                    st.session_state.preview_index = 0

    selected_configs = [name for name, selected in st.session_state.config_selections.items() if selected]

    if selected_configs:
        if st.session_state.preview_index >= len(selected_configs):
            st.session_state.preview_index = 0
            
        current_tournament_to_preview = selected_configs[st.session_state.preview_index]
        config_data = load_unified_config(current_tournament_to_preview)

        st.subheader(f"Previewing Configuration ({st.session_state.preview_index + 1} of {len(selected_configs)})")
        st.write(f"**Tournament:** `{config_data.get('tournament_name', 'N/A')}`")
        st.write(f"**Format:** `{config_data.get('format', 'N/A')}`")

        st.write("**Groups:**")
        if config_data.get('groups'):
            st.json(config_data['groups'])
        else:
            st.write("No groups configured.")

        st.write("**Brackets:**")
        if config_data.get('brackets'):
            for bracket in config_data['brackets']:
                st.write(f"- **{bracket.get('name', 'Unnamed')}**: Ranks {bracket.get('start', '?')} to {bracket.get('end', '?')}")
        else:
            st.write("No brackets configured.")
            
        nav_cols = st.columns([1, 1, 5])
        with nav_cols[0]:
            if st.button("⬅️ Previous", disabled=(st.session_state.preview_index <= 0)):
                st.session_state.preview_index -= 1
                st.rerun()
        with nav_cols[1]:
            if st.button("Next ➡️", disabled=(st.session_state.preview_index >= len(selected_configs) - 1)):
                st.session_state.preview_index += 1
                st.rerun()
        
        st.markdown("---")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for tournament_name in selected_configs:
                config_data = load_unified_config(tournament_name)
                json_string = json.dumps(config_data, indent=2)
                file_name = f"{tournament_name.replace(' ', '_')}.json"
                zip_file.writestr(file_name, json_string)
        
        st.download_button(
            label=f"Download {len(selected_configs)} Selected Configs as .zip",
            data=zip_buffer.getvalue(),
            file_name="tournament_configs.zip",
            mime="application/zip",
        )
    else:
        st.info("Select one or more tournaments to preview and download their configurations.")
