# utils/drafting_ai_tasks.py
import os
import cloudinary
import cloudinary.uploader
from celery_config import app
from utils.drafting_ai import train_and_save_prediction_model
from utils.hero_data import HERO_PROFILES

# Configure Cloudinary using environment variables/secrets
cloudinary.config(
  cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
  api_key = os.environ.get("CLOUDINARY_API_KEY"),
  api_secret = os.environ.get("CLOUDINARY_API_SECRET"),
  secure = True
)

@app.task(bind=True)
def train_ai_model_task(self, matches_data):
    """
    A Celery task to train the AI model and upload the results to cloud storage.
    """
    try:
        model_filename = "draft_predictor.json"
        assets_filename = "draft_assets.json"

        # Step 1: Train the model and save files locally (on the worker)
        feedback = train_and_save_prediction_model(
            matches=matches_data,
            hero_profiles=HERO_PROFILES,
            model_filename=model_filename,
            assets_filename=assets_filename
        )

        # Step 2: Upload the generated files to Cloudinary
        self.update_state(state='PROGRESS', meta={'status': 'Uploading model files...'})
        
        # Upload the model file
        model_upload_result = cloudinary.uploader.upload(
            model_filename,
            resource_type="raw", # Important for .json files
            public_id=model_filename,
            overwrite=True
        )
        
        # Upload the assets file
        assets_upload_result = cloudinary.uploader.upload(
            assets_filename,
            resource_type="raw",
            public_id=assets_filename,
            overwrite=True
        )

        # Step 3: Return the public URLs for downloading
        return {
            'status': 'Complete!', 
            'result': feedback,
            'download_urls': {
                'model_url': model_upload_result.get('secure_url'),
                'assets_url': assets_upload_result.get('secure_url')
            }
        }
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        return {'status': 'Failed', 'result': str(e)}
