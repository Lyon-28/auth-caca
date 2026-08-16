from celery import Celery
from app.config import settings
import app.celery_beat

celery_app = Celery("caca_auth", broker=settings.celery_broker_url)
celery_app.conf.task_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "UTC"