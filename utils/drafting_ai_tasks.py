# utils/drafting_ai_tasks.py

from celery_config import app
from utils.drafting_ai import train_and_save_prediction_model
from utils.hero_data import HERO_PROFILES

@app.task(bind=True)
def train_ai_model_task(self, matches_data):
    """
    A Celery task to train the AI model in the background.
    'bind=True' allows us to access task metadata, like its ID.
    """
    try:
        # The existing training function is called here. This is the core of the task.
        feedback = train_and_save_prediction_model(
            matches=matches_data,
            hero_profiles=HERO_PROFILES
        )
        # If successful, return a dictionary with the results.
        return {'status': 'Complete!', 'result': feedback}
    except Exception as e:
        # If an error occurs, update the task's state to FAILURE.
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        return {'status': 'Failed', 'result': str(e)}
