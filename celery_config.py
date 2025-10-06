import os
from celery import Celery
import streamlit as st

# This line will securely pull the Redis URL you store in your Streamlit/Railway secrets.
# It defaults to a local Redis server for testing if the secret isn't found.
REDIS_URL = st.secrets.get("REDIS_URL", "redis://localhost:6379/0")

# Create the Celery app instance.
# 'broker' is the "order ticket system" (where to send jobs).
# 'backend' is the "serving counter" (where to get results).
app = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Standard configuration for security and reliability.
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# This important line tells Celery where to look for your task definitions ("recipes").
# We will create these files in the next phases.
app.autodiscover_tasks(
    packages=[
        'utils.drafting_ai_tasks',
        'utils.simulation_tasks'
    ]
)
