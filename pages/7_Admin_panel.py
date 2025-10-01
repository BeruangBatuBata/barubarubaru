import streamlit as st
from utils.drafting_ai import train_and_save_prediction_model
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
    
    # --- Model Training Section ---
    st.header("AI Model Training")
    st.info("Use this tool to re-train the Drafting Assistant's AI model using the tournament data currently loaded in the application.")
    st.warning("Training a new model can take several minutes and will replace the existing AI model.", icon="⚠️")

    if 'model_path_to_download' not in st.session_state:
        st.session_state.model_path_to_download = None
    if 'assets_path_to_download' not in st.session_state:
        st.session_state.assets_path_to_download = None

    if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
        st.error("No tournament data loaded. Please go to the Overview page, select tournaments, and click 'Load Data' before training.")
    else:
        st.success(f"**{len(st.session_state['pooled_matches'])}** matches are loaded and ready for training.")

        if st.button("Train New AI Model", type="primary"):
            st.session_state.model_path_to_download = None
            st.session_state.assets_path_to_download = None

            try:
                with st.spinner("Training AI model and saving files..."):
                    model_filepath = "draft_predictor.json"
                    assets_filepath = "draft_assets.json"
                    feedback = train_and_save_prediction_model(
                        st.session_state['pooled_matches'],
                        HERO_PROFILES,
                        model_filename=model_filepath,
                        assets_filename=assets_filepath
                    )
                    st.session_state.model_path_to_download = model_filepath
                    st.session_state.assets_path_to_download = assets_filepath
                st.success(feedback)
            except Exception as e:
                st.error(f"An error occurred during training: {e}")

    if st.session_state.model_path_to_download and st.session_state.assets_path_to_download:
        st.subheader("Download New Model Files")
        st.info("Download both files, upload them to your GitHub repository, then reboot the app to apply the changes.")
        try:
            with open(st.session_state.model_path_to_download, "rb") as fp:
                model_data = fp.read()
            with open(st.session_state.assets_path_to_download, "rb") as fp:
                assets_data = fp.read()

            col1, col2 = st.columns(2)
            col1.download_button(
                label="📥 Download draft_predictor.json",
                data=model_data,
                file_name="draft_predictor.json",
                mime="application/json",
            )
            col2.download_button(
                label="📥 Download draft_assets.json",
                data=assets_data,
                file_name="draft_assets.json",
                mime="application/json",
            )
        except FileNotFoundError:
            st.error("Could not find the model files to offer for download. Please try training again.")

    st.markdown("---")

    # --- Configuration Management Section ---
    st.header("Tournament Configuration Management")
    st.info("Download the current configurations for a tournament to save them permanently in your GitHub repository.")

    all_tournaments = list(ALL_TOURNAMENTS.keys())
    selected_tournament = st.selectbox("Select a tournament to manage:", all_tournaments)

    if selected_tournament:
        if st.button("View & Download Configuration"):
            config_data = load_unified_config(selected_tournament)
            
            st.subheader(f"Current Configuration for: {selected_tournament}")
            
            # Display Format
            st.write(f"**Format:** `{config_data.get('format', 'N/A')}`")

            # Display Groups
            st.write("**Groups:**")
            if config_data.get('groups'):
                st.json(config_data['groups'])
            else:
                st.write("No groups configured.")

            # Display Brackets
            st.write("**Brackets:**")
            if config_data.get('brackets'):
                for bracket in config_data['brackets']:
                    st.write(f"- **{bracket.get('name', 'Unnamed')}**: Ranks {bracket.get('start', '?')} to {bracket.get('end', '?')}")
            else:
                st.write("No brackets configured.")

            # Prepare for download
            json_string = json.dumps(config_data, indent=2)
            zip_buffer = io.BytesIO()
            
            file_name = f"{selected_tournament.replace(' ', '_')}.json"

            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                zip_file.writestr(file_name, json_string)
            
            st.download_button(
                label=f"📥 Download Configs as .zip",
                data=zip_buffer.getvalue(),
                file_name=f"{selected_tournament.replace(' ', '_')}_configs.zip",
                mime="application/zip",
            )
