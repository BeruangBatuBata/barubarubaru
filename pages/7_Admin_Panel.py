import streamlit as st
from utils.drafting_ai import train_and_save_prediction_model
from utils.data_processing import HERO_PROFILES

st.set_page_config(layout="wide", page_title="Admin Panel")

st.title("👑 Admin Panel")
st.warning("This page is for advanced users. Training a new model can take several minutes.", icon="⚠️")

st.markdown("---")
st.header("AI Model Training")
st.info("Use this tool to re-train the Drafting Assistant's AI model using the tournament data currently loaded in the application.")

# --- Initialize state for downloads ---
if 'model_data' not in st.session_state:
    st.session_state.model_data = None
if 'assets_data' not in st.session_state:
    st.session_state.assets_data = None

# Check if data is loaded
if 'pooled_matches' not in st.session_state or not st.session_state['pooled_matches']:
    st.error("No tournament data loaded. Please go to the homepage, select tournaments, and click 'Load Data' before training.")
else:
    st.success(f"**{len(st.session_state['pooled_matches'])}** matches are loaded and ready for training.")
    
    if st.button("Train New AI Model", type="primary"):
        try:
            with st.spinner("Training AI model... This may take a minute. Please do not navigate away."):
                # The function now returns the data for download
                model_data, assets_data = train_and_save_prediction_model(
                    st.session_state['pooled_matches'],
                    HERO_PROFILES
                )
                # Store the data in session state
                st.session_state.model_data = model_data
                st.session_state.assets_data = assets_data
            st.success("✅ Training complete! Your new model files are ready for download below.")
        except Exception as e:
            st.error(f"An error occurred during training: {e}")

# --- Display Download Buttons ---
if st.session_state.model_data and st.session_state.assets_data:
    st.markdown("---")
    st.subheader("Download Your New Model Files")
    st.info("Download both files, upload them to your GitHub repository, then reboot the app.")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 Download draft_predictor.json",
            data=st.session_state.model_data,
            file_name="draft_predictor.json",
            mime="application/json",
        )
    with col2:
        st.download_button(
            label="📥 Download draft_assets.json",
            data=st.session_state.assets_data,
            file_name="draft_assets.json",
            mime="application/json",
        )
