import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from app.database import SessionLocal
from app.models import Token, Session, User
from app.config import settings
from app.celery_app import celery_app
from app.notify.email import send_email
from app.notify.sms import send_sms
from app.webhooks import dispatch_event

@celery_app.task(name="send_email_task", bind=True, max_retries=3, default_retry_delay=10)
def send_email_task(self, to: str, subject: str, html: str):
    try:
        asyncio.run(send_email(to, subject, html))
    except Exception as exc:
        raise self.retry(exc=exc)
        
@celery_app.task(name="send_sms_task", bind=True, max_retries=3, default_retry_delay=10)
def send_sms_task(self, to: str, message: str):
    try:
        asyncio.run(send_sms(to, message))
    except Exception as exc:
        raise self.retry(exc=exc)
        
@celery_app.task(name="cleanup_expired_tokens")
def cleanup_expired_tokens():
    asyncio.run(_cleanup_expired_tokens())

async def _cleanup_expired_tokens():
    async with SessionLocal() as db:
        await db.execute(delete(Token).where(Token.expires_at < datetime.now(timezone.utc)))
        await db.commit()

@celery_app.task(name="cleanup_expired_sessions")
def cleanup_expired_sessions():
    asyncio.run(_cleanup_expired_sessions())

async def _cleanup_expired_sessions():
    async with SessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.refresh_token_expire_days)
        await db.execute(delete(Session).where(Session.created_at < cutoff))
        await db.commit()

@celery_app.task(name="hard_delete_grace_expired")
def hard_delete_grace_expired():
    asyncio.run(_hard_delete_grace_expired())

async def _hard_delete_grace_expired():
    async with SessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.deactivation_grace_days)
        result = await db.execute(select(User).where(User.status == "deactivated", User.deactivated_at < cutoff))
        for user in result.scalars().all():
            user.status = "deleted"
            user.deleted_at = datetime.now(timezone.utc)
            user.email = f"deleted_{user.id}@deleted.caca-auth.local"
            user.phone = None
            user.password_hash = None
        await db.commit()
        
@celery_app.task(name="dispatch_webhook_task")
def dispatch_webhook_task(tenant_id: str, event: str, data: dict):
    asyncio.run(dispatch_event(tenant_id, event, data))