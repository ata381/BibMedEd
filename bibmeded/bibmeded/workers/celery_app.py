from celery import Celery
from bibmeded.config import settings

celery_app = Celery(
    "bibmeded",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["bibmeded.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)
