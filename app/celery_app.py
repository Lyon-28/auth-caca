from celery import Celery
from app.config import settings

celery_app = Celery("caca_auth", broker=settings.celery_broker_url)
celery_app.conf.task_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "UTC"

# Import beat schedule SETELAH celery_app didefinisikan, supaya celery_beat.py
# bisa import celery_app tanpa circular import.
import app.celery_beat  # noqa: E402,F401
