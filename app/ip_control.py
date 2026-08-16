from fastapi import Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import IPRule
from app.redis_client import redis
from app.config import settings

async def check_ip_blacklist(request: Request, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    result = await db.execute(select(IPRule).where(IPRule.ip_address == ip, IPRule.rule_type == "block"))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail={"code": "ip_blocked", "message": "your ip has been blocked"})

async def register_ip_failure(db: AsyncSession, ip: str, reason: str):
    key = f"ipfail:{ip}"
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, settings.ip_blacklist_window_seconds)
    if current >= settings.ip_blacklist_threshold:
        existing = await db.execute(select(IPRule).where(IPRule.ip_address == ip, IPRule.rule_type == "block"))
        if not existing.scalar_one_or_none():
            db.add(IPRule(ip_address=ip, rule_type="block", reason=reason))
            await db.commit()