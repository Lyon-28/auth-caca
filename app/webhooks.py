import hmac
import hashlib
import json
import httpx
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Webhook
from app.config import settings
from app.logger import log

def sign_payload(payload: bytes) -> str:
    return hmac.new(settings.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()

async def dispatch_event(tenant_id, event: str, data: dict):
    async with SessionLocal() as db:
        result = await db.execute(select(Webhook).where(Webhook.tenant_id == tenant_id, Webhook.active == True))
        hooks = [w for w in result.scalars().all() if event in w.events.split(",")]

    if not hooks:
        return

    body = json.dumps({"event": event, "data": data}).encode()
    signature = sign_payload(body)
    async with httpx.AsyncClient(timeout=10) as client:
        for hook in hooks:
            try:
                await client.post(hook.url, content=body, headers={"Content-Type": "application/json", "X-Caca-Signature": signature})
            except Exception as e:
                log("warning", "webhook_delivery_failed", url=hook.url, error=str(e))