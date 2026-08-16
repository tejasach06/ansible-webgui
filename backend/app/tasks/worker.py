from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "ansible_webgui",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.run_job", "app.tasks.notify"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    redbeat_redis_url=settings.REDIS_URL
)
