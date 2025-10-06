# utils/drafting_ai_tasks.py

from celery_config import app
from utils.drafting_ai import train_and_save_prediction_model
from utils.hero_data import HERO_PROFILES

@app.task(bind=True)
def train_ai_model_task(self, matches_data):
    """
    A Celery task to train the AI model in the background.
    """
    try:
        # NOTE: We need to pass HERO_PROFILES to the training function
        feedback = train_and_save_prediction_model(
            matches=matches_data,
            hero_profiles=HERO_PROFILES
        )
        return {'status': 'Complete!', 'result': feedback}
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        return {'status': 'Failed', 'result': str(e)}# utils/drafting_ai_tasks.py

from celery_config import app
from utils.drafting_ai import train_and_save_prediction_model
from utils.hero_data import HERO_PROFILES

@app.task(bind=True)
def train_ai_model_task(self, matches_data):
    """
    A Celery task to train the AI model in the background.
    """
    try:
        # NOTE: We need to pass HERO_PROFILES to the training function
        feedback = train_and_save_prediction_model(
            matches=matches_data,
            hero_profiles=HERO_PROFILES
        )
        return {'status': 'Complete!', 'result': feedback}
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        return {'status': 'Failed', 'result': str(e)}
