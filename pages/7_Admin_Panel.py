import streamlit as st
from utils.drafting_ai import train_and_save_prediction_model
from utils.data_processing import HERO_PROFILES
import os

st.set_page_config(layout="wide", page_title="Admin Panel")

st.title("👑 Admin Panel")
st.warning("This page is for advanced users. Training a new model can take several minutes.", icon="⚠️")

st.markdown("---")
st.header("AI Model Training")
st.info("Use this tool to re-train the Drafting Assistant's AI model using the tournament data currently loaded in the application.")

# Initialize state for downloads
if 'model_path_to_download' not in st.session_state:
    st.session_state.model_path_to_download = None
if 'assets_path_to_download' not in st.session_state:
    st.session_state.assets_path_to_download = None

# Check if data is loaded
if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.error("No tournament data loaded. Please go to the homepage, select tournaments, and click 'Load Data' before training.")
else:
    st.success(f"**{len(st.session_state['pooled_matches'])}** matches are loaded and ready for training.")
    
    if st.button("Train New AI Model", type="primary"):
        st.session_state.model_path_to_download = None
        st.session_state.assets_path_to_download = None
        
        try:
            with st.spinner("Training AI model and saving files to server... This may take a minute."):
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

# Display Download Buttons if files have been created
if st.session_state.model_path_to_download and st.session_state.assets_path_to_download:
    st.markdown("---")
    st.subheader("Download Your New Model Files")
    st.info("Download both files, upload them to your GitHub repository, then reboot the app.")

    try:
        with open(st.session_state.model_path_to_download, "rb") as fp:
            model_data = fp.read()
        with open(st.session_state.assets_path_to_download, "rb") as fp:
            assets_data = fp.read()

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Download draft_predictor.json",
                data=model_data,
                file_name="draft_predictor.json",
                mime="application/json",
            )
        with col2:
            st.download_button(
                label="📥 Download draft_assets.json",
                data=assets_data,
                file_name="draft_assets.json",
                mime="application/json",
            )
    except FileNotFoundError:
        st.error("Could not find the newly created model files to offer for download. Please try training again.")
