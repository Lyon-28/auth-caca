from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Session, User, Tenant
from app.deps import get_current_user, get_tenant_from_api_key
from app.response import ok, fail
from app.redis_client import redis

router = APIRouter(prefix="/auth/sessions", tags=["sessions"])

@router.get("")
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.user_id == user.id, Session.revoked == False))
    sessions = result.scalars().all()
    return ok({"sessions": [
        {
            "id": str(s.id),
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "location": s.location,
            "last_active_at": s.last_active_at.isoformat(),
            "created_at": s.created_at.isoformat(),
        } for s in sessions
    ]})

@router.delete("/{session_id}")
async def revoke_session(session_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id, Session.user_id == user.id))
    session = result.scalar_one_or_none()
    if not session:
        return fail("session_not_found", "session not found", status_code=404)
    session.revoked = True
    await redis.set(f"bl:{session.refresh_token_id}", "1", ex=60 * 60 * 24 * 7)
    await db.commit()
    return ok({"message": "session revoked"})

@router.delete("")
async def revoke_all_sessions(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.user_id == user.id, Session.revoked == False))
    sessions = result.scalars().all()
    for s in sessions:
        s.revoked = True
        await redis.set(f"bl:{s.refresh_token_id}", "1", ex=60 * 60 * 24 * 7)
    await db.commit()
    return ok({"message": f"{len(sessions)} session(s) revoked"})