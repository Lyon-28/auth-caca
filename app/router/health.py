from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.redis_client import redis
from app.response import ok, fail

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
async def health():
    return ok({"status": "up"})

@router.get("/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("select 1"))
        return ok({"status": "up"})
    except Exception as e:
        return fail("db_down", str(e), status_code=500)

@router.get("/redis")
async def health_redis():
    try:
        await redis.ping()
        return ok({"status": "up"})
    except Exception as e:
        return fail("redis_down", str(e), status_code=500)
        
@router.get("/ui-alerts/{email}")
async def ui_alerts(email: str):
    items = await redis.lrange(f"ui_alerts:{email}", 0, -1)
    return ok({"alerts": items})