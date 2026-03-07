"""
Celery application configuration for background task processing.

This module initializes the Celery app for running validation tasks asynchronously.
"""

from celery import Celery
from app.config import settings

# Initialize Celery app
celery_app = Celery(
    "ethical_ai_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.validation_tasks", "app.tasks.scheduled_tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    result_expires=86400,  # Results expire after 24 hours
)

# Task routing (optional - for multiple queues)
celery_app.conf.task_routes = {
    "app.tasks.validation_tasks.run_fairness_validation_task": {"queue": "validations"},
    "app.tasks.validation_tasks.run_transparency_validation_task": {"queue": "validations"},
    "app.tasks.validation_tasks.run_privacy_validation_task": {"queue": "validations"},
    "app.tasks.validation_tasks.run_all_validations_task": {"queue": "validations"},
    "app.tasks.scheduled_tasks.run_scheduled_validations": {"queue": "validations"},
    "app.tasks.scheduled_tasks.check_metric_regression": {"queue": "validations"},
}

# Celery Beat schedule — fires the scheduled-validation scanner every 5 minutes
celery_app.conf.beat_schedule = {
    "scan-scheduled-validations": {
        "task": "run_scheduled_validations",
        "schedule": 300.0,  # every 5 minutes
    },
}
