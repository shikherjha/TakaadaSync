from celery import Celery
from celery.schedules import crontab

from src.config import REDIS_URL, SYNC_INTERVAL_SECONDS

celery_app = Celery(
    "takaada",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.tasks.sync_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "sync-external-data": {
            "task": "src.tasks.sync_tasks.sync_all_data",
            "schedule": SYNC_INTERVAL_SECONDS,
        },
    },
)
