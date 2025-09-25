# In pages/7_Admin_Panel.py

import streamlit as st
from utils.drafting_ai import train_and_save_prediction_model
from utils.data_processing import HERO_PROFILES, HERO_DAMAGE_TYPE

st.set_page_config(layout="wide", page_title="Admin Panel")

st.title("👑 Admin Panel")
st.warning("This page is for advanced users. Training a new model can take several minutes and will replace the existing AI model.", icon="⚠️")

st.markdown("---")
st.header("AI Model Training")
st.info("Use this tool to re-train the Drafting Assistant's AI model using the tournament data currently loaded in the application.")

# Check if data is loaded
if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.error("No tournament data loaded. Please go to the homepage, select tournaments, and click 'Load Data' before training.")
else:
    st.success(f"**{len(st.session_state['pooled_matches'])}** matches are loaded and ready for training.")
    
    if st.button("Train New AI Model", type="primary"):
        try:
            with st.spinner("Training AI model... This may take a minute. Please do not navigate away."):
                feedback = train_and_save_prediction_model(
                    st.session_state['pooled_matches'],
                    HERO_PROFILES
                )
            st.success(feedback)
            st.info("The new model is now saved. Please upload the 'draft_predictor.json' and 'draft_assets.json' files to your repository and reboot the app to use it.")
        except Exception as e:
            st.error(f"An error occurred during training: {e}")
