from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Tenant, IPRule
from app.deps import get_platform_admin
from app.response import ok, fail
from pydantic import BaseModel

router = APIRouter(prefix="/platform", tags=["platform"])

class IPRuleCreate(BaseModel):
    ip_address: str
    rule_type: str
    reason: str | None = None

@router.get("/tenants")
async def list_tenants(page: int = Query(1, ge=1), limit: int = Query(20, le=100), admin: Tenant = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    total = await db.execute(select(func.count(Tenant.id)))
    result = await db.execute(select(Tenant).offset((page - 1) * limit).limit(limit).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()
    return ok(
        {"tenants": [{"id": str(t.id), "name": t.name, "email": t.email, "created_at": t.created_at.isoformat()} for t in tenants]},
        meta={"page": page, "limit": limit, "total": total.scalar()},
    )

@router.get("/ip-rules")
async def list_ip_rules(admin: Tenant = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(IPRule).order_by(IPRule.created_at.desc()))
    rules = result.scalars().all()
    return ok({"rules": [{"id": str(r.id), "ip_address": r.ip_address, "rule_type": r.rule_type, "reason": r.reason} for r in rules]})

@router.post("/ip-rules")
async def create_ip_rule(body: IPRuleCreate, admin: Tenant = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    if body.rule_type not in ("allow", "block"):
        return fail("invalid_rule_type", "rule_type must be allow or block", status_code=400)
    rule = IPRule(ip_address=body.ip_address, rule_type=body.rule_type, reason=body.reason)
    db.add(rule)
    await db.commit()
    return ok({"id": str(rule.id)}, status_code=201)

@router.delete("/ip-rules/{rule_id}")
async def delete_ip_rule(rule_id: str, admin: Tenant = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(IPRule).where(IPRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        return fail("not_found", "rule not found", status_code=404)
    await db.delete(rule)
    await db.commit()
    return ok({"message": "rule deleted"})