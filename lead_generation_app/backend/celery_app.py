import os
from celery import Celery

# Use SQS as broker (your sandbox has SQS, no Redis needed)
# Falls back to Redis if SQS not configured
SQS_URL = os.environ.get("SQS_URL", "")
REDIS_URL = os.environ.get("CELERY_BROKER_URL", "")

if SQS_URL:
    # Extract queue name from URL
    queue_name = SQS_URL.rstrip('/').split('/')[-1]
    region = os.environ.get("AWS_REGION", "us-east-1")

    BROKER_URL = f"sqs://"
    BROKER_TRANSPORT_OPTIONS = {
        "region": region,
        "queue_name_prefix": "",
        "wait_time_seconds": 10,
        "polling_interval": 0.5,
    }
    CELERY_BROKER_URL = BROKER_URL
else:
    CELERY_BROKER_URL = REDIS_URL or "redis://localhost:6379/0"
    BROKER_TRANSPORT_OPTIONS = {}

RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

celery_app = Celery(
    "lead_generation_tasks",
    broker=CELERY_BROKER_URL,
    backend=RESULT_BACKEND,
    include=["lead_generation_app.backend.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_transport_options=BROKER_TRANSPORT_OPTIONS,
)

# Route tasks to separate SQS queues for parallel processing
celery_app.conf.task_routes = {
    "phase_1_gmaps_scrape": {"queue": "scrape"},
    "phase_2_enrichment": {"queue": "enrich"},
    "phase_2_enrichment_batch": {"queue": "enrich"},
    "phase_3_email_verification": {"queue": "email"},
}

# Auto-create queues if using SQS
if SQS_URL:
    celery_app.conf.task_create_missing_queues = True
