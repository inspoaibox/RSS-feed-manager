"""Celery application configuration."""
import os

from celery import Celery
from celery.schedules import crontab

# Read REDIS_URL directly from environment to avoid caching issues
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "rss_reader",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.feed_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=10800,  # 3 hours max per task (for large embedding jobs)
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_default_queue="celery",
    task_routes={
        "app.tasks.feed_tasks.execute_custom_rule": {"queue": "feed"},
        "app.tasks.feed_tasks.translate_article": {"queue": "translation"},
    },
)

# Periodic tasks (beat schedule)
celery_app.conf.beat_schedule = {
    "check-feeds-due-for-refresh": {
        "task": "app.tasks.feed_tasks.refresh_due_feeds",
        "schedule": 60.0,  # Check every minute for feeds that need refresh
    },
    "execute-custom-rules": {
        "task": "app.tasks.feed_tasks.execute_all_custom_rules",
        "schedule": 60.0,  # Check every minute for rules that need execution
    },
    "cleanup-old-articles": {
        "task": "app.tasks.feed_tasks.cleanup_old_articles",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    },
}
