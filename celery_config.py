import os
from celery import Celery
import streamlit as st

# Default to a local Redis server if the secret is not available
# This allows for local testing without needing to connect to the cloud service.
# We will replace this with your actual Upstash URL from Streamlit secrets later.
REDIS_URL = st.secrets.get("REDIS_URL", "redis://localhost:6379/0")

# Create the Celery app instance
# The 'broker' tells Celery where to send and receive messages (our Redis queue).
# The 'backend' is where Celery stores the results of the tasks.
app = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Optional configuration to ensure tasks and results are handled securely.
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# This line tells Celery to look for task definitions in these files.
# We will create tasks in these files in the upcoming steps.
app.autodiscover_tasks(
    packages=[
        'utils.drafting_ai_tasks',  # We will create this file later
        'utils.simulation_tasks'     # We will create this file later
    ]
)
