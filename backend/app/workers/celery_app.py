import os
from celery import Celery
from kombu import Exchange, Queue

from backend.app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "fbr_invoice_cloud",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

default_exchange = Exchange("fbr_default", type="direct")

celery_app.conf.update(
    task_default_queue="default",
    task_queues=(
        Queue("default", default_exchange, routing_key="default"),
        Queue("fbr_submission", default_exchange, routing_key="fbr_submission"),
        Queue("pdf_generation", default_exchange, routing_key="pdf_generation"),
        Queue("reports", default_exchange, routing_key="reports"),
        Queue("notifications", default_exchange, routing_key="notifications"),
        Queue("maintenance", default_exchange, routing_key="maintenance"),
    ),
    task_routes={
        "backend.app.workers.tasks.submit_invoice_to_fbr_task": {"queue": "fbr_submission"},
        "backend.app.workers.tasks.generate_invoice_pdf_task": {"queue": "pdf_generation"},
        "backend.app.workers.tasks.send_notification_task": {"queue": "notifications"},
        "backend.app.workers.tasks.reap_stale_jobs_task": {"queue": "maintenance"},
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 min max
    task_soft_time_limit=240,  # 4 min soft
    worker_prefetch_multiplier=1,  # Prevent worker starving other workers
    worker_max_tasks_per_child=1000,
)
