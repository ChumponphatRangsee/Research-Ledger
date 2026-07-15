from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "investflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "daily-stock-screener": {
            "task": "app.workers.tasks.run_daily_screener",
            "schedule": crontab(
                hour=settings.screener_cron_hour,
                minute=settings.screener_cron_minute,
            ),
        },
    },
)
