import os
from celery import Celery
# We no longer need to import streamlit here

# This is the key change. We now read the REDIS_URL directly from the
# environment variables of the worker, which you set on Railway.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# The rest of the file remains exactly the same.
app = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

app.autodiscover_tasks(
    packages=[
        'utils.drafting_ai_tasks',
        'utils.simulation_tasks'
    ]
)
