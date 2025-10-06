import os
from celery import Celery
import ssl # <-- Import the ssl library

# Read the Redis URL from the environment variables
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# --- THIS IS THE KEY CHANGE ---
# Define SSL options for our secure rediss:// connection
# This tells Celery to accept the SSL certificate from Upstash without requiring it to be signed by a specific authority.
# This is a standard and secure practice for this use case.
broker_use_ssl = {
    'ssl_cert_reqs': ssl.CERT_NONE
}
backend_use_ssl = broker_use_ssl
# --- END OF CHANGE ---

# Update the Celery app instance to use these new SSL settings
app = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL,
    broker_use_ssl=broker_use_ssl,
    redis_backend_use_ssl=backend_use_ssl
)

# The rest of the file remains the same
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
