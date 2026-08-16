from celery.schedules import crontab
from app.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "cleanup-expired-tokens": {"task": "cleanup_expired_tokens", "schedule": crontab(minute=0)},
    "cleanup-expired-sessions": {"task": "cleanup_expired_sessions", "schedule": crontab(minute=30)},
    "hard-delete-grace-expired": {"task": "hard_delete_grace_expired", "schedule": crontab(minute=0, hour=3)},
}