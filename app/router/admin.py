from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User, Tenant, AuditLog, MfaFactor, Session, Webhook
from app.deps import get_tenant_from_api_key
from app.response import ok, fail
from app.metrics import compute_metrics, compute_method_breakdown, compute_avg_session_duration
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])

class StatusUpdate(BaseModel):
    status: str

@router.get("/users")
async def list_users(page: int = Query(1, ge=1), limit: int = Query(20, le=100), status: str | None = None, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.tenant_id == tenant.id)
    if status:
        query = query.where(User.status == status)
    total = await db.execute(select(func.count()).select_from(query.subquery()))
    result = await db.execute(query.offset((page - 1) * limit).limit(limit).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return ok(
        {"users": [{"id": str(u.id), "email": u.email, "status": u.status, "email_verified": u.email_verified, "mfa_enabled": u.mfa_enabled, "created_at": u.created_at.isoformat()} for u in users]},
        meta={"page": page, "limit": limit, "total": total.scalar()},
    )

@router.patch("/users/{user_id}/status")
async def update_user_status(user_id: str, body: StatusUpdate, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    if body.status not in ("active", "suspended", "banned"):
        return fail("invalid_status", "status must be active, suspended, or banned", status_code=400)
    result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()
    if not user:
        return fail("not_found", "user not found", status_code=404)
    user.status = body.status
    user.is_active = body.status == "active"
    await db.commit()
    return ok({"message": f"user status updated to {body.status}"})

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()
    if not user:
        return fail("not_found", "user not found", status_code=404)
    user.status = "deleted"
    user.is_active = False
    await db.commit()
    return ok({"message": "user deleted"})

@router.post("/users/{user_id}/reset-mfa")
async def reset_mfa(user_id: str, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id, User.tenant_id == tenant.id))
    user = result.scalar_one_or_none()
    if not user:
        return fail("not_found", "user not found", status_code=404)
    factors = await db.execute(select(MfaFactor).where(MfaFactor.user_id == user_id))
    for f in factors.scalars().all():
        await db.delete(f)
    user.mfa_enabled = False
    await db.commit()
    return ok({"message": "mfa reset for user"})

@router.get("/audit-logs")
async def audit_logs(page: int = Query(1, ge=1), limit: int = Query(50, le=200), action: str | None = None, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    query = select(AuditLog).where(AuditLog.tenant_id == tenant.id)
    if action:
        query = query.where(AuditLog.action == action)
    result = await db.execute(query.order_by(AuditLog.created_at.desc()).offset((page - 1) * limit).limit(limit))
    logs = result.scalars().all()
    return ok({"logs": [
        {"id": str(l.id), "user_id": str(l.user_id) if l.user_id else None, "action": l.action, "ip": l.ip_address, "created_at": l.created_at.isoformat(), "meta": l.metadata_json}
        for l in logs
    ]})

@router.get("/metrics")
async def metrics(tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    base = await compute_metrics(db, tenant.id)
    base["auth_method_breakdown"] = await compute_method_breakdown(db, tenant.id)
    base["avg_session_duration_seconds"] = await compute_avg_session_duration(db, tenant.id)
    return ok(base)



class WebhookCreate(BaseModel):
    url: str
    events: list[str]

@router.post("/webhooks")
async def create_webhook(body: WebhookCreate, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    hook = Webhook(tenant_id=tenant.id, url=body.url, events=",".join(body.events))
    db.add(hook)
    await db.commit()
    return ok({"id": str(hook.id)}, status_code=201)

@router.get("/webhooks")
async def list_webhooks(tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Webhook).where(Webhook.tenant_id == tenant.id))
    hooks = result.scalars().all()
    return ok({"webhooks": [{"id": str(h.id), "url": h.url, "events": h.events.split(","), "active": h.active} for h in hooks]})

@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id, Webhook.tenant_id == tenant.id))
    hook = result.scalar_one_or_none()
    if not hook:
        return fail("not_found", "webhook not found", status_code=404)
    await db.delete(hook)
    await db.commit()
    return ok({"message": "webhook deleted"})
    
    
    
    
@router.get("/siem-export")
async def siem_export(since: str | None = None, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone, timedelta
    since_dt = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(hours=1)
    result = await db.execute(select(AuditLog).where(AuditLog.tenant_id == tenant.id, AuditLog.created_at >= since_dt).order_by(AuditLog.created_at.asc()).limit(1000))
    logs = result.scalars().all()
    return ok({"events": [
        {"id": str(l.id), "timestamp": l.created_at.isoformat(), "action": l.action, "user_id": str(l.user_id) if l.user_id else None, "ip": l.ip_address, "user_agent": l.user_agent, "metadata": l.metadata_json}
        for l in logs
    ]})