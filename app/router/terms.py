from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import TermsVersion, TermsAcceptance, User, Tenant
from app.deps import get_current_user, get_tenant_from_api_key
from app.response import ok, fail
from pydantic import BaseModel

router = APIRouter(prefix="/terms", tags=["terms"])

class TermsCreate(BaseModel):
    version: str
    content_url: str

class TermsAccept(BaseModel):
    terms_version_id: str

@router.post("")
async def create_terms(body: TermsCreate, tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    terms = TermsVersion(tenant_id=tenant.id, version=body.version, content_url=body.content_url)
    db.add(terms)
    await db.commit()
    return ok({"id": str(terms.id), "version": terms.version}, status_code=201)

@router.get("/latest")
async def latest_terms(tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TermsVersion).where(TermsVersion.tenant_id == tenant.id).order_by(TermsVersion.created_at.desc()))
    terms = result.scalars().first()
    if not terms:
        return fail("not_found", "no terms configured", status_code=404)
    return ok({"id": str(terms.id), "version": terms.version, "content_url": terms.content_url})

@router.get("/status")
async def terms_status(user: User = Depends(get_current_user), tenant: Tenant = Depends(get_tenant_from_api_key), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TermsVersion).where(TermsVersion.tenant_id == tenant.id).order_by(TermsVersion.created_at.desc()))
    latest = result.scalars().first()
    if not latest:
        return ok({"accepted": True, "reason": "no_terms_configured"})
    accepted = await db.execute(select(TermsAcceptance).where(TermsAcceptance.user_id == user.id, TermsAcceptance.terms_version_id == latest.id))
    return ok({"accepted": bool(accepted.scalar_one_or_none()), "latest_version": latest.version, "terms_version_id": str(latest.id)})

@router.post("/accept")
async def accept_terms(body: TermsAccept, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(TermsAcceptance).where(TermsAcceptance.user_id == user.id, TermsAcceptance.terms_version_id == body.terms_version_id))
    if existing.scalar_one_or_none():
        return ok({"message": "already accepted"})
    db.add(TermsAcceptance(user_id=user.id, terms_version_id=body.terms_version_id))
    await db.commit()
    return ok({"message": "terms accepted"}, status_code=201)