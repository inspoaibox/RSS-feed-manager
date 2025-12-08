"""Celery application configuration."""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "rss_reader",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
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
    task_time_limit=300,  # 5 minutes max per task
    worker_prefetch_multiplier=1,
    task_acks_late=True,
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
