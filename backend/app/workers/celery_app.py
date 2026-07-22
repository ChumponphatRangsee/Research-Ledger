from celery import Celery

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
    # Phase-one MVP requires every analysis to originate from an authenticated user.
    # A global scheduled screener has no JWT identity, so it must not enqueue pipelines.
    beat_schedule={},
)
